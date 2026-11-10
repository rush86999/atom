# Goal3 durable document deletion — test results

Source code: `db6e4a2fc0792dcb8c204a4bd1ddfc691da54935`  
Current-main merge: `9496da733`  
Final test/evidence head: `c90693c4233bb3c191b89d11567ae0131e72cfa9`  
Current main after reconcile: `be8bb29f07b33077a49995816e8952721d3a6fd9`

Scratch SQLite + scratch LanceDB + deterministic embeddings. No live DB,
model/provider, credential, send or spend. Existing dependencies only.

## Failure-first

Joined lifecycle (`failure-first-joined.log`): **1 failed**. Before the repair,
after a verified delete the SQL `IngestedDocument` row, lexical/action marker,
FTS row and materialized file survived.

File safety (`file-safety-failure-first.log`): **2 failed against parent
`914b9470d`**. The unsafe outside-path delete did not raise partial, and the
shared-file case lacked the effects receipt. This is the retained negative for
the new controls.

## After repair at final head

Joined durable suite:

```
pytest backend/tests/test_document_joined_lifecycle.py -q
```

Result: **11 passed** (`joined-11-file-safety.log`).

File-safety controls alone:

```
pytest backend/tests/test_document_joined_lifecycle.py::test_unsafe_outside_file_path_is_not_unlinked \
       backend/tests/test_document_joined_lifecycle.py::test_shared_file_is_preserved_for_peer_document -q
```

Result: **2 passed** (`file-safety-at-c90693c42.log`).

Bounded gate via the existing shared runner:

```
TESTING=1 DATABASE_URL=sqlite:///.../gate.db ATOM_DATA_DIR=... ATOM_OFFICE_DIR=... \
python3.11 /private/tmp/atom-agent-cli/run_bounded_test_gate.py \
  --cwd .../backend --profile bounded -- \
  python -m pytest \
    tests/test_document_joined_lifecycle.py \
    tests/test_document_delete_truth.py \
    tests/test_document_upload_persistence_outcome.py \
    tests/test_document_export.py \
    tests/test_documents_search_workspace_scope.py \
    -q --tb=short -k 'not base_and_chunk_family_verified_with_one_receipt'
```

Result: **60 passed, 1 deselected**
(`bounded-gate-c90693c42.log`).

Covered: durable removed tombstone, vector absence, lexical/hybrid/action
filtering, VFS/citability/export freshness guards, owned file unlink, shared
file preservation, unsafe outside path refusal, exact scope/version CAS,
stale same-version producer refusal, authorized newer version preservation,
replay inertness, SQL/file/FTS partial outcomes.

Deselected test: `test_base_and_chunk_family_verified_with_one_receipt` hits
pre-existing `ModuleNotFoundError: lance` from `handler.list_documents` in this
local venv; unrelated to this change.

## Boundaries

No new store/router/engine/migration; no `/search` enablement; no original
binary download or deferred format claim; no live action. Historical 143
claims / 18 goals unchanged.
