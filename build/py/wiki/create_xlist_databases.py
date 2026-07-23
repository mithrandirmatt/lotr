#!/usr/bin/env python3
"""Build the X-List database from Cargo data, and parse PC_Errata.html."""

import html
import json
import os
import re
import sys

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT    = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..'))
WIKI_DIR     = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'wiki')
DB_DIR       = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database')
CARGO_DUMP   = os.path.join(WIKI_DIR, 'cargo_cards.json')
ERRATA_HTML  = os.path.join(WIKI_DIR, 'PC_Errata.html')
XLIST_OUT    = os.path.join(DB_DIR, 'xlist_database.json')
ERRATA_OUT   = os.path.join(DB_DIR, 'errata_database.json')


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def strip_tags(text):
    """Remove HTML tags, unescape entities, collapse whitespace."""
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


# ---------------------------------------------------------------------------
# X-List builder (from Cargo data)
# ---------------------------------------------------------------------------
# The old DokuWiki x-list.html page (with its own <table class="inline">
# markup) no longer exists -- the wiki migrated to wiki.lotrtcgpc.net
# (MediaWiki + Cargo). Exclusion-list membership is exposed per-card via a
# 'Lists: SXL, EXL, ...' tag embedded in each card's Cargo Notes field
# (SXL = Standard Exclusion List, EXL = Expanded Exclusion List), which
# lotr_download_site.py already captures in cargo_cards.json. Exact
# date_added/date_removed values aren't exposed via Cargo, so those fields
# are left None; any residual note text is preserved.

_LISTS_TAG_RE = re.compile(r'Lists:\s*([A-Z]+(?:\s*,\s*[A-Z]+)*)\.?')


def _parse_notes_lists(notes):
    """Return (cleaned_notes, list_tags) from a Cargo Notes field."""
    if not notes:
        return None, []
    m = _LISTS_TAG_RE.search(notes)
    if not m:
        return strip_tags(notes) or None, []
    tags = [t.strip() for t in m.group(1).split(',')]
    cleaned = notes[:m.start()] + notes[m.end():]
    return strip_tags(cleaned).strip(' .') or None, tags


def derive_card_id(set_num, card_num):
    """Same derivation as lotr_download_site.py's derive_card_id()."""
    try:
        card_num_int = int(card_num)
    except (TypeError, ValueError):
        card_num_int = 0
    if set_num is not None and re.match(r'^\d+$', str(set_num)):
        return f"lotr{int(set_num):02d}{card_num_int:03d}"
    slug = re.sub(r'[^A-Za-z0-9]', '', str(set_num or 'x')).lower()
    return f"lotr{slug}{card_num_int:03d}"


def build_xlist_from_cargo(cargo_path):
    """
    Build the xlist_database.json structure from cargo_cards.json.
    Returns (dict keyed by card id, errors).
    """
    if not os.path.exists(cargo_path):
        return {}, [f'{cargo_path} not found']

    with open(cargo_path, 'r', encoding='utf-8') as f:
        dump = json.load(f)

    result = {}
    for row in dump.get('cards', []):
        cleaned_notes, tags = _parse_notes_lists(row.get('Notes'))
        formats = []
        if 'SXL' in tags:
            formats.append('Standard')
        if 'EXL' in tags:
            formats.append('Expanded')
        if not formats:
            continue

        wiki_id = row.get('derived_id') or derive_card_id(row.get('SetNum'), row.get('CardNum'))
        title = row.get('Title')
        subtitle = row.get('Subtitle')
        card_name = f"{title}, {subtitle}" if subtitle else title

        result[wiki_id] = {
            'card_name': card_name,
            'formats': [
                {'format': fmt, 'date_added': None, 'date_removed': None, 'notes': cleaned_notes}
                for fmt in formats
            ],
        }
    return result, []



# ---------------------------------------------------------------------------
# PC Errata parser (MediaWiki source)
# ---------------------------------------------------------------------------

_ERRATA_SKIP_HEADINGS = {'x-list errata', 'references', 'notes', 'contents'}


