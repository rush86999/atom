# Context Memory: Per-Turn Fact Extraction

> **Status:** Implemented (Phase 1-7 + gap-analysis follow-on). Extraction + vector recall default OFF; pre-compress queue ON.
> **Evidence base:** Mem0 / Hermes deep-dive on production context-compression failures.
> **Related code:** `backend/core/turn_fact_extractor.py`, `turn_fact_queue.py`, `turn_fact_vector_store.py`, `turn_fact_categories.py`, `backend/tools/memory_tool.py`

---

## TL;DR

Two architecture gaps from the Discord critique, closed with an **extraction-first** strategy (not compression-first):

1. **Context poisoning** — Atom now has a Hermes-style memory-provider layer: per-turn fact extraction + pre-compression extraction + two-tier recall.
2. **Stack simplification** — LanceDB is *already* embedded in Personal Edition (file-based `./data/lancedb`). The remaining work was gating dead S3/R2 remote paths behind `LANCEDB_CLOUD_ENABLED` and documenting honestly.

We **deliberately do not** build a custom context compressor. Hermes' own compressor has 3 documented production bugs (see below). Provider compaction APIs exist. We build the extraction layer that makes compression less necessary.

---

## Why Extraction-First Beats Compression-First

The naive fix for context poisoning is "build a better compressor." The evidence says don't.

### Hermes Compressor Failure Modes (production)

| Bug | What happens | Why we avoid it |
|---|---|---|
| JSON silent drop | Compressor emits malformed JSON → entire memory batch silently discarded, no log | Our parser returns `None` on hard failure → caller increments a Prometheus-style counter (`turn_fact_extraction_failure{kind="parse_error"}`) and logs the raw output. Never silent. |
| Anti-thrashing permanent lock | A hash seen once is blocked forever, even after the underlying issue resolves | Our `_TTLSet(ttl=300)` self-heals after 5 minutes. Never a permanent lock. |
| Tool-pair crash | Certain tool-call sequences crash the compressor mid-turn, aborting the user response | Extraction runs `asyncio.create_task` (post-turn) or via a queue (pre-compress). User-visible response is already returned. Extraction failure cannot abort the turn. |

### The math

Compression operates on the **already-bloated** context. Extraction operates on a **single turn** (a few KB). Per-turn extraction is cheaper, more reliable, and the extracted facts are reusable across sessions. Compression is lossy and one-shot.

---

## The 5 Durable-Fact Categories (Mem0)

We use Mem0's production taxonomy verbatim — see `backend/core/turn_fact_categories.py`:

| Category | Extracts | Example |
|---|---|---|
| `exact_value` | Numbers, amounts, dates, SLAs, thresholds | "$50K MRR", "7-day SLA", "launch on Mar 14" |
| `hard_constraint` | Non-negotiable rules / prohibitions | "must use Stripe", "no PII to OpenAI" |
| `decision_reason` | WHY a choice was made, with rationale | "chose Postgres for X", "rejected Option B because ..." |
| `cross_task_dep` | Dependencies / blockers between work items | "blocks onboarding v2", "depends on auth service" |
| `implicit_pref` | Revealed user/agent preferences or habits | "prefers terse responses", "wants bullet points" |

The extraction prompt forbids generic paraphrases ("the user said X") and transient state ("currently running"). Each fact must fit exactly one category.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Agent Turn Loop                           │
│                                                                  │
│   execute() entry ──► prefetch_relevant_facts()  [Tier-2, OPT-IN]│
│                          │                                       │
│                          │   FastEmbed embed (10-20ms)           │
│                          │   LanceDB search → hydrate from SQL   │
│                          ▼                                       │
│   ┌──────────────────────────────────────────────────┐           │
│   │  _react_step()                                   │           │
│   │    prompt assembly:                              │           │
│   │      ┌─ TRUSTED BUSINESS FACTS (world model) ─┐  │           │
│   │      ├─ DURABLE FACTS (Tier-1, pure SQL)    ─┤  │           │
│   │      └─ ...                                  ┘  │           │
│   │    LLM call (structured ReAct)                  │           │
│   └──────────────┬─────────────────────────────────┘           │
│                  │                                               │
│   step persisted │                                               │
│                  ▼                                               │
│   ┌──────────────────────────────────────────────────┐           │
│   │  asyncio.create_task(extract_from_turn())        │  ◄── FIRE │
│   │    │  [Phase 3 hook, flag default OFF]           │   AND     │
│   │    │                                             │   FORGET  │
│   │    ├─ regex pre-filter (skip ~40% of turns)      │           │
│   │    ├─ LLM call model="fast", 2s timeout          │           │
│   │    ├─ parse JSON array (5 cats, never silent)    │           │
│   │    ├─ dedup via content_hash (EWMA / supersede)  │           │
│   │    ├─ SQL INSERT (source of truth)               │           │
│   │    └─ LanceDB write (best-effort, never blocks)  │           │
│   └──────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘

                    ─────────  separate path  ─────────

