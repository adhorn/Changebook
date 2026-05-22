import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.change import Change, ChangeStatus
from app.models.checklist import ChecklistItem, ChecklistPhase
from app.models.preflight import PREFLIGHT_SCHEMA_VERSION, validate_preflight_completeness

STALENESS_THRESHOLD = timedelta(hours=24)


def create_change(db: Session, data: dict) -> Change:
    # Auto-set schema version and timestamp when preflight answers are provided
    if data.get("preflight_answers"):
        data.setdefault("preflight_schema_version", PREFLIGHT_SCHEMA_VERSION)
        data.setdefault("preflight_answered_at", datetime.now(UTC))
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
    # Auto-set schema version and timestamp when preflight answers are updated
    if "preflight_answers" in data and data["preflight_answers"]:
        data.setdefault("preflight_schema_version", PREFLIGHT_SCHEMA_VERSION)
        data["preflight_answered_at"] = datetime.now(UTC)

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

    # Gates on transition to in_review
    if new_status == ChangeStatus.IN_REVIEW:
        # Gate 1: all required pre-flight answers must be filled
        missing_answers = validate_preflight_completeness(change.preflight_answers)
        if missing_answers:
            raise ValueError(
                f"Cannot submit for review — incomplete pre-flight answers. "
                f"Missing: {missing_answers}"
            )

        # Gate 2: all three phases must have at least one checklist item
        phases_with_items = set(
            row[0]
            for row in db.query(ChecklistItem.phase)
            .filter(ChecklistItem.change_id == change.id)
            .distinct()
            .all()
        )
        required_phases = {
            ChecklistPhase.PRE_FLIGHT,
            ChecklistPhase.EXECUTION,
            ChecklistPhase.VERIFICATION,
        }
        missing_phases = required_phases - phases_with_items
        if missing_phases:
            raise ValueError(
                f"Cannot submit for review — checklist items required in all "
                f"three phases. Missing: {sorted(p.value for p in missing_phases)}"
            )

    # Staleness warning on transition to executing
    if new_status == ChangeStatus.EXECUTING and change.preflight_answered_at:
        answered_at = change.preflight_answered_at
        # SQLite returns naive datetimes; ensure both are tz-aware for comparison
        if answered_at.tzinfo is None:
            answered_at = answered_at.replace(tzinfo=UTC)
        age = datetime.now(UTC) - answered_at
        if age > STALENESS_THRESHOLD:
            staleness_audit = AuditEvent(
                change_id=change.id,
                event_type="staleness_warning",
                actor_name=actor_name,
                description=(
                    f"Pre-flight answers are {age.total_seconds() / 3600:.0f}h old "
                    f"(threshold: 24h). Operator acknowledged stale pre-flight."
                ),
                event_data={
                    "preflight_answered_at": change.preflight_answered_at.isoformat(),
                    "hours_stale": round(age.total_seconds() / 3600, 1),
                },
            )
            db.add(staleness_audit)

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


def get_checklist_item(
    db: Session, change_id: uuid.UUID, item_id: uuid.UUID
) -> ChecklistItem | None:
    return (
        db.query(ChecklistItem)
        .filter(ChecklistItem.id == item_id, ChecklistItem.change_id == change_id)
        .first()
    )


# Logical phase order for sorting (not alphabetical)
PHASE_ORDER = {
    ChecklistPhase.PRE_FLIGHT: 0,
    ChecklistPhase.EXECUTION: 1,
    ChecklistPhase.VERIFICATION: 2,
}


def list_checklist_items(
    db: Session,
    change_id: uuid.UUID,
    phase: ChecklistPhase | None = None,
) -> list[ChecklistItem]:
    query = db.query(ChecklistItem).filter(ChecklistItem.change_id == change_id)
    if phase:
        query = query.filter(ChecklistItem.phase == phase)
    items = query.order_by(ChecklistItem.order).all()
    # Sort by logical phase order, then by item order within phase
    items.sort(key=lambda i: (PHASE_ORDER.get(i.phase, 99), i.order))
    return items


def update_checklist_item(
    db: Session, item: ChecklistItem, data: dict
) -> ChecklistItem:
    for key, value in data.items():
        if value is not None:
            setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete_checklist_item(db: Session, item: ChecklistItem) -> None:
    change_id = item.change_id
    phase = item.phase
    db.delete(item)
    db.flush()

    # Recompact ordering for remaining items in the same phase
    remaining = (
        db.query(ChecklistItem)
        .filter(
            ChecklistItem.change_id == change_id,
            ChecklistItem.phase == phase,
        )
        .order_by(ChecklistItem.order)
        .all()
    )
    for i, remaining_item in enumerate(remaining, start=1):
        remaining_item.order = i

    db.commit()


def reorder_checklist_items(
    db: Session,
    change_id: uuid.UUID,
    phase: ChecklistPhase,
    item_ids: list[uuid.UUID],
) -> list[ChecklistItem]:
    existing = (
        db.query(ChecklistItem)
        .filter(
            ChecklistItem.change_id == change_id,
            ChecklistItem.phase == phase,
        )
        .all()
    )
    existing_ids = {item.id for item in existing}
    requested_ids = set(item_ids)

    if existing_ids != requested_ids:
        raise ValueError(
            f"Reorder must include all {len(existing_ids)} items for phase "
            f"'{phase.value}'. Got {len(requested_ids)}."
        )

    id_to_item = {item.id: item for item in existing}
    for new_order, item_id in enumerate(item_ids, start=1):
        id_to_item[item_id].order = new_order

    db.commit()
    return list_checklist_items(db, change_id, phase)


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
