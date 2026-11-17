# Audit Evidence & Correction Requests

Status: implemented for F1/F2/F3/F6 of the audit/correction slice. F4
(approval `modified_params` snapshot) and F5 (Learning history/reason) remain
separate OPEN gaps and are NOT changed here.

Research basis (narrow concepts only, no certification claim):

- OWASP Logging Cheat Sheet — event context/correlation, access control, and
  "no secrets in logs".
- W3C PROV-O — a revision/request derives from the original entity; the
  original is not rewritten.
- NN/g progressive disclosure + visibility of system status — the result is
  primary; evidence is optional, and recorded/requested is never shown as
  applied/verified.

## 1. Read scope (one predicate for all four endpoints)

`backend/core/audit_access.py` owns the single SQL predicate used by
`GET /api/audit/{events,executions,executions/{id},summary}`.

| Caller | Rows visible |
|---|---|
| Ordinary member (current, ACTIVE) | `AuditLog.user_id == caller.id` only |
| Supervisor (TEAM_LEAD+ current role) | every user's rows in the caller's CURRENT workspace |
| Cross-workspace execution | `404` (never data), even by exact id |
| Unbound historical row (`user_id IS NULL`) | not assigned to an arbitrary member |
| Deactivated/suspended/deleted account | `403` before any read/write |
| Nonexistent token subject | `401` |

Rules that do not change:

- Authority comes from a fresh `User` re-read, not the token/body. A stale
  role, workspace, owner field or tenant id in the client is ignored.
- Personal/null workspaces (`None` / `""` / `"default"`) keep the existing
  Personal-Edition compatibility (via `core/personal_scope.py`), but a caller
  with a real workspace never falls into that shared bucket.
- Execution ids are matched exactly. LIKE metacharacters are escaped and the
  parsed `agent_execution_id` is re-checked, so `%`/`_` cannot broaden a read.
- An execution timeline for a member requires owner evidence (a scoped audit
  row). An `AgentExecution` row alone is not ownership. The supervisor
  no-events fallback remains for legacy runs in the same workspace.
- Read-side redaction reuses `blueprint_sanitizer.strip_credentials` and
  `experience_marketplace.sanitizer.redact_secrets`. Stored rows are unchanged.

The frontend renders `401/403/404/422` as honest permission/scope messages and
reserves "Audit service unreachable" for actual transport failures.

## 2. Correction requests (recorded, never applied/verified)

There is no new correction store or engine. A request reuses:

1. `POST /api/reasoning/feedback` → the existing `AgentFeedback` row;
2. `core/agent_action_audit.log_correction_request` → one existing-writer
   `agent_action`/`correction_requested` row tied to the subject execution.

Flow:

- The subject must be an audit row and/or execution visible under the same
  audit read scope. Validation happens BEFORE feedback is written, so a
  refused request leaves no half-recorded dispute.
- The COMPLETE subject is validated as one linked server-known object:
  - An owned audit row with no recorded execution supports an event-only
    correction. Supplying an execution id for that unbound event is refused
    (422) — an unrecorded event/execution link is never inferred.
  - Every supplied execution id is authorized independently of the event
    (visibility + agent). Matching an event's recorded id does not make a
    foreign run readable.
  - When the event records an execution, the submitted id must equal it; the
    receipt's `subject_execution_id` is always the recorded id.
  - `run_id` must agree with the proven execution.
  - A submitted step (`subject_step_number` or `step_number`) must belong to
    the proven execution; an unknown step is refused, not silently recorded.
- Claimed agent/execution/audit ids must agree; an arbitrary URL, path or
  unknown channel is rejected (422).
- The audit receipt carries `status="requested"`, `applied=false`,
  `verified=false`, the feedback id, actor, timestamp, reason and (when
  present) `channel` + `channel_target_id`.
