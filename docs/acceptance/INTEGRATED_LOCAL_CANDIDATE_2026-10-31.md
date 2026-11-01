# Integrated local candidate — 2026-10-31

This is the reproducible local candidate for the employee-execution,
complex-teaching and durable-recovery goals. It is **not** a hosted deployment,
public release or universal reliability claim. Hosted deployment and
publication remain deferred by the owner.

## Identity

| Item | Value |
|---|---|
| Branch | `codex/employee-execution-readiness` |
| Verifier acceptance | `VERIFIER_ACCEPTANCE_2026-10-31.md` — accepted source `b7ee7ee22` |
| Final code/evidence | `74464af69f98` (product code `0aa6105e4872`; guided rule authoring in `bc164fb96632`) |
| Assessment safety | `460f38c27` (atomic approval/scoped autonomy), `b80288e4e` (authoritative reads), `6363e3794` (route-level exact approval), `8123f12c6` + `099c15e02` (clarification identity/revisions) |
| Deterministic judgment | `assessment_mode=deterministic`; 18/18 V1 and 19/19 V3 under the V2 overlay, safe abstention passed (`employee-execution-deterministic-judgment/`); rules authored through the ordinary capability panel (`employee-execution-deterministic-rule-authoring/`) and the guided editor (`employee-execution-guided-rule-authoring/`, 13/13) |
| Normal-app employee journey | `31ba9725e02a`, clean (`dirty=false`): teach/conflict/qualification, upload, mapping, wait, real backend restart, resume, DOCX (550.00 Arial 11), revised work (500.00 Calibri 14) (`employee-execution-integrated-local-journey-repaired/`) |
| Unforced teaching | `bc164fb96632`, clean (`dirty=false`): welcome wizard completed with visible clicks, Teaching optional fields opened by click, form filled without `force=True`, lesson recorded and survived reload (`employee-execution-unforced-teaching/`, 9/9) |
| Office workbook | 24 sheets / 500 data rows / 547 catalog rows; 25-row retrieval 1725.00; edit `B2 2→5` recalculates 55 / 1758 / 34533; byte-identical export; restart/reopen with 24 tabs (`employee-execution-large-workbook/`). Two-sheet edit/sync/download/reload 6/6 remains in `employee-execution-office-workbook/` |
| Canvas capability | 290 → edit → 325, XLSX export, revision 2 reload (`employee-execution-canvas-capability/`) |
| Microsoft read-only live | `0aa6105e4872`, clean: account `rish@brennan.ca`, genuine Outlook workbook attachment, 8/8 rows, independent **216700**, product materialization, assignment retrieval, restart/reopen (`live_qualification_20261101/part-a/`; normal product `email_ingest_message` connector entry point in `part-a-connector/`) |
| Live Outlook send | one-use grant `sga-live-qual-…` exhausted 1/1; exact body binding; provider accepted; exactly one Sent Items row; restart terminal/no second effect; **recipient inbox delivery not claimed** (`live_qualification_20261101/part-b/`) |
| Real-transport gate | both live flags + one-use recipient-bound grant; one authorized send executed; default remains controlled (`employee-execution-live-authority-gate/`) |
| Practical browser recovery | `b24f67c29` / `e564890e7` (5/5 checks) |
| Bounded autonomy boundaries | `814962078` / `24b0633df` (185 backend + 6 frontend tests) |
| Execution boundaries | `b7ee7ee22` / `84da4cbfd` (81 assignment executor/route controls) |
| Two-domain autonomous journey | `814962078` / `24b0633df` (5/5); repaired-source smoke `0e21fd0f7` (5/5, 2 effects, 0 approvals) |
| Evidence source | `06d80f834` (product teaching `3e344f5b1`) |
| Agent 2 merge | `931892be0` |
| Integrated README rerun | `619960832` |
| Preserved core | `local-core-2026-10-30-final` → `da9cc8b12` |
| Preserved reviewed successor | `conversation-learning-2026-10-30` → `d2b297deb` |
| Python | 3.11.16 |
| Node | 20.19.6 |
| Product profile | `core` |
| Backend / frontend | `127.0.0.1:8071` / `127.0.0.1:3130` |
| Effect boundary | controlled local outbox by default; one authorized live send executed; recipient inbox delivery not claimed |

The accepted tags are not moved. This candidate is a successor branch.

