# Shopify product-create Oracle vertical — source-bound evidence

Exact source: `0b325c5f1e8de97a352f1d202cd1e8d13e21140b`
(`codex/shopify-product-oracle-20261107`, based on `f3b32005a`).

This packet covers **only** `shopify_create_product`. The blog, article and
fulfillment mutations remain the next owned cases and are explicitly not
claimed here.

## What changed

The registered action now:

1. resolves the workspace's `EcommerceStore` row from its supported
   `tenant_id == workspace_id` producer compatibility;
2. refuses a missing, foreign, moved, inactive or credential-less store **and**
   any body/model `shop`/`store`/`access_token`/`tenant_id`/`workspace_id`
   selector **before** transport;
3. freezes the normalized product payload and the accepted business material;
4. creates through the existing `ShopifyService`;
5. reads the exact returned product id back through the official
   `GET /admin/api/{version}/products/{product_id}.json` contract
   (<https://shopify.dev/docs/api/admin-rest/2026-07/resources/product>);
6. reports `applied` only when the exact id, current shop and accepted material
   agree; missing, contradictory or unidentifiable readback is explicit
   uncertainty.

The new postcondition verifier does not trust the producer's receipt or a
matching title. It independently re-reads the exact id from the **current**
workspace store and compares the frozen material. The existing GenericAgent
durable `TaskOperationRecord` claim remains the idempotency arbiter.

No new provider router, credential store, approval lifecycle, operation engine
or brand-specific authority shortcut was added.

## Verification boundary

Real code exercised: registered action, GenericAgent mutation consumer, durable
claim, material normalizer, `ShopifyService` methods and Oracle verifier.
Only the Shopify HTTP leaf (`ShopifyService.http`) is doubled.

Scratch world: `TESTING=1`, explicit synthetic `SECRET_KEY`, fresh scratch
SQLite `DATABASE_URL`, and scratch `ATOM_DATA_DIR` / `LANCEDB_URI` /
`LANCEDB_URI_BASE` / `ATOM_OUTPUT_DIR`. Provider credential variables are
pinned to empty strings. No live provider, store, token, account, credential,
spend, send, download, deployment or live dev DB was touched.

## Exact command and result

```text
/usr/local/opt/python@3.14/bin/python3.14 -m pytest \
  tests/test_oracle_shopify_product_create.py \
  tests/test_oracle_registry_verification_gap.py \
  tests/test_oracle_connected_mutations.py \
  tests/test_generic_oracle_mutation_contract.py \
  tests/test_shopify_fulfillment_actions.py \
  -q --disable-warnings --junitxml=.../focused.xml
```

Result: **123 passed, exit 0** (`focused-exit.json`, `focused.xml`).
The 18 product controls cover the exact positive, store/authority negatives,
same-title wrong id/material, moved authority, absent/contradictory/
unidentifiable readback, same-operation one-effect replay, changed-material
refusal, lost-confirmation no-resend and frozen-digest refusal before
transport.

### Replay boundary (honest)

A replay of a **succeeded** generic claim reports `committed_unverified` and
does not resend: the existing `TaskOperationRecord` claim stores the operation
identity and payload digest, not the provider's remote id, so the verifier
cannot honestly re-read by id from frozen material alone. The one-effect
invariant is still proven (POST count remains one, `idempotent`/`replayed` true).
No title-based lookup is used to manufacture a replayed success.

Artifact hashes are in `MANIFEST.json`. The scratch world is retained at
`backend/.shopify_oracle_evidence/scratch` and is not part of this commit.
