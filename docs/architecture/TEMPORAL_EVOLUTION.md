# Temporal Evolution (GraphRAG time travel)

> **Status**: W1–W4 implemented (2026-08-20). Companion to
> [CONTEXT_MEMORY.md](CONTEXT_MEMORY.md) / the Zep–Graphiti track of
> [AGENT_MEMORY_UNIFICATION_PLAN.md](../AGENT_MEMORY_UNIFICATION_PLAN.md)
> (Zep paper arXiv:2501.13956).
>
> **Principle**: every graph read answers "what did the network look like at
> instant *t*" — writes stay append/update-bi-temporal (GraphEdge already
> carries `valid_from`/`invalid_at` since P2.2), reads take an optional
> `as_of`/window cutoff. No cutoff = byte-identical legacy behavior.

## Program shape

| Wave | Delivery | Status |
|---|---|---|
| P0 | Ingestion-side temporal normalization (`core/memory/temporal_normalizer.py`) — regex date anchors, `temporal_entities`/`as_of`/`temporal_axis`, ingestion hook via `_record_to_text` override, `ATOM_TEMPORALITY_ENABLED` (default ON) | ✅ live |
| W1 | Point-in-time cutoffs on graph reads: `MultiHopExpander.expand(as_of=…)` (ORM + SQL), `SQLMultiHopExpander.expand_sql(as_of=…)`, `detect_communities(window_start/end)` + `_build_graph` | ✅ live |
| W2 | Hierarchy + persistence: `detect_hierarchy()` links children to the previous level's max-overlap parent and persists ALL levels into `graph_communities` with `parent_community_id` lineage (migration `20260820_add_graph_community_parent`) | ✅ live |
| W3 | Hierarchy rolling-window parity: `detect_hierarchy(store_results, window_start, window_end)` — window filters the graph before every resolution; recorded in `CommunityHierarchy.metadata` | ✅ live |
| W4 | Query-side time travel: `GraphRAGEngine.local_search(as_of=…)` (CTE traversal join + relationship listing + in-loop `expand_sql`), threaded through `query()` / `get_context_for_ai()` | ✅ live |
| W5 | This document + docs schema sync (`docs/intelligence/graphrag.md` `parent_community_id` column) | ✅ live |
| W6 | SQL expander SQLite portability: `_expand_sql_impl` emits a dialect-aware CTE (string-CSV path + `NOT LIKE` cycle detection on sqlite; legacy `ARRAY[]`/`ANY()` text for Postgres and bind-less callers) — Personal Edition's multi-hop augmentation now actually runs | ✅ live |
| W7 | Global-search time travel: outgoing community generations archive into `graph_community_snapshots` (`[valid_from, invalid_at)` intervals, memberships flattened to `node_ids`) on every replace-wipe; `global_search(as_of=…)` synthesizes from the generation active at that instant, falling back to live rows after the last replacement. Migration `20260821_graph_community_snapshots` | ✅ live |

**Out of scope (explicit boundaries)**:
- Nodes have no bi-temporal fields (only edges do, P2.2) — reads never
  time-filter nodes themselves; node `created_at` bounds only community
  detection windows (`_build_graph`).

## Contract details

### Window semantics (W1/W3 — `_build_graph`)

`[window_start, window_end]` snapshots the network as it was across the
interval:

- nodes participate when `created_at IS NULL OR created_at <= window_end`
- edges participate when their validity interval overlaps the window:
  `valid_from IS NULL OR valid_from <= window_end` **and**
  `invalid_at IS NULL OR invalid_at > window_start`
- NULL bi-temporal fields pass — legacy rows are never dropped
- window recorded in `DetectionResult.metadata` / `CommunityHierarchy.metadata`
  (`window_start`/`window_end` ISO strings + `graph_nodes`/`graph_edges` counts)

### as_of semantics (W1/W4)

