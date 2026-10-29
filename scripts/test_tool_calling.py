"""Tool-calling capability/consistency tester for local Ollama models.

Why this exists: repeated experience in this repo has shown that a model's
raw benchmark scores or "supports tools" marketing claims do NOT reliably
predict whether it actually emits Ollama's structured `message.tool_calls`
field in practice (Qwen2.5-Coder-7B-Instruct, base and LoRA, both silently
degrade to wrapping the tool call as text like `<json>...</json>` instead of
using the real field -- see /memories/repo/dev-environment-quirks.md). This
script empirically measures, for any model already pulled into host Ollama,
how consistently it produces a real structured tool call across repeated
trials on a small set of representative agentic-coding prompts, BEFORE any
time is spent fine-tuning/training against that model.

Usage:
    python scripts/test_tool_calling.py --models qwen2.5-coder:14b devstral gpt-oss:20b
    python scripts/test_tool_calling.py --models qwen3:8b-q4_K_M --repeats 8 --temperature 0.2
    python scripts/test_tool_calling.py --list-models   # show locally pulled models
    python scripts/test_tool_calling.py --models devstral --output results.json

Requires only `requests` (stdlib otherwise). Talks to host Ollama's native
API (default http://localhost:11434) -- NOT llama-server, NOT the OpenAI-
compatible shim -- so make sure no other process (e.g. scripts/llama_ollama_shim.py)
is squatting on port 11434 before running this.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field

import requests

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_TIMEOUT = 120  # seconds per request; tool_choice-style runaway generation is a real risk
DEFAULT_NUM_PREDICT = 300  # cap generation length -- see dev-environment-quirks.md runaway-generation note
DEFAULT_REPEATS = 5

# --- Representative agentic-coding tool schemas -----------------------------
# Mirrors the shape of real coding-agent tools (read/edit/search/run) closely
# enough to be a fair proxy, without depending on any actual IDE integration.

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file at the given path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to read."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace a string in a file with a new string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to edit."},
                    "old_string": {"type": "string", "description": "Exact text to replace."},
                    "new_string": {"type": "string", "description": "Replacement text."},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command and return its output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute."},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search the codebase for a text or regex pattern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text or regex pattern to search for."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List the files and folders in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list."},
                },
                "required": ["path"],
            },
        },
    },
]

# --- Test prompts ------------------------------------------------------------
# Each prompt is crafted so there is exactly one obviously-correct tool call.
# `expect_arg_substr` is a lowercase substring that should appear in the
# argument the model chose for `expect_arg_key`, as a loose correctness check
# (not exact-match, since paraphrasing e.g. quoting style is fine).

@dataclass
class TestPrompt:
    name: str
    system: str
    user: str
    expect_function: str
    expect_arg_key: str | None = None
    expect_arg_substr: str | None = None


SYSTEM_PROMPT = (
    "You are a coding agent with access to tools for reading, editing, and "
    "searching a codebase, and running shell commands. When the user's "
    "request requires an action, call the appropriate tool instead of just "
    "describing what you would do."
)

TEST_PROMPTS = [
    TestPrompt(
        name="read_file_basic",
        system=SYSTEM_PROMPT,
        user="Show me the contents of server/main.py",
        expect_function="read_file",
        expect_arg_key="path",
        expect_arg_substr="server/main.py",
    ),
    TestPrompt(
        name="edit_file_rename",
        system=SYSTEM_PROMPT,
        user=(
            "config.py currently contains exactly this line:\n"
            "DEBUG = True\n\n"
            "Update config.py so that line reads 'DEBUG = False' instead."
        ),
        expect_function="edit_file",
        expect_arg_key="old_string",
        expect_arg_substr="debug = true",
    ),
    TestPrompt(
        name="run_command_tests",
        system=SYSTEM_PROMPT,
        user="Run the test suite using pytest.",
        expect_function="run_command",
        expect_arg_key="command",
        expect_arg_substr="pytest",
    ),
    TestPrompt(
        name="search_code_symbol",
        system=SYSTEM_PROMPT,
        user="Find every place in the codebase where the function `validate_deck` is called.",
        expect_function="search_code",
        expect_arg_key="query",
        expect_arg_substr="validate_deck",
    ),
    TestPrompt(
        name="list_directory_basic",
        system=SYSTEM_PROMPT,
        user="What files are in the scripts directory?",
        expect_function="list_directory",
        expect_arg_key="path",
        expect_arg_substr="scripts",
    ),
]


@dataclass
class TrialResult:
    ok: bool
    reason: str
    latency_s: float
    raw_tool_calls: list = field(default_factory=list)
    raw_content: str = ""


def run_trial(host: str, model: str, prompt: TestPrompt, temperature: float, timeout: int) -> TrialResult:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt.system},
            {"role": "user", "content": prompt.user},
        ],
        "tools": TOOLS,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": DEFAULT_NUM_PREDICT,
        },
    }
    start = time.time()
    try:
        resp = requests.post(f"{host}/api/chat", json=body, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        return TrialResult(ok=False, reason=f"request_error: {exc}", latency_s=time.time() - start)
    latency = time.time() - start

    if resp.status_code != 200:
        return TrialResult(ok=False, reason=f"http_{resp.status_code}: {resp.text[:200]}", latency_s=latency)

    try:
        data = resp.json()
    except ValueError:
        return TrialResult(ok=False, reason="invalid_json_response", latency_s=latency, raw_content=resp.text[:300])

    message = data.get("message", {}) or {}
    tool_calls = message.get("tool_calls") or []
    content = message.get("content", "") or ""

    if not tool_calls:
        return TrialResult(
            ok=False,
            reason="no_structured_tool_call",
            latency_s=latency,
            raw_content=content[:300],
        )

    # Check the FIRST tool call matches what we expect (name + arg substring).
    first = tool_calls[0]
    fn = (first.get("function") or {})
    fn_name = fn.get("name", "")
    fn_args = fn.get("arguments", {})
    if isinstance(fn_args, str):
        try:
            fn_args = json.loads(fn_args)
        except ValueError:
            fn_args = {}

    if fn_name != prompt.expect_function:
        return TrialResult(
            ok=False,
            reason=f"wrong_function: got '{fn_name}', expected '{prompt.expect_function}'",
            latency_s=latency,
            raw_tool_calls=tool_calls,
        )

    if prompt.expect_arg_key and prompt.expect_arg_substr:
        arg_val = str(fn_args.get(prompt.expect_arg_key, "")).lower()
        if prompt.expect_arg_substr.lower() not in arg_val:
            return TrialResult(
                ok=False,
                reason=(
                    f"wrong_argument: {prompt.expect_arg_key}='{arg_val}' "
                    f"missing '{prompt.expect_arg_substr}'"
                ),
                latency_s=latency,
                raw_tool_calls=tool_calls,
            )

    return TrialResult(ok=True, reason="ok", latency_s=latency, raw_tool_calls=tool_calls)


def list_local_models(host: str) -> list[str]:
    resp = requests.get(f"{host}/api/tags", timeout=15)
    resp.raise_for_status()
    return [m["name"] for m in resp.json().get("models", [])]


def evaluate_model(host: str, model: str, repeats: int, temperature: float, timeout: int, verbose: bool) -> dict:
    print(f"\n=== {model} ===")
    prompt_results = {}
    total_trials = 0
    total_ok = 0
    total_latency = 0.0

    for prompt in TEST_PROMPTS:
        trials = []
        for i in range(repeats):
            trial = run_trial(host, model, prompt, temperature, timeout)
            trials.append(trial)
            total_trials += 1
            total_latency += trial.latency_s
            if trial.ok:
                total_ok += 1
            if verbose:
                status = "OK" if trial.ok else f"FAIL ({trial.reason})"
                print(f"  [{prompt.name} #{i + 1}] {status} ({trial.latency_s:.1f}s)")
        successes = sum(1 for t in trials if t.ok)
        rate = successes / repeats * 100
        prompt_results[prompt.name] = {
            "success_rate_pct": round(rate, 1),
            "successes": successes,
            "trials": repeats,
            "failure_reasons": [t.reason for t in trials if not t.ok],
        }
        marker = "PASS" if rate == 100 else ("PARTIAL" if rate > 0 else "FAIL")
        print(f"  {prompt.name}: {successes}/{repeats} ({rate:.0f}%) [{marker}]")

    overall_rate = (total_ok / total_trials * 100) if total_trials else 0.0
    avg_latency = (total_latency / total_trials) if total_trials else 0.0
    print(f"  -> overall: {total_ok}/{total_trials} ({overall_rate:.1f}%), avg latency {avg_latency:.1f}s")

    return {
        "model": model,
        "overall_success_rate_pct": round(overall_rate, 1),
        "avg_latency_s": round(avg_latency, 2),
        "per_prompt": prompt_results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+", help="Ollama model tags to test (must already be pulled).")
    parser.add_argument("--list-models", action="store_true", help="List locally pulled Ollama models and exit.")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Ollama host (default {DEFAULT_HOST}).")
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS, help="Trials per prompt per model.")
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Per-request timeout (seconds).")
    parser.add_argument("--verbose", action="store_true", help="Print each individual trial's result.")
    parser.add_argument("--output", help="Optional path to write full JSON results.")
    args = parser.parse_args()

    if args.list_models:
        for name in list_local_models(args.host):
            print(name)
        return

    if not args.models:
        parser.error("--models is required (or use --list-models)")

    results = []
    for model in args.models:
        results.append(evaluate_model(args.host, model, args.repeats, args.temperature, args.timeout, args.verbose))

    print("\n=== SUMMARY (best first) ===")
    for r in sorted(results, key=lambda r: r["overall_success_rate_pct"], reverse=True):
        print(f"  {r['model']:<50} {r['overall_success_rate_pct']:>5.1f}%   avg {r['avg_latency_s']:.1f}s")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\nFull results written to {args.output}")


if __name__ == "__main__":
    sys.exit(main())
