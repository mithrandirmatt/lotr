#!/usr/bin/env python3
"""Parse all downloaded LotR TCG card HTML files and write a JSON database."""

import html
import json
import os
import re
import sys

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT   = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..'))
PYUTILS_DIR = os.path.join(REPO_ROOT, 'pyutils')
CARDS_DIR   = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'cards')
START_HTML  = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'wiki', 'start.html')
OUTPUT_PATH = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'card_database.json')
XLIST_DB    = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'xlist_database.json')
ERRATA_DB   = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'errata_database.json')
UNIQUE_OVERRIDES_PATH = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'card_unique_overrides.json')
UNIQUE_OVERRIDES_DATA = {}

sys.path.insert(0, PYUTILS_DIR)
from utils.progress import ProgressBar

# Static set-to-format membership. A card belongs to every format whose
# set range includes its set_num. Set 0 (Promos) is Open/Standard only.
SET_FORMATS = {
    0:  ['Open'],
    1:  ['Fellowship Block', 'Open'],
    2:  ['Fellowship Block', 'Open'],
    3:  ['Fellowship Block', 'Open'],
    4:  ['Tower Block', 'Open'],
    5:  ['Tower Block', 'Open'],
    6:  ['Tower Block', 'Open'],
    7:  ['King Block', 'Open'],
    8:  ['King Block', 'Open'],
    9:  ['Open'],
    10: ['King Block', 'Expanded', 'Standard', 'Open'],
    11: ['Expanded', 'Standard', 'Open'],
    12: ['Expanded', 'Standard', 'Open'],
    13: ['Expanded', 'Standard', 'Open'],
    14: ['Standard', 'Open'],
    15: ['Standard', 'Open'],
    16: ['Standard', 'Open'],
    17: ['Standard', 'Open'],
    18: ['Standard', 'Open'],
    19: ['Standard', 'Open'],
}

# Standalone-sentence keyword detection.
# A keyword is any sentence in game_text that is a single word (or word + value),
# sourced from Comprehensive Rules v4.2/v5.0 and observed card data.
# Examples: "Archer." -> "archer"; "Damage +1." -> "damage +1"; "Forest." -> "forest"
_KW_PATTERN = re.compile(r'^[A-Za-z][A-Za-z\-]+(?:\s+\+?\d+)?$')


def strip_tags(text):
    """Remove HTML tags, unescape entities, and collapse whitespace."""
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    return ' '.join(text.split())


def parse_numeric(value):
    """Return int for plain integer strings, else keep as string (e.g. '+1')."""
    if re.match(r'^\d+$', value):
        return int(value)
    return value


def parse_title_tag(content):
    """Extract name and collector_info from the <title> tag."""
    m = re.search(r'<title>LotR TCG Wiki: (.+?)</title>', content)
    if not m:
        return None, None
    raw = html.unescape(m.group(1))
    # Last parenthesized token is collector_info, e.g. "(1R89)"
    m2 = re.match(r'^(.+?)\s+(\([^)]+\))\s*$', raw)
    if m2:
        return m2.group(1).strip(), m2.group(2).strip('()')
    return raw, None


def parse_inline_table(content):
    """
    Extract col0/col1 pairs from the card data <table class="inline">.
    Returns a dict mapping stripped label text -> stripped value text.
    """
    m = re.search(r'<table class="inline">(.*?)</table>', content, re.DOTALL)
    if not m:
        return {}
    table_html = m.group(1)
    rows = {}
    for row_m in re.finditer(
        r'<td class="col0">(.*?)</td>\s*<td class="col1">(.*?)</td>',
        table_html, re.DOTALL
    ):
        label = strip_tags(row_m.group(1)).rstrip(':').strip()
        value = strip_tags(row_m.group(2)).strip()
        rows[label] = value
    return rows


def parse_card_type(raw):
    """
    Split card type on bullet U+2022, return (card_type, subtypes, home_site).
    E.g. 'Companion • Man' -> ('Companion', ['Man'], None)
    E.g. 'Ally • Home 3 • Elf' -> ('Ally', ['Elf'], 3)
    """
    parts = [p.strip() for p in raw.split('\u2022')]
    card_type = parts[0] if parts else raw
    home_site = None
    subtypes = []
    for sub in parts[1:]:
        home_m = re.match(r'^Home\s+(\d+)$', sub, re.IGNORECASE)
        if home_m:
            home_site = int(home_m.group(1))
        else:
            subtypes.append(sub)
    return card_type, subtypes, home_site


