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
from passlib.context import CryptContext
import jwt
import secrets
import ipaddress
import os
import io
import base64
import pyotp
import qrcode

from ..core.database import get_db
from ..models.models import (
    User, RefreshToken, Card, Ownership, Purchase, Refund,
    Match, MatchPlayer, MatchState, AuditLog, MatchAuditLog,
    Deck, DeckCard
)
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
    # Ownership schemas
    OwnershipCreate, OwnershipUpdate, OwnershipResponse, UserCardList,
    # Purchase schemas
    PurchaseRequest, PurchaseResponse, RefundRequest, RefundResponse,
    StorePurchaseRequest, StorePurchaseResponse, StorePricingResponse,
    AdminTolkienAdjustRequest, AdminUserDeleteRequest, AdminUserSummary, AdminUserListResponse,
    # Match schemas
    MatchCreate, MatchResponse, MatchPlayerList,
    # Audit schemas
    AuditReport,
    # Deck schemas
    DeckCreate, DeckUpdate, DeckResponse, DeckListResponse, DeckCardAdd, DeckCardRemove, DeckCardEntry
)

# Router setup
router = APIRouter(prefix="/api/v1", tags=["API"])

# Security
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

# JWT settings
SECRET_KEY = secrets.token_urlsafe(32)  # In production, use environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 30

# LOT-006 store pricing strategy (1 USD == 1 Tolkien)
USD_PER_TOLKIEN = 1.0
STORE_PRODUCT_PRICES_TOLKIENS = {
    "pack": 1,
    "starter_deck": 5,
    "booster_box": 30,
}

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
    """Create JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
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

    return {"message": "Registration successful. Please log in."}


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
    """List all cards with filtering and pagination."""
    query = db.query(Card)

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
    """Get a specific card by ID."""
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


@router.post("/cards", response_model=CardResponse, status_code=status.HTTP_201_CREATED)
async def create_card(
    card_data: CardCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Create a new card (admin only)."""
    card = Card(**card_data.model_dump())
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
    for field, value in update_data.items():
        setattr(card, field, value)

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


# ============== PURCHASE ROUTES ==============

@router.get("/store/pricing", response_model=StorePricingResponse)
async def get_store_pricing():
    """Expose LOT-006 Tolkien product pricing strategy."""
    return StorePricingResponse(
        currency="Tolkien",
        usd_per_tolkien=USD_PER_TOLKIEN,
        products=STORE_PRODUCT_PRICES_TOLKIENS,
    )


@router.post("/store/purchase", response_model=StorePurchaseResponse)
async def purchase_store_product(
    payload: StorePurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Purchase packs/decks/boxes using Tolkien balance."""
    unit_price = STORE_PRODUCT_PRICES_TOLKIENS[payload.product.value]
    total_price = unit_price * payload.quantity

    if current_user.tolkien_balance < total_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient Tolkien balance. Need {total_price}, have {current_user.tolkien_balance}",
        )

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


# ============== DECK ROUTES ==============

# Format → set of allowed card attributes (placeholder — expand per game rules)
FORMAT_LEGAL_SETS: dict = {
    "standard": {"sets": ["fellowship", "two_towers", "return_of_king"]},
    "modern": {"sets": ["fellowship", "two_towers", "return_of_king", "shadows", "battle_of_helm_deep"]},
    "open": None,  # All cards legal
}


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


@router.get("/decks/legal-cards", response_model=CardListResponse)
async def get_legal_cards(
    format: str = Query("open", description="Ruleset format: standard, modern, open"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List cards the current user owns that are legal in the specified format."""
    if format not in FORMAT_LEGAL_SETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown format '{format}'. Choose from: {', '.join(FORMAT_LEGAL_SETS)}",
        )
    # Get all card IDs the user owns
    owned_card_ids = [
        o.card_id for o in db.query(Ownership).filter(
            Ownership.user_id == current_user.id, Ownership.is_active == True
        ).all()
    ]
    query = db.query(Card).filter(Card.id.in_(owned_card_ids), Card.is_active == True)
    total = query.count()
    cards = query.offset((page - 1) * page_size).limit(page_size).all()
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(__name__, host="0.0.0.0", port=8000)
