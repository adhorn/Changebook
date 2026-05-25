"""Tests for review indicator on change list.

The change list response includes pending_reviewers for each change,
so the frontend can show "needs your review" indicators.
"""

from tests.conftest import JANE


def _complete_preflight(client):
    resp = client.get("/api/v1/preflight-questions")
    keys = []
    for section in resp.json()["sections"]:
        for q in section["questions"]:
            if q["required"]:
                keys.append(q["key"])
    return {key: f"Answer for {key}" for key in keys}


def _create_review_ready_change(client, sample_change_data, title="Test change"):
    """Create a change that's ready for review (preflight + all phases)."""
    resp = client.post(
        "/api/v1/changes",
        json={
            "title": title,
            **sample_change_data,
            "preflight_answers": _complete_preflight(client),
        },
    )
    change_id = resp.json()["id"]
    for phase in ["pre_flight", "execution", "verification"]:
        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": phase, "description": f"{phase} step"},
        )
    return change_id


class TestPendingReviewersInList:
    """The change list response includes pending_reviewers for each change."""

    def test_no_reviewers_returns_empty_list(self, client, sample_change_data):
        """A change with no reviewers has an empty pending_reviewers list."""
        _create_review_ready_change(client, sample_change_data)

        resp = client.get("/api/v1/changes")
        assert resp.status_code == 200
        change = resp.json()["data"][0]
        assert change["pending_reviewers"] == []

    def test_pending_reviewer_appears_in_list(self, client, sample_change_data):
        """A reviewer with pending decision shows up in pending_reviewers."""
        change_id = _create_review_ready_change(client, sample_change_data)

        # Assign a reviewer
        client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "Jane Smith"},
        )

        resp = client.get("/api/v1/changes")
        change = resp.json()["data"][0]
        assert change["pending_reviewers"] == ["Jane Smith"]

    def test_approved_reviewer_not_in_pending(self, client, sample_change_data):
        """A reviewer who has approved is not in pending_reviewers."""
        change_id = _create_review_ready_change(client, sample_change_data)

        # Submit for review first so reviewer can decide
        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review"},
        )

        review = client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "Jane Smith"},
        )
        review_id = review.json()["id"]

        # Jane approves
        client.post(
            f"/api/v1/changes/{change_id}/reviewers/{review_id}/decision",
            json={"decision": "approved"},
            headers=JANE,
        )

        resp = client.get("/api/v1/changes")
        change = resp.json()["data"][0]
        assert change["pending_reviewers"] == []

    def test_multiple_reviewers_mixed_status(self, client, sample_change_data):
        """Only pending reviewers appear — approved ones are filtered out."""
        change_id = _create_review_ready_change(client, sample_change_data)

        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review"},
        )

        r1 = client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "Jane Smith"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "Bob Johnson"},
        )

        # Jane approves, Bob is still pending
        client.post(
            f"/api/v1/changes/{change_id}/reviewers/{r1.json()['id']}/decision",
            json={"decision": "approved"},
            headers=JANE,
        )

        resp = client.get("/api/v1/changes")
        change = resp.json()["data"][0]
        assert change["pending_reviewers"] == ["Bob Johnson"]

    def test_pending_reviewers_on_detail_endpoint(self, client, sample_change_data):
        """The detail endpoint also includes pending_reviewers."""
        change_id = _create_review_ready_change(client, sample_change_data)

        client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={"reviewer_name": "Jane Smith"},
        )

        resp = client.get(f"/api/v1/changes/{change_id}")
        assert resp.status_code == 200
        assert resp.json()["pending_reviewers"] == ["Jane Smith"]

    def test_needs_review_by_filter(self, client, sample_change_data):
        """Can filter the list to changes where a specific user has a pending review."""
        c1 = _create_review_ready_change(client, sample_change_data, title="Change for Jane")
        c2 = _create_review_ready_change(client, sample_change_data, title="Change for Bob")
        _create_review_ready_change(client, sample_change_data, title="No reviewers")

        # Assign Jane to c1, Bob to c2
        client.post(
            f"/api/v1/changes/{c1}/reviewers",
            json={"reviewer_name": "Jane Smith"},
        )
        client.post(
            f"/api/v1/changes/{c2}/reviewers",
            json={"reviewer_name": "Bob Johnson"},
        )

        # Filter for Jane's pending reviews
        resp = client.get("/api/v1/changes", params={"needs_review_by": "Jane Smith"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["title"] == "Change for Jane"

        # Filter for Bob's pending reviews
        resp = client.get("/api/v1/changes", params={"needs_review_by": "Bob Johnson"})
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["title"] == "Change for Bob"
