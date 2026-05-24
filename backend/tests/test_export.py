"""Tests for Feature 8: Markdown export.

Renders a complete change record as structured markdown — the full
human-readable output including metadata, pre-flight answers, checklist
with completion records, review decisions, and audit trail.
"""


def _complete_preflight(client):
    resp = client.get("/api/v1/preflight-questions")
    keys = []
    for section in resp.json()["sections"]:
        for q in section["questions"]:
            if q["required"]:
                keys.append(q["key"])
    return {key: f"Answer for {key}" for key in keys}


def _create_full_change(client, sample_change_data):
    """Create a change with everything filled in — ready for export."""
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

    # Add checklist items
    items = {}
    for phase, descs in [
        ("pre_flight", ["Verify current pool size is 100"]),
        ("execution", ["Run ALTER SYSTEM SET max_connections = 150"]),
        ("verification", ["Check pg_settings shows 150"]),
    ]:
        items[phase] = []
        for desc in descs:
            r = client.post(
                f"/api/v1/changes/{change_id}/checklist",
                json={"phase": phase, "description": desc},
            )
            items[phase].append(r.json())

    return change_id, items


def _move_to_executing(client, change_id):
    """Move a change through review to executing."""
    client.post(
        f"/api/v1/changes/{change_id}/transition",
        params={"target_status": "in_review", "actor_name": "Adrian Hornsby"},
    )
    review = client.post(
        f"/api/v1/changes/{change_id}/reviewers",
        json={"reviewer_name": "Jane Smith"},
    )
    client.post(
        f"/api/v1/changes/{change_id}/reviewers/{review.json()['id']}/decision",
        json={"decision": "approved", "comment": "Looks good."},
    )
    client.post(
        f"/api/v1/changes/{change_id}/transition",
        params={"target_status": "approved", "actor_name": "Adrian Hornsby"},
    )
    client.post(
        f"/api/v1/changes/{change_id}/transition",
        params={"target_status": "executing", "actor_name": "Adrian Hornsby"},
    )


class TestMarkdownExport:
    """GET /api/v1/changes/{change_id}/export/markdown"""

    def test_export_returns_markdown(self, client, sample_change_data):
        """The export endpoint returns a markdown string."""
        change_id, _ = _create_full_change(client, sample_change_data)

        resp = client.get(f"/api/v1/changes/{change_id}/export/markdown")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/markdown; charset=utf-8"
        assert len(resp.text) > 0

    def test_export_contains_title(self, client, sample_change_data):
        """The export contains the change title as an H1."""
        change_id, _ = _create_full_change(client, sample_change_data)

        md = client.get(f"/api/v1/changes/{change_id}/export/markdown").text
        assert "# Connection pool resize on PROD-EU" in md

    def test_export_contains_metadata(self, client, sample_change_data):
        """The export contains status, author, and description."""
        change_id, _ = _create_full_change(client, sample_change_data)

        md = client.get(f"/api/v1/changes/{change_id}/export/markdown").text
        assert "Test User" in md  # From auth headers
        assert "draft" in md.lower()
        assert "Increase max connections" in md

    def test_export_contains_defence_tags(self, client, sample_change_data):
        """Defence tags appear in the export."""
        change_id, _ = _create_full_change(client, sample_change_data)

        md = client.get(f"/api/v1/changes/{change_id}/export/markdown").text
        assert "database" in md
        assert "monitoring" in md

    def test_export_contains_change_profile(self, client, sample_change_data):
        """Change profile (formerly pre-flight answers) appears in the export."""
        change_id, _ = _create_full_change(client, sample_change_data)

        md = client.get(f"/api/v1/changes/{change_id}/export/markdown").text
        assert "## Change Profile" in md
        assert "Pre-flight Answers" not in md
        # Should contain at least one answer
        assert "Answer for" in md

    def test_export_contains_checklist(self, client, sample_change_data):
        """Checklist items appear grouped by phase."""
        change_id, _ = _create_full_change(client, sample_change_data)

        md = client.get(f"/api/v1/changes/{change_id}/export/markdown").text
        assert "Verify current pool size" in md
        assert "ALTER SYSTEM" in md
        assert "pg_settings" in md

    def test_export_not_found(self, client):
        """Exporting a non-existent change returns 404."""
        resp = client.get("/api/v1/changes/00000000-0000-0000-0000-000000000000/export/markdown")
        assert resp.status_code == 404


class TestExportWithExecution:
    """Export includes completion records when items have been executed."""

    def test_export_shows_completion_status(self, client, sample_change_data):
        """Completed items show their observed result in the export."""
        change_id, items = _create_full_change(client, sample_change_data)
        _move_to_executing(client, change_id)

        # Complete first item
        client.post(
            f"/api/v1/changes/{change_id}/checklist/{items['pre_flight'][0]['id']}/complete",
            json={
                "observed_result": "Pool size confirmed at 100",
                "status": "completed",
                "completed_by": "Adrian Hornsby",
            },
        )

        md = client.get(f"/api/v1/changes/{change_id}/export/markdown").text
        assert "Pool size confirmed at 100" in md
        assert "completed" in md.lower()


class TestExportWithReviews:
    """Export includes review decisions."""

    def test_export_shows_reviews(self, client, sample_change_data):
        """Review decisions appear in the export."""
        change_id, _ = _create_full_change(client, sample_change_data)

        # Move to in_review and get a review
        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review", "actor_name": "Adrian Hornsby"},
        )
        review = client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "Jane Smith"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/reviewers/{review.json()['id']}/decision",
            json={"decision": "approved", "comment": "Well planned, LGTM."},
        )

        md = client.get(f"/api/v1/changes/{change_id}/export/markdown").text
        assert "Jane Smith" in md
        assert "approved" in md.lower()


class TestExportWithAudit:
    """Export includes the audit trail."""

    def test_export_contains_audit_trail(self, client, sample_change_data):
        """The audit trail section appears with at least the creation event."""
        change_id, _ = _create_full_change(client, sample_change_data)

        md = client.get(f"/api/v1/changes/{change_id}/export/markdown").text
        assert "Audit" in md
        assert "change_created" in md or "created" in md.lower()
