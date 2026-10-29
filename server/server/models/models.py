"""
Database models for the LOTR TCG server.
Uses SQLAlchemy ORM for database operations.
"""

from datetime import datetime
import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Numeric,
    ForeignKey, Table, Index, Enum, JSON, BigInteger
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


# ============== USER MODELS ==============

class User(Base):
    """User account model."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)

    # Account status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    is_moderator = Column(Boolean, default=False)
    tolkien_balance = Column(Integer, nullable=False, default=0)

    # Two-factor authentication (TOTP, RFC 6238)
    totp_secret = Column(String(64), nullable=True)
    is_2fa_enabled = Column(Boolean, default=False)
    totp_recovery_codes = Column(JSON, nullable=True)  # list of bcrypt-hashed single-use codes

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    ownerships = relationship("Ownership", back_populates="user", cascade="all, delete-orphan")
    purchases = relationship("Purchase", back_populates="user", cascade="all, delete-orphan")
    match_players = relationship("MatchPlayer", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
    decks = relationship("Deck", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_user_email", "email"),
        Index("idx_user_username", "username"),
    )


class RefreshToken(Base):
    """Refresh token model for JWT rotation."""
    __tablename__ = "refresh_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String(500), nullable=False, unique=True)
    refresh_secret = Column(String(255), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    is_revoked = Column(Boolean, default=False)

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")

    __table_args__ = (
        Index("idx_refresh_token_user", "user_id"),
        Index("idx_refresh_token_expires", "expires_at"),
    )


# ============== CARD MODELS ==============

class Card(Base):
    """Card model."""
    __tablename__ = "cards"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=False)
    cost = Column(Integer, nullable=False, default=0)
    rarity = Column(Enum('common', 'uncommon', 'rare', 'epic', 'legendary', 'mythic'), nullable=False)

    # Media
    image_url = Column(String(500), nullable=True)

    # Metadata
    attributes = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)

    # LOT-025: release set this card belongs to (filters booster generation).
    set_number = Column(Integer, nullable=True, index=True)

    # LOT-100 card-authoring review gate.
    publish_status = Column(String(20), nullable=False, default='published')
    review_notes = Column(String(500), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    ownerships = relationship("Ownership", back_populates="card")

    __table_args__ = (
        Index("idx_card_rarity", "rarity"),
        Index("idx_card_set_number", "set_number"),
    )


# ============== OWNERSHIP MODELS ==============

class Ownership(Base):
    """Tracks which user owns which card."""
    __tablename__ = "ownerships"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    card_id = Column(String(36), ForeignKey("cards.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    source = Column(Enum('purchase', 'trade', 'reward', 'event', 'admin'), nullable=False)
    metadata_json = Column("metadata", JSON, nullable=True)

    # How many copies of this card the user owns
    quantity = Column(Integer, nullable=False, default=1)

    # Status
    is_active = Column(Boolean, default=True)

    # LOT-020: foil and non-foil copies of the same card are tracked as
    # distinct ownership rows.
    is_foil = Column(Boolean, nullable=False, default=False)

    # Timestamps
    acquired_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    card = relationship("Card", back_populates="ownerships")
    user = relationship("User", back_populates="ownerships")

    __table_args__ = (
        Index("idx_ownership_card_user_foil", "card_id", "user_id", "is_foil", unique=True),
        Index("idx_ownership_user", "user_id"),
        Index("idx_ownership_card", "card_id"),
    )


class CardHistory(Base):
    """History of card ownership transfers."""
    __tablename__ = "card_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ownership_id = Column(String(36), ForeignKey("ownerships.id"), nullable=False)
    previous_user_id = Column(String(36), nullable=True)
    new_user_id = Column(String(36), nullable=False)
    change_type = Column(Enum('transfer', 'revoke', 'restore', 'admin_change'), nullable=False)
    reason = Column(Text, nullable=True)
    performed_by = Column(String(36), nullable=True)  # Admin user ID or system

    acquired_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_card_history_ownership", "ownership_id"),
        Index("idx_card_history_user", "new_user_id"),
    )


# ============== PURCHASE MODELS ==============

class Purchase(Base):
    """Purchase transaction model."""
    __tablename__ = "purchases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Items
    items = Column(JSON, nullable=False)  # List of {card_id, quantity, price}

    # Financial details
    subtotal = Column(Numeric(10, 2), nullable=False)
    tax = Column(Numeric(10, 2), nullable=False, default=0.00)
    total = Column(Numeric(10, 2), nullable=False)

    # Payment info
    payment_method = Column(String(50), nullable=False)
    payment_provider_ref = Column(String(255), nullable=True)  # Stripe/PayPal transaction ID
    coupon_code = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)

    # Status
    status = Column(Enum('pending', 'processing', 'completed', 'failed', 'refunded'),
                    default='pending', nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="purchases")

    __table_args__ = (
        Index("idx_purchase_user", "user_id"),
        Index("idx_purchase_status", "status"),
        Index("idx_purchase_created", "created_at"),
    )


class PurchaseItem(Base):
    """Individual item in a purchase."""
    __tablename__ = "purchase_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    purchase_id = Column(String(36), ForeignKey("purchases.id"), nullable=False, index=True)
    card_id = Column(String(36), ForeignKey("cards.id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(10, 2), nullable=False)
    total_price = Column(Numeric(10, 2), nullable=False)

    __table_args__ = (
        Index("idx_purchase_item_purchase", "purchase_id"),
        Index("idx_purchase_item_card", "card_id"),
    )


class Refund(Base):
    """Refund transaction model."""
    __tablename__ = "refunds"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    purchase_id = Column(String(36), ForeignKey("purchases.id"), nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(Enum('pending', 'processing', 'completed', 'failed'), default='pending')
    reason = Column(Text, nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_refund_purchase", "purchase_id"),
    )


# ============== MATCH MODELS ==============

class Match(Base):
    """Match session model."""
    __tablename__ = "matches"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(10), unique=True, nullable=False, index=True)

    # Match configuration
    mode = Column(Enum('casual', 'ranked', 'tournament'), nullable=False)
    max_players = Column(Integer, nullable=False, default=2)
    current_players = Column(Integer, default=0)
    card_limit = Column(Integer, nullable=True)
    rules_override = Column(JSON, nullable=True)

    # Status
    status = Column(Enum('created', 'waiting', 'in_progress', 'paused', 'completed', 'cancelled'),
                    default='created', nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    players = relationship("MatchPlayer", back_populates="match", cascade="all, delete-orphan")
    audit_logs = relationship("MatchAuditLog", back_populates="match", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_match_code", "code"),
        Index("idx_match_status", "status"),
        Index("idx_match_created", "created_at"),
    )


class MatchPlayer(Base):
    """Player in a match."""
    __tablename__ = "match_players"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    match_id = Column(String(36), ForeignKey("matches.id"), nullable=False, index=True)
    player_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Player data
    username = Column(String(50), nullable=False)
    deck = Column(JSON, nullable=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    # Match stats (updated during match)
    hand = Column(JSON, nullable=True)
    board = Column(JSON, nullable=True)
    score = Column(Integer, default=0)

    # Relationships
    match = relationship("Match", back_populates="players")
    user = relationship("User", back_populates="match_players")

    __table_args__ = (
        Index("idx_match_player_match", "match_id"),
        Index("idx_match_player_player", "player_id"),
    )


class MatchState(Base):
    """Current state of a match (for persistence)."""
    __tablename__ = "match_states"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    match_id = Column(String(36), ForeignKey("matches.id"), nullable=False, unique=True, index=True)

    # Full match state snapshot
    state = Column(JSON, nullable=False)

    # Timestamps
    saved_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_match_state_match", "match_id"),
    )


# ============== AUDIT MODELS ==============

class AuditLog(Base):
    """General audit log for suspicious activity."""
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    match_id = Column(String(36), nullable=True, index=True)

    anomaly_type = Column(String(100), nullable=False)
    severity = Column(Enum('low', 'medium', 'high', 'critical'), nullable=False)
    description = Column(Text, nullable=False)
    metadata_json = Column("metadata", JSON, nullable=True)

    detected_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("idx_audit_user", "user_id"),
        Index("idx_audit_match", "match_id"),
        Index("idx_audit_severity", "severity"),
        Index("idx_audit_detected", "detected_at"),
    )


class MatchAuditLog(Base):
    """Audit log specific to matches."""
    __tablename__ = "match_audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    match_id = Column(String(36), ForeignKey("matches.id"), nullable=False, index=True)

    anomaly_type = Column(String(100), nullable=False)
    severity = Column(Enum('low', 'medium', 'high', 'critical'), nullable=False)
    description = Column(Text, nullable=False)
    metadata_json = Column("metadata", JSON, nullable=True)

    detected_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    match = relationship("Match", back_populates="audit_logs")

    __table_args__ = (
        Index("idx_match_audit_match", "match_id"),
        Index("idx_match_audit_type", "anomaly_type"),
    )


# ============== DECK MODELS ==============

class Deck(Base):
    """A user's named deck associated with a ruleset format."""
    __tablename__ = "decks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    # LOT-014: real LOTR TCG tournament format names (e.g. "Fellowship
    # Block", "King Block", "Open") -- plain string, not a SQL enum, since
    # the set of legal formats is defined in schemas.DeckFormat, not here.
    format = Column(String(50), nullable=False, default='Open')
    description = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="decks")
    cards = relationship("DeckCard", back_populates="deck", cascade="all, delete-orphan")

    __table_args__ = (
        # Each user must have uniquely named decks
        Index("idx_deck_user_name", "user_id", "name", unique=True),
        Index("idx_deck_user", "user_id"),
    )


