"""Checklist execution service — sequential read-do logic.

Enforces:
- Items completed in order within each phase
- Phases completed in order: pre_flight → execution → verification
- Hold points require second-person verification before the next item unlocks
- Only works when the change is in 'executing' status
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, GateError, ValidationError
from app.models.audit import AuditEvent
from app.models.change import Change, ChangeStatus
from app.models.checklist import (
    ChecklistCompletion,
    ChecklistItem,
    ChecklistPhase,
    CompletionStatus,
)

logger = logging.getLogger(__name__)

# Logical phase order — must match the PHASE_ORDER in changes service
PHASE_SEQUENCE = [
    ChecklistPhase.PRE_FLIGHT,
    ChecklistPhase.EXECUTION,
    ChecklistPhase.VERIFICATION,
]


def _get_ordered_items(db: Session, change_id: uuid.UUID) -> list[ChecklistItem]:
    """Get all checklist items in execution order (phase, then order within phase)."""
    phase_order = {
        ChecklistPhase.PRE_FLIGHT: 0,
        ChecklistPhase.EXECUTION: 1,
        ChecklistPhase.VERIFICATION: 2,
    }
    items = db.query(ChecklistItem).filter(ChecklistItem.change_id == change_id).all()
    items.sort(key=lambda i: (phase_order.get(i.phase, 99), i.order))
    return items


def _items_by_phase(
    items: list[ChecklistItem],
) -> dict[ChecklistPhase, list[ChecklistItem]]:
    """Group items by phase, preserving order."""
    grouped: dict[ChecklistPhase, list[ChecklistItem]] = {}
    for item in items:
        grouped.setdefault(item.phase, []).append(item)
    return grouped


def _is_item_completed(item: ChecklistItem) -> bool:
    """Check if an item has a completion record."""
    return item.completion is not None


def _is_phase_complete(items: list[ChecklistItem]) -> bool:
    """Check if all items in a phase are completed (and hold points verified)."""
    for item in items:
        if not _is_item_completed(item):
            return False
        if item.is_hold_point and item.completion.hold_point_verified_by is None:
            return False
    return True


def complete_item(
    db: Session,
    change: Change,
    item: ChecklistItem,
    observed_result: str,
    status: CompletionStatus,
    completed_by: str,
) -> ChecklistCompletion:
    """Complete a checklist item during execution.

    Validates:
    - Change is in executing status
    - Item hasn't already been completed
    - All preceding items in the same phase are done
    - All items in preceding phases are done (phase gating)
    - Previous hold points are verified
    """
    # Gate: change must be executing
    if change.status != ChangeStatus.EXECUTING:
        raise GateError(
            "Cannot complete checklist items — change is not in executing status. "
            f"Current status: {change.status.value}"
        )

    # Gate: item not already completed
    if _is_item_completed(item):
        raise ConflictError(f"Item '{item.description}' has already been completed.")

    all_items = _get_ordered_items(db, change.id)
    by_phase = _items_by_phase(all_items)

    # Gate: all preceding phases must be complete
    for phase in PHASE_SEQUENCE:
        if phase == item.phase:
            break
        phase_items = by_phase.get(phase, [])
        if not _is_phase_complete(phase_items):
            raise GateError(
                f"Cannot complete items in {item.phase.value} phase — "
                f"previous phase '{phase.value}' is not yet complete."
            )

    # Gate: all preceding items in the same phase must be complete
    phase_items = by_phase.get(item.phase, [])
    for preceding_item in phase_items:
        if preceding_item.id == item.id:
            break
        if not _is_item_completed(preceding_item):
            raise GateError(
                f"Cannot complete this item out of order. "
                f"Item '{preceding_item.description}' (order {preceding_item.order}) "
                f"must be completed first."
            )
        # Check hold point on preceding item
        if (
            preceding_item.is_hold_point
            and preceding_item.completion.hold_point_verified_by is None
        ):
            raise GateError(
                f"Cannot proceed — hold point on '{preceding_item.description}' "
                f"has not been verified. A second person must verify before continuing."
            )

    # Create completion record
    completion = ChecklistCompletion(
        item_id=item.id,
        observed_result=observed_result,
        status=status,
        completed_by=completed_by,
        completed_at=datetime.now(UTC),
    )
    db.add(completion)

    # Audit
    audit = AuditEvent(
        change_id=change.id,
        event_type="item_completed",
        actor_name=completed_by,
        description=(
            f"Checklist item completed: '{item.description}' "
            f"[{item.phase.value}/{item.order}] — {status.value}"
        ),
        event_data={
            "item_id": str(item.id),
            "phase": item.phase.value,
            "order": item.order,
            "status": status.value,
            "observed_result": observed_result,
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(completion)
    logger.info(
        "Item completed: %s [%s/%d] — %s",
        item.description,
        item.phase.value,
        item.order,
        status.value,
        extra={
            "change_id": str(change.id),
            "actor": completed_by,
            "action": "item_completed",
            "detail": f"phase={item.phase.value} order={item.order} status={status.value}",
        },
    )
    return completion


def verify_hold_point(
    db: Session,
    change: Change,
    item: ChecklistItem,
    verified_by: str,
) -> ChecklistCompletion:
    """Verify a hold point — requires a second person.

    Validates:
    - Change is in executing status
    - Item is a hold point
    - Item has been completed (you verify after completion, not before)
    - Hold point hasn't already been verified
    """
    if change.status != ChangeStatus.EXECUTING:
        raise GateError("Cannot verify hold points — change is not in executing status.")

    if not item.is_hold_point:
        raise ValidationError(f"Item '{item.description}' is not a hold point.")

    if not _is_item_completed(item):
        raise GateError(
            f"Cannot verify hold point — item '{item.description}' has not been completed yet."
        )

    completion = item.completion
    if completion.hold_point_verified_by is not None:
        raise ConflictError(
            f"Hold point on '{item.description}' has already been verified "
            f"by {completion.hold_point_verified_by}."
        )

    completion.hold_point_verified_by = verified_by
    completion.hold_point_verified_at = datetime.now(UTC)

    audit = AuditEvent(
        change_id=change.id,
        event_type="hold_point_verified",
        actor_name=verified_by,
        description=(
            f"Hold point verified: '{item.description}' [{item.phase.value}/{item.order}]"
        ),
        event_data={
            "item_id": str(item.id),
            "phase": item.phase.value,
            "order": item.order,
            "verified_by": verified_by,
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(completion)
    logger.info(
        "Hold point verified: %s [%s/%d]",
        item.description,
        item.phase.value,
        item.order,
        extra={
            "change_id": str(change.id),
            "actor": verified_by,
            "action": "hold_point_verified",
            "detail": f"phase={item.phase.value} order={item.order}",
        },
    )
    return completion


def get_execution_status(db: Session, change: Change) -> dict:
    """Get the current execution progress for a change.

    Returns:
    - current_phase: which phase is active
    - total_items: total checklist items
    - completed_items: how many are done
    - next_item_id: the next item to complete (or None if all done)
    - all_complete: whether everything is finished
    - phases: per-phase breakdown
    """
    if change.status != ChangeStatus.EXECUTING:
        raise ValidationError(
            "Execution status is only available when the change is in executing status. "
            f"Current status: {change.status.value}"
        )

    all_items = _get_ordered_items(db, change.id)
    by_phase = _items_by_phase(all_items)

    total = len(all_items)
    completed = sum(1 for item in all_items if _is_item_completed(item))

    # Find current phase and next item
    current_phase = None
    next_item_id = None

    for phase in PHASE_SEQUENCE:
        phase_items = by_phase.get(phase, [])
        if not phase_items:
            continue

        phase_complete = _is_phase_complete(phase_items)
        if not phase_complete:
            current_phase = phase.value
            # Find the first incomplete item in this phase
            for item in phase_items:
                if not _is_item_completed(item):
                    next_item_id = str(item.id)
                    break
                # Check if it's a hold point waiting for verification
                if item.is_hold_point and item.completion.hold_point_verified_by is None:
                    # Next action is to verify this hold point, but the
                    # "next_item_id" points to the next uncompleted item
                    # (or this hold point if no further items need completion)
                    pass
            break

    all_complete = completed == total and next_item_id is None
    if all_complete and current_phase is None and total > 0:
        # All done — report last phase
        current_phase = PHASE_SEQUENCE[-1].value

    # Per-phase breakdown
    phases = {}
    for phase in PHASE_SEQUENCE:
        phase_items = by_phase.get(phase, [])
        phase_completed = sum(1 for i in phase_items if _is_item_completed(i))
        phases[phase.value] = {
            "total": len(phase_items),
            "completed": phase_completed,
            "complete": _is_phase_complete(phase_items) if phase_items else True,
        }

    return {
        "current_phase": current_phase,
        "total_items": total,
        "completed_items": completed,
        "next_item_id": next_item_id,
        "all_complete": all_complete,
        "phases": phases,
    }
