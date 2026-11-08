# LEAD_REVIEW — finite document-extraction honesty repair

Date: 2026-11-08
Work order: `CLI_WORK_ORDER.md`
Repo/worktree: `/private/tmp/atom-document-extraction-honesty-20261108`
Verified `git rev-parse --show-toplevel` = that exact path and
`git rev-parse --show-prefix` = empty before any edit.

## Root-observed baseline (retained unchanged by this slice)

Root probe: `backend/tests/test_root_document_parse_honesty.py` (test-only cut
recorded at `abda85ae8`, over main `ffd934e2f`), real python-docx parser, real
LanceDB + scratch SQL; embeddings only doubled; optional Docling disabled.

- Valid DOCX paragraph+table upload/open/repeated GET/stored-text export:
  PASS. Export returned `provenance=authoritative`, source version kind
  `versioned`, and the exact stored text.
- Malformed DOCX and valid-empty DOCX: both returned HTTP 200 and their
  fabricated `[Empty or unparseable file: ...]` text exported with HTTP 200
  and `provenance=authoritative`.
- Observed result: **2 failed / 1 passed**.

The root probe file was not modified.

## Producing defect and repair

### 1. Normal upload producer — `backend/api/document_routes.py`

Contract before: `/api/documents/upload` parsed, then if `content` was falsy
replaced it with `"[Empty or unparseable file: <filename>]"`, then
materialized bytes, wrote a fresh LanceDB row and a fresh SQL mirror row. A
valid-empty or malformed file therefore became a durable, fresh document whose
invented placeholder text exported as authoritative.

Contract now:

- Parse once with the existing `DocumentParser.parse_document`.
- If the result is missing **or whitespace-only**, raise the existing typed
  error envelope as `422 DOCUMENT_EXTRACTION_EMPTY` with only bounded
  `file_type` details.
- This refusal happens before `ATOM_OFFICE_DIR` materialization, `_upsert_document`,
  the `IngestedDocument` SQL mirror, or any sheet-dataset scheduling.
- Sheet-dataset scheduling moved from before parsing to after successful
  extraction; valid workbook behavior is otherwise unchanged.
- Valid non-empty extraction is stored verbatim. There is deliberately no
  wording/regex heuristic: literal text that resembles an old placeholder is
  accepted if the parser actually produced it.
- `422` (not `415`) classifies parsed-but-empty content; unsupported file
  types keep their existing pre-parse `415` refusal.

The same file's `/api/documents/ingest` producer had the identical fabrication:
empty pasted content became `"(Empty document)"`. It now refuses whitespace-only
content with `422 DOCUMENT_CONTENT_EMPTY` before any vector write. Its broad
`except Exception` was also corrected to re-raise typed HTTP exceptions instead
of converting them to 500.

### 2. Shared parser dependency failures — `backend/core/auto_document_ingestion.py`

The three structured optional-dependency branches returned truthy prose:

- `_parse_pdf` ImportError → `"[PDF content - parser not available]"`
- `_parse_docx` ImportError → `"[DOCX content - parser not available]"`
- `_parse_excel` no-pandas/no-openpyxl ImportError →
  `"[Excel content - parser not available]"`

Those are now `""`, matching the established absent-content convention used by
every other parser failure branch (unparseable/corrupt input). Callers already
classify `""` as absent/no_text. Real available parsers are untouched.

The integration-sync loop now also treats whitespace-only extraction as absent
(`if not text or not text.strip()`), matching the single-file ingestion path.

### Callers/consumers traced

- `backend/api/document_routes.py` upload → fixed above.
- `backend/api/document_ingestion_routes.py` `/upload` → whitespace guard
  added under the root-authorized continuation (existing 400 shape; see
  below). Its `/parse` response is unchanged by instruction.
- `backend/core/auto_document_ingestion.py` `parse_document_cached` and
  `AutoDocumentIngestionService` single-file + folder sync → blank is already
  skip/no_text; folder sync tightened for whitespace.
- `backend/integrations/universal_integration_service.py` named-file open →
  already returns `found: false` for blank/whitespace; a missing parser now
  reaches that branch instead of storing the marker.
- `backend/tools/email_attachment_tool.py`, `backend/core/pdf_canvas_service.py`,
  `backend/api/canvas_email_routes.py` → already treat blank as "no text
  layer"; the removed marker no longer becomes preview/OCR content.

## Tests authored (NOT RUN in this slice)

New: `backend/tests/test_document_extraction_refusal_contract.py`

- `test_docx_without_extracted_content_refuses_before_side_effects`
  (parametrized `malformed`, `empty`, `whitespace`): real python-docx/parser
  path; asserts `422 DOCUMENT_EXTRACTION_EMPTY`, unchanged SQL row count,
  unchanged LanceDB row count, no materialized upload file.
- `test_missing_docx_parser_is_absence_not_factual_content`: direct parser
  contract is `""` under a missing `docx` module, and the upload producer
  refuses with no durable side effects.
