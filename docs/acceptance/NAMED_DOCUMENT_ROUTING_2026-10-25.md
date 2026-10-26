# Named-document routing fix — 2026-10-25

**Status: implemented and verified in an isolated worktree; not deployed.**
The serving pilot remains `55b13cd2f` and was not restarted.

## Root cause

A named `.txt` request entered the spreadsheet/dataset lane:

1. the ask gate's fallback `detect_file_task_mentions` accepted any file
   mention, including `.txt`;
2. `_datasets_named_file_block` treated every mention as a dataset-catalog
   lookup and returned “named file was not resolved in the indexed catalog”
   when no `dataset_entries` row existed;
3. the ask lane rendered that dataset-catalog miss as the final answer, even
   though `documents.search` could find the uploaded document.

`is_spreadsheet_task_mention("price list.txt")` also returned `True` from its
word hints, preserving part of the same bug.

## Fix

- **Explicit file type outranks wording.** New `DOCUMENT_EXTENSIONS` and
  `explicit_file_kind()` classify mentions by suffix. `price list.txt` is a
  document; `.xlsx`/`.csv` are datasets; extensionless names remain unknown
  until catalog resolution.
- **Dataset lane is not applicable to documents.** `_datasets_named_file_block`
  returns before the dataset catalog for explicit document/mixed mentions and
  no longer emits a dataset “not present” verdict for them.
- **Workspace-scoped document identity.** New `core/named_file_resolution.py`
  resolves mentions against `IngestedDocument` (workspace-filtered) and the
  dataset catalog. Missing workspace returns `workspace_required`, not an
  all-workspace scan or “no document”.
- **Deterministic named-document reader.** `_direct_named_document_read`
  resolves the catalog identity and reads via `documents.search`; it requires
  an exact hit ID (a same-title hit with a different ID is rejected), labels
  search content as a **matching excerpt** rather than a complete read, and
  records excerpt coverage limits.
- **Ambiguity/no-match/failure are explicit.** Duplicate names return a
  candidate clarification; no match returns “no uploaded document in this
  workspace matches”; catalog/search failures return a failure verdict, not
  “document absent”.
- **Mixed asks preserve every source.** A mixed document/workbook ask returns
  a clarification naming both (or all) sources and reads neither from a
  single-source shortcut. A single workbook mirrored into both catalogs is
  one dataset source, not a false mixed ask.
- **Extensionless names choose the reader after resolution.** A name without
  a suffix is checked against both catalogs; it enters the dataset lane only
  when the dataset catalog owns it.
- **Dataset fallback guard.** When the named-file scope is
  documents/mixed/unknown, the generic dataset search fallback is skipped so
  a document ask cannot be answered from unrelated workbook rows.

## Verification

### Unit / focused

- `tests/test_named_document_routing.py` + `tests/test_file_mention_resolution.py`:
  **29 passed**.
- Broader focused set (`named_document_routing`, `file_mention_resolution`,
  `cross_source_followup_routing`, `pending_file_task_resume`,
  `workbook_structured_delivery`): **426 passed, 11 failed**. The 11 failures
  are identical on parent `55b13cd2f` (pre-existing refresh/follow-up tests),
  not introduced by this change.

### Scratch product route

A patched backend on `:8121` with a fresh scratch DB and the deployed provider
profile was exercised through `POST /api/chat/message`:

| Request | Result |
|---|---|
| Exact smoke ask naming `release_smoke_record_55b13cd2f.txt` | `CEDAR-55`, source named, 49.5 s |
| `Read price list.txt …` | `MAPLE-77`, source named, 25.0 s |
| `Read duplicate_record.txt …` (two uploads) | “More than one uploaded document matches…”, both candidates, nothing read |
| `Read missing_record.txt …` | “No uploaded document in this workspace matches…”, nothing read |
| `Read other_workspace_record.txt …` (row in `ws-other`) | no content leak, same honest no-match |
| Ordinary workbook `mixed_workbook.xlsx` | routed to the dataset lane, not the document lane |
| Mixed document/workbook ask | both sources named; no single-source answer |
| Canvas writes | `canvases=0`, `canvas_audit=0` across the named-document reads |

The exact smoke answer is now deterministic:

> From `release_smoke_record_55b13cd2f.txt` (matching excerpt):
> Release smoke record — product 55b13cd2f.
> The release smoke code is CEDAR-55.
> …
> Source: `release_smoke_record_55b13cd2f.txt`.

Evidence (scratch, outside the repo):
`/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-named-doc-scratch/evidence/`.

## Review

An independent review identified the dead ask-gate guard, pinned-source loss,
both-catalog workbook misclassification, wrong-hit attribution, false
complete-read coverage, containment-as-verified, false durable identity, and
catalog/search failure handling. Those blockers were fixed and the focused
tests above were rerun. Remaining known limits are recorded below.

## Known limits / follow-ups

- The document reader uses `documents.search` and returns a bounded matching
  excerpt (up to 4,000 characters per source), explicitly labeled as an
  excerpt. A full-document paged read and question-targeted extraction are
  follow-ups.
- Mixed document/workbook asks are preserved as a clarification; they are not
  yet executed as one combined read.
- The legacy dataset lane can still operate without a workspace scope for
  callers that never provide one; the new document resolver fails closed on a
  missing workspace. Tightening the legacy dataset path is a separate change.
- Resume-lane telemetry now carries `document_result`; the ask-lane response
  is serialized by the existing chat response contract (its `data` is not a
  top-level response field).
- No deployment or live restart was performed. The pilot remains
  `55b13cd2f`; a separately approved update is required to serve this fix.
