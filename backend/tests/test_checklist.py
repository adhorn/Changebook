"""Tests for Feature 3: Checklist CRUD.

Full CRUD for checklist items across all three phases (pre_flight, execution,
verification). Items can only be modified when the change is in draft status.
Items are auto-ordered within their phase. Deleting re-compacts the order.
"""


class TestCreateChecklistItem:
    """POST /api/v1/changes/{id}/checklist"""

    def test_add_execution_item(self, client, sample_change_data):
        """An execution checklist item can be added with all fields."""
        change = client.post(
            "/api/v1/changes",
            json={"title": "Test", "author_name": "Adrian Hornsby", **sample_change_data},
        )
        change_id = change.json()["id"]

        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={
                "phase": "execution",
                "description": "Increase max_connections to 150",
                "command": "ALTER SYSTEM SET max_connections = 150;",
                "expected_outcome": "Parameter set, pending restart",
                "rollback_action": "ALTER SYSTEM SET max_connections = 100;",
                "is_hold_point": False,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["phase"] == "execution"
        assert data["description"] == "Increase max_connections to 150"
        assert data["command"] == "ALTER SYSTEM SET max_connections = 150;"
        assert data["expected_outcome"] == "Parameter set, pending restart"
        assert data["rollback_action"] == "ALTER SYSTEM SET max_connections = 100;"
        assert data["is_hold_point"] is False
        assert data["order"] == 1

    def test_add_verification_item_with_hold_point(self, client, sample_change_data):
        """A verification item can be a hold point for independent verification."""
        change = client.post(
            "/api/v1/changes",
            json={"title": "Test", "author_name": "Adrian Hornsby", **sample_change_data},
        )
        change_id = change.json()["id"]

        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={
                "phase": "verification",
                "description": "Confirm customer can connect",
                "is_hold_point": True,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["is_hold_point"] is True

    def test_add_item_minimal_fields(self, client, sample_change_data):
        """Only phase and description are required."""
        change = client.post(
            "/api/v1/changes",
            json={"title": "Test", "author_name": "Adrian Hornsby", **sample_change_data},
        )
        change_id = change.json()["id"]

        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={
                "phase": "pre_flight",
                "description": "Verify current connection count",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["command"] is None
        assert data["expected_outcome"] is None
        assert data["rollback_action"] is None

    def test_auto_ordering_within_phase(self, client, sample_change_data):
        """Items are auto-numbered sequentially within their phase."""
        change = client.post(
            "/api/v1/changes",
            json={"title": "Test", "author_name": "Adrian Hornsby", **sample_change_data},
        )
        change_id = change.json()["id"]

        for i in range(3):
            resp = client.post(
                f"/api/v1/changes/{change_id}/checklist",
                json={"phase": "execution", "description": f"Step {i + 1}"},
            )
            assert resp.json()["order"] == i + 1

    def test_ordering_independent_per_phase(self, client, sample_change_data):
        """Each phase has its own ordering starting at 1."""
        change = client.post(
            "/api/v1/changes",
            json={"title": "Test", "author_name": "Adrian Hornsby", **sample_change_data},
        )
        change_id = change.json()["id"]

        r1 = client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "execution", "description": "Exec step 1"},
        )
        r2 = client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "verification", "description": "Verify step 1"},
        )
        assert r1.json()["order"] == 1
        assert r2.json()["order"] == 1

    def test_cannot_add_to_non_draft_change(self, client, sample_change_data):
        """Checklist items can only be added to changes in draft status."""
        change = client.post(
            "/api/v1/changes",
            json={"title": "Test", "author_name": "Adrian Hornsby", **sample_change_data},
        )
        change_id = change.json()["id"]

        # Move to aborted (no preflight needed)
        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "aborted"},
        )

        resp = client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "execution", "description": "Too late"},
        )
        assert resp.status_code == 422

    def test_cannot_add_to_missing_change(self, client):
        """Adding to a non-existent change returns 404."""
        resp = client.post(
            "/api/v1/changes/00000000-0000-0000-0000-000000000000/checklist",
            json={"phase": "execution", "description": "Ghost"},
        )
        assert resp.status_code == 404


