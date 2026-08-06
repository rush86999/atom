# LLM Providers Guide — Complete Setup & Comparison

> **Quick decision**: 
> - **Free local** → [Ollama](getting_started/run-with-ollama.md) (no API key, runs on your hardware)
> - **Lowest cost cloud** → [OpenCode Go](guides/OPENCODE_GO_PROVIDER.md) (subscription, ~90% savings)
> - **Best quality** → OpenAI / Anthropic (pay-per-token, highest capability)
> - **Model variety** → OpenRouter (unified gateway, 100+ models)
> - **Specialized** → DeepSeek (code/reasoning), Gemini (long context), GLM (Chinese)

---

## Provider Comparison Matrix

| Provider | Cost Model | Best For | Context | Tools | Vision | Reasoning | Setup |
|----------|------------|----------|---------|-------|--------|-----------|-------|
| **Ollama** | Free (hardware) | Privacy, offline, dev | 8K–128K | ✅ | ❌ | ❌ | `OLLAMA_BASE_URL` |
| **OpenCode Go** | Subscription ($/mo) | High volume, code | 200K | ✅ | ❌ | ✅ | `OPENCODE_API_KEY` |
| **OpenAI** | Pay-per-token | General, quality | 128K–1M | ✅ | ✅ | ✅ | `OPENAI_API_KEY` |
| **Anthropic** | Pay-per-token | Reasoning, safety | 200K | ✅ | ✅ | ✅ | `ANTHROPIC_API_KEY` |
| **DeepSeek** | Pay-per-token | Code, math, reasoning | 64K | ✅ | ❌ | ✅ | `DEEPSEEK_API_KEY` |
| **Gemini** | Pay-per-token | Long context, multimodal | 2M | ✅ | ✅ | ✅ | `GOOGLE_API_KEY` |
| **OpenRouter** | Pay-per-token | Model variety | Varies | ✅ | Varies | Varies | `OPENROUTER_API_KEY` |
| **GLM** | Pay-per-token | Chinese, reasoning | 128K | ✅ | ❌ | ✅ | `GLM_API_KEY` |
| **MiniMax** | Pay-per-token | Long context | 200K+ | ✅ | ❌ | ❌ | `MINIMAX_API_KEY` |

---

## Quick Setup by Provider

### Ollama (Free Local) — Recommended First

```bash
# 1. Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# 2. Pull a model
ollama pull llama3:8b        # 4.7GB, general
ollama pull deepseek-coder:6.7b  # 3.8GB, code
ollama pull gemma2:9b        # 5.4GB, strong reasoning

# 3. Configure Atom (backend/.env)
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3:8b
ATOM_LOCAL_ONLY=true         # Blocks all cloud providers

# 4. Restart backend
```

**Pros**: Zero cost, total privacy, no rate limits, works offline  
**Cons**: Needs GPU/RAM, slower than cloud, limited model quality

> 📖 Full guide: [Run with Ollama](getting_started/run-with-ollama.md)

---

### OpenCode Go (Low-Cost Cloud) — Best Value for Production

```bash
# 1. Get key from https://opencode.ai
# 2. Configure (backend/.env)
OPENCODE_API_KEY=sk-opencode-...
OPENCODE_RPM=60              # Adjust to your plan
OPENCODE_TPM=2000000
OPENCODE_MAX_CONTEXT=200000

# 3. Restart backend
```

**Pros**: ~90% cheaper than direct APIs, 200K context, code-specialized models  
**Cons**: Requires subscription, fewer model choices

> 📖 Full guide: [OpenCode Go Provider](guides/OPENCODE_GO_PROVIDER.md)

---

### OpenAI (Best General Quality)

```bash
# 1. Get key from https://platform.openai.com/api-keys
# 2. Configure (backend/.env)
OPENAI_API_KEY=sk-...
# Optional: override default model
MODEL_NAME=gpt-4o-mini
```

