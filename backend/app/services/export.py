"""Markdown export service — renders a change as a structured document.

Produces a complete human-readable record: metadata, pre-flight answers,
checklist with completions, reviews, and audit trail.
"""

from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.change import Change
from app.models.checklist import ChecklistItem, ChecklistPhase
from app.models.preflight import PREFLIGHT_SECTIONS
from app.models.review import Review

PHASE_LABELS = {
    ChecklistPhase.PRE_FLIGHT: "Pre-flight",
    ChecklistPhase.EXECUTION: "Execution",
    ChecklistPhase.VERIFICATION: "Verification",
}

PHASE_ORDER = [
    ChecklistPhase.PRE_FLIGHT,
    ChecklistPhase.EXECUTION,
    ChecklistPhase.VERIFICATION,
]


def render_markdown(db: Session, change: Change) -> str:
    """Render a full change record as markdown."""
    sections = []

    # Title
    sections.append(f"# {change.title}")
    sections.append("")

    # Metadata
    sections.append("## Metadata")
    sections.append("")
    sections.append(f"- **Status:** {change.status.value}")
    sections.append(f"- **Author:** {change.author_name}")
    sections.append(f"- **Created:** {change.created_at}")
    if change.description:
        sections.append(f"- **Description:** {change.description}")
    if change.defence_tags:
        tags = ", ".join(change.defence_tags)
        sections.append(f"- **Defence tags:** {tags}")
    if change.cloned_from:
        sections.append(f"- **Cloned from:** {change.cloned_from}")
    sections.append("")

    # Pre-flight answers
    if change.preflight_answers:
        sections.append("## Pre-flight Answers")
        sections.append("")
        if change.preflight_schema_version:
            sections.append(f"*Schema version: {change.preflight_schema_version}*")
            sections.append("")

        # Render answers grouped by section, using the question labels
        question_map = {}
        for section in PREFLIGHT_SECTIONS:
            for q in section["questions"]:
                question_map[q["key"]] = q["label"]

        for key, answer in change.preflight_answers.items():
            label = question_map.get(key, key)
            sections.append(f"**{label}**")
            sections.append(f"> {answer}")
            sections.append("")

    # Checklist
    items = db.query(ChecklistItem).filter(ChecklistItem.change_id == change.id).all()
    if items:
        sections.append("## Checklist")
        sections.append("")

        # Group by phase
        by_phase: dict[ChecklistPhase, list[ChecklistItem]] = {}
        for item in items:
            by_phase.setdefault(item.phase, []).append(item)

        for phase in PHASE_ORDER:
            phase_items = by_phase.get(phase, [])
            if not phase_items:
                continue
            phase_items.sort(key=lambda i: i.order)

            sections.append(f"### {PHASE_LABELS[phase]}")
            sections.append("")

            for item in phase_items:
                hold = " 🔒" if item.is_hold_point else ""
                completion = item.completion

                if completion:
                    status_icon = {
                        "completed": "✅",
                        "flagged": "⚠️",
                        "skipped_with_justification": "⏭️",
                    }.get(completion.status.value, "❓")

                    sections.append(f"{item.order}. {status_icon} {item.description}{hold}")
                    sections.append(f"   - **Observed:** {completion.observed_result}")
                    sections.append(
                        f"   - **By:** {completion.completed_by} at {completion.completed_at}"
                    )
                    if item.is_hold_point and completion.hold_point_verified_by:
                        sections.append(
                            f"   - **Hold point verified by:** "
                            f"{completion.hold_point_verified_by} "
                            f"at {completion.hold_point_verified_at}"
                        )
                else:
                    sections.append(f"{item.order}. ⬜ {item.description}{hold}")

                if item.command:
                    sections.append(f"   - **Command:** `{item.command}`")
                if item.expected_outcome:
                    sections.append(f"   - **Expected:** {item.expected_outcome}")
                if item.rollback_action:
                    sections.append(f"   - **Rollback:** {item.rollback_action}")

            sections.append("")

    # Reviews
    reviews = db.query(Review).filter(Review.change_id == change.id).all()
    if reviews:
        sections.append("## Reviews")
        sections.append("")
        for review in reviews:
            decision_icon = {
                "approved": "✅",
                "changes_requested": "🔄",
                "blocked": "🚫",
                "pending": "⏳",
            }.get(review.decision.value, "❓")

            sections.append(
                f"- **{review.reviewer_name}:** {decision_icon} {review.decision.value}"
            )
            if review.comment:
                sections.append(f"  > {review.comment}")
        sections.append("")

    # Audit trail
    events = (
        db.query(AuditEvent)
        .filter(AuditEvent.change_id == change.id)
        .order_by(AuditEvent.created_at)
        .all()
    )
    if events:
        sections.append("## Audit Trail")
        sections.append("")
        sections.append("| Time | Event | Actor | Description |")
        sections.append("|------|-------|-------|-------------|")
        for event in events:
            desc = event.description or ""
            sections.append(
                f"| {event.created_at} | {event.event_type} | {event.actor_name} | {desc} |"
            )
        sections.append("")

    return "\n".join(sections)
