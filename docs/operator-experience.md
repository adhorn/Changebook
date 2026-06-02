# Operator experience spec

Status: draft — under discussion
Last updated: 2026-05-22

## Who is the operator

The operator is the person making the change. They know what they need to do. They may not have all the details yet — timing, exact commands, verification criteria — but they know a change is coming.

The tool does not tell the operator what to do. It makes them think before they act, keeps them on track during execution, and proves the work was done correctly afterward.

## The mental model: three phases

Every change has three cognitively distinct phases. They map to three different modes of thinking:

| Phase | Cognitive mode | Question it answers |
|---|---|---|
| **Pre-flight** | Planning, anticipation | "What could happen?" |
| **Execution** | Doing, attention | "What am I doing right now?" |
| **Verification** | Confirming, comparing | "Did it work?" |

These phases are visually and structurally separate in the UI. Different colours, different sections, different mental contexts. They are never mixed.

The operator fills all three phases in before submitting for review. They can work on them in any order and save incrementally. But all three must be complete before the change can be submitted.

### Why separate them

This is a cognitive forcing function. Mixing planning and doing leads to the operator thinking about execution while they should be thinking about failure modes. Mixing execution and verification leads to "I just did it, so it must be fine." Each phase requires the operator to shift their mental frame. The UI reinforces that shift.

Aviation parallel: pilots don't run pre-flight checks, fly the plane, and verify landing in one continuous stream. Each phase has its own checklist, its own mental posture, its own verification. The transitions between phases are explicit.

## The scope of a change record

**One change = one customer, one service, one environment.**

A change record is self-contained. It targets exactly one customer, one service within that customer, and one environment. The pre-flight answers are specific to that customer and service's context. The execution commands are specific to that environment's configuration.

If the same logical change needs to happen for multiple customers or across multiple environments (regions), the operator creates separate change records. The duplicate flow handles this: execute a change, clone it, adjust customer or environment details, go through the full cycle again. Each record has its own review, its own execution, its own verification, its own audit trail.

A change record has a `cloned_from` field so lineage is traceable — you can see that "these five changes are the same logical change applied across five customers."

## Phase 1: Pre-flight

The thinking phase. The operator answers structured questions that force them to consider the change from multiple perspectives — especially the customer's perspective.

### What the operator fills in

**Change details**
- Title
- Description
- Customer (single — who does this change affect?)
- Service (single — which service within this customer? e.g. "Portfolio Management")
- Environment (single — where is this change happening?)
- Author
- Defence tags (optional — what defence layers does this change touch?)

Team is deliberately absent. In v1 the author is a name field. When SSO lands, team is derived from the author's identity. No reason to ask the operator to select their own team — that's organisational bookkeeping, not cognitive work.

**Pre-flight questions** (cognitive forcing functions)

Each question asks one thing. One question, one answer. No compound questions.

The change:
- What is this change?
- What is the expected outcome?

What the customer experiences:
- Will the customer notice this change?
- How will they notice it?
- If this change fails mid-way, what is the customer in the middle of doing?
- What happens to their in-progress work if it fails?

Failure and recovery:
- What happens if this change fails?
- How do you roll back?
- How long does rollback take?
- What does the customer experience during rollback?
- What is the blast radius?

Timing and coordination:
- Is there a maintenance window?
- When is it?
- Is this the lowest-impact window for the customer, or the most convenient for the operator?
- Are there dependencies on other changes or teams?

Customer awareness and agreement:
- Is the customer aware this change is happening?
- Has the customer agreed to this change?
- Has a maintenance window been communicated to the customer?
- Who is the customer contact during this change?
- How will the customer be notified when the change is complete?

### Defence tags

Predefined set, operator picks from a list. No free-text. Keeps the taxonomy clean and queryable.

Default tags:
- monitoring
- alerting
- security
- access control
- DR
- backup
- networking
- database
- application

Tags are optional but low-friction — a simple multi-select. The value comes over time: "show me all changes to alerting config in the last 6 months" surfaces normalisation of deviance.

New tags can be added to the predefined list by admins. Operators cannot create ad-hoc tags.

### Design notes

**One question, one thought.** Compound questions ("What X? How Y?") let the operator answer the easier half and skip the harder one. Every question asks exactly one thing. If a topic has two dimensions, it gets two questions.

