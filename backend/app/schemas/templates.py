import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.change import ALLOWED_DEFENCE_TAGS

# --- Checklist item sub-schemas ---


class TemplateChecklistItemCreate(BaseModel):
    phase: str
    description: str
    command: str | None = None
    expected_outcome: str | None = None
    rollback_action: str | None = None
    is_hold_point: bool = False


class TemplateChecklistItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phase: str
    order: int
    description: str
    command: str | None
    expected_outcome: str | None
    rollback_action: str | None
    is_hold_point: bool


# --- Template schemas ---


class TemplateCreate(BaseModel):
    title: str
    description: str | None = None
    defence_tags: list[str] | None = None
    preflight_answers: dict | None = None
    items: list[TemplateChecklistItemCreate] | None = None

    @field_validator("defence_tags")
    @classmethod
    def validate_defence_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        invalid = [tag for tag in v if tag not in ALLOWED_DEFENCE_TAGS]
        if invalid:
            raise ValueError(f"Invalid defence tags: {invalid}")
        return v


class SaveAsTemplate(BaseModel):
    """When saving an existing change as a template."""

    title: str | None = None
    description: str | None = None


class UseTemplate(BaseModel):
    """When creating a new change from a template."""

    title: str
    customer_id: uuid.UUID
    service_id: uuid.UUID
    environment_id: uuid.UUID


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    defence_tags: list[str] | None
    preflight_answers: dict | None
    source_change_id: uuid.UUID | None
    author_name: str
    item_count: int = 0
    created_at: datetime
    updated_at: datetime


class TemplateDetailResponse(TemplateResponse):
    items: list[TemplateChecklistItemResponse] = []
