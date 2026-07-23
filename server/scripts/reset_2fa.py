"""One-off/maintenance script: forcibly clear a user's 2FA state (LOT-007.1).

For use when an account is fully locked out (authenticator app reset/lost
*and* no working recovery code), where the normal /auth/2fa/recover endpoint
can't help since it also requires a valid recovery code. This directly clears
totp_secret / is_2fa_enabled / totp_recovery_codes so the user can log in with
just their password and re-enroll via the normal /auth/2fa/setup flow.

Run inside the dev container:
    python scripts/reset_2fa.py <email-or-username>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import or_

from server.core.database import SessionLocal
from server.models.models import User


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/reset_2fa.py <email-or-username>")
        sys.exit(1)

    identifier = sys.argv[1]
    db = SessionLocal()
    try:
        user = db.query(User).filter(
            or_(User.email == identifier, User.username == identifier)
        ).first()
        if not user:
            print(f"No user found matching '{identifier}'.")
            sys.exit(1)

        user.is_2fa_enabled = False
        user.totp_secret = None
        user.totp_recovery_codes = None
        db.commit()
        print(f"2FA cleared for {user.email} ({user.username}). They can log in with just their password now.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
