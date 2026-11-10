# Goal 9 — per-physical-attempt reservation/admission (stream, gateway, ordinary)

Date: 2026-11-10

Base: `0733a4d109edce9f4e757a7de434ecd18df32d7b` (PR835 source at branch start).
Branch: `codex/goal9-physical-attempts-20261110` in an isolated
sparse worktree (`backend`, `docs`, `.github` only).

This packet closes the **physical-attempt** gate that the atomic packet
(`docs/engineering/evidence/goal9_atomic_cap_20261110/`) recorded as OPEN. It
does not replace or relabel that packet, the original a72 negative, or the
0733 bool follow-up.

## Decision

Every actual paid transport attempt now carries its own server-owned attempt
identity, actual route binding, conservative pre-dispatch bound and durable
settlement:

- streaming initial / self-heal / paid sibling / reasoning-budget retry /
  ranked-route hop / catalogue sweep;
- gateway `chat_completion` initial / temperature-lock / self-heal / paid
  substitution / sweep;
- ordinary `generate_response` initial / temperature-lock / tier fallback /
  self-heal / paid substitution / sweep.

Accounting refusal is a **stop**, never a provider failure: it blocks the
remainder of the ladder (no hidden fallback to an unauthorized route) and
surfaces an explicit budget-authorization refusal.

### Reused mechanism (no new store/router/engine)

`backend/core/spend_aggregation_service.py` remains the single ledger:
`begin_llm_usage` (pre-dispatch intent/reservation, hard-stop admission),
`record_llm_usage` (actual/unknown settlement, idempotent attempt key, CAS on
the immutable binding). The new byok helpers are thin adapters:

- `_admit_physical_attempt` — computes the bound from the ACTUAL serialized
  payload (messages/roles/tool-call shape/request body) and the request's real
  output cap, then calls `begin_llm_usage(enforce_budget=True)`.
- `_settle_physical_response` — settles one response under its exact attempt
  id (actual usage when exposed; explicit unknown otherwise).
- `_settle_stream_attempt` — streaming has no authoritative usage on this
  path, so a successful stream settles as explicit unknown liability (the
  conservative reservation stays on the ledger) unless the bound was
  authoritative numeric `0.0`, which settles free.

### Identity and binding

- One request-owned identity: the router decision id when present, else a
  generated id. `_StreamRequestState` carries `request_id`/`attempt_seq`
  across nested stream frames; `chat_completion` passes the same id and a
  shared sequence through the sweep.
- Attempt id = `f"{request_id}:{n}"`, monotonic per request across every
  nested dispatch. A nested retry (different model, different body) can never
  reuse another route's authorization.
- Existing scope/route binding is unchanged; a mismatch still refuses.

### Bound policy

- A retry with a larger output cap (reasoning-budget retry) gets a larger
  bound because the bound uses that attempt's actual `max_tokens`.
- A free→paid substitution reserves against the PAID model with the paid
  request body; the free attempt keeps its own retryable liability.
- A failed physical attempt keeps its active reservation (may have charged);
  settlement is never fabricated as zero. Mid-stream partial output stops the
  request exactly as before (`state.visible_yielded`) and never replays.
- Preserved: `attempted_pairs`, `self_heal_used`, `paid_retry_used`,
  `sweep_consumed`, one outer retry owner, strict pins/local-only/provider
  policy gates, and the existing `generate_response`/`chat_completion`
  fallback shape. No fallback is blanket-disabled; valid free/local/observe
  behavior is untouched.

## SDK retries audited (hidden physical requests)

The handler constructs `OpenAI`/`AsyncOpenAI` clients without `max_retries`,
so the SDK default (2) issued hidden retries for connection errors,
408/409/429 and 5xx — physical requests no reservation covered, and a second
retry owner. Every handler client construction (lux sync/async, ollama
sync/async, the shared provider kwargs, registered-local sync/async) now sets
`max_retries=_SDK_MAX_RETRIES = 0`. One admitted attempt is one HTTP request;
the application's provider/model ladder remains the single retry owner. A
bounded source contract pins the constant and all seven construction sites.

## Token bound (authoritative, tokenizer-agnostic)

The reviewed finite prerequisite contract (root commit `4559f24a`,
PR835 head `ba2a1acd`) is incorporated in the new helper **without replacing
it or blind-cherry-picking**:

- `core.llm.prompt_budget.count_tokens` returns `(token_count, estimated)`.
  `estimated=True` is a chars/4 heuristic — never a bound. Both flag values
  now keep the UTF-8 byte floor (`max(counter_count, utf8_bytes)`).
- No provider/brand regex is treated as tokenizer proof. `o200k` is not
  mathematically monotone against `cl100k`, and a provider id is not a model
  contract, so no brand mapping is used.
- Supported byte/char-aligned text tokenizers emit at most one token per
  input byte, so UTF-8 bytes is a conservative upper bound for text. This can
  over-reserve; under hard_stop that can refuse near the cap, which is the
  safe direction.
- The bound covers the serialized payload (roles, tool-call/function shape,
  stop/extra body) plus schema text, the request output cap, and a fixed
  message/overhead allowance.
- **Multimodal**: there is no proven upper bound for an arbitrary
  image/resolution/provider combination, so an image request is admitted with
  an explicit UNKNOWN bound. Under hard_stop that refuses **before dispatch**
  with the standard unpriced-usage refusal; no fixed per-image token
  allowance is fabricated. Observe/no-limit modes still dispatch and retain
  unknown liability.

### Research anchors (primary)

- tiktoken is a byte-level BPE tokenizer; encoding data is published per
  vocabulary (`cl100k_base` 100,256 entries, `o200k_base` 199,998):
  https://github.com/tryAGI/Tiktoken/blob/main/data/README.md and
  https://tokenreference.com/tokenizers/cl100k_base
- LiteLLM token counting uses a **model-specific** tokenizer and falls back
  to tiktoken when a model-specific one is unavailable — i.e. generic
  tiktoken is a fallback, not proof for an arbitrary served model:
  https://docs.litellm.ai/docs/completion/token_usage
- OpenAI image token cost depends on model, dimensions and detail level
  (tiles/patches, resize budgets), which is why no fixed per-image allowance
  is claimed:
  https://developers.openai.com/api/docs/guides/images-vision

## Evidence

- `gates/physical-controls.log` — the new failure-first matrix: **26 passed**
  on this successor (12 of these failed on the frozen `0733` source; exact
  log retained at `retained_negative/pre-fix-physical-negative.log`).
- `gates/focused.log` — physical controls + stream retry-state + P2 fallbacks
  + atomic/ordinary controls + durable settlement/upgrade + CI-lane contract:
  **269 passed**.
- `gates/affected.log` — focused set plus the wider budget selection:
  **479 passed**.
- `gates/root-prerequisite-probes.log` — root's invalid-price (5), direct
  bound (5) and estimated-flag (1) probes on this source: **11 passed**.
- `gates/ci-lane-contract.log` — additive CI ledger contract after adding the
  new gate: **27 passed**.

The retained negative is the same test module run against `0733` before any
source change: `tests/test_goal9_physical_attempts.py` → **12 failed,
11 passed** (second provider dispatched at cap; one request-level row for
nested retries; no stream settlement; tiktoken-based under-bound).

## CI

A normal additive CI step runs the new matrix:
`Run per-physical-attempt reservation controls` in
`.github/workflows/ci.yml`, declared exactly once in
`backend/tests/fixtures/ci_backend_additions.json`. The immutable pre-parallel
ledger and every existing command/environment/setup are preserved.

## Scope / honest limits

- Scratch SQLite + doubled transport only. No live provider/model/DB,
  credential, send, spend or deploy; no dependencies; no new store/router/
  engine; PostgreSQL concurrency remains implemented but not runtime-qualified.
- Streaming usage is not authoritative on this path, so successful streams
  settle as unknown liability rather than a fabricated priced amount.
- Multimodal requests have no proven image bound; hard_stop refuses them.
  This is explicit, not a claimed strict cap.
- Nested retries inside the older `generate_structured_response` cascade are
  out of this finite slice (that path already has its own pre-dispatch
  reservation); they remain a follow-up audit if root requires parity.
- SDK-internal retries are disabled for the handler's clients, but any client
  constructed elsewhere (embedding services, integrations) was not audited in
  this slice.
- Root owns independent review/acceptance/merge. Historical 143 claims /
  18 goals are unchanged.

## Prompt-injection note

No untrusted document/email/web content was executed as instruction in this
slice. The doubled transports are test fakes; no external content was fetched.