┌─────────────────────────────────────────────────────────────────┐
│               byok_handler (structured gen)                      │
│                                                                  │
│   if len(prompt) > context_window * 3:                           │
│     extraction_queue.enqueue(prompt)   ◄── [Phase 5, default ON] │
│     prompt = truncate_to_context(prompt)                         │
│                                                                  │
│   ExtractionQueue worker (background):                           │
│     extract_from_prompt_before_truncation()                      │
│       → same _extract core as extract_from_turn                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Two-Tier Retrieval

### Tier 1 — Pure SQL (default ON, always)

`get_active_facts_for_prompt()` runs a single indexed query on `(workspace_id, status, created_at)`. Latency budget:

| Store | P50 | P99 |
|---|---|---|
| SQLite (Personal) | ~1ms | ~3ms |
| PostgreSQL (prod) | <1ms | ~2ms |

Injects a `DURABLE FACTS (survive compression):` block into the assembled prompt. Up to 5 facts, most-recent-first. Fits the `<50ms agent resolution` target.

### Tier 2 — LanceDB semantic recall (opt-in)

`prefetch_relevant_facts()` is called **once** at `execute()` entry (not per `_react_step` — avoids N× embedding cost). Embeds the query, searches the LanceDB `turn_facts` table, hydrates from SQL via `vector_id`. Skipped for trivial queries ("hi", "thanks"). Gated by `TURN_FACT_VECTOR_RECALL_ENABLED`.

---

## Cost & Latency Budget

| Operation | When | Cost | Latency |
|---|---|---|---|
| Regex pre-filter | Every turn (extraction path) | Free | <0.1ms |
| LLM extraction call | Post-turn, flag ON | 1× `fast` model call (~$0.0001) | 500ms-2s (async, non-blocking) |
| Pre-compress enqueue | On truncation only | Free (queue + worker) | <1ms |
| Tier-1 SQL recall | Every prompt assembly | Free | 1-3ms |
| Tier-2 vector recall | Once per execute(), opt-in | 1× FastEmbed embed | 10-20ms |

**Cost controls:**
- `TURN_FACT_EXTRACTION_SAMPLE_RATE` (0.0–1.0) — dial down under cost pressure
- `TURN_FACT_MAX_PER_TURN=5` — hard cap per turn
- `model="fast"` always (haiku/4o-mini/flash) — extraction is classification, not reasoning
- Pre-filter skips ~40% of turns before any LLM call

---

## Dedup Contract

`content_hash = sha256(workspace_id + "::" + normalize(fact_text))`

Normalization: lowercase, strip, collapse whitespace, drop punctuation. So "Must use Stripe!" and "must use stripe" collide.

On hash collision (existing active row):
- **New confidence beats existing by >0.1** → mark existing `superseded` (keep for audit), insert new active row
- **Otherwise** → EWMA-blend confidence (`alpha=0.3`), touch `created_at` so it stays fresh for recency-based retrieval

**Never silently drop.** Anti-thrashing via `_TTLSet(ttl=300)` — self-heals after 5 min, never a permanent lock (the Hermes bug).

Postgres enforces "at most one active row per (workspace, hash)" via a **partial unique index**. SQLite enforces this in the application layer.

---

## Failure Modes → Mitigations

| Failure | Mitigation |
|---|---|
| JSON parse failure | Returns `None` → caller increments `parse_error` counter + logs raw output (truncated to 400 chars) |
| LLM call raises | `except Exception` → returns `[]`, increments `llm_error` counter |
| LLM call >2s | `asyncio.wait_for` → `TimeoutError` caught, increments `timeout` counter |
| LanceDB corruption | SQL row written first; LanceDB write is best-effort + swallowed |
| Queue full | Drop + increment `dropped` counter, never blocks the response |
| STUDENT agent | Maturity gate: skip extraction entirely (read-only) |
| Cost runaway | Regex pre-filter + sample rate + `MAX_PER_TURN=5` + `model="fast"` |

