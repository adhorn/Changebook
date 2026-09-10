"""Permission matrix tests — table-driven authorization checks.

Walks the matrix declared in `docs/permissions.md`. For each mutating
endpoint, asserts:

- The allowed role can call it (no 403 — the response might be 200/201
  or, for state-machine reasons, 422; either way not 403).
- Other roles cannot (HTTP 403).

This is intentionally scoped to the AUTH boundary. State-machine rules
(which transitions are valid when) are covered elsewhere — here we only
care that a wrong-user request is rejected with 403 before reaching the
business logic.

The default test client is authenticated as "Test User" (set in
conftest.py). Bob is a non-author identity from conftest.JANE/BOB.

When a new mutating endpoint is added: add a row both here and in
docs/permissions.md.
"""

import pytest

from tests.conftest import BOB
from tests.test_execution import _create_executing_change

# --- Fixtures: pre-built changes owned by the default test user ---


@pytest.fixture
def draft_change(client, sample_change_data):
    """A draft change owned by the default test user, with a checklist
    item present so item-scoped endpoints have something to target."""
    r = client.post(
        "/api/v1/changes",
        json={
            "title": "Permission matrix draft",
            "author_name": "Adrian Hornsby",
            **sample_change_data,
        },
    )
    change_id = r.json()["id"]
    item = client.post(
        f"/api/v1/changes/{change_id}/checklist",
        json={"phase": "pre_flight", "description": "Existing item"},
    ).json()
    return {"change_id": change_id, "item_id": item["id"]}


@pytest.fixture
def executing_change(client, sample_change_data):
    """A change driven all the way to executing, owned by the default
    test user. Has one item per phase; the pre_flight item is the next
    one waiting for completion."""
    change_id, items = _create_executing_change(client, sample_change_data)
    return {
        "change_id": change_id,
        "preflight_item_id": items["pre_flight"][0]["id"],
        "execution_item_id": items["execution"][0]["id"],
    }


# --- Endpoint table ---
#
# Each row: (rule_id, method, path_builder, body_builder, allowed_role, fixture)
#
# allowed_role is one of: "author", "any_authenticated", "assigned_reviewer".
# fixture names which pre-built change to use (or None if endpoint creates one).

AUTHOR_ONLY_CHANGE_ENDPOINTS = [
    # (label, method, path-builder using fixture, body)
    (
        "PATCH /changes/{id}",
        "patch",
        lambda f: f"/api/v1/changes/{f['change_id']}",
        {"title": "renamed"},
    ),
    (
        "POST /changes/{id}/transition",
        "post",
        lambda f: f"/api/v1/changes/{f['change_id']}/transition?target_status=aborted&reason=test",
        None,
    ),
    (
        "POST /changes/{id}/checklist",
        "post",
        lambda f: f"/api/v1/changes/{f['change_id']}/checklist",
        {"phase": "pre_flight", "description": "another"},
    ),
    (
        "PUT /changes/{id}/checklist/reorder",
        "put",
        lambda f: f"/api/v1/changes/{f['change_id']}/checklist/reorder",
        {"phase": "pre_flight", "item_ids": []},
    ),
    (
        "PATCH /changes/{id}/checklist/{item_id}",
        "patch",
        lambda f: f"/api/v1/changes/{f['change_id']}/checklist/{f['item_id']}",
        {"description": "edited"},
    ),
    (
        "DELETE /changes/{id}/checklist/{item_id}",
        "delete",
        lambda f: f"/api/v1/changes/{f['change_id']}/checklist/{f['item_id']}",
        None,
    ),
    (
        "POST /changes/{id}/reviewers",
        "post",
        lambda f: f"/api/v1/changes/{f['change_id']}/reviewers",
        {"reviewer_name": "Some Reviewer"},
    ),
]

