# Cached BYOK refresh — Settings → Chat without restart

Source: employee-execution candidate (BYOK handler rebuild + discovery
backoff invalidation). This probe uses the real FastAPI app, the real
`POST /api/ai/providers/openai/keys` route the Settings UI calls, and the
normal `POST /api/chat/message` route.

## What was exercised

1. Start the app with no OpenAI key.
2. Save key A through Settings → AI.
3. Send a Chat turn without restarting; the bounded local OpenAI-compatible
   server must receive key A and the reply must be the served content.
4. Replace the key with key B through the same route.
5. Send a second Chat turn without restarting; the local server must receive
   key B and the reply must succeed.
6. Remove the key through the Settings delete route.
7. Send a third Chat turn; no new provider call may be made and the turn must
   fail closed.

The probe pins `x-atom-model: gpt-4o-mini` to the bounded local server. It uses
the normal Chat route (streaming/tool planning/interpretation defaults), not a
special execution path.

## Fixes

- `LLMService._get_handler` now compares the non-secret credential fingerprint
  of its cached `BYOKHandler` before serving a new request and rebuilds the
  handler when Settings saves, replaces or removes a key.
- `BYOKHandler.credentials_changed()` reads the runtime manager's refreshed
  key-store fingerprint (provider, key identity, environment, tenant, key
  hash, active flag — never the secret).
- `BYOKHandler.invalidate_provider_failures()` now also clears the provider
  discovery backoff, so a credential change triggers an immediate catalogue
  refresh instead of waiting for the old backoff window.

## Result

`result.json`: **passed**.

- First key seen: true.
- Replacement key seen: true.
- Provider calls after removal: unchanged (no stale credential use).
- Both key values absent from captured logs: true.
- Chat replies after first and replacement: `BYOK refresh OK`.
- Removal reply: fail-closed, no provider call.

`app.log` is the captured application log with `sk-*`, `Bearer *` and `org_*`
values redacted. `manifest.json` hashes every file.
