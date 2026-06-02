# Contributing to Changebook

## Getting started

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker and Docker Compose (for the full stack or Postgres)

### Development setup

**Full stack (recommended):**

```bash
docker compose up
```

Open http://localhost:3000. The backend runs on http://localhost:8000.

**Backend only (requires Postgres — start one with `docker compose up db`):**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

**Frontend only:**

```bash
cd frontend
npm install
npm run dev
```

### Running tests

```bash
# Backend (from backend/)
python -m pytest tests/ -q

# Lint
ruff check .
ruff format --check .

# Frontend build check
cd frontend && npx next build

# E2E tests (requires Postgres with changebook_test DB — see below)
cd frontend && npx playwright test
```

All tests must pass before submitting a PR. The CI pipeline runs the same checks.

#### E2E tests

E2E tests run on **separate ports** (backend 8001, frontend 3001) against a **separate test database** (`changebook_test`), so they never touch the dev database or conflict with `docker compose up`.

**Prerequisites:**

1. Docker must be running — `docker compose up db` creates both the `changebook` and `changebook_test` databases (via `backend/init-test-db.sql`).
2. Install the browser: `cd frontend && npx playwright install chromium`

**Running:**

```bash
cd frontend

# Run all E2E tests — Playwright starts backend (port 8001) and frontend (port 3001) automatically
npx playwright test

# Run with visible browser
npx playwright test --headed
```

If a backend is already running on port 8001, Playwright reuses it (locally only — CI always starts fresh). The test port and database configuration lives in `frontend/e2e/config.ts`.

**Note:** If you see a timeout on the backend health check, make sure Postgres is running and the `changebook_test` database exists. Run `docker compose up db` to create it.

## Development workflow

1. **Branch** from `main`
2. **Write tests first** (TDD) — the test describes the behaviour, then the implementation makes it pass
3. **Run the full check suite locally** before pushing:
   - `ruff check .`
   - `ruff format --check .`
   - `python -m pytest tests/ -q`
   - `cd frontend && npx next build`
4. **Open a PR** with a clear description of what changed and why
5. **One feature per PR** — keep changes focused

## Code conventions

### Backend (Python / FastAPI)

- SQLAlchemy ORM for all database access — no raw SQL
- Pydantic schemas for all request/response validation
- Service layer (`app/services/`) holds business logic; API routes are thin
- Ruff for linting and formatting (config in `pyproject.toml`)

### Frontend (TypeScript / Next.js)

- All API calls go through `lib/api.ts`
- Tailwind CSS for styling — no separate CSS files
- Components in `components/`, pages in `app/`

### Tests

- Test files mirror the feature they test (e.g. `test_reviews.py` for the review workflow)
- Use the test helpers in `conftest.py` for creating test data
- Integration tests (in `tests/integration/`) run against Postgres and are skipped locally

### Database migrations

The schema is managed by Alembic. Any change to a model under `app/models/` — a new table, a new column, a changed type or constraint — needs a matching migration committed **in the same PR**.

Generate one after editing the models:

```bash
cd backend
alembic revision --autogenerate -m "describe the change"
# review the generated file in migrations/versions/, then apply it:
alembic upgrade head
```

CI runs `alembic check` and fails the PR if a model change has no matching migration.

The test suite constructs its schema by running `alembic upgrade head` once per session, then truncates tables between tests. This means unit tests exercise the same schema-construction path the backend uses on startup — so a migration that diverges from the models will surface in test failures as well as in `alembic check`.

## Reporting bugs

Open an issue with:
- What you expected
- What happened instead
- Steps to reproduce

## Security issues

See [SECURITY.md](SECURITY.md) for how to report security vulnerabilities privately.
