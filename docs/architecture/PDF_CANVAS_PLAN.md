# PDF Canvas — Plan (load → edit by user & agent → approve → attach to email → archive)

Status: **P1–P4 implemented and verified** (2026-09-04).
- P1 shipped: `pdf` canvas type, upload/blank create, PDF.js viewer, page ops
  (rotate/reorder/delete/merge), versioned+audited saves with optimistic
  concurrency, attach-to-email with provenance.
- P2 shipped: agent maturity-gated lifecycle — `pdf_canvas` autonomy topic,
  tools in `tools/pdf_canvas_tool.py` (reads STUDENT, draft mutations
  INTERN, approve/attach SUPERVISED; STUDENT proposes-for-teaching),
  propose-vs-execute via `gate_for_topic`, AgentProposal →
  `/api/maturity/proposals` HITL loop, lifecycle state machine with
  approved-immutability (409).
- P3 shipped: AcroForm fill + flatten (flatten-on-attach stages a frozen
  copy), TRUE content-level redaction with verification (unfindable targets
  refuse the op), real PDF annotation objects, OCR fallback via Docling.
  Generation from business data: quote/invoice/letter templates via
  POST /create/generate (the "generate from Zoho data" item — data-seeded
  templates today; a direct Zoho-fields mapper is future polish).
- P4 shipped: internal signature stamp (SignatureEditor text → script-style
  stamp + attribution), DocuSign envelope integration
  (`integrations/docusign_service.py`, JWT-consent grant, env-gated and
  dormant without credentials, mocked-transport tests), OneDrive archive
  with lifecycle.archive_ref provenance, sanitized archival export.
- Intentional deferrals (decided, documented): certified PDF/A conversion
  (needs embedded ICC profiles — we ship sanitized, self-contained archival
  copies instead); Graph cloud REFERENCE attachments (the existing >3MB
  upload-session inline path already covers large sends; reference
  attachments only matter for non-embedding); WorkDrive upload (service is
  download/search-only today — OneDrive covers archival); retention policies
  (audit-first: all versions deliberately retained forever).

Companion to `PLAYBOOK_USER_JOURNEY.md`; follows the same draft → review →
approve → immutable lifecycle pattern.

## 1. Business context

The business already lives in documents: Zoho Inventory/Books records (items, invoices via
`zoho_books_service.create_invoice`), proposals (`core/proposal_service.py` sends HITL-approved
email), and an email canvas people use daily. Today there is **no way to produce, correct, or
send a PDF anywhere in the product** — the only PDF code is inbound parsing (`pypdf` + Docling
in `core/auto_document_ingestion.py`, `integrations/pdf_processing/`). The PDF canvas closes the
outbound half of the document lifecycle:

| Stage | Business examples | Owner |
|---|---|---|
| Acquire | upload a vendor contract, save an attachment from an inbound email, generate a quote/invoice/order confirmation from Zoho data | user + agent |
| Understand | text/table extraction, "what does section 4 say", field discovery on AcroForms | agent |
| Edit | form fill, corrections (amounts, dates, addresses), page reorder/merge, stamping headers/page numbers, redaction | user + agent |
| Review/Approve | human-in-the-loop approval gate before anything leaves the building (playbook pattern) | user |
| Sign | internal initials stamp first; external e-sign via DocuSign later | user |
| Distribute | attach the approved version to an email canvas and send | user + agent (gated) |
| Archive | immutable version history + audit trail; WorkDrive/OneDrive archive later | system |

Design principle: **the approved artifact is immutable and every transformation is audited** —
a sent contract must be reproducible byte-for-byte (which version, which hash, who approved,
which email carried it).

## 2. Research findings → decisions (cited)

