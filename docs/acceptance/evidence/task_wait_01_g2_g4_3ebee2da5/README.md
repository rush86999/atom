# TASK-WAIT-01 continuation — G2/G4/G1 plus G3 trace

**Executed source:** `3ebee2da55f052b688d1ccb9047ff8a7277b0482`
(clean; parent `552aa1378`, which merged current main `36fa4ce39`).
**Main at start:** `36fa4ce39dd19a6b53b662699e5ceebede129df1` (browser PR744
merged; runtime unchanged).
**Status:** TASK-WAIT-01 remains OPEN at framework/whole-app scope. The 143
claim denominator and historical scores are unchanged.

This checkpoint continues the root-accepted reconciliation packet on the same
isolated branch. It makes no shared radio/MEM/fulfillment edits, no browser or
model replay, and no live provider/account/credential/send/spend/install/
deploy action. G2 is the only product-runtime fix in this checkpoint; G4 and
G1 are test-only; G3 is a trace/proposal for root review.

## Root clarifications applied

- **G5:** the per-file Git blob proof was independently accepted; the health
  badge alone was never authority. The badge caveat is preserved, but the
  browser packet is not called an unresolved full-goal blocker and is not
  replayed merely for a successor commit.
- **G6:** one ordinary UI journey plus API/process negative and two-event-order
  coverage meets the written browser boundary. There is no requirement that
  every case occur in one browser campaign. The limits stay visible.

## G2 — changed source after acceptance (reproduced and fixed)

`backend/tests/test_task_wait_source_version_after_acceptance.py` starts a
normal assignment with a purchase order, accepts/reads the invoice while the
receiving fact is still missing, then changes the invoice file from the
accepted `130.00` version to a `210.00` version before dependent consumption.

- **Before fix:** actual `1 failed`; the assignment reached `completed` with an
  `invoice.reconcile` result of `130.00` from the old accepted bytes.
  Failure log: `g2-failure-before-fix.log`.
- **Fix:** `backend/core/assignment_executor.py` now detects an applied local
  `document.read`/`workbook.read`/`document.text` source whose current file
  hash differs from the accepted `sha256`/`source_version`. It calls the
  existing `invalidate_step` path, which preserves prior results for audit,
  refreshes the local source/version binding and reopens only that source and
  its descendants. The same execution then re-reads the current version before
  dependent work; no new store, router, engine or budget was added. Connected
  sources retain their existing resolution/version checks.
- **After fix:** the same test passes; completion uses `210.00`, and no stale
  `130.00` result or artifact is certified. The clean affected selection is
  `30 passed`, exit 0.

## G4 — symmetric Generic two-job/two-wait isolation (test-only)

`backend/tests/test_generic_information_two_job_isolation.py` starts two real
Generic jobs in the same workspace through the public run route. Both reach
distinct durable waits; answering A must leave B waiting with its exact
correlation, no B model call and no B task. A stale A correlation delivered to
B returns `409` and changes nothing. Answering B then completes B. Durable
assertions: two information wait rows, both approved; two jobs/executions
success; exactly two `BoardTask` rows, one `Alpha` and one `Beta`; each job's
effect is verified by the default Oracle. The real Generic consumer/routes/
lifecycle/scratch SQLite run; only model transport is doubled.

This is a new contract test; no runtime defect was reproduced, so no G4 runtime
change was made.

## G1 — Generic budget/deadline trace (no new engine)

`G1_GENERIC_BUDGET_TRACE.md` records the actual contract:

- `AgentRunRequest` has only `agent_id` and `parameters`.
- `AgentJob` has no wall-budget, deadline or expiry column.
- `AgentExecution` has no wall-budget, deadline or expiry column.
- `GenericAgent.execute` has an active-run `timeout_seconds` and `max_steps`,
  plus the existing spend-budget gate; these are not a persisted wait budget.
- The durable information wait is an `HITLAction`; the run returns and the
  wait is not actively executing. `hitl_timeout` is an in-run approval poll,
  not an information-wait absolute deadline.

There is therefore no Generic wall-budget/absolute-deadline field to enforce
or extend. `test_generic_information_idle_contract.py` advances a controlled
clock by two hours, performs authorized job reads, and proves no additional
model call and an unchanged wait receipt. Existing actual-process tests cover
restart. The assignment wall/idle/absolute-deadline contract is **not** claimed
as Generic. No budget engine or owner API was added.

## G3 — source-answer trace (proposal only; root reviews first)

`G3_SOURCE_ANSWER_TRACE.md` traces the existing mechanisms:

- Generic answer body is currently `answer` + required server-owned
  `correlation_id`; the route checks job, wait, actor, workspace/tenant and
  correlation, then commits `HITLAction.user_feedback` and resumes the same
  job.
- Assignment source add accepts a source reference and resolves it through
  `resolve_assignment_source`, which supports document identity + current
  `source_content_hash`, dataset/source/external_id, workspace scoping and
  version refusal. Public callers cannot supply filesystem paths.
- The durable wait snapshot already carries job/execution/agent/workspace/
  tenant/actor/subject/correlation.

Proposal: add an **optional authorized source reference** to the Generic
answer path (document id + version, or existing dataset/source identity; no
path), require the exact wait correlation, resolve the current version through
the existing `resolve_assignment_source` and document/extraction reader,
reject foreign/stale versions, and persist the binding in the existing HITL
snapshot so the same job resumes with source evidence. No filename matching,
no global-upload settlement and no new store. Implementation is intentionally
not included here; root reviews the trace before broad UI work.

## Verification and evidence

- Clean executed source: `3ebee2da55f0`, `dirty=False` (0 modified/untracked).
- `affected-clean.log`: **30 passed**, actual exit 0, covering the new G2/G4/G1
  tests plus the affected assignment source/version/artifact/process and
  two-job contracts.
- `g2-failure-before-fix.log`: actual **1 failed** at the pre-fix merge head,
  preserving the reproduced stale-value negative.
- `source-change.patch`: exact runtime/CI/test delta from `552aa1378` to
  `3ebee2da5`.
- `MANIFEST.json` uses `executed_source`/`source_files`/`artifacts`; the
  standard Git checker verifies source hashes at the executed commit and
  artifact hashes at the evidence ref.

Not claimed: whole-app TASK-WAIT-01, general model judgment, served-model or
live-provider quality, browser breadth beyond the accepted boundary,
PostgreSQL/multi-worker/soak, guest/KVM, or any new external authority.
