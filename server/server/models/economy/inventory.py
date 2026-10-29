"""CardInventory and Ownership tracking (LOT-023).

This module implements the inventory system that tracks:
- What cards a user owns (with quantities)
- How they acquired each card (source attribution)
- When items were added/removed from inventory
- Current balance for economy interactions
"""

from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy import (
    Column, DateTime, ForeignKey, Index, Numeric, String, Text, func
)
from sqlalchemy.orm import relationship

# Import base classes and enums
from ..base import BaseModel


class CardInventory(BaseModel):
    """Tracks cards owned by a user with source attribution.
    
    This model implements LOT-023 requirements for transparent inventory tracking:
    - Each card entry records the acquisition source (purchase, trade, reward, etc.)
    - Quantities are tracked per unique card+user combination
    - Source attribution enables audit trails and dispute resolution
    
    Attributes:
        id: Unique identifier for this inventory slot
        user_id: Owner of these cards
        card_id: The specific card(s) in this slot
        quantity: Number of copies owned (default 1)
        source: How acquired (purchase, trade, reward, event, admin)
        purchase_reference: Optional link to Purchase transaction for LOT-025 compliance
    """
    
    __tablename__ = "card_inventory"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    card_id = Column(String(36), ForeignKey("cards.id", ondelete="SET NULL"), nullable=False)
    
    quantity = Column(Integer, default=1)  # Default to single copies
    
    source = Column(
        String(50), 
        nullable=False,  # purchase, trade, reward, event, admin
        index=True
    )
    
    # Link back to Purchase for LOT-025 compliance (audit trail)
    purchase_reference = Column(String(36), ForeignKey("purchases.id", ondelete="SET NULL"), nullable=True)


# ============== INDEXES FOR PERFORMANCE ==============

def create_inventory_indexes():
    """Create indexes for common inventory query patterns."""
    __table_args__ = (
        Index("idx_inv_user_card", "user_id", "card_id"),  # Fast lookups by user+card
        Index("idx_inv_source", "source"),  # Filter by acquisition source
        Index("idx_inv_quantity", "quantity"),  # Find bulk items quickly
    )


# ============== QUERY HELPERS ==============

def get_user_inventory(user_id: str, card_id: str | None = None) -> list["CardInventory"]:
    """Get inventory entries for a user.
    
    Args:
        user_id: The user's ID
        card_id: Optional filter to specific card
        
    Returns:
        List of CardInventory entries (aggregated by card+user)
    """
    from sqlalchemy.orm import Session
    
    with Session() as session:
        query = session.query(CardInventory).filter(
            CardInventory.user_id == user_id
        )
        
        if card_id:
            query = query.filter(CardInventory.card_id == card_id)
        
        return query.order_by(CardInventory.card_id, CardInventory.quantity.desc()).all()


def get_total_cards_owned(user_id: str) -> int:
    """Get total number of cards owned (summed across all inventory slots)."""
    from sqlalchemy.orm import Session
    
    with Session() as session:
        return sum(
            row.quantity 
            for row in session.query(CardInventory)
            .filter(CardInventory.user_id == user_id)
            .all()
        )


def get_inventory_by_source(user_id: str, source: str) -> list["CardInventory"]:
    """Get inventory filtered by acquisition source."""
    from sqlalchemy.orm import Session
    
    with Session() as session:
        return (
            session.query(CardInventory)
            .filter(
                CardInventory.user_id == user_id,
                CardInventory.source == source
            )
            .order_by(CardInventory.card_id)
            .all()
        )
