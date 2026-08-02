# LLM Gateway — OpenAI/Anthropic-Compatible Inbound Surface

> Phase A (core). Forward-pointers to Phases B/C/D at the end. Master switch:
> `ATOM_GATEWAY_ENABLED=true`.

Atom exposes its existing BYOK routing layer as an inbound OpenAI- **and**
Anthropic-compatible gateway. External AI tools — Claude Code, Hermes, any
OpenAI-SDK app — point their base URL at Atom and authenticate with an
`atom_sk_*` key. All routing, fallback, self-healing, cost tracking, and
credential resolution reuse the existing `BYOKHandler`; only the wire protocol
and identity model are new.

## Endpoints

| Method | Path | Protocol | Auth |
|---|---|---|---|
| POST | `/v1/chat/completions` | OpenAI | `x-api-key` / `Bearer atom_sk_*` / JWT |
| POST | `/v1/messages` | Anthropic | `x-api-key` / `Bearer atom_sk_*` / JWT |
| GET | `/v1/models` | OpenAI list | same |
| POST | `/api/gateway/keys` | key minting (returns plaintext once) | JWT (`get_current_user`) |
| GET/DELETE/POST | `/api/gateway/keys/{id}` | key list / revoke / rotate | JWT, owner-scoped |
| GET | `/api/v1/gateway/logs` | request-log list | JWT, owner-scoped |
| GET | `/api/v1/gateway/logs/{id}` | single request-log entry | JWT, owner-scoped |
| GET | `/api/v1/llm-oauth/{provider}/connect` | LLM OAuth initiate (`credential_type=oauth\|subscription`) | JWT |
| GET | `/api/v1/llm-oauth/{provider}/callback` | LLM OAuth callback (state-validated, rate-limited) | JWT |
| GET/DELETE | `/api/v1/llm-oauth/credentials[/{id}]` | list / revoke LLM OAuth + subscription credentials | JWT, owner-scoped |
| GET | `/api/v1/llm-oauth/status` | per-provider credential status | JWT |

Key management routes are the only gateway surface requiring a normal login
JWT; the `/v1/*` inference endpoints accept gateway keys.

## Routing decision flow

```
request (messages, model, headers)
  -> parse_routing_overrides(headers)        # x-atom-model / x-atom-tier / x-atom-intent
  -> prompt_from_messages(messages)          # last user message, flattened
  -> analyze_query_complexity(prompt)        # deterministic scorer
  -> intent = override or IntentDetector().detect(prompt)
  -> x-atom-tier ? get_ranked_providers(..., cognitive_tier) : get_optimal_provider(complexity, prefer_cost=ATOM_GATEWAY_PREFER_COST)
  -> model == "auto"/None ? ranked model : forced model + _resolve_provider_for_model
  -> BYOKHandler.chat_completion(...) / stream_completion(...)   # fallback + self-heal + cost/health/feedback
```

`NoProvidersConfiguredError` propagates as a 503 with a `recovery_url`
(`/settings/ai`). Gateway keys map key → user → tenant → workspace, so every
call is attributable and tenant-scoped.

## Auth matrix

| Secret | Path | Notes |
|---|---|---|
| `x-api-key: atom_sk_*` | SHA-256 lookup on `key_hash` | active / not revoked / not expired; Round-43 ACTIVE-user check; per-key sliding-window rate limit → 429 |
| `Authorization: Bearer atom_sk_*` | same | |
| `Authorization: Bearer <JWT>` | `get_current_user` | cookie fallback, revocation, ACTIVE checks reused |

Plaintext keys are **never stored** — only `key_hash` (sha256) + `key_prefix`
(`atom_sk_` + 4 chars). The plaintext `atom_sk_<uuid>` is returned exactly once
at creation time.

## Wire-format / SSE mapping

Pure translators live in `core/llm/gateway/wire_formats.py` (unit-tested):

| Anthropic → OpenAI | OpenAI → Anthropic |
|---|---|
| top-level `system` → `system` message | `choices[0].message.content` → `content[0].text` |
| image block → `image_url` data URL | `finish_reason` → `stop_reason` (`length`→`max_tokens`, `tool_calls`→`tool_use`) |
| `stop_sequences` → `stop` | `usage` → `input_tokens` / `output_tokens` |
| tool blocks best-effort preserved as text | error → Anthropic error body (status → type table) |

SSE adapters in `api/openai_gateway_routes.py`:

- **OpenAI**: role chunk → content-delta chunks → finish chunk → usage chunk → `data: [DONE]`.
- **Anthropic**: `message_start` → `content_block_start` → `content_block_delta`* → `content_block_stop` → `message_delta` → `message_stop`.
- Terminal `stream_completion` `[Error: ...]` yield → OpenAI: delta + `[DONE]`; Anthropic: `content_block_delta` + `message_stop` + `event: error`.

