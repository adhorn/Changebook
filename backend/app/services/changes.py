import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.change import Change, ChangeStatus
from app.models.checklist import ChecklistItem, ChecklistPhase
from app.models.preflight import PREFLIGHT_SCHEMA_VERSION, validate_preflight_completeness
from app.models.review import Review, ReviewDecision

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
    from sqlalchemy.orm import joinedload

    return (
        db.query(Change)
        .options(
            joinedload(Change.customer),
            joinedload(Change.service),
            joinedload(Change.environment),
        )
        .filter(Change.id == change_id)
        .first()
    )


def list_changes(
    db: Session,
    customer_id: uuid.UUID | None = None,
    service_id: uuid.UUID | None = None,
    environment_id: uuid.UUID | None = None,
    status: ChangeStatus | None = None,
    author_name: str | None = None,
    defence_tag: str | None = None,
    title_search: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    sort: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Change], int]:
    from sqlalchemy.orm import joinedload

    query = db.query(Change).options(
        joinedload(Change.customer),
        joinedload(Change.service),
        joinedload(Change.environment),
    )

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
    if title_search:
        query = query.filter(Change.title.ilike(f"%{title_search}%"))
    if created_after:
        query = query.filter(Change.created_at >= created_after)
    if created_before:
        query = query.filter(Change.created_at <= created_before)

    if defence_tag:
        from sqlalchemy import cast
        from sqlalchemy.dialects.postgresql import JSONB

        query = query.filter(Change.defence_tags.op("@>")(cast([defence_tag], JSONB)))

    # Sorting
    if sort == "oldest":
        order = Change.created_at.asc()
    elif sort == "recently_updated":
        order = Change.updated_at.desc()
    else:
        # Default: newest first
        order = Change.created_at.desc()

    total = query.count()
    changes = query.order_by(order).offset(offset).limit(limit).all()
    return changes, total


def update_change(db: Session, change: Change, data: dict, actor_name: str) -> Change:
    # Auto-set schema version and timestamp when preflight answers are updated
    if "preflight_answers" in data and data["preflight_answers"]:
        data.setdefault("preflight_schema_version", PREFLIGHT_SCHEMA_VERSION)
        data["preflight_answered_at"] = datetime.now(UTC)

    for key, value in data.items():
        if value is not None:
            setattr(change, key, value)

    # Integrity guarantee: any edit invalidates existing reviews
    _invalidate_reviews_if_any(db, change.id)

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


def duplicate_change(db: Session, source: Change, overrides: dict, author_name: str) -> Change:
    """Clone a change — same structure, fresh state.

    Copies: title, description, preflight answers, defence tags, checklist items.
    Resets: status to draft, no reviews, no completions.
    """
    title = overrides.get("title") or f"{source.title} (copy)"

    clone = Change(
        title=title,
        description=source.description,
        status=ChangeStatus.DRAFT,
        customer_id=overrides.get("customer_id") or source.customer_id,
        service_id=overrides.get("service_id") or source.service_id,
        environment_id=overrides.get("environment_id") or source.environment_id,
        author_name=author_name,
        preflight_answers=source.preflight_answers,
        preflight_schema_version=source.preflight_schema_version,
        preflight_answered_at=source.preflight_answered_at,
        defence_tags=source.defence_tags,
        maintenance_window_start=(
            overrides.get("maintenance_window_start") or source.maintenance_window_start
        ),
        maintenance_window_end=(
            overrides.get("maintenance_window_end") or source.maintenance_window_end
        ),
        maintenance_window_tz=(
            overrides.get("maintenance_window_tz") or source.maintenance_window_tz
        ),
        cloned_from=source.id,
    )
    db.add(clone)
    db.flush()

    # Copy checklist items (structure only — no completions)
    source_items = (
        db.query(ChecklistItem)
        .filter(ChecklistItem.change_id == source.id)
        .order_by(ChecklistItem.phase, ChecklistItem.order)
        .all()
    )
    for item in source_items:
        clone_item = ChecklistItem(
            change_id=clone.id,
            phase=item.phase,
            order=item.order,
            description=item.description,
            command=item.command,
            expected_outcome=item.expected_outcome,
            rollback_action=item.rollback_action,
            is_hold_point=item.is_hold_point,
        )
        db.add(clone_item)

    audit = AuditEvent(
        change_id=clone.id,
        event_type="change_duplicated",
        actor_name=author_name,
        description=f"Duplicated from change {source.id} ('{source.title}')",
        event_data={"source_change_id": str(source.id)},
    )
    db.add(audit)
    db.commit()
    db.refresh(clone)
    return clone