Each question section has a short framing sentence that sets the cognitive context:
- "What are you doing and what should happen?"
- "Think from the customer's perspective, not yours."
- "Assume this will go wrong. What then?"
- "Is this the right moment — for the customer, not just for you?"
- "Does the customer know?"

These framings come from Endsley's situation awareness model: push the operator through perception (what), comprehension (what it means for the customer), and projection (what happens next if it goes wrong).

## Phase 2: Execution checklist

The doing phase. An ordered list of discrete items. Each item is one command or one action.

### What each item contains

- **Description**: what to do, in plain language
- **Command/script**: the exact command to copy and paste (optional but encouraged)
- **Expected outcome**: what should happen when this command runs
- **Rollback action**: what to do if this step fails
- **Hold point flag**: if set, the step cannot be completed until an independent verifier authorizes it — the command is visible (the verifier needs to read it) but the copy button is locked until verification

### Execution model: read-do

Read-do is the only mode in v1. The operator reads the step, does it, confirms the result. The checklist leads. The operator follows.

Items are executed sequentially. One at a time. The operator:

1. Sees the current item — description, command, expected outcome
2. Copies the command to their system and executes it
3. Records what they observed (read-back — not just "done", but what happened)
4. Confirms the item is complete
5. Only then does the next item unlock

If the item is a hold point, execution pauses BEFORE the step can run. The command is visible — the verifier must be able to read it to do their job — but the copy button is locked and the operator cannot record completion. A second person reads the command, confirms it should be run, and verifies. Only then does copy unlock and the operator can complete the step. Completer must be a different person than the verifier (two-person rule).

If the observed result does not match the expected outcome, the operator has a clear choice: continue (with justification), pause (wait for guidance), or abort (trigger rollback).

### Why read-do

This is the forcing function against omission. Under pressure, operators skip steps, batch actions, stop reading. The sequential unlock prevents this. The read-back (recording observations) prevents "check the box without looking" — the operator must engage with the result.

Aviation parallel: READ-DO checklist. The pilot reads the step, does it, confirms the result. You cannot move on until the current step is confirmed. DO-VERIFY (do from memory, verify afterward) is a future optimisation for routine changes.

## Phase 3: Verification checklist

The proving phase. An ordered list of checks to confirm the change worked — from the system's perspective and the customer's perspective.

### What each item contains

Same structure as execution items:
- **Description**: what to check
- **Command/script**: the verification command (optional)
- **Expected outcome**: what the result should be
- **Hold point flag**: for checks that need independent verification

### Execution model

Same as Phase 2 — read-do. Sequential, one at a time, record observations, confirm.

### Default verification perspective

Verification must include the customer's perspective, not just the system's:
- Is the system functioning as expected?
- Can the customer do what they were doing before the change?
- Has anyone confirmed the customer's experience from their entry point — not just from the operator's?

## Review and approval

### When review happens

The operator submits for review when all three phases are complete. The submit button is disabled until all phases have content.

### Who reviews

Reviewers are assigned to a change. Assignment can be:
- **Manual**: the operator adds reviewers
- **Automatic**: rules based on change properties (customer, defence tags, change type) assign required reviewers
- **Escalation**: some properties (critical customers, certain tags) trigger additional reviewers (manager, VP, bar raiser)

### Review rules

- All assigned reviewers must approve. No partial approval.
- Reviewers see all three phases — the thinking, the plan, and the verification criteria.
- Reviewers can: approve, request changes (with comments), or block.
- Review comments are part of the audit trail.

### The integrity guarantee

**Any edit to the change after approval resets all approvals.** Every reviewer must re-review and re-approve.

This prevents "I got approval and then quietly changed the plan." It's a strong constraint by design. The operator knows: if you touch anything, everyone reviews again.

## The full lifecycle

```
1. DRAFT
   Operator creates the change, fills in the three phases incrementally.
   Can save and return. No time pressure.

2. SUBMITTED FOR REVIEW
   All three phases are complete. Reviewers are assigned.
   The change is read-only for the operator during review.
   If the operator needs to edit, the change goes back to draft.

3. APPROVED
   All reviewers have approved.
   The operator can begin execution.
   Pre-flight answers must be within 24h of execution start (staleness rule).

4. EXECUTING
   The operator works through all three checklists sequentially:
   pre-flight checks first, then execution steps, then verification.
   One item at a time. Sequential unlock. Read-back on each.
   Hold points require independent verification before the step can run.
   Can pause and resume. Can abort at any point.

5. DONE
   All three checklists are executed and confirmed.
   The change record is locked. Immutable audit trail.
```

