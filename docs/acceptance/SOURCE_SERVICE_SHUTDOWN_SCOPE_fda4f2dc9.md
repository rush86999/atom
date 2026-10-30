# Source service shutdown scope — successor fda4f2dc9

Status: **verified read-only; not stopped.** This scope is the only process
authorized to be stopped for the quiescence window. It is bound into
`config/source_shutdown_scope.json` and must appear verbatim in the production
approval record.

## Verified process

| Field | Value |
|---|---|
| PID | `19046` |
| Parent PID | `1` (orphaned; no launchd/supervisor job found) |
| Process group | `17573` |
| User | `rushiparikh` |
| Started | `Mon Oct 26 20:00:05 2026` |
| Command | `/Users/rushiparikh/projects/atom/backend/venv314/bin/python -m uvicorn main_api_app:app --host 0.0.0.0 --port 8001 --timeout-keep-alive 75` |
| CWD | `/Users/rushiparikh/projects/atom-releases/c912375de/backend` |
| Service identity | `atom-c912375de` / `c912375de81b55465e61fe468bf0bc2b405fd206` |
| Source DB handles | `/Users/rushiparikh/projects/atom/backend/data/atom.db`, `-wal`, `-shm` |
| Source memory handles | `/Users/rushiparikh/projects/atom/backend/data/atom_memory/default/...` |
| Listener | `0.0.0.0:8001` |
| Restore env source | `/Users/rushiparikh/projects/atom/backend/.env` |
| Restore venv | `/Users/rushiparikh/projects/atom/backend/venv314` |

No other process holds the source `atom.db`. The other uvicorn processes use
different release/rehearsal databases and are outside this scope. No launchd
job or supervisor was found for `19046`; it is an orphaned manually started
service.

## Re-verify immediately before stopping

Use the packaged verifier, which checks PID, command, CWD, listener, source DB
handles and other DB holders, then writes `run/source_verification.json`:

```bash
ROOT=/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-30-fda4f2dc9
python "$ROOT/current/scripts/source_service_control.py" --root "$ROOT" verify
```

The same facts can be inspected manually:

```bash
ps -p 19046 -o pid=,ppid=,lstart=,command=
lsof -a -p 19046 -d cwd -Fn
lsof -p 19046 | grep '/Users/rushiparikh/projects/atom/backend/data/atom.db'
lsof -nP -iTCP:8001 -sTCP:LISTEN
```

All of the following must match before any stop:

- command, CWD, service commit and source DB path above;
- PID owns the `8001` listener;
- no second process holds the source DB;
- no supervisor/launchd job that would immediately reopen it.

If any field differs, stop and re-scope; do not kill by PID alone.

## Authorized stop (only after approval)

```bash
ROOT=/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-30-fda4f2dc9
python "$ROOT/current/scripts/source_service_control.py" --root "$ROOT" stop
# prove quiescence (the stop command writes run/source_stop.json):
python "$ROOT/current/scripts/source_service_control.py" --root "$ROOT" check-stopped
```

If the process does not exit, do not use `kill -9` without a new owner
decision; report the blocker.

## Refresh and deploy while quiescent

1. `prepare_production_data.py` from the live source to the successor root.
2. `prepare_memory_handoff.py` from the live source memory.
3. `verify_production_handoff.py`.
4. `check_freshness.py --phase preflight --require-quiescent-source`.
5. Run the authorized `deploy_release.sh` transaction.

## Failure recovery

The deployment transaction's code rollback to `901e5d773` is **not** the
complete recovery. The intended source service must be restored as well:

```bash
ROOT=/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-30-fda4f2dc9
python "$ROOT/current/scripts/source_service_control.py" --root "$ROOT" restore
```

The packaged `deploy_release.sh` also calls `restore` on failure when
`run/source_stop.json` exists. It never starts a duplicate if the source
service is already listening.

Restore the same environment source (`/Users/rushiparikh/projects/atom/backend/.env`)
and verify `8001` health, source DB handles and the service identity. Do not
leave the original service unavailable merely because rollback code started.

## Explicit non-actions

- No stop, signal or supervisor change has been performed.
- No credential or source file was read or written.
- No secret value is stored in the scope file.
