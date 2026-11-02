# Goal effect-family controls + local-model qualification

Status: **submitted for independent verification; not self-accepted.**

This successor batch has two independent goals:

1. close the duplicate-effect gap in the native goal-run family with controls
   at the public resume route and the agent-facing registered action; and
2. qualify the declared local Ollama model through the real planner, goal
   router and alignment sweep, preserving every failure.

The local-model result is **negative/partial and is not a planning-quality
acceptance**. The earlier failed discretionary-judgment verdict remains.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Worktree | `/private/tmp/atom-full-app` |
| Executed source | `31c48718b` (full SHA in `MANIFEST.json`) |
| Tree at final test/probe run | clean |
| Local model | `llama3.1:8b` via separate `127.0.0.1:11436` |
| Model store | `/Users/rushiparikh/.ollama/models-local` |
| Owner service | `127.0.0.1:11434` untouched |
| Transport | controlled local service/DB and local Ollama; no cloud provider |

The model qualification ran with the same consumer code present at
`31c48718b`. The only script change between the planner/goal run and that
source is the alignment gate/seam fix, which does not touch the planner or
goal consumers.

## Goal family — repaired duplicate effect

`GoalRunService.resume` previously read the pending decision, cleared it
unconditionally, appended `approved`, and executed the loop turn. Two
supervisors or a retried request could both read the same pending decision:
both cleared it, appended two approvals and executed twice.

The repair claims the exact persisted pending-decision generation in one
conditional `UPDATE` bound to:

- the run id and workspace;
- the observed status;
- a non-null pending decision;
- the `human_interventions` generation persisted on the run.

Every writer that installs a pending decision increments that generation
(`_hold_for_approval`; the stalled-run interrupt now does too). A loser
returns before learning or execution. The resume route snapshots the exact
pre-turn HITL row ids and closes only those, only after the claim wins, so a
duplicate cannot rewrite the winner's reviewer and a new checkpoint row is
not closed inadvertently.

The independent probe `probe_goal_resume_claim.py` covers:

- **simultaneous resume**: two callers, one executor call, one approval,
  pending cleared, no error;
- **stale snapshot**: a caller holding generation 1 cannot clear the newer
  generation-2 pending decision; no approval, no executor call.

`test_goal_effect_family_controls.py` adds route and service controls:

- wrong-workspace supervisor read/advance/resume/cancel → 404 and no
  decision/effect;
- terminal run advance → 409, no new decision, no executor call;
- sequential duplicate resume → one execution and the first reviewer is
  preserved on the HITL row;
- two simultaneous resumes → one execution;
- fresh session resumes a persisted pending decision once;
- agent action `goal_runs.start`: foreign-workspace goal refused before a run
  row exists, self-impersonation refused, duplicate active run refused with
  one persisted run.

These are fresh-session/thread controls, not a claim of a process restart,
multi-worker soak or PostgreSQL runtime qualification.

## Local-model qualification

Commands use
`scripts/acceptance/local_model_qualification.py` with
`--ollama-url http://127.0.0.1:11436/v1 --model llama3.1:8b`. The scratch
root, provider pin and no-cloud boundary are in the report/log artifacts.

### Planner — 4/5 model-backed, overall failed

| Case | Expected | Actual | Result |
|---|---|---|---|
| inventory stock | inventory search | inventory/search | pass |
| Outlook RFQ email | outlook search | outlook/search | pass |
| dataset value | datasets search | datasets/search | pass |
| “Thanks, that’s all” | no tool | `None` (TOOLS-protocol failure) | **fail** |
| explicit email search | outlook search | outlook/search | pass |

The no-tool turn is a safe no-op (the planner's contract treats `None` as
“no tool”), but it is not a model-backed plan. A schema-compatible JSON-mode
retry on the same prompt produced a valid `use_tool=false` plan, so this is a
transport/protocol gap rather than evidence that the model cannot answer the
turn. The real consumer still failed and is counted as a failure.

### Goal router — 0/2 valid, overall failed

| Context | Actual | Result |
|---|---|---|
| ambiguous quote, research step | model `REPLAN` with `new_plan=None`; consumer falls back to `ASK_HUMAN` | **fail** |
| research finished, quote step remains | structured output `None`; consumer falls back to `ASK_HUMAN` | **fail** |

For the first case, one corrective retry that named the missing `new_plan`
schema produced a valid two-step REPLAN. The production consumer has no such
repair pass, so its recorded result remains the safe `ASK_HUMAN` fallback.

### Alignment — ran, not green

`alignment_verdict` with the local chat transport ran all 18 calls
(3 scenarios × 3 structures × proposal+judge) in 111.67 s. It returned
`ran=true`, `green=false`, `max_gap=3.0` against the `2.0` threshold, with
fleet policy scores below single on the pricing-pressure scenario. This
preserves the failed discretionary-judgment result rather than upgrading it.

### Failure controls

- planner planning timeout (0.25 s) → `None`, no exception;
- planner empty structured output → `None`, no exception;
- goal router unavailable → `ASK_HUMAN`, no plan;
- invalid `REPLAN` without `new_plan` → `ASK_HUMAN`, no plan.

Historical hard cases are retained in
`historical-planner-nested-output.txt` and
`historical-goal-invalid-replan.txt`.

## Tests

| Scope | Result |
|---|---|
| Combined backend goal/reviewed-skill/oracle/canvas neighborhood | **319 passed** |
| New goal effect-family controls | **9 passed** (included above) |
| Independent goal resume claim probe | **2/2 scenarios passed** |
| Frontend canvas suites | **7 passed** |
| Local model pin probe | **passed** (6.41 s) |

## Boundaries

No live provider lookup, refresh, write, send, credential, consent or spend.
No cloud fallback, model download, reseed, deployment, whole-app ORACLE-01,
planning-quality acceptance, soak or multi-worker claim. Historical
`111/123`, the 123 denominator and prior accepted tags/sources are unchanged.
