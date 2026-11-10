# Exact NULL/{} material in public custom agent creation

Status: **submitted for independent review.** No merge or self-acceptance.

## Confirmed finding on PR833 head `b36bd760b`

The public `POST /api/agents/custom` create decision collapsed an omitted
JSON field (`null`) and an explicit empty object (`{}`) through `or {}` in
both the request digest and `_create_state_material`. A replay using the other
value on the same `operation_id` returned **201 already_applied** instead of
**409**. A post-commit NULL↔{} mutation could not refute the original receipt.

Root probe excerpts on the unchanged source:

```
test_null_to_empty_request_is_changed_material[configuration]  -> 201, expected 409
test_null_to_empty_request_is_changed_material[schedule_config] -> 201, expected 409
```

Our own failure-first reproduction (`probe-before.log`) also exposed the
post-commit mutation negatives in this environment: **4 failed / 2 passed**
(the two unchanged replays passed).

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/web-goal14-agent-create-null-repair-20261110` |
| Base | `b36bd760b1fa060e43f9468c0f47109ec84270f0` |
| Code commit | `71edf465f` |
| Runtime | real scratch SQLite + FastAPI route + scratch JWT; no live DB/model/provider |

The original PR833 branch and evidence packet are untouched.

## Product repair

`backend/core/agent_decision_write_service.py`:

1. **Request digest preserves the exact submitted value.**
   `_create_config_digest(configuration)` and
   `_create_schedule_digest(schedule_config)` no longer use `or {}`. `None`
   and `{}` produce different request digests, so changing only that field on
   the same operation id returns `409 OPERATION_CONFLICT`.
2. **Stored state preserves NULL.** The create inserts `sqlalchemy.null()`
   when the request omitted the field, instead of letting the column default
   turn it into `{}`. An explicit `{}` stays `{}`.
3. **State readback uses the physical value.** `_stored_json_value` maps a
   pre-flush SQL `Null` expression (and readback `None`) to `None`, leaving a
   dict untouched. `_create_state_material` therefore binds NULL vs `{}`
   exactly.

The replay path is unchanged apart from the material it binds: same
operation/material → `201 already_applied`; changed request → `409`; changed
stored state → `503 AGENT_COMMITTED_UNVERIFIED`.

## Controls

`backend/tests/api/test_agent_create_goal14.py` now covers:

| Control | Result |
|---|---|
| Changed request NULL→{} (configuration and schedule_config) | 409 |
| Changed request {}→NULL (configuration and schedule_config) | 409 |
| Post-commit stored NULL→{} refutes receipt (both fields) | 503 |
| Post-commit stored {}→NULL refutes receipt (both fields) | 503 |
| Unchanged NULL request replays once | 201 already_applied |
| Unchanged {} request replays once | 201 already_applied |
| Scheduler runs only on the first verified create, not replay/conflict | pass |
| Forged body identity/scope/tier ignored | pass |
| Concurrent actor demotion refused | 409 |
| Member without AGENT_MANAGE forbidden | 403 |
| Changed name on same operation conflicts | 409 |

Failure-first: `probe-before.log` — **4 failed / 2 passed**.
After: `probe-after.log` — **6 passed**; `create-controls-after.log` —
**15 passed**.

## Affected selection

`affected-after.log` — **216 passed, 1 failed**. The one failure is
`tests/test_agent_confidence_baseline.py::TestConfidenceBaseline::test_marketplace_declared_intern_gets_score_in_band`,
a pre-existing source-literal assertion against untouched
`core/agent_marketplace_service.py` (same failure on the PR833 base).

## Boundaries

- Real scratch SQLite only; no PostgreSQL/soak/multi-worker qualification.
- No live model, provider, credential, send, spend, download, deployment or
  live-administrator change.
- No new dependency, table or migration.
- No scope, role, maturity or scheduler policy change.
- No test deleted, skipped or xfailed.
- No merge or self-acceptance; root review remains independent.