**Models available**: `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `gpt-3.5-turbo`  
**Pros**: Highest quality, best tool use, reliable  
**Cons**: Most expensive, rate limits on lower tiers

---

### Anthropic (Best Reasoning & Safety)

```bash
# 1. Get key from https://console.anthropic.com/
# 2. Configure (backend/.env)
ANTHROPIC_API_KEY=sk-ant-...
```

**Models available**: `claude-3-5-sonnet-20241022`, `claude-3-5-haiku-20241022`, `claude-3-opus-20240229`  
**Pros**: Best reasoning, constitutional AI, large context  
**Cons**: Expensive, stricter rate limits

---

### DeepSeek (Best for Code/Reasoning)

```bash
# 1. Get key from https://platform.deepseek.com/
# 2. Configure (backend/.env)
DEEPSEEK_API_KEY=...
```

**Models**: `deepseek-chat` (V3), `deepseek-reasoner` (R1)  
**Pros**: Excellent code/reasoning, cheaper than OpenAI/Anthropic  
**Cons**: No vision, smaller context (64K)

---

### Google Gemini (Best Long Context)

```bash
# 1. Get key from https://aistudio.google.com/app/apikey
# 2. Configure (backend/.env)
GOOGLE_API_KEY=...
```

**Models**: `gemini-1.5-pro` (2M context), `gemini-1.5-flash` (1M context)  
**Pros**: Massive context, multimodal, competitive pricing  
**Cons**: Tool use less reliable, newer API

---

### OpenRouter (Model Variety Gateway)

```bash
# 1. Get key from https://openrouter.ai/keys
# 2. Configure (backend/.env)
OPENROUTER_API_KEY=...
OPENROUTER_RPM=50            # Conservative defaults
OPENROUTER_TPM=1000000
OPENROUTER_MAX_CONTEXT=200000
```

**Pros**: 100+ models via single key, automatic fallbacks  
**Cons**: Shared rate limits, markup on token prices

---

## Routing: How Atom Chooses Providers

Atom uses **BPC (Best Provider Candidate)** ranking. For each request:

```
1. Classify complexity → SIMPLE / MODERATE / COMPLEX / ADVANCED
2. Filter providers by:
   - Has valid API key configured
   - Supports required features (tools, vision, reasoning)
   - Context window ≥ request needs
3. Score each candidate:
   value = cost_score × quality_score × latency_score × headroom_factor
4. Top-ranked wins (fallback chain on failure)
```

### Force a Provider/Tier Per Request

```bash
# Force budget tier (prefers OpenCode Go, Ollama, cheap models)
curl -X POST http://localhost:8000/api/agent/route \
  -H "x-atom-tier: budget" \
  -d '{"request": "..."}'

# Force specific model
curl -X POST http://localhost:8000/api/agent/route \
  -H "x-atom-model: gpt-4o" \
  -d '{"request": "..."}'

# Force cognitive tier (routes to appropriate provider)
curl -X POST http://localhost:8000/api/agent/route \
  -H "x-atom-tier: reasoning" \
  -d '{"request": "Complex math problem"}'
```

> 📖 Details: [Routing Strategies](reference/ROUTING_STRATEGIES.md) | [Routing Headers](reference/ROUTING_HEADERS.md)

---

## Cost Optimization Strategies

### 1. Tier-Based Routing (Automatic)

Set `ATOM_GATEWAY_PREFER_COST=true` (default) to bias toward cheaper providers for simple tasks.

### 2. Cognitive Tiers

| Tier | Use Case | Typical Provider |
|------|----------|------------------|
| `budget` | Chat, classification | OpenCode Go, Ollama |
| `balanced` | General tasks | DeepSeek, GPT-4o-mini |
| `reasoning` | Math, logic | DeepSeek-R1, Claude |
| `coding` | Code gen/debug | DeepSeek-Coder, Kimi |
| `premium` | Critical quality | GPT-4o, Opus |

### 3. Daily/Monthly Budgets

```bash
# backend/.env
ATOM_DAILY_BUDGET=10.00      # $10/day hard cap
ATOM_MONTHLY_BUDGET=200.00   # $200/month hard cap
```

### 4. Model-Specific Routing

```bash
# Cheap model for simple, expensive for complex
# Automatic via complexity classification
```

---

## Troubleshooting Provider Issues

| Issue | Diagnosis | Fix |
|-------|-----------|-----|
| "No providers configured" | No API keys set | Add at least one key to `backend/.env` |
| "All providers failed" | All keys invalid/rate-limited | Check keys, wait for reset, add fallbacks |
| Wrong model chosen | Complexity misclassified | Use `x-atom-tier` or `x-atom-model` header |
| High costs | Premium models winning | Set `ATOM_GATEWAY_PREFER_COST=true`, check budgets |
| Slow responses | Provider latency | Check `/api/llm/providers/health`, adjust routing |
| Context errors | Request > provider limit | Use Gemini (2M) or reduce input |

### Debug Commands

```bash
# List configured providers
curl http://localhost:8000/api/llm/providers

# Check provider health + rate limits
curl http://localhost:8000/api/llm/providers/health

# See routing decision for a request
curl -X POST http://localhost:8000/api/agent/route \
  -H "Content-Type: application/json" \
  -d '{"request": "Your test prompt"}' | jq '{provider, model, tier, complexity}'

