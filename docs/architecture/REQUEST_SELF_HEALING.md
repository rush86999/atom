# Request Self-Healing (Autofix)

When an LLM provider rejects a request with a **repairable 4xx error** (400/404/422),
atom now attempts to **patch the request body and retry once** before falling back
to another model. Previously, the fallback chain just retried the same (broken)
request on a different provider — which failed the same way.

This is inspired by [Manifest](https://github.com/mnfst/manifest)'s Phoenix
self-healing service, but rule-first to avoid adding latency/cost on the common cases.

## How it works

```
provider returns 4xx
  └─ classify_error()
       ├─ repairable_4xx (400/404/422) → run healer
       ├─ non_repairable_4xx (401/403/429) → skip (auth/rate-limit aren't body bugs)
       └─ server_error / transient → skip (server-side, not a request bug)
  └─ healer.heal()
       ├─ 1. Rule-based patches (instant, always on) — first match wins
       └─ 2. LLM healer (gated, off by default) — only if no rule matched
  └─ if patched: retry ONCE with patched body
       ├─ success → return (heal logged)
       └─ failure → normal fallback to next provider
```

## Rule-based patches (always on)

Each rule has a `matches(error, kwargs, provider, model)` predicate and an `apply(kwargs)`
that returns patched kwargs. First match wins.

| Rule | Trigger | Patch |
|------|---------|-------|
| `param_rename_max_tokens` | Error mentions `max_tokens` / `unexpected parameter` | Rename `max_tokens` → `max_output_tokens` (Gemini/Claude) |
| `drop_temperature_o_series` | Error mentions `temperature` + model is `o1`/`o3`/`o4` | Remove `temperature` |
| `strip_multimodal` | Error mentions `image`/`multimodal`/`vision` + payload has `image_url` | Collapse multimodal content to text-only |
| `truncate_context` | Error mentions `context length`/`too long`/`token limit` | Keep system message + last 4 turns |
| `drop_response_format` | Error mentions `response_format`/`json mode` | Remove `response_format` |

Rules never mutate the input kwargs (shallow-copied). Rule exceptions are caught
and swallowed — a buggy rule can't break the heal path.

## LLM fallback healer (off by default)

When no rule matches but the error is still a repairable 4xx, an optional LLM-based
healer can generate a patch. Gated behind `ATOM_LLM_HEALER_ENABLED=true`.

- Sends the failed request + normalized error to the cheapest available model.
- Asks for a JSON patch (`{"patch": {full corrected body}}` or `{"patch": null}`).
- Strict 5-second timeout.
- Allowed-keys whitelist: only `messages`, `max_tokens`, `max_output_tokens`,
  `temperature`, `top_p`, `response_format`, etc. Never `model`/auth/headers.
- Single attempt.

## Integration points

The healer runs inside the per-provider fallback loop in `BYOKHandler`:

- **`generate_response`** (non-stream): heal-and-retry before `continue` to next provider.
- **`stream_completion`** (stream): heal-and-retry before provider fallback. Only on
  initial stream-creation failure (never mid-stream).
- **`generate_structured_response`**: left alone — it already has its own
  classify-then-retry cascade for schema errors.

Each provider gets **at most one heal attempt** (per-provider `heal_attempted` flag),
mirroring the existing structured-response `cascade_attempted` pattern.

## Error classification

This is the **first status-code-aware error classification** on the LLM call path.
It inspects `openai.APIStatusError.status_code` (the SDK base for
`BadRequestError`/`NotFoundError`/`UnprocessableEntityError`/`AuthenticationError`/
`RateLimitError`), with a substring fallback for non-SDK or wrapped errors.

```python
from core.llm.routing.request_healer import classify_error, is_repairable

category = classify_error(exc)
# "repairable_4xx" | "non_repairable_4xx" | "server_error" | "transient" | "unknown"

if is_repairable(exc):
    # worth a heal attempt
```

## Observability

Every heal attempt is logged:

```
[SelfHeal] retrying openai/gpt-4o with patch=param_rename_max_tokens keys=['max_tokens->max_output_tokens']
[SelfHeal] retry SUCCEEDED for openai/gpt-4o (rule=param_rename_max_tokens)
```

Healed requests also flow through the normal learning-router outcome feedback path,
so per-model predictors learn from healed successes/failures.

## Configuration

| Env var | Default | Effect |
|---------|---------|--------|
| `ATOM_LLM_HEALER_ENABLED` | `false` | Enable the LLM fallback healer (rules are always on) |

## File layout

- `core/llm/routing/request_healer.py` — healer engine, rules, classification
- `core/llm/byok_handler.py` — integration at the 2 call sites
- `tests/test_request_healer.py` — 41 tests covering all rules + LLM path + edge cases

## Adding a new rule

```python
class _MyRule(HealingRule):
    name = "my_rule"
    def matches(self, error, kwargs, provider, model):
        return "my keyword" in str(error).lower() and "my_param" in kwargs
    def apply(self, kwargs):
        patched = dict(kwargs)
        patched["my_param"] = "fixed_value"
        return patched, ["my_param"]

# Add to _DEFAULT_RULES list (order matters — first match wins)
_DEFAULT_RULES.append(_MyRule())
```
