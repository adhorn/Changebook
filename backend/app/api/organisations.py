import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.environment import Environment
from app.models.organisation import Organisation
from app.models.team import Team
from app.schemas.environments import EnvironmentCreate, EnvironmentResponse
from app.schemas.organisations import (
    OrganisationCreate,
    OrganisationResponse,
    TeamCreate,
    TeamResponse,
)

router = APIRouter(tags=["organisations"])


# --- Organisations ---


@router.post("/organisations", response_model=OrganisationResponse, status_code=201)
def create_organisation(payload: OrganisationCreate, db: Session = Depends(get_db)):
    org = Organisation(name=payload.name)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@router.get("/organisations", response_model=list[OrganisationResponse])
def list_organisations(db: Session = Depends(get_db)):
    return db.query(Organisation).all()


# --- Teams ---


@router.post("/teams", response_model=TeamResponse, status_code=201)
def create_team(payload: TeamCreate, db: Session = Depends(get_db)):
    org = db.query(Organisation).filter(Organisation.id == payload.organisation_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organisation not found")
    team = Team(name=payload.name, organisation_id=payload.organisation_id)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


@router.get("/teams", response_model=list[TeamResponse])
def list_teams(
    organisation_id: uuid.UUID | None = None, db: Session = Depends(get_db)
):
    query = db.query(Team)
    if organisation_id:
        query = query.filter(Team.organisation_id == organisation_id)
    return query.all()


# --- Environments ---


@router.post("/environments", response_model=EnvironmentResponse, status_code=201)
def create_environment(payload: EnvironmentCreate, db: Session = Depends(get_db)):
    org = db.query(Organisation).filter(Organisation.id == payload.organisation_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organisation not found")
    env = Environment(
        name=payload.name,
        platform=payload.platform,
        description=payload.description,
        organisation_id=payload.organisation_id,
    )
    db.add(env)
    db.commit()
    db.refresh(env)
    return env


@router.get("/environments", response_model=list[EnvironmentResponse])
def list_environments(
    organisation_id: uuid.UUID | None = None, db: Session = Depends(get_db)
):
    query = db.query(Environment)
    if organisation_id:
        query = query.filter(Environment.organisation_id == organisation_id)
    return query.all()
