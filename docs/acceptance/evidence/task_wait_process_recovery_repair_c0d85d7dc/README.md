# TASK-WAIT-01 actual process recovery repair

This packet repairs the failure retained at
`docs/acceptance/evidence/task_wait_process_recovery_baseline_a966bca18/` and
corrects the earlier packet's restart wording without rewriting its historical
log (`task_wait_source_continuation_6d08b1c4b/final.log` is unchanged).

Executed source: `c0d85d7dc` (`test(tasks): record actual child pids and
exits`), clean tracked worktree, Python 3.14.7, `TESTING=1`, a fresh private
scratch SQLite/data/Lance root and a new owned pytest basetemp. The tracked
tree contained the repair implementation from `1f4001dcb` plus the process-log
capture; all source bytes are hash-pinned in `MANIFEST.json`.

## What changed

- `AssignmentExecutor.recover_ready_assignments` — the existing ordinary
  re-entry owner — now detects durable applied evidence that no adaptation
  patch consumed. It CAS-claims one recovery inside the assignment plan
  (bounded TTL, one-shot per observation set) and hands the evidence to the
  SAME `_advance_employee_work` consumer used by `/sources` and `/advance`.
  No new table, daemon, task engine or authority.
- `core.assignment_recovery.recover_active_assignments_at_startup` — a thin
  startup adapter that enumerates active workspace/tenant scopes and invokes
  that existing owner. It is spawned from `main_api_app.lifespan` outside the
  scheduler gate.
- `_employee_llm_for_scope` — one scope-based consumer builder shared by the
  interactive route and restart recovery.

Eligibility is deliberately narrow: `employee_objective` provenance,
model-driven, non-terminal, non-expired, no cancelled authorization, no open
obligation, and at least one unconsumed applied evidence observation. A genuine
missing prerequisite therefore never triggers a model call; a retain/clarify
attempt is recorded once instead of being polled on every boot; a second
prerequisite keeps the task asleep; concurrent successors lose the claim.

## Actual-process distinction (explicit)

This packet proves **actual OS process** boundaries: separate child process
ids exit and relaunch against the same scratch SQLite store. It is not an
in-Python executor rebuild and not a manual source replay.

- Scenario A: child `start` creates the objective and stops at the genuine
  missing-invoice obligation; child `startup-recover` relaunches and makes
  **0** adaptation calls while the invoice is missing (no polling); child
  `source-complete` delivers the authorized invoice through the same run's
  public `/sources` route and the same task completes with one verified
  `140.25` reconciliation.
- Scenario B: child `source-interrupt` posts the invoice, the route durably
  adds/reads it and settles the obligation, then the child hard-exits with
  status **17** inside the adaptation consumer. The pre-exit checkpoint shows
  the committed boundary: same run/objective/assignment, zero open questions,
  one applied invoice source (`operation_id` and source version recorded),
  three unconsumed evidence observations, zero reconciliations and a
  non-completed status. Child `startup-recover` runs only
  `recover_active_assignments_at_startup` (no second `/sources` POST, no
  `/advance`, no new objective, no injected plan/result) and completes the
  same task with exactly one dependent `invoice.reconcile` operation and
  verified value `140.25`.
- Child `duplicate-source` re-delivers the same source after completion:
  `already_present`, **0** adaptation calls, still exactly one reconciliation.
- Original source read receipts (`source-1`, `source-2`), the accepted invoice
  (`source-3`), the task id, objective, assignment id and plan inputs are
  preserved across recovery. The invoice source is not re-read under a new
  operation.

Actual child pids and exit codes are in `processes.json`.

## Additional controls

- No-suitable/absence: the restart owner does not adapt or complete while the
  genuine missing-invoice obligation is open.
- Concurrent wake / second successor: a fresh bounded claim makes the second
  successor and a repeat boot inert; the first real successor performs the one
  dependent operation.
- Second prerequisite: an open second material obligation blocks recovery;
  resolving it lets the same successor recover the accepted source once.
- Expired absolute deadline and cancellation: neither is revived by restart
  recovery.
- Boot wiring: the structural control now requires
  `recover_active_assignments_at_startup` to be called outside every
  `ENABLE_SCHEDULER`/test gate, with a negative control that still detects a
  deliberately re-nested call.
- Existing source-route continuation, wrong/partial/unrelated source, model
  retain, `use_model=false`, cancellation and deadline regressions stay green.

## Test boundary and command

Project Python 3.14 ran from the clean tracked source:

```
python -m pytest \
  tests/test_task_wait_source_trigger_contract.py \
  tests/test_task_wait_source_continuation_regressions.py \
  tests/test_task_wait_process_recovery.py \
  tests/test_assignment_routes.py \
  tests/test_employee_durable_wait_g5.py \
  tests/test_assignment_executor.py \
  tests/test_boot_recovery_not_gated_by_scheduler.py \
  -vv -rA --tb=long
```

with `TESTING=1`, a fresh scratch `DATABASE_URL`, `ATOM_DATA_DIR` and
`ATOM_LANCEDB_PATH`, and a newly owned `--basetemp`. Full stdout/stderr and the
true pytest exit code are retained unchanged in `final.log`.

Result: `199 passed`, true exit code `0`.

Public assignment routes, real compiler/executor and scratch SQLite are real.
Proposal transport and the authenticated-user dependency use the repository's
existing controlled fixtures. No live app model/provider, network, credential,
account, send, spend, download, guest or deployment action occurred. Frontend
Jest remains not executable in this sandbox (`frontend-nextjs/node_modules`
absent); the prior frontend assertion is unchanged for CI.

## Scope

TASK-WAIT-01 remains open outside this proven entrypoint: this covers the
employee-objective `/sources` and restart-recovery seam only. Generic
`GenericAgent`, workflow/long-running-task and other assignment entrypoints
are not claimed. Ordinary login, browser/UI, served-model quality, multi-worker
and PostgreSQL behavior are not qualified.
