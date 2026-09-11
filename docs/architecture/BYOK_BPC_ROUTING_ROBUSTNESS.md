# BYOK / BPC Routing Robustness — failure taxonomy, prior art, hardening plan

> Status: research + gap analysis (2026-09-11). Sources are cited inline; the
> "what ships today" section reflects `backend/core/llm/` at this commit.
> Companion to `docs/architecture/LEARNING_LLM_ROUTER.md` and
> `CLAUDE.md` §10/§10b.

## 0. Why this exists — the incident that motivated it

Live 2026-09-11, canvas `a1a13834` (Sales Agent turn):

1. BPC ranked `z-ai/glm-5.3-flash` (a reasoning model) top for `task_type=chat`.
2. OpenRouter streamed **zero visible content** with `finish_reason=length` —
   hidden reasoning consumed the whole 6000-token completion cap. Direct
   non-streamed calls to the *same* model returned content fine on a moderate
   prompt, so the provider was healthy; the budget was starved.
3. The provider-fallback loop then retried the **same model id** on `ollama`
   (only two providers are configured) → `404 model not found`.
4. Turn ended `All 2 providers failed`, then (after the fallback gate was
   fixed) `chat streaming exceeded the turn budget (95s)`.

Root shape: **a single ranked model with a single healthy provider has no
model-level fallback, no reasoning-budget policy, and no first-token/inactivity
bound.** Every failure mode below is a variation on that shape.

Landed in the same session (already tested/live): local-runtime fallback gate,
same-provider reasoning-budget retry, planner/evidence budget split, and the
canvas no-edit directive. This document is the general plan.

---

## 1. Failure taxonomy — what "all kinds of scenarios" actually means

| # | Scenario | Symptom | Handling today | Gap |
|---|---|---|---|---|
| 1 | Provider 5xx / network / DNS | request error | provider fallback order + health monitor | — |
| 2 | 429 / rate-limit | HTTP 429 | retry/backoff + provider cooldown | no per-*model* cooldown |
| 3 | First-token stall ("200 then silent") | stream open, no chunks | only the 95s turn budget + SDK read timeout | **no stream inactivity / first-chunk bound** |
| 4 | Reasoning-only empty | `finish_reason=length`, `content=None` | `_EmptyCompletionError` + budget retry | **no reasoning-effort control; retry can exceed the turn budget** |
| 5 | Cross-provider model mismatch | 404 "model not found" | `_provider_serves_model` gate | fixed for local runtimes; provider-catalog knowledge still heuristic |
| 6 | Chosen model's providers all down, other models healthy | `All N providers failed` | none | **no model-level fallback** |
| 7 | Silent model drift (alias resolves elsewhere) | quality/format shift | `model_provenance` detects | drift not fed back into ranking/cooldown |
| 8 | Context-window exceeded | provider 400 | `truncate_to_context` + compression | no explicit `context_window_fallbacks` to a larger-context model |
| 9 | Content moderation / refusal | refusal text | `response_quality` detects refusal | no `content_policy_fallbacks` |
| 10 | Stream dies after partial output | truncated answer | `_tokens_yielded` guard | must never replay (duplicate content) — keep pinned |
| 11 | Turn deadline | client 120s axios | 95s turn budget | no per-provider `stream_timeout`; no SSE keepalive |
| 12 | Structured output invalid | schema error | repair ladders / re-ask | — |
| 13 | Cost blow-up | spend spike | BPC cost-priority + learning router | no `max_price` / latency ceiling |

---

## 2. Prior art (primary sources)

### LiteLLM Router (most widely deployed OSS gateway)

