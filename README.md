# Changebook

Every production change, tracked from plan to verification. Like a pilot's checklist for ops.

## What it does

Changebook tracks the full lifecycle of production changes in three stages:

1. **Pre-flight** — What are you changing? What happens if it fails? Who is affected? How do you roll back?
2. **Execution** — Step-by-step checklist. Each step verified before proceeding. Nothing skipped.
3. **Verification** — Did it work? Does the customer's experience confirm it worked?

Everything is audited. The full change — who proposed it, who reviewed it, what was executed step by step, what was verified — is an immutable record.

## Quick start

```bash
docker compose up
```

Open [http://localhost:3000](http://localhost:3000).

## Why

ITSM tools track approval. Runbook tools track execution. Nothing tracks the full lifecycle in one place with the discipline of a pilot's checklist.

When an incident happens and the question is "what changed?", the answer should be in the tool — not in someone's memory or a chat message.

## Tech stack

- **Backend**: FastAPI (Python)
- **Frontend**: Next.js (React, TypeScript)
- **Database**: PostgreSQL
- **Deployment**: Docker Compose

## License

Apache 2.0