def _extract_collector_info(title_attr):
    """Return the last (XNY) token from a title attribute string, or None."""
    matches = re.findall(r'\(([^)]+)\)', title_attr)
    return matches[-1].strip() if matches else None


def _card_name_from_anchor_text(text):
    """Strip non-breaking spaces and trailing '(collector_info)' suffix."""
    text = html.unescape(text).replace('\u00a0', ' ').strip()
    # Remove trailing parenthesised collector info e.g. " (1C5)"
    text = re.sub(r'\s*\([^)]+\)\s*$', '', text).strip()
    return text


def parse_errata_html(html_path):
    """
    Parse PC_Errata.html.
    Returns dict keyed by collector_info:
      { card_name, batches: [batch_label, ...] }
    """
    content = read_file(html_path)

    # Scope to the main content div
    content_m = re.search(
        r'<div[^>]+id="mw-content-text"[^>]*>(.*)',
        content, re.DOTALL
    )
    page = content_m.group(1) if content_m else content

    # Find all h2 positions with their headline text
    h2_pattern = re.compile(
        r'<h2>[^<]*<span[^>]*class="mw-headline"[^>]*>([^<]+)</span>',
        re.DOTALL
    )
    h2_matches = list(h2_pattern.finditer(page))

    result = {}
    errors = []

    for i, h2m in enumerate(h2_matches):
        batch_label = html.unescape(h2m.group(1)).strip()

        if batch_label.lower() in _ERRATA_SKIP_HEADINGS:
            continue

        chunk_end = h2_matches[i + 1].start() if i + 1 < len(h2_matches) else len(page)
        chunk = page[h2m.end():chunk_end]

        # Find all <li> entries with tooltip anchors
        li_list = re.findall(r'<li>(.*?)</li>', chunk, re.DOTALL)

        for li in li_list:
            title_m = re.search(r'title="([^"]+)"', li)
            if not title_m:
                continue

            collector_info = _extract_collector_info(title_m.group(1))
            if not collector_info:
                continue

            # card name from anchor text
            anchor_text_m = re.search(r'<a[^>]+>([^<]+)</a>', li)
            if anchor_text_m:
                card_name = _card_name_from_anchor_text(anchor_text_m.group(1))
            else:
                card_name = strip_tags(li)
                card_name = re.sub(r'\s*\([^)]+\)\s*$', '', card_name).strip()

            if collector_info not in result:
                result[collector_info] = {
                    'card_name': card_name,
                    'batches':   [],
                }
            if batch_label not in result[collector_info]['batches']:
                result[collector_info]['batches'].append(batch_label)

    return result, errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    all_errors = []

    # --- X-List ---
    print('Building X-List database from Cargo data...')
    xlist_db, xlist_errors = build_xlist_from_cargo(CARGO_DUMP)
    all_errors.extend(f'[xlist] {e}' for e in xlist_errors)

    os.makedirs(DB_DIR, exist_ok=True)
    with open(XLIST_OUT, 'w', encoding='utf-8') as f:
        json.dump(xlist_db, f, ensure_ascii=False, indent=2)
    print(f'Wrote {len(xlist_db)} X-List entries to {XLIST_OUT}')

    # --- PC Errata ---
    if not os.path.exists(ERRATA_HTML):
        print(f'ERROR: {ERRATA_HTML} not found. Run wiki_gather_sites first.')
        sys.exit(1)

    print('Parsing PC_Errata.html...')
    errata_db, errata_errors = parse_errata_html(ERRATA_HTML)
    all_errors.extend(f'[errata] {e}' for e in errata_errors)

    with open(ERRATA_OUT, 'w', encoding='utf-8') as f:
        json.dump(errata_db, f, ensure_ascii=False, indent=2)
    print(f'Wrote {len(errata_db)} Errata entries to {ERRATA_OUT}')

    # --- Summary ---
    if all_errors:
        print(f'\n{len(all_errors)} error(s):')
        for err in all_errors[:20]:
            print(f'  {err}')
        if len(all_errors) > 20:
            print(f'  ... and {len(all_errors) - 20} more')
        sys.exit(1)


if __name__ == '__main__':
    main()
