# Generic accepted-answer recovery — fair startup drain

Executed source: `2bf38bc9d8a501d2dd13a3233a0d3ae0e51185cc`
(follows `0a2db1f2a` recovery fix on integrated base `d92260105`).

## Why this successor

`0a2db1f2a` woke accepted information waits after a crash, but the lifespan
called the 20-row batch helper once. A 21st genuinely eligible accepted wait
would therefore remain unconsumed until another restart. The batch API stays
legitimate; the production startup path now calls a keyset-paged **drain**
driver instead.

`drain_accepted_information_waits(batch_size=20)` walks the finite active-job
set one bounded page at a time (`AgentJob.id` keyset, yield between pages),
processing every accepted wait on each page until the set is exhausted. It
reports `pages`, `examined`, `complete` and the usual outcome counts. It is a
one-shot startup pass: no daemon, periodic model poll, new table or second
engine.

Fairness properties now covered:

- 21 ready accepted jobs are all dispatched in **one** startup pass; a second
  boot is inert;
- 20 completed approved waits plus a 21st ready waiting job: the 21st is
  selected and dispatched, historical rows stay auditable;
- 50 unanswered/pending active jobs ahead of one ready accepted fact do not
  consume the budget or block it (keyset paging reaches it);
- keyset paging avoids the offset-skip problem while earlier pages settle;
- cancellation, current authority, actor availability, old/replaced receipts,
  foreign scope and post-claim uncertainty still refuse exactly as in
  `0a2db1f2a`.

## Verification

`gate.log` / `gate-junit.xml`: **48 passed**, 0 failed, actual exit 0 (74.07s),
covering the wait/exact-event/namespace suites, 12 recovery selection/drain
units, the boot-placement structural controls (including the negative control),
six real-process cases using the drain driver, and HITL resume.

The earlier source checkpoint and its preserved first-failure artifacts remain
in `docs/acceptance/evidence/generic_information_wait_accepted_answer_recovery_0a2db1f2a/`.
The root negative `/private/tmp/root-generic-accepted-crash.log` is not
regenerated.

## Scope / not claimed

- Real-process API/helper behavior plus AST lifespan-wiring control; executing
  the whole `main_api_app` lifespan is not claimed.
- No live model/provider, network, credential, spend, send, deploy or live DB.
  Scratch SQLite/Lance only; committed child interpreter is
  `ATOM_TEST_PYTHON`/`sys.executable`.
- UI/browser, A2 assignment recovery, automatic external information-event
  mapping and whole-app TASK-WAIT-01 remain open. The app goal remains open.
