# GOAL-11 generated Canvas document/presentation Office export

Packet: `docs/acceptance/evidence/goal11_canvas_office_export_b9b3ebbb6/`

## Evidence hygiene

The raw root negative log (`controls.log`) contains the original actor
failure's dumped DOCX response bytes. It is retained privately with the root
world and is deliberately **not** committed or reproduced here. What is
committed is a labelled sanitized summary
(`gates/root_independent_original_fail5.summary`) preserving all five case
names, observed 200 statuses, expected refusals, the one positive, 7.38s,
`actual_exit 1`, `same_source true`, and the original probe/review/log hashes.
The updated root probe changes only the actor failure diagnostic to
status/bytes/header facts; its assertions are unchanged. No raw DB, tokens,
env dumps, response bytes or emails are in this packet.

## Boundary

Baseline `750f42215`: `GET /api/canvas/{id}/export/office` is absent (404,
`BASELINE_HAS_ROUTE False`). Generated `document`/`markdown` canvases rendered
only editor/preview; `OfficeFileCanvas` download exists only for a real bound
`content.office_file`; capability Export is XLSX-only. This is a missing
ordinary capability, not a reproduced runtime defect.

Implementation first frozen at `b9b3ebbb6`; root's independent six-control
probe then failed 5/6. The repair successor is
`7afcf65deabe4dbfde51de93e68b7ea01fedc23f` (same branch). Only
`backend/api/canvas_routes.py` changed in the runtime repair; tests were
extended. `office_service`, `employee_business_outcomes` and `canvas_authority`
hashes are unchanged from the inspected runtime.

Surface: `GET /api/canvas/{canvas_id}/export/office?format=docx|pptx`.

## Root failures and repair

| Root control | Frozen `b9` | Repair at `7afcf65de` |
|---|---|---|
| DOCX sections reordered, same groups/labels | 200 file | exact ordered body blocks compared to canonical `_markdown_blocks`; 422 |
| H2 demoted to H1 | 200 file | heading depth compared per block; 422 |
| Top-level requirements shadowed by truthy `assignment={run_id}` | 200 + `required_results_verified` | both representations read, normalized and compared; disagreement 409; top-level set can no longer vanish |
| `business_requirements=[None]` | 200 + false verified | malformed/non-list/duplicate/unsupported/unknown bindings 409 |
| Actor revoked in peer transaction during render | 200 file (cached ORM identity) | final actor/scope/source recheck in an independent session bound to the request engine; 403/no file |

A valid bound requirement still exports: normalized requirements are merged
with the assignment's applied steps and evaluated by the existing
`business_requirement_views` receipts. Satisfied results carry
`X-Atom-Business-Result: required_results_verified`; unscoped drafts carry
`X-Atom-Artifact-Scope: unscoped_canvas_draft` and `not_claimed`. There is no
blanket bound refusal and no client metadata self-certification.

The final recheck uses `SqlSession(bind=db.get_bind())` and closes it; it does
not call `expire_all`, rollback, flush or otherwise touch the caller's dirty
ORM state, and it adds no store/router/engine.

## A1–A10 mapping

- **A1**: Baseline public route/UI boundary captured; source shapes are current
  `docs`/`document`/`markdown` canvas text and `markdown` Slide outline content.
- **A2**: Reuses `require_active_actor` + `require_canvas_read` (current active
  actor, owner/co-editor, tenant/workspace), `visible_canvas_material` latest
  saved revision; optional `expected_audit_id` only. Foreign/stale/withheld
  targets refuse before rendering.
- **A3**: Extends the existing `api/canvas_routes.py` surface; reuses
  `office_service` Word/PowerPoint renderers, no new model/renderer/store/
  schema/router family.
- **A4**: CanvasPanel download awaits `flushAutosave`; dirty/failed/uncertain
  saves refuse; never downloads the old server body. Existing XLSX/file-office
  paths are unchanged.
- **A5**: DOCX body, in XML order, must equal the canonical
  `_markdown_blocks` sequence: title/heading depth, bullets, paragraphs and
  tables in place. PPTX compares slide count, titles, body lines, tables and
  notes against `extract_slide_outline`. Wrong-same-shape DOCX, reordered/
  demoted DOCX, and title-only/missing-body PPTX are refused.
- **A6**: `review_status` pending/rejected/withheld refuses. Top-level and
  nested assignment `business_requirements` are both normalized and compared;
  malformed/contradictory/unknown bindings fail closed; satisfied scoped
  receipts are still publishable. Unscoped drafts are not labelled grounded
  merely because they were converted.
- **A7**: Server-owned filename/storage; `core.local_paths.resolve_local_path`
  anchors default `data/office` to backend regardless of launch CWD. No path is
  returned. Renderer errors expose only fixed messages/stage, never exception
  or path text. No model/agent/scheduler effect.
- **A8**: Real source revision/content digest and output digest headers. OPC ZIP
  entry timestamps are normalized to a fixed DOS timestamp, so the same saved
  source yields identical bytes/hash across a fresh child OS process. DOCX and
  PPTX are separate source-bound controls.
- **A9**: Negative twins cover foreign scope, stale audit, withheld/empty,
  wrong format, unresolved/ malformed/ unknown/ contradictory requirements,
  renderer failure sanitization, wrong-same-shape/reordered/demoted DOCX,
  missing-body PPTX, concurrent save recheck, actor revocation during render,
  no audit write, and no download on unconfirmed save.
- **A10**: Boundary, source hashes, commands and logs captured; this is an API +
  component + real-child-process sample, not a browser/whole-GOAL claim.

## Gates

| Gate | Result | Log |
|---|---|---|
| Backend public-route export controls | 21 passed | `gates/backend_export_21.proof` |
| Root independent six controls on repair | 6 passed | `gates/root_independent_repair_6.proof` |
| CanvasPanel component controls | 47 passed | `gates/canvas_panel_47.proof` |
| Existing office-file/co-editing selection | 32 passed, 1 pre-existing failure | `gates/office_file_compat_32pass_1pre_existing.proof` |
| Baseline route absence | 404 / no route | `baseline/base_export_route_absent.proof` |
| Original root failure facts | 5 failed / 1 passed, 7.38s | `gates/root_independent_original_fail5.summary` |

The one office compatibility failure is
`TestPresentPersistence::test_explicit_canvas_id_respected`
(`/present` response lacks `canvas_id`) and is unrelated to this export route;
it is preserved, not skipped or weakened.

A broader local compatibility selection also includes
`tests/test_api_canvas_routes.py` submit failures caused by a pre-existing
test-auth/audience 403 (`JWT validation skipped: invalid token format`). Three
representative failures reproduce identically at baseline `750f42215`
(`compat/canvas_api_preexisting_base_3fail.proof`); they are not caused by this
route and are not counted as this feature's gates.

## Fresh process and CWD

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

- Bounded generated-canvas sample; no general DOCX/PPTX, browser, whole-GOAL-11,
  served-model, provider, PostgreSQL, soak or production claim.
- No CI/PR/merge; root owns independent verification and integration.
- PR number is intentionally not guessed.
