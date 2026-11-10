# Goal3 — durable document deletion and cross-store invalidation

Status: **frozen backend source/test candidate submitted for independent review.**
No merge or self-acceptance. This closes the observed supported-Documents
lifecycle gap only; it does not claim Goal 3 complete or enable deferred Search.

Base/current main after reconcile: `be8bb29f07b33077a49995816e8952721d3a6fd9`  
Merge commit: `9496da733`  
Source code: `db6e4a2fc0792dcb8c204a4bd1ddfc691da54935`  
Final test/evidence head: `c90693c4233bb3c191b89d11567ae0131e72cfa9`

## Confirmed gap (failure-first)

On the prior source, the verified `DELETE /api/documents/{doc_id}` removed only
LanceDB base/chunk rows. The retained negative
(`failure-first-joined.log`) uploads a synthetic TXT through the real public
upload route, confirms vector/list/open, SQL `IngestedDocument` + FTS, lexical,
hybrid, legacy `documents.search`, and the materialized file, then deletes and
finds:

- vector list/get/search clean (passes today);
- **SQL row still present**;
- **lexical/hybrid/action still return the marker**;
- **materialized file still present**.

Deleting only the SQL row would not be durable either: a queued/stale producer
could recreate it as fresh. The retained failure also demonstrates that a
naive vector-only delete test can pass while supported reads still leak.

The new file-safety controls also fail first against parent `914b9470d`
(`file-safety-failure-first.log`): the unsafe outside-path delete did not raise
partial, and the shared-file case had no effects receipt.

## Repair (existing mechanisms only)

`document_delete_service.py`:

- Captures the exact scoped/version `IngestedDocument` row before effects.
  A different source version returns **409** before any vector/file effect.
- Revokes with a retained `freshness_status='removed'` tombstone — the existing
  terminal marker used by upstream removal/supersession — instead of deleting
  the row. This makes revocation durable against stale producers.
- Materialized file effect:
  - only the row's `file_path`;
  - must resolve under `ATOM_OFFICE_DIR/uploads` and match `<doc_id>.<ext>`;
  - refuses symlinks/outside paths;
  - checks another SQL row referencing the same path before unlinking;
  - shared file is left alone and recorded; unsafe/failed unlink stays partial.
- Receipt/data aggregate vector, SQL tombstone, FTS/lexical and file effects.
  `verified` only when all supported effects are safe; otherwise
  `committed_unverified`/`effect_unknown` with `replay=do_not_repeat`. No
  cross-store atomicity or rollback is claimed.
- Same-operation replay returns the original receipt; incomplete/legacy
  receipts do not become clean `already_applied`.

Read/write guards:

- `lexical_ranker` SQLite/Postgres and ILIKE paths exclude terminal
  `stale/outdated/removed/superseded` freshness.
- legacy `documents.search` excludes the same terminal statuses; VFS/export
  already did.
- `vector_upsert` refuses the **same removed source version** before writing
  (`skipped_revoked`); a genuinely changed source version is allowed.
- `DocFreshnessService.mark_on_ingest` refuses terminal tombstone replay;
  superseded docs are never revived by an ingest.
- upload routes return **409 DOCUMENT_REVOKED** for the same removed version
  instead of rematerializing it.

No new store, table, router, engine or parallel catalog. The FTS row may remain
as part of the retained SQL tombstone; supported lexical/action/VFS reads
filter it, which is the content-access revocation.

## Verification

| Check | Result |
|---|---|
| Failure-first joined lifecycle | **1 failed**: SQL row/lexical/action/file survived vector delete |
| Failure-first shared/unsafe file controls on parent `914b9470d` | **2 failed** |
| Joined durable tests after merge | **11 passed** (`joined-11-file-safety.log`) |
| File-safety controls at final head | **2 passed** (`file-safety-at-c90693c42.log`) |
| Bounded documents gate via `run_bounded_test_gate.py` | **60 passed, 1 deselected** (`bounded-gate-c90693c42.log`) |
| Deselected test | `test_base_and_chunk_family_verified_with_one_receipt` hits pre-existing local `ModuleNotFoundError: lance` in `list_documents`; unrelated |

The joined positive proves: upload → list/open/vector/lexical/hybrid/action →
stored-text export → delete (verified) → SQL tombstone + vector absence +
lexical/action/hybrid absence + file absent → replay safe. Stale same-version
producer cannot republish; a changed version can be written and an old receipt
cannot delete it. Shared files are preserved; outside paths are never unlinked.

## Current-main reconcile

`origin/main` advanced to `be8bb29f0` (verified web creation receipt merge).
It was merged at `9496da733`, preserving both sides of the coordination/CI
union and every prior negative. No PR838/UI branch or worktree was edited.

## Boundaries

Supported synthetic-TXT ordinary Documents lifecycle only. No `/search` UI
enablement, original-binary download, PDF/Markdown breadth, PostgreSQL
multi-worker concurrency, model grounding or Goal 11 claim. No live
DB/model/provider/credential/send/spend, no world build/deletion, no dependency
install. Historical 143 claims / 18 goals unchanged; root owns merge/review.
