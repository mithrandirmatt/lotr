"""
API routes for the LOTR TCG server.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext
import jwt
import secrets
import random
import ipaddress
import os
import io
import json
import base64
import pyotp
import qrcode

from ..core.database import get_db
from ..core.config import get_settings
from ..models.models import (
    User, RefreshToken, Card, Ownership, Purchase, Refund,
    Match, MatchPlayer, MatchState, AuditLog, MatchAuditLog,
    Deck, DeckCard, SetRelease, DistributionTransaction, Gift, Entitlement,
    WeeklyRewardRoll, ReleaseEvent, EventParticipation, EconomySnapshot
)
from ..engine import booster as booster_engine
from ..services import deck_legality
from ..models.schemas import (
    # User schemas
    UserCreate, UserUpdate, UserResponse, RegisterRequest,
    # Auth schemas
    Token, LoginRequest, RefreshTokenRequest,
    # Two-factor auth schemas
    CheckExistsResponse, TwoFactorSetupResponse, TwoFactorEnableRequest,
    TwoFactorEnableResponse, TwoFactorDisableRequest, TwoFactorVerifyLoginRequest,
    TwoFactorRecoverRequest,
    # Card schemas
    CardCreate, CardUpdate, CardResponse, CardListResponse,
    CardPublishStatus, CardRejectRequest,
    # Ownership schemas
    OwnershipCreate, OwnershipUpdate, OwnershipResponse, UserCardList,
    # Purchase schemas
    PurchaseRequest, PurchaseResponse, RefundRequest, RefundResponse,
    StorePurchaseRequest, StorePurchaseResponse, StorePricingResponse, StoreProduct,
    GrantedCardSummary, StoreSellBackRequest, StoreSellBackResponse,
    AdminTolkienAdjustRequest, AdminUserDeleteRequest, AdminUserSummary, AdminUserListResponse,
    # Match schemas
    MatchCreate, MatchResponse, MatchPlayerList,
    # Audit schemas
    AuditReport,
    # Deck schemas
    DeckCreate, DeckUpdate, DeckResponse, DeckListResponse, DeckCardAdd, DeckCardRemove, DeckCardEntry,
    DeckFormat,
    # Set release schemas
    SetReleaseSummary, SetReleaseListResponse, ActiveSetsResponse,
    # Economy telemetry schemas
    CirculationEntry, DistributionSourceTotals, SellBackRarityTotals, EconomySummaryResponse,
    WeeklyRewardStats, EconomySnapshotSummary, EconomyTrendsResponse,
    # Gift ledger schemas
    GiftStatus, AdminGiftCreateRequest, GiftSummary, GiftListResponse, GiftRedeemResponse,
    # Entitlement schemas
    EntitlementStatus, EntitlementSummary, EntitlementListResponse, EntitlementClaimResponse,
    EntitlementClaimRequest, StarterDeckOption, StarterDeckOptionsResponse,
    # Deck legality schemas
    DeckLegalityResponse,
    # Deck builder availability schemas
    OwnedCardAvailability, OwnedCardAvailabilityListResponse,
    # Release event schemas
    ReleaseEventCreate, ReleaseEventSummary, ReleaseEventListResponse,
    EventParticipationSummary, EventParticipationListResponse,
)

# Router setup
router = APIRouter(prefix="/api/v1", tags=["API"])

# Security
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

# JWT settings
# LOT-6.5: SECRET_KEY previously regenerated randomly on every process start,
# invalidating all issued tokens on every restart. Now sourced from the shared
# Settings (SECRET_KEY env var), which is stable across restarts.
SECRET_KEY = get_settings().SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 30

# LOT-006 store pricing strategy (1 USD == 1 Tolkien)
USD_PER_TOLKIEN = 1.0
STORE_PRODUCT_PRICES_TOLKIENS = {
    "pack": 1,
    "starter_deck": 5,
    "booster_box": 25,
}

# LOT-025 slice 3: a booster box's Tolkien price (25) is exactly 25x the
# single-pack price (1), with no bulk discount modeled yet, so a box is
# defined as 25 packs. Not specified anywhere in the design docs -- a
# placeholder tuning knob like the sell-back scale constant, revisit during
# playtesting.
BOOSTER_BOX_PACK_COUNT = 25

# LOT-018: one-time Tolkien welcome bonus credited to every new account
# alongside the starter deck / booster pack entitlements. Not specified in
# the design docs -- a tuning knob, confirmed with the product owner as 5
# (enough for a player to buy an extra booster pack if they want).
WELCOME_TOLKIEN_BONUS = 5

# LOT-025: maximum number of decks a single user may have saved at once.
MAX_DECKS_PER_USER = 25

# LOT-021/LOT-025: weekly active-user random foil reward. Not specified as
# an exact number in the design docs beyond "low-probability" -- a
# placeholder tuning knob like the other economy constants, revisit during
# playtesting. Rarity weights bias toward common, mirroring booster pack
# composition (1 rare/3 uncommon/7 common per pack).
WEEKLY_FOIL_REWARD_CHANCE = 0.05
WEEKLY_FOIL_REWARD_RARITY_WEIGHTS: Dict[str, int] = {"common": 70, "uncommon": 20, "rare": 10}

LOCAL_ADMIN_USERNAME = os.getenv("LOTR_LOCAL_ADMIN_USERNAME", "lotradmin")
LOCAL_ADMIN_PASSWORD = os.getenv("LOTR_LOCAL_ADMIN_PASSWORD", "yourmommalooksfunny")
LOCAL_ADMIN_EMAIL = os.getenv("LOTR_LOCAL_ADMIN_EMAIL", "lotradmin@example.com")
ENABLE_LOCAL_ADMIN_SHORTCUT = os.getenv("LOTR_ENABLE_LOCAL_ADMIN_SHORTCUT", "1").strip().lower() in {
    "1", "true", "yes", "on"
}

# Shared password hashing context for the 2FA helpers below.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

MFA_TOKEN_EXPIRE_MINUTES = 5
TOTP_ISSUER_NAME = "LotR TCG"
RECOVERY_CODE_COUNT = 10


def create_mfa_token(user_id: str) -> str:
    """Create a short-lived JWT proving the password step of login succeeded,
    used to gate the follow-up TOTP code submission."""
    to_encode = {
        "sub": user_id,
        "type": "mfa",
        "exp": datetime.utcnow() + timedelta(minutes=MFA_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_mfa_token(token: str) -> str:
    """Verify an MFA token and return the associated user id."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired MFA session")
    if payload.get("type") != "mfa" or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA session")
    return payload["sub"]


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=TOTP_ISSUER_NAME)


