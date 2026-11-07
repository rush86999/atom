# TASK-WAIT-01 independent work without a premature final artifact

This packet records the second genuine defect found from the assignment
acceptance map: while a source-triggered information wait is open, an
independent authorized branch may run and retain its result, but the job must
not complete or release the requested final artifact. It also fixes the
duplicate artifact step that appeared when the answer arrived later.

- failure-first probe source basis: `784a2eb14` plus only the new test
- repair source: `c85788d66`
- preceding evidence: `task_wait_long_wait_budget_e1b91fa89/`

## Defect (failure first)

The public-route probe
`backend/tests/test_task_wait_independent_work.py::test_independent_work_does_not_release_a_premature_final_artifact`
starts an objective that both asks to reconcile a missing invoice and prepare
a quote. It establishes the missing-invoice question, then calls the ordinary
`/advance` route. The controlled model chooses the independent quote branch.

Before the repair, `baseline-probe.log` shows (exit 1):

- the quote applied (`105.00`) while the invoice question was still open;
- the requested `artifact.document` was nevertheless applied, and the job
  reached `completed`;
- after the later authorized invoice arrived, a second
  `requested-artifact-2` step was compiled and applied, duplicating the final
  deliverable.

Two product rules were therefore false in this representation:
"final artifacts remain blocked" and "waiting is not completed".

## Repair

- `AssignmentExecutor.execute` no longer turns an open unresolved prerequisite
  into `completed`. It also removes declared deliverable steps from readiness
  while an obligation is open; independent ready branches still run.
- `adopt_adaptation` now passes the durable open obligations from the task
  revision into the compiler context (the previous minimal context silently
  dropped them).
- `_requested_artifact_step` refuses to compile a whole-objective artifact
  while an open obligation exists, so only the post-answer compilation
  produces the single final deliverable.

No new table, task engine, daemon, model poll or authority was added. The
quote is retained with its original operation; the final artifact is produced
once, after the invoice reconciliation is verified.

## Verification

Executed source: `c85788d66` (tracked tree clean; only untracked worker
guidance files present and not part of the run). Project Python 3.14.7,
`TESTING=1`, fresh private scratch SQLite/data/Lance and an owned basetemp.

```
python -m pytest -p no:cacheprovider --basetemp=<fresh> \
  tests/test_task_wait_independent_work.py \
  tests/test_task_wait_source_continuation_regressions.py \
  tests/test_task_wait_process_recovery.py \
  tests/test_employee_work_requests.py \
  tests/test_employee_work_request_matrix.py \
  tests/test_employee_durable_wait_g5.py \
  tests/test_employee_evidence_change_g5.py \
  tests/test_employee_adaptation_contract.py \
  tests/test_assignment_routes.py \
  tests/test_assignment_executor.py \
  tests/test_boot_recovery_not_gated_by_scheduler.py \
  -q --tb=short
```

Result: **238 passed**, true exit code **0**, 131.98s. `final.log` is retained
unchanged. It includes the new probe, all source-continuation/recovery
regressions, the actual OS-process cases, compiler/work-request suites,
evidence-change and durable-wait suites, assignment routes/executor and boot
wiring.

The new probe asserts:

1. the missing-invoice question is open, no reconciliation and no applied
   artifact exist;
2. `/advance` applies the independent quote (`105.00`) and retains it, but the
   question stays open, status is not `completed`, and no final artifact is
   applied;
3. the authorized invoice arrives through the normal `/sources` route; the
   same task completes with one verified `270.00` reconciliation, the retained
   `105.00` quote and exactly one applied requested artifact;
4. no duplicate artifact step is created.

## Scope and remaining claim

Covered: assignment entrypoint representation 1 (open unresolved prerequisite),
useful independent work, no premature final artifact, no completion while
waiting, single post-answer artifact, and the existing restart/process/replay
controls rerun around the change.

Not claimed: model-created second pause on the same assignment (E1 in the
acceptance map), cross-run wait isolation (E2), public-route
revocation/scope-after-wait (E3), Generic/GenericAgent, workflow, provider/model
quality, UI/browser, PostgreSQL or multi-worker behavior.

Preserved unchanged: every prior TASK-WAIT packet, including the generation
repair at `223a286a4`, the long-wait packet at `e1b91fa89`, and historical
G5/episode70a evidence at its recorded scope.
