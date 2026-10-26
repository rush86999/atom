# Saved-lookup continuation — 2026-10-26

**Scope:** repair the planner-enabled saved-lookup continuation on the frozen
spreadsheet candidate (`e14d3efdd`), preserving the original failure. This is
a repair branch, not a deployment.

## Preserved failure

`planner_failure_preserved/` under the trained-eval evidence directory holds:

- `atom_run2_verbose_confirmation.db` — pending task stored; verbose
  confirmation follow-ups left the task `pending` and never dispatched a read.
- `atom_run6_no_followup.db` — planner-enabled broad review stored the pending
  task and reported that no search ran.
- `metadata_dump.json` — session/message metadata for the affected sessions.

## Harness correction (2026-10-26)

The first evaluation harness did not match the release configuration: it set
`CHAT_FINALIZATION_M1=0`, `CHAT_FINALIZATION_M2=0`,
`ATOM_TASK_LIFECYCLE_ENABLED=0`, and `ATOM_DISABLE_TOOL_PLANNER=1`. The
observed `outcome=null` therefore did not establish a settlement defect. It
also sent a verbose "confirmation" that the production classifier correctly
rejects because it carries substantial new instructions.

The corrected control uses:

- `CHAT_FINALIZATION_M1=1`
- `CHAT_FINALIZATION_M2=1`
- `ATOM_TASK_LIFECYCLE_ENABLED=1`
- `ATOM_DISABLE_TOOL_PLANNER` unset
- exactly `go ahead`, in the same session, agent, and authenticated workspace.

The effective settings are captured in the evidence before the request. No
success override or forced `outcome="completed"` is applied.

## Trace

1. **Lookup proposed.** The first planner-enabled review returns "the lookup
   hasn't run; it is saved" and stores `_pending_file_task` on the session
   (`status=pending`, `attempts=0`).
2. **Confirmation accepted.** On the next turn, exactly `go ahead` matches the
   existing confirmation contract. The task gains `attempts=1` and
   `confirmed_mention`, and its stored original ask is preserved.
3. **First missing transition.** The resume lane restored `_gate_msg` to the
   original review, but `_research_turn`, `_required_research_sources`, and
   the replan obligation were still computed from the bare approval. The
   planner boundary therefore saw `research=False` and never dispatched a
   read.
4. **Fix — judge the resumed turn as the original ask.** `_research_turn` is
   true for a resumed turn, and required-source selection, replan subject /
   field extraction, and the obligation text all use the restored
   `_gate_msg`. A resumed file ask admits its named file as a required
   `datasets` / `documents` source even when no taught lesson names it.
5. **Continuity.** `request_extends_objective` treats a bare approval as
   confirmation, not a new objective. `merge_pending_task` keeps the original
   ask for a still-pending task and does not replace a terminal task with the
   bare approval; the attempt is counted and `confirmed_mention` refreshed.
6. **Verified receipt.** The replan executes the dataset read and produces a
   `file_scoped_read` receipt (`verified=true`, `addresses_requested=true`,
   file name and content hash). That receipt is bound to the pending task
   (`retrieved` → `delivered`) and to the persisted result, including the
   current execution id.
7. **Machine settlement.** The existing criteria verifier resolves
   `source_scoped_retrieval` from the verified receipt. `build_task_outcome`
   now writes that verdict into `objective_met` / `criterion_results` instead
   of leaving them empty. The finalizer carries the execution row's
   `task_outcome` into the envelope and maps only an explicit verdict:
   `true → completed`, `false → failed`, unknown/absent → `null`. A failed
   execution is never rounded to completed.

## Corrected control result

One-order release-config control
(`release_control_20261026/evidence.json`):

- pending task found: **true**
- `go ahead` accepted: **true**
- original request restored: **true**
- planner not disabled: **true**
- finalization M1/M2 on: **true**
- task lifecycle on: **true**
- read dispatched: **true**
- receipt verified / file + hash: **true**
- pending task delivered: **true**
- response cites workbook: **true**
- response `outcome`: **`completed`**
- execution `task_outcome.objective_met`: **true**
- `success_kinds`: `task_success=true`, `tool_success=true`,
  `delivery_success=true`, basis `criteria_met`
- assistant metadata outcome matches response: **true**
- fresh history persisted: **true**

The response is a genuine settlement of the verified read, not a success
override: `objective_met` comes from the existing `criteria_verdict` and the
envelope maps that explicit verdict.

## Combined evaluation (planner enabled, no supplied rows)

