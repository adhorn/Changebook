"""Tests for customer and service CRUD.

Customers are first-class entities. Services belong to customers.
Each change targets exactly one customer, one service, one environment.
Organisation is an invisible tenant boundary — auto-injected, never user-facing.
"""


class TestCustomerCRUD:
    """Customer create, list, get, with inline services."""

    def test_create_customer(self, client, org_and_team):
        """A customer can be created — org is auto-injected."""
        resp = client.post(
            "/api/v1/customers",
            json={
                "name": "Global Asset Manager",
                "description": "Largest institutional client",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Global Asset Manager"
        assert data["description"] == "Largest institutional client"
        assert data["organisation_id"] is not None
        assert data["services"] == []

    def test_create_customer_with_services(self, client, org_and_team):
        """A customer can be created with inline services."""
        resp = client.post(
            "/api/v1/customers",
            json={
                "name": "Pension Fund Alpha",
                "services": [
                    {"name": "Portfolio Management", "description": "Core PM platform"},
                    {"name": "Risk Analytics"},
                ],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["services"]) == 2
        names = {s["name"] for s in data["services"]}
        assert names == {"Portfolio Management", "Risk Analytics"}

    def test_list_customers(self, client, org_and_team):
        """Customers can be listed."""
        client.post("/api/v1/customers", json={"name": "Customer A"})
        client.post("/api/v1/customers", json={"name": "Customer B"})

        resp = client.get("/api/v1/customers")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_customer_detail(self, client, org_and_team):
        """A single customer can be retrieved with services."""
        create_resp = client.post(
            "/api/v1/customers",
            json={
                "name": "Bank XYZ",
                "services": [{"name": "Trading Platform"}],
            },
        )
        customer_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/customers/{customer_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Bank XYZ"
        assert len(resp.json()["services"]) == 1

    def test_customer_not_found(self, client):
        """Requesting a non-existent customer returns 404."""
        resp = client.get("/api/v1/customers/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


class TestServiceCRUD:
    """Services can be added to existing customers."""

    def test_add_service_to_customer(self, client, org_and_team):
        """A service can be added to an existing customer."""
        customer_resp = client.post(
            "/api/v1/customers",
            json={"name": "Fund Corp"},
        )
        customer_id = customer_resp.json()["id"]

        resp = client.post(
            f"/api/v1/customers/{customer_id}/services",
            json={"name": "Settlement Engine", "description": "T+1 settlement"},
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Settlement Engine"
        assert resp.json()["customer_id"] == customer_id

    def test_add_service_to_missing_customer(self, client):
        """Adding a service to a non-existent customer returns 404."""
        resp = client.post(
            "/api/v1/customers/00000000-0000-0000-0000-000000000000/services",
            json={"name": "Ghost Service"},
        )
        assert resp.status_code == 404


class TestChangeWithCustomer:
    """Each change targets exactly one customer, one service, one environment."""

    def test_create_change_with_customer_and_service(self, client, sample_change_data):
        """A change targets a single customer and service."""
        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Connection pool update",
                "author_name": "Adrian Hornsby",
                **sample_change_data,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["customer_id"] == sample_change_data["customer_id"]
        assert resp.json()["service_id"] == sample_change_data["service_id"]
        assert resp.json()["environment_id"] == sample_change_data["environment_id"]

    def test_change_requires_customer_and_environment(self, client):
        """A change cannot be created without customer_id, service_id, and environment_id."""
        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Missing required fields",
                "author_name": "Adrian Hornsby",
            },
        )
        assert resp.status_code == 422


class TestEnvironmentWithCustomer:
    """Environments can optionally be linked to a customer."""

    def test_create_environment_with_customer(self, client, org_and_team):
        """An environment can be linked to a customer."""
        customer = client.post(
            "/api/v1/customers",
            json={"name": "Dedicated Client"},
        )
        customer_id = customer.json()["id"]

        resp = client.post(
            "/api/v1/environments",
            json={
                "name": "PROD-CLIENT-01",
                "platform": "AWS",
                "description": "Dedicated env for client",
                "customer_id": customer_id,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["customer_id"] == customer_id

    def test_create_environment_without_customer(self, client, org_and_team):
        """An environment without a customer still works (shared envs)."""
        resp = client.post(
            "/api/v1/environments",
            json={
                "name": "SHARED-PROD-01",
                "platform": "Azure",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["customer_id"] is None
