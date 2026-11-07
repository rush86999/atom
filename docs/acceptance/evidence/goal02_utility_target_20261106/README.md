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
| Source checkpoint | `e0469141c884bfd37ebd152ade00f1e13b91fe91` |
| Baseline for comparison | `248a2329623b433e68104c4d89d2965683d81013` (`origin/main` in `/private/tmp/goal02-baseline`) |
| Interpreter | `/Users/rushiparikh/projects/atom/backend/venv314/bin/python` |
| World | per-test scratch SQLite files; `TESTING=1`; no live DB |
| Model/provider inference | **none** |

Source blobs (git blob ids at the source checkpoint):

| Path | Blob |
|---|---|
| `backend/core/goals/utility_target.py` | `c6d45de025361072887c37751fbe1c9ead26e56e` |
| `backend/core/agent_objective.py` | `246e6529bf6b12b38e7a91d6e9f8f55a21a9f7c2` |
| `backend/core/goals/goal_service.py` | `aa4bc59dc05f22ed50b36d0c549d8b8be26a6f5f` |
| `backend/core/goals/goal_run_router.py` | `c06b55e5324015be44277b63fcae72ce56875013` |
| `backend/api/goal_routes.py` | `5f69c4c1ea8b2dc93c79f0ea68d37238f9b74d0e` |
| `backend/core/action_registry.py` | `7d1e1a4cf6c68776f22d1142e6e8dc72370bb72f` |
| `backend/tests/test_goal_utility_target.py` | `ae54aabefca7e19e63ba8ed448ab1b8628e94dfc` |
| `docs/architecture/AGENT_ENVIRONMENT.md` | `2b326866012b9d77ca07f63d918e349b75336fb1` |

## What was verified

- Target definition is explicit and validated before any write; malformed
  targets are rejected.
- The target survives a fresh engine/service (restart simulation) and reaches
  `Objective.utility_target`.
- Two completed outcomes: higher normalized utility ranks higher for both
  `maximize` and `minimize` targets.
- failed/cancelled outcomes cannot win on a better metric; an explicit trusted
  `constraints_ok=False` candidate is withheld.
- Missing, non-finite, fractional, negative, string, bool, and float-overflowing
  huge count evidence is unknown (`utility=None`, no rank), not zero and not a
  crash.
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
  --junitxml=../docs/acceptance/evidence/goal02_utility_target_20261106/focused-junit.xml
```

Result: **109 passed, 0 failed, 0 skipped** (`focused-junit.xml`).

Baseline comparison for the unrelated `test_objective_evidence_flow.py`
(not imported by this change; same 12 pre-existing failures on both trees):
`changed-objective-evidence-junit.xml` (12 failed / 41 passed) and
`baseline-objective-evidence-junit.xml` (12 failed / 41 passed).

## Boundaries / limits

- Controlled consumer tests, not served model inference or a served multi-model
  qualification.
- Utility metrics are durable `GoalRun` counters (`human_interventions`,
  `steps_executed`, `replan_count`), not arbitrary business revenue metrics.
- The supplied independent probe
  `/private/tmp/test_lead_utility_metric_bounds.py` could not be executed
  directly from this shell because external-path execution was denied; its two
  defect classes are covered by equivalent in-tree controls
  (`test_negative_and_huge_counts_never_earn_a_rank` and the malformed/
  non-finite twins).
- This is not final acceptance; a separate reviewer decides.
