# Public spawned-agent creation — caller scope, exact material, receipt

Status: **frozen candidate submitted for independent review.** No merge or
self-acceptance.

## Scope

`POST /api/agents/spawn` durable `persist=True` path, its ephemeral
`persist=False` path, and the MCP `spawn_agent` consumer. Stacked on the
accepted guided branch `492e41ea1`; root integration worktree untouched.

## Confirmed gaps on `492e41ea1`

The route required `AGENT_MANAGE` but called `get_atom_agent()` with no caller
scope; the Atom instance defaulted to `workspace_id="default"` /
`tenant_id="default"`. Persist used
`AgentGovernanceService.register_or_update_agent`, which:

- upserted by `core.generic_agent`/`GenericAgent`, collapsing persisted
  spawns onto one row;
- dropped the template/custom `configuration` and `capabilities`;
- committed directly with no operation id, `AuditLog` receipt, replay,
  current-actor claim, or readback.

`persist=False` created an ephemeral object under the default Atom scope.
Ordinary spawn also called
`reset_maturity("atom_specialty_init", ...)` for template capabilities.

Failure-first on clean `492e41ea1` with only the new matrix present:
**10 failed / 1 passed** (`failure-first-base492.log`).

## Repair

`backend/api/agent_routes.py`:

- Resolve the authenticated user with
  `resolve_workspace_id(user)` / `resolve_tenant_id(user)` — no hardcoded
  `"default"` alias.
- Construct a request-scoped Atom (`get_scoped_atom_agent`) so factory
  settings/readers never borrow another caller's/default workspace.
- `persist=True` calls the shared create decision writer with exact template
  material and distinct operation identity; response includes
  `operation_id`/`audit_id`/`verification`.
- `persist=False` stays in memory and returns an honest `persisted: false` /
  `not_persisted` response with no DB row or audit.

`backend/core/atom_meta_agent.py`:

- `spawn_agent_decision` creates a distinct STUDENT agent with exact
  template/config/capabilities and caller identity through
  `agent_decision_write_service.create_agent`.
- `spawn_agent` persists via that decision when durable; no module/class
  upsert collapse; no `atom_specialty_init` reset.
- `get_scoped_atom_agent` constructs a request-scoped instance, never the
  process singleton.

`backend/integrations/mcp_service.py`:

- The MCP spawn tool uses the scoped factory for ephemeral spawn too.
- When a `user_id` is present, context workspace/tenant are checked against
  the user's authoritative scope and contradictions are refused **before**
  constructing an Atom.
- Persistent MCP spawn uses the shared decision writer with the authenticated
  user; no actor → fail closed.

## Root personal-scope followup

Runtime probe with the Personal-Edition constants temporarily moved off
`"default"` (`personal-scope-before.log`): **2 failed / 11 passed**. The route
captured `default` while the shared writer created `personal-ws/personal-tenant`.
The route now uses the existing personal-scope resolvers; the after run is
included in the 13 focused controls. No new default alias was added.

## Results

| Check | Result |
|---|---|
| Failure-first base 492 | 10 failed / 1 passed |
| Personal-scope probe before resolver fix | 2 failed / 11 passed |
| Focused route matrix after | **13 passed** (`focused-after.log`) |
| Spawn/MCP focused | **16 passed** (`spawn-mcp-focused.log`) |
| Spawn consumer focused | **41 passed** (`spawn-consumers-focused.log`) |
| Affected selection | **888 passed, 6 skipped, 9 deselected** (`affected-after.log`) |
| Additive CI step | **13 passed** (`focused-after.log`) |
| CI lane contract | **41 passed** (`ci-lane-contract.log`) |
| Clean-base unrelated failures | same 7 (`baseline-pre-existing-7.log`) |

The 9 deselections are the same 7 pre-existing failures reproduced on clean
`492e41ea1` plus two `fpdf`-missing environment tests
(`affected-environment-seams.log`). No new product failures.

## Controls

- ordinary caller scope (company/ws-a) and foreign admin scope (other/ws-b);
- personal/null workspace/tenant uses the effective personal scope for both
  durable writer and ephemeral factory;
- forged `custom_params` status/tier/confidence/user/scope/parent ignored;
- distinct operation ids create distinct agents (no generic upsert collapse);
- exact replay is idempotent; changed material/scope conflicts;
- concurrent actor demotion refused with zero child/audit/scheduler;
- NULL/`{}` configuration exact identity;
- PK-conflict rollback and unreadable readback uncertainty;
- `persist=False` no row/audit and honest non-durable response;
- `atom_specialty_init` unchanged by ordinary spawn;
- MCP context contradiction refused before Atom construction;
- existing spawn/Atom/MCP consumers retained.

## CI

Added `Run spawned agent authority and receipt controls` to
`.github/workflows/ci.yml` and the identical entry to
`backend/tests/fixtures/ci_backend_additions.json`. The immutable baseline
file is unchanged; the lane contract verifies the additive union.

## Boundaries

- Real scratch SQLite + FastAPI + real JWT; no live model/provider/DB.
- No budget/BYOK files, no new table/store, no dependency, no test weakening.
- Guided/root-integration worktrees untouched.
- PR is stacked on guided `492e41ea1`; no main-CI claim until root retargets.
- 143 claims / 18 goals unchanged.
- No merge or self-acceptance.