- Reliability primitives are **per-deployment**: router-wide/global `timeout`
  (whole call) and `stream_timeout` (**maximum time to wait for the *first*
  chunk** — "abort hanging providers … and retry another model"), fixed +
  exponential backoff retries, **cooldowns**, and health-check-driven routing.
  ([Router – Load Balancing](https://docs.litellm.ai/docs/routing))
- **Fallbacks are model-group → model-group, tried in order**, with dedicated
  classes for `content_policy_fallbacks`, `context_window_fallbacks`, and a
  generic `fallbacks` for everything else, plus `default_fallbacks`.
  ([Fallbacks (Provider Failover)](https://docs.litellm.ai/docs/proxy/reliability))
- Long silent gaps (extended/adaptive thinking) are handled with
  **`keepalive_seconds`**: SSE comment frames (`: ping`) every N seconds so
  proxies/load balancers don't close an idle connection.
  ([Timeouts](https://docs.litellm.ai/docs/proxy/timeout))
- Routing strategies: `simple-shuffle` (recommended default), latency-based,
  least-busy, rate-limit-aware, lowest-cost.

### OpenRouter (the provider Atom actually uses)

- **Model fallbacks**: pass `models: ["primary", "fallback", …]` (Chat
  Completions) or `fallbacks: [{model}]` (Anthropic Messages, max 3). Triggers
  on context-length errors, moderation flags, rate-limiting and downtime —
  i.e. **error classes, not just HTTP failures**.
  ([Model Fallbacks](https://openrouter.ai/docs/guides/routing/model-fallbacks))
- **Provider selection** per request: `order`, `allow_fallbacks` (default true),
  `require_parameters`, `only`/`ignore`, `sort: price|throughput|latency`,
  `max_price`, and latency/throughput thresholds as **percentiles over a rolling
  5-minute window** (`preferred_max_latency` / `preferred_min_throughput`,
  p50–p99). The default strategy load-balances by price but **excludes providers
  with significant outages in the last 30 seconds**, weighting survivors by
  inverse-square price and keeping the rest as fallbacks.
  ([Provider Routing](https://openrouter.ai/docs/guides/routing/provider-selection))
- **Reasoning controls**: a unified `reasoning` object —
  `{effort: none|minimal|low|medium|high|xhigh|max}` or `{max_tokens: N}`,
  `exclude`, `enabled`. Per-model metadata exposes `supported_efforts`,
  `default_effort`, `mandatory`, `supports_max_tokens`. **"`max_tokens` must be
  strictly higher than the reasoning budget to ensure there are tokens available
  for the final response after thinking."** For Anthropic-style models the
  budget is `max(min(max_tokens * effort_ratio, 128000), 1024)`.
  ([Reasoning Tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens))
- **Zero Completion Insurance**: no charge when a response has zero completion
  tokens and a blank/null finish reason, or an error finish reason — OpenRouter's
  own acknowledgement that "HTTP 200 + zero tokens" is a first-class failure,
  not a success. ([Zero Completion Insurance](https://openrouter.ai/docs/guides/features/zero-completion-insurance))

### Qwen Code — streaming inactivity watchdog (the closest analogue to scenario 3/4)

- A request-level SDK timeout covers **connect + getting the response object**;
  once a 200 stream is open, **inter-chunk inactivity is unbounded**. The
  incident: a gateway accepted the request and streamed nothing for ~595s with
  no `finish_reason`.
- Design: an async-generator wrapper that races each `next()` against an
  idle timer, **resets the timer on every raw chunk (including reasoning
  deltas)**, and on silence aborts the request and raises a **synthetic
  `ETIMEDOUT`** so the existing transport-retry stack handles it. Retry only
  when **zero chunks** were yielded; a stall after partial output surfaces as an
  error and is **never replayed** (would duplicate content).
  ([stream-inactivity-timeout design](https://raw.githubusercontent.com/QwenLM/qwen-code/35d1f1d2dbfb9fa40424da9fee0858aa13478d60/docs/superpowers/specs/2026-06-24-stream-inactivity-timeout-design.md))

### Academic cost/quality routing (secondary)

Cascade/serving-lineup work (FrugalGPT; RouteLLM) establishes routing across a
*ladder of models by cost*, escalating only when the cheap model's answer is
insufficient. Atom's `cost_priority` + learning router is a first-order version
of this; the missing piece is **model-level escalation on failure**, not only
on predicted quality.

---

## 3. What ships today (grounding)

| Capability | Where |
|---|---|
| Provider fallback order + health/cooldown bench | `byok_handler._get_provider_fallback_order`, `_is_provider_available`, `fallback/circuit_breaker.py`, `health_monitor.is_breaker_open` |
| Retry with exponential backoff + jitter | `fallback/retry_policy.py` |
| Cross-provider model eligibility gate | `byok_handler._provider_serves_model` (local runtimes now reject `namespace/model` ids) |
| Empty-visible-content = failed attempt | `_EmptyCompletionError` + `_visible_content_missing` (streaming and non-streaming) |
| Reasoning-model detection | `byok_handler._model_supports_reasoning` (pricing-cache capabilities) |
| Context truncation / compression | `truncate_to_context`, `llm/compression/`, `context/` |
| Model drift detection | `llm/model_provenance.py` |
| Quality probes (truncation/refusal/empty) | `llm/response_quality.py`, learning router (`LEARNING_LLM_ROUTER.md`) |
| Cost/quality ranking (BPC) + cost-priority | `byok_handler.get_optimal_provider` / `get_ranked_providers`, `routing/` |
| Turn budget (95s) + non-streaming fallback | `chat_orchestrator._chat_turn_budget_seconds`, streaming loop |
| Reasoning param — response parsing **and a planning-only disable switch** | `byok_handler._reasoning_from_message`; `_create_kwargs["extra_body"]["reasoning"] = {"enabled": False, "exclude": True}` under `disable_reasoning=True` (tool planner / canvas editor), memoized per `(provider, model)` in `_REASONING_MANDATORY`. **The chat/stream reply path never sets a reasoning budget.** |

---

## 4. Gaps and recommended changes (prioritized)

### P0 — closes the observed failure class

1. **Model-level fallback (scenario 6, and the general escape hatch).**
   Thread the ranked alternatives from `get_ranked_providers` into the
   completion/stream call and, on a *model-level* failure (empty payload,
   length-starvation after the budget retry, drift, moderation, context error),
   try the **next ranked model** — not just the next provider of the same model.
   Two equivalent implementations: emit OpenRouter's `models: [...]` array
   (server-side fallback), or loop the ranked list client-side (works for every
   provider, and keeps one code path). Prefer the client-side loop for
   provider-agnostic behavior; add `models: [...]` as an optimization when the
   provider is OpenRouter.
   *Files*: `core/llm/byok_handler.py` (`generate_response`, `stream_completion`),
   `core/llm_service.py`, `core/llm/routing/`.

2. **Reasoning-budget policy (scenario 4).**
   The planning path already sends the OpenRouter disable switch
   (`extra_body.reasoning = {enabled: False, exclude: True}`,
   `_REASONING_MANDATORY` memo). Extend the **same mechanism** to the chat /
   stream reply path, where no reasoning control exists today: for models where
   `_model_supports_reasoning` is true, send an explicit
   `reasoning.max_tokens` (or `effort: "low"` for `task_type=chat`) and
   guarantee headroom — `max_tokens` must be **strictly greater** than the
   reasoning budget. This is the documented OpenRouter contract and removes the
   starvation that produced the empty stream at 6000 tokens. Keep the existing
   same-provider budget retry as a backstop; it should normally not fire, and
   reuse the memo so a reasoning-mandatory pair is not asked twice.
   *Files*: `byok_handler.stream_completion` + `generate_response` request
   builders, `_model_supports_reasoning`, `_REASONING_MANDATORY`.

3. **Stream inactivity / first-chunk watchdog (scenarios 3, 11).**
   Adopt the Qwen-Code shape: race each `__anext__` against an idle timeout that
   **resets on any chunk, including reasoning deltas**; on silence abort and
   raise a retryable transport error. Retry only when zero chunks were yielded;
   never replay after partial output. This is complementary to the turn budget
   (which bounds the whole turn) and to a per-provider `stream_timeout`
   (time-to-first-chunk, LiteLLM-style).
   *Files*: `byok_handler.stream_completion`.

### P1 — makes routing self-correcting

4. **Per-model cooldown, fed by outcome quality.**
   Bench a (provider, model) pair for a cooldown when it produces empty /
   length-starved / truncated output, using the same breaker machinery as
   connection failures. This stops BPC from re-picking a model that is HTTP-
   healthy but unusable, and it is the deterministic complement to the learning
   router's slower EMA.
   *Files*: `health_monitor`/`fallback/circuit_breaker.py`, `get_ranked_providers`.

5. **Record empty/truncated outcomes into the learning router.**
   Ensure the empty-stream and truncated paths call `_record_outcome_feedback`
   with the real `finish_reason` and `success=False` so the per-model predictors
   learn to down-rank that model for that workload.
   *Files*: `byok_handler` empty/truncated branches, `learning_llm_router`.

6. **Route on measured latency/throughput, not just price.**
   BPC ranks on cost/quality; add rolling p50/p90 latency and throughput as
   ranking terms (OpenRouter exposes both as request preferences; Atom can track
   them from `_record_outcome_feedback` telemetry). Prevents "cheapest model,
   unusable latency" outcomes.
   *Files*: `get_ranked_providers`, `provider_rate_limits.py`.

7. **Keepalive for long reasoning gaps.** *Implemented as a WebSocket
   heartbeat* (Atom streams chat over WS, not SSE): while the provider stream
   is silent but the turn still has budget, emit a `chat_heartbeat` frame so the
   socket/proxy never sees an idle connection. (LiteLLM's `keepalive_seconds`
   is the SSE analogue.)
   *Files*: `integrations/chat_orchestrator.py` streaming loop
   (`_HEARTBEAT_SLICE_SECONDS`).

### P2 — policy knobs and error-class fallbacks

8. **Error-class fallback families** (LiteLLM pattern): `context_window_fallbacks`
   → a larger-context model; `content_policy_fallbacks` → an alternative model.
   Both currently surface as generic failures.
9. **`max_price` and `preferred_max_latency` guards** on BPC candidates so a
   mis-ranked expensive/slow model can't win by default.
10. **Zero-completion accounting**: mark empty responses as non-billable in the
    cost ledger (mirrors OpenRouter's insurance) so routing feedback isn't
    polluted by spend on dead completions.

---

## 5. Test plan (one test per scenario)

| Scenario | Test intent |
|---|---|
| 3 | silent stream (no chunks) trips the watchdog within the idle budget and retries |
| 3 | long *reasoning* deltas keep the watchdog alive (never aborted) |
| 4 | reasoning-only `finish_reason=length` → budget retry; and with a reasoning budget set, the first attempt already yields content |
| 6 | primary model's only provider fails → **next ranked model** serves the turn |
| 7 | drifted resolved model is benched / de-ranked |
| 8 | context-window 400 → next model with a larger window |
| 9 | refusal/moderation → `content_policy` fallback |
| 10 | partial output then failure → **no replay** (no duplicated tokens) |
| 4/5 | local runtime never offered a gateway-namespaced model id (landed) |
| 2 | provider 429 → cooldown honored on the next call |

---

## 6. Recommended sequencing

1. **P0.2 reasoning budget** + **P0.1 model fallback** — together they make the
   ranked ladder actually usable and are the direct fix for the motivating
   incident.
2. **P0.3 watchdog** — removes the 200-then-silent hang class.
3. **P1.4/P1.5** — bench bad models and teach the router.
4. P1.6/P1.7, then P2.

Each item lands shadow-first where it changes routing decisions (mirroring the
repo's stage-router/trust-gateway convention: compute + audit on, enforce
behind a resolver), with a red→green test before the behavior flips, per
`CLAUDE.md` §Decision Standards.

---

## 7. Implemented (2026-09-11)

All P0 + P1 items landed with red→green tests; backend restarted healthy.

| Item | Change | Tests |
|---|---|---|
| P0.2 | `byok_handler._reasoning_request_body` — bounded `reasoning.max_tokens` (cap/3, floor 1024, ceil 8000, always `< max_tokens`) for reasoning models on gateway providers; wired into both `stream_completion` and `generate_response`. New memo `_REASONING_BUDGET_UNSUPPORTED`. | `tests/test_llm_reasoning_budget.py` (3) |
| P0.1 | `stream_completion(fallback_models=…)` recurses to the next ranked model when every provider for the current model fails; `byok_handler.get_fallback_models` exposes the ladder; `LLMService.stream_completion` forwards it; the chat reply path supplies it. | `tests/test_llm_model_fallback.py` (2) |
| P0.3 | `_stream_with_idle_watchdog` + `_StreamInactivityError`; `ATOM_STREAM_IDLE_TIMEOUT_SECONDS` (default 45s, resets on every chunk incl. reasoning); zero-chunk silence fails the attempt, mid-stream silence keeps the partial answer and never replays. | `tests/test_llm_stream_idle_watchdog.py` (2) |
| P1.4 | Per-`(provider, model)` cooldown (`_bench_model` / `_model_cooldown_active`, 120s) set when empty/inactive output survives the budget retry; skipped in the provider loop. | `tests/test_llm_model_cooldown.py` (1) |
| P1.5 | Empty/inactive outcomes now call `_record_outcome_feedback(success=False, finish_reason=…)` so the learning router down-ranks the model (previously only successes were recorded). | same test |
| P1.6 | Provider health/latency score folded into the BPC value score as a bounded multiplier (`health_factor`, 0.5–1.0). | covered by existing BPC suites |
| P1.7 | `chat_heartbeat` WS frame during silent-but-in-budget streaming (`_HEARTBEAT_SLICE_SECONDS = 10s`). | covered by orchestrator suites |

### P2 + grounding (also landed)

| Item | Change | Tests |
|---|---|---|
| P2.1/P2.2 | `_is_context_length_error` / `_is_content_policy_error`; such an error fails on every provider of the model, so the loop skips the rest and jumps to the model-level fallback (LiteLLM's `context_window_fallbacks` / `content_policy_fallbacks` classes). | `tests/test_llm_p2_fallbacks.py` |
| P2.3 | Optional hard price ceiling `ATOM_BPC_MAX_PRICE_PER_MTOK` (default 0 = disabled) filters candidates before scoring. | existing BPC suites |
| P2.4 | Empty/inactive outcomes record `cost=0.0` — zero-completion responses never pollute spend/quality feedback. | `tests/test_llm_model_cooldown.py` |
| Grounding | Canvas context was cut at 4000 chars (head-only), hiding the END of the draft — the agent told the operator the draft had no alternative machine. `_elide_middle(text, 12000)` keeps head + tail with an elision marker. | `tests/test_llm_p2_fallbacks.py` |
| Grounding | `_resolve_canvas_ctx` — when a client sends `canvas_id` but no `canvas_content`, the server loads the draft from the store (`read_canvas`) instead of silently running the turn canvas-blind (the same incident, from the harness/API side). Client snapshot still wins; failures degrade to no context. | `tests/test_canvas_ctx_store_fallback.py` (4) |

### Verification

- New suites: `test_llm_reasoning_budget.py`, `test_llm_model_fallback.py`,
  `test_llm_stream_idle_watchdog.py`, `test_llm_model_cooldown.py`,
  `test_llm_p2_fallbacks.py` — all red→green.
- Provider/orchestrator/canvas regression: **267 passed** on the final sweep
  (the earlier wider sweep's single failure,
  `TestGetQwenResponse::test_overrides_and_sticky_hint_forwarded`, is
  pre-existing on clean `main` per `TESTED_FILES_TRACKER.md`).
- Backend restarted healthy (`scripts/restart_backend.sh`, `:8001` pid 48059).
- Live smoke test (read-only question on the Foot Shear canvas): **HTTP 200 in
  13s**, no error, no `stream-empty` / fallback / budget events — previously
  79–96s failures.
