# Employee Batch B — atomic adaptation core

Status: **deterministic Batch B core submitted; the served two-domain
adaptive campaign (G5) is not run and is not claimed.**

This successor adds the bounded plan-patch and observation-adaptation
mechanisms over the existing assignment lifecycle. It does not add a second
planner, executor, queue or effect store.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Worktree | `/private/tmp/atom-full-app` |
| Executed source | `dfd05cbfc` (full SHA in `MANIFEST.json`) |
| Tree at integrated run | clean |
| Transport | controlled local service/DB; no live provider |

## Delivered

### Atomic plan patches

`core/employee_patch.py` validates a bounded proposal against the current
task and plan revision, refuses stale bases and running/uncertain effects, and
adopts through `TaskLifecycle.mutate_assignment`. The CAS callback is pure:
no provider call, file write, model inference or notification. Plan revision
increments once; criteria, authority, budgets and unaffected receipts are
preserved; affected results move to `prior_results`; duplicate patch IDs are
idempotent.

### Observation adaptation

`core/employee_adaptation.py` turns provenance-bearing observations into
retain / clarify / invalidate / replan / reconcile proposals. Deterministic
code computes the affected closure. A model proposal can only compile through
the same patch contract. Missing qualification evidence produces one targeted
question; an uncertain effect returns `reconcile` without resending.

### Outcome truth

Assignment completion now uses declared criteria and durable receipts.
Applied steps with an unresolved required criterion remain partial; artifact
and provider acceptance remain separate evidence. The job view exposes the
business verdict.

### Consumer

`POST /api/assignments/{run_id}/patch` adopts one validated patch atomically
and advances ready work through the existing executor.

## Results

| Scope | Result |
|---|---|
| Integrated backend neighborhood | **638 passed**, 8 known WebSocket tests deselected |
| Frontend assignment/goal/approval surfaces | **54 passed** |
| Verifier G0 boundary probes | **3 passed** |
| Patch/adaptation focused controls | **7 passed** |

Controls cover stale base refusal, running/uncertain refusal, duplicate
idempotency, unaffected receipt retention, fresh-session readback, source/
quantity/qualification observations, clarification instead of guessing and
uncertain-effect reconciliation without resend.

## Boundaries / remaining gates

- The actual served model has **not** been run for adaptive choice.
- The held-out two-domain industrial-quote and procurement/bookkeeping
  campaign (G5) is **not** run; general adaptive employee capability remains
  unqualified.
- Full event-order/restart/recovery campaign beyond the focused controls is
  not claimed.
- Planner remains 5/5; goal router remains failed 1/2; alignment remains a
  valid negative at gap 3.0. No model inference was run here.
- No live provider lookup/write/send/credential/consent/spend; historical
  111/123 and accepted tags/sources unchanged.
