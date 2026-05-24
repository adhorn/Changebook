from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Organisation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "organisations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    teams: Mapped[list["Team"]] = relationship(back_populates="organisation")  # noqa: F821
    customers: Mapped[list["Customer"]] = relationship(  # noqa: F821
        back_populates="organisation"
    )
    environments: Mapped[list["Environment"]] = relationship(  # noqa: F821
        back_populates="organisation"
    )
