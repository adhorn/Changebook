"""Tests for Feature 6: Checklist execution — sequential read-do.

The execution model enforces:
- Items completed in order within each phase (sequential unlock)
- Phases completed in order: pre_flight → execution → verification
- Hold points require second-person verification before proceeding
- Only works when the change is in 'executing' status
- Each completion records who, when, what was observed
"""

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


def _create_executing_change(client, sample_change_data, items=None):
    """Create a change and move it to executing status.

    items: optional dict of {phase: [descriptions]} to override defaults.
    Default: one item per phase.
    """
    resp = client.post(
        "/api/v1/changes",
        json={
            "title": "Execution test change",
            "author_name": "Adrian Hornsby",
            **sample_change_data,
            "preflight_answers": _complete_preflight(client),
        },
    )
    change_id = resp.json()["id"]

    # Add checklist items
    if items is None:
        items = {
            "pre_flight": [{"description": "Verify backup exists"}],
            "execution": [{"description": "Run migration script"}],
            "verification": [{"description": "Check service health"}],
        }

    created_items = {}
    for phase, item_list in items.items():
        created_items[phase] = []
        for item_data in item_list:
            payload = {"phase": phase, **item_data}
            r = client.post(
                f"/api/v1/changes/{change_id}/checklist",
                json=payload,
            )
            created_items[phase].append(r.json())

    # Move to executing: draft → in_review → approved → executing
    client.post(
        f"/api/v1/changes/{change_id}/transition",
        params={"target_status": "in_review"},
    )
    review = client.post(
        f"/api/v1/changes/{change_id}/reviewers",
        json={"reviewer_name": "Jane Smith"},
    )
    client.post(
        f"/api/v1/changes/{change_id}/reviewers/{review.json()['id']}/decision",
        json={"decision": "approved"},
        headers=JANE,
    )
    client.post(
        f"/api/v1/changes/{change_id}/transition",
        params={"target_status": "approved"},
    )
    client.post(
        f"/api/v1/changes/{change_id}/transition",
        params={"target_status": "executing"},
    )

    return change_id, created_items


class TestSequentialUnlock:
    """Items must be completed in order — no skipping ahead."""

    def test_complete_first_item(self, client, sample_change_data):
        """The first item in the first phase can be completed."""
        change_id, items = _create_executing_change(client, sample_change_data)
        first_item = items["pre_flight"][0]

        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist/{first_item['id']}/complete",
            json={
                "observed_result": "Backup verified — 2.3GB snapshot from 10 minutes ago",
                "status": "completed",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        assert resp.json()["completed_by"] == "Test User"
        assert resp.json()["observed_result"] is not None

    def test_cannot_complete_second_item_before_first(self, client, sample_change_data):
        """Cannot skip ahead — the second item is blocked until the first is done."""
        items_def = {
            "pre_flight": [
                {"description": "Check backup"},
                {"description": "Verify connectivity"},
            ],
            "execution": [{"description": "Run script"}],
            "verification": [{"description": "Verify output"}],
        }
        change_id, items = _create_executing_change(client, sample_change_data, items=items_def)
        second_item = items["pre_flight"][1]

        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist/{second_item['id']}/complete",
            json={
                "observed_result": "Connected",
                "status": "completed",
            },
        )
        assert resp.status_code == 422
        assert "order" in resp.json()["detail"].lower()

    def test_can_complete_second_after_first(self, client, sample_change_data):
        """After the first item is done, the second unlocks."""
        items_def = {
            "pre_flight": [
                {"description": "Check backup"},
                {"description": "Verify connectivity"},
            ],
            "execution": [{"description": "Run script"}],
            "verification": [{"description": "Verify output"}],
        }
        change_id, items = _create_executing_change(client, sample_change_data, items=items_def)

        # Complete first
        client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['pre_flight'][0]['id']}/complete",
            json={
                "observed_result": "Backup OK",
                "status": "completed",
            },
        )

        # Now second should work
        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['pre_flight'][1]['id']}/complete",
            json={
                "observed_result": "Connected OK",
                "status": "completed",
            },
        )
        assert resp.status_code == 200

    def test_cannot_complete_same_item_twice(self, client, sample_change_data):
        """An already-completed item cannot be completed again."""
        change_id, items = _create_executing_change(client, sample_change_data)
        first_item = items["pre_flight"][0]

        client.post(
            f"/api/v1/changes/{change_id}/checklist/{first_item['id']}/complete",
            json={
                "observed_result": "Done",
                "status": "completed",
            },
        )

        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist/{first_item['id']}/complete",
            json={
                "observed_result": "Done again",
                "status": "completed",
            },
        )
        assert resp.status_code == 422
        assert "already" in resp.json()["detail"].lower()


