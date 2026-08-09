# Plan: Agent Hybrid Search (lexical + semantic, RRF) across all memory stores

## Objective

Give the agent the ability to hybrid-search relevant data — fusing a true lexical leg
(FTS5/BM25 on SQLite, tsvector on PG) with the existing LanceDB semantic leg via
Reciprocal Rank Fusion (RRF) — across **all four stores**: Documents (knowledge base),
Episodes (past runs), TurnFacts (long-term memory), Reasoning steps (thought/observation
traces). Two surfaces: an agent-callable **tool** (`memory_search`) and **automatic
context injection** into the agent prompt. Complements the Knowledge VFS: search finds
the doc, VFS cites the line.

## Current state (verified)

- `backend/core/hybrid_retrieval_service.py` — two-stage vector+rerank pipeline, only
  via `POST /agents/{id}/retrieve-hybrid`, **not wired into the agent loop**.
- `documents.search` (`action_registry.py:226-334`) — lexical-only ILIKE + hand-rolled
  weights; vector leg exists only in `unified_search_endpoints.py:71-194` (0.7/0.3
  weighted, post-hoc boost over a single vector result set).
- Real BM25 exists **only** for reasoning steps: `search_reasoning_steps_lexical`
  (`turn_fact_extractor.py:899-966`) — SQLite FTS5 `bm25()` + PG `ts_rank`,
  external-content table from `alembic/versions/20260624_add_reasoning_fts.py`.
- **No RRF anywhere**; no FTS on Episode / IngestedDocument / KnowledgeDocument / TurnFact.
- LanceDB tables (1536-dim `vector`, written by default): `documents`, `episodes`,
  `turn_facts`, `agent_experience`. Reasoning steps have **no vector** → lexical-only
  leg. Dual-embedder hazard: query vectors MUST use `LLMService.generate_embedding`
  (1536-dim) to match the `vector` column — NOT FastEmbed 384-dim.
- `memory_search` / `memory_recall` already whitelisted as capability/tool names in
  `sandbox_policy.py:90-91` + `mini_app_service.py:41-42` — **stubs with no
  implementation**; zero sandbox-policy changes needed to activate.
- **Result-identity silo (audit finding)**: LanceDB `documents` rows get
  `id = str(datetime.timestamp())` when the caller passes no `doc_id`
  (`lancedb_handler.py:725`; `add_document` supports caller `doc_id` at `:653-655`).
  `auto_document_ingestion.py:434` writes the vector row WITHOUT `doc_id`, while the
  PG `IngestedDocument` row gets a UUID (`:615`/`:749`) — no join key. The VFS
  resolves `knowledge/documents/<id>` against PG UUIDs only
  (`knowledge_vfs.py:163-170`), and `unified_search_endpoints.py` hydrates only from
  LanceDB `metadata` (`:137-178`) — so a semantic hit today can neither be hydrated
  from PG nor catted via the VFS. (Contrast: `turn_facts` and `episodes` LanceDB ids
  already equal their PG ids — both hydrators work today, so documents is the only
  broken store.)
- Agent context today: `world_model.recall_experiences` once per execute
  (`generic_agent.py:121-124`), MEMORY CONTEXT block in `user_prompt` (`:913-923`);
  meta-agent does Tier-1/Tier-2 TurnFact recall per step.

## Design

### 1. `backend/core/agent_hybrid_search.py` (NEW) — `AgentHybridSearchService`

```
search(query, top_k=8, sources=(documents|episodes|turn_facts|reasoning_steps),
       agent_id=None, workspace_id=None, since=None)
```

Per-source legs, then RRF fusion:

- **Lexical leg (per source with FTS)**:
  - reasoning_steps → reuse `search_reasoning_steps_lexical` (exists, BM25/ts_rank)
  - documents / episodes / turn_facts → new FTS5 external-content tables (SQLite)
    + generated tsvector + GIN (PG), mirroring `20260624_add_reasoning_fts.py`;
    rank via `bm25()` / `ts_rank(plainto_tsquery(...))` with the same
    `_query_safe_tokens` prefix-token MATCH technique (`turn_fact_extractor.py:972-974`)
- **Semantic leg**: `LanceDBHandler.similarity_search` on the `vector` column
  (1536-dim) per LanceDB-backed source (documents, episodes, turn_facts), prefiltered
  by `agent_id ==` / `workspace_id ==`; query embedded via
  `LLMService.generate_embedding` (matching the write path). reasoning_steps → no leg.
- **Fusion**: RRF with k=60, `score = Σ 1/(k + rank)` over each leg's ranked list;
  per-source dedupe by store id; keep leg provenance per result (`lexical_rank`,
  `semantic_rank`, fused score) for observability.
- **Contract**: capped top-k, per-source limits, never raises (each leg individually
  try/except → empty leg, logged), timeout budget, results tagged
  `{source, source_id, score, snippet, title}` so callers can hydrate.
- Kill switch `ATOM_AGENT_HYBRID_SEARCH_ENABLED` (default true).

### 2. Tool — `memory_search` (implement the whitelisted stub)

- `backend/tools/memory_tool.py`: add `memory_search(query, top_k=8, sources=None)`
  registered like `memory_remember` (INTERN+ read-only floor? — read-only search stays
  STUDENT+ per platform read-only rule; propose INTERN+ to match existing memory tools,
  decide in review), delegating to the service. No sandbox-policy changes (names
  already whitelisted). Add to MCP pseudo-server dispatch alongside memory tools.

