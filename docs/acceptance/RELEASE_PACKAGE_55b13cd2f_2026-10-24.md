# Release package — Atom candidate `55b13cd2f` (prepared 2026-10-24)

**Status: PREPARED, NOT EXECUTED. The live-deployment hold remains in
force. Do not start the candidate on :8001/:3000 until
`RELEASE_APPROVAL_55b13cd2f_2026-10-24.md` is explicitly approved.**

## Candidate identity

| Item | Value |
|---|---|
| Product commit | `55b13cd2fcab67ba8436618f7032339649cbdffc` |
| Backend release tree | `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-release-55b13cd2f-20261024` |
| Backend revision at HEAD | `55b13cd2fcab67ba8436618f7032339649cbdffc` |
| Backend tree state | clean (`git status --porcelain` empty) |
| Frontend runtime tree | `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-release-a729df5f5-20261024/frontend-nextjs` |
| Frontend build | `P5jHbHKTzj_38xHIMFoe9` |
| Frontend source | byte-identical to `55b13cd2f` (`git diff a729df5f5..55b13cd2f -- frontend-nextjs` empty) |
| Python | `/Users/rushiparikh/projects/atom/backend/venv314/bin/python` (3.14.7) |
| Harness content used | `a0c185e35` runner; final run HEAD `331b9eeac`; L3 contract correction `f40d2a881` (post-run recheck only) |

The backend release tree was created as a detached worktree at the product
commit and verified clean. The frontend production build is the verified
`P5jHb...` build; the frontend source did not change between the build
tree and the candidate.

## Verification evidence

- **Attempt 16: declared no-pilot isolated rehearsal.**
  - `no_pilot_isolation_asserted`: **true**; `pilot_untouched` was not a
    gate in this mode.
  - **Original result: 61/62.** The only failure is `l3_answer_correct`
    under the original predeclared gate (expected code, **no decoy
    mention**). The gate remains failed and the run is **not** an
    automated 62/62.
  - The captured L3 answer is **semantically correct per an independent
    manual assessment**: it serves **QUARTZ-77** for Zephyr-9 and
    correctly attributes BASALT-13 to Halcyon-2 as its archive key. That
    assessment is a separate human review, not the automated gate
    passing. The earlier lenient predicate was withdrawn; it could accept
    swapped or contradictory assignments. **No answer-scope contract
    change is requested in this package.**
  - S7: `deterministic:continuation`; 5s DeepSeek refinement was attempted
    and cancelled (`wait_timeout`); source
    `approved_records_q2026_114.txt`; fields exactly
    `["expiration_date"]`; `broader_comparison=false`; context
    `completed`; zero writes; outcome `partial` for the captured prior
    outlook obligation; `success=true`; **38.64s**.
  - Edit applied exactly once; identical re-ask completed with zero writes;
    provider policy gates passed (automatic; DeepSeek/Ollama/OpenCode
    Go/OpenRouter).
- **517 focused tests passed** on the final local batch. Two
  `test_fallback_honesty` receipt fixtures fail identically on parent
  `73bcae400` (pre-existing; outside this slice).
- Attempt 15 remains **functional verification passed; original
  pilot-preservation assertion not established**. It is not used as a
  62/62 claim.

Environment claim: the pilot `:8001`/`:3000` was absent **before** launch;
the disappearance is **unexplained**. No live-DB holder was present at
capture. The candidate ran on isolated `:8121` with its own scratch
DB/BYOK/vector/session paths. This is a declared no-pilot run; pilot
preservation is not being tested.

## Rollback backup (prepared, verified)

Fresh read-only SQLite backup:

```
/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-cutover-55b13cd2f-20261024/pre_cutover/atom-pre-cutover-55b13cd2f-20261025T034740Z.db
sha256 de62922c9d826d133e6813bd0455a6668a5576c175d2a3486a97310e58a82f6b
quick_check ok
users 49; chat_sessions 1025; chat_messages 5430; agent_executions 4257;
canvases 197; canvas_audit 1116; ingested_documents 3747; task_operation_records 269
gzip sha256 fd6eefd678d1caa73dc51a57beae6779565dcc50eaf2cbe966955485fcb58a51
```

Source live DB: `backend/data/atom.db`, sha256
`4b25241ef0754e33424bdaac74f5ee063e5b750eeaedf0f7c596429eb13aca7e`,
WAL size 0. **Immediately before cutover, re-verify the live DB is
unchanged; if any writer touched it, take a new fresh snapshot.** The
09:19 rehearsal backup is not the cutover rollback source.