class TestPhaseGating:
    """Must complete all items in one phase before the next phase unlocks."""

    def test_cannot_start_execution_before_preflight_done(self, client, sample_change_data):
        """Execution items are blocked until all pre-flight items are complete."""
        change_id, items = _create_executing_change(client, sample_change_data)
        exec_item = items["execution"][0]

        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist/{exec_item['id']}/complete",
            json={
                "observed_result": "Migration ran",
                "status": "completed",
            },
        )
        assert resp.status_code == 422
        assert "phase" in resp.json()["detail"].lower()

    def test_execution_unlocks_after_preflight_complete(self, client, sample_change_data):
        """After all pre-flight items are done, execution items unlock."""
        change_id, items = _create_executing_change(client, sample_change_data)

        # Complete pre-flight
        client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['pre_flight'][0]['id']}/complete",
            json={
                "observed_result": "Backup verified",
                "status": "completed",
            },
        )

        # Now execution should work
        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['execution'][0]['id']}/complete",
            json={
                "observed_result": "Migration applied, 42 rows updated",
                "status": "completed",
            },
        )
        assert resp.status_code == 200

    def test_cannot_start_verification_before_execution_done(self, client, sample_change_data):
        """Verification items are blocked until all execution items are complete."""
        change_id, items = _create_executing_change(client, sample_change_data)

        # Complete pre-flight
        client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['pre_flight'][0]['id']}/complete",
            json={
                "observed_result": "OK",
                "status": "completed",
            },
        )

        # Try verification — execution not done yet
        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['verification'][0]['id']}/complete",
            json={
                "observed_result": "Healthy",
                "status": "completed",
            },
        )
        assert resp.status_code == 422
        assert "phase" in resp.json()["detail"].lower()


