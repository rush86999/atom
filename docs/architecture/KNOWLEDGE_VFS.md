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
- `documents.search` is upgraded (flag on) from ILIKE to a weighted
  lexical ranking with `since/source/author` filters.

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
```

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

## `documents.search` — hybrid upgrade (P2c)

Flag off → exact pre-P2 ILIKE implementation (`_documents_search_legacy`,
kill-switch parity, test `test_action_search_flag_off_is_legacy_parity`).

Flag on → `_documents_search`:
- **Lexical leg:** SQL `ILIKE` prefilter, then deterministic scoring —
  title/`file_name` hit = 3.0, content hit = 1.0; results sorted by score,
  capped by `limit`.
- **Filters:** `source` (`ingested|knowledge` — hard store exclusion),
  `since` (ISO datetime vs `created_at`/`external_modified_at`/
  `updated_at`), `author` (`integration_id` ILIKE for ingested,
  `metadata_json->author` for knowledge).
- Response tags `"hybrid": "lexical_ranked"`.

### Deviation recorded (H11 disposition)

The plan cited reusing `core/hybrid_retrieval_service.py` for a true
BM25+vector fusion. **Verified: that service is agent-episode-bound**
(`coarse_search_fastembed(agent_id=...)` over LanceDB episodes); no document
embeddings or FTS5 index exist for `IngestedDocument`/`KnowledgeDocument`.
Building one (background document indexer + embedding column/LanceDB table) is
a separate phase — tracked here as the H11 follow-on. Until then the semantic
leg is absent by design, not by omission: the action degrades honestly
(`lexical_ranked`) instead of claiming vector fusion it doesn't have.

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
