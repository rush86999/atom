# PR #705 delete-truth — raw focused evidence package (2026-11-06)

This directory contains **raw, inspectable evidence** only. It proves nothing
beyond what the bytes below show. No acceptance is claimed here; whole-family
acceptance remains withheld pending independent verification.

## Raw outcome (this session, exact source)

Log: `focused-delete-truth-314.log` (verbatim stdout+stderr of the run below,
no post-processing).

Final line of the raw log:

```text
================= 3 failed, 48 passed, 175 warnings in 20.96s ==================
```

| Suite in the combined run | Tests | Outcome |
|---|---|---|
| `tests/test_document_delete_truth.py` (new contract suite) | 9 | 9 passed |
| `tests/test_document_vector_family_cleanup.py` | 7 | 7 passed |
| `tests/api/test_document_routes_coverage_w52.py` | 35 | 32 passed, 3 failed (pre-existing, identities below) |

(Counts read from the raw log's progress markers; 9+7+35 = 51.)

The 3 failures are exactly the pre-existing, documented-in-advance failures
with their raw assertion lines from the log:

1. `test_ingest_success` — `assert 2 == 1` (`chunk_count`), at
   `tests/api/test_document_routes_coverage_w52.py:154`.
2. `test_ingest_empty_content_placeholder` —
   `'Untitled document'.startswith('Document ')` is False, at line 165.
3. `test_upload_workspace_resolution_exception_warned` — `KeyError:
   'workspace_id'`, at line 406.

None of the three touches the deletion route. They were declared
pre-existing before this evidence run (`docs/acceptance/
DOCUMENT_DELETE_TRUTH_2026_11_06.md`, "Baseline vs. after") and the run
reproduces exactly those three, unchanged.

Reconciliation with the recorded claim: `3 failed, 48 passed` over 51 tests =
the recorded after-change family (`3 failed, 39 passed` over 42 tests) plus
the 9-test contract suite. Identical failure identities.

## Command and environment identity

Command (run from `backend/` of this checkout, no other arguments, no
regenerated or edited logs):

```text
/Users/rushiparikh/projects/atom/backend/venv314/bin/python -m pytest \
  tests/test_document_delete_truth.py \
  tests/test_document_vector_family_cleanup.py \
  tests/api/test_document_routes_coverage_w52.py -q
```

| Item | Value |
|---|---|
| Interpreter | Python 3.14.7 (`venv314`, `--version` captured before the run) |
| Working tree | branch `codex/document-delete-truth-20261106`, head `bf28b07f3`, clean except untracked bootstrap files (`CLI_WORK_ORDER.md`, `CLI_BASELINE_CLAIMS.json`, `opencode.jsonc` — never staged) |
| Scratch state | `TESTING=1` is force-set by `backend/tests/conftest.py` (tripwire against the live DB); the contract suite creates its own per-test scratch SQLite and LanceDB under the run's unique pytest tmp root (visible in the raw log, `pytest-26`); no store outside tmp is opened by it |
| Runtime edits | none in this task — `git status` shows the three untracked bootstrap files only |

## Source identity

Execution used exactly the committed bytes at head `bf28b07f3`:

| File | Git blob |
|---|---|
| `backend/api/document_routes.py` | `2474f6e58936c9e146ff13c9fdd79f9b085b4f48` |
| `backend/core/document_delete_service.py` | `87847e4b6f56eb825fef3a7f909ab8778b8ba8ae` |
| `backend/core/lancedb_handler.py` | `52847d508fdde3b1b106a2c7b2664209c072d539` |
| `backend/tests/test_document_delete_truth.py` | `3c18be340575a8b29cbf09ef6efab9f58756c3d1` |
| `backend/tests/test_document_vector_family_cleanup.py` | `6cf5b84e5cf2061d7a5c094fcb114da4c95ea36b` |
| `backend/tests/api/test_document_routes_coverage_w52.py` | `c9cb35c0e635cb66df0d10b566bc09beed687b00` |

Verified against `git ls-tree bf28b07f3` at packaging time; `verification.json`
records uniquely resolving source/log blob prefixes and the exact-byte checks against the executed and packaging refs.

## Attribution of test kinds (do not over-read)

The raw log itself shows the limit of these suites:

- `test_document_delete_truth.py` drives the delete route **function**
  directly. The log line `Governance check skipped for delete_document:
  missing request or db` shows the governance dependency is bypassed in these
  calls. They are **function-call controls**, **not** public HTTP and
  **not** governance/authorization tests.
- `tests/api/test_document_routes_coverage_w52.py` uses the in-process
  FastAPI/Starlette TestClient (`http://testserver`). That is mounted
  in-process HTTP with dependency-overridden identity — not ordinary login
  and not cross-tenant authorization proof.
- The lead-run HTTP twins (prefix delete raising / returning `False` →
  HTTP 503, `verification.effect=partial`, original `operation_id`,
  `replay=do_not_repeat`) were run **by the lead independently** with the
  identity dependency overridden to a known scratch member (controlled auth).
  Their files (`/private/tmp/root-document-http.log`,
  `/private/tmp/test_lead_document_http_truth.py`) were **not reachable from
  this session's permitted paths** and are therefore **not** reproduced in,
  or certified by, this package. Reference: `/private/tmp/brennan-brief/
  VERIFIER_PR705_DELETE_TRUTH_20261106.md`. Those probes do not prove
  ordinary login, broader authorization, stale actor/CAS, concurrent
  vector-store changes, PostgreSQL or process restart.
- The baseline false-success counterexamples (base deleted, chunk cleanup
  raised/`False`, caller still got a clean success) were reproduced at
  baseline source `9d6a09d52` by the lead
  (`/private/tmp/brennan-brief/VERIFIER_DOCUMENT_DELETE_NEGATIVE_20261106.md`,
  log `/private/tmp/root-document-negative.log`). They were **not** re-run
  here; the original negatives and their source identity are preserved
  untouched.

## Scope boundaries

- Finite repair of `DELETE /api/documents/{doc_id}` only; no runtime source
  change on this follow-through, evidence packaging only.
- Single-tenant owner scope: nothing here is a SaaS qualification gate, and
  the runtime was not modified to satisfy hypothetical tenants.
- No model/provider/live DB/install/download/deployment/merge action was
  used or performed. No merge/review/comment on the PR.
- No self-acceptance: this package reports raw outcomes and source refs
  only. Independent verification remains required.
