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
    created_at: datetime


class ChecklistItemUpdate(BaseModel):
    description: str | None = None
    command: str | None = None
    expected_outcome: str | None = None
    rollback_action: str | None = None
    is_hold_point: bool | None = None


class ChecklistReorder(BaseModel):
    phase: ChecklistPhase
    item_ids: list[uuid.UUID]


class ChecklistCompletionCreate(BaseModel):
    observed_result: str
    status: CompletionStatus
    completed_by: str


class ChecklistCompletionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_id: uuid.UUID
    observed_result: str
    status: CompletionStatus
    completed_by: str
    completed_at: datetime
    hold_point_verified_by: str | None
    hold_point_verified_at: datetime | None
