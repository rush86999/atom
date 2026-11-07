# TASK-WAIT-01 source-answer continuation

This packet records the repaired delivery for the failure-first checkpoint at
`docs/acceptance/evidence/task_wait_source_trigger_baseline_bc4970f97/`. The
original negative log and its checks are preserved unchanged.

Executed source: `6d08b1c4b` (clean detached worktree; runtime identity
`source_id=6d08b1c4baa9 revision=6d08b1c4baa9 dirty=False (0 modified, 0 untracked)`).
The source-only contract now passes, and the otherwise-identical explicit
`/advance` twin still passes. Both produce the real compiled/executed
`invoice.reconcile` receipt with value `140.25`; the route/model is never given
an expected total, formula or plan.

## What changed

`POST /api/assignments/{run_id}/sources` already resolved/read-authorized the
source and settled the targeted prerequisite question, but it did not hand the
fresh accepted evidence to the business-adaptation consumer. The explicit UI
button made a second `advanceAssignment` call, which is why the manual twin
passed.

The route now calls the SAME existing `_advance_employee_work` consumer and
`AssignmentExecutor` after a source settles a targeted obligation. A replayed
source delivery no longer returns early at `already_present`; it runs the same
idempotent executor and recovers when durable source acceptance exists but its
unconsumed evidence observation has not yet been adapted (interruption before
adaptation). No new task engine, table, daemon or route was added.

The redundant frontend `advanceAssignment` call was removed; the authenticated
source route owns that continuation. The frontend unit test now asserts the
duplicate call is absent (Jest was not executable in this sandbox because
`frontend-nextjs/node_modules` is absent; the assertion is committed for CI).

## Required boundaries exercised

- Source-only posive: settle the question, then the same task adapts and the
  real executor produces one verified `140.25` reconciliation and completes.
- Separate-advance twin: unchanged behavior and receipt.
- Wrong subject (`po_id` mismatch), partial invoice and unrelated source:
  question stays open, zero new adaptations, no reconciliation.
- Model retain after a relevant source: question settlement is not business
  success; no reconciliation, task not completed.
- Duplicate/replay after completion: no second step, no repeated adaptation,
  one applied reconciliation.
- Interruption after durable source acceptance and before adaptation: the
  first delivery resolves the question but the continuation is interrupted;
  a restart/replay through `already_present` recovers exactly once.
- Restart while waiting (order A) and accept-then-restart-then-replay (order B).
- Explicit `use_model=false`: no adaptation is started from the source answer.
- Cancellation and an explicit past absolute deadline stay terminal; a late
  source answer cannot resurrect or extend them.

## Test boundary and command

Project Python 3.14 (`/Users/rushiparikh/projects/atom/backend/venv314/bin/python`)
ran from the clean detached worktree:

```
python -m pytest \
  tests/test_task_wait_source_trigger_contract.py \
  tests/test_task_wait_source_continuation_regressions.py \
  tests/test_assignment_routes.py \
  -vv -rA --tb=long
```

with `TESTING=1`, a fresh scratch `DATABASE_URL`, `ATOM_DATA_DIR` and
`ATOM_LANCEDB_PATH`, and a newly owned pytest `--basetemp`. The full
stdout/stderr, including the runtime identity, is retained unchanged in
`final.log`; the true pytest exit code is recorded at its end.

Result: `74 passed` (`2` contract + `8` new regressions + `64` existing
assignment-route controls), exit code `0`.

Proposal transport and the authenticated-user dependency use the repository's
existing controlled fixtures. No live model, provider, cloud, credential,
account, send, spend, download, guest or deployment action occurred. This does
not qualify ordinary login, served-model quality, browser/UI execution,
multi-worker or PostgreSQL behavior.

## Scope

This proves automatic continuation for the source-answer `/sources` entrypoint
only. Broader generic/workflow/long-running-task entrypoints remain OPEN for
TASK-WAIT-01; this packet does not claim they are covered.