class TestHoldPoints:
    """Hold points require second-person verification before proceeding."""

    def test_hold_point_blocks_next_item(self, client, sample_change_data):
        """After completing a hold-point item, the next item is blocked until verified."""
        items_def = {
            "pre_flight": [{"description": "Pre-flight check"}],
            "execution": [
                {"description": "Apply config", "is_hold_point": True},
                {"description": "Restart service"},
            ],
            "verification": [{"description": "Check health"}],
        }
        change_id, items = _create_executing_change(client, sample_change_data, items=items_def)

        # Complete pre-flight
        client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['pre_flight'][0]['id']}/complete",
            json={
                "observed_result": "OK",
                "status": "completed",
            },
        )

        # Complete the hold-point item
        client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['execution'][0]['id']}/complete",
            json={
                "observed_result": "Config applied",
                "status": "completed",
            },
        )

        # Try next item — blocked, hold point not verified
        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['execution'][1]['id']}/complete",
            json={
                "observed_result": "Restarted",
                "status": "completed",
            },
        )
        assert resp.status_code == 422
        assert "hold" in resp.json()["detail"].lower()

    def test_hold_point_verification(self, client, sample_change_data):
        """A second person can verify a hold point."""
        items_def = {
            "pre_flight": [{"description": "Pre-flight check"}],
            "execution": [
                {"description": "Apply config", "is_hold_point": True},
                {"description": "Restart service"},
            ],
            "verification": [{"description": "Check health"}],
        }
        change_id, items = _create_executing_change(client, sample_change_data, items=items_def)

        # Complete pre-flight
        client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['pre_flight'][0]['id']}/complete",
            json={
                "observed_result": "OK",
                "status": "completed",
            },
        )

        # Complete the hold-point item
        client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['execution'][0]['id']}/complete",
            json={
                "observed_result": "Config applied",
                "status": "completed",
            },
        )

        # Verify the hold point — operator types the verifier's name
        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['execution'][0]['id']}/hold-point-verify",
            json={"verified_by": "Jane Smith"},
        )
        assert resp.status_code == 200
        assert resp.json()["hold_point_verified_by"] == "Jane Smith"
        assert resp.json()["hold_point_verified_at"] is not None

    def test_hold_point_verified_unlocks_next(self, client, sample_change_data):
        """After hold-point verification, the next item unlocks."""
        items_def = {
            "pre_flight": [{"description": "Pre-flight check"}],
            "execution": [
                {"description": "Apply config", "is_hold_point": True},
                {"description": "Restart service"},
            ],
            "verification": [{"description": "Check health"}],
        }
        change_id, items = _create_executing_change(client, sample_change_data, items=items_def)

        # Complete pre-flight
        client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['pre_flight'][0]['id']}/complete",
            json={
                "observed_result": "OK",
                "status": "completed",
            },
        )

        # Complete hold-point item
        client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['execution'][0]['id']}/complete",
            json={
                "observed_result": "Config applied",
                "status": "completed",
            },
        )

        # Verify hold point — operator types the verifier's name
        client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['execution'][0]['id']}/hold-point-verify",
            json={"verified_by": "Jane Smith"},
        )

        # Now next item should unlock
        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['execution'][1]['id']}/complete",
            json={
                "observed_result": "Service restarted, PID 4821",
                "status": "completed",
            },
        )
        assert resp.status_code == 200

    def test_cannot_verify_non_hold_point(self, client, sample_change_data):
        """Verifying a non-hold-point item is an error."""
        change_id, items = _create_executing_change(client, sample_change_data)

        # Complete first item (not a hold point)
        client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['pre_flight'][0]['id']}/complete",
            json={
                "observed_result": "OK",
                "status": "completed",
            },
        )

        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['pre_flight'][0]['id']}/hold-point-verify",
            json={"verified_by": "Jane Smith"},
        )
        assert resp.status_code == 422
        assert "hold" in resp.json()["detail"].lower()

    def test_cannot_verify_uncompleted_hold_point(self, client, sample_change_data):
        """Cannot verify a hold point that hasn't been completed yet."""
        items_def = {
            "pre_flight": [{"description": "Pre-flight check"}],
            "execution": [
                {"description": "Apply config", "is_hold_point": True},
            ],
            "verification": [{"description": "Check health"}],
        }
        change_id, items = _create_executing_change(client, sample_change_data, items=items_def)

        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['execution'][0]['id']}/hold-point-verify",
            json={"verified_by": "Jane Smith"},
        )
        assert resp.status_code == 422

    def test_cannot_verify_with_same_name_as_completer(self, client, sample_change_data):
        """The verifier name cannot match the completer — two-person rule."""
        items_def = {
            "pre_flight": [{"description": "Pre-flight check"}],
            "execution": [
                {"description": "Apply config", "is_hold_point": True},
                {"description": "Restart service"},
            ],
            "verification": [{"description": "Check health"}],
        }
        change_id, items = _create_executing_change(client, sample_change_data, items=items_def)

        # Complete pre-flight
        client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['pre_flight'][0]['id']}/complete",
            json={"observed_result": "OK", "status": "completed"},
        )

        # Complete the hold-point item (completer is "Test User" from conftest)
        client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['execution'][0]['id']}/complete",
            json={"observed_result": "Config applied", "status": "completed"},
        )

        # Try to verify with the same name as the completer
        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['execution'][0]['id']}/hold-point-verify",
            json={"verified_by": "Test User"},
        )
        assert resp.status_code == 422
        assert "different person" in resp.json()["detail"].lower()

    def test_verified_by_is_required(self, client, sample_change_data):
        """The verified_by field is required — cannot send empty body."""
        items_def = {
            "pre_flight": [{"description": "Pre-flight check"}],
            "execution": [
                {"description": "Apply config", "is_hold_point": True},
            ],
            "verification": [{"description": "Check health"}],
        }
        change_id, items = _create_executing_change(client, sample_change_data, items=items_def)

        client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['pre_flight'][0]['id']}/complete",
            json={"observed_result": "OK", "status": "completed"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['execution'][0]['id']}/complete",
            json={"observed_result": "Config applied", "status": "completed"},
        )

        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['execution'][0]['id']}/hold-point-verify",
            json={},
        )
        assert resp.status_code == 422


class TestCompletionStatuses:
    """Items can be completed, flagged, or skipped with justification."""

    def test_flagged_item(self, client, sample_change_data):
        """An item can be flagged — something unexpected was observed."""
        change_id, items = _create_executing_change(client, sample_change_data)

        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['pre_flight'][0]['id']}/complete",
            json={
                "observed_result": "Backup exists but is 6 hours old, not recent",
                "status": "flagged",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "flagged"

    def test_skipped_requires_justification(self, client, sample_change_data):
        """Skipping an item requires observed_result as justification."""
        change_id, items = _create_executing_change(client, sample_change_data)

        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['pre_flight'][0]['id']}/complete",
            json={
                "observed_result": "Backup service is down, but change is low-risk and reversible",
                "status": "skipped_with_justification",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "skipped_with_justification"


class TestStatusGate:
    """Execution only works when the change is in 'executing' status."""

    def test_cannot_execute_in_draft(self, client, sample_change_data):
        """Cannot complete items on a change that's still in draft."""
        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Draft change",
                "author_name": "Adrian Hornsby",
                **sample_change_data,
                "preflight_answers": _complete_preflight(client),
            },
        )
        change_id = resp.json()["id"]

        item_resp = client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "pre_flight", "description": "Step 1"},
        )
        item_id = item_resp.json()["id"]

        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist/{item_id}/complete",
            json={
                "observed_result": "Done",
                "status": "completed",
            },
        )
        assert resp.status_code == 422
        assert "executing" in resp.json()["detail"].lower()

    def test_cannot_execute_in_done(self, client, sample_change_data):
        """Cannot complete items on a change that's already done."""
        change_id, items = _create_executing_change(client, sample_change_data)

        # Complete all items to enable done transition
        for phase in ["pre_flight", "execution", "verification"]:
            for item in items[phase]:
                client.post(
                    f"/api/v1/changes/{change_id}/checklist/{item['id']}/complete",
                    json={
                        "observed_result": "Done",
                        "status": "completed",
                    },
                )

        # Transition to done
        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "done"},
        )

        # Try completing again — should fail
        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['pre_flight'][0]['id']}/complete",
            json={
                "observed_result": "Redo",
                "status": "completed",
            },
        )
        assert resp.status_code == 422


