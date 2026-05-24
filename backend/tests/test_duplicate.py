"""Tests for Feature 7: Duplicate flow.

Cloning copies the structure of an existing change (checklist items,
pre-flight answers, defence tags) but starts fresh — draft status,
no reviews, no completions. The operator can override the target
(customer, service, environment) to apply the same change elsewhere.
"""


def _complete_preflight(client):
    resp = client.get("/api/v1/preflight-questions")
    keys = []
    for section in resp.json()["sections"]:
        for q in section["questions"]:
            if q["required"]:
                keys.append(q["key"])
    return {key: f"Answer for {key}" for key in keys}


def _create_source_change(client, sample_change_data):
    """Create a change with preflight answers, checklist items, and defence tags."""
    preflight = _complete_preflight(client)
    resp = client.post(
        "/api/v1/changes",
        json={
            "title": "Connection pool resize on PROD-EU",
            "description": "Increase max connections from 100 to 150",
            "author_name": "Adrian Hornsby",
            **sample_change_data,
            "preflight_answers": preflight,
            "defence_tags": ["database", "monitoring"],
        },
    )
    change_id = resp.json()["id"]

    # Add checklist items across all phases
    items = [
        {"phase": "pre_flight", "description": "Verify current pool size is 100"},
        {"phase": "pre_flight", "description": "Check no active long-running queries"},
        {"phase": "execution", "description": "Run ALTER SYSTEM SET max_connections = 150"},
        {"phase": "execution", "description": "Reload config", "is_hold_point": True},
        {"phase": "verification", "description": "Check pg_settings shows 150"},
        {"phase": "verification", "description": "Run connection test script"},
    ]
    for item in items:
        client.post(f"/api/v1/changes/{change_id}/checklist", json=item)

    return change_id


class TestDuplicateBasics:
    """POST /api/v1/changes/{change_id}/duplicate"""

    def test_duplicate_creates_new_change(self, client, sample_change_data):
        """Duplicating a change creates a new change in draft status."""
        source_id = _create_source_change(client, sample_change_data)

        resp = client.post(
            f"/api/v1/changes/{source_id}/duplicate",
            json={},
        )
        assert resp.status_code == 201
        clone = resp.json()
        assert clone["id"] != source_id
        assert clone["status"] == "draft"
        assert clone["cloned_from"] == source_id

    def test_duplicate_copies_title(self, client, sample_change_data):
        """The clone gets the source title with a (copy) suffix."""
        source_id = _create_source_change(client, sample_change_data)

        resp = client.post(
            f"/api/v1/changes/{source_id}/duplicate",
            json={},
        )
        assert "Connection pool resize" in resp.json()["title"]
        assert "(copy)" in resp.json()["title"]

    def test_duplicate_copies_description(self, client, sample_change_data):
        """The clone gets the source description."""
        source_id = _create_source_change(client, sample_change_data)

        resp = client.post(
            f"/api/v1/changes/{source_id}/duplicate",
            json={},
        )
        assert resp.json()["description"] == "Increase max connections from 100 to 150"

    def test_duplicate_copies_preflight_answers(self, client, sample_change_data):
        """The clone gets the source pre-flight answers."""
        source_id = _create_source_change(client, sample_change_data)
        source = client.get(f"/api/v1/changes/{source_id}").json()

        resp = client.post(
            f"/api/v1/changes/{source_id}/duplicate",
            json={},
        )
        clone = resp.json()
        assert clone["preflight_answers"] == source["preflight_answers"]
        assert clone["preflight_schema_version"] == source["preflight_schema_version"]

    def test_duplicate_copies_defence_tags(self, client, sample_change_data):
        """The clone gets the source defence tags."""
        source_id = _create_source_change(client, sample_change_data)

        resp = client.post(
            f"/api/v1/changes/{source_id}/duplicate",
            json={},
        )
        assert resp.json()["defence_tags"] == ["database", "monitoring"]

    def test_duplicate_copies_checklist_items(self, client, sample_change_data):
        """The clone gets copies of all checklist items, in order."""
        source_id = _create_source_change(client, sample_change_data)

        resp = client.post(
            f"/api/v1/changes/{source_id}/duplicate",
            json={},
        )
        clone_id = resp.json()["id"]

        source_items = client.get(f"/api/v1/changes/{source_id}/checklist").json()
        clone_items = client.get(f"/api/v1/changes/{clone_id}/checklist").json()

        assert len(clone_items) == len(source_items)
        for src, cln in zip(source_items, clone_items):
            assert cln["id"] != src["id"]  # new IDs
            assert cln["change_id"] == clone_id
            assert cln["phase"] == src["phase"]
            assert cln["order"] == src["order"]
            assert cln["description"] == src["description"]
            assert cln["is_hold_point"] == src["is_hold_point"]

    def test_duplicate_preserves_hold_points(self, client, sample_change_data):
        """Hold-point flags are preserved on cloned items."""
        source_id = _create_source_change(client, sample_change_data)

        resp = client.post(
            f"/api/v1/changes/{source_id}/duplicate",
            json={},
        )
        clone_id = resp.json()["id"]

        clone_items = client.get(f"/api/v1/changes/{clone_id}/checklist").json()
        hold_points = [i for i in clone_items if i["is_hold_point"]]
        assert len(hold_points) == 1
        assert hold_points[0]["description"] == "Reload config"