Evidence: `combined_eval_repair_20261026/evidence.json` (scratch world). The
run taught the policy, reviewed O-1001, reviewed O-1010 before correction,
taught the O-1010 credit-hold correction, reviewed O-1010 before restart,
performed a real app restart, and reviewed O-1010 again. No Order rows were
supplied in any prompt.

- **Teaching:** O-1001 → **Process**, citing `Orders` row 2 and the values.
- **Correction, pre-restart:** O-1010 → **Escalate**, citing **M. Chen** and
  **2026-10-25** (credit hold).
- **Correction, post-restart:** O-1010 → **Escalate**, citing **M. Chen** and
  **2026-10-25**; the lesson log and retrieval still contain the correction.
- **Settlement:** every reviewed turn returned `outcome=completed`; the
  execution `task_outcome.objective_met` is `true`; assistant metadata and
  fresh history agree in every case.
- **Zero unauthorized actions:** canvas audit unchanged (`create`,
  `agent_attached`, `data_loaded`), `task_operation_records=0`, `tasks=0`, no
  outbound/send/edit/approve operation, workbook SHA-256 unchanged.

The first combined run exposed a real product failure behind the corrected
configuration: file-scoped turns skipped **all** memory/lesson assembly when
the read succeeded. The correction was stored and retrievable, but never
entered the prompt, so O-1010 was processed after restart. The repair adds a
lessons-only assembly path for file-scoped turns, retrieves lessons for the
pending task's original ask (not the bare `go ahead`), and states explicitly
that training lessons are policy, not a file-value substitute. The failing
pre-fix evidence is preserved as
`combined_eval_repair_20261026/evidence_before_lesson_fix.json`.

**Disclosed baseline limitation:** with no supplied rows, the pre-correction
O-1010 read returned Status and Unit Price but not the Currency field, so the
model escalated on the base policy's “uncertain currency” rule rather than
recommending Process. This is the known file-read projection limitation (the
read does not return the full row contract); it is not a correction failure.
The correction itself is applied and persists across restart. The bounded
row-projection repair below supersedes this limitation for review asks.

## Bounded outcome + row-projection repair

Two local outcome controls were corrected before another expensive run:

- **Per-criterion verdicts.** `build_task_outcome` no longer copies the
  aggregate verdict onto every criterion. Each declared criterion keeps its
  own registered-verifier result; a mixed True/False control now yields
  `source_scoped_retrieval=True` and `record_review=False` for an incomplete
  review, never two false rows.
- **Execution-state eligibility.** The finalizer maps a task verdict only for
  an established successful execution (`success` / `succeeded` /
  `completed`). Unknown, missing, failed, partial and queued dispositions are
  never rounded to `completed`; existing partial/queued envelope outcomes are
  preserved.

The row projection was then repaired for review asks:

- A review's named fields (Order ID, Status, Qty, Unit Price, Currency,
  Approval 1, Approval 2, Manager Exception, Notes) are extracted before the
  read.
- A review ask selects the whole matched row, so Currency, both approvals,
  exception and notes are returned; genuinely absent headers are recorded as
  `coverage.field_gaps` and rendered explicitly.
- A new `record_review` criterion requires a delivered decision, not just a
  verified read. Deterministic read blocks and r4 recovered scans are staged
  as evidence and narrated for review asks; a read alone cannot certify the
  review obligation.

Bounded evidence: `combined_eval_row_projection_20261026/evidence.json`
(fresh scratch world, planner enabled, no supplied rows):

- O-1010 before correction → **Process**, complete row (Currency CAD,
  approvals, notes) → `outcome=completed`.
- O-1010 after correction, pre-restart → **Escalate**, citing **M. Chen /
  2026-10-25** → `outcome=completed`.
- O-1010 after restart → **Escalate**, same citation → `outcome=completed`.
- O-1001 positive twin → **Process**, unchanged → `outcome=completed`.
- All four: metadata outcome agrees, history persists, no unauthorized
  task/canvas/outbound writes, source hash unchanged.
- `checks_all_true: true` for the bounded checks.

The earlier budget failure is preserved as
`combined_eval_row_projection_20261026/evidence_before_budget_retry.json`; a
single retry re-delivered the stored read. The earlier full-run evidence
remains under `combined_eval_repair_20261026/` and is not overwritten.

## Task-defined review contract (domain-independent)

The review completion path no longer hardcodes order vocabulary, and
certification no longer comes from prose. Review recognition is only the
generic assessment-verb shape (`assess`, `evaluate`, `review`, `classify`,
`decide`, `determine`, `recommend`, `score`, `rank`, `triage`). The choices
themselves come from the task's own teaching:

- `POST /api/agents/{id}/teach` accepts `decision_options`; the lesson entry
  stores them.
