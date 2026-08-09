# Hybrid Search — Phase 1: Documents Leg (multi-source-shaped)

The agreed scope is a full multi-source hybrid service (documents + episodes + turn_facts + reasoning-steps → RRF + `_react_step` injection). This plan delivers **Phase 1: the documents leg**, built so the additional legs are additive follow-ups on the same `HybridSearchService` — not a parallel engine. I'm stating this explicitly to avoid the earlier silent-rescope mistake.

**Corrections applied from the critique (all verified):**
- **FTS5/tsvector is the lexical default**, copying the proven `turn_fact_extractor.py:929` + `20260624_add_reasoning_fts.py` pattern (FTS5 external-content on SQLite, tsvector/GIN twin on Postgres, dialect-aware migration). NOT `rank_bm25`. My "no BM25 anywhere" claim was false.
- **`vector_fastembed` exists in the schema** (`lancedb_handler.py:386`) but is unpopulated by `add_document` — the 1536-dim OpenAI decision stands, for the right reason now.
- **Backfill uses metadata stamping + hydration**, not an `id`-column rewrite. Two heuristic legs: `external_id` (adapter-ingested) and `source+file_name+ingested_at` window (file-ingested, which lacks `external_id` per `auto_document_ingestion.py:434-447`).
- **Deprecate/alias `unified_search_endpoints.py:71`** (`/api/lancedb-search/hybrid`, 0.7/0.3 fusion) so the two engines don't diverge.
- **Handle unbridged vector hits** (docs written by `competitive_intel.py`/`inventory_reconcile.py` with no PG row): `bridged: false` → drop or flag.

**Steps (per your todo list):**
1. **Join-key bridge** — reorder `new_id` before the LanceDB write in `auto_document_ingestion.py`; pass `doc_id=new_id`; stamp `metadata.pg_document_id` + `source_type`. TDD.
2. **FTS5/tsvector lexical ranker** — migration `202608XX_add_documents_fts.py` (copy the proven dialect-aware pattern); new `core/hybrid_search/lexical_ranker.py`. TDD.
3. **DocumentsHybridSearch service** — vector leg (1536-dim OpenAI via `EmbeddingService` → `LanceDBHandler.search`) + lexical leg (Step 2) + RRF k=60 fusion + degradation ladder (`lexical_only`/`no_results`). New `core/hybrid_search/documents_hybrid.py`. Designed as one leg of a multi-source `HybridSearchService`. TDD.
4. **Wire into `documents.search`** — preserve return shape (`{success,query,results:[{source,id,title,preview,score,modified?}],hybrid}`), label `lexical_ranked` → `bm25_vector_rrf`, update test assertion, flag-off parity unchanged. Deprecate `/api/lancedb-search/hybrid` to alias. TDD.
5. **Backfill** — `scripts/backfill_lancedb_join_keys.py` (external_id leg + file-heuristic leg; metadata stamp + hydrate, no id rewrite). Full regression.
6. **Docs** — `docs/architecture/AGENT_HYBRID_SEARCH.md` (multi-source shape documented, additional legs as named follow-ups), env vars, `TESTED_FILES_TRACKER.md`.

**Explicitly named as follow-ups on this same architecture (NOT in Phase 1):** episodes leg, turn_facts leg, reasoning-steps leg, `_react_step` auto-injection. Each is a new `*SearchLeg` class registered into the RRF service.

First build target: Step 1 (join-key bridge).