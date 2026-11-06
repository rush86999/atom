# ORACLE-01 — verified agent-marketplace seller publication

Status: **submitted for independent verification.** This is the bounded local
marketplace mutation family: packaging a trained agent into one `AgentTemplate`
listing. Remote SaaS push and remote install are separate external-effect routes
and remain out of scope.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-marketplace-20261105` |
| Accepted admin base | `9d73552d249ae8ec5b05af77546faf9621bbcd47` |
| Accepted admin product | `5fbb377a4e1eef8fdd0013275cd8b1c9b278cd41` |
| Product source | `fb5091069f7ce55882bfb85c23dac2d26a6730eb` |
| Executed source (product + tests) | `7530ce554af4dc8ae3695ab016650e0bcf6479f4` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | real scratch SQLite; no external SaaS/network/model/provider call |

## Scope

| Method | Path | Handler | Effect |
|---|---|---|---|
| POST | `/api/agent-marketplace/agents/{agent_id}/publish` | `publish_agent_for_sale` | insert one local `AgentTemplate` listing |

The durable target is the existing `agent_templates` row created by the
existing packaging service. No new table or migration is introduced.

## Authority and scope

- Retains mandatory `get_current_user`; the existing owner-or-admin policy is
  preserved.
- The service re-reads the current `User` row, requires active status, and
  permits the agent's `user_id` owner or an ADMIN+ user.
- Current actor status/is_active/role/raw tenant is claimed in a guarded no-op
  `User` UPDATE in the publication transaction.
- The exact source `AgentRegistry` material is loaded fresh and claimed in a
  guarded no-op UPDATE in the same transaction: id, tenant, owner, workspace,
  name, description, category, specialty, status and configuration JSON.
- A peer source edit, actor deactivation/demotion or lost admin role matches
  zero rows and returns `effect=none`; no listing/audit commits.
- The listing inherits the source agent's tenant. The route accepts no tenant
  or workspace input.

## Exact effect contract

- Existing packaging rules are preserved:
  - marketplace-managed agents cannot be re-published;
  - a paid listing requires at least one verified achieved goal run;
  - prompts/playbooks/guidance/verified record are derived as today;
  - credentials are stripped, PII redacted and entity names tokenized.
- `package_agent_for_sale` gains an internal `commit=False` flush path and
  accepts the exact source snapshot; its default public behavior is unchanged.
- The listing is inserted with `is_public=True`, `is_approved=True`,
  `is_active=True`, the source tenant and the acting author.
- One `AuditLog` receipt commits in the same transaction. A confirmed failure
  rolls back both the listing and the audit.
- Same operation id + same request material -> `already_applied`; changed
  material -> 409; missing/different listing -> `committed_unverified`.

## Receipt and result states

Operation id: `agent-marketplace:publish:<supplied-or-generated>`. Metadata
contains operation id, action, event type, source agent id, result template id,
prior/request/result digests and actor id/role/tenant. No raw system prompt,
configuration, playbook, memory bundle, credential, secret or SQL parameter is
stored in the receipt or logs.

- `verified`: `success`, `template_id`, `verified_record` plus additive
  verification/operation_id/audit_id.
- `already_applied`: same operation/material; one receipt.
- `conflict` (409): paid gate, marketplace-managed agent, stale source,
  changed operation or authority change; `effect=none`.
- `not_applied` (409): confirmed local rollback; `effect=none`.
- `committed_unverified` (503): post-commit readback failed/refuted.
- `effect_unknown` (503): lost confirmation; original identity, no exception
  text.

## Caller / parallel-writer map

| Caller or consumer | Action |
|---|---|
| `publish_agent_for_sale` route | verified publication service |
| `AgentMarketplaceService.package_agent_for_sale` | retained; internal no-commit path and exact source snapshot |
| `AgentRegistry` source row | exact guarded no-op claim |
| `AgentTemplate` listing | inserted once per operation |
| sale-readiness / listing reads / remote install / push | unchanged and out of scope |
| `AuditLog` | additive safe receipt |

## Controls

- **Focused: 23 new decision controls passed on Python 3.14 and 3.11**
  (`focused-314.log`, `focused-311.log`).
- **Affected marketplace/packaging/runtime/audit selection: 211 passed, 7
  skipped, 24 failed baseline on both versions** (`affected-314.log`,
  `affected-311.log`).
- **Baseline at `9d73552d2` (without the new contract file): 188 passed, 7
  skipped, the same 24 failures on both versions** (`baseline-314.log`,
  `baseline-311.log`). The branch adds exactly 23 passing controls; failure
  lists are byte-identical.

The 24 baseline failures are pre-existing and unrelated to this route:

- 23 `test_covpush_w69_marketplace.py` workflow-marketplace router controls fail
  on the accepted base from their existing app/fixture setup;
- `test_agent_marketplace_service.py::TestSkillInstallation::test_install_agent_handles_template_not_found`
  already fails with the `int(Mock)` template-not-found path.

All reproduce exactly on the accepted admin base.

The new matrix covers owner/admin publication, member and anonymous refusal,
listing fields/tenant inheritance, raw prompt omission, missing/managed agents,
paid gate with the existing explanatory message, achieved-run paid success,
replay/changed material/missing listing, stale source, authority deactivation/
demotion, audit rollback, post-commit readback, lost confirmation and 11
audit-tamper variants.

## Boundaries

- No push-to-SaaS, remote install, browse, sale-readiness or listing-read
  changes; no external marketplace/network/credential operation.
- No live agent/model/provider/credential/spend/send/download/deployment.
- No new table, migration or second marketplace/approval engine; `AgentTemplate`,
  `AuditLog` and the existing packaging service are reused.
- No change to accepted admin/auth-2FA/canvas/feedback/wait/employee/ORCH-01
  lanes or the submitted review/memory/skill/agent/goal/document/workflow-
  template branches.
- PostgreSQL runtime/soak, multi-worker serialization and whole-app ORACLE-01
  remain open.

## Artifacts

`focused-*.log`, `affected-*.log`, `baseline-*.log`, `source-tree.txt`,
`README.md`, `TEST_RESULTS.md`, `verification.json`, `routes.json`.
`MANIFEST.json` records the SHA-256 of every artifact and source file.
