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
fenced checkpoint/task-admission paths are untouched. Mount order note: the
legacy `api.agent_routes` router is included before `api.approvals_routes`, so
its `POST /api/agents/approvals/{id}` is the handler the web UI actually
reaches; the alias handler remains for direct/alias callers. Both now share
the same atomic claim (below).

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
* `revisions` (bounded, newest last) / `revisions_truncated`
* `history_complete` / `malformed_history_entries` / `history_unreadable`

Historical rows approved before this receipt existed have no recorded
original. They report `original_known: false`, `original_params: null`, and
the current `params` as `effective_params`; `modified` stays `null`. The code
never reconstructs a reviewed original from the rewritten column.

Malformed history material is preserved verbatim in the stored list. Invalid
list elements are never dropped, and a container that cannot be read is never
overwritten: the readback reports `history_complete: false` (plus
`malformed_history_entries` / `history_unreadable`) instead of claiming a
complete append-only chain. Appending a new revision keeps every existing
element in place and numbers the revision from the well-formed entries.

The read projection is redacted by default with the repo's existing
`core.blueprint_sanitizer.strip_credentials` (deep copy, credential-shaped
keys dropped). Raw values remain only in the protected HITL authority row.
This is a key-shape sanitizer, not a content/PII classifier, and not a
compliance claim.

## Atomic decision claim (both mounted writers)

A loaded-then-unconditional-`UPDATE` race let two reviewers both "approve" the
same pending row: the second write overwrote the first effective payload and
appended a second history entry (the independent counter run reproduced two
`success: true` decisions for different recipients, one retained receipt).

Both writers now share one fence:

* `api/agent_routes.py::decide_hitl_action` (the legacy route mounted FIRST at
  `/api/agents/approvals/{id}`) computes its historical MERGE payload and
  calls the shared claim.
* `api/approvals_routes.py` → `InterventionService.approve_intervention` /
  `reject_intervention` keeps its historical REPLACE payload and calls the
  same claim.
* Goal-run checkpoints and never-autonomous task admissions keep their own
  pre-existing atomic claims/bindings (untouched).

`resolve_decision_reviewer` re-reads the CURRENT actor (fresh session, not the
request token/object), checks canonical tenant/workspace scope and BOTH
persisted `required_role` locations, then `claim_fresh_reviewer` fences that
actor in the decision transaction. Personal/default is the one universal
actor fallback; a named-scope reviewer never crosses into another named or
unscoped row (404, so an id is never confirmed).

`claim_pending_decision` then issues ONE conditional UPDATE whose WHERE clause
requires: the row id, `status = 'pending'`, the same `action_type`,
`required_role`, `workspace_id`, `tenant_id`, `params` and `context_snapshot`
the reviewer was checked against. SET carries `status`, effective `params`,
`reviewed_by`, `reviewed_at`, optional `user_feedback` and the appended
history snapshot — so the decision, reviewer and receipt commit in the SAME
statement/transaction. A peer decision, payload rewrite, role/scope change or
snapshot revision makes `rowcount` 0 and the loser gets a 409
`DECISION_CONFLICT` / `AUTHORITY_CHANGED` without touching the row.

SQLAlchemy's JSON type stores Python `None` as JSON text `null`, not SQL NULL,
so the JSON predicates match `IS NULL OR CAST(... AS VARCHAR) = 'null'`.
Dialect trace (compile-only, no server run): PostgreSQL compares the non-null
`params` / `context_snapshot` predicates as `::JSONB` equality (semantic,
key-order independent); SQLite compares serialized text. A PostgreSQL run is
NOT claimed here — the permanent race controls execute on real file SQLite,
and the compiled PostgreSQL shape is pinned by a test.

## Usable readback (Approvals page)

`GET /api/agents/approvals/recent?limit=20` — bounded, permission-scoped list
of decided rows (id/action type/status/actor/time only; no params/snapshot) so
a reloaded page can discover a decision after it leaves the pending queue.

`GET /api/agents/approvals/{id}/history?revision_limit=10` — redacted
reviewed-vs-approved projection. Scope/permission is server-derived (fresh
active user, canonical tenant/workspace, supervisors see their scope, a member
only their own subject/reviewed rows). Cross-scope/guessed id → 404, in-scope
unauthorized member → 403, storage failure → 503 (never an empty success). The
protected `context_snapshot` is never returned and credential-shaped keys /
free-text secrets go through the existing sanitizers.

`pages/approvals.tsx` gains a "Decision history" section that reads nothing
until opened, then one lazy read per row. It shows the redacted original and
effective params, actual actor/time, optional reason, revision list, unknown
pre-history originals, and incomplete-lineage warnings. Approval status and
execution are rendered as distinct states: "approved" explicitly does not mean
executed or verified, and an `executed` row says execution is recorded but its
outcome is not verified by this history. The ordinary pending queue's API
shape, reads and action buttons are unchanged.

## Tests

`backend/tests/test_hitl_parameter_history.py` (23 tests, scratch file SQLite,
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
  refuses the reviewed original, and refuses a second consumption;
* two real sessions race approve/approve with different params: exactly one
  commits, the loser gets 409, one history entry, cold readback matches the
  winner, one downstream consumption;
* two real sessions race approve/reject: exactly one decisive outcome;
* reviewer role, activity, workspace and tenant drift between the authority
  read and the claim are refused, leaving the row pending and untouched;
* duplicate replay is a 409 conflict with no params/history rewrite;
* the legacy mounted route races two sessions and keeps its MERGE semantics;
* malformed stored history elements survive a new append and are reported as
  incomplete (never silently dropped);
* an unreadable history container is never overwritten and reports unknown;
* the read routes enforce scope/member policy (subject/reviewer/404/403),
  bound recent decisions and revisions, redact credentials and never export
  `context_snapshot`;
* storage failure is a 503 `HISTORY_UNAVAILABLE`, not an empty success;
* the claim fence compiles to semantic PostgreSQL JSONB equality (compile-only
  trace; no PostgreSQL run is claimed).

`frontend-nextjs/tests/pages/approvals-page.test.tsx` adds 8 client controls:
no history read before the section/row is opened; redacted original/effective
with actor, reason and status; executed kept distinct from verified; unknown
pre-history original; denied vs unavailable vs not-found; denied/unavailable
recent list; hostile text rendered literally; reload readback plus bounded
revision notice.

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
* The readback is an operational audit view, not a compliance export: it is
  unsigned, redacted by existing key/text sanitizers (not a PII classifier),
  bounded to a recent-decisions list plus the newest revisions per decision,
  and it never returns the protected `context_snapshot`.
* Race controls ran on real file SQLite in this packet. PostgreSQL semantics
  were traced by compiling the same conditional UPDATE for the PostgreSQL
  dialect (semantic JSONB equality; JSON-null equivalence) and pinned by a
  compile-only test; no PostgreSQL server run is claimed.
* `context_snapshot` is protected authority storage, not a public export; any
  future surface must use the redacted readback or its own sanitizer.

## References

Narrow design concepts only: OWASP Logging Cheat Sheet
(`https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html` —
actor/action/object/outcome context, no secrets in logs) and W3C PROV-O
(`https://www.w3.org/TR/prov-o/` — a revised entity derives from the original
and the deciding activity/agent is provenance). No schema mapping or
certification is implied.
