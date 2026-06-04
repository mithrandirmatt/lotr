"""
SQLAlchemy ORM models for the LotR TCG Server.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, ForeignKey,
    Boolean, JSON, UniqueConstraint, Index, Numeric
)
from sqlalchemy.orm import relationship
from models.database import Base


class User(Base):
    """User table for authentication and authorization."""
    __tablename__ = "users"

    user_id = Column(String(36), primary_key=True, comment="Unique user identifier")
    email = Column(String(255), unique=True, nullable=False, comment="User email address")
    password_hash = Column(String(255), nullable=False, comment="Hashed password")
    role = Column(String(20), default="user", nullable=False, comment="User role")
    is_active = Column(Boolean, default=True, nullable=False, comment="Account status")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="Account creation timestamp")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment="Last update timestamp")

    # Relationships
    card_ownerships = relationship("CardOwnership", back_populates="user", cascade="all, delete-orphan")
    purchase_transactions = relationship("PurchaseTransaction", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_role", "role"),
    )


class CardOwnership(Base):
    """Card ownership records linking users to cards."""
    __tablename__ = "card_ownerships"

    ownership_id = Column(String(36), primary_key=True, comment="Ownership record ID")
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, comment="User identifier")
    card_id = Column(String(50), nullable=False, comment="Card identifier from card database")
    acquired_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="When card was acquired")
    source = Column(String(50), nullable=False, comment="Acquisition method: purchase, reward, etc.")
    metadata = Column(JSON, default=dict, nullable=False, comment="Additional metadata")

    # Relationships
    user = relationship("User", back_populates="card_ownerships")

    __table_args__ = (
        UniqueConstraint("user_id", "card_id", name="uq_user_card"),
        Index("idx_card_ownership_user", "user_id"),
        Index("idx_card_ownership_card", "card_id"),
    )


class PurchaseTransaction(Base):
    """Purchase transaction records for card purchases."""
    __tablename__ = "purchase_transactions"

    transaction_id = Column(String(36), primary_key=True, comment="Unique transaction identifier")
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, comment="User identifier")
    card_id = Column(String(50), nullable=True, comment="Purchased card identifier")
    amount = Column(Numeric(10, 2), nullable=False, comment="Purchase amount")
    currency = Column(String(10), default="USD", nullable=False, comment="Currency code")
    status = Column(String(20), default="pending", nullable=False, comment="Transaction status")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="Transaction creation timestamp")
    completed_at = Column(DateTime, nullable=True, comment="Transaction completion timestamp")
    payment_method = Column(String(100), nullable=False, comment="Payment processor reference")
    payment_reference = Column(String(255), nullable=True, comment="Payment processor reference ID")
    metadata = Column(JSON, default=dict, nullable=False, comment="Additional transaction metadata")

    # Relationships
    user = relationship("User", back_populates="purchase_transactions")

    __table_args__ = (
        Index("idx_purchase_user", "user_id"),
        Index("idx_purchase_card", "card_id"),
        Index("idx_purchase_status", "status"),
    )


class MatchSnapshot(Base):
    """Immutable snapshots of match states for dispute resolution."""
    __tablename__ = "match_snapshots"

    snapshot_id = Column(String(36), primary_key=True, comment="Snapshot ID")
    match_id = Column(String(50), nullable=False, comment="Match identifier")
    state_hash = Column(String(64), nullable=False, comment="Cryptographic hash of match state")
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, comment="Snapshot timestamp")
    players_data = Column(JSON, nullable=False, comment="Serialized player states")
    board_state = Column(JSON, nullable=False, comment="Board state at snapshot time")
    card_positions = Column(JSON, nullable=False, comment="Card positions at snapshot time")
    actions_log = Column(JSON, nullable=False, comment="Actions log at snapshot time")

    __table_args__ = (
        UniqueConstraint("match_id", "timestamp", name="uq_match_timestamp"),
        Index("idx_match_snapshots_match", "match_id"),
    )


class MatchAudit(Base):
    """Audit records for match integrity checking."""
    __tablename__ = "match_audits"

    audit_id = Column(String(36), primary_key=True, comment="Audit ID")
    match_id = Column(String(50), nullable=False, comment="Match identifier")
    anomalies = Column(JSON, nullable=False, comment="Detected anomalies")
    integrity_score = Column(Float, nullable=False, comment="Overall integrity score (0-100)")
    recommendations = Column(JSON, default=list, nullable=False, comment="Recommendations for remediation")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="Audit creation timestamp")

    __table_args__ = (
        Index("idx_match_audits_match", "match_id"),
        Index("idx_match_audits_score", "integrity_score"),
    )


class RateLimit(Base):
    """Rate limiting tracking table."""
    __tablename__ = "rate_limits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    identifier = Column(String(100), nullable=False, comment="Rate limit identifier (IP, user_id, etc.)")
    endpoint = Column(String(100), nullable=False, comment="API endpoint")
    request_count = Column(Integer, default=0, nullable=False, comment="Number of requests in window")
    window_start = Column(DateTime, default=datetime.utcnow, nullable=False, comment="Window start time")
    window_end = Column(DateTime, nullable=False, comment="Window end time")

    __table_args__ = (
        UniqueConstraint("identifier", "endpoint", "window_start", name="uq_rate_limit"),
        Index("idx_rate_limit_identifier", "identifier"),
        Index("idx_rate_limit_endpoint", "endpoint"),
    )
