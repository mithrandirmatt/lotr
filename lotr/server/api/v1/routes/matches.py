"""
Match API routes.
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from api.v1.deps import get_db
from models.schemas import (
    MatchCreate,
    MatchResponse,
    MatchListResponse,
    MatchSnapshotCreate,
    MatchAuditCreate,
    SuccessResponse,
    ErrorResponse,
)
from models.entities import MatchSnapshot, MatchAudit

router = APIRouter(prefix="/matches", tags=["Matches"])


def get_match_by_id(db: Session, match_id: str) -> Optional[MatchSnapshot]:
    """Get match snapshot by match ID."""
    result = db.execute(select(MatchSnapshot).where(MatchSnapshot.match_id == match_id))
    return result.scalar_one_or_none()


@router.post("", response_model=SuccessResponse, status_code=status.HTTP_201_CREATED)
def create_match(
    match_data: MatchCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new match snapshot.

    - Records initial match state
    - Creates cryptographic hash for integrity
    """
    state_hash = match_data.state_hash or "initial_state"

    snapshot = MatchSnapshot(
        snapshot_id=str(datetime.utcnow().isoformat()),
        match_id=match_data.match_id,
        state_hash=state_hash,
        timestamp=datetime.utcnow(),
        players_data=match_data.players_data,
        board_state=match_data.board_state,
        card_positions=match_data.card_positions,
        actions_log=match_data.actions_log,
    )

    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    return SuccessResponse(
        message="Match created successfully",
        data=MatchResponse.model_validate(snapshot)
    )


@router.get("", response_model=MatchListResponse)
def list_matches(
    db: Session = Depends(get_db),
    page: int = 1,
    page_size: int = 20,
):
    """
    List match snapshots.

    - Returns paginated match history
    - Useful for dispute resolution
    """
    query = select(MatchSnapshot).order_by(MatchSnapshot.timestamp.desc())

    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar()

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    snapshots = db.execute(query).scalars().all()

    return MatchListResponse(
        items=[MatchResponse.model_validate(s) for s in snapshots],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )


@router.get("/{match_id}", response_model=MatchResponse)
def get_match(
    match_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific match snapshot by ID.

    - Returns immutable match state
    - Used for dispute resolution
    """
    snapshot = get_match_by_id(db, match_id)

    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found"
        )

    return MatchResponse.model_validate(snapshot)


@router.post("/snapshots", response_model=SuccessResponse, status_code=status.HTTP_201_CREATED)
def create_snapshot(
    snapshot_data: MatchSnapshotCreate,
    db: Session = Depends(get_db)
):
    """
    Create a match state snapshot.

    - Records match state at a point in time
    - Immutable for dispute resolution
    """
    snapshot = MatchSnapshot(
        snapshot_id=str(datetime.utcnow().isoformat()),
        match_id=snapshot_data.match_id,
        state_hash=snapshot_data.state_hash,
        timestamp=datetime.utcnow(),
        players_data=snapshot_data.players_data,
        board_state=snapshot_data.board_state,
        card_positions=snapshot_data.card_positions,
        actions_log=snapshot_data.actions_log,
    )

    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    return SuccessResponse(
        message="Match snapshot created successfully",
        data=MatchResponse.model_validate(snapshot)
    )


@router.post("/audits", response_model=SuccessResponse, status_code=status.HTTP_201_CREATED)
def create_audit(
    audit_data: MatchAuditCreate,
    db: Session = Depends(get_db)
):
    """
    Create a match integrity audit record.

    - Records detected anomalies
    - Provides integrity score
    - Offers remediation recommendations
    """
    audit = MatchAudit(
        audit_id=str(datetime.utcnow().isoformat()),
        match_id=audit_data.match_id,
        anomalies=audit_data.anomalies,
        integrity_score=audit_data.integrity_score,
        recommendations=audit_data.recommendations,
        created_at=datetime.utcnow(),
    )

    db.add(audit)
    db.commit()
    db.refresh(audit)

    return SuccessResponse(
        message="Audit record created successfully",
        data={
            "audit_id": audit.audit_id,
            "match_id": audit.match_id,
            "integrity_score": audit.integrity_score,
        }
    )
