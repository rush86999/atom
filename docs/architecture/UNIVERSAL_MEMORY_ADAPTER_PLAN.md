# Universal Memory Adapter Plan — swappable memory providers per user preference

**Status:** PROPOSAL — drafted 2026-09-02, not yet approved, no code changed.
**Preceded by:** `docs/architecture/AGENT_MEMORY_UNIFICATION_PLAN.md` (P0–P2 complete —
the native stack this adapter wraps).

---

## 1. Why: the commodity question, answered with evidence

**Memory *operations* are a commodity. Memory *semantics* are not.**

External research (2026-09-02):

- The provider API surface has converged: `add / search / get_all / update / delete`,
  scoped by `user_id` / `agent_id` / `run_id`, is the de facto convention Mem0 popularized.
  Zep ships an official **Mem0→Zep migration guide** mapping operations 1:1
  ([help.getzep.com/mem0-to-zep](https://help.getzep.com/mem0-to-zep)); the Graphlit 2026
  survey notes the same shared surface
  ([graphlit.com survey](https://www.graphlit.com/blog/survey-of-ai-agent-memory-frameworks)).
- The architectures behind that surface are **not interchangeable** — Mem0
  (extract-and-retrieve), Zep/Graphiti (bi-temporal knowledge graph), Letta (agent-owned
  memory blocks), Cognee (ontology pipelines) make different architectural bets
  ([mnemoverse Q3-2026 comparison](https://mnemoverse.com/docs/library/ai-memory-solutions-2026-q3);
  vendor benchmarks like LOCOMO are contested between Mem0 and Zep —
  [digitalapplied comparison](https://digitalapplied.com/blog/open-source-agent-memory-mem0-letta-zep-compared)).
- **No "LiteLLM for memory" exists.** Closest prior art: a vendor-neutral wire-format paper
  with five backend adapters ([arXiv 2606.01138](https://arxiv.org/html/2606.01138));
  LangChain/LangGraph `BaseStore` as a de facto interchange layer; and the community
  recommendation to roll a **thin adapter** rather than a gateway.
- The harness-ownership argument supports owning the interface client-side to avoid lock-in
  ([LangChain, "Your harness, your memory"](https://www.langchain.com/blog/your-harness-your-memory));
  Anthropic's memory tool is a client-side convention with cross-provider import, while
  OpenAI's memory is not API-exposed.

**Conclusion:** an adapter is reasonable *if it is thin and defines Atom's contract* —
not if it promises identical results across backends. Different providers will produce
different (not worse, different) memories; the contract must make capability differences
explicit and eval-gated, and the native stack must remain the default and the reference.

---

## 2. What Atom already has (the case for it being cheap)

From the repo map (2026-09-02):

- A unified native stack already implementing the ideas behind Mem0/Zep/Letta
  (`AGENT_MEMORY_UNIFICATION_PLAN.md` P0–P2): assembler
  (`backend/core/memory_context_assembler.py:850`), mem0-style consolidation
  (`backend/core/memory_consolidator.py`), Zep-style temporal normalization
  (`backend/core/memory/temporal_normalizer.py`), turn-fact store + LanceDB mirror
  (`backend/core/turn_fact_extractor.py`, `turn_fact_vector_store.py`), episodic stack
  (`backend/core/episode_*`), recall eval harness with a CI gate
  (`backend/core/memory_eval.py`, `backend/tests/test_memory_eval_gate.py`, baseline recall 1.0).
- **The read side is a funnel:** `assemble_memory_context()` has exactly **one** production
  caller (`backend/integrations/chat_orchestrator.py:1214`); the ReAct path recalls via
  `WorldModelService.recall_experiences()` (`backend/core/agent_world_model.py:1321`).
- **The write side has ~6 entry points** (chat turn-fact dispatch, two agent extractors,
  episode archival, comms ingestion, explicit `memory_remember`/`memory_forget` tools).
- **Every pattern an adapter needs already exists:** `ServiceFactory`
  (`backend/core/service_factory.py`, keyed by workspace+tenant), typed runtime settings
  (`backend/core/runtime_settings.py`, `experiments.py`, `settings_catalog.py` category
  `C_MEM`), an action registry, a tool registry with governance tiers, and — critically —
  a **provider-selection precedent on the LLM side** (`ProviderRegistry` table +
  `core/learning_llm_router.py` + BYOK). Memory has none of that; it is hardcoded native.
- Friction to respect: ~16.4k LOC memory layer, but fan-in is concentrated; per-table
  embedding-dim coupling (fastembed 384 vs configured 1536) with self-heal logic; the
  `episodes`/`agent_episodes` dual-table split-brain (deliberately deferred, fused at read);
  SQL-side features a hosted provider must replicate or explicitly drop (bi-temporal
  invalidation, sensitivity/epistemic scoping, poison tripwire, governance tiers on
  `memory_forget`); the consolidation worker and eval gate assume native stores.

---

## 3. Design

### 3.1 The contract: `MemoryProvider` protocol

New module `backend/core/memory/provider.py`. One protocol, five operations, matching the
commoditized surface but scoped to Atom's needs:

```python
class MemoryProvider(Protocol):
    def capabilities(self) -> ProviderCapabilities: ...
    # write
    async def ingest_turn(self, ws: WorkspaceScope, turn: TurnRecord) -> None: ...
    async def remember(self, ws: WorkspaceScope, fact: FactRecord,
                       *, source: str = "explicit") -> str: ...
    async def forget(self, ws: WorkspaceScope, fact_id: str) -> None: ...
    # read
    async def recall(self, ws: WorkspaceScope, query: RecallQuery) -> list[MemoryHit]: ...
    # maintenance
    async def consolidate(self, ws: WorkspaceScope) -> ConsolidationReport: ...
```

Non-negotiables carried over from the current tests (the 49 memory test files + eval gate
pin these):

1. **Workspace-scoped** everything (`resolve_user_workspace` semantics preserved).
2. **Never-raise**: providers return empty/partial results on failure; fault isolation and
   per-call timeouts stay in the assembler, not the provider.
3. **Bounded budgets**: char/leg budgets and rerank behavior stay at the assembler layer,
   which renders `RELEVANT MEMORY` regardless of provider.

`ProviderCapabilities` declares what the provider actually implements, with graded support:
`temporal_invalidation`, `knowledge_graph`, `episodic`, `consolidation`, `sensitivity_scoping`,
`governance_forget`, `hybrid_search`. The assembler consults capabilities: a leg whose
signal the provider can't produce is **skipped** (same as today's fault-isolated empty leg),
never silently faked.

### 3.2 Native provider first, behavior-identical

`NativeMemoryProvider` wraps the existing modules (turn-fact extractor, episode services,
graph/knowledge legs, LanceDB mirror). It is a **refactor, not a rewrite**: P0 moves no
logic, it only routes the funnel calls through the factory. The eval gate must stay at
baseline (recall 1.0) with zero flag flips.

### 3.3 Selection: per-workspace preference, mirroring the LLM precedent

- `ServiceFactory.get_memory_provider(workspace_id, tenant_id)` — cached, keyed like the
  other factories.
- Runtime setting `memory.provider` (default `native`), registered in `settings_catalog.py`
  (`C_MEM`) + `runtime_settings.py` (env `MEMORY_PROVIDER` > DB row > default), so both
  per-install env config and per-user preference work. Hosted providers get BYOK keys via
  the existing `byok_handler` pattern.
- Rollout lever copies the proven `ATOM_EXCHANGE_MEMORY = auto|shadow|enforce` ladder:
  - `shadow`: new provider receives writes and answerable reads; assembler still renders
    native results; deltas logged to a comparison table.
  - `enforce`: assembler renders the selected provider's results.

### 3.4 First external adapter: Mem0 (OSS, self-hostable)

Mem0's `add/search/get_all/update/delete` maps ~1:1 onto `ingest_turn/remember/recall/forget`
and its extraction pipeline is the closest semantic match to Atom's turn-fact model
(what `consolidator.py` already reimplements). Zep/Graphiti is the *second* candidate and
only makes sense if a user wants a live temporal KG — that adapter must map onto the graph
legs and is where the `episodes` split-brain decision gets forced, so it is deliberately
not in the first wave.

### 3.5 Portability: export in a neutral format

`memory.export(ws)` / `memory.import_(ws)` in the vendor-neutral operation format from
arXiv 2606.01138 (add/update/delete/search ops, scoping keys) so a preference switch can
backfill a new provider from the durable store instead of starting cold. Backfill reuses
the `MemoryIntegrationMixin` batching pattern. The durable store (SQL + LanceDB) stays
authoritative; external providers are projections, which is what keeps a swap reversible
("stale caches shadowing durable state" rule from AGENTS.md applies directly).

### 3.6 What we are explicitly NOT building

- **No gateway product** ("LiteLLM for memory" as a service) — out of scope; the market
  signal is that no one has made it work because semantics differ.
- **No semantic-equivalence promise.** Each adapter ships with its eval numbers.
- **No per-provider code branches at call sites.** Call sites keep calling the funnel; all
  provider differences live behind the protocol + capabilities.

---

## 4. Phases

| Phase | Scope | Exit criteria |
|---|---|---|
| **P0 — Interface** | `memory/provider.py` protocol + capabilities; `NativeMemoryProvider` wrapping existing modules; `ServiceFactory.get_memory_provider`; `memory.provider` setting + `MEMORY_PROVIDER` env; reroute the 2 read entries (assembler call, `recall_experiences`) and the ~6 write entries through the factory. Native default everywhere. | All ~49 memory test files + eval gate green with zero behavior change; `git diff` shows no logic moved, only routing. |
| **P1 — Shadow mode** | `shadow`/`enforce` ladder; capabilities negotiation in assembler legs (skip unsupported, log); delta logging table. | Shadow run produces comparable recall metrics; unsupported legs degrade visibly in logs, never in prompts. |
| **P2 — Mem0 adapter** | OSS/self-hosted Mem0 adapter (BYOK key + endpoint), backfill via neutral-format import, consolidation mapped to Mem0's update pipeline. | Mem0 passes the same recall@k eval gate on the golden set; deltas documented in this doc; governance tiers enforced at the adapter boundary (forget governed Atom-side regardless of provider). |
| **P3 — Optional: Zep/Graphiti + UI** | Temporal-KG adapter; episodes-table mapping decision resolved; frontend preference control in the existing settings panel; `memory.export`. | Only if a concrete user preference exists; not started by default. |

Estimate: P0 is the small, high-certainty step (protocol + factory + routing; no algorithm
changes). P1–P2 are where the real cost lives (eval certification of an external store).

## 5. Risks and mitigations

- **Silent feature degradation on swap** (bi-temporal, poison tripwire, sensitivity scoping
  are SQL-side and would be lost on a hosted provider) → capabilities grades + shadow
  comparisons + eval gate; governance (`memory_forget` tiers, INTERN/SUPERVISED) enforced
  Atom-side, never delegated.
- **Embedding-dim coupling** (384 fastembed vs 1536 config, self-heal rebuilds) → adapters
  must declare dims per table; Mem0 brings its own embedder, so import maps embeddings, not
  vectors.
- **`episodes`/`agent_episodes` split-brain** → P3 forced-mapping decision documented here
  before any Zep adapter starts.
- **Cost/latency of hosted providers** → route through the existing BPC cost-router
  accounting; providers declare cost class.
- **Concurrency/clobbering** → coordination note logged; P0 touches `service_factory.py`,
  `settings_catalog.py`, `experiments.py`, `memory_context_assembler.py`,
  `agent_world_model.py`, `chat_orchestrator.py` (call sites only) — checked against the
  Active-work table before starting.

## 6. Sources

- Zep Mem0→Zep migration guide: https://help.getzep.com/mem0-to-zep
- Graphlit, "AI Agent Memory Frameworks in 2026": https://www.graphlit.com/blog/survey-of-ai-agent-memory-frameworks
- Mnemoverse, "Mem0 vs Zep vs Letta vs Cognee vs Supermemory (Q3 2026)": https://mnemoverse.com/docs/library/ai-memory-solutions-2026-q3
- Digital Applied, "Open-Source Agent Memory: Mem0 vs Letta vs Zep": https://digitalapplied.com/blog/open-source-agent-memory-mem0-letta-zep-compared
- "A Vendor-Neutral Wire Format for Agent Memory Operations": https://arxiv.org/html/2606.01138
- LangChain, "Your harness, your memory": https://www.langchain.com/blog/your-harness-your-memory
- Vercel AI SDK, "Agents & Memory" (Anthropic memory tool): https://ai-sdk.dev/docs/agents/memory
- Mem0, "Long-Term Memory for AI Agents": https://mem0.ai/blog/long-term-memory-ai-agents
- In-repo: `docs/architecture/AGENT_MEMORY_UNIFICATION_PLAN.md`, `docs/guides/MEMORY_SYSTEMS.md`, `docs/CONTEXT_MEMORY.md`
