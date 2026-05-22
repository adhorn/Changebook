import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EnvironmentCreate(BaseModel):
    name: str
    platform: str | None = None
    description: str | None = None
    # organisation_id is auto-injected by the backend (invisible tenant)
    customer_id: uuid.UUID | None = None


class EnvironmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    platform: str | None
    description: str | None
    organisation_id: uuid.UUID
    customer_id: uuid.UUID | None
    created_at: datetime
