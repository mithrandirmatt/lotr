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

# Copilot BYOM has a hard response-size limit; cap tokens to stay under it.
# Caller-supplied values are respected (only set if not already present).
DEFAULT_MAX_TOKENS = 4096

# Log file: records every intercepted request summary for diagnostics
LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "build", "docker", "logs", "ollama_proxy.log")


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

    def _forward(self, method: str, body: bytes | None, content_type: str | None, log_prefix: str = ""):
        conn = http.client.HTTPConnection(self.upstream_host, self.upstream_port, timeout=300)
        headers = {
            k: v for k, v in self.headers.items()
            if k.lower() not in ("host", "content-length")
        }
        if body is not None:
            headers["Content-Length"] = str(len(body))
        if content_type:
            headers["Content-Type"] = content_type

        conn.request(method, self.path, body=body, headers=headers)
        resp = conn.getresponse()

        self.send_response(resp.status)
        for name, value in resp.getheaders():
            if name.lower() == "transfer-encoding":
                continue  # let Python handle chunking
            self.send_header(name, value)
        self.end_headers()

        # Stream response back in chunks, flush after each to avoid buffering pauses
        # Also capture first chunk for diagnostics
        first_chunk = True
        total_bytes = 0
        finish_reason = None
        while True:
            chunk = resp.read(4096)
            if not chunk:
                break
            if first_chunk and log_prefix:
                # Try to extract finish_reason from non-streaming response
                try:
                    j = json.loads(chunk.decode("utf-8", errors="replace"))
                    choices = j.get("choices", [])
                    if choices:
                        finish_reason = choices[0].get("finish_reason")
                        usage = j.get("usage", {})
                        _log(f"{log_prefix} -> finish_reason={finish_reason} "
                             f"completion_tokens={usage.get('completion_tokens','?')} "
                             f"total_tokens={usage.get('total_tokens','?')}")
                except Exception:
                    pass
                first_chunk = False
            total_bytes += len(chunk)
            self.wfile.write(chunk)
            self.wfile.flush()
        if log_prefix and finish_reason is None:
            _log(f"{log_prefix} -> streamed {total_bytes} bytes")
        conn.close()

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
