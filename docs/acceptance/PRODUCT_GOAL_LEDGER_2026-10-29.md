# Product goal ledger — current state

**Current as of 2026-10-31.** This is the single current-state completion
contract. The prior ledger and its appended history are preserved separately
at `docs/acceptance/PRODUCT_GOAL_LEDGER_HISTORY_2026-10-29.md`; historical
statuses there do not override this table.

**Candidate source:** `31ba9725e02a` on branch
`codex/employee-execution-readiness` (product code `589389218`; accepted
product source `b7ee7ee22`) (evidence source `06d80f834`; product teaching
`3e344f5b1`; Agent 2 README-readiness merge `931892be0`). The post-repair
journey, deterministic-UI and 24-sheet evidence all executed on
`31ba9725e02a` with `dirty=false`. **Configuration:** isolated local world, `ATOM_PRODUCT_PROFILE=core`,
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
| 4 | Upload/connect authorized data and retrieve it for work | `core/assignment_resources.py`, `core/sheet_dataset_service.py`, document/data ingestion, shared OAuth resolver | Current merged candidate; local uploads + Office workbook sheets; live Microsoft historical only | `employee-execution-integrated-local-journey-repaired/` (CSV upload/source picker on clean `31ba9725e02a`) and `employee-execution-large-workbook/` (24 uploaded sheet sources, 547 rows); live historical bound to `001f93472` | **External Part A**: live read-only Microsoft account/workbook/attachment; no credential change or external write. |
| 5 | Ingest large/multi-sheet workbooks and supported formulas; retrieve and calculate with citations | Workbook ingestion, `sheet_dataset_service`, formula sidecar/evaluator, `dataset_aggregation` | Current merged candidate; 24-sheet XLSX with arithmetic and cross-sheet `SUM` formulas | `employee-execution-large-workbook/`: 24 sheets, 500 data rows / 547 catalog rows, leading-zero IDs and blanks; 25-row assignment retrieval **1725.00** without supplied rows; `B2 2→5` sync update `recalc_status=complete`, `D2=55`, `Summary!B2=1758`, `B22=34533`; UI export byte-identical; restart/reopen shows 24 sheets and persisted values. Two-sheet edit/export/reload 6/6 remains in `employee-execution-office-workbook/` | Arbitrary Excel functions, macros, charts, external links and full compatibility not claimed. |
| 6 | Create a user canvas, bind data, calculate, edit with readback, export XLSX, reload | Canvas capability manifest/adapter, authoritative frame, revision-checked edits, office export | Current merged candidate; table adapter | `employee-execution-canvas-capability/`: 290 → edit 110 → 325; XLSX export; reload `revision 2 · 4 rows`; no page errors | Arbitrary spreadsheet controls/formulas/future components not claimed. |
| 7 | Grounded selection, calculation and assessment with citations | `core/table_selection.py`, `core/dataset_aggregation.py`, `core/review_result.py`, `core/assessment_rules.py`, review contract, deterministic receipts | Current merged candidate; deterministic rules for rule-expressible policies | `employee-execution-deterministic-judgment/`: V1 18/18, V3 19/19, safe abstention passed; `employee-execution-deterministic-rule-authoring/`: rules authored in the ordinary capability panel, `served_provider=deterministic`, `D-1 APPROVE / D-2 REVIEW / D-3 DENY`; model `ollama`/`llama3.1:8b` remains **failed** (17/18 V1, 18/19 V3) | Model-dependent judgment is unqualified; deterministic path does not interpret arbitrary prose. |
| 8 | Produce editable DOCX/PPTX and an email draft | `core/office_service.py`, artifact renderers, `core/canvas_email_service.py`, assignment deliverable adapters | `06d80f834`; controlled outbox; no live send | DOCX active/reload hashes; PPTX 4 slides with result/findings/sources (`grants-presentation/`); email draft `[Quote]`/`[Grant]` with greeting/signature; controlled outbox exactly one line per job | Image/chart understanding and real recipient delivery are not claimed. Real send remains disabled. |
| 9 | User-created canvases inherit supported capabilities | Versioned capability manifests, adapter registry, canvas routes, deterministic rule mode | Current merged candidate; table adapter + deterministic rules | `employee-execution-canvas-capability/`: manifest/canvas operations; `employee-execution-deterministic-rule-authoring/`: manifest edited in the normal panel, CSV bound, deterministic assess, exact-content approval and decisions used; `employee-execution-deterministic-judgment/`: rules qualified | Table adapter only; no future-component or arbitrary-formula claim. |
| 10 | Long-running multi-source assignment with missing information, browser close, restart, delayed response, changed teaching, artifact restart, cancellation/uncertain-effect controls | `core/task_lifecycle.py`, GoalRun services, executor checkpoints, durable waits, HITL routes, reconciliation | `06d80f834`; one worker; controlled transport | Sales and grant composites: waiting → browser closed → backend PID changed → same run resumed → correlated response → artifact. `test_assignment_executor` recovery/cancel/uncertain/duplicate/artifact-restart tests pass in the 284 suite | One-worker topology only. No multi-day soak, multi-worker campaign or unrestricted autonomous browsing. Real credential expiry is not exercised on this candidate. |
| 11 | Approval binds the exact payload/artifact; controlled continuation; duplicate approval does not duplicate transport; changed payload requires fresh review | `core/proposal_service.py`, `core/hitl_resume.py`, assignment approval binding | `06d80f834`; accepted atomic-binding repair from `dcac5d323`; controlled outbox | Accepted verifier evidence `conversation-learning-dcac5d323/`; composite approvals executed once; duplicate/rejection/drift controls in the 284 suite | Real-provider send is not part of this candidate. Recipient delivery is unclaimed. |
| 12 | Install/start the local app, sign in, use the supported workspace, restart and recover | Normal auth, Assignments/Activity, durable storage, local UI entry points, documented launch | Current merged candidate; normal app on 8071/3130, isolated world | `employee-execution-integrated-local-journey-repaired/`: login, teach, upload, wait, real backend restart, resume, artifacts (550.00 active / 500.00 revised); verify.json passed. `employee-execution-large-workbook/`: 24-sheet canvas reopened after restart with all tabs and values | Hosted deployment/public release owner-deferred; live connectors and real sends not performed. |

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

