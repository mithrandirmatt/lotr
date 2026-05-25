"""
Pydantic schemas for API request/response validation.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, validator, ConfigDict
from enum import Enum

# ============== USER SCHEMAS ==============

class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., min_length=8, max_length=100)
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)


class UserUpdate(BaseModel):
    """Schema for updating user information."""
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    current_password: Optional[str] = None
    new_password: Optional[str] = Field(None, min_length=8, max_length=100)


class UserResponse(UserBase):
    """User response schema (includes ID)."""
    id: str
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
    is_verified: bool = False


# ============== AUTH SCHEMAS ==============

class Token(BaseModel):
    """Authentication token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    """Decoded token payload."""
    sub: str
    type: str
    exp: int
    iat: int


class LoginRequest(BaseModel):
    """Login request schema."""
    email: EmailStr
    password: str = Field(..., min_length=8)


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""
    refresh_token: str


# ============== CARD SCHEMAS ==============

class Rarity(str, Enum):
    """Card rarity enum."""
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"


class CardBase(BaseModel):
    """Base card schema."""
    name: str = Field(..., min_length=1, max_length=200)
    cost: int = Field(..., ge=0)
    rarity: Rarity = Rarity.COMMON
    description: Optional[str] = Field(None, max_length=1000)
    stats: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None


class CardCreate(CardBase):
    """Schema for creating a new card."""
    pass


class CardUpdate(BaseModel):
    """Schema for updating card information."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    cost: Optional[int] = Field(None, ge=0)
    rarity: Optional[Rarity] = None
    description: Optional[str] = Field(None, max_length=1000)
    stats: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None


class CardResponse(CardBase):
    """Card response schema (includes ID)."""
    id: str
    created_at: datetime
    updated_at: datetime


class CardListResponse(BaseModel):
    """Card list response with pagination."""
    items: List[CardResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ============== OWNERSHIP SCHEMAS ==============

class OwnershipBase(BaseModel):
    """Base ownership schema."""
    card_id: str
    source: str = Field(..., description="How card was acquired: purchase, match_reward, event, etc.")
    metadata: Optional[Dict[str, Any]] = None


class OwnershipCreate(OwnershipBase):
    """Schema for creating ownership record."""
    pass


class OwnershipUpdate(BaseModel):
    """Schema for updating ownership."""
    source: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class OwnershipResponse(OwnershipBase):
    """Ownership response schema."""
    id: str
    user_id: str
    acquired_at: datetime
    is_active: bool = True


class UserCardList(BaseModel):
    """User's card collection response."""
    user_id: str
    cards: List[OwnershipResponse]
    total_cards: int
    total_cost: float


# ============== PURCHASE SCHEMAS ==============

class PurchaseItem(BaseModel):
    """Purchase item schema."""
    card_id: str
    quantity: int = Field(..., ge=1)


class PurchaseRequest(BaseModel):
    """Schema for purchase request."""
    items: List[PurchaseItem]
    payment_method: str = Field(..., description="Payment method: credit_card, paypal, etc.")
    coupon_code: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = Field(None, max_length=500)


class PurchaseResponse(BaseModel):
    """Purchase response schema."""
    id: str
    user_id: str
    items: List[Dict[str, Any]]
    subtotal: float
    tax: float
    total: float
    payment_method: str
    coupon_code: Optional[str]
    notes: Optional[str]
    status: str = "completed"
    created_at: datetime


class RefundRequest(BaseModel):
    """Schema for refund request."""
    partial_amount: Optional[float] = Field(None, ge=0)
    reason: str = Field(..., max_length=500)


class RefundResponse(BaseModel):
    """Refund response schema."""
    id: str
    purchase_id: str
    amount: float
    reason: str
    status: str = "pending"
    created_at: datetime


# ============== MATCH SCHEMAS ==============

class MatchMode(str, Enum):
    """Match mode enum."""
    STANDARD = "standard"
    CUSTOM = "custom"
    TOURNAMENT = "tournament"


class MatchBase(BaseModel):
    """Base match schema."""
    mode: MatchMode = MatchMode.STANDARD
    max_players: int = Field(..., ge=2, le=16)
    card_limit: int = Field(..., ge=1, le=100)
    rules_override: Optional[Dict[str, Any]] = None


class MatchCreate(MatchBase):
    """Schema for creating a match."""
    pass


class MatchResponse(MatchBase):
    """Match response schema."""
    id: str
    code: str
    status: str = "waiting"
    current_players: int = 0
    created_at: datetime
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class MatchPlayer(BaseModel):
    """Match player schema."""
    player_id: str
    username: str
    joined_at: datetime
    ready: bool = False


class MatchPlayerList(BaseModel):
    """Match players list response."""
    match_id: str
    players: List[MatchPlayer]
    max_players: int


# ============== AUDIT SCHEMAS ==============

class AuditReport(BaseModel):
    """Match audit report."""
    match_id: str
    total_checks: int
    anomalies_found: int
    integrity_score: int
    last_checked: datetime
    recent_anomalies: List[Dict[str, Any]]


# ============== GENERIC SCHEMAS ==============

class PageParams(BaseModel):
    """Pagination parameters."""
    page: int = 1
    page_size: int = 20


class ErrorResponse(BaseModel):
    """Error response schema."""
    detail: str
    code: Optional[str] = None


# ============== CONFIGURATION ==============

class ModelConfig:
    """Pydantic model configuration."""
    from pydantic import ConfigDict

    model_config = ConfigDict(
        populate_by_name=True,  # Allow alias access
        validate_assignment=True,  # Validate on assignment
        arbitrary_types_allowed=True,  # Allow arbitrary types
        json_schema_extra={
            "title": "LOTR TCG API",
            "description": "Schemas for the Lord of the Rings TCG API"
        }
    )
