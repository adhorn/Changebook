"""Reusable change templates — procedures without context.

A template captures the "how" of a change (checklist, defence tags,
general preflight answers) without the "who/where/when" (customer,
service, environment, maintenance window). Operators browse the
library and click "Use" to start a new draft pre-filled with the
template's procedure.
"""

import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.checklist import ChecklistPhase


class ChangeTemplate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "change_templates"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Procedure metadata
    defence_tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    preflight_answers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Provenance — which change was this saved from (nullable for manual creation)
    source_change_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("changes.id"), nullable=True
    )

    # Who created the template
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    items: Mapped[list["TemplateChecklistItem"]] = relationship(
        back_populates="template",
        order_by="TemplateChecklistItem.phase, TemplateChecklistItem.order",
        cascade="all, delete-orphan",
    )


class TemplateChecklistItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "template_checklist_items"

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("change_templates.id"), nullable=False
    )
    phase: Mapped[ChecklistPhase] = mapped_column(Enum(ChecklistPhase), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=False)
    command: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    rollback_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_hold_point: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Deviation tracking: was this step added during execution?
    added_during_execution: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Relationships
    template: Mapped["ChangeTemplate"] = relationship(back_populates="items")