def transition_status(
    db: Session,
    change: Change,
    new_status: ChangeStatus,
    actor_name: str,
    reason: str | None = None,
) -> Change:
    old_status = change.status
    _validate_transition(old_status, new_status)

    # Gates on transition to in_review
    if new_status == ChangeStatus.IN_REVIEW:
        # Gate 1: all required change profile answers must be filled
        missing_answers = validate_preflight_completeness(change.preflight_answers)
        if missing_answers:
            raise ValueError(
                f"Cannot submit for review — incomplete change profile. Missing: {missing_answers}"
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

    # Gate on transition to approved: all reviewers must have approved
    if new_status == ChangeStatus.APPROVED:
        reviews = db.query(Review).filter(Review.change_id == change.id).all()
        if not reviews:
            raise ValueError(
                "Cannot approve — no reviewers assigned. At least one reviewer must approve."
            )
        non_approved = [r for r in reviews if r.decision != ReviewDecision.APPROVED]
        if non_approved:
            pending_names = [r.reviewer_name for r in non_approved]
            raise ValueError(
                f"Cannot approve — not all reviewers have approved. Outstanding: {pending_names}"
            )

    # Gate on transition to done: all checklist items must be completed
    if new_status == ChangeStatus.DONE:
        from app.services.execution import _is_item_completed

        all_items = list_checklist_items(db, change.id)
        incomplete = [i for i in all_items if not _is_item_completed(i)]
        if incomplete:
            raise ValueError(
                f"Cannot mark done — {len(incomplete)} checklist item(s) not completed. "
                f"All items must be completed before marking a change as done."
            )
        # Also check hold points are verified
        unverified = [
            i
            for i in all_items
            if i.is_hold_point
            and i.completion is not None
            and i.completion.hold_point_verified_by is None
        ]
        if unverified:
            raise ValueError(
                f"Cannot mark done — {len(unverified)} hold point(s) not verified. "
                f"All hold points must be verified before marking a change as done."
            )

    # Window warning on transition to executing
    if new_status == ChangeStatus.EXECUTING:
        now = datetime.now(UTC)
        if change.maintenance_window_start and now < change.maintenance_window_start:
            window_data: dict = {
                "window_start": change.maintenance_window_start.isoformat(),
                "executed_at": now.isoformat(),
            }
            if reason:
                window_data["operator_reason"] = reason
            db.add(
                AuditEvent(
                    change_id=change.id,
                    event_type="window_warning",
                    actor_name=actor_name,
                    description="Execution started before maintenance window opens.",
                    event_data=window_data,
                )
            )
        elif change.maintenance_window_end and now > change.maintenance_window_end:
            window_data = {
                "window_end": change.maintenance_window_end.isoformat(),
                "executed_at": now.isoformat(),
            }
            if reason:
                window_data["operator_reason"] = reason
            db.add(
                AuditEvent(
                    change_id=change.id,
                    event_type="window_warning",
                    actor_name=actor_name,
                    description="Execution started after maintenance window closed.",
                    event_data=window_data,
                )
            )

    # Store window override reason on the change for easy display
    if (
        new_status == ChangeStatus.EXECUTING
        and reason
        and change.maintenance_window_start
        and change.maintenance_window_end
    ):
        now_check = datetime.now(UTC)
        if now_check < change.maintenance_window_start or now_check > change.maintenance_window_end:
            change.window_override_reason = reason

    # Staleness warning on transition to executing
    if new_status == ChangeStatus.EXECUTING and change.preflight_answered_at:
        answered_at = change.preflight_answered_at
        age = datetime.now(UTC) - answered_at
        if age > STALENESS_THRESHOLD:
            staleness_audit = AuditEvent(
                change_id=change.id,
                event_type="staleness_warning",
                actor_name=actor_name,
                description=(
                    f"Change profile is {age.total_seconds() / 3600:.0f}h old "
                    f"(threshold: 24h). Operator acknowledged stale change profile."
                ),
                event_data={
                    "preflight_answered_at": change.preflight_answered_at.isoformat(),
                    "hours_stale": round(age.total_seconds() / 3600, 1),
                },
            )
            db.add(staleness_audit)

    change.status = new_status

    # Store abort reason on the change itself for easy display
    if new_status == ChangeStatus.ABORTED and reason:
        change.abort_reason = reason

    description = f"Status changed from {old_status.value} to {new_status.value}"
    if reason:
        description += f" — {reason}"

    event_data: dict = {"old_status": old_status.value, "new_status": new_status.value}
    if reason:
        event_data["reason"] = reason

    audit = AuditEvent(
        change_id=change.id,
        event_type="status_changed",
        actor_name=actor_name,
        description=description,
        event_data=event_data,
    )
    db.add(audit)
    db.commit()
    db.refresh(change)
    return change


# --- Checklist operations ---


def add_checklist_item(db: Session, change_id: uuid.UUID, data: dict) -> ChecklistItem:
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
    _invalidate_reviews_if_any(db, change_id)
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
    from sqlalchemy.orm import joinedload

    query = (
        db.query(ChecklistItem)
        .options(joinedload(ChecklistItem.completion))
        .filter(ChecklistItem.change_id == change_id)
    )
    if phase:
        query = query.filter(ChecklistItem.phase == phase)
    items = query.order_by(ChecklistItem.order).all()
    # Sort by logical phase order, then by item order within phase
    items.sort(key=lambda i: (PHASE_ORDER.get(i.phase, 99), i.order))
    return items


def update_checklist_item(db: Session, item: ChecklistItem, data: dict) -> ChecklistItem:
    for key, value in data.items():
        if value is not None:
            setattr(item, key, value)
    _invalidate_reviews_if_any(db, item.change_id)
    db.commit()
    db.refresh(item)
    return item


def delete_checklist_item(db: Session, item: ChecklistItem) -> None:
    change_id = item.change_id
    phase = item.phase
    _invalidate_reviews_if_any(db, change_id)
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
    ChangeStatus.APPROVED: {ChangeStatus.EXECUTING, ChangeStatus.DRAFT, ChangeStatus.ABORTED},
    ChangeStatus.EXECUTING: {ChangeStatus.DONE, ChangeStatus.ABORTED},
    ChangeStatus.DONE: set(),
    ChangeStatus.ABORTED: set(),
}


def _invalidate_reviews_if_any(db: Session, change_id: uuid.UUID) -> None:
    """Reset all reviews to pending if any exist. Integrity guarantee."""
    reviews = db.query(Review).filter(Review.change_id == change_id).all()
    changed = False
    for review in reviews:
        if review.decision != ReviewDecision.PENDING:
            review.decision = ReviewDecision.PENDING
            review.comment = None
            changed = True
    if changed:
        audit = AuditEvent(
            change_id=change_id,
            event_type="reviews_invalidated",
            actor_name="system",
            description="All reviews reset to pending due to change edit",
            event_data={
                "reviewers_affected": [r.reviewer_name for r in reviews],
            },
        )
        db.add(audit)


def _validate_transition(current: ChangeStatus, target: ChangeStatus) -> None:
    valid = VALID_TRANSITIONS.get(current, set())
    if target not in valid:
        raise ValueError(
            f"Cannot transition from {current.value} to {target.value}. "
            f"Valid transitions: {[s.value for s in valid]}"
        )
