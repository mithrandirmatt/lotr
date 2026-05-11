#!/usr/bin/env python3
"""Benchmark an LLM invocation (CLI) for latency and token throughput.

This script is intentionally generic: it can call `ollama run <model> --prompt "..."`
via a command-template or use a default `ollama` invocation when `--model` is
provided. It measures wall-clock time and (optionally) token counts using
tiktoken if available.

Examples:
  python build/py/tools/bench_model.py --model llama2 --prompt "Hello world" --iterations 3
  python build/py/tools/bench_model.py --cmd-template 'ollama run {model} --prompt "{}"' --model llama2 --prompt-file prompts.txt
"""
from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import time
from typing import List


def try_get_tokenizer():
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")

        def encode(s: str) -> List[int]:
            return enc.encode(s)

        return encode
    except Exception:
        return None


def run_command_template(template: str, prompt: str, timeout: int = 600) -> tuple[int, str, float]:
    """Run a shell command built from template.format(prompt). Returns (rc, stdout, elapsed_sec)."""
    cmd = template.format(prompt)
    t0 = time.perf_counter()
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        elapsed = time.perf_counter() - t0
        out = p.stdout.strip() if p.stdout else p.stderr.strip()
        return p.returncode, out, elapsed
    except subprocess.TimeoutExpired:
        return -1, '', time.perf_counter() - t0


def run_ollama(model: str, prompt: str, timeout: int = 600) -> tuple[int, str, float]:
    """Call `ollama run <model> --prompt <prompt>` if `ollama` is in PATH."""
    from shutil import which
    # Prefer the local `ollama` CLI when available.
    if which('ollama') is not None:
        cmd = ['ollama', 'run', model, '--prompt', prompt]
        t0 = time.perf_counter()
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            elapsed = time.perf_counter() - t0
            out = p.stdout.strip() if p.stdout else p.stderr.strip()
            return p.returncode, out, elapsed
        except subprocess.TimeoutExpired:
            return -1, '', time.perf_counter() - t0

    # If the CLI is not available, try calling a running Ollama HTTP server
    # pointed to by the OLLAMA_URL environment variable (e.g. http://host:11435).
    import os
    base_url = os.environ.get('OLLAMA_URL')
    if not base_url:
        return 127, 'ollama not found in PATH and OLLAMA_URL not set', 0.0

    try:
        import httpx
    except Exception:
        return 127, 'ollama CLI not found and httpx not installed for HTTP fallback', 0.0

    payload = {"model": model, "prompt": prompt, "stream": False}
    t0 = time.perf_counter()
    try:
        resp = httpx.post(f"{base_url}/api/generate", json=payload, timeout=timeout)
        elapsed = time.perf_counter() - t0
        resp.raise_for_status()
        out = resp.json().get('response', '')
        return 0, out, elapsed
    except Exception as exc:
        return 1, f'HTTP Ollama error: {exc}', time.perf_counter() - t0