### 3. Auto context injection — `generic_agent._react_step`

- One hybrid recall per `execute` with the user query (alongside
  `recall_experiences` at `generic_agent.py:121-124`), gated on the flag, never raises.
- Inject `HYBRID SEARCH RESULTS` block into `user_prompt` after MEMORY CONTEXT
  (`:913-923`), capped top-4 with source tags (episode ids, doc titles, fact text,
  step refs) so follow-up tool calls can cite/hydrate.
- meta-agent wiring = follow-up, out of scope.

### 4. Result-identity bridge (documents — canonical join key)

**Design decision: the LanceDB `documents` row `id` IS the PG `IngestedDocument.id`**
(no new columns, no schema migration, no metadata-prefilter joins — the latter are
unreliable anyway: `unified_search_endpoints.py:109-116` documents that nested
`metadata.*` SQL filters don't work because metadata is stored as a JSON string).

- **Write time** (`auto_document_ingestion.py:434` and the `_upsert_document` path
  at `:723-780`): pass `doc_id=str(pg_uuid)` into `add_document(...)` (param already
  supported, `lancedb_handler.py:653-655`); also stamp `source_doc_id` + `pg_id` into
  the row `metadata` for audit/tracing.
- **Hydration**: semantic-leg hit carries `id` → PG lookup
  `IngestedDocument.id == hit["id"]` → title/content_preview + VFS path
  `knowledge/documents/<uuid>` (directly `cat`-able via `KnowledgeVFSProvider`).
- **Legacy rows** (pre-fix timestamp ids): no PG row resolves → degraded display
  (metadata title/preview only), result flagged `"bridged": false`; `documents.search`
  lexical-leg hits are PG-native so always bridged. No mass backfill (id rewriting
  would corrupt existing vector rows); bridge is write-time going forward.
- **Reverse lookup (PG → LanceDB) deferred** — RRF needs only rank lists, so the
  semantic leg never requires PG→LanceDB; revisit only if a future feature needs
  vector enrichment of lexical hits.
- **Invariant test**: every LanceDB `documents` row id resolves to a PG
  `IngestedDocument` (property test over a seeded corpus); same id-consistency
  assertion for `turn_facts` / `episodes` (already true — locks the invariant).

### 5. Migrations (one revision)

- `20260808_add_agent_hybrid_search_fts.py`: FTS5 external-content tables + triggers
  for Episode (summary/content/outcome), IngestedDocument (file_name/content_preview),
  KnowledgeDocument (title/content), TurnFact (fact_text); PG: tsvector columns + GIN.
  Guard everything with `_table_exists()`/`_column_exists()` (SQLite hybrid dev DB).

## Files to change

| File | Change |
|---|---|
| `backend/core/agent_hybrid_search.py` | NEW — service, legs, RRF, contract, identity bridge |
| `backend/core/auto_document_ingestion.py` | pass `doc_id=pg_uuid` at both `add_document` sites + metadata stamp |
| `backend/alembic/versions/20260808_add_agent_hybrid_search_fts.py` | NEW — FTS5/tsvector |
| `backend/tools/memory_tool.py` | `memory_search` tool (stub activation) |
| `backend/core/generic_agent.py` | hybrid recall + prompt block + flag |
| `backend/core/hallucination_config.py` | `ATOM_AGENT_HYBRID_SEARCH_ENABLED` |
| `backend/core/turn_fact_extractor.py` | (optional) export `_query_safe_tokens`/lexical helper for reuse |
| `docs/architecture/AGENT_HYBRID_SEARCH.md` | NEW — design + usage |
| `docs/reference/ENVIRONMENT_VARIABLES.md` | flag row |
| `docs/testing/TESTED_FILES_TRACKER.md` | session row after verification |

## Tests (TDD first)

- `backend/tests/core/test_agent_hybrid_search.py` (NEW):
  - lexical leg per source (known-answer fixtures: term hits + ranking)
  - semantic leg per source (mocked LanceDB) + 1536-dim embedding contract
  - **bridge**: semantic hit id → PG row hydrated → VFS path cat-able; timestamp-id
    legacy row → `bridged: false` degraded display, no raise
  - RRF fusion: doc in both legs ranks above single-leg doc; dedupe; top-k cap; ordering deterministic
  - filters (agent_id/workspace_id/since) applied per leg
  - empty corpus → empty result, no raise; flag OFF → no-op
  - property tests: top-k ≤ k, no duplicate ids, source tags present, never raises,
    LanceDB-documents-id ↔ PG-id consistency (seeded corpus)
- `backend/tests/core/test_memory_tool.py`-adjacent: `memory_search` dispatch through
  registry + maturity gate (governance floor respected)
- Regression: `test_reviewer_and_diversity.py`, `test_agent_environment_harness.py`,
  `test_turn_fact*.py`, episode-retrieval suites, `test_covpush_generic_agent.py`

## Verification

```bash
PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m pytest \
  backend/tests/core/test_agent_hybrid_search.py \
  backend/tests/core/test_memory_tool.py -q          # new suites
# regression sweep + mypy (zero new errors) per repo standards
```

## Out of scope (follow-ups)

- meta-agent auto-injection; PG runtime validation of tsvector branch (SQLite default);
- rerank-stage (cross-encoder) on fused results; federation of VFS grep as a 5th source.
