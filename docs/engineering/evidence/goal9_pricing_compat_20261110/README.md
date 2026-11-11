# Goal 9 pricing compatibility — quantity-aware rates, preserved metadata

Date: 2026-11-10
Withheld source reviewed: `8deaf95159c908da56e34491685936ef419236ec`
New head: this branch's commit (append-only on PR837).
Current main integrated: `914b9470d254293369475cd9f0fecdbf76acd650` (reviewed
PR836 tree `04e6cc4e`); foundation merge also carries
`54df9f6778aa1fb4db514dc0b29fc23b5012c225` (main 230 + authoritative
Tenant/Workspace fixtures + late feedback session factory fix + both parents'
CI steps).

## Withheld findings (retained, not relabelled)

1. **Valid input-only regression**: a known row with
   `mode=embedding, input_cost_per_token=0.01, max_input_tokens=8192` and
   `100` input / `0` output returned `1.0` on 973 but the unconditional
   "BOTH rates required" guard returned `None`. Log:
   `before/root-input-only-8de-failure.log`; earlier passing run retained in
   `before/root-input-only-before.log`.
2. **Metadata erasure**: normalization skipped every row with a missing rate,
   deleting `max_input_tokens`/`max_tokens`/`mode` consumed by
   `BYOKHandler.get_context_window` and `_pinned_model_fits` (unknown row =
   pin passes; dropped row = conservative 4096 default).
3. Root's independent 8de gate was **1 failed / 6 passed**: the six invalid
   rate twins passed; the valid input-only row regressed. Retained at
   `before/root-8de-independent-negative.log` + review JSON/probes.

## Contract (quantity/operation-aware)

`DynamicPricingFetcher`:

- `rate_is_valid`: explicit, finite, non-negative, non-bool.
- **Every provided rate is validated**, even for a zero-quantity dimension.
- A rate is **required only for a positive quantity**. A legitimate
  input-only/embedding charge (positive input, zero output, absent output
  rate) keeps its known input cost; the absent rate is genuinely unused
  basis, not an invented $0 output price.
- A chat reservation has positive input and a positive output cap, so both
  rates are required there: missing/partial/bool/negative-cancelling material
  stays unknown and hard_stop refuses.
- Explicit `0/0` remains authoritative free; absence is never free.
- `estimate_cost` rejects negative/bool quantities and non-finite totals.

Normalization (LiteLLM, OpenRouter) **preserves the catalog row and
metadata**; only an invalid provided rate is omitted (never defaulted to 0).
Context/read consumers keep known windows; ranking/display consumers
(`get_cheapest_models`, `compare_providers`, cache router, provider-cost sync,
cost-estimate API) require a complete valid pair and report unknown instead
of a fabricated `$0`.

## Guarantees preserved

- Authoritative free image: a genuine `0/0` contract keeps the image route
  free (image token count cannot change a $0 cost); positive/unknown image
  requests remain explicit unknown and refuse under hard_stop.
- Structured retry per-physical-attempt admission/settlement is unchanged.
- Physical stream/chat/ordinary admission, visible-partial stop, single-flight,
  receipt/CAS and semantic feedback are unchanged.
- Both parents' and main's CI steps are preserved exactly once (23-step
  additive union; immutable baseline untouched).

## Gates (current-main integrated)

| Gate | Result | Log |
|---|---|---|
| joined main-230 + physical/pricing/structured + five root probes (current main) | **371 passed** | `after/joined-current-main.log` |
| broad current-main affected (CI lane, atomic/durable/upgrade, feedback, live factory, w57, physical/structured/pricing, all six root probes) | **300 passed** | `after/broad-current-main.log` |
| root price-material (6) + input-only compat (1) + free image (1) | pass (in the joined run) | `after/joined-current-main.log` |

No live pricing fetch/provider/model/DB/credential/spend/send/deploy or browser
campaign; scratch SQLite only (`SECRET_KEY=scratch-only-readable`).

## Boundaries

- Not claiming Goal 9 complete: authoritative streaming usage remains the next
  finite gap; SDK/integration/embedding retry inventory remains open scope.
- Ranking consumers outside this repo (third-party) may still read raw cache
  entries; only the audited in-repo consumers were changed.
- Root owns independent acceptance/merge.
