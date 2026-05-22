"""Tests for the change lifecycle — the core of Changebook.

These tests define the expected behaviour:
- Create a change with pre-flight answers (one customer, one service, one environment)
- List and retrieve changes
- State machine transitions
- Audit trail is recorded
"""

from tests.conftest import JANE


def test_create_change(client, sample_change_data):
    """A change can be created with customer, service, environment, and pre-flight answers."""
    response = client.post(
        "/api/v1/changes",
        json={
            "title": "Update connection pool size on PROD-EU",
            "description": "Increase max connections from 100 to 150",
            "author_name": "Adrian Hornsby",
            **sample_change_data,
            "preflight_answers": {
                "what_is_this_change": "Increase connection pool from 100 to 150",
                "what_if_fails": "Connections rejected, EOD batch fails",
                "rollback_plan": "Set parameter back to 100, restart pool",
            },
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Update connection pool size on PROD-EU"
    assert data["status"] == "draft"
    assert data["author_name"] == "Test User"  # From auth headers, not body
    assert data["customer_id"] == sample_change_data["customer_id"]
    assert data["service_id"] == sample_change_data["service_id"]
    assert data["environment_id"] == sample_change_data["environment_id"]


def test_list_changes(client, sample_change_data):
    """Changes can be listed with pagination."""
    for i in range(3):
        client.post(
            "/api/v1/changes",
            json={
                "title": f"Change {i}",
                "author_name": "Adrian Hornsby",
                **sample_change_data,
            },
        )

    response = client.get("/api/v1/changes")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 3
    assert data["meta"]["total"] == 3


def test_get_change_detail(client, sample_change_data):
    """A single change can be retrieved."""
    create_resp = client.post(
        "/api/v1/changes",
        json={
            "title": "Firewall rule update",
            "author_name": "Adrian Hornsby",
            **sample_change_data,
        },
    )
    change_id = create_resp.json()["id"]

    response = client.get(f"/api/v1/changes/{change_id}")
    assert response.status_code == 200
    assert response.json()["title"] == "Firewall rule update"


def test_change_not_found(client):
    """Requesting a non-existent change returns 404."""
    response = client.get("/api/v1/changes/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_update_draft_change(client, sample_change_data):
    """A change in draft status can be updated."""
    create_resp = client.post(
        "/api/v1/changes",
        json={
            "title": "Original title",
            "author_name": "Adrian Hornsby",
            **sample_change_data,
        },
    )
    change_id = create_resp.json()["id"]

    response = client.patch(
        f"/api/v1/changes/{change_id}",
        json={"title": "Updated title", "defence_tags": ["monitoring", "alerting"]},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated title"
    assert response.json()["defence_tags"] == ["monitoring", "alerting"]


def test_create_change_with_defence_tags(client, sample_change_data):
    """Changes can be tagged with defence layers they affect."""
    response = client.post(
        "/api/v1/changes",
        json={
            "title": "Update alert routing",
            "author_name": "Adrian Hornsby",
            "defence_tags": ["alerting", "monitoring"],
            **sample_change_data,
        },
    )
    assert response.status_code == 201
    assert response.json()["defence_tags"] == ["alerting", "monitoring"]


class TestStateTransitions:
    """The state machine enforces valid transitions only."""

    def _complete_preflight_answers(self, client):
        """Build a complete set of pre-flight answers by discovering questions from the API."""
        resp = client.get("/api/v1/preflight-questions")
        keys = []
        for section in resp.json()["sections"]:
            for q in section["questions"]:
                if q["required"]:
                    keys.append(q["key"])
        return {key: f"Answer for {key}" for key in keys}

    def _add_items_to_all_phases(self, client, change_id):
        for phase in ["pre_flight", "execution", "verification"]:
            client.post(
                f"/api/v1/changes/{change_id}/checklist",
                json={"phase": phase, "description": f"{phase} step"},
            )

    def _approve_change(self, client, change_id):
        """Assign a reviewer and approve so the change can transition to approved."""
        review = client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "Jane Smith"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/reviewers/{review.json()['id']}/decision",
            json={"decision": "approved"},
            headers=JANE,
        )

    def _create_change(self, client, sample_change_data, ready_for_review=False):
        data = {
            "title": "Test change",
            "author_name": "Adrian Hornsby",
            **sample_change_data,
        }
        if ready_for_review:
            data["preflight_answers"] = self._complete_preflight_answers(client)
        resp = client.post("/api/v1/changes", json=data)
        change_id = resp.json()["id"]
        if ready_for_review:
            self._add_items_to_all_phases(client, change_id)
        return change_id

    def test_draft_to_in_review(self, client, sample_change_data):
        change_id = self._create_change(client, sample_change_data, ready_for_review=True)
        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_review"

    def test_cannot_skip_to_executing(self, client, sample_change_data):
        """Cannot jump from draft to executing — must go through review first."""
        change_id = self._create_change(client, sample_change_data, ready_for_review=True)
        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "executing"},
        )
        assert resp.status_code == 422

    def test_full_lifecycle(self, client, sample_change_data):
        """A change can go through the full lifecycle."""
        change_id = self._create_change(client, sample_change_data, ready_for_review=True)

        # Submit for review
        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review"},
        )
        # Approve (requires reviewer)
        self._approve_change(client, change_id)

        for status in ["approved", "executing"]:
            resp = client.post(
                f"/api/v1/changes/{change_id}/transition",
                params={"target_status": status},
            )
            assert resp.status_code == 200, f"Failed transition to {status}: {resp.json()}"
            assert resp.json()["status"] == status

        # Complete all checklist items before marking done
        items = client.get(f"/api/v1/changes/{change_id}/checklist").json()
        for item in items:
            client.post(
                f"/api/v1/changes/{change_id}/checklist/{item['id']}/complete",
                json={"observed_result": "OK", "status": "completed"},
            )

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "done"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "done"

    def test_abort_from_any_active_state(self, client, sample_change_data):
        """A change can be aborted from any active state."""
        change_id = self._create_change(client, sample_change_data)
        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "aborted"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "aborted"

    def test_cannot_assign_reviewer_during_execution(self, client, sample_change_data):
        """Reviewers cannot be assigned once the change is past in_review."""
        change_id = self._create_change(client, sample_change_data, ready_for_review=True)
        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review"},
        )
        self._approve_change(client, change_id)
        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "approved"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "executing"},
        )

        resp = client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "Late Reviewer"},
        )
        assert resp.status_code == 422
        assert "draft or in_review" in resp.json()["detail"].lower()

    def test_done_is_terminal(self, client, sample_change_data):
        """Once done, a change cannot transition to any other state."""
        change_id = self._create_change(client, sample_change_data, ready_for_review=True)
        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review"},
        )
        self._approve_change(client, change_id)
        for status in ["approved", "executing", "done"]:
            client.post(
                f"/api/v1/changes/{change_id}/transition",
                params={"target_status": status},
            )

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "draft"},
        )
        assert resp.status_code == 422


