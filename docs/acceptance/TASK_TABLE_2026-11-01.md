# Live task table — 2026-11-01

One short backlog. Update this table, not the large ledgers, until a batch passes.

| Task | Owner | Next executable action | Failing test | Blocker |
|---|---|---|---|---|
| ORCH-08 delegation depth/cycles/scope | Agent 1 | Batch ready; verifier re-check | none (16 controls) | none |
| TEAM-01 single accountability | Agent 1 | Batch ready; verifier re-check | none | none |
| ASK-03 runtime revocation + re-entry + fail-closed | Agent 1 | Batch ready; verifier re-check | none (8 controls + calibration suite) | none |
| GOAL-04 no-progress stop | Agent 1 | Batch ready; verifier re-check | none (2 controls) | none |
| WF-05 policy pause → approval → resume once | Agent 1 | Batch ready (acceptance test landed) | none (7 controls) | none |
| GOV-04 training lifecycle | Agent 1 | Batch ready (4 controls incl. unauthorized transitions, no-evidence) | none | none |
| Reusable acceptance world | Agent 1 | In use by new tests; migrate remaining fixtures opportunistically | none | none |
| Complex teaching campaign (A) | Agent 1 | Run through normal UI on the integrated candidate after Agent 2's install work | — | Agent 2 install/browser surface |
| Long-running ≥2h campaign (C) | Agent 1 | Start the elapsed assignment while other work continues; reuse controlled outbox | — | none (time) |
| CORE-06 credential lifecycle | Agent 2 | Reconcile against final source | — | none |
| ROUTE-06 local endpoint | Agent 2 | — | — | — |
| ROUTE-03 fallback | Agent 2 | — | — | — |
| GRAPH-05 graph explorer | Agent 2 | — | — | — |
| INST-01 pristine bootstrap | Agent 2 | — | — | none |
| GOV-05 OIDC lifecycle | Agent 2 | — | — | none |
| Microsoft read-only ingestion | Agent 2 | Await owner authorization (Part A) | — | external authorization |
| Real Outlook send | Agent 2 | Await owner authorization (Part B) | — | external authorization |

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
