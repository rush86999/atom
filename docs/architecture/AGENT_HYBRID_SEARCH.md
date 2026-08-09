# Agent Hybrid Search — BM25 + Vector RRF (Multi-Source)

> **Status:** Phase 1 (documents leg) shipped. The agent's `documents.search`
> is now a real hybrid search engine: BM25 (FTS5/tsvector) + vector (LanceDB)
> fused by Reciprocal Rank Fusion (RRF, k=60). Additional legs (episodes,
> turn_facts, reasoning-steps) + `_react_step` auto-injection are named
> follow-ups on the same architecture.
>
> **Last Updated:** Aug 8, 2026
> **Related code:** `core/hybrid_search/` (package), `core/action_registry.py`
> **Cross-references:** [`KNOWLEDGE_VFS.md`](./STANFORD_VIRTUAL_BIOTECH_PAPERCLIP.md)

---

## TL;DR

- `documents.search` was hand-weighted substring matching (`"lexical_ranked"`) —
  no semantic retrieval, no BM25. It now fuses **two real legs** via RRF:
  - **Lexical**: BM25 over FTS5 (SQLite) / tsvector+GIN (Postgres)
  - **Vector**: 1536-dim OpenAI embeddings → LanceDB ANN
- The LanceDB vector store and Postgres documents were **disconnected silos**
  (timestamp ID vs UUID). A join-key bridge (`pg_document_id` stamped at ingest)
  lets vector hits resolve to `documents.cat` VFS paths.
- This is **one leg** of a planned multi-source service. The RRF fusion layer
  is leg-agnostic; episodes/turn_facts/reasoning-steps legs are additive.

## The three discoverability goals (and where each stands)

| Goal | What it solves | Status |
|---|---|---|
| **Semantic search** | "find docs about X" (ranked, fuzzy) | ✅ shipped (this work) |
| **Precise access + citation** | "show me doc Y line 47" | ✅ shipped (VFS `ls`/`cat`/`grep`) |
| **Topic-organized browsing** | "show me the finance folder" | ❌ future (VFS hierarchy restructure) |

Hybrid search (row 1) and the VFS (row 2) **compose**: search finds the doc,
VFS cites the line.

## Architecture

```
documents.search(query)
  └─ DocumentsHybridSearch.search(query)
       ├─ Lexical leg: search_documents_lexical(db, query)
       │    └─ BM25 over ingested_documents_fts + knowledge_documents_fts
       │       (FTS5 external-content + triggers, SQLite; tsvector+GIN, Postgres)
       │       Falls back to ILIKE if FTS tables absent.
       ├─ Vector leg: LanceDBHandler.search("documents", query)
       │    └─ 1536-dim OpenAI embedding → ANN over LanceDB documents table
       │       Vector hit id = PG doc id (via join-key bridge) → VFS-citable
       └─ RRF fusion (k=60): rrf(d) = Σ 1/(60 + rank_i) across both legs
            └─ Hydrate from PG (drop/count unbridged hits)
```

### RRF over weighted-average

RRF is rank-based, so the two legs' incomparable score scales (BM25 vs cosine)
need no normalization. This is why RRF is used instead of the weighted-average
(`0.3*coarse + 0.7*reranked`) the episodes `HybridRetrievalService` uses —
that pattern works when both scores are comparable confidences; BM25 and cosine
are not.

## The join-key bridge (Step 1)

The LanceDB `documents` table and Postgres `IngestedDocument`/`KnowledgeDocument`
were disconnected: LanceDB used `str(timestamp)` as the id; Postgres used
`"doc_<ts>"` (or a UUID). No join key existed.

**Fix:** generate the PG id *before* the LanceDB write and pass it as `doc_id=`,
so the LanceDB row id equals the PG row id. Stamp `metadata.pg_document_id` +
`source_type` for filtering/audit. Three ingest paths covered:
- **Adapter-ingest** (`auto_document_ingestion.py:587`) — `source_type:"ingested"`
- **API-ingest** (`api/document_routes.py`) — passes `doc_id` directly
- **File-ingest** (`auto_document_ingestion.py:434`) — `source_type:"file"` (no PG row → flagged `bridged:false`)

**Backfill** (`scripts/backfill_lancedb_join_keys.py`): stamps pre-bridge rows
via two heuristic legs (external_id match; source+file_name+time-window). Stamps
metadata only — does NOT rewrite the id column (LanceDB is append-only).

## Degradation ladder

| Condition | Label | Behavior |
|---|---|---|
| Both legs return results | `bm25_vector_rrf` | Full hybrid fusion |
| Vector leg empty (no LanceDB/embeddings) | `lexical_only` | BM25 results only |
| Lexical leg empty | `semantic_only` | Vector results only |
| Both empty | `no_results` | Empty list |
| Vector hit has no PG row (unbridged) | (counted in `stats.unbridged_hits`) | Dropped from results, counted |

Never raises — every failure degrades to a labeled empty/partial result.

## Feature flag

`ATOM_KNOWLEDGE_VFS_ENABLED` (default `true`). When `false`, `documents.search`
falls through to `_documents_search_legacy` — the exact pre-hybrid ILIKE path
(kill-switch parity; no `hybrid` key in the response).

## Named follow-ups (NOT in Phase 1)

Each is a new `*SearchLeg` class registered into the same RRF service:
- **Episodes leg** — reuse `HybridRetrievalService.retrieve_semantic_hybrid`
  (episodes have dual vectors: 1536-dim + 384-dim FastEmbed).
- **Turn-facts leg** — the FTS5 `agent_reasoning_steps_fts` already exists;
  add a vector leg if turn-facts get embeddings.
- **Reasoning-steps leg** — `agent_reasoning_steps_fts` (BM25) is live.
- **`_react_step` auto-injection** — inject hybrid-retrieved context into the
  agent's ReAct loop at step start (the recall-experiences injection point).

## Verification

- `test_hybrid_join_key.py` (3) — join-key bridge across all 3 ingest paths.
- `test_lexical_ranker.py` (8) — FTS5 BM25 ranking + ILIKE fallback.
- `test_documents_hybrid_search.py` (5) — RRF fusion, degradation ladder, unbridged counting.
- `test_documents_search_wired.py` (3) — action wiring, label, flag-off parity.
