import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db
from app.models.audit import AuditEvent
from app.models.change import ChangeStatus
from app.models.checklist import ChecklistPhase
from app.models.review import Review, ReviewDecision
from app.schemas.changes import (
    ChangeCreate,
    ChangeDetailResponse,
    ChangeDuplicate,
    ChangeListResponse,
    ChangeResponse,
    ChangeUpdate,
)
from app.schemas.checklist import (
    ChecklistCompletionCreate,
    ChecklistCompletionResponse,
    ChecklistItemCreate,
    ChecklistItemResponse,
    ChecklistItemUpdate,
    ChecklistReorder,
    ExecutionStatusResponse,
    HoldPointVerify,
)
from app.schemas.reviews import ReviewDecisionSubmit, ReviewerAssign, ReviewResponse
from app.schemas.templates import SaveAsTemplate, TemplateDetailResponse
from app.services import changes as change_service
from app.services import execution as execution_service
from app.services import export as export_service
from app.services import reviews as review_service
from app.services import templates as template_service

router = APIRouter(prefix="/changes", tags=["changes"])


def _require_author(user: CurrentUser, change) -> None:
    """Raise 403 if the current user is not the change author."""
    if user.name != change.author_name:
        raise HTTPException(
            status_code=403,
            detail=f"Only the change author ({change.author_name}) can perform this action.",
        )


