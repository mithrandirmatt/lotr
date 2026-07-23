#!/usr/bin/env python3
"""
Remove the white border from downloaded card JPGs and save as transparent PNGs.

Input:  build/do/assets/cards/set{N}/lotrNNNNN/*.jpg
Output: build/do/assets/cards/processed/set{N}/{card_id}.png

Requires Pillow:  pip install Pillow
"""

import os
import re
import sys
import colorsys
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT     = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..'))
PYUTILS_DIR   = os.path.join(REPO_ROOT, 'pyutils')
CARDS_DIR     = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'cards')
PROCESSED_DIR = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'cards', 'processed')

sys.path.insert(0, PYUTILS_DIR)
from utils.progress import ProgressBar

try:
    from PIL import Image
except ImportError:
    print('ERROR: Pillow is not installed. Run:  pip install Pillow')
    sys.exit(1)


# ---------------------------------------------------------------------------
# Image processing
# ---------------------------------------------------------------------------

# Background detection uses HSV colour space rather than raw RGB so that both
# the white border and any soft grey drop shadow around the card are caught.
#
# A pixel is "background" when:
#   Value (brightness) >= _BG_VALUE_MIN   — avoids removing dark card content
#   Saturation         <= _BG_SAT_MAX     — achromatic only (white / grey)
#
# Coloured card frames (gold, silver, culture colours) all exceed _BG_SAT_MAX,
# so the flood-fill stops naturally at the true card edge.
_BG_VALUE_MIN = 0.35   # lowered to 0.35 to catch dark grey drop shadows
_BG_SAT_MAX   = 0.15   # 0.0 = pure grey/white, 1.0 = fully saturated

# Thresholds for the fringe colour-replacement pass.
# Off-white anti-aliased corner pixels have low saturation and high brightness.
# We recolour them (rather than remove them) by spreading the adjacent card-frame
# colour inward.  The saturation ceiling is loose so blended fringe is caught;
# the fill is still safe because it only runs on pixels bordering transparent.
_FRINGE_VALUE_MIN = 0.50
_FRINGE_SAT_MAX   = 0.40


def _hsv(pixel):
    r, g, b = pixel[:3]
    return colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)


def _is_background(pixel):
    """Return True if pixel is background (white, near-white, or grey drop shadow)."""
    _h, s, v = _hsv(pixel)
    return v >= _BG_VALUE_MIN and s <= _BG_SAT_MAX


def _is_fringe(pixel):
    """Return True if pixel is off-white fringe (candidate for colour replacement)."""
    _h, s, v = _hsv(pixel)
    return v >= _FRINGE_VALUE_MIN and s <= _FRINGE_SAT_MAX


def _recolour_fringe_pass(pixels, width, height):
    """
    One iteration of fringe colour replacement.

    Finds every opaque pixel that:
      (a) looks like fringe (_is_fringe),
      (b) is adjacent to a transparent pixel (boundary condition — prevents
          the pass from touching interior card content), and
      (c) has at least one non-fringe opaque neighbour to sample colour from.

    Replaces the fringe pixel's RGB with that neighbour's colour, keeping
    alpha = 255.  Returns the number of pixels changed (used for convergence).
    """
    changed = 0
    neighbors_4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    for x in range(width):
        for y in range(height):
            px = pixels[x, y]
            if px[3] == 0 or not _is_fringe(px):
                continue

            # Must touch transparent to ensure we're at the edge
            adj_transparent = any(
                0 <= x + dx < width and 0 <= y + dy < height
                and pixels[x + dx, y + dy][3] == 0
                for dx, dy in neighbors_4
            )
            if not adj_transparent:
                continue

            # Copy colour from the first non-fringe opaque neighbour found
            for dx, dy in neighbors_4:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    np_ = pixels[nx, ny]
                    if np_[3] > 0 and not _is_fringe(np_):
                        r, g, b, _ = np_
                        pixels[x, y] = (r, g, b, 255)
                        changed += 1
                        break

    return changed


def remove_white_border(img):
    """
    Convert img to RGBA and clean up the background around the card.

    Three-pass strategy:
      1. BFS flood-fill from the entire perimeter (pass 1) — removes solid
         white borders and grey drop shadows (including dark ones on vertical
         card bottoms) using _is_background().
      2. Fringe colour replacement (pass 2, up to 6 iterations) — off-white
         anti-aliased pixels at rounded card corners are NOT removed; instead
         their colour is replaced with the adjacent card-frame colour, spreading
         inward one pixel at a time.  Stops when no more fringe pixels remain.
    """
    img = img.convert('RGBA')
    pixels = img.load()
    width, height = img.size

    visited = [[False] * height for _ in range(width)]
    queue = []

    # --- Pass 1: BFS flood-fill from perimeter (removes background/shadow) ---
    perimeter = (
        [(x, 0)          for x in range(width)]   +  # top
        [(x, height - 1) for x in range(width)]   +  # bottom
        [(0, y)          for y in range(height)]   +  # left
        [(width - 1, y)  for y in range(height)]      # right
    )
    for x, y in perimeter:
        if not visited[x][y] and _is_background(pixels[x, y]):
            visited[x][y] = True
            queue.append((x, y))

    while queue:
        cx, cy = queue.pop(0)
        r, g, b, a = pixels[cx, cy]
        pixels[cx, cy] = (r, g, b, 0)

        for nx, ny in [(cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)]:
            if 0 <= nx < width and 0 <= ny < height and not visited[nx][ny]:
                if _is_background(pixels[nx, ny]):
                    visited[nx][ny] = True
                    queue.append((nx, ny))

    # --- Pass 2: fringe colour replacement (iterative, inward from edge) ---
    for _ in range(6):
        if _recolour_fringe_pass(pixels, width, height) == 0:
            break

    return img


