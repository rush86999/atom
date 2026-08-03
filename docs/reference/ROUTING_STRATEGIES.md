# Routing Strategies

Atom supports multiple LLM routing strategies, selectable per-request. The default is `auto` (cost-aware BPC + learning router + cognitive tiers).

## Strategies

### `auto` (default)
Cost-aware BPC (Benchmark-Price-Capability) routing with:
- 5-tier cognitive classification (MICRO → COMPLEX)
- Learning router (sklearn predictors + EMA telemetry)
- Intent detector (6-category domain classifier)
- Self-healing autofix (request body repair on 4xx)
- Token compression (RTK + session-dedup)

No header needed — this is the default.

### `fusion` (opt-in, heavily restricted)
Sends the prompt to N top-ranked models in parallel, then a judge synthesizes the best answer. **Only for one-off high-stakes tasks** — never batch/workflow automation.

**Evidence-based restrictions** ([Spheron](https://www.spheron.network/blog/mixture-of-agents-gpu-cloud/), [OpenPipe](https://openpipe.ai/blog/mixture-of-agents), [Nama](https://www.linkedin.com/pulse/mixture-agents-moa-framework-technical-dive-nagesh-nama-isdhe)): MoA latency×cost is inappropriate for real-time or batch paths.

**Eligibility (ALL must be true):**
1. `x-atom-strategy: fusion` header explicitly set
2. `ATOM_FUSION_ROUTING_ENABLED=true` (default ON)
3. Cognitive tier is COMPLEX (highest tier)
4. NOT a batch/workflow task type (agentic/extraction/pdf_ocr excluded)
5. ≥2 providers available

```bash
curl -X POST https://your-atom/api/chat/message \
  -H "x-atom-strategy: fusion" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message": "Analyze the legal implications of this contract clause"}'
```

### `lkgp` (session-sticky, default ON)
Last-Known-Good-Path: remembers which provider/model last succeeded for a session and prefers it for follow-ups. Reduces quality variance in multi-turn conversations.

**Evidence** ([vLLM #1439](https://github.com/vllm-project/semantic-router/issues/1439), [Vercel](https://vercel.com/i/llm-routing-strategies), [LLM Gateway](https://docs.llmgateway.io/features/sessions), [Red Hat llm-d](https://developers.redhat.com/articles/2026/01/13/accelerate-multi-turn-workloads-llm-d)): sticky routing is the production default for multi-turn consistency.

No header needed — LKGP is automatic when `ATOM_LKGP_ENABLED=true` (default ON). The session's last-known-good `(provider, model)` is boosted to position 0 in the candidate list if available and healthy.

## Per-request selection

| Strategy | How to select | When to use |
|----------|--------------|-------------|
| `auto` | Default (no header) | General-purpose business automation + coding |
| `fusion` | `x-atom-strategy: fusion` | One-off high-stakes reasoning (legal, strategic, complex debugging) |
| `lkgp` | Automatic (session-sticky) | Multi-turn conversations where consistency matters |

## Configuration

| Env var | Default | Effect |
|---------|---------|--------|
| `ATOM_FUSION_ROUTING_ENABLED` | `true` | Enable fusion (still requires header + COMPLEX tier) |
| `ATOM_LKGP_ENABLED` | `true` | Enable session sticky routing |
| `ATOM_FUSION_SAMPLES` | `3` | Number of parallel models in fusion |
