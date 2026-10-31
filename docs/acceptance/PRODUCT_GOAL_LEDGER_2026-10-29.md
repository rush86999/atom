# Product goal ledger — current state

**Current as of 2026-10-31.** This is the single current-state completion
contract. The prior ledger and its appended history are preserved separately
at `docs/acceptance/PRODUCT_GOAL_LEDGER_HISTORY_2026-10-29.md`; historical
statuses there do not override this table.

**Candidate source:** `c8203613e` on branch `codex/employee-execution-readiness`
(evidence source `06d80f834`; product teaching `3e344f5b1`; Agent 2
README-readiness merge `931892be0`). **Configuration:** isolated local world, `ATOM_PRODUCT_PROFILE=core`,
`ATOM_LOCAL_ONLY=true`, `ATOM_TURN_DECISION_ROUTING=0`,
`ATOM_TASK_LIFECYCLE_ENABLED=1`, scheduler and ingestion sync off, controlled
assignment transport with a local outbox. Backend `127.0.0.1:8071`, frontend
`127.0.0.1:3130`.

**Preserved identities (not moved):**

- Core: `local-core-2026-10-30-final` → `da9cc8b12`
- Reviewed successor: `conversation-learning-2026-10-30` → `d2b297deb`

Status vocabulary: **Verified for tested scope**, **Partial**, **Unverified**,
**Blocked-external**, **Owner-deferred**. "Verified" never means universal
reliability.

