# ORACLE-01 — verified tool-mutation review decisions

Status: **submitted for independent verification.** This is the bounded
successor to the seven-route admin privilege/budget repair. It covers exactly
the two Auto-Dev tool-mutation decision routes plus the parallel sandbox writer.
The remaining Auto-Dev surfaces and whole-app ORACLE-01 remain open.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-evolution-review-20261105` |
| Accepted auth/2FA base | `95f7bcac1a0375b4f0465a77e15130f68fc9665d` |
| Product source | `eaba0cb8f551796677a8c516155a4be7399207ff` |
| Executed source (product + tests) | `e4816e59c84041333c7571988ebf5da90f1dc1ce` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | real scratch SQLite with fresh sessions; controlled interleaving/fault seams |
| Model/provider/browser calls | none |

The admin repair remains independent at product `5fbb377a4`; it is not merged
into this branch and its acceptance is not assumed.

## Scope

| Method | Path | Handler | Service |
|---|---|---|---|
| POST | `/api/autodev/mutations/{mutation_id}/approve` | `approve_tool_mutation` | `core.evolution_review_write_service.review_tool_mutation` |
| POST | `/api/autodev/mutations/{mutation_id}/reject` | `reject_tool_mutation` | `core.evolution_review_write_service.review_tool_mutation` |

Parallel writer:

| Component | Effect |
|---|---|
| `AlphaEvolverEngine.sandbox_execute_mutation` | pending/failed → passed/failed, guarded by exact material and prior status |

`ToolMutation` is tenant-scoped: `id`, `tenant_id`, `parent_tool_id`,
`tool_name`, `mutated_code`, `sandbox_status`, `execution_error`, `created_at`.
There is no workspace/agent column on the mutation itself.

## Authority and scope

- Both decision routes now use `require_role(UserRole.TEAM_LEAD)`, matching the
  existing list/skill review surface. The service independently reads the
  actor row, freezes id/role/status/active/tenant, and conditionally claims the
  actor in the same transaction as the mutation.
- A member, viewer or guest is refused by the route gate. An anonymous request
  is refused by authentication. A TEAM_LEAD+ actor from another tenant is
  refused before target lookup.
- The target is resolved by `(mutation_id, tenant_id)` from
  `get_current_tenant`; a missing or foreign-tenant mutation is a 404 with zero
  effect. No tenant or workspace is inferred from request content.

## Decision contract

### Exact transitions

- **Approve:** allowed from `pending` or `passed`; result `approved`.
  `failed` is refused 409 (a sandbox-failed mutation cannot be approved), and
  an existing `approved`/`rejected` is a competing decision unless the request
  is the exact same-operation replay.
- **Reject:** allowed from `pending`, `passed` or `failed`; result `rejected`.
  An existing `approved`/`rejected` is a competing decision unless the request
  is the exact same-operation replay.
- Any other prior status is refused 409 with zero effect.

### Material binding

The guarded `UPDATE` binds the exact:
mutation id, tenant id, prior sandbox status, tool name, parent tool id,
execution error (nullable-exact), and mutated code. The receipt also binds a
keyed digest of the mutated code and execution error. A peer edit to any of
those fields, or a peer decision, matches zero rows and returns a typed 409;
the peer's state is preserved.

### Durable receipt and result states

The existing `AuditLog` (`saas_audit_logs`) table is the operation ledger; no
new table or migration was added. The audit row id is the server-owned
operation id (`autodev:tool-mutation:<supplied-or-generated>`). Metadata
contains the operation id, decision, prior/result status, actor id/role, tenant
id, target id, tool/parent identity, code/error digests, material digest and
result digest. No raw mutated code, execution-error text, SQL parameter or
exception message is stored in the receipt or returned in the response/logs.

- Same operation id and same material: HTTP 200 `already_applied`, with no
  second status write and one audit row.
- Same operation id with a different decision or material: typed 409
  `OPERATION_CONFLICT`.
- Different operation id after an `approved`/`rejected` decision: typed 409
  `ALREADY_REVIEWED`.
- A later material revision after the original decision: 503
  `committed_unverified` with `effect=committed` and `do_not_repeat`.
- A confirmed local rollback (audit constraint failure, no original
  operation): HTTP 409 `not_applied`, `verification.effect="none"` and
  `TOOL_MUTATION_TRANSACTION_ROLLED_BACK`; target and audit are absent.
- A post-commit audit/target readback failure: 503
  `committed_unverified`, `effect=committed`, original operation identity.
- A genuinely lost commit confirmation: 503 `effect_unknown`,
  `effect=unknown`, original identity, `do_not_repeat`, and no exception text.
- A wrong audit row (action, actor, tenant, workspace, success, security level,
  resource, decision, prior/result status, target, code/error digest, material
  digest or result digest) is never certified: 503 with `refuted` or
  `unavailable`.

Ordinary success remains HTTP 200 and the existing `success`/`data`/`message`
shape, with additive `verification`, `operation_id` and `audit_id` metadata.
Refusals keep 403/404/409/422; uncertainty is 503.

## Parallel sandbox writer

`AlphaEvolverEngine.sandbox_execute_mutation` previously wrote
`passed`/`failed` unconditionally. It now:

- pre-checks `approved`/`rejected` and returns a non-recording result
  (`skipped=true`, `reason="review_decision_present"`) without invoking the
  sandbox;
- pre-checks any other non-`pending`/non-`failed` status and does not execute;
- captures the exact mutation material before the external sandbox call and,
  when the caller's session has no pending work, releases its read transaction
  so it does not block a reviewer;
- after execution, conditionally updates only where the id, tenant, prior
  status, tool name, code and execution error still match; a racing review or
  peer edit matches zero rows and is not recorded;
- returns the existing `success`/`output`/`proxy_signals` shape plus
  `skipped`/`status`, and only writes `passed`/`failed` on a successful guard.

## Caller / consumer map

| Caller or consumer | Action in this slice |
|---|---|
| `list_candidates` | Retained TEAM_LEAD+/tenant list; decided items leave the selected status. |
| `approve_tool_mutation` / `reject_tool_mutation` | Replaced unconditional writes with the verified decision service. |
| `AlphaEvolverEngine.sandbox_execute_mutation` | Guarded to pending/failed only; can never overwrite a decision. |
| `check_auto_synthesis_readiness` | Retained; counts `passed` only. |
| `advisor_service` | Retained; reports passed/failed counts. |
| `capability_gate` | Retained; counts daily mutations, not review status. |
| `guidance` | Retained; broadcasts pending proposals. |
| Skill review/apply routes | Untouched accepted reviewed-improvement contract; included in affected regression. |

## Controls

- **Focused decision gate: 47 passed on Python 3.14 and 3.11**
  (`focused-314.log`, `focused-311.log`): 39 new failure-first decision tests,
  5 rewritten Auto-Dev route tests, and 3 sandbox-gap controls.
- **Affected Auto-Dev selection: 747 passed, 28 failed baseline on both
  versions** (`affected-autodev-314.log`, `affected-autodev-311.log`). The
  failed-test list is byte-identical to the accepted base `95f7bcac1`
  (`baseline-autodev-95f7-*.log`).
- **Affected evolution selection: 293 passed, 29 skipped, 1 failed baseline on
  both versions** (`affected-evolution-*.log`), with the same single baseline
  failure as `95f7bcac1` (`baseline-evolution-95f7-*.log`).
- **Affected reviewed-improvement/audit selection: 63 passed on both
  versions** (`affected-review-audit-*.log`), identical to baseline.
- The new decision matrix covers: TEAM_LEAD+ and admin twins; member/viewer/
  guest/anonymous refusal; missing/foreign target; foreign-tenant actor;
  approve pending/passed and refuse failed; reject pending/passed/failed;
  competing decisions; same-operation idempotence; same-operation changed
  decision; later material revision; stale material before claim; authority
  demotion before claim; sandbox after approve/reject; sandbox/review race;
  pending/failed sandbox writes; audit constraint rollback `effect=none`;
  post-commit readback `committed_unverified`; lost confirmation
  `effect_unknown`; 14 audit-tamper variants; and code/error non-leakage.

### Baseline exclusions

The 28 Auto-Dev and 1 evolution baseline failures reproduce exactly on
`95f7bcac1`:

- `tests/test_covpush_autodev_comms.py` — 14 pre-existing LanceDBHandler /
  ReflectionEngine API-drift controls.
- `tests/test_covpush_w84c_autodev2.py` — 8 ReflectionEngine API-drift controls.
- `tests/test_covpush_w82a_autodev.py` — 3 pre-existing DynamicBenchmarkFetcher
  controls.
- `tests/test_covpush_autodev2.py` — 3 ReflectionEngine API-drift controls.
- `tests/test_auto_dev/test_reflection_engine.py` — 1 pre-existing pattern
  grouping control.

The failure lists are identical to the base worktree at `95f7bcac1`; see
`baseline-reflection-95f7.log` and the paired baseline logs. No baseline
failure is in the new decision service, the two decision routes or the sandbox
guard.

## Boundaries

- No live model, provider, credential, spend, send, download, deployment,
  administrator/account/budget or PostgreSQL/soak operation was used.
- No second review/approval/audit/operation engine; the existing `User`,
  `UserRole`, `ToolMutation`, `AuditLog` and tenant mechanisms are reused.
- No schema change or migration; no new table.
- No live PostgreSQL runtime, multi-worker serialization or whole-app
  ORACLE-01 qualification.
- Accepted canvas/auth-2FA/ORCH-01/feedback/wait/employee lanes and historical
  model scores remain unchanged.
- The admin repair at `5fbb377a4` remains on its own branch and is not a
  dependency of this slice.

## Artifacts

`focused-*.log`, `affected-autodev-*.log`, `affected-evolution-*.log`,
`affected-review-audit-*.log`, `baseline-*-95f7-*.log`,
`baseline-reflection-95f7.log`, `source-tree.txt`, `README.md`,
`TEST_RESULTS.md`, `verification.json`, `routes.json`.
`MANIFEST.json` records the SHA-256 of every artifact and source file.
