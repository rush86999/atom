# TASK-WAIT-01 prolonged information wait budget repair

This packet records a genuine unproven row in the assignment entrypoint:
a source-triggered missing-fact wait must not consume the assignment's active
wall budget. It is bound to source `e1b91fa89` (runtime fix), reached from the
generation-repair evidence packet at `223a286a4` / `f55f83668`.

## Defect (failure first)

The failure-first public-route probe is
`backend/tests/test_task_wait_source_continuation_regressions.py::test_prolonged_information_wait_does_not_consume_active_wall_budget`.
At the pre-fix source (`f55f83668` plus only the probe) it fails at:

```
AssertionError/KeyError: 'idle_open'
the information wait must be recorded as an idle interval
```

`baseline-probe.log` is the retained unchanged run: 1 failed, exit 1.

Root cause found from the durable budget, not from the test name:

- The source-triggered missing-invoice wait is represented by an open
  unresolved prerequisite plus a `blocked` assignment state. It is **not** an
  `assignment.wait` step.
- `AssignmentExecutor.execute` only opened the assignment-level idle interval
  when `_waiting_steps(assignment)` was non-empty. A real missing-fact
  obligation therefore had no idle interval and kept charging wall time.
- With a 900-second active wall budget and a controlled two-hour wait, the
  authorized invoice read was refused with
  `assignment_budget_exhausted`; no reconciliation ran. This is the same task
  failing a required TASK-WAIT-01 long-wait behavior, not a cosmetic status.

## Repair

- `AssignmentExecutor.execute` now treats an open information obligation as a
  wait at the existing no-ready-work boundary: it opens the same
  assignment-level idle ledger used by compiled `assignment.wait` steps. A
  ready independent branch still wins and closes the idle interval first.
- `_record_information_wait` records the durable question and re-enters that
  same executor boundary, so the idle interval starts when the question is
  recorded (not only when an answer arrives). It adds no model call, task,
  engine, daemon or authority.
- Assignment status semantics are unchanged (`blocked` for the unresolved-
  prerequisite representation); only the budget clock is corrected.

No live authority, provider, credential, send, spend or deployment action was
used.

## Verification

Executed source: `e1b91fa89` (tracked tree clean; only untracked worker
guidance files were present and are not part of the run). Project Python
3.14.7, `TESTING=1`, fresh private scratch SQLite/data/Lance roots and a new
owned basetemp.

```
python -m pytest -p no:cacheprovider --basetemp=<fresh> \
  tests/test_task_wait_process_recovery.py \
  tests/test_task_wait_source_continuation_regressions.py -q --tb=short
```

Result: **21 passed**, true exit code **0**, 59.43s. `final.log` is retained
unchanged. It includes the three actual OS-process recovery cases (including
the second-crash lease wake) and the new controlled-clock long-wait probe.

Additional targeted regression run on the same source bytes: 206 passed in
96.52s (`related-targeted.log`) covering `test_assignment_routes`,
`test_assignment_executor`,
`test_employee_durable_wait_g5`, `test_employee_evidence_change_g5`,
`test_employee_prerequisite_eligibility`, `test_employee_wait_choice` and the
boot-recovery wiring controls.

The new probe:

1. starts the objective through the public `/api/assignments/from-objective`
   route with a 900-second active wall budget and no invoice;
2. asserts the targeted question is open, no reconciliation exists and the
   durable idle interval is recorded;
3. advances a controlled clock by two hours around the normal public
   `/sources` delivery (not a soak, not an invented answer);
4. asserts the same task completes with exactly one verified `140.25`
   reconciliation, one additional adaptation, an idle interval ledger entry
   and active elapsed time below 60 seconds.

## Scope and remaining claim

Covered: employee-objective `/sources` + restart-recovery seam, both wait
representations (compiled `assignment.wait` and open unresolved prerequisite),
long-wait budget accounting, real process restart and second-crash lease wake.

Not claimed: Generic/GenericAgent, workflow/long-running-task, other assignment
entrypoints, provider/model quality, ordinary login/browser/UI, PostgreSQL or
multi-worker behavior. The controlled clock is not production soak evidence.

Preserved unchanged: all prior TASK-WAIT packets, including
`task_wait_recovery_generation_repair_223a286a4`,
`task_wait_process_recovery_repair_e9e43ea60`,
`task_wait_process_recovery_baseline_a966bca18`,
`task_wait_source_continuation_6d08b1c4b` and
`task_wait_source_trigger_baseline_bc4970f97`.
