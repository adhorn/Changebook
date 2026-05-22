import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PortableJSON, PortableUUID, TimestampMixin, UUIDMixin


class ChangeStatus(str, enum.Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    EXECUTING = "executing"
    AWAITING_VERIFICATION = "awaiting_verification"
    VERIFIED = "verified"
    CLOSED = "closed"
    ABORTED = "aborted"


class Change(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "changes"

    # Core fields
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ChangeStatus] = mapped_column(
        Enum(ChangeStatus), default=ChangeStatus.DRAFT, nullable=False
    )

    # Ownership
    team_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("teams.id"), nullable=False
    )
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Environments targeted by this change (list of UUID strings as JSON)
    environment_ids: Mapped[list | None] = mapped_column(PortableJSON, nullable=True)

    # Pre-flight answers stored as PortableJSON for flexibility
    preflight_answers: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)

    # Defence tags (monitoring, alerting, security, access control, DR, backup)
    defence_tags: Mapped[list | None] = mapped_column(PortableJSON, nullable=True)

    # Relationships
    team: Mapped["Team"] = relationship(back_populates="changes")  # noqa: F821
    steps: Mapped[list["Step"]] = relationship(  # noqa: F821
        back_populates="change", order_by="Step.order"
    )
    reviews: Mapped[list["Review"]] = relationship(back_populates="change")  # noqa: F821
    verifications: Mapped[list["Verification"]] = relationship(  # noqa: F821
        back_populates="change"
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(  # noqa: F821
        back_populates="change"
    )
