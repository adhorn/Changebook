import logging
import uuid

from sqlalchemy.orm import Session

from app.models.change import Change, ChangeStatus
from app.models.checklist import ChecklistItem
from app.models.template import ChangeTemplate, TemplateChecklistItem

logger = logging.getLogger(__name__)

# Preflight keys that describe the procedure (reusable across contexts).
# Customer-specific and timing-specific keys are excluded from templates.
GENERAL_PREFLIGHT_KEYS = {
    "what_is_this_change",
    "expected_outcome",
    "what_if_fails",
    "rollback_plan",
    "rollback_duration",
    "blast_radius",
    "dependencies",
}


def _filter_general_preflight(
    answers: dict[str, str] | None,
) -> dict[str, str] | None:
    """Keep only the general (procedure-level) preflight answers."""
    if not answers:
        return None
    filtered = {k: v for k, v in answers.items() if k in GENERAL_PREFLIGHT_KEYS}
    return filtered or None


def create_template(db: Session, data: dict, author_name: str) -> ChangeTemplate:
    items_data = data.pop("items", None) or []
    template = ChangeTemplate(author_name=author_name, **data)
    db.add(template)
    db.flush()

    for i, item_data in enumerate(items_data, start=1):
        item = TemplateChecklistItem(
            template_id=template.id,
            order=i,
            **item_data,
        )
        db.add(item)

    db.commit()
    db.refresh(template)
    logger.info(
        "Template created: %s",
        template.title,
        extra={"actor": author_name, "action": "template_created"},
    )
    return template


def save_change_as_template(
    db: Session,
    change: Change,
    title: str | None,
    description: str | None,
    author_name: str,
) -> ChangeTemplate:
    """Extract the procedure from a change into a reusable template."""
    template = ChangeTemplate(
        title=title or f"{change.title} (template)",
        description=description or change.description,
        defence_tags=change.defence_tags,
        preflight_answers=_filter_general_preflight(change.preflight_answers),
        source_change_id=change.id,
        author_name=author_name,
    )
    db.add(template)
    db.flush()

    # Copy checklist items — procedure only, no completions
    source_items = (
        db.query(ChecklistItem)
        .filter(ChecklistItem.change_id == change.id)
        .order_by(ChecklistItem.phase, ChecklistItem.order)
        .all()
    )
    for item in source_items:
        db.add(
            TemplateChecklistItem(
                template_id=template.id,
                phase=item.phase,
                order=item.order,
                description=item.description,
                command=item.command,
                expected_outcome=item.expected_outcome,
                rollback_action=item.rollback_action,
                is_hold_point=item.is_hold_point,
            )
        )

    db.commit()
    db.refresh(template)
    logger.info(
        "Template saved from change",
        extra={
            "change_id": str(change.id),
            "actor": author_name,
            "action": "template_from_change",
        },
    )
    return template


def create_change_from_template(
    db: Session,
    template: ChangeTemplate,
    title: str,
    customer_id: uuid.UUID,
    service_id: uuid.UUID,
    environment_id: uuid.UUID,
    author_name: str,
) -> Change:
    """Instantiate a template into a new draft change."""
    change = Change(
        title=title,
        description=template.description,
        status=ChangeStatus.DRAFT,
        customer_id=customer_id,
        service_id=service_id,
        environment_id=environment_id,
        author_name=author_name,
        preflight_answers=template.preflight_answers,
        defence_tags=template.defence_tags,
    )
    db.add(change)
    db.flush()

    # Copy template checklist items into the change
    for item in template.items:
        db.add(
            ChecklistItem(
                change_id=change.id,
                phase=item.phase,
                order=item.order,
                description=item.description,
                command=item.command,
                expected_outcome=item.expected_outcome,
                rollback_action=item.rollback_action,
                is_hold_point=item.is_hold_point,
            )
        )

    db.commit()
    db.refresh(change)
    logger.info(
        "Change created from template",
        extra={
            "change_id": str(change.id),
            "actor": author_name,
            "action": "change_from_template",
            "detail": f"template={template.id}",
        },
    )
    return change


def list_templates(
    db: Session,
    title_search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ChangeTemplate], int]:
    query = db.query(ChangeTemplate)
    if title_search:
        query = query.filter(ChangeTemplate.title.ilike(f"%{title_search}%"))
    total = query.count()
    templates = query.order_by(ChangeTemplate.created_at.desc()).offset(offset).limit(limit).all()
    return templates, total


def get_template(db: Session, template_id: uuid.UUID) -> ChangeTemplate | None:
    return db.query(ChangeTemplate).filter(ChangeTemplate.id == template_id).first()
