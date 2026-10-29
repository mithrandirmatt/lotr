"""One-off migration: add the card-authoring review-gate columns (LOT-100
follow-up to LOT-025) -- idempotent, safe to re-run.

Adds `publish_status` (draft/in_review/published, DB-level default
'published' so the existing bulk-imported catalog stays visible without a
backfill) and `review_notes` (nullable, populated on reject) to `cards`.
See `server/server/models/models.py::Card` for full field documentation.

No Alembic environment is wired up yet for this project, so this follows
the existing repo convention of small, idempotent one-off scripts (see
migrate_add_release_events.py, migrate_add_weekly_rewards.py).

SQLite has no "ADD COLUMN IF NOT EXISTS", so existence is checked via
PRAGMA table_info before each ALTER TABLE.

Run inside the dev container (cwd MUST be server/, see repo memory gotcha):
    python scripts/migrate_add_card_review_gate.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from server.core.database import engine


def _existing_columns(conn) -> set:
    rows = conn.execute(text("PRAGMA table_info(cards)")).fetchall()
    return {row[1] for row in rows}


def main():
    with engine.begin() as conn:
        columns = _existing_columns(conn)

        if "publish_status" not in columns:
            conn.execute(text(
                "ALTER TABLE cards ADD COLUMN publish_status VARCHAR(20) "
                "NOT NULL DEFAULT 'published'"
            ))
            print("Added 'publish_status' column to cards.")
        else:
            print("'publish_status' column already exists on cards.")

        if "review_notes" not in columns:
            conn.execute(text("ALTER TABLE cards ADD COLUMN review_notes VARCHAR(500)"))
            print("Added 'review_notes' column to cards.")
        else:
            print("'review_notes' column already exists on cards.")

        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_card_publish_status ON cards (publish_status)")
        )
        print("Ensured 'idx_card_publish_status' index exists.")


if __name__ == "__main__":
    main()
