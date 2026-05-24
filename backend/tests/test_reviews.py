"""Tests for Feature 5: Review workflow.

Reviewers are assigned to a change. All must approve before the change
can transition to approved. Any edit after approval resets all reviews.
"""


def _complete_preflight(client):
    resp = client.get("/api/v1/preflight-questions")
    keys = []
    for section in resp.json()["sections"]:
        for q in section["questions"]:
            if q["required"]:
                keys.append(q["key"])
    return {key: f"Answer for {key}" for key in keys}


def _create_review_ready_change(client, sample_change_data):
    """Create a change that's ready for review (preflight + all phases)."""
    resp = client.post(
        "/api/v1/changes",
        json={
            "title": "Review test change",
            "author_name": "Adrian Hornsby",
            **sample_change_data,
            "preflight_answers": _complete_preflight(client),
        },
    )
    change_id = resp.json()["id"]
    for phase in ["pre_flight", "execution", "verification"]:
        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": phase, "description": f"{phase} step"},
        )
    return change_id


def _submit_for_review(client, change_id):
    """Transition a change to in_review."""
    client.post(
        f"/api/v1/changes/{change_id}/transition",
        params={"target_status": "in_review", "actor_name": "Adrian Hornsby"},
    )


class TestAssignReviewers:
    """POST /api/v1/changes/{id}/reviewers"""

    def test_assign_reviewer(self, client, sample_change_data):
        """A reviewer can be assigned to a change."""
        change_id = _create_review_ready_change(client, sample_change_data)

        resp = client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "Jane Smith"},
        )
        assert resp.status_code == 201
        assert resp.json()["reviewer_name"] == "Jane Smith"
        assert resp.json()["decision"] == "pending"

    def test_assign_multiple_reviewers(self, client, sample_change_data):
        """Multiple reviewers can be assigned."""
        change_id = _create_review_ready_change(client, sample_change_data)

        client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "Jane Smith"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "Bob Johnson"},
        )

        resp = client.get(f"/api/v1/changes/{change_id}/reviewers")
        assert resp.status_code == 200
        assert len(resp.json()) == 2
        names = {r["reviewer_name"] for r in resp.json()}
        assert names == {"Jane Smith", "Bob Johnson"}

    def test_cannot_assign_duplicate_reviewer(self, client, sample_change_data):
        """The same reviewer cannot be assigned twice."""
        change_id = _create_review_ready_change(client, sample_change_data)

        client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "Jane Smith"},
        )
        resp = client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "Jane Smith"},
        )
        assert resp.status_code == 422

    def test_list_reviewers_empty(self, client, sample_change_data):
        """A change with no reviewers returns an empty list."""
        change_id = _create_review_ready_change(client, sample_change_data)

        resp = client.get(f"/api/v1/changes/{change_id}/reviewers")
        assert resp.status_code == 200
        assert resp.json() == []


class TestSubmitReview:
    """POST /api/v1/changes/{id}/reviewers/{review_id}/decision"""

    def test_approve(self, client, sample_change_data):
        """A reviewer can approve a change."""
        change_id = _create_review_ready_change(client, sample_change_data)
        _submit_for_review(client, change_id)

        review = client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "Jane Smith"},
        )
        review_id = review.json()["id"]

        resp = client.post(
            f"/api/v1/changes/{change_id}/reviewers/{review_id}/decision",
            json={
                "decision": "approved",
                "comment": "Looks good, well thought out.",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["decision"] == "approved"
        assert resp.json()["comment"] == "Looks good, well thought out."

    def test_request_changes(self, client, sample_change_data):
        """A reviewer can request changes."""
        change_id = _create_review_ready_change(client, sample_change_data)
        _submit_for_review(client, change_id)

        review = client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "Jane Smith"},
        )
        review_id = review.json()["id"]

        resp = client.post(
            f"/api/v1/changes/{change_id}/reviewers/{review_id}/decision",
            json={
                "decision": "changes_requested",
                "comment": "Rollback plan needs more detail.",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["decision"] == "changes_requested"

    def test_block(self, client, sample_change_data):
        """A reviewer can block a change."""
        change_id = _create_review_ready_change(client, sample_change_data)
        _submit_for_review(client, change_id)

        review = client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "VP Risk"},
        )
        review_id = review.json()["id"]

        resp = client.post(
            f"/api/v1/changes/{change_id}/reviewers/{review_id}/decision",
            json={
                "decision": "blocked",
                "comment": "Not during quarter-end processing.",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["decision"] == "blocked"

    def test_cannot_review_non_review_status(self, client, sample_change_data):
        """Reviews can only be submitted when the change is in_review."""
        change_id = _create_review_ready_change(client, sample_change_data)
        # Still in draft — not yet submitted

        review = client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "Jane Smith"},
        )
        review_id = review.json()["id"]

        resp = client.post(
            f"/api/v1/changes/{change_id}/reviewers/{review_id}/decision",
            json={"decision": "approved"},
        )
        assert resp.status_code == 422


