import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.main import app
from app.models import Base

# In-memory SQLite for tests (fast, no Postgres dependency)
SQLALCHEMY_TEST_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
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
def unauthenticated_client(db):
    """Client with no auth headers — for testing 401 responses."""

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def org_and_team(client):
    """Create a default team. Organisation is auto-injected."""
    team = client.post("/api/v1/teams", json={"name": "Platform Team"})
    team_data = team.json()

    return {"org_id": team_data["organisation_id"], "team_id": team_data["id"]}


@pytest.fixture
def sample_change_data(client, org_and_team):
    """Create a customer, service, and environment — the minimum needed for a change."""
    customer = client.post(
        "/api/v1/customers",
        json={
            "name": "Test Client",
            "services": [{"name": "Core Platform"}],
        },
    )
    customer_data = customer.json()

    env = client.post(
        "/api/v1/environments",
        json={"name": "PROD-EU-01", "platform": "Azure"},
    )
    env_data = env.json()

    return {
        "customer_id": customer_data["id"],
        "service_id": customer_data["services"][0]["id"],
        "environment_id": env_data["id"],
    }
