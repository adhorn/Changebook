import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.review import ReviewDecision


class ReviewerAssign(BaseModel):
    reviewer_name: str


class ReviewDecisionSubmit(BaseModel):
    decision: ReviewDecision
    comment: str | None = None


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    change_id: uuid.UUID
    reviewer_name: str
    decision: ReviewDecision
    comment: str | None
    created_at: datetime
    updated_at: datetime