class TestListChecklistItems:
    """GET /api/v1/changes/{id}/checklist"""

    def test_list_all_items(self, client, sample_change_data):
        """All items across all phases are returned, ordered by phase then order."""
        change = client.post(
            "/api/v1/changes",
            json={"title": "Test", "author_name": "Adrian Hornsby", **sample_change_data},
        )
        change_id = change.json()["id"]

        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "verification", "description": "Check customer access"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "execution", "description": "Run migration"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "pre_flight", "description": "Confirm backup"},
        )

        resp = client.get(f"/api/v1/changes/{change_id}/checklist")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 3
        # Ordered: pre_flight, execution, verification
        assert items[0]["phase"] == "pre_flight"
        assert items[1]["phase"] == "execution"
        assert items[2]["phase"] == "verification"

    def test_filter_by_phase(self, client, sample_change_data):
        """Items can be filtered by phase."""
        change = client.post(
            "/api/v1/changes",
            json={"title": "Test", "author_name": "Adrian Hornsby", **sample_change_data},
        )
        change_id = change.json()["id"]

        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "execution", "description": "Step 1"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "execution", "description": "Step 2"},
        )
        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "verification", "description": "Check 1"},
        )

        resp = client.get(
            f"/api/v1/changes/{change_id}/checklist",
            params={"phase": "execution"},
        )
        assert len(resp.json()) == 2
        assert all(i["phase"] == "execution" for i in resp.json())

    def test_empty_checklist(self, client, sample_change_data):
        """A change with no checklist items returns an empty list."""
        change = client.post(
            "/api/v1/changes",
            json={"title": "Test", "author_name": "Adrian Hornsby", **sample_change_data},
        )
        change_id = change.json()["id"]

        resp = client.get(f"/api/v1/changes/{change_id}/checklist")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetChecklistItem:
    """GET /api/v1/changes/{change_id}/checklist/{item_id}"""

    def test_get_single_item(self, client, sample_change_data):
        """A single checklist item can be retrieved by ID."""
        change = client.post(
            "/api/v1/changes",
            json={"title": "Test", "author_name": "Adrian Hornsby", **sample_change_data},
        )
        change_id = change.json()["id"]

        create_resp = client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={
                "phase": "execution",
                "description": "Run the script",
                "command": "./deploy.sh",
            },
        )
        item_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/changes/{change_id}/checklist/{item_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == item_id
        assert resp.json()["description"] == "Run the script"

    def test_item_not_found(self, client, sample_change_data):
        """Requesting a non-existent item returns 404."""
        change = client.post(
            "/api/v1/changes",
            json={"title": "Test", "author_name": "Adrian Hornsby", **sample_change_data},
        )
        change_id = change.json()["id"]

        resp = client.get(
            f"/api/v1/changes/{change_id}/checklist/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404


class TestUpdateChecklistItem:
    """PATCH /api/v1/changes/{change_id}/checklist/{item_id}"""

    def test_update_description(self, client, sample_change_data):
        """An item's description can be updated."""
        change = client.post(
            "/api/v1/changes",
            json={"title": "Test", "author_name": "Adrian Hornsby", **sample_change_data},
        )
        change_id = change.json()["id"]

        item = client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "execution", "description": "Old description"},
        )
        item_id = item.json()["id"]

        resp = client.patch(
            f"/api/v1/changes/{change_id}/checklist/{item_id}",
            json={"description": "New description"},
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "New description"

    def test_update_command_and_expected_outcome(self, client, sample_change_data):
        """Command and expected outcome can be updated independently."""
        change = client.post(
            "/api/v1/changes",
            json={"title": "Test", "author_name": "Adrian Hornsby", **sample_change_data},
        )
        change_id = change.json()["id"]

        item = client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "execution", "description": "Deploy"},
        )
        item_id = item.json()["id"]

        resp = client.patch(
            f"/api/v1/changes/{change_id}/checklist/{item_id}",
            json={
                "command": "./deploy.sh --env prod",
                "expected_outcome": "Deployment successful, no errors in logs",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["command"] == "./deploy.sh --env prod"
        assert resp.json()["expected_outcome"] == "Deployment successful, no errors in logs"
        # Description unchanged
        assert resp.json()["description"] == "Deploy"

    def test_update_hold_point(self, client, sample_change_data):
        """An item can be toggled to a hold point."""
        change = client.post(
            "/api/v1/changes",
            json={"title": "Test", "author_name": "Adrian Hornsby", **sample_change_data},
        )
        change_id = change.json()["id"]

        item = client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "execution", "description": "Critical step"},
        )
        item_id = item.json()["id"]

        resp = client.patch(
            f"/api/v1/changes/{change_id}/checklist/{item_id}",
            json={"is_hold_point": True},
        )
        assert resp.status_code == 200
        assert resp.json()["is_hold_point"] is True

    def test_cannot_update_non_draft_change(self, client, sample_change_data):
        """Checklist items cannot be updated on non-draft changes."""
        change = client.post(
            "/api/v1/changes",
            json={"title": "Test", "author_name": "Adrian Hornsby", **sample_change_data},
        )
        change_id = change.json()["id"]

        item = client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "execution", "description": "Step"},
        )
        item_id = item.json()["id"]

        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "aborted"},
        )

        resp = client.patch(
            f"/api/v1/changes/{change_id}/checklist/{item_id}",
            json={"description": "Updated"},
        )
        assert resp.status_code == 422


