# fix(shopify): keep FO-line and order-line identity namespaces separate

## Why

Root's new permanent probe at `b813c2a1f` reproduced the remaining pre-effect
defect: a source `FulfillmentOrder.line_items[]` entry without `line_item_id`
borrowed the FO-line `id` and dispatched a fulfillment.

Per the official FulfillmentOrder resource, those are distinct namespaces:

- `line_items[].id` — fulfillment-order line id
- `line_items[].line_item_id` — order line id

Only `line_item_id` proves order-line scope. Missing it must refuse **before**
POST with zero effect.

A completed `Fulfillment.line_items[].id` is different: it **is** the order-line
id, so the documented completed shape must still verify when `line_item_id` is
absent.

## What changed

- Source preflight now requires `line_item_id`; it never falls back to the
  FO-line `id`.
- Planning/source and observed/completed line identities are projected through
  separate helpers ("source uses line_item_id only"; "completed uses
  line_item_id or documented Fulfillment id").
- `create_fulfillment`'s stale docstring now names the parent-order-scoped exact
  read: `GET /orders/{order_id}/fulfillments/{id}.json`.
- Added valid distinct-namespace, missing-source-binding, and
  contradictory-completed-binding twins.
- Merged current `origin/main` (`2d251acdf`) normally; all prior five
  fulfillment contracts, product formatter, and Article publication repairs are
  preserved.

## Verification

Actual processes on clean committed source `c37cfde0c`:

| Phase | Result | Exit |
| --- | --- | --- |
| Failure-first on `b813c2a1f` | 1 failed | **1** |
| Exact permanent controls | 6 passed | **0** |
| Affected contract/caller controls | 72 passed | **0** |

Only `ShopifyService.http` is doubled. Every phase used `TESTING=1`, a fresh
scratch SQLite database, and no live provider/model/server/browser/account/
credential/spend/install action.

Evidence:
`docs/acceptance/evidence/shopify_fulfillment_line_namespace_repair_20261107/`

Prior root-reviewed packet is preserved unchanged:
`docs/acceptance/evidence/shopify_fulfillment_lead_repair_20261107/`

Root acceptance remains withheld pending independent re-verification.

## Finite delivery

This closes the concrete missing-order-line namespace defect without weakening
the five original fulfillment controls or forbidding the correct official
completed Fulfillment line shape.
