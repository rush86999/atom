# Knowledge-document deletion truth — 2026-11-06

Branch: `codex/document-delete-truth-20261106`
Base: `9d6a09d52` (pushed audit; `248a23296` on `origin/main`)
Code commits: `d6f9cbd43`, follow-up `8add04906`

## Authorized scope

Finite repair of `DELETE /api/documents/{doc_id}` only. No upload, search,
provider, model, credential, account, merge or deployment action. No live DB
and no inference were used; tests set `TESTING=1` through
`backend/tests/conftest.py`, and every LanceDB/SQLite store in the new suite is
a per-test `tmp_path`.

## First failure (reproduced)

Before the change, `backend/tests/test_document_vector_family_cleanup.py`
asserted `success is True` when the prefix delete raised. The route deleted the
base row, swallowed the chunk-family failure/`False`, and returned
`Document '<id>' deleted` with no operation id, counts, receipt or readback.
Chunks remained retrievable in LanceDB.

## Contract implemented

- Route keeps `@require_governance(action_name="delete_document")` and the
  existing `_resolve_ws_id` workspace resolution. No workspace/tenant comes
  from the request body.
- Optional caller `operation_id` (query parameter) is bound to the exact
  workspace, actor, document id and request digest.
- One `AuditLog` receipt keyed by `operation_id` records actor/tenant/workspace,
  exact `doc_id`, outcome, and pre/post base-row and chunk-family counts.
- `verified` only after a fresh readback shows both exact-id count and
  `<doc_id>::` count at zero.
- A removed base row with surviving chunks is `committed_unverified` (HTTP 503)
  with the original operation id and `replay: do_not_repeat`. It is never a
  clean success.
- Replay of the same operation returns the original receipt and performs no
  second delete. A changed document, workspace or actor under the same
  operation id is a 409 conflict.
- An already-absent id covered by an earlier receipt is `no_change` and no new
  receipt is invented; an unknown/foreign id is still 404 with zero effects.
- LanceDB and SQL are separate stores. The service makes no one-transaction
  atomicity claim; receipt-commit failure after a known effect is
  `effect_unknown`.

## Code

| File | Git blob |
|---|---|
| `backend/api/document_routes.py` | `2474f6e58936c9e146ff13c9fdd79f9b085b4f48` |
| `backend/core/document_delete_service.py` | `87847e4b6f56eb825fef3a7f909ab8778b8ba8ae` |
| `backend/core/lancedb_handler.py` | `52847d508fdde3b1b106a2c7b2664209c072d539` |
| `backend/tests/test_document_delete_truth.py` | `3c18be340575a8b29cbf09ef6efab9f58756c3d1` |
| `backend/tests/test_document_vector_family_cleanup.py` | `6cf5b84e5cf2061d7a5c094fcb114da4c95ea36b` |
| `backend/tests/api/test_document_routes_coverage_w52.py` | `c9cb35c0e635cb66df0d10b566bc09beed687b00` |

## Test results

Command (from `backend/`):

```text
/Users/rushiparikh/projects/atom/backend/venv314/bin/python -m pytest \
  tests/test_document_delete_truth.py \
  tests/test_document_vector_family_cleanup.py \
  tests/api/test_document_routes_coverage_w52.py -q
```

- New contract suite: **9 passed**.
  - base row + chunk family -> one verified deletion, fresh list/get/search and
    prefix readback empty, one receipt.
  - chunk-only family -> verified, no 404, one receipt.
  - prefix delete raises and prefix delete returns `False` -> 503
    `committed_unverified`/`partial`, base effect known, chunks still readable,
    receipt persisted, replay does not repeat the failed cleanup.
  - unknown id and foreign-workspace id -> 404, zero deletes, zero receipts.
  - replay same operation id -> one effect/original receipt; different document
    and different actor -> 409, target intact.
  - second delete under a new operation id -> `no_change`, no new receipt.
  - fresh SQL session + restarted LanceDB handler -> effect and receipt survive,
    replay `already_applied`.
- Target regression file (`test_document_vector_family_cleanup.py`): the old
  “cleanup failure is success” expectation was replaced and passes.
- Target route coverage file: delete tests now use a stateful handler and a
  scratch DB; the stale “deletion scheduled” assertion was corrected.

Test-kind attribution: the contract suite (`test_document_delete_truth.py`)
invokes the delete route **function** with dependency-overridden identity
(the raw log shows `Governance check skipped for delete_document` during those
calls); the w52 route-coverage file uses the in-process Starlette TestClient
with overridden identity dependencies. Neither is a public-HTTP,
governance or ordinary-login/authorization test. Lead-run mounted-HTTP twins
(503 partial) and baseline counterexamples were run independently under
controlled auth; see the raw evidence package below for exact attribution.

### Baseline vs. after

| Suite | Before change | After change |
|---|---|---|
| `test_document_vector_family_cleanup.py` + `test_document_routes_coverage_w52.py` | 4 failed, 38 passed | 3 failed, 39 passed |

The first run’s fourth failure was the delete-route success message assertion
in this family; it now passes. The three remaining failures are pre-existing
and outside this change:

- `test_ingest_success` (`chunk_count` 2 vs 1),
- `test_ingest_empty_content_placeholder` (title `Untitled document`),
- `test_upload_workspace_resolution_exception_warned` (upload metadata lacks
  `workspace_id`).

Adjacent suites were also compared and fail independently of this branch when
run alone: `tests/core/test_same_file_freshness.py` (3 pre-existing freshness
failures) and `tests/unit/test_lancedb_handler.py` (9 pre-existing
embedding/create-table state failures). Neither touches the deletion route and
neither failure changed after the added readback counters.

## Raw evidence package

The inspectable raw focused-run evidence is committed at
`docs/acceptance/evidence/document_delete_truth_20261106/`:

- `focused-delete-truth-314.log` — verbatim stdout+stderr of the command
  above, re-executed on exact head `bf28b07f3` (raw outcome: 3 failed, 48
  passed; the 3 failures are the pre-existing ones listed above, unchanged
  and numbered).
- `README.md` — command/environment/source identity, failure identities, and
  the explicit test-kind attribution (function-call controls ≠ public
  HTTP/governance tests; lead-run HTTP twins and baseline counterexamples are
  referenced, not re-run or certified here).
- `verification.json` — artifact/source blob-identity manifest.

## Non-claims

- No atomicity between SQL `AuditLog` and LanceDB.
- No reconciliation worker or new operation engine; this reuses `AuditLog` and
  the already-merged replay patterns.
- Upload and search behaviour were not changed.
- No served-UI click, live provider, credential, account, merge or deployment
  was exercised.
