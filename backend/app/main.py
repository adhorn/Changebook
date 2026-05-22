import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.changes import router as changes_router
from app.api.organisations import router as organisations_router
from app.core.config import settings

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

app.include_router(changes_router, prefix="/api/v1")
app.include_router(organisations_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
