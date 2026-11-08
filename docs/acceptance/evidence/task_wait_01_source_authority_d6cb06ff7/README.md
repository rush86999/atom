# TASK-WAIT-01 — source authority before cached consumption

**Executed/committed source:** `d6cb06ff71f3ead5baa996d9b6a183871ba4a134`
(clean; parent `6e776dff0`, root permanent test `b8c7d995a`).
**Base:** main `36fa4ce39` merged earlier as `552aa1378`.
**Status:** G2 repair reworked; root acceptance still required. No post-fix
pytest exit is claimed here because the bounded heavy gate was permission-
denied before dispatch.

## Root-withheld failures preserved

The prior G2 repair `3ebee2da5` was withheld for three actual false completions
after an accepted invoice became unavailable:

- `root-source-unavailable-negative.log`: **2 failed** (removed and unreadable
  invoice), actual exit 1; task reached receiving-only wait and completed with
  cached `130.00`.
- `root-upload-removed-negative.log`: **1 failed**, actual exit 1; deleting
  the authoritative `IngestedDocument` row still completed from cached
  `130.00`.

Both root logs are copied unchanged. They remain the failure-first negatives
for this repair.

## General consumption boundary

`backend/core/assignment_executor.py` now rechecks every applied source before
dependent work or a final artifact:

1. **Authority before bytes:** the current reader/workspace/tenant and the
   connected grant are rechecked through the existing
   `_recheck_binding`/`recheck_resource_access` path. Uploads require the
   workspace-scoped `IngestedDocument` row and an active reader before any file
   is opened.
2. **Existence/readability:** missing files, unreadable files and deleted
   authoritative upload rows produce a typed `source_unavailable` /
   `source_access` gap. They do not silently continue.
3. **Accepted version pin:** the current version/hash is compared with the
   explicit accepted pin (including non-hash pins). A mismatch produces a
   typed `source_version_changed` gap; a replacement is never silently
   authorized.
4. **Gap scope:** the applied source operation remains for audit; the source
   step is marked waiting with one actionable question. Only dependents and
   the final artifact are blocked; unrelated ready branches and receipts stay
   runnable. No 500, infinite invalidation, retry loop or revoked read.
5. **Explicit newer version:** re-posting the same authorized source path with
   changed bytes reuses/invalidate the prior source step through the existing
   CAS path, so an explicitly authorized newer version can be consumed while
   the old value is not kept.

No new store, router, engine, table or budget API was added.

## Tests / gate status

The heavy gate is required for pytest. The exact command was attempted and
returned **exit 126 `permission denied`** before dispatch; see
`gate-permission-denied.log`. Per instruction, this was not bypassed.

Root command (run after granting execute permission or through the gate
owner):

```bash
TESTING=1 DATABASE_URL="sqlite:////private/tmp/atom-gate-neg/atom.db" \
ATOM_DATA_DIR=/private/tmp/atom-gate-neg/data \
ATOM_OFFICE_DIR=/private/tmp/atom-gate-neg/office \
LANCEDB_URI=/private/tmp/atom-gate-neg/lancedb \
ATOM_TEST_PYTHON=/Users/rushiparikh/projects/atom/backend/venv314/bin/python \
/private/tmp/atom-agent-cli/run_bounded_test_gate.py \
  --cwd /private/tmp/atom-task-wait-01-reconciliation-20261107/backend \
  -- /Users/rushiparikh/projects/atom/backend/venv314/bin/python \
  -m pytest tests/test_lead_wait_source_disappears.py \
             tests/test_task_wait_source_version_after_acceptance.py \
             tests/test_task_wait_two_fact_events.py \
  -q --tb=short
```

The G2 file now includes the failure-first changed-source refusal and an
explicitly authorized newer-version twin. A valid unchanged source is covered
by `test_task_wait_two_fact_events.py`. The root permanent negatives include
removed/unreadable fixture and deleted authoritative upload.

Clean static compile at `d6cb06ff7` succeeded (`compile.log`, exit 0). This is
not a pytest pass and is not labelled as one.

## Preserved scope

G1/G4 tests and the G3 source-answer trace remain in the tree. TASK-WAIT-01 is
still OPEN at framework/whole-app scope; 143 claims and historical scores are
unchanged. No live model/provider/browser/account/credential/send/spend/install
or deployment action occurred.
