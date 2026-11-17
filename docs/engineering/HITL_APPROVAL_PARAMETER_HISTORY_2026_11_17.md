# HITL approval parameter history (F4)

**Date:** 2026-11-17
**Scope:** `core/intervention_service.py`, the two mounted HITL approval
surfaces, durable HITL readback. No new table, registry, or correction engine.

## Problem

The edit-before-approve flow rewrote `HITLAction.params` in place:

* `InterventionService.approve_intervention(..., modified_params=...)` replaced
  the row's params with the modified payload.
* The legacy `/api/agents/approvals/{id}` handler in `api/agent_routes.py`
  merged the modification into the same column.

That is required for execution consumers that re-read the row (for example
`WorkflowEngine._durable_step_approval` binds the current step payload to the
approved params), but it silently destroyed the payload the human was actually
shown. After the first approval there was no durable way to distinguish the
reviewed proposal from the effective one.

## Runtime path traced

| Surface | Path | `modified_params`? |
|---|---|---|
| UI approvals alias | `api/approvals_routes.py` → `InterventionService.approve_intervention` | yes |
| Legacy mounted handler | `api/agent_routes.py::decide_hitl_action` | yes (merge) |
| Workflow approval | `integrations/workflow_approval_routes.py` → same service | no |
| Messaging approval | `core/messaging_action_dispatcher.py` → same service | no |
| 2FA action verification | `core/auth_2fa_write_service.py` | no (status only) |
| Goal-run checkpoint | `core/hitl_resume.resolve_goal_run_checkpoint` | explicitly refused |
| Never-autonomous task admission | `core/review_decision_authority.py` | explicitly refused |
| Information wait | own atomic claim in `api/agent_routes.py` | own answer material |
| Durable workflow step | `core/workflow_engine.py::_durable_step_approval` | re-reads the row |
| Effect applied receipt | `core/governance_engine.py::mark_effect_applied` | read-modify-write of the snapshot |

The two `modified_params` writers now use the same receipt helper; the
fenced checkpoint/task-admission paths are untouched.

## Durable receipt

The existing `HITLAction.context_snapshot` JSON column is the history store
(the column already carries the policy role and execution bindings). A new
`parameter_history` list is append-only. Each entry is:

```json
{
  "revision": 1,
  "reviewed_params": {"...": "what the human saw"},
  "approved_params": {"...": "what execution will consume"},
  "modified": true,
  "modified_by": "<approver id>",
  "modified_at": "2026-11-17T10:14:22.123456",
  "reason": "optional approver note, or null"
}
```

`reviewed_params` and `approved_params` are deep-copied before the live
`params` column is rewritten, so caller/live nested objects are never aliased.
The helper appends rather than replaces: a re-decided row keeps every prior
revision. Existing `context_snapshot` keys (`required_role`, job/execution
bindings, `effect_applied`, ...) are preserved.

`action.params` still holds the exact effective payload. Execution consumers
that read the row therefore keep working; `workflow_engine` is locked by a
regression test that accepts the effective payload and refuses the reviewed
original.

## Readback contract

`core.intervention_service.describe_parameter_history(action)` returns:

* `original_known` / `original_params`
* `effective_params`
* `modified` / `revision` / `modified_by` / `modified_at` / `reason`
* `reviewed_by` / `reviewed_at`
* `history_entries` / `legacy_unrecorded` / `redacted`

Historical rows approved before this receipt existed have no recorded
original. They report `original_known: false`, `original_params: null`, and
the current `params` as `effective_params`; `modified` stays `null`. The code
never reconstructs a reviewed original from the rewritten column.

The read projection is redacted by default with the repo's existing
`core.blueprint_sanitizer.strip_credentials` (deep copy, credential-shaped
keys dropped). Raw values remain only in the protected HITL authority row.
This is a key-shape sanitizer, not a content/PII classifier, and not a
compliance claim.

## Tests

`backend/tests/test_hitl_parameter_history.py` (13 tests, scratch file SQLite,
no network/provider):

* modified approval keeps original + effective, policy snapshot preserved;
* unchanged approval records identical reviewed/effective values;
* rejection never rewrites params and creates no approval receipt;
* denied role / inactive actor / foreign route actor leaves no mutation;
* alias and legacy mounted routes both write the same receipt;
* alias response does not export credential-shaped params or the snapshot;
* duplicate decisions are idempotent and do not append a second receipt;
* engine dispose/reopen (cold session) still reads original + effective;
* nested caller/live params are not aliased into the receipt;
* receipt append-only when a row is decided again;
* legacy approved row reports the original as unknown;
* `WorkflowEngine._durable_step_approval` consumes the effective payload,
  refuses the reviewed original, and refuses a second consumption.

## Limits

* The generic chat agent loop resumes a paused tool call with its in-memory
  `authorized` arguments; it does not re-read `HITLAction.params` after the
  wait. Durable consumers that re-read the row (workflow step approval,
  assignment, etc.) do consume the effective payload. Rewriting the generic
  loop would move the payload past the already-run risk/governance checks and
  is deliberately out of this packet; that gap is reported rather than
  papered over.
* No mandatory reason modal, automatic retry, undo, hash chain, or
  certification is added.
* `context_snapshot` is protected authority storage, not a public export; any
  future surface must use the redacted readback or its own sanitizer.

## References

Narrow design concepts only: OWASP Logging Cheat Sheet
(`https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html` —
actor/action/object/outcome context, no secrets in logs) and W3C PROV-O
(`https://www.w3.org/TR/prov-o/` — a revised entity derives from the original
and the deciding activity/agent is provenance). No schema mapping or
certification is implied.
