#!/usr/bin/env python3
"""
Build the card database JSON from the Cargo API dump written by
lotr_download_site.py (build/do/assets/wiki/cargo_cards.json), joining in
downloaded card images.
"""

import html
import json
import os
import re
import sys

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT   = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..'))
PYUTILS_DIR = os.path.join(REPO_ROOT, 'pyutils')
CARDS_DIR   = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'cards')
CARGO_DUMP  = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'wiki', 'cargo_cards.json')
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
    """Return int for plain (possibly negative) integer strings/numbers, else keep as-is."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if re.match(r'^-?\d+$', str(value)):
        return int(value)
    return value


def derive_card_id(set_num, card_num):
    """
    Same derivation as lotr_download_site.py's derive_card_id() -- kept in
    sync so ids match the directories images were downloaded into. Prefer
    the 'derived_id' already stamped onto each cargo_cards.json row; this is
    only a fallback if that's missing.
    """
    try:
        card_num_int = int(card_num)
    except (TypeError, ValueError):
        card_num_int = 0
    if set_num is not None and re.match(r'^\d+$', str(set_num)):
        return f"lotr{int(set_num):02d}{card_num_int:03d}"
    slug = re.sub(r'[^A-Za-z0-9]', '', str(set_num or 'x')).lower()
    return f"lotr{slug}{card_num_int:03d}"


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


def parse_notes(notes):
    """
    Split a Cargo Notes field into (cleaned_notes, list_tags).
    Notes look like 'Lists: ERL, MXL. When the fellowship moves...' or just
    'Oversized. Lists: EXL' -- the 'Lists: TAG, TAG2' fragment can appear
    anywhere in the string, not only at the start.
    """
    if not notes:
        return None, []
    m = re.search(r'Lists:\s*([A-Z]+(?:\s*,\s*[A-Z]+)*)\.?', notes)
    if not m:
        cleaned = strip_tags(html.unescape(notes)).strip() or None
        return cleaned, []
    tags = [t.strip() for t in m.group(1).split(',')]
    cleaned = notes[:m.start()] + notes[m.end():]
    cleaned = strip_tags(html.unescape(cleaned)).strip(' .')
    return (cleaned or None), tags


def find_image_path(card_dir):
    """Return the first .jpg in card_dir as a repo-root-relative forward-slash path."""
    if not card_dir:
        return None
    try:
        for fname in os.listdir(card_dir):
            if fname.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
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


def build_card(row, card_sets):
    """Build a single card dict from one joined Cargo row."""
    set_num_raw = row.get('SetNum')
    card_id = row.get('derived_id') or derive_card_id(set_num_raw, row.get('CardNum'))

    is_numeric_set = bool(set_num_raw is not None and re.match(r'^\d+$', str(set_num_raw)))
    set_num = int(set_num_raw) if is_numeric_set else set_num_raw
    set_name = card_sets.get(str(set_num_raw)) if set_num_raw is not None else None

    title = row.get('Title')
    subtitle = row.get('Subtitle') or None
    name = f"{title}, {subtitle}" if subtitle else title

    subtypes_raw = row.get('Subtypes')
    subtypes = [s.strip() for s in subtypes_raw.split(',') if s.strip()] if subtypes_raw else []

    game_text = strip_tags(html.unescape(row['GameText'])) if row.get('GameText') else None
    lore = strip_tags(html.unescape(row['Lore'])) if row.get('Lore') else None

    notes_cleaned, list_tags = parse_notes(row.get('Notes'))
    on_xlist = []
    if 'SXL' in list_tags:
        on_xlist.append('Standard')
    if 'EXL' in list_tags:
        on_xlist.append('Expanded')
    has_errata = 'ERL' in list_tags

    kind = row.get('Side')
    kind = None if kind in (None, 'None') else kind

    signet = row.get('Signet')
    signet = None if signet in (None, 'None') else signet

    unique = str(row.get('IsUnique')) == '1'
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

    set_dir_name = f"set{set_num_raw}" if set_num_raw is not None else None
    card_dir = os.path.join(CARDS_DIR, set_dir_name, card_id) if set_dir_name else None

    clean_set_seg = f"set{set_num:02d}" if is_numeric_set else f"set{set_num_raw}"
    clean_png = f'build/do/assets/cards/processed/{clean_set_seg}/{card_id}.png'

    formats = SET_FORMATS.get(set_num, ['Open']) if is_numeric_set else ['Open']

    return {
        'id':                card_id,
        'name':              name,
        'subtitle':          subtitle,
        'collector_info':    row.get('CollInfo'),
        'set_num':           set_num,
        'set_name':          set_name,
        'formats':           formats,
        'kind':              kind,
        'culture':           row.get('Culture') or None,
        'twilight':          parse_numeric(row.get('TwilightCost')),
        'card_type':         row.get('CardType'),
        'subtypes':          subtypes,
        'home_site':         None,
        'strength':          parse_numeric(row.get('Strength')),
        'vitality':          parse_numeric(row.get('Vitality')),
        'resistance':        parse_numeric(row.get('Resistance')),
        'signet':            signet,
        'site_number':       parse_numeric(row.get('SiteNum')),
        'game_text':         game_text,
        'lore':              lore,
        'rarity':            row.get('Rarity'),
        'keywords':          parse_keywords(game_text),
        'image_path':        find_image_path(card_dir),
        'image_path_clean':  clean_png,
        'on_xlist':          on_xlist or None,
        'has_errata':        has_errata,
        'unique':            unique,
    }


def main():
    global UNIQUE_OVERRIDES_DATA
    UNIQUE_OVERRIDES_DATA = {}
    if os.path.exists(UNIQUE_OVERRIDES_PATH):
        try:
            with open(UNIQUE_OVERRIDES_PATH, 'r', encoding='utf-8') as f:
                UNIQUE_OVERRIDES_DATA = json.load(f)
        except Exception as e:
            print(f'Warning: failed to load unique overrides from {UNIQUE_OVERRIDES_PATH}: {e}')

    if not os.path.exists(CARGO_DUMP):
        print(f'Cargo dump not found: {CARGO_DUMP} -- run lotr_download_site.py first.')
        sys.exit(1)

    with open(CARGO_DUMP, 'r', encoding='utf-8') as f:
        dump = json.load(f)
    card_sets = dump.get('card_sets', {})
    rows = dump.get('cards', [])

    cards = {}
    errors = []
    missing = []  # cards skipped because their derived id collides with an already-kept card

    bar = ProgressBar(label='cards', min=0, max=len(rows), units='cards')
    for i, row in enumerate(rows, 1):
        try:
            card = build_card(row, card_sets)
        except Exception as e:
            errors.append(f"{row.get('ID', '?')}: {e}")
            bar.update(i, task=row.get('Title', '') or '')
            continue

        if card['id'] in cards:
            existing = cards[card['id']]
            missing.append({
                'id':                    card['id'],
                'cargo_id':              row.get('ID'),
                'title':                 card['name'],
                'collector_info':        card['collector_info'],
                'kept_cargo_id':         existing.get('_cargo_id'),
                'kept_collector_info':   existing['collector_info'],
            })
        else:
            card['_cargo_id'] = row.get('ID')
            cards[card['id']] = card
        bar.update(i, task=row.get('Title', '') or '')
    bar.done(task='cards')

    # Drop the internal bookkeeping field before annotation/output.
    for card in cards.values():
        card.pop('_cargo_id', None)

    # Annotate cards with X-List and PC Errata status from already-built databases.
    # These are optional and additive: the primary source is each card's own
    # Cargo Notes 'Lists: ...' tag (handled in build_card above); these files
    # only fill in cards that source didn't already flag.
    xlist_index  = load_xlist_index(XLIST_DB)
    errata_index = load_errata_index(ERRATA_DB)
    for card in cards.values():
        if not card['on_xlist']:
            xlist_formats = xlist_index.get(card['id'])
            card['on_xlist'] = xlist_formats or None
        if not card['has_errata']:
            card['has_errata'] = bool(
                card.get('collector_info') and card['collector_info'] in errata_index
            )

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)

    print(f'Wrote {len(cards)} cards to {OUTPUT_PATH}')

    if missing:
        missing_path = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'missing_cards.json')
        with open(missing_path, 'w', encoding='utf-8') as f:
            json.dump(missing, f, ensure_ascii=False, indent=2)
        print(f'\n{len(missing)} card(s) skipped due to duplicate id (missing from database):')
        for m in missing[:20]:
            print(f"  MISSING: {m['id']} ({m['cargo_id']}) '{m['title']}' [{m['collector_info']}]"
                  f" -- id already used by {m['kept_cargo_id']} [{m['kept_collector_info']}]")
        if len(missing) > 20:
            print(f'  ... and {len(missing) - 20} more')
        print(f'Wrote {len(missing)} missing card entries to {missing_path}')

    if errors:
        print(f'\n{len(errors)} error(s):')
        for err in errors[:20]:
            print(f'  {err}')
        if len(errors) > 20:
            print(f'  ... and {len(errors) - 20} more')
        sys.exit(1)


if __name__ == '__main__':
    main()