- A review turn builds a `review_contract` with the accepted `subjects`, the
  `required_evidence`, and the task's `allowed_decisions`.
- The existing generation call is instructed once to emit a fenced
  `review_result` block alongside its explanation. Only that structured block
  is certified; ordinary prose — including a quoted example such as
  `"Decision: Process"` — cannot create or override a decision.
- `core/review_result.py` binds each assessment to the read's
  target-to-row association. An `evidence_id` must name the SAME subject,
  accepted source identity and accepted retrieval operation. A file/hash alone
  does not certify a record-level assessment.
- `policy_ids` must resolve to teaching entries carrying the task's decision
  schema, not merely any retrieved lesson.
- `record_review` consumes only the validated result. A raw read block, a
  refusal, a wrong-subject evidence reference, swapped evidence, missing or
  unknown IDs, an execution mismatch, or a decision outside the task schema
  cannot certify completion.
- The delivered answer carries the rendered, request-bound validated block.

The order cases remain regressions: the order policy teaches
`["Process", "Escalate"]`. A second-domain control uses the same mechanism
with `["Approve", "Deny", "Request More Info"]` for vendor risk — no platform
change between them.

Local controls cover: quoted/example decision prose rejected; valid order
Process/Escalate twins; a valid vendor review with different decisions;
wrong-record evidence, swapped evidence between requested subjects,
missing/unknown evidence and policy IDs, missing second subject, refusal
containing decision words, execution mismatch and out-of-schema decisions all
rejected; the resumed review production path reaching narration rather than
the raw read block.

The four-check behavioral evidence below was produced before this structured
contract refactor and is preserved as **scoped behavioral evidence**; the
refactor is validated by the local controls.

## Served acceptance on the structured contract

Canonical run: clean commit `c0c0d2e87262` (`d4d0576d1` plus the
response/outcome propagation fix), scratch world, planner enabled,
finalization/task lifecycle on, no supplied rows. Evidence:
`served_freeze_d4d0576d1_20261026/evidence.json`.

| Check | Decision | Structured review | Outcome |
|---|---|---|---|
| O-1010 before correction | **Process** | valid, persisted | completed |
| O-1010 after correction, pre-restart | **Escalate**, cites **M. Chen / 2026-10-25** | valid, persisted | completed |
| O-1010 after restart | **Escalate**, same directive | valid, persisted | completed |
| O-1001 positive twin | **Process** | valid, persisted | completed |

All four: raw fenced machine blocks hidden; validated block visible; complete
row retrieved; response/persistence/history agree; workbook SHA-256 unchanged;
canvas audit unchanged; `task_operation_records=0`; `tasks=0`; no
outbound/send/edit/approve. `checks_all_true=true`.

All four completed through the **confirmation path** (pending task → short
confirmation → review). No timeout recovery was required in the canonical run;
this establishes confirmation-path completion, not first-request completion or
recovery-after-timeout completion.

Attempt trail preserved in the same directory:

- `attempt1_propagation_failure.json` — run on `d4d0576d1`: decisions rendered,
  but the structured result was not propagated to response/outcome.
- `attempt2_response_metadata_gap.json` — run on `d4d0576d1`: outcomes
  completed, but the response metadata lacked the structured result.
- `attempt3_uncommitted_success.json` — propagation fix, uncommitted: all four
  green.
- `evidence.json` — clean `c0c0d2e87`: all four green (canonical).

**Closed slice (tested candidate/configuration):** task-defined,
evidence-bound recommendations with scoped correction and restart persistence.
Order teaching supplied `["Process", "Escalate"]`; the structured review was
bound to the requested subject, accepted source/retrieval identity and task
policy; O-1010 changed Process → Escalate and stayed Escalate after a real
restart; O-1001 stayed Process.

**Separate, not claimed:** five-order latency, general policy transfer beyond
the tested controls, and deployment. The pilot remains `c912375de`.

## Release candidate package

Candidate source `ae0c2fda340e9a85e840e310d84d4d0da4fedab8` (includes the
spreadsheet fix and trained-review fixes, plus the independent-review release
blockers). Frozen source directory:
`/Users/rushiparikh/projects/atom-releases/ae0c2fda3`; canonical plain-tar
archive SHA-256
`33a317c2b981f5947f854056aad8b11ffce4ac8c0a6b908e96f998d5dca4f526`.
The preserved original gzip artifact and its different SHA-256
(`3b4caf8cf9fa0be9bc3ef20e7505eb62af3a73b4bc7e6c13698142e112cc5fc5`)
are recorded in `evidence/archive/`.