def find_source_jpg(card_dir):
    """Return the first .jpg file path in card_dir, or None."""
    try:
        for fname in os.listdir(card_dir):
            if fname.lower().endswith('.jpg'):
                return os.path.join(card_dir, fname)
    except OSError:
        pass
    return None


def _process_one_card(args):
    """
    Worker function run in a separate process: open, clean, and save one
    card image. Runs in a ProcessPoolExecutor since remove_white_border()'s
    per-pixel BFS/fringe passes are pure-Python and CPU-bound -- threads
    wouldn't help here (the GIL isn't released during that work), but
    separate processes let it use all available cores.
    Returns (card_id, error_message_or_None).
    """
    card_id, src_jpg, out_path = args
    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with Image.open(src_jpg) as img:
            result = remove_white_border(img)
            result.save(out_path, 'PNG')
        return (card_id, None)
    except Exception as e:
        return (card_id, str(e))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not os.path.isdir(CARDS_DIR):
        print(f'ERROR: Cards directory not found: {CARDS_DIR}')
        print('Run wiki_gather_sites first.')
        sys.exit(1)

    set_dirs = sorted(
        d for d in os.listdir(CARDS_DIR)
        if os.path.isdir(os.path.join(CARDS_DIR, d))
        and re.match(r'^set\d+$', d)
    )

    if not set_dirs:
        print('No set directories found. Run wiki_gather_sites first.')
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Scan phase: collect (set_dir, card_id, src_jpg) and show progress.
    #
    # CARDS_DIR is a bind-mounted directory (WSL2/9p or similar), where each
    # listdir/isdir/exists syscall carries real round-trip latency -- a fully
    # sequential per-card scan over 3200+ cards is I/O-latency bound, not CPU
    # bound, so isdir()/find_source_jpg() checks are parallelized with a
    # thread pool (threads release the GIL during syscalls). Results are
    # still collected in submission order, so `work` stays deterministic.
    # -----------------------------------------------------------------------
    print(f'Scanning {len(set_dirs)} sets...', flush=True)

    max_workers = min(32, max(4, (os.cpu_count() or 4) * 4))

    # One listdir per set (not two, as a prior version did for a separate
    # counting pass) to build the flat candidate list up front.
    candidates = []
    for set_dir in set_dirs:
        set_path = os.path.join(CARDS_DIR, set_dir)
        for card_id in sorted(os.listdir(set_path)):
            candidates.append((set_dir, card_id, os.path.join(set_path, card_id)))

    scan_bar = ProgressBar(label='scanning', min=0, max=len(candidates), units='dirs')

    def _scan_one(item):
        _set_dir, _card_id, card_dir = item
        if not os.path.isdir(card_dir):
            return None
        return find_source_jpg(card_dir)

    work = []          # (set_dir, card_id, src_jpg)
    scanned = 0

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_scan_one, item) for item in candidates]
        for (set_dir, card_id, _card_dir), future in zip(candidates, futures):
            src_jpg = future.result()
            scanned += 1
            if src_jpg:
                work.append((set_dir, card_id, src_jpg))
            scan_bar.update(scanned, task=card_id)

    scan_bar.done()
    print(f'Found {len(work)} card images across {len(set_dirs)} sets.', flush=True)

    # -----------------------------------------------------------------------
    # Pre-check which outputs already exist, in parallel -- same rationale
    # as the scan phase: batch the I/O-bound exists() round trips instead of
    # interleaving them one at a time with the (CPU-bound) image processing
    # loop below.
    out_paths = [
        os.path.join(PROCESSED_DIR, set_dir, card_id + '.png')
        for set_dir, card_id, _ in work
    ]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        exists_flags = list(pool.map(os.path.exists, out_paths))

    # -----------------------------------------------------------------------
    # Process phase: CPU-bound (per-pixel BFS + fringe passes), so this runs
    # across a process pool (one worker per core) instead of sequentially --
    # threads wouldn't help since remove_white_border() never releases the
    # GIL. Only images whose processed PNG doesn't already exist are submitted.
    # -----------------------------------------------------------------------
    to_process = [
        (card_id, src_jpg, out_path)
        for (_set_dir, card_id, src_jpg), out_path, already_exists
        in zip(work, out_paths, exists_flags)
        if not already_exists
    ]
    skipped = len(work) - len(to_process)
    processed = 0
    errors = []

    if to_process:
        max_procs = os.cpu_count() or 4
        print(f'Processing {len(to_process)} card image(s) (up to {max_procs} parallel processes)...', flush=True)
        proc_bar = ProgressBar(label='processing', min=0, max=len(to_process), units='cards')
        with ProcessPoolExecutor(max_workers=max_procs) as pool:
            for i, (card_id, error) in enumerate(pool.map(_process_one_card, to_process, chunksize=8), 1):
                if error:
                    errors.append(f'{card_id}: {error}')
                else:
                    processed += 1
                proc_bar.update(i, task=card_id)
        proc_bar.done()

    print(f'\nProcessed: {processed}  Skipped (already exists): {skipped}')

    if errors:
        print(f'\n{len(errors)} error(s):')
        for err in errors[:20]:
            print(f'  {err}')
        if len(errors) > 20:
            print(f'  ... and {len(errors) - 20} more')
        sys.exit(1)


if __name__ == '__main__':
    main()
