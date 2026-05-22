"""Unified checklist item model for all three phases.

Every change has three checklists: pre_flight, execution, verification.
Each item is one action or one check. Same structure across all phases.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PortableUUID, TimestampMixin, UUIDMixin


class ChecklistPhase(enum.StrEnum):
    PRE_FLIGHT = "pre_flight"
    EXECUTION = "execution"
    VERIFICATION = "verification"


class CompletionStatus(enum.StrEnum):
    COMPLETED = "completed"
    FLAGGED = "flagged"
    SKIPPED_WITH_JUSTIFICATION = "skipped_with_justification"


class ChecklistItem(UUIDMixin, TimestampMixin, Base):
    """A single item in a checklist. One command, one action, one check."""

    __tablename__ = "checklist_items"

    change_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("changes.id"), nullable=False
    )
    phase: Mapped[ChecklistPhase] = mapped_column(
        Enum(ChecklistPhase), nullable=False
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False)

    # What to do
    description: Mapped[str] = mapped_column(Text, nullable=False)
    command: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    rollback_action: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Hold point: execution pauses here until independent verification
    is_hold_point: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Relationships
    change: Mapped["Change"] = relationship(back_populates="checklist_items")  # noqa: F821
    completion: Mapped["ChecklistCompletion | None"] = relationship(
        back_populates="item", uselist=False
    )


class ChecklistCompletion(UUIDMixin, TimestampMixin, Base):
    """Recorded when an operator completes a checklist item during execution.

    The observed_result is the read-back: what the operator actually saw,
    not just that they did it.
    """

    __tablename__ = "checklist_completions"

    item_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("checklist_items.id"), nullable=False, unique=True
    )

    # The read-back — what the operator observed
    observed_result: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[CompletionStatus] = mapped_column(
        Enum(CompletionStatus), nullable=False
    )

    # Who completed it
    completed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Hold point verification (by a second person)
    hold_point_verified_by: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    hold_point_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    item: Mapped["ChecklistItem"] = relationship(back_populates="completion")
