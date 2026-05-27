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
from app.core.logging import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    description="Production change tracking — from plan to verification",
    version="0.1.0",
)


@app.exception_handler(IntegrityError)
def integrity_error_handler(request: Request, exc: IntegrityError):
    logger.error("Database integrity error: %s", exc.orig)
    return JSONResponse(
        status_code=422,
        content={"detail": "Database constraint violation. Check that referenced resources exist."},
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
def create_tables():
    import app.models  # noqa: F401 — ensure all models are imported
    from app.core.database import engine
    from app.models.base import Base

    Base.metadata.create_all(bind=engine)


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
