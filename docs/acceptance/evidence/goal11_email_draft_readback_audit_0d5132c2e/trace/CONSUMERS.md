# Email draft consumers and parallel writers (source at 0d5132c2e)

## Ordinary UI save

- `frontend-nextjs/components/canvas/CanvasPanel.tsx`
  - `handleSave` → `auditTrailContent()`; for email the native dict is
    `{to, cc, subject, body}` (plus thread/attachment fields when present).
  - Guarded frames call `saveCanvasAuditReceipt(..., {expectedPriorAuditId})`
    → `PUT /api/canvas/{id}?canvas_type=email`.
  - Legacy unguarded frames call `saveCanvasAudit` (same generic endpoint,
    no prior token).
  - Email saves never fall through to the legacy artifacts store; a failed
    audit save keeps the draft dirty.
- `frontend-nextjs/lib/canvasAuditSave.ts` — verifies exact canvas id and
  receipt; unconfirmed outcomes are typed non-retryable errors.
- `frontend-nextjs/pages/canvas/[id].tsx` — loads `GET /api/canvas/{id}` and
  binds `canvasData.content` to the panel.

## Generic shared writer/read

- `backend/api/canvas_routes.py` `PUT /{canvas_id}` →
  `core.canvas_write_service.update_canvas_verified`:
  current actor/scope preflight, expected-prior audit CAS, durable append,
  postcondition envelope (`verification.status`).
- `backend/api/canvas_routes.py` `GET /{canvas_id}` →
  `tools.canvas_crud_tool.read_canvas` / `visible_canvas_material`.
- Prior accepted evidence `docs/acceptance/evidence/connected_core_20261028/
  employee_email_draft.json` and `employee_email_reopen.json` were produced by
  this path (`write_outcome=committed`, `action_type=update`, generic read
  `content`).

## Email-specific API (parallel writer/read)

- `backend/api/canvas_email_routes.py`
  - `_get_owned_email_canvas_or_error`: first email audit row's `user_id` only;
    no current active-actor/is_active or tenant/workspace check.
  - `POST /create` → `EmailCanvasService.create_email_canvas`.
  - `POST /{id}/draft` → `EmailCanvasService.save_draft`.
  - `GET /{id}` → newest `CanvasAudit.details_json` (expects email `draft`).
  - `POST /{id}/message`, attachments, `/send` → same service family.
- `backend/core/canvas_email_service.py`
  - `create_email_canvas` writes Canvas + audit with hardcoded
    `tenant_id="default"`, `workspace_id="default"`.
  - `save_draft` checks only first-audit owner, reads the newest audit,
    mutates the Canvas mirror directly, appends a new audit row with
    `tenant_id="default"`; no current scope, no expected-prior/CAS.
  - `record_send`/attachment rows also use `tenant_id="default"`; send
    governance is separate and is not changed by this audit.
- `backend/tests/api/test_canvas_email_routes.py` exercises `/create`,
  `/message`, `/draft`, `/categorize`; it does not assert active-actor scope,
  tenant scope, expected-prior conflict or generic/email read agreement.

## Other draft producers (not ordinary canvas save)

- `backend/core/assignment_executor.py` `email.draft` adapter composes an
  assignment draft result; it does not write the canvas DB row.
- `backend/api/canvas_pdf_routes.py` can stage a PDF onto an email canvas as a
  draft; it uses the email service family.
- Chat/agent canvas presentation writes through the generic canvas tools, not
  `save_draft`.

## Conclusion

The generic path is already the accepted, shared, scope/CAS-aware mechanism.
The email-specific `/draft` writer and its create/read siblings are a second
mutation/read path with weaker guarantees. The finite repair should collapse
that path onto the shared mechanism; no new engine/store/CAS/approval lifecycle
is justified.
