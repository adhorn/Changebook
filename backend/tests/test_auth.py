"""Tests for Issue #1: Mock auth — identity from headers, not manual input.

The mock auth system:
- Reads identity from X-User-Email and X-User-Name headers
- Provides a GET /api/v1/me endpoint returning the current user
- Injects identity into operations (transitions, reviews, completions)
- Enforces: author cannot approve their own change
"""


def _complete_preflight(client):
    """Build a complete set of pre-flight answers from the API."""
    resp = client.get("/api/v1/preflight-questions")
    keys = []
    for section in resp.json()["sections"]:
        for q in section["questions"]:
            if q["required"]:
                keys.append(q["key"])
    return {key: f"Answer for {key}" for key in keys}


def _create_change(client, sample_change_data, author_headers):
    """Create a change with auth headers."""
    resp = client.post(
        "/api/v1/changes",
        json={
            "title": "Test change",
            **sample_change_data,
            "preflight_answers": _complete_preflight(client),
        },
        headers=author_headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _add_items_to_all_phases(client, change_id, headers):
    """Add at least one checklist item to each phase."""
    for phase in ["pre_flight", "execution", "verification"]:
        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": phase, "description": f"{phase} step"},
            headers=headers,
        )


# --- Mock users ---

ALICE = {"X-User-Email": "alice@changebook.dev", "X-User-Name": "Alice Engineer"}
BOB = {"X-User-Email": "bob@changebook.dev", "X-User-Name": "Bob Reviewer"}


class TestMeEndpoint:
    """GET /api/v1/me returns the current user from headers."""

    def test_me_returns_user_identity(self, client):
        resp = client.get("/api/v1/me", headers=ALICE)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "alice@changebook.dev"
        assert data["name"] == "Alice Engineer"

    def test_me_without_headers_returns_401(self, unauthenticated_client):
        resp = unauthenticated_client.get("/api/v1/me")
        assert resp.status_code == 401


class TestAuthOnCreateChange:
    """Change creation uses identity from auth headers, not request body."""

    def test_author_comes_from_headers(self, client, sample_change_data):
        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Auth test change",
                **sample_change_data,
                "preflight_answers": _complete_preflight(client),
            },
            headers=ALICE,
        )
        assert resp.status_code == 201
        assert resp.json()["author_name"] == "Alice Engineer"

    def test_create_without_auth_returns_401(self, unauthenticated_client, sample_change_data):
        resp = unauthenticated_client.post(
            "/api/v1/changes",
            json={
                "title": "No auth change",
                **sample_change_data,
            },
        )
        assert resp.status_code == 401


class TestAuthOnTransition:
    """Transitions use identity from auth, not query params."""

    def test_transition_uses_auth_identity(self, client, sample_change_data):
        change_id = _create_change(client, sample_change_data, ALICE)
        _add_items_to_all_phases(client, change_id, ALICE)

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review"},
            headers=ALICE,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_review"


class TestAuthorCannotApprove:
    """The change author cannot approve their own change."""

    def test_author_cannot_review_own_change(self, client, sample_change_data):
        """Alice creates a change, Alice cannot be assigned as reviewer."""
        change_id = _create_change(client, sample_change_data, ALICE)
        _add_items_to_all_phases(client, change_id, ALICE)

        # Submit for review
        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review"},
            headers=ALICE,
        )

        # Alice tries to assign herself as reviewer — should fail
        resp = client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={},
            headers=ALICE,
        )
        assert resp.status_code == 422
        assert "own change" in resp.json()["detail"].lower()

    def test_different_user_can_review(self, client, sample_change_data):
        """Alice creates, Bob reviews — this should work."""
        change_id = _create_change(client, sample_change_data, ALICE)
        _add_items_to_all_phases(client, change_id, ALICE)

        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review"},
            headers=ALICE,
        )

        # Bob assigns himself as reviewer — should work
        resp = client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={},
            headers=BOB,
        )
        assert resp.status_code == 201
        assert resp.json()["reviewer_name"] == "Bob Reviewer"

    def test_reviewer_can_approve(self, client, sample_change_data):
        """Bob reviews and approves Alice's change."""
        change_id = _create_change(client, sample_change_data, ALICE)
        _add_items_to_all_phases(client, change_id, ALICE)

        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review"},
            headers=ALICE,
        )

        # Bob assigns himself and approves
        review = client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={},
            headers=BOB,
        )
        resp = client.post(
            f"/api/v1/changes/{change_id}/reviewers/{review.json()['id']}/decision",
            json={"decision": "approved"},
            headers=BOB,
        )
        assert resp.status_code == 200
        assert resp.json()["decision"] == "approved"


class TestAuthOnExecution:
    """Checklist completion records who completed it from auth."""

    def test_completion_records_auth_identity(self, client, sample_change_data, db):
        change_id = _create_change(client, sample_change_data, ALICE)
        _add_items_to_all_phases(client, change_id, ALICE)

        # Move to executing
        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review"},
            headers=ALICE,
        )
        review = client.post(
            f"/api/v1/changes/{change_id}/reviewers",
            json={},
            headers=BOB,
        )
        client.post(
            f"/api/v1/changes/{change_id}/reviewers/{review.json()['id']}/decision",
            json={"decision": "approved"},
            headers=BOB,
        )
        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "approved"},
            headers=ALICE,
        )
        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "executing"},
            headers=ALICE,
        )

        # Get first checklist item
        items = client.get(f"/api/v1/changes/{change_id}/checklist").json()
        item_id = items[0]["id"]

        # Complete it — completed_by should come from auth headers
        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist/{item_id}/complete",
            json={
                "observed_result": "Looks good",
                "status": "completed",
            },
            headers=ALICE,
        )
        assert resp.status_code == 200
        assert resp.json()["completed_by"] == "Alice Engineer"