| # | Supported user action | Governing implementation | Final source / configuration | Acceptance evidence | Genuinely unfinished behavior |
|---|---|---|---|---|---|
| 1 | Create/select an employee, teach it a method, start work on an uploaded source, and complete the same job in a different business domain | `core/assignment_planner.py`, `core/assignment_executor.py`, `core/table_selection.py`, `core/dataset_aggregation.py`, `core/student_learning_service.py` | `06d80f834`; controlled local world; two domains through the same UI/API mechanisms | Sales quote and grant-review composite runs: `sales-composite-2/verify.json`, `grants-composite-2/verify.json` (400.00 USD and 4250.00 USD, mapped columns, DOCX, email draft, approval, restart) | Arbitrary domains, schemas and business policies are not claimed. Two domains are demonstrated, not universal competence. |
| 2 | Teach general method, contextual exception, qualification, effective period, conflict, formatting, email protocol, correction, and transfer to new work; review a conversation-derived guidance lesson without inventing a calculation | `core/conversation_learning.py`, `core/student_learning_service.py`, `core/artifact_teaching.py`, `core/chat_orchestrator.py`, `core/chat_teaching_runtime.py`, `core/method_operands.py` | `06d80f834` (guidance-only + format/protocol promotion in `3e344f5b1`); local candidate | Composite: conflict `font_name`, missing `qualification`, expired lesson exclusion, `[Quote]`/`[Grant]` protocol, revised teaching, second source. Conversation review: guidance-only candidate promoted with `method_status=not_applicable`, `format_spec` persisted, `lesson_id dffc99c4…` (`conversation-guidance/`). 284 targeted backend tests passed. | Arbitrary prose cannot be made deterministic; every renderer field and every possible instruction are not claimed. Discretionary assessment quality remains bounded by the configured review model. |
| 3 | Resolve unfamiliar columns and units; confirm or correct a mapping; resume the same assignment | Mapping resolver in `core/artifact_teaching.py`; gap/correction and resume in `core/assignment_executor.py` and `backend/api/assignment_routes.py`; `AssignmentPanel` UI | `06d80f834`; sales `Price → Gross Amount`, grants `Approved Amount → Award Amount` and `Approved Amount → Approved Award` | `sales-composite-2/verify.json`, `grants-composite-2/verify.json`; mapping/unit/stale tests in the 284-pass suite | Arbitrary Excel schemas and every authority surface are not claimed. |
| 4 | Upload/connect authorized data and retrieve it for work | `core/assignment_resources.py`, `core/sheet_dataset_service.py`, document/data ingestion, shared OAuth resolver | Current candidate: controlled local uploads only. Historical live Microsoft evidence is bound to `001f93472`; it is not a current-candidate live-connector run | Current: sales/grant CSV uploads and source picker through the UI. Historical: `live-connected/guided/gate-result.json`, `live-connected/changed-source/gate-result.json` | No fresh live Outlook/OneDrive/Zoho run on this candidate; no credential change or external write. Connector breadth beyond the historical Microsoft scope is unverified. |
| 5 | Ingest large/multi-sheet workbooks and supported formulas; retrieve and calculate with citations | Workbook ingestion, `sheet_dataset_service`, formula sidecar/evaluator, `dataset_aggregation` | Historical large-workbook evidence at `connected_core_20261028`; current candidate uses small CSVs | Historical evidence preserved; current composite proves sourced aggregation and row/cell citations | Current-candidate 24-sheet/formula recalculation was not rerun. Arbitrary Excel compatibility and unsupported formulas as certified recalculation are not claimed. |
| 6 | Create a user canvas, bind data, calculate, edit with readback, export XLSX, reload | Canvas capability manifest/adapter, authoritative frame, revision-checked edits, office export | `06d80f834`; supported table adapter; `canvas-capability/canvas.json` | 290.00 → edit A-101 75→110 → 325.00; readback matched; XLSX `0f10cc8e…`; reload `revision 2 · 4 rows`; no page errors | Canvas assessment was not part of this row's run (it is row 7). Arbitrary spreadsheet controls, formulas and future canvas components are not claimed. |
| 7 | Grounded selection, calculation and assessment with citations | `core/table_selection.py`, `core/dataset_aggregation.py`, `core/review_result.py`, review contract, deterministic receipts | `06d80f834`; local candidate | Calculations: 400.00 USD (sales, rows 2–4) and 4250.00 USD (grants, rows 2–4) with source identity. Review contract/unit tests pass in the 284 suite. Assessment attempt: `employee-execution-assessment-blocker/` | **Executed on a local model** (`ollama`/`llama3.1:8b`, CPU) on six unfamiliar grant records with real `served_provider`/`served_model` provenance: certified 6/6 subjects; judgment **5/6** under policy v1 (approved `A-204`, Amount 95), **6/6** after the policy correction, **6/6** after a real backend restart with an identical request hash. Pipeline verified; the 8B model's boundary judgment is **not** claimed reliable. Cloud providers remain unavailable (DeepSeek key empty; OpenRouter HTTP 402). Evidence: `employee-execution-substantive-assessment/`; earlier failed-closed attempts in `employee-execution-assessment-blocker/`. |
| 8 | Produce editable DOCX/PPTX and an email draft | `core/office_service.py`, artifact renderers, `core/canvas_email_service.py`, assignment deliverable adapters | `06d80f834`; controlled outbox; no live send | DOCX active/reload hashes; PPTX 4 slides with result/findings/sources (`grants-presentation/`); email draft `[Quote]`/`[Grant]` with greeting/signature; controlled outbox exactly one line per job | Image/chart understanding and real recipient delivery are not claimed. Real send remains disabled. |
| 9 | User-created canvases inherit supported capabilities | Versioned capability manifests, adapter registry, canvas routes | `06d80f834`; table adapter only | `canvas-capability/canvas.json`: manifest installed, CSV bound, calculate/edit/export/reload | Only the supported table adapter is verified; every future canvas component is not. |
| 10 | Long-running multi-source assignment with missing information, browser close, restart, delayed response, changed teaching, artifact restart, cancellation/uncertain-effect controls | `core/task_lifecycle.py`, GoalRun services, executor checkpoints, durable waits, HITL routes, reconciliation | `06d80f834`; one worker; controlled transport | Sales and grant composites: waiting → browser closed → backend PID changed → same run resumed → correlated response → artifact. `test_assignment_executor` recovery/cancel/uncertain/duplicate/artifact-restart tests pass in the 284 suite | One-worker topology only. No multi-day soak, multi-worker campaign or unrestricted autonomous browsing. Real credential expiry is not exercised on this candidate. |
| 11 | Approval binds the exact payload/artifact; controlled continuation; duplicate approval does not duplicate transport; changed payload requires fresh review | `core/proposal_service.py`, `core/hitl_resume.py`, assignment approval binding | `06d80f834`; accepted atomic-binding repair from `dcac5d323`; controlled outbox | Accepted verifier evidence `conversation-learning-dcac5d323/`; composite approvals executed once; duplicate/rejection/drift controls in the 284 suite | Real-provider send is not part of this candidate. Recipient delivery is unclaimed. |
| 12 | Install/start the local app, sign in, use the supported workspace, restart and recover | Normal auth, Assignments/Activity, durable storage, local UI entry points, documented launch | `06d80f834`; Python 3.11.16, Node 20.19.6, `core` profile, isolated data root | Two-domain browser/API acceptance; clean install procedure in `docs/acceptance/INTEGRATED_LOCAL_CANDIDATE_2026-10-31.md`; restart identities in the composite JSON | Hosted deployment, public release and publication are **owner-deferred**. Live connectors, real sends, credential changes and source shutdown were not performed. |

