"""Tests for the change lifecycle — the core of Changebook.

These tests define the expected behaviour:
- Create a change with pre-flight answers (one customer, one service, one environment)
- List and retrieve changes
- State machine transitions
- Audit trail is recorded
"""


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
    assert data["author_name"] == "Adrian Hornsby"
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
            json={"reviewer_name": "Reviewer"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/reviewers/{review.json()['id']}/decision",
            json={"decision": "approved"},
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
            params={"target_status": "in_review", "actor_name": "Adrian Hornsby"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_review"

    def test_cannot_skip_to_executing(self, client, sample_change_data):
        """Cannot jump from draft to executing — must go through review first."""
        change_id = self._create_change(client, sample_change_data, ready_for_review=True)
        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "executing", "actor_name": "Adrian Hornsby"},
        )
        assert resp.status_code == 422

    def test_full_lifecycle(self, client, sample_change_data):
        """A change can go through the full lifecycle."""
        change_id = self._create_change(client, sample_change_data, ready_for_review=True)

        # Submit for review
        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review", "actor_name": "Adrian Hornsby"},
        )
        # Approve (requires reviewer)
        self._approve_change(client, change_id)

        for status in ["approved", "executing", "done"]:
            resp = client.post(
                f"/api/v1/changes/{change_id}/transition",
                params={"target_status": status, "actor_name": "Adrian Hornsby"},
            )
            assert resp.status_code == 200, f"Failed transition to {status}: {resp.json()}"
            assert resp.json()["status"] == status

    def test_abort_from_any_active_state(self, client, sample_change_data):
        """A change can be aborted from any active state."""
        change_id = self._create_change(client, sample_change_data)
        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "aborted", "actor_name": "Adrian Hornsby"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "aborted"

    def test_done_is_terminal(self, client, sample_change_data):
        """Once done, a change cannot transition to any other state."""
        change_id = self._create_change(client, sample_change_data, ready_for_review=True)
        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review", "actor_name": "Adrian Hornsby"},
        )
        self._approve_change(client, change_id)
        for status in ["approved", "executing", "done"]:
            client.post(
                f"/api/v1/changes/{change_id}/transition",
                params={"target_status": status, "actor_name": "Adrian Hornsby"},
            )

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "draft", "actor_name": "Adrian Hornsby"},
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