### The 24h staleness rule

Pre-flight answers reflect the operator's understanding of the situation at the time they wrote them. If the change is approved on Monday but executed on Friday, the situation may have changed — different customers active, different load patterns, different risks.

Default: pre-flight must be completed or re-confirmed within 24h of execution start. This is a warning, not a hard block (the operator can acknowledge and proceed). The acknowledgement is recorded in the audit trail.

## Duplicate flow

When a change is complete (or in any state), the operator can duplicate it. This creates a new change in DRAFT with:
- All three checklists copied
- Pre-flight answers copied
- Customer and environment cleared (operator selects the new target)
- A `cloned_from` reference to the source change

This handles the common pattern: same logical change, different customer or different environment. The operator adjusts the customer-specific or environment-specific details and goes through the full cycle again.

## Markdown export

Every change record can be exported as a self-contained markdown file. The export includes the full lifecycle: change details, pre-flight answers, all three checklists with the operator's observed results, review decisions and comments, timestamps throughout.

The markdown file is the audit artefact. It can be stored in git, attached to an ITSM ticket, included in a regulatory submission, or fed into an LLM for analysis. Markdown because it's human-readable and machine-parseable.

The API also exposes the full change record as JSON for programmatic access.

## Change history and filtering

The operator can browse the history of all changes. Basic filtering:
- By customer
- By service
- By environment
- By defence tag
- By status (draft, in review, approved, executing, done, aborted)
- By author
- By date range

This serves two purposes:
1. **During incidents**: "what changed for this customer in the last 7 days?" is the first question an investigator asks.
2. **Over time**: filtering by defence tag surfaces normalisation of deviance — 12 small changes to alerting config over 6 months that each seemed fine but cumulatively broke something.

## What the operator never sees

**Organisation.** This is an invisible tenant boundary. Auto-created, auto-injected. The operator thinks about customers, teams, and environments — not organisational hierarchy. Organisation is infrastructure, not cognition.

## Data model implications

### Change
- title, description
- customer_id (single, required — who is affected)
- service_id (single, required — which service within this customer)
- environment_id (single, required — where is this happening)
- author_name (free text in v1, derived from SSO later)
- defence_tags (list of predefined strings, optional)
- preflight_answers (structured responses to the pre-flight questions)
- status (draft / in_review / approved / executing / done / aborted)
- cloned_from (optional — reference to source change)

No team_id. Team is derived from the author's identity when SSO is added.

### Customer
First-class entity. Has a name, description, and services. The operator selects the affected customer when creating a change, then selects the specific service within that customer. This two-step selection (customer then service) makes the operator think about exactly who and what is affected.

### Environment
First-class entity. Has a name, platform, description. Optionally linked to a customer (dedicated environments).

### Checklist item (shared structure across all three phases)
- order (sequential position)
- description (what to do / what to check)
- command (optional — the thing to copy-paste)
- expected_outcome (what should happen)
- rollback_action (what to do if it fails — execution and pre-flight phases)
- is_hold_point (boolean)
- hold_point_verified_by (set before completion, if hold point)
- hold_point_verified_at (set before completion, if hold point)
- phase (pre_flight / execution / verification)

### Checklist completion (recorded during execution)
- item_id
- observed_result (what the operator saw — the read-back)
- status (completed / flagged / skipped_with_justification)
- completed_by
- completed_at

### Review
- reviewer (who)
- decision (approved / changes_requested / blocked)
- comment
- reviewed_at
- invalidated_at (set if the change is edited post-approval)

## Decisions made

1. **Read-do only in v1.** The checklist leads, the operator follows. Do-verify is a future optimisation for routine changes.
2. **One change = one customer, one environment.** No arrays, no matrices. Duplicate flow handles repetition across customers/environments.
3. **Defence tags: predefined set, optional, multi-select.** No free-text. Admins can extend the list. Value compounds over time.
4. **No delayed verification in v1.** Verification happens immediately after execution.
5. **Routine changes / templates: deferred.** Build the full model first, earn the right to abbreviate.
