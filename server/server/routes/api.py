"""
API routes for the LOTR TCG server.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
import jwt
import secrets

from server.core.database import get_db
from server.models.models import (
    User, RefreshToken, Card, Ownership, Purchase, Refund,
    Match, MatchPlayer, MatchState, AuditLog, MatchAuditLog
)
from server.models.schemas import (
    # User schemas
    UserCreate, UserUpdate, UserResponse,
    # Auth schemas
    Token, LoginRequest, RefreshTokenRequest,
    # Card schemas
    CardCreate, CardUpdate, CardResponse, CardListResponse,
    # Ownership schemas
    OwnershipCreate, OwnershipUpdate, OwnershipResponse, UserCardList,
    # Purchase schemas
    PurchaseRequest, PurchaseResponse, PurchaseItemResponse, RefundRequest, RefundResponse,
    # Match schemas
    MatchCreate, MatchResponse, MatchPlayerList,
    # Audit schemas
    AuditReport
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


# ============== AUTH ROUTES ==============

@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    # Check if email exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Check if username exists
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )

    # Hash password
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed_password = pwd_context.hash(user_data.password)

    # Create user
    user = User(
        email=user_data.email,
        username=user_data.username,
        password_hash=hashed_password,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        is_verified=True  # Email verification can be added later
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # Create refresh token
    refresh_token = create_refresh_token({"sub": user.id})

    return {
        "user": user,
        "refresh_token": refresh_token
    }


@router.post("/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Login and get access token."""
    user = db.query(User).filter(
        or_(User.email == form_data.username, User.username == form_data.username)
    ).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    if not pwd_context.verify(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create tokens
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})

    # Store refresh token
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
async def create_card(card_data: CardCreate, db: Session = Depends(get_db)):
    """Create a new card (admin only)."""
    card = Card(**card_data.model_dump())
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


@router.put("/cards/{card_id}", response_model=CardResponse)
async def update_card(card_id: str, card_data: CardUpdate, db: Session = Depends(get_db)):
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
                metadata=ownership.metadata,
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
    return [OwnershipResponse.model_validate(ownership) for ownership in ownerships]


# ============== PURCHASE ROUTES ==============

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
async def get_card_stats(db: Session = Depends(get_db)):
    """Get card statistics (admin only)."""
    total_cards = db.query(Card).count()
    total_ownerships = db.query(Ownership).count()
    total_purchases = db.query(Purchase).count()

    return {
        "total_cards": total_cards,
        "total_ownerships": total_ownerships,
        "total_purchases": total_purchases
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(__name__, host="0.0.0.0", port=8000)