- A channel target is only a **proven** link when the exact
  `(channel, target_id)` pair appears in allowlisted metadata the server
  recorded for the subject (the event, its bound execution, or that
  execution's scoped events). Otherwise the receipt records
  `channel_target_basis="caller_asserted_unverified"` and
  `repair_link_proven=false`; the UI does not render it as a linked review
  channel. No new target registry is introduced.
- Correction requests never stamp a canvas: canvas chat-feedback remains
  ordinary-thumbs behaviour, so a caller-named canvas id cannot be mutated
  through the correction path.
- Retries are idempotent: the existing feedback dedup key includes the audit
  subject, and the receipt is reused if already written.
- If the audit link cannot be written, the response says
  `feedback_recorded_audit_unavailable`; it does not claim a link.
- If a subject has no supported/validated repair channel, the UI says so.
  Recording a request never executes code or data repair. Activity, Learning,
  assignment reconciliation and Auto-Dev still own any actual change and
  their existing approvals/fences apply.

Supported channel links are built server-side from a channel allowlist plus a
validated id (letters/digits/`.`/`_`/`:`/`-` only): Activity
`/goal-runs/{id}`, Learning `/learning?thread={id}`, Assignments
`/assignments?agent={id}`, Auto-Dev `/agents`. No free-form URL is stored or
rendered.

## 3. Evidence and identity honesty

- `llm_call` audit rows record the **router-requested label** (often a tier or
  alias), not a provider-echoed served model. The API exposes
  `model_identity.recorded_label` with `label_kind="router_tier_or_alias"`
  and `served_model=null`. Missing labels are `unknown`.
- A served model is shown only when existing server provenance recorded it:
  `AgentExecution.metadata_json["model_provenance"]` and
  `AgentReasoningStep.requested_model/resolved_model`.
- Cost comes only from recorded `TokenUsage` rows, in ONE grouped query per
  page (no N+1):
  `recorded_estimate` / `partial` / `known_free` / `unavailable`.
  None of these is invoice price or a certification.
- Verification stays tri-state from the existing oracle columns:
  `verified` (step-level oracle), `partially_verified`, `unverified`,
  `failed_verification`, `not_recorded`, `unavailable`. A successful run
  status never turns into "verified". `verification_evidence` is rendered in
  an optional "Evidence" disclosure; an explicit `unverified` /
  `verification unknown` badge replaces the old silent-no-badge state.
- Audit rows are not independently re-verified by the audit reader; run
  status is labelled `recorded_execution_status`.

## 4. Bounded evidence download

`frontend-nextjs/lib/audit-export.ts` serializes the SAME authorized timeline
payload the UI rendered:

- `format`, `generated_at`, `source_app_version` (or `unknown`);
- `execution_id`, `read_scope`, `filter_window`, `row_count`;
- `rows` (exact API payload), `execution`, `counts`;
- `integrity` with signed/hash-chain/tamper-evident/completeness all `false`
  and a literal limitation statement;
- `coverage` with the scope note and explicit missing-row caveats.

No credentials, unread source bodies or other users' rows can enter the file:
the backend already scoped and redacted the payload. Exporting does not
rewrite history and preserves the original event plus any correction link.
There is no server export route and no hash chain for `saas_audit_logs`;
adding one is a separate, larger change with its own tamper test.

## 5. UX and request-count notes

Default request count is unchanged:

| Path | Before | After |
|---|---|---|
| `/audit-trail` mount | 1 × summary + 1 × executions | same (test locks it) |
| Poll while open | 2 reads / 15 s | same |
| Selecting a run | 1 × timeline | same |
| Correction submit | n/a | 1 × POST, only on user submit |
| Evidence download | n/a | 0 network; client serialization of the loaded payload |

Render delta on the evidence surface: the scope badge, one disabled/enabled
download button, one report button per visible timeline event, and the
timeline header status line. Agent Workspace adds one small flag button per
step plus the explicit verification badge/evidence disclosure; those are the
requested honesty signals, not extra task confirmation. No new wizard, modal
or default request is introduced. Unit tests cannot measure real render or
task time — the root must record API/browser latency and task time before and
after with the running app.

Per the owner request, the Audit Trail nav entry is now available to ordinary
members (capability `activity`) instead of being hidden behind the supervisor
minimum level. The release scope now agrees with that surface: `/audit-trail`
is mapped to `activity` in both the backend product profile and the frontend
core fallback, so a direct link and the Activity nav entry render the explorer
instead of the deferred-scope page. Admin, forensics, owner-cockpit, system
status and self-healing harness routes stay `governance` (deferred in core).
The backend still enforces the audit read/correction scope.

## 6. Verification performed vs. what the root must run

Automated (unit/API, this slice):

- Real SQLite + real bearer JWT + the route's fresh `User` re-read.
- Owner/member/supervisor/cross-workspace/nonowner/unbound/deactivated/
  nonexistent/stale-role/wildcard-id negatives; personal default positive.
- All four endpoints share the scope; timeline-only fallback is supervisor
  and same-workspace.
- Correction request links the actual feedback/execution/audit ids, survives
  a cold session read, is idempotent, refuses foreign/mismatched subjects,
  and always reports `applied=false`, `verified=false`.
- Frontend: 403 vs network vs 404 copy, optional evidence, LLM label honesty,
  tri-state verification, prefilled correction form, recorded-vs-applied,
  export payload fidelity, default fetch count.

Not performed here (root/independent review must do it):

- Browser end-to-end against a running backend + real world: ordinary member
  opens Activity/Agent Workspace/Audit Trail, records a request, reloads,
  restarts both processes, and confirms the receipt persists.
- Real API/browser latency, render count and task-time before/after. Unit
  tests cannot claim zero UX impact; the expected delta is one user-initiated
  POST only on submit.
- Screenshot/keyboard pass at mobile/desktop widths and screen-reader labels.
- The documented `saas_audit_logs` tamper limitation (no hash chain) remains.

## 7. Remaining gaps (separate owners)

- **F4**: `intervention_service` still overwrites `HitlAction.params` in
  place; the original reviewed snapshot is not preserved. Not touched here.
- **F5**: Learning correction reason/history and four-eyes review remain with
  the conversation-learning worker. Not touched here.
- No regulated-compliance, e-signature, independent-reviewer, retention or
  "certified complete" guarantee is made.
