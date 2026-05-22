# Changebook — Development Guide

Production change tracking tool. FastAPI backend, Next.js frontend, Postgres database.

## Running the project

```bash
# Full stack
docker compose up

# Backend only (development)
cd backend && pip install -e ".[dev]" && uvicorn app.main:app --reload --port 8000

# Frontend only (development)
cd frontend && npm install && npm run dev

# Run backend tests
cd backend && pytest

# Run frontend tests
cd frontend && npm test
```

## Architecture

- `backend/` — FastAPI (Python 3.11+). REST API. SQLAlchemy ORM + Alembic migrations.
- `frontend/` — Next.js 14 (React, TypeScript, Tailwind). App Router.
- `docker-compose.yml` — Postgres + backend + frontend. One command to run.

## Code conventions

### Backend (Python)
- Models in `backend/app/models/`. SQLAlchemy declarative base.
- API routes in `backend/app/api/`. One file per resource (changes.py, steps.py, etc).
- Schemas in `backend/app/schemas/`. Pydantic models for request/response validation.
- Services in `backend/app/services/`. Business logic lives here, not in route handlers.
- Tests in `backend/tests/`. Pytest. Each test gets a clean database transaction (rolled back after).
- Alembic migrations in `backend/migrations/`. Never edit a migration after it's been applied.
- IMPORTANT: Always write tests first, then implementation. Tests drive design.

### Frontend (TypeScript)
- App Router: pages in `frontend/src/app/`. Server components by default.
- Components in `frontend/src/components/`. One component per file.
- API client in `frontend/src/lib/api.ts`. All backend calls go through this.
- IMPORTANT: Use `fetch` for API calls, not axios. Keep dependencies minimal.

### Database
- Postgres 16. All tables have `created_at` and `updated_at` timestamps.
- Audit events table is append-only. No UPDATE or DELETE on audit_events, ever.
- Use JSONB for flexible fields (pre-flight answers, template definitions).
- Alembic for migrations: `cd backend && alembic revision --autogenerate -m "description"`

### API conventions
- REST. Resource-oriented URLs: `/api/v1/changes`, `/api/v1/changes/{id}/steps`.
- Consistent response envelope: `{"data": ..., "meta": {...}}` for lists, raw object for single items.
- HTTP status codes: 201 for create, 200 for read/update, 204 for delete, 422 for validation errors.
- All timestamps in ISO 8601 UTC.

### General
- No print statements. Use Python logging / console.error.
- No hardcoded secrets. Everything through environment variables.
- Commit messages: imperative mood, one line, explain why not what.
