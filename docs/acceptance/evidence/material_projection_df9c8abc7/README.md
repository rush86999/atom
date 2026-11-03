# Material-state approval claim + assignment projection separation

Status: **submitted for independent verification; not self-accepted.**

This successor closes the two cross-boundary failures on `e7758c7f8`:

1. a plan/parameter/cursor/mode/wait/terminal change after review validation
   could still execute under the old approval; and
2. an assignment `operation` projection could fall through the native goal
   executor and create a canvas.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Worktree | `/private/tmp/atom-full-app` |
| Executed source | `df9c8abc7` (full SHA in `MANIFEST.json`) |
| Tree at integrated run | clean |
| Transport | controlled local service/DB; no live provider |

## Material-state claim

`GoalRun.material_revision` is a monotonic persisted revision over
binding-material state. It is advanced by every writer of:

- plan, cursor, parameters;
- waiting state and terminal/cancelled state;
- supervision mode and scope fields;
- replan/progress counters;
- pending-decision status.

Diagnostic decision log entries and display timestamps do not advance it.
The reviewed decision binding includes this revision, and the approval claim's
single conditional UPDATE filters on:

- run id/workspace;
- observed status;
- non-null pending decision;
- pending generation;
- the exact `material_revision` read during validation.

A change after validation (plan, parameters, cursor, mode, wait or terminal)
therefore loses with `stale_review`, no learning, no HITL closure and no
executor call. Added controls cover each writer, the after-validation
interleaving, and the earlier changed-plan/decision/terminal/replay cases.
A migration `20261102_goal_run_material_revision` adds the column with
server default 0. SQLite drift repair now gives a missing non-nullable
`INTEGER` column a numeric default (`0`) instead of text `''`, so an existing
dev database cannot turn the CAS value into TEXT and make an otherwise valid
review unapprovable.

## Projection ownership

Native goal dispatch is explicit: `canvas_work`, `integration_action`,
`computer_use_work`, `human_checkpoint` and `wait_for` dispatch; assignment
`operation` projections and unknown kinds refuse with `not_executed` before
canvas/counter/effect changes. There is no unknown-kind-to-canvas fallback.

Assignment ownership is established by trusted server-side task-lifecycle
association, not a caller-supplied `parameters.task_lifecycle` key. Genuine
assignment projections remain readable; native advance/resume refuses them
and the goal page directs the user to the assignment panel. The existing
assignment executor remains the single driver for assignment work.

## Results

| Scope | Result |
|---|---|
| Integrated backend neighborhood | **611 passed, 8 WebSocket tests deselected** |
| Integrated frontend goal-run + approvals | **49 passed** |
| Verifier boundary probes (material race + projection + adapted HTTP) | **3 passed** |
| Adapted bound HTTP replay probe | **passed** |
| Service claim probe | **2/2 scenarios passed** |
| Material-writer revision controls | **26 passed** |
| Projection/ownership controls | **7 passed** |
| SQLite integer-column repair | **1 passed** |

The original unbound HTTP probe's first request remains a targeted 409
`decision_review_required`.

## Prerequisite for the employee-outcome campaign

This batch is the deterministic approval/projection prerequisite. The next
employee-owned objective campaign starts from an ordinary objective with
changing prerequisites and events; it is not claimed here.

## Boundaries

No live provider action, send, credential, consent or spend. Alignment and
model results from the previous bundle remain separate and unchanged: planner
5/5, goal router failed 1/2, alignment valid negative gap 3.0. Interrupted-
claim/provider-lost reconciliation is not claimed here. Whole-app ORACLE-01,
soak, multi-worker and PostgreSQL runtime qualification remain open.
Historical `111/123` and accepted tags/sources are unchanged.
