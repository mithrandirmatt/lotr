"""One-off migration: add release event / participation tables (LOT-022 /
LOT-025) -- idempotent, safe to re-run.

Adds `release_events` (one row per monthly release event, scheduled -> live
-> closed) and `event_participations` (one row per (event, user), unique
per pair so joining is idempotent). See
`server/server/models/models.py::ReleaseEvent`/`EventParticipation` for full
field documentation.

No Alembic environment is wired up yet for this project, so this follows
the existing repo convention of small, idempotent one-off scripts (see
migrate_add_weekly_rewards.py, migrate_add_gifts.py).

Run inside the dev container (cwd MUST be server/, see repo memory gotcha):
    python scripts/migrate_add_release_events.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from server.core.database import engine

CREATE_RELEASE_EVENTS_SQL = """
CREATE TABLE IF NOT EXISTS release_events (
    id VARCHAR(36) PRIMARY KEY,
    set_number INTEGER NOT NULL,
    title VARCHAR(150) NOT NULL,
    description VARCHAR(500),
    status VARCHAR(20) NOT NULL DEFAULT 'scheduled',
    reward_policy JSON,
    starts_at DATETIME,
    ends_at DATETIME,
    closed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME
)
"""

CREATE_EVENT_PARTICIPATIONS_SQL = """
CREATE TABLE IF NOT EXISTS event_participations (
    id VARCHAR(36) PRIMARY KEY,
    event_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    reward_transaction_id VARCHAR(36),
    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""


def main():
    with engine.begin() as conn:
        conn.execute(text(CREATE_RELEASE_EVENTS_SQL))
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_release_event_set_number ON release_events (set_number)")
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_release_event_status ON release_events (status)")
        )
        conn.execute(text(CREATE_EVENT_PARTICIPATIONS_SQL))
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_event_participation_event ON event_participations (event_id)")
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_event_participation_user ON event_participations (user_id)")
        )
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_event_participation_event_user "
                "ON event_participations (event_id, user_id)"
            )
        )
        print("Ensured 'release_events' and 'event_participations' tables exist.")


if __name__ == "__main__":
    main()
