import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PortableJSON, PortableUUID, TimestampMixin, UUIDMixin


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
        PortableUUID, ForeignKey("customers.id"), nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("services.id"), nullable=False
    )
    environment_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("environments.id"), nullable=False
    )

    # Author (free text in v1, derived from SSO later)
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Pre-flight answers stored as JSONB for flexibility
    preflight_answers: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)

    # Defence tags — validated against ALLOWED_DEFENCE_TAGS
    defence_tags: Mapped[list | None] = mapped_column(PortableJSON, nullable=True)

    # Duplicate flow — reference to the change this was cloned from
    cloned_from: Mapped[uuid.UUID | None] = mapped_column(
        PortableUUID, ForeignKey("changes.id"), nullable=True
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