## Current-state notes

- The earlier "intentionally excluded" dispositions for canvas editing,
  review/assessment, artifact generation and durable execution are superseded
  by the consumer audit: applicable teaching now reaches the shared resolver,
  artifact teaching (format/protocol), review decision schemas and the
  canvas/review lanes. Where a lane lacks an established context or a pinned
  review model, it clarifies or reports the unsupported boundary rather than
  silently applying teaching.
- The accepted core and conversation-learning tags remain historical
  identities. This candidate is a successor; it does not move them.
- Hosted deployment and publication are not unfinished engineering in this
  ledger; they are explicitly deferred by the owner.

## Settings BYOK refresh

Verified through the normal Settings key route and Chat route without a
restart: save, replacement and removal; the bounded provider sees the saved
and replacement keys, removal makes no new call, and key values do not appear
in logs.

The journey also runs on **normal routing with no model pin**: with the
bounded provider advertising the models the router selects, key A was served by
`gpt-4o-mini` and the replacement by `gpt-5.6-luna` / `o4-mini`. The earlier
pinned run is history; the pin is a diagnostic override only. Evidence:
`docs/acceptance/evidence/durable_assignment_20261031/employee-execution-byok-refresh/`
(`normal-routing/`). Local provider, not a real-account send.

## Practical assignment boundaries

The five boundaries the practical gate left open now have passing executable
controls: restart-while-waiting, changed-revision invalidation, ambiguity,
cancellation and duplicate resume. Run: **8 passed**, 0 failed. These are
executor/route-level controls, not a browser rerun. Evidence:
`docs/acceptance/evidence/durable_assignment_20261031/employee-execution-assignment-boundaries/`.

## Substantive model-backed assessment

Executed on a real served model instead of remaining blocked:

- `ollama` / `llama3.1:8b` (Q4_K_M, CPU) served from a readable local store on
  a separate port; `ATOM_REVIEW_MODEL`/`ATOM_REVIEW_PROVIDER` declared and
  pinned; `ATOM_LOCAL_ONLY=true`; no cloud provider used.
- Six unfamiliar grant records, a taught policy, a policy correction that
  removes a regional exception, and a fresh judgment after a real backend
  restart (pid 93571 → 94951).
- System gates passed at every phase: certified, exact subject coverage,
  non-empty `served_provider`/`served_model`, changed policy revision after the
  correction, identical request hash and decisions after restart.
- Judgment: **5/6** on policy v1 — the model approved `A-204` (Amount **95**)
  citing `Amount >= 100`, a model reading error on the boundary record — then
  **6/6** on the corrected policy and **6/6** after restart.
