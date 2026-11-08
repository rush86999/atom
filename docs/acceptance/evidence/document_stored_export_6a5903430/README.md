# Stored-document export (NEXT03) — implementation checkpoint

**Branch:** `codex/document-stored-export-20261107`
**Executed source:** `6a5903430dc7adabfdaa1d56f8272265a59f73f7` (clean)
**Main base:** `cf5e981917bc31809ca9e8824a2363bdbc9c8f68`
**Original G3 worktree:** `b493abb30` remains frozen; not switched or edited.

## User outcome

The enabled Data surface can now export the **stored extracted text** of a
document the user can already open, from the Documents detail page, through the
normal authenticated API client. This is a bounded export of text already in
the document index. It is **not** a download of original file bytes and does
not widen `/search`, upload formats or any deferred surface.

## API

`GET /api/documents/{doc_id}/export?format=text|markdown|json`

- Existing Document Hub router, auth, FK-first workspace resolution, LanceDB
  point read and freshness/identity rows.
- `text`/`markdown` return the full stored text; `json` returns a schema-v1
  allowlisted provenance envelope with the content.
- Full stored content is returned up to the explicit 2 MiB export bound; the
  model reader's 20k context window is not used.
- Unsupported formats (`html`, `pdf`, `docx`, `original`, unknown) return
  typed 422; client `path`/`url`/`file_path`/`original` query authority is
  rejected 422.
- Empty text 422; oversize 413; unknown/foreign/removed 404; explicit
  stale/outdated/superseded 409; unknown/contradictory/old-extractor identity
  409.
- No JSON self-hash. `X-Document-Export-Sha256` covers the exact response body.
  `source_version`, `stored_text_sha256` and the response-body digest remain
  distinct fields/uses.
- Attachment disposition, `nosniff`, `no-store`, RFC 6266/5987 Unicode-safe
  filename, no HTML/inline rendering.

## Identity rules

- Known indexed/SQL bindings must have matching indexed and authoritative
  revisions through the existing strict matcher (`ev4` current extractor or
  exact opaque manual revision).
- Missing/contradictory indexed or SQL versions, wrong `pg_document_id`,
  old extractor versions, foreign workspace, removed/stale/superseded rows
  refuse with no content.
- Only producer-marked manual/legacy vector rows with no SQL/index binding may
  export as `snapshot_only` + `source_version_status=unknown`; they are never
  labelled current/verified. Manual SQL rows with no version are also
  snapshot-only; automated SQL rows with no version fail closed.
- JSON provenance is allowlisted (no `file_path`, source URL, arbitrary
  metadata, secrets).

## UI

One control on `frontend-nextjs/pages/documents/[docId].tsx`:
`Export stored text` + Text/Markdown/JSON select + Download. It uses the
existing `api` auth client with `responseType: 'blob'`, safe filename, object
URL download and inline bounded errors. Profile copy now advertises export;
`search` remains disabled.

## Evidence

| Artifact | Result |
|---|---|
| `baseline-no-export.log` / `baseline-no-export.json` | main-identical mounted API valid read + no export route/control; **2 passed, exit 0** |
| `backend-export-26.log` | mounted real router + real scratch LanceDB/SQLite export suite; **26 passed, exit 0** |
| `frontend-detail-3.log` | actual detail component: control/success/failure; **3 passed, exit 0** |
| `frontend-documents-17.log` | existing Documents list/profile tests; **17 passed, exit 0** |
| `typescript-noemit.log` / `.exit.json` | clean source; **exit 0**, no install/npx |
| `compat-39pass-3known.log` | existing document route/search compatibility: **39 passed, 3 pre-existing failures** |
| `pre-existing-compat-baseline.log` | the same 3 failures on pristine main `cf5e98191`; not caused by export |

The only doubled test leaf is `EmbeddingService.generate_embedding` (deterministic
vector). Parsing, upload, SQL mirroring, LanceDB storage, strict identity,
auth/workspace resolution, response bytes and download control are real.
No world, browser, model, provider, account, send, spend, install, download or
deployment ran. The three compatibility failures are pre-existing test drift
(chunk-count expectation, old empty-title text, omitted workspace_id kwarg),
reproduced identically on pristine main.

TASK-WAIT-01/source/goal/radio lanes were not touched. Root owns independent
review, PR/CI and merge.