class TestExecutionStatus:
    """GET endpoint shows current execution progress."""

    def test_execution_status_at_start(self, client, sample_change_data):
        """At the start, all items are pending and current phase is pre_flight."""
        change_id, items = _create_executing_change(client, sample_change_data)

        resp = client.get(f"/api/v1/changes/{change_id}/execution-status")
        assert resp.status_code == 200

        data = resp.json()
        assert data["current_phase"] == "pre_flight"
        assert data["total_items"] == 3
        assert data["completed_items"] == 0
        assert data["next_item_id"] == items["pre_flight"][0]["id"]

    def test_execution_status_mid_execution(self, client, sample_change_data):
        """After completing pre-flight, status shows execution phase."""
        change_id, items = _create_executing_change(client, sample_change_data)

        # Complete pre-flight
        client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['pre_flight'][0]['id']}/complete",
            json={
                "observed_result": "OK",
                "status": "completed",
            },
        )

        resp = client.get(f"/api/v1/changes/{change_id}/execution-status")
        data = resp.json()
        assert data["current_phase"] == "execution"
        assert data["completed_items"] == 1
        assert data["next_item_id"] == items["execution"][0]["id"]

    def test_execution_status_all_done(self, client, sample_change_data):
        """After all items completed, status reflects that."""
        change_id, items = _create_executing_change(client, sample_change_data)

        for phase in ["pre_flight", "execution", "verification"]:
            for item in items[phase]:
                client.post(
                    f"/api/v1/changes/{change_id}/checklist/{item['id']}/complete",
                    json={
                        "observed_result": "Done",
                        "status": "completed",
                    },
                )

        resp = client.get(f"/api/v1/changes/{change_id}/execution-status")
        data = resp.json()
        assert data["completed_items"] == 3
        assert data["total_items"] == 3
        assert data["next_item_id"] is None
        assert data["all_complete"] is True

    def test_execution_status_only_when_executing(self, client, sample_change_data):
        """Execution status is only available when the change is executing."""
        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Draft change",
                "author_name": "Adrian Hornsby",
                **sample_change_data,
            },
        )
        change_id = resp.json()["id"]

        resp = client.get(f"/api/v1/changes/{change_id}/execution-status")
        assert resp.status_code == 422


class TestExecutionAudit:
    """Completions are recorded in the audit trail."""

    def test_completion_creates_audit_event(self, client, sample_change_data, db):
        """Each item completion is recorded in the audit trail."""
        change_id, items = _create_executing_change(client, sample_change_data)

        client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['pre_flight'][0]['id']}/complete",
            json={
                "observed_result": "Backup verified",
                "status": "completed",
            },
        )

        from app.models.audit import AuditEvent

        events = (
            db.query(AuditEvent)
            .filter(
                AuditEvent.change_id == change_id,
                AuditEvent.event_type == "item_completed",
            )
            .all()
        )
        assert len(events) == 1
        assert events[0].actor_name == "Test User"

    def test_hold_point_verification_creates_audit(self, client, sample_change_data, db):
        """Hold-point verification is recorded in the audit trail."""
        items_def = {
            "pre_flight": [
                {"description": "Check", "is_hold_point": True},
            ],
            "execution": [{"description": "Run"}],
            "verification": [{"description": "Verify"}],
        }
        change_id, items = _create_executing_change(client, sample_change_data, items=items_def)

        # Complete the hold-point item
        client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['pre_flight'][0]['id']}/complete",
            json={
                "observed_result": "Checked",
                "status": "completed",
            },
        )

        # Verify — operator types the verifier's name
        client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['pre_flight'][0]['id']}/hold-point-verify",
            json={"verified_by": "Jane Smith"},
        )

        from app.models.audit import AuditEvent

        events = (
            db.query(AuditEvent)
            .filter(
                AuditEvent.change_id == change_id,
                AuditEvent.event_type == "hold_point_verified",
            )
            .all()
        )
        assert len(events) == 1
        assert events[0].actor_name == "Jane Smith"
