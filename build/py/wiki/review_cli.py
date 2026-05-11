#!/usr/bin/env python3
"""Interactive review CLI (skeleton).

Usage: py -3 build/py/wiki/review_cli.py [--preview=browser|none] [--dry-run] [--resume]

This is a lightweight, safe starter implementation that provides:
- Browser preview (`--preview=browser`) which emits a temporary HTML file and opens it
- A small interactive loop showing ambiguous items
- Exit & save (`q`) that writes a session snapshot and creates backups

This file is intentionally conservative; it implements the essential flows
so the review loop can be exercised and extended.
"""
from __future__ import annotations

import argparse
import datetime
import getpass
import json
import os
import shutil
import sys
import tempfile
import webbrowser
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..'))

AMB_PATH = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'ambiguous_filters.json')
SUGGEST_PATH = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'card_filter_overrides_suggestions.json')
OVERRIDES_PATH = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'card_filter_overrides.json')
HISTORY_PATH = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'overrides_history.json')
REVIEW_QUEUE_PATH = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'overrides_review_queue.json')
CARD_DB_PATH = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'card_database.json')
APPROVAL_PATH = os.path.join(REPO_ROOT, 'gotdot', 'assets', 'data', 'approval_status.json')
SESSION_STATE_PATH = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'review_session_state.json')


