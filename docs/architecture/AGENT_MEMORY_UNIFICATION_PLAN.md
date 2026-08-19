# Agent Memory Unification Plan — Retrieval at the Moment of Service

**Status:** Proposed (2026-08-19) · **Owner:** brennan.ca pilot → upstream · **Sponsor goal:** the README's "AI agent employee" promise — a teammate that *remembers customers, commitments, and past work* and retrieves the right memory at the moment it serves an employee.

**Companion audit:** the gap inventory below comes from a full code trace (2026-08-19) of ingestion → retrieval paths. This plan maps research-proven patterns onto those exact gaps, ranked by pilot-visible value.

---

## 1. Research summary — what the leading systems agree on

| System | Pattern worth borrowing | Source |
|---|---|---|
| **mem0** | Three-stage pipeline: **extract** salient facts → **consolidate** (LLM decides ADD / UPDATE / DELETE against existing memories — prevents bloat and contradiction) → **hybrid retrieve** (vector for semantics + graph for relational structure). Atom already owns all three stores; it lacks consolidation and the retrieval wiring. | [Mem0 paper (arXiv:2504.19413)](https://arxiv.org/abs/2504.19413), [mem0 hybrid design](https://mem0.ai/blog/long-term-memory-ai-agents) |
| **Zep / Graphiti** | **Bi-temporal graph edges**: every fact carries valid-time + ingestion-time; contradictions **invalidate** edges instead of overwriting — "what was the price last month" stays answerable, stale facts stop leaking into prompts. | [Zep paper (arXiv:2501.13956)](https://arxiv.org/html/2501.13956v1), [Graphiti](https://github.com/getzep/graphiti) |
| **Letta / MemGPT** | Tiered memory: **core** (small, always-in-context block) vs **archival** (vector-searchable), plus **sleep-time compute** — memory reorganization happens offline, not in the user-facing turn. Latency-critical turns read; background workers write/compact. | [MemGPT paper](https://alphaxiv.org/abs/2310.08560), [Letta sleep-time compute](https://www.letta.com/blog/sleep-time-compute/) |
| **Claude vs ChatGPT memory** | Two poles: ChatGPT injects a growing flat fact-list every turn; Claude starts blank and *pulls* context on demand via an inspectable file-based memory tool. Best-of-both: a **bounded, high-precision always-injected block** + **agentic tools for deep dives**. | [Simon Willison's analysis](https://simonwillison.net/2025/Sep/12/claude-memory/), [cross-vendor comparison](https://shibuiyusuke.medium.com/a-deep-comparison-of-memory-implementations-across-gemini-openai-and-anthropic-the-state-of-5b5fc9c1fa6) |
| **Context engineering** | Hybrid retrieval cadence wins: cheap **pre-retrieval** for base context + **just-in-time agentic search** for depth, with post-retrieval **reranking** to fit latency budgets. Pure pre-retrieval goes stale; pure agentic search is slow. | [Anthropic: Effective Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents), [mem0 retrieval strategies](https://mem0.ai/blog/memory-retrieval-strategies-for-ai-agents) |

**Design principles adopted:** (1) turns *read* memory, background jobs *write/compact* it; (2) always-injected context must be small and high-precision, everything else is tool-gated; (3) hybrid legs (vector + lexical + graph + episodes) fused with bounded rerank; (4) facts consolidate — supersede, don't accumulate.

---

## 2. Current-state gaps (from the 2026-08-19 code audit)

1. **ChatOrchestrator** (`integrations/chat_orchestrator.py:504-587`) — the brain behind web chat AND every IM bridge (Telegram/Slack/WhatsApp via `universal_webhook_bridge.py:120`) — performs **zero retrieval** and extracts **no turn facts**. Static prompt + last-3 turns only.
2. **Meta agent fetches-then-drops context**: `world_model.recall_experiences` returns `knowledge_graph`, `conversations`, `episodes` keys; `_react_step` (`atom_meta_agent.py:1383-1387`, `generic_agent.py:900-903`) never renders them.
3. **Meta agent tool whitelist** (`CORE_TOOLS_NAMES`, `atom_meta_agent.py:352-377`) excludes `documents.search`, `memory_remember/forget`, and all communication-memory search.
4. **Conversational data is unreadable at retrieval time**: comms land in `atom_communications` (Pipeline A, vector+FTS — no agent reader), `integration_*` tables (Pipeline B — write-only), `tenant_*_messages` (Pipeline C). `DocumentsHybridSearch` reads only the `documents` table.
5. **Episode split-brain**: segmentation writes LanceDB `episodes`; world-model recall reads `agent_episodes`; no agent tool exposes `EpisodeRetrievalService` (HTTP-only).
6. **Telegram asymmetry**: graph ingestion yes (Pipeline B), FTS comms store no (not in Pipeline A's bridge list).

---

## 3. The plan — ranked by value to the AI agent employee

### P0 — Make the employee surface memory-aware (pilot-visible this week)

**P0.1 — Unified turn-time context assembly for ChatOrchestrator** (highest value)
New `core/memory_context_assembler.py`: given `(message, user_id, workspace_id)`, run in parallel with a hard budget (≤400 ms, degrade to empty on timeout):
- Comm-memory hybrid search: `CommunicationIngestionPipeline.search_communications` (vector+FTS) — top 5
- GraphRAG: `graphrag_engine.get_context_for_ai` — bounded entity/relationship string
- Episodes: `EpisodeRetrievalService.retrieve_contextual` — top 3
- Turn-facts: existing `prefetch_relevant_facts` — top 5
Fuse via per-leg caps + recency tiebreak (skip cross-encoder rerank in P0; add in P1), render as one `RELEVANT MEMORY` block ≤1,500 tokens into `_get_qwen_response`'s messages. Behind env `MEMORY_CONTEXT_ASSEMBLY=true` (default on, off = old behavior).
*Pattern: Anthropic pre-retrieval + Claude bounded-block; mem0 hybrid legs.*

**P0.2 — Turn-fact extraction on the chat path** — after orchestrator response, fire-and-forget `turn_fact_extractor` per turn (same call the meta agent makes at `atom_meta_agent.py:2301`). Chat stops being a memory black hole.
*Pattern: Letta — writes happen off the user-facing path.*

**P0.3 — Render the dropped keys** — `_react_step`/`generic_agent` render `knowledge_graph` and `episodes` from `recall_experiences` (bounded: graph ≤800 tokens, episodes ≤600). Two-block prompt diff; the flagship agent instantly sees ontology identities + learning episodes it already paid to fetch.

**P0.4 — Telegram into Pipeline A** — add a telegram normalizer/bridge in the tiered comm list (`ingestion_pipeline.py:1279`) so Telegram messages get the FTS-indexed `atom_communications` representation alongside their graph entities.

**P0 verification:** live bot test — "what did we quote ACME Fab?" must return seeded graph facts; unit tests per leg; latency budget test.

### P1 — Agentic deep-dive + tool equality (week 2)

**P1.1 — Expose retrieval tools to the meta agent**: add `documents.search`, `memory_remember`, `memory_forget`, and a new `search_communications` MCP tool (wrapping Pipeline A's search — memory store, not live APIs) to `CORE_TOOLS_NAMES`. *Claude's memory-tool pattern: inspectable, agent-driven pulls for depth beyond the injected block.*

**P1.2 — Episodic recall tool + table unification**: register `recall_episodes` (modes: semantic/similar_failures/contextual) in the tool registry; standardize both write paths on the `episodes` table (migrate `agent_episodes` writes in `episode_service.py:1553`, backfill, read from one).

**P1.3 — Conversations leg for hybrid search**: extend `DocumentsHybridSearch` (or add a `memory.search` action) to RRF-fuse `atom_communications` + `documents` + `turn_facts` legs — closing the "ingested but unreadable" loop for emails/Slack/WhatsApp.

**P1.4 — Rerank**: cross-encoder rerank of the assembled block when budget allows (`HybridRetrievalService` already exists — reuse it inside the assembler instead of HTTP-only).

### P2 — Memory quality: consolidation + time (post-pilot, pre-SaaS)

**P2.1 — Consolidation worker (mem0-style)**: nightly `memory_consolidator` job — for each entity/subject, LLM reviews recent turn facts + comms extracts vs existing facts/graph edges, emits ADD/UPDATE/INVALIDATE ops with audit trail. Kills drift, dedupes, and controls prompt bloat. *Sleep-time compute: never in the employee-facing turn.*

**P2.2 — Bi-temporal graph edges**: add `valid_from`/`invalid_at` to `GraphEdge` (migration), invalidation-not-deletion on contradiction (Zep pattern). Makes "what did ACME pay last quarter" answerable and stops superseded facts leaking into `get_context_for_ai`.

**P2.3 — Memory eval harness**: golden set of (question → expected memory) pairs from brennan pilot transcripts; regression-gate recall@k for the assembler. Without this, consolidation changes are unmeasurable.

---

## 4. Budgets, risks, rollout

- **Latency:** assembler hard-caps at 400 ms parallel (P0), rerank only when total < 800 ms (P1). IM replies already tolerate multi-second LLM time; the budget protects p95.
- **Prompt bloat:** total injected memory ≤2,500 tokens across blocks; per-leg caps; consolidation (P2) is the long-term governor.
- **Privacy:** assembler is workspace-scoped; sensitivity tags respected (confidential+ excluded from any cross-user injection) — matches org-sharing sensitivity ladder.
- **Rollout:** env-flagged (`MEMORY_CONTEXT_ASSEMBLY`), default-on after P0 verification on the brennan pilot, auditable in runbook.

**Sequencing rationale:** P0 turns the surface employees actually touch (Telegram/web chat) from amnesiac to memory-aware and unblocks every demo beat that hinges on recall ("Atom remembered the quote, the budget, the deadline"). P1 gives agents self-serve depth. P2 makes memory *trustworthy* over months — the difference between a demo and a deployable employee.

---

## 5. Sources

- [Mem0: Building Production-Ready AI Agents with Scalable Memory (arXiv)](https://arxiv.org/abs/2504.19413) · [mem0: Long-Term Memory for AI Agents](https://mem0.ai/blog/long-term-memory-ai-agents) · [mem0: Memory Retrieval Strategies](https://mem0.ai/blog/memory-retrieval-strategies-for-ai-agents)
- [Zep: A Temporal Knowledge Graph Architecture for Agent Memory (arXiv)](https://arxiv.org/html/2501.13956v1) · [Graphiti](https://github.com/getzep/graphiti) · [Zep: What Is a Temporal Knowledge Graph?](https://www.getzep.com/ai-agents/temporal-knowledge-graph/)
- [MemGPT: Towards LLMs as Operating Systems](https://alphaxiv.org/abs/2310.08560) · [Letta: Sleep-time Compute](https://www.letta.com/blog/sleep-time-compute/)
- [Simon Willison: Claude memory](https://simonwillison.net/2025/Sep/12/claude-memory/) · [Memory implementations across Gemini/OpenAI/Anthropic](https://shibuiyusuke.medium.com/a-deep-comparison-of-memory-implementations-across-gemini-openai-and-anthropic-the-state-of-5b5fc9c1fa6)
- [Anthropic: Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) · [Weaviate: Context Engineering](https://weaviate.io/blog/context-engineering) · [Elastic: Relevance in Context Engineering](https://www.elastic.co/search-labs/blog/context-engineering-relevance-ai-agents-elasticsearch)
