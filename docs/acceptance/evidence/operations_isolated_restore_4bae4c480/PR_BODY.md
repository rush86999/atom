# Ops: correct audit-history preservation and manifest-byte binding in isolated restore

NEXT-02 requires usable local backup/isolated restore/rollback. Root withheld
the predecessor candidate `a4b56af59` after an independent probe found two
field-class integrity failures. This PR is the corrected candidate at
`4bae4c480`, still inside the existing release kit.

## What changed

### A. Audit history is append-only
- No `canvas_audit` row is updated. Every original audit/receipt/operation row
  remains byte-for-byte identical (id, tenant, action, actor, timestamp,
  material).
- Only current writable projections are rebased.
- When a current content-bearing audit row must change, restore appends a new
  restore-owned event with its own id, exact canvas/tenant scope, original
  audit id/material hash + manifest SHA-256 provenance, and target binding.
  Old `operation_id`/evidence/postconditions/review status are not reused;
  actor fields stay NULL.
- Strict recency uses the latest audit row so `read_canvas` serves the event.

### B. Copy is bound to validated manifest bytes
- The already-checkpointed backup DB is frozen through a nofollow
  directory-descriptor walk into private staging, re-verified for
  size/SHA-256/device/inode/stat identity, and only then copied through the
  SQLite backup API.
- Rejects in-place updates, inode/path swaps (even identical bytes), symlink
  swaps, added/changed WAL/SHM/journal sidecars, and changes during read.
- Backup producer leaves a self-contained sidecar-free DB and rejects
  symlinks/hardlinks in managed stores.

### Hardening
- `row_counts` keys are validated SQL identifiers; values are non-negative
  ints or None; missing tables are never zero; 0 is exact; None requires
  absence.
- Target must not exist; target/ancestor symlinks refused; claim token+inode
  ownership checked before cleanup; no-replace publication prevents peer
  target/symlink overwrite.
- Runbook correction records the predecessor's wrong claim; predecessor
  evidence is preserved unmodified.

## Verification

Executed source `4bae4c480`, shared bounded gate, fresh `TESTING=1` scratch:
**80 passed** (root permanent 3 + native restore 34 + existing db-safety/kit
43), exit 0. Safe synthetic-root failure-first: exit 2, no target effect.
Root's raw predecessor negative probe is retained: 2 failed, 1 passed at `a4b`.

Child HTTP backend/login/public-read/restart proof remains **OPEN**. It was not
launched because free space was `4,413,313,024` bytes, only `118,345,728` above
the 4 GiB floor, and a full-app child would not maintain the required working
margin. The exact harness/workorder is frozen in the evidence packet for root
to run after cleanup; no HTTP acceptance is claimed.

## Boundaries

Local SQLite only. No live DB/world/provider/account/credential/send/spend/
install/deploy, no acceptance-world relocation, no new backup engine/store/
router/authority lifecycle. Code rollback remains code-only. Full-app
ORACLE/claim scores remain OPEN. Root owns independent review, normal CI and
merge.
