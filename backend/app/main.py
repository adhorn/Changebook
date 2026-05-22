from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.changes import router as changes_router
from app.api.organisations import router as organisations_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    description="Production change tracking — from plan to verification",
    version="0.1.0",
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