def qr_code_png_base64(uri: str) -> str:
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def verify_totp_code(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    return pyotp.totp.TOTP(secret).verify(code, valid_window=1)


def generate_recovery_codes(count: int = RECOVERY_CODE_COUNT) -> List[str]:
    return [f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(count)]


def consume_recovery_code(user: User, code: str) -> bool:
    """Check `code` against the user's remaining hashed recovery codes; if it
    matches, remove that code (single-use) and return True."""
    if not user.totp_recovery_codes:
        return False
    for hashed in user.totp_recovery_codes:
        if pwd_context.verify(code, hashed):
            remaining = list(user.totp_recovery_codes)
            remaining.remove(hashed)
            user.totp_recovery_codes = remaining
            return True
    return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token.

    Includes a random `jti` (JWT ID) so two refresh tokens issued for the
    same user within the same second (e.g. login immediately followed by a
    refresh, or two concurrent refresh calls) don't encode to the exact same
    JWT string -- `refresh_tokens.token` has a UNIQUE DB constraint, and
    without a nonce, `jwt.encode` is deterministic for identical
    sub/exp/type payloads, causing an IntegrityError -> 500 on insert.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh", "jti": secrets.token_urlsafe(16)})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str, credentials_exception: HTTPException) -> dict:
    """Verify JWT token and return payload."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_type = payload.get("type")
        if token_type != "access":
            raise credentials_exception
        return payload
    except jwt.ExpiredSignatureError:
        raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception


def _is_local_address(raw_host: Optional[str]) -> bool:
    if not raw_host:
        return False
    host = raw_host.strip().split(",")[0].strip()
    if host.lower() == "localhost":
        return True
    try:
        parsed = ipaddress.ip_address(host)
        return parsed.is_loopback or parsed.is_private
    except ValueError:
        return False


def _is_local_request(request: Request) -> bool:
    forwarded = request.headers.get("x-forwarded-for")
    if _is_local_address(forwarded):
        return True
    if request.client and _is_local_address(request.client.host):
        return True
    return False


def _is_local_admin_shortcut(request: Request, username: str, password: str) -> bool:
    return (
        ENABLE_LOCAL_ADMIN_SHORTCUT
        and username == LOCAL_ADMIN_USERNAME
        and password == LOCAL_ADMIN_PASSWORD
        and _is_local_request(request)
    )


def _issue_tokens_for_user(db: Session, user: User) -> Token:
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})

    refresh_token_record = RefreshToken(
        user_id=user.id,
        token=refresh_token,
        refresh_secret=secrets.token_urlsafe(32),
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(refresh_token_record)
    db.commit()

    # LOT-021/LOT-025: weekly active-user random foil reward roll. Never
    # let a reward-roll issue block login -- swallow unexpected errors.
    try:
        _maybe_roll_weekly_foil_reward(user, db)
    except Exception:
        logging.exception("Weekly foil reward roll failed for user %s", user.id)
        db.rollback()

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES
    )


# ============== DEPENDENCIES ==============

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = verify_token(token, credentials_exception)
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require admin privileges for protected endpoints."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


# Fellowship (Set 1) is always available and must never be deactivated,
# per LOT-025's release-control acceptance criteria.
PROTECTED_SET_NUMBERS = {1}


def _is_protected_set(set_number: int) -> bool:
    """Return True if the given set number is permanently active and must
    reject deactivation (currently just Set 1 / Fellowship)."""
    return set_number in PROTECTED_SET_NUMBERS


# ============== AUTH ROUTES ==============

@router.get("/auth/check-email", response_model=CheckExistsResponse)
async def check_email(email: str, db: Session = Depends(get_db)):
    """Check whether an email address is already registered."""
    exists = db.query(User).filter(User.email == email).first() is not None
    return CheckExistsResponse(exists=exists)


@router.get("/auth/check-unique-name", response_model=CheckExistsResponse)
async def check_unique_name(unique_name: str, db: Session = Depends(get_db)):
    """Check whether a unique name (username) is already taken."""
    exists = db.query(User).filter(User.username == unique_name).first() is not None
    return CheckExistsResponse(exists=exists)


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user."""
    if user_data.password != user_data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match"
        )

    # Check if email exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Check if unique name exists
    if db.query(User).filter(User.username == user_data.unique_name).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unique name already taken"
        )

    hashed_password = pwd_context.hash(user_data.password)

    # Create user. New accounts always start with 2FA disabled — LOT-007
    # requires it be set up right after the user's first login.
    user = User(
        email=user_data.email,
        username=user_data.unique_name,
        password_hash=hashed_password,
        is_active=True,
        is_verified=True,  # Email verification can be added later
        is_admin=False,
        is_moderator=False,
        is_2fa_enabled=False,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # Grant new-user entitlements (LOT-018): 1 starter deck + 5 booster packs from set 1
    _grant_new_user_entitlements(user, db)

    return {"message": "Registration successful. Please log in."}


def _grant_new_user_entitlements(user: User, db: Session):
    """Grant new-user entitlement bundles (LOT-018).

    New accounts receive:
      - 1 starter deck entitlement from set 1 only
      - 5 booster pack entitlements from set 1 only
      - a one-time Tolkien welcome bonus (WELCOME_TOLKIEN_BONUS), credited
        immediately (not an entitlement -- there's nothing to "claim" for a
        currency grant)

    The entitlement rows only create a claimable grant -- they do NOT
    generate any cards. Actual card generation happens at claim time via
    `POST /entitlements/{id}/claim`, which reuses the same card-generation
    helpers as `/store/purchase` and `/gifts/{id}/redeem`. This is a
    one-time bootstrap grant; on each new set release activation, eligible
    users receive the same bundle for that set (handled by LOT-025 release
    control logic).
    """
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

    user.tolkien_balance += WELCOME_TOLKIEN_BONUS
    db.add(DistributionTransaction(
        user_id=user.id,
        source="starter",
        product="tolkien_bonus",
        set_number=None,
        cards=[],
        tolkien_delta=WELCOME_TOLKIEN_BONUS,
    ))
    db.commit()


def _grant_release_bundle_to_all_users(set_number: int, db: Session) -> int:
    """Grant the per-set-unlock release bundle (LOT-018) to every eligible user.

    Called when a (non-launch) set transitions from inactive -> active.
    Each eligible (active) user receives, at most once per set: 1 starter
    deck entitlement + 5 booster pack entitlements for that set_number.

    Idempotency: a user already holding any entitlement for this
    set_number (from a prior activation of the same set, e.g. an earlier
    activate/deactivate/reactivate cycle) is skipped entirely, so a set can
    be toggled on/off/on without re-granting -- matching the LOT-018
    acceptance criterion "each eligible user receives exactly one release
    bundle for that set".

    Returns the number of users granted a bundle (for admin-facing
    confirmation / telemetry).
    """
    already_granted_user_ids = {
        row[0]
        for row in db.query(Entitlement.user_id)
        .filter(Entitlement.set_number == set_number)
        .distinct()
        .all()
    }
    eligible_users = db.query(User).filter(User.is_active == True).all()  # noqa: E712

    granted_count = 0
    for user in eligible_users:
        if user.id in already_granted_user_ids:
            continue
        db.add(Entitlement(
            user_id=user.id,
            product_type='starter_deck',
            set_number=set_number,
            quantity=1,
            status='active',
        ))
        for _ in range(5):
            db.add(Entitlement(
                user_id=user.id,
                product_type='booster_pack',
                set_number=set_number,
                quantity=1,
                status='active',
            ))
        granted_count += 1

    db.commit()
    return granted_count


def _ensure_live_release_event(set_number: int, db: Session) -> ReleaseEvent:
    """Ensure a `live` ReleaseEvent exists for this set_number (LOT-022).

    Reuses the most recent event already recorded for this set_number
    (reactivating it to `live`) instead of creating a duplicate row, so a
    deactivate/reactivate cycle doesn't pile up redundant event records --
    this is what "Set activations are linked to event records" means in
    practice.
    """
    event = (
        db.query(ReleaseEvent)
        .filter(ReleaseEvent.set_number == set_number)
        .order_by(ReleaseEvent.created_at.desc())
        .first()
    )
    now = datetime.utcnow()
    if event is None:
        event = ReleaseEvent(
            set_number=set_number,
            title=f"Set {set_number} Release",
            status='live',
            starts_at=now,
        )
        db.add(event)
    elif event.status != 'live':
        event.status = 'live'
        event.starts_at = event.starts_at or now
        event.closed_at = None
    db.commit()
    db.refresh(event)
    return event


def _maybe_roll_weekly_foil_reward(user: User, db: Session) -> None:
    """Weekly active-user random foil reward (LOT-021/LOT-025).

    Triggered lazily at login time (the "active this week" signal) rather
    than by a background scheduler -- this repo has no job-scheduling infra,
    and login is a cheap, natural checkpoint every active user hits.

    Reward windows are anchored to the user's persisted registration
    timestamp (`User.created_at`), not a global calendar week:
    `week_index = floor((now - created_at).days / 7)`. Exactly one roll is
    recorded per (user, week_index) via the `weekly_reward_rolls` unique
    index, regardless of outcome -- this is what enforces "non-stacking,
    max 1 reward per user per week" even across multiple logins in the same
    week.

    On a win, grants one foil card (rarity chosen via
    `WEEKLY_FOIL_REWARD_RARITY_WEIGHTS`) from the currently-active card
    pool, recorded with `Ownership.source="reward"` and a
    `DistributionTransaction(source="reward")` for audit linkage. Failures
    to find a matching card (e.g. no active cards of the chosen rarity) are
    swallowed silently -- a missed reward roll should never break login.
    """
    if not user.created_at:
        return

    now = datetime.utcnow()
    created_at = user.created_at
    if created_at.tzinfo is not None:
        created_at = created_at.replace(tzinfo=None)
    elapsed_days = (now - created_at).days
    if elapsed_days < 0:
        return
    week_index = elapsed_days // 7

    already_rolled = db.query(WeeklyRewardRoll).filter(
        WeeklyRewardRoll.user_id == user.id,
        WeeklyRewardRoll.week_index == week_index,
    ).first()
    if already_rolled:
        return

    won = random.random() < WEEKLY_FOIL_REWARD_CHANCE
    if not won:
        db.add(WeeklyRewardRoll(user_id=user.id, week_index=week_index, won=False))
        db.commit()
        return

    rarities = list(WEEKLY_FOIL_REWARD_RARITY_WEIGHTS.keys())
    weights = list(WEEKLY_FOIL_REWARD_RARITY_WEIGHTS.values())
    chosen_rarity = random.choices(rarities, weights=weights, k=1)[0]

    candidate_cards = db.query(Card).filter(
        Card.rarity == chosen_rarity,
        Card.is_active.is_(True),
    ).all()
    if not candidate_cards:
        # Nothing to grant (e.g. no active cards of this rarity yet) --
        # still record the roll so the week isn't re-evaluated, but with no
        # card/transaction attached.
        db.add(WeeklyRewardRoll(user_id=user.id, week_index=week_index, won=False))
        db.commit()
        return

    card = random.choice(candidate_cards)

    ownership = db.query(Ownership).filter(
        Ownership.user_id == user.id,
        Ownership.card_id == card.id,
        Ownership.is_foil == True,  # noqa: E712
    ).first()
    if ownership:
        ownership.quantity += 1
    else:
        db.add(Ownership(
            card_id=card.id,
            user_id=user.id,
            source="reward",
            quantity=1,
            is_foil=True,
        ))

    transaction = DistributionTransaction(
        user_id=user.id,
        source="reward",
        product="weekly_foil",
        set_number=card.set_number,
        cards=[{"card_id": card.id, "rarity": card.rarity, "is_foil": True, "quantity": 1}],
        tolkien_delta=0,
    )
    db.add(transaction)
    db.flush()

    db.add(WeeklyRewardRoll(
        user_id=user.id,
        week_index=week_index,
        won=True,
        card_id=card.id,
        rarity=card.rarity,
        transaction_id=transaction.id,
    ))
    db.commit()




import logging

# Log file for login attempts – create the directory if it doesn't exist
log_dir = Path("server/server/logs")
log_dir.mkdir(parents=True, exist_ok=True)
handler = logging.FileHandler(log_dir / "api_login.log")
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

logging.basicConfig(level=logging.INFO, handlers=[handler])

@router.post("/auth/login")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login and get access token."""
    logging.info("Login attempt for %s", form_data.username)

    if _is_local_admin_shortcut(request, form_data.username, form_data.password):
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        user = db.query(User).filter(User.username == LOCAL_ADMIN_USERNAME).first()
        if not user:
            user = User(
                email=LOCAL_ADMIN_EMAIL,
                username=LOCAL_ADMIN_USERNAME,
                password_hash=pwd_context.hash(LOCAL_ADMIN_PASSWORD),
                first_name="Local",
                last_name="Admin",
                is_active=True,
                is_verified=True,
                is_admin=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logging.info("Local admin account created for shortcut login")
        else:
            changed = False
            if not user.is_active:
                user.is_active = True
                changed = True
            if not user.is_verified:
                user.is_verified = True
                changed = True
            if not user.is_admin:
                user.is_admin = True
                changed = True
            if user.email != LOCAL_ADMIN_EMAIL:
                # Repair rows created before LOCAL_ADMIN_EMAIL's default was
                # fixed to a validly-formatted address (e.g. "lotradmin@localhost",
                # which fails EmailStr validation on response serialization).
                user.email = LOCAL_ADMIN_EMAIL
                changed = True
            if changed:
                db.commit()
                db.refresh(user)

        logging.info("Local admin shortcut login succeeded")
        return _issue_tokens_for_user(db, user)

    user = db.query(User).filter(
        or_(User.email == form_data.username, User.username == form_data.username)
    ).first()

    if not user or not user.is_active:
        logging.warning("Login failed (user not found or inactive) for %s", form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    if not pwd_context.verify(form_data.password, user.password_hash):
        logging.warning("Login failed (bad password) for %s", form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.is_2fa_enabled:
        logging.info("Password verified for %s; awaiting 2FA code", form_data.username)
        return {"requires_2fa": True, "mfa_token": create_mfa_token(user.id)}

    return _issue_tokens_for_user(db, user)


@router.post("/auth/2fa/setup", response_model=TwoFactorSetupResponse)
async def setup_2fa(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Generate a new (not-yet-active) TOTP secret for the current user."""
    secret = generate_totp_secret()
    current_user.totp_secret = secret
    db.commit()

    uri = totp_provisioning_uri(secret, current_user.email)
    return TwoFactorSetupResponse(
        secret=secret,
        otpauth_uri=uri,
        qr_code_png_base64=qr_code_png_base64(uri),
    )


@router.post("/auth/2fa/enable", response_model=TwoFactorEnableResponse)
async def enable_2fa(
    body: TwoFactorEnableRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Confirm the pending TOTP secret with a code and turn 2FA on."""
    if not current_user.totp_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Call /auth/2fa/setup first")

    if not verify_totp_code(current_user.totp_secret, body.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid authentication code")

    recovery_codes = generate_recovery_codes()
    current_user.is_2fa_enabled = True
    current_user.totp_recovery_codes = [pwd_context.hash(c) for c in recovery_codes]
    db.commit()

    return TwoFactorEnableResponse(recovery_codes=recovery_codes)


@router.post("/auth/2fa/disable")
async def disable_2fa(
    body: TwoFactorDisableRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disable 2FA; requires the account password plus a valid TOTP or recovery code."""
    if not pwd_context.verify(body.password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    valid = verify_totp_code(current_user.totp_secret, body.code) or consume_recovery_code(current_user, body.code)
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid authentication code")

    current_user.is_2fa_enabled = False
    current_user.totp_secret = None
    current_user.totp_recovery_codes = None
    db.commit()

    return {"message": "Two-factor authentication disabled"}


@router.post("/auth/2fa/verify-login", response_model=Token)
async def verify_2fa_login(body: TwoFactorVerifyLoginRequest, db: Session = Depends(get_db)):
    """Complete login by exchanging an mfa_token + TOTP/recovery code for real tokens."""
    user_id = verify_mfa_token(body.mfa_token)
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active or not user.is_2fa_enabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA session")

    valid = verify_totp_code(user.totp_secret, body.code) or consume_recovery_code(user, body.code)
    if not valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication code")

    db.commit()
    return _issue_tokens_for_user(db, user)


@router.post("/auth/2fa/recover", response_model=Token)
async def recover_2fa(body: TwoFactorRecoverRequest, db: Session = Depends(get_db)):
    """Log in with a recovery code when the authenticator app itself is no
    longer available (LOT-007.1). Unlike /auth/2fa/verify-login, this also
    clears the account's 2FA state (secret + remaining recovery codes), so
    the caller lands back on the normal /auth/2fa/setup flow to scan a fresh
    QR code instead of being left with a stale, unusable TOTP secret."""
    user_id = verify_mfa_token(body.mfa_token)
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active or not user.is_2fa_enabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA session")

    if not consume_recovery_code(user, body.recovery_code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or already-used recovery code")

    user.is_2fa_enabled = False
    user.totp_secret = None
    user.totp_recovery_codes = None
    db.commit()

    return _issue_tokens_for_user(db, user)


@router.post("/auth/refresh", response_model=Token)
async def refresh_token_endpoint(token_data: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Refresh access token using refresh token."""
    # Verify refresh token
    token_payload = jwt.decode(
        token_data.refresh_token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
        options={"require": ["exp", "type"]}
    )

    if token_payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    if datetime.utcnow() > datetime.fromtimestamp(token_payload["exp"]):
        raise HTTPException(status_code=401, detail="Token expired")

    # Check if token is revoked
    token_record = db.query(RefreshToken).filter(
        RefreshToken.token == token_data.refresh_token
    ).first()

    if not token_record or token_record.is_revoked:
        raise HTTPException(status_code=401, detail="Invalid or revoked token")

    # Revoke old token
    token_record.is_revoked = True

    # Create new tokens
    access_token = create_access_token(data={"sub": token_record.user_id})
    new_refresh_token = create_refresh_token(data={"sub": token_record.user_id})

    # Store new refresh token
    new_token_record = RefreshToken(
        user_id=token_record.user_id,
        token=new_refresh_token,
        refresh_secret=secrets.token_urlsafe(32),
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(new_token_record)
    db.commit()

    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES
    )


@router.post("/auth/logout")
async def logout(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Logout and revoke refresh token."""
    # Revoke all refresh tokens for this user
    db.query(RefreshToken).filter(
        RefreshToken.user_id == current_user.id,
        RefreshToken.is_revoked == False
    ).update({"is_revoked": True})
    db.commit()
    return {"message": "Logged out successfully"}


# ============== USER ROUTES ==============

@router.get("/users/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return current_user


@router.put("/users/me", response_model=UserResponse)
async def update_current_user(user_data: UserUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update current user information."""
    update_data = user_data.model_dump(exclude_unset=True)

    # Handle password change
    if update_data.get("new_password"):
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        update_data["password_hash"] = pwd_context.hash(update_data.pop("new_password"))

    # Update user
    for field, value in update_data.items():
        if field != "password_hash":  # Already handled above
            setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)
    return current_user


# ============== CARD ROUTES ==============

@router.get("/cards", response_model=CardListResponse)
async def list_cards(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    rarity: Optional[str] = None,
    min_cost: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all cards with filtering and pagination.

    Public catalog view -- only `published` cards are visible here (LOT-100
    card-authoring review gate). Drafts/in-review cards are only visible
    via `GET /admin/cards`.
    """
    query = db.query(Card).filter(Card.publish_status == 'published')

    # Apply filters
    if rarity:
        query = query.filter(Card.rarity == rarity)
    if min_cost is not None:
        query = query.filter(Card.cost >= min_cost)
    if search:
        query = query.filter(Card.name.ilike(f"%{search}%"))

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    cards = query.offset(offset).limit(page_size).all()

    return CardListResponse(
        items=[CardResponse.model_validate(card) for card in cards],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )


@router.get("/cards/{card_id}", response_model=CardResponse)
async def get_card(card_id: str, db: Session = Depends(get_db)):
    """Get a specific card by ID (public catalog -- must be `published`)."""
    card = db.query(Card).filter(Card.id == card_id, Card.publish_status == 'published').first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


def _validate_card_set_number(set_number: Optional[int], db: Session) -> None:
    """Release linking (LOT-100): a card tagged to a set must reference a
    set that's actually been registered via the set-release system."""
    if set_number is None:
        return
    exists = db.query(SetRelease).filter(SetRelease.set_number == set_number).first()
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"set_number {set_number} does not correspond to a known release set",
        )


@router.post("/cards", response_model=CardResponse, status_code=status.HTTP_201_CREATED)
async def create_card(
    card_data: CardCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Author a new card (admin only). Starts as `draft` -- use the
    review-gate endpoints (`POST /admin/cards/{id}/submit-review`, `.../publish`)
    to make it visible in the public catalog."""
    _validate_card_set_number(card_data.set_number, db)
    # CardCreate exposes `stats`, but the Card ORM column is `attributes`.
    card_fields = card_data.model_dump()
    card_fields["attributes"] = card_fields.pop("stats", None)
    card = Card(**card_fields)
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


@router.put("/cards/{card_id}", response_model=CardResponse)
async def update_card(
    card_id: str,
    card_data: CardUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Update a card (admin only)."""
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    update_data = card_data.model_dump(exclude_unset=True)
    if "set_number" in update_data:
        _validate_card_set_number(update_data["set_number"], db)
    if "stats" in update_data:
        # CardUpdate exposes `stats`, but the Card ORM column is `attributes`.
        update_data["attributes"] = update_data.pop("stats")
    for field, value in update_data.items():
        setattr(card, field, value)

    db.commit()
    db.refresh(card)
    return card


@router.get("/admin/cards", response_model=CardListResponse)
async def admin_list_cards(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    publish_status: Optional[CardPublishStatus] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Admin authoring queue -- lists cards of ANY publish status
    (draft/in_review/published), optionally filtered to one status."""
    query = db.query(Card)
    if publish_status is not None:
        query = query.filter(Card.publish_status == publish_status.value)

    total = query.count()
    offset = (page - 1) * page_size
    cards = query.order_by(Card.created_at.desc()).offset(offset).limit(page_size).all()

    return CardListResponse(
        items=[CardResponse.model_validate(card) for card in cards],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.post("/admin/cards/{card_id}/submit-review", response_model=CardResponse)
async def admin_submit_card_for_review(
    card_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Review gate step 1: `draft` -> `in_review`."""
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    if card.publish_status != 'draft':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Card must be in 'draft' status to submit for review (currently '{card.publish_status}')",
        )
    card.publish_status = 'in_review'
    db.commit()
    db.refresh(card)
    return card


@router.post("/admin/cards/{card_id}/publish", response_model=CardResponse)
async def admin_publish_card(
    card_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Review gate step 2: `in_review` -> `published`."""
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    if card.publish_status != 'in_review':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Card must be in 'in_review' status to publish (currently '{card.publish_status}')",
        )
    card.publish_status = 'published'
    db.commit()
    db.refresh(card)
    return card


@router.post("/admin/cards/{card_id}/reject", response_model=CardResponse)
async def admin_reject_card(
    card_id: str,
    payload: CardRejectRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Review gate rejection: `in_review` -> `draft`, with optional reviewer notes."""
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    if card.publish_status != 'in_review':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Card must be in 'in_review' status to reject (currently '{card.publish_status}')",
        )
    card.publish_status = 'draft'
    card.review_notes = payload.review_notes
    db.commit()
    db.refresh(card)
    return card


@router.delete("/admin/cards/{card_id}", response_model=CardResponse)
async def admin_remove_card(
    card_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Soft-delete a card so it is no longer purchasable/selectable."""
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    card.is_active = False
    db.commit()
    db.refresh(card)
    return card


# ============== OWNERSHIP ROUTES ==============

@router.get("/users/me/cards", response_model=UserCardList)
async def get_user_cards(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get all cards owned by the current user."""
    # Get all active ownerships for this user
    ownerships = db.query(Ownership).filter(
        Ownership.user_id == current_user.id,
        Ownership.is_active == True
    ).all()

    # Get card details
    cards_data = []
    total_cost = 0
    for ownership in ownerships:
        card = db.query(Card).filter(Card.id == ownership.card_id).first()
        if card:
            cards_data.append(OwnershipResponse(
                id=ownership.id,
                card_id=ownership.card_id,
                user_id=ownership.user_id,
                source=ownership.source,
                acquired_at=ownership.acquired_at,
                metadata=ownership.metadata_json,
                is_active=ownership.is_active
            ))
            total_cost += card.cost

    return UserCardList(
        user_id=current_user.id,
        cards=cards_data,
        total_cards=len(cards_data),
        total_cost=total_cost
    )


@router.get("/cards/{card_id}/owners", response_model=List[OwnershipResponse])
async def get_card_owners(card_id: str, db: Session = Depends(get_db)):
    """Get all current owners of a card (for tracking purposes)."""
    ownerships = db.query(Ownership).filter(
        Ownership.card_id == card_id,
        Ownership.is_active == True
    ).all()
    return [
        OwnershipResponse(
            id=ownership.id,
            card_id=ownership.card_id,
            user_id=ownership.user_id,
            source=ownership.source,
            acquired_at=ownership.acquired_at,
            metadata=ownership.metadata_json,
            is_active=ownership.is_active,
            quantity=ownership.quantity,
        )
        for ownership in ownerships
    ]


# ============== RELEASE ROUTES (LOT-025) ==============

@router.get("/releases/active-sets", response_model=ActiveSetsResponse)
async def get_active_sets(db: Session = Depends(get_db)):
    """Public list of currently-active (purchasable) sets, used to gate the
    storefront and deck builder to only sets the admin has activated."""
    sets = db.query(SetRelease).filter(SetRelease.is_active.is_(True)).order_by(SetRelease.set_number).all()
    return ActiveSetsResponse(active_sets=[SetReleaseSummary.model_validate(s) for s in sets])


# ============== PURCHASE ROUTES ==============

@router.get("/store/pricing", response_model=StorePricingResponse)
async def get_store_pricing():
    """Expose LOT-006 Tolkien product pricing strategy."""
    return StorePricingResponse(
        currency="Tolkien",
        usd_per_tolkien=USD_PER_TOLKIEN,
        products=STORE_PRODUCT_PRICES_TOLKIENS,
    )


def _generate_and_grant_packs(
    db: Session, user_id: str, set_number: int, pack_count: int, ownership_source: str = "purchase",
):
    """Validate the set is active, generate `pack_count` booster packs from
    its catalog, and grant the resulting cards to `user_id` (Ownership
    upsert, consolidated per (card_id, is_foil) to avoid duplicate-key
    inserts within one autoflush=False transaction -- see LOT-025 slice 2).

    Shared by `/store/purchase` (pack/booster_box) and `/gifts/{id}/redeem`
    (LOT-019), which differ only in what `DistributionTransaction` they
    record (source/product/tolkien_delta) -- building that transaction is
    left to the caller.

    `ownership_source` must be one of `Ownership.source`'s declared enum
    values (purchase/trade/reward/event/admin -- it has no 'gift' value).
    Gift redemptions pass `ownership_source="reward"`; the actual 'gift'
    provenance is recorded independently on the `DistributionTransaction`
    the caller creates, which is what the "every card delta has a
    transaction ID" requirement (LOT-020) actually needs.

    Returns (cards_granted, generated_cards, rng_seed).
    """
    set_release = db.query(SetRelease).filter(SetRelease.set_number == set_number).first()
    if not set_release or not set_release.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Set {set_number} is not currently active",
        )

    cards_by_rarity: Dict[str, List[Card]] = {
        rarity: db.query(Card).filter(
            Card.set_number == set_number,
            Card.rarity == rarity,
            Card.is_active.is_(True),
        ).all()
        for rarity in booster_engine.RARITY_COMPOSITION
    }

    rng_seed = secrets.token_hex(16)
    rng = random.Random(rng_seed)
    generated_cards: List[Dict[str, Any]] = []
    try:
        for _ in range(pack_count):
            generated_cards.extend(booster_engine.generate_booster_pack(cards_by_rarity, rng))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    quantity_deltas: Dict[tuple, int] = {}
    cards_granted: List[GrantedCardSummary] = []
    for card_outcome in generated_cards:
        key = (card_outcome["card_id"], card_outcome["is_foil"])
        quantity_deltas[key] = quantity_deltas.get(key, 0) + 1
        cards_granted.append(GrantedCardSummary(
            card_id=card_outcome["card_id"],
            name=card_outcome["name"],
            rarity=card_outcome["rarity"],
            is_foil=card_outcome["is_foil"],
            image_url=card_outcome.get("image_url"),
        ))

    for (card_id, is_foil), delta in quantity_deltas.items():
        ownership = db.query(Ownership).filter(
            Ownership.user_id == user_id,
            Ownership.card_id == card_id,
            Ownership.is_foil == is_foil,
        ).first()
        if ownership:
            ownership.quantity += delta
        else:
            db.add(Ownership(
                card_id=card_id,
                user_id=user_id,
                source=ownership_source,
                quantity=delta,
                is_foil=is_foil,
            ))

    return cards_granted, generated_cards, rng_seed


# Curated starter deck decklists (LOT-018/LOT-025), resolved to real card IDs
# by server/scripts/build_starter_deck_catalog.py from the wiki-sourced
# starter_database.json. Only set 1 (Fellowship of the Ring) has a curated
# decklist today; other blocks become relevant once those sets are unlocked.
STARTER_DECKS_BY_SET: Dict[int, Dict[str, Any]] = {}
_starter_decks_set1_path = Path(__file__).resolve().parent.parent / "data" / "starter_decks_set1.json"
if _starter_decks_set1_path.exists():
    with _starter_decks_set1_path.open(encoding="utf-8") as _f:
        STARTER_DECKS_BY_SET[1] = json.load(_f)


def _grant_starter_deck_cards(db: Session, user_id: str, set_number: int, deck_key: Optional[str] = None):
    """Grant one curated starter deck's exact cards (LOT-018/LOT-025).
    Unlike `_generate_and_grant_packs`, this is not RNG booster generation --
    it grants a fixed, real decklist (see STARTER_DECKS_BY_SET above).

    If `deck_key` is given, that specific deck is granted (see GET
    /entitlements/starter-deck-options for the available keys); otherwise
    one is chosen at random among the curated decks for `set_number`.

    Returns (cards_granted, deck_name, tx_cards) where `tx_cards` is the
    aggregated-per-card delta list suitable for `DistributionTransaction.cards`.
    """
    decks = STARTER_DECKS_BY_SET.get(set_number)
    if not decks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No curated starter deck available for set {set_number} yet",
        )
    if deck_key:
        deck = decks.get(deck_key)
        if not deck:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown starter deck option: {deck_key}",
            )
    else:
        deck = random.choice(list(decks.values()))

    card_ids = [entry["card_id"] for entry in deck["cards"]]
    cards_by_id = {c.id: c for c in db.query(Card).filter(Card.id.in_(card_ids)).all()}

    # Consolidate by card_id first: the curated decklist can reference the
    # same resolved card_id more than once (e.g. two distinct collector_info
    # tokens that both alias to the same "kept" card after card_database.json's
    # dedup pass -- see build_starter_deck_catalog.py). SessionLocal is
    # autoflush=False, so a naive query-then-insert loop over duplicate keys
    # within one transaction would attempt two INSERTs for the same
    # (card_id, user_id, is_foil) and hit the ownerships unique constraint.
    quantity_by_card_id: Dict[str, int] = {}
    for entry in deck["cards"]:
        if entry["card_id"] not in cards_by_id:
            continue  # defensive: shouldn't happen, catalog was resolved against this same table
        quantity_by_card_id[entry["card_id"]] = quantity_by_card_id.get(entry["card_id"], 0) + entry["quantity"]

    cards_granted: List[GrantedCardSummary] = []
    tx_cards: List[Dict[str, Any]] = []
    for card_id, quantity in quantity_by_card_id.items():
        card = cards_by_id[card_id]

        ownership = db.query(Ownership).filter(
            Ownership.user_id == user_id,
            Ownership.card_id == card.id,
            Ownership.is_foil.is_(False),
        ).first()
        if ownership:
            ownership.quantity += quantity
        else:
            db.add(Ownership(
                card_id=card.id, user_id=user_id, source="reward",
                quantity=quantity, is_foil=False,
            ))

        for _ in range(quantity):
            cards_granted.append(GrantedCardSummary(
                card_id=card.id, name=card.name, rarity=card.rarity, is_foil=False,
                image_url=card.image_url,
            ))
        tx_cards.append({"card_id": card.id, "rarity": card.rarity, "is_foil": False, "quantity": quantity})

    return cards_granted, deck["name"], tx_cards


@router.post("/store/purchase", response_model=StorePurchaseResponse)
async def purchase_store_product(
    payload: StorePurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Purchase packs/decks/boxes using Tolkien balance.

    product=pack and product=booster_box generate and grant cards
    server-side (LOT-020/LOT-025 slices 2-3): a booster box is
    BOOSTER_BOX_PACK_COUNT packs. product=starter_deck grants one randomly
    -chosen curated deck per unit purchased (LOT-018/LOT-025) -- see
    `_grant_starter_deck_cards` -- currently only available for set 1.
    """
    unit_price = STORE_PRODUCT_PRICES_TOLKIENS[payload.product.value]
    total_price = unit_price * payload.quantity

    if current_user.tolkien_balance < total_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient Tolkien balance. Need {total_price}, have {current_user.tolkien_balance}",
        )

    cards_granted: List[GrantedCardSummary] = []
    transaction_id: Optional[str] = None

    if payload.product in (StoreProduct.PACK, StoreProduct.BOOSTER_BOX):
        if payload.set_number is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="set_number is required when purchasing packs or booster boxes",
            )

        pack_count = payload.quantity * (
            BOOSTER_BOX_PACK_COUNT if payload.product == StoreProduct.BOOSTER_BOX else 1
        )
        cards_granted, generated_cards, rng_seed = _generate_and_grant_packs(
            db, current_user.id, payload.set_number, pack_count,
        )

        transaction = DistributionTransaction(
            user_id=current_user.id,
            source="purchase",
            product=payload.product.value,
            set_number=payload.set_number,
            cards=[
                {"card_id": c["card_id"], "rarity": c["rarity"], "is_foil": c["is_foil"], "quantity": 1}
                for c in generated_cards
            ],
            rng_seed=rng_seed,
            tolkien_delta=-total_price,
        )
        db.add(transaction)
        db.flush()
        transaction_id = transaction.id

    elif payload.product == StoreProduct.STARTER_DECK:
        if payload.set_number is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="set_number is required when purchasing a starter deck",
            )

        tx_cards_all: List[Dict[str, Any]] = []
        for _ in range(payload.quantity):
            deck_cards_granted, _deck_name, tx_cards = _grant_starter_deck_cards(
                db, current_user.id, payload.set_number,
            )
            cards_granted.extend(deck_cards_granted)
            tx_cards_all.extend(tx_cards)

        transaction = DistributionTransaction(
            user_id=current_user.id,
            source="purchase",
            product=payload.product.value,
            set_number=payload.set_number,
            cards=tx_cards_all,
            rng_seed=None,
            tolkien_delta=-total_price,
        )
        db.add(transaction)
        db.flush()
        transaction_id = transaction.id

    balance_before = current_user.tolkien_balance
    current_user.tolkien_balance -= total_price
    db.commit()
    db.refresh(current_user)

    return StorePurchaseResponse(
        user_id=current_user.id,
        product=payload.product,
        quantity=payload.quantity,
        unit_price_tolkiens=unit_price,
        total_price_tolkiens=total_price,
        balance_before=balance_before,
        balance_after=current_user.tolkien_balance,
        cards_granted=cards_granted,
        transaction_id=transaction_id,
    )


@router.post("/store/sell-back", response_model=StoreSellBackResponse)
async def sell_back_card(
    payload: StoreSellBackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sell owned card copies back to the store for Tolkien (LOT-025 sell-back
    pathway): always 50% of the card's normalized purchase-equivalent value,
    per `booster_engine.compute_sell_back_value_tolkiens`."""
    ownership = db.query(Ownership).filter(
        Ownership.user_id == current_user.id,
        Ownership.card_id == payload.card_id,
        Ownership.is_foil == payload.is_foil,
    ).first()
    if not ownership or ownership.quantity < payload.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not enough copies owned to sell back",
        )

    card = db.query(Card).filter(Card.id == payload.card_id).first()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")

    unit_value = booster_engine.compute_sell_back_value_tolkiens(
        card.rarity, STORE_PRODUCT_PRICES_TOLKIENS["pack"]
    )
    total_value = unit_value * payload.quantity

    ownership.quantity -= payload.quantity
    if ownership.quantity <= 0:
        db.delete(ownership)

    balance_before = current_user.tolkien_balance
    current_user.tolkien_balance += total_value

    transaction = DistributionTransaction(
        user_id=current_user.id,
        source="sell_back",
        product=None,
        set_number=card.set_number,
        cards=[{
            "card_id": card.id,
            "rarity": card.rarity,
            "is_foil": payload.is_foil,
            "quantity": -payload.quantity,
        }],
        rng_seed=None,
        tolkien_delta=total_value,
    )
    db.add(transaction)
    db.flush()
    transaction_id = transaction.id

    db.commit()
    db.refresh(current_user)

    return StoreSellBackResponse(
        user_id=current_user.id,
        card_id=card.id,
        quantity=payload.quantity,
        is_foil=payload.is_foil,
        unit_value_tolkiens=unit_value,
        total_value_tolkiens=total_value,
        balance_before=balance_before,
        balance_after=current_user.tolkien_balance,
        transaction_id=transaction_id,
    )


@router.get("/admin/economy/summary", response_model=EconomySummaryResponse)
async def admin_economy_summary(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Current-totals economy/circulation telemetry (LOT-021 baseline).

    Covers: card circulation (owned quantities by card, split foil/non-foil),
    Tolkien flow totals by distribution source, sell-back volume/value by
    rarity, and weekly active-user reward roll stats. Also lazily captures
    an `EconomySnapshot` for historical trend telemetry (at most once per
    calendar day) -- see `GET /admin/economy/trends` for drift alerting.
    """
    # --- Circulation: current owned quantities per card, split foil/non-foil.
    circulation_rows = (
        db.query(
            Card.id, Card.name, Card.set_number, Card.rarity,
            Ownership.is_foil, func.sum(Ownership.quantity),
        )
        .join(Ownership, Ownership.card_id == Card.id)
        .filter(Ownership.is_active.is_(True))
        .group_by(Card.id, Card.name, Card.set_number, Card.rarity, Ownership.is_foil)
        .all()
    )
    circulation_by_card: Dict[str, CirculationEntry] = {}
    for card_id, name, set_number, rarity, is_foil, total_qty in circulation_rows:
        entry = circulation_by_card.setdefault(card_id, CirculationEntry(
            card_id=card_id, name=name, set_number=set_number, rarity=rarity,
            non_foil_quantity=0, foil_quantity=0,
        ))
        if is_foil:
            entry.foil_quantity += int(total_qty)
        else:
            entry.non_foil_quantity += int(total_qty)

    # --- Distribution audit trail: Tolkien flow totals grouped by source, and
    # foil-issuance/sell-back breakdowns by rarity. `cards` is a JSON column
    # (SQLite), so per-card-delta aggregation is done in Python rather than
    # in SQL -- fine at this dataset size; revisit if the audit table grows
    # large enough for this to matter (noted in LOT-100).
    source_totals: Dict[str, Dict[str, int]] = {}
    foil_issuance_by_rarity: Dict[str, int] = {}
    sell_back_by_rarity: Dict[str, Dict[str, int]] = {}
    for source, product, cards_json, tolkien_delta in db.query(
        DistributionTransaction.source,
        DistributionTransaction.product,
        DistributionTransaction.cards,
        DistributionTransaction.tolkien_delta,
    ):
        totals = source_totals.setdefault(source, {"transaction_count": 0, "total_tolkien_delta": 0})
        totals["transaction_count"] += 1
        totals["total_tolkien_delta"] += tolkien_delta

        for delta in cards_json or []:
            rarity = delta.get("rarity")
            quantity = delta.get("quantity", 0)
            if source == "sell_back":
                # Sell-back transactions are single-card today, so it's safe
                # to attribute the whole transaction's tolkien_delta to this
                # delta's rarity.
                band = sell_back_by_rarity.setdefault(rarity, {"cards_sold": 0, "total_tolkien_returned": 0})
                band["cards_sold"] += -quantity  # sell-back deltas are negative
                band["total_tolkien_returned"] += tolkien_delta
            elif delta.get("is_foil") and quantity > 0:
                foil_issuance_by_rarity[rarity] = foil_issuance_by_rarity.get(rarity, 0) + quantity

    # --- Weekly reward roll stats (proxy for weekly-active-user telemetry):
    # every roll row (win or loss) is only ever created via a successful
    # login, so distinct_users_rolled approximates weekly-active users.
    total_rolls = 0
    total_wins = 0
    distinct_users_rolled: set = set()
    wins_by_rarity: Dict[str, int] = {}
    for user_id, won, rarity in db.query(
        WeeklyRewardRoll.user_id, WeeklyRewardRoll.won, WeeklyRewardRoll.rarity,
    ):
        total_rolls += 1
        distinct_users_rolled.add(user_id)
        if won:
            total_wins += 1
            if rarity:
                wins_by_rarity[rarity] = wins_by_rarity.get(rarity, 0) + 1
    total_losses = total_rolls - total_wins
    win_rate = (total_wins / total_rolls) if total_rolls else 0.0

    summary = EconomySummaryResponse(
        circulation=list(circulation_by_card.values()),
        foil_issuance_by_rarity=foil_issuance_by_rarity,
        distribution_by_source=[
            DistributionSourceTotals(source=source, **totals)
            for source, totals in source_totals.items()
        ],
        sell_back_by_rarity=[
            SellBackRarityTotals(rarity=rarity, **totals)
            for rarity, totals in sell_back_by_rarity.items()
        ],
        weekly_reward_stats=WeeklyRewardStats(
            total_rolls=total_rolls,
            total_wins=total_wins,
            total_losses=total_losses,
            win_rate=win_rate,
            distinct_users_rolled=len(distinct_users_rolled),
            wins_by_rarity=wins_by_rarity,
        ),
    )
    _maybe_capture_economy_snapshot(summary, db)
    return summary


# LOT-021/LOT-100: simple percentage-drift threshold for flagging historical
# economy snapshots -- no bespoke alerting config exists yet, this is
# deliberately a single tunable constant rather than a full rules engine.
ECONOMY_SNAPSHOT_DRIFT_ALERT_THRESHOLD_PCT = 25.0


def _maybe_capture_economy_snapshot(summary: EconomySummaryResponse, db: Session) -> None:
    """Capture at most one `EconomySnapshot` per calendar day (LOT-021
    historical trend telemetry). Lazily triggered from
    `GET /admin/economy/summary` -- see `EconomySnapshot` for why this repo
    uses lazy capture instead of a background scheduler.
    """
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    already_captured_today = (
        db.query(EconomySnapshot)
        .filter(EconomySnapshot.captured_at >= today_start)
        .first()
    )
    if already_captured_today:
        return

    total_cards_in_circulation = sum(
        entry.non_foil_quantity + entry.foil_quantity for entry in summary.circulation
    )
    total_tolkien_net_flow = sum(s.total_tolkien_delta for s in summary.distribution_by_source)

    snapshot = EconomySnapshot(
        total_cards_in_circulation=total_cards_in_circulation,
        total_foil_issued=sum(summary.foil_issuance_by_rarity.values()),
        total_tolkien_net_flow=total_tolkien_net_flow,
        total_sell_back_cards=sum(s.cards_sold for s in summary.sell_back_by_rarity),
        total_sell_back_tolkien_returned=sum(s.total_tolkien_returned for s in summary.sell_back_by_rarity),
        weekly_reward_total_rolls=summary.weekly_reward_stats.total_rolls,
        weekly_reward_total_wins=summary.weekly_reward_stats.total_wins,
        weekly_reward_distinct_users=summary.weekly_reward_stats.distinct_users_rolled,
        raw_summary=summary.model_dump(mode="json"),
    )
    db.add(snapshot)
    db.commit()


@router.get("/admin/economy/trends", response_model=EconomyTrendsResponse)
async def admin_economy_trends(
    limit: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Historical economy snapshots (LOT-021/LOT-100), oldest-first, with
    simple threshold/drift alerts flagged between consecutive snapshots.
    Snapshots are captured lazily by `GET /admin/economy/summary` (at most
    once per calendar day) -- there is no background scheduler in this repo.
    """
    total = db.query(EconomySnapshot).count()
    rows = (
        db.query(EconomySnapshot)
        .order_by(EconomySnapshot.captured_at.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()  # oldest first

    trend_fields = [
        ("total_cards_in_circulation", "cards in circulation"),
        ("total_foil_issued", "foil cards issued"),
        ("total_tolkien_net_flow", "Tolkien net flow"),
        ("weekly_reward_distinct_users", "weekly-active users"),
    ]
    items: List[EconomySnapshotSummary] = []
    previous: Optional[EconomySnapshot] = None
    for row in rows:
        alerts: List[str] = []
        if previous is not None:
            for field_name, label in trend_fields:
                old_value = getattr(previous, field_name)
                new_value = getattr(row, field_name)
                if old_value == 0:
                    continue  # no baseline to compute a meaningful percentage drift from
                pct_change = ((new_value - old_value) / abs(old_value)) * 100
                if abs(pct_change) >= ECONOMY_SNAPSHOT_DRIFT_ALERT_THRESHOLD_PCT:
                    direction = "up" if pct_change > 0 else "down"
                    alerts.append(f"{label} {direction} {abs(pct_change):.0f}% since previous snapshot")
        items.append(EconomySnapshotSummary(
            id=row.id, captured_at=row.captured_at,
            total_cards_in_circulation=row.total_cards_in_circulation,
            total_foil_issued=row.total_foil_issued,
            total_tolkien_net_flow=row.total_tolkien_net_flow,
            total_sell_back_cards=row.total_sell_back_cards,
            total_sell_back_tolkien_returned=row.total_sell_back_tolkien_returned,
            weekly_reward_total_rolls=row.weekly_reward_total_rolls,
            weekly_reward_total_wins=row.weekly_reward_total_wins,
            weekly_reward_distinct_users=row.weekly_reward_distinct_users,
            alerts=alerts,
        ))
        previous = row

    return EconomyTrendsResponse(items=items, total=total)


# LOT-019: only pack/booster_box can currently be redeemed server-side (they
# reuse the booster generation engine). starter_deck needs a curated,
# fixed-per-set decklist and promo_card needs a promo-card catalog concept --
# neither exists yet, so gifting those raises a clear 400 for now (tracked
# as a LOT-100 backlog item) rather than silently doing nothing.
GIFT_REDEEMABLE_PRODUCTS = {StoreProduct.PACK.value, StoreProduct.BOOSTER_BOX.value}


@router.post("/admin/gifts", response_model=GiftSummary, status_code=status.HTTP_201_CREATED)
async def admin_create_gift(
    payload: AdminGiftCreateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """Admin-issue a gift to a user (LOT-019). Gifts are immediately usable
    (status starts 'granted' -- this slice has no draft/scheduled-send
    workflow, so 'created' as a distinct persisted step isn't used yet)."""
    recipient = db.query(User).filter(User.id == payload.recipient_id).first()
    if not recipient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient user not found")

    if payload.product in (StoreProduct.PACK, StoreProduct.BOOSTER_BOX) and payload.set_number is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="set_number is required when gifting packs or booster boxes",
        )

    gift = Gift(
        sender_id=admin_user.id,
        recipient_id=payload.recipient_id,
        product=payload.product.value,
        quantity=payload.quantity,
        set_number=payload.set_number,
        status="granted",
        note=payload.note,
        expires_at=payload.expires_at,
        created_at=datetime.utcnow(),
    )
    db.add(gift)
    db.commit()
    db.refresh(gift)
    return GiftSummary.model_validate(gift)


@router.get("/gifts", response_model=GiftListResponse)
async def list_my_gifts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the current user's gift ledger entries (any status)."""
    gifts = (
        db.query(Gift)
        .filter(Gift.recipient_id == current_user.id)
        .order_by(Gift.created_at.desc())
        .all()
    )
    return GiftListResponse(items=[GiftSummary.model_validate(g) for g in gifts])


@router.post("/gifts/{gift_id}/redeem", response_model=GiftRedeemResponse)
async def redeem_gift(
    gift_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Redeem a gift addressed to the current user (LOT-019).

    Uses an atomic conditional UPDATE (`WHERE id=... AND status='granted'`)
    to guard the state transition: this is idempotent and safe under
    concurrent redeem requests for the same gift without needing dialect-
    specific row locking (works identically on SQLite and Postgres) -- if
    zero rows are updated, someone else already redeemed/revoked it (or it
    was never granted), and we report that instead of double-granting cards.
    """
    gift = db.query(Gift).filter(Gift.id == gift_id, Gift.recipient_id == current_user.id).first()
    if not gift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gift not found")

    if gift.product not in GIFT_REDEEMABLE_PRODUCTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Gifted product '{gift.product}' cannot be redeemed yet (tracked as LOT-100 follow-up)",
        )

    now = datetime.utcnow()
    if gift.expires_at and gift.expires_at < now:
        db.query(Gift).filter(Gift.id == gift_id, Gift.status == "granted").update(
            {"status": "expired"}, synchronize_session=False
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gift has expired")

    updated_rows = (
        db.query(Gift)
        .filter(Gift.id == gift_id, Gift.status == "granted")
        .update({"status": "redeemed", "redeemed_at": now}, synchronize_session=False)
    )
    if updated_rows == 0:
        db.commit()
        db.refresh(gift)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Gift is not available to redeem (current status: {gift.status})",
        )

    pack_count = gift.quantity * (
        BOOSTER_BOX_PACK_COUNT if gift.product == StoreProduct.BOOSTER_BOX.value else 1
    )
    cards_granted, generated_cards, rng_seed = _generate_and_grant_packs(
        db, current_user.id, gift.set_number, pack_count, ownership_source="reward",
    )

    transaction = DistributionTransaction(
        user_id=current_user.id,
        source="gift",
        product=gift.product,
        set_number=gift.set_number,
        cards=[
            {"card_id": c["card_id"], "rarity": c["rarity"], "is_foil": c["is_foil"], "quantity": 1}
            for c in generated_cards
        ],
        rng_seed=rng_seed,
        tolkien_delta=0,
    )
    db.add(transaction)
    db.flush()

    db.query(Gift).filter(Gift.id == gift_id).update(
        {"transaction_id": transaction.id}, synchronize_session=False
    )
    db.commit()
    db.refresh(gift)

    return GiftRedeemResponse(gift=GiftSummary.model_validate(gift), cards_granted=cards_granted)


@router.post("/admin/gifts/{gift_id}/revoke", response_model=GiftSummary)
async def admin_revoke_gift(
    gift_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Revoke a not-yet-redeemed gift (LOT-019)."""
    gift = db.query(Gift).filter(Gift.id == gift_id).first()
    if not gift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gift not found")

    updated_rows = (
        db.query(Gift)
        .filter(Gift.id == gift_id, Gift.status.in_(["created", "granted"]))
        .update({"status": "revoked", "revoked_at": datetime.utcnow()}, synchronize_session=False)
    )
    if updated_rows == 0:
        db.commit()
        db.refresh(gift)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Gift cannot be revoked (current status: {gift.status})",
        )

    db.commit()
    db.refresh(gift)
    return GiftSummary.model_validate(gift)


# ============== ENTITLEMENT ROUTES (LOT-018 / LOT-025) ==============

@router.get("/entitlements", response_model=EntitlementListResponse)
async def list_my_entitlements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the current user's entitlement ledger entries (any status)."""
    entitlements = (
        db.query(Entitlement)
        .filter(Entitlement.user_id == current_user.id)
        .order_by(Entitlement.granted_at.desc())
        .all()
    )
    return EntitlementListResponse(items=[EntitlementSummary.model_validate(e) for e in entitlements])


@router.get("/entitlements/starter-deck-options", response_model=StarterDeckOptionsResponse)
async def list_starter_deck_options(
    set_number: int = 1,
    current_user: User = Depends(get_current_user),
):
    """List the curated starter decks a player can choose from for a set
    (LOT-018 'starter_deck_choice' -- see game-mechanism-release-and-gifting.md),
    for use with the `deck_key` field of `POST /entitlements/{id}/claim`.
    """
    decks = STARTER_DECKS_BY_SET.get(set_number, {})
    return StarterDeckOptionsResponse(items=[
        StarterDeckOption(deck_key=key, name=deck["name"], card_count=sum(c["quantity"] for c in deck["cards"]))
        for key, deck in decks.items()
    ])


@router.post("/entitlements/{entitlement_id}/claim", response_model=EntitlementClaimResponse)
async def claim_entitlement(
    entitlement_id: str,
    payload: EntitlementClaimRequest = EntitlementClaimRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Claim a pending entitlement (LOT-018), generating and granting its
    actual cards at claim time -- mirrors `/gifts/{id}/redeem`'s atomic
    conditional-UPDATE pattern (see there for the concurrency rationale):
    the state transition (active -> consumed) is what guards against
    double-claiming, not an app-level lock.

    For `starter_deck` entitlements, `payload.deck_key` optionally selects
    which curated deck to grant (see GET /entitlements/starter-deck-options);
    if omitted, one is chosen at random. Ignored for `booster_pack` claims.
    """
    entitlement = db.query(Entitlement).filter(
        Entitlement.id == entitlement_id, Entitlement.user_id == current_user.id,
    ).first()
    if not entitlement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entitlement not found")

    updated_rows = (
        db.query(Entitlement)
        .filter(Entitlement.id == entitlement_id, Entitlement.status == "active")
        .update({"status": "consumed", "consumed_at": datetime.utcnow()}, synchronize_session=False)
    )
    if updated_rows == 0:
        db.commit()
        db.refresh(entitlement)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Entitlement is not available to claim (current status: {entitlement.status})",
        )

    deck_name: Optional[str] = None
    if entitlement.product_type == "booster_pack":
        cards_granted, generated_cards, rng_seed = _generate_and_grant_packs(
            db, current_user.id, entitlement.set_number, entitlement.quantity, ownership_source="reward",
        )
        tx_cards = [
            {"card_id": c["card_id"], "rarity": c["rarity"], "is_foil": c["is_foil"], "quantity": 1}
            for c in generated_cards
        ]
    else:  # starter_deck
        cards_granted, deck_name, tx_cards = _grant_starter_deck_cards(
            db, current_user.id, entitlement.set_number, deck_key=payload.deck_key,
        )

    transaction = DistributionTransaction(
        user_id=current_user.id,
        source="starter",
        product=entitlement.product_type,
        set_number=entitlement.set_number,
        cards=tx_cards,
        rng_seed=None,
        tolkien_delta=0,
    )
    db.add(transaction)
    db.flush()

    db.query(Entitlement).filter(Entitlement.id == entitlement_id).update(
        {"transaction_id": transaction.id}, synchronize_session=False
    )
    db.commit()
    db.refresh(entitlement)

    return EntitlementClaimResponse(
        entitlement=EntitlementSummary.model_validate(entitlement),
        cards_granted=cards_granted,
        deck_name=deck_name,
    )


@router.post("/purchases", response_model=PurchaseResponse)
async def create_purchase(
    purchase_data: PurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new purchase (mock implementation)."""
    # Validate items
    items = []
    subtotal = 0.0

    for item in purchase_data.items:
        card = db.query(Card).filter(Card.id == item.card_id).first()
        if not card:
            raise HTTPException(status_code=404, detail=f"Card {item.card_id} not found")

        item_total = card.cost * item.quantity
        subtotal += item_total

        items.append({
            "card_id": item.card_id,
            "card_name": card.name,
            "quantity": item.quantity,
            "unit_price": float(card.cost),
            "total_price": float(item_total)
        })

    # Calculate tax (10%)
    tax = subtotal * 0.10
    total = subtotal + tax

    # Create purchase
    purchase = Purchase(
        user_id=current_user.id,
        items=items,
        subtotal=float(subtotal),
        tax=float(tax),
        total=float(total),
        payment_method=purchase_data.payment_method,
        coupon_code=purchase_data.coupon_code,
        notes=purchase_data.notes
    )

    db.add(purchase)
    db.commit()
    db.refresh(purchase)

    return purchase


@router.get("/purchases", response_model=List[PurchaseResponse])
async def list_purchases(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List user's purchase history."""
    purchases = db.query(Purchase).filter(
        Purchase.user_id == current_user.id,
        Purchase.status == "completed"
    ).order_by(Purchase.created_at.desc()).all()
    return purchases


@router.post("/purchases/{purchase_id}/refund", response_model=RefundResponse)
async def request_refund(
    purchase_id: str,
    refund_data: RefundRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Request a refund."""
    purchase = db.query(Purchase).filter(
        Purchase.id == purchase_id,
        Purchase.user_id == current_user.id
    ).first()

    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")

    if purchase.status != "completed":
        raise HTTPException(status_code=400, detail="Only completed purchases can be refunded")

    # Create refund (mock)
    refund = Refund(
        purchase_id=purchase_id,
        amount=refund_data.partial_amount or purchase.total,
        reason=refund_data.reason
    )

    db.add(refund)
    db.commit()
    db.refresh(refund)

    return refund


# ============== MATCH ROUTES ==============

@router.post("/matches", response_model=MatchResponse)
async def create_match(
    match_data: MatchCreate,
    db: Session = Depends(get_db)
):
    """Create a new match lobby."""
    match_code = secrets.token_urlsafe(6)[:8].upper()

    match = Match(
        code=match_code,
        mode=match_data.mode,
        max_players=match_data.max_players,
        card_limit=match_data.card_limit,
        rules_override=match_data.rules_override
    )

    db.add(match)
    db.commit()
    db.refresh(match)

    return match


@router.get("/matches/{match_id}", response_model=MatchResponse)
async def get_match(match_id: str, db: Session = Depends(get_db)):
    """Get match details."""
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return match


@router.get("/matches/{match_id}/players", response_model=MatchPlayerList)
async def get_match_players(match_id: str, db: Session = Depends(get_db)):
    """Get players in a match."""
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    players = db.query(MatchPlayer).filter(MatchPlayer.match_id == match_id).all()

    return MatchPlayerList(
        match_id=match_id,
        players=[MatchPlayerList.model_validate(player) for player in players],
        max_players=match.max_players
    )


@router.post("/matches/{match_id}/join")
async def join_match(
    match_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Join a match."""
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    if match.status != "waiting":
        raise HTTPException(status_code=400, detail="Match is not in waiting state")

    if match.current_players >= match.max_players:
        raise HTTPException(status_code=400, detail="Match is full")

    # Check if user already joined
    existing = db.query(MatchPlayer).filter(
        MatchPlayer.match_id == match_id,
        MatchPlayer.player_id == current_user.id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Already in this match")

    # Add player
    player = MatchPlayer(
        match_id=match_id,
        player_id=current_user.id,
        username=current_user.username
    )

    db.add(player)
    match.current_players += 1
    db.commit()

    return {"message": "Joined match successfully"}


# ============== AUDIT ROUTES ==============

@router.get("/matches/{match_id}/audit", response_model=AuditReport)
async def get_match_audit(
    match_id: str,
    db: Session = Depends(get_db)
):
    """Get audit report for a match."""
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    # Get recent anomalies
    anomalies = db.query(MatchAuditLog).filter(
        MatchAuditLog.match_id == match_id
    ).order_by(MatchAuditLog.detected_at.desc()).limit(10).all()

    # Calculate integrity score (mock)
    total_checks = 100
    anomalies_found = len(anomalies)
    integrity_score = max(0, 100 - (anomalies_found * 10))

    return AuditReport(
        match_id=match_id,
        total_checks=total_checks,
        anomalies_found=anomalies_found,
        integrity_score=integrity_score,
        last_checked=datetime.utcnow(),
        recent_anomalies=[MatchAuditLog.model_validate(audit) for audit in anomalies]
    )


# ============== HEALTH CHECK ==============

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


# ============== ADMIN ROUTES (Protected) ==============

@router.get("/admin/cards/stats")
async def get_card_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Get card statistics (admin only)."""
    total_cards = db.query(Card).count()
    total_ownerships = db.query(Ownership).count()
    total_purchases = db.query(Purchase).count()

    return {
        "total_cards": total_cards,
        "total_ownerships": total_ownerships,
        "total_purchases": total_purchases
    }


@router.get("/admin/users", response_model=AdminUserListResponse)
async def admin_list_users(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Admin list/search of user accounts."""
    query = db.query(User)
    if search:
        query = query.filter(
            or_(
                User.email.ilike(f"%{search}%"),
                User.username.ilike(f"%{search}%"),
            )
        )

    total = query.count()
    users = query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return AdminUserListResponse(
        items=[AdminUserSummary.model_validate(u) for u in users],
        total=total,
    )


@router.post("/admin/users/{user_id}/tolkiens", response_model=AdminUserSummary)
async def admin_adjust_user_tolkien_balance(
    user_id: str,
    payload: AdminTolkienAdjustRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Add/remove Tolkien currency from a user account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    new_balance = user.tolkien_balance + payload.amount
    if new_balance < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Operation would produce negative balance ({new_balance})",
        )

    user.tolkien_balance = new_balance
    db.commit()
    db.refresh(user)
    return AdminUserSummary.model_validate(user)


@router.put("/admin/users/{user_id}/moderator", response_model=AdminUserSummary)
async def admin_toggle_user_moderator(
    user_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Grant or revoke moderator (in-game admin) status for a user.

    Moderator accounts have elevated in-game privileges but cannot access
    the admin panel and cannot modify other accounts.
    Panel admins (is_admin=True) are unaffected by this toggle.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Panel admins cannot be demoted via this endpoint — they are managed separately
    if user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change moderator status of a panel admin account",
        )

    user.is_moderator = not user.is_moderator
    db.commit()
    db.refresh(user)
    return AdminUserSummary.model_validate(user)


@router.delete("/admin/users/{user_id}")
async def admin_delete_user(
    user_id: str,
    payload: AdminUserDeleteRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Delete a user with triple-verification safeguards."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.confirm_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User ID confirmation failed")
    if payload.confirm_username != user.username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username confirmation failed")
    if str(payload.confirm_email).lower() != user.email.lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email confirmation failed")

    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully", "deleted_user_id": user_id}


@router.post("/admin/users/{user_id}/reset", response_model=AdminUserSummary)
async def admin_reset_user(
    user_id: str,
    payload: AdminUserDeleteRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Wipe a user's collection, decks, and pending entitlements and
    re-grant the same bootstrap bundle a brand-new account receives, while
    keeping their login (email/username/password) intact.

    Uses the same triple-confirmation payload as delete since it's just as
    destructive to game progress.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.confirm_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User ID confirmation failed")
    if payload.confirm_username != user.username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username confirmation failed")
    if str(payload.confirm_email).lower() != user.email.lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email confirmation failed")

    # Entitlements reference distribution_transactions by id, so clear them first.
    db.query(Entitlement).filter(Entitlement.user_id == user_id).delete(synchronize_session=False)
    db.query(Ownership).filter(Ownership.user_id == user_id).delete(synchronize_session=False)
    # Deleted one at a time (not a bulk query.delete()) so the ORM cascade
    # ("all, delete-orphan" on Deck.cards) removes each deck's DeckCard rows.
    for deck in db.query(Deck).filter(Deck.user_id == user_id).all():
        db.delete(deck)

    user.tolkien_balance = 0
    db.commit()

    _grant_new_user_entitlements(user, db)
    db.refresh(user)
    return AdminUserSummary.model_validate(user)


# ============== ADMIN: SET RELEASES (LOT-025) ==============

@router.get("/admin/set-releases", response_model=SetReleaseListResponse)
async def admin_list_set_releases(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Admin list of every set with its current release/availability status."""
    sets = db.query(SetRelease).order_by(SetRelease.set_number).all()
    return SetReleaseListResponse(items=[SetReleaseSummary.model_validate(s) for s in sets])


@router.post("/admin/set-releases/{set_number}/activate", response_model=SetReleaseSummary)
async def admin_activate_set_release(
    set_number: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Activate a set, making it available in the storefront/deck builder."""
    set_release = db.query(SetRelease).filter(SetRelease.set_number == set_number).first()
    if not set_release:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Set not found")

    if not set_release.is_active:
        set_release.is_active = True
        set_release.activated_at = datetime.utcnow()
        db.commit()
        db.refresh(set_release)
        # LOT-018: grant every eligible user a release bundle for this set
        # (1 starter deck + 5 booster packs), idempotent per user per set.
        _grant_release_bundle_to_all_users(set_number, db)
        # LOT-022: link this activation to a live release event record.
        _ensure_live_release_event(set_number, db)
    return SetReleaseSummary.model_validate(set_release)


@router.post("/admin/set-releases/{set_number}/deactivate", response_model=SetReleaseSummary)
async def admin_deactivate_set_release(
    set_number: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Deactivate a set. Fellowship (Set 1) can never be deactivated."""
    if _is_protected_set(set_number):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This set is permanently active and cannot be deactivated",
        )

    set_release = db.query(SetRelease).filter(SetRelease.set_number == set_number).first()
    if not set_release:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Set not found")

    if set_release.is_active:
        set_release.is_active = False
        db.commit()
        # LOT-018/LOT-025 bugfix: revoke any still-unclaimed entitlements
        # for this set so players aren't left with permanently-stuck
        # "active" grants referencing content that's no longer available
        # (e.g. starter-deck-options legitimately has nothing to offer for
        # a set with no curated decks built, and booster claims would
        # 400 since the set is no longer active -- both previously
        # produced confusing/silent client-side failures). Using status
        # 'revoked' (not a hard delete) preserves
        # `_grant_release_bundle_to_all_users`'s "already granted" check,
        # so a later reactivation still won't double-grant.
        db.query(Entitlement).filter(
            Entitlement.set_number == set_number,
            Entitlement.status == "active",
        ).update(
            {
                "status": "revoked",
                "revoked_at": datetime.utcnow(),
                "revocation_reason": "Set was deactivated before this entitlement was claimed",
            },
            synchronize_session=False,
        )
        db.commit()
        db.refresh(set_release)
    return SetReleaseSummary.model_validate(set_release)


# ============== RELEASE EVENTS (LOT-022 / LOT-025) ==============

@router.post("/admin/events", response_model=ReleaseEventSummary, status_code=status.HTTP_201_CREATED)
async def admin_create_release_event(
    payload: ReleaseEventCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Admin creates a release event for a set (starts in `scheduled` status)."""
    event = ReleaseEvent(
        set_number=payload.set_number,
        title=payload.title,
        description=payload.description,
        reward_policy=payload.reward_policy,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return ReleaseEventSummary.model_validate(event)


@router.get("/admin/events", response_model=ReleaseEventListResponse)
async def admin_list_release_events(
    set_number: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Admin list of release events, optionally filtered by set_number."""
    query = db.query(ReleaseEvent)
    if set_number is not None:
        query = query.filter(ReleaseEvent.set_number == set_number)
    events = query.order_by(ReleaseEvent.created_at.desc()).all()
    return ReleaseEventListResponse(items=[ReleaseEventSummary.model_validate(e) for e in events])


@router.post("/admin/events/{event_id}/activate", response_model=ReleaseEventSummary)
async def admin_activate_release_event(
    event_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Transition a release event to `live` (idempotent no-op if already live)."""
    event = db.query(ReleaseEvent).filter(ReleaseEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    if event.status != 'live':
        event.status = 'live'
        event.starts_at = event.starts_at or datetime.utcnow()
        event.closed_at = None
        db.commit()
        db.refresh(event)
    return ReleaseEventSummary.model_validate(event)


@router.post("/admin/events/{event_id}/close", response_model=ReleaseEventSummary)
async def admin_close_release_event(
    event_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Transition a release event to `closed` (idempotent no-op if already closed)."""
    event = db.query(ReleaseEvent).filter(ReleaseEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    if event.status != 'closed':
        event.status = 'closed'
        event.closed_at = datetime.utcnow()
        db.commit()
        db.refresh(event)
    return ReleaseEventSummary.model_validate(event)


@router.get("/admin/events/{event_id}/participants", response_model=EventParticipationListResponse)
async def admin_list_event_participants(
    event_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Admin-queryable, auditable list of participation records for an event."""
    event = db.query(ReleaseEvent).filter(ReleaseEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    participants = (
        db.query(EventParticipation)
        .filter(EventParticipation.event_id == event_id)
        .order_by(EventParticipation.joined_at)
        .all()
    )
    return EventParticipationListResponse(
        items=[EventParticipationSummary.model_validate(p) for p in participants]
    )


@router.get("/events", response_model=ReleaseEventListResponse)
async def list_release_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Public list of release events (any status) for the storefront/events UI."""
    events = db.query(ReleaseEvent).order_by(ReleaseEvent.created_at.desc()).all()
    return ReleaseEventListResponse(items=[ReleaseEventSummary.model_validate(e) for e in events])


@router.post("/events/{event_id}/join", response_model=EventParticipationSummary)
async def join_release_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """User joins a live release event. Idempotent -- rejoining returns the
    existing participation record rather than erroring or duplicating."""
    event = db.query(ReleaseEvent).filter(ReleaseEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    if event.status != 'live':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Event is not currently live")

    existing = (
        db.query(EventParticipation)
        .filter(EventParticipation.event_id == event_id, EventParticipation.user_id == current_user.id)
        .first()
    )
    if existing:
        return EventParticipationSummary.model_validate(existing)

    participation = EventParticipation(event_id=event_id, user_id=current_user.id)
    db.add(participation)
    try:
        db.commit()
    except IntegrityError:
        # Concurrent join race lost the unique-index race; fetch the winner's row.
        db.rollback()
        existing = (
            db.query(EventParticipation)
            .filter(EventParticipation.event_id == event_id, EventParticipation.user_id == current_user.id)
            .first()
        )
        return EventParticipationSummary.model_validate(existing)
    db.refresh(participation)
    return EventParticipationSummary.model_validate(participation)


# ============== DECK ROUTES ==============

def _deck_response(deck: Deck) -> DeckResponse:
    """Build a DeckResponse from an ORM Deck, computing total_cards."""
    entries = []
    total = 0
    for dc in deck.cards:
        card = dc.card
        card_resp = None
        if card:
            card_resp = CardResponse(
                id=card.id, name=card.name, cost=card.cost,
                rarity=card.rarity, description=card.description,
                stats=card.attributes, image_url=card.image_url,
                created_at=card.created_at, updated_at=card.updated_at,
            )
        entries.append(DeckCardEntry(card_id=dc.card_id, quantity=dc.quantity, card=card_resp))
        total += dc.quantity
    return DeckResponse(
        id=deck.id, user_id=deck.user_id, name=deck.name,
        format=deck.format, description=deck.description,
        created_at=deck.created_at, updated_at=deck.updated_at,
        cards=entries, total_cards=total,
    )


@router.post("/decks", response_model=DeckResponse, status_code=status.HTTP_201_CREATED)
async def create_deck(
    deck_data: DeckCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new deck for the current user."""
    existing_count = db.query(Deck).filter(Deck.user_id == current_user.id).count()
    if existing_count >= MAX_DECKS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Deck limit reached: a maximum of {MAX_DECKS_PER_USER} decks per user is allowed",
        )
    existing = db.query(Deck).filter(
        Deck.user_id == current_user.id,
        Deck.name == deck_data.name,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Deck named '{deck_data.name}' already exists",
        )
    deck = Deck(
        id=str(uuid4()),
        user_id=current_user.id,
        name=deck_data.name,
        format=deck_data.format.value,
        description=deck_data.description,
    )
    db.add(deck)
    db.commit()
    db.refresh(deck)
    return _deck_response(deck)


@router.get("/decks", response_model=DeckListResponse)
async def list_decks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all decks belonging to the current user."""
    decks = db.query(Deck).filter(Deck.user_id == current_user.id).all()
    return DeckListResponse(items=[_deck_response(d) for d in decks], total=len(decks))


@router.get("/decks/legal-cards", response_model=CardListResponse)
async def get_legal_cards(
    format: DeckFormat = Query(DeckFormat.OPEN, description="Ruleset format"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List cards the current user owns that are legal in the specified
    format (LOT-014): a card is legal if its scraped `formats` attribute
    includes `format` (or has no `formats` data at all) and it isn't on
    that format's X-List (see deck_legality.is_format_legal)."""
    owned_card_ids = [
        o.card_id for o in db.query(Ownership).filter(
            Ownership.user_id == current_user.id, Ownership.is_active == True
        ).all()
    ]
    all_owned_cards = db.query(Card).filter(
        Card.id.in_(owned_card_ids), Card.is_active == True
    ).all()
    legal_cards = [c for c in all_owned_cards if deck_legality.is_format_legal(c, format.value)]
    total = len(legal_cards)
    offset = (page - 1) * page_size
    cards = legal_cards[offset:offset + page_size]
    return CardListResponse(
        items=[
            CardResponse(
                id=c.id, name=c.name, cost=c.cost, rarity=c.rarity,
                description=c.description, stats=c.attributes,
                image_url=c.image_url, created_at=c.created_at, updated_at=c.updated_at,
            )
            for c in cards
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/decks/{deck_id}", response_model=DeckResponse)
async def get_deck(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific deck with all its cards."""
    deck = db.query(Deck).filter(Deck.id == deck_id, Deck.user_id == current_user.id).first()
    if not deck:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return _deck_response(deck)


@router.put("/decks/{deck_id}", response_model=DeckResponse)
async def update_deck(
    deck_id: str,
    deck_data: DeckUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Rename or change format of a deck."""
    deck = db.query(Deck).filter(Deck.id == deck_id, Deck.user_id == current_user.id).first()
    if not deck:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    if deck_data.name is not None:
        conflict = db.query(Deck).filter(
            Deck.user_id == current_user.id,
            Deck.name == deck_data.name,
            Deck.id != deck_id,
        ).first()
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Another deck named '{deck_data.name}' already exists",
            )
        deck.name = deck_data.name
    if deck_data.format is not None:
        deck.format = deck_data.format.value
    if deck_data.description is not None:
        deck.description = deck_data.description
    db.commit()
    db.refresh(deck)
    return _deck_response(deck)


@router.delete("/decks/{deck_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deck(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a deck and return all its cards to the user's collection."""
    deck = db.query(Deck).filter(Deck.id == deck_id, Deck.user_id == current_user.id).first()
    if not deck:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    # Cards re-enter collection automatically since Ownership records are untouched;
    # deck_cards are removed via cascade.
    db.delete(deck)
    db.commit()


@router.post("/decks/{deck_id}/cards", response_model=DeckResponse)
async def add_card_to_deck(
    deck_id: str,
    body: DeckCardAdd,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a card the user owns to a deck."""
    deck = db.query(Deck).filter(Deck.id == deck_id, Deck.user_id == current_user.id).first()
    if not deck:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")

    # Verify user owns the card
    ownership = db.query(Ownership).filter(
        Ownership.user_id == current_user.id,
        Ownership.card_id == body.card_id,
        Ownership.is_active == True,
    ).first()
    if not ownership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Card not in your collection",
        )

    # Enforce quantity constraint: sum of copies assigned across ALL user's decks
    # must not exceed the number of copies the user owns.
    already_assigned = db.query(
        func.coalesce(func.sum(DeckCard.quantity), 0)
    ).join(Deck, DeckCard.deck_id == Deck.id).filter(
        Deck.user_id == current_user.id,
        DeckCard.card_id == body.card_id,
    ).scalar() or 0

    available = ownership.quantity - already_assigned
    if body.quantity > available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Not enough unassigned copies. "
                f"Owned: {ownership.quantity}, already in decks: {already_assigned}, "
                f"requested: {body.quantity}"
            ),
        )

    # Check format legality (basic check — extend with attribute filtering as needed)
    card = db.query(Card).filter(Card.id == body.card_id, Card.is_active == True).first()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")

    # Enforce deck-construction copy limits (LOT-014): max 4 copies of a card
    # title (ignoring subtitle), max 1 copy of a given site.
    try:
        deck_legality.check_copy_limit(deck.cards, card, body.quantity)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Enforce format/X-List legality (LOT-014): reject cards that aren't
    # legal (or are explicitly excluded) in this deck's declared format.
    try:
        deck_legality.check_format_legality(card, deck.format)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    existing_slot = db.query(DeckCard).filter(
        DeckCard.deck_id == deck_id, DeckCard.card_id == body.card_id
    ).first()
    if existing_slot:
        existing_slot.quantity += body.quantity
    else:
        db.add(DeckCard(id=str(uuid4()), deck_id=deck_id, card_id=body.card_id, quantity=body.quantity))
    db.commit()
    db.refresh(deck)
    return _deck_response(deck)


@router.delete("/decks/{deck_id}/cards/{card_id}", response_model=DeckResponse)
async def remove_card_from_deck(
    deck_id: str,
    card_id: str,
    quantity: Optional[int] = Query(None, ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a card (or reduce quantity) from a deck."""
    deck = db.query(Deck).filter(Deck.id == deck_id, Deck.user_id == current_user.id).first()
    if not deck:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    slot = db.query(DeckCard).filter(DeckCard.deck_id == deck_id, DeckCard.card_id == card_id).first()
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not in deck")
    if quantity is None or quantity >= slot.quantity:
        db.delete(slot)
    else:
        slot.quantity -= quantity
    db.commit()
    db.refresh(deck)
    return _deck_response(deck)


@router.get("/decks/{deck_id}/legality", response_model=DeckLegalityResponse)
async def get_deck_legality(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Report LOT-014 deck-construction legality: draw deck size (>=60),
    equal Free Peoples/Shadow split, adventure deck site count (=9), and
    format/X-List legality for every card against the deck's own
    `format`. `errata_notes` is informational only (see DeckLegalityResponse).
    """
    deck = db.query(Deck).filter(Deck.id == deck_id, Deck.user_id == current_user.id).first()
    if not deck:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return DeckLegalityResponse(**deck_legality.evaluate_deck_legality(deck.cards, deck.format))


@router.get("/users/me/cards/available", response_model=OwnedCardAvailabilityListResponse)
async def get_available_cards(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Per-card owned/assigned/available breakdown for the deck builder's
    "available pool" (LOT-014): a card only has spare copies to add to a
    deck if it has at least 1 unassigned copy across ALL of the user's
    decks combined -- mirrors the same accounting `POST /decks/{id}/cards`
    uses to enforce its quantity limit.
    """
    owned_rows = (
        db.query(Ownership.card_id, func.sum(Ownership.quantity).label("qty"))
        .filter(Ownership.user_id == current_user.id, Ownership.is_active == True)
        .group_by(Ownership.card_id)
        .all()
    )
    if not owned_rows:
        return OwnedCardAvailabilityListResponse(items=[])

    owned_by_card = {row.card_id: int(row.qty) for row in owned_rows}

    assigned_rows = (
        db.query(DeckCard.card_id, func.sum(DeckCard.quantity).label("qty"))
        .join(Deck, DeckCard.deck_id == Deck.id)
        .filter(Deck.user_id == current_user.id, DeckCard.card_id.in_(owned_by_card.keys()))
        .group_by(DeckCard.card_id)
        .all()
    )
    assigned_by_card = {row.card_id: int(row.qty) for row in assigned_rows}

    cards_by_id = {c.id: c for c in db.query(Card).filter(Card.id.in_(owned_by_card.keys())).all()}

    items: List[OwnedCardAvailability] = []
    for card_id, owned_qty in owned_by_card.items():
        card = cards_by_id.get(card_id)
        if not card:
            continue
        assigned_qty = assigned_by_card.get(card_id, 0)
        items.append(OwnedCardAvailability(
            card=CardResponse(
                id=card.id, name=card.name, cost=card.cost, rarity=card.rarity,
                description=card.description, stats=card.attributes,
                image_url=card.image_url, created_at=card.created_at, updated_at=card.updated_at,
            ),
            owned_quantity=owned_qty,
            assigned_quantity=assigned_qty,
            available_quantity=max(0, owned_qty - assigned_qty),
        ))

    return OwnedCardAvailabilityListResponse(items=items)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(__name__, host="0.0.0.0", port=8000)
