# OpenCode Go Provider — Low-Cost LLM Gateway

> **Provider ID**: `opencode-go`  
> **Gateway**: https://opencode.ai/zen/v1  
> **Auth**: `OPENCODE_API_KEY` (not `OPENCODE-GO_API_KEY` — hyphen in env name doesn't work)  
> **Tier**: Budget + Code  
> **Default models**: DeepSeek V4 Flash/Pro, Kimi K2.7 Code  
> **Cost reduction**: ~90% vs direct provider APIs via subscription model  

---

## Quick Start

```bash
# 1. Get your API key from https://opencode.ai
# 2. Add to backend/.env
OPENCODE_API_KEY=sk-opencode-...

# 3. Optional: override defaults for your subscription tier
OPENCODE_RPM=60                 # requests/minute ceiling
OPENCODE_TPM=2000000            # tokens/minute ceiling
OPENCODE_MAX_CONTEXT=200000     # gateway context cap (clamps candidate models)
OPENCODE_MONTHLY_TPM=           # opt-in monthly subscription allowance (hard-skip when exhausted)
OPENCODE_MODEL_LIMITS=          # per-model quota weights + RPM/TPM (JSON, see below)

# 4. Restart backend
```

The provider auto-registers when `OPENCODE_API_KEY` is set. No code changes needed.

---

## How It Works

### Architecture

```
Your App → Atom BYOK Router → OpenCode Zen Gateway (opencode.ai/zen/v1) → Provider Models
                                    ↑
                              Subscription billing
                              (not per-token)
```

### Routing Integration

OpenCode Go participates in Atom's **BPC (Best Provider Candidate)** ranking alongside OpenAI, Anthropic, DeepSeek, etc. The router considers:

| Factor | How OpenCode Go Is Scored |
|--------|---------------------------|
| **Cost** | Subscription = effectively $0/marginal-token → highest cost score |
| **Latency** | Measured per-request; fed into value score |
| **Health** | Circuit breaker + 4xx/5xx tracking |
| **Rate headroom** | Custom RPM/TPM limits → headroom penalty when near ceiling |
| **Per-model quota** | Weighted TPM + quota penalty — heavy models (kimi-k3, pro) burn the shared budget faster and lose ties at equal quality |
| **Per-model limits** | Models with their own RPM/TPM are hard-skipped independently |
| **Monthly cap** | `OPENCODE_MONTHLY_TPM` hard-skips provider once the month's allowance is consumed |
| **Context clamp** | `OPENCODE_MAX_CONTEXT` clamps model context windows |
| **Exhaustion** | Hard-skip when rate budget = 0 |

### Model Mapping (Static Fallback)

When the dynamic pricing cache is unavailable, the router uses built-in mappings:

| Complexity | Model | Use Case |
|------------|-------|----------|
| SIMPLE | `deepseek-v4-flash` | Chat, classification, extraction |
| MODERATE | `deepseek-v4-flash` | Summarization, rewriting |
| COMPLEX | `deepseek-v4-pro` | Reasoning, multi-step tasks |
| ADVANCED | `kimi-k2.7-code` | Code generation, debugging |

> **Note**: These are the *gateway model IDs*. The actual upstream model may differ — OpenCode Zen handles the mapping.

---

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENCODE_API_KEY` | *to use this provider* | Subscription key from opencode.ai (format: `sk-opencode-...`) |
| `OPENCODE_BASE_URL` | `https://opencode.ai/zen/v1` | Gateway endpoint (rarely needs changing) |
| `OPENCODE_RPM` | `60` | Max requests/minute for your tier. Adjust to match your plan. |
| `OPENCODE_TPM` | `2000000` | Max tokens/minute for your tier. |
| `OPENCODE_MAX_CONTEXT` | `200000` | Max context tokens the gateway accepts. Clamps candidate models. |
| `OPENCODE_MONTHLY_TPM` | *unset* | **Opt-in** monthly subscription allowance (tokens). When set, BPC hard-skips the provider once persisted usage for the current calendar month meets/exceeds it. Unset = no monthly gate. |
| `OPENCODE_MODEL_LIMITS` | *unset* | **Per-model** quota weights + RPM/TPM overrides as JSON (see below). |

### Setting Limits to Match Your Plan

Check your OpenCode subscription for actual limits, then set:

```bash
# Example: Pro tier with higher limits
OPENCODE_RPM=120
OPENCODE_TPM=5000000
OPENCODE_MAX_CONTEXT=200000
```

**Why this matters**: The router uses these to:
1. **Clamp context** — A 200K context model won't be chosen if `OPENCODE_MAX_CONTEXT=32000`
2. **Penalize headroom** — At 80% RPM usage, OpenCode Go's value score drops, letting other providers win
3. **Hard-skip at exhaustion** — When RPM/TPM = 0, provider is excluded entirely
4. **Monthly cap** — `OPENCODE_MONTHLY_TPM` hard-skips the provider once the month's allowance is gone

---

## Per-Model Usage Levels (Quota Accounting)

OpenCode Go is a **flat-rate subscription**, so every request's *marginal* cost
is ~$0 — but not every model burns the subscription's token allowance at the
same rate. `kimi-k3` ($3/$15 per 1M) consumes ~43x the allowance of
`deepseek-v4-flash` ($0.14/$0.28) for the same nominal request. Atom accounts
for this with a **quota weight** per model:

| Model | Quota weight | Meaning |
|-------|-------------|---------|
| `deepseek-v4-flash` | 1.0 | Baseline — cheapest burn |
| `minimax-m2.7` / `minimax-m3` | ~3.6 | |
| `qwen3.7-plus` | ~4.8 | |
| `kimi-k2.7-code` / `kimi-k2.6` | ~11.8 | |
| `deepseek-v4-pro` | ~12.4 | |
| `glm-5.1` / `glm-5.2` | ~13.8 | |
| `qwen3.7-max` | ~23.8 | |
| `kimi-k3` | ~42.9 | Heaviest burn — drains quota ~43x faster |

Weights are derived from the gateway's per-token price table (normalized to
`deepseek-v4-flash` = 1.0) and applied in three places:

1. **Weighted provider TPM** — a `kimi-k3` request counts ~43x a
   `deepseek-v4-flash` request against the shared `OPENCODE_TPM` window, so a
   single heavy model can't silently drain the provider budget while the
   request counter looks healthy.
2. **Quota value-score penalty** — the BPC ranker multiplies a model's value
   score by `max(0.25, weight^-0.2)`: weight 1.0 → 1.0, ~12x → ~0.61, ~43x →
   ~0.47. This is a mild nudge that only decides ties at *equal quality* — a
   heavy model still wins when it's meaningfully better (e.g.
   `deepseek-v4-pro` still wins COMPLEX tasks over `deepseek-v4-flash`).
3. **Per-model limits** — models with their own RPM/TPM are hard-skipped
   **independently**; one exhausted model doesn't take the whole provider down.

### Per-Model Overrides (`OPENCODE_MODEL_LIMITS`)

Cap a notoriously quota-hungry model while leaving cheap ones unlimited:

```bash
# JSON object keyed by gateway model id
OPENCODE_MODEL_LIMITS='{"deepseek-v4-pro": {"weight": 3.0, "rpm": 20, "tpm": 500000},
                        "kimi-k3": {"weight": 15.0, "tpm": 200000}}'
```

- `weight` overrides the price-derived quota weight (min 1.0)
- `rpm` / `tpm` give the model its own rate budget — it is hard-skipped when
  exhausted, while other models on the same key keep routing
- Models not listed keep their price-derived weight and fall back to the
  provider-wide headroom

### Monthly Subscription Allowance (`OPENCODE_MONTHLY_TPM`)

