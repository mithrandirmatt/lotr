"""
Authentication API routes.
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import select

from core.security import (
    verify_password,
    get_password_hash,
    generate_jwt,
    decode_jwt,
)
from models.database import get_db
from models.schemas import (
    UserCreate,
    UserUpdate,
    UserResponse,
    SuccessResponse,
    ErrorResponse,
)
from models.entities import User

router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def create_user(db: Session, user_data: UserCreate) -> User:
    """Create a new user."""
    # Check if user already exists
    result = db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user
    user = User(
        user_id=str(datetime.utcnow().isoformat()),
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        role="user",
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """Get user by ID."""
    result = db.execute(select(User).where(User.user_id == user_id))
    return result.scalar_one_or_none()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email."""
    result = db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


@router.post("/register", response_model=SuccessResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user.

    - Creates a new user account
    - Hashes the password securely
    - Returns user data (without password)
    """
    user = create_user(db, user_data)

    return SuccessResponse(
        message="User registered successfully",
        data=UserResponse.model_validate(user)
    )


@router.post("/token", response_model=SuccessResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Login and get access/refresh tokens.

    - Validates email and password
    - Returns JWT tokens
    """
    user = get_user_by_email(db, form_data.username)

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )

    access_token, refresh_token = generate_jwt(
        subject=user.user_id,
        additional_claims={"email": user.email, "role": user.role}
    )

    return SuccessResponse(
        message="Login successful",
        data={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 1800,  # 30 minutes
        }
    )


@router.post("/refresh", response_model=SuccessResponse)
def refresh_token(
    refresh_token: str = Header(..., description="Refresh token"),
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token.

    - Validates refresh token
    - Returns new access token
    """
    payload = decode_jwt(refresh_token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is not a refresh token"
        )

    if datetime.utcnow() > datetime.fromtimestamp(payload["exp"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired"
        )

    user = get_user_by_id(db, payload["sub"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    new_access_token, _ = generate_jwt(
        subject=user.user_id,
        additional_claims={"email": user.email, "role": user.role}
    )

    return SuccessResponse(
        message="Token refreshed successfully",
        data={
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": 1800,
        }
    )


@router.get("/me", response_model=UserResponse)
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user.

    - Validates access token
    - Returns user data
    """
    payload = decode_jwt(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is not an access token"
        )

    user = get_user_by_id(db, payload["sub"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserResponse.model_validate(user)


@router.patch("/me", response_model=UserResponse)
def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update current user's information.

    - Updates email and/or password
    - Requires authentication
    """
    update_data = user_update.model_dump(exclude_unset=True)

    if "password" in update_data:
        update_data["password_hash"] = get_password_hash(update_data.pop("password"))

    for key, value in update_data.items():
        setattr(current_user, key, value)

    db.commit()
    db.refresh(current_user)

    return UserResponse.model_validate(current_user)
