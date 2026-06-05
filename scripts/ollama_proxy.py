#!/usr/bin/env python3
"""
ollama_proxy.py -- Thin proxy for Ollama that:
  1. Injects `think: false` into every /api/chat and /api/generate request
     (prevents Qwen3 reasoning tokens from consuming the entire response)
  2. Caps response length via `max_tokens` / `num_predict` to avoid the
     Copilot BYOM "Response too long" hard limit.

Usage:
    python scripts/ollama_proxy.py [--port 11436] [--upstream http://localhost:11434] [--max-tokens 4096]

Point Copilot to the proxy:
    settings.json -> "github.copilot.chat.languageModel.ollama.serverUrl": "http://localhost:11436"
"""
import argparse
import http.client
import http.server
import json
import os
import sys
import urllib.parse
from datetime import datetime

INJECT_THINK_FALSE_PATHS = {"/api/chat", "/api/generate", "/v1/chat/completions"}

# Token ceiling. VS Code Copilot rejects responses with finish_reason=="length",
# so we rewrite that to "stop" (see _rewrite_finish_reason). This cap is a backstop
# only — most coding responses complete in 300-2000 tokens.
DEFAULT_MAX_TOKENS = 16384

# Log file: records every intercepted request summary for diagnostics
LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "build", "docker", "logs", "ollama_proxy.log")


def _rewrite_finish_reason(chunk: bytes) -> tuple[bytes, str | None]:
    """Scan a streaming chunk for finish_reason/done_reason == 'length' and
    rewrite it to 'stop'.  VS Code Copilot BYOM hard-rejects any response
    where finish_reason=="length"; rewriting lets it accept truncated output
    gracefully rather than surfacing "Response too long" to the user.

    Works on both OpenAI SSE format  (data: {...})  and Ollama native NDJSON.
    Assumes each SSE line fits within a single 4096-byte chunk (true in practice).
    Returns (possibly-modified chunk bytes, original finish_reason or None).
    """
    try:
        raw = chunk.decode("utf-8", errors="replace")
    except Exception:
        return chunk, None

    found_reason: str | None = None
    new_lines = []
    for line in raw.split("\n"):
        # OpenAI SSE: "data: {...}"  (skip "data: [DONE]")
        if "data: " in line and "[DONE]" not in line:
            prefix_end = line.index("data: ") + 6
            json_str = line[prefix_end:]
            prefix = line[:prefix_end]
        elif line.lstrip().startswith("{"):
            json_str = line.lstrip()
            prefix = line[: len(line) - len(line.lstrip())]
        else:
            new_lines.append(line)
            continue
        try:
            j = json.loads(json_str)
            modified = False
            # OpenAI SSE: choices[].finish_reason
            for choice in j.get("choices", []):
                if choice.get("finish_reason") == "length":
                    found_reason = "length"
                    choice["finish_reason"] = "stop"
                    modified = True
            # Ollama native NDJSON: done_reason
            if j.get("done_reason") == "length":
                found_reason = "length"
                j["done_reason"] = "stop"
                modified = True
            if modified:
                line = prefix + json.dumps(j, separators=(",", ":"))
        except (json.JSONDecodeError, ValueError):
            pass
        new_lines.append(line)

    if found_reason is not None:
        return "\n".join(new_lines).encode("utf-8"), found_reason
    return chunk, None


