"""One-off migration: create the set_releases table (LOT-025) if missing and
seed the monthly release plan (Set 1..19), with Set 1 (Fellowship) active and
locked so it can never be deactivated.

No Alembic environment is wired up yet for this project (empty versions/ dir,
no env.py/alembic.ini), so this follows the existing repo convention of small,
idempotent one-off scripts (see migrate_add_2fa_columns.py, create_admin_user.py)
rather than introducing a new migration framework.

Run inside the dev container:
    python scripts/migrate_add_set_releases.py
"""
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from server.core.database import engine

# Monthly release plan through Set 19 (see
# assets/reference/agent/game-mechanism-release-and-gifting.md). Only Set 1's
# real name is finalized today; the rest are seeded as placeholders so admins
# have a row to toggle once each set's content is ready, and can be renamed
# later without changing set_number (the stable key).
SEED_SETS = [(1, "Fellowship of the Ring")] + [(n, f"Set {n}") for n in range(2, 20)]

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS set_releases (
    id VARCHAR(36) PRIMARY KEY,
    set_number INTEGER NOT NULL UNIQUE,
    set_code VARCHAR(20),
    name VARCHAR(100) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 0,
    is_locked_active BOOLEAN NOT NULL DEFAULT 0,
    activated_at DATETIME,
    created_at DATETIME,
    updated_at DATETIME
)
"""


def main():
    with engine.begin() as conn:
        conn.execute(text(CREATE_TABLE_SQL))
        print("Ensured 'set_releases' table exists.")

        existing_numbers = {
            row[0] for row in conn.execute(text("SELECT set_number FROM set_releases"))
        }

        for set_number, name in SEED_SETS:
            if set_number in existing_numbers:
                continue
            is_fellowship = set_number == 1
            conn.execute(
                text(
                    "INSERT INTO set_releases "
                    "(id, set_number, name, is_active, is_locked_active, activated_at, created_at) "
                    "VALUES (:id, :set_number, :name, :is_active, :is_locked_active, :activated_at, CURRENT_TIMESTAMP)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "set_number": set_number,
                    "name": name,
                    "is_active": is_fellowship,
                    "is_locked_active": is_fellowship,
                    "activated_at": datetime.now(timezone.utc) if is_fellowship else None,
                },
            )
            print(f"Seeded set {set_number} ('{name}'), active={is_fellowship}.")


if __name__ == "__main__":
    main()
