#!/usr/bin/env python3
"""
Download HTML content from LOTR wiki sites and save them locally.

Card data itself is no longer scraped from rendered HTML: wiki.lotrtcgpc.net
(the MediaWiki site the wiki migrated to) exposes a Cargo extension with
structured `Cards`/`CardReleases`/`CardSets` tables queryable via api.php.
That structured data (plus resolved card image URLs) is fetched here and
dumped to cargo_cards.json for create_card_database.py to consume.
"""

import concurrent.futures
import configparser
import json
import os
import re
import sys
import time
from urllib.parse import urlparse

import requests

# Add pyutils to the path so we can import our web utilities
# When run from the root directory, we need to adjust the path
script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
sys.path.insert(0, os.path.join(repo_root, 'pyutils'))

# Import the web utilities
from web.utils import download_html, download_binary, get_filename_from_url
from utils.progress import ProgressBar

ASSETS_DIR   = os.path.abspath(os.path.join(script_dir, '..', '..', 'do', 'assets', 'wiki'))
CARDS_DIR    = os.path.abspath(os.path.join(script_dir, '..', '..', 'do', 'assets', 'cards'))
STARTERS_DIR = os.path.abspath(os.path.join(script_dir, '..', '..', 'do', 'assets', 'wiki', 'starters'))
STARTER_IMAGES_DIR = os.path.abspath(os.path.join(script_dir, '..', '..', 'do', 'assets', 'starters'))
CARGO_DUMP_PATH = os.path.join(ASSETS_DIR, 'cargo_cards.json')

# Starter deck cover art (e.g. "Starter-01-Aragorn.jpg") is linked from each
# deck's block page as a File: link right after its heading, e.g.
# href="/wiki/File:Starter-01-Aragorn.jpg"
_STARTER_IMAGE_RE = re.compile(r'href="/wiki/File:([^"]+?\.(?:jpg|jpeg|png))"', re.IGNORECASE)

CARGO_PAGE_LIMIT = 500

# Fields pulled from the joined Cards+CardReleases Cargo tables. Cards holds
# the one canonical row per named card; CardReleases holds the per-printing
# stats/text (there is a 1:1 CardReleases row sharing the same ID as its
# Cards row -- see build/py/wiki/README or the wiki's Template:BaseCard /
# Template:CardRelease Cargo declarations for the full schema).
CARGO_FIELDS = [
    'Cards.ID=ID',
    'Cards.Title=Title',
    'Cards.Subtitle=Subtitle',
    'Cards.SetNum=SetNum',
    'Cards.CardNum=CardNum',
    'Cards.Rarity=Rarity',
    'Cards.CollInfo=CollInfo',
    'Cards.Culture=Culture',
    'Cards.Side=Side',
    'Cards.CardType=CardType',
    'Cards.Notes=Notes',
    'CardReleases.TwilightCost=TwilightCost',
    'CardReleases.Strength=Strength',
    'CardReleases.Vitality=Vitality',
    'CardReleases.Resistance=Resistance',
    'CardReleases.SiteNum=SiteNum',
    'CardReleases.Signet=Signet',
    'CardReleases.GameText=GameText',
    'CardReleases.Lore=Lore',
    'CardReleases.ImageFilename=ImageFilename',
    'CardReleases.Subtypes=Subtypes',
    'CardReleases.IsUnique=IsUnique',
]


def load_wiki_config():
    """Load wiki source URLs from build.ini configuration file."""
    config = configparser.ConfigParser()

    # build/py/wiki/ -> build/py/ -> build/ -> build.ini
    config_file = os.path.join(os.path.dirname(__file__), '..', '..', 'build.ini')
    config_file = os.path.abspath(config_file)

    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")

    config.read(config_file)

    # Get wiki sources from the configuration
    wiki_sources = {}
    if 'WIKI_SRC' in config:
        for key, value in config['WIKI_SRC'].items():
            wiki_sources[key] = value

    return wiki_sources

def get_pc_base_url(wiki_sources):
    """Return the scheme+host for the wiki.lotrtcgpc.net source."""
    for url in wiki_sources.values():
        parsed = urlparse(url)
        if 'lotrtcgpc.net' in parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    return None

