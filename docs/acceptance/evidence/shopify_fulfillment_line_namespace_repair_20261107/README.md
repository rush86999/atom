# Shopify fulfillment — separate FO-line and order-line namespaces

This is the finite repair packet for the remaining pre-effect defect found by
root at `b813c2a1f`.

- Repair commit: `eff0ff7b0`
- Current-main merge: `c37cfde0c` (merged `origin/main` `2d251acdf`)
- Pre-repair source: `b813c2a1f`
- New permanent probe (authored by root):
  `tests/test_lead_shopify_fulfillment_rest_shape.py::test_missing_order_line_identity_cannot_borrow_fulfillment_order_line_id`

Root reviewed the prior repaired source `8055fae56`. The present packet does
**not** relabel that review as a clean source test, because root added the new
probe while executing. Production bytes in this repair are `eff0ff7b0` plus the
current-main merge.

## Contract trace

Primary official FulfillmentOrder resource:
<https://shopify.dev/docs/api/admin-rest/latest/resources/fulfillmentorder>

A source `FulfillmentOrder.line_items[]` entry has two distinct namespaces:

| Field | Namespace |
| --- | --- |
| `id` | fulfillment-order line id |
| `line_item_id` | order line id |

Only `line_item_id` may bind the dispatch plan. If it is missing, the source
line has no proven order-line scope and dispatch must refuse **before** POST.

A completed `Fulfillment.line_items[]` entry is different: its documented `id`
**is** the order-line id. That valid official shape must still verify even when
no `line_item_id` is returned.

## Repair

- `ShopifyService._validate_fulfillment_order_material` now requires the source
  `line_item_id`; it no longer falls back to the FO-line `id`.
- `core.shopify_mutations` now has separate source and completed line-identity
  projections:
  - source/planning: `line_item_id` only;
  - completed/observed: `line_item_id` or the documented Fulfillment `id`.
- `create_fulfillment`'s stale docstring now names the parent-order-scoped exact
  read `GET /orders/{order_id}/fulfillments/{id}.json`.

No other fulfillment contract was relaxed. The earlier five permanent probes
and their negatives remain in place and pass.

## Failure-first and valid matrix

`run_and_capture.py` executes the existing interpreter with `TESTING=1`, a
fresh scratch SQLite URL, `ENABLE_SCHEDULER=false`, and a scratch pytest
basetemp. Only the provider HTTP leaf is doubled.

| Phase | Source | Result | Exit |
| --- | --- | --- | --- |
| `failure-first-line-namespace` | `b813c2a1f` | 1 failed | **1** |
| `exact6` | clean `c37cfde0c` | 6 passed | **0** |
| `affected` | clean `c37cfde0c` | 72 passed | **0** |

The failure phase reproduces the concrete defect: one POST was made when the
source line had only the FO-line `id`.

## Added twins

- Valid distinct-namespace source line (`id=foli-*`, `line_item_id=line-*`)
  dispatches and verifies.
- Valid completed Fulfillment line containing only `id=line-*` still verifies.
- Missing or blank source `line_item_id` refuses before POST (permanent probe +
  direct service twins).
- Contradictory completed order-line binding stays unverified.

## Preserved evidence

- Original five negatives: unchanged in
  `backend/tests/test_lead_shopify_fulfillment_rest_shape.py`.
- Previous source/evidence packet:
  `docs/acceptance/evidence/shopify_fulfillment_lead_repair_20261107/`.
- New permanent negative: root-authored probe at `b813c2a1f`, preserved
  unchanged except for being executed.

## Safety and disclosure

- No live provider, model, server, browser, account, install, spend or send
  action was made.
- No live/shared database was used; every phase used `TESTING=1` and scratch
  SQLite.
- Existing permissions/config (`opencode.jsonc`) was copied unchanged from the
  established CLI lane and contains no credentials; it is not part of this
  packet or repair.
- Root acceptance remains withheld pending independent re-verification. This
  packet is evidence, not self-acceptance.

## Finite delivery

The missing-order-line namespace defect is repaired at producer, planning,
validation, and verification boundaries, with both failure-first and valid
twins. The five earlier fulfillment contracts remain green after merging
current main.
