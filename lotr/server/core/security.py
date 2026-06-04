"""
Security utilities for authentication and authorization.
"""
import os
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple
from jose import JWTError, jwt
from passlib.context import CryptContext

from core.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.

    Args:
        plain_password: The plain text password to verify
        hashed_password: The hashed password to check against

    Returns:
        True if the password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: The plain text password to hash

    Returns:
        The hashed password
    """
    return pwd_context.hash(password)


def generate_jwt(
    subject: str,
    additional_claims: Optional[dict] = None
) -> Tuple[str, str]:
    """
    Generate a JWT access token and refresh token.

    Args:
        subject: The subject (usually user ID)
        additional_claims: Additional claims to include

    Returns:
        Tuple of (access_token, refresh_token)
    """
    now = datetime.utcnow()

    # Access token
    access_token_payload = {
        "sub": subject,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": now,
        "type": "access"
    }
    if additional_claims:
        access_token_payload.update(additional_claims)

    access_token = jwt.encode(
        access_token_payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    # Refresh token
    refresh_token_payload = {
        "sub": subject,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "iat": now,
        "type": "refresh"
    }
    if additional_claims:
        refresh_token_payload.update(additional_claims)

    refresh_token = jwt.encode(
        refresh_token_payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    return access_token, refresh_token


def decode_jwt(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT token.

    Args:
        token: The JWT token to decode

    Returns:
        The decoded token payload, or None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def generate_refresh_token() -> str:
    """Generate a cryptographically secure random refresh token."""
    return secrets.token_urlsafe(256)


def hash_sensitive_data(data: str) -> str:
    """
    Hash sensitive data using SHA-256 with salt.

    Args:
        data: The sensitive data to hash

    Returns:
        The hashed data
    """
    salt = hashlib.sha256(os.urandom(32)).hexdigest()
    hashed = hashlib.sha256((salt + data).encode()).hexdigest()
    return f"{salt}:{hashed}"