The in-window RPM/TPM guards burst rates; `OPENCODE_MONTHLY_TPM` guards the
monthly allowance. Usage is persisted per call (`rate_usage_records` table,
fire-and-forget) and aggregated since the 1st of the current month:

```bash
# Example: 200M token monthly plan
OPENCODE_MONTHLY_TPM=200000000
```

When the weighted monthly total reaches the limit, BPC logs
`BPC skipped opencode-go — monthly subscription quota exhausted` and routes to
fallback providers for the rest of the month. Unset (default) = no monthly
gate, matching prior behavior.

> **Weighted vs raw**: the persisted monthly total is *raw* tokens; the
> in-window TPM check is *weighted* by quota weight. If you set
> `OPENCODE_MONTHLY_TPM`, size it against your plan's raw-token allowance.

---

### Verification

```bash
# Check provider is registered
curl http://localhost:8000/api/llm/providers | jq '.[] | select(.id=="opencode-go")'

# Check routing includes opencode-go
curl -X POST http://localhost:8000/api/agent/route \
  -H "Content-Type: application/json" \
  -d '{"request": "Hello", "tier": "budget"}' | jq '.provider'
```

---

## Cost Model

| Aspect | Direct API | OpenCode Go |
|--------|------------|-------------|
| **Pricing** | Per-token ($/1M) | Flat monthly subscription |
| **Marginal cost** | Increases with usage | ~$0 |
| **Budget predictability** | Variable | Fixed |
| **Best for** | Low/sporadic usage | High-volume, cost-sensitive workloads |

**Typical savings**: 80–95% for workloads >100K tokens/day.

---

## Routing Behavior Deep Dive

### BPC Ranking with OpenCode Go

```
1. Request arrives → complexity classified (SIMPLE/MODERATE/COMPLEX/ADVANCED)
2. Candidate providers filtered by:
   - Has valid API key
   - Model supports required features (tools, vision, reasoning)
   - Context window ≥ request needs (clamped by OPENCODE_MAX_CONTEXT)
3. Each candidate scored:
   value_score = cost_score × quality_score × latency_score × headroom_factor
4. Headroom factor = 1.0 - (current_usage / limit)  [0.0 to 1.0]
5. Top-ranked provider wins (or fallback chain on failure)
```

### Example: Headroom Penalty

```python
# At 48/60 RPM used (80%):
headroom = 1.0 - 48/60 = 0.2
value_score *= 0.2  # Heavy penalty — other providers likely win

# At 10/60 RPM used (17%):
headroom = 1.0 - 10/60 = 0.83
value_score *= 0.83  # Light penalty — OpenCode Go stays competitive
```

### Example: Context Clamp

```python
# Request needs 50K context
# OPENCODE_MAX_CONTEXT = 32000 (set by user)
# → deepseek-v4-flash (200K native) CLAMPED to 32K
# → Model skipped for this request (insufficient context)
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Provider not in routing | `OPENCODE_API_KEY` not set | Add key to `backend/.env`, restart |
| "All providers failed" | Rate limit exhausted | Increase `OPENCODE_RPM/TPM` or wait for window reset |
| Model context errors | `OPENCODE_MAX_CONTEXT` too low | Raise to match gateway capability (200K default) |
| Wrong model selected | Complexity misclassified | Use `x-atom-tier` header to force budget tier |
| 401 from gateway | Invalid/expired key | Regenerate key at opencode.ai |

### Debug Commands

```bash
# View per-model usage levels (weights, limits, window + monthly usage)
curl http://localhost:8000/api/debug/opencode-usage | jq '.data'

# Filter to a single model
curl "http://localhost:8000/api/debug/opencode-usage?model=kimi-k3" | jq '.data.models'

# View provider health
curl http://localhost:8000/api/ai/providers | jq '.[] | select(.id=="opencode-go")'

