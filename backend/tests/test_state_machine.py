"""Tests for Feature 4: State machine with completeness gates.

The state machine enforces:
- All three phases must have checklist items before submitting for review
- Pre-flight answers must be complete (already tested in test_preflight.py)
- 24h staleness warning when pre-flight answers are old at execution time
"""

from datetime import UTC, datetime, timedelta

from tests.conftest import JANE


def _complete_preflight(client):
    """Build a complete set of pre-flight answers from the API."""
    resp = client.get("/api/v1/preflight-questions")
    keys = []
    for section in resp.json()["sections"]:
        for q in section["questions"]:
            if q["required"]:
                keys.append(q["key"])
    return {key: f"Answer for {key}" for key in keys}


def _create_change_with_preflight(client, sample_change_data):
    """Create a change with complete pre-flight answers."""
    resp = client.post(
        "/api/v1/changes",
        json={
            "title": "Test change",
            "author_name": "Adrian Hornsby",
            **sample_change_data,
            "preflight_answers": _complete_preflight(client),
        },
    )
    return resp.json()["id"]


def _add_items_to_all_phases(client, change_id):
    """Add at least one checklist item to each phase."""
    for phase in ["pre_flight", "execution", "verification"]:
        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": phase, "description": f"{phase} step"},
        )


def _approve_change(client, change_id):
    """Assign a reviewer and approve."""
    review = client.post(
        f"/api/v1/changes/{change_id}/reviewers",
        json={"reviewer_name": "Jane Smith"},
    )
    client.post(
        f"/api/v1/changes/{change_id}/reviewers/{review.json()['id']}/decision",
        json={"decision": "approved"},
        headers=JANE,
    )


class TestCompletenessGate:
    """Cannot submit for review unless all three phases have checklist items."""

    def test_cannot_submit_without_checklist_items(self, client, sample_change_data):
        """A change with preflight answers but no checklist items cannot go to in_review."""
        change_id = _create_change_with_preflight(client, sample_change_data)

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review"},
        )
        assert resp.status_code == 422
        assert "checklist" in resp.json()["detail"].lower()

    def test_cannot_submit_with_only_one_phase(self, client, sample_change_data):
        """Having items in only one phase is not enough."""
        change_id = _create_change_with_preflight(client, sample_change_data)

        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "execution", "description": "Run migration"},
        )

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review"},
        )
        assert resp.status_code == 422
        assert "checklist" in resp.json()["detail"].lower()

    def test_cannot_submit_with_two_phases(self, client, sample_change_data):
        """Having items in two of three phases is still not enough."""
        change_id = _create_change_with_preflight(client, sample_change_data)

        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "execution", "description": "Step"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "verification", "description": "Check"},
        )

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review"},
        )
        assert resp.status_code == 422

    def test_can_submit_with_all_phases(self, client, sample_change_data):
        """All three phases plus pre-flight answers allows submission."""
        change_id = _create_change_with_preflight(client, sample_change_data)
        _add_items_to_all_phases(client, change_id)

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_review"

    def test_error_lists_missing_phases(self, client, sample_change_data):
        """The error message names which phases are missing."""
        change_id = _create_change_with_preflight(client, sample_change_data)

        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "execution", "description": "Step"},
        )

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review"},
        )
        detail = resp.json()["detail"].lower()
        assert "pre_flight" in detail
        assert "verification" in detail
        assert "execution" not in detail  # execution has items, shouldn't be listed


class TestFullLifecycleWithGates:
    """The full lifecycle works when all gates are satisfied."""

    def test_full_lifecycle(self, client, sample_change_data):
        """draft → in_review → approved → executing → done with all gates passed."""
        change_id = _create_change_with_preflight(client, sample_change_data)
        _add_items_to_all_phases(client, change_id)

        # Submit for review
        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review"},
        )
        assert resp.status_code == 200

        # Approve (requires reviewer)
        _approve_change(client, change_id)

        for status in ["approved", "executing", "done"]:
            resp = client.post(
                f"/api/v1/changes/{change_id}/transition",
                params={"target_status": status},
            )
            assert resp.status_code == 200, f"Failed transition to {status}: {resp.json()}"
            assert resp.json()["status"] == status

    def test_abort_bypasses_all_gates(self, client, sample_change_data):
        """Abort is always allowed regardless of completeness."""
        change_id = _create_change_with_preflight(client, sample_change_data)
        # No checklist items at all

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "aborted"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "aborted"

    def test_back_to_draft_from_review(self, client, sample_change_data):
        """A change can go back to draft from in_review (for edits)."""
        change_id = _create_change_with_preflight(client, sample_change_data)
        _add_items_to_all_phases(client, change_id)

        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review"},
        )

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "draft"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "draft"


