# TASK-WAIT-01 assignment entrypoint acceptance map (2026-11-07)

Scope: the employee-objective assignment entrypoint
(`POST /api/assignments/from-objective`, `/sources`, `/advance`,
`/responses/{correlation}`, and the startup recovery owner). This map inspects
the real assertion scope of existing evidence; it does not treat a test name
as acceptance.

Source: `e1b91fa89`, on top of the generation-recovery packets at `223a286a4`
and `f55f83668`. All evidence below is controlled-transport, scratch
SQLite/data/Lance; no live model/provider/spend/account/send was used.

## Two wait representations (do not conflate them)

1. **Open unresolved prerequisite** — the ordinary source-triggered missing
   fact (for example, the invoice file is absent). The assignment is durably
   `blocked`; an actionable question names the missing fact and subject. The
   authorized source event settles the matching question and continues the
   same task.
2. **Compiled `assignment.wait` step** — the model explicitly chooses an
   `await_evidence` wait with a signed correlation id, typed subject and
   expected answer type. A later `/responses/{correlation}` or matching source
   resumes it.

Historical G5 evidence at `70a74cd02b5` / `4fd8951cc` remains accepted only at
its recorded scope; it exercised representation 2. It is not reused as proof
for representation 1, and this map does not replay it.

## Requirement-by-requirement map

| Required observation | Real evidence and assertion scope | Status |
|---|---|---|
| Missing prerequisite: durable wait, targeted question, retained useful results, zero dependent effect/final artifact | Public `/from-objective` source-trigger contract reaches an open unresolved question, applies only the two authorized reads and has no invoice reconciliation (`test_task_wait_source_trigger_contract.py`, both `separate_advance` values). Real OS-child start is the same negative at process scope (`test_task_wait_process_recovery.py`, restart-while-missing). The compiled-wait representation asserts fact/subject/typed binding and that the requested document is absent until reconciliation (`test_employee_durable_wait_g5.py`). | Covered across both wait representations |
| Relevant input triggers continuation: the event itself wakes the same task/wait; no second objective, manual advance or harness replay | `/sources` settles the matching question and continues through the existing consumer; a separate `/advance` is not needed (`test_task_wait_source_trigger_contract.py`). Actual OS-process accept-then-exit-then-startup-recovery completes the same run without a second `/sources`, `/advance`, objective or injected plan (process packet). The compiled wait resumes through `/responses/{correlation}` (`test_employee_durable_wait_g5.py`). | Covered |
| Restart: task/wait/subject/question and prior receipts survive; no repeated model poll | Real OS child processes on one scratch store preserve run, objective, assignment, source operation ids and versions; a boot while genuinely missing makes 0 adaptation calls (`test_task_wait_process_recovery.py`). The second-crash case starts before lease expiry, makes 0 adaptation calls and wakes once at the bounded lease. | Covered |
| Long wait: no active execution-allowance burn or hot model polling | Compiled `assignment.wait` time is excluded from the wall budget and overlapping waits are unioned across restart (`test_assignment_executor.py`). The source-triggered unresolved-prerequisite wait was **not** covered: a controlled two-hour wait under a 900-second active budget failed the authorized read with `assignment_budget_exhausted`. Repaired at `e1b91fa89`; the public-route probe now records the idle interval and completes with one verified `140.25` reconciliation. Evidence: `docs/acceptance/evidence/task_wait_long_wait_budget_e1b91fa89/`. | Repaired here (representation 1); controlled clock, not soak |
| Explicit absolute deadline: still refused, not silently extended | A past `budget.deadline` blocks the assignment; source arrival and restart recovery do not revive it (`test_task_wait_source_continuation_regressions.py`, deadline tests). | Covered |
| Wrong subject/relevance: unrelated, partial or wrong-subject input cannot settle the question or manufacture a result | Public `/sources` leaves the genuine question open for wrong PO, partial invoice and unrelated notes; no adaptation runs and replay is inert (`test_task_wait_source_continuation_regressions.py`). Wrong correlation id/party/answer type stays waiting (`test_employee_durable_wait_g5.py`). | Covered |
| Scope/version/revocation negatives | Resource recheck assertions cover wrong workspace, revoked grant, expired token, stale/short version and revocation between start and resumed read (`test_assignment_resource_boundary.py`). Changed source values reopen only the dependent branch and retain unrelated receipts (`test_employee_evidence_change_g5.py`). These are executor/resource-boundary assertions, not a single public `/sources` campaign. | Covered at resource/executor boundary; public-route twin remains E3 |
| Duplicate/concurrent delivery: identity preserved, one effect/artifact | Duplicate `/sources` after completion is `already_present`, 0 adaptations and still one reconciliation; a real process duplicate is inert. Concurrent successors (in-process and actual process) produce exactly one adaptation and one reconciliation; the lease wake rotates the claim token. Duplicate `/responses` does not repeat reconciliation. | Covered |
| Cancelled late input: no resurrection | Cancelled assignment refuses late `/sources` and late `/responses`; restart does not revive cancelled work (`test_task_wait_source_continuation_regressions.py`, `test_employee_durable_wait_g5.py`). | Covered |
| Changed source before consumption: revalidate; stale receipts cannot certify the new result | A real parquet value change invalidates only the dependent quote/artifact; the artifact revision and content change while the unrelated accepted read keeps its operation id (`test_employee_evidence_change_g5.py`). Stale/revoked resource versions are rechecked before the resumed read (`test_assignment_resource_boundary.py`). | Covered at assignment/executor boundary |
| Repeated pauses and honest completion: a second prerequisite can pause the same task again; later valid input resumes remaining work and retains unrelated receipts | A second open material prerequisite blocks recovery until resolved, then one reconciliation completes and prior accepted reads are retained (`test_task_wait_source_continuation_regressions.py`). Model `retain` after relevant input does not fake completion; irrelevant evidence never completes. The current second-prerequisite twin **injects** the second obligation through the lifecycle; it does not prove the model/consumer creates a second pause after the first answer resumes. | Partially covered; E1 is the missing executable case |
| Useful independent work and no premature artifact | Compiled-wait evidence: quote work completes while the receiving wait stays open, ready work is visible, and a requested document is not rendered before verified reconciliation (`test_employee_durable_wait_g5.py`). Representation 1 has no independent-branch twin; the new long-wait repair deliberately keeps the existing "ready branch runs first and closes idle" boundary but does not add a scenario. | Covered for representation 2; representation 1 remains E4 |
| Final UI/durable task/outcome agree; evidence arrival alone is not completion | The route returns the post-continuation status; completion requires the verified employee-result and artifact criteria. Model retain, wrong/partial/unrelated input and evidence arrival without a verified result stay non-completed. UI rendering itself is not executed here (frontend node_modules absent). | Backend/durable covered; UI execution not claimed |

