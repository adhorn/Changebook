"""Tenant resolution — invisible to the user.

Organisation exists as a database-level tenant boundary for future multi-tenancy.
In single-tenant mode (the default), a default org is auto-created on first use
and injected into every request. The operator never sees or picks an organisation.
"""

import uuid

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.organisation import Organisation


def get_default_org_id(db: Session = Depends(get_db)) -> uuid.UUID:
    """Return the default organisation ID, creating it if it doesn't exist."""
    org = db.query(Organisation).filter(Organisation.name == settings.org_name).first()
    if not org:
        org = Organisation(name=settings.org_name)
        db.add(org)
        db.commit()
        db.refresh(org)
    return org.id