## 1. Pre-cutover (approval required first)

1. Confirm the live DB fingerprint is still `4b25241...`, WAL size 0, and
   no live-DB/WAL/SHM holder exists.
2. Copy the four live config/secret files to the **private backup
   directory outside committed evidence**:
   `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-cutover-55b13cd2f-20261024/private_config_backup`
   (directory mode 700, files mode 600, via `cp -p`):
   `byok_config.json`, `byok_keys.json`, `byok_encryption_key`, `.env`.
   **Never copy their contents into `docs/` or any committed evidence.**
   Archive only the redacted metadata manifest
   (`pre_cutover_config_manifest.redacted.json`): file names, modes, and
   backup references, no secret values.
3. Record the candidate PIDs, ports, and the fresh backup manifest.
4. If the DB changed since the prepared backup, take a new fresh
   WAL-safe snapshot with SQLite's backup API and verify `quick_check` and
   row counts. Do not use a blind `cp`.

## 2. Start the release backend

```bash
cd /private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-release-55b13cd2f-20261024/backend
set -a; source /Users/rushiparikh/projects/atom/backend/.env; set +a

export DATABASE_URL="sqlite:////Users/rushiparikh/projects/atom/backend/data/atom.db"
export ATOM_DATA_DIR="/Users/rushiparikh/projects/atom/backend/data"
export LANCEDB_URI="/Users/rushiparikh/projects/atom/backend/data/atom_memory"
export LANCEDB_URI_BASE="/Users/rushiparikh/projects/atom/backend/data/atom_memory"
export LANCEDB_PATH="/Users/rushiparikh/projects/atom/backend/data/lancedb"
export BYOK_CONFIG_FILE="/Users/rushiparikh/projects/atom/backend/data/byok_config.json"
export BYOK_KEYS_FILE="/Users/rushiparikh/projects/atom/backend/data/byok_keys.json"
export BYOK_ENC_KEY_FILE="/Users/rushiparikh/projects/atom/backend/data/byok_encryption_key"
export ALLOWED_ORIGINS="http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"
export CORS_ORIGINS="$ALLOWED_ORIGINS"
export PORT=8001 HOST=0.0.0.0

export ATOM_TURN_INTERPRETATION=1
export ATOM_TURN_INTERPRET_PIN="deepseek:deepseek-v4-pro"
export ATOM_TURN_INTERPRET_CAPTURE=1
export ATOM_TURN_DECISION_ROUTING=1
export ATOM_ASYNC_EDIT_PLAN_MODEL="deepseek/deepseek-v4-pro"
export ATOM_LLM_PROVIDER_POLICY='{"mode":"automatic","allowed_providers":[],"preferred":{"provider":"ollama","model":"llama3.1:8b"}}'
export ATOM_PREFERRED_LLM_PROVIDER="ollama"
export ATOM_PREFERRED_LLM_MODEL="llama3.1:8b"
export CHAT_FINALIZATION_M1=1 CHAT_FINALIZATION_M2=1
export ATOM_TASK_LIFECYCLE_ENABLED=1
export ATOM_STREAM_FALLBACK_RESERVE_SECONDS=70

nohup /Users/rushiparikh/projects/atom/backend/venv314/bin/python \
  -m uvicorn main_api_app:app --host 0.0.0.0 --port 8001 \
  > /private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-cutover-55b13cd2f-20261024/candidate_backend.log 2>&1 &
echo $! > /private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-cutover-55b13cd2f-20261024/candidate_backend.pid
```

Do **not** set `TESTING=1`. Do not use `--reload`.

Require:

```bash
curl -fsS http://127.0.0.1:8001/api/health | tee .../candidate_health.json
```

- HTTP 200;
- `identity.revision == 55b13cd2fcab67ba8436618f7032339649cbdffc`;
- `identity.dirty == false`;
- `identity.database == /Users/rushiparikh/projects/atom/backend/data/atom.db`;
- `identity.byok_key_store == .../data/byok_keys.json`;
- no startup traceback or port conflict.

## 3. Start the release frontend

```bash
cd /private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-release-a729df5f5-20261024/frontend-nextjs
NEXT_PUBLIC_API_URL=http://127.0.0.1:8001 \
NEXT_PUBLIC_ALLOW_LOOPBACK=1 \
nohup ./node_modules/.bin/next start -p 3000 \
  > /private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-cutover-55b13cd2f-20261024/candidate_frontend.log 2>&1 &
echo $! > /private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-cutover-55b13cd2f-20261024/candidate_frontend.pid
```

