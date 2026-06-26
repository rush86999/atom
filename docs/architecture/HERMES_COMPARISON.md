# Atom vs. Hermes Agent — Architecture Comparison

> **Purpose:** Honest, evidence-based comparison to guide feature decisions and onboard contributors. Not a marketing document — both systems have real strengths and real gaps.
> **Last reviewed:** June 24, 2026
> **Sources:** [Mem0 blog](https://mem0.ai/blog/how-hermes-and-claude-handle-context-compression-in-real-production-agents-(and-what-you-should-extract)), [LanceDB blog](https://www.lancedb.com/blog/semantic-memory-for-hermes-agent-with-lancedb), [Hermes official docs](https://hermes-agent.nousresearch.com/docs/developer-guide/architecture), [Hermes repo](https://github.com/NousResearch/hermes-agent)
> **Related:** [Context Memory design](CONTEXT_MEMORY.md)

---

## Subjects

| | Atom | Hermes Agent |
|---|---|---|
| **What** | AI-powered business automation platform (multi-agent, governance, canvas) | Open-source self-hosted personal AI agent (Nous Research) |
| **Repo** | `rush86999/atom` | `NousResearch/hermes-agent` |
| **Model** | Multi-provider (OpenAI, Anthropic, DeepSeek, Gemini, MiniMax, Ollama, …) | Any OpenAI-compatible endpoint |
| **Deployment** | Single-tenant (Personal / SaaS) | Single-user self-hosted |
| **Orientation** | Business workflows, integrations, regulated actions | Personal coding/productivity assistant |

These are **different products** — Atom is a multi-tenant business platform; Hermes is a personal agent. Comparisons are most useful where they overlap: memory, context management, reasoning, and production resilience.

---

## At-a-glance capability matrix

Legend: ✅ strong · ◐ partial / opt-in · ❌ absent · ➖ not applicable (out of scope for the product)

| Dimension | Atom | Hermes | Notes |
|---|:---:|:---:|---|
| **Per-turn fact extraction** | ◐ | ✅ | Atom implemented (`turn_fact_extractor.py`); Hermes is the reference design. Atom defaults OFF. |
| **Pre-compression extraction** | ✅ | ✅ | Both have `on_pre_compress` hooks. |
| **Memory-provider ABC** | ❌ | ✅ | Hermes formalizes the interface; Atom hardcodes SQL+LanceDB backend. Deferred as premature. |
| **Agent-callable memory tools** | ✅ | ✅ | `memory_remember` / `memory_forget` (Atom) vs `lancedb_remember` / `mem0_*` (Hermes). |
| **Context compression** | ◐ | ◐ | Both partial. Hermes has an LLM-summary phase (3 documented bugs); Atom has boundary-protection + tool-pair sanitization only (no LLM summary, deliberately). |
| **FTS5 lexical search** | ✅ | ✅ | Both have SQLite FTS5 session search. |
| **Hybrid retrieval + reranker** | ❌ | ✅ | Hermes has BM25+vector fusion + cross-encoder reranker. Atom is pure vector (deferred — modest benchmark gain). |
| **Outcome prefilter (pass/fail)** | ✅ | ❌ | Atom prefilters `WHERE outcome='failure'` BEFORE vector search (native LanceDB). Hermes relies on cosine, which can't separate near-identical success/fail snapshots. |
| **Outcome verification** | ✅ | ❌ | Atom: tri-state `verified` flag; graduation gates on evidence. Hermes trusts tool self-report. |
| **Tier-1 SQL recall** | ✅ | ➖ | Atom injects `DURABLE FACTS` prompt block. Hermes uses curated markdown instead. |
| **Circuit breaker (memory)** | ✅ | ✅ | Both: trip after N failures, cooldown. Atom half-open probes; Hermes fixed window. |
| **Maturity / governance** | ✅ | ❌ | Atom: STUDENT→INTERN→SUPERVISED→AUTONOMOUS with action gating. Hermes has none. |
| **HITL supervision** | ✅ | ❌ | Atom has real-time supervision sessions. |
| **Multi-agent orchestration** | ✅ | ❌ | Atom: Queen + Fleet Admiral + spawnable specialists. Hermes is single-loop. |
| **Canvas / rich presentations** | ✅ | ❌ | 7 canvas types, WebSocket, a11y. Hermes is terminal + messaging. |
| **Cognitive-tier cost routing** | ✅ | ◐ | Atom 5-tier routing. Hermes has aux-model only. |
| **Production observability** | ✅ | ❌ | Prometheus, `/health/*`, structlog. Hermes has WARNING logs. |
| **Browser / device automation** | ✅ | ❌ | Playwright + device capabilities. |
| **Procedural skill authoring** | ◐ | ✅ | Hermes writes/refines skills from experience. Atom has graduation + marketplace but skills are dev-authored. |
| **BYOK + OAuth mgmt** | ✅ | ◐ | Atom: encrypted multi-provider credentials. Hermes: "your model of choice." |
| **Reflection / self-correction** | ❌ | ❌ | Neither documents it. |
| **Parallel tool calls** | ❌ | ❌ | Neither documents it. |
| **Sleep-like offline consolidation** | ◐ | ◐ | Atom has episode decay/similarity consolidation. Hermes has LanceDB background compaction. Neither has a true forgetting curve. |

---

## Memory architecture — detailed

### Hermes (the reference design)

Hermes treats memory as a **first-class plugin contract**. A `MemoryProvider` ABC defines 7 hooks:

- `sync_turn(user, assistant)` — persist after every turn (background daemon thread, non-blocking)
- `on_pre_compress(messages)` — last-chance extraction before lossy compression
- `prefetch(query)` — recall before each API call (Mem0 returns cached previous-turn results instantly, searches next-turn in background)
- `system_prompt_block()` — inject a static "you have memory tools" block
- `get_tool_schemas()` / `handle_tool_call()` — expose agent-callable tools (`lancedb_remember/recall/read/forget`)
- `on_session_end(messages)` — final flush

Three coexisting memory modalities by default:
1. **Curated markdown** — `MEMORY.md` (facts, ~800 tokens) + `USER.md` (preferences, ~500 tokens), frozen into the system prompt at session start
2. **SQLite FTS5** — raw conversation history, lexical search
3. **Pluggable semantic provider** — Mem0 (managed) or LanceDB (embedded local)

### Atom (the implementation)

Atom implemented the **hooks** without the **ABC**. The extraction layer lives in `turn_fact_extractor.py`:

- `extract_from_turn()` — the `sync_turn` hook (fire-and-forget `asyncio.create_task`)
- `extract_from_prompt_before_truncation()` — the `on_pre_compress` hook (drained by `ExtractionQueue`)
- `prefetch_relevant_facts()` — Tier-2 recall (opt-in)
- `extract_from_turn(...)` called again at ReAct loop end — the `on_session_end` hook
- `memory_remember` / `memory_forget` tools — the `get_tool_schemas` / `handle_tool_call` equivalent

Recall is two-tier:
- **Tier-1** — pure SQL `DURABLE FACTS` prompt block (`get_active_facts_for_prompt`, sub-ms, always on)
- **Tier-2** — LanceDB semantic `prefetch_relevant_facts` (opt-in, 10-20ms embed)

The SQL row (`turn_facts` table) is the source of truth; LanceDB vectors are best-effort. This is the inverse of Hermes, where the vector store is primary and markdown is a frozen supplement.

### Why Atom didn't build the ABC

A formal `MemoryProvider` interface is only worth its cost when there are **multiple backends** to swap between. Atom has one (SQL + embedded LanceDB). Extracting the ABC prematurely would freeze an interface before a second implementation validates it. The hooks are the stable surface; the ABC is deferred. See [Out of Scope](#out-of-scope-deliberately-deferred) below.

---

## Context compression — detailed

### Hermes' 4-phase compressor (`agent/context_compressor.py`)

1. **Prune tool results** — replace old verbose tool outputs (>200 chars) with a placeholder (deterministic, no LLM)
2. **Boundaries** — protect first N messages + recent tail; `_align_boundary_backward()` keeps tool-call/result pairs together
3. **Structured summary** — middle goes to an aux LLM; on subsequent passes the previous summary is passed and the model *updates* it rather than regenerating
4. **Reassemble** — head + summary + tail; `_sanitize_tool_pairs()` injects stubs for orphaned tool results

Fires at **50%** of context (agent loop) and **85%** (gateway session hygiene) — deliberately offset.

**Three documented production bugs:**
1. **Silent summary drop** — `_generate_summary()` doesn't handle `json.JSONDecodeError`; a non-JSON response (rate-limit HTML) causes the middle to be dropped *without* a summary, only a WARNING log
2. **Tool-ordering crash** — if the tail's first message is `tool` role without preceding `assistant.tool_calls`, every OpenAI-compatible provider returns HTTP 400
3. **Anti-thrashing permanent lock** — `should_compress()` returns `False` permanently after two low-savings compressions; no timeout/decay until the user runs `/new`

### Atom's approach

Atom ported **only the deterministic phases** (no LLM summary):

- **Boundary protection** — `truncate_to_context` rewritten from a naive head-chop (which lost the tail — the worst possible direction) to head+tail preservation (head 40%, tail 60%, drop stale middle)
- **Tool-pair sanitization** — `sanitize_tool_pairs()` injects stub `assistant.tool_calls` before orphaned `tool` results (Hermes' Phase-4 mitigation, minus the bug)

**Deliberately not built:** the LLM-summary phase. The evidence says Hermes' own is broken; provider compaction APIs (Anthropic compaction, Gemini context) are the correct place for lossy summarization. Atom sits beneath them as the deterministic safety net.

The extraction layer we built makes the missing summary phase **less costly** — durable facts survive compression because they're already extracted to the `turn_facts` table before truncation fires.

---

## Where Atom is stronger

These are capabilities Hermes lacks or doesn't document — **not gaps to close, strengths to preserve**:

1. **Governance & maturity levels** — 4-tier (STUDENT→INTERN→SUPERVISED→AUTONOMOUS) with action-complexity gating (1=LOW read-only through 4=CRITICAL autonomous-only). Every AI action attributable, governable, auditable. Sub-ms cached checks. Hermes has no equivalent.
2. **HITL supervision** — real-time supervision sessions with intervention + outcome tracking. Essential for regulated business actions.
3. **Canvas presentations** — 7 canvas types (sheets, docs, email, orchestration, terminal, coding, generic) with WebSocket streaming and a11y trees. Hermes is terminal + messaging.
4. **Multi-agent fleet** — Queen Agent (blueprint generation) + Fleet Admiral (specialist recruitment) + spawnable specialty agents (finance, sales, ops, …). Hermes is a single `AIAgent` loop.
5. **Cognitive-tier cost routing** — 5-tier query classification → model selection, ~90% cost reduction via caching + routing. Hermes has aux-model configurability only.
6. **Production observability** — Prometheus metrics, `/health/{live,ready,metrics}`, structlog. Hermes documents only WARNING logs.
7. **Browser/device automation** — Playwright CDP + device capabilities (camera, screen, location), all maturity-gated.
8. **Marketplace + supply-chain security** — community skills, pip-audit+Safety scanning, per-skill Docker. Hermes has plugin install only.

---

## Where Hermes is stronger

1. **Memory-provider formalism** — the 7-hook ABC is a clean, documented contract. Atom has the hooks but no ABC (deferred).
2. **Curated markdown notes** — `MEMORY.md` / `USER.md` frozen into the system prompt is a cheap, token-efficient way to carry durable context. Atom's SQL-fetched `DURABLE FACTS` block is fresher but costs a query per turn.
3. **Rolling summary update** — passing the previous summary and asking the LLM to update (vs. regenerate) is better than single-pass over long sessions. Atom has nothing here (deferred — see compression above).
4. **Hybrid retrieval + cross-encoder reranker** — BM25+vector fusion with RRF/linear + 17M-param reranker. LongMemEval benchmark: 0.68 acc (hybrid+reranker) vs 0.66 (pure vector). Atom is pure vector.
5. **Zero-latency prefetch** — Mem0 injects previous-turn cached results instantly while next-turn search runs in background. Atom's prefetch is synchronous (10-20ms).
6. **Procedural skill authoring** — Hermes writes/refines skills from experience (Voyager-style). Atom's skills are developer-authored (graduation + marketplace, not agent-authored).

---

## Where both are weak

Opportunities — but not Hermes-derived, so not tracked as gaps:

- **Reflection / self-correction** — neither documents a critique/backtracking phase in the reasoning loop. Atom's episodic outcome-prefilter (retrieve past failures similar to the current state) is a building block, not a full self-correction loop.
- **Parallel tool calls** — both are sequential
- **Tool-result caching** — neither has it
- **Sleep-like offline consolidation** — both have approximate versions (episode decay / LanceDB compaction); neither has a true forgetting curve
- **Distributed tracing** — Atom has structured logs + Prometheus; no OpenTelemetry. Hermes has neither.
- **Full state-diff verification** — Atom's verified-outcome contract distinguishes "tool said success" from "tool proved success via evidence" and gates graduation on the latter, but it does not yet snapshot world state before/after an action to compute a real diff. That's the "full" tier described in [Context Memory](CONTEXT_MEMORY.md) — deferred until the minimum-viable contract proves its value.

---

## Out of scope (deliberately deferred)

These were considered and **explicitly not built**, with the reasoning recorded so future contributors don't relitigate without new evidence:

| Deferred item | Reason |
|---|---|
| **Custom LLM-summary compressor** | Hermes' own has 3 documented production bugs (JSON silent drop, tool-pair 400, anti-thrashing permanent lock). Provider compaction APIs exist and are the correct abstraction. |
| **`MemoryProvider` ABC** | Premature without a second backend (Mem0 cloud, Pinecone, etc.). The hooks are the stable surface; extract the ABC when a second implementation validates the contract. |
| **Hybrid BM25 + cross-encoder reranker** | Modest benchmark gain (+2pts acc on LongMemEval) for a 17M-param model dependency. Defer unless retrieval quality becomes a measured problem. |
| **Backfilling facts from historical `EpisodeSegment` rows** | Expensive, low-value. Extraction starts fresh from the next turn. |
| **Removing Postgres / Redis-Valkey** | Evidence ambiguous. Postgres retained for prod parity; Redis for WebSocket pub-sub. Separate decision. |

---

## Decision log (what Atom did and why)

A condensed record of the architectural choices, for contributors:

1. **Extraction-first, not compression-first.** Per-turn extraction (cheap, reliable, reusable) over a custom compressor (lossy, buggy, one-shot). The extraction layer makes compression less necessary.
2. **SQL is the source of truth; vectors are best-effort.** A `turn_facts` SQL row is always queryable even if LanceDB is corrupted/unavailable. The vector store is an acceleration layer, not the system of record.
3. **`model="fast"` always for extraction.** Extraction is classification, not reasoning. Haiku/4o-mini/flash, 2s timeout. Never `quality`.
4. **Never raise, never silently drop.** Every public method catches all exceptions and returns `[]`. Parse failures increment a counter + log raw output (not a silent JSON drop). Dedup never drops — it EWMA-bumps or supersedes.
5. **Anti-thrashing is a TTL cache, not a permanent lock.** Self-heals after 5 minutes. (Hermes bug #3 avoided.)
6. **Maturity-gated.** STUDENT agents are read-only — they don't learn from untrusted input. `>= INTERN` required for extraction.
7. **Boundary protection, not summarization.** The deterministic compressor phases are ported; the LLM-summary phase is not (provider compaction APIs instead).
8. **Deletion safety.** `memory_forget` refuses without a specific target (mirrors Hermes' `lancedb_forget`). No workspace-wide wipes on vague requests.

---

## Benchmark evidence (where available)

Hermes publishes LongMemEval-S results (60-case stratified subset):

| Retrieval mode | Accuracy | Recall@5 |
|---|---|---|
| FTS5 (`hermes-session-search`) | 0.53 | 0.66 |
| LanceDB pure vector | 0.66 | 0.80 |
| LanceDB hybrid + cross-encoder | 0.68 | 0.75 |
| LanceDB hybrid + RRF | 0.61 | — (worse than pure vector) |

Atom does not publish equivalent benchmarks yet. The FTS5 + Tier-1 SQL + Tier-2 vector stack maps to Hermes' first three rows; the reranker (row 3) is deferred.

---

## When to choose which

This section is intentionally blunt.

**Choose Hermes if:** you want a single-user, self-hosted, terminal-first personal coding assistant with mature memory plugins and you're willing to operate it (no governance, no HITL, no observability built in).

**Choose Atom if:** you need multi-tenant business automation with governed agents (maturity levels, HITL supervision, audit trails), rich canvas presentations, multi-agent orchestration, browser/device automation, production observability, or cost-routed multi-provider LLM.

**Neither is a good fit if:** you need reflection/self-correction in the reasoning loop, parallel tool execution, distributed tracing, or sleep-like offline memory consolidation — both are weak here.

---

*This document is a living reference. Update it when either system ships a material change to the compared dimensions, and re-derive the "Out of scope" decisions against new evidence.*
