"""
Core security utilities for JWT authentication, password hashing, and encryption.
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple
from jose import JWTError, jwt
from passlib.context import CryptContext
import secrets
import hashlib
import os

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate a password hash."""
    return pwd_context.hash(password)


def generate_jwt(
    subject: str,
    additional_claims: Optional[dict] = None,
    token_type: str = "access"
) -> str:
    """
    Generate a JWT token.

    Args:
        subject: The subject (usually user ID)
        additional_claims: Additional claims to include
        token_type: 'access' or 'refresh'

    Returns:
        JWT token string
    """
    from core.config import get_settings

    settings = get_settings()

    if token_type == "access":
        expire_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    else:
        expire_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "sub": subject,
        "type": token_type,
        "exp": datetime.utcnow() + expire_delta,
        "iat": datetime.utcnow()
    }

    if additional_claims:
        to_encode.update(additional_claims)

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def decode_jwt(token: str, token_type: str = "access") -> Optional[dict]:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string
        token_type: Expected token type ('access' or 'refresh')

    Returns:
        Decoded claims or None if invalid
    """
    from core.config import get_settings

    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        # Verify token type
        if payload.get("type") != token_type:
            return None

        # Verify not expired
        if datetime.utcnow() > datetime.fromtimestamp(payload["exp"]):
            return None

        return payload
    except JWTError:
        return None


def generate_refresh_token(user_id: str) -> Tuple[str, str]:
    """
    Generate a refresh token pair (token + secret).

    Returns:
        Tuple of (refresh_token, refresh_secret)
    """
    refresh_secret = secrets.token_urlsafe(32)
    token_data = {
        "sub": user_id,
        "type": "refresh",
        "exp": datetime.utcnow() + timedelta(days=7)
    }

    refresh_token = jwt.encode(
        token_data,
        refresh_secret,
        algorithm="HS256"
    )

    return refresh_token, refresh_secret


def verify_refresh_token(refresh_token: str, refresh_secret: str) -> Optional[dict]:
    """Verify a refresh token with its secret."""
    try:
        payload = jwt.decode(
            refresh_token,
            refresh_secret,
            algorithms=["HS256"]
        )

        if datetime.utcnow() > datetime.fromtimestamp(payload["exp"]):
            return None

        return payload
    except JWTError:
        return None


def hash_sensitive_data(data: str, salt: Optional[str] = None) -> str:
    """
    Hash sensitive data with a salt for additional security.
    """
    if salt is None:
        salt = secrets.token_hex(16)

    # Combine data with salt and hash
    combined = f"{salt}:{data}"
    hashed = hashlib.sha256(combined.encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_sensitive_data(data: str, stored_hash: str) -> bool:
    """Verify sensitive data against stored hash."""
    try:
        salt, expected_hash = stored_hash.split(":", 1)
        computed_hash = hash_sensitive_data(data, salt)
        return computed_hash == stored_hash
    except ValueError:
        return False


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(length)


def validate_input(data: dict, schema: dict) -> Tuple[bool, list]:
    """
    Basic input validation against a schema.

    Args:
        data: Input data to validate
        schema: Schema with field names and types

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []

    for field, field_type in schema.items():
        if field not in data:
            errors.append(f"Missing required field: {field}")
            continue

        value = data[field]

        if field_type == "string":
            if not isinstance(value, str):
                errors.append(f"Field '{field}' must be a string")
        elif field_type == "integer":
            if not isinstance(value, int):
                errors.append(f"Field '{field}' must be an integer")
        elif field_type == "float":
            if not isinstance(value, (int, float)):
                errors.append(f"Field '{field}' must be a number")
        elif field_type == "boolean":
            if not isinstance(value, bool):
                errors.append(f"Field '{field}' must be a boolean")
        elif field_type == "list":
            if not isinstance(value, list):
                errors.append(f"Field '{field}' must be a list")

    return len(errors) == 0, errors
