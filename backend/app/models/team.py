import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PortableUUID, TimestampMixin, UUIDMixin


class Team(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("organisations.id"), nullable=False
    )

    organisation: Mapped["Organisation"] = relationship(back_populates="teams")  # noqa: F821
    changes: Mapped[list["Change"]] = relationship(back_populates="team")  # noqa: F821
