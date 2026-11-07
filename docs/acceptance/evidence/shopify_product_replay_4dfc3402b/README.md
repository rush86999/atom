# Shopify durable replay — migration identity + real existing-DB upgrade

Exact implementation source:
`4dfc3402b3d232ce1fda993f2c2362331600ef6f`
(`codex/shopify-product-oracle-20261107`), repairing the migration identity
left by `6ed0fc82e8ec1846b84c11ef00c0f04a6550e168`.

The `6ed0fc82e` packet and its source identity are preserved unchanged:
`docs/acceptance/evidence/shopify_product_replay_6ed0fc82e/`. This packet only
records the confirmed follow-up blocker and its repair.

## Blocker: revision identifier exceeded the Alembic version column

`6ed0fc82e` named the revision `20261107_task_operation_result_json`
(35 characters). The installed Alembic creates
`alembic_version.version_num` as `String(32)`
(`alembic/ddl/impl.py:169`). SQLite does not enforce a declared `VARCHAR`
length, so a SQLite-only upgrade could hide the PostgreSQL failure.

The revision is now `20261107_task_operation_result` (30 characters). The
filename stays descriptive, and `down_revision = "a2f0c1d4e5b6"` is the
existing auth/2FA revision that was already the head of this line. The new
revision is itself a head; there is no duplicate revision id.

## Real existing-database upgrade, not `create_all`

The new controls do not merely call `Base.metadata.create_all`.

* `check_migration_upgrade.py` builds a predecessor scratch database: a
  `task_operation_records` table without `result_json`, an old **succeeded**
  claim row, and `alembic_version` stamped at `a2f0c1d4e5b6`. It then runs the
  real `alembic upgrade` in a subprocess.
* The upgrade records exactly `20261107_task_operation_result`, adds a
  nullable `result_json`, retains the old claim with a `NULL` receipt, and a
  second upgrade in a new process is an idempotent no-op.
* `test_alembic_upgrade_records_revision_keeps_old_claim_and_restart_replays_once`
  performs the same real upgrade from a genuine consumer-created succeeded
  claim. After a process-style engine/session restart and another no-op
  upgrade, the retained predecessor claim replays as `committed_unverified`
  with **one POST total** — no second create and no invented title lookup.
* `test_migration_revision_fits_alembic_version_column_and_parent_resolves`
  locks the ≤32-character contract, unique revision id, existing parent and
  head relationship.

The existing SQLite `repair_known_drift` / guarded repair control from the
prior packet is kept and still runs; no new table, engine or lifecycle was
added.

## Exact command and result

`focused-spec.json` records the exact nodes and environment;
`run_and_capture.py` is the executable form. The run uses the project Python
3.14.7, `TESTING=1`, an explicit synthetic `SECRET_KEY`, a fresh scratch SQLite
`DATABASE_URL` and scratch data/Lance/office/output, with provider credentials
pinned empty.

Result: **102 passed, exit 0**, 68.22s (`focused.log`, `focused-exit.json`).
The replay file alone contributes 23 controls (21 prior + 2 new migration
controls). `revision_contract.log` and `migration_upgrade.log` are the separate
independent contract/upgrade checks.

## Scope and honesty notes

- Only `ShopifyService.http` is doubled. Registry, Generic mutation consumer,
  durable claim row, oracle verifier, material normalizer and the real Alembic
  command are real.
- Only SQLite was executed. No PostgreSQL runtime qualification is claimed;
  the revision-length defect is a deterministic schema/Wire contract check.
- No live Shopify/provider/model/account/credential call or configuration, and
  no live dev database, was touched.
- First evidence attempt hit `ENOSPC` while pytest wrote `focused.xml`; its
  scratch was discarded and the successful run above is the only result
  recorded. Per-test pytest temp trees from the successful run were pruned
  after log/XML capture to respect the ~1GB disk budget; `scratch.db`,
  `upgrade.db` and the logs are retained.
- Root independently verifies and owns integration/acceptance; this packet is
  not self-acceptance and does not relabel prior evidence.
