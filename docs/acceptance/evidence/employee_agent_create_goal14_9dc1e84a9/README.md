# Verified public custom agent creation — current authority, exact material, durable receipt

Status: **submitted for independent verification.** No merge or deployment was
performed.

## Confirmed finding on base main `0d5132c2e`

`POST /api/agents/custom` created an `AgentRegistry` row and committed
directly. It had no operation identity, durable `AuditLog` receipt, replay
protection, or commit-time actor claim. The route permission check ran once;
a concurrent demotion after that check still returned 201 and created the
agent. The response also omitted `operation_id`/`audit_id`.

The failure-first controls captured both defects on the unmodified route:

```
tests/api/test_agent_create_goal14.py::test_custom_create_forged_body_is_ignored_and_receipt_replays FAILED
  KeyError: 'operation_id'
tests/api/test_agent_create_goal14.py::test_custom_create_refuses_concurrent_actor_demotion FAILED
  assert 201 == 409
tests/api/test_agent_create_goal14.py::test_custom_create_member_is_forbidden PASSED
```

Log: `failure-first.log` — **2 failed / 1 passed**.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/web-goal14-agent-create-20261110` |
| Base main | `01b554c55045334fa562cd2858c278f5bb3e1545` |
| Executed source | `9dc1e84a9` (rebased onto base main; no conflicts) |
| Runtime | real scratch SQLite + real FastAPI route + real scratch JWT; no live model/provider |

The repair reuses the merged agent-decision engine (`update/promote/delete/
run/replace/stop`), including its current-authority claim, audit/replay
machinery and tenant/workspace policy. No parallel mutation engine, store or
auth system was added.

## Route and contract

| Method | Path | Handler | Service |
|---|---|---|---|
| POST | `/api/agents/custom` | `api.agent_routes.create_custom_agent` | `core.agent_decision_write_service.create_agent` |

### Authority and scope

- Route permission remains `require_permission(Permission.AGENT_MANAGE)` plus
  `get_current_user`.
- The service re-reads the current `User`, requires active status and
  `WORKSPACE_ADMIN+` (the same policy that grants `AGENT_MANAGE`).
- The create transaction claims `is_active`/`status`/`role`/raw tenant/raw
  workspace in a guarded no-op UPDATE. A concurrent change returns
  `409 AUTHORITY_CHANGED` with `effect=none` and creates nothing.
- The created row uses the actor's resolved tenant/workspace. Forged body
  `tenant_id`, `workspace_id`, `user_id`, `status`, `maturity` and
  `confidence_score` fields are ignored; the request model does not accept
  them as authority.

### Exact effect

- Forces `AgentStatus.STUDENT` and `NEW_AGENT_CONFIDENCE` (0.35, below the
  INTERN floor). No forged maturity can skip training.
- Remains create-only: no name-based upsert, no new unique-name policy, and
  no retro-demotion of existing agents.
- Writes one `AuditLog` action `agent_created`, event type `create`, in the
  same transaction, with operation id, request digest, prior/result digests,
  actor id/role/tenant and target scope. No raw configuration, schedule or
  secret is stored.
- Verifies the receipt and the exact created material from a fresh session.
- Same operation/material replays idempotently (`already_applied`,
  `do_not_repeat`); changed material on the same operation id returns
  `409 OPERATION_CONFLICT`; a missing target/receipt readback returns
  `503 committed_unverified`.
- Scheduler is called only after the first verified create; never on replay.

## Focused result

`focused-311.log` — **4 passed**:

- forged body identity/scope/tier ignored, row forced STUDENT/current scope,
  receipt durable, replay does not duplicate;
- concurrent actor demotion refused with 409 and no row/receipt;
- member forbidden with 403 and no row;
- same operation id with changed material conflicts with 409 and does not
  create a second row.

## Affected selection

`affected-311.log` — **216 passed, 1 failed**. The single failure is
`tests/test_agent_confidence_baseline.py::TestConfidenceBaseline::test_marketplace_declared_intern_gets_score_in_band`,
which asserts the source literal `confidence_score=0.55` in
`core/agent_marketplace_service.py`. That file is untouched by this diff and
the same assertion fails on pristine `origin/main`
(`baseline-main-confidence.log`). It is not caused by this candidate.

## Remaining create/registration family reconciliation

This slice closes only the public custom-create alias. The other create/
registration surfaces were reconciled but are **not** repaired here:

| Surface | Current behavior | Remaining gap |
|---|---|---|
| `POST /api/agents/guided` | Any employee self-serve; forces STUDENT/0.1; agent-initiated creation goes through the governance trust/HITL gate | Direct commit with no operation id, durable `AuditLog` receipt, replay, or commit-time actor claim; `acting_agent_id` is not re-validated at commit |
| `POST /api/agents/spawn` | Requires `AGENT_MANAGE`; `get_atom_agent()` is called with its default workspace; persisted spawns go through `register_or_update_agent` (create-or-upsert by module/class) | Caller scope is not bound (Atom default workspace/tenant); no operation id, receipt, replay, or claim |
| `AgentGovernanceService.register_or_update_agent` | Internal create-or-upsert used by spawn and other callers | Direct commit; no receipt/replay/claim; preserved as create-versus-upsert by design |

These are the next concrete Goal14 mutation candidates. They are reported
truthfully rather than force-enabled or silently folded into this slice.

## Boundaries

- Real scratch SQLite only; no PostgreSQL/soak/multi-worker qualification.
- No live model, provider, credential, send, spend, download, deployment or
  live-administrator change.
- No new table or migration.
- No test deleted, skipped or xfailed.
- No merge or deployment; independent review remains required.
