# Shopify blog create — registered exact-id/material Oracle

Exact implementation source: `d1c474b5e` on
`codex/shopify-blog-oracle-20261107`, implementing the queued
`shopify_create_blog` write after the shared product-material blocker was
repaired and pushed separately at `7cc5471f7`.

## Failure first

The predecessor handler returned the provider's raw response:

```python
blog = await ShopifyService().create_blog(...)
return {"success": True, "blog": blog}
```

No exact id was retained, no current-store readback was performed, and the
registered mutation therefore had no independent proof. Under the real Generic
mutation consumer the predecessor is honestly reported as `uncertain` rather
than verified; `failure-first.log` captures that missing capability
(**23 failed, 1 passed, exit 1**) against the `HEAD^` implementation. The one
passing control is the already-honest lost-confirmation case.

## Implementation

The new path uses the existing contracts; no new router, receipt store,
operation engine or provider access was added.

- `core/action_registry.py`: the registered `shopify_create_blog` handler now
  refuses missing/foreign/moved/inactive/ambiguous stores, body store/credential
  selectors, and a blank title before transport. The shared Shopify store
  resolver fails closed when a workspace has more than one store row instead of
  picking an arbitrary storefront.
- `core/shopify_mutations.py`: blog payload/material projection, producer with
  exact created-id readback through `ShopifyService.get_blog`, and the domain
  durable receipt projector/matcher (title/handle).
- `integrations/shopify_service.py`: `get_blog` by exact id:
  `GET /admin/api/{version}/blogs/{blog_id}.json`
  (https://shopify.dev/docs/api/admin-rest/2026-07/resources/blog).
- `core/oracle/postcondition_verifiers.py`: registered independent verifier.
  It requires the frozen operation/request digest, provider receipt, exact
  remote id, same current workspace store, and a fresh exact-id readback whose
  title/handle match the authorized material. Missing/contradictory proof stays
  unverified.
- `core/oracle/request_expectations.py` and `core/connected_actions.py`: freeze
  and bind the same authorized title/handle payload, so a succeeded claim can
  replay only from its durable exact id and changed material is refused.

## Controls

`backend/tests/test_oracle_shopify_blog_create.py` joins the REAL registered
action, REAL GenericAgent durable claim, REAL ShopifyService methods and REAL
shared Oracle. Only `ShopifyService.http` is doubled. Covered:

- exact create: one POST, two GETs (producer + Oracle), exact id/store/material;
- pre-effect refusal: missing/foreign/moved/inactive/ambiguous store, body
  store/credential selectors, blank title;
- wrong returned id, wrong title, wrong handle, absent/contradictory readback,
  unavailable readback, unidentified effect;
- same-operation same-material replay and process-style restart: one POST total
  and `already_applied`;
- changed current material, missing current resource, changed store, missing
  durable identity, and unavailable current readback: `committed_unverified`
  with no second create;
- changed same-operation material: `conflict` before readback/transport;
- lost confirmation: `uncertain`, never resent, never a replayed success.

## Exact runs

`run_and_capture.py` is the executable spec: Python 3.14.7, `TESTING=1`, an
explicit synthetic `SECRET_KEY`, fresh scratch SQLite `DATABASE_URL`, scratch
data/Lance/output and blank provider credentials.

- `failure-first.log` / `failure-first-exit.json`: predecessor implementation,
  **exit 1**, 23 failed / 1 passed.
- `focused.log` / `focused-exit.json` / `focused.xml`: current implementation
  across blog + product material/replay + Oracle/Generic/service suites,
  **275 passed, 1 deselected, exit 0**.

The deselected node is the real-Alembic upgrade test, which needs the project
venv's `passlib` (absent from this machine's pytest interpreter). The migration
revision-contract node still runs; no migration contract changed.

No live Shopify/provider/model/account/credential/download/dev-database call
was made. The scratch SQLite database was pruned after log/XML capture to respect
the ~1GB disk budget; `run_and_capture.py` recreates it. Root independently
reviews and owns integration/acceptance; this packet is not self-acceptance and
does not relabel prior evidence.
