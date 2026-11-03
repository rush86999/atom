# Employee Batch A — objective context, readiness and verified outcomes

Status: **submitted for independent verification of Batch A only; the
two-domain adaptive campaign is not claimed.**

This is the first vertical slice of the employee-owned outcome contract. It
preserves the G0 material-approval/projection repairs and adds an
objective -> bounded employee context -> read-only proposal -> deterministic
plan -> readiness-scheduled assignment path, with business outcome
verification.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Worktree | `/private/tmp/atom-full-app` |
| Executed source | `27f256177` (full SHA in `MANIFEST.json`) |
| Tree at integrated run | clean |
| Transport | controlled local service/DB; no live provider |

## Delivered

### Objective and proposal context

`core/employee_proposal.py` builds a bounded employee context from objective,
employee/workspace/tenant identity, teaching, source identities/coverage,
typed facts, obligations, authorized actions and budget. It excludes file
paths/raw bodies and records `execution_owner=assignment`.

A proposal is read-only: it can select registered evidence reads or ask one
targeted clarification. It cannot execute, grant authority or supply a
receipt. The existing assignment planner compiles accepted descriptors; the
planner carries typed `requires` and `facts` into durable steps.

### Business readiness

`core/assignment_readiness.py` evaluates bounded `requires` predicates:
established/missing/stale/conflicting/unavailable facts, predecessor receipts
(applied with a material result; skipped does not satisfy), current
authority, expiry, and `all`/`any`/`not` truth tables. `ready_steps` and
`derive_state` consume readiness; the executor rechecks immediately before the
operation claim. Blocked pending steps retain typed blockers in the plan read
projection. Independent ready branches continue while another branch waits.

The assignment manager remains the sole execution owner; native goal dispatch
does not execute task-lifecycle projections.

### Outcome verification

Assignment completion is derived from declared completion criteria and durable
receipts via the existing task outcome contract. Artifact verification and
provider acceptance are separate evidence; last-step status or model narration
cannot establish completion. The assignment UI exposes objective/employee,
verified progress, readiness reasons, material change and verified/partial
outcome.

## Results

| Scope | Result |
|---|---|
| Integrated backend neighborhood | **506 passed** |
| Integrated frontend assignment/goal/approvals | **54 passed** |
| Verifier G0 boundary probes | **2/2 passed** |
| Assignment readiness suite | **227 passed** |
| Focused readiness/proposal/outcome controls | **19 passed** |

The deterministic controls demonstrate: unknown qualification blocks only the
dependent branch while independent work completes; established false differs
from missing; skipped predecessor does not satisfy a receipt; expired evidence
and insufficient authority block; blockers persist; and adding a valid fact
lets the dependent branch run to a verified completion.

## Boundaries / remaining gates

- G3 atomic plan-patch adoption is **not yet** implemented/claimed.
- G4 general observation-driven reassessment, durable clarification/event
  ordering and uncertain-effect recovery are **not yet** re-proven for this
  new path.
- G5 two-domain adaptive campaign (industrial quote and procurement/bookkeeping
  with changing quantity/source/event ordering, restart, and independent
  expected outcomes) is **not yet** run. General adaptive employee capability
  remains unqualified.
- Served planner remains 5/5; goal router remains failed 1/2; alignment remains
  a valid negative at gap 3.0. No model inference was run in this batch.
- No live provider action/send/credential/consent/spend; historical 111/123 and
  accepted tags/sources unchanged.