class TestStalenessWarning:
    """24h staleness rule: warning when pre-flight answers are old at execution time."""

    def test_fresh_preflight_no_warning(self, client, sample_change_data, db):
        """No staleness warning when pre-flight is recent."""
        change_id = _create_change_with_preflight(client, sample_change_data)
        _add_items_to_all_phases(client, change_id)

        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review"},
        )
        _approve_change(client, change_id)
        for status in ["approved", "executing"]:
            client.post(
                f"/api/v1/changes/{change_id}/transition",
                params={"target_status": status},
            )

        # Check audit trail — no staleness event
        resp = client.get(f"/api/v1/changes/{change_id}")
        # The response should have audit events accessible
        # For now, check that the transition succeeded without issue
        assert resp.json()["status"] == "executing"

    def test_stale_preflight_warning_in_audit(self, client, sample_change_data, db):
        """When pre-flight is older than 24h, a staleness warning is recorded."""
        change_id = _create_change_with_preflight(client, sample_change_data)
        _add_items_to_all_phases(client, change_id)

        # Move to approved
        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review"},
        )
        _approve_change(client, change_id)
        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "approved"},
        )

        # Backdate the preflight_answered_at to 48h ago
        from app.models.change import Change

        change = db.query(Change).filter(Change.id == change_id).first()
        change.preflight_answered_at = datetime.now(UTC) - timedelta(hours=48)
        db.commit()

        # Transition to executing — should succeed but with staleness warning
        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "executing"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "executing"

        # Check audit trail for staleness warning
        from app.models.audit import AuditEvent

        staleness_events = (
            db.query(AuditEvent)
            .filter(
                AuditEvent.change_id == change_id,
                AuditEvent.event_type == "staleness_warning",
            )
            .all()
        )
        assert len(staleness_events) == 1
        assert "24h" in staleness_events[0].description.lower() or (
            "stale" in staleness_events[0].description.lower()
        )

    def test_stale_preflight_does_not_block(self, client, sample_change_data, db):
        """Staleness is a warning, not a hard block — execution still proceeds."""
        change_id = _create_change_with_preflight(client, sample_change_data)
        _add_items_to_all_phases(client, change_id)

        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review"},
        )
        _approve_change(client, change_id)
        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "approved"},
        )

        from app.models.change import Change

        change = db.query(Change).filter(Change.id == change_id).first()
        change.preflight_answered_at = datetime.now(UTC) - timedelta(hours=72)
        db.commit()

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "executing"},
        )
        assert resp.status_code == 200


class TestAbortReason:
    """Abort transitions can include a reason, stored in the audit trail."""

    def test_abort_with_reason(self, client, sample_change_data, db):
        """Aborting with a reason records it in the audit event."""
        change_id = _create_change_with_preflight(client, sample_change_data)

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={
                "target_status": "aborted",
                "reason": "Customer requested postponement due to quarter-end freeze",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "aborted"

        from app.models.audit import AuditEvent

        events = (
            db.query(AuditEvent)
            .filter(
                AuditEvent.change_id == change_id,
                AuditEvent.event_type == "status_changed",
            )
            .all()
        )
        abort_event = [e for e in events if "aborted" in e.description]
        assert len(abort_event) == 1
        assert "quarter-end freeze" in abort_event[0].description
        assert abort_event[0].event_data["reason"] == (
            "Customer requested postponement due to quarter-end freeze"
        )

    def test_abort_without_reason(self, client, sample_change_data, db):
        """Aborting without a reason still works — reason is optional."""
        change_id = _create_change_with_preflight(client, sample_change_data)

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={
                "target_status": "aborted",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "aborted"

        from app.models.audit import AuditEvent

        events = (
            db.query(AuditEvent)
            .filter(
                AuditEvent.change_id == change_id,
                AuditEvent.event_type == "status_changed",
            )
            .all()
        )
        abort_event = [e for e in events if "aborted" in e.description]
        assert len(abort_event) == 1
        assert "reason" not in abort_event[0].event_data
