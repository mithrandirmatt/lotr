"""One-off backfill: grant the LOT-018 bootstrap entitlement bundle (1 starter
deck + 5 booster packs, set 1) to any existing user account that has zero
entitlement rows -- idempotent, safe to re-run.

Some accounts were registered before `_grant_new_user_entitlements()` existed
(or while it had the `Card.name.like('Starter-%')` bug that always returned
early -- see api.py history / repo memory), so they never received their
entitlements. This backfills exactly those accounts.

Does NOT touch `tolkien_balance` -- the Tolkien welcome bonus is a separate,
harder-to-safely-backfill decision (some legacy accounts already have
non-zero balances from unrelated manual admin adjustments), so it's left
alone here; use the admin panel's Tolkien adjustment if a manual top-up is
wanted for a specific account.

Run inside the dev container (cwd MUST be server/, see repo memory gotcha):
    python scripts/migrate_backfill_entitlements.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.core.database import SessionLocal
from server.models.models import User, Entitlement


def main():
    db = SessionLocal()
    try:
        users = db.query(User).all()
        backfilled = 0
        for user in users:
            existing_count = db.query(Entitlement).filter(Entitlement.user_id == user.id).count()
            if existing_count > 0:
                continue

            db.add(Entitlement(
                user_id=user.id,
                product_type='starter_deck',
                set_number=1,
                quantity=1,
                status='active',
            ))
            for _ in range(5):
                db.add(Entitlement(
                    user_id=user.id,
                    product_type='booster_pack',
                    set_number=1,
                    quantity=1,
                    status='active',
                ))
            backfilled += 1
            print(f"Backfilled entitlements for {user.username} ({user.email})")

        db.commit()
        print(f"Done. Backfilled {backfilled}/{len(users)} user(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
