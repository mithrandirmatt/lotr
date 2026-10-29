"""PurchaseHistory entity for detailed transaction tracking (LOT-025).

This model tracks individual line-items from each purchase, enabling:
- Detailed purchase history per user
- Item-level audit trail with timestamps
- Financial reconciliation by querying specific purchases
- Compliance with LOT-025 requirements for transparent economy
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
import uuid

from sqlalchemy import (
    Column, DateTime, ForeignKey, Index, Numeric, String, Text, func
)
from sqlalchemy.orm import relationship

# Import base classes and enums
from ..base import BaseModel, ItemType


class PurchaseHistory(BaseModel):
    """Detailed record of each item purchased.
    
    This model tracks individual line-items from purchases (e.g., "I bought a pack 
    containing 4 copies of Card X on date Y"). It provides the granular history 
    required by LOT-025 for transparent economy tracking.
    
    Attributes:
        id: Unique identifier for this purchase line-item
        purchase_id: Reference to parent Purchase transaction (LOT-018)
        card_id: The specific card contained in this item
        item_type: Type of purchased item (pack, starter_deck, booster_box)
        pack_contents_json: JSON describing what was inside the pack
        quantity_per_pack: Number of packs bought (default 1)
        unit_price: Price per individual pack/item
        total_cost: Total cost for this line-item (unit_price × quantity)
        purchased_at: When this item was acquired
    """
    
    __tablename__ = "purchase_history"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    purchase_id = Column(
        String(36), 
        ForeignKey("purchases.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    card_id = Column(
        String(36), 
        ForeignKey("cards.id", ondelete="SET NULL"),  # SET NULL allows cards to be removed from history
        nullable=False,
        index=True
    )
    
    item_type = Column(Enum(ItemType), nullable=False)
    
    # Item contents (for packs/boxes that contain multiple cards)
    pack_contents_json = Column(Text, nullable=True)  # e.g., {"card_a": 4, "card_b": 2}
    quantity_per_pack = Column(Integer, default=1)
    
    # Financials with Decimal for precision
    unit_price = Column(Numeric(10, 2), nullable=False)
    total_cost = Column(Numeric(10, 2), nullable=False)
    
    # Timestamps
    purchased_at = Column(DateTime(timezone=True), server_default=func.now())


# ============== INDEXES FOR PERFORMANCE ==============

def create_purchase_history_indexes():
    """Create indexes for common query patterns."""
    __table_args__ = (
        Index("idx_ph_user", "user_id"),  # Fast user history lookups
        Index("idx_ph_date_range", "purchased_at"),  # Date range queries
        Index("idx_ph_item_type", "item_type"),  # Filter by item type
    )


# ============== QUERY HELPERS ==============

def get_user_purchase_history(user_id: str, limit: int = 100) -> list["PurchaseHistory"]:
    """Get recent purchases for a user."""
    from sqlalchemy.orm import Session
    
    with Session() as session:
        return (
            session.query(PurchaseHistory)
            .filter(PurchaseHistory.user_id == user_id)
            .order_by(PurchaseHistory.purchased_at.desc())
            .limit(limit)
            .all()
        )