class TestTeamsAndEnvironments:
    """Basic CRUD for teams and environments."""

    def test_create_team(self, client):
        resp = client.post("/api/v1/teams", json={"name": "DBA Team"})
        assert resp.status_code == 201
        assert resp.json()["name"] == "DBA Team"
        assert resp.json()["organisation_id"] is not None

    def test_create_environment(self, client):
        resp = client.post(
            "/api/v1/environments",
            json={
                "name": "PROD-EU-01",
                "platform": "Azure",
                "description": "Production EU client 1",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "PROD-EU-01"
        assert resp.json()["platform"] == "Azure"


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


class TestMaintenanceWindow:
    """Structured maintenance window fields on changes."""

    def test_create_with_maintenance_window(self, client, sample_change_data):
        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Scheduled change",
                **sample_change_data,
                "maintenance_window_start": "2026-05-24T22:00:00Z",
                "maintenance_window_end": "2026-05-25T02:00:00Z",
                "maintenance_window_tz": "Europe/London",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["maintenance_window_start"] is not None
        assert data["maintenance_window_end"] is not None
        assert data["maintenance_window_tz"] == "Europe/London"

    def test_create_without_maintenance_window(self, client, sample_change_data):
        resp = client.post(
            "/api/v1/changes",
            json={"title": "No window", **sample_change_data},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["maintenance_window_start"] is None
        assert data["maintenance_window_end"] is None
        assert data["maintenance_window_tz"] is None

    def test_end_must_be_after_start(self, client, sample_change_data):
        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Bad window",
                **sample_change_data,
                "maintenance_window_start": "2026-05-25T02:00:00Z",
                "maintenance_window_end": "2026-05-24T22:00:00Z",
            },
        )
        assert resp.status_code == 422

    def test_start_without_end_rejected(self, client, sample_change_data):
        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Missing end",
                **sample_change_data,
                "maintenance_window_start": "2026-05-24T22:00:00Z",
            },
        )
        assert resp.status_code == 422

    def test_window_override_reason_stored(self, client, sample_change_data):
        """When executing outside the window, the override reason is stored on the change."""
        # Create with a window entirely in the past
        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Past window change",
                **sample_change_data,
                "maintenance_window_start": "2020-01-01T00:00:00Z",
                "maintenance_window_end": "2020-01-01T04:00:00Z",
                "maintenance_window_tz": "UTC",
            },
        )
        change_id = resp.json()["id"]

        # Fill preflight + checklist so it can pass review gates
        preflight_resp = client.get("/api/v1/preflight-questions")
        answers = {}
        for section in preflight_resp.json()["sections"]:
            for q in section["questions"]:
                if q["required"]:
                    answers[q["key"]] = f"Answer for {q['key']}"
        client.patch(
            f"/api/v1/changes/{change_id}",
            json={"preflight_answers": answers},
        )
        for phase in ["pre_flight", "execution", "verification"]:
            client.post(
                f"/api/v1/changes/{change_id}/checklist",
                json={"phase": phase, "description": f"{phase} step"},
            )

        # Move through: draft → in_review → approved
        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review"},
        )
        from tests.conftest import JANE

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

        # Execute with a reason — window is in the past
        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "executing", "reason": "Customer approved early start"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "executing"
        assert resp.json()["window_override_reason"] == "Customer approved early start"

        # Also visible on GET
        detail = client.get(f"/api/v1/changes/{change_id}")
        assert detail.json()["window_override_reason"] == "Customer approved early start"

    def test_patch_maintenance_window(self, client, sample_change_data):
        create = client.post(
            "/api/v1/changes",
            json={"title": "Will add window later", **sample_change_data},
        )
        change_id = create.json()["id"]

        resp = client.patch(
            f"/api/v1/changes/{change_id}",
            json={
                "maintenance_window_start": "2026-06-01T18:00:00Z",
                "maintenance_window_end": "2026-06-01T22:00:00Z",
                "maintenance_window_tz": "US/Eastern",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["maintenance_window_tz"] == "US/Eastern"

    def test_clear_maintenance_window(self, client, sample_change_data):
        """A maintenance window can be cleared by sending null values."""
        create = client.post(
            "/api/v1/changes",
            json={
                "title": "Has window",
                **sample_change_data,
                "maintenance_window_start": "2026-06-01T18:00:00Z",
                "maintenance_window_end": "2026-06-01T22:00:00Z",
                "maintenance_window_tz": "UTC",
            },
        )
        change_id = create.json()["id"]
        assert create.json()["maintenance_window_start"] is not None

        resp = client.patch(
            f"/api/v1/changes/{change_id}",
            json={
                "maintenance_window_start": None,
                "maintenance_window_end": None,
                "maintenance_window_tz": None,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["maintenance_window_start"] is None
        assert data["maintenance_window_end"] is None
        assert data["maintenance_window_tz"] is None