## Error mapping (central table — never leaks `str(e)`)

`map_gateway_error(exc, anthropic)` in `core/llm/gateway/__init__.py`:

| Exception | HTTP | OpenAI code | Anthropic type |
|---|---|---|---|
| `NoProvidersConfiguredError` | 503 | `no_llm_provider` + `recovery_url` | `overloaded_error` |
| `GatewayBlockedError` | 429 | `budget_exceeded` / `trial_expired` | `rate_limit_error` |
| `AllProvidersFailedError` | 502 | `all_providers_failed` | `api_error` |
| `ValueError` | 400 | `invalid_request` | `invalid_request_error` |
| other | 500 | `internal_error` | `api_error` |

## Env vars

```
ATOM_GATEWAY_ENABLED=true            # master switch (404 when off)
ATOM_GATEWAY_PREFER_COST=true        # cost-aware routing default
ATOM_GATEWAY_LOG_BODIES=false        # Phase B: persist full request/response bodies
ATOM_GATEWAY_DEFAULT_MAX_TOKENS=1000
ATOM_GATEWAY_BUDGET_ALERTS=false     # Phase B: threshold spend alerts
ATOM_GATEWAY_LOG_RETENTION_DAYS=30   # Phase B: log sweep retention
```

## Header overrides

`x-atom-model`, `x-atom-tier`, `x-atom-intent` force routing per-request
(see `docs/reference/ROUTING_HEADERS.md`). The routed `model` is echoed in the
response; with `ATOM_GATEWAY_LOG_BODIES=true` the effective route is visible in
`/api/v1/gateway/logs`.

## Manual checks

```bash
# OpenAI path
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer atom_sk_..." -H "Content-Type: application/json" \
  -d '{"model":"auto","messages":[{"role":"user","content":"Hello"}]}'

# Anthropic path
curl http://localhost:8000/v1/messages \
  -H "x-api-key: atom_sk_..." -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{"model":"auto","max_tokens":100,"messages":[{"role":"user","content":"Hi"}]}'

# Claude Code plug-in
ANTHROPIC_BASE_URL=http://localhost:8000 ANTHROPIC_API_KEY=atom_sk_... claude
```

## Forward-pointers

- **Phase B** — spend alerts + log viewer landed:
  - **B1** notification-signature fix (3-arg `send_notification`).
  - **B2** `personal_budget_service.send_budget_alert` now delivers an in-app
    notification (`NotificationService.send_notification(user_id, "budget_alert", {...})`)
    in addition to the console warning.
  - **B3** gateway budget threshold alerts at 50/80/90/100% of the personal
    budget limit, fire-once per workspace-day, gated by
    `ATOM_GATEWAY_BUDGET_ALERTS` (in-memory daily spend tracking).
  - **B4** `GatewayRequestLog` write hooks on stream + non-stream paths with
    PII redaction, dropped auth headers, and 64 KB truncation; owner-scoped
    viewer at `/api/v1/gateway/logs`; retention sweep
    (`periodic_tasks.run_gateway_log_sweep`, `ATOM_GATEWAY_LOG_RETENTION_DAYS`).
    Bodies persist only when `ATOM_GATEWAY_LOG_BODIES=true`.
- **Phase C** — provider breadth: 6 OpenAI-compatible providers added to
  `providers_config` (`xai`, `cerebras`, `fireworks`, `huggingface`,
  `nvidia_nim`, `zai`) + BYOK defaults/env keys. n8n interop is auto-closed by
  Phase A (point n8n's OpenAI node at Atom's `/v1`). AWS Bedrock is a stretch
  (SigV4) — optional.
- **Phase D** — subscription-credential reuse (ChatGPT Plus / Claude Pro)
  landed: `credential_type` column on `LLMOAuthCredential` (+ guarded migration
  `20260802_credential_type`); `LLMCredentialService.get_credential` priority is
  now OAuth → subscription → BYOK → ENV; connect flow at
  `/api/v1/llm-oauth/*` carries the intent in the OAuth `state` and persists it.
  The `state` is an **HMAC-SHA256-signed token** (`llm:{provider}:{type}:{user_id}:{nonce}:{sig}`,
  signed with `SECRET_KEY`) so it is unforgeable — a tampered or re-targeted
  state is rejected in constant time at the callback. Connect also builds the
  provider `redirect_uri` via `core.llm_oauth_config.build_redirect_uri`.
  **Security note:** consumer-session **cookie/token capture** is out of scope —
  only OAuth-granted flows ship; see
  `docs/security/LLM_GATEWAY_SUBSCRIPTION_REUSE.md`.