## Supported configuration

```text
ATOM_PRODUCT_PROFILE=core
ATOM_LOCAL_ONLY=true
ATOM_TURN_DECISION_ROUTING=0
ATOM_TASK_LIFECYCLE_ENABLED=1
ENABLE_SCHEDULER=false
ENABLE_INGESTION_SYNC=false
ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT=1
ATOM_ASSIGNMENT_OUTBOX=<world>/controlled-outbox.jsonl
DATABASE_URL=sqlite:///<world>/atom.db
ATOM_DATA_DIR=<world>/data
LANCEDB_URI=<world>/data/atom_memory
ATOM_OFFICE_DIR=<world>/data/office
ATOM_ASSIGNMENT_OUTPUT_DIR=<world>/data/assignments
```

### Model provenance

The two-domain acceptance uses **deterministic assignment, teaching,
calculation, artifact and approval paths**. It does not dispatch an LLM for the
final business result.

A substantive model-backed assessment **was executed** on an unfamiliar
six-record grant dataset with a declared policy, a policy correction and a
fresh post-restart judgment. The cloud blockers remain real (DeepSeek key
empty; OpenRouter HTTP 402), but a readable local model store was found and
served: `ollama` / `llama3.1:8b` (Q4_K_M, CPU) on a separate server over
`~/.ollama/models-local`.

| Phase | Certification | Judgment |
|---|---|---|
| `create` (policy v1) | certified, 6/6 subjects, `served_provider=ollama`, `served_model=llama3.1:8b` | **5/6** |
| `correct` (policy v3, exception removed) | certified, changed policy revision | **6/6** |
| `after-restart` (policy v3, new backend pid) | certified, identical request hash, identical decisions | **6/6** |

The single failure is stated plainly: under v1 the model approved `A-204`
(Amount **95**) and cited `Amount >= 100`, although the row was rendered as
`Amount=95`. That is a model reading error on the boundary record, not a
rendering defect; the same model returned `A-204` = REVIEW and `A-205` =
APPROVE after the correction. So the **assessment pipeline** is verified
end-to-end with real provenance, while `llama3.1:8b` is **not** reliable enough
on the more complex policy to claim correct boundary judgment. A stronger
serving model is required for that claim.

Evidence:
`docs/acceptance/evidence/durable_assignment_20261031/employee-execution-substantive-assessment/`.
The earlier failed-closed cloud attempts are preserved as history in
`employee-execution-assessment-blocker/`. Historical DeepSeek assessment/send
qualifications remain bound to their own source/configuration and are **not**
merged into this candidate's claim.

Declared operation → model:

| Operation | Model/provider |
|---|---|
| Teaching review/promotion, assignment planning, calculation, DOCX/PPTX/XLSX rendering, approval | deterministic application code; no model dispatch |
| Canvas assessment | `ollama`/`llama3.1:8b` (local, CPU) — pipeline verified; judgment 5/6 on policy v1, 6/6 on the corrected policy |
| Chat prose generation | not exercised for a final result in this acceptance |

## Install

From a clean checkout of the branch:

```bash
python3.11 -m venv backend/venv
backend/venv/bin/pip install --prefer-binary -r backend/requirements.txt
cd frontend-nextjs
npm ci
NEXT_PUBLIC_API_URL=http://127.0.0.1:8071 \
NEXT_PUBLIC_ALLOW_LOOPBACK=1 \
NEXT_PUBLIC_ASSIGNMENT_TRANSPORT=controlled \
./node_modules/.bin/next build --webpack
```

`--webpack` is required in this worktree because `node_modules` is a symlink to
the shared install and Next 16 Turbopack rejects the out-of-root symlink.

## Launch

```bash
export WORLD=/absolute/path/under/backend/data/acceptance_worlds/<new-world>
export ADMIN_PASSWORD='<local-only password>'
scripts/acceptance/launch_integrated_local_candidate.sh
```

Safety contract before the first write:

- `WORLD` must be under the configured `worlds.root` from
  `backend/config/world_storage.json` (default
  `backend/data/acceptance_worlds`), not the root itself, the repo, home,
  `backend/data`, or a database file.
- A new world must not exist or must be empty. An existing world must carry
  `.atom-integrated-world.json` with exactly the same resolved world, repo and
  database paths; a live PID in its marker/PID files refuses reuse.
