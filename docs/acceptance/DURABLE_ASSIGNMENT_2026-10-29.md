# Durable, domain-independent employee assignments — 2026-10-29

Status: **local production-boundary controls passed; mocked external transport
and crash/restart controls passed. No live send, source writeback, credential
change or deployment is claimed.**

Baseline: `999b28afc` plus the owner's in-flight teaching/context and OAuth
work. R3 remains `expanded-core-2026-10-28-r3 → 68b949409`.

Recorded at implementation time: HEAD `999b28afc38debca03781f868224ac92eefe4ac2`,
44 working-tree entries (the owner's teaching/OAuth work plus this slice),
tag `expanded-core-2026-10-28-r3` present.

## What was built

One generic executor (`core/assignment_executor.py`) composes the existing
spine:

- `GoalRunService` records and runs (identity, plan, decision log, waits);
- `TaskLifecycle` revisions, operations, claims, questions, cancellation,
  uncertain outcomes and reconciliation;
- `TaskOperationRecord` database uniqueness;
- the shared applicability resolver (`core/artifact_teaching.py`);
- the action/integration registry (`core/action_registry.py`);
- existing artifact renderers and the Outlook/canvas email path;
- `task_outcome_contract` criteria and `build_task_outcome`.

The assignment plan lives beside the task revision and operations in the
existing GoalRun `task_lifecycle` record. No second workflow engine, queue,
database or business pipeline was added.

## Patch 1 — executable operation binding

**Confirmed defect:** the legacy operation hash covered only operation type,
requested-change text and parent operation. Two different recipients/bodies
under one idempotency key could not be distinguished by the reservation.

**Changed seam:** `core/task_lifecycle.py` now supports an optional,
versioned `operation_binding`:

- registered action name;
- authenticated workspace/account;
- task revision;
- validated arguments (deterministic JSON types only);
- artifact IDs/revisions/hashes;
- authorization reference;
- prerequisite operations and evidence revisions.

The idempotency payload hash includes the binding digest. Legacy operations
without a binding keep the old hash and meaning. Unsupported values and
bindings over 32 KiB are rejected explicitly; nothing is silently truncated.
Credentials are not accepted in the binding.

**Controls:** `backend/tests/test_operation_binding.py` — same payload
replays; changed recipient/attachment revision conflicts; different
workspace does not share the reservation; binding survives a new session;
oversized arguments fail; missing action/workspace fails; registry dispatch
keeps the binding on the operation.

## Patch 2 — execution through the lifecycle

**Confirmed defect:** no generic bridge existed between a persisted plan and
a registry-dispatched effect. Special-case continuations could not serve as
the general runner.

**Changed seam:** `AssignmentExecutor` reloads durable state, checks the task
revision (optional `expected_task_revision`), refuses cancelled work, checks
step dependencies, claims the operation, dispatches the resolved inputs,
persists the observed result, then settles the plan. The default
`action.registry` adapter is the execution boundary for registered actions;
it checks the action's declared preconditions against authenticated context.

**Controls:** stale revision refuses dispatch; a failed prerequisite blocks
a downstream external effect; cancellation before dispatch prevents the
effect; duplicate approval/execute cannot repeat the effect; the registry
receipt and task outcome stay linked.

## Patch 3 — normalized receipts

**Changed seam:** every operation now receives a versioned `receipt` with:

- operation/execution identity and binding digest;
- action/adapter and observed status;
- source/artifact identity and source version;
- calculation expression/value/unit/steps when applicable;
- outbound provider state and provider reference;
- readback revision/hash for artifacts;
- error class;
- reconciliation requirement and timestamp.

Statuses are separated: `confirmed`, `provider_accepted`,
`failed_before_effect`, `uncertain`. A bare `{"success": true}` is not treated
as every outcome.

## Patch 4 — external outcome reconciliation

**Changed seam:** the Outlook/canvas send path now carries `run_id` and
`operation_id` into `EmailCanvasService.send_email()`. Provider acceptance
(HTTP 2xx), confirmed pre-effect failure and ambiguous transport failure are
reconciled through `TaskLifecycle.reconcile_outbound()`. `OutlookService`
records whether a transport failure happened before any HTTP response.

**Controls:** failure before dispatch; provider accepted with local receipt;
provider accepted then connection lost; worker died after possible
acceptance; reconciliation applied; reconciliation insufficient; duplicate
approval during uncertainty. The uncertain state never automatically resends.

**Limitation:** provider reconciliation currently proves Graph acceptance for
this send call; recipient delivery is not claimed.

## Patch 5 — exact, durable waits

**Confirmed defects:** `_match_wait()` used substring containment for every
field, so `thread-1` could match `thread-10`; and the wake commit and the
successor step were separate writes.

**Changed seam:** `goal_run_service._match_wait()` now separates descriptive
`match` (containment, legacy) from `match_exact` (opaque IDs). `consume_wake`
uses a single conditional UPDATE so concurrent consumers cannot both consume
the same wait. The inbound Outlook/Gmail webhook path now calls
`ingest_event()` with the provider thread/conversation identity, message
identity, source and workspace/tenant. Assignment wakes resume through the
same run id; `replay_pending_wake()` recovers a wake committed before the
successor ran. Ordinary GoalRuns keep the existing router advance path.

**Controls:** same event twice → one wake; substring-similar ID → no wake;
unrelated event → no wake; crash after wake commit → recovery applies the
logged event and resumes; cancelled work is not revived.

**Limitation:** the pilot is verified for one worker process per assignment.
The database conditional update is the cross-process guard, but no
multi-worker campaign was run.

## Patch 6 — approval scope and binding

**Confirmed defect:** the pending-approval alias called
`get_pending_interventions()` with no workspace/user scope, and the decision
route looked up an approval id without workspace/tenant scoping. Role alone
could therefore decide another workspace's action.

**Changed seam:** workspace/tenant filters are applied when the authenticated
principal has them (legacy unscoped principals keep their previous view);
the decision routes 404 an out-of-scope id before any role check. Assignment
approvals are filed as `assignment_approval` HITL rows carrying run, step,
operation, payload digest, artifact revision and authorization revision.
`hitl_resume` approves/rejects through the assignment executor and resumes the
same run. Modified binding keys are refused. Approval after cancellation is
refused.

**Controls:** wrong-payload/artifact rebinding refused; approval after
cancellation refused; approval persists across restart; duplicate approval
returns `already_applied` without a second effect.

## Patch 7 — completion criteria

**Changed seam:** `task_outcome_contract` adds:
`artifact_verified`, `draft_saved`, `provider_accepted`,
`sent_record_confirmed`, `delivery_confirmed`, `required_work_complete` and
`no_open_gaps`. `action_dispatched` keeps its dispatch-only meaning and is
now tenant-bindable. The assignment outcome is built from applied operations,
saved artifact hashes, provider state and open gaps — not from a model's
"DONE" text.

**Control:** a dispatched audit row alone is not provider acceptance; a
provider-accepted result without a provider reference does not satisfy the
criterion.

## Patch 8 — recovery and durable UI surface

**Changed seam:** `AssignmentExecutor.recover_ready_assignments()` re-enters
active assignments from durable state. Steps expose a `recovery_class`
(`safe_to_resume`, `waiting_for_event`, `awaiting_approval`,
`uncertain_requires_reconciliation`, `terminal_failed`, `terminal`). The new
`/api/assignments` routes expose list/status/resume/cancel/approve and are
scoped to the authenticated workspace/tenant. Ordering and missing
information are read from the durable record, not the transcript.

**Limitation:** the backend surface and projection are implemented; the
Chat/Activity/Workspace frontend components were not rebuilt in this slice.

## Boundary-hardening pass — 2026-10-29 (second slice)

### Ordinary resume vs restart recovery

`AssignmentExecutor.resume()` no longer asserts worker loss. The explicit
`recover_after_restart(run_id, lost_worker=..., is_worker_live=...)` path owns
that decision. A running operation is marked `uncertain` only when its
recorded owner is demonstrably gone; no owner, the current worker, a live
probe, or an old lease leaves it untouched. Claims now persist
`claimed_task_revision` and `claimed_operation_revision` alongside the worker
fingerprint and timestamp. Expired claims alone never prove an effect failed.
The public `/resume` route calls ordinary resume; it does not auto-run restart
recovery.

Controls: `test_ordinary_resume_leaves_healthy_running_operation_intact`,
`test_recovery_without_worker_proof_does_not_assert_loss`,
`test_recovery_names_previous_worker_and_marks_uncertain`,
`test_liveness_probe_true_keeps_running_operation`, and
`test_two_concurrent_resume_requests_dispatch_once`.

### Approval authority at the public boundary

The `/api/assignments/{run_id}/approve/{step_id}` route now:

- resolves the assignment approval HITL row by id, workspace and tenant;
- refuses a missing/decided/wrong-workspace row before approval;
- applies the existing `InterventionService._required_role_denial` policy and
  requires the established team-lead band;
- verifies run/step/operation/payload/artifact/authorization bindings exactly;
- marks the HITL row approved only after the executor accepts the decision;
- resumes the same durable run, and never runs a second effect on a duplicate
  decision.

Controls through the real routes:
`test_authorized_team_lead_approves_once`,
`test_same_workspace_member_cannot_approve`,
`test_wrong_workspace_approver_is_refused`,
`test_changed_payload_is_not_approved_under_old_request`,
`test_cancelled_assignment_cannot_be_approved`.

### Strict semantic fingerprints

`canonical_sha256()` version 2 hashes the complete validated representation
and rejects unsupported/oversized input (1 MiB, depth 32, 10,000 items,
100,000-character strings). Version 1 remains available only to verify stored
legacy fingerprints. Teaching snapshots now declare `fingerprint_version: 2`;
the bounded `_json_safe()` projection remains for diagnostics, not identity.
Approval payload digests and operation binding digests now use strict JSON and
no `default=str` fallback.

Controls: `backend/tests/test_fingerprint_identity.py` distinguishes values
that differ after the old 1,000-character, 40-item, or depth-4 limits and
checks explicit failure for unsupported/oversized identity input.

### Frontend and browser acceptance

The existing chat workspace now has an **Assignments** tab backed by
`components/assignments/AssignmentPanel.tsx` and the durable
`/api/assignments` projection. It shows objective, current step, completed
work, artifacts, open gaps, waiting party, the concrete approval payload,
resume/cancel, uncertain outcomes and final status. It does not call restart
recovery on load and does not infer state from transcript text. A standalone
`/assignments` activity page reuses the same panel.

Browser acceptance (Playwright, real assignment routes and executor on a
scratch database, controlled outbox only):

1. open the page with both domains waiting;
2. deliver the correlated response for the first domain;
3. inspect and approve the concrete payload;
4. observe completed state and the one-record controlled outbox;
5. reload and confirm the same durable completed state;
6. repeat for the second domain with different teaching/decision labels.

Evidence: `docs/acceptance/evidence/durable_assignment_20261029/browser/`
(`playwright.txt`, both completion screenshots, controlled `outbox.jsonl`,
backend log).

Concurrent `/resume` requests are safe at the operation-claim boundary; the
verified topology remains one worker process per assignment, documented in
the evidence README.

## Two-domain proof

The same executor ran two materially different assignments; only task
definitions, teaching snapshots, schemas, decision labels and permissions
differed.

| | Commercial response | Eligibility package |
|---|---|---|
| Sources | workbook + email context | document |
| Teaching | `teach-r1`, US$ fields | `teach-b1`, Times New Roman |
| Decisions | `APPROVE`/`REVIEW` | `CLEAR`/`HOLD` |
| Missing fact | external reference | qualification expiry |
| Outputs | DOCX + draft + send | DOCX + notice |
| Approval | send payload | notice payload |
| Final | completed | completed |

Evidence: `docs/acceptance/evidence/durable_assignment_20261029/`

- `commercial_evidence.json` / `eligibility_evidence.json` — task revision,
  operations, approvals, receipts, decisions and final status;
- `commercial.docx`, `eligibility/eligibility.docx` — saved artifacts;
- `outbox.jsonl`, `eligibility/outbox-eligibility.jsonl` — controlled
  transport outboxes (one record each; duplicate execution did not add one);
- `records.xlsx`, `eligibility/qualification.txt` — source fixtures.

The controlled outbox is a mocked transport, not a live recipient.

## Controls run

`130 passed` across:

- `backend/tests/test_operation_binding.py` (8)
- `backend/tests/test_assignment_executor.py` (11)
- `backend/tests/test_goal_run_events.py`
- `backend/tests/test_hitl_approvals_journey.py`
- `backend/tests/test_hitl_resume.py`
- `backend/tests/test_active_intervention_service.py`
- `backend/tests/test_artifact_teaching_context.py`
- `backend/tests/test_artifact_renderers_teaching.py`
- `backend/tests/test_lesson_scope.py`
- `backend/tests/test_canvas_connected_binding.py`

The four pre-existing `test_task_lifecycle` revision-count failures remain
unchanged and are not counted here. `test_search_outcome_contracts.py` also
passes (30) after the criteria additions.

## Remaining limitations

- No live connected-source send was performed; the combined Microsoft
  config restoration / disposable-source authorization remains outstanding.
- Provider delivery confirmation is not claimed; only provider acceptance.
- Multi-worker execution is not claimed; one worker process per assignment
  is the verified topology. Concurrent API resumes are guarded by the
  operation claim and tested.
- The live connected provider path remains unexercised; the browser run used
  the environment-gated controlled outbox.
- Pre-existing `test_task_lifecycle` failures (goal-text/`objective_text`
  backfill revision counts) are unchanged by this slice and are not counted
  as passing controls.

## Release position

R3 is untouched. This successor is additive and local. Deployment remains
separate and unauthorized.
