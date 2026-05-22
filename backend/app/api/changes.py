import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.change import ChangeStatus
from app.schemas.changes import (
    ChangeCreate,
    ChangeDetailResponse,
    ChangeListResponse,
    ChangeResponse,
    ChangeUpdate,
)
from app.services import changes as change_service

router = APIRouter(prefix="/changes", tags=["changes"])


@router.post("", response_model=ChangeDetailResponse, status_code=201)
def create_change(payload: ChangeCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    change = change_service.create_change(db, data)
    return change


@router.get("", response_model=ChangeListResponse)
def list_changes(
    team_id: uuid.UUID | None = None,
    status: ChangeStatus | None = None,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    changes, total = change_service.list_changes(db, team_id, status, limit, offset)
    return ChangeListResponse(
        data=[ChangeResponse.model_validate(c) for c in changes],
        meta={"total": total, "limit": limit, "offset": offset},
    )


@router.get("/{change_id}", response_model=ChangeDetailResponse)
def get_change(change_id: uuid.UUID, db: Session = Depends(get_db)):
    change = change_service.get_change(db, change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    return change


@router.patch("/{change_id}", response_model=ChangeDetailResponse)
def update_change(
    change_id: uuid.UUID,
    payload: ChangeUpdate,
    db: Session = Depends(get_db),
):
    change = change_service.get_change(db, change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    if change.status != ChangeStatus.DRAFT:
        raise HTTPException(status_code=422, detail="Can only update changes in draft status")

    data = payload.model_dump(exclude_unset=True)
    # TODO: get actor from auth context. For now, use the change author.
    change = change_service.update_change(db, change, data, change.author_name)
    return change


@router.post("/{change_id}/transition", response_model=ChangeDetailResponse)
def transition_change(
    change_id: uuid.UUID,
    target_status: ChangeStatus,
    actor_name: str,
    db: Session = Depends(get_db),
):
    change = change_service.get_change(db, change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    try:
        change = change_service.transition_status(db, change, target_status, actor_name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return change
