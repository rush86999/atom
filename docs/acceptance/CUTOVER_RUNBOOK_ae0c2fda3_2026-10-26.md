# Cutover runbook — `ae0c2fda3` over pilot `c912375de`

**Status:** prepared and locally checked; **not executed**.
**Approval token:** `ATOM_DEPLOY_APPROVED=ae0c2fda3`
**Script:** `scripts/deploy_release_candidate_ae0c2fda3.sh`

This runbook replaces the generic `scripts/restart_backend.sh` for this
cutover. The generic script is not used because it stops every matching
Uvicorn process, continues after a snapshot failure, and resolves paths
relative to the script.

One authorization covers the complete reversible attempt:

1. verified backup and scoped cutover to `ae0c2fda3`;
2. immediate live smoke (pre-restart);
3. scoped candidate restart and post-restart agreement smoke;
4. automatic **code** rollback to untouched `c912375de` if any required check
   fails;
5. preservation of the attempt and publication of the final served identity.

The database is **never restored automatically**. It is restored only for
demonstrated corruption, after preserving the post-cutover database.

## Fixed identities

| Item | Value |
|---|---|
| Candidate | `/Users/rushiparikh/projects/atom-releases/ae0c2fda3` |
| Candidate commit | `ae0c2fda340e9a85e840e310d84d4d0da4fedab8` |
| Canonical archive | `evidence/archive/atom-ae0c2fda3-backend.tar` |
| Archive SHA-256 | `33a317c2b981f5947f854056aad8b11ffce4ac8c0a6b908e96f998d5dca4f526` |
| Rollback release | `/Users/rushiparikh/projects/atom-releases/c912375de` |
| Rollback commit | `c912375de81b55465e61fe468bf0bc2b405fd206` |
| Pilot PID / port | `33426` / `8001` |
| Live data | `/Users/rushiparikh/projects/atom/backend/data` |
| Live env | `/Users/rushiparikh/projects/atom/backend/.env` |
| Live venv | `/Users/rushiparikh/projects/atom/backend/venv314` |
| Final identity pointer | `/Users/rushiparikh/projects/atom-releases/SERVED_IDENTITY.json` |

The candidate archive is plain tar. The preserved original gzip and its
different SHA-256 are explained in `evidence/archive/README.md`; they are not
interchangeable strings.

## Read-only preflight

```bash
cd /Users/rushiparikh/projects/atom-saved-lookup-repair
./scripts/deploy_release_candidate_ae0c2fda3.sh --preflight
```

Recorded result on 2026-10-26:

```
==> preflight candidate ae0c2fda340e9a85e840e310d84d4d0da4fedab8
==> candidate state: source-only
==> candidate source matches the canonical archive (0 differences)
==> pilot pid=33426 port=8001
==> live smoke precheck (read-only)
==> live smoke precheck OK
==> preflight OK; no changes made
==> apply: ATOM_DEPLOY_APPROVED=ae0c2fda3 ./scripts/deploy_release_candidate_ae0c2fda3.sh --apply
==> authorization covers cutover, live smoke, scoped restart, and automatic code rollback
```

The preflight runs again inside `--apply`. The approval token is checked before
any snapshot, link, stop, or start.

Preflight fails closed if any of these is false:

- candidate/rollback identity commits and the canonical archive checksum;
- candidate source tree matches the archive (source-only state);
- pilot PID `33426` is alive, owns `--port 8001`, and its cwd is
  `c912375de/backend`;
- `/api/health` reports healthy, PID `33426`, that cwd, and
  `c912375de/backend/data/atom.db`;
- the pilot's `data`, `.env`, and `venv314` links resolve exactly to the live
  data/env/venv paths above, and its DB resolves to the verified live DB;
- live data/env/venv and rollback config exist; live DB `quick_check` is `ok`;
- the backup directory is writable and at least 2 GiB is free;
- the live smoke script, both fixtures, the active admin user, the password
  file, and the required live DB tables are present (`--check-only`).

A wrong token was tested and exits `1` before any change; the pilot remained
PID `33426` healthy and the candidate remained source-only.

## Immediate live smoke

The smoke is `scripts/smoke_release_candidate_ae0c2fda3.py` with fixtures in
`scripts/smoke_inputs/`. It creates a clearly named smoke agent/canvas and
uploads uniquely named copies of the two workbooks, so live dataset entries
cannot collide with earlier runs. Smoke data is deliberately preserved.

Required checks:

- **Sourced answer.** O-1001 review returns a structured `decision=Process`
  with a source file and row reference in `evidence_refs`, not just prose.
- **Spreadsheet total/gap.** PO Register approved rows = CAD **8050.00**
  (3 rows, qty 10), USD **3999.96** (1 row, qty 4). Adjustments approved rows =
  known subtotal **−700.00 CAD**, gap **0055** at **C5**, complete/grand total
  withheld.
- **Taught review.** O-1010 is **Process** before correction and **Escalate**
  after the M. Chen / 2026-10-25 correction, with the correction cited.
