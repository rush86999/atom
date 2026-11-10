# Goal3 durable document deletion — test results

Executed source: `db6e4a2fc0792dcb8c204a4bd1ddfc691da54935`  
Base/current main: `914b9470d254293369475cd9f0fecdbf76acd650`

Scratch SQLite + scratch LanceDB + deterministic embeddings. No live DB,
model/provider, credential, send or spend. Existing dependencies only.

## Failure-first

```
TESTING=1 DATABASE_URL=sqlite:///.../joined.db \
ATOM_DATA_DIR=... ATOM_OFFICE_DIR=... \
python -m pytest backend/tests/test_document_joined_lifecycle.py -q
```

Before the repair (`failure-first-joined.log`): **1 failed**.

The upload/open/vector/lexical/hybrid/action/file preconditions pass; after a
verified delete the SQL row `IngestedDocument`, lexical/action marker, FTS row
and materialized file survive.

## After repair

```
TESTING=1 DATABASE_URL=sqlite:///.../gate.db \
ATOM_DATA_DIR=... ATOM_OFFICE_DIR=... \
python -m pytest \
  backend/tests/test_document_joined_lifecycle.py \
  backend/tests/test_document_delete_truth.py \
  backend/tests/test_document_upload_persistence_outcome.py \
  backend/tests/test_document_export.py \
  backend/tests/test_documents_search_workspace_scope.py \
  -q --tb=short -k 'not base_and_chunk_family_verified_with_one_receipt'
```

Result: **58 passed, 1 deselected** (`focused-at-db6e4a2fc.log`).

The joined suite alone: **9 passed** (`joined-durable-tests.log`):

- verified delete leaves a `freshness_status='removed'` SQL tombstone, no
  vector base/chunks, no file, and lexical/hybrid/action cannot return it;
- replay returns the original receipt without a second effect;
- SQL revocation failure, file unlink failure and FTS readback failure return
  503 partial/unknown with `replay=do_not_repeat`, never clean success;
- foreign SQL scope is refused with zero effects;
- stale SQL version is 409 before vector/file effects;
- stale producer replaying the same removed version returns
  `skipped_revoked` and writes no vector row;
- an authorized changed version can be written, and the old receipt cannot
  delete it;
- upload of the same removed version returns 409 `DOCUMENT_REVOKED`.

Deselected test: `test_base_and_chunk_family_verified_with_one_receipt` hits
pre-existing `ModuleNotFoundError: lance` from `handler.list_documents` in this
local venv; it is an environment/dependency gap, not caused by this change.
The rest of `test_document_delete_truth.py` passes.

## Boundaries

No new store/router/engine/migration; no `/search` enablement; no original
binary download or deferred format claim; no live action. Historical 143
claims / 18 goals unchanged.
