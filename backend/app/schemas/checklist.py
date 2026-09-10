import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.checklist import ChecklistPhase, CompletionStatus


class ChecklistItemCreate(BaseModel):
    phase: ChecklistPhase
    description: str
    command: str | None = None
    expected_outcome: str | None = None
    rollback_action: str | None = None
    is_hold_point: bool = False


class ChecklistCompletionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_id: uuid.UUID
    observed_result: str
    status: CompletionStatus
    completed_by: str
    completed_at: datetime


class ChecklistItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    change_id: uuid.UUID
    phase: ChecklistPhase
    order: int
    description: str
    command: str | None
    expected_outcome: str | None
    rollback_action: str | None
    is_hold_point: bool
    hold_point_verified_by: str | None = None
    hold_point_verified_at: datetime | None = None
    added_during_execution: bool = False
    created_at: datetime
    completion: ChecklistCompletionResponse | None = None


class ChecklistItemUpdate(BaseModel):
    description: str | None = None
    command: str | None = None
    expected_outcome: str | None = None
    rollback_action: str | None = None
    is_hold_point: bool | None = None


class ChecklistReorder(BaseModel):
    phase: ChecklistPhase
    item_ids: list[uuid.UUID]


class ExecutionStepCreate(BaseModel):
    """Add a step during execution — inserted after a completed item."""

    insert_after_item_id: uuid.UUID
    description: str
    command: str | None = None
    expected_outcome: str | None = None
    rollback_action: str | None = None
    is_hold_point: bool = False


class ChecklistCompletionCreate(BaseModel):
    observed_result: str
    status: CompletionStatus
    completed_by: str | None = None  # Injected from auth headers


class HoldPointVerify(BaseModel):
    verified_by: str  # Name of the person who verified (typed by operator)


class PhaseStatus(BaseModel):
    total: int
    completed: int
    complete: bool


class ExecutionStatusResponse(BaseModel):
    current_phase: str | None
    total_items: int
    completed_items: int
    next_item_id: str | None
    all_complete: bool
    phases: dict[str, PhaseStatus]
