"""What does `alembic check` actually catch?

The migration-check CI job runs `alembic upgrade head && alembic check`
and is documented as catching "model changes that lack a corresponding
migration." Empirically that's been confirmed for added and removed
columns. This module exercises the other drift classes — type changes,
nullability flips, indexes, constraints, enum value additions — to
verify (or disprove) coverage for each.

Each test introduces one class of drift between the SQLAlchemy models
(`Base.metadata`) and the live schema (built from migrations), then
invokes `alembic check`. If `alembic check` exits non-zero,
`command.check` raises `CommandError` and the test passes. If
`alembic check` returns clean, that's a coverage gap and the test
fails — at which point the missed drift class needs to be either
caught some other way or documented as a known carve-out in
CONTRIBUTING.md.

Two patterns are used:

- *Model gained X but the DB doesn't have it*: mutate `Base.metadata`
  in-memory for the duration of the test, then restore.
- *DB has X but the model doesn't*: ALTER the DB directly, then revert
  in teardown. (This is what happens when someone drops a column
  from a model and forgets the migration.)
"""

from alembic import command
from alembic.config import Config
from alembic.util.exc import CommandError
from sqlalchemy import CheckConstraint, Column, Index, String, text

from app.models import Base
from tests.conftest import SQLALCHEMY_TEST_URL, engine


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", SQLALCHEMY_TEST_URL)
    return cfg


def _alembic_check_succeeds() -> bool:
    """True if `alembic check` returns clean (no drift detected),
    False if it raises CommandError (drift detected)."""
    try:
        command.check(_alembic_config())
        return True
    except CommandError:
        return False


# --- Canonical state sanity check ----------------------------------------


def test_no_drift_when_models_match_db():
    """When nothing has been mutated, alembic check passes. This is the
    baseline — every drift test below relies on this being green."""
    assert _alembic_check_succeeds(), (
        "Baseline alembic check failed — models do not match the migration-built schema "
        "before any drift was introduced. Fix this before trusting the rest of this file."
    )


# --- Added column ---------------------------------------------------------


def test_added_column_in_model_is_detected():
    """A column added to a model without a migration must be caught."""
    extra = Column("drift_test_added", String(50))
    Base.metadata.tables["changes"].append_column(extra)
    try:
        assert not _alembic_check_succeeds(), (
            "alembic check failed to detect a column added to a model"
        )
    finally:
        Base.metadata.tables["changes"]._columns.remove(extra)


# --- Dropped column (DB still has it) ------------------------------------


def test_extra_column_in_db_is_detected():
    """A column present in the DB but absent from the model (the
    symptom of dropping a column without writing a migration) must
    be caught."""
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE changes ADD COLUMN drift_test_extra VARCHAR(50)"))
        conn.commit()
    try:
        assert not _alembic_check_succeeds(), (
            "alembic check failed to detect a column present in the DB but not in the model"
        )
    finally:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE changes DROP COLUMN drift_test_extra"))
            conn.commit()


# --- Nullability flip ----------------------------------------------------


def test_nullability_flip_is_detected():
    """Changing a column from NOT NULL in the DB to nullable in the model
    (or vice versa) must be caught."""
    # `changes.title` is nullable=False in the model. Flip it to True
    # in metadata while the DB stays NOT NULL.
    col = Base.metadata.tables["changes"].columns["title"]
    original = col.nullable
    col.nullable = True
    try:
        assert not _alembic_check_succeeds(), "alembic check failed to detect a nullability flip"
    finally:
        col.nullable = original


# --- Column type change --------------------------------------------------


def test_type_change_is_detected():
    """Changing a column's SQL type in the model (e.g. String(255) → String(100))
    must be caught."""
    col = Base.metadata.tables["changes"].columns["title"]
    original_type = col.type
    # Shrink from String(255) to String(50) — clear type narrowing.
    col.type = String(50)
    try:
        assert not _alembic_check_succeeds(), "alembic check failed to detect a column type change"
    finally:
        col.type = original_type


# --- Index addition ------------------------------------------------------


def test_added_index_in_model_is_detected():
    """An index added to a model without a migration must be caught."""
    tbl = Base.metadata.tables["changes"]
    new_index = Index("ix_drift_test_changes_title", tbl.c.title)
    try:
        assert not _alembic_check_succeeds(), (
            "alembic check failed to detect an index added to a model"
        )
    finally:
        tbl.indexes.discard(new_index)


# --- Index removal (DB has extra) ----------------------------------------


def test_extra_index_in_db_is_detected():
    """An index present in the DB but absent from the model must be caught."""
    with engine.connect() as conn:
        conn.execute(text("CREATE INDEX ix_drift_test_extra ON changes (title)"))
        conn.commit()
    try:
        assert not _alembic_check_succeeds(), (
            "alembic check failed to detect an index present in the DB but not in the model"
        )
    finally:
        with engine.connect() as conn:
            conn.execute(text("DROP INDEX IF EXISTS ix_drift_test_extra"))
            conn.commit()


# --- Known carve-outs ----------------------------------------------------
#
# The following two classes are NOT caught by `alembic check`. The
# tests assert the gap, so they stay green as long as the gap exists.
# If alembic ever improves and starts detecting them, the tests will
# fail — at which point the corresponding entry in CONTRIBUTING.md can
# be removed.
#
# When this happens, invert the assertion (`not _alembic_check_succeeds()`)
# and update the documented carve-out list.


def test_added_check_constraint_is_not_detected_carve_out():
    """alembic check does not detect CHECK constraint additions.

    Documented in CONTRIBUTING.md as a known carve-out. If you add a
    CHECK constraint to a model, also write the migration explicitly —
    autogenerate will not flag a missing one.
    """
    tbl = Base.metadata.tables["changes"]
    constraint = CheckConstraint("title != ''", name="ck_drift_test_title_nonempty")
    tbl.append_constraint(constraint)
    try:
        assert _alembic_check_succeeds(), (
            "alembic check now detects added CHECK constraints — "
            "remove the carve-out from CONTRIBUTING.md and invert this assertion."
        )
    finally:
        tbl.constraints.discard(constraint)


def test_added_enum_value_is_not_detected_carve_out():
    """alembic check does not detect PostgreSQL enum value additions.

    Documented in CONTRIBUTING.md as a known carve-out. If you add a
    value to a model enum, write the migration explicitly with
    `op.execute("ALTER TYPE ... ADD VALUE ...")` — autogenerate will
    not flag a missing one.
    """
    # ChangeStatus is a Python StrEnum; we cannot add a value at
    # runtime. Simulate the symptom by adding the value to the live
    # PostgreSQL enum and asking whether alembic notices the DB enum
    # has an extra value the model does not declare.
    with engine.connect() as conn:
        conn.execute(text("ALTER TYPE changestatus ADD VALUE IF NOT EXISTS 'drift_test_value'"))
        conn.commit()
    # The enum value lingers in this session — PostgreSQL has no
    # DROP VALUE. The session-scoped fixture rebuilds the schema
    # next session, and nothing in our code references the extra value.
    assert _alembic_check_succeeds(), (
        "alembic check now detects added enum values — "
        "remove the carve-out from CONTRIBUTING.md and invert this assertion."
    )
