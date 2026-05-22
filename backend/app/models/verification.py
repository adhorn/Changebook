import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PortableJSON, PortableUUID, TimestampMixin, UUIDMixin


class Verification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "verifications"

    change_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("changes.id"), nullable=False
    )
    environment_id: Mapped[uuid.UUID | None] = mapped_column(
        PortableUUID, ForeignKey("environments.id"), nullable=True
    )

    # What to check
    check_description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(
        String(50), default="system", nullable=False
    )  # "system" or "customer"

    # Result
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)

    change: Mapped["Change"] = relationship(back_populates="verifications")  # noqa: F821