- Therefore the assessment **pipeline** is verified end-to-end; reliable
  boundary judgment is **not** claimed for this 8B CPU model. Cloud providers
  remain unavailable (DeepSeek key empty, OpenRouter HTTP 402).

Evidence:
`docs/acceptance/evidence/durable_assignment_20261031/employee-execution-substantive-assessment/`.
Historical failed-closed attempts remain in
`employee-execution-assessment-blocker/`.

### Qualification on a fixed unseen set

The intended local launch configuration was then qualified against a frozen
24-record set (`sha256 54a7037e…`, committed before the run) covering exact
thresholds, decimals, exceptions, missing values, conflicting context and a
correction with a real restart:

- **Attempt 1** (default 600 s provider budget, 4096 context): **incomplete** —
  three calls ended at exactly 10m0s; no judgment observed. Preserved.
- **Attempt 2** (same set; `OLLAMA_REQUEST_TIMEOUT=1800`, context 8192):
  completed. `create` **17/18 (94.4%)**, `correct` **17/18**, `after-restart`
  **17/18**; all **8** V1→V3 flips correct, including the three non-North
  `Risk High` records that isolate the two rule changes; 10/10 restart gates.
- Stable error: `Q-021` (Region blank, otherwise approvable) returns REVIEW.
- Serious gap behaviour: `Q-012` (**Amount 0**) is APPROVE in every phase,
  although the policy gives no rule below 50. That is an invented approval.

**Verdict:** pipeline verified, configuration **not** reliable enough for
autonomous substantive recommendations. Substantive recommendations from this
configuration require **human review**; autonomous decisions stay outside its
supported scope.

Review is enforced server-side, not just documented. The default policy
(`ATOM_ASSESSMENT_REVIEW_POLICY=always`) requires human approval for **every**
assessment, whatever the model reports about its own uncertainty — a confident
wrong APPROVE reports none, so model-reported uncertainty cannot be the gate.
Approval is bound to the execution, source and policy revisions **and** the
assessment content hash; re-assessing or changing a decision invalidates it.
The existing assess response withholds the actionable artifact (`rendered`,
`authorized=false`) until approval, and the capability read exposes the
authorization state. `model_reported` is an explicit opt-out only for an
independently qualified deployment.

Scoring correction (v2): a blank field is a gap only when the policy in force
depends on it. `Q-010` (blank Risk) is a gap under V1 but scored under V3
("regardless of Risk"). Under v2 the v3 phases are 18/19 (0.9474); the verdict
is unchanged. Evidence:
`docs/acceptance/evidence/durable_assignment_20261031/employee-execution-assessment-qualification/`.

## README marketed-surface coverage

The frozen README claim inventory (123 eligible functional claims) was
re-executed on the integrated candidate after merging Agent 2's
feature-readiness branch:

- **83 / 123 verified functional claims (67.5%)** after the verifier-driven
  correction. The earlier 100/123 figure was withdrawn because status-only and
  source-inspection assertions did not establish the claims.
- 40 claims are not counted (partial/unverified/inaccurate/blocked/
  environment-limited/architecture-only); see
  `docs/acceptance/readme_feature_readiness_2026-10-31/COVERAGE_REPORT_2026-10-31.md` §4.
- The 80% milestone gate is **not met**.
- Security 8/8 verified; performance, compatibility and comparative claims
  remain tracked separately and are not part of the functional numerator.
- No group errors in the integrated rerun.

Evidence: `docs/acceptance/evidence/durable_assignment_20261031/employee-execution-integrated-readme/`.
This is a self-assessment pending independent verifier agreement; it is not a
release approval, and the 80% gate remains open. The rerun used the bounded local provider/OAuth/MCP stub, not
live provider qualification.

## Historical records

The full previous ledger, including the 2026-10-29 table and all appended
status sections, is preserved at
`docs/acceptance/PRODUCT_GOAL_LEDGER_HISTORY_2026-10-29.md`. Evidence
directories referenced by that history remain unchanged.
