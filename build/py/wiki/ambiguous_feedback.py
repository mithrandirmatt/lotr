#!/usr/bin/env python3
"""Ambiguous filter feedback loop.

Reads `build/do/assets/database/ambiguous_filters.json`, attempts to auto-resolve
filters using the same heuristics as the parser, writes a test-results file and
an overrides-suggestions file for human confirmation.

Run: `py -3 build/py/wiki/ambiguous_feedback.py`
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..'))
sys.path.insert(0, SCRIPT_DIR)

import parse_game_logic as pg


AMB_PATH = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'ambiguous_filters.json')
CARD_DB_PATH = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'card_database.json')
RESULTS_PATH = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'ambiguous_filters_test_results.json')
SUGGEST_PATH = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'card_filter_overrides_suggestions.json')
APPROVAL_PATH = os.path.join(REPO_ROOT, 'gotdot', 'assets', 'data', 'approval_status.json')


def load_json(path: str) -> Any:
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    amb = load_json(AMB_PATH)
    if amb is None:
        print(f'Missing ambiguous file: {AMB_PATH}')
        return 1

    card_db = load_json(CARD_DB_PATH) or {}

    # Load or create approval status file; initialize to all-failed if absent
    approval = load_json(APPROVAL_PATH)
    if approval is None:
        approval = {cid: False for cid in card_db.keys()}
        os.makedirs(os.path.dirname(APPROVAL_PATH), exist_ok=True)
        with open(APPROVAL_PATH, 'w', encoding='utf-8') as pf:
            json.dump(approval, pf, ensure_ascii=False, indent=2)
        print(f'Created approval status file with {len(approval)} entries at {APPROVAL_PATH}')

    # set parser module globals so we reuse the same heuristics
    pg.CARD_DB = card_db
    pg.ALIAS_INDEX = pg._build_alias_index(card_db)

    # Only run tests for cards that are not approved (failed)
    all_items = amb.get('items', [])
    items = [it for it in all_items if not approval.get(it.get('card_id'), False)]
    results = []
    suggestions = {}

    counts = {'auto': 0, 'multiple': 0, 'none': 0}

    for it in items:
        cid = it.get('card_id')
        aid = it.get('action_id')
        raw = it.get('raw_text')
        f = it.get('filter') or {}
        name_text = f.get('name_text') if isinstance(f, dict) else None

        status = 'none'
        candidates = []
        suggestion = None

        if name_text:
            candidates = pg._resolve_name_to_ids(name_text)
            if len(candidates) == 1:
                status = 'auto'
                suggestion = candidates[0]
                counts['auto'] += 1
            elif len(candidates) > 1:
                status = 'multiple'
                counts['multiple'] += 1
            else:
                # try trait-based extraction
                tf = pg._extract_trait_filter(name_text)
                if tf:
                    candidates = pg._filter_cards_by_traits(tf)
                    if len(candidates) == 1:
                        status = 'auto'
                        suggestion = candidates[0]
                        counts['auto'] += 1
                    elif len(candidates) > 1:
                        status = 'multiple'
                        counts['multiple'] += 1
                    else:
                        status = 'none'
                        counts['none'] += 1
                else:
                    status = 'none'
                    counts['none'] += 1
        else:
            # no name_text; try trait capture from raw_text
            tf = pg._extract_trait_filter(raw)
            if tf:
                candidates = pg._filter_cards_by_traits(tf)
                if len(candidates) == 1:
                    status = 'auto'
                    suggestion = candidates[0]
                    counts['auto'] += 1
                elif len(candidates) > 1:
                    status = 'multiple'
                    counts['multiple'] += 1
                else:
                    status = 'none'
                    counts['none'] += 1
            else:
                status = 'none'
                counts['none'] += 1

        res = {
            'card_id': cid,
            'action_id': aid,
            'card_name': it.get('card_name'),
            'raw_text': raw,
            'filter': f,
            'status': status,
            'candidates': candidates,
            'suggestion': suggestion,
        }
        results.append(res)
        if suggestion:
            # suggestions keyed by card_id -> list of action suggestions
            suggestions.setdefault(cid, []).append({'action_id': aid, 'suggested_card_id': suggestion, 'raw_text': raw, 'filter': f})

    # write results and suggestions
    with open(RESULTS_PATH, 'w', encoding='utf-8') as rf:
        json.dump({'counts': counts, 'results': results}, rf, ensure_ascii=False, indent=2)

    with open(SUGGEST_PATH, 'w', encoding='utf-8') as sf:
        json.dump(suggestions, sf, ensure_ascii=False, indent=2)

    print(f"Test completed: {len(results)} items — auto={counts['auto']} multiple={counts['multiple']} none={counts['none']}")
    print(f"Wrote results: {RESULTS_PATH}")
    print(f"Wrote suggestions: {SUGGEST_PATH}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
