# Physical attempts successor — configured free image + price material + structured parity

Date: 2026-11-10
Base: `973bea2f52f47c589b28e938f1771bb1709a1a39` (frozen physical delivery,
PR837). New worktree only; the frozen 973 worktree/packet are untouched.

This successor closes the three open items the physical packet recorded, after
root's independent review withheld the free-image control:

1. configured **numeric-zero** image requests were refused because
   `_admit_physical_attempt` replaced every image bound with `None`;
2. `bound == 0` was not yet a trustworthy "free" signal because the real
   `DynamicPricingFetcher.estimate_cost` fabricated `0` from invalid price
   material (missing rates, partial rates, bools, negative cancellation);
3. the structured (`instructor`) cascade's re-issues needed the same
   per-physical-attempt admission contract (payload/schema bound, multimodal
   policy, accounting stop).

No live pricing fetch, provider, model, credential, spend, send or deploy was
used. Scratch SQLite + doubled transport only.

## Root negatives (retained; not relabelled)

- `before/root-free-image-negative.log` — frozen 973 physical gate:
  **1 failed / 32 passed**; the configured numeric-zero image request was
  refused. Probe retained at `before/root-free-image-probe.py`.
- `before/root-price-material-negative.log` + `.json` + probe — the REAL
  `estimate_cost` on frozen 973 returned `0` for four invalid materials:
  missing both rates, missing one rate, `False/False`, negative input +
  positive output cancelling. **4 failed / 2 valid twins passed**.
- `before/pre-existing-missing-tenant-structured.log` — a structured
  dispatch-policy control that already fails at 973 because its scratch DB
  lacks the named tenant rows (same pre-existing fixture class root repaired
  in the budget join). It is retained honestly, not claimed as this
  successor's regression and not weakened.

## Fix 1 — price material is explicit or unknown

`DynamicPricingFetcher.rates_are_material` requires BOTH per-token rates to be
present, non-bool, finite and non-negative. `estimate_cost` returns `None`
unless that holds; an explicit `0/0` remains authoritative free and a positive
pair still prices. Fetch normalization for LiteLLM and OpenRouter now **skips**
entries with missing/invalid rates instead of caching them as `$0`. No
brand/model-name guess, no image-token heuristic.

This makes `bound == 0.0` a genuine price-contract answer rather than an
artifact of `.get(rate, 0)` or arithmetic cancellation.

## Fix 2 — authoritative free image route

`_admit_physical_attempt` keeps the text bound for an image request when it is
exactly `0.0` (authoritative numeric-zero pricing: any image token count still
costs 0). Every other image request keeps the explicit-unknown path: hard_stop
refuses before dispatch, observe/no-limit retains unknown liability. Settlement
uses the same distinction (`_image_cost_is_unknown`), so a genuinely free image
settles `free`/`settled` and a priced image never fabricates a cost.

## Fix 3 — structured retry parity

`generate_structured_response` now admits each physical re-issue through
`_admit_physical_attempt` with the actual payload/schema/this attempt's cap,
maps accounting refusal to `_DurableUsageIntentUnavailable` (the cascade stops;
no silent re-dispatch), applies the image free/unknown policy, and settles with
`known_free`/`durable_unknown` so a no-usage free attempt settles free instead
of uncertain. The existing fresh attempt id per recovery iteration is retained.

## Gates

| Gate | Result | Log |
|---|---|---|
| physical + structured + pricing + atomic/durable/upgrade + structured consumers + CI lane + all five root counterprobes | **380 passed** | `after/gates.log` |
| root counterprobes after (free image, price material, invalid price, direct bound, estimated flag) | **18 passed** | `after/root-counterprobes-after.log` |
| CI-lane contract after additive step update | **27 passed** | `after/ci-lane.log` |

Included controls: 35 physical (32 prior + 3 zero-image/paid-image), 3
structured attempt, 10 pricing-material, and the prior atomic/durable/ordinary
sets. `test_structured_dispatch_policy.py`'s pre-existing missing-tenant
failure is recorded in `before/` and excluded from the green count.

## CI

The existing additive step `Run per-physical-attempt reservation controls` now
runs the physical, structured and pricing-material suites; it remains declared
exactly once in `backend/tests/fixtures/ci_backend_additions.json`. The
immutable pre-parallel ledger and all existing steps are preserved
(CI-lane contract passes).

## Boundaries

- Still not claimed: universal strict-cap coverage for every SDK/transport
  retry outside the handler, authoritative streaming usage, PostgreSQL runtime
  concurrency, or provider image token accounting.
- The 54df main-230/live-factory foundation is not merged into this physical
  branch; when PR837 lands after PR835 it inherits it. Nothing here drops the
  live-session-factory fix, the joined CI steps or the authoritative scratch
  fixtures.
- Root owns independent acceptance/merge.
