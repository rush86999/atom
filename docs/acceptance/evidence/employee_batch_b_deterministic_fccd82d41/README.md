# Employee Batch B — deterministic rewiring, recovery and two-domain campaign

Status: **deterministic mechanism campaign submitted; the served-model
adaptive-choice campaign and Batch A acceptance are not claimed.**

This successor integrates the verified-receipt/Sent Items repair (`046fe0bf3`,
evidence `f0b1ad23a`) with bounded plan rewiring, authoritative task-version
patch binding and a two-domain deterministic campaign. It does not add a
second planner, executor, queue or effect store.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Worktree | `/private/tmp/atom-full-app` |
| Executed source | `fccd82d41` (full SHA in `MANIFEST.json`) |
| Batch A repair | `046fe0bf3` / evidence `f0b1ad23a` |
| Batch B core parent | `93650be55` |
| Transport | controlled local service/DB; no live provider |

## Delivered

### Authoritative patch identity and safety

Plan patches now bind to the durable lifecycle `task_version` (not the
objective revision), carry a canonical material digest, and conflict when a
patch id is reused with different material content. Validation refuses:

- registered-adapter/action mismatches and effect/authority expansion;
- removal of required work or weakening of existing requirements;
- changes whose affected closure contains an active or uncertain operation;
- established facts without accepted source/authority provenance.

`StepUpdate` permits bounded rewiring of inputs, dependencies and requirements
for pending, failed or invalidated work. Objective, adapter, effect, authority
and required flag remain immutable; dependency cycles are refused by the
existing validator.

### Observation-driven continuation

An adapted observation has a stable patch identity. A replay returns
`already_applied` without a second plan revision or reopening completed work.
A restarted executor re-runs only the affected branch and its descendants;
independent operation ids, results and receipts remain byte-for-byte intact.
Stale readiness blockers are cleared at dispatch.

### Two-domain deterministic campaign

`tests/test_employee_two_domain_campaign.py` uses production assignment,
readiness, plan-patch, wait, restart, approval and outcome paths with two
different business vocabularies:

- **Industrial quote**: eligibility blocks the discount until established;
  independent reads complete first; B price 50→55 and A quantity 2→3 reopen
  only their dependent closures; the primary 12-day lead fails the 10-day
  requirement; an approved 7-day equivalent is adopted by rewiring selection
  to wait for the equivalence read; final quote is 494.75 with an artifact and
  a draft that records `send_performed=false`.
- **Procurement/bookkeeping**: the invoice (3 units, 390.00) disagrees with
  receiving (2 units); vendor/CoA/period checks complete while the supplier
  wait is open; restart preserves the wait; an old correlation is unmatched;
  the corrected invoice v2 rebinds for 270.00 with the old result retained;
  one approved bill is created and read back; a duplicate reply is terminal
  and no payment step exists.

Negative twins: a 5-day delivery limit makes the approved 7-day equivalent
infeasible (494.75 calculated, no artifact, no completion), and a closed
accounting period refuses bill creation with zero effects.

## Results

| Scope | Result |
|---|---|
| Integrated backend selection | **544 passed** |
| Frontend assignment/goal/approvals | **54 passed** |
| Independent evidence + G0 + blocked route probes | **9 passed** |
| Assignment/employee suite | **295 passed** |
| Two-domain campaign | **4 passed** |
| G3/G4 focused controls | **7 passed** |

## Not claimed / remaining

- **G5 level 2 is not run**: no actual served-model adaptive choice, no raw
  model traces. General adaptive employee capability remains unqualified.
- Batch A acceptance remains withheld pending independent re-verification.
- G4 is demonstrated deterministically for the named controls; a broader
  event-order/recovery campaign beyond them is not claimed.
- Planner remains 5/5; goal router remains failed 1/2; alignment remains a
  valid negative at gap 3.0. No model inference was run.
- No live provider action/send/credential/consent/spend; historical `111/123`
  and accepted tags are unchanged.
- Four `test_task_lifecycle.py` controls fail identically at the parent and at
  this source; they are disclosed rather than silenced.
