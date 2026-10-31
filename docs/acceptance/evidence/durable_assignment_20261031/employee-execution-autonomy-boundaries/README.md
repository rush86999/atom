# Bounded autonomy boundaries — standing authority, budgets, reconciliation, UI

This bundle records the implementation controls behind the remaining practical
acceptance items. It reuses the accepted assignment recovery and assessment
approval mechanisms; it does not add a second engine or a broad campaign.

## Bounded standing authority

An explicit user grant covers external `outbound` effects only:

- named recipients (required; normalized case-insensitively);
- a hard `max_effects` bound of 1–20;
- optional expiry;
- one use is consumed under the existing assignment CAS **before** dispatch;
- the step records the grant id, use number, max and prepared payload hash;
- an exhausted, expired, out-of-scope, wrong-recipient or non-opted-in effect
  falls back to ordinary human approval — never a silent send;
- only the acceptance-controlled outbox adapter opts in. Live email send
  remains approval-required.

Executor controls: two covered sends dispatch without approval and exhaust the
grant; a one-use grant sends once then awaits approval; a recipient outside the
grant and an expired grant both wait for approval.

Browser evidence: the integrated two-domain journey grants one send per domain,
restarts the backend, resumes both waits, and completes with **2 effects and 0
assignment approvals** (`../two-domain-autonomous-journey/`, 5/5).

## Budgets

`max_steps`, `max_attempts_per_step` and `max_wall_seconds` were already
enforced. `max_cost_usd` is now enforced too, and a step's returned `cost_usd`
is accumulated on the assignment before the next step is considered. The
control sets a $5 bound, completes one $10 step, and asserts the next step is
blocked with `assignment_budget_exhausted`.

## Uncertain-effect reconciliation

`POST /api/assignments/{run_id}/reconcile/{step_id}` requires TEAM_LEAD
authority and non-empty evidence, with three distinct verdicts:

- `applied` — records completion and advances; never resends;
- `not_applied` — preserves the failed evidence and creates a NEW operation on
  the next resume (which still needs its own approval unless a grant covers it);
- `insufficient` — leaves the uncertain state intact and never resends.

The Assignments panel exposes the evidence field and the three verdicts.

## Draft vs authorized assessment UI

The canvas capability panel now labels an unapproved assessment as a draft,
shows the review requirement, approves the exact execution, surfaces durable
clarification questions, and only exposes a "Use decisions" surface once the
server reports `authorized=true`.

The clarification route re-dispatches the original selection ask and passes the
answers as clarification context, so an answer value cannot contaminate the
selection. The route test pins: resume produces a new execution, the prior
approval cannot authorize it, and decisions remain refused until fresh review.

## Result

`focused-backend-tests.log`: **185 passed**, 0 failed.
`frontend-tests.log`: **6 passed**, 0 failed; TypeScript `--noEmit` clean.

The browser journey is recorded separately in
`../two-domain-autonomous-journey/two-domain.json` (**5/5**).

## Scope

- controlled local outbox; no provider contact and no real send;
- one worker, one scratch world; multi-worker/soak not claimed;
- standing authority is not a general autonomy switch and does not authorize
  live sends;
- the phase-aware qualification verdict remains failed (17/18 V1, 18/19
  V3/post-restart).

## Reconciliation on the final source (2108a2839)

The implementation landed at `814962078`; the clarification-binding repair
landed after it. Both were re-run together on the final source:

- backend: **208 passed** across the assignment executor/routes, all four
  canvas-assessment suites, the clarification suites, review contract/result,
  assessment judge and canvas training context
  (`reconciled-at-2108a2839.log`);
- frontend: **6 passed** in `AssignmentPanel.test.tsx` and
  `CanvasCapabilityAssessment.test.tsx` (draft vs authorized decisions,
  clarification questions, bounded authority and reconciliation surfaces).

The earlier `focused-backend-tests.log` (185 passed at `814962078`) is
preserved as that commit's record.
