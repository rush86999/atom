# Structured consumer repair — test results

| # | Control | Expected | Result |
|---|---|---|---|
| 1 | REPLAN repair success | REPLAN with non-empty plan; repair.recovered=true; 2 calls | PASS |
| 2 | REPLAN repair failure | ASK_HUMAN; no plan; recovered=false; 2 calls | PASS |
| 3 | Transport None | ASK_HUMAN; no repair call; no fabricated no-tool | PASS |
| 4 | Invalid REPLAN execution | held ASK_HUMAN; executor calls 0 | PASS |
| 5 | Planner typed decline | ToolPlan(use_tool=false), not None | PASS |
| 6 | Planner transport None | None, not fabricated | PASS |

Suites: 132 goal-family/service tests passed, 5 focused controls passed,
7 frontend tests passed on source `bf9de381b`.
