# Generic accepted-answer recovery after a crash

Executed source: `0a2db1f2af142273c59f29e754c12ae67b13b73a`
(integrated base `d92260105`, built on the process-test checkpoint
`e1ffc9743`).

## Defect

The job-answer route durably commits `HITLAction.status=approved` and
`user_feedback` **before** the resume consumer claims the job. If the process
dies in that gap, the accepted answer survives but the same job and execution
stay `waiting` forever: startup only failed `RUNNING` executions and never woke
an approved wait. The root negative (`/private/tmp/root-generic-accepted-crash.log`,
`-spec.json`, `-exit.json`) is preserved unchanged and is not regenerated here.

## Repair

A bounded one-shot startup join (`core.information_wait.
recover_accepted_information_waits`) now hands only an exact approved wait back
to the existing resume consumer:

- **No history starvation.** Candidates are driven from jobs that still own a
  run slot (`waiting`/active), then matched to approved information waits. The
  unbounded approved-HITL history is never used as the limit window, so a
  completed backlog cannot hide the newest accepted wait. The real-process
  twin seeds 20 completed jobs/executions/waits and proves the 21st waiting job
  still dispatches once without deleting history.
- **Server-owned authority only.** Identity and material (`job`, `execution`,
  `agent`, `workspace`, `tenant`, `correlation`) come from the server-written
  `context_snapshot`; there is no fallback to action params or partial rows.
  The job's current wait receipt must name the same action, the execution and
  agent must match, and the original actor must still be active. Missing scope,
  foreign scope, old waits, unapproved/rejected/expired/cancelled waits, an
  unavailable actor and a replaced wait receipt are never dispatched.
- **Truthful concurrency/crash handling.** The winning claim records
  `claim_owner` (pid/token/host/OS-start). A concurrent startup sees a live
  owner and leaves it alone; a verified-dead claim is marked
  `failed/uncertain` with `requires_reconciliation` and is never re-dispatched;
  unknown ownership is reported and left alone. The execution is CAS-updated
  together with the job, so stale cleanup cannot overwrite a peer execution
  winner.
- **Actual startup join.** `main_api_app.lifespan` starts the pass outside the
  scheduler gate. The existing structural boot test now includes this call and
  its negative control; no whole-app import/boot is claimed.

## Verification

`gate.log` / `gate-junit.xml`: **46 passed**, 0 failed, actual exit 0 (73.11s),
covering the wait/exact-event/resume-namespace suites, the recovery units, the
boot-placement structural controls, six real-process cases, and HITL resume.

Real-process twins in the gate:

1. accepted answer, crash before claim -> fresh process resumes the **same**
   job/execution exactly once through a real `tasks.create` (oracle-verified
   row);
2. two successors race the same accepted wait -> exactly one resumes;
3. 20 completed approved-wait rows + one ready 21st job -> the 21st is
   selected and dispatched; the 20 historical rows stay approved/auditable;
4. crash after the job claim -> reported `failed/uncertain` with
   `requires_reconciliation`, zero tasks and no model continuation;
5. a second restart after success is inert (no second task/model call).

The first concurrency attempt (kept as `concurrency-race-before-fix.log`)
exposed a real race: a successor mistook a peer's active claim for a dead claim
and marked it uncertain (`uncertain==1`). Recording the claim owner fixed it;
`concurrency-after-fix-run1.log` and the final gate are the re-checks.

## Scope / not claimed

- The recovery helper and its lifespan wiring are verified behaviorally and
  structurally; executing the entire `main_api_app` lifespan is not claimed.
- No live model/provider, network, credential, spend, send, deploy or live DB.
  Scratch SQLite/Lance only; the committed child interpreter is
  `ATOM_TEST_PYTHON` or `sys.executable`.
- Assignment recovery (A2), ordinary UI/browser flow, general model judgment,
  automatic external information-event mapping and whole-app TASK-WAIT-01 stay
  outside this checkpoint. The app goal remains open.
