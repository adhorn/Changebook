"""Tests for the change template library.

Templates capture reusable procedures (checklists, defence tags, general
preflight answers) without context (customer, service, environment).
"""


class TestTemplateLifecycle:
    """Create, list, and use templates."""

    def test_create_template_from_scratch(self, client):
        resp = client.post(
            "/api/v1/templates",
            json={
                "title": "Connection pool resize",
                "description": "Standard procedure for resizing DB connection pools",
                "defence_tags": ["database"],
                "items": [
                    {
                        "phase": "pre_flight",
                        "description": "Check current pool size",
                        "command": 'psql -c "SHOW max_connections;"',
                        "expected_outcome": "Shows current value",
                    },
                    {
                        "phase": "execution",
                        "description": "Update pool parameter",
                        "command": 'psql -c "ALTER SYSTEM SET max_connections = NEW_VALUE;"',
                        "rollback_action": "Set back to original value",
                    },
                    {
                        "phase": "verification",
                        "description": "Confirm new value",
                        "command": 'psql -c "SHOW max_connections;"',
                        "expected_outcome": "Shows new value",
                    },
                ],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Connection pool resize"
        assert data["defence_tags"] == ["database"]
        assert data["item_count"] == 3
        assert len(data["items"]) == 3
        assert data["items"][0]["phase"] == "pre_flight"
        assert data["items"][1]["phase"] == "execution"

    def test_list_templates(self, client):
        for i in range(3):
            client.post(
                "/api/v1/templates",
                json={"title": f"Template {i}"},
            )
        resp = client.get("/api/v1/templates")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_list_templates_search(self, client):
        client.post("/api/v1/templates", json={"title": "DB resize"})
        client.post("/api/v1/templates", json={"title": "Cert rotation"})

        resp = client.get("/api/v1/templates?title_search=cert")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert "Cert" in resp.json()[0]["title"]

    def test_get_template_detail(self, client):
        create = client.post(
            "/api/v1/templates",
            json={
                "title": "Firewall rule update",
                "items": [
                    {"phase": "execution", "description": "Apply rule"},
                ],
            },
        )
        tid = create.json()["id"]

        resp = client.get(f"/api/v1/templates/{tid}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Firewall rule update"
        assert len(resp.json()["items"]) == 1

    def test_template_not_found(self, client):
        resp = client.get("/api/v1/templates/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


class TestSaveAsTemplate:
    """Save an existing change as a template."""

    def test_save_change_as_template(self, client, sample_change_data):
        # Create a change with checklist items
        change = client.post(
            "/api/v1/changes",
            json={
                "title": "Resize pool on PROD-EU",
                "defence_tags": ["database"],
                "preflight_answers": {
                    "what_if_fails": "Connections rejected",
                    "rollback_plan": "Set back to 100",
                    "customer_aware": "Yes, discussed in weekly call",
                    "maintenance_communicated": "Yes, calendar updated",
                },
                **sample_change_data,
            },
        )
        change_id = change.json()["id"]

        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={
                "phase": "pre_flight",
                "description": "Check current size",
                "command": 'psql -c "SHOW max_connections;"',
            },
        )
        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={
                "phase": "execution",
                "description": "Update parameter",
            },
        )
        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={
                "phase": "verification",
                "description": "Verify new value",
            },
        )

        # Save as template
        resp = client.post(
            f"/api/v1/changes/{change_id}/save-as-template",
            json={"title": "DB pool resize procedure"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "DB pool resize procedure"
        assert data["source_change_id"] == change_id
        assert data["defence_tags"] == ["database"]
        assert data["item_count"] == 3
        # General preflight answers are carried over
        assert data["preflight_answers"]["what_if_fails"] == "Connections rejected"
        assert data["preflight_answers"]["rollback_plan"] == "Set back to 100"
        # Customer-specific answers are excluded
        assert "customer_aware" not in data["preflight_answers"]
        assert "maintenance_communicated" not in data["preflight_answers"]

    def test_save_as_template_default_title(self, client, sample_change_data):
        change = client.post(
            "/api/v1/changes",
            json={"title": "My change", **sample_change_data},
        )
        change_id = change.json()["id"]

        resp = client.post(
            f"/api/v1/changes/{change_id}/save-as-template",
            json={},
        )
        assert resp.status_code == 201
        assert resp.json()["title"] == "My change (template)"


class TestUseTemplate:
    """Create a new change from a template."""

    def test_use_template_creates_draft(self, client, sample_change_data):
        # Create a template with items
        tmpl = client.post(
            "/api/v1/templates",
            json={
                "title": "Cert rotation",
                "defence_tags": ["security"],
                "preflight_answers": {
                    "rollback_plan": "Restore old cert from backup",
                },
                "items": [
                    {
                        "phase": "pre_flight",
                        "description": "Check cert expiry",
                        "command": "openssl x509 -enddate -noout -in cert.pem",
                    },
                    {
                        "phase": "execution",
                        "description": "Deploy new cert",
                    },
                    {
                        "phase": "verification",
                        "description": "Verify TLS handshake",
                        "command": "openssl s_client -connect host:443",
                    },
                ],
            },
        )
        template_id = tmpl.json()["id"]

        # Use the template
        resp = client.post(
            f"/api/v1/templates/{template_id}/use",
            json={
                "title": "Rotate cert on PROD-EU web servers",
                **sample_change_data,
            },
        )
        assert resp.status_code == 201
        change_id = resp.json()["change_id"]

        # Verify the change was created correctly
        change = client.get(f"/api/v1/changes/{change_id}")
        assert change.status_code == 200
        cdata = change.json()
        assert cdata["status"] == "draft"
        assert cdata["title"] == "Rotate cert on PROD-EU web servers"
        assert cdata["defence_tags"] == ["security"]
        assert cdata["preflight_answers"]["rollback_plan"] == "Restore old cert from backup"

        # Verify checklist was copied
        items = client.get(f"/api/v1/changes/{change_id}/checklist")
        assert len(items.json()) == 3
        assert items.json()[0]["description"] == "Check cert expiry"
        assert items.json()[0]["command"] is not None
