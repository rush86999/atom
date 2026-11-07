# Shopify durable replay — shared-core blocker repair

Exact implementation source: `6ed0fc82e8ec1846b84c11ef00c0f04a6550e168`
(`codex/shopify-product-oracle-20261107`), repairing the durable replay
checkpoint `963a27781b58d606e0fe47e78f5ccf008cc597c2`. The prior packet
`docs/acceptance/evidence/shopify_product_replay_963a27781/` and its source
identity are preserved unchanged.

Root review withheld `963a27781` for three shared-core blockers. This packet
records the corrective source and the exact scratch verification for them.

## 1. Domain-neutral durable claim persistence

`963a27781` read `_oracle_expected_shopify_product` and Shopify-specific
receipt keys inside `GenericAgent._durable_effect_result`. That put a provider
special case in shared claim persistence.

Now `GenericAgent` calls `core.oracle.build_durable_effect_result`, which stores
only the common result/receipt envelope: operation/action identity, payload
digest, exact remote id, allowlisted opaque store identity, allowlisted
provider/read/verification receipt fields and strict JSON. Shopify product
material is supplied by the registered projector/matcher in the existing
verifier/provider layer:

- `core/oracle/__init__.py`: domain-neutral builder, strict JSON proof,
  allowlists, projector/matcher registries;
- `core/oracle/postcondition_verifiers.py`: registers the
  `shopify_create_product` projection/comparison with its existing verifier;
- `core/shopify_mutations.py`: owns the actual product-material projection and
  mismatch comparison.

Books/Outlook and non-provider tools keep the same neutral contract. The
connected-mutation suite verifies their receipt path still works.

## 2. Fail-closed proof serialization

The predecessor's `json.dumps(receipt, default=str)` silently certified
arbitrary objects and non-finite numbers. It is removed.

`core/outbound_operation_claim.py` now exposes `strict_json_value` and
`strict_json_roundtrip`, which reject objects, tuples, sets, bytes, Decimal,
non-string dict keys, cyclic/deep values and NaN/Inf. `mark_status` enforces the
same rule before writing `result_json`, so malformed proof cannot become a
succeeded claim. The replay file covers both the builder and the persistence
boundary, including object/NaN/Decimal/tuple malformed-proof negatives.

## 3. Existing-database upgrade, not create_all

A fresh `Base.metadata.create_all` never upgrades an existing installation.

- SQLite: `core.sqlite_schema_repair.repair_known_drift` covers
  `TaskOperationRecord`, compares the live table with the model and adds the
  missing nullable `result_json` idempotently.
- PostgreSQL: the new guarded alembic revision
  `backend/alembic/versions/20261107_task_operation_result_json.py` adds the
  same column, skipping a missing/already-upgraded table.

The replay file's `test_existing_database_upgrade_and_replay_survives_restart`
starts from an existing scratch DB, **drops** `result_json`, upgrades through
the real repair, creates once, restarts the engine/session, re-runs the
idempotent repair, and replays the same operation with no second POST. The
alembic revision's upgrade/downgrade/idempotence is checked separately on a
scratch SQLite table in `migration_guard.log`.

## Exact command and result

`focused-spec.json` records the exact nodes and environment; `run_and_capture.py`
is the executable form. The run uses the project Python 3.14.7, `TESTING=1`, an
explicit synthetic `SECRET_KEY`, a fresh scratch SQLite `DATABASE_URL` and
scratch data/Lance/office/output, with provider credentials pinned empty.

Result: **100 passed, exit 0**, 103.57s (`focused.log`, `focused-exit.json`).
The replay file alone contributes 21 controls, including:

- known success replays the exact id/store/material without a second create;
- restart with a fresh engine/session reloads the same durable identity;
- failed post-effect identity receipt is uncertain, not rolled back, not resent;
- wrong/missing current resource and changed store stay `committed_unverified`;
- receipt-unavailable predecessor claims stay `committed_unverified`;
- unavailable readback stays `committed_unverified`;
- changed material refuses before readback/create;
- lost confirmation stays uncertain and never replays as success;
- unsupported lossy proof is rejected by the builder and by persistence;
- an existing scratch DB is upgraded by the guarded repair and replays across
  restart with no second create.

## Scope and honesty notes

- Only `ShopifyService.http` is doubled. Registry, Generic mutation consumer,
  durable claim row, oracle verifier and material normalizer are real.
- No live Shopify/provider/model/account/credential call or configuration, and
  no live dev database, was touched.
- The predecessor's exact removed code is cited above; this packet does not
  claim a captured failing run for those three blockers. The new negative
  controls are the post-repair executable proof.
- A separate broader claim/effect run had 81 passed and 4 failures in
  `test_zero_effect_claim.py` / `test_write_zero_effect_claims.py` (canvas
  wording, planner fallback, missing seeded workspace). Those files/codepaths
  are untouched here and the failures reproduce independently.
- Root independently verifies and owns integration/acceptance; this packet is
  not self-acceptance and does not relabel prior evidence.
