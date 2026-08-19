# Knowledge VFS — Agent-Native Document Tree (W1, Phase 2)

> **Status:** Phase 2 (P2a–P2c) implemented behind `ATOM_KNOWLEDGE_VFS_ENABLED`
> (default **off**). Kill-switch parity: flag off = exact pre-P2 behavior
> (legacy ILIKE `documents.search`, no VFS actions).
>
> **Last Updated:** Aug 8, 2026
>
> **Related code:** `backend/core/vfs_base.py`, `backend/core/vfs_registry.py`,
> `backend/integrations/vfs/knowledge_vfs.py`,
> `backend/core/knowledge_vfs_config.py`, `backend/core/action_registry.py`
> **Cross-references:** [`STANFORD_VIRTUAL_BIOTECH_PAPERCLIP.md`](./STANFORD_VIRTUAL_BIOTECH_PAPERCLIP.md)

---

## TL;DR

- The knowledge stores (`IngestedDocument` + `KnowledgeDocument`) are exposed
  as an agent-native virtual tree under `knowledge/` so agents navigate with
  `ls`/`cat`/`grep`/`search` instead of bespoke per-store operations.
- **Citable core:** every leaf's content is line-numbered `L<n>: <text>`, so
  `grep` returns precise citations and agents can quote
  `knowledge/documents/<id>/content.lines:L47`.
- 11 `documents.*` actions (`ls/tree/cat/head/tail/grep/scan/search/map/
  reduce/ask_image`) auto-discover through `action_registry` → RPC +
  capability_resolver + MCP dispatch (P1/P2/P9 enforcement points apply).
- `documents.search` is upgraded (flag on) to a real **hybrid search engine**
  — BM25 (FTS5/tsvector) + vector (LanceDB) fused by RRF. See
  [`AGENT_HYBRID_SEARCH.md`](./AGENT_HYBRID_SEARCH.md).

## VFS contract (`core/vfs_base.py`)

```
VFSNode      {name, type(dir|file), path, size?, modified?}
VFSResource  {path, meta, lines: ["L1: ...", "L2: ..."]}
VFSCitation  {path, line, snippet}
VFSProvider  {prefix, ls(), cat(), grep(), scan(), ask_image()}
```

- `grep` returns `[{path, line, snippet}]` — precise citations.
- `scan(path)` recursively enumerates every leaf `VFSNode` (BFS, depth-bounded).
- `ask_image` defaults to `vision_unavailable` (providers opt in).
- Providers register in `core/vfs_registry.py` under their `prefix`
  (`"knowledge"`); `resolve_provider(path)` picks by path prefix.

## Tree layout (`integrations/vfs/knowledge_vfs.py`)

```
knowledge/
  documents/
    <id>/                ← IngestedDocument or KnowledgeDocument
      meta.json          ← JSON metadata (source, file_name, title, …)
      content.lines      ← line-numbered content
  conversations/         ← 2026-08: communication memory subtree (bridge, not copy)
    <id>/                ← record in atom_communications (email/Slack/WhatsApp/Teams/Telegram)
      content.lines      ← line-numbered message content (meta: app_type, timestamp)
```

`grep` at a root prefix (`/`, `` or `knowledge`) scans **both** trees and
returns line-cited matches; a specific prefix scopes the scan. Conversation
records live in the comms memory store — the VFS reads them by id; nothing is
duplicated into the documents tables.

## Actions (flag-gated, kill-switch parity)

| Action | Purpose | Params |
|---|---|---|
| `documents.ls` | List children | `path` |
| `documents.tree` | Indented recursive tree (depth-limited) | `path`, `depth` |
| `documents.cat` | Full leaf, line-numbered | `path` |
| `documents.head` / `tail` | First/last N lines | `path`, `lines` |
| `documents.grep` | Regex citations | `pattern`, `path_prefix` |
| `documents.scan` | All leaf files under a dir | `path`, `max_depth` |
| `documents.search` | Ranked + filtered search (see below) | `query`, `limit`, `since`, `source`, `author` |
| `documents.map` | Bounded fan-out: one op per path (`cat/head/grep`), capped 50 | `paths`, `op`, `max_items` |
| `documents.reduce` | Aggregate map output (`count/concat/unique`) | `items`, `mode` |
| `documents.ask_image` | Vision question over a VFS image | `path`, `prompt` |

