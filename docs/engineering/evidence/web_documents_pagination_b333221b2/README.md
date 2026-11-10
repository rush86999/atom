# Document library pagination repair — b333 / c4bc1d4b6

## Source

- Branch: `codex/web-documents-pagination-20261110`
- Clean base: `b333221b23f925b3768ab82c2549200360a31865`
- Code/test commit: `c4bc1d4b623eb56d54491e4c79052885b5950cff`
- No old-811 history and no PR-812 workflow change is included.

## Retained negative

Root independently re-read the real 130-record store and kept the negative:
page 0 returned 100, `offset=100` returned 30, pages overlapped by **30** and
**30** records were missing, including the newest `w1-doc-129`. Root proof:
`/private/tmp/root-document-pagination-independent-20261110.json`.

## Repair

- `LanceDBHandler.list_documents_page` uses the installed Lance SDK's
  projected native scan:
  `LanceDataset.to_table(columns=..., limit=..., offset=...,
  order_by=[ColumnOrdering("created_at", descending),
  ColumnOrdering("id", descending)])`.
  Ordering is global and applied before offset/limit; the vector column is not
  projected. The opaque id is the deterministic tie-break for equal
  timestamps. Native `LanceTable.count_rows()` supplies the total.
- The API returns `total`, `count`, `has_more`, `next_offset`,
  `previous_offset` and `ordering`. `next_offset` is emitted only when the
  page returned at least one row, so a zero-length page cannot self-loop; a
  stale zero-length page is flagged.
- Unsupported/failed native ordering/count raises
  `DocumentListingUnavailable`. The old incomplete prefix-sort fallback is
  removed. The route maps that to **503**; a missing/empty table remains a
  truthful **200** empty library. Traced other callers (`org_data_bundle_service`
  catches and records unavailable; `pack_service` uses the stub handler and
  already degrades) keep their existing behavior. The 1..100 limit cap,
  workspace resolution and auth dependency are unchanged.
- Documents UI: stable `limit=100`/`offset` paging, `Page X of Y`,
  `Showing A–B of N`, Previous/Next with boundary disabling,
  loading/empty/error+Retry states, upload resets page 1, deletion elsewhere
  that empties a later page falls back to the previous page, and request
  sequencing ignores stale responses. Search stays profile-gated; upload,
  open, reload, export and supported formats are unchanged.

## Ordering semantics / limits

Lexicographic ordering on the stored `created_at` string descending, then
opaque `id` descending. Values are expected to be UTC ISO-8601. There is no
snapshot guarantee across concurrent writes: total and the page are separate
native scans; `has_more` never self-loops.

Official SDK references:
- https://lancedb.github.io/lancedb/python/python
- https://lance.org/guide/read_and_write
Installed runtime: lancedb 0.24.3.

## Commands and exits

Backend focused gate (`run_bounded_test_gate.py --profile bounded`):

```
python3 /private/tmp/atom-agent-cli/run_bounded_test_gate.py \
  --cwd /private/tmp/atom-web-task-project-20261109/backend --profile bounded -- \
  /usr/local/bin/python3.11 -m pytest \
  tests/api/test_document_library_pagination.py \
  tests/test_covpush_w90_core_services.py::TestW90ListDocuments \
  tests/core/test_lancedb_handler_bughunt2.py \
  tests/test_document_delete_truth.py \
  tests/unit/api/test_document_routes.py \
  tests/test_org_memory_bundle.py -q --tb=short
```

Result: **77 passed, exit 0**. The new pagination file alone: **13 passed**.

Frontend focused gate:

```
python3 /private/tmp/atom-agent-cli/run_bounded_test_gate.py \
  --cwd /private/tmp/atom-web-task-project-20261109/frontend-nextjs --profile bounded -- \
  node node_modules/.bin/jest tests/pages/documents.test.tsx --runInBand
```

Result: **23 passed, exit 0** (17 existing + 6 pagination/invalidation).

TypeScript: `node node_modules/typescript/bin/tsc --noEmit` → **exit 0, 0 errors**.
ESLint on the two changed frontend files → **exit 0**.

## Baseline identity

At clean base `b333221b2`, these same two tests fail and are unrelated to this
repair:

- `tests/test_covpush_ingestion_lancedb.py::TestLanceDBInit::test_llm_service_unavailable_fallback`
- `tests/test_covpush_ingestion_lancedb.py::TestLanceDBEmbed::test_async_embed_text_success`

Baseline log: `/private/tmp/doc-pagination-repair-backup/baseline-two-tests.log`
(2 failed). After the repair the same 2 remain; no new failures were added.
The erroneous post-commit stash episode from the earlier evidence task is not
used as a baseline.

## Scope

Real scratch SQLite auth DB and per-workspace scratch LanceDB; real JWT and
normal `get_current_user` dependency; no live database, provider, model,
browser, build, download, key or deployment. Not qualified: concurrent-write
snapshot isolation, production browser/UI acceptance, PostgreSQL/soak, and
whole-app completion (143 claims / 18 goal rows remain unchanged).


## Root independent proof (appended 2026-11-10)

Root independently accepted the frozen repair on evidence source
`1605d7713116f1552d23e6a8288fd3902ce9468a` / product source
`c4bc1d4b623eb56d54491e4c79052885b5950cff`:

- 13 normal controls passed in 26.99s.
- Original real 130-record fixture acceptance passed in 3.73s: all 130
  complete/disjoint, newest first, truthful total 130 including offset beyond
  end, foreign/shared isolation, rows unchanged.
- 23 frontend tests passed in 1.098s.
- Strict packet: 8 source / 2 artifact checks passed.

Root records and private probe are included as
`root_independent_verification.json`, `root_independent_original_130_results.json`
and `root_independent_probe.py`; `root_proof_summary.json` carries the safe
counts. The original 100/30 overlap-30/missing-30 negative remains preserved.
Selector counts 77 (worker focused gate) and 80 (root backend neighborhood) are
different and must not be summed; 13 and 23 are separate selectors.

No browser/build/server was executed for this append.