def load_json(path: str) -> Any:
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_json_atomic(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def backup_file(path: str) -> Optional[str]:
    if os.path.exists(path):
        ts = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        bak = f"{path}.bak.{ts}"
        try:
            shutil.copy2(path, bak)
            return bak
        except Exception:
            return None
    return None


def save_session_state(index: int, remaining_queue: List[Dict], overrides_snapshot: Dict[str, Any], history_delta: List[Dict]) -> None:
    state = {
        'queue_index': index,
        'remaining_queue': remaining_queue,
        'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
        'overrides_snapshot': overrides_snapshot,
        'history_delta': history_delta,
    }
    write_json_atomic(SESSION_STATE_PATH, state)


def create_preview_html(card: Dict[str, Any], item: Dict[str, Any], card_db: Dict[str, Any]) -> str:
    """Create a temporary HTML preview containing the main card and any candidates.

    Returns the path to the temporary HTML file.
    """
    title = card.get('name') or item.get('card_name') or item.get('card_id')

    def _img_uri_for_card(rec: Dict[str, Any]) -> Optional[str]:
        if not rec:
            return None
        image_rel = rec.get('image_path_clean') or rec.get('image_path') or ''
        if not image_rel:
            return None

        # Try the path as recorded in the DB
        image_abs = os.path.join(REPO_ROOT, image_rel.replace('/', os.sep))
        if os.path.exists(image_abs):
            return Path(image_abs).resolve().as_uri()

        # Normalize common variation: set00 -> set0 (leading zeros removed)
        parts = image_rel.split('/')
        for i, part in enumerate(parts):
            if part.startswith('set') and part[3:].isdigit():
                try:
                    num = int(part[3:])
                except Exception:
                    continue
                new_part = 'set' + str(num)
                if new_part != part:
                    parts2 = parts.copy()
                    parts2[i] = new_part
                    new_rel = '/'.join(parts2)
                    image_abs2 = os.path.join(REPO_ROOT, new_rel.replace('/', os.sep))
                    if os.path.exists(image_abs2):
                        return Path(image_abs2).resolve().as_uri()

        # Also try removing a 'processed' segment (older layout)
        if '/processed/' in image_rel:
            new_rel = image_rel.replace('/processed/', '/')
            image_abs3 = os.path.join(REPO_ROOT, new_rel.replace('/', os.sep))
            if os.path.exists(image_abs3):
                return Path(image_abs3).resolve().as_uri()

        return None

    main_img = _img_uri_for_card(card)

    html = [
        "<html><head><meta charset=\"utf-8\"><title>Card Preview</title></head>",
        "<body style='font-family: sans-serif;'>",
    ]
    html.append(f"<h2>{title}</h2>")
    if main_img:
        html.append(f"<img src=\"{main_img}\" style=\"max-width:800px;display:block;margin-bottom:1rem;\">")
    else:
        html.append("<div style='color:#666;padding:1rem;border:1px solid #ddd'>No image found for main card</div>")

    html.append("<h3>Metadata</h3>")
    html.append('<ul>')
    for k in ('id', 'name', 'subtitle', 'set_name', 'card_type', 'culture', 'keywords'):
        v = card.get(k)
        if v is not None:
            html.append(f"<li><strong>{k}:</strong> {v}</li>")
    html.append('</ul>')

    # Candidates (if any)
    candidates = item.get('candidate_ids') or []
    if candidates:
        html.append('<h3>Candidates</h3>')
        html.append('<div style="display:flex;flex-wrap:wrap;gap:1rem;">')
        for cid in candidates:
            crec = card_db.get(cid) or {}
            cname = crec.get('name') or cid
            cimg = _img_uri_for_card(crec)
            html.append('<div style="width:240px;border:1px solid #eee;padding:0.5rem;">')
            html.append(f"<div style='font-size:0.9rem;font-weight:600;margin-bottom:0.25rem'>{cname}</div>")
            if cimg:
                html.append(f"<img src=\"{cimg}\" style=\"max-width:220px;display:block;margin-bottom:0.25rem;\">")
            else:
                html.append('<div style="color:#888;padding:0.5rem;border:1px dashed #ddd">No image</div>')
            html.append(f"<div style='font-size:0.8rem;color:#444'>ID: {cid}</div>")
            html.append('</div>')
        html.append('</div>')

    html.append("<h3>Ambiguous Item JSON</h3>")
    html.append('<pre style=\"white-space:pre-wrap;\">')
    html.append(json.dumps(item, ensure_ascii=False, indent=2))
    html.append('</pre>')
    html.append('</body></html>')

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w', encoding='utf-8')
    tmp.write('\n'.join(html))
    tmp.close()
    print('Preview written to', tmp.name, flush=True)
    return tmp.name


def open_preview_file(path: str) -> None:
    uri = Path(path).resolve().as_uri()
    try:
        # Prefer Windows native opener first — more reliable in some environments
        if sys.platform.startswith('win'):
            try:
                print('Opening preview with os.startfile...', flush=True)
                os.startfile(path)
                print('Preview opened with os.startfile', flush=True)
                return
            except Exception as exc:
                print('os.startfile failed:', exc, flush=True)

        print('Opening preview with webbrowser.open...', flush=True)
        opened = webbrowser.open(uri, new=2)
        if opened:
            print('webbrowser.open succeeded', flush=True)
            return
        # fallback: instruct manual open
        print('No browser could be opened automatically. Open this file manually:', path, flush=True)
    except Exception as exc:
        print('Failed to open preview automatically:', exc, flush=True)
        print('Preview available at:', path, flush=True)


def main(argv: List[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    p = argparse.ArgumentParser()
    p.add_argument('--preview', choices=['browser', 'none'], default='browser')
    p.add_argument('--debug', action='store_true', help='Print debug messages to help diagnose input/preview issues')
    p.add_argument('--start-card', type=str, default=None, help='Card id to start at (e.g., lotr00001)')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--resume', action='store_true')
    p.add_argument('--start-index', type=int, default=0)
    args = p.parse_args(argv)

    card_db = load_json(CARD_DB_PATH) or {}
    amb = load_json(AMB_PATH) or {}
    suggestions_map = load_json(SUGGEST_PATH) or {}
    overrides = load_json(OVERRIDES_PATH) or {}
    history = load_json(HISTORY_PATH) or []
    approval = load_json(APPROVAL_PATH) or {}

    items = amb.get('items', []) if isinstance(amb, dict) else []

    # build queue (skip approved)
    queue = [it for it in items if not approval.get(it.get('card_id'))]

    # resume support + sorting: if resuming with a snapshot, preserve order; otherwise sort by set and card number
    start_index = args.start_index
    resumed = False
    if args.resume and os.path.exists(SESSION_STATE_PATH):
        try:
            state = load_json(SESSION_STATE_PATH) or {}
            if state.get('remaining_queue'):
                queue = state.get('remaining_queue')
                start_index = int(state.get('queue_index', 0))
                resumed = True
                print(f'Resuming session at index {start_index} (remaining {len(queue)})')
        except Exception:
            pass

    def _card_sort_key_for_cid(cid: str):
        if not cid:
            return (9999, 9999, '')
        rec = card_db.get(cid) if isinstance(card_db, dict) else None
        if rec and isinstance(rec.get('set_num'), int):
            set_num = rec.get('set_num')
            collector = rec.get('collector_info') or ''
            m = re.search(r'(\d+)$', collector)
            if m:
                try:
                    card_num = int(m.group(1))
                    return (set_num, card_num, cid)
                except Exception:
                    pass
        m = re.search(r'(\d+)$', cid)
        if m:
            num = int(m.group(1))
            return (num // 1000, num % 1000, cid)
        return (9999, 9999, cid)

    def _card_sort_key(item: Dict[str, Any]):
        return _card_sort_key_for_cid((item or {}).get('card_id') or '')

    if not resumed:
        queue.sort(key=_card_sort_key)

    # allow starting at a specific card id (e.g., --start-card lotr00001)
    start_card_arg = None
    try:
        # read arg without crashing if attribute absent
        start_card_arg = args.start_card if hasattr(args, 'start_card') else None
    except Exception:
        start_card_arg = None
    if start_card_arg:
        target_key = _card_sort_key_for_cid(start_card_arg)
        for i, it in enumerate(queue):
            if _card_sort_key_for_cid(it.get('card_id') or '') >= target_key:
                start_index = i
                break

    index = max(0, start_index)
    history_delta: List[Dict] = []

    user = getpass.getuser()

    try:
        while index < len(queue):
            it = queue[index]
            card_id = it.get('card_id')
            action_id = it.get('action_id')
            raw = it.get('raw_text') or ''
            card = card_db.get(card_id) or {}
            candidates = it.get('candidate_ids') or []

            print('\n' + '=' * 60)
            print(f"Item {index+1}/{len(queue)} — Card: {card.get('name','(unknown)')} ({card_id})")
            print(f"Action: {action_id}")
            if raw:
                print('Raw:', raw)
            if candidates:
                print('Candidates:', ', '.join(candidates))

            # find suggestion for this action if present
            suggestion = None
            for s in suggestions_map.get(card_id, []):
                if isinstance(s, dict) and s.get('action_id') == action_id:
                    suggestion = s.get('suggested_card_id')
                    break

            if suggestion:
                print('Suggestion:', suggestion)

            cmd = input("Command [p=preview a=accept e=edit r=reject d=defer n=next q=quit]: ").strip().lower()
            if args.debug:
                print(f"[debug] received raw input: {cmd!r}", flush=True)
            if not cmd or cmd == 'n':
                index += 1
                continue

            if cmd == 'p':
                if args.preview == 'browser':
                    html_path = create_preview_html(card, it, card_db)
                    open_preview_file(html_path)
                else:
                    print('Preview disabled (--preview=none)')
                continue

            if cmd in ('q', 'x'):
                # safe abort: backup active files and save session state
                b1 = backup_file(OVERRIDES_PATH)
                b2 = backup_file(HISTORY_PATH)
                save_session_state(index, queue[index:], overrides, history_delta)
                print('Session saved to', SESSION_STATE_PATH)
                if b1:
                    print('Backed up overrides to', b1)
                if b2:
                    print('Backed up history to', b2)
                return 0

            if cmd in ('a', 'accept'):
                new_card = suggestion
                if not new_card:
                    new_card = input('Enter card_id to apply for this action (or blank to cancel): ').strip()
                if not new_card:
                    print('No card chosen — skip')
                    continue
                # apply in-memory
                overrides[action_id] = new_card
                entry = {
                    'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
                    'action_id': action_id,
                    'card_id': card_id,
                    'operation': 'apply',
                    'new_value': new_card,
                    'source': 'review_cli',
                    'applied_by': user,
                }
                history.append(entry)
                history_delta.append(entry)
                if not args.dry_run:
                    write_json_atomic(OVERRIDES_PATH, overrides)
                    write_json_atomic(HISTORY_PATH, history)
                    print('Wrote overrides and history')
                else:
                    print('Dry-run: override not persisted')
                index += 1
                continue

            if cmd in ('e', 'edit'):
                new_card = input('Edit -> enter card_id (or blank to cancel): ').strip()
                if new_card:
                    overrides[action_id] = new_card
                    entry = {
                        'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
                        'action_id': action_id,
                        'card_id': card_id,
                        'operation': 'edit',
                        'new_value': new_card,
                        'source': 'review_cli',
                        'applied_by': user,
                    }
                    history.append(entry)
                    history_delta.append(entry)
                    if not args.dry_run:
                        write_json_atomic(OVERRIDES_PATH, overrides)
                        write_json_atomic(HISTORY_PATH, history)
                        print('Wrote overrides and history')
                    else:
                        print('Dry-run: edit not persisted')
                index += 1
                continue

            if cmd == 'r' or cmd == 'reject':
                entry = {
                    'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
                    'action_id': action_id,
                    'card_id': card_id,
                    'operation': 'reject',
                    'reason': 'reviewer',
                    'applied_by': user,
                }
                history.append(entry)
                history_delta.append(entry)
                if not args.dry_run:
                    write_json_atomic(HISTORY_PATH, history)
                    print('Appended reject to history')
                else:
                    print('Dry-run: reject not persisted')
                index += 1
                continue

            if cmd == 'd' or cmd == 'defer':
                item = {
                    'action_id': action_id,
                    'card_id': card_id,
                    'raw_text': raw,
                    'reason': 'deferred by reviewer',
                    'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
                }
                queue_review = load_json(REVIEW_QUEUE_PATH) or []
                queue_review.append(item)
                if not args.dry_run:
                    write_json_atomic(REVIEW_QUEUE_PATH, queue_review)
                    print('Added item to review queue')
                else:
                    print('Dry-run: item not added')
                index += 1
                continue

            print('Unknown command:', cmd)
            index += 1

    except KeyboardInterrupt:
        print('\nInterrupted — saving session...')
        save_session_state(index, queue[index:], overrides, history_delta)
        return 0

    # Completed queue
    print('\nAll items processed (index reached end).')
    # remove any session snapshot on successful completion
    if os.path.exists(SESSION_STATE_PATH):
        try:
            os.remove(SESSION_STATE_PATH)
        except Exception:
            pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
