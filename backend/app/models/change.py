import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ChangeStatus(enum.StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    EXECUTING = "executing"
    DONE = "done"
    ABORTED = "aborted"


# Predefined defence tags. Operators pick from this list. No free-text.
ALLOWED_DEFENCE_TAGS = [
    "monitoring",
    "alerting",
    "security",
    "access_control",
    "DR",
    "backup",
    "networking",
    "database",
    "application",
]


class Change(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "changes"

    # Core fields
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ChangeStatus] = mapped_column(
        Enum(ChangeStatus), default=ChangeStatus.DRAFT, nullable=False
    )

    # Who and where — one customer, one service, one environment per change
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id"), nullable=False
    )
    environment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("environments.id"), nullable=False
    )

    # Author (free text in v1, derived from SSO later)
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Pre-flight answers stored as JSONB for flexibility
    preflight_answers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Tracks which version of the question schema the answers were written against
    preflight_schema_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # When pre-flight answers were last written (for 24h staleness check)
    preflight_answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Structured maintenance window — stored as UTC, tz records display timezone
    maintenance_window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    maintenance_window_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    maintenance_window_tz: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Defence tags — validated against ALLOWED_DEFENCE_TAGS
    defence_tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Abort reason — recorded when the change is aborted
    abort_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Duplicate flow — reference to the change this was cloned from
    cloned_from: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("changes.id"), nullable=True
    )

    # Relationships
    customer: Mapped["Customer"] = relationship(foreign_keys=[customer_id])  # noqa: F821
    service: Mapped["Service"] = relationship(foreign_keys=[service_id])  # noqa: F821
    environment: Mapped["Environment"] = relationship(  # noqa: F821
        foreign_keys=[environment_id]
    )
    checklist_items: Mapped[list["ChecklistItem"]] = relationship(  # noqa: F821
        back_populates="change", order_by="ChecklistItem.phase, ChecklistItem.order"
    )
    reviews: Mapped[list["Review"]] = relationship(back_populates="change")  # noqa: F821
    audit_events: Mapped[list["AuditEvent"]] = relationship(  # noqa: F821
        back_populates="change"
    )

    # Derived properties for response serialisation
    @property
    def customer_name(self) -> str | None:
        return self.customer.name if self.customer else None

    @property
    def service_name(self) -> str | None:
        return self.service.name if self.service else None

    @property
    def environment_name(self) -> str | None:
        return self.environment.name if self.environment else None

    @property
    def environment_platform(self) -> str | None:
        return self.environment.platform if self.environment else None
