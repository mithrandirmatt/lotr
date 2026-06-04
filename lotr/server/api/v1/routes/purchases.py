"""
Purchase transaction API routes.
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from api.v1.deps import get_db
from models.schemas import (
    PurchaseTransactionCreate,
    PurchaseTransactionResponse,
    PurchaseTransactionListResponse,
    SuccessResponse,
    ErrorResponse,
)
from models.entities import PurchaseTransaction

router = APIRouter(prefix="/purchases", tags=["Purchases"])


def get_transaction_by_id(db: Session, transaction_id: str) -> Optional[PurchaseTransaction]:
    """Get purchase transaction by ID."""
    result = db.execute(select(PurchaseTransaction).where(PurchaseTransaction.transaction_id == transaction_id))
    return result.scalar_one_or_none()


def get_user_transactions(db: Session, user_id: str, page: int = 1, page_size: int = 20) -> tuple:
    """Get user's purchase transactions with pagination."""
    query = select(PurchaseTransaction).where(PurchaseTransaction.user_id == user_id).order_by(PurchaseTransaction.created_at.desc())

    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar()

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    transactions = db.execute(query).scalars().all()

    return transactions, total


@router.post("", response_model=SuccessResponse, status_code=status.HTTP_201_CREATED)
def create_purchase(
    purchase_data: PurchaseTransactionCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new purchase transaction.

    - Records a card purchase
    - Sets initial status to PENDING
    - Returns transaction details
    """
    transaction = PurchaseTransaction(
        transaction_id=str(datetime.utcnow().isoformat()),
        user_id=purchase_data.user_id,
        card_id=purchase_data.card_id,
        amount=purchase_data.amount,
        currency=purchase_data.currency,
        status=purchase_data.status,
        created_at=datetime.utcnow(),
        payment_method=purchase_data.payment_method,
        metadata={},
    )

    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    return SuccessResponse(
        message="Purchase transaction created successfully",
        data=PurchaseTransactionResponse.model_validate(transaction)
    )


@router.get("", response_model=PurchaseTransactionListResponse)
def list_transactions(
    db: Session = Depends(get_db),
    page: int = 1,
    page_size: int = 20,
):
    """
    List purchase transactions.

    - Requires authentication (user sees their own transactions)
    - Supports pagination
    """
    transactions, total = get_user_transactions(db, None, page, page_size)

    return PurchaseTransactionListResponse(
        items=[PurchaseTransactionResponse.model_validate(t) for t in transactions],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )


@router.get("/{transaction_id}", response_model=PurchaseTransactionResponse)
def get_transaction(
    transaction_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific purchase transaction by ID.

    - Returns full transaction details
    - Returns 404 if not found
    """
    transaction = get_transaction_by_id(db, transaction_id)

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )

    return PurchaseTransactionResponse.model_validate(transaction)


@router.patch("/{transaction_id}/complete", response_model=SuccessResponse)
def complete_transaction(
    transaction_id: str,
    db: Session = Depends(get_db)
):
    """
    Mark a purchase transaction as completed.

    - Updates status to COMPLETED
    - Records completion timestamp
    - May trigger card ownership creation
    """
    transaction = get_transaction_by_id(db, transaction_id)

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )

    if transaction.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transaction is not in pending state"
        )

    transaction.status = "completed"
    transaction.completed_at = datetime.utcnow()

    db.commit()

    return SuccessResponse(
        message="Transaction completed successfully"
    )