- Both ports are checked before startup. The backend health response must be
  HTTP-successful and must report the exact child PID, backend CWD, database
  path, port, source ID and instance ID. The frontend must report
  `service=atom-frontend` and healthy status.
- `core.world_storage_guard check` and
  `scripts.orchestration_acceptance.storage_policy space` run before any
  world directory is created. A fresh checkout with a `local` layout gets the
  configured worlds root created after validation; a `drive_symlink` layout
  never is.
- `SECRET_KEY` is generated once and persisted at `$WORLD/.atom-secret`
  (mode 600); there is no fixed fallback.
- On startup failure the script stops only the backend/frontend PIDs it
  started. It never stops the existing service on `:8001`.

The script creates the world's data/office/assignment/LanceDB directories and
writes PIDs/logs under `$WORLD`.

First sign-in: `admin@example.com` with `ADMIN_PASSWORD`. The world is isolated;
do not point `DATABASE_URL` at a live development database.

## Acceptance harnesses

All commands use the normal browser UI for user actions and read durable state
through the public API for assertions. Controlled transport writes a local
JSONL outbox; no real email is sent.

### 1. Two-domain composite (sales quote + grant review)

```bash
WORLD=/absolute/path/to/isolated-world
python scripts/acceptance/composite_long_running_part1.py \
  --frontend http://127.0.0.1:3130 \
  --password-file "$WORLD/password.txt" \
  --csv "$WORLD/integrated_quote.csv" \
  --out-dir "$WORLD/evidence/sales-composite" \
  --agent-name "Integrated Quote Specialist" \
  --objective "Sum Price for the integrated quote sheet 2026-10-31" \
  --correlation "quote-missing-currency-20261031"
# close the browser, restart the backend against the same world, then:
python scripts/acceptance/composite_long_running_part2.py \
  --frontend http://127.0.0.1:3130 \
  --password-file "$WORLD/password.txt" \
  --out-dir "$WORLD/evidence/sales-composite" \
  --part1 "$WORLD/evidence/sales-composite/part1.json" \
  --objective "Sum Price for the integrated quote sheet 2026-10-31" \
  --second-objective "Sum Price for the revised clean quote sheet 2026-10-31" \
  --outbox "$WORLD/controlled-outbox.jsonl"
python scripts/acceptance/composite_long_running_verify.py \
  --frontend http://127.0.0.1:3130 \
  --password-file "$WORLD/password.txt" \
  --out-dir "$WORLD/evidence/sales-composite" \
  --part1 "$WORLD/evidence/sales-composite/part1.json" \
  --objective "Sum Price for the integrated quote sheet 2026-10-31" \
  --second-objective "Sum Price for the revised clean quote sheet 2026-10-31" \
  --outbox "$WORLD/controlled-outbox.jsonl" --negative-controls
```

Grant domain: same commands with `--measure "Approved Amount"`,
`--context grants`, `--qualification verified`, `--mapping-candidate "Award
Amount"`, `--second-source grant_applications_revised.csv`,
`--second-candidate "Approved Award"`, `--greeting "Dear grants committee,"`,
`--signature "Grants team"`, `--subject-prefix "[Grant]"`, and the grant
objectives. The exact invocations are in the evidence `README`/manifest.

### 2. User-created canvas capability

```bash
python scripts/acceptance/canvas_capability_local.py \
  --frontend http://127.0.0.1:3130 \
  --password-file "$WORLD/password.txt" \
  --agent-id <grant-agent-id> \
  --csv "$WORLD/pipeline_a.csv" \
  --out-dir "$WORLD/evidence/canvas-capability"
```

Expected: calculate 290.00, edit row 2 75→110 with readback, calculate 325.00,
download a real XLSX, reload `revision 2 · 4 rows`, no page errors.

### 3. Conversation-derived guidance-only lesson

Use the product email-canvas API to create a local thread and add an authored
message, then open `/learning?thread=<thread_id>` in the browser. Draft a
lesson, check **Guidance only**, supply the email format spec, confirm and
promote. Expected candidate: `method_status=not_applicable`,
`review_ready=true`, `format_spec={greeting, signature, subject_prefix}`, and a
promoted `lesson_id`. No dummy arithmetic operation is created.

### 4. Focused regressions

