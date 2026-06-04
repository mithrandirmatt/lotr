"""
SQLAlchemy database configuration and session management.
"""
from typing import Optional
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import StaticPool

from core.config import settings

# Create database engine
def get_engine() -> create_engine:
    """Create and configure the database engine."""
    if "sqlite" in settings.DATABASE_URL:
        # SQLite with check_same_thread disabled for better performance
        return create_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
    else:
        return create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_recycle=3600
        )

# Create session factory
engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """
    Dependency that provides a database session.
    Always use this dependency for database operations.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Base class for all models
Base = declarative_base()


@event.listens_for(engine, "connect")
def on_connect(dbapi_connection, connection_record):
    """Listen for connect events and apply additional configuration."""
    # Set timezone to UTC
    dbapi_connection.execute("SET timezone TO 'UTC'")


@event.listens_for(engine, "checkout")
def on_checkout(dbapi_connection, connection_record, connection_proxy):
    """Listen for checkout events and apply additional configuration."""
    # Set timezone on each connection checkout
    dbapi_connection.execute("SET timezone TO 'UTC'")
