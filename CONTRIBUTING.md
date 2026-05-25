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

**Backend only:**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
# Uses SQLite by default for development
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

# E2E tests (requires backend + frontend running)
cd frontend && npx playwright test
```

All tests must pass before submitting a PR. The CI pipeline runs the same checks.

#### E2E tests

The E2E tests use Playwright and run against the full stack (backend + frontend). If both are already running locally, Playwright reuses them. Otherwise it starts them automatically.

```bash
# First time: install browser
cd frontend && npx playwright install chromium

# Run all E2E tests
npx playwright test

# Run with visible browser
npx playwright test --headed
```

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

## Reporting bugs

Open an issue with:
- What you expected
- What happened instead
- Steps to reproduce

## Security issues

See [SECURITY.md](SECURITY.md) for how to report security vulnerabilities privately.
