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
    # With 3200+ dirs over a mounted filesystem this can take a while.
    # -----------------------------------------------------------------------
    print(f'Scanning {len(set_dirs)} sets...', flush=True)

    # Count card dirs first (cheap — no per-card listdir needed yet)
    total_dirs = sum(
        1 for set_dir in set_dirs
        for card_id in os.listdir(os.path.join(CARDS_DIR, set_dir))
        if os.path.isdir(os.path.join(CARDS_DIR, set_dir, card_id))
    )

    scan_bar = ProgressBar(label='scanning', min=0, max=total_dirs, units='dirs')
    work = []          # (set_dir, card_id, src_jpg)
    scanned = 0

    for set_dir in set_dirs:
        set_path = os.path.join(CARDS_DIR, set_dir)
        for card_id in sorted(os.listdir(set_path)):
            card_dir = os.path.join(set_path, card_id)
            if not os.path.isdir(card_dir):
                continue
            scanned += 1
            src_jpg = find_source_jpg(card_dir)
            if src_jpg:
                work.append((set_dir, card_id, src_jpg))
            scan_bar.update(scanned, task=card_id)

    scan_bar.done()
    print(f'Found {len(work)} card images across {len(set_dirs)} sets.', flush=True)

    # -----------------------------------------------------------------------
    # Process phase: one progress bar per set
    # -----------------------------------------------------------------------
    processed = 0
    skipped   = 0
    errors    = []

    # Pre-compute per-set counts
    set_counts = {}
    for set_dir, _, __ in work:
        set_counts[set_dir] = set_counts.get(set_dir, 0) + 1

    current_set = None
    bar = None
    set_pos = 0

    for set_dir, card_id, src_jpg in work:
        if set_dir != current_set:
            if bar:
                bar.done(task=current_set)
            current_set = set_dir
            bar = ProgressBar(label=f'{set_dir:<8}', min=0, max=set_counts[set_dir], units='cards')
            set_pos = 0

        set_pos += 1

        out_dir  = os.path.join(PROCESSED_DIR, set_dir)
        out_path = os.path.join(out_dir, card_id + '.png')

        if os.path.exists(out_path):
            skipped += 1
            bar.update(set_pos, task=card_id)
            continue

        try:
            os.makedirs(out_dir, exist_ok=True)
            with Image.open(src_jpg) as img:
                result = remove_white_border(img)
                result.save(out_path, 'PNG')
            processed += 1
        except Exception as e:
            errors.append(f'{card_id}: {e}')

        bar.update(set_pos, task=card_id)

    if bar:
        bar.done(task=current_set)

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
