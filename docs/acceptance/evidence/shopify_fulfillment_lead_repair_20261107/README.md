# Shopify fulfillment lead repair — official REST shapes and pre-effect identity

This packet is the finite deliverable for the root handoff in
`FULFILLMENT_LEAD_REPAIR.md`. It repairs the five confirmed fulfillment
contracts on the isolated worktree/branch
`codex/shopify-fulfillment-lead-review-20261107`.

- Runtime repair commit: `c5dbcb68e` (based on handed-off source
  `c00146111`).
- Permanent independent control:
  `backend/tests/test_lead_shopify_fulfillment_rest_shape.py`.
- Runtime file hashes and actual process exits are recorded in
  `source-binding.json`, `*-exit.json`, `matrix-exit.json`, and the raw
  `*.log` files in this directory.

## Contract trace

Primary official contract:
<https://shopify.dev/docs/api/admin-rest/2026-07/resources/fulfillment>

| Operation | Documented shape used |
| --- | --- |
| Create | `POST /admin/api/{version}/fulfillments.json` with `line_items_by_fulfillment_order` |
| Exact fulfillment read | `GET /admin/api/{version}/orders/{order_id}/fulfillments/{id}.json` |
| Fulfillment orders for an order | `GET /admin/api/{version}/orders/{order_id}/fulfillment_orders.json` |
| Authoritative FO association | `GET /admin/api/{version}/fulfillment_orders/{fulfillment_order_id}/fulfillments.json` |

The retired order-scoped **write** is not used. The global
`GET /fulfillments/{id}.json` read is not used.

## Five repairs

1. **Official Fulfillment response shape.** The official resource reports
   completed line `quantity` and typically `fulfillable_quantity=0`, but no
   trustworthy `fulfillment_order_id` on line items and no
   `fulfillment_orders` array. Producer and Oracle now obtain the authoritative
   FO association from the documented FO-scoped collection instead of
   fabricating it from the submitted request or a fake response field.

2. **Quantity namespaces.** Planning quantity is read from the source
   fulfillment-order line (`remaining_quantity` → `fulfillable_quantity` →
   `quantity`). Observed completed quantity is read from the Fulfillment line
   `quantity` only. `fulfillable_quantity=0` can no longer certify a completed
   quantity of `0`.

3. **Pre-effect parent/material identity.** Before the POST, every actionable
   source fulfillment order is required to match the authorized `order_id` and
   carry its own id, assigned location and line identity. A foreign or missing
   parent, missing location, missing lines or a line without an order-line id
   refuses with `failed_before_effect` and **zero** POSTs. Valid twins still
   dispatch.

4. **Status truth.** Only `status=success` is completed business success.
   `failure`/`cancelled`/`error` are contradictory, and `pending`/`open` are
   honestly unresolved. None is verified and none is resent.

5. **Parent-bound exact read.** `get_fulfillment` now takes the parent
   `order_id` and reads the documented order-scoped path. The parent is
   propagated through the producer, the independent Oracle re-read and durable
   replay. The test HTTP double only accepts the strict documented paths, so a
   regression to the old overbroad global path fails.

The already-integrated product monetary formatter and Article publication
repairs were not modified.

## Failure-first and valid matrix

`run_and_capture.py` is the executable evidence script. It runs the existing
interpreter with `TESTING=1`, a fresh scratch SQLite URL, `ENABLE_SCHEDULER=false`
and a scratch pytest basetemp. Only `ShopifyService.http` is doubled.

Actual results (see the raw logs / exit JSON):

| Phase | Source | Result | Process exit |
| --- | --- | --- | --- |
| `failure-first` | handed-off `c00146111` | 5 failed / 0 passed | **1** |
| `valid` | repaired `c5dbcb68e` | 69 passed | **0** |
| `callers` | repaired `c5dbcb68e` | 4 passed | **0** |

The `valid` phase contains the permanent independent five controls plus the
integrated fulfillment create/replay suite, the agent-surface caller contract,
and the direct service control class. The `callers` phase covers the affected
`ShopifyService.create_fulfillment` fixtures in `test_covpush_saaspair`,
`test_covpush_intgr_b`, and `test_covpush_w87_freshdesk_trello_shopify`.

A wider combined invocation of the affected files also passed 442 tests but
showed four pre-existing WhatsApp request-context failures in
`test_covpush_intgr_b.py`; those nodes are unrelated to Shopify and are not
claimed as repaired here. The focused Shopify caller nodes are green above.

## Retained negatives

The permanent/integrated controls continue to cover:

- contradictory source parent refused before POST;
- wrong returned remote id;
- wrong order/tracking/company/location;
- wrong or removed FO association, line-item id or completed quantity;
- missing tracking proof;
- missing/absent readback and unidentifiable effect;
- durable same-operation replay and process-style restart with one POST total;
- changed current material, changed store, missing resource, missing durable
  identity and unavailable readback → `committed_unverified`, never resend;
- changed same-operation material → `conflict` before readback;
- lost confirmation → `uncertain`, never resent;
- failed identity receipt → `uncertain`, never rolled back or recreated.

## Safety and disclosure

- No live provider, model, browser, server, account, credential, install,
  download, send, spend or deployment action was made.
- No live/shared database was used. Every evidence phase used `TESTING=1` and a
  scratch SQLite database outside the repository.
- Existing permissions/config (`opencode.jsonc`) was copied unchanged from the
  established CLI lane and contains no credentials; it is not part of this
  packet or runtime repair.
- `notify_customer` is an input request acknowledgement. It is frozen into the
  request binding but Shopify does not return it on the Fulfillment resource;
  this packet makes **no** claim that customer notification was delivered.
  Fulfillment existence is not delivery proof.
- The broader suite's unrelated WhatsApp nodes are disclosed above rather than
  hidden. Root owns independent re-verification and final acceptance; this
  packet is not self-acceptance.

## Finite delivery

This is the complete fulfillment lead repair requested by the handoff: the five
confirmed contracts are fixed, the permanent independent controls pass with the
same assertions and new official-shape coverage, and affected caller controls
are green. No further fulfillment family work is implied by this packet.
