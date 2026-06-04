"""
Card API routes.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from api.v1.deps import get_db
from models.schemas import (
    CardResponse,
    CardListResponse,
    SuccessResponse,
    ErrorResponse,
)
from models.entities import Card

router = APIRouter(prefix="/cards", tags=["Cards"])


def get_card_by_id(db: Session, card_id: str) -> Optional[Card]:
    """Get card by ID."""
    result = db.execute(select(Card).where(Card.card_id == card_id))
    return result.scalar_one_or_none()


def get_card_by_name(db: Session, name: str) -> Optional[Card]:
    """Get card by name."""
    result = db.execute(select(Card).where(Card.name.ilike(f"%{name}%")))
    return result.scalar_one_or_none()


@router.get("", response_model=CardListResponse)
def list_cards(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by name"),
    rarity: Optional[str] = Query(None, description="Filter by rarity"),
):
    """
    List all cards with pagination and filtering.

    - Supports search by name
    - Supports filtering by rarity
    - Returns paginated results
    """
    query = select(Card)

    # Apply filters
    if search:
        query = query.where(Card.name.ilike(f"%{search}%"))
    if rarity:
        query = query.where(Card.rarity == rarity)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar()

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    cards = db.execute(query).scalars().all()

    return CardListResponse(
        items=[CardResponse.model_validate(card) for card in cards],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )


@router.get("/{card_id}", response_model=CardResponse)
def get_card(
    card_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific card by ID.

    - Returns full card details
    - Returns 404 if not found
    """
    card = get_card_by_id(db, card_id)

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )

    return CardResponse.model_validate(card)


@router.get("/search", response_model=CardListResponse)
def search_cards(
    db: Session = Depends(get_db),
    query: str = Query(..., min_length=2, description="Search query"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    Search cards by name, lore, or keywords.

    - Full-text search support
    - Returns paginated results
    """
    query = select(Card).where(
        Card.name.ilike(f"%{query}%") |
        Card.lore.ilike(f"%{query}%") |
        Card.keywords.ilike(f"%{query}%")
    )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar()

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    cards = db.execute(query).scalars().all()

    return CardListResponse(
        items=[CardResponse.model_validate(card) for card in cards],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )
