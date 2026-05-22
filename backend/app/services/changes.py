import uuid

from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.change import Change, ChangeStatus
from app.models.checklist import ChecklistItem, ChecklistPhase
from app.models.preflight import PREFLIGHT_SCHEMA_VERSION, validate_preflight_completeness


def create_change(db: Session, data: dict) -> Change:
    # Auto-set schema version when preflight answers are provided
    if data.get("preflight_answers"):
        data.setdefault("preflight_schema_version", PREFLIGHT_SCHEMA_VERSION)
    change = Change(**data)
    db.add(change)
    db.flush()

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
    return db.query(Change).filter(Change.id == change_id).first()


def list_changes(
    db: Session,
    customer_id: uuid.UUID | None = None,
    service_id: uuid.UUID | None = None,
    environment_id: uuid.UUID | None = None,
    status: ChangeStatus | None = None,
    author_name: str | None = None,
    defence_tag: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Change], int]:
    query = db.query(Change)

    if customer_id:
        query = query.filter(Change.customer_id == customer_id)
    if service_id:
        query = query.filter(Change.service_id == service_id)
    if environment_id:
        query = query.filter(Change.environment_id == environment_id)
    if status:
        query = query.filter(Change.status == status)
    if author_name:
        query = query.filter(Change.author_name == author_name)
    # Defence tag filtering requires JSON contains — handled at DB level
    # For SQLite compatibility, we filter in Python for now
    if defence_tag:
        all_changes = query.all()
        filtered = [
            c for c in all_changes
            if c.defence_tags and defence_tag in c.defence_tags
        ]
        total = len(filtered)
        changes = filtered[offset : offset + limit]
        return changes, total

    total = query.count()
    changes = query.order_by(Change.created_at.desc()).offset(offset).limit(limit).all()
    return changes, total


def update_change(db: Session, change: Change, data: dict, actor_name: str) -> Change:
    # Auto-set schema version when preflight answers are updated
    if "preflight_answers" in data and data["preflight_answers"]:
        data.setdefault("preflight_schema_version", PREFLIGHT_SCHEMA_VERSION)

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

    # Pre-flight completeness gate: all required answers must be filled before review
    if new_status == ChangeStatus.IN_REVIEW:
        missing = validate_preflight_completeness(change.preflight_answers)
        if missing:
            raise ValueError(
                f"Cannot submit for review — incomplete pre-flight answers. "
                f"Missing: {missing}"
            )

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


# --- Checklist operations ---


def add_checklist_item(
    db: Session, change_id: uuid.UUID, data: dict
) -> ChecklistItem:
    phase = data["phase"]

    # Auto-order: next in sequence for this phase
    max_order = (
        db.query(ChecklistItem)
        .filter(
            ChecklistItem.change_id == change_id,
            ChecklistItem.phase == phase,
        )
        .count()
    )

    item = ChecklistItem(
        change_id=change_id,
        order=max_order + 1,
        **data,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_checklist_items(
    db: Session,
    change_id: uuid.UUID,
    phase: ChecklistPhase | None = None,
) -> list[ChecklistItem]:
    query = db.query(ChecklistItem).filter(ChecklistItem.change_id == change_id)
    if phase:
        query = query.filter(ChecklistItem.phase == phase)
    return query.order_by(ChecklistItem.phase, ChecklistItem.order).all()


# Valid state transitions
VALID_TRANSITIONS = {
    ChangeStatus.DRAFT: {ChangeStatus.IN_REVIEW, ChangeStatus.ABORTED},
    ChangeStatus.IN_REVIEW: {ChangeStatus.APPROVED, ChangeStatus.DRAFT, ChangeStatus.ABORTED},
    ChangeStatus.APPROVED: {ChangeStatus.EXECUTING, ChangeStatus.ABORTED},
    ChangeStatus.EXECUTING: {ChangeStatus.DONE, ChangeStatus.ABORTED},
    ChangeStatus.DONE: set(),
    ChangeStatus.ABORTED: set(),
}


def _validate_transition(current: ChangeStatus, target: ChangeStatus) -> None:
    valid = VALID_TRANSITIONS.get(current, set())
    if target not in valid:
        raise ValueError(
            f"Cannot transition from {current.value} to {target.value}. "
            f"Valid transitions: {[s.value for s in valid]}"
        )
