# Permissions

This document is the source of truth for who can call which mutating API endpoint in Changebook. Read-only endpoints (`GET ...`) are not listed — they are accessible to any authenticated user.

The roles used here are scoped to one change at a time:

- **Author** — the user who created the change. Determined by `change.author_name == current_user.name`.
- **Assigned reviewer** — a user listed as a reviewer on a specific change. Determined by `review.reviewer_name == current_user.name`.
- **Any authenticated user** — any user whose request carries valid auth headers.

The parametrized test in `backend/tests/test_permission_matrix.py` walks this table and asserts each cell. When a new endpoint is added, add a row here in the same PR — the test will surface it as missing coverage.

## Mutating endpoints

| Endpoint | Allowed role | Failure status if not allowed | Rationale |
|---|---|---|---|
| `POST /changes` | any authenticated | n/a | The caller becomes the author of a new change. |
| `POST /changes/{id}/duplicate` | any authenticated | n/a | Clones into a new change owned by the caller. Source is not mutated. |
| `POST /changes/{id}/save-as-template` | any authenticated | n/a | Creates a template owned by the caller. Source is not mutated. |
| `PATCH /changes/{id}` | author | 403 | Edits the change. Only the author edits their own change. |
| `POST /changes/{id}/transition` | author | 403 | Status changes (submit for review, mark done, abort) are driven by the author. |
| `POST /changes/{id}/checklist` | author | 403 | Add a checklist item to the plan. |
| `PUT /changes/{id}/checklist/reorder` | author | 403 | Reorder checklist items. |
| `PATCH /changes/{id}/checklist/{item_id}` | author | 403 | Edit a checklist item. |
| `DELETE /changes/{id}/checklist/{item_id}` | author | 403 | Delete a checklist item. |
| `POST /changes/{id}/checklist/{item_id}/complete` | author | 403 | The author is the operator. Recording observed results during execution is the author's act. |
| `POST /changes/{id}/checklist/{item_id}/hold-point-verify` | any authenticated | n/a | **Honor system — see note below.** |
| `POST /changes/{id}/checklist/execution-step` | author | 403 | Adding a step during execution is part of the operator's actions and stays with the author. |
| `POST /changes/{id}/reviewers` | author | 403 | The author assigns reviewers to their own change. |
| `POST /changes/{id}/reviewers/{review_id}/decision` | assigned reviewer | 403 | Only the user named as the reviewer can submit that review. The author cannot self-review (separately enforced with 422). |
| `POST /organisations/teams` | any authenticated | n/a | Org-level resources are shared in single-org deployments. |
| `POST /organisations/customers` | any authenticated | n/a | Same — single-org-shared. |
| `POST /organisations/customers/{id}/services` | any authenticated | n/a | Same — single-org-shared. |
| `POST /organisations/environments` | any authenticated | n/a | Same — single-org-shared. |
| `POST /templates` | any authenticated | n/a | Anyone can author a template. |
| `POST /templates/{id}/use` | any authenticated | n/a | Anyone can spin a new change from any template. |

## Note on hold-point verification

`POST /changes/{id}/checklist/{item_id}/hold-point-verify` is intentionally callable by any authenticated user. The verifier's name is supplied in the request body as plain text — not derived from authentication. This is a deliberate design choice:

- The two-person rule is a **cognitive forcing function**, not a technical control. It exists to ensure a moment of shared attention before the action runs.
- In practice the operator is at the keyboard and the verifier is physically beside them, reading the screen. The operator types the verifier's name. Requiring the verifier to log in separately would add friction without strengthening the underlying control.
- The actual integrity guard is enforced at completion time: `complete_item` rejects completions where `completed_by == verified_by` (a different person must complete than verified).

This is analogous to aviation CRM: the captain reads, the first officer confirms verbally, neither logs into a system to do so. The cognitive moment is what matters.

When real authentication and roles arrive (#39), this design choice should be revisited but is unlikely to change.
