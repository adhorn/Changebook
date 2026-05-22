"""Tests for Feature 9: Change history and filtering.

Adds to the existing list endpoint:
- Title search (case-insensitive substring match)
- Date range filtering (created_after, created_before)
- Sort options (newest, oldest, recently_updated)
- Audit event count in list responses
"""

def _create_changes(client, sample_change_data, titles):
    """Create multiple changes with given titles."""
    ids = []
    for title in titles:
        resp = client.post(
            "/api/v1/changes",
            json={
                "title": title,
                "author_name": "Adrian Hornsby",
                **sample_change_data,
            },
        )
        ids.append(resp.json()["id"])
    return ids


class TestTitleSearch:
    """Filter changes by title substring."""

    def test_search_by_title(self, client, sample_change_data):
        """Title search finds matching changes."""
        _create_changes(
            client,
            sample_change_data,
            ["Firewall rule update", "Connection pool resize", "Firewall migration"],
        )

        resp = client.get("/api/v1/changes", params={"title_search": "Firewall"})
        assert resp.status_code == 200
        assert resp.json()["meta"]["total"] == 2

    def test_search_is_case_insensitive(self, client, sample_change_data):
        """Title search is case-insensitive."""
        _create_changes(
            client,
            sample_change_data,
            ["Firewall Rule Update", "firewall migration"],
        )

        resp = client.get("/api/v1/changes", params={"title_search": "firewall"})
        assert resp.json()["meta"]["total"] == 2

    def test_search_no_results(self, client, sample_change_data):
        """Title search with no matches returns empty list."""
        _create_changes(client, sample_change_data, ["Firewall update"])

        resp = client.get("/api/v1/changes", params={"title_search": "kubernetes"})
        assert resp.json()["meta"]["total"] == 0
        assert resp.json()["data"] == []

    def test_search_combined_with_status(self, client, sample_change_data):
        """Title search can be combined with other filters."""
        _create_changes(
            client,
            sample_change_data,
            ["Firewall rule update", "Firewall migration"],
        )

        # Both are in draft, so filtering by draft + firewall should return both
        resp = client.get(
            "/api/v1/changes",
            params={"title_search": "Firewall", "status": "draft"},
        )
        assert resp.json()["meta"]["total"] == 2


class TestDateRangeFiltering:
    """Filter changes by creation date range."""

    def test_created_after(self, client, sample_change_data, db):
        """Filter changes created after a given date."""
        from datetime import UTC, datetime, timedelta

        from app.models.change import Change

        ids = _create_changes(client, sample_change_data, ["Old change", "New change"])

        # Backdate the first change
        change = db.query(Change).filter(Change.id == ids[0]).first()
        change.created_at = datetime.now(UTC) - timedelta(days=30)
        db.commit()

        # Filter for recent changes only
        cutoff = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        resp = client.get("/api/v1/changes", params={"created_after": cutoff})
        assert resp.json()["meta"]["total"] == 1
        assert resp.json()["data"][0]["title"] == "New change"

    def test_created_before(self, client, sample_change_data, db):
        """Filter changes created before a given date."""
        from datetime import UTC, datetime, timedelta

        from app.models.change import Change

        ids = _create_changes(client, sample_change_data, ["Old change", "New change"])

        # Backdate the first change
        change = db.query(Change).filter(Change.id == ids[0]).first()
        change.created_at = datetime.now(UTC) - timedelta(days=30)
        db.commit()

        cutoff = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        resp = client.get("/api/v1/changes", params={"created_before": cutoff})
        assert resp.json()["meta"]["total"] == 1
        assert resp.json()["data"][0]["title"] == "Old change"

    def test_date_range(self, client, sample_change_data, db):
        """Filter changes within a date range."""
        from datetime import UTC, datetime, timedelta

        from app.models.change import Change

        ids = _create_changes(
            client,
            sample_change_data,
            ["Very old", "Middle", "Recent"],
        )

        # Backdate
        changes = db.query(Change).filter(Change.id.in_(ids)).all()
        id_to_change = {str(c.id): c for c in changes}
        id_to_change[ids[0]].created_at = datetime.now(UTC) - timedelta(days=60)
        id_to_change[ids[1]].created_at = datetime.now(UTC) - timedelta(days=10)
        db.commit()

        after = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        before = (datetime.now(UTC) - timedelta(days=1)).isoformat()

        resp = client.get(
            "/api/v1/changes",
            params={"created_after": after, "created_before": before},
        )
        assert resp.json()["meta"]["total"] == 1
        assert resp.json()["data"][0]["title"] == "Middle"


class TestSorting:
    """Sort changes by different criteria."""

    def test_sort_newest_first(self, client, sample_change_data):
        """Default sort is newest first."""
        _create_changes(client, sample_change_data, ["First", "Second", "Third"])

        resp = client.get("/api/v1/changes", params={"sort": "newest"})
        titles = [c["title"] for c in resp.json()["data"]]
        assert titles == ["Third", "Second", "First"]

    def test_sort_oldest_first(self, client, sample_change_data):
        """Sort by oldest first."""
        _create_changes(client, sample_change_data, ["First", "Second", "Third"])

        resp = client.get("/api/v1/changes", params={"sort": "oldest"})
        titles = [c["title"] for c in resp.json()["data"]]
        assert titles == ["First", "Second", "Third"]

    def test_sort_recently_updated(self, client, sample_change_data):
        """Sort by most recently updated."""
        ids = _create_changes(
            client, sample_change_data, ["Alpha", "Beta", "Gamma"]
        )

        # Update Alpha so it becomes the most recently updated
        client.patch(
            f"/api/v1/changes/{ids[0]}",
            json={"title": "Alpha (updated)"},
        )

        resp = client.get("/api/v1/changes", params={"sort": "recently_updated"})
        titles = [c["title"] for c in resp.json()["data"]]
        # Alpha was updated last, so it should be first
        assert titles[0] == "Alpha (updated)"

    def test_default_sort_is_newest(self, client, sample_change_data):
        """Without sort param, default is newest first."""
        _create_changes(client, sample_change_data, ["First", "Second"])

        resp = client.get("/api/v1/changes")
        titles = [c["title"] for c in resp.json()["data"]]
        assert titles == ["Second", "First"]


class TestAuditEventCount:
    """List responses include audit event count per change."""

    def test_new_change_has_one_audit_event(self, client, sample_change_data):
        """A freshly created change has 1 audit event (creation)."""
        _create_changes(client, sample_change_data, ["Test"])

        resp = client.get("/api/v1/changes")
        assert resp.json()["data"][0]["audit_event_count"] == 1

    def test_transitioned_change_has_more_events(self, client, sample_change_data):
        """A change that's been transitioned has more audit events."""
        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Audit test",
                "author_name": "Adrian Hornsby",
                **sample_change_data,
            },
        )
        change_id = resp.json()["id"]

        # Abort it (generates a status_changed event)
        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "aborted", "actor_name": "Adrian Hornsby"},
        )

        resp = client.get("/api/v1/changes")
        change_data = next(
            c for c in resp.json()["data"] if c["id"] == change_id
        )
        assert change_data["audit_event_count"] >= 2
