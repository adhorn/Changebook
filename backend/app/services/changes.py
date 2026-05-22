import uuid

from sqlalchemy.orm import Session, joinedload

from app.models.audit import AuditEvent
from app.models.change import Change, ChangeStatus
from app.models.step import Step


def create_change(db: Session, data: dict) -> Change:
    steps_data = data.pop("steps", None) or []

    change = Change(**data)
    db.add(change)
    db.flush()

    for i, step_data in enumerate(steps_data):
        step = Step(change_id=change.id, order=i + 1, **step_data)
        db.add(step)

    audit = AuditEvent(
        change_id=change.id,
        event_type="change_created",
        actor_name=change.author_name,
        description=f"Change '{change.title}' created",
        event_data={"status": change.status.value},
    )
    db.add(audit)
    db.commit()
    db.refresh(change)
    return change


def get_change(db: Session, change_id: uuid.UUID) -> Change | None:
    return db.query(Change).options(joinedload(Change.steps)).filter(Change.id == change_id).first()


def list_changes(
    db: Session,
    team_id: uuid.UUID | None = None,
    status: ChangeStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Change], int]:
    query = db.query(Change)

    if team_id:
        query = query.filter(Change.team_id == team_id)
    if status:
        query = query.filter(Change.status == status)

    total = query.count()
    changes = query.order_by(Change.created_at.desc()).offset(offset).limit(limit).all()
    return changes, total


def update_change(db: Session, change: Change, data: dict, actor_name: str) -> Change:
    for key, value in data.items():
        if value is not None:
            setattr(change, key, value)

    audit = AuditEvent(
        change_id=change.id,
        event_type="change_updated",
        actor_name=actor_name,
        description=f"Change '{change.title}' updated",
        event_data={"fields_updated": list(data.keys())},
    )
    db.add(audit)
    db.commit()
    db.refresh(change)
    return change


def transition_status(
    db: Session, change: Change, new_status: ChangeStatus, actor_name: str
) -> Change:
    old_status = change.status
    _validate_transition(old_status, new_status)

    change.status = new_status

    audit = AuditEvent(
        change_id=change.id,
        event_type="status_changed",
        actor_name=actor_name,
        description=f"Status changed from {old_status.value} to {new_status.value}",
        event_data={"old_status": old_status.value, "new_status": new_status.value},
    )
    db.add(audit)
    db.commit()
    db.refresh(change)
    return change


# Valid state transitions
VALID_TRANSITIONS = {
    ChangeStatus.DRAFT: {ChangeStatus.IN_REVIEW, ChangeStatus.ABORTED},
    ChangeStatus.IN_REVIEW: {ChangeStatus.APPROVED, ChangeStatus.DRAFT, ChangeStatus.ABORTED},
    ChangeStatus.APPROVED: {ChangeStatus.EXECUTING, ChangeStatus.ABORTED},
    ChangeStatus.EXECUTING: {
        ChangeStatus.AWAITING_VERIFICATION,
        ChangeStatus.ABORTED,
    },
    ChangeStatus.AWAITING_VERIFICATION: {
        ChangeStatus.VERIFIED,
        ChangeStatus.EXECUTING,  # can go back if verification fails
        ChangeStatus.ABORTED,
    },
    ChangeStatus.VERIFIED: {ChangeStatus.CLOSED},
    ChangeStatus.CLOSED: set(),
    ChangeStatus.ABORTED: set(),
}


def _validate_transition(current: ChangeStatus, target: ChangeStatus) -> None:
    valid = VALID_TRANSITIONS.get(current, set())
    if target not in valid:
        raise ValueError(
            f"Cannot transition from {current.value} to {target.value}. "
            f"Valid transitions: {[s.value for s in valid]}"
        )
