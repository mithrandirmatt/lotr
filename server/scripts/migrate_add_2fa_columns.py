"""One-off migration: add two-factor-auth columns to the users table if missing.

No Alembic environment is wired up yet for this project (empty versions/ dir,
no env.py/alembic.ini), so this follows the existing repo convention of small,
idempotent one-off scripts (see create_admin_user.py, fix_admin_hash.py, etc.)
rather than introducing a new migration framework.

Run inside the dev container:
    python scripts/migrate_add_2fa_columns.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from server.core.database import engine

NEW_COLUMNS = {
    "totp_secret": "VARCHAR(64)",
    "is_2fa_enabled": "BOOLEAN DEFAULT 0",
    "totp_recovery_codes": "JSON",
}


def main():
    with engine.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(users)"))}
        for column, ddl_type in NEW_COLUMNS.items():
            if column in existing:
                print(f"Column '{column}' already exists, skipping.")
                continue
            conn.execute(text(f"ALTER TABLE users ADD COLUMN {column} {ddl_type}"))
            print(f"Added column '{column}' ({ddl_type}).")


if __name__ == "__main__":
    main()
