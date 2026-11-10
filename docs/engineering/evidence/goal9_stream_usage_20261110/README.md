# Goal 9 — authoritative stream usage when the provider supplies it

Date: 2026-11-10
Lineage: `8deaf951` → pricing-compat successor → current main `914b9470`
(foundation `54df9f67`).

## Scope

Streaming never requested `stream_options.include_usage`, but some providers
still emit a terminal usage chunk. The physical slice settled every successful
stream as explicit UNKNOWN because the chunk was ignored. This finite change
records that report **only when it is complete**, on the SAME `TokenUsage`
ledger and the SAME attempt identity.

## Contract

- **Complete** terminal usage (`prompt_tokens`/`input_tokens` AND
  `completion_tokens`/`output_tokens` present, non-negative ints): the attempt
  settles with those authoritative token counts. Cost is the configured price
  when usable; if the model price is genuinely unknown, the tokens are still
  recorded and the cost stays `None` with the reservation retained.
- **Absent or partial** usage: unchanged explicit unknown liability
  (`reserved` kept, status `uncertain`); a partial report is never read as
  zero tokens.
- **Zero-token terminal report** on a priced model is treated as unknown, not
  a fabricated free settlement.
- **Authoritative numeric-zero bound** remains the only trusted free case.
- **Visible-delta failure** (transport drop, cancellation) still returns the
  partial answer without replay and keeps the reservation; a usage chunk seen
  before a failure does not settle a failed attempt.
- **Retries** settle their own attempt id only; a failed first provider's
  reservation is not settled by the second provider's usage.
- No request-shape change: usage is captured only if the provider sends it.
  No replay after a visible delta; `_StreamRequestState`, single-flight,
  receipt/CAS and semantic feedback are untouched. No new ledger/store/router.

## Doubled controls (`after/stream-usage-controls.log`, 6 tests)

| Case | Expected |
|---|---|
| complete terminal usage + usable price | settled priced, exact tokens, reserved released |
| absent usage | unknown/uncertain, reservation retained |
| partial usage (prompt only) | unknown/uncertain, zero tokens recorded |
| visible partial then mid-stream failure | partial returned, no replay, attempt stays active |
| two-provider retry | failed attempt active; second settles its own row/priced |
| complete usage + genuinely unknown price | tokens recorded, cost unknown, liability kept |

## Gates

| Gate | Result | Log |
|---|---|---|
| stream usage + retry-state + physical/pricing/structured + CI lane + root pricing/free-image probes | **119 passed** | `after/focused-stream-pricing.log` |
| stream consumers (f6 orchestrator, deepseek harness, w57, P2 fallbacks, ordinary CI, durable settlement) | **105 passed** | `after/broad-stream-consumers.log` |

Scratch SQLite + doubled transport only; no live provider/model/pricing
fetch/DB/credential/spend/send/deploy.

## Not claimed

- Providers that never supply usage remain unknown by design; the
  reservation is retained rather than released.
- Provider-side image-token accounting and PostgreSQL concurrency remain open.
- Goal 9 is not complete: the SDK/integration/embedding retry inventory is the
  next mapped scope (concrete caller map first, bounded repair only where a
  traced defect is proven).