### Deterministic taught-rule judgment (qualified)

A second, model-free path is qualified for rule-expressible policies:
`assessment_mode=deterministic` with ordered `decision_rules` on the versioned
capability manifest. Rules validate against bound columns/decisions, require a
REVIEW fallback, evaluate first-match-wins, cannot match blank/unparseable
values, and return REVIEW plus a durable unresolved requirement when nothing
matches. On the frozen 24-record set it scores **18/18 determinate under V1 and 19/19
under V3** (the accepted phase-aware V2 scoring: blank Risk is immaterial once
the policy says "regardless of Risk"), with safe abstention passed and no gap
approved. The earlier 18/18 V3 figure used the old scoring interpretation and is
preserved as superseded evidence. Evidence:
`employee-execution-deterministic-judgment/`.

This does **not** qualify discretionary judgment: the model-dependent
configuration remains failed, and model funding is optional rather than a
blanket blocker while the deterministic path covers rule-expressible work.

### Qualification on a fixed unseen set

The intended local launch configuration was then qualified against a frozen
24-record set (`sha256 54a7037e…`, committed before the run) covering exact
thresholds, decimals, exceptions, missing values, conflicting context and a
correction with a real restart:

- **Attempt 1** (default 600 s provider budget, 4096 context): **incomplete** —
  three calls ended at exactly 10m0s; no judgment observed. Preserved.
- **Attempt 2** (same set; `OLLAMA_REQUEST_TIMEOUT=1800`, context 8192):
  completed. `create` **17/18 (94.4%)**, `correct` **18/19 (94.7%)**,
  `after-restart` **18/19 (94.7%)**; all **8** V1→V3 flips correct, including the three non-North
  `Risk High` records that isolate the two rule changes; 10/10 restart gates.
- Stable error: `Q-021` (Region blank, otherwise approvable) returns REVIEW.
- Serious gap behaviour: `Q-012` (**Amount 0**) is APPROVE in every phase,
  although the policy gives no rule below 50. That is an invented approval.

**Verdict:** pipeline verified, configuration **not** reliable enough for
autonomous substantive recommendations. Substantive recommendations from this
configuration require **human review**; autonomous decisions stay outside its
supported scope.

