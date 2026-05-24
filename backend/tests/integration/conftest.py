"""Integration test fixtures using real Postgres.

These tests require a running Postgres instance. In CI, this is provided
by the GitHub Actions service container. Locally, use:

    docker compose up db

Then run:

    CHANGEBOOK_DATABASE_URL=postgresql://changebook:changebook@localhost:5432/changebook_test \
    pytest tests/integration -v
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import get_db
from app.main import app
from app.models import Base

# Skip entire module if no Postgres URL is configured
POSTGRES_URL = os.environ.get("CHANGEBOOK_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_URL or "sqlite" in (POSTGRES_URL or ""),
    reason="Requires CHANGEBOOK_DATABASE_URL pointing to a real Postgres instance",
)


@pytest.fixture(scope="session")
def pg_engine():
    """Create engine once for all integration tests."""
    engine = create_engine(POSTGRES_URL)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def setup_db(pg_engine):
    """Create all tables before each test, drop after.

    Each test gets a clean database.
    """
    Base.metadata.create_all(bind=pg_engine)
    yield
    Base.metadata.drop_all(bind=pg_engine)


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
    with TestClient(app, headers={
        "X-User-Email": "test@changebook.dev",
        "X-User-Name": "Test User",
    }) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def org_and_team(client):
    """Create a default team. Organisation is auto-injected."""
    team = client.post("/api/v1/teams", json={"name": "Platform Team"})
    team_data = team.json()

    return {"org_id": team_data["organisation_id"], "team_id": team_data["id"]}


@pytest.fixture
def environment(client, org_and_team):
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
