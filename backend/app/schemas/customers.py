import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ServiceCreate(BaseModel):
    name: str
    description: str | None = None


class CustomerCreate(BaseModel):
    name: str
    description: str | None = None
    # organisation_id is auto-injected by the backend (invisible tenant)
    services: list[ServiceCreate] | None = None


class ServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    customer_id: uuid.UUID
    created_at: datetime


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    organisation_id: uuid.UUID
    created_at: datetime


class CustomerDetailResponse(CustomerResponse):
    services: list[ServiceResponse] = []
