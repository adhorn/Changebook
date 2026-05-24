# Feature breakdown

Derived from the operator experience spec. Each feature is small enough to implement and test in one session. Order follows dependencies.

## Feature 1: Align data model with spec

The current data model doesn't match the spec. Fix it first.

Changes:
- Change: drop `team_id`. `customer_ids` (array) becomes `customer_id` (single, required). `environment_ids` (array) becomes `environment_id` (single, required). Add `service_id` (required). Add `cloned_from` (optional FK to self).
- ChecklistItem: new unified model for all three phases. Fields: `change_id`, `phase` (pre_flight / execution / verification), `order`, `description`, `command`, `expected_outcome`, `rollback_action`, `is_hold_point`. Replaces the current Step model.
- Defence tags: predefined set. Stored as JSON array on the change. Validation against the allowed list.
- Drop old Step/StepCompletion models.

Acceptance criteria:
- A change has exactly one customer_id, one service_id, one environment_id
- Checklist items belong to a change and have a phase
- Defence tags are validated against the predefined list
- All existing tests updated or replaced to match

## Feature 2: Pre-flight questions

The structured pre-flight questions with five sections, one question per field.

Changes:
- Update preflight question definitions (5 sections, no compound questions)
- Pre-flight answers stored as JSONB on the change
- API to save/update pre-flight answers incrementally (draft saves)

Acceptance criteria:
- All 18 pre-flight questions are defined, one thought per question
- Answers can be saved incrementally (partial drafts)
- Answers round-trip correctly through the API

## Feature 3: Checklist CRUD (backend)

API for managing checklist items across all three phases.

Changes:
- Create checklist item for a given phase
- List checklist items by phase
- Reorder checklist items within a phase
- Update/delete checklist items (only in draft status)

Acceptance criteria:
- Items can be added to any of the three phases
- Items within a phase are ordered sequentially
- Items can be reordered
- Items cannot be modified once the change leaves draft status

## Feature 4: State machine (updated lifecycle)

Update the state machine to match the spec lifecycle.

States: draft → in_review → approved → executing → done → (aborted from any active state)

Changes:
- Completeness gate: cannot transition to in_review unless all three phases have at least one checklist item AND pre-flight answers are filled in
- 24h staleness warning on transition to executing
- Status "done" replaces "closed" and "verified" (simplification — verification is a phase, not a status)

Acceptance criteria:
- Cannot submit for review with empty phases
- Full lifecycle works: draft → in_review → approved → executing → done
- Abort works from any active state
- Staleness warning recorded in audit trail if pre-flight is older than 24h

## Feature 5: Review workflow

Reviewers are assigned to a change. All must approve.

Changes:
- Assign reviewers to a change (by name in v1, by user ID after SSO)
- Submit review: approve / request_changes / block, with comment
- All assigned reviewers must approve before transition to approved
- Any edit to a change after approval invalidates all reviews

Acceptance criteria:
- Reviewers can be assigned
- All must approve for the change to be approvable
- A single block prevents approval
- Editing a change resets all existing approvals
- Review decisions are in the audit trail

## Feature 6: Checklist execution

The core. Sequential read-do execution across all three phases.

Changes:
- ChecklistCompletion model: item_id, observed_result, status (completed / flagged / skipped_with_justification), completed_by, completed_at, hold_point_verified_by, hold_point_verified_at
- API: complete a checklist item (with observed result)
- Sequential unlock: can only complete the next uncompleted item
- Hold points: item is completed by operator, then must be verified by a different person before the next item unlocks
- Abort: can abort at any point during execution
- Transition to done when all items in all three phases are completed

Acceptance criteria:
- Items must be completed in order — cannot skip ahead
- Completing an item requires an observed_result (the read-back)
- Hold points require a second person to verify
- Cannot complete items out of sequence
- Change transitions to done when the last verification item is completed
- Abort is available at any point

## Feature 7: Duplicate flow

Clone a change record for a different customer/environment.

Changes:
- API: duplicate a change — copies checklist items, pre-flight answers
- Clears customer_id, service_id, environment_id (operator must re-select)
- Sets cloned_from to the source change ID
- New change starts in draft

Acceptance criteria:
- Duplicated change has all checklist items from the source
- Pre-flight answers are copied
- Customer, service, environment are cleared
- cloned_from references the source
- New change is in draft status

## Feature 8: Markdown export

Export a complete change record as markdown.

Changes:
- API endpoint: GET /changes/{id}/export returns markdown
- Export includes: change details, pre-flight answers, all three checklists with observed results, review decisions and comments, timestamps

Acceptance criteria:
- Export includes all phases and completions
- Export includes review history
- Export is valid markdown
- Timestamps are human-readable

## Feature 9: Change history and filtering

Browse and filter change history.

Changes:
- List API with filters: customer_id, service_id, environment_id, defence_tag, status, author, date range
- Frontend: filterable change list

Acceptance criteria:
- Each filter works independently
- Filters can be combined
- Results are paginated

## Feature 10: Frontend — three-phase change form

The create/edit UI with cognitively distinct phases.

Changes:
- Customer → Service cascading select
- Environment select
- Defence tags multi-select (predefined list)
- Five pre-flight question sections with framing sentences
- Three checklist builders (pre-flight checks, execution, verification) — visually distinct
- Submit for review button: disabled until all phases are complete

Acceptance criteria:
- Selecting a customer loads its services
- Each phase is visually distinct (different colours)
- Pre-flight questions are one per field, no compound questions
- Submit button only enabled when all phases have content

## Feature 11: Frontend — execution view

The read-do execution UI.

Changes:
- Sequential display: current item prominent, future items locked
- Copy-to-clipboard for commands
- Observed result input (the read-back)
- Confirm button
- Hold point indicator and verifier confirmation
- Continue/pause/abort controls
- Progress indicator across all three phases

Acceptance criteria:
- Only the current item is actionable
- Future items are visible but locked
- Copy button works for commands
- Hold points block until verified by second person
- Abort is always available

## Implementation order

1. Feature 1 — data model (everything depends on this)
2. Feature 2 — pre-flight questions
3. Feature 3 — checklist CRUD
4. Feature 4 — state machine
5. Feature 5 — review workflow
6. Feature 6 — checklist execution
7. Feature 7 — duplicate flow
8. Feature 8 — markdown export
9. Feature 9 — change history and filtering
10. Feature 10 — frontend form
11. Feature 11 — frontend execution view