Every public method catches all exceptions and returns `[]`. Failures are best-effort, never user-visible. This is **graceful degradation** per CLAUDE.md concept #4.

---

## Embedded Stack (Personal Edition)

LanceDB runs **embedded** — file-based `./data/lancedb` (or `./data/atom_memory` for the memory handler). No server container. This was already true; Phase 7 just gates the dead S3/R2 codepaths behind `LANCEDB_CLOUD_ENABLED=false` so Personal Edition stops evaluating them.

| Edition | Relational | Vector | Cache |
|---|---|---|---|
| Personal | SQLite (file) | LanceDB (embedded file) | Optional (single-process) |
| SaaS | PostgreSQL | LanceDB on S3/R2 (`LANCEDB_CLOUD_ENABLED=true`) | Redis/Valkey |

Postgres and Redis/Valkey support is retained for production parity and WebSocket pub-sub respectively — **not** removed (evidence ambiguous; separate decision).

---

## Feature Flags

| Flag | Default | Rationale |
|---|---|---|
| `TURN_FACT_EXTRACTION_ENABLED` | `false` | Costs 1 LLM call/turn; opt-in until telemetry validates |
| `TURN_FACT_PRE_COMPRESS_ENABLED` | `true` | Free (queue + worker); strictly additive |
| `TURN_FACT_VECTOR_RECALL_ENABLED` | `false` | Adds embedding latency; opt-in |
| `LANCEDB_CLOUD_ENABLED` | `false` | Personal = embedded; SaaS flips to true |
| `TURN_FACT_MAX_PER_TURN` | `5` | Hard cap per turn |
| `TURN_FACT_EXTRACTION_SAMPLE_RATE` | `1.0` | Dial down in cost crunch |
| `TURN_FACT_QUEUE_MAXSIZE` | `100` | Queue capacity (overflow drops, never blocks) |

---

## Verification

See `backend/tests/test_turn_fact_extraction.py` (60 tests incl. circuit breaker), `test_turn_fact_queue.py` (8 tests), `test_memory_tools.py` (15 tests), `test_reasoning_fts.py` (11 tests), `test_context_compression.py` (13 tests). All green.

Covers: schema + unique constraint, regex pre-filter (positive + negative), hash normalization, JSON parse robustness (clean/wrapped/dirty/garbage), extract core (happy path / pre-filter skip / invalid category / cap / empty / parse failure), all dedup branches (EWMA bump / supersede), maturity gate, sample rate, every failure mode (LLM raises / timeout / LanceDB failure / pre-compress entrypoint), TTLSet eviction, Tier-1 retrieval (ordering / category filter / empty / failure), Tier-2 recall (flag off / trivial / short / happy / LanceDB failure), cloud-gate flag default, circuit breaker (trip / skip / half-open probe / close-on-success), agent memory tools (remember / forget / deletion safety), FTS5 lexical search (happy path / exact-match / special chars / graceful degradation), boundary-protection truncation (head + tail preserved), tool-pair sanitization (orphan stub injection / trailing-call drop).

---

## Gap-Analysis Follow-On (Hermes comparison)

After the initial extraction layer, a structured gap analysis against the Hermes agent surfaced 5 follow-on improvements. All 5 are now implemented:

| # | Feature | What it does | File |
|---|---|---|---|
| 1 | **Agent-callable memory tools** | `memory_remember` (INTERN+) and `memory_forget` (SUPERVISED+) let the agent explicitly persist or invalidate a durable fact mid-turn. Backed by `remember_fact_explicit` / `forget_fact_explicit`. Deletion safety: refuses to forget without a specific target. | `tools/memory_tool.py` |
| 2 | **`on_session_end` hook** | Final extraction pass over the full turn digest when the ReAct loop completes — catches facts only visible once the final answer is composed. Fire-and-forget. | `atom_meta_agent.py` (post-loop) |
| 3 | **Circuit breaker** | After N consecutive failures (default 5), extraction is skipped for a cooldown (default 120s). Closed → Open → Half-open (one probe) → Closed. Prevents extraction storms during provider outages. Mirrors Hermes' Mem0-provider 2-min/5-failure pattern. | `turn_fact_extractor.py:_CircuitBreaker` |
| 4 | **FTS5 lexical session search** | SQLite FTS5 virtual table over `agent_reasoning_steps` (thought + observation) with auto-sync triggers. Fast exact-match fallback for error strings / IDs / function names — the queries where semantic recall misses. Postgres equivalent: tsvector + GIN index. | `search_reasoning_steps_lexical()`, migration `20260624_reasoning_fts` |
| 5 | **Context compression (deterministic only)** | `truncate_to_context` rewritten from naive head-chop to **boundary protection** (preserve head + tail, drop stale middle — tail gets 60% share). Plus `sanitize_tool_pairs()` for the message-array path (inject stub `assistant.tool_calls` before orphaned `tool` results → prevents OpenAI 400). **No LLM-summary phase** — Hermes' own has 3 documented production bugs; provider compaction APIs are the right place for lossy summarization. | `byok_handler.py` |

