#!/usr/bin/env python3
"""Parse x-list.html and PC_Errata.html and write two JSON databases."""

import html
import json
import os
import re
import sys

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT    = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..'))
WIKI_DIR     = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'wiki')
DB_DIR       = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database')
XLIST_HTML   = os.path.join(WIKI_DIR, 'x-list.html')
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
# X-List parser (DokuWiki source)
# ---------------------------------------------------------------------------

# Map h3 anchor names to format labels
_XLIST_SECTIONS = {
    'cards_on_the_standard_format_exclusion_list':  'Standard',
    'cards_on_the_expanded_format_exclusion_list':  'Expanded',
}


def _parse_xlist_table_rows(table_html, format_label):
    """
    Parse rows from a DokuWiki <table class="inline">.
    Returns list of (wiki_id, card_name, date_added, date_removed, notes).
    Skips the header row (contains <strong> tags).
    """
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL)
    entries = []
    for row in rows:
        if '<strong>' in row:   # header row
            continue

        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if not cells:
            continue

        # col0: card name + wikilink
        cell0 = cells[0]
        link_m = re.search(r'href="/wiki/(lotr\w+)"', cell0)
        if not link_m:
            continue
        wiki_id   = link_m.group(1)
        card_name = strip_tags(cell0)

        # col1: date_added (present for both Standard and Expanded)
        date_added = strip_tags(cells[1]) if len(cells) > 1 else None
        date_added = date_added or None

        # col2: date_removed (Standard only; Expanded uses colspan on col1)
        # Expanded rows have col1 with colspan="2" so len(cells)==2
        if len(cells) >= 3:
            date_removed = strip_tags(cells[2]) or None
        else:
            date_removed = None

        # col3: notes (Standard only; may also be empty)
        if len(cells) >= 4:
            notes = strip_tags(cells[3]) or None
        else:
            notes = None

        entries.append({
            'wiki_id':      wiki_id,
            'card_name':    card_name,
            'format':       format_label,
            'date_added':   date_added,
            'date_removed': date_removed,
            'notes':        notes,
        })
    return entries


def _find_table_after_h3(content, anchor_name):
    """
    Locate the first <table class="inline"> that follows the h3 with
    the given anchor name. Returns the raw table HTML or None.
    """
    # Find the h3 position
    h3_m = re.search(
        r'<h3>[^<]*<a\s+name="' + re.escape(anchor_name) + r'"',
        content
    )
    if not h3_m:
        return None
    after = content[h3_m.end():]
    # Find next table.inline
    table_m = re.search(r'<table class="inline">(.*?)</table>', after, re.DOTALL)
    if not table_m:
        return None
    return table_m.group(0)


def parse_xlist_html(html_path):
    """
    Parse x-list.html.
    Returns dict keyed by wiki_id:
      { card_name, formats: [{format, date_added, date_removed, notes}] }
    """
    content = read_file(html_path)

    # Scope to the main page div
    page_m = re.search(r'<div class="page">(.*)', content, re.DOTALL)
    page = page_m.group(1) if page_m else content

    result = {}
    errors = []

    for anchor, format_label in _XLIST_SECTIONS.items():
        table_html = _find_table_after_h3(page, anchor)
        if not table_html:
            errors.append(f'Section not found: {anchor}')
            continue

        try:
            rows = _parse_xlist_table_rows(table_html, format_label)
        except Exception as e:
            errors.append(f'Error parsing {format_label} table: {e}')
            continue

        for row in rows:
            wiki_id   = row['wiki_id']
            card_name = row['card_name']
            fmt_entry = {
                'format':       row['format'],
                'date_added':   row['date_added'],
                'date_removed': row['date_removed'],
                'notes':        row['notes'],
            }
            if wiki_id not in result:
                result[wiki_id] = {'card_name': card_name, 'formats': []}
            result[wiki_id]['formats'].append(fmt_entry)

    return result, errors


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
    if not os.path.exists(XLIST_HTML):
        print(f'ERROR: {XLIST_HTML} not found. Run wiki_gather_sites first.')
        sys.exit(1)

    print('Parsing x-list.html...')
    xlist_db, xlist_errors = parse_xlist_html(XLIST_HTML)
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