```bash
cd backend
TESTING=1 /Users/rushiparikh/projects/atom/backend/venv/bin/python -m pytest \
  tests/test_conversation_learning.py \
  tests/test_conversation_learning_routes.py \
  tests/test_chat_teaching_route.py \
  tests/test_assignment_routes.py \
  tests/test_assignment_executor.py \
  tests/test_assignment_resource_boundary.py \
  tests/test_hitl_resume.py \
  tests/test_memory_context_assembler.py \
  tests/test_artifact_teaching_context.py \
  tests/test_review_result.py \
  tests/test_review_contract.py \
  tests/test_canvas_training_context.py -q
```

Observed: **284 passed**. Frontend learning tests: **5 passed**; TypeScript
`--noEmit` clean.

## Evidence

Committed evidence is under
`docs/acceptance/evidence/durable_assignment_20261031/employee-execution-06d80f834/`.
It contains:

- sales and grant `part1.json`, `verify.json`, `negative-controls.json`;
- active/reload/revised DOCX artifacts and hashes;
- the grant PPTX (4 slides: Overview, Result, Findings, Sources);
- canvas JSON, exported XLSX and screenshot;
- conversation guidance candidate JSON and screenshots;
- targeted backend/frontend/TypeScript logs;
- a manifest with SHA-256 for every file.

## Settings BYOK refresh without restart

Verified through the normal Settings key route and the normal Chat route, with
no process restart:

- save key A → Chat succeeds and the bounded provider sees key A;
- replace with key B → Chat succeeds and the provider sees key B;
- delete the key → no new provider call; Chat fails closed;
- both key values are absent from captured logs.

Fixes: `LLMService._get_handler` compares a non-secret credential fingerprint
and rebuilds its cached `BYOKHandler` on save/replacement/removal;
`BYOKHandler.credentials_changed()` reads the refreshed store fingerprint; and
a credential change clears the provider discovery backoff so the new key's
catalogue is refreshed immediately.

The normal journey was then re-run **without any model pin**: with the bounded
provider advertising the models the router actually selects, normal routing
served key A on `gpt-4o-mini` and the replacement key on `gpt-5.6-luna` /
`o4-mini`, and removal still made no new call. The earlier pinned run is kept as
history; the pin is now an explicit diagnostic override only.

Evidence:
`docs/acceptance/evidence/durable_assignment_20261031/employee-execution-byok-refresh/`
(`normal-routing/` for the unpinned run). The provider is a bounded local
OpenAI-compatible server, not a real OpenAI account; this is not a
real-provider send qualification.

## Practical assignment boundaries

**Verifier acceptance (2026-10-31):** the exact-content approval, five recovery
boundaries, execution-boundary repairs and two-domain controlled-autonomy
journey are accepted within the local, single-worker, controlled-outbox scope
at source `b7ee7ee22`. See `VERIFIER_ACCEPTANCE_2026-10-31.md`. This does not
qualify autonomous substantive judgment, live sending, multi-worker execution
or universal feature reliability.

The practical gate's five open boundaries now have named executable controls
that pass (executor and route level, scratch store):

- process restart while waiting — `test_crash_after_wake_before_advance_recovers`;
- changed-revision invalidation — `test_stale_task_revision_prevents_dispatch`;
- ambiguity — `test_ambiguous_mapping_correction_requires_source_identity`;
- cancellation — `test_cancellation_prevents_unstarted_effect`,
  `test_approval_after_cancellation_is_refused`,
  `test_cancelled_assignment_cannot_be_approved`;
- duplicate resume — `test_two_concurrent_resume_requests_dispatch_once`,
  `test_external_reply_matches_exact_correlation_once`.

Run: **8 passed**, 0 failed. Evidence:
`docs/acceptance/evidence/durable_assignment_20261031/employee-execution-assignment-boundaries/`.

### Browser journey

The same five boundaries were then exercised through the real Assignments
page against the standalone acceptance server (real routes and executor, one
scratch world, controlled outbox):

| Scenario | Browser evidence |
|---|---|
| Wait → restart → resume | backend PID changed, the assignment stayed `waiting` across the restart, then completed with the calculated result |
| Changed source revision | changing the active dataset version made the mapping correction show `Requested version … is not the active version …`; the mapping and the completed `85.00` result survived |
| Ambiguity | two confirmed mappings for `Total` were visible; an unqualified correction was refused with `more than one confirmed mapping exists`; choosing the identified mapping resolved to `Total → Unit Price` |
| Cancellation | cancelled status survived reload; a late correlated response returned the cancelled assignment and produced no effect |
| Duplicate resume | submitting the same correlated response from two pages at once produced one calculation dispatch/result and no outbox effect |

