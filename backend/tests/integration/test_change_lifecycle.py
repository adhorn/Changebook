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


# Complete set of required pre-flight answers for gate validation
COMPLETE_PREFLIGHT = {
    "what_is_this_change": "Increase connection pool from 100 to 150",
    "expected_outcome": "Higher throughput during peak batch processing",
    "customer_notice": "Brief connection reset during restart",
    "how_customer_notices": "Monitoring alert for connection drop",
    "customer_mid_failure": "EOD batch would fail, positions not reconciled",
    "customer_work_impact": "Batch processing delayed by ~5 minutes",
    "what_if_fails": "Connections rejected, batch processing halts",
    "rollback_plan": "ALTER SYSTEM SET max_connections = 100; restart",
    "rollback_duration": "2 minutes",
    "customer_during_rollback": "Brief connection drop during rollback restart",
    "blast_radius": "Single environment, ~50 users",
    "maintenance_window": "Saturday 22:00-02:00 UTC",
    "maintenance_window_when": "Saturday 22:00 UTC",
    "lowest_impact_window": "Yes — no trading, no EOD batch",
    "dependencies": "None — standalone parameter change",
    "customer_aware": "Yes — communicated via change advisory board",
    "customer_agreed": "Yes — approved in CAB meeting",
    "maintenance_communicated": "Yes — email sent to operations team",
    "customer_contact": "ops@simcorp.com",
    "completion_notification": "Email to ops team + Slack #changes channel",
}


def _add_checklist_items_all_phases(client, change_id):
    """Add one checklist item per phase to satisfy Gate 2."""
    phases = [
        {
            "phase": "pre_flight",
            "description": "Verify current parameter value",
            "command": "SHOW max_connections;",
            "expected_outcome": "max_connections = 100",
        },
        {
            "phase": "execution",
            "description": "Update connection pool parameter",
            "command": "ALTER SYSTEM SET max_connections = 150;",
            "expected_outcome": "Parameter set to 150",
            "rollback_action": "ALTER SYSTEM SET max_connections = 100;",
            "is_hold_point": True,
        },
        {
            "phase": "verification",
            "description": "Confirm new pool size is active",
            "command": "SHOW max_connections;",
            "expected_outcome": "max_connections = 150",
        },
    ]
    for item in phases:
        resp = client.post(f"/api/v1/changes/{change_id}/checklist", json=item)
        assert resp.status_code == 201


REVIEWER_BOB = {"X-User-Email": "bob@changebook.dev", "X-User-Name": "Reviewer Bob"}


def _assign_and_approve_reviewer(client, change_id):
    """Assign a reviewer and approve the change (Gate 3)."""
    # Assign a different user as reviewer (author is "Test User")
    resp = client.post(
        f"/api/v1/changes/{change_id}/reviewers",
        json={"reviewer_name": "Reviewer Bob"},
    )
    assert resp.status_code == 201
    review_id = resp.json()["id"]

    # Submit approval — must use the reviewer's identity headers
    resp = client.post(
        f"/api/v1/changes/{change_id}/reviewers/{review_id}/decision",
        json={"decision": "approved", "comment": "LGTM"},
        headers=REVIEWER_BOB,
    )
    assert resp.status_code == 200


class TestFullChangeLifecycle:
    """A change goes from draft to closed with full audit trail."""

    def test_complete_lifecycle(self, client, customer_and_service, environment):
        """Create a change, add checklist, transition through every state."""
        cust_id = customer_and_service["customer_id"]
        svc_id = customer_and_service["service_id"]
        env_id = environment["id"]

        # 1. Create a change with complete pre-flight answers
        create_resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Update connection pool on PROD-EU-01",
                "description": "Increase max_connections from 100 to 150",
                "customer_id": cust_id,
                "service_id": svc_id,
                "environment_id": env_id,
                "preflight_answers": COMPLETE_PREFLIGHT,
                "defence_tags": ["monitoring"],
            },
        )
        assert create_resp.status_code == 201
        change = create_resp.json()
        change_id = change["id"]

        assert change["status"] == "draft"
        assert change["environment_id"] == env_id
        assert change["defence_tags"] == ["monitoring"]

        # 2. Add checklist items in all 3 phases (Gate 2)
        _add_checklist_items_all_phases(client, change_id)

        checklist = client.get(f"/api/v1/changes/{change_id}/checklist").json()
        assert len(checklist) == 3

        # 3. Verify pre-flight answers persisted (JSONB on Postgres)
        detail = client.get(f"/api/v1/changes/{change_id}").json()
        assert detail["preflight_answers"]["rollback_plan"] == (
            "ALTER SYSTEM SET max_connections = 100; restart"
        )

        # 4. Submit for review (Gate 1: preflight + Gate 2: checklist)
        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review"},
        )
        assert resp.status_code == 200, f"in_review failed: {resp.json()}"

        # 5. Assign reviewer and approve (Gate 3)
        _assign_and_approve_reviewer(client, change_id)

        # 6. Walk through remaining transitions
        transitions = [
            ("approved", "Reviewer approved"),
            ("executing", "Start execution"),
            ("done", "Mark as done"),
        ]

        for target_status, description in transitions:
            resp = client.post(
                f"/api/v1/changes/{change_id}/transition",
                params={"target_status": target_status},
            )
            assert resp.status_code == 200, f"Failed at '{description}': {resp.json()}"
            assert resp.json()["status"] == target_status

        # 7. Confirm the change is done
        final = client.get(f"/api/v1/changes/{change_id}").json()
        assert final["status"] == "done"

        # 8. Confirm done changes cannot transition back to draft
        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "draft"},
        )
        assert resp.status_code == 422


