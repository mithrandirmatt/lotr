"""One-off migration: add the `economy_snapshots` table (LOT-021 historical
trend telemetry, LOT-100 follow-up) -- idempotent, safe to re-run.

See `server/server/models/models.py::EconomySnapshot` for full field
documentation and the "why lazy capture, not a scheduler" rationale.

No Alembic environment is wired up yet for this project, so this follows
the existing repo convention of small, idempotent one-off scripts (see
migrate_add_weekly_rewards.py, migrate_add_release_events.py).

Run inside the dev container (cwd MUST be server/, see repo memory gotcha):
    python scripts/migrate_add_economy_snapshots.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from server.core.database import engine

CREATE_ECONOMY_SNAPSHOTS_SQL = """
CREATE TABLE IF NOT EXISTS economy_snapshots (
    id VARCHAR(36) PRIMARY KEY,
    captured_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    total_cards_in_circulation INTEGER NOT NULL DEFAULT 0,
    total_foil_issued INTEGER NOT NULL DEFAULT 0,
    total_tolkien_net_flow INTEGER NOT NULL DEFAULT 0,
    total_sell_back_cards INTEGER NOT NULL DEFAULT 0,
    total_sell_back_tolkien_returned INTEGER NOT NULL DEFAULT 0,
    weekly_reward_total_rolls INTEGER NOT NULL DEFAULT 0,
    weekly_reward_total_wins INTEGER NOT NULL DEFAULT 0,
    weekly_reward_distinct_users INTEGER NOT NULL DEFAULT 0,
    raw_summary JSON
)
"""


def main():
    with engine.begin() as conn:
        conn.execute(text(CREATE_ECONOMY_SNAPSHOTS_SQL))
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_economy_snapshot_captured_at ON economy_snapshots (captured_at)")
        )
    print("Ensured 'economy_snapshots' table exists.")


if __name__ == "__main__":
    main()