---

## Reddit-Critique Follow-On (outcome prefilter + verified contract)

Two further gaps surfaced from a Reddit review of the extraction layer:

### Outcome prefilter (cosine can't separate pass from fail)

**Problem:** Episodes were embedded as title + description + summary + topics — no outcome. A snapshot that succeeded and one that failed are near-identical text, so they land almost on top of each other in vector space. The exact signal self-correction depends on ("did this state fail before?") is what cosine similarity is worst at separating.

**Fix:** Push `outcome` into LanceDB metadata and prefilter on it BEFORE the vector search (LanceDB does this natively). Specifically:
- `EpisodeSegmentationService._derive_outcome()` computes `success` | `failure` | `partial` | `unknown` from execution statuses
- The outcome is stored in the LanceDB metadata dict at index time
- `EpisodeRetrievalService.retrieve_semantic(outcome=...)` builds a native `WHERE outcome == '...'` prefilter (zero added latency)
- `retrieve_failed_similar()` is the self-correction entrypoint — prefilters failures, then ranks within them by similarity

This is the standard hybrid-retrieval pattern: structured discriminator as prefilter, similarity as ranker.

### Verified-outcome contract (silent no-op defense)

**Problem:** Tool returns were stringified and recorded as observations with no verification. Tools self-report `{"success": True}` when they don't throw. Graduation incremented success counters on the self-reported bool — and one call site even hardcoded `success=True` regardless of the return. A silent no-op (tool does nothing, returns success) would propagate as a learned success and inflate capability stats. "State blindness one layer up."

**Fix — tri-state verified flag:**
- `core/tool_outcome_verifier.py` parses tool returns into a `VerifiedOutcome(kind, success, evidence)`:
  - `verified` — tool actively confirmed the world changed (returned evidence)
  - `unverified` (default) — tool self-reported success without evidence
  - `failed_verification` — an explicit verify() step rejected the result
- Parsed at the ReAct loop observation site and persisted on `AgentReasoningStep.verified` + `verification_evidence`
- `CapabilityGraduationService.record_usage` now gates on `verified='verified'` — only verified successes increment the graduation counter. Unverified successes still count in the denominator (they *lower* the success ratio), so silent no-ops cannot inflate capability stats.
- Backward-compatible: existing tools returning a plain string or `{success: true}` without a `verified` key default to `unverified` — no contract break, they just stop being able to graduate capabilities alone.

Also fixed a pre-existing bug surfaced by this work: `CapabilityGraduationService` referenced `agent.properties` which doesn't exist on `AgentRegistry` — it now uses the real `configuration` JSON column with `flag_modified`.

---

## Out of Scope (deferred)

- Building a custom context compressor (evidence says don't)
- Removing Postgres or Redis/Valkey (evidence ambiguous)
- Backfilling facts from historical `EpisodeSegment` rows (expensive, low-value)
- `MemoryProvider` ABC abstraction (premature until a second backend like Mem0 cloud is added)

---

## Related Layer: Pre-Action Match-Confidence

This document covers the **post-action** side (facts extracted *after* a tool
runs, outcomes verified *after* execution). Atom now has a **pre-action**
mirror for browser automation:

- **[MATCH_CONFIDENCE.md](MATCH_CONFIDENCE.md)** — selector-resolution
  certainty scored BEFORE `browser_click` runs. Same tri-state shape as
  `VerifiedOutcome`: `high / partial / ambiguous` ↔ `verified / unverified /
  failed_verification`. When certainty is low, the action routes through
  `ProposalService` before executing — including for AUTONOMOUS-tier agents
  (whose tier is otherwise routed by historical clean executions, not
  current-call certainty).
- **[SELECTOR_CONFIDENCE_THRESHOLDS.md](SELECTOR_CONFIDENCE_THRESHOLDS.md)**
  — tuning one-pager.

The bookends framing is documented in
[HERMES_COMPARISON.md § Pre-action vs. post-action](HERMES_COMPARISON.md).
