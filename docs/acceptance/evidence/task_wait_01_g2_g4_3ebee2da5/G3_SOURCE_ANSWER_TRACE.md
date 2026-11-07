# G3 — authorized source-answer extension trace (proposal only)

Source: `3ebee2da5`. This is a trace/proposal for root review; no runtime or
UI implementation is included.

## Current Generic text answer

- `AgentInformationAnswer` (`backend/api/agent_routes.py:3438-3446`) requires
  `answer` and a required `correlation_id`.
- `answer_agent_job_information_wait` (`agent_routes.py:3449-3575`) loads the
  job, resolves the exact wait action, checks:
  - job/agent identity,
  - exact wait/correlation,
  - current workspace/tenant,
  - waiting actor or admin,
  - pending vs already-approved idempotence,
  then commits `HITLAction.user_feedback` with an atomic status update and
  calls `resume_information_wait_action` for the same job.
- The durable wait snapshot (`core/information_wait.py:40-62`) carries
  server-owned job/execution/agent/workspace/tenant/actor/subject/correlation.
  Recovery (`_recovery_binding`, lines 171-206) accepts only the snapshot-bound
  answer; it does not reconstruct authority from caller params.

## Current assignment source answer

- `EmployeeSourceAdd` (`backend/api/assignment_routes.py:153-155`) carries a
  source reference plus reason; `add_assignment_source`
  (`assignment_routes.py:2086-2373`) resolves it with
  `resolve_assignment_source`, adds a versioned source step, settles only the
  matching obligation, and continues the same assignment executor.
- `resolve_assignment_source` (`backend/core/assignment_resources.py:150-224`)
  supports:
  - `document_id`/`ingested_document_id` with workspace scoping and
    `IngestedDocument.source_content_hash` version equality/refusal;
  - `dataset_name` or `(source, external_id)` through the existing connected
    catalog;
  - filesystem paths only when `allow_internal` is explicitly enabled (public
    proposals are refused).
- It returns the current `source_version`, resource identity, path/representation
  and freshness. The assignment executor stores this in the source step's
  `resource_binding` and refuses stale versions at resolution/consumption.

## Minimal proposal (not implemented)

Extend the existing Generic answer body with an **optional typed source
reference**, for example:

```json
{
  "correlation_id": "<server-owned wait correlation>",
  "answer": "<short human answer or label>",
  "source": {
    "document_id": "<authorized document id>",
    "source_version": "<current source_content_hash>"
  }
}
```

or the existing `dataset_name` / `source`+`external_id` identity. Rules:

1. The exact job and correlation remain required; a source alone never selects
   or settles a wait.
2. Resolve through the existing `resolve_assignment_source` (public path
   disabled), using the authenticated actor and the wait snapshot's
   workspace/tenant/actor; reject foreign, stale, removed or scope-mismatched
   sources.
3. Read through the existing document/extraction/versioned-read path and bind
   the returned `source_version`/content hash into the existing HITL
   `context_snapshot`/params. No schema, store, router or second task engine.
4. Pass the authorized source text/reference plus binding into the same job's
   resume context (`information_answer`/`information_source`), so the real
   Generic consumer continues the same execution. A source upload alone,
   filename similarity, or an unrelated global upload must never settle a
   wait.
5. Keep the text-answer path unchanged; source answers are an additive
   authorized evidence route, not a replacement for text facts.

## Open design points for root

- Whether `answer` remains required as a short label or becomes optional when
  a source is supplied; recovery must remain snapshot-bound and idempotent.
- Exact source representation to hand to the model (bounded text/preview vs
  structured data) and its context-size bound.
- UI affordance for selecting/uploading a source against a displayed wait;
  this proposal intentionally does not implement broad UI.
- Negative twins needed: wrong job/correlation, foreign workspace/tenant,
  revoked grant, stale version, duplicate delivery, and source-only upload with
  no wait selection.
