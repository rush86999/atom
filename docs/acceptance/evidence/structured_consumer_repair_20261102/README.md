# Structured planner/goal consumer repair — evidence

Status: **submitted for independent verification; not self-accepted.**

Agent 1's parallel slice for the reviewed goal family: repair the structured
consumers without competing with Agent 2's serialized model inference. The
public approval-binding slice is the owner's separate bundle
`goal_approval_binding_013e1b7cc/`; this source includes both.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Executed source | `bf9de381b08c5f0f2d7b3aa6fddc5cfc4f13a61f` |
| Worktree | `/private/tmp/atom-consolidated-clean` (isolated) |
| Tree at execution | clean |
| Included other product commits | `1e0aa0339` (public approval binding), `013e1b7cc` (approvals UI/stale conflict) |
| Model inference | not run by this slice; Agent 2 owns the serialized 11436 serving configuration |

## Repairs

- **Typed no-tool:** a planner/repair pass that legitimately concludes “no
  tool” returns `ToolPlan(use_tool=False)`, distinct from a transport/parse
  `None`. Callers can audit a decline; a failure still returns `None`.
- **REPLAN repair:** `GoalRunRouter` rejects REPLAN without a non-empty
  id-bearing `new_plan`, performs one bounded corrective pass (defect + prior
  invalid output preserved), and falls back to `ASK_HUMAN` if still invalid.
- **Validation:** `_coerce` now rejects empty/invalid `new_plan` lists, not just
  wrong types.
- **Execution guard:** `execute_decision` never applies/executes an invalid
  REPLAN; it holds for human input without changing the plan or replan count.

## Controls (controlled transport, no model inference)

| Control | Expected | Actual |
|---|---|---|
| REPLAN repair succeeds | REPLAN + non-empty plan; recovered; 2 calls | pass |
| REPLAN repair fails | ASK_HUMAN; no plan; recovered false; 2 calls | pass |
| Transport None | ASK_HUMAN; no repair call; no fabricated decline | pass |
| Invalid REPLAN execution | held ASK_HUMAN; executor not called | pass |
| Planner typed decline | `use_tool=false` typed plan, not None | pass |
| Planner transport None | `None`, not a fabricated decline | pass |

Raw case table: `structured-transport-controls.json`.

## Suites

| Suite | Command | Result | Log |
|---|---|---|---|
| Goal family + service/router/loop/routes/controls | `TESTING=1 pytest <12 files> -q` | **132 passed** | `goal-suite.log` |
| Structured consumer controls | `pytest tests/test_structured_consumer_contracts.py -q` | **5 passed** | `contracts.log` |
| Frontend canvas panels | `jest <3 canvas suites> --runInBand` | **7 passed** | `frontend-tests.log` |

## Model qualification

The failed discretionary-judgment reports (planner 4/5, goal 0/2, alignment
green=false) remain unchanged. This slice does not rerun or relabel them; the
local inference owner serializes the serving configuration. No model-quality or
planning claim is advanced.

## Scope

No live provider call, credential, spend, send or reseed. Whole-app ORACLE
remains open; historical 111/123 and prior accepted sources/tags are unchanged.
