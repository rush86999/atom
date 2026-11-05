# ORCH-01 — persisted workflow blueprint from a plain-language request

2026-11-05, America/Toronto.

**Status: demonstrated at controlled upstream/SQLite scope with one small
two-case served qualification on the already-configured local Ollama route.**
A plain-language request produces a validated, reviewable workflow blueprint
with a durable workflow id; reading that id in the same tenant/workspace after
a fresh session returns the exact committed definition. Generation does not
execute the workflow or activate a recurring trigger.

| Item | Value |
|---|---|
| Original source | `7bda6a25f` |
| Repaired source | `b7e67f49a` |
| Branch | `codex/orch01-blueprint-20261105` |
| Base | `81c5962bd` |
| Served route | `ollama/llama3.1:8b` via `127.0.0.1:11436` |
| Profile | `workflow_blueprint` v2026-11-05.1 |
| Served qualification | **2/2 accepted**, 2 model calls total |
| Served latency | 16.18 s / 12.78 s |
| Served usage | 1,608/371 and 1,603/332 prompt/completion tokens |
| Fresh-session readback | **exact** (definition digest, nodes, steps) |
| Focused affected tests | **647 passed** on Python 3.11.16 and 3.14 |
| Workflow neighborhood | **443 passed** |
| ORCH-01 / checkpoint controls | **25 passed** |
| Independent contract probes | **3/3 passed** |

## Product contract

### Validated blueprint

The model returns a typed `WorkflowBlueprintDraft`. The server, not the model,
owns:

- unique node ids and stable dependency references;
- no self-dependency, dangling dependency or cycle;
- exactly one start node and the recurring-trigger rules;
- explicit action kinds (`read`, `compute`, `notify`, `write`, `approval`);
- allowlisted service/action references; unknown references are refused;
- effect class derived from the trusted binding, not the model's read/write
  label or arbitrary metadata;
- missing-capability refusal (no silent integration fallback);
- a mandatory `approval_required` node/step before every governed mutation
  (`entity` changes, `write` or `notify` actions);
- compilation into the existing `WorkflowStep` representation;
- an explicit `execution_ready` / `execution_blockers` decision: unbound
  skill/agent capabilities make the design reviewable but non-executable and
  unregistered.

A model-supplied action on a trigger is ignored as design metadata; the trigger
is a start marker, not an effect. A skill/agent node maps to the existing
business-agent execution step, never to an external universal integration.

### Durable scope and readback

The design is stored in the existing `workflows` / `workflow_steps` tables:

- the exact authenticated tenant is stored in `Workflow.tenant_id`;
- the authenticated workspace is stored in the existing JSON `configuration`;
- the authenticated user is stored as the designer;
- status is `designed`, not active;
- the read route filters by tenant and workspace and returns 404 for any
  foreign/unknown id.

`GET /api/v1/workflows/generated/{id}` (and the compatibility
`GET /api/v1/workflows/{id}`) read from the database, not the in-memory
orchestrator. A fresh session returns the same `definition_digest`, nodes,
steps, start step and trigger metadata.

The response includes a reviewable `blueprint` object, `nodes`, ordered
`steps`, `hitl_gates`, `definition_digest`, `execution_ready`,
`execution_blockers`, scope/provenance and `registration.registered`. The
requested trigger metadata is retained in the blueprint/readback, but the live
orchestrator definition is registered with `triggers=[]` so design cannot
activate it. Only an execution-ready design is registered; unbound designs are
kept reviewable and unregistered.

The actual checkpoint consumer now calls the synchronous governance contract
correctly, treats `PENDING_APPROVAL` / `WAIT_FOR_APPROVAL` as waiting, stops
on `BLOCKED` / rejected / expired / failed without dispatching descendants,
and forces a durable server-required approval even when agent maturity would
otherwise return `APPROVED`. A context completion guard prevents duplicate
continuation from re-dispatching the downstream governed effect.

### Failure contract

No fallback/template is presented as a model blueprint. Invalid model output,
model unavailability, no-suitable route and timeout produce typed safe
responses and no persisted workflow:

- empty request → `workflow_request_empty` (422), zero model calls;
- malformed/empty/unknown-type/unknown-action → `workflow_blueprint_invalid`
  (422);
