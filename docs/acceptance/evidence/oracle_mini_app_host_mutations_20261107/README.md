# Six supported mini-app host mutations — producer/verifier evidence

Activated source: `2b53eda29d9d357b3b613c1f1633bf79c1bc7cbe` (PR714's finished
integrated candidate). Qualified code/test commit: `b205fc151` (the
implementation commit `af97665c7` plus the restart-shaped fresh-engine readback
control) on `codex/oracle-mini-host-proofs-20261107`. No merge/rebase was
performed.

This is a bounded ORACLE-01 subfamily, not whole-app acceptance. It adds
supported host-side write proof for six registered actions that need no guest
execution:

- `mini_app_scaffold`
- `mini_app_write_logic`
- `mini_app_publish`
- `mini_app_install`
- `mini_app_db_write`
- `mini_app_revert_logic`

`mini_app_run` (guest execution) and the four Shopify writes remain explicitly
uncovered. No live model, provider, microVM, container, account, send, spend,
download or deployment was used.

## Producer transaction and receipt binding

Each producer writes its `CanvasAudit` receipt in the SAME transaction as the
host effect:

- **scaffold**: app + source canvas + starter `CanvasLogic` + `mini_app_scaffold`
  receipt (name, dependencies, scopes, base image/canvas type, starter digest,
  operation/request digest).
- **write_logic / revert_logic**: controller write + `mini_app_logic` checkpoint
  receipt commit together. The receipt binds the operation/request, source
  digest, checkpoint version and (for revert) the exact target checkpoint.
- **publish**: `prepare_runtime` runs with `commit=False`; its runtime-image
  state is applied by the publish CAS in the same transaction. The receipt binds
  the published version/status and manifest/blueprint/initial-state digests.
- **install**: instance canvas + logic + state + component rows + installation +
  `mini_app_install` receipt commit together. The receipt binds the installed
  version and blueprint/initial-state/manifest digests.
- **db_write**: the record mutation and `mini_app_db_write` receipt commit
  together. The receipt binds the exact affected record ids, sequences, payload
  digests and operation/request — never a page-wide count.

## Verification and stale-write controls

Verifiers re-read authoritative `MiniApp`, `Canvas`, `CanvasLogic`,
`CanvasState`, `MiniAppInstallation`, `CanvasRecord` and `CanvasAudit` rows in a
FRESH session and require the executor-owned operation id, frozen request digest
and exact material. Returned ids only locate records; they do not supply
authority/material.

Writers use guarded DML so a peer change after the read is zero-effect:

- publish binds prior manifest (SQL NULL / JSON null / `{}` distinct), status,
  version, `is_public`, tenant/workspace/owner/blueprint and runtime image/version;
- logic writes bind prior row id, canvas, source, language and nullable creator;
- record updates/deletes bind the exact prior payload and sequence, and
  `delete_series`/`clear` bind the exact prior record-id set.

A zero-row match returns a truthful `proven_not_applied` conflict and appends no
receipt; the peer's row is preserved. A published-app install may legitimately
have a different instance owner, so install verification checks the
installer/instance scope and the existing `is_public AND is_approved` sharing
policy instead of copying app-owner-only rules.

## Root-supplied findings repaired

1. **Logic CAS material** (`LEAD_PROBES/test_lead_mini_logic_cas_material.py`).
   The draft bound only id/canvas/source and could overwrite a same-source peer
   language change. It now binds prior language and nullable creator too. The
   supplied probe is **2 passed** (was 1 failed / 1 passed).
2. **Publish preparation atomicity**
   (`LEAD_PROBES/test_lead_mini_publish_preparation.py`). The draft called
   `prepare_runtime` first, which cleared and committed `runtime_image` before a
   missing blueprint raised. `prepare_runtime` now accepts `commit=False`, and
   publish applies preparation through its guarded transaction; the supplied
   probe is **2 passed** (was 1 failed / 1 passed).

The earlier three mock-shape `mini_app_set_tests` failures identified by root
are pre-existing on accepted main and are unchanged/not weakened; the immutable
`mini_app_set_tests` receipt code is untouched.

## Measured qualification at `b205fc151`

Fresh owned basetemp children under `<scratch>/opencode/.../qualify2/`; the
affected cluster used a pre-created scratch SQLite file because three
chat-orchestrator controls create real session/execution rows. The focused
evidence includes a restart-shaped fresh-engine readback (producer session
closed, new engine/session reads the same scratch file).

- extended ORACLE control step: **209 passed** (`focused-gate.log`, exit 0);
- supplied logic-CAS probe: **2 passed** (`supplied-logic-cas.log`, exit 0);
- supplied publish-preparation probe: **2 passed**
  (`supplied-publish-preparation.log`, exit 0);
- affected 22-file cluster: **785 passed, 9 pre-existing unrelated failures**
  (`affected-cluster.log`, exit 1; IDs/root causes in
  `baseline-unrelated-failures.txt`).

## Registry snapshot

`coverage/inventory.json` (registry-only, source `b205fc151`):

- 90 registered actions, 26 declared mutations;
- **21 covered, 5 explicitly uncovered**:
  `mini_app_run`, `shopify_create_article`, `shopify_create_blog`,
  `shopify_create_fulfillment`, `shopify_create_product`;
- 16 local mutations, 15 covered (only `mini_app_run` uncovered);
- 0 undeclared, 1 plan-output validator covered.

This is an inventory, not a qualification run. HTTP mutation routes and
provider writes remain out of scope; the HTTP/provider counts in registry-only
mode are intentionally zero-by-mode, not proof that none exist.

## Boundary

No guest/runtime isolation, live provider breadth, PostgreSQL/concurrency/soak,
or whole-app ORACLE claim follows from this packet. Root owns authenticated
PR/check/merge actions and the final frozen-source decision.
