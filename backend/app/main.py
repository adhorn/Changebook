import logging

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.auth import router as auth_router
from app.api.changes import router as changes_router
from app.api.organisations import router as organisations_router
from app.api.preflight import router as preflight_router
from app.api.templates import router as templates_router
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import ChangebookError
from app.core.logging import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    description="Production change tracking — from plan to verification",
    version="0.1.0",
)


@app.exception_handler(ChangebookError)
def domain_error_handler(request: Request, exc: ChangebookError):
    """Handle all domain exceptions — return clean JSON with the right status code."""
    logger.warning(
        "Domain error: %s",
        exc.detail,
        extra={"action": "domain_error", "detail": type(exc).__name__},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(IntegrityError)
def integrity_error_handler(request: Request, exc: IntegrityError):
    logger.error("Database integrity error: %s", exc.orig)
    return JSONResponse(
        status_code=422,
        content={"detail": "Database constraint violation. Check that referenced resources exist."},
    )


@app.exception_handler(Exception)
def unhandled_error_handler(request: Request, exc: Exception):
    """Catch-all — log the full error, return a clean JSON response."""
    logger.error(
        "Unhandled error: %s",
        str(exc),
        exc_info=True,
        extra={"action": "unhandled_error", "detail": type(exc).__name__},
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check server logs for details."},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(changes_router, prefix="/api/v1")
app.include_router(organisations_router, prefix="/api/v1")
app.include_router(preflight_router, prefix="/api/v1")
app.include_router(templates_router, prefix="/api/v1")


@app.on_event("startup")
def run_migrations():
    """Apply database migrations on startup.

    Uses Alembic to bring the database schema to the latest revision.
    This replaces the previous create_all() approach, which could only
    create new tables but not ALTER existing ones to add columns.

    Handles three cases:
    1. Fresh database — runs upgrade to create all tables.
    2. Existing database with alembic_version — runs upgrade (may be no-op).
    3. Existing database without alembic_version — stamps current revision
       (one-time migration from create_all to Alembic).

    Skipped during testing — test fixtures manage their own schema via
    create_all()/drop_all(), and migration correctness is validated by
    dedicated tests in test_migrations.py.
    """
    import os

    if os.environ.get("TESTING"):
        return

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect as sa_inspect

    from app.core.database import engine

    alembic_cfg = Config("alembic.ini")

    inspector = sa_inspect(engine)
    has_alembic = "alembic_version" in inspector.get_table_names()
    has_tables = "changes" in inspector.get_table_names()

    if has_tables and not has_alembic:
        # Existing database created by create_all() — stamp it so future
        # migrations apply correctly. No schema changes needed.
        logger.info("Existing database detected without migration history. Stamping as current.")
        command.stamp(alembic_cfg, "head")
    else:
        # Fresh database or already tracked — run migrations normally.
        command.upgrade(alembic_cfg, "head")


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "detail": "database not ready"},
        )
    return {"status": "ok"}