- **Identical no-op.** Repeat the exact O-1001 review in the same session.
  Require the same structured decision, evidence, subject and outcome, and no
  new `task_operation_records`, `tasks`, or canvas audit actions.
- **History/outcome agreement.** Every review turn has persisted assistant
  history whose outcome matches the execution's task outcome; the correction
  lesson is stored.
- **No unintended writes.** `task_operation_records` and `tasks` counts do not
  grow; canvas audit actions for the smoke canvas stay within
  `create`/`update`/`agent_attached`/`data_loaded`; workbook hashes are unchanged.

Pre-restart evidence: `attempt-<ts>/smoke/pre.json`.

## Apply sequence

```bash
cd /Users/rushiparikh/projects/atom-saved-lookup-repair
ATOM_DEPLOY_APPROVED=ae0c2fda3 \
  ./scripts/deploy_release_candidate_ae0c2fda3.sh --apply
```

The script performs these steps in order:

1. **Preflight again.** Abort before any change if any identity, health, or
   smoke-precheck item fails.
2. **Snapshot the live DB.** `sqlite3 .backup` to a temporary file, verify
   `PRAGMA quick_check`, gzip it, verify `gzip -t`, and write
   `attempt-<ts>/snapshot.json`. The snapshot lives under
   `backend/data/backups/atom-pre-ae0c2fda3-<timestamp>.db.gz`.
   **Any snapshot failure aborts before the pilot is stopped.**
3. **Prepare the candidate locally, before the stop.**
   - move tracked `backend/data` to `attempt-<ts>/source-backend-data`;
   - link `backend/data` -> live data;
   - link `backend/.env` -> live env;
   - link `backend/venv314` -> live venv;
   - copy the three pilot BYOK config files into the candidate's own
     `config/` directory (`chmod 700` directory, `chmod 600` files), so
     candidate runtime writes cannot mutate the rollback release.
4. **Stop only PID `33426`.** `kill -TERM`, wait up to 30s, verify the port has
   no listener. No `pkill`, no pattern matching, no second instance.
5. **Start the candidate release.** cwd is
   `/Users/rushiparikh/projects/atom-releases/ae0c2fda3/backend`, using the
   live venv and the pilot's provider/model/BYOK environment.
6. **Require candidate health.** `/api/health` must be healthy with the new
   PID, cwd `ae0c2fda3/backend`, and
   `identity.database = ae0c2fda3/backend/data/atom.db`.
7. **Run pre-restart live smoke.** Any failure triggers automatic code
   rollback.
8. **Scoped candidate restart.** Stop only the candidate PID, start the
   candidate again, require matching health. Any failure triggers automatic
   code rollback.
9. **Run post-restart smoke.** Repeat O-1010 in the same session; require
   **Escalate**, persisted pre-restart history/outcomes, the correction lesson,
   and zero new task operations/tasks/canvas writes.
10. **Recheck live DB `quick_check`.** A failure triggers automatic code
    rollback; the DB is not restored.
11. **Publish final served identity.** Success writes
    `attempt-<ts>/deployed.json`, `attempt-<ts>/served-identity.json`, and
    `/Users/rushiparikh/projects/atom-releases/SERVED_IDENTITY.json` with the
    served release, commit, PID, health, smoke evidence, and
    `database_restored=false`.

Post-restart evidence: `attempt-<ts>/smoke/post.json`.

## Automatic code rollback

If preflight, snapshot, candidate start/health, pre-smoke, restart, post-smoke,
or the post-smoke DB check fails:

- kill only the failed candidate PID and verify port `8001` is free;
- start `c912375de` from its untouched directory with its own config;
- require rollback health identity;
- write `attempt-<ts>/failed.json` and
  `attempt-<ts>/served-identity.json`;
- publish `SERVED_IDENTITY.json` with `served_release=atom-c912375de`,
  `status=rolled_back`, the failure reason, smoke evidence, and
  `database_restored=false`;
- exit nonzero.

If rollback itself fails, publish `status=rollback_failed` and require manual
recovery. The candidate and rollback releases remain separate; `c912375de` is
never overwritten.

## Database restore rule

The snapshot is for disaster recovery, not normal rollback. The script never
restores the database. Restore only after demonstrated corruption, and only
after copying the post-cutover DB (including WAL/SHM if present) to a preserved
evidence path. Normal code rollback keeps the post-cutover data.

## Local checks performed (no deployment)

- `bash -n`: pass.
- `--preflight`: pass with zero archive/source differences and live smoke
  precheck OK.
- wrong approval token: exit `1`, no snapshot/link/stop/start.
- `smoke...py --check-only`: pass against the live DB (admin user, required
  tables, password file, fixture hashes); no network and no writes.
- isolated self-test of preparation, config copy, snapshot gzip/quick_check,
  health identity parsing, scoped PID/port stop, and served-identity
  publication: pass.
- Pilot remains PID `33426` healthy on `:8001`; candidate remains source-only.
