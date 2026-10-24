# Live-world release candidate — 2026-10-23 (refreshed 2026-10-24)

**Status: the `[ingested]` fix is functionally verified, but intended-route
parity FAILED on the preserved unfiltered BYOK. Cutover is NOT authorized
and NOT executed. The old pilot `8c593e57031e` is still serving.**

This supersedes the `cc813aeeb` attempt-8 candidate. Attempt 8 remains
historical evidence for that exact product; its 60/60 is not transferred to
the changed code.

## Exact identity

| Item | Value |
|---|---|
| Product commit | `09cccb5b0b977f86c0a39d59af5b922c83143e7f` |
| Product tree | `4c7ec787c8ff1f81baa89f1cdc3c40496ef44b1f` |
| Rehearsal/launch commit | `4bfcbc2adc3a6bb36568eef4a000c65910bb795f`, clean |
| Product diff, launch vs pin | none in `backend/core` / `backend/integrations` |
| Staged release tree | `…/opencode/atom-release-09cccb5b0-20261024` (HEAD `4bfcbc2ad`, clean) |
| Staged backend health | 200; `revision=4bfcbc2ad`, `dirty=false` |
| Frontend source tree | `0d48f0b863ba3069526006ed29441099df435c71` (unchanged) |
| Frontend build | Next 16.2.2 webpack, Node 20.19.6, npm 10.8.2, `BUILD_ID=VHwW5YQ_s140w5s6u7HWl` |
| Interpreter | `/Users/rushiparikh/projects/atom/backend/venv314/bin/python` 3.14.7 |
| Live gate | `successor_gates_live.py` `6d66d0b8b3b2c9a24efbe111a750c477f623a207d34692dcd4fa07cfceb88dd2` |
| Serving pilot (hold) | `8c593e57031e` clean, `:8001` pid 16055; frontend `:3000` pid 16488 |
| Rollback snapshot | the 09:19 backup restores but is stale; a fresh quiescent snapshot is required at cutover |

## Verification (attempt 9)

Evidence: `LIVE_WORLD_REHEARSAL_ATTEMPT9.md` and
`release_evidence_20261024/live_world_rehearsal_attempt9/`.

- **59/61 checks true.** All 59 functional workflow checks passed:
  L3 76.05 s (`QUARTZ-77`, documents receipt, no decoy), edit 33.74 s
  (one write), re-ask 31.36 s (no-op, zero writes), S3 85.36 s (honest
  partial, broader obligation OPEN), S7 53.63 s (date-only, restart
  agreement).
- The two failing checks are both route checks:
  `provider_reply_parity` and `provider_allowlist_clean` under the declared
  Ollama/DeepSeek allowlist.
- `live_db_isolated=true`, `live_db_unchanged=true`,
  `pilot_untouched=true`.
- BYOK: full 13-key / 37-provider configuration copied into the isolated
  world; live files read-only.

### Actual routes (important)

| Leg | Actual provider/model |
|---|---|
| L3 reply | `openrouter` / `z-ai/glm-5.3-flash` |
| S3 reply | `opencode-go` / `glm-5.3-flash` |
| S7 reply | `opencode-go` / `glm-5.3-flash` |
| Structured interpretation | `deepseek` / `deepseek-v4-pro` |
| Edit planning | `opencode-go` / `glm-5.3-flash` |
| Tool planning | `opencode-go` / `glm-5.3-flash` |

Every POST destination was a configured provider: DeepSeek, local Ollama,
OpenCode Go, OpenRouter. There was no unconfigured/rogue destination. But
the intended reply route was Ollama, with DeepSeek fallback; the BPC router
selected OpenCode Go/OpenRouter GLM-5.3 Flash. The DeepSeek edit pin did not
hold (`BPC skipped deepseek/deepseek-v4-pro — observed structured latency
40s > interactive cap 25s`).

This is a route/config parity failure, not a functional workflow failure.
Attempt 8's Ollama reply route was an artifact of its DeepSeek-only
isolated credential store and is not reproduced by the preserved BYOK.

## Delta fix

`DELTA_FIX_REVIEW_09CCCB5B0_2026-10-24.md`: independent review verdict
**APPROVE WITH COMMENTS**. The `[ingested]` path no longer deletes
paragraphs. It removes only a positively identified carrier prefix and
keeps the source label and body. Ordinary quotations, marker mentions,
explanatory prose, mismatched markers, and explicit quote requests are
preserved. Line-numbered removal remains a separate pre-existing path with
answer-value/decoy/short-remainder guards.

## Configuration the request would run

- Existing pilot BYOK files are preserved in place. The historical
  `candidate-byok/` filtered store is not used.
- Additive flags: `ATOM_TURN_INTERPRETATION=1`,
  `ATOM_TURN_INTERPRET_PIN=deepseek:deepseek-v4-pro`,
  `ATOM_TURN_INTERPRET_CAPTURE=1`, `ATOM_TURN_DECISION_ROUTING=1`,
  `ATOM_ASYNC_EDIT_PLAN_MODEL=deepseek/deepseek-v4-pro`,
  `ATOM_PREFERRED_LLM_PROVIDER=ollama`,
  `ATOM_PREFERRED_LLM_MODEL=llama3.1:8b`.
- Preserve `CHAT_FINALIZATION_M1=1`, `CHAT_FINALIZATION_M2=1`,
  `ATOM_TASK_LIFECYCLE_ENABLED=1`,
  `ATOM_STREAM_FALLBACK_RESERVE_SECONDS=70`, and the existing origins.
- Intended routes: Ollama reply, DeepSeek structured.
- Actual observed routes: OpenCode Go/OpenRouter GLM-5.3 Flash replies,
  OpenCode Go edit/tool planning, DeepSeek interpretation.
- Allowed fallback set for the smoke: the configured providers
  (`deepseek`, `ollama`, `opencode-go`, `openrouter`). Any other
  destination is a failure.

Exact JSON: `release_evidence_20261024/cutover_09cccb5b0/release_config.json`.

## Cutover (prepared, not executed)

The procedure is `CUTOVER_2026-10-24.md`. It requires a fresh quiescent
snapshot, narrowly owned shutdown, a served sourced-answer/edit/no-op
smoke, restart agreement, actual-route recording, and rollback on any
failure. The cutover request is `CUTOVER_APPROVAL_2026-10-24.md` and is
explicitly conditional on accepting the actual provider profile.

## Limits

- One rehearsal; not a reliability or latency-tail estimate. L3 76.05 s,
  S3 85.36 s.
- The route deviation is unresolved; the owner must accept it or withhold
  for routing containment.
- The `[ingested]` fix retains the source label/body, so internal metadata
  in the body can remain visible; this is deliberate to avoid deleting an
  answer.
- No SaaS/multi-tenant, security, or high-availability certification.

## Hold

The hold remains in force. No cutover has been executed for
`09cccb5b0`; the serving pilot is still `8c593e57031e`.

Support statement: `SUPPORT_STATEMENT_LIVE_WORLD_2026-10-23.md`.
