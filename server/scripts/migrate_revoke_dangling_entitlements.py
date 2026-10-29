"""One-off migration: revoke dangling 'active' entitlements whose set is not
currently active (LOT-018/LOT-025 bugfix follow-up).

Mirrors what POST /admin/set-releases/{set_number}/deactivate now does
automatically when a set is deactivated -- this migration applies the same
cleanup retroactively for entitlements that were left stuck before that
route-level fix existed (e.g. from earlier LOT-025 release-bundle testing
on a set that was activated, bundle-granted, then deactivated again before
players could claim their packs). Without this, affected accounts saw an
empty "choose your starter deck" list and booster claims silently failing
(masked client-side by a misleading success message, also fixed
separately).

Idempotent -- re-running finds zero matching rows once all dangling
entitlements have been revoked.

Run inside the dev container (working directory pinned to server/):
    python scripts/migrate_revoke_dangling_entitlements.py
"""
from datetime import datetime

from sqlalchemy import text

from server.core.database import engine


def main():
    with engine.begin() as conn:
        active_sets = {
            row[0] for row in conn.execute(text("SELECT set_number FROM set_releases WHERE is_active = 1"))
        }
        rows = conn.execute(text("SELECT id, set_number FROM entitlements WHERE status = 'active'")).fetchall()
        dangling_ids = [row[0] for row in rows if row[1] not in active_sets]

        if not dangling_ids:
            print("No dangling active entitlements found. Done.")
            return

        now = datetime.utcnow()
        for entitlement_id in dangling_ids:
            conn.execute(
                text(
                    "UPDATE entitlements SET status = 'revoked', revoked_at = :now, "
                    "revocation_reason = :reason WHERE id = :id"
                ),
                {
                    "now": now,
                    "reason": "Set was deactivated before this entitlement was claimed (retroactive cleanup)",
                    "id": entitlement_id,
                },
            )
        print(f"Revoked {len(dangling_ids)} dangling entitlement(s) for inactive sets.")


if __name__ == "__main__":
    main()
