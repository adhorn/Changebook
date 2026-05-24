import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PortableUUID, TimestampMixin, UUIDMixin


class Customer(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("organisations.id"), nullable=False
    )

    organisation: Mapped["Organisation"] = relationship(  # noqa: F821
        back_populates="customers"
    )
    services: Mapped[list["Service"]] = relationship(back_populates="customer")
    environments: Mapped[list["Environment"]] = relationship(  # noqa: F821
        back_populates="customer"
    )


class Service(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "services"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("customers.id"), nullable=False
    )

    customer: Mapped["Customer"] = relationship(back_populates="services")
