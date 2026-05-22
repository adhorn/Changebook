import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PortableUUID, TimestampMixin, UUIDMixin


class Environment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "environments"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("organisations.id"), nullable=False
    )

    organisation: Mapped["Organisation"] = relationship(  # noqa: F821
        back_populates="environments"
    )
