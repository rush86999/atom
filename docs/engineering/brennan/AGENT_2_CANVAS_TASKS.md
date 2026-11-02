# Agent 2 tasks: user-authored canvases

Source: [USER_AUTHORED_CANVASES.md](https://github.com/rush86999/atom/blob/main/docs/engineering/USER_AUTHORED_CANVASES.md)

Sequencing: this is an addendum for **after** the current outcome-mapping,
discount-resolution and commercial-readback repairs close. It is recorded here
as a task/contract note; this repair batch does not expand the canvas runtime.

## Agent 2 scope

| Area | Agent 2 task |
|---|---|
| Provider bindings | Map declared canvas fields to registered connector capabilities (`connected.*`), not to ad-hoc provider clients. |
| Version/provenance receipts | Supply provider/account/org/workspace identity, stable resource ID, version, retrieved time, typed fields/units, citations, coverage/continuation and access outcome. |
| Action mapping | Bind a canvas action to a named registered operation with allowed targets/fields, current authority and payload/attachment digests. |
| Remote readback | Verify the complete commercial object (see `AGENT_2_READBACK_VERIFICATION.md`); preserve remote identity and reconcile without a second effect. |
| Sandbox boundary | Declared custom-code runtime unavailable => explicit refusal, no host-execution fallback. |
| Authority | Canvas title/labels/rendered text/generated JavaScript cannot grant an operation or certify a fact. |

## Shared contracts to reuse (no parallel engine)

- `core/action_registry.py`
- task lifecycle / assignment executor
- existing teaching journal
- capability-canvas and mini-app manifests/instances
- provider receipts and the commercial readback verifier

## Required controls that touch Agent 2

- Unknown widget/action, forged derived total and out-of-scope record are
  refused by server validation.
- Renamed/reordered fields preserve identity and meaning.
- Missing/ambiguous units or required values create a targeted obligation.
- Answering an obligation resumes the same job; duplicate answers add no work.
- Concurrent edit, changed source and changed rule invalidate stale execution
  and stale provider action bindings.
- Restart preserves state, history, artifacts and operation identities.
- Canvas/mini-app content cannot expand authority or silently promote teaching.
- Declared custom-code runtime unavailable is an explicit refusal.

## Acceptance canvases (later batch)

1. Industrial quote.
2. Service proposal.
3. Non-sales exception/reconciliation queue.

All three must be created through ordinary interfaces on one build with no
domain-specific core edits. Provider-side controls use the same registered
`connected.*` actions and readback verification as the current business flows.

## Status

Captured 2026-11-01. Not started beyond this task note; current batch remains
focused on the blocking pricing/readback/outcome repairs.
