import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PortableJSON, PortableUUID, TimestampMixin, UUIDMixin


class AuditEvent(UUIDMixin, TimestampMixin, Base):
    """Immutable, append-only audit log.

    Every state transition, step completion, review action, and verification
    is recorded here. This table must never have UPDATE or DELETE operations.
    """

    __tablename__ = "audit_events"

    change_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("changes.id"), nullable=False
    )

    # What happened
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # e.g. "status_changed", "step_completed", "review_submitted",
    #       "verification_completed", "change_created", "step_added"

    # Who did it
    actor_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Which environment (if applicable)
    environment_id: Mapped[uuid.UUID | None] = mapped_column(
        PortableUUID, ForeignKey("environments.id"), nullable=True
    )

    # Human-readable description
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Structured data about the event (old/new status, step details, etc)
    event_data: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)

    change: Mapped["Change"] = relationship(back_populates="audit_events")  # noqa: F821
