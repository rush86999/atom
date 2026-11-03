# Material-state claim and projection separation — results

Executed source: `df9c8abc7` (clean worktree).

## Backend

`backend-integrated.log` — **611 passed, 8 WebSocket tests deselected** in one run across goal effect-family,
routes/service/loop/events/learning/watchdog/access, HITL approvals, shared
goal plan validation, projection ownership, structured consumers, alignment,
chat teaching, assignment executor, reviewed-skill/Memento, oracle/presentation
and direct canvas controls.

`verifier-boundary-probes.log` — **3 passed** (two boundary probes plus the adapted bound HTTP replay):

- plan changed after binding validation cannot win the claim;
- assignment operation projection cannot execute as native canvas work.

`material-writer-test.log` — **26 passed**: every material writer advances the
revision; each mutation after validation returns stale with zero effects and
the original pending decision retained.

`projection-ownership-tests.log` — **7 passed**: genuine assignment projection
readable; forged marker not trusted; native advance/resume refuses owned
projection; unknown kind creates nothing; assignment executor still completes.

`sqlite-integer-repair.log` — **1 passed**: a drifted SQLite table repairs a
missing non-nullable Integer column with numeric `0`, not TEXT `''`.

## Frontend

`frontend-integrated.log` — **49 passed** across goal-run detail/index and
approvals. Assignment-owned runs show a read-only projection notice and no
native Advance; stale review still refreshes to the newer decision.

## Claims

| Control | Result |
|---|---|
| set_plan after validation | stale; no effect |
| patch_parameters after validation | stale; no effect |
| cursor/mode/wait after validation | stale; no effect |
| terminal/cancelled held decision | 409 run_terminal; no effect |
| exact bound A replay after B | 409 stale; one effect; B pending |
| assignment operation projection native advance | not_executed; canvas 0 |
| forged task_lifecycle marker | ownership not trusted; native refusal |
| genuine assignment projection | readable; assignment executor owns work |
| unknown native kind | not_executed; canvas 0; counters unchanged |

`goal-resume-claim-probe.log` / `.json` — **status passed** (simultaneous and
stale-generation service claims). `adapted-http-binding.log` — bound replay
probe **1 passed**. `legacy-unbound-refusal.txt` — old unbound request first
gets **409 decision_review_required**, as intended.

## Boundaries

No live provider action, send, credential, consent or spend. Previous served
model/alignment results remain separate: planner 5/5, goal router failed 1/2,
alignment valid negative gap 3.0. Interrupted-claim/provider-lost recovery is
not claimed. Whole-app ORACLE-01, soak, multi-worker and PostgreSQL runtime
qualification remain open. Historical `111/123` unchanged.
