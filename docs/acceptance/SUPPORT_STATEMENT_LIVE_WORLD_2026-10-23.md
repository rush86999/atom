# Atom live-world pilot support statement — 2026-10-23 (refreshed 2026-10-24)

**Build:** `09cccb5b0b977f86c0a39d59af5b922c83143e7f`
**Launch/runtime:** `4bfcbc2adc3a6bb36568eef4a000c65910bb795f` (`4bfcbc2ad`)
**Scope:** single-tenant local Atom pilot on the declared configuration
**Status:** the `[ingested]` fix is functionally verified (attempt 9:
59/61; all 59 functional checks pass). Intended-route parity failed on the
preserved unfiltered BYOK. Cutover is held and **not executed**; the old
pilot `8c593e57031e` is serving.

## Supported (on this exact candidate)

The composed workflow passed with the pilot's full copied BYOK:

- sign in, upload records, get a sourced answer;
- edit a draft once and repeat without another write;
- compare a draft with its source, including an honest partial/open
  comparison instead of a fabricated match;
- ask a follow-up and reload/restart without losing or contradicting the
  saved result.

Attempt 9 latencies: L3 76.05 s, edit 33.74 s, re-ask 31.36 s, S3 85.36 s,
S7 53.63 s. `live_db_isolated=true`, `pilot_untouched=true`.

## Actual provider profile (disclosed)

The preserved unfiltered BYOK produced these actual routes:

| Leg | Actual route |
|---|---|
| L3 reply | `openrouter` / `z-ai/glm-5.3-flash` |
| S3 reply | `opencode-go` / `glm-5.3-flash` |
| S7 reply | `opencode-go` / `glm-5.3-flash` |
| Structured interpretation | `deepseek` / `deepseek-v4-pro` |
| Edit planning | `opencode-go` / `glm-5.3-flash` |
| Tool planning | `opencode-go` / `glm-5.3-flash` |

All POST destinations were configured providers. There was no
unconfigured/rogue destination, but OpenCode Go and OpenRouter were outside
the intended Ollama/DeepSeek reply profile. Attempt 8's Ollama route was an
artifact of its DeepSeek-only isolated store.

## Not claimed

- No claim that every integration/background agent/automation/marketplace/
  mobile/installation platform works.
- Not a SaaS/multi-tenant certification, security audit, or
  high-availability deployment.
- Only the declared configuration is verified. Changing providers, models,
  embeddings, deadlines, or corpus invalidates this statement until
  re-measured.
- The S3 comparison may remain partial with the broader obligation OPEN;
  that is the intended truthful behavior.
- One rehearsal is not a reliability or latency-tail estimate.
- The `[ingested]` fix removes the carrier prefix and retains the source
  label/body. Internal metadata in the body can remain visible; this is
  deliberate so an answer-bearing paragraph is never deleted. Line-numbered
  block removal remains a separate pre-existing path.
- The actual provider profile above is not the attempt-8 route; approval is
  conditional on accepting it.

## Operation / recovery

- Exact cutover, smoke, and rollback instructions: `CUTOVER_2026-10-24.md`.
- Candidate identity/config:
  `RELEASE_CANDIDATE_LIVE_WORLD_2026-10-23.md` and
  `release_evidence_20261024/cutover_09cccb5b0/release_config.json`.
- Preserve the pilot BYOK files in place. Do not use the historical
  `candidate-byok/` filtered store.
- The 09:19 backup restores but is stale; take a fresh quiescent snapshot at
  cutover.
- One backend on `:8001`, one frontend on `:3000`; no `--reload`.
- On smoke failure, restore the fresh snapshot and unchanged BYOK/env,
  restart `8c593e57031e`, and preserve evidence. Do not retry in the same
  window.

## Support boundary

Report the build identity, request text, observed answer/draft/history,
`/api/health` identity, and the actual provider/model if visible. Do not
send credentials or full private documents. This statement is revised to
“deployed” only after a successful cutover smoke on the served identity.