Require `/login` 200 and a real browser sign-in to `/dashboard` with no
page errors. A dashboard screenshot alone is not a smoke pass.

## 4. Post-start smoke (required)

Use the real product API with a token from `POST /api/auth/login` (the
local 0600 password file; never print or persist the password/token).

### 4a. Sourced answer

Upload `release_smoke_record_55b13cd2f.txt` through
`POST /api/documents/upload`:

```
Release smoke record — product 55b13cd2f.
The release smoke code is CEDAR-55.
Approved valid-until date: 2026-12-31.
```

Ask in a new session:

> Search my uploaded documents for the release smoke code in
> release_smoke_record_55b13cd2f.txt and tell me the code. Name the source.

Pass: HTTP 200; answer contains `CEDAR-55`; names the source; no
provider/error text; persisted history; actual provider/model recorded in
the server log; any outbound POST only to the four authorized providers.

### 4b. One edit

Create a canvas (`canvas_type: "document"`) and seed:

```
Quotation Q-2026-114
Payment terms: Net 45
Valid until: 2026-12-31
```

Ask with `context.canvas_id`:

> Please update the payment terms in the draft to Net 30.

Pass: HTTP 200; body contains `Net 30`; other fields unchanged; exactly
one new audit/write; fresh `GET` confirms.

### 4c. Identical re-ask (no-op)

Send the identical edit request. Pass: body byte-identical; zero
additional audit/write rows; response says already satisfied/no change
needed.

### 4d. S7 date-only continuation

With the draft and the approved record available, ask:

> What is the current Valid until date on the draft, and does it still
> match the approved record?

Pass: the answer states the draft date and the approved record date
truthfully; the requirement binds `approved_records_q2026_114.txt`; the
scope is `expiration_date`; no broad field expansion; zero canvas writes;
settlement/response/history agree. A correct sentence without source
binding is not a pass.

### 4e. Reload / restart agreement

Reload history and canvas; restart the backend once with the same
environment. Require the same health identity, persisted answer/source,
canvas `Net 30`, no new write, and `/login` 200.

### 4f. Route and DB evidence

- Extract every outbound `POST http(s)://...` destination from the
  candidate logs into `provider_posts.json`.
- Allowed destinations: `api.deepseek.com`, local Ollama, OpenCode Go,
  OpenRouter. Any other destination is a rollback condition.
- Record actual reply/structured/edit-planning routes; do not present
  intended routes as actual.
- Record `post_smoke_db_fingerprint.json`; user-visible delta must equal
  the smoke fixtures; background rows must be attributable in logs.

## 5. Rollback (mandatory on any failure)

Roll back on health/revision/path failure, frontend/login failure not
fixed in 5 minutes, wrong smoke answer/source, edit write count wrong,
no-op writes, restart disagreement, DB integrity failure, unexplained
user-visible delta, or owner abort.

1. Stop candidate PIDs; confirm `:8001`/`:3000` free.
2. Remove `atom.db-wal`/`atom.db-shm`; restore the prepared fresh backup;
   verify `quick_check` and row counts.
3. Restore the four pre-cutover config/secret files with original modes.
4. Restart the old backend from
   `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-rollback-8c593e/backend`
   on `:8001` and the old frontend from
   `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-release-910bf85a6/frontend-nextjs`
   on `:3000`.
5. Verify `/api/health` reports `8c593e57031e`, clean, and `/login` 200.
6. Keep all candidate logs/evidence. Do not delete or overwrite them.
7. Record `rollback_summary.json`; the attempt is over.

## 6. On success

- Save served identity headers/health.
- Write `deployment_summary.json` with times, backup hashes, identities,
  smoke latencies, actual routes, POST destinations, row deltas, and the
  route acceptance reference.
- Update the support statement to "deployed" with the actual provider
  profile; update `journey_status.json` `RELEASE.pilot` with
  `served_runtime: 55b13cd2f` and the deployment timestamp.
- Keep the fresh backup at least seven days; keep old trees until the
  observation period ends.

## 7. Evidence

`docs/acceptance/release_evidence_20261024/release_55b13cd2f/` contains the
attempt-16 config/summary/result/console, predeclared config, no-pilot
preflight, independent manual L3 answer assessment, redacted config
manifest, backup verification, release config, and checksums. The backup
DB and any secret/config files remain outside the repo at the private
paths above; committed evidence contains only redacted metadata and
references.

**No deployment has been executed. This package is the material for the
approval decision.**
