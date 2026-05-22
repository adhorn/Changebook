import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EnvironmentCreate(BaseModel):
    name: str
    platform: str | None = None
    description: str | None = None
    organisation_id: uuid.UUID


class EnvironmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    platform: str | None
    description: str | None
    organisation_id: uuid.UUID
    created_at: datetime
