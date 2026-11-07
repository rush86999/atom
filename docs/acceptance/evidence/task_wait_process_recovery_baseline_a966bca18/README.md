# TASK-WAIT-01 actual-process recovery baseline

This is the failure-first checkpoint for the successor of the frozen
`d874e1872` / `6d08b1c4b` packet. That packet proved source-triggered
continuation and an in-Python executor rebuild, but it did **not** prove an
actual OS process exit/relaunch or autonomous consumption of durable
already-accepted input. Its README's unqualified restart wording is corrected
by the evidence packet that follows; the historical log is preserved unchanged.

Executed source: `a966bca18` (`test(tasks): capture missing actual-process
recovery owner`), clean tracked worktree, Python 3.14.7,
`TESTING=1`, a fresh scratch SQLite/data/Lance root and a new owned pytest
basetemp. The child-process worker and test bytes are committed at this source.

## What the negative actually does

`backend/tests/test_task_wait_process_recovery.py` launches real OS child
processes. Each child builds the public assignment router, real
compiler/executor and the same scratch SQLite store; proposal transport and
authentication use the repository's existing controlled fixtures.

1. `start`: create the objective through `/api/assignments/from-objective`
   with PO and receiving sources. A genuine missing-invoice obligation is
   open; the child exits `0` and records its pid and the durable task.
2. `source-interrupt`: post the invoice through the same run's
   `/api/assignments/{run_id}/sources`. The route durably adds/reads the
   source and settles the targeted obligation, then the worker hard-exits
   (`os._exit(17)`) inside the adaptation consumer, before any business plan
   or result exists. The pre-exit checkpoint is written from the committed
   durable state and records: same run/objective/assignment, zero open
   questions, one applied invoice source with an operation id and source
   version, unconsumed evidence observations, zero reconciliations, and a
   non-completed status.
3. `startup-recover`: a third OS process runs only the existing
   `AssignmentExecutor.recover_ready_assignments()` owner. The verifier issues
   no second `/sources` POST, no `/advance`, no new objective and injects no
   plan/result. It asserts that the same task completes with exactly one
   verified `140.25` reconciliation, one adaptation of the durable accepted
   evidence, and preserved original receipts. A later duplicate source POST
   must be inert.

The separate positive control starts an objective, restarts while the invoice
is genuinely missing (zero adaptation calls), then delivers the invoice
through the public source route in the successor process; the same task must
complete.

## Actual negative

`1 failed, 1 passed`, true pytest exit code `1`.

- The missing-prerequisite restart control passes: the recovery owner does not
  model-poll an open obligation.
- The accepted-evidence recovery case fails at
  `assert recovered["adaptation_calls"] == 1`: the successor process makes
  **0** adaptation calls, applies **0** reconciliations and leaves the same
  task unfinished. The checkpoint proves the source acceptance/read/obligation
  settlement was already committed before the process exited.

That is the finite remaining gap. It must become green by wiring the accepted
evidence into the existing employee adaptation consumer through the existing
assignment lifecycle/recovery owner, with an explicit bounded claim and no new
polling daemon, table, task engine or authority.

## Boundary

Public assignment routes, real compiler/executor and scratch SQLite are real.
Proposal transport and the authenticated-user dependency use the repository's
existing controlled fixtures. No live app model/provider, network, credential,
account, send, spend, download, guest or deployment action occurred. This is not
ordinary-login, served-model, browser/UI, multi-worker or PostgreSQL
qualification. Frontend Jest remains not executable here (`node_modules`
absent); the prior frontend assertion is unchanged.
