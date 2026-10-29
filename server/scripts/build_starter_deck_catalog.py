"""One-off tool: resolve the curated Set 1 (Fellowship of the Ring) starter
decklists from build/do/assets/database/starter_database.json (produced by
`make wiki_create_starter_database`, see build/py/wiki/create_starter_database.py)
into a small, repo-committed config keyed by our own `cards` table IDs.

Only the three FOTR-prefixed decks (Fellowship Block, collector_info starting
with "1") are resolved -- these are the only ones eligible for the current
Set 1 SetRelease. Other blocks (Mines of Moria, Realms of the Elf-lords,
etc.) become relevant once those sets are unlocked; re-run this script with
an updated allow-list at that point.

Output: server/server/data/starter_decks_set1.json, consumed by the
LOT-018 entitlement claim flow (grants one of these decks' cards on claim,
instead of the old ad hoc random booster generation).

Safe to re-run: fully regenerates the output file each time.

Run inside the dev container (working directory pinned to server/):
    python scripts/build_starter_deck_catalog.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.core.database import SessionLocal
from server.models.models import Card

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STARTER_DATABASE_PATH = REPO_ROOT / "build" / "do" / "assets" / "database" / "starter_database.json"
MISSING_CARDS_PATH = REPO_ROOT / "build" / "do" / "assets" / "database" / "missing_cards.json"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "server" / "data" / "starter_decks_set1.json"

SECTIONS = ("ring_bearer", "adventure_deck", "free_peoples", "shadow", "lotro_additions")


def load_collector_info_aliases() -> dict:
    """Map a discarded collector_info (e.g. a starter-exclusive print '1C2')
    to the collector_info of the duplicate-id card that was actually kept
    during card_database.json's dedup pass (e.g. '1M2') -- both refer to the
    same underlying card, just a different printing. See missing_cards.json,
    produced by build/py/wiki/create_card_database.py."""
    if not MISSING_CARDS_PATH.exists():
        return {}
    with MISSING_CARDS_PATH.open(encoding="utf-8") as f:
        missing = json.load(f)
    aliases = {}
    for entry in missing:
        collector_info = entry.get("collector_info")
        kept_collector_info = entry.get("kept_collector_info")
        if collector_info and kept_collector_info:
            aliases[collector_info] = kept_collector_info
    return aliases


def main():
    if not STARTER_DATABASE_PATH.exists():
        print(f"ERROR: {STARTER_DATABASE_PATH} not found. Run 'make wiki_create_starter_database' first.")
        sys.exit(1)

    with STARTER_DATABASE_PATH.open(encoding="utf-8") as f:
        starter_db = json.load(f)

    db = SessionLocal()
    try:
        collector_info_to_card = {}
        for card in db.query(Card).filter(Card.set_number == 1).all():
            attrs = card.attributes or {}
            collector_info = attrs.get("collector_info")
            if collector_info:
                collector_info_to_card[collector_info] = card

        collector_info_aliases = load_collector_info_aliases()

        resolved_decks = {}
        unresolved_total = 0
        for deck_id, deck in starter_db.items():
            if not deck_id.startswith("fotr_"):
                continue

            resolved_cards = []
            unresolved = []
            for section in SECTIONS:
                for entry in deck.get(section, []):
                    collector_info = entry["collector_info"]
                    card = collector_info_to_card.get(collector_info)
                    if not card:
                        alias = collector_info_aliases.get(collector_info)
                        card = collector_info_to_card.get(alias) if alias else None
                    if not card:
                        unresolved.append(collector_info)
                        continue
                    resolved_cards.append({
                        "card_id": card.id,
                        "name": card.name,
                        "quantity": entry["count"],
                        "section": section,
                    })

            resolved_decks[deck_id] = {
                "name": deck["name"],
                "block": deck["block"],
                "set_number": 1,
                "cards": resolved_cards,
            }
            if unresolved:
                unresolved_total += len(unresolved)
                print(f"  {deck_id}: {len(unresolved)} unresolved collector_info token(s): {unresolved}")

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with OUTPUT_PATH.open("w", encoding="utf-8") as f:
            json.dump(resolved_decks, f, indent=2, ensure_ascii=False)

        print(f"Wrote {len(resolved_decks)} Set 1 starter deck(s) to {OUTPUT_PATH}")
        if unresolved_total:
            print(f"NOTE: {unresolved_total} total unresolved card reference(s) across all decks (see above).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
