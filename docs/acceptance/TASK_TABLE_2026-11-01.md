# Live task table — 2026-11-01

One short backlog. Update this table, not the large ledgers, until a batch passes.

| Task | Owner | Next executable action | Failing test | Blocker |
|---|---|---|---|---|
| ORCH-08 delegation depth/cycles/scope | Agent 1 | **Passed** whole-graph depth/cycle/scope controls; evidence in claims/orch-team | none (16 controls) | none |
| TEAM-01 single accountability | Agent 1 | **Passed** exactly-one contract enforcement | none | none |
| ASK-03 runtime revocation + re-entry + fail-closed | Agent 1 | **Passed** runtime gate, restart and re-entry controls | none (8 controls + calibration suite) | none |
| GOAL-04 no-progress stop | Agent 1 | **Passed** real loop halt/strategy-change controls | none | none |
| WF-05 policy pause → approval → resume once | Agent 1 | **Passed** payload-bound approval, duplicate and fresh-engine controls | none (7 controls) | none |
| GOV-04 training lifecycle | Agent 1 | **Passed** start/approval/guidance/evidence/completion controls | none | none |
| Reusable acceptance world | Agent 1 | In use by new tests; migrate remaining fixtures opportunistically | none | none |
| Complex teaching campaign (A) | Agent 1 | **Passed** on isolated world: conflict refusal -> UI correction -> missing qualification -> mapping -> 506.00; restart; active run kept Arial 11 while revised run used Calibri 14; expedited exception Arial 10; wrong-context grants lesson excluded; conflict deletion is recovery, not correction history. Limitation: taught rounding has no UI field (no counted claim promises it). | — | rounding UI missing (not counted) |
| Long-running ≥2h campaign (C) | Agent 1 | C resumed 1h49m after its wait (below the gate) and is kept as the restart/upgrade control. **C2** (`cac9cbd6…`) closed at **7,239.8s** after its wait on the pinned historical source `414d8add3`: source-1 110.00 with one attempt/operation, explicit send approval, Arial 11 artifact SHA `bce1a2ad…`, one controlled effect, final restart preserved. | — | historical source; not budget-repair verification |
| Cancellation consistency repair | Agent 1 | **Passed** at `f5d2e085a` (backend tree `d37da0be5943`): terminal transition clears the live wait, cancel projects/idempotent, late replies refused before matching (409), gap resolve refused, fresh-session/resume/scheduler consumers consistent, outbox empty. 129 focused tests + 2 public-API cancellation tests. | none | none |
| Budget pause-credit repair | Agent 1 | **Accepted within tested scope** at `f1ef414c3` / backend tree `c2963fbcdc8e`: legacy stale-live-wait double subtraction fixed; 63 focused tests (61 executor + 2 public-route cancellation). Post-acceptance finding appended to the acceptance record; accepted tag preserved. | none | none |
| CORE-06 credential lifecycle | Agent 2 | **Passed** save/replace/delete without restart | — | none |
| ROUTE-06 local endpoint | Agent 2 | **Passed** registered local route/first chat | — | — |
| ROUTE-03 fallback | Agent 2 | **Passed** primary failure -> secondary, policy denial zero calls | — | — |
| GRAPH-05 graph explorer | Agent 2 | **Passed** real browser 3 nodes/2 relationships | — | — |
| INST-01 pristine bootstrap | Agent 2 | **Passed** clean worktree, own venv/node_modules, empty root, restart, production build | — | none |
| GOV-05 OIDC lifecycle | Agent 2 | **Passed** 20 controlled-IdP tests | — | none |
| Microsoft read-only ingestion | Agent 2 | Preserved accepted qualification; no rerun | — | closed |
| Real Outlook send | Agent 2 | Preserved accepted one-use qualification; no second send | — | closed |

## Failure-class coverage now in place

- **Fleet:** all-edge cycles (multi-parent DAG), longest-path depth, existing
  descendants over a lowered limit, foreign tenant/workspace, no mutation on
  refusal.
- **Revocation:** failure blocks immediately; 1 and 19 new successes still
  blocked; 20 clears; second regression resets; new session persists; unreadable
  store refuses.
- **Approval:** no effect before approval; exactly one after; wrong step or
  execution, rejected/missing row, crash-after-dispatch, payload drift and
  fresh-engine resume all refuse or stay single.
- **Training:** start → guidance → evidence → completion → promotion; duplicate
  completion idempotent; invalid transitions refused; no evidence, no promotion.

## Current batch state

- README breadth: **111/123 (90.2%)** in `readme_feature_readiness_2026-11-01/CLAIM_INVENTORY.json`.
- Runtime batch: **229 passed** at `aba2754ec`.
- Product batch: CORE-06 passed; ROUTE-03/06 3 passed; GOV-05 20 passed; GRAPH-05 verified; INST-01 clean bootstrap passed.
- Recovery browser: **5/5** on the integrated candidate (wait/restart/resume, changed source, ambiguity, cancellation, duplicate resume).
- Remaining: C2's 2h resume (earliest 20:04:53Z), then the final coverage report/manifests. A and the sibling controls are done.

## Hard release target

- **111/123 verified functional claims** remains mandatory. Current:
  **111/123 (90.2%)**.
- Reserve claims if a target is rejected: **TEAM-05**, **MEM-07**, **GOAL-02**.
  Do not change the frozen denominator.
- First-use path: clean install -> `make setup` -> `make dev` -> `make sample`
  completed `232990.00` and a DOCX in **13 seconds** after backend start on the
  clean-install world at `776c6644f`.

## Acceptance record

**Accepted 2026-11-01 within the documented local and controlled-provider
scope.** Runtime `bec60978b`; evidence/docs `88bf413e8431`; breadth
**111/123 = 90.2%**. See
[`VERIFIER_ACCEPTANCE_2026-11-01.md`](VERIFIER_ACCEPTANCE_2026-11-01.md).

The two focused findings (wait-credit duplication and untracked evidence) are
closed. No further repair campaign is indicated for them. Hosted deployment and
publication remain deferred. Broader live sending, autonomous live sending,
connector breadth and model-quality exclusions remain; the previously accepted
one-use Outlook send and Microsoft read-only qualification remain closed and
unchanged.
