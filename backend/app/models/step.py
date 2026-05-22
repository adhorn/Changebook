import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PortableJSON, PortableUUID, TimestampMixin, UUIDMixin


class StepStatus(enum.StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Step(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "steps"

    change_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("changes.id"), nullable=False
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False)

    # Step definition
    description: Mapped[str] = mapped_column(Text, nullable=False)
    expected_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    rollback_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    script: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Hold point: execution pauses here until independent verification
    is_hold_point: Mapped[bool] = mapped_column(default=False, nullable=False)
    hold_point_verified_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hold_point_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    change: Mapped["Change"] = relationship(back_populates="steps")  # noqa: F821
    completions: Mapped[list["StepCompletion"]] = relationship(back_populates="step")


class StepCompletion(UUIDMixin, TimestampMixin, Base):
    """Tracks step completion per environment.

    A step may be completed once (single environment) or many times
    (one per target environment in a multi-environment change).
    """

    __tablename__ = "step_completions"

    step_id: Mapped[uuid.UUID] = mapped_column(PortableUUID, ForeignKey("steps.id"), nullable=False)
    environment_id: Mapped[uuid.UUID | None] = mapped_column(
        PortableUUID, ForeignKey("environments.id"), nullable=True
    )

    status: Mapped[StepStatus] = mapped_column(
        Enum(StepStatus), default=StepStatus.PENDING, nullable=False
    )
    completed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)

    # If something went wrong
    issue_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    step: Mapped["Step"] = relationship(back_populates="completions")