An edge is alive at instant `t` iff `valid_from IS NULL OR valid_from <= t`
and `invalid_at IS NULL OR invalid_at > t` (invalidation boundary exclusive —
an edge invalidated *at* `t` is gone by `t`).

- W1: expansion prunes edges not alive at `as_of` in the ORM neighbor query
  and the SQL CTE + relationship listing; clause + `:as_of` params emitted
  only when present (legacy SQL byte-identical — no parameter drift for old
  callers); `metadata["as_of"]` recorded.
- W4: same predicate replaces `e.invalid_at IS NULL` in the engine's
  recursive CTE join and relationship listing **only** when `as_of` is given;
  the in-loop `expand_sql` receives the same cutoff; the result dict records
  `as_of` (ISO). `query()`/`get_context_for_ai()` thread the cutoff; SQLite
  note: `query()` runs local_search in a worker thread (embedding guard) —
  SQLite sessions are not thread-safe, so threaded regression tests mock the
  search legs (sync tests exercise real filtering).
- W6: the expander's own SQL is dialect-aware — sqlite gets the portable
  variant; Postgres and bind-less sessions keep the byte-identical legacy
  text (W1's recording-session contract holds).
- W7: one generation instant per persist — archived rows' `invalid_at` AND
  the incoming rows' explicit `created_at` (SQLite's `CURRENT_TIMESTAMP`
  has 1-second resolution, which would break exact interval chaining).
  Snapshot reads cover `[first_created, last_replacement)`; live rows are
  the active generation from the last replacement onward.

### Hierarchy lineage (W2/W3)

- Multi-resolution Leiden runs (`min_resolution → max_resolution` over
  `max_hierarchy_depth` levels); each child links to the community at the
  previous level with **maximal node overlap** (containment heuristic —
  multi-resolution partitions are not guaranteed nested; ties → first parent;
  zero overlap → unparented). Populated in-memory
  (`Community.parent_community` / `child_communities`) and mirrored to
  `graph_communities.parent_community_id` (migration
  `20260820_add_graph_community_parent`, guarded, nullable).
- Persistence is one shared replace-wipe core (`_persist_communities` /
  `_clear_workspace_communities`) for both `detect_communities` and
  `detect_hierarchy`; membership rows are deleted before communities.
- Generated ids (`comm_<i>`, `leiden_comm_<i>`) are per-run counters that
  recur at every level — the persisted-id map is keyed `(id, level)` and
  non-prefixed repeat ids are the caller's contract violation (tests use
  prefixed ids; the store mints fresh UUIDs only for prefixed ids).

## Files

- `core/graphrag/multi_hop_expansion.py` — W1 `as_of` (ORM + SQL), W6 dialect-aware SQL
- `core/graphrag/community_detection.py` — W1 windows, W2 hierarchy/link/
  persist, W3 hierarchy windows, W7 generation archival
- `core/graphrag_engine.py` — W4 query-side `as_of`, W7 `global_search(as_of=…)`
- `core/models.py::GraphCommunity.parent_community_id` — W2 column
- `core/models.py::GraphCommunitySnapshot` — W7 archive table
- `backend/alembic/versions/20260820_add_graph_community_parent.py` — W2 migration
- `backend/alembic/versions/20260821_graph_community_snapshots.py` — W7 migration
- `core/memory/temporal_normalizer.py` — P0 ingestion normalization
- Tests: `test_temporal_normalizer_p0.py` (24), `test_temporal_w1_timelines.py`
  (16), `test_temporal_w2_community_hierarchy.py` (10),
  `test_temporal_w3_hierarchy_windows.py` (8), `test_temporal_w4_query_asof.py` (8),
  `test_temporal_w6_sqlite_expander.py` (6), `test_temporal_w7_global_asof.py` (8)

## Verification

```bash
PYTHONPATH=backend venv/bin/python -m pytest backend/tests/test_temporal_w{1,2,3,4}_*.py -q
# regression: full graphrag cluster (see TESTED_FILES_TRACKER W2/W3 sessions)
```