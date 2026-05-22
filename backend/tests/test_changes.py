"""Tests for the change lifecycle — the core of Changebook.

These tests define the expected behaviour:
- Create a change with pre-flight answers
- List and retrieve changes
- State machine transitions
- Audit trail is recorded
"""


def test_create_change(client, org_and_team):
    """A change can be created with a title, team, author, and pre-flight answers."""
    response = client.post(
        "/api/v1/changes",
        json={
            "title": "Update connection pool size on PROD-EU",
            "description": "Increase max connections from 100 to 150",
            "team_id": org_and_team["team_id"],
            "author_name": "Adrian Hornsby",
            "preflight_answers": {
                "what_is_this_change": "Increase connection pool from 100 to 150",
                "who_is_using": "Portfolio managers running EOD batch",
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
    assert data["preflight_answers"]["who_is_using"] == "Portfolio managers running EOD batch"


def test_create_change_with_steps(client, org_and_team):
    """A change can include execution steps at creation time."""
    response = client.post(
        "/api/v1/changes",
        json={
            "title": "Database parameter change",
            "team_id": org_and_team["team_id"],
            "author_name": "Adrian Hornsby",
            "steps": [
                {
                    "description": "Take backup of current parameter values",
                    "expected_outcome": "Backup file created",
                    "rollback_action": "N/A",
                },
                {
                    "description": "Update connection pool parameter",
                    "expected_outcome": "Parameter set to 150",
                    "rollback_action": "Set parameter back to 100",
                    "script": "ALTER SYSTEM SET max_connections = 150;",
                    "is_hold_point": True,
                },
                {
                    "description": "Restart connection pool",
                    "expected_outcome": "Pool restarted, connections accepting",
                    "rollback_action": "Restart with old config",
                },
            ],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data["steps"]) == 3
    assert data["steps"][0]["order"] == 1
    assert data["steps"][1]["is_hold_point"] is True
    assert data["steps"][1]["script"] == "ALTER SYSTEM SET max_connections = 150;"


def test_list_changes(client, org_and_team):
    """Changes can be listed with pagination."""
    for i in range(3):
        client.post(
            "/api/v1/changes",
            json={
                "title": f"Change {i}",
                "team_id": org_and_team["team_id"],
                "author_name": "Adrian Hornsby",
            },
        )

    response = client.get("/api/v1/changes")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 3
    assert data["meta"]["total"] == 3


def test_get_change_detail(client, org_and_team):
    """A single change can be retrieved with full detail including steps."""
    create_resp = client.post(
        "/api/v1/changes",
        json={
            "title": "Firewall rule update",
            "team_id": org_and_team["team_id"],
            "author_name": "Adrian Hornsby",
            "steps": [
                {"description": "Backup current rules"},
                {"description": "Apply new rules"},
            ],
        },
    )
    change_id = create_resp.json()["id"]

    response = client.get(f"/api/v1/changes/{change_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Firewall rule update"
    assert len(data["steps"]) == 2


def test_change_not_found(client):
    """Requesting a non-existent change returns 404."""
    response = client.get("/api/v1/changes/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_update_draft_change(client, org_and_team):
    """A change in draft status can be updated."""
    create_resp = client.post(
        "/api/v1/changes",
        json={
            "title": "Original title",
            "team_id": org_and_team["team_id"],
            "author_name": "Adrian Hornsby",
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


def test_create_change_with_defence_tags(client, org_and_team):
    """Changes can be tagged with defence layers they affect."""
    response = client.post(
        "/api/v1/changes",
        json={
            "title": "Update alert routing",
            "team_id": org_and_team["team_id"],
            "author_name": "Adrian Hornsby",
            "defence_tags": ["alerting", "monitoring"],
        },
    )
    assert response.status_code == 201
    assert response.json()["defence_tags"] == ["alerting", "monitoring"]


class TestStateTransitions:
    """The state machine enforces valid transitions only."""

    def _create_change(self, client, org_and_team):
        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Test change",
                "team_id": org_and_team["team_id"],
                "author_name": "Adrian Hornsby",
            },
        )
        return resp.json()["id"]

    def test_draft_to_in_review(self, client, org_and_team):
        change_id = self._create_change(client, org_and_team)
        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review", "actor_name": "Adrian Hornsby"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_review"

    def test_cannot_skip_to_executing(self, client, org_and_team):
        """Cannot jump from draft to executing — must go through review first."""
        change_id = self._create_change(client, org_and_team)
        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "executing", "actor_name": "Adrian Hornsby"},
        )
        assert resp.status_code == 422

    def test_full_lifecycle(self, client, org_and_team):
        """A change can go through the full lifecycle: draft → review → approved → executing → verifying → verified → closed."""
        change_id = self._create_change(client, org_and_team)

        transitions = [
            "in_review",
            "approved",
            "executing",
            "awaiting_verification",
            "verified",
            "closed",
        ]
        for status in transitions:
            resp = client.post(
                f"/api/v1/changes/{change_id}/transition",
                params={"target_status": status, "actor_name": "Adrian Hornsby"},
            )
            assert resp.status_code == 200, f"Failed transition to {status}: {resp.json()}"
            assert resp.json()["status"] == status

    def test_abort_from_any_active_state(self, client, org_and_team):
        """A change can be aborted from any active state."""
        change_id = self._create_change(client, org_and_team)
        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "aborted", "actor_name": "Adrian Hornsby"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "aborted"

    def test_closed_is_terminal(self, client, org_and_team):
        """Once closed, a change cannot transition to any other state."""
        change_id = self._create_change(client, org_and_team)
        for status in ["in_review", "approved", "executing", "awaiting_verification", "verified", "closed"]:
            client.post(
                f"/api/v1/changes/{change_id}/transition",
                params={"target_status": status, "actor_name": "Adrian Hornsby"},
            )

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "draft", "actor_name": "Adrian Hornsby"},
        )
        assert resp.status_code == 422


class TestOrganisations:
    """Basic CRUD for organisations, teams, and environments."""

    def test_create_organisation(self, client):
        resp = client.post("/api/v1/organisations", json={"name": "Acme Corp"})
        assert resp.status_code == 201
        assert resp.json()["name"] == "Acme Corp"

    def test_create_team(self, client):
        org = client.post("/api/v1/organisations", json={"name": "Acme Corp"})
        resp = client.post(
            "/api/v1/teams",
            json={"name": "DBA Team", "organisation_id": org.json()["id"]},
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "DBA Team"

    def test_create_environment(self, client):
        org = client.post("/api/v1/organisations", json={"name": "Acme Corp"})
        resp = client.post(
            "/api/v1/environments",
            json={
                "name": "PROD-EU-01",
                "platform": "Azure",
                "description": "Production EU client 1",
                "organisation_id": org.json()["id"],
            },
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "PROD-EU-01"
        assert resp.json()["platform"] == "Azure"


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
