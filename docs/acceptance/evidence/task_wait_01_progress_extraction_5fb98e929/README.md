# TASK-WAIT-01 — applied-source progress and revision namespaces

**Focused executed source:** `5fb98e929a5d81c819c25ecaac4643bb2e2b81d9`
(clean; `dirty=False`). **CI-only successor:** `e20219b36` registers the
permanent probe; runtime bytes are unchanged.
**Base:** root permanent probe `75a7cfc71`; earlier source-authority packet
`c218b070a`; main `36fa4ce39` merged.

## Root-withheld negatives

`/private/tmp/root-wait-progress-extraction-final-negative.log` was preserved
unchanged: **3 failed**, actual exit 1, at clean `75a7cfc71`.

1. `test_source_gap_returns_instead_of_syncing_applied_receipt_forever`
   observed the identical source gap **twice**. `_sync_assignment` restored
   the old applied operation over the waiting source step after
   `_record_applied_source_gap`, so the loop re-recorded the gap.
2. `test_valid_indexed_source_version_is_not_a_binary_file_digest[ev4]`
   falsely refused a valid `ev4:` revision because it was compared with raw
   binary file bytes.
3. `[manual_opaque]` made the same false comparison with `manual-revision-17`.

The earlier missing/unreadable/deleted-authority negatives in
`test_lead_wait_source_disappears.py` are preserved unchanged:
`root-source-unavailable-negative.log` (**2 failed**) and
`root-upload-removed-negative.log` (**1 failed**).

The earlier unbounded diagnostic ended at exit 247 / child signal 9 after being
manually stopped; it is not a normal pass/fail and is not used as evidence.

## Repair

- `_sync_assignment` now preserves a waiting source step with open `gap_ids`
  when the immutable applied operation is re-synced. The operation receipt
  stays audited, but current freshness wins and repeated advances yield.
- Revision namespaces are separated:
  - binary file bytes are compared only with a binary SHA-256 pin;
  - `ev4:` extractor revisions and manual opaque revisions are validated
    against the authoritative `IngestedDocument.source_content_hash`, never
    hashed as bytes;
  - extracted-text hashes retain their existing `extraction.text_sha256`
    namespace.
- A waiting source gap is revalidated once per external advance, not inside
  the execution loop. When the same accepted version is valid again, applied
  status is restored, only that source's gap questions are resolved, and
  dependent work resumes.
- Re-posting the same authorized source path with a newer version uses the
  existing invalidation/CAS path; the prior result is retained for audit and
  the current value is recomputed.
- `assignment_routes` fallback `raw_step` construction was moved outside the
  source-index loop, correcting the indentation/reuse bug.

No new store/router/engine/budget, no schema/extraction/authority weakening,
no G3 UI/source-answer feature, no live provider/model action.

## Focused actual results (bounded profile)

All runs used the executable wrapper, `--profile bounded`, global lock,
scratch DB/data/Lance/output, and `TESTING=1`.

| Log | Selection | Actual result |
|---|---|---|
| `focused-root-and-recovery-11.log` | root progress/extraction probe; three disappearance negatives; G2 refusal; explicitly authorized newer version; same-version restoration; valid unchanged two-fact | **11 passed**, exit 0 |
| `focused-neighborhood-25.log` | revocation, independent ready work, artifact blocking, two-job isolation, full continuation/repair/pin/concurrency, real-OS-process restart | **25 passed**, exit 0 |
| `focused-resource-authority-34.log` | resource boundary: forged/wrong-workspace/revoked/stale/expired authority, resumed reads, scope and deliverable gates | **34 passed**, exit 0 |

**Total: 70 focused controls passed, actual exit 0**, at clean
`5fb98e929a5d` (`dirty=False`). No broad test or browser/model run was
dispatched.

Focused command shape:

```bash
TESTING=1 DATABASE_URL=sqlite:///<scratch>/atom.db \
ATOM_DATA_DIR=<scratch>/data ATOM_OFFICE_DIR=<scratch>/office \
LANCEDB_URI=<scratch>/lancedb \
ATOM_TEST_PYTHON=/Users/rushiparikh/projects/atom/backend/venv314/bin/python \
/private/tmp/atom-agent-cli/run_bounded_test_gate.py \
  --cwd /private/tmp/atom-task-wait-01-reconciliation-20261107/backend \
  --profile bounded -- \
  /Users/rushiparikh/projects/atom/backend/venv314/bin/python -m pytest \
  <focused files> -q --tb=short
```

## Preserved behavior

- Missing/unreadable/deleted authority blocks only dependent work and the
  final artifact; immutable operation receipts remain.
- Revoked/foreign/stale authority refuses safely (34 controls).
- Valid unchanged source completes; same-version restoration and explicitly
  authorized newer version complete through normal source routes on the same
  job.
- Independent ready branches and prior receipts survive; repeated advances
  yield without a CPU loop.
- G1/G4 tests and the G3 proposal remain in the tree; G5/G6 remain accepted
  limitations.

TASK-WAIT-01 remains OPEN at whole-app scope; 143 claims and historical scores
unchanged. Root independently verifies and owns PR/merge.
