# Ops: manifest-verified isolated restore in the existing release kit

NEXT-02 requires usable local backup/isolated restore/rollback. The release kit
already wrote a verified `BACKUP_MANIFEST.json` but had no consumer; rollback is
explicitly code-only.

## Change

- Resolve backup sources from `DATABASE_URL`/`ATOM_DATA_DIR`/`ATOM_OFFICE_DIR`/
  `ATOM_EMAIL_ATTACHMENT_DIR`/`LANCEDB_URI`; refuse ambiguous DB roots or
  missing explicit stores; record `store_roots` and copy external configured
  stores into canonical backup paths.
- Add `restore --backup ... --target-data-dir ...` to the same kit.
- Verify schema, every file byte/SHA-256, DB integrity/row counts; refuse path
  escapes, duplicate/colliding/symlink/hardlink entries, non-empty/live targets,
  target symlinks, corrupt DB, and changed-source copies.
- Restore DB via the SQLite backup API into an owned staging dir; verify copies,
  rebase only known current managed path bindings, refuse unresolved managed
  references, then atomic-publish with a concurrent claim.
- `memory_included=false` is reported truthfully; included memory is copied and
  read back in the test. Credential/config modes are 0600; no secret contents
  are logged.
- Code rollback stays `database_restored:false`; no new store/engine/API/UI.

## Verification

At `d4b313992`: shared bounded gate **62 passed** (19 restore + 43 existing
db_safety/kit contract), exit 0. Pre-implementation failure-first argparse
`restore` invalid choice, exit 2, no target effect.

Child HTTP backend/login/restart proof was not launched because free space was
4,158,459,904 bytes, below the required 4 GiB floor. No new process/world was
started; this is explicitly not claimed as HTTP acceptance. Service-level reads
after source rename/unavailability are covered.

## Boundaries

Local SQLite only; no PostgreSQL/KVM/multiworker/soak/live-provider/account/
send/spend/deploy. No live DB. Root owns review, normal CI and merge.