AUTHOR_ONLY_EXECUTION_ENDPOINTS = [
    (
        "POST /changes/{id}/checklist/{item_id}/complete",
        "post",
        lambda f: f"/api/v1/changes/{f['change_id']}/checklist/{f['preflight_item_id']}/complete",
        {"observed_result": "ok", "status": "completed"},
    ),
    (
        "POST /changes/{id}/checklist/execution-step",
        "post",
        lambda f: f"/api/v1/changes/{f['change_id']}/checklist/execution-step",
        {"insert_after_item_id": "00000000-0000-0000-0000-000000000000", "description": "new step"},
    ),
    (
        "POST /changes/{id}/checklist/{item_id}/hold-point-verify",
        "post",
        # The item may or may not actually be a hold point — we only care
        # about the AUTH boundary here. If the item isn't a hold point we
        # get 422 (not 403), which still demonstrates the auth check did
        # not reject the call.
        lambda f: (
            f"/api/v1/changes/{f['change_id']}/checklist/{f['execution_item_id']}/hold-point-verify"
        ),
        {"verified_by": "Some Verifier"},
    ),
]

ANY_AUTHENTICATED_CHANGE_ENDPOINTS = [
    (
        "POST /changes/{id}/duplicate",
        "post",
        lambda f: f"/api/v1/changes/{f['change_id']}/duplicate",
        {},
    ),
    (
        "POST /changes/{id}/save-as-template",
        "post",
        lambda f: f"/api/v1/changes/{f['change_id']}/save-as-template",
        {"title": "Saved as template by Bob"},
    ),
]

# No "any authenticated" execution-time endpoints today — all execution
# actions are author-only, including hold-point verification (the operator
# at the keyboard types the verifier's name). Kept as a named slot so it's
# clear where a future endpoint of that kind would be registered.
ANY_AUTHENTICATED_EXECUTION_ENDPOINTS: list = []


def _do_request(client, method, url, body, headers=None):
    if method == "get":
        return client.get(url, headers=headers or {})
    if method == "post":
        return client.post(url, json=body, headers=headers or {})
    if method == "put":
        return client.put(url, json=body, headers=headers or {})
    if method == "patch":
        return client.patch(url, json=body, headers=headers or {})
    if method == "delete":
        return client.delete(url, headers=headers or {})
    raise ValueError(f"Unknown method: {method}")


# --- Tests on a DRAFT change ---


@pytest.mark.parametrize(
    "label,method,path_fn,body",
    AUTHOR_ONLY_CHANGE_ENDPOINTS,
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_author_only_endpoint_rejects_non_author(
    label, method, path_fn, body, client, draft_change
):
    url = path_fn(draft_change)
    resp = _do_request(client, method, url, body, headers=BOB)
    assert resp.status_code == 403, (
        f"{label}: expected 403 when called by non-author, got {resp.status_code}: {resp.text}"
    )


@pytest.mark.parametrize(
    "label,method,path_fn,body",
    AUTHOR_ONLY_CHANGE_ENDPOINTS,
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_author_only_endpoint_allows_author(label, method, path_fn, body, client, draft_change):
    url = path_fn(draft_change)
    resp = _do_request(client, method, url, body)
    # Author may hit 422 if the state machine rejects (e.g. transition to
    # invalid state), but it must NOT be 403.
    assert resp.status_code != 403, (
        f"{label}: author was unexpectedly rejected with 403: {resp.text}"
    )


@pytest.mark.parametrize(
    "label,method,path_fn,body",
    ANY_AUTHENTICATED_CHANGE_ENDPOINTS,
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_any_authenticated_endpoint_allows_non_author(
    label, method, path_fn, body, client, draft_change
):
    url = path_fn(draft_change)
    resp = _do_request(client, method, url, body, headers=BOB)
    assert resp.status_code != 403, (
        f"{label}: non-author was unexpectedly rejected with 403: {resp.text}"
    )


# --- Tests on an EXECUTING change ---


@pytest.mark.parametrize(
    "label,method,path_fn,body",
    AUTHOR_ONLY_EXECUTION_ENDPOINTS,
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_author_only_execution_endpoint_rejects_non_author(
    label, method, path_fn, body, client, executing_change
):
    url = path_fn(executing_change)
    resp = _do_request(client, method, url, body, headers=BOB)
    assert resp.status_code == 403, (
        f"{label}: expected 403 when called by non-author, got {resp.status_code}: {resp.text}"
    )


# If ANY_AUTHENTICATED_EXECUTION_ENDPOINTS ever has rows, restore the
# parametrized test "test_any_authenticated_execution_endpoint_allows_non_author"
# from git history. Today the bucket is empty by design.
