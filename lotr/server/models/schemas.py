"""
Pydantic models and schemas for the LotR TCG Server.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, EmailStr, ConfigDict


# Enums
class TransactionStatus(str, Enum):
    """Status of a purchase transaction."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class UserRole(str, Enum):
    """User roles for RBAC."""
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"


class MatchActionType(str, Enum):
    """Types of actions in a match."""
    PLAY_CARD = "play_card"
    DISCARD = "discard"
    DRAW = "draw"
    ATTACK = "attack"
    DEFEND = "defend"
    SPECIAL_ABILITY = "special_ability"


# User Models
class UserBase(BaseModel):
    """Base model for user data."""
    email: EmailStr = Field(..., description="User email address")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")


class UserUpdate(BaseModel):
    """Schema for updating user data."""
    email: Optional[EmailStr] = None
    password: Optional[str] = None


class UserResponse(UserBase):
    """Response schema for user data."""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique user identifier")
    role: UserRole = Field(default=UserRole.USER, description="User role")


# Card Ownership Models
class CardOwnershipBase(BaseModel):
    """Base model for card ownership."""
    card_id: str = Field(..., description="Card identifier from card database")
    source: str = Field(..., description="How card was acquired: purchase, reward, etc.")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CardOwnershipCreate(CardOwnershipBase):
    """Schema for creating card ownership."""
    user_id: str = Field(..., description="Unique user identifier")


class CardOwnershipResponse(BaseModel):
    """Response schema for card ownership."""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Ownership record ID")
    user_id: str
    card_id: str
    acquired_at: datetime
    source: str
    metadata: Dict[str, Any]


# Purchase Transaction Models
class PurchaseTransactionBase(BaseModel):
    """Base model for purchase transactions."""
    card_id: Optional[str] = None
    amount: float = Field(..., gt=0, description="Purchase amount")
    currency: str = Field(default="USD", description="Currency code")
    payment_method: str = Field(..., description="Payment processor reference")


class PurchaseTransactionCreate(PurchaseTransactionBase):
    """Schema for creating a purchase transaction."""
    user_id: str
    status: TransactionStatus = Field(default=TransactionStatus.PENDING)


class PurchaseTransactionResponse(BaseModel):
    """Response schema for purchase transaction."""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique transaction identifier")
    user_id: str
    card_id: Optional[str]
    amount: float
    currency: str
    status: TransactionStatus
    created_at: datetime
    completed_at: Optional[datetime]
    payment_method: str
    payment_reference: Optional[str] = None


# Match State Models
class PlayerState(BaseModel):
    """State of a player in a match."""
    user_id: str
    deck: List[str] = Field(default_factory=list)
    hand: List[str] = Field(default_factory=list)
    board: List[str] = Field(default_factory=list)
    resources: int = 0
    is_active: bool = True


class MatchStateSnapshot(BaseModel):
    """Immutable snapshot of match state."""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Snapshot ID")
    match_id: str
    state_hash: str = Field(..., description="Cryptographic hash of match state")
    timestamp: datetime
    players: List[PlayerState]
    board_state: Dict[str, Any]
    card_positions: Dict[str, Any]
    actions_log: List[Dict[str, Any]]


# Audit Models
class MatchAuditAnomaly(BaseModel):
    """An anomaly detected during match audit."""
    type: str
    severity: str = Field(..., description="low, medium, high, critical")
    description: str
    evidence: Dict[str, Any]


class MatchAuditResponse(BaseModel):
    """Response schema for match audit."""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Audit ID")
    match_id: str
    timestamp: datetime
    anomalies: List[MatchAuditAnomaly]
    integrity_score: float
    recommendations: List[str]


# Common Response Models
class PaginatedResponse(BaseModel):
    """Base model for paginated responses."""
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    message: str
    code: str
    details: Optional[Dict[str, Any]] = None


class SuccessResponse(BaseModel):
    """Standard success response."""
    success: bool = True
    message: Optional[str] = None
    data: Optional[Any] = None
