# Structured planning final — results

## Frozen planner/goal qualification

| Case | Expected | Actual | Result |
|---|---|---|---|
| inventory_stock | use_tool=true, inventory | typed plan, inventory | PASS (17.07 s) |
| outlook_rfq | use_tool=true, outlook | typed plan, outlook | PASS (9.25 s) |
| dataset_price | use_tool=true, datasets | typed plan, datasets | PASS (14.35 s) |
| no_tool_chat | use_tool=false typed decline | ToolPlan(use_tool=false) | PASS (7.76 s) |
| explicit_email_search | use_tool=true, outlook | typed plan, outlook | PASS (5.11 s) |
| research_finished | valid decision with concrete plan | REPLAN with step-2 plan | PASS (10.45 s) |
| ambiguous_quote | valid decision; REPLAN non-empty plan | empty REPLAN after one repair → ASK_HUMAN, no execution | FAIL, preserved |

Planner 5/5; goal 1/2. The failed case is a genuine model failure, not
relabelled. Invalid-judge alignment certification is Agent 2's scope.

## Deterministic boundary controls

| Control | Result |
|---|---|
| Empty/dict/duplicate/unknown-kind/bad-dependency/authority plans rejected | PASS |
| Valid dependency order accepted | PASS |
| Unregistered integration action rejected at dispatch | PASS |
| Invalid REPLAN repair success / repeated failure / transport None | PASS |
| Deadline exhaustion → ASK_HUMAN, one attempt | PASS |
| Planner scoped JSON options (output_mode/cascade/MoA) | PASS |
| Typed no-tool vs transport None | PASS |

Suites: 152 backend passed, 7 frontend passed on `756edfd45`.