def list_ollama_models(timeout: int = 3) -> List[str]:
    """Discover available Ollama models.

    Tries the local `ollama` CLI first (commands: `ollama list` or `ollama ls`),
    then falls back to querying the HTTP API at `$OLLAMA_URL/api/models`.
    Returns a list of model names (may be empty on failure).
    """
    from shutil import which
    import os

    models: List[str] = []

    # Try CLI listing first
    if which('ollama') is not None:
        for cmd in (('ollama', 'list'), ('ollama', 'ls')):
            try:
                p = subprocess.run(list(cmd), capture_output=True, text=True, timeout=timeout)
                if p.returncode != 0:
                    continue
                out = p.stdout.strip()
                if not out:
                    continue
                for line in out.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    # Skip header-ish lines
                    if line.lower().startswith('name') or line.lower().startswith('model'):
                        continue
                    # Take first token as model name
                    model_name = line.split()[0]
                    if model_name and model_name not in models:
                        models.append(model_name)
                if models:
                    return models
            except Exception:
                continue

    # Fallback: HTTP API
    base_url = os.environ.get('OLLAMA_URL')
    if base_url:
        try:
            import httpx

            resp = httpx.get(f"{base_url}/api/models", timeout=timeout)
            resp.raise_for_status()
            j = resp.json()
            # Accept various shapes: {"models":[...]} or [...]
            items = j.get('models') if isinstance(j, dict) and 'models' in j else j
            if isinstance(items, list):
                for it in items:
                    if isinstance(it, dict):
                        name = it.get('name') or it.get('id') or it.get('model')
                        if name and name not in models:
                            models.append(name)
                    elif isinstance(it, str):
                        if it not in models:
                            models.append(it)
        except Exception:
            pass

    return models


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--model', help='Model name (used with ollama run <model>)')
    p.add_argument('--cmd-template', help='Command template with {} placeholder for prompt (shell executed)')
    p.add_argument('--prompt', help='Prompt text to send to model')
    p.add_argument('--prompt-file', help='File with prompt text (first line used)')
    p.add_argument('--default-prompt', help='Default prompt used when iterating discovered models', default='Hello world')
    p.add_argument('--iterations', type=int, default=3, help='Number of iterations to run')
    p.add_argument('--timeout', type=int, default=600, help='Timeout (seconds) per run')
    args = p.parse_args(argv)

    prompt = ''
    if args.prompt_file:
        with open(args.prompt_file, 'r', encoding='utf-8') as f:
            prompt = f.read().strip()
    else:
        prompt = args.prompt or ''

    encode = try_get_tokenizer()
    if encode is None:
        print('tiktoken not available; token counts will not be shown', file=sys.stderr)

    # Print what invocation we're about to benchmark so logs clearly show the model/cmd-template.
    print(f'Benchmark invocation: model={args.model} cmd_template={args.cmd_template} iterations={args.iterations}', file=sys.stderr)

    # If no prompt was provided, attempt to discover models and iterate over them
    if not prompt:
        default_prompt = args.default_prompt
        # If a specific model was requested, use the default prompt for it
        if args.model:
            prompt = default_prompt
        else:
            models = list_ollama_models()
            if not models:
                print('No prompt provided and no models could be discovered via ollama/list or OLLAMA_URL', file=sys.stderr)
                p.print_help()
                return 2

            for model in models:
                print('\n' + '=' * 40)
                print(f'Model: {model}')
                print('=' * 40)
                times = []
                tokens_in = None
                tokens_out = []
                for i in range(1, args.iterations + 1):
                    if args.cmd_template:
                        rc, out, elapsed = run_command_template(args.cmd_template, default_prompt, timeout=args.timeout)
                    else:
                        rc, out, elapsed = run_ollama(model, default_prompt, timeout=args.timeout)

                    times.append(elapsed)
                    if encode:
                        try:
                            tokens_in = len(encode(default_prompt))
                            tokens_out.append(len(encode(out)) if out else 0)
                        except Exception:
                            tokens_in = None
                    print(f'iter={i}\treturn={rc}\ttime_s={elapsed:.3f}\toutput_tokens={tokens_out[-1] if tokens_out else "?"}')

                import statistics

                print('\nSummary:')
                print(f'model: {model}')
                print(f'iterations: {len(times)}')
                print(f'total_time_s: {sum(times):.3f} avg_s: {statistics.mean(times):.3f} median_s: {statistics.median(times):.3f}')
                if tokens_in is not None:
                    print(f'tokens_in: {tokens_in} tokens_out_avg: {statistics.mean(tokens_out):.1f}')

            return 0

    # Fall through to single-model / cmd-template benchmarking
    times = []
    tokens_in = None
    tokens_out = []
    for i in range(1, args.iterations + 1):
        if args.cmd_template:
            rc, out, elapsed = run_command_template(args.cmd_template, prompt, timeout=args.timeout)
        elif args.model:
            rc, out, elapsed = run_ollama(args.model, prompt, timeout=args.timeout)
        else:
            print('Either --cmd-template or --model must be provided', file=sys.stderr)
            return 2

        times.append(elapsed)
        if encode:
            try:
                tokens_in = len(encode(prompt))
                tokens_out.append(len(encode(out)) if out else 0)
            except Exception:
                tokens_in = None
        print(f'iter={i}\treturn={rc}\ttime_s={elapsed:.3f}\toutput_tokens={tokens_out[-1] if tokens_out else "?"}')

    import statistics

    print('\nSummary:')
    print(f'iterations: {len(times)}')
    print(f'total_time_s: {sum(times):.3f} avg_s: {statistics.mean(times):.3f} median_s: {statistics.median(times):.3f}')
    if tokens_in is not None:
        print(f'tokens_in: {tokens_in} tokens_out_avg: {statistics.mean(tokens_out):.1f}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
