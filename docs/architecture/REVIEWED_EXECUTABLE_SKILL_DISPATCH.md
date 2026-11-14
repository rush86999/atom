# Reviewed executable skills — ordinary agent dispatch

Status: implemented and unit/integration verified on scratch state (2026-11-14).
Scope: a narrow, reviewed executable exception for benign deterministic code.
It is not a general "generate and run code" path.

## What changed

Before this change an approved executable skill could only be run by calling
`POST /api/skills/execute` (or `SkillRegistryService.execute_skill` directly).
A model could see the skill's name in its prompt but had no normal tool to
invoke it.

The approved artifact is now reachable on the ordinary agent tool surface:

| Surface | What it does |
|---|---|
| `skills.list` | Metadata-only list of reviewed executable skills approved for the current tenant + workspace + employee. |
| `skills.execute` | Re-resolves the model-supplied skill **name** at dispatch time and delegates to the existing `SkillRegistryService.execute_skill` authority. |
| Prompt skills block | For a reviewed executable skill, advertises name/description plus the `skills.execute` call shape. The generated code is never included. |
| `WORKSPACE EXECUTABLE SKILLS` | Names the reviewed executable skills currently invocable by this employee, so the model can invoke them even when keyword retrieval is weak. |

Both actions are registered in `core/action_registry.py` via
`core/skill_actions.py`, appear in `mcp_service.get_all_tools`, and are in
`GenericAgent.CORE_TOOLS_NAMES`. `skills.execute` is a level-2 (INTERN+)
governance action; `skills.list` is level 1.

This follows mature harness practice: MCP tool discovery is model-controlled
and clients list tools then call them
(<https://modelcontextprotocol.io/specification/2025-06-18/server/tools>);
Agent Skills load name/description metadata first and run code without the
source entering context
(<https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview>).

## Authorization order (no bypass)

1. **Server-owned scope.** `GenericAgent._step_act_unaudited` stamps
   `handler_context["_skill_scope"]` from its own runtime identity
   (`agent.id`, `workspace_id`, `tenant_id`). Model arguments cannot set it.
2. **Discovery.** `SkillRegistryService.list_invocable_skills` returns an
   entry only when the registry row is `community`, `Active`, sandbox-enabled,
   and its durable binding matches the exact tenant/workspace/employee. The
   linked `Skill` row must be `type == "script"`, carry the same binding, be
   assigned to the workspace via `workspace_skills`, and the row's stored
   review revision/digest are reported as metadata.
3. **Resolution.** `resolve_invocable_skill` accepts the workspace
   `Skill.name`, the registered package name, or the registry execution id.
   Ambiguous or unknown identifiers are refused rather than guessed.
4. **Artifact authorization.** `SkillRegistryService.execute_skill` re-checks
   the binding, current candidate digest, review revision/digest, linked
   `Skill.code`, the single python block in the package, and the caller scope.
   Any refusal raises **before** a `SkillExecution` row is created and
   **before** `HazardSandbox` is constructed.
5. **Execution.** Only then is the reviewed source embedded with the fixed
   harness and sent to the Docker sandbox. There is no subprocess fallback.
6. **Receipt.** The durable `SkillExecution` row carries the reviewed
   executable receipt: binding/review digests, input/result hashes, sandbox
   backend, container id, network/read-only flags, cleanup outcome and the
   per-execution nonce echo.

## Tenancy and assignment

- Reviewed bindings include `tenant_id`, `workspace_id` and `agent_id`; an
  entry bound elsewhere is not advertised and re-authorization refuses it.
- `workspace_skills` is the product assignment. Removing the assignment stops
  discovery and dispatch.
- `skills.list` / `skills.execute` refuse a request-only/RPC context (no
  employee scope). They are agent dispatch actions, not a new human API.

## Evidence limits (what the tests do and do not prove)

Covered by `backend/tests/test_reviewed_executable_skill_agent_dispatch.py`:

- real approve/apply routes and candidate/Skill/SkillExecution rows on a
  scratch in-memory DB (`TESTING=1`);
- the real action registry, MCP dispatch wrapper, `GenericAgent._step_act`
  governance, a fresh DB session, and durable receipts;
- a positive run through normal dispatch (`skills.execute`) with the expected
  computed result and nonce receipt;
- denial before the sandbox for: changed candidate material, removed registry
  binding, unreviewed community skill, cross-workspace scope, and manual
  RPC-style scope (tripwire sandbox proves zero leaf calls);
- the final ReAct model request contains `skills.execute` and the skill name,
  and does not contain generated code.

Simulated / not proven here:

- **Docker is simulated** in this control by the deterministic in-process
  stand-in already used by the executable controls (same wrapper + nonce).
  The real container lane remains
  `backend/tests/test_reviewed_executable_skill_docker.py` and the service
  restart lane `test_reviewed_executable_service_restart.py`.
- **The model choice is not a live-provider run.** The test asserts the tool is
  advertised and that dispatch works when the tool is called; it does not
  measure whether a particular served model selects it unprompted.
- **The security scanner is stubbed** to deterministic LOW, as in the prior
  executable acceptance controls. No provider or network call is made.
- The reviewed policy is still a narrow AST allowlist for pure computations:
  no imports, filesystem, network, classes, decorators or lambdas.
- This does not widen the existing community-skill, package-install, workflow
  or mini-app execution paths, and it does not add a subprocess path.

## Running the evidence

```bash
cd backend
TESTING=1 <python> -m pytest -q \
  tests/test_reviewed_executable_skill_agent_dispatch.py \
  tests/test_reviewed_executable_skill.py \
  tests/test_reviewed_executable_agent_consumption.py
```

`TESTING=1` must be set before the interpreter imports backend modules. The
tests create their own in-memory engine; they never read the live dev DB.