- `test_malformed_workbook_refusal_dispatches_no_sheet_background_work`:
  real malformed XLSX; spies on `ensure_sheet_dataset_background` and asserts
  zero dispatch plus no SQL/index/file writes.
- `test_real_docx_fallback_content_is_retained_and_authoritative`: valid DOCX
  paragraph+table twin; content retained, repeated read stable, export exact,
  `authoritative`/`versioned`/`matched`, fresh SQL row with a revision.
- `test_literal_old_placeholder_text_is_real_user_content`: legitimate TXT
  containing the literal old marker is accepted and exported unchanged
  (proves no wording heuristic).
- `test_valid_txt_upload_is_retained`: short real TXT twin.
- `test_valid_structured_workbook_is_retained`: real openpyxl workbook twin;
  cell content retained and exported authoritatively.
- `test_parallel_ingestion_upload_whitespace_refuses_before_writes`: mounted
  `/api/document-ingestion/upload`, whitespace TXT, existing 400 detail, zero
  SQL/LanceDB rows.
- `test_parallel_ingestion_upload_nonempty_is_retained`: mounted positive
  twin, nonempty TXT read back and exported under the route's existing
  authoritative/opaque/matched policy.

Existing focused assertions updated to the new contract (not weakened; they
now assert absence/refusal instead of the fabricated marker):

- `backend/tests/test_covpush_ingest.py`
- `backend/tests/test_covpush_w93_pomdp_misc.py`
- `backend/tests/core/test_auto_document_ingestion_coverage.py`
- `backend/tests/api/test_document_routes_coverage_w52.py`

