# Verified agent stop/cancel — scope, exact material and receipt

Status: **submitted for independent verification.** PR from
`codex/oracle01-agent-stop-20261106`. No merge or deployment was performed.

## Confirmed gap

The pre-existing stop route checked `AGENT_RUN` and then called
`AgentTaskRegistry.cancel_agent_tasks` directly. It did not bind the current
actor/tenant/workspace to a durable decision, compare exact agent material,
suppress a repeated cancellation on replay, or write an AuditLog receipt.
A retried request could cancel tasks that started after the first stop.

## Repair

- `/api/agents/{agent_id}/stop` delegates to
  `core.agent_decision_write_service.stop_agent`.
- Current authority is resolved at `MEMBER` minimum with `AGENT_RUN`; the
  agent must be visible in the caller's tenant/workspace. Cross-scope stop
  returns 404.
- The decision snapshots and compares exact agent material before cancellation:
  authority change returns `409 AUTHORITY_CHANGED`, target change returns
  `409 STALE_TARGET`.
- The existing `AgentTaskRegistry` remains the cancellation effect. No new
  task engine was added.
- Zero active tasks is `no_change` with `cancelled_tasks: 0` and **no**
  receipt.
- Replaying the same `operation_id` returns the recorded result and does not
  call `cancel_agent_tasks` again.
- After a successful cancellation exactly one AuditLog receipt is written,
  bound to the actor, operation, agent material and cancelled count.
- A receipt/commit failure after cancellation reports `effect_unknown`; it does
  not claim rollback or that no task was cancelled.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-agent-stop-20261106` |
| Base main | `66e09c5ee9f6693ab3a6e188bd50d03fae62bf39` |
| Source checkpoint | `6d7b453dc8e88813c3a142b1c88dd3c185a4872a` |
| Executed source | `1faccf71cf00f5a1d421ce67adca3f0f652066d2` |
| Runtime | scratch SQLite; in-process task registry fake; no live model/provider |

The executed source adds a test-only alignment commit on top of the source
checkpoint: two legacy stop-route tests now supply `get_agent_tasks` alongside
`cancel_agent_tasks`, matching the service preflight.

## Verification

| Gate | Candidate `1faccf71c` | Main `66e09c5ee` |
|---|---|---|
| Focused, 3.14 | **74 passed** | — |
| Focused, 3.11 | **74 passed** | — |
| Affected, 3.14 | **367 passed, 3 skipped, 2 failed** | 358 passed, 3 skipped, 2 failed |
| Affected, 3.11 | **349 passed, 1 failed** | 340 passed, 1 failed |

Delta: **+9 stop controls on both interpreters, zero new failures**.

### Shared baseline failures

- `tests/test_covpush_w29_governance.py::TestRegistry::test_register_new_agent`
  (both versions)
- `tests/contract/test_agent_api_contract.py::TestAgentListContract::test_get_agents_invalid_pagination`
  (3.14 only; the 3.11 environment lacks `schemathesis`)

They fail identically on exact main and are not claimed as repaired.

## Stop controls

`tests/test_agent_stop_scope_contract.py` collects **9** controls:

1. member stops own agent and writes exactly one receipt;
2. cross-tenant and cross-workspace stop refused (404, no cancel);
3. no tasks is no-change with no receipt;
4. replay does not cancel newly started tasks;
5. authority deactivation before claim refuses (effect none);
6. authority demotion before claim refuses (effect none);
7. target material change before claim refuses (409 `STALE_TARGET`);
8. receipt failure after cancellation reports `effect_unknown`;
9. missing agent is 404 with no cancellation.

The legacy stop route and coverage tests now exercise the matching preflight
and assert the returned cancellation count.

## Boundaries

- The task registry is an in-process fake in these controls. Real worker
  shutdown, OS process termination and multi-worker cancellation are not
  qualified.
- Scratch SQLite only; no PostgreSQL, soak or multi-worker qualification.
- No live model, provider, credential, spend, send, download or deployment.
- No merge or deployment; independent verification and code-owner review
  remain required.