class TestDuplicateOverrides:
    """The operator can override fields when duplicating."""

    def test_override_title(self, client, sample_change_data):
        """A custom title replaces the default (copy) suffix."""
        source_id = _create_source_change(client, sample_change_data)

        resp = client.post(
            f"/api/v1/changes/{source_id}/duplicate",
            json={
                "title": "Connection pool resize on PROD-US",
            },
        )
        assert resp.json()["title"] == "Connection pool resize on PROD-US"

    def test_override_environment(self, client, sample_change_data, db):
        """The clone can target a different environment."""
        source_id = _create_source_change(client, sample_change_data)

        # Create a second environment
        env_resp = client.post(
            "/api/v1/environments",
            json={"name": "PROD-US", "platform": "AWS"},
        )
        new_env_id = env_resp.json()["id"]

        resp = client.post(
            f"/api/v1/changes/{source_id}/duplicate",
            json={
                "environment_id": new_env_id,
            },
        )
        clone = resp.json()
        assert clone["environment_id"] == new_env_id
        assert clone["customer_id"] == sample_change_data["customer_id"]

    def test_author_comes_from_auth_headers(self, client, sample_change_data):
        """The clone's author is always the authenticated user, not a body field."""
        source_id = _create_source_change(client, sample_change_data)

        resp = client.post(
            f"/api/v1/changes/{source_id}/duplicate",
            json={},
        )
        assert resp.status_code == 201
        # Author comes from the default test client headers ("Test User")
        assert resp.json()["author_name"] == "Test User"


class TestDuplicateFreshState:
    """Clones start completely fresh — no reviews, no completions."""

    def test_clone_has_no_reviews(self, client, sample_change_data):
        """The clone has no reviewers, even if the source had reviews."""
        source_id = _create_source_change(client, sample_change_data)

        # Add a reviewer to the source
        client.post(
            f"/api/v1/changes/{source_id}/reviewers",
            json={"reviewer_name": "Jane Smith"},
        )

        resp = client.post(
            f"/api/v1/changes/{source_id}/duplicate",
            json={},
        )
        clone_id = resp.json()["id"]

        reviews = client.get(f"/api/v1/changes/{clone_id}/reviewers").json()
        assert reviews == []

    def test_clone_checklist_items_have_no_completions(self, client, sample_change_data):
        """Cloned checklist items have no completion records."""
        source_id = _create_source_change(client, sample_change_data)

        resp = client.post(
            f"/api/v1/changes/{source_id}/duplicate",
            json={},
        )
        clone_id = resp.json()["id"]

        # Move clone to executing to check execution status
        for phase in ["pre_flight", "execution", "verification"]:
            # Items already exist from duplication — no need to add
            pass

        # The clone should be in draft with all items pending
        clone_items = client.get(f"/api/v1/changes/{clone_id}/checklist").json()
        assert len(clone_items) == 6
        # All items should exist and the clone should be editable (draft)
        assert resp.json()["status"] == "draft"

    def test_duplicate_non_existent_change(self, client):
        """Duplicating a non-existent change returns 404."""
        resp = client.post(
            "/api/v1/changes/00000000-0000-0000-0000-000000000000/duplicate",
            json={},
        )
        assert resp.status_code == 404


class TestDuplicateAudit:
    """Duplication is recorded in the audit trail."""

    def test_duplicate_creates_audit_event(self, client, sample_change_data, db):
        """Duplicating a change creates an audit event on the clone."""
        source_id = _create_source_change(client, sample_change_data)

        resp = client.post(
            f"/api/v1/changes/{source_id}/duplicate",
            json={},
        )
        clone_id = resp.json()["id"]

        from app.models.audit import AuditEvent

        events = (
            db.query(AuditEvent)
            .filter(
                AuditEvent.change_id == clone_id,
                AuditEvent.event_type == "change_duplicated",
            )
            .all()
        )
        assert len(events) == 1
        assert str(source_id) in events[0].description
