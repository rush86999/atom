# Settings → save key → Chat on normal routing

The earlier BYOK acceptance pinned `x-atom-model: gpt-4o-mini` to the bounded
local provider. That proved the credential-refresh fix but not the normal chat
journey: with a catalogue that advertised too few models, the router selected a
model the provider did not serve (`catalog_not_in_provider`) and the turn had no
dispatchable route.

This run removes the pin entirely (`BYOK_PROBE_PIN` unset) and advertises the
models the router actually selects. Normal routing served:

- key A → `gpt-4o-mini` → reply `BYOK refresh OK`;
- replacement key B → `gpt-5.6-luna` / `o4-mini` → reply `BYOK refresh OK`;
- deletion → no new provider call, turn fails closed.

Both keys were seen by the provider; neither appears in the captured log.

**Scope:** bounded local OpenAI-compatible provider, not a real OpenAI account.
It is the same normal Settings key route and normal `/api/chat/message` route a
user hits; no execution path was special-cased.

`result.json` is the probe output; `app.log` is the sanitized application log.
