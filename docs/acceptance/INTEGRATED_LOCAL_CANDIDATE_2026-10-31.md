# Integrated local candidate — 2026-10-31

This is the reproducible local candidate for the employee-execution,
complex-teaching and durable-recovery goals. It is **not** a hosted deployment,
public release or universal reliability claim. Hosted deployment and
publication remain deferred by the owner.

## Identity

| Item | Value |
|---|---|
| Branch | `codex/employee-execution-readiness` |
| Final code/evidence | `619960832` |
| Evidence source | `06d80f834` (product teaching `3e344f5b1`) |
| Agent 2 merge | `931892be0` |
| Integrated README rerun | `619960832` |
| Preserved core | `local-core-2026-10-30-final` → `da9cc8b12` |
| Preserved reviewed successor | `conversation-learning-2026-10-30` → `d2b297deb` |
| Python | 3.11.16 |
| Node | 20.19.6 |
| Product profile | `core` |
| Backend / frontend | `127.0.0.1:8071` / `127.0.0.1:3130` |
| Effect boundary | controlled local outbox; no real send |

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
Not claimed: a browser-level rerun of these five on this candidate, or
multi-worker/soak behaviour.

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
  24-record set scored **17/18 determinate (94.4%)** in every phase, with all
  eight V1→V3 flips correct and 10/10 restart gates. But the error is stable
  (`Q-021`, blank Region → REVIEW) and one untaught value was **approved**
  (`Q-012`, Amount 0). Autonomous substantive decisions therefore stay outside
  this configuration's supported scope; a human must review its
  recommendations, and the product enforces that: the default
  `ATOM_ASSESSMENT_REVIEW_POLICY=always` requires approval for every
  assessment even when the model reports no uncertainty. Approval is bound to a
  canonical assessment artifact by a digest recomputed from persisted content
  (not a stored hash), plus execution/source/policy/canvas revisions; a changed
  decision, basis, evidence entry or unresolved requirement requires fresh
  review, and the assess response withholds the actionable artifact until
  approval. A stronger model is a candidate remedy, not a proven one.
  Cloud providers remain unavailable (DeepSeek key empty, OpenRouter HTTP 402);
  see `employee-execution-assessment-qualification/`,
  `employee-execution-substantive-assessment/` and the historical
  `employee-execution-assessment-blocker/`.
- **PPTX** is verified as an editable 4-slide artifact with grounded text; it
  is not a visual-design or chart-rendering claim.
- **Live connectors**: current candidate uses controlled local uploads. The
  historical Microsoft live-connector evidence is source-bound to `001f93472`
  and is not repeated here.
- **Large workbook/formula recalculation** was not rerun on this candidate;
  historical 24-sheet evidence is preserved but not merged into the current
  claim.
- **Long-running**: one worker, controlled transport, actual backend restart
  and browser close. No multi-day soak, multi-worker campaign or real
  credential expiry.
- **Approval/send**: atomic payload binding is accepted; controlled
  continuation executed once; duplicate approval replayed; no real send and no
  recipient-delivery claim.
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
