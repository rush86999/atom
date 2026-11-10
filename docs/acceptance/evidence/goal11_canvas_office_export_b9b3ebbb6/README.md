# GOAL-11 generated Canvas document/presentation Office export

Packet: `docs/acceptance/evidence/goal11_canvas_office_export_b9b3ebbb6/`

## Boundary

Baseline `750f42215`: `GET /api/canvas/{id}/export/office` is absent (404,
`BASELINE_HAS_ROUTE False`). Generated `document`/`markdown` canvases render
only editor/preview; `OfficeFileCanvas` download exists only for a real bound
`content.office_file`; capability Export is XLSX-only. This is a missing
ordinary capability, not a reproduced runtime defect.

Implementation at `b9b3ebbb6` adds the existing Canvas general export surface:
`GET /api/canvas/{canvas_id}/export/office?format=docx|pptx`.

## A1–A10 mapping

- **A1**: Baseline public route/UI boundary captured; source shapes are current
  `docs`/`document`/`markdown` canvas text and `markdown` Slide outline content.
- **A2**: Reuses `require_active_actor` + `require_canvas_read` (current active
  actor, owner/co-editor, tenant/workspace), `visible_canvas_material` latest
  saved revision; optional `expected_audit_id` only. Foreign/stale/withheld
  targets refuse before rendering.
- **A3**: Extends the existing `api/canvas_routes.py` surface; reuses
  `office_service` COW/PPTX renderers, no new model/renderer/store/schema/
  router family.
- **A4**: CanvasPanel download awaits `flushAutosave`; dirty/failed/uncertain
  saves refuse; never downloads the old server body. Existing XLSX/file-office
  paths are unchanged.
- **A5**: DOCX validator compares actual headings, bullets, paragraphs and
  tables against the canonical `_markdown_blocks`; PPTX compares slide count,
  titles, body lines, tables and notes against `extract_slide_outline`.
  Wrong-same-shape DOCX and title-only/missing-body PPTX are refused.
- **A6**: `review_status` pending/rejected/withheld and assignment
  `business_requirements` (via existing `business_requirement_views`) refuse.
  Unscoped drafts carry `X-Atom-Artifact-Scope: unscoped_canvas_draft` and
  `X-Atom-Business-Result: not_claimed`; no verified-business-outcome claim.
- **A7**: Server-owned filename/storage; `core.local_paths.resolve_local_path`
  anchors default `data/office` to backend regardless of launch CWD. No path is
  returned. Renderer errors expose only fixed messages/stage, not exception or
  path text. No model/agent/scheduler effect.
- **A8**: Real source revision/content digest and output digest headers. OPC ZIP
  entry timestamps are normalized to a fixed DOS timestamp, so the same saved
  source yields identical bytes/hash across a fresh child OS process. No
  persisted second artifact store and no timestamp-based false mismatch.
- **A9**: Negative twins cover foreign scope, stale audit, withheld/empty,
  wrong format, unresolved assignment result, renderer failure sanitization,
  wrong-same-shape DOCX, missing-body PPTX, concurrent save recheck, no audit
  write, and no download on unconfirmed save. Existing file-office tests remain
  green except one pre-existing unrelated failure.
- **A10**: Boundary, source hashes, commands and logs captured; this is an API +
  component + real-child-process sample, not a browser/whole-GOAL claim.

## Gates

| Gate | Result | Log |
|---|---|---|
| Backend public-route export controls | 11 passed | `gates/backend_export_11.proof` |
| CanvasPanel component controls | 47 passed | `gates/canvas_panel_47.proof` |
| Existing office-file/co-editing selection | 32 passed, 1 pre-existing failure | `gates/office_file_compat_32pass_1pre_existing.proof` |
| Baseline route absence | 404 / no route | `baseline/base_export_route_absent.proof` |

The one office compatibility failure is
`TestPresentPersistence::test_explicit_canvas_id_respected`
(`/present` response lacks `canvas_id`) and is unrelated to this export route;
it is preserved, not skipped or weakened.

## Fresh process

DOCX and PPTX are separate source-bound fresh-process controls. The PPTX twin
uses multiple slides, body, table cells and speaker notes; parent and child
assert the same bytes/SHA-256, and the child reports the actual slide
count/titles/body/table cells/notes. Both use the same scratch SQLite and real
renderer with no model calls or new business/agent rows. A runtime CWD test
exports from repo root and backend with `ATOM_OFFICE_DIR` unset and asserts
identical bytes, exercising `core.local_paths.resolve_local_path`.

## Research

- python-docx documents: https://python-docx.readthedocs.io/en/latest/user/documents.html
  — reuse the existing document package/renderer rather than a second Word engine.
- python-pptx presentations: https://python-pptx.readthedocs.io/en/latest/user/presentations.html
  — reuse the existing presentation model and verify the actual package.

## Non-claims

- Deterministic JSON is not the subject here; this is DOCX/PPTX file export for
  the selected generated-canvas sample only.
- No DOCX/PPTX generality, whole-GOAL-11, browser, served-model, provider,
  PostgreSQL, soak or production claim.
- No CI/PR/merge; root owns independent verification and integration.
