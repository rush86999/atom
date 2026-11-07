# Shopify product-create — complete authorized-material proof

Exact implementation source:
`7cc5471f7` on `codex/shopify-blog-oracle-20261107` (source/tests commit).
This packet repairs the shared product blocker before any blog implementation,
as required by the root review.

## Root failure being repaired

Root's independent real-registry / real-Generic / real-Oracle matrix doubled
only the Shopify HTTP leaf and found 3 false-verified cases plus 3 valid twins:

| Accepted request | Provider readback | Predecessor verdict |
| --- | --- | --- |
| `images: [{src, alt}]` | images omitted | `oracle_verified=True` (wrong) |
| variant `price: 1.005` | `price: 1.00` | `oracle_verified=True` (wrong) |
| variant `compare_at_price: 20.00` | `compare_at_price: 25.00` | `oracle_verified=True` (wrong) |
| same three, exact readback | exact | verified (valid twins) |

The predecessor material projection omitted `images` entirely, omitted every
variant field except a curated subset, and quantized prices to two decimals.
A matching title/body therefore still certified a provider that dropped or
changed authorized material.

## Repair

`backend/core/shopify_mutations.py` now:

- projects **every accepted variant field** and **every accepted image**, not a
  curated subset;
- compares numeric fields (`price`, `compare_at_price`, `cost`, weight,
  inventory/position) at exact decimal identity — `1.0 == 1.00` but
  `1.005 != 1.00`; no rounding is applied;
- treats a provider-rewritten/CDN image `src` as **not** content proof: with
  no content readback the verdict stays unverified rather than assuming URI
  identity proves bytes;
- reports every mismatch in the existing readback receipt (`images[0].src`,
  `variants[0].compare_at_price`, ...), so the existing producer and Oracle
  report `uncertain`/unverified instead of `applied`;
- feeds the same complete projection through the existing durable receipt
  projector/matcher. Same-operation exact-id replay therefore re-reads the
  exact resource and refuses changed current material without a second create.

No generic Shopify special case, new receipt store, router, operation engine,
field allowlist narrowing, dependency, or extra provider/store/token access was
added. The prior store-authority, strict-JSON receipt and migration contracts
are unchanged. Official Shopify Admin REST product, product-image and
product-variant resources are cited in the module docstring.

## Controls

`backend/tests/test_oracle_shopify_product_authorized_material.py` joins the
REAL registered action, REAL GenericAgent mutation claim, REAL shared Oracle,
REAL producer/material normalizer and REAL verifier. Only
`ShopifyService.http` is doubled. It covers:

- all 3 root negatives and their valid twins;
- image source rewrite stays unverified;
- same-operation replay with omitted/rounded/changed current material for
  images, price and compare-at price stays `committed_unverified`, with one
  POST total;
- same-operation exact-material replay verifies the original resource with no
  second create.

`root_probe/test_lead_shopify_authorized_material.py` is the exact supplied
3-negative/3-positive root probe copied into the packet so the fixture is
reproducible against this source.

## Exact runs

`run_and_capture.py` is the executable spec. It uses Python 3.14.7,
`TESTING=1`, an explicit synthetic `SECRET_KEY`, a fresh scratch SQLite
`DATABASE_URL`, scratch data/Lance/output, and blank provider credentials.

- `failure-first.log` / `failure-first-exit.json`: the new controls run against
  the predecessor `shopify_mutations.py` (`HEAD^`), **exit 1**, reproducing all
  three root negatives and the replay variants.
- `focused.log` / `focused-exit.json`: the complete product/oracle suites plus
  the new controls against the repaired source, **161 passed, exit 0**.
- `root-probe.log` / `root-probe-exit.json`: root's 3-negative/3-positive
  probe against the repaired source, **6 passed, exit 0**.

The unrelated real-Alembic upgrade node is deselected because this machine's
pytest interpreter lacks `passlib`; the migration revision-contract node still
runs. This is disclosed rather than hidden, and no migration contract changed.

No live Shopify/provider/model/account/credential/download/dev-database call
was made. The scratch SQLite database was pruned after log/XML capture (the
`run_and_capture.py` spec recreates it) to respect the ~1GB disk budget.
Root independently reviews and owns integration/acceptance; this packet is not
self-acceptance and does not relabel the frozen product 4df packet or the
original 3-negative fixture bytes.