@router.post("", response_model=ChangeDetailResponse, status_code=201)
def create_change(
    payload: ChangeCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = payload.model_dump()
    data["author_name"] = user.name  # Always from auth
    change = change_service.create_change(db, data)
    return change


@router.get("", response_model=ChangeListResponse)
def list_changes(
    customer_id: uuid.UUID | None = None,
    service_id: uuid.UUID | None = None,
    environment_id: uuid.UUID | None = None,
    status: ChangeStatus | None = None,
    author_name: str | None = None,
    defence_tag: str | None = None,
    title_search: str | None = None,
    created_after: str | None = None,
    created_before: str | None = None,
    needs_review_by: str | None = None,
    sort: str | None = None,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    created_after_dt = datetime.fromisoformat(created_after) if created_after else None
    created_before_dt = datetime.fromisoformat(created_before) if created_before else None

    changes, total = change_service.list_changes(
        db,
        customer_id=customer_id,
        service_id=service_id,
        environment_id=environment_id,
        status=status,
        author_name=author_name,
        defence_tag=defence_tag,
        title_search=title_search,
        created_after=created_after_dt,
        created_before=created_before_dt,
        sort=sort,
        limit=limit,
        offset=offset,
    )

    # Compute audit event counts
    change_ids = [c.id for c in changes]
    if change_ids:
        counts = dict(
            db.query(AuditEvent.change_id, func.count(AuditEvent.id))
            .filter(AuditEvent.change_id.in_(change_ids))
            .group_by(AuditEvent.change_id)
            .all()
        )
    else:
        counts = {}

    # Compute pending reviewers per change
    pending_reviews_map: dict[uuid.UUID, list[str]] = {}
    if change_ids:
        pending_reviews = (
            db.query(Review.change_id, Review.reviewer_name)
            .filter(
                Review.change_id.in_(change_ids),
                Review.decision == ReviewDecision.PENDING,
            )
            .all()
        )
        for cid, reviewer_name in pending_reviews:
            pending_reviews_map.setdefault(cid, []).append(reviewer_name)

    # Filter by needs_review_by if requested
    if needs_review_by:
        # Get all change IDs where this user has a pending review
        reviewer_change_ids = set(
            row[0]
            for row in db.query(Review.change_id)
            .filter(
                Review.reviewer_name == needs_review_by,
                Review.decision == ReviewDecision.PENDING,
            )
            .all()
        )
        changes = [c for c in changes if c.id in reviewer_change_ids]
        total = len(changes)

    data = []
    for c in changes:
        resp = ChangeResponse.model_validate(c)
        resp.audit_event_count = counts.get(c.id, 0)
        resp.pending_reviewers = pending_reviews_map.get(c.id, [])
        data.append(resp)

    return ChangeListResponse(
        data=data,
        meta={"total": total, "limit": limit, "offset": offset},
    )


@router.get("/{change_id}", response_model=ChangeDetailResponse)
def get_change(change_id: uuid.UUID, db: Session = Depends(get_db)):
    change = change_service.get_change(db, change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    resp = ChangeDetailResponse.model_validate(change)
    # Populate pending reviewers
    pending = (
        db.query(Review.reviewer_name)
        .filter(
            Review.change_id == change_id,
            Review.decision == ReviewDecision.PENDING,
        )
        .all()
    )
    resp.pending_reviewers = [r[0] for r in pending]
    return resp


@router.post("/{change_id}/duplicate", response_model=ChangeDetailResponse, status_code=201)
def duplicate_change(
    change_id: uuid.UUID,
    payload: ChangeDuplicate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    source = change_service.get_change(db, change_id)
    if not source:
        raise HTTPException(status_code=404, detail="Change not found")

    overrides = payload.model_dump(exclude_unset=True)
    clone = change_service.duplicate_change(db, source, overrides, user.name)
    return clone


@router.post(
    "/{change_id}/save-as-template",
    response_model=TemplateDetailResponse,
    status_code=201,
)
def save_as_template(
    change_id: uuid.UUID,
    payload: SaveAsTemplate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change = change_service.get_change(db, change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    template = template_service.save_change_as_template(
        db,
        change,
        title=payload.title,
        description=payload.description,
        author_name=user.name,
    )
    resp = TemplateDetailResponse.model_validate(template)
    resp.item_count = len(template.items)
    return resp


@router.get("/{change_id}/export/markdown")
def export_markdown(
    change_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    change = change_service.get_change(db, change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    md = export_service.render_markdown(db, change)
    return Response(content=md, media_type="text/markdown; charset=utf-8")


@router.patch("/{change_id}", response_model=ChangeDetailResponse)
def update_change(
    change_id: uuid.UUID,
    payload: ChangeUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change = change_service.get_change(db, change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    _require_author(user, change)
    if change.status != ChangeStatus.DRAFT:
        raise HTTPException(status_code=422, detail="Can only update changes in draft status")

    data = payload.model_dump(exclude_unset=True)
    change = change_service.update_change(db, change, data, user.name)
    return change


@router.post("/{change_id}/transition", response_model=ChangeDetailResponse)
def transition_change(
    change_id: uuid.UUID,
    target_status: ChangeStatus,
    reason: str | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change = change_service.get_change(db, change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    _require_author(user, change)
    change = change_service.transition_status(
        db,
        change,
        target_status,
        user.name,
        reason=reason,
    )
    return change


# --- Checklist items ---


@router.post(
    "/{change_id}/checklist",
    response_model=ChecklistItemResponse,
    status_code=201,
)
def add_checklist_item(
    change_id: uuid.UUID,
    payload: ChecklistItemCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change = change_service.get_change(db, change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    _require_author(user, change)
    if change.status != ChangeStatus.DRAFT:
        raise HTTPException(
            status_code=422,
            detail="Can only add checklist items to changes in draft status",
        )

    data = payload.model_dump()
    item = change_service.add_checklist_item(db, change_id, data)
    return item


@router.get(
    "/{change_id}/checklist",
    response_model=list[ChecklistItemResponse],
)
def list_checklist_items(
    change_id: uuid.UUID,
    phase: ChecklistPhase | None = None,
    db: Session = Depends(get_db),
):
    change = change_service.get_change(db, change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    items = change_service.list_checklist_items(db, change_id, phase)
    return items


@router.put(
    "/{change_id}/checklist/reorder",
    response_model=list[ChecklistItemResponse],
)
def reorder_checklist_items(
    change_id: uuid.UUID,
    payload: ChecklistReorder,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change = change_service.get_change(db, change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    _require_author(user, change)
    if change.status != ChangeStatus.DRAFT:
        raise HTTPException(
            status_code=422,
            detail="Can only reorder checklist items on changes in draft status",
        )

    items = change_service.reorder_checklist_items(db, change_id, payload.phase, payload.item_ids)
    return items


@router.get(
    "/{change_id}/checklist/{item_id}",
    response_model=ChecklistItemResponse,
)
def get_checklist_item(
    change_id: uuid.UUID,
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    change = change_service.get_change(db, change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    item = change_service.get_checklist_item(db, change_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    return item


@router.patch(
    "/{change_id}/checklist/{item_id}",
    response_model=ChecklistItemResponse,
)
def update_checklist_item(
    change_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: ChecklistItemUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change = change_service.get_change(db, change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    _require_author(user, change)
    if change.status != ChangeStatus.DRAFT:
        raise HTTPException(
            status_code=422,
            detail="Can only update checklist items on changes in draft status",
        )

    item = change_service.get_checklist_item(db, change_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")

    data = payload.model_dump(exclude_unset=True)
    item = change_service.update_checklist_item(db, item, data)
    return item


@router.delete(
    "/{change_id}/checklist/{item_id}",
    status_code=204,
)
def delete_checklist_item(
    change_id: uuid.UUID,
    item_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change = change_service.get_change(db, change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    _require_author(user, change)
    if change.status != ChangeStatus.DRAFT:
        raise HTTPException(
            status_code=422,
            detail="Can only delete checklist items on changes in draft status",
        )

    item = change_service.get_checklist_item(db, change_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")

    change_service.delete_checklist_item(db, item)
    return Response(status_code=204)


# --- Execution ---


@router.post(
    "/{change_id}/checklist/{item_id}/complete",
    response_model=ChecklistCompletionResponse,
)
def complete_checklist_item(
    change_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: ChecklistCompletionCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change = change_service.get_change(db, change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    item = change_service.get_checklist_item(db, change_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")

    completion = execution_service.complete_item(
        db, change, item, payload.observed_result, payload.status, user.name
    )
    return completion


@router.post(
    "/{change_id}/checklist/{item_id}/hold-point-verify",
    response_model=ChecklistCompletionResponse,
)
def verify_hold_point(
    change_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: HoldPointVerify,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change = change_service.get_change(db, change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    item = change_service.get_checklist_item(db, change_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")

    # Two-person rule: verifier name must be different from completer
    if item.completion and item.completion.completed_by == payload.verified_by:
        raise HTTPException(
            status_code=422,
            detail=f"Hold point must be verified by a different person "
            f"than the one who completed the item ({item.completion.completed_by}).",
        )

    completion = execution_service.verify_hold_point(db, change, item, payload.verified_by)
    return completion


@router.get(
    "/{change_id}/execution-status",
    response_model=ExecutionStatusResponse,
)
def get_execution_status(
    change_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    change = change_service.get_change(db, change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    return execution_service.get_execution_status(db, change)


# --- Reviews ---


@router.post(
    "/{change_id}/reviewers",
    response_model=ReviewResponse,
    status_code=201,
)
def assign_reviewer(
    change_id: uuid.UUID,
    payload: ReviewerAssign,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change = change_service.get_change(db, change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    _require_author(user, change)

    reviewable = {"draft", "in_review"}
    if change.status.value not in reviewable:
        raise HTTPException(
            status_code=422,
            detail="Reviewers can only be assigned in draft or in_review.",
        )

    reviewer_name = payload.reviewer_name or user.name

    # Author cannot review their own change
    if reviewer_name == change.author_name:
        raise HTTPException(
            status_code=422,
            detail="Cannot review your own change. A different person must review.",
        )

    review = review_service.assign_reviewer(db, change_id, reviewer_name)
    return review


@router.get(
    "/{change_id}/reviewers",
    response_model=list[ReviewResponse],
)
def list_reviewers(
    change_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    change = change_service.get_change(db, change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    return review_service.list_reviews(db, change_id)


@router.post(
    "/{change_id}/reviewers/{review_id}/decision",
    response_model=ReviewResponse,
)
def submit_review_decision(
    change_id: uuid.UUID,
    review_id: uuid.UUID,
    payload: ReviewDecisionSubmit,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change = change_service.get_change(db, change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    if change.status != ChangeStatus.IN_REVIEW:
        raise HTTPException(
            status_code=422,
            detail="Reviews can only be submitted when the change is in_review",
        )

    review = review_service.get_review(db, change_id, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # Only the assigned reviewer can submit their own decision
    if user.name != review.reviewer_name:
        raise HTTPException(
            status_code=403,
            detail=f"Only the assigned reviewer ({review.reviewer_name}) can submit this decision.",
        )

    review = review_service.submit_decision(db, review, payload.decision, payload.comment)
    return review
