import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db
from app.schemas.templates import (
    TemplateCreate,
    TemplateDetailResponse,
    TemplateResponse,
    UseTemplate,
)
from app.services import templates as template_service

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[TemplateResponse])
def list_templates(
    title_search: str | None = None,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    templates, _ = template_service.list_templates(
        db, title_search=title_search, limit=limit, offset=offset
    )
    results = []
    for t in templates:
        resp = TemplateResponse.model_validate(t)
        resp.item_count = len(t.items)
        results.append(resp)
    return results


@router.get("/{template_id}", response_model=TemplateDetailResponse)
def get_template(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    template = template_service.get_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    resp = TemplateDetailResponse.model_validate(template)
    resp.item_count = len(template.items)
    return resp


@router.post("", response_model=TemplateDetailResponse, status_code=201)
def create_template(
    payload: TemplateCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = payload.model_dump()
    template = template_service.create_template(db, data, user.name)
    resp = TemplateDetailResponse.model_validate(template)
    resp.item_count = len(template.items)
    return resp


@router.post(
    "/{template_id}/use",
    response_model=dict,
    status_code=201,
)
def use_template(
    template_id: uuid.UUID,
    payload: UseTemplate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    template = template_service.get_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    change = template_service.create_change_from_template(
        db,
        template,
        title=payload.title,
        customer_id=payload.customer_id,
        service_id=payload.service_id,
        environment_id=payload.environment_id,
        author_name=user.name,
    )
    return {"change_id": str(change.id)}
