"""Migration tests — validates Alembic scripts produce a correct schema.

These tests are mandatory: every migration must pass the round-trip test
(upgrade → downgrade → upgrade) and produce a schema that matches the
SQLAlchemy models.
"""

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.models import Base

SQLALCHEMY_TEST_URL = os.environ.get(
    "CHANGEBOOK_TEST_DATABASE_URL",
    "postgresql://changebook:changebook@localhost:5432/changebook_test",
)


def _alembic_config() -> Config:
    """Create Alembic config pointing at the test database."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", SQLALCHEMY_TEST_URL)
    return cfg


def _drop_everything(engine):
    """Drop all tables and enum types for a clean slate."""
    with engine.connect() as conn:
        # Drop alembic_version first (not tracked by Base.metadata)
        conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
        conn.commit()
    Base.metadata.drop_all(bind=engine)
    # Drop PostgreSQL enum types that survive table drops
    with engine.connect() as conn:
        for enum_name in ["changestatus", "checklistphase", "completionstatus", "reviewdecision"]:
            conn.execute(text(f"DROP TYPE IF EXISTS {enum_name} CASCADE"))
        conn.commit()


@pytest.fixture
def migration_engine():
    """Provide a clean database engine for migration tests."""
    engine = create_engine(SQLALCHEMY_TEST_URL)
    _drop_everything(engine)
    yield engine
    _drop_everything(engine)
    engine.dispose()


class TestMigrationRoundTrip:
    """Alembic migration round-trip: upgrade → downgrade → upgrade."""

    def test_upgrade_creates_all_tables(self, migration_engine):
        cfg = _alembic_config()
        command.upgrade(cfg, "head")

        inspector = inspect(migration_engine)
        tables = set(inspector.get_table_names())

        expected = {
            "organisations",
            "customers",
            "services",
            "environments",
            "changes",
            "checklist_items",
            "checklist_completions",
            "reviews",
            "audit_events",
            "change_templates",
            "template_checklist_items",
            "alembic_version",
        }
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"

    def test_downgrade_removes_all_tables(self, migration_engine):
        cfg = _alembic_config()
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")

        inspector = inspect(migration_engine)
        tables = set(inspector.get_table_names())
        # Only alembic_version should remain (or nothing)
        domain_tables = tables - {"alembic_version"}
        assert domain_tables == set(), f"Tables not cleaned up: {domain_tables}"

    def test_full_round_trip(self, migration_engine):
        """Upgrade → downgrade → upgrade must succeed without errors."""
        cfg = _alembic_config()
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")

        inspector = inspect(migration_engine)
        tables = set(inspector.get_table_names())
        assert "changes" in tables
        assert "checklist_items" in tables

    def test_migration_matches_models(self, migration_engine):
        """Schema from migration must match schema from SQLAlchemy models.

        Compares table names and column names between Alembic-created schema
        and model-defined metadata. Catches drift between models and migrations.
        """
        cfg = _alembic_config()
        command.upgrade(cfg, "head")

        inspector = inspect(migration_engine)
        db_tables = set(inspector.get_table_names()) - {"alembic_version"}

        model_tables = {table.name for table in Base.metadata.sorted_tables}
        assert db_tables == model_tables, (
            f"Table mismatch.\n"
            f"  In DB but not models: {db_tables - model_tables}\n"
            f"  In models but not DB: {model_tables - db_tables}"
        )

        # Check columns match for each table
        for table_name in model_tables:
            db_columns = {col["name"] for col in inspector.get_columns(table_name)}
            model_columns = {col.name for col in Base.metadata.tables[table_name].columns}
            assert db_columns == model_columns, (
                f"Column mismatch in {table_name}.\n"
                f"  In DB but not model: {db_columns - model_columns}\n"
                f"  In model but not DB: {model_columns - db_columns}"
            )