Run: **5/5 checks passed**, 0 failed, 0 controlled-outbox effects. Evidence:
`docs/acceptance/evidence/durable_assignment_20261031/assignment-recovery-browser/`
(`browser-recovery.json` + screenshots).

Not claimed: multi-worker or soak behaviour. The ambiguity scenario also
notes a UX limitation: the correction form is keyed by concept, so two
mappings that share a concept open the form on both cards. The route still
requires the mapping's sheet/version identity, and the safe path is the
correctable card.

### Bounded autonomy, budgets and reconciliation

- **Standing authority** is an explicit user grant, never model-inferred:
  outbound effects only, named recipients, a hard 1–20 effect bound and an
  optional expiry. The executor consumes one use under the assignment CAS
  before dispatch; exhausted, expired, out-of-scope or wrong-recipient steps
  fall back to ordinary approval. Only the acceptance-controlled outbox opts
  in; live email send stays approval-required.
- **Budgets** enforce `max_steps`, `max_attempts_per_step`,
  `max_wall_seconds` and `max_cost_usd`. Cost is a conservative reservation
  made under the assignment CAS **before dispatch**: a hard limit refuses the
  operation when committed + reserved + bound would exceed it (and refuses a
  cost-bearing adapter with no declared bound); concurrent reservations and
  retries share the same bound; uncertainty charges the bound and a proven
  no-effect failure releases it. A soft limit requires an explicit authorizer
  and exposes the overrun. Wall time is enforced during the operation.
- **Post-effect errors** are `uncertain`, never `failed_before_effect`: an
  ordinary runtime error, parse error, timeout or cancellation after an
  external adapter was invoked preserves uncertainty and never resends.
  Retryable `failed_before_effect` requires a trusted
  `ExternalOutcomeNotApplied` / `effect_possible=False`.
- **Uncertain effects** reconcile through a TEAM_LEAD route with mandatory
  evidence: `applied` never resends, `not_applied` creates a new operation for
  the next approval/resume, `insufficient` preserves the uncertain state. The
  Assignments panel exposes the evidence and all three verdicts.
- **Assessment clarification** re-dispatches the original selection ask with
  the answers as clarification context, so an answer value cannot contaminate
  selection. Each obligation carries a stable `requirement_id`; a subject-only
  answer is refused when the subject has multiple open requirements; changed
  source/policy/manifest revisions preserve answers as history and require a
  reassessment instead of transferring them; the resumed prompt names the
  accepted revisions. The route test pins a new execution and prior-approval
  invalidation.
- **UI**: the canvas panel labels an unapproved assessment as a draft, approves
  the exact execution, answers durable clarifications, and only exposes
  decisions once authorized.

Evidence: `employee-execution-autonomy-boundaries/` (185 backend + 6 frontend
tests at the autonomy source), `employee-execution-execution-boundaries/`
(81 assignment executor/route controls for the post-effect and cost fixes),
and `two-domain-autonomous-journey/` — sales **85** and grants **4250**
from unfamiliar datasets, one bounded grant per send, backend restart while
both wait, both complete on return with **2 effects / 0 assignment approvals**,
**5/5** browser checks.

## README breadth on the integrated candidate

Agent 2's corrected frozen inventory (123 eligible functional claims) reports
**83 verified (67.5%)**, 40 not counted, security 8/8. The earlier 100/123
figure was withdrawn after the verifier's audit of status-only and
source-inspection assertions; it is preserved only as history. The corrected
run used `ATOM_PRODUCT_PROFILE=full` and the bounded local
OpenAI/Anthropic/OAuth/MCP stub, with schedulers/pollers off. It remains a
self-assessment pending independent verifier agreement, and it does **not**
meet the 80% milestone gate.
Evidence:
`docs/acceptance/evidence/durable_assignment_20261031/employee-execution-integrated-readme/`
and `docs/acceptance/readme_feature_readiness_2026-10-31/INTEGRATED_RERUN_2026-10-31.md`.

