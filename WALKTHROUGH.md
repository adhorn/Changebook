# Try Changebook in 5 minutes

This walks you through one complete change lifecycle — from plan to verification. You'll see how the pre-flight questions force thinking, how hold points require a second pair of eyes, and how the audit trail captures what actually happened.

## Start it up

```bash
docker compose up
```

Open [http://localhost:3000](http://localhost:3000).

Load the demo data (customers, environments, and certificate rotation templates):

```bash
cd backend
python seed.py
```

## 1. Create a change from a template

Go to **Templates** in the nav bar. You'll see two certificate rotation templates seeded from real operations. Pick one — say "Certificate Rotation — Web Servers".

Click **Use Template**. This creates a new change pre-loaded with a realistic checklist: backup the current cert, deploy the new one, reload nginx, verify the TLS handshake, confirm customer-facing URLs respond.

Give it a title. Pick a customer, service, and environment from the dropdowns.

## 2. Answer the pre-flight questions

The pre-flight section has five groups of questions — a cognitive forcing function. The sequence matters:

1. **The change** — what you're doing and what should happen
2. **What the customer experiences** — not what you see, what they see
3. **Failure and recovery** — assume it goes wrong, then what?
4. **Timing and coordination** — is this the right moment for the customer, or just convenient for you?
5. **Customer awareness** — does the customer actually know?

Fill them in. Notice how the third question in "Customer experience" asks *"if this fails mid-way, what is the customer in the middle of doing?"* — that's the forcing function. You have to think about the customer's state at the moment of failure, not just your own.

## 3. Submit for review

Click **Submit for Review**. The change moves from draft to in_review.

Assign a reviewer (type any name — the system uses header-based identity, no login required). Then switch identity: set the `X-User-Name` header to the reviewer's name (the UI shows the current user in the top bar — click it to change).

As the reviewer, you see everything: the pre-flight answers, the full checklist, the maintenance window. Approve, request changes, or block. Two people building shared understanding of what's about to happen.

## 4. Execute the checklist

Once approved, transition to **Executing**. Now the checklist is live.

Work through it step by step. For each item you'll see:
- The step description and command
- The expected outcome
- The rollback action (what to do if this step fails)

Complete each step by recording **what you actually observed**. The system enforces order: you can't skip ahead.

When you reach a **hold point** (marked with a shield icon), the copy button is locked — the operator can see the command but cannot copy or complete the step until a second person verifies. Switch identity, read the command, and verify it. Copy then unlocks and the step can be run. Completer must be a different person than the verifier (two-person rule).

## 5. Verify and close

The verification phase asks you to confirm the change worked from the customer's perspective. Complete the verification steps, then transition to **Done**.

## What to look at

- **Audit trail** — scroll down on any change to see every state transition, review, and step completion with timestamps and actors
- **Markdown export** — click Export to get the full change record as a portable document
- **Pre-flight edit invalidation** — try editing a change after it's been approved. All reviews reset to pending. The system won't let approved changes drift from what was reviewed.

## Architecture (for the curious)

- **Backend**: Python, FastAPI, SQLAlchemy, PostgreSQL
- **Frontend**: TypeScript, Next.js, Tailwind
- **State machine**: draft → in_review → approved → executing → done (with abort from any active state)
- **Auth**: mock headers (`X-User-Name`) — designed to be swapped for real auth without changing business logic
- **218 backend tests**, structured JSON logging, domain exception hierarchy

The design is grounded in cognitive systems engineering — the same discipline behind checklists in aviation. See the [README](README.md) for the full design rationale.