# Force OpenCode Go for a request
curl -X POST http://localhost:8000/api/agent/route \
  -H "x-atom-tier: budget" \
  -H "Content-Type: application/json" \
  -d '{"request": "Write a Python function"}'
```

---

## Comparison: OpenCode Go vs OpenRouter

| Feature | OpenCode Go | OpenRouter |
|---------|-------------|------------|
| **Pricing** | Subscription | Per-token (pay-as-you-go) |
| **Models** | Curated (DeepSeek, Kimi, etc.) | 100+ models |
| **Rate limits** | Custom per-tier | Shared key limits |
| **Context** | 200K default | Varies by model |
| **Best for** | Predictable high volume | Model experimentation |

Both can be enabled simultaneously — the router picks the best per request.

---

## Advanced: Custom Model Overrides

Force a specific OpenCode Go model via header:

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer atom_sk_..." \
  -H "x-atom-model: deepseek-v4-pro" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"..."}]}'
```

Or via Atom's internal routing API:

```bash
curl -X POST http://localhost:8000/api/agent/route \
  -H "Content-Type: application/json" \
  -d '{"request": "...", "model": "deepseek-v4-pro"}'
```

---

## FAQ

**Q: Why `OPENCODE_API_KEY` not `OPENCODE_GO_API_KEY`?**  
A: The code convention is `{PROVIDER_ID}_API_KEY` (uppercase). The provider ID is `opencode-go`, which would produce `OPENCODE-GO_API_KEY` — invalid because env var names use underscores, not hyphens. So it's a special case in `byok_handler.py` that maps `opencode-go` → `OPENCODE_API_KEY`, dropping the "GO".

**Q: Can I use OpenCode Go with the LLM Gateway (`/v1/*`)?**  
A: Yes. Configure an `atom_sk_*` gateway key, and the gateway will route through OpenCode Go when it wins BPC ranking.

**Q: Does OpenCode Go support streaming?**  
A: Yes — the gateway supports SSE streaming. Atom's `BYOKHandler.stream_completion` handles it transparently.

**Q: What happens if my subscription expires?**  
A: The gateway returns 401/403. Atom's circuit breaker marks the provider unhealthy; fallback providers take over. Renew at opencode.ai.

**Q: Can I override the static fallback models?**  
A: Not via config — they're hardcoded in `COST_EFFICIENT_MODELS["opencode-go"]`. The dynamic pricing fetcher (when cache is warm) uses real gateway model list.

**Q: How do I stop one model from draining my subscription quota?**  
A: Two levers: (1) `OPENCODE_MODEL_LIMITS` gives that model its own RPM/TPM so it's hard-skipped independently (e.g. `{"kimi-k3": {"tpm": 200000}}`); (2) raise its `weight` so the quota penalty deprioritizes it at equal quality (e.g. `{"kimi-k3": {"weight": 60}}`).

**Q: Does quota accounting change existing routing behavior?**  
A: Only for models with a quota weight > 1.0 at *quality parity*. The per-token price is already in the value score; the quota factor (0.25–1.0) merely breaks ties toward lighter models. All defaults preserve prior behavior: no monthly gate unless `OPENCODE_MONTHLY_TPM` is set, no per-model limits unless `OPENCODE_MODEL_LIMITS` is set.

---

## Related Documentation

- [LLM Gateway](../architecture/LLM_GATEWAY.md) — Inbound OpenAI/Anthropic-compatible surface
- [Routing Strategies](../reference/ROUTING_STRATEGIES.md) — How BPC ranking works
- [Cognitive Tier System](../architecture/COGNITIVE_TIER_SYSTEM.md) — 5-tier routing
- [Environment Variables](../reference/ENVIRONMENT_VARIABLES.md) — Complete env var reference
- [Provider Rate Limits](../architecture/PROVIDER_RATE_LIMITS.md) — Rate tracking architecture

---

*Last Updated: August 2026*