import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PortableUUID, TimestampMixin, UUIDMixin


class ReviewDecision(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    BLOCKED = "blocked"


class Review(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reviews"

    change_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("changes.id"), nullable=False
    )
    reviewer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    decision: Mapped[ReviewDecision] = mapped_column(
        Enum(ReviewDecision), default=ReviewDecision.PENDING, nullable=False
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    change: Mapped["Change"] = relationship(back_populates="reviews")  # noqa: F821
