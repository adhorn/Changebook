import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.change import ALLOWED_DEFENCE_TAGS, ChangeStatus

# --- Request schemas ---


class ChangeCreate(BaseModel):
    title: str
    description: str | None = None
    customer_id: uuid.UUID
    service_id: uuid.UUID
    environment_id: uuid.UUID
    author_name: str
    preflight_answers: dict | None = None
    defence_tags: list[str] | None = None
    cloned_from: uuid.UUID | None = None

    @field_validator("defence_tags")
    @classmethod
    def validate_defence_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        invalid = [tag for tag in v if tag not in ALLOWED_DEFENCE_TAGS]
        if invalid:
            raise ValueError(
                f"Invalid defence tags: {invalid}. "
                f"Allowed tags: {ALLOWED_DEFENCE_TAGS}"
            )
        return v


class ChangeDuplicate(BaseModel):
    author_name: str
    title: str | None = None
    customer_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    environment_id: uuid.UUID | None = None


class ChangeUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    customer_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    environment_id: uuid.UUID | None = None
    preflight_answers: dict | None = None
    defence_tags: list[str] | None = None

    @field_validator("defence_tags")
    @classmethod
    def validate_defence_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        invalid = [tag for tag in v if tag not in ALLOWED_DEFENCE_TAGS]
        if invalid:
            raise ValueError(
                f"Invalid defence tags: {invalid}. "
                f"Allowed tags: {ALLOWED_DEFENCE_TAGS}"
            )
        return v


# --- Response schemas ---


class ChangeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    status: ChangeStatus
    customer_id: uuid.UUID
    service_id: uuid.UUID
    environment_id: uuid.UUID
    author_name: str
    preflight_answers: dict | None
    preflight_schema_version: str | None
    defence_tags: list[str] | None
    cloned_from: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    audit_event_count: int | None = None

    # Denormalised names from relationships
    customer_name: str | None = None
    service_name: str | None = None
    environment_name: str | None = None
    environment_platform: str | None = None


class ChangeDetailResponse(ChangeResponse):
    pass  # Will add checklist_items here in Feature 3


class ChangeListResponse(BaseModel):
    data: list[ChangeResponse]
    meta: dict
