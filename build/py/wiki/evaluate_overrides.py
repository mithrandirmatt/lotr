#!/usr/bin/env python3
"""Evaluate applied overrides, rollback failing ones, and populate a review queue.

This script reads the active overrides (`card_filter_overrides.json`), the
ambiguous test results produced by `ambiguous_feedback.py` (typically
`ambiguous_filters_test_results.json`), and the overrides history. For any
override whose action still reports a non-'auto' status in the test results,
the override is removed (rolled back), an entry is appended to the history,
and a detailed item is placed in the review queue
`overrides_review_queue.json` for human inspection.

Run: `py -3 build/py/wiki/evaluate_overrides.py [--dry-run] [--user NAME]`
"""
from __future__ import annotations

import argparse
import datetime
import getpass
import json
import os
import sys
from typing import Any, Dict, List

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..'))

OVERRIDES_PATH = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'card_filter_overrides.json')
RESULTS_PATH = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'ambiguous_filters_test_results.json')
HISTORY_PATH = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'overrides_history.json')
REVIEW_QUEUE_PATH = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'overrides_review_queue.json')
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


def find_history_for_action(history: List[Dict], action_id: str) -> List[Dict]:
    return [h for h in history if h.get('action_id') == action_id]


def main(argv: List[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--dry-run', action='store_true', help='Do not write changes; show plan only')
    p.add_argument('--user', help='User performing evaluation (defaults to current user)')
    args = p.parse_args(argv)

    user = args.user or getpass.getuser()
    now = datetime.datetime.utcnow().isoformat() + 'Z'

    overrides = load_json(OVERRIDES_PATH) or {}
    results = load_json(RESULTS_PATH) or {}
    history = load_json(HISTORY_PATH) or []
    review_queue = load_json(REVIEW_QUEUE_PATH) or []
    approval = load_json(APPROVAL_PATH) or {}

    # Build a lookup of action_id -> test result status
    result_map: Dict[str, Dict] = {}
    for r in results.get('results', []) if isinstance(results, dict) else []:
        aid = r.get('action_id')
        if aid:
            result_map[aid] = r

    if not overrides:
        print('No active overrides to evaluate.')
        return 0

    rolled_back: List[str] = []
    kept: List[str] = []

    for action_id, applied_card in list(overrides.items()):
        res = result_map.get(action_id)
        if not res:
            # No test result available for this action; keep the override
            kept.append(action_id)
            continue

        status = res.get('status')
        # Consider anything other than 'auto' a failing outcome for a previously-applied override
        if status and status != 'auto':
            # prepare review item
            card_id = res.get('card_id') or res.get('card_id')
            candidates = res.get('candidates') or []
            raw = res.get('raw_text')
            history_entries = find_history_for_action(history, action_id)

            review_item = {
                'action_id': action_id,
                'applied_card_id': applied_card,
                'card_id': card_id,
                'status': status,
                'candidates': candidates,
                'raw_text': raw,
                'history': history_entries,
                'detected_at': now,
                'reason': 'failed_test',
            }
            review_queue.append(review_item)

            # rollback: remove from active overrides and add history entry
            old_val = overrides.pop(action_id, None)
            hb = {
                'timestamp': now,
                'action_id': action_id,
                'card_id': card_id,
                'operation': 'rollback',
                'old_value': old_val,
                'reason': 'failed_test',
                'detected_by': user,
            }
            history.append(hb)

            # un-approve the card if it was approved
            if card_id and approval.get(card_id):
                approval[card_id] = False

            rolled_back.append(action_id)
        else:
            kept.append(action_id)

    # Persist changes unless dry-run
    if args.dry_run:
        print(f'DRY-RUN: would rollback {len(rolled_back)} overrides, keep {len(kept)}')
        if rolled_back:
            print('Rolled back actions (preview):')
            for a in rolled_back:
                print('  ', a)
        return 0

    # Write updated files
    write_json(OVERRIDES_PATH, overrides)
    write_json(HISTORY_PATH, history)
    write_json(REVIEW_QUEUE_PATH, review_queue)
    write_json(APPROVAL_PATH, approval)

    print(f'Rolled back {len(rolled_back)} overrides; kept {len(kept)} active overrides.')
    if rolled_back:
        print(f'Appended {len(rolled_back)} items to review queue at {REVIEW_QUEUE_PATH}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
