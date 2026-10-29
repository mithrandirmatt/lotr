"""One-off migration: add the weekly active-user random foil reward
tracking table (LOT-021 / LOT-025) -- idempotent, safe to re-run.

Adds a `weekly_reward_rolls` table: one row per (user, week_index),
recording that the weekly reward has already been evaluated for that user
for that week (win or lose), which is what enforces "non-stacking, max 1
reward per user per week". See `server/server/models/models.py::WeeklyRewardRoll`
for full field documentation.

No Alembic environment is wired up yet for this project, so this follows
the existing repo convention of small, idempotent one-off scripts (see
migrate_add_gifts.py, migrate_add_booster_economy.py).

Run inside the dev container (cwd MUST be server/, see repo memory gotcha):
    python scripts/migrate_add_weekly_rewards.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from server.core.database import engine

CREATE_WEEKLY_REWARD_ROLLS_SQL = """
CREATE TABLE IF NOT EXISTS weekly_reward_rolls (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    week_index INTEGER NOT NULL,
    won BOOLEAN NOT NULL DEFAULT 0,
    card_id VARCHAR(36),
    rarity VARCHAR(20),
    transaction_id VARCHAR(36),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""


def main():
    with engine.begin() as conn:
        conn.execute(text(CREATE_WEEKLY_REWARD_ROLLS_SQL))
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_weekly_reward_user ON weekly_reward_rolls (user_id)")
        )
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_weekly_reward_user_week "
                "ON weekly_reward_rolls (user_id, week_index)"
            )
        )
        print("Ensured 'weekly_reward_rolls' table exists.")


if __name__ == "__main__":
    main()
