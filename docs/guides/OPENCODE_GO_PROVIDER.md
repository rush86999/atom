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
| `OPENCODE_API_KEY` | *required* | Subscription key from opencode.ai (format: `sk-opencode-...`) |
| `OPENCODE_BASE_URL` | `https://opencode.ai/zen/v1` | Gateway endpoint (rarely needs changing) |
| `OPENCODE_RPM` | `60` | Max requests/minute for your tier. Adjust to match your plan. |
| `OPENCODE_TPM` | `2000000` | Max tokens/minute for your tier. |
| `OPENCODE_MAX_CONTEXT` | `200000` | Max context tokens the gateway accepts. Clamps candidate models. |

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
# View rate tracker state
curl http://localhost:8000/api/debug/rate-tracker | jq '.["opencode-go"]'

# View provider health
curl http://localhost:8000/api/llm/providers/health | jq '.["opencode-go"]'

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
A: Environment variables can't have hyphens in Python's `os.getenv`. The code explicitly looks for `OPENCODE_API_KEY`.

**Q: Can I use OpenCode Go with the LLM Gateway (`/v1/*`)?**  
A: Yes. Configure an `atom_sk_*` gateway key, and the gateway will route through OpenCode Go when it wins BPC ranking.

**Q: Does OpenCode Go support streaming?**  
A: Yes — the gateway supports SSE streaming. Atom's `BYOKHandler.stream_completion` handles it transparently.

**Q: What happens if my subscription expires?**  
A: The gateway returns 401/403. Atom's circuit breaker marks the provider unhealthy; fallback providers take over. Renew at opencode.ai.

**Q: Can I override the static fallback models?**  
A: Not via config — they're hardcoded in `COST_EFFICIENT_MODELS["opencode-go"]`. The dynamic pricing fetcher (when cache is warm) uses real gateway model list.

---

## Related Documentation

- [LLM Gateway](../architecture/LLM_GATEWAY.md) — Inbound OpenAI/Anthropic-compatible surface
- [Routing Strategies](../reference/ROUTING_STRATEGIES.md) — How BPC ranking works
- [Cognitive Tier System](../architecture/COGNITIVE_TIER_SYSTEM.md) — 5-tier routing
- [Environment Variables](../reference/ENVIRONMENT_VARIABLES.md) — Complete env var reference
- [Provider Rate Limits](../architecture/PROVIDER_RATE_LIMITS.md) — Rate tracking architecture

---

*Last Updated: August 2026*