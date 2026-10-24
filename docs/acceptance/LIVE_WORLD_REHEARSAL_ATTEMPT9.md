# Live-world rehearsal — attempt 9 (unfiltered BYOK)

**Result: functional workflow PASSED, intended-route parity FAILED.**
The pilot was not modified; no cutover was performed.

## Identity

- Product commit `09cccb5b0b977f86c0a39d59af5b922c83143e7f`
  (the `[ingested]` prefix-neutralization fix).
- Product tree `4c7ec787c8ff1f81baa89f1cdc3c40496ef44b1f`.
- Launch/runtime commit `4bfcbc2adc3a6bb36568eef4a000c65910bb795f`, clean.
- Live gate `successor_gates_live.py` `6d66d0b8…` unchanged.
- World: the 09:19 876 MB snapshot (`quick_check=ok`; 48 users / 1022
  sessions / 5426 messages), isolated on `:8121`.
- BYOK: a **copy** of the pilot's full 13-key / 37-provider configuration
  was placed in the scratch world. The live files were read-only.

## Functional result

All 59 functional checks passed:

- L3 76.05 s: `QUARTZ-77`, verified `documents.search` receipt, no decoy.
- Edit 33.74 s: one write, postcondition verified.
- Re-ask 31.36 s: no-op `already_satisfied`, zero writes.
- S3 85.36 s: honest partial, broader obligation OPEN, truthful date.
- S7 53.63 s: date-only completed, settlement basis, restart agreement.
- `live_db_isolated=true`, `live_db_unchanged=true`,
  `pilot_untouched=true`.

## Route result — FAILED

The unfiltered BYOK exposed providers that the attempt-8 isolated store
did not contain. The actual routes were:

| Leg | Provider | Model |
|---|---|---|
| L3 reply | `openrouter` | `z-ai/glm-5.3-flash` |
| S3 reply | `opencode-go` | `glm-5.3-flash` |
| S7 reply | `opencode-go` | `glm-5.3-flash` |
| Structured interpretation | `deepseek` | `deepseek-v4-pro` |
| Edit planning | `opencode-go` | `glm-5.3-flash` |
| Tool planning | `opencode-go` | `glm-5.3-flash` |

Every outbound destination was a configured provider:

```
http://localhost:11434/v1/chat/completions                 (ollama)
https://api.deepseek.com/v1/chat/completions               (deepseek)
https://opencode.ai/zen/go/v1/chat/completions             (opencode-go)
https://openrouter.ai/api/v1/chat/completions              (openrouter)
```

There was **no unconfigured/rogue provider** destination. But the
intended reply route from the release profile was
`ollama/llama3.1:8b`, with DeepSeek as fallback. The BPC router selected
OpenCode Go/OpenRouter GLM-5.3 Flash instead; the DeepSeek edit pin did
not hold either (the log records `BPC skipped deepseek/deepseek-v4-pro —
observed structured latency 40s > interactive cap 25s`). The
`ATOM_PREFERRED_LLM_PROVIDER=ollama` preference was logged as inserted
for one completion but did not control the streaming reply.

Checks `provider_reply_parity` and `provider_allowlist_clean` are false
under the declared Ollama/DeepSeek allowlist. This is a **route/config
parity failure**, not a functional workflow failure.

## What this means

Attempt 8's 60/60 was measured with an isolated DeepSeek-only store plus
local Ollama. It is historical evidence for `cc813aeeb`; it does not
transfer to this product or to the preserved multi-provider BYOK.

The fixed code works on the real provider set. The real provider set does
not preserve the attempt-8 reply route. A cutover on this configuration
must declare OpenCode Go/OpenRouter GLM-5.3 Flash as actual routes, or
hold for a routing-containment change.

## Limits

- One rehearsal; not a reliability or latency-tail estimate.
- S3 85.36 s; L3 76.05 s.
- The route deviation is the finding of this run, not a cleared condition.
- The `[ingested]` fix removes the carrier prefix and keeps the source
  label/body; internal metadata in the body is intentionally retained so
  an answer-bearing paragraph is never deleted.

Evidence:
`release_evidence_20261024/live_world_rehearsal_attempt9/`.
