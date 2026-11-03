# Structured planning final — executable plan contract and frozen qualification

Status: **submitted for independent verification; not self-accepted.**

Agent 1's completion slice for the fast-resolution batch. Agent 2's public
approval binding/restart/replay controls are in the same ancestry and the
separate `goal_approval_binding_013e1b7cc/` bundle.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Executed source | `756edfd4520649778d3fa27a4b514bb1530679ac` |
| Worktree | `/private/tmp/atom-consolidated-clean` |
| Tree at execution | clean (qualification was run on the identical pre-commit tree) |
| Model | `llama3.1:8b` at `http://127.0.0.1:11436/v1`, pin `ollama:llama3.1:8b` |
| Inference | one owner, one active generation; `11434` untouched |

## Production contracts

- Planner structured calls use the scoped JSON output mode (`cascade`/MoA off).
  The frozen no-tool turn is now a typed `ToolPlan(use_tool=false)`; the old
  TOOLS-mode `None` remains preserved as a failed attempt in the historical
  report.
- Goal router uses JSON mode, one shared monotonic deadline (initial + at most
  one repair), request-scoped trace/errors, and validator feedback in the
  repair prompt.
- One semantic plan validator is shared by router acceptance, repair feedback,
  `create_run`/`set_plan` shape checks and the integration-action dispatch
  boundary. It validates non-empty plans, unique ids, supported kinds,
  dependencies/order, kind-specific required fields and forbidden
  authority-expanding declarations; unregistered action names are checked at
  dispatch.
- An unrepaired REPLAN becomes ASK_HUMAN with no plan/cursor/replan-count
  change and no execution.

## Frozen qualification (final run, 9 raw calls)

| Capability | Result | Detail |
|---|---|---|
| Planner | **5/5 passed, model-backed** | inventory, outlook, dataset price, explicit email, and **no-tool** (`use_tool=false`, 7.76 s) |
| Goal | **1/2, failed and preserved** | `research_finished` valid concrete REPLAN; `ambiguous_quote` returns empty REPLAN after one repair → ASK_HUMAN, no execution |
| Alignment | **not run here** | Agent 2 scope; invalid-judge gate is separate |

Raw report and every call: `qualification-report.json`,
`qualification-calls.jsonl`, `qualification-summary.json`.

## Deterministic suites

| Suite | Command | Result | Log |
|---|---|---|---|
| Goal/approval/structured family | `TESTING=1 pytest <14 files> -q` | **152 passed** | `goal-suite.log` |
| Frontend canvas panels | `jest <3 canvas suites> --runInBand` | **7 passed** | `frontend-tests.log` |

## Scope

No live provider call, credential, spend, send or reseed. Alignment quality,
arbitrary behavior improvement and hosted/platform gaps remain unqualified.
Historical 111/123, the 123 denominator and prior accepted sources/tags are
unchanged.