Review is enforced server-side, not just documented. Approval is an atomic
compare-and-swap on a monotonic assessment revision plus the execution id and
capability revision; a stale session cannot overwrite newer canvas work, and
consumption reloads authoritative state. The default policy
(`ATOM_ASSESSMENT_REVIEW_POLICY=always`) is temporary containment: it requires
human approval for **every** assessment, whatever the model reports about its
own uncertainty — a confident
wrong APPROVE reports none, so model-reported uncertainty cannot be the gate.
Approval is bound to the execution, source and policy revisions, the canvas
revision and the **recomputed digest of one canonical assessment artifact**
(decisions, basis, evidence, policy references, unresolved requirements). The
digest is recomputed from persisted content at approval and at consumption, so
changing a decision, basis entry, evidence row or unresolved requirement — even
with the stored hash untouched — refuses downstream use (`content_drift`) until
a fresh review. There is no separate decision map: downstream decisions are
derived from the approved artifact.
The existing assess response withholds the actionable artifact (`rendered`,
`authorized=false`) until approval, and the capability read exposes the
authorization state. `scoped` is the earned path: it requires both a server-controlled qualification
entry (`backend/config/assessment_qualification.json`, status `qualified`, not
revoked) and the owner's autonomy policy for the registered `canvas_assessment`
topic (mode × maturity × trust). Both are re-evaluated from live state at
consumption: withdrawing the owner gate stops downstream use immediately even
though the assessment recorded `review_required=false`. The qualification entry
is scoped to its contract version, serving configuration, policy text, decision
vocabulary and subject field — a model name authorizes nothing on its own. The failed llama3.1:8b configuration is
registered as `failed`; revocation is re-read at consumption. `model_reported`
is removed — a model cannot authorize itself.

Scoring correction (v2): a blank field is a gap only when the policy in force
depends on it. `Q-010` (blank Risk) is a gap under V1 but scored under V3
("regardless of Risk"). Under v2 the deterministic V3 phase is 19/19 (1.0); the verdict
is unchanged. Evidence:
`docs/acceptance/evidence/durable_assignment_20261031/employee-execution-assessment-qualification/`.

## Practical acceptance status

**Verifier acceptance (2026-10-31):** accepted within the local, single-worker,
controlled-outbox scope at source `b7ee7ee22`. See
`VERIFIER_ACCEPTANCE_2026-10-31.md`. Autonomous substantive judgment, live
sending, multi-worker execution and universal feature reliability remain
explicit exclusions; the model qualification verdict remains failed.

Closed with browser-level evidence:

- the five practical assignment boundaries — wait→restart→resume (backend PID
  changed), changed-source-revision refusal, ambiguous mapping resolution,
  cancellation surviving reload with no late effect, duplicate resume
  dispatching once — **5/5**, controlled outbox effects **0**
  (`assignment-recovery-browser/`), with executor/route controls in
  `employee-execution-assignment-boundaries/`;
- exact-content approval through the public routes
  (`employee-execution-assessment-approval/`);
- typed next-step outcomes at the assessment boundary — `execute` / `clarify` /
  `propose` / `refuse`, with `reconcile` reserved (`661c751b2`);
- **durable assessment clarification**: the original objective, request
  identity, source/teaching revisions and one obligation per unresolved
  requirement persist on the canvas. Each obligation has a stable
  `requirement_id`; an answer must identify it (subject-only answers are
  refused when a subject has more than one requirement). Source, policy,
  manifest and canvas revisions are revalidated before recording and before
  resumed dispatch; a moved revision preserves the answer as historical input
  and returns `reassessment_required` instead of transferring it. Answers use
  the same CAS, clear any prior approval, and a full answer re-dispatches the
  same work with the original objective, the identified answers and an
  `ACCEPTED REVISIONS` block (`employee-execution-assessment-clarification/`).

Closed after the verifier handoff:

- **bounded standing authority for external effects**: an explicit user grant
  (named recipients, hard 1–20 effect bound, optional expiry) is consumed under
  the assignment CAS before dispatch; exhausted/out-of-scope steps fall back to
  approval. Only the controlled outbox opts in; live send stays
  approval-required (`employee-execution-autonomy-boundaries/`);