Combined served smoke on the candidate (`checks_all_true=true`):

- PO Register approved rows: CAD **8050.00** / USD **3999.96**;
- Adjustments: known subtotal **−700.00 CAD**, gap **0055** at **C5**,
  grand total withheld;
- O-1010 Process → Escalate after correction and after restart, citing
  M. Chen / 2026-10-25; O-1001 Process;
- structured reviews persisted, raw blocks hidden, response/persistence/
  history agree, workbook hashes unchanged, zero unintended writes.

Package/docs:
`docs/acceptance/RELEASE_CANDIDATE_ae0c2fda3_2026-10-26.md`,
`docs/acceptance/SUPPORT_STATEMENT_2026-10-26_CANDIDATE_ae0c2fda3.md`, and
`docs/acceptance/CUTOVER_RUNBOOK_ae0c2fda3_2026-10-26.md`.
The cutover now requires immediate live smoke, a scoped restart, post-restart
agreement, and automatic code rollback to `c912375de` on any failure. Database
restore is not part of normal rollback. Two authorized attempts were executed
before any product turn. The first failed at smoke admin login (HTTP 401) and
was manually recovered; the second passed preflight, backup and candidate
startup, created one smoke agent, then failed at guided-agent HTTP 201 and
automatically rolled code back to `c912375de` (PID `13038`, healthy). No
database restore occurred. The confirmation helper now uses exactly `go ahead`
and passes parity tests against the packaged helper and frozen classifier. The
HTTP-201 acceptance mismatch remains for a bounded future correction; no third
attempt has run.

## Tests

Focused suite (`test_review_result.py`,
`test_workbook_read_artifact.py`, `test_memory_context_assembler.py`,
`test_l2_guard_order.py`, `test_pending_file_task_resume.py`,
`test_cross_source_followup_routing.py`, `test_dataset_aggregation.py`,
`test_finalization_m1.py`, `test_finalization_m2.py`,
`test_outcome_resolution.py`, `test_fallback_honesty.py`,
`test_objective_evidence_flow.py`, `test_search_outcome_contracts.py`,
`test_acceptance_harness_integrity.py`):

- Repair branch: **602 passed, 23 failed, 2 xfailed**.
- Frozen baseline: **557 passed, 23 failed, 2 xfailed** (same existing
  files; the new `test_review_result.py` is repair-only).
- The same 23 named failures exist on both sides (known refresh/cross-source
  and objective-evidence test gaps, plus one order-dependent shared-state
  failure that passes in isolation on both sides). No new failure was
  introduced.
- New tests cover bare-approval resume, `resume_operation`, terminal-task
  merge, the finalizer's explicit-verdict mapping and status eligibility,
  mixed per-criterion verdicts, lessons-only assembly for file-scoped turns,
  review-field extraction, whole-row selection, field gaps, the task-defined
  `review_result` contract, order regressions, a vendor-domain control, and
  the resumed-review narration production path.

## Remaining gaps and limits

- The four served checks on `c0c0d2e87` (O-1010 before/after correction,
  after restart, and the O-1001 positive twin) are green on complete-row
  retrieval, structured decisions, correction, settlement, and zero
  unauthorized actions; all four used the confirmation path. A five-order /
  full-group review still reaches the product's fixed turn budget
  (`turn_budget_exceeded`); the captured
  `ATOM_CHAT_TURN_BUDGET_SECONDS=180` does not change the product's
  `budget=95.0s` deadline. The broader five-order latency problem remains
  separate and is not claimed solved.
- Review asks now retrieve the whole row and expose absent named headers as
  `coverage.field_gaps`. Blank values that are genuinely part of the record
  (for example a blank Manager Exception meaning “none”) are returned as
  explicit blanks, not converted into invented values. The full-row behavior
  is demonstrated for these bounded review asks; broader field-contract
  coverage is not claimed.
- Domain independence describes the completion mechanism, not universal
  capability. Supported formats, operations, formula functions and judgment
  quality remain evidence-bound. The vendor-risk control is a small local
  regression using the same contract, not a broad second-domain capability
  claim.
- The policy basis in the one-order response is explicitly a draft: the
  workbook was retrieved, but the policy document itself was not. Do not
  describe the prior behavioral result — policy-conditioned recommendations
  and the O-1010-specific correction on supplied rows — as autonomous workbook
  retrieval. It remains a separate, prompt-supplied-rows result.
- The spreadsheet role-clarification flow and the required-input filter
  limitation remain disclosed; filter-language expansion was not combined
  with role correction here.
- This repair branch is **not deployed**. The pilot remains the separate
  `c912375de` release; deployment is a separate boundary.
