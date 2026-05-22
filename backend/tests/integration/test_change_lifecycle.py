"""End-to-end change lifecycle test against real Postgres.

This is the most important test in the project. It walks a change through
the full lifecycle — create, pre-flight, review, execute steps, verify,
close — and confirms the audit trail is complete and correct.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("CHANGEBOOK_DATABASE_URL")
    or "sqlite" in (os.environ.get("CHANGEBOOK_DATABASE_URL") or ""),
    reason="Requires Postgres",
)


class TestFullChangeLifecycle:
    """A change goes from draft to closed with full audit trail."""

    def test_complete_lifecycle(self, client, org_and_team, environment):
        """Create a change, transition through every state, confirm audit trail."""
        team_id = org_and_team["team_id"]
        env_id = environment["id"]

        # 1. Create a change with pre-flight answers and steps
        create_resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Update connection pool on PROD-EU-01",
                "description": "Increase max_connections from 100 to 150",
                "team_id": team_id,
                "author_name": "Adrian Hornsby",
                "environment_ids": [env_id],
                "preflight_answers": {
                    "what_is_this_change": "Increase connection pool from 100 to 150",
                    "who_is_using": "Portfolio managers running EOD batch processing",
                    "customer_mid_failure": "EOD batch would fail, positions not reconciled",
                    "what_if_fails": "Connections rejected, batch processing halts",
                    "rollback_plan": "ALTER SYSTEM SET max_connections = 100; restart",
                    "rollback_duration": "2 minutes. Customer sees brief connection drop.",
                    "blast_radius": "Single environment, ~50 users",
                    "maintenance_window": "Saturday 22:00-02:00 UTC",
                    "why_this_time": "Lowest impact — no trading, no EOD batch",
                },
                "defence_tags": ["monitoring"],
                "steps": [
                    {
                        "description": "Verify current parameter value",
                        "expected_outcome": "max_connections = 100",
                        "rollback_action": "N/A",
                        "script": "SHOW max_connections;",
                    },
                    {
                        "description": "Take parameter backup",
                        "expected_outcome": "Backup file written",
                        "rollback_action": "N/A",
                    },
                    {
                        "description": "Update connection pool parameter",
                        "expected_outcome": "Parameter set to 150",
                        "rollback_action": "ALTER SYSTEM SET max_connections = 100;",
                        "script": "ALTER SYSTEM SET max_connections = 150;",
                        "is_hold_point": True,
                    },
                    {
                        "description": "Restart connection pool",
                        "expected_outcome": "Pool restarted, accepting connections",
                        "rollback_action": "Restart with old configuration",
                    },
                ],
            },
        )
        assert create_resp.status_code == 201
        change = create_resp.json()
        change_id = change["id"]

        assert change["status"] == "draft"
        assert len(change["steps"]) == 4
        assert change["steps"][2]["is_hold_point"] is True
        assert change["environment_ids"] == [env_id]
        assert change["defence_tags"] == ["monitoring"]

        # 2. Verify pre-flight answers persisted correctly (JSONB on Postgres)
        detail = client.get(f"/api/v1/changes/{change_id}").json()
        assert detail["preflight_answers"]["who_is_using"] == (
            "Portfolio managers running EOD batch processing"
        )
        assert detail["preflight_answers"]["rollback_plan"] == (
            "ALTER SYSTEM SET max_connections = 100; restart"
        )

        # 3. Walk through the full state machine
        transitions = [
            ("in_review", "Submit for review"),
            ("approved", "Reviewer approves"),
            ("executing", "Start execution"),
            ("awaiting_verification", "Execution complete"),
            ("verified", "Verification passed"),
            ("closed", "Close the change"),
        ]

        for target_status, description in transitions:
            resp = client.post(
                f"/api/v1/changes/{change_id}/transition",
                params={
                    "target_status": target_status,
                    "actor_name": "Adrian Hornsby",
                },
            )
            assert resp.status_code == 200, f"Failed at '{description}': {resp.json()}"
            assert resp.json()["status"] == target_status

        # 4. Confirm the change is closed and immutable
        final = client.get(f"/api/v1/changes/{change_id}").json()
        assert final["status"] == "closed"

        # 5. Confirm closed changes cannot transition
        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "draft", "actor_name": "Adrian Hornsby"},
        )
        assert resp.status_code == 422


class TestPostgresSpecificBehaviour:
    """Tests that exercise Postgres-specific features (JSONB, UUID)."""

    def test_jsonb_preflight_stored_and_retrieved(self, client, org_and_team):
        """JSONB preflight answers survive a round trip through Postgres."""
        nested_answers = {
            "what_is_this_change": "Complex nested test",
            "custom_field": "Custom value with special chars: é à ü ñ 日本語",
            "numeric_field": "42",
        }

        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "JSONB round-trip test",
                "team_id": org_and_team["team_id"],
                "author_name": "Test",
                "preflight_answers": nested_answers,
            },
        )
        assert resp.status_code == 201
        change_id = resp.json()["id"]

        detail = client.get(f"/api/v1/changes/{change_id}").json()
        assert detail["preflight_answers"] == nested_answers

    def test_uuid_foreign_keys_enforced(self, client, org_and_team):
        """Foreign key constraints are enforced on Postgres (not on SQLite)."""
        fake_team_id = "00000000-0000-0000-0000-000000000099"
        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Bad FK test",
                "team_id": fake_team_id,
                "author_name": "Test",
            },
        )
        # Postgres enforces the FK constraint — returns 422
        assert resp.status_code == 422
        assert "constraint" in resp.json()["detail"].lower()

    def test_multiple_environments_as_json_array(self, client, org_and_team):
        """Multiple environment IDs stored as JSON array in Postgres."""
        org_id = org_and_team["org_id"]

        # Create three environments
        env_ids = []
        for name in ["PROD-EU-01", "PROD-EU-02", "PROD-US-01"]:
            resp = client.post(
                "/api/v1/environments",
                json={
                    "name": name,
                    "platform": "Azure",
                    "organisation_id": org_id,
                },
            )
            env_ids.append(resp.json()["id"])

        # Create a change targeting all three
        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Multi-env change",
                "team_id": org_and_team["team_id"],
                "author_name": "Test",
                "environment_ids": env_ids,
            },
        )
        assert resp.status_code == 201
        assert sorted(resp.json()["environment_ids"]) == sorted(env_ids)

    def test_defence_tags_as_json_array(self, client, org_and_team):
        """Defence tags stored and retrieved correctly."""
        tags = ["monitoring", "alerting", "DR", "backup"]
        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Defence tag test",
                "team_id": org_and_team["team_id"],
                "author_name": "Test",
                "defence_tags": tags,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["defence_tags"] == tags


class TestFilterAndList:
    """List and filter operations against Postgres."""

    def test_filter_by_status(self, client, org_and_team):
        """Changes can be filtered by status."""
        team_id = org_and_team["team_id"]

        # Create two changes, advance one to in_review
        client.post(
            "/api/v1/changes",
            json={"title": "Draft change", "team_id": team_id, "author_name": "Test"},
        )
        resp2 = client.post(
            "/api/v1/changes",
            json={"title": "Reviewed change", "team_id": team_id, "author_name": "Test"},
        )
        change2_id = resp2.json()["id"]
        client.post(
            f"/api/v1/changes/{change2_id}/transition",
            params={"target_status": "in_review", "actor_name": "Test"},
        )

        # Filter by draft — should get 1
        drafts = client.get("/api/v1/changes", params={"status": "draft"}).json()
        assert drafts["meta"]["total"] == 1
        assert drafts["data"][0]["title"] == "Draft change"

        # Filter by in_review — should get 1
        reviews = client.get("/api/v1/changes", params={"status": "in_review"}).json()
        assert reviews["meta"]["total"] == 1
        assert reviews["data"][0]["title"] == "Reviewed change"

    def test_pagination(self, client, org_and_team):
        """Pagination works correctly."""
        team_id = org_and_team["team_id"]

        for i in range(5):
            client.post(
                "/api/v1/changes",
                json={"title": f"Change {i}", "team_id": team_id, "author_name": "Test"},
            )

        page1 = client.get("/api/v1/changes", params={"limit": 2, "offset": 0}).json()
        assert len(page1["data"]) == 2
        assert page1["meta"]["total"] == 5

        page2 = client.get("/api/v1/changes", params={"limit": 2, "offset": 2}).json()
        assert len(page2["data"]) == 2

        page3 = client.get("/api/v1/changes", params={"limit": 2, "offset": 4}).json()
        assert len(page3["data"]) == 1
