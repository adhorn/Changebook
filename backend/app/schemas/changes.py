import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.change import ChangeStatus


# --- Request schemas ---


class StepCreate(BaseModel):
    description: str
    expected_outcome: str | None = None
    rollback_action: str | None = None
    script: str | None = None
    is_hold_point: bool = False


class ChangeCreate(BaseModel):
    title: str
    description: str | None = None
    team_id: uuid.UUID
    author_name: str
    environment_ids: list[uuid.UUID] | None = None
    preflight_answers: dict | None = None
    defence_tags: list[str] | None = None
    steps: list[StepCreate] | None = None


class ChangeUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    preflight_answers: dict | None = None
    defence_tags: list[str] | None = None
    environment_ids: list[uuid.UUID] | None = None


# --- Response schemas ---


class StepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order: int
    description: str
    expected_outcome: str | None
    rollback_action: str | None
    script: str | None
    is_hold_point: bool
    created_at: datetime


class ChangeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    status: ChangeStatus
    team_id: uuid.UUID
    author_name: str
    environment_ids: list[uuid.UUID] | None
    preflight_answers: dict | None
    defence_tags: list[str] | None
    created_at: datetime
    updated_at: datetime


class ChangeDetailResponse(ChangeResponse):
    steps: list[StepResponse] = []


class ChangeListResponse(BaseModel):
    data: list[ChangeResponse]
    meta: dict
