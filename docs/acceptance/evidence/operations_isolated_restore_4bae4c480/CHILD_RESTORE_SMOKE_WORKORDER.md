# Child full-app restore smoke workorder (frozen, NOT EXECUTED)

Status at `4bae4c480`: **not run**. The measured free space was
`4,413,313,024` bytes, only `118,345,728` bytes above the literal 4 GiB floor.
The preceding 80-test bounded gate consumed more than 700 MB of scratch space;
a full-app child needs a scratch source world, a restore target, DB/LanceDB
files and logs. Launching it would not maintain the required >=4 GiB working
margin. No child process or world was launched, and no HTTP acceptance is
claimed. This workorder is exact so root can run it after cleanup.

## Preconditions

- `python3 -c "import shutil; assert shutil.disk_usage('/private/tmp').free >= 4*1024**3"`
- A clean scratch root outside any live data/world, e.g.
  `SCRATCH=/private/tmp/ops-child-restore-$(date +%Y%m%dT%H%M%SZ)`.
- `TESTING=0` for the child, but every path below points at `$SCRATCH`.
- No provider keys, accounts, live DB, live world, real credentials, sends,
  spends, installs, deployments or acceptance-world relocation.
- The read-only endpoints used below do not dispatch a model. Do not call a
  chat/generation endpoint.

## Variables

```bash
SCRATCH=/private/tmp/ops-child-restore-$(date +%Y%m%dT%H%M%SZ)
VENV=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
KIT=${ATOM_WORKTREE:-/private/tmp/atom-oracle-refresh-20261107}/scripts/deployment/assignment_successor_2026-10-30_fda4f2dc9
PACKET=${ATOM_WORKTREE:-/private/tmp/atom-oracle-refresh-20261107}/docs/acceptance/evidence/operations_isolated_restore_4bae4c480
PORT=18771
mkdir -p "$SCRATCH"
```

## 1. Seed an ordinary scratch source world

The seed script uses product models and ordinary files only. Its goal/assignment
rows are labeled readback fixtures; they are not a provider or business
completion claim.

```bash
printf '%s' 'Child-Restore-Smoke-Password-1' > "$SCRATCH/password"
chmod 600 "$SCRATCH/password"
"$VENV" "$PACKET/child_restore_seed.py" \
  --source-root "$SCRATCH/source" \
  --password-file "$SCRATCH/password" \
  --ids-out "$SCRATCH/ids.json"
```

## 2. Back up the source with the existing release kit

```bash
set -a
ATOM_DATA_DIR="$SCRATCH/source"
DATABASE_URL="sqlite:///$SCRATCH/source/atom.db"
ATOM_OFFICE_DIR="$SCRATCH/source/office"
ATOM_EMAIL_ATTACHMENT_DIR="$SCRATCH/source/email_attachments"
LANCEDB_URI="$SCRATCH/source/atom_memory"
SECRET_KEY="synthetic-child-restore-smoke"
set +a

"$VENV" "$KIT/release_tool.py" --root "$SCRATCH/release" \
  backup --label child
```

`memory_included` is false in this workorder. Do not claim search/recall or the
LanceDB-backed document API. The document evidence below is the SQL
`ingested_documents` row plus its managed file, read after source absence.

## 3. Restore into a fresh explicit target

```bash
BACKUP=$(ls -d "$SCRATCH"/release/backups/child-* | tail -1)
"$VENV" "$KIT/release_tool.py" --root "$SCRATCH/release" \
  restore --backup "$BACKUP" --target-data-dir "$SCRATCH/target"
```

Require `status == "verified"` and `exit_code == 0`. A `refused` result means no
target; `committed_unverified` means do not blindly repeat.

## 4. Make the original source unavailable

```bash
mv "$SCRATCH/source" "$SCRATCH/source-unavailable"
```

Do not restore or copy anything from `source-unavailable`. The readback harness
refuses if the source root still exists.

## 5. Start the isolated child backend

