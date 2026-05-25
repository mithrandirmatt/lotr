#!/usr/bin/env python3
"""Simple RAG query: lexical retrieval + Ollama HTTP generate.
Saves queries to /workspace/build/docker/logs/rag_queries.log
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path


def score_chunk(query_tokens, chunk_text):
    ctoks = set(chunk_text.lower().split())
    qtoks = set(query_tokens)
    return len(ctoks & qtoks)


def load_chunks(path: Path):
    with path.open('r', encoding='utf-8') as f:
        j = json.load(f)
    return j.get('chunks', [])


def compose_prompt(context_chunks, user_prompt):
    parts = ['Repository context:']
    for c in context_chunks:
        parts.append(f"-- {c['source']} ({c['start']}-{c['end']}) --\n{c['text']}")
    parts.append('\nUser prompt:')
    parts.append(user_prompt)
    parts.append('\nAnswer:')
    return '\n\n'.join(parts)


def call_ollama(ollama_url, model, prompt, max_tokens=512):
    try:
        import httpx
    except Exception as exc:
        return 127, f'httpx not available: {exc}'

    payload = {"model": model, "prompt": prompt, "max_tokens": max_tokens, "stream": False}
    try:
        r = httpx.post(f"{ollama_url}/api/generate", json=payload, timeout=120)
        r.raise_for_status()
        try:
            return 0, r.json()
        except Exception:
            return 0, r.text
    except Exception as exc:
        return 1, str(exc)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--prompt', required=True)
    p.add_argument('--index', default='/workspace/build/docker/artifacts/index/chunks.json')
    p.add_argument('--top_k', type=int, default=5)
    p.add_argument('--model', default=os.environ.get('AI_MODEL', 'qwen3.5-claude-4.6-opus:latest'))
    p.add_argument('--ollama', default=os.environ.get('OLLAMA_URL', 'http://localhost:11434'))
    args = p.parse_args()

    idx_path = Path(args.index)
    if not idx_path.exists():
        print(f'Index file not found: {idx_path}', file=sys.stderr)
        sys.exit(2)

    chunks = load_chunks(idx_path)
    if not chunks:
        print('No chunks found in index', file=sys.stderr)
        sys.exit(3)

    query_tokens = args.prompt.lower().split()
    scored = []
    for c in chunks:
        sc = score_chunk(query_tokens, c['text'])
        scored.append((sc, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [c for s, c in scored[:args.top_k]]

    final_prompt = compose_prompt(top, args.prompt)

    rc, resp = call_ollama(args.ollama, args.model, final_prompt)

    out = {
        'model': args.model,
        'ollama': args.ollama,
        'prompt': args.prompt,
        'top_k': args.top_k,
        'retrieved': [{'source': c['source'], 'start': c['start'], 'end': c['end']} for c in top],
        'rc': rc,
        'response': resp,
    }

    log_dir = Path('/workspace/build/docker/logs')
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / 'rag_queries.log'
    with log_path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(out, ensure_ascii=False) + '\n')

    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
