# Cancellation consistency repair — 2026-11-01

A focused product repair, separate from the campaign sources. It closes the
defect where a cancelled assignment stayed publicly "waiting for input" and a
late correlated reply could still match and wake it.

## Source identity

| Item | Value |
|---|---|
| Repair commit | `f5d2e085a` (cherry-picked from worktree commit `4efabd2aa`) |
| Backend tree | `d37da0be5943` |
| Frontend tree | `c921cb82e784` (unchanged) |
| Development | isolated worktree `/private/…/cancel-repair` at `414d8add3` |
| C2 closure source | `414d8add3` / backend tree `715969f01d23` — **not** this repair |

C2's wait/resume path does not exercise cancellation, so it stays pinned to its
original source through closure. Campaign A and the recovery controls ran on
the pre-repair product tree `715969f01d23`; this repair is orthogonal to their
paths.

## Root cause (traced, not guessed)

Both the Assignments panel and the public API call the same route:

`cancelAssignment` → `POST /api/assignments/{run_id}/cancel` →
`AssignmentExecutor.cancel`.

That method called `TaskLifecycle.apply_transition("cancel")` and
`mutate_assignment`, which update the assignment/task ledger under
`GoalRun.parameters["task_lifecycle"]` — but they never updated the GoalRun
row's top-level `status`/`waiting_on`. Separately,
`GoalRunService.transition("cancelled")` changed `status` but left
`waiting_on` intact. Finally, `record_external_response` matched the cancelled
step's **historical** `waiting.correlation_id` and woke the run (visible in the
recovery run's decision log as `external response matched … wake`).

So the assignment was not lost: it was cancelled, while the run projection and
the response matcher still treated the historical wait as active.

## Changes

1. **`GoalRunService.transition`** clears `waiting_on` for terminal statuses
   (`achieved`, `failed`, `cancelled`). The assignment step record, its
   correlation id, and the decision log remain as history; only the live run
   projection is cleared.
2. **`AssignmentExecutor.cancel`** projects `cancelled` onto the GoalRun
   immediately via the existing `_set_run_status`, and is idempotent: a second
   cancel returns the status without a second transition, preserving the first
   cancellation evidence.
3. **`record_external_response`** refuses any response for terminal work
   **before** matching a wait. It appends an `external_response_refused`
   decision (correlation id + rationale), returns `status="terminal"`, and the
   public route maps that to **409**. It does not wake, resume, or dispatch.
4. Historical waits are preserved on the cancelled step (`waiting` dict with
   its correlation/party/state); the top-level active wait is cleared.

No statuses were rewritten broadly, no history was deleted, and no new
subsystem was added.

## Public-API controls

Both use the real `api.assignment_routes` router, a scratch SQLite database,
and a real `AssignmentExecutor`/`TaskLifecycle`/`GoalRunService`:

### Correlated-response wait
- execute → `waiting`, GoalRun `waiting` with `waiting_on`
- `POST /cancel` → 200, assignment `cancelled`
- GoalRun `cancelled`, `waiting_on = null` in a **fresh SQLAlchemy session**
- `GET /api/assignments/{run_id}` → `cancelled`
- historical step still carries `correlation_id = corr-cancel-route`
- late `POST /responses/corr-cancel-route` → **409**, message names `cancelled`
- repeated `POST /cancel` → 200, one cancellation rationale, one
  `external_response_refused`
- `POST /resume` → no effect; `find_active_task` returns nothing;
  `list_runs(include_terminal=False)` excludes it; outbox empty

### Mapping wait
- execute → `waiting` on a mapping gap (`question_id`, mapping proposal)
- `POST /cancel` → 200; GoalRun `cancelled`/`waiting_on null` (fresh session)
- `POST /gaps/{question_id}/resolve` → **409** `The assignment is cancelled; a
  gap cannot revive it`
- late correlated reply → **409**; outbox empty

## Focused results

| Suite | Result |
|---|---|
| `test_assignment_routes.py` + `test_assignment_executor.py` | **85 passed** |
| `test_goal_run_service.py` + events + routes + watchdog sweep | **44 passed** |
| Combined repair run | **129 passed** |
| New public-API cancellation tests | **2 passed** |

Logs: `focused-tests.txt`, `public-api-cancel-tests.txt`.

## Note on the earlier recovery evidence

Before the repair, recovery run `afe9748b-b813-47f8-bc9a-3b8bb618874c` showed
the inconsistency: cancellation through the UI persisted and no effect was
dispatched, but the late reply still matched the historical wait and produced a
`wake` before the terminal projection. After the repair the same shape is
refused before matching. The campaign-A 404 remains a **correlation-mismatch**
case (a mapping-gap run that never had the email correlation); it is not the
cancellation proof.