- **execution boundaries**: post-effect runtime errors, parse errors, timeouts
  and cancellations are `uncertain` (never `failed_before_effect`) and never
  resend; `max_cost_usd` is a conservative pre-dispatch reservation with
  concurrent/retry accounting, hard refusal before overspend, an explicit
  soft-limit path, and wall-time enforcement during the operation
  (`employee-execution-execution-boundaries/`). A TEAM_LEAD reconcile route settles
  applied/not_applied/insufficient with mandatory evidence, never resending an
  applied effect (`employee-execution-autonomy-boundaries/`);
- **draft vs authorized assessment UI**: the canvas panel labels unapproved
  assessments as drafts, approves the exact execution, answers durable
  clarifications, and exposes decisions only when authorized;
- **integrated two-domain autonomous journey**: sales (85) and grants (4250)
  from unfamiliar datasets, one bounded grant per send, backend restart while
  both wait, both complete on return, **2 effects / 0 assignment approvals**
  (`two-domain-autonomous-journey/`, 5/5). The same journey was rerun on the
  repaired execution boundary (`0e21fd0f7`): 5/5, PID 43597 → 43717, exactly
  two controlled effects, zero HITL rows, artifact hashes recorded
  (`two-domain-autonomous-journey-repaired/`).

Still open:

- independent verification of these runs — acceptance is not self-granted;
- multi-worker/soak, live connectors and real sends remain outside this
  candidate's scope.

## Accepted milestone — bounded autonomous local execution (2026-10-31)

Verifier-accepted within its controlled, single-worker scope.

**What is accepted**

- Unfamiliar fixture data in two domains, durable waiting, a real backend
  restart, resume, artifact creation and **controlled** effects without
  redundant per-send approval.
- Bounded standing authority: one 1-use grant per domain, consumed under the
  assignment CAS and **durably recorded** at
  `GoalRun.parameters.task_lifecycle.assignment.standing_authority`
  (`used_effects=1`, `max_effects=1`, `status=exhausted`), with the usage
  operation id matching the outbox effect.
- The repaired-source smoke: 5/5 checks, PID 43597 → 43717, exactly two
  controlled effects, zero `assignment_approval` HITL rows, both DOCX hashes
  verified.

**Limits that remain**

- The model qualification **failed**; autonomous substantive judgment is
  outside this configuration's supported scope and requires human review.
- Live autonomous sending is unsupported (controlled outbox only).
- Multi-worker/soak and live-connector qualification are unclaimed.
- Hard-cost protection depends on trusted adapters declaring truthful bounds.
- Hosted deployment remains deferred.

**Identity:** code/evidence `0e21fd0f7` (repaired source `b7ee7ee22`;
recorded head `803ef2666`); evidence
`two-domain-autonomous-journey-repaired/`.

## README marketed-surface coverage

The frozen README claim inventory (123 eligible functional claims) was
re-executed on the integrated candidate after merging Agent 2's
feature-readiness branch:

- **99 / 123 verified functional claims (80.5%)** in the final wave after the
  verifier-driven corrections. The earlier 100/123 and 83/123 figures are
  history: the first was withdrawn for status-only assertions, the second was
  an intermediate correction.
- 24 claims are not counted (partial/unverified/inaccurate/blocked/
  environment-limited/architecture-only); see
  `docs/acceptance/readme_feature_readiness_2026-10-31/COVERAGE_REPORT_2026-10-31.md` §4.
- The 80% breadth checkpoint is **met**; it is not a readiness claim.
- Security 8/8 verified; performance, compatibility and comparative claims
  remain tracked separately and are not part of the functional numerator.
- No group errors in the integrated rerun.

Evidence: `docs/acceptance/evidence/durable_assignment_20261031/employee-execution-integrated-readme/`.
This is a self-assessment pending independent verifier agreement; it is not a
release approval. The 80% breadth checkpoint is met, while the practical
employee gates are tracked separately in `REMAINING_WORK_2026-10-31.md`. The rerun used the bounded local provider/OAuth/MCP stub, not
live provider qualification.

## Historical records

The full previous ledger, including the 2026-10-29 table and all appended
status sections, is preserved at
`docs/acceptance/PRODUCT_GOAL_LEDGER_HISTORY_2026-10-29.md`. Evidence
directories referenced by that history remain unchanged.
