"""One-off migration: add the gift ledger (LOT-019 / LOT-025 slice 5) --
idempotent, safe to re-run.

Adds a `gifts` table tracking the lifecycle of a gifted store product
(created/granted/redeemed/consumed/expired/revoked) per the LOT-019 design.
See `server/server/models/models.py::Gift` for field/state documentation.

No Alembic environment is wired up yet for this project, so this follows the
existing repo convention of small, idempotent one-off scripts (see
migrate_add_set_releases.py, migrate_add_booster_economy.py).

Run inside the dev container (cwd MUST be server/, see repo memory gotcha):
    python scripts/migrate_add_gifts.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from server.core.database import engine

CREATE_GIFTS_SQL = """
CREATE TABLE IF NOT EXISTS gifts (
    id VARCHAR(36) PRIMARY KEY,
    sender_id VARCHAR(36),
    recipient_id VARCHAR(36) NOT NULL,
    product VARCHAR(50) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    set_number INTEGER,
    status VARCHAR(10) NOT NULL DEFAULT 'granted',
    note VARCHAR(250),
    expires_at DATETIME,
    redeemed_at DATETIME,
    revoked_at DATETIME,
    transaction_id VARCHAR(36),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""


def main():
    with engine.begin() as conn:
        conn.execute(text(CREATE_GIFTS_SQL))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_gift_recipient ON gifts (recipient_id)"))
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_gift_recipient_status ON gifts (recipient_id, status)")
        )
        print("Ensured 'gifts' table exists.")


if __name__ == "__main__":
    main()