1. **Render/write split is the standard architecture**: PDF.js (Mozilla, Apache-2.0) renders and
   hosts the annotation/form interaction layer; a mutation library writes real PDF bytes.
   pdf-lib is the common client-side writer, but mature deployments keep the authoritative save
   server-side for heavy ops (OCR, flatten guarantees, signing, redaction) — hybrid is the 2025
   consensus. Sources: [pdf-lib](https://pdf-lib.js.org/), [Nutrient's PDF.js guide](https://www.nutrient.io/blog/complete-guide-to-pdfjs/),
   [client-vs-server thread](https://www.reddit.com/r/reactjs/comments/vc0wkz/pdf_editing_client_side_with_canvas_or_on_server/),
   [Syncfusion on broken fillable forms in JS viewers](https://www.syncfusion.com/blogs/post/fillable-pdf-forms-in-javascript).
2. **Agents don't patch bytes — they call deterministic tools.** The dominant 2025–26 pattern is
   MCP/tool-registry wrapping of pypdf/PyMuPDF/pdf-lib, with a strict read/write split and a
   validation loop (visual/text checks after edits). Sources: [Anthropic — Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents),
   [Foxit agentic PDF workflows](https://www.llamaindex.ai/insights/best-agentic-document-processing-tools),
   [pypdfium2/PyMuPDF parsing benchmarks](https://arxiv.org/abs/2410.09871).
   → This repo *already has* the exact pattern: `tools/registry.py` + `tools/email_attachment_tool.py`
   + `core/autonomy_policy.py` gating + `AgentProposal` HITL. Reuse it; do **not** route PDF byte
   edits through `chat_canvas_editor.CanvasPatchOp` (its verbatim find→replace contract is for
   text/JSON content, and "surgical text patch" on binary is the wrong mechanism).
3. **Library choice**: rule of thumb from the 2025 comparisons — pypdf for merge/assembly/form
   values, ReportLab for generation, pdfplumber for tables, PyMuPDF for fast extraction.
   Sources: [Nutrient 2026 Python PDF comparison](https://www.nutrient.io/blog/complete-guide-to-pdfjs/),
   ["I tested 7 Python PDF extractors"](https://onlyoneaman.medium.com/i-tested-7-python-pdf-extractors-so-you-dont-have-to-2025-edition-c88013922257).
   → Repo already ships `pypdf>=3.0.0` and `reportlab>=4.0.0` (reportlab already generates
   invoices in `core/apar_engine.py`). Stay on pypdf + reportlab; add **pikepdf (MPL)** later only
   if content-stream surgery (redaction) needs it. **Avoid PyMuPDF (AGPL)** unless licensing is
   explicitly accepted — the BSD/MPL stack covers our needs.
4. **Build vs buy**: commercial SDKs (Apryse ~$6.5K–$102K/yr, Nutrient quote-based, Adobe PDF
   Services 500 free transactions/mo) buy annotation/edit/OCR polish; open source covers viewing
   (PDF.js) + generation/mutation (pdf-lib/pypdf/reportlab) at engineering cost. Sources:
   [Apryse build-vs-buy](https://apryse.com/blog/pdf-js/pdf-js-build-vs-buy), [Nutrient on PDF.js limits](https://www.nutrient.io/blog/pdfjs-limitations-commercial-upgrade/),
   [Adobe PDF Services pricing](https://www.adobe.io/document-services/pricing/main/).
   → Build on open source for v1 (our ops are form-fill/merge/stamp/generate — well within reach);
   revisit a commercial SDK only if pixel-perfect freehand editing or high-volume OCR is demanded.
5. **Redaction must remove content, then sanitize, then verify** — a black rectangle is not
   redaction; metadata/hidden layers are the most common leak. Sources:
   [PDF Association](https://pdfa.org/unlocking-the-power-of-pdf-redaction/),
   [redaction failure research](https://www.argeliuslabs.com/deep-research-on-pdf-redaction-failures-and-security-risks-exploits-and-best-practices/),
   [Nitro](https://www.gonitro.com/best-pdf-redaction-tools).
   → Server-side only, with a unit test asserting extracted text no longer contains redacted
   strings, and a sanitize pass (metadata, attachments, JS, orphaned objects).
6. **E-sign**: external signing is an envelope workflow (send → recipients sign → completed PDF
   returns) via the DocuSign eSign REST API; don't hand-roll cryptographic signatures.
   Sources: [DocuSign integration 101](https://www.docusign.com/blog/developers/docusign-esignature-integration-101-planning-your-integration),
   [DocuSign API products](https://www.docusign.com/products/apis).
   → Phase 4. Interim: internal initials/approval stamp reusing the existing `SignatureEditor.tsx`
   image → reportlab stamp.
7. **Email attachment limits**: Graph inline `fileAttachment` works for small files; >3MB must use
   `createUploadSession` chunked upload; very large files should be cloud attachments (OneDrive
   reference). → Repo already implements the upload-session path in
   `integrations/outlook_service.py` (`_upload_large_attachment`); the PDF canvas rides it as-is.

## 3. What already exists (reuse, don't rebuild)

- **Canvas spine**: `canvases` table (`core/models.py:3925`, `canvas_type`, JSON content),
  `CanvasAudit` append-only history with `/history` + `/restore` + `/fork` endpoints
  (`api/canvas_routes.py`). New type = a `canvas_type='pdf'` value, not a new table.
- **Real-file canvas precedent**: `office_*` types store real generated files (`core/office_service.py`,
  `data/office`) and render via `OfficeFileCanvas` in `CanvasPanel.tsx`. PDF follows this shape.
- **Attachment staging → send, end-to-end**: `core/email_attachment_store.py` (disk staging,
  extension whitelist incl. pdf, 20MB/upload + 50MB/canvas caps, orphan sweep) →
  `EmailCanvasService.stage_attachments` → `outlook_service.send_email` with base64 attachments
  and >3MB upload-session fallback. `EmailAttachmentStrip.tsx` already renders staged files.
- **Agent tooling**: `tools/registry.py` (ToolMetadata, maturity, importlib discovery),
  `tools/email_attachment_tool.py` as the closest template (list/get_text/stage/attach with
  byte caps), `core/autonomy_policy.py` topics + `AgentProposal` approve/reject flow, WS
  `canvas:update` broadcast + `lib/canvasSync.ts` for live UI sync.
- **Approval lifecycle**: `core/playbook_service.py` — draft-only editing, approve gate, approved
  objects immutable (409 on edit), `ATOM_PLAYBOOKS_AUTO_APPROVE` latch pattern for evidence-gated
  promotion.
- **Inbound PDF reading**: `core/auto_document_ingestion.DocumentParser` (Docling OCR → pypdf)
  already wired to the email attachment preview endpoint (`canvas_email_routes.py:375`).
- **Background work**: `_spawn_background_task` asyncio pattern in `main_api_app.py`; SQS worker
  (`sqs_worker.py`) for deployed environments.

## 4. Architecture

### 4.1 Data model

```
canvases row: canvas_type = 'pdf'
content JSON: {
  "file":       {"current_hash": "...", "page_count": 3, "size_bytes": 81234},
  "versions":   [{"hash", "audit_id", "author": "user:<id>|agent:<id>",
                  "op_summary", "created_at"} ...],          // mirrored into CanvasAudit
  "form_values": {"field_name": "value"},                     // last applied AcroForm values
  "annotations": [{page, kind, rect, text, author} ...],      // data model until flattened
  "lifecycle":  {"state": "drafting|in_review|approved|sent|archived",
                 "approved_by", "sent_refs": [{message_id, attachment_hash, sent_at}]}
}
file bytes: backend/data/pdf_canvases/{user_id}/{canvas_id}/{content_hash}.pdf   // content-addressed, immutable
```

- Content-addressed blobs make every version restorable and byte-comparable ("which bytes were
  sent" = the hash in `sent_refs`). All paths anchored through one store module
  (`core/pdf_canvas_store.py`) — the known root-vs-`backend/` path bug class stays closed.
- Optimistic concurrency: write requests carry `base_hash`; mismatch → 409 with current version.

### 4.2 Backend

- `core/pdf_engine.py` — deterministic, unit-testable ops: `load/merge/split/rotate/reorder`,
  `set_form_fields` (pypdf AcroForm), `stamp` (reportlab overlay: text, signature image, page
  numbers, headers), `generate_from_template` (reportlab), `extract_text` (reuse
  `DocumentParser`), `flatten`, `redact` (phase 3: content-stream removal + sanitize + verify).
- `core/pdf_canvas_service.py` — lifecycle state machine, versioning, audit, WS broadcast;
  mirrors `canvas_email_service.py` structure.
- `api/canvas_pdf_routes.py` — `POST create` (blank | upload | from_email_attachment |
  from_template | from_zoho_data), `GET file?hash=`, `POST pages|form|annotations|flatten|
  approve|archive|attach-to-email`. Mirrors `canvas_email_routes.py` conventions.
- **attach-to-email** = stage the current (approved, or user-confirmed draft) version via
  `email_attachment_store.save_staged` into the target email canvas → existing
  `EmailAttachmentStrip` + send path light up unchanged. Extend `_record_attachment_state` to
  stamp `{source_canvas_id, version_hash}` so the email audit names the exact PDF version sent.
- Slow ops (OCR of scans, big merges, Zoho→PDF generation with tables/charts) run via
  `_spawn_background_task` with progress broadcast on `canvas:update`; SQS handler when deployed.

### 4.3 Agent surface (`tools/pdf_canvas_tool.py`)

Read (planner-safe, like `email_attachment_get_text`): `pdf_canvas_read_text`,
`pdf_canvas_get_metadata`, `pdf_canvas_list_versions`.
Write (gated by `autonomy_policy` topic `pdf_canvas`; propose-by-default → `AgentProposal`):
`pdf_canvas_set_form_fields`, `pdf_canvas_apply_page_ops`, `pdf_canvas_annotate`,
`pdf_canvas_merge`, `pdf_canvas_generate_from_data`, `pdf_canvas_attach_to_email`.
- Chat wiring: in `chat_orchestrator._try_canvas_edit`, when the open canvas is `pdf`, metadata/
  title edits still go through `CanvasPatchOp` on the content JSON, but content edits are answered
  with proposed tool actions (research finding #2) — never LLM patching of bytes.
- Validation loop: after a write op the agent receives extraction of the affected page/text
  (and, when the harness supports it, a rendered page image) to confirm the edit before
  proposing approval.

### 4.4 Frontend

- `components/canvas/canvasType.ts`: add `pdf`; `CanvasPanel.tsx`: `case "pdf"` → new
  `PdfFileCanvas.tsx` (mirrors `OfficeFileCanvas`, WS-snapshot re-render).
- Viewer: `pdfjs-dist` lazy-loaded chunk; pages rendered to canvas with an annotation overlay
  (annotations stay a JS data model until save — enables undo/redo per research #1); AcroForm
  widgets interactive; save posts deltas (`form_values`, `annotations`, page ops) to the server,
  which returns the new version hash → `canvas:update` WS refreshes all viewers.
- Right rail: lifecycle chip (Drafting/In review/Approved/Sent/Archived), Approve button (HITL),
  version history (reuse `CanvasVersionHistory`), **Attach to email** action (new or existing
  email canvas). Email side: staged attachment shows provenance chip ("PDF canvas 'Q3 Quote' v4
  · hash ab12ef").
- Text/agent panel: extraction view + "ask the agent about this document" chat affordance
  (reuses existing chat → canvas context plumbing).

### 4.5 Lifecycle & governance

`drafting → in_review → approved → sent → archived`
- Drafting: free edits by user or agent (every op audited, versioned).
- Approved: content immutable — edits must fork a new draft version from approved (playbook
  retire/re-draft analog). Only `attach-to-email` and `archive` allowed.
- Agent default = propose (HITL). Per-user autonomy escalation can later allow auto-apply in
  `drafting` only — never on approved docs. The playbook auto-approve latch is deliberately NOT
  applied to PDFs at launch (financial/legal artifacts; evidence-based latch is a later,
  eval-gated option).
- Send path: `attach-to-email` records provenance; `EmailCanvasService.send_email` records
  `message_id` back into `lifecycle.sent_refs`.

## 5. Phases

1. **P1 — Canvas exists & reaches email (MVP).** `pdf` canvas type; upload + blank create;
   PDF.js viewer; page ops (rotate/reorder/delete/merge-in); save → versioned + audited;
   attach-to-email + send via existing staging path; provenance in send audit.
2. **P2 — Agent lifecycle.** `pdf_canvas_tool` read/write tools + autonomy gate + proposals;
   in_review/approve states; generation from business data (quote/invoice/order-confirm
   templates via reportlab, seeded from Zoho Books/Inventory reads); "save email attachment as
   PDF canvas" inbound flow; background jobs for slow ops.
3. **P3 — Trust operations.** AcroForm fill + flatten-on-send option; redaction
   (remove + sanitize + verify test); OCR of scanned inbound PDFs (Docling already present);
   annotations persisted as real PDF annotations; pikepdf if content-stream surgery needed.
4. **P4 — Sign & archive.** Internal stamp signing (SignatureEditor image → reportlab);
   DocuSign envelope integration for external signing; WorkDrive/OneDrive archive (needs
   `onedrive_service` upload-session extension) + Graph cloud (reference) attachments for
   >3MB sends without embedding; PDF/A-flavored archival export; retention policies.

## 6. Verification (per AGENTS.md)

- Unit tests: `backend/tests/test_pdf_engine.py` with committed fixture PDFs — form values read
  back after set; merged page counts/order; flattened output has no interactive fields;
  redacted text absent from extraction; every op idempotent given same inputs.
- Route/tool tests mirroring `test_playbook_draft_editing.py` (state machine: edit-after-approve
  → 409) and `test_playbook_auto_approve_latch.py` style for any future automation.
- Frontend: `PdfFileCanvas` tests modeled on `PlaybookSection.test.tsx`.
- End-to-end at the boundary the user touches: **`scripts/restart_backend.sh` first** (no
  `--reload`), then UI run: upload → agent form-fill proposal → approve → attach to email →
  send → assert `CanvasAudit` rows + `sent_refs` hash matches the delivered attachment bytes.

## 7. Risks / open decisions

- **pypdf AcroForm appearance streams** are the #1 cross-viewer breakage (research #1) —
  mitigate with flatten-on-send default for outbound forms; test in ≥2 viewers.
- **Browser memory on large PDFs** — cap sizes to the attachment-store budgets (20/50MB),
  render lazily page-by-page.
- **AGPL temptation** (PyMuPDF) — stay BSD/MPL; if extraction quality ever demands more, use
  Docling (already integrated) or revisit licensing explicitly.
- **Server-authoritative vs client pdf-lib saves**: chosen server-side (repo deps + audit +
  one engine for user AND agent edits), against the more common client-side pattern — flagged
  per AGENTS.md §3; flip only if offline editing becomes a requirement.
- **Zoho PDF export**: Zoho Books has no PDF endpoint in our service layer; we generate our own
  branded PDFs from the same data (also gives template control). Revisit if Zoho-native PDFs
  are legally required.
