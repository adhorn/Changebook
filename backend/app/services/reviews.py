import uuid

from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.review import Review, ReviewDecision


def assign_reviewer(
    db: Session, change_id: uuid.UUID, reviewer_name: str
) -> Review:
    # Check for duplicate
    existing = (
        db.query(Review)
        .filter(
            Review.change_id == change_id,
            Review.reviewer_name == reviewer_name,
        )
        .first()
    )
    if existing:
        raise ValueError(f"Reviewer '{reviewer_name}' is already assigned")

    review = Review(
        change_id=change_id,
        reviewer_name=reviewer_name,
        decision=ReviewDecision.PENDING,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def list_reviews(db: Session, change_id: uuid.UUID) -> list[Review]:
    return (
        db.query(Review)
        .filter(Review.change_id == change_id)
        .order_by(Review.created_at)
        .all()
    )


def get_review(
    db: Session, change_id: uuid.UUID, review_id: uuid.UUID
) -> Review | None:
    return (
        db.query(Review)
        .filter(Review.id == review_id, Review.change_id == change_id)
        .first()
    )


def submit_decision(
    db: Session,
    review: Review,
    decision: ReviewDecision,
    comment: str | None,
) -> Review:
    review.decision = decision
    review.comment = comment

    audit = AuditEvent(
        change_id=review.change_id,
        event_type="review_submitted",
        actor_name=review.reviewer_name,
        description=(
            f"Review by {review.reviewer_name}: {decision.value}"
            + (f" — {comment}" if comment else "")
        ),
        event_data={
            "review_id": str(review.id),
            "decision": decision.value,
            "comment": comment,
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(review)
    return review


def all_approved(db: Session, change_id: uuid.UUID) -> bool:
    """Check if all assigned reviewers have approved."""
    reviews = list_reviews(db, change_id)
    if not reviews:
        return False
    return all(r.decision == ReviewDecision.APPROVED for r in reviews)


def invalidate_reviews(db: Session, change_id: uuid.UUID) -> None:
    """Reset all reviews to pending. Called when the change is edited after approval."""
    reviews = list_reviews(db, change_id)
    for review in reviews:
        if review.decision != ReviewDecision.PENDING:
            review.decision = ReviewDecision.PENDING
            review.comment = None

    if reviews:
        audit = AuditEvent(
            change_id=change_id,
            event_type="reviews_invalidated",
            actor_name="system",
            description="All reviews reset to pending due to change edit",
            event_data={
                "reviewers_affected": [r.reviewer_name for r in reviews],
            },
        )
        db.add(audit)

    db.commit()
