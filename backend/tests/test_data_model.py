"""Tests for the aligned data model (Feature 1).

These tests define the expected data model before implementation.
The model must match the operator experience spec:
- One change = one customer, one service, one environment
- No team_id on changes
- Checklist items unified across three phases (pre_flight, execution, verification)
- Defence tags validated against a predefined set
- cloned_from for duplicate flow
"""

from app.models.change import ALLOWED_DEFENCE_TAGS


class TestChangeModel:
    """A change targets one customer, one service, one environment."""

    def test_create_change_single_customer_and_environment(self, client, org_and_team):
        """A change targets exactly one customer and one environment."""
        customer = client.post(
            "/api/v1/customers",
            json={
                "name": "Pension Fund Alpha",
                "services": [{"name": "Portfolio Management"}],
            },
        )
        customer_id = customer.json()["id"]
        service_id = customer.json()["services"][0]["id"]

        env = client.post(
            "/api/v1/environments",
            json={"name": "PROD-EU-01", "platform": "Azure"},
        )
        env_id = env.json()["id"]

        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Update connection pool",
                "description": "Increase max_connections from 100 to 150",
                "customer_id": customer_id,
                "service_id": service_id,
                "environment_id": env_id,
                "author_name": "Adrian Hornsby",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["customer_id"] == customer_id
        assert data["service_id"] == service_id
        assert data["environment_id"] == env_id
        assert data["author_name"] == "Adrian Hornsby"
        assert data["status"] == "draft"
        # No team_id in the response
        assert "team_id" not in data

    def test_create_change_requires_customer(self, client, org_and_team):
        """A change must have a customer_id."""
        env = client.post(
            "/api/v1/environments",
            json={"name": "PROD-01", "platform": "AWS"},
        )
        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Missing customer",
                "environment_id": env.json()["id"],
                "service_id": "00000000-0000-0000-0000-000000000001",
                "author_name": "Test",
            },
        )
        assert resp.status_code == 422

    def test_create_change_requires_environment(self, client, org_and_team):
        """A change must have an environment_id."""
        customer = client.post(
            "/api/v1/customers",
            json={
                "name": "Test Client",
                "services": [{"name": "Core Platform"}],
            },
        )
        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Missing environment",
                "customer_id": customer.json()["id"],
                "service_id": customer.json()["services"][0]["id"],
                "author_name": "Test",
            },
        )
        assert resp.status_code == 422

    def test_create_change_with_cloned_from(self, client, org_and_team):
        """A change can reference the change it was cloned from."""
        customer = client.post(
            "/api/v1/customers",
            json={
                "name": "Client A",
                "services": [{"name": "Trading"}],
            },
        )
        env = client.post(
            "/api/v1/environments",
            json={"name": "PROD-01", "platform": "Azure"},
        )

        # Create original
        original = client.post(
            "/api/v1/changes",
            json={
                "title": "Original change",
                "customer_id": customer.json()["id"],
                "service_id": customer.json()["services"][0]["id"],
                "environment_id": env.json()["id"],
                "author_name": "Test",
            },
        )
        original_id = original.json()["id"]

        # Create clone referencing original
        clone = client.post(
            "/api/v1/changes",
            json={
                "title": "Cloned change",
                "customer_id": customer.json()["id"],
                "service_id": customer.json()["services"][0]["id"],
                "environment_id": env.json()["id"],
                "author_name": "Test",
                "cloned_from": original_id,
            },
        )
        assert clone.status_code == 201
        assert clone.json()["cloned_from"] == original_id


class TestDefenceTags:
    """Defence tags must come from a predefined set."""

    def test_valid_defence_tags(self, client, org_and_team):
        """Valid tags are accepted."""
        customer = client.post(
            "/api/v1/customers",
            json={
                "name": "Tag Client",
                "services": [{"name": "Platform"}],
            },
        )
        env = client.post(
            "/api/v1/environments",
            json={"name": "PROD-01", "platform": "AWS"},
        )

        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Tagged change",
                "customer_id": customer.json()["id"],
                "service_id": customer.json()["services"][0]["id"],
                "environment_id": env.json()["id"],
                "author_name": "Test",
                "defence_tags": ["monitoring", "alerting"],
            },
        )
        assert resp.status_code == 201
        assert resp.json()["defence_tags"] == ["monitoring", "alerting"]

    def test_invalid_defence_tag_rejected(self, client, org_and_team):
        """Tags not in the predefined set are rejected."""
        customer = client.post(
            "/api/v1/customers",
            json={
                "name": "Tag Client",
                "services": [{"name": "Platform"}],
            },
        )
        env = client.post(
            "/api/v1/environments",
            json={"name": "PROD-01", "platform": "AWS"},
        )

        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Bad tag change",
                "customer_id": customer.json()["id"],
                "service_id": customer.json()["services"][0]["id"],
                "environment_id": env.json()["id"],
                "author_name": "Test",
                "defence_tags": ["monitoring", "made_up_tag"],
            },
        )
        assert resp.status_code == 422

    def test_predefined_tags_exist(self):
        """The predefined tag set includes the expected defaults."""
        expected = {
            "monitoring",
            "alerting",
            "security",
            "access_control",
            "DR",
            "backup",
            "networking",
            "database",
            "application",
        }
        assert expected == set(ALLOWED_DEFENCE_TAGS)


