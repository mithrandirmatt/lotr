#!/usr/bin/env python3
"""Apply suggested overrides and record an audit history.

Reads suggestions from `build/do/assets/database/card_filter_overrides_suggestions.json`
or a user-provided mapping, writes `build/do/assets/database/card_filter_overrides.json`,
and appends history entries to `build/do/assets/database/overrides_history.json`.

Usage:
  py -3 build/py/wiki/apply_overrides.py --from-suggestions [--approve] [--user NAME] [--run-id ID] [--dry-run]
  py -3 build/py/wiki/apply_overrides.py --file path/to/overrides.json

The suggestions file format is produced by `ambiguous_feedback.py` and is a mapping
`card_id -> [ { action_id, suggested_card_id, raw_text, filter }, ... ]`.

The overrides file written is a mapping `action_id -> card_id` (simple and deterministic).
History entries are appended to the overrides history JSON array with metadata.
"""
from __future__ import annotations

import argparse
import datetime
import getpass
import json
import os
import sys
from typing import Any, Dict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..'))

SUGGEST_PATH = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'card_filter_overrides_suggestions.json')
OVERRIDES_PATH = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'card_filter_overrides.json')
HISTORY_PATH = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'overrides_history.json')
CARD_DB_PATH = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'card_database.json')
APPROVAL_PATH = os.path.join(REPO_ROOT, 'gotdot', 'assets', 'data', 'approval_status.json')


def load_json(path: str) -> Any:
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def extract_overrides_from_suggestions(suggestions: Dict[str, Any]) -> Dict[str, Dict]:
    """Convert suggestions mapping to action_id -> metadata dict.

    Returns mapping: action_id -> { suggested_card_id, card_id, raw_text, filter, source }
    """
    out: Dict[str, Dict] = {}
    for card_id, lst in (suggestions or {}).items():
        if not isinstance(lst, list):
            continue
        for item in lst:
            aid = item.get('action_id')
            sid = item.get('suggested_card_id')
            if not aid or not sid:
                continue
            out[aid] = {
                'suggested_card_id': sid,
                'card_id': card_id,
                'raw_text': item.get('raw_text'),
                'filter': item.get('filter'),
                'source': 'suggestion',
            }
    return out


def normalize_input_map(inp: Dict[str, Any]) -> Dict[str, Dict]:
    """Normalize a user-provided mapping into the internal action->meta format.

    Accepts either action->card_id mapping or suggestions-style mapping.
    """
    # If values are lists, treat as suggestions-style
    if any(isinstance(v, list) for v in inp.values()):
        return extract_overrides_from_suggestions(inp)

    out: Dict[str, Dict] = {}
    for k, v in inp.items():
        # assume k is action_id and v is card_id
        if isinstance(v, str):
            card_id = k.split('-a-')[0] if '-a-' in k else None
            out[k] = {
                'suggested_card_id': v,
                'card_id': card_id,
                'raw_text': None,
                'filter': None,
                'source': 'user',
            }
    return out


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--from-suggestions', action='store_true', help='Read suggestions file and apply them')
    p.add_argument('--file', help='Path to a suggestions file or a mapping file to apply')
    p.add_argument('--approve', action='store_true', help='Also mark affected cards as approved in approval_status.json')
    p.add_argument('--user', help='User who applies the overrides (defaults to current user)')
    p.add_argument('--run-id', help='Identifier for this run', default=datetime.datetime.utcnow().isoformat() + 'Z')
    p.add_argument('--dry-run', action='store_true', help='Show planned changes but do not write files')
    args = p.parse_args(argv)

    new_map: Dict[str, Dict] = {}

    if args.file:
        content = load_json(args.file)
        if content is None:
            print(f'File not found or empty: {args.file}')
            return 1
        new_map = normalize_input_map(content)
    elif args.from_suggestions:
        content = load_json(SUGGEST_PATH) or {}
        new_map = extract_overrides_from_suggestions(content)
    else:
        print('Nothing to do: pass --from-suggestions or --file <path>')
        return 1

    if not new_map:
        print('No overrides found to apply.')
        return 0

    existing = load_json(OVERRIDES_PATH) or {}
    history = load_json(HISTORY_PATH) or []
    card_db = load_json(CARD_DB_PATH) or {}

    applied = 0
    updated = 0
    skipped = 0
    entries = []
    user = args.user or getpass.getuser()
    now = datetime.datetime.utcnow().isoformat() + 'Z'

    for aid, meta in new_map.items():
        new_card = meta.get('suggested_card_id')
        card_id = meta.get('card_id') or (aid.split('-a-')[0] if '-a-' in aid else None)
        candidates = meta.get('candidates') or []
        raw_text = meta.get('raw_text')
        filt = meta.get('filter')

        if aid in existing:
            old = existing.get(aid)
            if old == new_card:
                skipped += 1
                continue
            existing[aid] = new_card
            updated += 1
            entry = {
                'timestamp': now,
                'action_id': aid,
                'card_id': card_id,
                'operation': 'update',
                'old_value': old,
                'new_value': new_card,
                'source': meta.get('source', 'suggestion'),
                'applied_by': user,
                'run_id': args.run_id,
                'candidates': candidates,
                'raw_text': raw_text,
                'filter': filt,
            }
            entries.append(entry)
        else:
            existing[aid] = new_card
            applied += 1
            entry = {
                'timestamp': now,
                'action_id': aid,
                'card_id': card_id,
                'operation': 'apply',
                'new_value': new_card,
                'source': meta.get('source', 'suggestion'),
                'applied_by': user,
                'run_id': args.run_id,
                'candidates': candidates,
                'raw_text': raw_text,
                'filter': filt,
            }
            entries.append(entry)

    # If requested, mark affected cards as approved
    if args.approve:
        approval = load_json(APPROVAL_PATH) or {}
        for e in entries:
            cid = e.get('card_id')
            if not cid:
                continue
            approval[cid] = True
        if not args.dry_run:
            write_json(APPROVAL_PATH, approval)
        print(f'Marked {len(entries)} cards as approved in {APPROVAL_PATH}')

    # Persist overrides and history
    if not args.dry_run:
        write_json(OVERRIDES_PATH, existing)
        history.extend(entries)
        write_json(HISTORY_PATH, history)

    print(f'Applied: {applied}, Updated: {updated}, Skipped (already same): {skipped}')
    if args.dry_run:
        print('Dry-run mode: no files were written.')
    else:
        print(f'Wrote overrides to {OVERRIDES_PATH} and appended {len(entries)} history entries to {HISTORY_PATH}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
