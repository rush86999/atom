# User-authored canvases and deterministic employee interaction

Implementation addendum to the [two-agent work orders](brennan/README.md).
This is a feasible extension, not a claim of existing end-to-end qualification.
Finish the current outcome, pricing and readback repairs before expanding their
runtime surfaces. Design contracts and fixtures can proceed independently.

## Product outcome

An end user creates a useful workspace application: quote worksheet, service
proposal, invoice exception queue or another supported business form. The user
and employee operate on the same durable state. Values entering execution and
learning have explicit identity, validation, source and revision.

A canvas is an interaction surface, not an authority boundary. Its title, labels,
rendered text or generated JavaScript cannot grant an operation or certify a fact.

## Reuse the two existing execution paths

- [Capability canvases](../../backend/core/canvas_capability_service.py) provide
  installed operations, typed table bindings, deterministic rules, authorization
  and versioned assessments. Extend supported declarative forms/components here.
- [Mini-app service](../../backend/core/mini_app_service.py) provides manifest,
  logic/test versioning, blueprint publication and installed instances.
- [Mini-app runtime](../../backend/core/mini_app_runtime.py) preserves sandboxed
  custom code execution. Its production Firecracker path requires Linux/KVM;
  local docker-dev is explicitly development-only. Do not silently fall back to
  host execution to make an authoring demo pass.
- Reuse the [action registry](../../backend/core/action_registry.py), existing
  task lifecycle/executor and teaching journal. No third app/task/learning store.

Simple forms/tables can use registered native capabilities without arbitrary
custom code. Full custom logic continues through the existing mini-app runtime.
Align blueprint/instance and receipt contracts across these surfaces rather than
routing every native form through a VM or bypassing sandbox requirements.

## Required contract

Extend existing manifests/envelopes with equivalent semantics; do not create a
parallel engine merely to use these field names.

| Area | Required semantics |
|---|---|
| Definition | Stable blueprint ID, manifest/schema version, logic/rule revision, installed component types and registered operations |
| Instance | Canvas/instance ID, authenticated owner/workspace, employee binding, state revision and explicit resource bindings |
| Field | Stable field ID, type, required/null semantics, units/currency, source/user/derived provenance, editability and validation |
| Execution input | Server-read values, accepted instance/definition/state/source/teaching revisions, evidence and complete digest |
| Action | Named registered operation, allowed targets/fields, current authority and payload/attachment bindings |
| History | Validated edit, actor, before/after revisions, reason, affected jobs and prior results |
| Learning | Explicit fact resolution versus proposed method/mapping/format lesson, context, provenance and accepted revision |

Use schema validation with bounded collections/strings/nesting and explicit
handling of unknown fields. Client validation is convenience; server validation
is mandatory. Reject invalid values rather than silently truncating or repairing.

Derived fields are recomputed server-side. A browser-supplied total, hidden field
or read-only widget value is not trusted. Preserve zero versus missing, finite
Decimal arithmetic, units and explicit conversion authority. Field identity must
survive relabeling/reordering; widget position is not identity.

## End-user authoring journey

1. Create a blank application canvas from the normal UI or a described need.
2. Select supported layout/components; generated proposals use the same validator.
3. Bind authorized records/files or declare explicit user-input fields.
4. Configure calculations, validation, rules and permitted actions through guided
   controls; unsupported operations remain visibly unavailable.
5. Preview with sample inputs and independent expected outputs.
6. Save/version the definition and instantiate it with fresh scoped state.
7. Attach an employee and run a task from the validated state.
8. Answer an obligation inside that instance; resume the same task.
9. Correct values or teaching, inspect history and reopen after restart.

Keep draft definition, valid saved state, running job, pending clarification,
proposed action and confirmed effect visually distinct. A disabled button is not
server enforcement. An arbitrary canvas name does not acquire executable methods.

## Deterministic execution and revision control

The employee reads structured state through the existing authenticated capability
API, not screenshots or DOM scraping. Build an input receipt from the authoritative
server snapshot. Persist it with the task/operation. Revalidate current access and
accepted revisions immediately before effects.

An edit must use the existing revision/CAS pattern. A changed state or definition
invalidates affected derived outputs and stale action bindings; preserve earlier
results. Recompute only dependent work. An active job must not silently adopt a
changed blueprint, rule or input while retaining approval for the old payload.

Repeated/concurrent submissions use a stable request/operation identity. Restart
reopens the same instance and task. An uncertain external operation reconciles
without another effect. User-authored rules never create broader standing authority.

## Learning boundary

Distinguish these user actions:

- **Supply a fact:** resolve one typed requirement for a subject/task.
- **Correct a value:** update instance state with provenance and invalidation.
- **Teach a reusable method:** propose/review an explicit scoped lesson using the
  existing teaching mechanism and permitted deterministic method contract.
- **Change authority:** separate authenticated permission/grant operation.

A successful edit or calculated result is not automatically a standing lesson.
A user's correction may create a reviewable lesson candidate, preserving context,
source/field identity and revision. Wrong-context, stale or conflicting lessons
must refuse reuse. Promotion must not silently retrain other employees/businesses.

## Agent ownership

Agent 1: normal authoring UI, shared capability manifest/state APIs, typed input
receipt consumption, obligations in new canvases, teaching/correction and history.
Agent 2: provider bindings and version/provenance receipts, mapping app actions to
registered connector capabilities, remote readback/reconciliation. Name one editor
before shared schema/runtime/migration changes. Arbitrary code runtime changes
require their own explicit scope and qualification.

## Acceptance and usefulness

Create at least three differently shaped canvases through ordinary interfaces:
industrial quote, service proposal, and non-sales exception/reconciliation queue.
Use one build with no domain-specific core edits.

Required controls:
- Supported new canvas works without developer-authored per-instance Python.
- Unknown widget/action, forged derived total and out-of-scope record are refused.
- Renamed/reordered fields preserve identity and meaning.
- Missing/ambiguous units or required values cause a targeted question.
- User answer resumes the same job; duplicate answer produces no duplicate work.
- Concurrent edit, changed source and changed rule invalidate stale execution.
- Restart preserves state, lessons, history, artifacts and operation identities.
- Browser/mini-app content cannot expand authority or silently promote teaching.
- Declared custom-code runtime unavailable: explicit refusal, no unsafe fallback.

Measure utility with a user unfamiliar with the harness: can they create the
canvas, understand a question, obtain the independently checked result, correct
it and find the history? Record time, errors and manual interventions separately
from schema/test passes. Do not certify usefulness from rendered screenshots alone.

Sources: [JSON Schema object validation](https://json-schema.org/understanding-json-schema/reference/object),
[MCP risk annotations and trust](https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/).
A manifest describes requested capability; trusted server policy authorizes it.
