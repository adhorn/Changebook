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

Most production changes should flow through a pipeline. But some can't — infrastructure migrations, manual database operations, one-off platform changes. These still happen, and they still need discipline.

Changebook tracks those changes. It's not a runbook tool or a CI/CD replacement. It's a structured record for planned changes that require human judgement.

## Design principles

Changebook is grounded in cognitive systems engineering (CSE) — the same discipline behind checklists in aviation and decision support in other safety-critical environments. Each principle translates into a specific tool behaviour:

**Cognitive forcing functions.** The pre-flight questions don't score risk or make decisions. They force the operator to think before acting. *What happens if this fails? What's the blast radius? How do you roll back, and how long does it take?* The section ordering is deliberate: what you're doing, then who it affects, then what happens if it goes wrong. That sequence walks the operator through a mental simulation of the change before a single command runs.

**Common ground, not gatekeeping.** Reviewers see everything the author sees — pre-flight answers, the full checklist, the maintenance window. The review isn't an approval stamp. It's two people building shared understanding of what's about to happen. Hold points are the sharpest version: execution stops until a second person confirms they see what the operator sees.

**Show, don't decide.** During execution, the operator sees the maintenance window, the expected outcome for each step, the rollback action. The completion form asks *"what did you observe?"* — not *"did it pass?"* There's no green/red traffic light. The operator records what happened and decides whether to proceed.

**Organisational memory through templates.** Templates don't come from playbooks written in advance. They come from changes that were actually executed. A team does a certificate rotation, works through the steps, discovers the edge cases, records what they observed — then saves it as a template. Next time, the starting point is real operational experience, not theory. Customer-specific context is stripped; the procedure transfers, the context doesn't.

**The audit trail is the team's memory.** Every state transition, every review decision, every step completion — who did it, when, what they observed. This isn't for auditors. It's so the team can look back at what actually happened during a change, not what they planned to happen.

## Key features

- **Pre-flight profile** — structured questions that force thinking about blast radius, rollback, dependencies, and customer impact before execution begins
- **Phased checklists** — pre-flight, execution, and verification steps with observed results recorded at each step
- **Hold points** — steps that require a second person to verify before proceeding
- **Peer review** — approve, request changes, or block a change before execution starts
- **Maintenance windows** — structured datetime range with timezone, visible during execution
- **Templates** — save any completed change as a reusable procedure; the library grows from real operations
- **Markdown export** — full change record (metadata, pre-flight answers, checklist, reviews, audit trail) as a portable document
- **Audit trail** — every state transition, review, and completion recorded with actor and timestamp
- **Multi-tenancy** — customers, services, and environments scoped to an organisation

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
| `CHANGEBOOK_DATABASE_URL` | `postgresql://changebook:changebook@localhost:5432/changebook` | Database connection string |
| `CHANGEBOOK_DEBUG` | `false` | Enable SQL logging |
| `CHANGEBOOK_CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins (JSON array) |
| `CHANGEBOOK_LOG_LEVEL` | `INFO` | Log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `CHANGEBOOK_LOG_FORMAT` | `json` | `json` for structured output, `text` for local dev |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend URL for the frontend |

### Logging

Logs go to stdout as one JSON object per line. Every service-layer event carries `change_id`, `actor`, and `action` fields so you can trace the full lifecycle of a single change:

```bash
# Filter logs for a specific change
uvicorn app.main:app | jq 'select(.change_id == "some-uuid")'

# Show only gate rejections
uvicorn app.main:app | jq 'select(.action == "gate_rejected")'

# Save to a file
uvicorn app.main:app | tee -a changebook.log
```

Set `CHANGEBOOK_LOG_FORMAT=text` for human-readable output during development. In production, leave it as `json` and let your infrastructure (Docker, CloudWatch, journald) handle the log drain.

## Project structure

```
backend/
  app/
    api/          # FastAPI route handlers (thin — delegate to services)
    core/         # Config, database, auth
    models/       # SQLAlchemy models
    schemas/      # Pydantic request/response schemas
    services/     # Business logic (state machine, export, templates)
  tests/          # 218 pytest tests
  migrations/     # Alembic migrations

frontend/
  app/            # Next.js App Router pages
  components/     # Shared React components
  lib/            # API client, auth, shared constants
  e2e/            # Playwright end-to-end tests
```

## Tech stack

- **Backend**: Python, FastAPI, SQLAlchemy, Alembic
- **Frontend**: TypeScript, Next.js (App Router), React, Tailwind CSS
- **Database**: PostgreSQL
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
