# Local backup / isolated restore — release-kit implementation

Executed source: `d4b313992` (branch
`codex/operations-isolated-restore-20261107`, parent current main `8ded00232`).

This is a bounded NEXT-02 implementation in the **existing release kit**. It
does not add a second backup store, engine, API, UI, permission gate, or schema
migration. It does not change the radio branch/evidence/config or any
Goal/source/CI worker tree.

## What was added

- `scripts/deployment/assignment_successor_2026-10-30_fda4f2dc9/restore_support.py`
- `scripts/deployment/assignment_successor_2026-10-30_fda4f2dc9/release_tool.py`
  (`restore` subcommand; backup store-root resolution)
- `.../tests/test_release_restore.py`
- `DEPLOYMENT_RUNBOOK.md` section and a normal CI step.

### Backup source resolution

`backup` now resolves the configured DB and managed stores before copying:

- `DATABASE_URL` absolute SQLite path must agree with
  `ATOM_DATA_DIR/atom.db`; disagreement refuses before effect.
- `ATOM_OFFICE_DIR`, `ATOM_EMAIL_ATTACHMENT_DIR` and `LANCEDB_URI` are honored.
  Explicitly configured missing stores refuse; non-local memory with
  `--include-memory` refuses.
- Outside-data roots are copied into canonical backup paths, and
  `store_roots` records the actual source provenance. A declared managed store
  is therefore not silently omitted.

SQLite is copied with the SQLite backup API (consistent snapshot including
committed WAL; destination is a separate connection), never a byte copy of a
live DB or its WAL/SHM. Integrity and row counts are verified.

### Restore contract

`restore` requires an explicit backup directory/manifest and an explicit
target. It refuses live/overlapping roots, source==target, existing/non-empty
targets, existing target `atom.db`, target symlinks, unknown schema,
duplicate/colliding/absolute/`..`/symlink/hardlink manifest entries, missing
files, byte/SHA-256 mismatch, corrupt/truncated DB, and changed source files.
It verifies every manifest entry before copying, restores the DB through the
SQLite backup API into an owned staging directory, re-verifies copied bytes and
DB integrity/row counts, then publishes atomically. A concurrent target claim
and a final target check prevent overwrite/races. Failure before publish leaves
no target; post-publish uncertainty returns `committed_unverified` and is never
blindly repeated.

Only known current managed path bindings are rebased from manifest source
provenance to the target:

- `dataset_entries.parquet_path`
- optional `ingested_documents.file_path` / `accounting_documents.file_path`
- assignment operational paths in `goal_runs.parameters`
- current `Canvas.content` office binding and the latest content-bearing
  `CanvasAudit` office binding (the row `read_canvas` treats as current state)

Historical audit rows, receipts, provenance and operation bindings are not
rewritten. If any managed reference remains unresolved, restore refuses before
publish rather than claiming a half-restored world. This is the explicit
portability gate; the positive test renames the original source **and** the
external office root before calling the real `read_canvas` and reading the
target document/dataset/goal rows.

`memory_included: false` reports `memory_restored: false` and makes no
search/recall claim. When memory is included, the test opens the restored
LanceDB table and reads its content after the source is unavailable. Credential
and config files are published mode 0600; results/logs contain no secret values
or DB contents.

Code rollback remains code-only: `database_restored: false`,
`user_data_preserved: true`. It was not run and is not presented as data
restore.

## Verification at `d4b313992`

Shared bounded gate, `TESTING=1`, unique scratch DB/data/Lance/output/basetemp,
synthetic `SECRET_KEY`:

- `final-gate.log`: **62 passed**, exit 0
  - 19 restore cases (WAL committed row, external office store, memory
    included content readback, missing/corrupt/hash/path/symlink/hardlink/
    concurrent/source-change/postpublish, source-absent portability and
    read_canvas/document/dataset/goal readback)
  - 43 existing db_safety/atomicity/snapshot-protection and release-kit
    deployment contract cases.
- `failure-first-restore.log`: pre-implementation argparse
  `invalid choice: 'restore'`, exit 2, no target effect.

The child HTTP backend/login/public-read/restart proof was **not run**: free
space was below the required 4 GiB floor (4,158,459,904 bytes <
4,294,967,296). No new process/world was launched. `child-backend-not-run.json`
records the exact blocker and required conditions; service-level target reads
after source absence are proven above. This is an explicit root-run boundary,
not a claimed HTTP acceptance.

## Boundaries

Local SQLite personal-edition recoverability only. PostgreSQL, KVM, multi-worker/
soak, live provider/account/send/spend/deploy, external-drive relocation and
acceptance-world relocation remain separate and unclaimed. No live DB was
connected; no real backup/restore/maintenance/restart/lock was run outside the
scratch tests. Full-app ORACLE and claim scores remain open/unchanged. Root owns
independent review, normal PR/CI acceptance and merge.