Every action returns `{success: False, error: "vfs_disabled", ...}` when the
flag is off — never raises (test `test_new_actions_disabled_when_flag_off`).

**Governance:** `map/reduce` are complexity-3 (HIGH) / SUPERVISED-gated at the
dispatch layer (capability_resolver / MCP tool gating); the registry itself is
thin and metadata-free, per the P1 architecture. All side effects still flow
through P1→P3→P4→P9 enforcement points.

## `documents.search` — hybrid search engine (BM25 + vector, RRF)

Flag off → exact pre-P2 ILIKE implementation (`_documents_search_legacy`,
kill-switch parity, test `test_action_search_flag_off_is_legacy_parity`).

Flag on → `_documents_search` delegates to `DocumentsHybridSearch`
(`core/hybrid_search/documents_hybrid.py`), which fuses two retrieval legs via
Reciprocal Rank Fusion (RRF, k=60). See
[`AGENT_HYBRID_SEARCH.md`](./AGENT_HYBRID_SEARCH.md) for the full architecture.
- **Lexical leg:** BM25 over FTS5 (`ingested_documents_fts` /
  `knowledge_documents_fts`, SQLite) or tsvector+GIN (Postgres), via
  `core/hybrid_search/lexical_ranker.py`. Falls back to ILIKE if the FTS
  tables are absent.
- **Vector leg:** 1536-dim OpenAI embedding → LanceDB ANN over the
  `documents` table. Each hit's `id` is the Postgres doc id (via the
  join-key bridge) → `documents.cat`-able.
- **RRF fusion:** rank-based, so BM25 and cosine scores need no
  normalization. Degradation ladder: `bm25_vector_rrf` → `lexical_only` →
  `semantic_only` → `no_results`.
- **Filters:** `source` (`ingested|knowledge`), `since`, `author` —
  passed through to both legs.
- Response tags the mode in `"hybrid"` (`bm25_vector_rrf` / `lexical_only` /
  `semantic_only` / `no_results`).

### H11 disposition — RESOLVED

The earlier plan noted the semantic leg was "absent by design" because
`hybrid_retrieval_service.py` was episode-bound and no FTS5/vector path
existed for documents. **This is now resolved:** the documents hybrid search
ships its own FTS5 indexes (`20260808_add_documents_fts.py`), a lexical ranker
(`lexical_ranker.py`), the vector leg via LanceDB, and the join-key bridge
(stamping `pg_document_id` at ingest). The episodes `HybridRetrievalService`
remains untouched; the documents leg is a separate service in the same
multi-source RRF architecture (episodes/turn_facts/reasoning-steps legs are
named follow-ups).

## Feature flags (`core/knowledge_vfs_config.py`)

| Flag | Default | Gates |
|---|---|---|
| `ATOM_KNOWLEDGE_VFS_ENABLED` | **false** | All `documents.*` VFS actions + hybrid search |

## Bug fixed along the way

The P2c action insertion **split `_canvas_read`**: its body's tail
(`canvas_id` handling + `read_canvas` call) was orphaned after
`documents.grep`, so `canvas.read` silently returned `None`. Restored as a
single contiguous action; regression test `test_canvas_read_registered_and_requires_auth`.

## Verification

- `tests/core/test_knowledge_vfs.py` (18) — ls/cat/grep, line-numbered
  content, hybrid search (parity + filters + ranking), tree/head/tail/scan,
  map/reduce, kill-switch parity for all new actions, `ask_image` degrade,
  canvas.read regression.
- `tests/test_action_registry.py` + `test_r79_action_registry_rpc.py` +
  `tests/core/test_action_registry_coverage.py` (85) — registry surface
  intact after additions.
