# Cutover runbook — `ae0c2fda3` over pilot `c912375de`

**Status:** prepared and locally checked; **not executed**.
**Approval token:** `ATOM_DEPLOY_APPROVED=ae0c2fda3`
**Script:** `scripts/deploy_release_candidate_ae0c2fda3.sh`

This runbook replaces the generic `scripts/restart_backend.sh` for this
cutover. The generic script is not used because it stops every matching
Uvicorn process, continues after a snapshot failure, and resolves paths
relative to the script.

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
==> preflight OK; no changes made
==> apply: ATOM_DEPLOY_APPROVED=ae0c2fda3 ./scripts/deploy_release_candidate_ae0c2fda3.sh --apply
```

The script runs this preflight again inside `--apply`. The approval token is
checked before any snapshot, link, stop, or start.

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
- the backup directory is writable and at least 2 GiB is free.

A wrong token was tested and exits `1` before any change; the pilot remained
PID `33426` healthy and the candidate remained source-only.

## Apply sequence

```bash
cd /Users/rushiparikh/projects/atom-saved-lookup-repair
ATOM_DEPLOY_APPROVED=ae0c2fda3 \
  ./scripts/deploy_release_candidate_ae0c2fda3.sh --apply
```

The script performs these steps in order:

1. **Preflight again.** Abort before any change if any identity or health check
   fails.
2. **Snapshot the live DB.** `sqlite3 .backup` to a temporary file, verify
   `PRAGMA quick_check`, gzip it, verify `gzip -t`, and write
   `evidence/cutover/snapshot-<timestamp>.json`. The snapshot lives under
   `backend/data/backups/atom-pre-ae0c2fda3-<timestamp>.db.gz`.
   **Any snapshot failure aborts before the pilot is stopped.**
3. **Prepare the candidate locally, before the stop.**
   - move tracked `backend/data` to
     `evidence/cutover/source-backend-data-<timestamp>`;
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
7. **Roll back on candidate start/health failure.** Kill only the failed
   candidate PID, start `c912375de` from its untouched directory, and require
   its health identity. The script exits nonzero either way; a successful
   rollback is recorded in `evidence/cutover/failed-<timestamp>.json`.

On success the script writes `evidence/cutover/deployed-<timestamp>.json`.
It does **not** run the product smoke; that is a separate approved step.

## Rollback boundary

- `c912375de` is never the candidate source and is never overwritten.
- The candidate gets its own source directory, data/env/venv links, and config
  copy.
- The only shared writable surface is the live data directory (the live DB and
  its backups). That is intentional: rollback must see the same data.
- If the candidate fails during cutover, the script automatically restores the
  `c912375de` process from its untouched directory and verifies health.
- A post-deploy product-smoke failure is a separate rollback decision. Stop
  only the candidate PID discovered on port `8001`, snapshot the live DB
  again, and start `c912375de` from its untouched directory; do not use the
  generic restart script or a broad process match.

## Local checks performed (no deployment)

- `bash -n`: pass.
- `--preflight`: pass with zero archive/source differences.
- wrong approval token: exit `1`, no snapshot/link/stop/start.
- isolated self-test of preparation, config copy, snapshot gzip/quick_check,
  and health identity parsing (including wrong-database rejection): pass.
- Pilot remains PID `33426` healthy on `:8001`; candidate remains source-only.
