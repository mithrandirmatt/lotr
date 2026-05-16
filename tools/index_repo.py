#!/usr/bin/env python3
"""Index repository files into simple lexical chunks (no heavy deps).

Saves: build/docker/artifacts/index/chunks.json
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

CHUNK_SIZE = 1000
OVERLAP = 200

EXCLUDE_DIRS = {'.git', 'node_modules', 'venv', '.venv', '.ollama', 'build/docker/artifacts'}
INCLUDE_EXT = {'.py', '.md', '.rst', '.txt', '.json', '.toml', '.ini', '.cfg', '.yml', '.yaml', '.html', '.js', '.ts'}


def should_skip(path: Path) -> bool:
    parts = set(p for p in path.parts)
    if parts & EXCLUDE_DIRS:
        return True
    if path.is_dir():
        return True
    if path.suffix.lower() not in INCLUDE_EXT:
        return True
    return False


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP):
    chunks = []
    i = 0
    n = len(text)
    while i < n:
        end = min(n, i + chunk_size)
        chunk = text[i:end]
        chunks.append((i, end, chunk))
        i = end - overlap
        if i < 0:
            i = 0
    return chunks


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', default='/workspace', help='Repository root inside container')
    p.add_argument('--out', default='/workspace/build/docker/artifacts/index/chunks.json')
    args = p.parse_args()

    root = Path(args.root)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    chunks_list = []
    file_count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # filter out excluded dirs
        rel = os.path.relpath(dirpath, root)
        if rel != '.' and any(part in EXCLUDE_DIRS for part in Path(rel).parts):
            continue
        for fn in filenames:
            fp = Path(dirpath) / fn
            if should_skip(fp.relative_to(root)):
                continue
            try:
                text = fp.read_text(encoding='utf-8')
            except Exception:
                try:
                    text = fp.read_text(encoding='latin-1')
                except Exception:
                    continue
            file_count += 1
            file_rel = str(fp.relative_to(root))
            for idx, (start, end, chunk) in enumerate(chunk_text(text)):
                chunk_id = f"{file_rel}:{start}-{end}"
                chunks_list.append({'id': chunk_id, 'source': file_rel, 'start': start, 'end': end, 'text': chunk})

    # write chunks
    with out_path.open('w', encoding='utf-8') as f:
        json.dump({'root': str(root), 'file_count': file_count, 'chunks': chunks_list}, f, indent=2)

    print(f'Indexed {file_count} files -> {len(chunks_list)} chunks to {out_path}')


if __name__ == '__main__':
    main()