def parse_set_names(start_html_path):
    """
    Parse start.html to build a set_num -> set_name mapping.
    Looks for wrap_setthumbs divs containing href="/wiki/setN" anchors.
    Returns dict[int, str].
    """
    with open(start_html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    set_names = {}
    for block in re.finditer(
        r'class="wrap_setthumbs[^"]*"[^>]*>(.*?)</div>', content, re.DOTALL
    ):
        block_html = block.group(1)
        num_m = re.search(r'href="/wiki/set(\d+)"', block_html)
        if not num_m:
            continue
        set_num = int(num_m.group(1))
        name_m = re.search(r'<br\s*/>\s*\n?\s*([^\n<]+)', block_html)
        if name_m:
            set_names[set_num] = html.unescape(name_m.group(1).strip())
    return set_names


def parse_subtitle(name):
    """Return the subtitle portion of 'Title, Subtitle', or None."""
    if not name:
        return None
    idx = name.find(', ')
    return name[idx + 2:] if idx != -1 else None


def parse_keywords(game_text):
    """
    Extract standalone keyword sentences from stripped game text.
    Keywords are sentences consisting of a single word (or word + numeric value).
    This covers all intrinsic card keywords and site terrain types without a
    hard-coded list, per Comprehensive Rules v4.2/v5.0.

    Examples:
      "Archer. Fierce. Damage +1. While you can spot..." -> ["archer", "fierce", "damage +1"]
      "Battleground. Underground. The Balrog..."         -> ["battleground", "underground"]
      "While skirmishing a fierce minion..."             -> []  (not a standalone sentence)
    """
    if not game_text:
        return []
    keywords = []
    for raw_sent in re.split(r'\. ', game_text):
        sent = raw_sent.rstrip('.')
        # Normalise en/em dashes to space (handles "Aid \u2013 2" variants)
        sent = re.sub(r'[\u2013\u2014]', ' ', sent)
        sent = re.sub(r'\s+', ' ', sent).strip()
        if _KW_PATTERN.match(sent):
            keywords.append(sent.lower())
    return keywords


def normalize_title(name):
    """Return a normalized lowercase title used as a lookup key in overrides."""
    if not name:
        return ''
    s = name.strip().lower()
    s = re.sub(r'\s+', ' ', s)
    return s


def infer_unique_by_heuristics(name, card_type, game_text, fields):
    """
    Heuristic determination of whether a card is unique.
    Current heuristic: name starts with 'The ' OR contains a comma.
    """
    if not name:
        return False
    if name.startswith('The ') or ',' in name:
        return True
    return False


def find_image_path(card_dir):
    """Return the first .jpg in card_dir as a repo-root-relative forward-slash path."""
    try:
        for fname in os.listdir(card_dir):
            if fname.lower().endswith('.jpg'):
                rel = os.path.relpath(os.path.join(card_dir, fname), REPO_ROOT)
                return rel.replace('\\', '/')
    except OSError:
        pass
    return None


def load_xlist_index(path):
    """Return dict[wiki_id -> [format_name, ...]] from xlist_database.json."""
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        db = json.load(f)
    return {wid: [e['format'] for e in entry['formats']] for wid, entry in db.items()}


def load_errata_index(path):
    """Return set of collector_info strings from errata_database.json."""
    if not os.path.exists(path):
        return set()
    with open(path, 'r', encoding='utf-8') as f:
        db = json.load(f)
    return set(db.keys())


def parse_card(html_path, card_id, set_names):
    """Parse a single card HTML file and return the card dict."""
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    name, collector_info = parse_title_tag(content)

    # Set number from card_id filename: lotrSSNNN -> digits 4-5
    set_num = int(card_id[4:6])
    set_name = set_names.get(set_num)

    fields = parse_inline_table(content)

    card_type_raw = fields.get('Card Type', '')
    card_type, subtypes, home_site = parse_card_type(card_type_raw)

    def get_numeric(key):
        val = fields.get(key)
        return parse_numeric(val) if val is not None else None

    def get_str(key):
        val = fields.get(key)
        return val if val else None

    game_text = get_str('Game Text')
    card_dir  = os.path.dirname(html_path)

    # Determine uniqueness (heuristics), allow overrides via UNIQUE_OVERRIDES_DATA.
    unique = infer_unique_by_heuristics(name, card_type, game_text, fields)
    try:
        if UNIQUE_OVERRIDES_DATA:
            if card_id in UNIQUE_OVERRIDES_DATA:
                unique = bool(UNIQUE_OVERRIDES_DATA[card_id])
            else:
                norm = normalize_title(name)
                if norm in UNIQUE_OVERRIDES_DATA:
                    unique = bool(UNIQUE_OVERRIDES_DATA[norm])
    except Exception:
        pass

    # Derive the expected processed PNG path (produced by process_card_images.py).
    # This is a forward-slash repo-root-relative path; the file may not exist yet.
    clean_png = f'build/do/assets/cards/processed/set{set_num:02d}/{card_id}.png'

    return {
        'id':             card_id,
        'name':           name,
        'subtitle':       parse_subtitle(name),
        'collector_info': collector_info,
        'set_num':        set_num,
        'set_name':       set_name,
        'formats':        SET_FORMATS.get(set_num, ['Open']),
        'kind':           get_str('Kind'),
        'culture':        get_str('Culture'),
        'twilight':       get_numeric('Twilight'),
        'card_type':      card_type,
        'subtypes':       subtypes,
        'home_site':      home_site,
        'strength':       get_numeric('Strength'),
        'vitality':       get_numeric('Vitality'),
        'resistance':     get_numeric('Resistance'),
        'signet':         get_str('Signet'),
        'site_number':    get_numeric('Site'),
        'game_text':      game_text,
        'lore':           get_str('Lore'),
        'rarity':         get_str('Rarity'),
        'keywords':        parse_keywords(game_text),
        'image_path':      find_image_path(card_dir),
        'image_path_clean': clean_png,
        'on_xlist':        None,   # populated in main() post-processing
        'has_errata':      False,  # populated in main() post-processing
        'unique':          unique,
    }


def main():
    set_names = parse_set_names(START_HTML)

    # Load unique overrides if present (maps card_id or normalized title -> bool)
    global UNIQUE_OVERRIDES_DATA
    UNIQUE_OVERRIDES_DATA = {}
    if os.path.exists(UNIQUE_OVERRIDES_PATH):
        try:
            with open(UNIQUE_OVERRIDES_PATH, 'r', encoding='utf-8') as f:
                UNIQUE_OVERRIDES_DATA = json.load(f)
        except Exception as e:
            print(f'Warning: failed to load unique overrides from {UNIQUE_OVERRIDES_PATH}: {e}')

    cards = {}
    errors = []

    for set_dir in sorted(os.listdir(CARDS_DIR)):
        set_path = os.path.join(CARDS_DIR, set_dir)
        if not os.path.isdir(set_path):
            continue

        set_num = int(re.sub(r'\D', '', set_dir)) if re.search(r'\d', set_dir) else 0
        set_name = set_names.get(set_num, set_dir)

        card_ids = [
            card_id for card_id in sorted(os.listdir(set_path))
            if os.path.isdir(os.path.join(set_path, card_id))
            and os.path.exists(os.path.join(set_path, card_id, card_id + '.html'))
        ]

        bar = ProgressBar(label=f'{set_dir:<8}', min=0, max=len(card_ids), units='cards')
        set_count = 0
        set_errors = 0

        for card_id in card_ids:
            html_file = os.path.join(set_path, card_id, card_id + '.html')
            try:
                cards[card_id] = parse_card(html_file, card_id, set_names)
                set_count += 1
            except Exception as e:
                errors.append(f'{card_id}: {e}')
                set_errors += 1
            bar.update(set_count + set_errors, task=card_id)

        error_note = f'  {set_errors} error(s)' if set_errors else ''
        bar.done(task=set_name + error_note)

    # Annotate cards with X-List and PC Errata status from already-built databases.
    # These are optional: if the database files don't exist yet, fields stay at defaults.
    xlist_index  = load_xlist_index(XLIST_DB)
    errata_index = load_errata_index(ERRATA_DB)
    for card in cards.values():
        xlist_formats = xlist_index.get(card['id'])
        card['on_xlist']   = xlist_formats or None
        card['has_errata'] = bool(
            card.get('collector_info') and card['collector_info'] in errata_index
        )

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)

    print(f'Wrote {len(cards)} cards to {OUTPUT_PATH}')

    if errors:
        print(f'\n{len(errors)} error(s):')
        for err in errors[:20]:
            print(f'  {err}')
        if len(errors) > 20:
            print(f'  ... and {len(errors) - 20} more')
        sys.exit(1)


if __name__ == '__main__':
    main()