```bash
env -i \
  PATH="$PATH" HOME="$HOME" \
  TESTING=0 ENVIRONMENT=test \
  SECRET_KEY="synthetic-child-restore-smoke" \
  DATABASE_URL="sqlite:///$SCRATCH/target/atom.db" \
  ATOM_DATA_DIR="$SCRATCH/target" \
  ATOM_OFFICE_DIR="$SCRATCH/target/office" \
  ATOM_EMAIL_ATTACHMENT_DIR="$SCRATCH/target/email_attachments" \
  LANCEDB_URI="$SCRATCH/target/atom_memory" \
  LANCEDB_URI_BASE="$SCRATCH/target/atom_memory" \
  ATOM_OUTPUT_DIR="$SCRATCH/target/output" \
  PYTHONDONTWRITEBYTECODE=1 \
  "$VENV" -m uvicorn main_api_app:app \
    --host 127.0.0.1 --port "$PORT" \
  > "$SCRATCH/backend-1.log" 2>&1 &
echo $! > "$SCRATCH/backend-1.pid"
```

Wait for `GET http://127.0.0.1:$PORT/api/health` to return 200.

## 6. First readback

Read the ids from `ids.json` and run:

```bash
IDS="$SCRATCH/ids.json"
"$VENV" "$PACKET/child_restore_readback.py" \
  --api-base "http://127.0.0.1:$PORT" \
  --email "$(python3 -c "import json;print(json.load(open('$IDS'))['email'])")" \
  --password-file "$SCRATCH/password" \
  --canvas-id "$(python3 -c "import json;print(json.load(open('$IDS'))['canvas_id'])")" \
  --goal-id "$(python3 -c "import json;print(json.load(open('$IDS'))['goal_id'])")" \
  --document-id "$(python3 -c "import json;print(json.load(open('$IDS'))['document_id'])")" \
  --db-path "$SCRATCH/target/atom.db" \
  --artifact-path "$SCRATCH/target/office/restored-office.docx" \
  --artifact-sha256 "$(python3 -c "import json;print(json.load(open('$IDS'))['office_artifact_sha256'])")" \
  --source-root "$SCRATCH/source-unavailable" \
  --out "$SCRATCH/before-restart.json"
```

## 7. Stop and restart the same child

```bash
kill "$(cat "$SCRATCH/backend-1.pid")"
wait "$(cat "$SCRATCH/backend-1.pid")" 2>/dev/null || true
# Identical environment as step 5, separate log/pid.
env -i \
  PATH="$PATH" HOME="$HOME" TESTING=0 ENVIRONMENT=test \
  SECRET_KEY="synthetic-child-restore-smoke" \
  DATABASE_URL="sqlite:///$SCRATCH/target/atom.db" \
  ATOM_DATA_DIR="$SCRATCH/target" \
  ATOM_OFFICE_DIR="$SCRATCH/target/office" \
  ATOM_EMAIL_ATTACHMENT_DIR="$SCRATCH/target/email_attachments" \
  LANCEDB_URI="$SCRATCH/target/atom_memory" \
  LANCEDB_URI_BASE="$SCRATCH/target/atom_memory" \
  ATOM_OUTPUT_DIR="$SCRATCH/target/output" \
  PYTHONDONTWRITEBYTECODE=1 \
  "$VENV" -m uvicorn main_api_app:app --host 127.0.0.1 --port "$PORT" \
  > "$SCRATCH/backend-2.log" 2>&1 &
echo $! > "$SCRATCH/backend-2.pid"
```

Wait for `/api/health` again, then repeat the readback with
`--compare-to "$SCRATCH/before-restart.json" --out "$SCRATCH/after-restart.json"`.

## 8. Acceptance conditions for this smoke

Only if all of the following are true may the child service-level evidence be
called passed:

- login uses the normal `/api/auth/login` boundary and returns a token;
- `/api/auth/me` returns the same user/tenant/workspace before and after restart;
- `/api/canvas/{id}` returns content whose `office_file` is under the target and
  is a real file; the original source root is unavailable;
- `/api/goals/{id}` returns the same goal before and after restart;
- the `ingested_documents` row and managed file are readable and under the target;
- the expected office artifact hash matches;
- `restart_agreement.ok` is true with no mismatches;
- no model/provider/account/send/spend/deploy was used.

## 9. Cleanup

Kill the child; remove only `$SCRATCH` (the workorder's own scratch), never a
live world or another owner's directory.
