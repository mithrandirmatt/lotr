"""One-off migration: add booster-pack card generation support (LOT-020 /
LOT-025 slice 2) -- idempotent, safe to re-run.

Changes:
1. `cards.set_number` column (INTEGER, nullable) so the catalog can be
   filtered to a given active set when generating booster packs.
2. `ownerships.is_foil` column (BOOLEAN, default 0) so foil and non-foil
   copies of the same card are tracked as distinct rows.
3. Unique index on ownerships changed from (card_id, user_id) to
   (card_id, user_id, is_foil) -- the live DB had no such unique index
   applied yet (only `ix_ownerships_user_id`), so this just adds the new one.
4. `distribution_transactions` table (server-authoritative audit trail for
   every card grant/removal event -- LOT-020 "every card delta has a
   transaction ID").
5. Seeds a small placeholder Set 1 (Fellowship) test catalog (a handful of
   common/uncommon/rare cards) ONLY if the `cards` table is empty, purely so
   `/store/purchase` (product=pack) has something to draw from in dev/test.
   This is NOT the real ~3,216-card catalog import -- that remains separate,
   larger future work (see issues-tracker.md card-catalog-import gap noted in
   this session's issues-todo.md).

No Alembic environment is wired up yet for this project, so this follows the
existing repo convention of small, idempotent one-off scripts (see
migrate_add_set_releases.py, migrate_add_2fa_columns.py).

Run inside the dev container:
    python scripts/migrate_add_booster_economy.py
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from server.core.database import engine

CREATE_DISTRIBUTION_TX_SQL = """
CREATE TABLE IF NOT EXISTS distribution_transactions (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    source VARCHAR(10) NOT NULL,
    product VARCHAR(50),
    set_number INTEGER,
    cards JSON NOT NULL,
    rng_seed VARCHAR(64),
    tolkien_delta INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME
)
"""

# (name, rarity, cost) placeholder rows -- clearly named as test/placeholder,
# not real LotR TCG card names.
SEED_SET_1_CARDS = (
    [(f"Placeholder Common {n}", "common", 1) for n in range(1, 8)]
    + [(f"Placeholder Uncommon {n}", "uncommon", 2) for n in range(1, 4)]
    + [(f"Placeholder Rare {n}", "rare", 3) for n in range(1, 3)]
)


def main():
    with engine.begin() as conn:
        existing_card_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(cards)"))}
        if "set_number" not in existing_card_columns:
            conn.execute(text("ALTER TABLE cards ADD COLUMN set_number INTEGER"))
            print("Added column 'cards.set_number'.")
        else:
            print("Column 'cards.set_number' already exists, skipping.")
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_card_set_number ON cards (set_number)"))

        existing_ownership_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(ownerships)"))}
        if "is_foil" not in existing_ownership_columns:
            conn.execute(text("ALTER TABLE ownerships ADD COLUMN is_foil BOOLEAN NOT NULL DEFAULT 0"))
            print("Added column 'ownerships.is_foil'.")
        else:
            print("Column 'ownerships.is_foil' already exists, skipping.")

        conn.execute(text("DROP INDEX IF EXISTS idx_ownership_card_user"))
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_ownership_card_user_foil "
                "ON ownerships (card_id, user_id, is_foil)"
            )
        )
        print("Ensured unique index 'idx_ownership_card_user_foil' on ownerships.")

        conn.execute(text(CREATE_DISTRIBUTION_TX_SQL))
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_distribution_tx_user ON distribution_transactions (user_id)")
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_distribution_tx_source ON distribution_transactions (source)")
        )
        print("Ensured 'distribution_transactions' table exists.")

        card_count = conn.execute(text("SELECT COUNT(*) FROM cards")).scalar()
        if card_count == 0:
            for name, rarity, cost in SEED_SET_1_CARDS:
                conn.execute(
                    text(
                        "INSERT INTO cards (id, name, description, cost, rarity, set_number, is_active) "
                        "VALUES (:id, :name, :description, :cost, :rarity, 1, 1)"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "name": name,
                        "description": "Placeholder catalog card (LOT-025 booster generation dev seed).",
                        "cost": cost,
                        "rarity": rarity,
                    },
                )
            print(f"Seeded {len(SEED_SET_1_CARDS)} placeholder Set 1 cards (cards table was empty).")
        else:
            print(f"'cards' table already has {card_count} row(s), skipping placeholder seed.")


if __name__ == "__main__":
    main()
