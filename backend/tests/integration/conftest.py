"""Integration test fixtures using real Postgres.

These tests require a running Postgres instance. Locally, use:

    docker compose up db

Then run:

    pytest tests/integration -v

Schema construction and per-test cleanup are handled by the parent
conftest (`tests/conftest.py`) via the session-scoped Alembic fixture
and the per-test TRUNCATE fixture. This module only adds Postgres-
specific session and client wiring.
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import get_db
from app.main import app

POSTGRES_URL = os.environ.get(
    "CHANGEBOOK_TEST_DATABASE_URL",
    "postgresql://changebook:changebook@localhost:5432/changebook_test",
)


@pytest.fixture(scope="session")
def pg_engine():
    """Create engine once for all integration tests."""
    engine = create_engine(POSTGRES_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def db(pg_engine):
    """Provide a transactional database session for each test."""
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    """Test client wired to the Postgres session."""

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(
        app,
        headers={
            "X-User-Email": "test@changebook.dev",
            "X-User-Name": "Test User",
        },
    ) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def customer_and_service(client):
    """Create a customer with one service. Organisation is auto-injected."""
    resp = client.post(
        "/api/v1/customers",
        json={
            "name": "Northwind Trading",
            "services": [{"name": "Data Platform"}],
        },
    )
    cust_data = resp.json()
    return {
        "customer_id": cust_data["id"],
        "service_id": cust_data["services"][0]["id"],
    }


@pytest.fixture
def environment(client):
    """Create a test environment."""
    resp = client.post(
        "/api/v1/environments",
        json={
            "name": "PROD-EU-01",
            "platform": "Azure",
            "description": "Production EU client 1",
        },
    )
    return resp.json()