def _log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    print(line, end="", flush=True)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    upstream_host: str
    upstream_port: int
    upstream_scheme: str  # "http" or "https"
    max_tokens: int = DEFAULT_MAX_TOKENS

    def log_message(self, fmt, *args):  # suppress default access log noise
        pass

    def log_request_info(self, method: str, injected: bool = False):
        tag = " [think:false injected]" if injected else ""
        print(f"{method} {self.path}{tag}", flush=True)

    def _send_sse_error(self, message: str):
        """Send a well-formed OpenAI SSE error chunk so Copilot surfaces the
        error message instead of showing 'Sorry, no response was returned.'"""
        payload = json.dumps({
            "choices": [{
                "delta": {"content": f"[Proxy error: {message}]"},
                "finish_reason": "stop",
                "index": 0,
            }]
        })
        body = f"data: {payload}\n\ndata: [DONE]\n\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()

    def _forward(self, method: str, body: bytes | None, content_type: str | None, log_prefix: str = ""):
        try:
            conn = http.client.HTTPConnection(self.upstream_host, self.upstream_port, timeout=300)
        except Exception as exc:
            _log(f"ERROR  Failed to create connection to upstream: {exc}")
            if log_prefix:
                self._send_sse_error(f"upstream connection failed: {exc}")
            return

        headers = {
            k: v for k, v in self.headers.items()
            if k.lower() not in ("host", "content-length")
        }
        if body is not None:
            headers["Content-Length"] = str(len(body))
        if content_type:
            headers["Content-Type"] = content_type

        try:
            conn.request(method, self.path, body=body, headers=headers)
            resp = conn.getresponse()
        except Exception as exc:
            _log(f"ERROR  Upstream request failed ({log_prefix or self.path}): {exc}")
            try:
                self._send_sse_error(f"upstream unreachable: {exc}")
            except Exception:
                pass
            return

        upstream_status = resp.status
        if upstream_status >= 400 and log_prefix:
            # Read error body for logging, then we still forward it
            _log(f"WARN  Upstream returned HTTP {upstream_status} for {log_prefix}")

        self.send_response(upstream_status)
        for name, value in resp.getheaders():
            if name.lower() == "transfer-encoding":
                continue  # let Python handle chunking
            self.send_header(name, value)
        self.end_headers()

        # Stream response back in chunks.
        # Rewrite finish_reason=="length" -> "stop" in every chunk so VS Code
        # Copilot does not surface "Response too long" when the model is truncated.
        total_bytes = 0
        rewrote_finish = False
        finish_reason = None
        first_chunk = True
        try:
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                chunk, detected = _rewrite_finish_reason(chunk)
                if detected == "length":
                    rewrote_finish = True
                if first_chunk and log_prefix:
                    # Try to extract finish_reason from non-streaming (single JSON) response
                    try:
                        j = json.loads(chunk.decode("utf-8", errors="replace"))
                        choices = j.get("choices", [])
                        if choices:
                            finish_reason = choices[0].get("finish_reason")
                            usage = j.get("usage", {})
                            _log(f"{log_prefix} -> HTTP {upstream_status} finish_reason={finish_reason} "
                                 f"completion_tokens={usage.get('completion_tokens','?')} "
                                 f"total_tokens={usage.get('total_tokens','?')}")
                    except Exception:
                        pass
                    first_chunk = False
                total_bytes += len(chunk)
                self.wfile.write(chunk)
                self.wfile.flush()
        except Exception as exc:
            _log(f"ERROR  Stream interrupted after {total_bytes} bytes ({log_prefix or self.path}): {exc}")
        finally:
            conn.close()

        rewrite_tag = " [finish_reason:length->stop REWRITTEN]" if rewrote_finish else ""
        warn_tag = " [WARN: suspiciously small response]" if total_bytes < 500 and method == "POST" else ""
        if log_prefix and finish_reason is None:
            _log(f"{log_prefix} -> HTTP {upstream_status} streamed {total_bytes} bytes{rewrite_tag}{warn_tag}")

    def _handle(self, method: str):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw_body = self.rfile.read(length) if length > 0 else b""
        content_type = self.headers.get("Content-Type", "")

        path_only = urllib.parse.urlparse(self.path).path
        injected = False
        log_prefix = ""
        if method == "POST" and path_only in INJECT_THINK_FALSE_PATHS and raw_body:
            try:
                data = json.loads(raw_body)

                # Log what the caller sent (Copilot diagnostic)
                caller_max = data.get("max_tokens", "not-set")
                caller_think = data.get("think", "not-set")
                caller_stream = data.get("stream", "not-set")
                model = data.get("model", "?")

                # 1. Inject think:false (Ollama native endpoints)
                data["think"] = False

                # 2. Cap token output to avoid Copilot's "Response too long" error.
                # Always enforce the ceiling — Copilot BYOM sends its own max_tokens
                # (often very large), so we must override it, not just set a default.
                if path_only == "/v1/chat/completions":
                    # OpenAI-compat: max_tokens field
                    existing = data.get("max_tokens")
                    if existing is None or existing > self.max_tokens:
                        data["max_tokens"] = self.max_tokens
                else:
                    # Ollama native: options.num_predict (-1 means unlimited)
                    opts = data.setdefault("options", {})
                    existing = opts.get("num_predict")
                    if existing is None or existing < 0 or existing > self.max_tokens:
                        opts["num_predict"] = self.max_tokens

                final_max = data.get("max_tokens") or data.get("options", {}).get("num_predict", "?")
                log_prefix = (f"POST {path_only} model={model} "
                              f"caller_max_tokens={caller_max} -> capped={final_max} "
                              f"caller_think={caller_think} stream={caller_stream}")
                _log(f"REQ  {log_prefix}")

                raw_body = json.dumps(data).encode()
                content_type = "application/json"
                injected = True
            except (json.JSONDecodeError, ValueError):
                pass  # not JSON, forward as-is

        self._forward(method, raw_body, content_type, log_prefix=log_prefix)

    def do_GET(self):
        self._forward("GET", None, None)

    def do_POST(self):
        self._handle("POST")

    def do_DELETE(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length > 0 else None
        self._forward("DELETE", body, self.headers.get("Content-Type"))

    def do_HEAD(self):
        self._forward("HEAD", None, None)


def main():
    parser = argparse.ArgumentParser(description="Ollama think:false proxy")
    parser.add_argument("--port", type=int, default=11436, help="Port to listen on (default: 11436)")
    parser.add_argument("--upstream", default="http://localhost:11434", help="Ollama upstream URL")
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS,
                        help=f"Max tokens per response (default: {DEFAULT_MAX_TOKENS}). "
                             "Caps num_predict / max_tokens to avoid Copilot's response-too-long error.")
    args = parser.parse_args()

    parsed = urllib.parse.urlparse(args.upstream)
    ProxyHandler.upstream_host = parsed.hostname
    ProxyHandler.upstream_port = parsed.port or (443 if parsed.scheme == "https" else 80)
    ProxyHandler.upstream_scheme = parsed.scheme
    ProxyHandler.max_tokens = args.max_tokens

    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), ProxyHandler)
    print(f"Ollama proxy listening on http://localhost:{args.port}")
    print(f"Forwarding to {args.upstream}")
    print(f"  think:false injected | max_tokens cap: {args.max_tokens}")
    print(f'  Copilot serverUrl -> "http://localhost:{args.port}"')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nProxy stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
