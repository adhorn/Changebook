import os

# Skip Alembic migrations in app startup — the suite manages its own
# schema via a session-scoped fixture below.
os.environ["TESTING"] = "1"

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.database import get_db
from app.main import app
from app.models import Base

# Test database — separate from the dev database to avoid data loss
SQLALCHEMY_TEST_URL = os.environ.get(
    "CHANGEBOOK_TEST_DATABASE_URL",
    "postgresql://changebook:changebook@localhost:5432/changebook_test",
)

engine = create_engine(SQLALCHEMY_TEST_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# PostgreSQL enum types created by the models — listed once so the migration
# tests and the cleanup logic agree on what needs dropping with CASCADE.
_ENUM_TYPES = ("changestatus", "checklistphase", "completionstatus", "reviewdecision")


def _drop_everything(eng) -> None:
    """Drop all domain tables, alembic_version, and enum types."""
    with eng.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
        conn.commit()
    Base.metadata.drop_all(bind=eng)
    with eng.connect() as conn:
        for enum_name in _ENUM_TYPES:
            conn.execute(text(f"DROP TYPE IF EXISTS {enum_name} CASCADE"))
        conn.commit()


def _alembic_upgrade_head() -> None:
    """Apply all migrations to the test database — the same code path the
    backend uses on startup."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", SQLALCHEMY_TEST_URL)
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session", autouse=True)
def _build_schema_via_migrations():
    """Build the test database schema by running Alembic to head, once
    per test session.

    This matches the production startup path (app/main.py runs the same
    `alembic upgrade head` on startup), so the suite exercises the
    migration-built schema rather than a `create_all()`-built one.
    """
    _drop_everything(engine)
    _alembic_upgrade_head()
    yield
    _drop_everything(engine)


@pytest.fixture(autouse=True)
def _clean_tables():
    """Truncate all domain tables before each test, keeping the schema
    (and alembic_version) intact."""
    tables = [f'"{t.name}"' for t in Base.metadata.sorted_tables]
    if tables:
        with engine.connect() as conn:
            conn.execute(text(f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE"))
            conn.commit()
    yield


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


# Standard test user identities — use as headers= on requests
JANE = {"X-User-Email": "jane@changebook.dev", "X-User-Name": "Jane Smith"}
BOB = {"X-User-Email": "bob@changebook.dev", "X-User-Name": "Bob Johnson"}


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