class DeckCard(Base):
    """A card slot inside a deck (1 row per card in the deck)."""
    __tablename__ = "deck_cards"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    deck_id = Column(String(36), ForeignKey("decks.id", ondelete="CASCADE"), nullable=False, index=True)
    card_id = Column(String(36), ForeignKey("cards.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=1)

    # Relationships
    deck = relationship("Deck", back_populates="cards")
    card = relationship("Card")

    __table_args__ = (
        Index("idx_deck_card_deck", "deck_id"),
        Index("idx_deck_card_unique", "deck_id", "card_id", unique=True),
    )


# ============== SET RELEASE MODELS (LOT-025) ==============

class SetRelease(Base):
    """Admin-controlled release status for a monthly card set."""
    __tablename__ = "set_releases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    set_number = Column(Integer, nullable=False, unique=True, index=True)
    set_code = Column(String(20), nullable=True)
    name = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False, default=False)
    is_locked_active = Column(Boolean, nullable=False, default=False)
    activated_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


# ============== ENTITLEMENT MODELS (LOT-018 / LOT-025) ==============

class Entitlement(Base):
    """A user's not-yet-claimed grant (starter deck or booster pack)."""
    __tablename__ = "entitlements"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    product_type = Column(String(20), nullable=False)
    set_number = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    status = Column(String(10), nullable=False, default='active')
    granted_at = Column(DateTime, server_default=func.now())
    consumed_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    revocation_reason = Column(String(250), nullable=True)
    transaction_id = Column(String(36), nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        Index("idx_entitlement_user", "user_id"),
        Index("idx_entitlement_user_product_set", "user_id", "product_type", "set_number"),
        Index("idx_entitlement_status", "status"),
    )


# ============== GIFT LEDGER MODELS (LOT-019 / LOT-025) ==============

class Gift(Base):
    """Lifecycle of a gifted store product (created/granted/redeemed/
    consumed/expired/revoked)."""
    __tablename__ = "gifts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sender_id = Column(String(36), nullable=True)
    recipient_id = Column(String(36), nullable=False, index=True)
    product = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    set_number = Column(Integer, nullable=True)
    status = Column(String(10), nullable=False, default='granted')
    note = Column(String(250), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    redeemed_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    transaction_id = Column(String(36), nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_gift_recipient", "recipient_id"),
        Index("idx_gift_recipient_status", "recipient_id", "status"),
    )


# ============== DISTRIBUTION TRANSACTION MODELS (LOT-020) ==============

class DistributionTransaction(Base):
    """Server-authoritative audit trail for every card grant/removal event."""
    __tablename__ = "distribution_transactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    source = Column(String(10), nullable=False, index=True)
    product = Column(String(50), nullable=True)
    set_number = Column(Integer, nullable=True)
    cards = Column(JSON, nullable=False)
    rng_seed = Column(String(64), nullable=True)
    tolkien_delta = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, server_default=func.now())


# ============== WEEKLY REWARD MODELS (LOT-021 / LOT-025) ==============

class WeeklyRewardRoll(Base):
    """One row per (user, week_index): records that the weekly active-user
    random foil reward has already been evaluated for that user/week."""
    __tablename__ = "weekly_reward_rolls"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    week_index = Column(Integer, nullable=False)
    won = Column(Boolean, nullable=False, default=False)
    card_id = Column(String(36), nullable=True)
    rarity = Column(String(20), nullable=True)
    transaction_id = Column(String(36), nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_weekly_reward_user_week", "user_id", "week_index", unique=True),
    )


# ============== ECONOMY SNAPSHOT MODELS (LOT-021 / LOT-100) ==============

class EconomySnapshot(Base):
    """A captured point-in-time economy/circulation telemetry snapshot."""
    __tablename__ = "economy_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    captured_at = Column(DateTime, server_default=func.now(), index=True)
    total_cards_in_circulation = Column(Integer, nullable=False, default=0)
    total_foil_issued = Column(Integer, nullable=False, default=0)
    total_tolkien_net_flow = Column(Integer, nullable=False, default=0)
    total_sell_back_cards = Column(Integer, nullable=False, default=0)
    total_sell_back_tolkien_returned = Column(Integer, nullable=False, default=0)
    weekly_reward_total_rolls = Column(Integer, nullable=False, default=0)
    weekly_reward_total_wins = Column(Integer, nullable=False, default=0)
    weekly_reward_distinct_users = Column(Integer, nullable=False, default=0)
    raw_summary = Column(JSON, nullable=True)


# ============== RELEASE EVENT MODELS (LOT-022 / LOT-025) ==============

class ReleaseEvent(Base):
    """One row per monthly release event (scheduled -> live -> closed)."""
    __tablename__ = "release_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    set_number = Column(Integer, nullable=False, index=True)
    title = Column(String(150), nullable=False)
    description = Column(String(500), nullable=True)
    status = Column(String(20), nullable=False, default='scheduled', index=True)
    reward_policy = Column(JSON, nullable=True)
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class EventParticipation(Base):
    """One row per (event, user): records a user joining a release event."""
    __tablename__ = "event_participations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    reward_transaction_id = Column(String(36), nullable=True)

    joined_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_event_participation_event_user", "event_id", "user_id", unique=True),
    )


# ============== INDEXES ==============

def create_indexes():
    """Create additional indexes for performance."""
    # Card search indexes
    Base.metadata.create_all()
