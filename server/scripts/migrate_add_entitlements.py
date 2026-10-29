"""One-off migration: add the entitlements table (LOT-018 / LOT-025) --
idempotent, safe to re-run.

Adds an `entitlements` table tracking a user's not-yet-claimed grants
(starter decks, booster packs). See `server/server/models/models.py::Entitlement`
for field/state documentation.

No Alembic environment is wired up yet for this project, so this follows the
existing repo convention of small, idempotent one-off scripts (see
migrate_add_gifts.py, migrate_add_set_releases.py).

Run inside the dev container (cwd MUST be server/, see repo memory gotcha):
    python scripts/migrate_add_entitlements.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from server.core.database import engine

CREATE_ENTITLEMENTS_SQL = """
CREATE TABLE IF NOT EXISTS entitlements (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    product_type VARCHAR(20) NOT NULL,
    set_number INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(10) NOT NULL DEFAULT 'active',
    granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    consumed_at DATETIME,
    revoked_at DATETIME,
    revocation_reason VARCHAR(250),
    transaction_id VARCHAR(36),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME
)
"""


def main():
    with engine.begin() as conn:
        conn.execute(text(CREATE_ENTITLEMENTS_SQL))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_entitlement_user ON entitlements (user_id)"))
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_entitlement_user_product_set "
                "ON entitlements (user_id, product_type, set_number)"
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_entitlement_status ON entitlements (status)"))
        print("Ensured 'entitlements' table exists.")


if __name__ == "__main__":
    main()
