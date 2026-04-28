#!/usr/bin/env python3
"""
Download HTML content from LOTR wiki sites and save them locally.
"""

import os
import re
import sys
import configparser
import concurrent.futures
from urllib.parse import urlparse

# Add pyutils to the path so we can import our web utilities
# When run from the root directory, we need to adjust the path
script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
sys.path.insert(0, os.path.join(repo_root, 'pyutils'))

# Import the web utilities
from web.utils import download_html, download_binary, get_filename_from_url

ASSETS_DIR   = os.path.abspath(os.path.join(script_dir, '..', '..', 'do', 'assets', 'wiki'))
CARDS_DIR    = os.path.abspath(os.path.join(script_dir, '..', '..', 'do', 'assets', 'cards'))
STARTERS_DIR = os.path.abspath(os.path.join(script_dir, '..', '..', 'do', 'assets', 'wiki', 'starters'))

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

def get_base_url(wiki_sources):
    """Return the scheme+host for the main lotrtcgwiki.com source."""
    for url in wiki_sources.values():
        parsed = urlparse(url)
        if 'lotrtcgwiki.com' in parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    return None

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

def detect_set_urls(html_path, base_url):
    """
    Parse a downloaded HTML file and return a dict of {set_name: full_url}
    for every /wiki/setN link found (deduplicated, in order of first appearance).
    """
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    seen = set()
    sets = {}
    for path in re.findall(r'href="(/wiki/set\d+)"', content):
        if path not in seen:
            seen.add(path)
            name = path.split('/')[-1]   # "set0", "set1", ...
            sets[name] = base_url + path
    return sets

def detect_card_ids(grand_html_path):
    """Return an ordered, deduplicated list of lotrNNNNN card IDs from grand.html."""
    with open(grand_html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    seen = set()
    cards = []
    for card_id in re.findall(r'href="/wiki/(lotr\d{5})"', content):
        if card_id not in seen:
            seen.add(card_id)
            cards.append(card_id)
    return cards

def get_set_num(card_id):
    """Extract set number from a card ID, e.g. 'lotr00001' -> 0, 'lotr01324' -> 1."""
    return int(card_id[4:6])

def sanitize_filename(name):
    """Replace characters that are invalid in file names with underscores."""
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def parse_card_page(html_content):
    """
    Return (title, image_path) from a downloaded card page.
    title      -- card name, e.g. 'The Prancing Pony (P) (0P1)'
    image_path -- site-relative path, e.g. '/wiki/_media/cards:lotr00001.jpg'
    Either value is None if not found.
    """
    title_match = re.search(r'<title>LotR TCG Wiki: (.+?)</title>', html_content)
    title = title_match.group(1).strip() if title_match else None

    img_match = re.search(r'src="(/wiki/_media/cards:lotr\d{5}\.[a-z]+)"', html_content)
    image_path = img_match.group(1) if img_match else None

    return title, image_path

def _download_card(card_id, base_url):
    """
    Download the HTML page and card image for a single card.
    Returns None on success, or an error string on failure.
    """
    set_num = get_set_num(card_id)
    card_dir = os.path.join(CARDS_DIR, f"set{set_num}", card_id)
    os.makedirs(card_dir, exist_ok=True)

    # --- card HTML page ---
    card_html_path = os.path.join(card_dir, f"{card_id}.html")
    if os.path.exists(card_html_path):
        print(f"  Skipping HTML (exists): {card_id}")
        with open(card_html_path, 'r', encoding='utf-8') as f:
            card_content = f.read()
    else:
        card_url = f"{base_url}/wiki/{card_id}"
        if not download_html(card_url, card_html_path):
            return f"{card_id}: failed to download HTML from {card_url}"
        print(f"  Downloaded HTML: {card_id}")
        with open(card_html_path, 'r', encoding='utf-8') as f:
            card_content = f.read()

    # --- parse for title and image ---
    title, image_path = parse_card_page(card_content)
    if not title:
        return f"{card_id}: could not find card title in downloaded page"
    if not image_path:
        return f"{card_id}: could not find card image path in downloaded page"

    # --- card image ---
    image_ext = os.path.splitext(image_path)[1]
    image_filename = sanitize_filename(title) + image_ext
    image_save_path = os.path.join(card_dir, image_filename)

    if os.path.exists(image_save_path):
        print(f"  Skipping image (exists): {image_filename}")
    else:
        image_url = base_url + image_path
        if not download_binary(image_url, image_save_path):
            return f"{card_id}: failed to download image from {image_url}"
        print(f"  Downloaded image: {image_filename}")

    return None

def download_cards(base_url):
    """
    Download the HTML page and card image for every card listed in grand.html.
    Downloads run in parallel using os.cpu_count() workers.
    Returns a list of error strings (empty if all succeeded).
    """
    grand_html = os.path.join(ASSETS_DIR, 'grand.html')
    if not os.path.exists(grand_html):
        print("grand.html not found — skipping card download.")
        return []

    card_ids = detect_card_ids(grand_html)
    if not card_ids:
        print("No card IDs detected in grand.html.")
        return []

    workers = os.cpu_count() or 4
    print(f"Downloading {len(card_ids)} cards (up to {workers} parallel workers)...")

    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_download_card, cid, base_url): cid for cid in card_ids}
        for future in concurrent.futures.as_completed(futures):
            error = future.result()
            if error:
                failures.append(error)

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

        # Download the initial configured pages (start, grand, rules, ...)
        download_wiki_pages(wiki_sources)

        # Detect set pages from the downloaded start.html and download them
        base_url = get_base_url(wiki_sources)
        if base_url:
            start_html = os.path.join(ASSETS_DIR, 'start.html')
            if os.path.exists(start_html):
                set_sources = detect_set_urls(start_html, base_url)
                if set_sources:
                    download_wiki_pages(
                        set_sources,
                        label=f"Downloading {len(set_sources)} set pages detected from start.html"
                    )
                else:
                    print("No set pages detected in start.html.")
            else:
                print("start.html not found — skipping set page detection.")

            # Download starter deck block pages from PC wiki
            starter_html = os.path.join(ASSETS_DIR, 'Starter_Decks.html')
            if os.path.exists(starter_html):
                pc_base = get_pc_base_url(wiki_sources)
                if pc_base:
                    block_sources = detect_starter_block_urls(starter_html, pc_base)
                    if block_sources:
                        download_wiki_pages(
                            block_sources,
                            label=f"Downloading {len(block_sources)} starter block pages",
                            output_dir=STARTERS_DIR
                        )
                    else:
                        print("No starter block pages detected in Starter_Decks.html.")
                else:
                    print("PC wiki base URL not found — skipping starter block download.")
            else:
                print("Starter_Decks.html not found — skipping starter block download.")

            # Download all card pages + images detected from grand.html
            grand_html = os.path.join(ASSETS_DIR, 'grand.html')
            if os.path.exists(grand_html):
                failures = download_cards(base_url)
                if failures:
                    print(f"\n{len(failures)} card(s) failed:")
                    for err in failures:
                        print(f"  ERROR: {err}")
                    sys.exit(1)
            else:
                print("grand.html not found — skipping card download.")

        print("Wiki download process completed.")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()