class TestDeleteChecklistItem:
    """DELETE /api/v1/changes/{change_id}/checklist/{item_id}"""

    def test_delete_item(self, client, sample_change_data):
        """A checklist item can be deleted."""
        change = client.post(
            "/api/v1/changes",
            json={"title": "Test", "author_name": "Adrian Hornsby", **sample_change_data},
        )
        change_id = change.json()["id"]

        item = client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "execution", "description": "To be deleted"},
        )
        item_id = item.json()["id"]

        resp = client.delete(f"/api/v1/changes/{change_id}/checklist/{item_id}")
        assert resp.status_code == 204

        # Confirm it's gone
        get_resp = client.get(f"/api/v1/changes/{change_id}/checklist/{item_id}")
        assert get_resp.status_code == 404

    def test_delete_recompacts_order(self, client, sample_change_data):
        """Deleting an item re-numbers remaining items in that phase."""
        change = client.post(
            "/api/v1/changes",
            json={"title": "Test", "author_name": "Adrian Hornsby", **sample_change_data},
        )
        change_id = change.json()["id"]

        # Create 3 items
        ids = []
        for i in range(3):
            r = client.post(
                f"/api/v1/changes/{change_id}/checklist",
                json={"phase": "execution", "description": f"Step {i + 1}"},
            )
            ids.append(r.json()["id"])

        # Delete the middle one (order=2)
        client.delete(f"/api/v1/changes/{change_id}/checklist/{ids[1]}")

        # Remaining items should be re-numbered 1, 2
        items = client.get(
            f"/api/v1/changes/{change_id}/checklist",
            params={"phase": "execution"},
        ).json()
        assert len(items) == 2
        assert items[0]["order"] == 1
        assert items[0]["description"] == "Step 1"
        assert items[1]["order"] == 2
        assert items[1]["description"] == "Step 3"

    def test_cannot_delete_non_draft_change(self, client, sample_change_data):
        """Checklist items cannot be deleted from non-draft changes."""
        change = client.post(
            "/api/v1/changes",
            json={"title": "Test", "author_name": "Adrian Hornsby", **sample_change_data},
        )
        change_id = change.json()["id"]

        item = client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "execution", "description": "Step"},
        )
        item_id = item.json()["id"]

        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "aborted"},
        )

        resp = client.delete(f"/api/v1/changes/{change_id}/checklist/{item_id}")
        assert resp.status_code == 422

    def test_delete_nonexistent_item(self, client, sample_change_data):
        """Deleting a non-existent item returns 404."""
        change = client.post(
            "/api/v1/changes",
            json={"title": "Test", "author_name": "Adrian Hornsby", **sample_change_data},
        )
        change_id = change.json()["id"]

        resp = client.delete(
            f"/api/v1/changes/{change_id}/checklist/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404


class TestReorderChecklistItems:
    """PUT /api/v1/changes/{change_id}/checklist/reorder"""

    def test_reorder_items(self, client, sample_change_data):
        """Items within a phase can be reordered by passing an ordered list of IDs."""
        change = client.post(
            "/api/v1/changes",
            json={"title": "Test", "author_name": "Adrian Hornsby", **sample_change_data},
        )
        change_id = change.json()["id"]

        ids = []
        for i in range(3):
            r = client.post(
                f"/api/v1/changes/{change_id}/checklist",
                json={"phase": "execution", "description": f"Step {i + 1}"},
            )
            ids.append(r.json()["id"])

        # Reverse the order
        resp = client.put(
            f"/api/v1/changes/{change_id}/checklist/reorder",
            json={"phase": "execution", "item_ids": list(reversed(ids))},
        )
        assert resp.status_code == 200

        items = client.get(
            f"/api/v1/changes/{change_id}/checklist",
            params={"phase": "execution"},
        ).json()
        assert items[0]["description"] == "Step 3"
        assert items[0]["order"] == 1
        assert items[1]["description"] == "Step 2"
        assert items[1]["order"] == 2
        assert items[2]["description"] == "Step 1"
        assert items[2]["order"] == 3

    def test_reorder_must_include_all_items(self, client, sample_change_data):
        """Reorder must include all items for that phase — no partial reorder."""
        change = client.post(
            "/api/v1/changes",
            json={"title": "Test", "author_name": "Adrian Hornsby", **sample_change_data},
        )
        change_id = change.json()["id"]

        ids = []
        for i in range(3):
            r = client.post(
                f"/api/v1/changes/{change_id}/checklist",
                json={"phase": "execution", "description": f"Step {i + 1}"},
            )
            ids.append(r.json()["id"])

        # Only send 2 of 3
        resp = client.put(
            f"/api/v1/changes/{change_id}/checklist/reorder",
            json={"phase": "execution", "item_ids": ids[:2]},
        )
        assert resp.status_code == 422

    def test_cannot_reorder_non_draft(self, client, sample_change_data):
        """Cannot reorder items on a non-draft change."""
        change = client.post(
            "/api/v1/changes",
            json={"title": "Test", "author_name": "Adrian Hornsby", **sample_change_data},
        )
        change_id = change.json()["id"]

        client.post(
            f"/api/v1/changes/{change_id}/checklist",
            json={"phase": "execution", "description": "Step 1"},
        )

        client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "aborted"},
        )

        resp = client.put(
            f"/api/v1/changes/{change_id}/checklist/reorder",
            json={"phase": "execution", "item_ids": []},
        )
        assert resp.status_code == 422
