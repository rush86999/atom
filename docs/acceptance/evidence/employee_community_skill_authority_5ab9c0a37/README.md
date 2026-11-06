# ORACLE-01 — community-skill reviewer authority repair

Status: **submitted for independent verification.** This is the bounded
authority repair on the community-skill promote/delete family. The exact
`SkillExecution` material CAS, audit receipt, replay and result-state controls
from `5eb3cf626` remain; the new repair binds the current reviewer principal in
the decision transaction.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-skill-review-20261105` |
| Prior submitted tests | `5eb3cf626` (product `f8477493c`, evidence `5efb59b75`) |
| Repair product source | `f751fd80f265b2de44231a040cd85dac35a37d8f` |
| Executed repair source | `5ab9c0a37f0f80fe99f29175bfa726d6ecfcd3fa` |
| Accepted admin base | `9d73552d249ae8ec5b05af77546faf9621bbcd47` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | real scratch SQLite with fresh sessions; two-session authority interleaving; no live code sandbox/model/provider |

## Finding and repair

The request-entry `User` object was only a snapshot. The service checked role
and active state from that object, and the guarded target CAS did not bind the
current reviewer authority. A concurrent deactivation, demotion or tenant
reassignment after the target read could still let the decision commit (and the
audit use the stale tenant).

The repair:

1. `_resolve_actor(db, actor)` reads the authoritative `User` row and freezes
   `id`, `email`, `role`, `status`, `is_active`, raw `tenant_id` and the
   effective personal tenant (`resolve_tenant_id`). Missing, inactive,
   non-`active`, or below-TEAM_LEAD actors are refused before any effect.
2. `_claim_actor(db, authority)` executes a guarded no-op `UPDATE User` binding
   the frozen id/is_active/status/role/raw-tenant in the **same transaction** as
   the target `UPDATE`/`DELETE` and `AuditLog` receipt.
3. A zero-match rolls back all attempted target/audit work, preserves the peer
   principal and target row, appends no audit, and returns a safe 401/403/409
   `effect=none` refusal.
4. Both routes retain the explicit `get_current_user` dependency and
   `require_role(UserRole.TEAM_LEAD)`; the service check is defence in depth.

## Scope and transitions

| Method | Path | Effect |
|---|---|---|
| POST | `/api/skills/promote` | `Untrusted` community skill -> `Active`; already-Active new operation = 200 no-change/effect-none; unsupported status 409 |
| DELETE | `/api/skills/{skill_id}` | conditional community row delete; missing 404; tombstone replay `already_applied`; stale 409 |

Material binding: id, prior status, `skill_source`, target `skill_id`, row
tenant/agent/workspace, `input_params`, `security_scan_result` and
`sandbox_enabled`. Cloud rows are invisible.

Receipt/result states: verified, already_applied, no_change, conflict
(`ALREADY_PROMOTED`/`STALE_TARGET`/`UNSUPPORTED_STATUS`), not_applied
(`effect=none`), committed_unverified and effect_unknown. The existing
`AuditLog` is the ledger; no new table or migration.

## New authority twins

`tests/test_skill_review_write_contract.py` now covers:

- promote and delete × actor deactivation and tenant move after the target read
  but before the guarded authority claim;
- each returns 401/403/409 with `verification.effect="none"`;
- the target row remains `Untrusted`, and zero decision audit rows are
  appended.

The prior 34 decision/route controls, including TEAM_LEAD/admin twins,
member/viewer/guest refusal, same-operation replay, changed material, stale
peer edits, audit rollback/readback/unknown and audit tampering, remain.

## Controls

- **Focused community-skill gate: 46 passed on Python 3.14 and 3.11**
  (`focused-314.log`, `focused-311.log`): the prior 42 controls plus 4
  authority-change twins.
- **Affected skill/registry/review/audit selection: 272 passed, 4 failed
  baseline on both versions** (`affected-314.log`, `affected-311.log`). The
  same selection on `9d73552d2` gives 234 passed and the same 4 failures
  (`baseline-314.log`, `baseline-311.log`). The branch adds 38 passing controls;
  failure lists are identical.
- The 4 are pre-existing missing `api.package_routes`/`api.marketplace_routes`
  import errors in `test_round22_marketplace_security.py`, unrelated to the
  skill decision routes.

## Boundaries

- No import/execute/list/get/episodes/learning-progress changes.
- No live skill/code sandbox, Docker, model, provider, credential, spend,
  send, download or deployment operation.
- No new table, migration or second review/approval/authorization engine.
- PostgreSQL runtime/soak, multi-worker serialization and whole-app ORACLE-01
  remain open.
- The repaired scoped-memory and tool-mutation branches are independent and not
  merged.

## Artifacts

`focused-*.log`, `affected-*.log`, `baseline-*.log`, `source-tree.txt`,
`README.md`, `TEST_RESULTS.md`, `verification.json`, `routes.json`.
`MANIFEST.json` records the SHA-256 of every artifact and source file.