# View rate tracker (OpenCode Go, OpenRouter)
curl http://localhost:8000/api/debug/rate-tracker
```

---

## Environment Variables Summary

Add to `backend/.env`:

```bash
# === REQUIRED: At least ONE ===
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# DEEPSEEK_API_KEY=...
# GOOGLE_API_KEY=...
# GLM_API_KEY=...
# MINIMAX_API_KEY=...
# OPENROUTER_API_KEY=...
# OPENCODE_API_KEY=sk-opencode-...
# OLLAMA_BASE_URL=http://localhost:11434/v1  # For local

# === OPTIONAL: Routing behavior ===
ATOM_GATEWAY_PREFER_COST=true        # Cost-aware routing (default: true)
ATOM_GATEWAY_ENABLED=true            # Enable /v1/* gateway (default: true)
ATOM_LEARNING_ROUTER=false           # Learning router (default: false)
MODEL_NAME=gpt-3.5-turbo             # Default model fallback
MAX_TOKENS=2048                      # Default max tokens
TEMPERATURE=0.7                      # Default temperature

# === OPTIONAL: OpenCode Go tuning ===
OPENCODE_RPM=60
OPENCODE_TPM=2000000
OPENCODE_MAX_CONTEXT=200000

# === OPTIONAL: OpenRouter tuning ===
OPENROUTER_RPM=50
OPENROUTER_TPM=1000000
OPENROUTER_MAX_CONTEXT=200000

# === OPTIONAL: Budgets ===
ATOM_DAILY_BUDGET=10.00
ATOM_MONTHLY_BUDGET=200.00

# === OPTIONAL: Local-only mode ===
ATOM_LOCAL_ONLY=false                # true = block ALL cloud providers
```

---

## Recommended Configurations

### Development (Free)
```bash
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3:8b
ATOM_LOCAL_ONLY=true
```

### Production - Cost Optimized
```bash
OPENCODE_API_KEY=sk-opencode-...      # Primary
DEEPSEEK_API_KEY=...                  # Fallback for reasoning
OPENAI_API_KEY=sk-...                 # Fallback for quality
ATOM_GATEWAY_PREFER_COST=true
ATOM_DAILY_BUDGET=20.00
```

### Production - Quality Optimized
```bash
OPENAI_API_KEY=sk-...                 # Primary
ANTHROPIC_API_KEY=sk-ant-...          # Reasoning fallback
DEEPSEEK_API_KEY=...                  # Code fallback
GOOGLE_API_KEY=...                    # Long context fallback
ATOM_DAILY_BUDGET=100.00
```

### Enterprise - Maximum Coverage
```bash
# All providers configured
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
DEEPSEEK_API_KEY=...
GOOGLE_API_KEY=...
GLM_API_KEY=...
MINIMAX_API_KEY=...
OPENROUTER_API_KEY=...
OPENCODE_API_KEY=...
OLLAMA_BASE_URL=http://localhost:11434/v1  # Local fallback
ATOM_LEARNING_ROUTER=true             # Enable learning router
ATOM_GATEWAY_BUDGET_ALERTS=true       # Spend alerts
```

---

## FAQ

**Q: Can I use multiple providers simultaneously?**  
A: Yes. Atom routes each request to the best provider. All configured providers participate in BPC ranking.

**Q: How do I know which provider was used?**  
A: Response includes `provider` and `model` fields. Check `/api/llm/providers/health` for stats.

**Q: What if a provider fails mid-request?**  
A: Automatic fallback to next-ranked provider. Streaming requests retry transparently.

**Q: Does OpenCode Go work with the LLM Gateway (`/v1/*`)?**  
A: Yes. Gateway keys (`atom_sk_*`) route through the same BPC layer.

**Q: How do I add a custom provider?**  
A: Add to `PROVIDER_TIERS` and `COST_EFFICIENT_MODELS` in `byok_handler.py`, implement client init.

**Q: Can I use Azure OpenAI / AWS Bedrock?**  
A: Not natively. Use OpenRouter (supports both) or implement custom provider.

---

## Related Documentation

- [OpenCode Go Provider](guides/OPENCODE_GO_PROVIDER.md) — Deep dive
- [Run with Ollama](getting_started/run-with-ollama.md) — Local setup
- [Routing Strategies](reference/ROUTING_STRATEGIES.md) — BPC, fusion, cascade
- [Routing Headers](reference/ROUTING_HEADERS.md) — Per-request control
- [Cognitive Tier System](architecture/COGNITIVE_TIER_SYSTEM.md) — 5-tier routing
- [Learning LLM Router](architecture/LEARNING_LLM_ROUTER.md) — Feedback-based re-ranking
- [Environment Variables](reference/ENVIRONMENT_VARIABLES.md) — Complete reference

---

*Last Updated: August 2026*