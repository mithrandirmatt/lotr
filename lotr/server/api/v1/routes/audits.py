"""
Audit log API routes.
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from api.v1.deps import get_db
from models.schemas import (
    AuditLogCreate,
    AuditLogResponse,
    AuditLogListResponse,
    SuccessResponse,
)
from models.entities import AuditLog

router = APIRouter(prefix="/audits", tags=["Audit Logs"])


def get_audit_by_id(db: Session, audit_id: str) -> Optional[AuditLog]:
    """Get audit log by ID."""
    result = db.execute(select(AuditLog).where(AuditLog.audit_id == audit_id))
    return result.scalar_one_or_none()


@router.post("", response_model=SuccessResponse, status_code=status.HTTP_201_CREATED)
def create_audit(
    audit_data: AuditLogCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new audit log entry.

    - Records system events
    - Immutable for compliance
    """
    audit = AuditLog(
        audit_id=str(datetime.utcnow().isoformat()),
        event_type=audit_data.event_type,
        user_id=audit_data.user_id,
        resource_type=audit_data.resource_type,
        resource_id=audit_data.resource_id,
        action=audit_data.action,
        details=audit_data.details,
        ip_address=audit_data.ip_address,
        user_agent=audit_data.user_agent,
        timestamp=datetime.utcnow(),
    )

    db.add(audit)
    db.commit()
    db.refresh(audit)

    return SuccessResponse(
        message="Audit log created successfully",
        data=AuditLogResponse.model_validate(audit)
    )


@router.get("", response_model=AuditLogListResponse)
def list_audits(
    db: Session = Depends(get_db),
    page: int = 1,
    page_size: int = 20,
    event_type: Optional[str] = None,
    resource_type: Optional[str] = None,
):
    """
    List audit logs with filtering.

    - Supports filtering by event type and resource type
    - Returns paginated results
    """
    query = select(AuditLog)

    if event_type:
        query = query.where(AuditLog.event_type == event_type)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)

    query = query.order_by(AuditLog.timestamp.desc())

    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar()

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    audits = db.execute(query).scalars().all()

    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(a) for a in audits],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )


@router.get("/{audit_id}", response_model=AuditLogResponse)
def get_audit(
    audit_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific audit log entry by ID.

    - Returns full audit details
    - Returns 404 if not found
    """
    audit = get_audit_by_id(db, audit_id)

    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log not found"
        )

    return AuditLogResponse.model_validate(audit)
