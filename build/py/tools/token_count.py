#!/usr/bin/env python3
"""Count tokens for text samples using tiktoken (cl100k_base) when available.

Usage examples:
  python build/py/tools/token_count.py --text "Fellowship: Add a burden..."
  python build/py/tools/token_count.py --file README.md
  python build/py/tools/token_count.py --cards gotdot/assets/data/card_database.json --summary
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from typing import Iterable


def try_get_tokenizer():
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")

        def encode(s: str) -> list[int]:
            return enc.encode(s)

        return encode
    except Exception:
        return None


def simple_whitespace_encode(s: str) -> list[str]:
    return s.split()


def count_tokens_for_text(encode, text: str) -> int:
    if encode is None:
        return len(simple_whitespace_encode(text))
    return len(encode(text))


def load_card_texts(path: str) -> Iterable[str]:
    with open(path, 'r', encoding='utf-8') as f:
        db = json.load(f)
    for card_id, card in db.items():
        txt = card.get('game_text') or ''
        yield txt


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--text', '-t', nargs='+', help='Text samples to count tokens for')
    p.add_argument('--file', '-f', nargs='+', help='File(s) to read and count tokens for (prints whole file)')
    p.add_argument('--cards', help='Path to card_database.json to analyze game_text fields')
    p.add_argument('--sample', '-n', type=int, default=100, help='Number of card samples when using --cards (default 100)')
    p.add_argument('--summary', action='store_true', help='Print summary histogram when using --cards')
    args = p.parse_args(argv)

    encode = try_get_tokenizer()
    if encode is None:
        print('tiktoken not available; falling back to whitespace tokenization', file=sys.stderr)

    if args.text:
        for t in args.text:
            cnt = count_tokens_for_text(encode, t)
            print(f'tokens={cnt}\t{text_preview(t)}')
        return 0

    if args.file:
        for fp in args.file:
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    txt = f.read()
            except Exception as e:
                print(f'ERROR reading {fp}: {e}', file=sys.stderr)
                continue
            cnt = count_tokens_for_text(encode, txt)
            print(f'file={fp}\ttokens={cnt}')
        return 0

    if args.cards:
        texts = list(load_card_texts(args.cards))
        if not texts:
            print('No card texts found in', args.cards, file=sys.stderr)
            return 1
        # sample first N (deterministic)
        n = min(args.sample, len(texts))
        counts = [count_tokens_for_text(encode, t) for t in texts[:n]]
        if args.summary:
            hist = Counter(counts)
            total = sum(hist.values())
            print(f'Analyzed {n} card texts (first {n} entries)')
            for k in sorted(hist.keys()):
                print(f'{k:4d} tokens: {hist[k]:4d} ({hist[k]*100/total:5.1f}%)')
            avg = sum(counts)/len(counts)
            print(f'avg tokens: {avg:.2f}\nmin: {min(counts)} max: {max(counts)}')
        else:
            for i, c in enumerate(counts, 1):
                print(f'{i:4d}\t{c}')
        return 0

    p.print_help()
    return 2


def text_preview(t: str, length: int = 60) -> str:
    s = ' '.join(t.split())
    if len(s) <= length:
        return s
    return s[:length-3] + '...'


if __name__ == '__main__':
    raise SystemExit(main())