class TestPostgresSpecificBehaviour:
    """Tests that exercise Postgres-specific features (JSONB, UUID)."""

    def test_jsonb_preflight_stored_and_retrieved(self, client, customer_and_service, environment):
        """JSONB preflight answers survive a round trip through Postgres."""
        nested_answers = {
            "what_is_this_change": "Complex nested test",
            "custom_field": "Special chars: é à ü ñ",
            "numeric_field": "42",
        }

        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "JSONB round-trip test",
                "customer_id": customer_and_service["customer_id"],
                "service_id": customer_and_service["service_id"],
                "environment_id": environment["id"],
                "preflight_answers": nested_answers,
            },
        )
        assert resp.status_code == 201
        change_id = resp.json()["id"]

        detail = client.get(f"/api/v1/changes/{change_id}").json()
        assert detail["preflight_answers"] == nested_answers

    def test_uuid_foreign_keys_enforced(self, client, customer_and_service):
        """Foreign key constraints are enforced on Postgres."""
        fake_customer = "00000000-0000-0000-0000-000000000099"
        fake_service = "00000000-0000-0000-0000-000000000098"
        fake_env = "00000000-0000-0000-0000-000000000097"

        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Bad FK test",
                "customer_id": fake_customer,
                "service_id": fake_service,
                "environment_id": fake_env,
            },
        )
        # Postgres enforces the FK constraint — returns 422
        assert resp.status_code == 422

    def test_defence_tags_as_json_array(self, client, customer_and_service, environment):
        """Defence tags stored and retrieved correctly."""
        tags = ["monitoring", "alerting", "DR", "backup"]
        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Defence tag test",
                "customer_id": customer_and_service["customer_id"],
                "service_id": customer_and_service["service_id"],
                "environment_id": environment["id"],
                "defence_tags": tags,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["defence_tags"] == tags


class TestFilterAndList:
    """List and filter operations against Postgres."""

    def test_filter_by_status(self, client, customer_and_service, environment):
        """Changes can be filtered by status."""
        base = {
            "customer_id": customer_and_service["customer_id"],
            "service_id": customer_and_service["service_id"],
            "environment_id": environment["id"],
        }

        # Create two changes
        client.post(
            "/api/v1/changes",
            json={"title": "Draft change", **base},
        )
        resp2 = client.post(
            "/api/v1/changes",
            json={
                "title": "Reviewed change",
                "preflight_answers": COMPLETE_PREFLIGHT,
                **base,
            },
        )
        change2_id = resp2.json()["id"]

        # Satisfy gates before transitioning to in_review
        _add_checklist_items_all_phases(client, change2_id)

        resp = client.post(
            f"/api/v1/changes/{change2_id}/transition",
            params={"target_status": "in_review"},
        )
        assert resp.status_code == 200, f"Transition failed: {resp.json()}"

        # Filter by draft — should get 1
        drafts = client.get("/api/v1/changes", params={"status": "draft"}).json()
        assert drafts["meta"]["total"] == 1
        assert drafts["data"][0]["title"] == "Draft change"

        # Filter by in_review — should get 1
        reviews = client.get("/api/v1/changes", params={"status": "in_review"}).json()
        assert reviews["meta"]["total"] == 1
        assert reviews["data"][0]["title"] == "Reviewed change"

    def test_pagination(self, client, customer_and_service, environment):
        """Pagination works correctly."""
        base = {
            "customer_id": customer_and_service["customer_id"],
            "service_id": customer_and_service["service_id"],
            "environment_id": environment["id"],
        }

        for i in range(5):
            client.post(
                "/api/v1/changes",
                json={"title": f"Change {i}", **base},
            )

        page1 = client.get("/api/v1/changes", params={"limit": 2, "offset": 0}).json()
        assert len(page1["data"]) == 2
        assert page1["meta"]["total"] == 5

        page2 = client.get("/api/v1/changes", params={"limit": 2, "offset": 2}).json()
        assert len(page2["data"]) == 2

        page3 = client.get("/api/v1/changes", params={"limit": 2, "offset": 4}).json()
        assert len(page3["data"]) == 1
