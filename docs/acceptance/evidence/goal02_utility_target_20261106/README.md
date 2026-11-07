# GOAL-02 — persisted utility target and deterministic trajectory ranking

Status: **submitted for independent review** (not self-accepted).

This evidence covers the production GOAL-02 contract: an explicit utility target
persists on the existing `GoalObjective`, completed `GoalRun` trajectories are
ranked deterministically against it, and higher utility ranks higher. Utility is
an optimization signal only; it never satisfies a goal or overrides
completion/safety/constraint gates.

## Exact source

| Item | Value |
|---|---|
| Branch | `codex/goal02-utility-target-20261106` |
| Original checkpoint | `e0469141c884bfd37ebd152ade00f1e13b91fe91` |
| Corrected checkpoint (PR707 review fix) | `0839733ceb4ea0f4513b967a1db1bfb46625d760` |
| Baseline for comparison | `248a2329623b433e68104c4d89d2965683d81013` (`origin/main` in `/private/tmp/goal02-baseline`) |
| Interpreter | `/Users/rushiparikh/projects/atom/backend/venv314/bin/python` |
| World | per-test scratch SQLite files; `TESTING=1`; no live DB |
| Model/provider inference | **none** |

Source blobs (git blob ids at the corrected checkpoint):

| Path | Blob |
|---|---|
| `backend/core/goals/utility_target.py` | `c6d45de025361072887c37751fbe1c9ead26e56e` |
| `backend/core/agent_objective.py` | `246e6529bf6b12b38e7a91d6e9f8f55a21a9f7c2` |
| `backend/core/goals/goal_service.py` | `5fc000ef7561c34305546f78c1a6fb607406256d` |
| `backend/core/goals/goal_run_router.py` | `c06b55e5324015be44277b63fcae72ce56875013` |
| `backend/api/goal_routes.py` | `5f69c4c1ea8b2dc93c79f0ea68d37238f9b74d0e` |
| `backend/core/action_registry.py` | `7d1e1a4cf6c68776f22d1142e6e8dc72370bb72f` |
| `backend/tests/test_goal_utility_target.py` | `f486b2715350bc5642a510995b9b635c9cb4e865` |
| `docs/architecture/AGENT_ENVIRONMENT.md` | `1afec0eec3657f2a1ddac4bd2f54ddaf7a625c4f` |

## Review finding and correction

Independent review reproduced on the original checkpoint:

- **Wrong winner at 100+ candidates.** `GoalService.utility_ranking` ordered
  `created_at ASC` and silently applied `limit(100)`. With 100 older achieved
  runs and a newer best run (target minimize `human_interventions`, 10 vs 0),
  the 101st/best candidate was omitted and the wrong winner was reported.
- Retained original negative: the reviewer probe is the 100-older-plus-latest
  case above. It is **not** relabeled as accepted.
- Correction at `0839733ce`: complete candidate coverage — every terminal
  `GoalRun` for the scoped goal/workspace participates; there is no hidden
  candidate cap. Stable `created_at, id` ordering is only deterministic input
  order. If pagination is ever needed it must be explicit end-to-end with
  honest coverage metadata.
- Equivalent in-tree controls: `test_complete_coverage_beyond_the_old_hundred_run_cap`
  (101st best wins) and `test_invalid_latest_candidate_beyond_cap_cannot_win`
  (invalid 101st is included but withheld, so it earns no rank).

## What was verified

- Target definition is explicit and validated before any write; malformed
  targets are rejected.
- The target survives a fresh engine/service (restart simulation) and reaches
  `Objective.utility_target`.
- Two completed outcomes: higher normalized utility ranks higher for both
  `maximize` and `minimize` targets.
- Complete coverage beyond 100 terminal candidates; the best latest run wins.
- failed/cancelled outcomes cannot win on a better metric; an explicit trusted
  `constraints_ok=False` candidate is withheld.
- Missing, non-finite, fractional, negative, string, bool, and float-overflowing
  huge count evidence is unknown (`utility=None`, no rank), not zero and not a
  crash — including at the 101st position.
- Ranking is scoped to the requested goal and workspace.
- `GoalService.evaluate` exposes the ranking **without** changing the goal's
  status/progress; an unsatisfied manual criterion remains active.
- `GoalRunService` -> `GoalRunRouter` consume the durable ranking on the
  production decision path.
- Supervisor-gated API set/clear and any-signed-in read on
  `GET/PUT/DELETE /api/goals/{id}/utility`; member writes are 403.

## Reproduction

```bash
cd backend
/Users/rushiparikh/projects/atom/backend/venv314/bin/python -m pytest \
  tests/test_goal_utility_target.py \
  tests/test_goal_run_service.py \
  tests/test_goal_journey_gaps.py \
  tests/test_goal_run_routes.py \
  tests/core/test_agent_objective.py \
  tests/core/test_agent_environment_harness.py \
  tests/test_goal_run_loop.py \
  -q --tb=short \
  --junitxml=../docs/acceptance/evidence/goal02_utility_target_20261106/focused-review2-junit.xml
```

Corrected result: **111 passed, 0 failed, 0 skipped**
(`focused-review2-junit.xml`; 31 new GOAL-02 controls + 80 existing controls).
Original result at `e0469141c`: 109 passed (`focused-junit.xml`).

Baseline comparison for the unrelated `test_objective_evidence_flow.py`
(not imported by this change; same 12 pre-existing failures on both trees):
`changed-objective-evidence-junit.xml` (12 failed / 41 passed) and
`baseline-objective-evidence-junit.xml` (12 failed / 41 passed). Existing
baseline results are reused because the review fix does not touch that path.

## Boundaries / limits

- Controlled consumer tests, not served model inference or a served multi-model
  qualification.
- Utility metrics are durable `GoalRun` counters (`human_interventions`,
  `steps_executed`, `replan_count`), not arbitrary business revenue metrics.
- The supplied independent probe
  `/private/tmp/test_lead_utility_metric_bounds.py` could not be executed
  directly from this shell because external-path execution was denied; its
  defect classes are covered by equivalent in-tree controls. The later
  PR707 100+ candidate finding is also covered in-tree.
- This is not final acceptance; a separate reviewer decides.
