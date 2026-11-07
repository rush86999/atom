# Shopify product-create durable replay — source-bound evidence

Exact implementation source: `963a27781b58d606e0fe47e78f5ccf008cc597c2`
(`codex/shopify-product-oracle-20261107`, parent `556bc4e40`; product code
predecessor `0b325c5f1`). This packet covers **durable replay of a known
successful `shopify_create_product`** only. The blog, article and fulfillment
mutations remain the next owned cases and are not claimed here.

## What changed

`TaskOperationRecord` already arbitrated same-operation/same-material
idempotency but stored only the operation identity and payload digest. A
succeeded claim therefore had to replay as `committed_unverified`, because the
verifier could not identify the provider resource without guessing from a
title.

The same claim row now carries a durable result/receipt, written in the SAME
conditional UPDATE as the `succeeded` transition. It retains:

- the exact provider resource id and provider operation;
- the authoritative shop/store and the producer readback receipt;
- the frozen authorized product material (id, normalized fields, store).

A replay of the same operation + same material:

1. loads that durable receipt (never a title lookup);
2. checks its authorized material still matches the operation;
3. re-runs the existing independent verifier, which re-reads the exact remote
   id from the **current** workspace store and compares the accepted material;
4. returns `already_applied` / `verified` only when id, store and material
   agree, with no second create.

Changed material is still a conflict before readback. Missing/contradictory
resource or material, a changed current store, an unavailable readback, or a
succeeded claim with no identity receipt stays `committed_unverified`. A lost
confirmation stays `uncertain` with do-not-repeat and never resends. A provider
success whose identity receipt cannot be committed is reported as uncertain,
never as a rollback or a retry invitation.

No new operation engine, table, provider router, credential store or approval
lifecycle was added. Claims that can still verify from frozen material alone
keep the legacy replay path, so unrelated Generic/MCP/assignment and
Books/Outlook claims are not forced onto the identity-receipt contract.

## Failure-first control (preserved raw)

`failure-first.log` / `failure-first.xml` are the raw negative captured **before**
the implementation, against code source `0b325c5f1` (HEAD `556bc4e40`):

```text
tests/test_oracle_shopify_product_replay.py::test_known_success_replays_exact_resource_without_second_create
AssertionError: {'success': False, 'status': 'committed_unverified',
                 'action_result': 'already_applied_unverified', ...}
assert False is True
```

The honest predecessor limitation is exactly what this work removes for claims
that now carry the durable identity receipt.

## Verification boundary

Real code exercised: registered action, GenericAgent mutation consumer, durable
`TaskOperationRecord` claim/receipt, frozen request expectations, product
material normalizer, `ShopifyService` methods and the Oracle verifier. Only the
Shopify HTTP leaf (`ShopifyService.http`) is doubled.

Scratch world: `TESTING=1`, explicit synthetic `SECRET_KEY`, fresh scratch
SQLite `DATABASE_URL`, and scratch `ATOM_DATA_DIR` / `LANCEDB_URI` /
`LANCEDB_URI_BASE` / `ATOM_OUTPUT_DIR`. Provider credential variables are
pinned to empty strings. No live provider, store, token, account, credential,
spend, send, download, deployment or live dev DB was touched.

## Exact command and result

```text
/Users/rushiparikh/projects/atom/backend/venv314/bin/python -m pytest \
  tests/test_oracle_shopify_product_replay.py \
  tests/test_oracle_shopify_product_create.py \
  tests/test_oracle_registry_verification_gap.py \
  tests/test_oracle_connected_mutations.py \
  tests/test_generic_oracle_mutation_contract.py \
  tests/test_shopify_fulfillment_actions.py \
  -q --disable-warnings --junitxml=.../focused.xml
```

Result: **133 passed, exit 0** (`focused-exit.json`, `focused.xml`). The ten new
replay controls are:

- known success replays the exact id/store/material without a second create;
- restart with a fresh engine/session reloads the same durable identity;
- failed post-effect identity receipt is uncertain, not rolled back, not resent;
- wrong current resource material stays `committed_unverified`;
- missing current resource stays `committed_unverified`;
- changed current store stays `committed_unverified`;
- receipt-unavailable (predecessor-style) succeeded claim stays
  `committed_unverified`;
- unavailable readback stays `committed_unverified`;
- changed material refuses before any readback/create;
- lost confirmation stays uncertain and never replays as success.

The predecessor product controls (18), registry/connected/Generic contract
controls and Shopify fulfillment tests all still pass.

Artifact hashes are in `MANIFEST.json`. The scratch world is retained at
`<packet>/scratch` and is not part of the evidence commit.
