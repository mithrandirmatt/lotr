#!/usr/bin/env python3
"""Parse downloaded starter deck block HTML files and write a JSON database."""

import html
import json
import os
import re
import sys

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT    = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..'))
PYUTILS_DIR  = os.path.join(REPO_ROOT, 'pyutils')
STARTERS_DIR = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'wiki', 'starters')
STARTER_IMAGES_DIR = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'starters')
OUTPUT_PATH  = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'starter_database.json')

sys.path.insert(0, PYUTILS_DIR)
from utils.progress import ProgressBar

# Cover art (e.g. "Starter-01-Aragorn.jpg") is linked from each deck's block
# page as a File: link right after its heading, e.g.
# href="/wiki/File:Starter-01-Aragorn.jpg"
_COVER_IMAGE_RE = re.compile(r'href="/wiki/File:([^"]+?\.(?:jpg|jpeg|png))"', re.IGNORECASE)

# Maps h3 heading text fragments to output field names
_SECTION_MAP = {
    'ring-bearer':       'ring_bearer',
    'adventure deck':    'adventure_deck',
    'sites':             'adventure_deck',
    'free peoples':      'free_peoples',
    'shadow':            'shadow',
    'lotro additions':   'lotro_additions',
}


def parse_block_name(filename):
    """'Fellowship_Block.html' -> 'Fellowship Block'"""
    return os.path.splitext(filename)[0].replace('_', ' ')


def parse_deck_id(name):
    """'FOTR Aragorn Starter Deck' -> 'fotr_aragorn_starter_deck'"""
    return re.sub(r'\s+', '_', name.strip().lower())


def find_cover_image_path(filename):
    """Return the repo-root-relative forward-slash path to a downloaded cover
    image, or None if it hasn't been downloaded (see lotr_download_site.py's
    download_starter_images())."""
    if not filename:
        return None
    full_path = os.path.join(STARTER_IMAGES_DIR, filename)
    if not os.path.exists(full_path):
        return None
    return os.path.relpath(full_path, REPO_ROOT).replace('\\', '/')


def parse_section_key(h3_text):
    """Map h3 heading text to a field name, or None if unrecognised."""
    clean = h3_text.lower().strip()
    # Strip trailing count "(N cards)" noise
    clean = re.sub(r'\s*\(\d+\s+cards?\)\s*$', '', clean)
    for fragment, key in _SECTION_MAP.items():
        if fragment in clean:
            return key
    return None


def parse_card_entries(li_html_list):
    """
    Parse a list of raw <li>...</li> HTML strings into card entry dicts.
    Each entry: {count, collector_info, starting}
    collector_info is the raw token like "1C290" or "1R89".
    """
    entries = []
    for li in li_html_list:
        # Count: leading integer before the first <span or (
        count_m = re.match(r'\s*(\d+)x', li)
        count = int(count_m.group(1)) if count_m else 1

        # Collector info: last "(XNY)" token in a title="" attribute
        # e.g. title="Frodo, Son of Drogo (1C290)"
        collector_m = re.findall(r'title="[^"]+\(([^)]+)\)"', li)
        if not collector_m:
            continue
        collector_info = collector_m[-1].strip()

        # Starting: "(starting)" text after the card link
        starting = bool(re.search(r'\(starting\)', li, re.IGNORECASE))

        entries.append({
            'count':          count,
            'collector_info': collector_info,
            'starting':       starting,
        })
    return entries


def split_li_tags(html_content):
    """Return a list of raw innerHTML strings for each <li> in html_content."""
    return re.findall(r'<li>(.*?)</li>', html_content, re.DOTALL)


def parse_block_file(html_path, block_name):
    """
    Parse one starter block HTML file and return a list of deck dicts.
    """
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Locate the main page content div — skip navigation chrome
    page_m = re.search(r'<div[^>]+id="mw-content-text"[^>]*>(.*)', content, re.DOTALL)
    page_content = page_m.group(1) if page_m else content

    # Split on <h2> tags to get per-deck chunks
    # Pattern: <h2>...<span ...>DECK NAME</span>...
    h2_pattern = re.compile(
        r'<h2>[^<]*<span[^>]*id="([^"]+)"[^>]*>([^<]+)</span>', re.DOTALL
    )

    # Find all h2 positions and their names
    h2_matches = list(h2_pattern.finditer(page_content))

    decks = []
    for i, h2m in enumerate(h2_matches):
        raw_name = html.unescape(h2m.group(2)).strip()
        # Skip non-deck headings (TOC anchors, edit sections, etc.)
        if not re.search(r'starter|deck|set', raw_name, re.IGNORECASE):
            continue

        deck_id   = parse_deck_id(raw_name)
        chunk_end = h2_matches[i + 1].start() if i + 1 < len(h2_matches) else len(page_content)
        chunk     = page_content[h2m.end():chunk_end]

        cover_m = _COVER_IMAGE_RE.search(chunk)
        image_filename = cover_m.group(1) if cover_m else None

        deck = {
            'id':              deck_id,
            'name':            raw_name,
            'block':           block_name,
            'source_file':     os.path.basename(html_path),
            'image_filename':  image_filename,
            'image_path':      find_cover_image_path(image_filename),
            'ring_bearer':     [],
            'adventure_deck':  [],
            'free_peoples':    [],
            'shadow':          [],
            'lotro_additions': [],
        }

        # Split chunk on <h3> tags to get per-section content
        h3_pattern = re.compile(
            r'<h3>[^<]*<span[^>]*>([^<]+)</span>', re.DOTALL
        )
        h3_matches = list(h3_pattern.finditer(chunk))

        for j, h3m in enumerate(h3_matches):
            section_key = parse_section_key(html.unescape(h3m.group(1)))
            if not section_key:
                continue
            sec_end    = h3_matches[j + 1].start() if j + 1 < len(h3_matches) else len(chunk)
            sec_chunk  = chunk[h3m.end():sec_end]
            li_list    = split_li_tags(sec_chunk)
            entries    = parse_card_entries(li_list)
            # Multiple h3s can map to the same key (e.g. two "Shadow" sections)
            deck[section_key].extend(entries)

        decks.append(deck)

    return decks


def main():
    if not os.path.isdir(STARTERS_DIR):
        print(f'Starters directory not found: {STARTERS_DIR}')
        print('Run wiki_gather_sites first.')
        sys.exit(1)

    block_files = sorted(
        f for f in os.listdir(STARTERS_DIR) if f.endswith('.html')
    )
    if not block_files:
        print(f'No HTML files found in {STARTERS_DIR}')
        sys.exit(1)

    all_decks = {}
    errors = []

    bar = ProgressBar(label='Starter decks', min=0, max=len(block_files), units='blocks')

    for idx, filename in enumerate(block_files):
        block_name = parse_block_name(filename)
        html_path  = os.path.join(STARTERS_DIR, filename)
        try:
            decks = parse_block_file(html_path, block_name)
            for deck in decks:
                all_decks[deck['id']] = deck
        except Exception as e:
            errors.append(f'{filename}: {e}')
        bar.update(idx + 1, task=block_name)

    bar.done()

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(all_decks, f, ensure_ascii=False, indent=2)

    print(f'Wrote {len(all_decks)} starter decks to {OUTPUT_PATH}')

    if errors:
        print(f'\n{len(errors)} error(s):')
        for err in errors[:20]:
            print(f'  {err}')
        if len(errors) > 20:
            print(f'  ... and {len(errors) - 20} more')
        sys.exit(1)


if __name__ == '__main__':
    main()
