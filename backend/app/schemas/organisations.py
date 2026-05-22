import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OrganisationCreate(BaseModel):
    name: str


class TeamCreate(BaseModel):
    name: str
    organisation_id: uuid.UUID


class OrganisationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_at: datetime


class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    organisation_id: uuid.UUID
    created_at: datetime
