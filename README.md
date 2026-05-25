# Changebook

Every production change, tracked from plan to verification. Like a pilot's checklist for ops.

> **Status**: v0.1 — functional for local use and demos. Not production-hardened yet. See [Security](#security) below.

## What it does

Changebook tracks the full lifecycle of production changes in three stages:

1. **Pre-flight** — What are you changing? What happens if it fails? Who is affected? How do you roll back?
2. **Execution** — Step-by-step checklist. Each step verified before proceeding. Nothing skipped. Hold points require a second pair of eyes.
3. **Verification** — Did it work? Does the customer's experience confirm it worked?

Everything is audited. The full change — who proposed it, who reviewed it, what was executed step by step, what was verified — is an immutable record.

## Why

ITSM tools track approval. Runbook tools track execution. Nothing tracks the full lifecycle in one place with the discipline of a pilot's checklist.

When an incident happens and the question is "what changed?", the answer should be in the tool — not in someone's memory or a chat message.

## Quick start

```bash
docker compose up
```

Open [http://localhost:3000](http://localhost:3000). The backend API is at [http://localhost:8000](http://localhost:8000) (Swagger docs at `/docs`).

## Development setup

See [CONTRIBUTING.md](CONTRIBUTING.md) for full details. The short version:

**Full stack (Docker):**

```bash
docker compose up
```

**Backend only (SQLite, no Docker):**

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
# Backend
cd backend
ruff check .
ruff format --check .
python -m pytest tests/ -q

# Frontend
cd frontend
npx next build
```

### Environment variables

Copy `.env.example` to `backend/.env` and adjust as needed. Key variables:

| Variable | Default | Description |
|---|---|---|
| `CHANGEBOOK_DATABASE_URL` | `sqlite:///./changebook_dev.db` | Database connection string |
| `CHANGEBOOK_DEBUG` | `false` | Enable SQL logging |
| `CHANGEBOOK_CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins (JSON array) |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend URL for the frontend |

## Tech stack

- **Backend**: Python, FastAPI, SQLAlchemy, Alembic
- **Frontend**: TypeScript, Next.js (App Router), React, Tailwind CSS
- **Database**: PostgreSQL (Docker) or SQLite (local dev)
- **Deployment**: Docker Compose

## Security

Changebook is in early development. The current authentication model uses **mock identity headers** (`X-User-Name`, `X-User-Email`) intended for local development and demos only. There is no cryptographic authentication.

**Do not deploy this to a network accessible by untrusted users without adding real authentication first.**

The codebase is designed so that swapping in real auth (e.g. Auth.js / NextAuth JWT verification) requires changing a single dependency (`backend/app/core/auth.py`) without modifying any business logic.

See [SECURITY.md](SECURITY.md) for the full security model and how to report vulnerabilities.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow, code conventions, and how to submit changes.

## License

[Apache 2.0](LICENSE)
