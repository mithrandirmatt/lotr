"""Base classes, enums, and utilities shared across all models."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
import uuid


# ============== ENUMS ==============

class ItemType(Enum):
    """Types of items that can be purchased or tracked in inventory."""
    
    PACK = "pack"
    STARTER_DECK = "starter_deck"
    BOOSTER_BOX = "booster_box"
    CARD = "card"  # Individual cards for inventory


# ============== UTILITY CLASSES ==============

class Money:
    """Utility class for handling monetary values with precision."""
    
    def __init__(self, amount: Decimal):
        self.amount = amount
    
    @classmethod
    def from_cents(cls, cents: int) -> "Money":
        return cls(Decimal(cents) / Decimal("100"))
    
    def to_cents(self) -> int:
        return int(round(self.amount * 100))
    
    def __add__(self, other: "Money") -> "Money":
        if isinstance(other, Money):
            return Money(self.amount + other.amount)
        raise TypeError("Cannot add non-Money to Money")
    
    def __rsub__(self, other: "Money") -> "Money":
        if isinstance(other, Money):
            return Money(other.amount - self.amount)
        raise TypeError("Can only subtract Money from Money")
    
    def __str__(self) -> str:
        return f"${self.amount:.2f}"


class TimestampMixin:
    """Mix-in for automatic timestamp tracking."""
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(),
        onupdate=func.now()
    )


# ============== BASE MODEL CLASSES ==============

class BaseModel:
    """Base class for all models with common functionality."""
    
    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())
    updated_at: datetime = Column(
        DateTime(timezone=True), 
        server_default=func.now(),
        onupdate=func.now()
    )
