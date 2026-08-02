# LLM Gateway — Subscription-Credential Reuse (Phase D)

> Scope + security posture for reusing a consumer LLM subscription (ChatGPT
> Plus / Claude Pro) through Atom's gateway. Read this before enabling any
> consumer-credential capture.

## What this feature is

Phase D lets a user's **subscription-linked OAuth grant** participate in Atom's
normal credential-resolution fallback for the LLM gateway:

```
OAuth token  →  subscription grant  →  BYOK key  →  env var
```

A subscription grant is just an OAuth credential stored in
`llm_oauth_credentials` tagged with `credential_type='subscription'`. The tag is
carried through the OAuth `state` parameter at connect time, so the callback
persists the right kind. `LLMCredentialService.get_credential` now prefers a
regular OAuth token, then a subscription-linked grant, then BYOK/env.

## What ships (in scope)

- **OAuth-granted flows only.** Connect happens through the provider's real
  OAuth authorization server (`api/llm_oauth_routes.py`):
  `GET /api/v1/llm-oauth/{provider}/connect` → provider consent screen →
  `GET /api/v1/llm-oauth/{provider}/callback`.
- The callback validates the `state` parameter (CSRF binding): it is an
  **HMAC-SHA256-signed token** (`llm:{provider}:{type}:{user_id}:{nonce}:{sig}`,
  signed with `SECRET_KEY`). The signature is verified in constant time
  (`hmac.compare_digest`), so a forged or tampered state is rejected even if the
  attacker knows the victim's `user_id`. The callback also checks the provider
  and credential intent (`oauth`/`subscription`), so a forged callback can't
  bind a victim's grant to an attacker's account.
- Callbacks are rate-limited (20/min/IP) and require a normal JWT
  (`get_current_user`), same posture as `/api/v1/auth/oauth`.
- Management is owner-scoped: list/revoke only touch the authenticated user's
  rows; the plaintext access token is never returned by any endpoint.

## What is explicitly deferred (OUT OF SCOPE)

**Consumer-session cookie / bearer-token capture is NOT implemented and must
not be added without a dedicated threat model and review.**

Capturing a ChatGPT Plus / Claude Pro session cookie (or a browser-side OAuth
bearer token extracted from the consumer app) is fundamentally different from an
OAuth grant:

| Concern | OAuth grant (ships) | Consumer-session capture (deferred) |
|---|---|---|
| Consent | Provider consent screen, revocable | None — silent account use |
| Lifetime | Short-lived + refresh, expires | Long-lived session cookie |
| Detection | Provider can see the app client | Indistinguishable from the user |
| ToS | App-policy governed | Almost certainly violates provider ToS |
| Blast radius on leak | One revocable grant | Full consumer-account takeover |
| 2FA | Provider flow enforced | Cookie bypasses 2FA entirely |

If consumer-session support is ever requested, it must be treated as a new
credential class with: a written threat model, provider ToS review, keyed
encryption at rest (never plaintext cookies), an explicit per-user opt-in
screen, session-expiry enforcement, and a revocation path. None of that exists
today, so the feature is simply not offered.

## Threat model (what the shipped code guards)

- **OAuth CSRF** — a malicious site triggers a callback with a victim's `code`.
  Mitigated by validating `state`'s user binding against the authenticated
  caller (403 on mismatch).
- **Credential theft at rest** — tokens are Fernet-encrypted when
  `BYOK_ENCRYPTION_KEY` is set (the connect flow and `LLMCredentialService`
  share that key). In dev without the key, tokens are stored plaintext with a
  loud warning — never deploy without `BYOK_ENCRYPTION_KEY`.
- **Over-broad credential use** — a subscription grant is consumed only through
  the existing BYOK routing layer, which already enforces tenant/workspace
  scoping, budget enforcement, and request logging.
- **Enumeration / brute force** — callbacks are rate-limited.

## Config

- No new env vars. Reuses `BYOK_ENCRYPTION_KEY` for token encryption.
- Provider OAuth config: `core/llm_oauth_config.py` (client id/secret, scopes,
  auth/token URLs per provider).

## Related

- `docs/architecture/LLM_GATEWAY.md` (gateway design, Phase D pointer)
- `backend/core/llm_credential_service.py` (resolution priority)
- `backend/api/llm_oauth_routes.py` (connect flow)
- `backend/alembic/versions/20260802_add_credential_type.py` (schema)
