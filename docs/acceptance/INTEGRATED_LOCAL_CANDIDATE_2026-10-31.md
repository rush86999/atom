# Integrated local candidate — 2026-10-31

This is the reproducible local candidate for the employee-execution,
complex-teaching and durable-recovery goals. It is **not** a hosted deployment,
public release or universal reliability claim. Hosted deployment and
publication remain deferred by the owner.

## Identity

| Item | Value |
|---|---|
| Branch | `codex/employee-execution-readiness` |
| Final candidate | `2ebeddfb1` |
| Evidence source | `06d80f834` (product teaching `3e344f5b1`) |
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

A substantive model-backed assessment was attempted on an unfamiliar six-record
grant dataset with a declared policy and decision labels. It is **blocked by
external model infrastructure**, not completed:

- DeepSeek direct: `DEEPSEEK_API_KEY` is present but empty; no deepseek client
  was built (`pin_unavailable`).
- OpenRouter / `deepseek/deepseek-v4-pro`: the pin resolved and dispatch was
  attempted; OpenRouter returned HTTP 402 "requires more credits" for the
  6000-token request; fallback models also returned 402 (`empty_payload`).
- Local Ollama: model storage is on an unreadable/unmounted external volume.

The failed-closed response, sanitized provider errors, dataset hash and policy
are preserved in
`docs/acceptance/evidence/durable_assignment_20261031/employee-execution-assessment-blocker/`.
The smallest required input is a funded provider key with a declared review
model, or a readable local Ollama model store. No assessment-quality claim is
made until then. Historical DeepSeek assessment/send qualifications remain
bound to their own source/configuration and are **not** merged into this
candidate's claim.

Declared operation → model:

| Operation | Model/provider |
|---|---|
| Teaching review/promotion, assignment planning, calculation, DOCX/PPTX/XLSX rendering, approval | deterministic application code; no model dispatch |
| Canvas assessment | **blocked** — attempted DeepSeek direct, OpenRouter and local Ollama; no usable model infrastructure |
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
  world directory is created.
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

## README breadth on the integrated candidate

Agent 2's frozen inventory (123 eligible functional claims) was re-executed
after the merge: **100 verified (81.3%)**, 23 not counted, security 8/8, no
group errors. The run used `ATOM_PRODUCT_PROFILE=full` and the bounded local
OpenAI/Anthropic/OAuth/MCP stub, with schedulers/pollers off. It is a
self-assessment pending independent verifier agreement, not a release approval.
Evidence:
`docs/acceptance/evidence/durable_assignment_20261031/employee-execution-integrated-readme/`
and `docs/acceptance/readme_feature_readiness_2026-10-31/INTEGRATED_RERUN_2026-10-31.md`.

## Known limitations and failure records

- **Canvas assessment is blocked by external model infrastructure.** DeepSeek
  direct has an empty key, OpenRouter returns HTTP 402 (no credits), and local
  Ollama's model store is unreadable. The review contract is unit-tested, but
  no live model-quality claim is made. See
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
9. the declared model-provenance boundary and the assessment blocker
   (deterministic paths; DeepSeek/OpenRouter/Ollama attempts).

Acceptance is not self-granted. This document supplies the executable
harnesses, source/config identity, browser actions versus setup, restart
identities and preserved limitations for independent verification.
