# Generic source-answer repair — full material, snapshot CAS, process restarts

**Successor branch:** `codex/generic-source-answer-20261107`
**Executed source:** `32bb1e8cc952efb673fb69b5db96f1a4917b4c14` (clean).
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
- Pending claim CASes on the exact observed authoritative snapshot:
  `id + pending status + action_type + context_snapshot == observed` (plus the
  existing current-actor/scope checks downstream). A peer snapshot/correlation
  change leaves the peer row intact, rolls back, and returns typed 409 with zero
  effects.
- Recovery consumes the frozen user_feedback/accepted source; caller replacement
  cannot alter it.
- Existing shared CAS/binding mechanics only; no new revision store/engine/
  lifecycle. Current actor authority checks retained.

## Clean focused coverage

| Log | Selection | Actual |
|---|---|---:|
| `focused-backend-20-clean.log` | root material replay and peer snapshot CAS probes; source-only valid; wrong correlation; duplicate exact + changed material; missing/foreign/stale/revoked source; dataset valid; offline actor-authority replay; text compatibility; **real-OS-process** source-answer-after-restart, accepted-source-crash-before-claim recovery, and upload-alone | **20 passed**, exit 0 |
| `focused-ui-11-clean.log` | all panel text journeys + authorized-source picker bound to exact wait | **11 passed**, exit 0 |

The real-process rows run separate interpreters against one scratch SQLite/Lance
root. A worker serves the real `api.agent_routes` and document-ingestion routers,
real document reader, registry, durable rows and oracle; only
`LLMService.generate_structured` is scripted and the indexed source text is a
controlled fixture.

Covered orders and guards:

- restart while waiting, then answer with the authorized source on the same
  job/execution;
- accept/read/commit the source, hard-exit before claim, then let the bounded
  startup join consume the frozen answer exactly once with no replay POST;
- exact source replay is idempotent; changed text under the same source is 409
  with zero second effect;
- a normal upload alone leaves the wait pending, creates no task and does not
  wake on a startup recovery pass;
- public job reads expose no result before the answer, and only verified action
  results after continuation.

## Remaining independent verification

- The single ordinary UI source-selection episode remains root-owned. Backend
  API/source contracts are complete here; TASK-WAIT-01/full app remain OPEN and
  this packet is not self-acceptance. Root owns PR/CI/review/merge.

No live provider/model/account/credential/send/spend/install/deploy occurred.
