"""Utility script to create or reset the LOTR admin user in the SQLite database.

This script is intended to be run inside the dev‑container where the repository
is mounted at ``/workspace/lotr``.  It connects to the ``lotr.db`` file that
the FastAPI application uses, removes any existing row with the admin email,
and inserts a fresh user with the supplied credentials.

Example usage inside the container::

    python scripts/create_admin_user.py --email lotradmin@example.com \
        --username lotradmin --password yourmommalooksfunny

The script uses :mod:`bcrypt` for password hashing.  It prints the generated
user id on success.
"""

import argparse
import sqlite3
from pathlib import Path

try:
    import bcrypt
except ImportError as exc:  # pragma: no cover - defensive
    raise RuntimeError("bcrypt is required to run this script") from exc


DB_PATH = Path("lotr.db")


def create_admin(email: str, username: str, password: str) -> str:
    """Create or replace an admin user.

    Parameters
    ----------
    email: str
        The e‑mail address for the admin account.
    username: str
        Username to display in the UI.
    password: str
        Plain‑text password; it will be hashed with bcrypt.

    Returns
    -------
    str
        The UUID of the created user.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Ensure table exists – this matches the schema used by server/main.py.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            unique_name TEXT UNIQUE NOT NULL,
            is_admin BOOLEAN DEFAULT 0,
            is_moderator BOOLEAN DEFAULT 0
        );
        """
    )
    # Remove any existing admin with the same email.
    cur.execute("DELETE FROM users WHERE email = ?", (email,))
    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cur.execute(
        "INSERT INTO users (email, password, unique_name, is_admin) VALUES (?, ?, ?, 1)",
        (email, hashed_pw, username),
    )
    conn.commit()
    # Return the auto‑generated primary key.
    return cur.lastrowid


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or reset LOTR admin user")
    parser.add_argument("--email", required=True, help="Admin e‑mail address")
    parser.add_argument("--username", required=True, help="Admin username")
    parser.add_argument("--password", required=True, help="Plain‑text password")
    args = parser.parse_args()
    uid = create_admin(args.email, args.username, args.password)
    print(f"Created admin user with id {uid}")


if __name__ == "__main__":  # pragma: no cover
    main()