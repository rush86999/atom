# Generic source-answer repair — full accepted material and snapshot CAS

**Successor branch:** `codex/generic-source-answer-20261107`
**Executed source:** `960b8c5a225b637eb383df2678af42e139013260` (clean).
**Stack base:** `7d38d2ac9`; root probes `c58340b18`; previous checkpoint
`323e40507` (withheld, preserved).

## Root failures preserved

- `root-material-negative.log`: **1 failed**, actual exit 1. A replayed answer
  with the same source but changed text (`priority low`) resumed and fed the
  low value into the real consumer because replay compared only source hash.
- `root-snapshot-cas-negative.log`: **1 failed**, actual exit 1. A peer changed
  the HITL `context_snapshot.correlation_id` after source read but before the
  pending claim; the route overwrote the peer snapshot with its stale frozen
  copy and resumed, creating a task.
- The earlier first-probe exit 2 was its circular-import setup mistake, not a
  product failure; it is not counted here.

## Repairs

- Freeze a stable `accepted_answer_sha256` over **meaningful text + complete
  source material** (resource/version/content/receipt/label) in the durable HITL
  snapshot. Approved/replay and lost-CAS paths compare this digest; changed text
  or source refuses 409, exact replay remains idempotent.
- Pending claim now CASes on the exact observed authoritative snapshot:
  `id + pending status + action_type + context_snapshot == observed` (plus the
  existing current-actor/scope checks downstream). A peer snapshot/correlation
  change leaves the peer row intact, rolls back, and returns typed 409 with zero
  effects.
- Recovery consumes the frozen user_feedback/accepted text and frozen source;
  caller replacement cannot alter it.
- Existing shared CAS/binding mechanics only; no new revision store/engine/
  lifecycle. Current actor authority checks retained.

## Completed focused coverage

| Log | Selection | Actual |
|---|---|---:|
| `focused-backend-11.log` | root material replay and peer snapshot CAS probes; source-only valid; wrong correlation; duplicate exact + changed material; missing/foreign/stale/revoked source; dataset valid; offline actor-authority replay; existing text contracts | **11 passed**, exit 0 |
| `focused-ui-11.log` | all panel text journeys + authorized-source picker bound to exact wait | **11 passed**, exit 0 |

Dataset, Generic-specific authority failures, offline-authority refusal,
duplicate/changed material, text compatibility and UI selection are now locally
exercised. Backend/UI source is clean at `960b8c5a2`; only the existing model
transport and indexed/read fixtures are doubled.

## Remaining independent verification

- actual-process source accepted before/after restart (existing process controls
  cover neighboring text boundary; this source-specific process episode remains
  for root/CI);
- source-upload-alone route behavior (no hook exists; root should confirm);
- the single ordinary UI source-selection episode (root-owned).

TASK-WAIT-01/full app remain OPEN; no self-acceptance. Root owns PR/CI/review/
merge.