class TestApprovalGate:
    """Transition to approved requires all reviewers to have approved."""

    def test_cannot_approve_without_reviewers(self, client, sample_change_data):
        """A change with no reviewers cannot transition to approved."""
        change_id = _create_review_ready_change(client, sample_change_data)
        _submit_for_review(client, change_id)

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "approved", "actor_name": "Adrian Hornsby"},
        )
        assert resp.status_code == 422
        assert "review" in resp.json()["detail"].lower()

    def test_cannot_approve_with_pending_reviews(self, client, sample_change_data):
        """Cannot approve when some reviewers haven't decided yet."""
        change_id = _create_review_ready_change(client, sample_change_data)
        _submit_for_review(client, change_id)

        r1 = client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "Jane Smith"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "Bob Johnson"},
        )

        # Only one approves
        client.post(
            f"/api/v1/changes/{r1.json()['id']}/reviewers/{r1.json()['id']}/decision",
            json={"decision": "approved"},
        )

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "approved", "actor_name": "Adrian Hornsby"},
        )
        assert resp.status_code == 422

    def test_cannot_approve_with_block(self, client, sample_change_data):
        """A single block prevents approval even if others approved."""
        change_id = _create_review_ready_change(client, sample_change_data)
        _submit_for_review(client, change_id)

        r1 = client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "Jane Smith"},
        )
        r2 = client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "VP Risk"},
        )

        client.post(
            f"/api/v1/changes/{change_id}/reviewers/{r1.json()['id']}/decision",
            json={"decision": "approved"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/reviewers/{r2.json()['id']}/decision",
            json={"decision": "blocked", "comment": "No."},
        )

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "approved", "actor_name": "Adrian Hornsby"},
        )
        assert resp.status_code == 422

    def test_all_approved_allows_transition(self, client, sample_change_data):
        """When all reviewers approve, the change can transition to approved."""
        change_id = _create_review_ready_change(client, sample_change_data)
        _submit_for_review(client, change_id)

        r1 = client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "Jane Smith"},
        )
        r2 = client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "Bob Johnson"},
        )

        client.post(
            f"/api/v1/changes/{change_id}/reviewers/{r1.json()['id']}/decision",
            json={"decision": "approved"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/reviewers/{r2.json()['id']}/decision",
            json={"decision": "approved"},
        )

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "approved", "actor_name": "Adrian Hornsby"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"


class TestIntegrityGuarantee:
    """Any edit after approval resets all reviews to pending."""

    def _get_change_approved(self, client, sample_change_data):
        """Helper: create a change, get it approved, return the change_id."""
        change_id = _create_review_ready_change(client, sample_change_data)
        _submit_for_review(client, change_id)

        review = client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "Jane Smith"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/reviewers/{review.json()['id']}/decision",
            json={"decision": "approved"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "approved", "actor_name": "Adrian Hornsby"},
        )
        return change_id

    def test_edit_after_approval_resets_reviews(self, client, sample_change_data):
        """Editing a change after approval sends it back to draft and resets reviews."""
        change_id = self._get_change_approved(client, sample_change_data)

        # Move back to draft to edit
        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "draft", "actor_name": "Adrian Hornsby"},
        )

        # Edit the change
        client.patch(
            f"/api/v1/changes/{change_id}",
            json={"title": "Updated after approval"},
        )

        # Check that all reviews are reset to pending
        reviews = client.get(f"/api/v1/changes/{change_id}/reviewers").json()
        assert len(reviews) == 1
        assert all(r["decision"] == "pending" for r in reviews)

    def test_edit_checklist_after_approval_resets_reviews(self, client, sample_change_data):
        """Editing checklist items after approval also resets reviews."""
        change_id = self._get_change_approved(client, sample_change_data)

        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "draft", "actor_name": "Adrian Hornsby"},
        )

        # Add a new checklist item
        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "execution", "description": "New step added post-approval"},
        )

        # Reviews should be reset
        reviews = client.get(f"/api/v1/changes/{change_id}/reviewers").json()
        assert all(r["decision"] == "pending" for r in reviews)

    def test_must_re_review_after_edit(self, client, sample_change_data):
        """After an edit resets reviews, cannot transition to approved without re-approval."""
        change_id = self._get_change_approved(client, sample_change_data)

        # Back to draft, edit, back to in_review
        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "draft", "actor_name": "Adrian Hornsby"},
        )
        client.patch(
            f"/api/v1/changes/{change_id}",
            json={"title": "Edited"},
        )
        _submit_for_review(client, change_id)

        # Try to approve — should fail, reviews are pending
        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "approved", "actor_name": "Adrian Hornsby"},
        )
        assert resp.status_code == 422


class TestReviewAuditTrail:
    """Review actions are recorded in the audit trail."""

    def test_review_decision_in_audit(self, client, sample_change_data, db):
        """Review decisions appear in the audit trail."""
        change_id = _create_review_ready_change(client, sample_change_data)
        _submit_for_review(client, change_id)

        review = client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "Jane Smith"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/reviewers/{review.json()['id']}/decision",
            json={"decision": "approved", "comment": "LGTM"},
        )

        from app.models.audit import AuditEvent

        events = (
            db.query(AuditEvent)
            .filter(
                AuditEvent.change_id == change_id,
                AuditEvent.event_type == "review_submitted",
            )
            .all()
        )
        assert len(events) == 1
        assert events[0].actor_name == "Jane Smith"