## Known limitations and failure records

- **Canvas assessment requires human review for substantive recommendations.**
  The pipeline is verified end-to-end on `ollama`/`llama3.1:8b` with real
  provenance, correction and post-restart stability. Qualification on a frozen
  24-record set scored **17/18 on V1 and 18/19 on V3/post-restart**
  (94.4% / 94.7%), with all
  eight V1→V3 flips correct and 10/10 restart gates. But the error is stable
  (`Q-021`, blank Region → REVIEW) and one untaught value was **approved**
  (`Q-012`, Amount 0). Autonomous substantive decisions therefore stay outside
  this configuration's supported scope; a human must review its
  recommendations, and the product enforces that: the default
  `ATOM_ASSESSMENT_REVIEW_POLICY=always` requires approval for every
  assessment even when the model reports no uncertainty (temporary containment
  until a configuration is qualified). Approval is an atomic compare-and-swap on
  a monotonic assessment revision, bound to a canonical artifact digest
  recomputed from persisted content plus execution/source/policy/canvas
  revisions; a stale session cannot overwrite newer work, and a changed
  decision, basis, evidence entry or unresolved requirement requires fresh
  review. `scoped` autonomy requires both a scoped qualified registry entry and the
  owner's `canvas_assessment` autonomy policy, and both are re-evaluated at
  consumption: withdrawing the owner gate blocks the decision immediately.
  Qualification is scoped to contract version, serving configuration, policy
  text, decision vocabulary and subject field. The exact-content boundary is
  also exercised through the public routes: an unreviewed assessment is
  refused, approval of the exact execution authorizes it, and changing one
  reviewed decision while leaving the stored hash untouched makes authorization,
  decisions and re-approval refuse (`content_drift`). 106 focused
  assessment/canvas tests pass; evidence:
  `docs/acceptance/evidence/durable_assignment_20261031/employee-execution-assessment-approval/`.
  A stronger model is a candidate remedy, not a proven one.
  Cloud providers remain unavailable (DeepSeek key empty, OpenRouter HTTP 402);
  see `employee-execution-assessment-qualification/`,
  `employee-execution-substantive-assessment/` and the historical
  `employee-execution-assessment-blocker/`.
- **PPTX** is verified as an editable 4-slide artifact with grounded text; it
  is not a visual-design or chart-rendering claim.
- **Live connectors**: current candidate uses controlled local uploads. The
  historical Microsoft live-connector evidence is source-bound to `001f93472`
  and is not repeated here.
- **Large workbook/formula recalculation** was rerun on this candidate with a
  24-sheet, 500-row fixture: full-population retrieval, supported edit
  recalculation, byte-identical export and restart/reopen all passed
  (`employee-execution-large-workbook/`). Arbitrary Excel functions, macros,
  charts and external links are not claimed.
- **Long-running**: one worker, controlled transport, actual backend restart
  and browser close. No multi-day soak, multi-worker campaign or real
  credential expiry.
- **Approval/send**: atomic payload binding is accepted; controlled
  continuation executed once; duplicate approval replayed. One authorized live
  send ran under a one-use grant: exact body binding, provider acceptance,
  exactly one Sent Items row, restart terminal and no second effect. Recipient
  inbox delivery is not claimed.
- **Agent 2 integration**: the feature/Office/README worktree was observed at
  `da9cc8b12` with no published checkpoint. This candidate does not overwrite
  or merge Agent 2's work; integration remains at the shared teaching,
  assignment snapshot and approval interfaces.

## Verifier handoff

The independent verifier should challenge:

1. the exact pre-claim interleaving reproduction (recipient and canvas drift);
2. a changed source/teaching while waiting;
3. duplicate and out-of-order correlated responses;
4. cancellation followed by a late approval/response;
5. uncertain external effect and no automatic resend;
6. the guidance-only conversation candidate with no calculation method;
7. the two-domain browser/API composite and artifact hashes;
8. canvas export/reload and the XLSX contents;
9. the declared model-provenance boundary and the executed assessment
   (deterministic paths; local `ollama`/`llama3.1:8b` provenance, the 5/6 v1
   judgment and the 6/6 corrected/post-restart result).

Acceptance is not self-granted. This document supplies the executable
harnesses, source/config identity, browser actions versus setup, restart
identities and preserved limitations for independent verification.