class TestChecklistItem:
    """Checklist items are unified across three phases."""

    def _create_change(self, client):
        """Helper: create a change with customer, service, environment."""
        customer = client.post(
            "/api/v1/customers",
            json={
                "name": "Checklist Client",
                "services": [{"name": "Core"}],
            },
        )
        env = client.post(
            "/api/v1/environments",
            json={"name": "PROD-01", "platform": "AWS"},
        )
        change = client.post(
            "/api/v1/changes",
            json={
                "title": "Checklist test",
                "customer_id": customer.json()["id"],
                "service_id": customer.json()["services"][0]["id"],
                "environment_id": env.json()["id"],
                "author_name": "Test",
            },
        )
        return change.json()["id"]

    def test_add_preflight_item(self, client, org_and_team):
        """A checklist item can be added to the pre_flight phase."""
        change_id = self._create_change(client)

        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={
                "phase": "pre_flight",
                "description": "Verify current parameter value",
                "command": "SHOW max_connections;",
                "expected_outcome": "max_connections = 100",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["phase"] == "pre_flight"
        assert data["order"] == 1
        assert data["command"] == "SHOW max_connections;"
        assert data["is_hold_point"] is False

    def test_add_execution_item(self, client, org_and_team):
        """A checklist item can be added to the execution phase."""
        change_id = self._create_change(client)

        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={
                "phase": "execution",
                "description": "Update connection pool parameter",
                "command": "ALTER SYSTEM SET max_connections = 150;",
                "expected_outcome": "Parameter set to 150",
                "rollback_action": "ALTER SYSTEM SET max_connections = 100;",
                "is_hold_point": True,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["phase"] == "execution"
        assert data["rollback_action"] == "ALTER SYSTEM SET max_connections = 100;"
        assert data["is_hold_point"] is True

    def test_add_verification_item(self, client, org_and_team):
        """A checklist item can be added to the verification phase."""
        change_id = self._create_change(client)

        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={
                "phase": "verification",
                "description": "Confirm customer can log in",
                "expected_outcome": "Login successful",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["phase"] == "verification"

    def test_items_auto_ordered_within_phase(self, client, org_and_team):
        """Items within a phase are automatically ordered sequentially."""
        change_id = self._create_change(client)

        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "execution", "description": "Step one"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "execution", "description": "Step two"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "execution", "description": "Step three"},
        )

        resp = client.get(
            f"/api/v1/changes/{change_id}/checklist",
            params={"phase": "execution"},
        )
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 3
        assert items[0]["order"] == 1
        assert items[1]["order"] == 2
        assert items[2]["order"] == 3

    def test_items_ordered_independently_per_phase(self, client, org_and_team):
        """Each phase has its own ordering — adding to one doesn't affect another."""
        change_id = self._create_change(client)

        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "pre_flight", "description": "Pre-check 1"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "execution", "description": "Exec step 1"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "pre_flight", "description": "Pre-check 2"},
        )

        preflight = client.get(
            f"/api/v1/changes/{change_id}/checklist",
            params={"phase": "pre_flight"},
        ).json()
        execution = client.get(
            f"/api/v1/changes/{change_id}/checklist",
            params={"phase": "execution"},
        ).json()

        assert len(preflight) == 2
        assert preflight[0]["order"] == 1
        assert preflight[1]["order"] == 2
        assert len(execution) == 1
        assert execution[0]["order"] == 1

    def test_invalid_phase_rejected(self, client, org_and_team):
        """An invalid phase name is rejected."""
        change_id = self._create_change(client)

        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "made_up_phase", "description": "Bad phase"},
        )
        assert resp.status_code == 422

    def test_get_all_checklist_items(self, client, org_and_team):
        """All checklist items across all phases can be retrieved."""
        change_id = self._create_change(client)

        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "pre_flight", "description": "Pre-check"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "execution", "description": "Exec step"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "verification", "description": "Verify"},
        )

        resp = client.get(f"/api/v1/changes/{change_id}/checklist")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 3
        phases = {item["phase"] for item in items}
        assert phases == {"pre_flight", "execution", "verification"}