Existing CI document-export step (`.github/workflows/ci.yml`, "Run
stored-document export authority controls") now also runs the new module;
every existing module in that step is preserved.

**No tests, app, DB, server, browser, install, provider/model call, credential
access or send/spend were executed. The test module and updated assertions are
authored only; root must run the gates.**

## Risks / limits

- Behavior change: clients that previously relied on a `200` for an
  unextractable upload now receive `422 DOCUMENT_EXTRACTION_EMPTY`; empty
  `/api/documents/ingest` now receives `422 DOCUMENT_CONTENT_EMPTY`; the
  parallel `/api/document-ingestion/upload` keeps its existing 400 shape but
  now also refuses whitespace-only extraction. This is the intended honesty
  contract, but UI callers should surface the typed error.
- File materialization and sheet scheduling still happen for valid content;
  only the refusal ordering changed.
- A parser exception that escapes `DocumentParser` (rare; it catches broadly)
  still becomes the route's generic `500`, never a fabricated document.
- Missing parser `""` is indistinguishable from a genuinely empty file at the
  parser boundary. That matches the existing absent-content convention; the
  ingestion pipelines already report `no_text`/`found: false` rather than
  inventing content.

## Parallel surface continuation (root-authorized after 60-step exit)

`backend/api/document_ingestion_routes.py` `POST /api/document-ingestion/upload`
is the parallel ingestion surface. Root's clarification explicitly authorized
only this additional guard. Its existing `not text` refusal already ran before
the vector/SQL writes with HTTP 400 and the detail string
`"Could not extract text from document"`; the guard now also rejects
whitespace-only extraction (`not text or not text.strip()`) and preserves that
exact 400 shape. No workspace resolution, source-hash, identity/version,
freshness, TTL, path-anchoring or broader write-truth policy was changed.

Its separate `/parse` endpoint was deliberately left unchanged: an empty parse
response is not itself stored source evidence.

Added mounted-route twins (authored, not run) in
`backend/tests/test_document_extraction_refusal_contract.py` using the existing
`exported` fixture:

- `test_parallel_ingestion_upload_whitespace_refuses_before_writes` — real
  mounted route, Docling disabled, whitespace TXT gets the existing 400 detail
  and leaves zero SQL/LanceDB rows.
- `test_parallel_ingestion_upload_nonempty_is_retained` — real mounted route,
  nonempty TXT uploads, reads back, and exports with the surface's existing
  authoritative/opaque/matched policy.

## Explicitly open / not claimed by this slice

Broader upload persistence/readback/authority CAS, manual-upload TTL or
integration-scoped freshness, legacy stored placeholders, upload path
anchoring, workspace-default inconsistencies, archive/adversarial parsing, UI
qualification, search/grounding/original-binary export, and arbitrary-format
qualification remain open. No existing stored document was reclassified by
text wording, and no data was wiped or migrated.


## Root first execution at711bd177e

Original root DOCX probes now pass. Combined execution:7passed/7failed. Six
new-author failures incorrectly expected a process-wide SQL database to have
zero rows after earlier valid tests. The new controls now compare complete
pre/post SQL identity/scope/version/filename/freshness snapshots, preserving
peer rows; no deletes or per-test DB wipes were introduced. The remaining
valid DOCX failure is NOT dismissed: repeated identical extracted text in
different workspaces aliases the global SQL document id. The second upload
can return200 but export404 and update the first workspace's metadata. An
independent real-factory two-workspace probe is being added before repair.
No complete DOCX acceptance is claimed.


The shared-index fixture also contains prior legitimate vector rows. Refusal
controls now compare complete SQL and Arrow-row snapshots rather than
expecting global index count0. At380cf77c0 the independent REAL workspace
handler factory (distinct physical directories) reproduced the actual product
identity defect: identical DOCX content in two workspaces got the same docid;
second upload200/export404 and peer_record_unchanged=false. This is not a
fixture-only problem and must be repaired before document acceptance.


## Content-namespace repair at 01f72a136

Root runtime at 01f72a136: **13 passed / 2 failed**. Both failures are the real
same-content cross-workspace collision, not parser failure. The parser repair
from 711bd177e and root's complete SQL/Arrow pre/post snapshot fixtures are
retained unchanged; root's scope probes are unchanged.

### Changed producer contract — `backend/api/document_routes.py`

`_content_doc_key(text, workspace_id, tenant_id)` is now
`sha256(JSON{content, tenant_id, workspace_id})` sorted/compact. JSON is an
unambiguous canonical serialization (no lossy separators, no case folding) and
keeps raw `None` distinct from the literal `"default"` namespace.

- Normal `/api/documents/upload` binds the id to `_resolve_ws_id(current_user)`
  (the existing FK-first workspace resolver) and the authenticated user's raw
  tenant. `/api/documents/ingest` uses the same server-owned scope; caller body
  metadata can no longer supply `doc_id`, `pg_document_id`,
  `source_content_hash`, `workspace_id` or `tenant_id`.
- Same content in the same scope re-uploads to the same id (idempotent).
  Identical bytes in different workspaces/tenants get different ids, so the
  second upload cannot update the first workspace's SQL row.
- Legacy content-only ids (`doc_<sha256(text)>`) remain readable and are reused
  ONLY when the authoritative SQL `IngestedDocument` row's owner scope matches
  the current scope (workspace under the existing Personal `None`→`"default"`
  storage policy; tenant compared raw). Otherwise the scoped id is used and
  the foreign/history row is left untouched.
- An unbacked old vector (no authoritative SQL owner) is never adopted:
  adoption fails closed to the scoped id, while the historical vector bytes
  remain readable. No delete or migration.
- A computed scoped id that already belongs to a foreign SQL row refuses with
  `409 DOCUMENT_IDENTITY_CONFLICT` before materialization/vector write; the SQL
  mirror also refuses to rewrite such a row if it appears concurrently.
- Text ingest still creates no SQL row; the string `"pg_document_id"` is
  stripped from caller metadata so a body cannot invent a PG binding. Existing
  `ev4`/raw revision kinds, freshness statuses and export-authority rules were
  not changed.

### Tests authored (NOT RUN)

New `backend/tests/test_document_content_namespace_identity.py`, reusing the
existing `exported` fixture/helpers and the real workspace handler factory:

- same-scope re-upload is idempotent (one id/row, updated filename);
- two real workspace stores with identical DOCX bytes get distinct ids, both
  export authoritatively, the first SQL row is byte/metadata unchanged, the
  physical stores differ, and cross-workspace reads/exports return 404;
- raw `None` vs `"default"` workspace/tenant identities differ, while existing
  Personal storage ownership still treats missing workspace as `"default"`;
- an owned legacy SQL id is reused; a foreign legacy row is preserved verbatim
  and the upload uses a fresh scoped id that exports authoritatively;
- an unbacked legacy vector is not adopted and remains readable;
- forged ingest-body `doc_id`/`pg_document_id`/`source_content_hash`/
  `workspace_id`/`tenant_id` are ignored for identity and PG binding.

The existing CI document-export step now also runs this module; every previous
module is preserved. No tests/runtime/DB/browser/provider/install/credential
actions were executed here. Root independently runs and accepts.

### Boundaries / risks

- Legacy adoption uses the existing Personal `None`→`"default"` storage policy
  for workspace ownership, so a legacy row stored as `"default"` is reusable
  by the Personal scope; new identities still distinguish raw `None` from
  `"default"`.
- Cross-store transactional CAS, database availability during the identity
  probe (falls back to the scoped id without legacy adoption), TTL/path
  policy, legacy placeholder cleanup, UI and arbitrary-format qualification
  remain out of scope. No actor/target CAS or broader readback integrity is
  claimed.


Root first namespace verification atb7bd0540a:22/22 focused controls pass,
including unchanged real-factory two-workspace and malformed/empty probes.
The new identity-lookup exception path now logs only a safe stage/class,
rather than a raw database/exception string. One guard asserts private
exception material is absent from logs/response while fresh scoped identity
remains deterministic. Root probes are included in the existing CI step.
Broader persistence/authority/concurrency/legacy-policy limits remain open.
