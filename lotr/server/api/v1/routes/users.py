"""
User management API routes.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from api.v1.deps import get_db
from models.schemas import (
    UserResponse,
    UserListResponse,
    SuccessResponse,
    ErrorResponse,
)
from models.entities import User

router = APIRouter(prefix="/users", tags=["Users"])


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """Get user by ID."""
    result = db.execute(select(User).where(User.user_id == user_id))
    return result.scalar_one_or_none()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email."""
    result = db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


@router.get("", response_model=UserListResponse)
def list_users(
    db: Session = Depends(get_db),
    page: int = 1,
    page_size: int = 20,
):
    """
    List all users (admin only).

    - Returns paginated user list
    - Requires admin authentication
    """
    query = select(User).order_by(User.email)

    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar()

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    users = db.execute(query).scalars().all()

    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific user by ID.

    - Returns user details (excluding password hash)
    - Returns 404 if not found
    """
    user = get_user_by_id(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserResponse.model_validate(user)


@router.get("/email/{email}", response_model=UserResponse)
def get_user_by_email_route(
    email: str,
    db: Session = Depends(get_db)
):
    """
    Get user by email address.

    - Useful for email verification flows
    - Returns 404 if not found
    """
    user = get_user_by_email(db, email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserResponse.model_validate(user)
