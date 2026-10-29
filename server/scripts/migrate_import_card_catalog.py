"""One-off migration: import the real LotR TCG card catalog (idempotent, safe
to re-run).

Reads `build/do/assets/database/card_database.json` (produced by
`make wiki_gather_sites && make wiki_create_lotr_database`, see
`build/makefiles/wiki.mk`) and inserts one `cards` row per wiki card entry
that has an integer `set_num` (the four "V0"-"V3" PC fan-made sets use
non-numeric set numbers and don't fit the `cards.set_number` INTEGER column,
so they're skipped and reported separately).

This replaces the earlier dev-only placeholder Set 1 catalog seeded by
`migrate_add_booster_economy.py` (12 rows named "Placeholder Common/Uncommon/
Rare N"): those rows are deactivated (is_active=0), not deleted, so any
existing Ownership/DeckCard rows created against them during earlier dev/
smoke testing keep a valid foreign key.

Rarity mapping caveat: `cards.rarity` is a fixed enum
(common/uncommon/rare/epic/legendary/mythic) enforced by SQLAlchemy on every
ORM read. The wiki's real rarity codes are much more varied (draft/starter/
promo block letters etc.) -- see RARITY_MAP below. This mapping is a
best-effort placeholder categorization (flagged like other placeholder
economy constants in this repo, e.g. BOOSTER_BOX_PACK_COUNT), not authoritative
game-design rarity semantics. The original wiki rarity code is preserved
verbatim in `cards.attributes["raw_rarity"]` so it can be corrected later
without re-running the whole import.

Run inside the dev container (working directory pinned to server/):
    python scripts/migrate_import_card_catalog.py
"""
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from server.core.database import engine

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CARD_DATABASE_PATH = REPO_ROOT / "build" / "do" / "assets" / "database" / "card_database.json"

# Best-effort raw wiki rarity code -> our fixed enum. Unmapped/unknown codes
# fall back to 'common' (see module docstring).
RARITY_MAP = {
    "C": "common",
    "U": "uncommon",
    "R": "rare",
    "R+": "rare",
    "M": "mythic",
    "S": "mythic",
    "S1": "mythic",
    "S2": "mythic",
    "S3": "mythic",
    "P": "legendary",
    "FP": "legendary",
    "TF": "rare",
    "RF": "rare",
}


def map_rarity(raw: str) -> str:
    return RARITY_MAP.get(raw, "common")


def main():
    if not CARD_DATABASE_PATH.exists():
        print(
            f"ERROR: {CARD_DATABASE_PATH} not found. Run "
            "'make wiki_gather_sites && make wiki_create_lotr_database' first."
        )
        sys.exit(1)

    with CARD_DATABASE_PATH.open(encoding="utf-8") as f:
        catalog = json.load(f)

    with engine.begin() as conn:
        deactivated = conn.execute(
            text("UPDATE cards SET is_active = 0 WHERE name LIKE 'Placeholder %'")
        ).rowcount
        print(f"Deactivated {deactivated} placeholder dev-seed card(s).")

        existing_wiki_ids = set()
        for row in conn.execute(text("SELECT attributes FROM cards WHERE attributes IS NOT NULL")):
            raw_attrs = row[0]
            if not raw_attrs:
                continue
            try:
                attrs = json.loads(raw_attrs) if isinstance(raw_attrs, str) else raw_attrs
            except (TypeError, ValueError):
                continue
            wiki_id = attrs.get("wiki_id") if isinstance(attrs, dict) else None
            if wiki_id:
                existing_wiki_ids.add(wiki_id)

        inserted = 0
        skipped_existing = 0
        skipped_non_numeric_set = 0
        unmapped_rarities = set()

        for wiki_id, card in catalog.items():
            if wiki_id in existing_wiki_ids:
                skipped_existing += 1
                continue

            set_num = card.get("set_num")
            if not isinstance(set_num, int):
                skipped_non_numeric_set += 1
                continue

            raw_rarity = card.get("rarity") or ""
            if raw_rarity not in RARITY_MAP:
                unmapped_rarities.add(raw_rarity)
            rarity = map_rarity(raw_rarity)

            twilight = card.get("twilight")
            cost = twilight if isinstance(twilight, int) else 0

            attributes = dict(card)
            attributes["wiki_id"] = wiki_id
            attributes["raw_rarity"] = raw_rarity

            conn.execute(
                text(
                    "INSERT INTO cards "
                    "(id, name, description, cost, rarity, image_url, attributes, is_active, set_number) "
                    "VALUES (:id, :name, :description, :cost, :rarity, "
                    ":image_url, :attributes, 1, :set_number)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "name": card.get("name") or wiki_id,
                    "description": card.get("game_text") or "",
                    "cost": cost,
                    "rarity": rarity,
                    "image_url": None,
                    "attributes": json.dumps(attributes),
                    "set_number": set_num,
                },
            )
            inserted += 1

        print(f"Inserted {inserted} card(s) from the real catalog.")
        print(f"Skipped {skipped_existing} already-imported card(s) (idempotent re-run).")
        print(f"Skipped {skipped_non_numeric_set} card(s) with non-numeric set_num (e.g. V0-V3 PC sets).")
        if unmapped_rarities:
            print(
                f"NOTE: {len(unmapped_rarities)} raw rarity code(s) had no explicit mapping "
                f"and were bucketed as 'common': {sorted(unmapped_rarities)}"
            )


if __name__ == "__main__":
    main()
