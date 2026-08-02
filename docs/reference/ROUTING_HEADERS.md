# Routing Header Overrides

Atom supports **per-request routing overrides** via advisory HTTP headers. These let
callers force a specific cognitive tier, model, or intent for a single request without
changing environment flags or configuration.

This is inspired by [Manifest](https://github.com/mnfst/manifest)'s `x-manifest-*`
headers, which give callers fine programmatic control over routing.

## Headers

All three headers are **advisory**: invalid values are logged-and-ignored (never cause
a 400 error), so a malformed header cannot break a chat request. Budget enforcement
and capability filters still apply downstream.

| Header | Values | Effect |
|--------|--------|--------|
| `x-atom-tier` | `micro` \| `standard` \| `versatile` \| `heavy` \| `complex` | Forces a cognitive tier, skipping complexity classification |
| `x-atom-model` | any known model id (e.g. `gpt-4o`) | Forces a specific model, bypassing auto-routing entirely |
| `x-atom-intent` | `coding` \| `data_analysis` \| `web_browsing` \| `creative_writing` \| `reasoning` \| `conversation` | Forces an intent label, skipping intent detection |

Headers are case-insensitive (standard HTTP). Values are lowercased and trimmed.

## Usage

```bash
curl -X POST https://your-atom/api/chat/message \
  -H "Authorization: Bearer $TOKEN" \
  -H "x-atom-tier: heavy" \
  -H "x-atom-intent: reasoning" \
  -H "Content-Type: application/json" \
  -d '{"message": "Prove this theorem step by step"}'
```

Force a specific model (bypasses routing):

```bash
curl -X POST https://your-atom/api/chat/message \
  -H "Authorization: Bearer $TOKEN" \
  -H "x-atom-model: claude-mythos-5" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}'
```

Combine all three (model takes precedence for selection; tier/intent inform quality filtering and learning):

```bash
curl -X POST https://your-atom/api/chat/message \
  -H "Authorization: Bearer $TOKEN" \
  -H "x-atom-model: gpt-5.6-sol" \
  -H "x-atom-tier: complex" \
  -H "x-atom-intent: coding" \
  -H "Content-Type: application/json" \
  -d '{"message": "Refactor this function"}'
```

## Threading path

```
POST /api/chat/message (chat_routes.py)
  └─ parse_routing_overrides(http_request.headers)  →  {tier?, model?, intent?}
  └─ ChatOrchestrator.process_chat_message(routing_overrides=...)
      └─ _get_qwen_response(routing_overrides=...)
          └─ LLMService.generate_completion(model=forced_model, **tier/intent kwargs)
              └─ BYOKHandler.generate_response(cognitive_tier=..., intent_override=...)
```

- **`x-atom-model`**: overrides the `"auto"` default → concrete model short-circuits routing.
- **`x-atom-tier`**: forwarded as `cognitive_tier` → skips `analyze_query_complexity`, drives `MIN_QUALITY_BY_TIER` selection directly.
- **`x-atom-intent`**: forwarded as `intent_override` → skips intent detection, feeds the learning-router predictor cache key.

## Security

- The route is already authenticated (`get_current_user` dependency). No additional role
  check — any authenticated user can use these headers.
- Overrides are **advisory**: budget enforcement (`llm_usage_tracker.is_budget_exceeded`)
  still blocks overrides that exceed budget. Capability filters still apply.

## Validation behavior

| Input | Result |
|-------|--------|
| `x-atom-tier: heavy` | ✓ accepted |
| `x-atom-tier: bogus` | ✗ dropped (logged at debug), routing unchanged |
| `x-atom-intent: coding` | ✓ accepted |
| `x-atom-intent: bogus` | ✗ dropped |
| `x-atom-model: gpt-4o` | ✓ accepted (known model) |
| `x-atom-model: unknown-model` | ⚠ accepted (fail-open; downstream handler rejects gracefully) |
| `x-atom-model: "  "` | ✗ dropped (empty after trim) |

## Related

- [Cognitive Tier System](../architecture/COGNITIVE_TIER_SYSTEM.md) — the tier classification being overridden
- [Learning LLM Router](../architecture/LEARNING_LLM_ROUTER.md) — the auto-routing being bypassed
- [Intent Detector](../architecture/COGNITIVE_TIER_SYSTEM.md#intent-detection) — the intent detection being overridden