- duplicate/dangling/cyclic/multiple-start/trigger-rule failures → typed 422;
- missing capability → `workflow_capability_missing` (422), no runnable object;
- timeout → `workflow_blueprint_timeout` (504);
- no-suitable/unavailable → `workflow_blueprint_no_suitable_route` /
  `workflow_blueprint_unavailable` (503).

Forged body `tenant_id`/`user_id` values are ignored. A foreign workspace or
tenant read returns 404.

## Served qualification

The controlled contract was frozen first. The HTTP route and persistence
boundary were exercised by the controlled tests with a doubled transport.

The served harness called `Queen._workflow_blueprint_prompt` and then
`pinned_structured_call` directly; production `generate_workflow_blueprint`
calls `self.llm.generate_structured_response`. They share the prompt, schema,
compiler and persistence service, but they are **not the exact same generation
consumer**. The recorded cases are therefore **candidate-generation plus
service-persistence evidence**, not served HTTP or exact production-method
qualification. The two calls were serialized; no expected blueprint was
supplied and no provider was added.

Recompiling the captured raw candidates with the repaired compiler
(`served-candidates-recompiled.json`, no inference) shows both are reviewable
designs with HITL gates, but `execution_ready=false`: their skill capabilities
are not bound to a registered business agent. They are not registered as
runnable workflows. The execution-ready entity/checkpoint path is covered by
the controlled contract tests.

1. Service intake/review (one-off): intake → triage → notify reviewer →
   record review decision. The server inserted two approval gates (notify and
   write).
2. Inventory/operations review (recurring): weekly schedule trigger → collect
   counts → compare thresholds → update stock review. The server inserted one
   approval gate before the write. The trigger is present in the blueprint and
   absent from the live orchestrator triggers.

Both cases returned accepted, persisted, exactly readable blueprints. Actual
structured prompts, raw completions, usage, routing and readback are in
`served-qualification.json`; the run log is `served-qualification.log`.

A first protocol attempt in the default structured TOOLS mode returned a
function-call envelope and no parsed blueprint. The existing structured
transport's explicit JSON mode was used; the failure is preserved as
`served-protocol-negative.log`. No provider/route was added or substituted.

## Negative controls

- empty request, malformed/empty nodes, unknown node type and unknown action;
- unknown service/action references; metadata `action=create` under a read
  label;
- duplicate ids, dangling dependency, cycle, multiple starts;
- recurring without a trigger and invalid trigger metadata;
- missing capability and unbound capability (reviewable design, no
  registration);
- actual governance `PENDING_APPROVAL`, `BLOCKED`, rejected/expired and mature
  `APPROVED` states; no descendant dispatch before a valid approval;
- duplicate continuation dispatches exactly one downstream effect;
- forged body identity and foreign workspace/tenant read;
- timeout and generic model failure;
- repeated model calls bounded to one per request.

## Verification

- `focused-314.log` / `focused-311.log`: **647 passed** on each version.
- `workflow-neighborhood.log`: **443 passed** (included in the 647).
- `tests/test_orch01_workflow_blueprint.py` plus
  `tests/test_orch01_checkpoint_contract.py`: **25 passed**.
- Independent contract probe: **3/3 passed**.
- Served candidates: **2/2 compiled/persisted**, exact readback; recompiled as
  reviewable non-executable designs because their skill capabilities are
  unbound. This is candidate-generation/service-persistence evidence, not
  exact production-method/HTTP qualification.
- No model-authored execution plumbing, no workflow execution and no trigger
  activation during generation.

The two `TestWorkflowSchedulerCriticalNodes::test_execute_job_runs_*` timing
tests fail identically at baseline `81c5962bd` in this environment because the
background scheduler has not completed before the assertion; they are outside
ORCH-01 and are excluded from the focused selection. No production
eligibility/context gate was weakened.

## Limits

- Controlled SQLite and one local served route. PostgreSQL runtime
  qualification, other providers, served multi-model comparison, live
  connector breadth, Linux/KVM and soak remain separate.
- This is workflow **design** and readback, not execution quality, fleet
  recruitment, scheduling reliability or general model competence.
- Historical tags/counts and accepted feedback/wait/employee evidence remain
  unchanged.