def detect_starter_block_urls(starter_html_path, pc_base_url):
    """
    Parse the downloaded Starter_Decks.html and return a dict of
    {block_slug: full_url} for each Starter_Decks/Block sub-page.
    E.g. {"Fellowship_Block": "https://wiki.lotrtcgpc.net/wiki/Starter_Decks/Fellowship_Block"}
    """
    with open(starter_html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    seen = set()
    blocks = {}
    for path in re.findall(r'href="(/wiki/Starter_Decks/([^"#]+))"', content):
        full_path, slug = path
        if slug not in seen:
            seen.add(slug)
            blocks[slug] = pc_base_url + full_path
    return blocks

def sanitize_filename(name):
    """Replace characters that are invalid in file names with underscores."""
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def derive_card_id(set_num, card_num):
    """
    Deterministically derive the same lotrNNNNN id scheme the old
    lotrtcgwiki.com DokuWiki site used (2-digit set number + 3-digit card
    number, e.g. set 0 / card 25 -> 'lotr00025'), so existing downstream
    state (gotdot/assets/data/approval_status.json, Godot scripts) keyed by
    these ids stays valid across the site migration.

    For sets that aren't a plain integer (Player's Council sets like 'V1',
    'V2', 'V3', or the Hobbit Draft Game sets '30'-'32' already fit the
    numeric case) a slug fallback is used instead.
    """
    try:
        card_num_int = int(card_num)
    except (TypeError, ValueError):
        card_num_int = 0
    if set_num is not None and re.match(r'^\d+$', str(set_num)):
        return f"lotr{int(set_num):02d}{card_num_int:03d}"
    slug = re.sub(r'[^A-Za-z0-9]', '', str(set_num or 'x')).lower()
    return f"lotr{slug}{card_num_int:03d}"

def get_set_num(card_id):
    """Not derivable from the new-style card id alone; kept for compatibility."""
    m = re.match(r'^lotr(\d{2})\d{3}$', card_id)
    return int(m.group(1)) if m else None

def format_display_id(set_num, card_num):
    """
    Human-readable 'lotr-<set>-<card>' label for progress/log display -- a
    dashed variant of derive_card_id's folder-safe 'lotrNNNNN' id.
    """
    try:
        card_num_int = int(card_num)
    except (TypeError, ValueError):
        card_num_int = 0
    if set_num is not None and re.match(r'^\d+$', str(set_num)):
        return f"lotr-{int(set_num):02d}-{card_num_int:03d}"
    slug = re.sub(r'[^A-Za-z0-9]', '', str(set_num or 'x')).lower()
    return f"lotr-{slug}-{card_num_int:03d}"

def _cargo_request(base_url, params, retries=3, backoff=2.0):
    """GET api.php with the given params, retrying transient failures."""
    url = f"{base_url}/api.php"
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if 'error' in data:
                raise RuntimeError(f"Cargo API error: {data['error']}")
            return data
        except (requests.RequestException, RuntimeError, ValueError) as e:
            last_error = e
            if attempt < retries:
                time.sleep(backoff * attempt)
    raise RuntimeError(f"Failed to query {url} with {params}: {last_error}")

def fetch_cargo_cards(base_url):
    """
    Fetch every row of the joined Cards+CardReleases Cargo tables (paginated).
    Returns a list of dicts with the keys from CARGO_FIELDS.
    """
    rows = []
    offset = 0
    while True:
        params = {
            'action': 'cargoquery',
            'tables': 'Cards,CardReleases',
            'join on': 'Cards.ID=CardReleases.ID',
            'fields': ','.join(CARGO_FIELDS),
            'limit': CARGO_PAGE_LIMIT,
            'offset': offset,
            'format': 'json',
        }
        data = _cargo_request(base_url, params)
        page = [entry['title'] for entry in data.get('cargoquery', [])]
        rows.extend(page)
        print(f"  Fetched {len(rows)} card rows so far (offset {offset})...")
        if len(page) < CARGO_PAGE_LIMIT:
            break
        offset += CARGO_PAGE_LIMIT
    return rows

def fetch_card_sets(base_url):
    """Fetch the CardSets Cargo table. Returns dict[set_num_str] = set_name."""
    sets = {}
    offset = 0
    while True:
        params = {
            'action': 'cargoquery',
            'tables': 'CardSets',
            'fields': 'ID,Name',
            'limit': CARGO_PAGE_LIMIT,
            'offset': offset,
            'format': 'json',
        }
        data = _cargo_request(base_url, params)
        page = [entry['title'] for entry in data.get('cargoquery', [])]
        for entry in page:
            if entry.get('ID'):
                sets[entry['ID']] = entry.get('Name')
        if len(page) < CARGO_PAGE_LIMIT:
            break
        offset += CARGO_PAGE_LIMIT
    return sets

def _resolve_image_batch(base_url, filenames):
    """Resolve a batch (<=50) of File: titles to their direct image URLs."""
    titles = '|'.join(f"File:{name}" for name in filenames)
    params = {
        'action': 'query',
        'titles': titles,
        'prop': 'imageinfo',
        'iiprop': 'url',
        'format': 'json',
    }
    data = _cargo_request(base_url, params)
    # MediaWiki normalizes titles when echoing them back (e.g. underscores ->
    # spaces), so map normalized title -> original title first to recover the
    # exact (underscored) filename used as the Cargo ImageFilename value.
    normalized_to_original = {
        n['to']: n['from'] for n in data.get('query', {}).get('normalized', [])
    }
    resolved = {}
    pages = data.get('query', {}).get('pages', {})
    for page in pages.values():
        title = page.get('title', '')
        original_title = normalized_to_original.get(title, title)
        filename = original_title[len('File:'):] if original_title.startswith('File:') else original_title
        info = page.get('imageinfo')
        if info:
            resolved[filename] = info[0].get('url')
    return resolved

def resolve_image_urls(base_url, filenames):
    """Resolve many File: titles to direct image URLs, batching 50 at a time."""
    filenames = sorted(set(f for f in filenames if f))
    resolved = {}
    for i in range(0, len(filenames), 50):
        batch = filenames[i:i + 50]
        resolved.update(_resolve_image_batch(base_url, batch))
    return resolved

def _download_card_image(card_id, set_num, filename, image_url):
    """Download a single card image. Returns None on success, else an error string."""
    set_dir = f"set{set_num}" if set_num is not None else "setx"
    card_dir = os.path.join(CARDS_DIR, set_dir, card_id)
    save_path = os.path.join(card_dir, filename)
    if os.path.exists(save_path):
        return None
    if not download_binary(image_url, save_path):
        return f"{card_id}: failed to download image from {image_url}"
    return None

def download_cargo_data(wiki_sources):
    """
    Fetch all card data from the Cargo API, dump it to cargo_cards.json, and
    download every referenced card image. Returns a list of error strings.
    """
    base_url = get_pc_base_url(wiki_sources)
    if not base_url:
        print("No wiki.lotrtcgpc.net source configured — skipping Cargo card fetch.")
        return []

    print("Fetching card data from the Cargo API...")
    card_sets = fetch_card_sets(base_url)
    rows = fetch_cargo_cards(base_url)
    print(f"Fetched {len(rows)} card rows and {len(card_sets)} sets.")

    for row in rows:
        row['derived_id'] = derive_card_id(row.get('SetNum'), row.get('CardNum'))

    os.makedirs(ASSETS_DIR, exist_ok=True)
    with open(CARGO_DUMP_PATH, 'w', encoding='utf-8') as f:
        json.dump({'card_sets': card_sets, 'cards': rows}, f, ensure_ascii=False, indent=2)
    print(f"Wrote raw Cargo dump to {CARGO_DUMP_PATH}")

    filenames = [row['ImageFilename'] for row in rows if row.get('ImageFilename')]
    print(f"Resolving {len(set(filenames))} image URL(s)...")
    image_urls = resolve_image_urls(base_url, filenames)

    workers = os.cpu_count() or 4
    print(f"Downloading card images (up to {workers} parallel workers)...")
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for row in rows:
            filename = row.get('ImageFilename')
            image_url = image_urls.get(filename) if filename else None
            if not image_url:
                failures.append(f"{row['derived_id']}: no resolvable image URL for {filename!r}")
                continue
            set_num = int(row['SetNum']) if str(row.get('SetNum')).isdigit() else None
            future = pool.submit(_download_card_image, row['derived_id'], set_num, filename, image_url)
            futures[future] = format_display_id(row.get('SetNum'), row.get('CardNum'))

        bar = ProgressBar(label='images', min=0, max=len(futures), units='images')
        done = 0
        for future in concurrent.futures.as_completed(futures):
            display_id = futures[future]
            error = future.result()
            if error:
                failures.append(error)
            done += 1
            bar.update(done, task=display_id)
        bar.done()

    return failures

def find_starter_image_filenames(starters_dir):
    """Scan downloaded starter block HTML files for referenced cover-art filenames."""
    filenames = set()
    if not os.path.isdir(starters_dir):
        return filenames
    for name in os.listdir(starters_dir):
        if not name.endswith('.html'):
            continue
        with open(os.path.join(starters_dir, name), 'r', encoding='utf-8') as f:
            content = f.read()
        filenames.update(_STARTER_IMAGE_RE.findall(content))
    return filenames

def download_starter_images(base_url, starters_dir):
    """
    Resolve and download the starter-deck cover art images (e.g.
    Starter-01-Aragorn.jpg) referenced in the downloaded starter block pages,
    saving them to STARTER_IMAGES_DIR. Returns a list of error strings.
    """
    filenames = find_starter_image_filenames(starters_dir)
    if not filenames:
        print("No starter deck cover images detected in the block pages.")
        return []

    print(f"Resolving {len(filenames)} starter deck cover image URL(s)...")
    image_urls = resolve_image_urls(base_url, filenames)

    os.makedirs(STARTER_IMAGES_DIR, exist_ok=True)
    failures = []
    filenames = sorted(filenames)
    bar = ProgressBar(label='starter images', min=0, max=len(filenames), units='images')
    for i, filename in enumerate(filenames, start=1):
        image_url = image_urls.get(filename)
        if not image_url:
            failures.append(f"{filename}: no resolvable image URL")
            bar.update(i, task=filename)
            continue
        save_path = os.path.join(STARTER_IMAGES_DIR, filename)
        if not os.path.exists(save_path):
            if not download_binary(image_url, save_path):
                failures.append(f"{filename}: failed to download image from {image_url}")
        bar.update(i, task=filename)
    bar.done()

    return failures

def download_wiki_pages(wiki_sources, label="Downloading wiki pages", output_dir=None):
    """Download HTML content for each wiki source and save locally."""
    dest = output_dir or ASSETS_DIR
    os.makedirs(dest, exist_ok=True)

    print(f"{label}...")

    for name, url in wiki_sources.items():
        print(f"  {name}: {url}")

        filename = get_filename_from_url(url)
        if not filename.endswith('.html'):
            filename += '.html'

        save_path = os.path.join(dest, filename)

        if os.path.exists(save_path):
            print(f"    Skipping (already exists): {filename}")
            continue

        success = download_html(url, save_path)

        if success:
            print(f"    Saved to: {save_path}")
        else:
            print(f"    Failed to download: {url}")

def main():
    """Main function to run the wiki download process."""
    try:
        # Ensure the output root exists before any downloads begin
        do_assets = os.path.abspath(os.path.join(script_dir, '..', '..', 'do', 'assets'))
        os.makedirs(do_assets, exist_ok=True)

        wiki_sources = load_wiki_config()

        # Download the configured reference pages (rules, starter list, errata, ...)
        download_wiki_pages(wiki_sources)

        pc_base = get_pc_base_url(wiki_sources)

        # Download starter deck block pages from PC wiki
        starter_html = os.path.join(ASSETS_DIR, 'Starter_Decks.html')
        if os.path.exists(starter_html):
            if pc_base:
                block_sources = detect_starter_block_urls(starter_html, pc_base)
                if block_sources:
                    download_wiki_pages(
                        block_sources,
                        label=f"Downloading {len(block_sources)} starter block pages",
                        output_dir=STARTERS_DIR
                    )

                    # Also grab each starter deck's cover art image
                    starter_image_failures = download_starter_images(pc_base, STARTERS_DIR)
                    if starter_image_failures:
                        print(f"\n{len(starter_image_failures)} starter image failure(s) (non-fatal):")
                        for err in starter_image_failures[:20]:
                            print(f"  WARNING: {err}")
                        if len(starter_image_failures) > 20:
                            print(f"  ... and {len(starter_image_failures) - 20} more")
                else:
                    print("No starter block pages detected in Starter_Decks.html.")
            else:
                print("PC wiki base URL not found — skipping starter block download.")
        else:
            print("Starter_Decks.html not found — skipping starter block download.")

        # Fetch all card data + images via the Cargo API
        failures = download_cargo_data(wiki_sources)
        if failures:
            # A handful of cards can have permanently missing/unresolvable
            # images on the wiki itself (verified upstream data gaps, not a
            # scraping bug) -- warn but don't fail the whole build for them.
            print(f"\n{len(failures)} card image failure(s) (non-fatal):")
            for err in failures[:20]:
                print(f"  WARNING: {err}")
            if len(failures) > 20:
                print(f"  ... and {len(failures) - 20} more")

        print("Wiki download process completed.")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()