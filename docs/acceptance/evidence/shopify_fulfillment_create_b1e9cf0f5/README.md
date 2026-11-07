# Shopify fulfillment create — registered exact-id/dispatch Oracle

Exact implementation source: `b1e9cf0f5` on
`codex/shopify-fulfillment-oracle-20261107`, based on the independently
reviewed article delivery `9171412c4`.

Root Decimal-context formatter/test fixes `e359b5ac7` (prerequisites
`4e0ead635`, then `00979657d`) are **not integrated** on this isolated branch.
Their `_normalized_number` lines were not modified.

## Contract trace before design

The current Shopify Admin REST contract used by the code:

- create: `POST /admin/api/{version}/fulfillments.json` with
  `line_items_by_fulfillment_order` / `tracking_info`;
- exact readback: `GET /admin/api/{version}/fulfillments/{fulfillment_id}.json`;
- fulfillment orders: `GET /admin/api/{version}/orders/{order_id}/fulfillment_orders.json`.

https://shopify.dev/docs/api/admin-rest/2026-07/resources/fulfillment

The retired order-scoped fulfillment **write** (`POST /orders/{id}/fulfillments.json`)
is not used. The controls assert the POST is `/fulfillments.json` and not the
legacy order-scoped write.

A single fulfillment is per-location. The predecessor service combined
actionable fulfillment orders across locations in one request. It now refuses
that as a pre-effect 422 (`ambiguous_fulfillment_location`) unless `location_id`
selects one location. This is a contract repair, disclosed here and in the
commit; existing caller tests have negative and valid compatibility twins.

`notify_customer` remains part of the frozen request binding (it changes the
logical operation/request digest) but is not readback material: Shopify does
not return it on the Fulfillment resource. It is therefore documented as an
input preference, not silently dropped from the digest.

## Failure first

The predecessor handler returned the raw create response:

```python
fulfillment = await ShopifyService().create_fulfillment(...)
return {"success": True, "fulfillment": fulfillment}
```

It retained no exact id, did not re-read the resource, did not bind the
server-resolved fulfillment-order/line-item/quantity set, and could not verify
order/location/tracking material. Under the real Generic consumer it was
honestly uncertain. `failure-first.log` captures that against `HEAD^`:
**37 failed, 5 passed, exit 1**. The passing controls are the already-honest
lost-confirmation and negative-only cases.

## Implementation

Existing registry / Generic durable claim / shared Oracle / domain-neutral
receipt projector machinery is reused; no new operation engine, store or
router was added.

- `core/action_registry.py`: refuses missing/foreign/moved/inactive/ambiguous
  stores, body store or credential selectors, and a missing `order_id` before
  transport. Schema text now states the per-location rule.
- `core/shopify_mutations.py`:
  - authorized material: `order_id` plus optional `location_id`,
    `tracking_number`, `tracking_company`;
  - server-derived dispatch plan: exact fulfillment-order ids, line-item ids
    and quantities resolved from the current fulfillment orders immediately
    before the POST;
  - producer: creates through `ShopifyService`, reads the exact returned id
    back with `get_fulfillment`, and reports `uncertain` on missing/contradictory
    readback;
  - durable projector/matcher stores the authorized material and dispatch plan,
    so same-operation replay compares the current readback with the exact
    original dispatch.
- `integrations/shopify_service.py`: current `get_fulfillment` by exact id,
  `meta_out` dispatch capture, preflight vs dispatch exception separation, and
  multi-location refusal. `create_fulfillment` still returns the fulfillment
  dict for existing callers.
- `core/oracle/postcondition_verifiers.py`: independent verifier requires the
  frozen operation/request digest, provider receipt, exact remote id, same
  current store, a fresh exact-id fulfillment readback, authorized material,
  and the dispatch plan. Missing/changed/unavailable proof stays unverified.
- `core/oracle/request_expectations.py` + `core/connected_actions.py`: freeze
  and bind the same order/location/tracking/notify request.

## Controls

`backend/tests/test_oracle_shopify_fulfillment_create.py` joins the REAL
registered action, REAL Generic durable claim, REAL ShopifyService methods and
REAL shared Oracle. Only `ShopifyService.http` is doubled. Covered:

- exact create: current POST URL, exact id, current store, order, location,
  tracking, fulfillment-order ids, line-item ids and quantities;
- missing/foreign/moved/inactive/ambiguous store, selectors, missing order id,
  no fulfillable orders, multi-location ambiguity, and location filtering —
  all refused before POST;
- wrong returned id; wrong order/tracking/company/location; changed/removed
  fulfillment-order/line-item/quantity; missing tracking proof;
- absent/contradictory readback and unidentifiable effect;
- same-operation replay and process-style restart: one POST total,
  `already_applied`;
- changed current material for every authorized/dispatch field, missing
  resource, changed store, missing durable identity and unavailable readback:
  `committed_unverified`, no second create;
- changed same-operation material (tracking, order, notify preference):
  `conflict` before readback/transport;
- lost confirmation: `uncertain`, never resent;
- failed identity receipt: `uncertain`, never labelled rolled back, never
  re-created.

`backend/tests/test_shopify_fulfillment_actions.py` keeps the legacy
`success`/`fulfillment` shape as a compatibility twin while asserting the new
readback contract and `meta_out`.

## Exact runs

`run_and_capture.py` is the executable spec: existing Python 3.14.7
interpreter, `TESTING=1`, explicit synthetic `SECRET_KEY`, fresh scratch SQLite
`DATABASE_URL`, scratch data/Lance/output and blank provider credentials.

- `failure-first.log` / `failure-first-exit.json`: predecessor implementation,
  **exit 1**, 37 failed / 5 passed.
- `focused.log` / `focused-exit.json` / `focused.xml`: current implementation
  across fulfillment + article + blog + product material/replay + Oracle/
  Generic/service suites, **353 passed, 1 deselected, exit 0**.

The deselected node is the real-Alembic upgrade test, which needs the project
venv's `passlib` (absent from this interpreter). The migration revision-contract
node still runs; no migration contract changed.

No live provider/model/browser/server/account/credential/install/spend/send/
deployment/dev-database action was made. The scratch SQLite database was pruned
after log/XML capture; `run_and_capture.py` recreates it. Root independently
reviews and owns acceptance; this packet is not self-acceptance and does not
relabel prior packets.

## Finite delivery

This completes the already-authorized Shopify fulfillment-create write. It is
the last queued Shopify create mutation in this family.