## Defect found and fixed in this pass

The long-wait row was genuinely unproven and also defective. The failure-first
probe asserts the durable idle interval before delivering the invoice; it
failed at `KeyError: 'idle_open'` at the pre-fix source, and the same controlled
two-hour clock then produced `assignment_budget_exhausted` on the authorized
read with zero reconciliations. The repair is limited to the existing executor
idle ledger plus recording the question through that executor boundary; see
`docs/acceptance/evidence/task_wait_long_wait_budget_e1b91fa89/`.

## Remaining evidence map (no speculative repair)

These are executable next cases, not prod changes. They are ordered by what
would make the owner requirement more true.

- **E1 — model-created second pause on the same assignment.** Extend the
  public-route source probe so the first invoice answer resumes, the next
  adaptation returns a *new* targeted prerequisite (for example approval), and
  a second authorized event settles it. Assert two distinct open question ids,
  two source/response generations, retained first-result receipts, exactly one
  final dependent effect/artifact and no manual `/advance`. This is the only
  clearly unproven clause in the repeated-pauses row.
- **E2 — cross-run wait isolation.** Two assignments in the same workspace
  wait on different subjects; deliver a source that matches only run A. Assert
  run A settles/continues, run B keeps its own question, model call count and
  status, and neither run's operation ids move. This would make the
  "multiple waits/tasks settle only their relevant prerequisites" sentence
  executable beyond the current same-run checks.
- **E3 — public-route revocation/scope after the wait.** Start from a
  connected/resource binding, revoke the grant while waiting, then deliver the
  authorized-looking source through `/sources`. Assert the resource recheck
  produces a typed `source_access_revoked` wait, no adaptation/effect and no
  completion. Existing boundary tests cover the recheck itself; this case
  covers the automatic-continuation caller.
- **E4 — independent branch on representation 1.** Start a missing-invoice
  objective that also has an independently ready authorized calculation;
  assert that branch applies while the invoice question stays open, no
  requested artifact is emitted, and the later invoice event completes the
  remaining work with the independent receipt retained.

## Claim boundary

This map is for the assignment entrypoint only. Generic/GenericAgent,
workflow/long-running-task and other TASK-WAIT-01 entrypoints remain OPEN.
The long-wait test is a controlled-clock proof, not production soak. Ordinary
login, served-model quality, browser/UI execution, PostgreSQL and multi-worker
behavior are not qualified. Historical G5/episode70a evidence and every prior
negative packet stay at their original sources and are not rewritten here.
