import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import MOCK_USERS
from app.core.database import get_db
from app.core.tenant import get_default_org_id
from app.models.customer import Customer, Service
from app.models.environment import Environment
from app.models.team import Team
from app.schemas.customers import (
    CustomerCreate,
    CustomerDetailResponse,
    ServiceCreate,
    ServiceResponse,
)
from app.schemas.environments import EnvironmentCreate, EnvironmentResponse
from app.schemas.organisations import (
    TeamCreate,
    TeamResponse,
)

router = APIRouter(tags=["organisations"])


# --- Teams ---


@router.post("/teams", response_model=TeamResponse, status_code=201)
def create_team(
    payload: TeamCreate,
    db: Session = Depends(get_db),
    org_id: uuid.UUID = Depends(get_default_org_id),
):
    team = Team(name=payload.name, organisation_id=org_id)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


@router.get("/teams", response_model=list[TeamResponse])
def list_teams(db: Session = Depends(get_db)):
    return db.query(Team).all()


# --- Customers ---


@router.post("/customers", response_model=CustomerDetailResponse, status_code=201)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    org_id: uuid.UUID = Depends(get_default_org_id),
):
    customer = Customer(
        name=payload.name,
        description=payload.description,
        organisation_id=org_id,
    )
    db.add(customer)
    db.flush()

    if payload.services:
        for svc_data in payload.services:
            svc = Service(
                name=svc_data.name,
                description=svc_data.description,
                customer_id=customer.id,
            )
            db.add(svc)

    db.commit()
    db.refresh(customer)
    return customer


@router.get("/customers", response_model=list[CustomerDetailResponse])
def list_customers(db: Session = Depends(get_db)):
    return db.query(Customer).all()


@router.get("/customers/{customer_id}", response_model=CustomerDetailResponse)
def get_customer(customer_id: uuid.UUID, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.post(
    "/customers/{customer_id}/services",
    response_model=ServiceResponse,
    status_code=201,
)
def add_service(
    customer_id: uuid.UUID,
    payload: ServiceCreate,
    db: Session = Depends(get_db),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    svc = Service(
        name=payload.name,
        description=payload.description,
        customer_id=customer_id,
    )
    db.add(svc)
    db.commit()
    db.refresh(svc)
    return svc


# --- Environments ---


@router.post("/environments", response_model=EnvironmentResponse, status_code=201)
def create_environment(
    payload: EnvironmentCreate,
    db: Session = Depends(get_db),
    org_id: uuid.UUID = Depends(get_default_org_id),
):
    env = Environment(
        name=payload.name,
        platform=payload.platform,
        description=payload.description,
        organisation_id=org_id,
        customer_id=payload.customer_id,
    )
    db.add(env)
    db.commit()
    db.refresh(env)
    return env


@router.get("/environments", response_model=list[EnvironmentResponse])
def list_environments(db: Session = Depends(get_db)):
    return db.query(Environment).all()


# --- People (known users) ---


@router.get("/people", response_model=list[str])
def list_people():
    """Return all known users in the system."""
    return sorted(u.name for u in MOCK_USERS)
