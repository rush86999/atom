# Goal effect-family + local-model qualification — results

Executed source: `31c48718b` (`codex/brennan-full-app-20261102`), clean at
the final test/probe run.

## Goal family

### New controls

`goal-family-tests.log` — **319 passed** in the combined backend
neighborhood. The new `backend/tests/test_goal_effect_family_controls.py`
contributes **9 passed**:

| Control | Result |
|---|---|
| wrong-workspace supervisor read/advance/resume/cancel | 404; owner decision log unchanged |
| terminal run advance | 409; no decision; executor not called |
| duplicate resume after one hold | one executor call; one approval; first reviewer preserved |
| two simultaneous resumes (file DB, two sessions) | one winner; one executor call; one approval |
| stale resume snapshot vs newer pending | loser refused; newer pending retained; no approval/executor |
| fresh session resumes persisted pending | one execution; second fresh-session resume is a no-op |
| action `goal_runs.start` foreign workspace | refused before a GoalRun row exists |
| action `goal_runs.start` self-impersonation | refused; no run row |
| action `goal_runs.start` duplicate active run | refused; exactly one run row |

The standalone probe is independent of pytest:

`goal-resume-claim-probe.log` / `.json` — **status passed**:

- simultaneous: one `resumed=true`, one `resumed=false`, `executor_calls=1`,
  `approved_entries=1`, `pending=null`;
- stale snapshot: `resumed=false`, `executor_calls=0`,
  `old_generation=1`, `current_generation=2`, newer pending retained,
  `approved_entries=0`.

This is a fresh-session/thread control, not a process-restart or multi-worker
soak claim.

## Local model

### Availability / pin

`local-model-tags.json`: `llama3.1:8b`, 4,920,753,328 bytes, Q4_K_M.
`ollama-server-config.txt`: separate `127.0.0.1:11436`, Metal on Apple M4
Pro, 37.4 GiB, default context 32768, models store
`/Users/rushiparikh/.ollama/models-local`. Owner `11434` untouched.

`local-model-pin-probe.log`: pin `ollama/llama3.1:8b`; served provider
`ollama`; served model `llama3.1:8b`; structured decision returned;
**passed** in 6.41 s.

### Planner

`local-model-qualification-planner-goal-report.json` — **planner failed**
(4 model-backed passes, 1 failure):

| Case | Expected | Actual |
|---|---|---|
| inventory stock | inventory/search | inventory/search (model-backed) |
| Outlook RFQ | outlook/search | outlook/search (model-backed) |
| dataset price | datasets/search | datasets/search (model-backed) |
| no-tool thanks | use_tool=false | consumer `None` (TOOLS protocol) |
| explicit email search | outlook/search | outlook/search (model-backed) |

The no-tool consumer failure is safe (`None` = run without a tool), but it
is not a model-backed plan. JSON-mode retry on the same prompt produced
`use_tool=false` with `reason="No lookup needed"`. The real consumer failure
stays counted.

### Goal router

`local-model-qualification-planner-goal-report.json` — **goal failed**
(0/2 valid):

- ambiguous quote: model `REPLAN` with `new_plan=None`; consumer returned
  `ASK_HUMAN` with `router returned an unusable decision`; no plan executed.
- research finished: structured output `None`; consumer returned `ASK_HUMAN`
  (`router returned an unusable decision: None`).

A corrective retry for the first case (naming the missing `new_plan`
requirement) produced a valid two-step REPLAN. The production consumer does
not run that repair, so its result remains the safe human hold.

### Alignment

`local-model-qualification-alignment-report.json` — **failed**:
`ran=true`, `green=false`, `max_gap=3.0` (threshold 2.0), 18 calls,
111.67 s. Scores are persisted per scenario/structure. This preserves the
failed discretionary-judgment verdict; model availability did not upgrade it.

### Failure controls

| Control | Result |
|---|---|
| planner timeout 0.25 s | `None`, no exception |
| planner empty structured output | `None`, no exception |
| goal router unavailable | `ASK_HUMAN`, no plan |
| invalid `REPLAN` without `new_plan` | `ASK_HUMAN`, no plan |

## Frontend

`frontend-canvas-tests.log` — **7 passed** across
`CanvasCapabilityRules`, `CanvasCapabilityDerive` and
`CanvasCapabilityAssessment`.

## Boundaries

No live provider action, send, credential, consent or spend. No cloud
fallback, download, reseed or deployment. Local-model qualification is
negative and is not planning-quality acceptance. Whole-app ORACLE-01 remains
open; historical 111/123 and prior accepted sources/tags are unchanged.
