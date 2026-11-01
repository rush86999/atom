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
| Complex teaching campaign (A) | Agent 1 | Next: run sales + grants browser flow on the restarted final candidate | — | none |
| Long-running ≥2h campaign (C) | Agent 1 | Waiting assignment started 13:40 UTC; resume after 15:40 UTC with a real restart | — | elapsed time |
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
- Recovery browser: **5/5** at `aba2754ec` (wait/restart/resume, changed source, ambiguity, cancellation, duplicate resume).
- Remaining: elapsed long-run resume (15:40 UTC), sales + grants teaching campaign, final coverage report/manifests.
