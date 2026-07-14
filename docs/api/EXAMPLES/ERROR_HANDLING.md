# Error Handling

How Atom's API reports errors, and how to handle them as a client.

> **Important:** Atom uses two conventions. The dominant one is FastAPI's native
> `{"detail": "..."}` shape. A few flows return business-level errors on HTTP 200
> (chat's `no_llm_provider`, federation's `allowed: false`) — **always inspect the
> body, not just the status code.**

## The error envelope

Most errors use FastAPI's native shape:

```json
{"detail": "<human-readable message>"}
```

Unhandled exceptions are caught by a global handler and return:

```json
{
  "detail": "An internal server error occurred. Please try again.",
  "path": "/api/chat/message"
}
```

## Status code reference

| Status | Meaning | Body shape |
|--------|---------|------------|
| 400 | Bad request (blocked by input validation) | `{"error": "Invalid request parameters"}` |
| 401 | Missing/invalid token or bad credentials | `{"detail": "...", }` + `WWW-Authenticate: Bearer` |
| 403 | Forbidden (wrong owner, CSRF) | `{"detail": "Access denied"}` |
| 404 | Resource not found | `{"detail": "Session not found"}` |
| 422 | Validation error | `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` |
| 429 | Rate limited | `{"error": "Rate limit exceeded", "detail": "...", "retry_after": N}` |
| 500 | Unhandled server error | `{"detail": "...", "path": "/..."}` |
| 200 | Business error (chat/federation) | see below |

## Authentication errors

### Bad credentials

```bash
curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"user@example.com","password":"wrong"}' -i
```

```
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer
content-type: application/json

{"detail": "Incorrect username or password"}
```

### Missing or expired token

Any authenticated endpoint returns the same generic message for a missing,
malformed, or expired token — there is no distinct "expired" code:

```bash
curl -s http://localhost:8000/api/chat/sessions -i
```

```
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer

{"detail": "Could not validate credentials"}
```

**Client handling:** on 401, discard the cached token and re-authenticate (or
redirect to login). Don't try to distinguish expiry from invalidity — just
re-login.

### 2FA required

Login for a 2FA-enabled account returns **200** (not an error) prompting for the
code:

```json
{
  "two_factor_required": true,
  "user_id": "...",
  "email": "user@example.com",
  "message": "Two-factor authentication required"
}
```

Retry the same endpoint with `totp_code` included.

## Rate limiting

Atom enforces per-minute and per-day limits (default 120 rpm / 5000 rpd for
tenants). When exceeded:

```bash
# Hit the limit, then one more:
for i in $(seq 1 130); do curl -s -o /dev/null -w "%{http_code} " \
  -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/chat/sessions; done
```

```
HTTP/1.1 429 Too Many Requests
Retry-After: 42
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1720000000

{
  "error": "Rate limit exceeded",
  "detail": "Per-minute limit exceeded",
  "retry_after": 42
}
```

**Client handling:** honor `Retry-After` (or `retry_after` in the body). The
value is seconds until the window resets. For the daily cap, `detail` is
`"Daily limit exceeded"` and `retry_after` can be up to 86400.

## Validation errors (422)

Missing a required field — FastAPI's default Pydantic shape:

```bash
curl -s -X POST http://localhost:8000/api/chat/message \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"default_user","session_id":"new","context":{}}' -i
```

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "message"],
      "msg": "Field required",
      "input": {"user_id": "default_user", "session_id": "new", "context": {}}
    }
  ]
}
```

Manual validation produces a **string** detail (not an array):

```bash
curl -s -X POST http://localhost:8000/api/chat/feedback \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message_id":"msg_1","feedback":"bad_value"}'
```

```json
{"detail": "feedback must be 'thumbs_up' or 'thumbs_down'"}
```

## Business errors on HTTP 200

### No LLM provider configured

Chat returns a **200** with a recoverable error shape when no AI provider is
configured — this is not an HTTP error, it's a user-actionable state:

```bash
curl -s -X POST http://localhost:8000/api/chat/message \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello","user_id":"default_user","session_id":"new","context":{}}'
```

```json
{
  "success": false,
  "error_code": "no_llm_provider",
  "message": "You need an AI provider to use chat. Add an API key in Settings to get started.",
  "recovery_url": "/settings/ai",
  "session_id": "unknown"
}
```

**Client handling:** check `success === false` and `error_code` before treating
a chat response as successful. Direct the user to `recovery_url`.

### Federation access denied

Federation `/verify` always returns **200** with a decision body — denial is not
an error status:

```json
{
  "allowed": false,
  "reason": "policy_violation",
  "security_level": "none"
}
```

Possible `reason` values: `valid_credentials`, `insufficient_permissions`,
`expired_credential`, `revoked_credential`, `anomaly_detected`,
`unknown_identity`, `invalid_signature`, `policy_violation`, `rate_limited`.

**Client handling:** branch on `allowed`, not on status code.

## Authorization errors (403)

Session ownership is enforced — accessing another user's session returns a
deliberately non-revealing 403:

```bash
curl -s http://localhost:8000/api/chat/sessions/<other_user_session> \
  -H "Authorization: Bearer $TOKEN"
```

```json
{"detail": "Access denied"}
```

The same message is returned whether the session doesn't exist or belongs to
someone else, to prevent enumeration. Note: history lookup lazy-creates a new
session for the caller rather than 404-ing.

## CSRF errors

State-changing requests using cookie auth require a CSRF token. Bearer-token
requests are exempt. A missing/invalid token returns:

```json
{"error": {"type": "csrf_token_invalid", "message": "Invalid or missing CSRF token"}}
```

(status 403). **Client handling:** if you're using cookie auth, fetch the CSRF
token from the cookie/meta tag and include it in the `X-CSRF-Token` header. If
you're using `Authorization: Bearer`, CSRF does not apply.

## Circuit breaker (integration layer)

When a downstream integration (e.g. an LLM provider or external API) is failing
repeatedly, Atom's `IntegrationHTTP` wrapper opens a circuit breaker and returns
a synthetic **503** for that integration:

```
Circuit breaker open for <integration_name>
```

This surfaces to the client as a 500/503 from the wrapping endpoint. The circuit
auto-resets after a cooldown. **Client handling:** treat repeated 5xx from a
specific integration as degraded-mode; fall back to a different provider if
available.

The wrapper also transparently retries:
- **429** from upstream → respects `Retry-After` (capped at 300s), up to 3 retries
- **500/502/503/504** → exponential backoff, up to 3 retries
- **401** → triggers a one-shot token refresh, then retries

So a single client request may absorb several upstream failures before surfacing.

## Robust client pattern

```python
import httpx, time

def chat(token, message, session="new"):
    r = httpx.post(
        "http://localhost:8000/api/chat/message",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"message": message, "user_id": "default_user", "session_id": session, "context": {}},
        timeout=60.0,
    )

    # 401 → re-authenticate
    if r.status_code == 401:
        raise AuthExpired()

    # 429 → honor Retry-After
    if r.status_code == 429:
        wait = int(r.headers.get("Retry-After", r.json().get("retry_after", 5)))
        time.sleep(wait)
        return chat(token, message, session)

    # 5xx → retry with backoff
    if r.status_code >= 500:
        raise ServerError(r.json().get("detail"))

    body = r.json()

    # Business error on 200 — no provider configured
    if body.get("success") is False and body.get("error_code") == "no_llm_provider":
        raise ProviderMissing(body["recovery_url"])

    return body
```

Key principles:
1. **Don't rely on status alone** — check `success`/`error_code` for chat and
   `allowed` for federation.
2. **Honor `Retry-After`** on 429 — it's authoritative.
3. **Re-authenticate on 401** — don't retry the same token.
4. **Treat 403 as terminal** for that resource — it's ownership/CSRF, not transient.
5. **Let 5xx retry** with backoff — the integration layer already retried
   upstream failures, so a surfaced 5xx means sustained degradation.
