from fastapi import APIRouter

from app.models.preflight import get_preflight_schema

router = APIRouter(prefix="/preflight-questions", tags=["preflight"])


@router.get("")
def get_preflight_questions():
    """Return the full pre-flight question structure.

    Any client (frontend, LLM agent, CLI) can call this to discover
    what questions to ask, without prior knowledge of the question set.
    """
    return get_preflight_schema()
