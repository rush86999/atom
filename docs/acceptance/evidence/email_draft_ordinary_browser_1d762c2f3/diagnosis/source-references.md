# Source references — frozen 1d762c2f3

All excerpts are read from the immutable worktree at
`1d762c2f3daee7746cf2430cd3ae37e8971364f7` (product bytes match clean PR829
`7fb2645c9`; the branch deltas are evidence/CI only).

## The ordinary UI save path (what the passing capture exercised)

`frontend-nextjs/components/canvas/CanvasPanel.tsx`

- `auditTrailContent()` — lines 191–213. For `component === "email"` it builds
  the PUT body by spreading the existing payload and replacing the canonical
  fields from panel state:

  ```tsx
  return {
      content: {
          ...existing,
          to: emailMetadata.to,
          cc: emailMetadata.cc,
          subject: emailMetadata.subject,
          body: localContentRef.current,
      },
      echo: localContentRef.current || "",
  };
  ```

- The panel marks edits dirty and schedules the 3 s idle autosave on both the
  metadata fields and the body (lines 981–983):

  ```tsx
  setEmailMetadata={(m) => { setEmailMetadata(m); setHasUnsavedChanges(true); scheduleAutosave(); }}
  onEmailBodyChange={(v) => { setEmailBody(v); localContentRef.current = v; setHasUnsavedChanges(true); scheduleAutosave(); }}
  ```

`frontend-nextjs/components/canvas/EmailRecipientField.tsx` — the To/Cc inputs
are controlled and call `onChange(e.target.value)`.

`frontend-nextjs/components/canvas/RichTextEditor.tsx` — the body is a
`contentEditable` surface; `emit()` sanitizes `innerHTML` and calls `onChange`
on `onInput` and `onBlur` (lines 256–260, 547).

`frontend-nextjs/lib/canvasAuditSave.ts` — `saveCanvasAuditReceipt` sends
`PUT /api/canvas/{id}?…&expected_prior_audit_id=…` and requires a
`verification.status === "verified"` receipt with an exact `audit_id`.

## The write normalizer

`backend/tools/canvas_crud_tool.py` — `canonical_update_content` (line 1250)
routes non-pinned email writes through `coerce_email_canvas`.

`backend/core/chat_draft_classifier.py` — `normalize_email_content` (line 591).
When the submitted dict contains a nested `draft` dict, it rebuilds the
canonical fields **from that draft** (lines 605–619):

```python
draft = content.get("draft")
if isinstance(draft, dict):
    to = draft.get("to_emails")
    cc = draft.get("cc_emails")
    return {
        **content,
        "to": ", ".join(to) if isinstance(to, list) else str(to or ""),
        "cc": ", ".join(cc) if isinstance(cc, list) else str(cc or ""),
        "subject": str(draft.get("subject") or content.get("subject") or ""),
        "body": _style_markdown_tables(str(draft.get("body") or "")),
    }
```

`backend/api/canvas_email_routes.py` — the read-side visible view documents the
opposite precedence (top-level wins by key presence, lines 131+). The two
normalizers therefore disagree when a nested `draft` survives on the content.

## Why the first attempt looked like a save failure

The first harness seed wrote a full legacy `draft` dict into the canvas
content in addition to the canonical `{to, cc, subject, body}`. The panel then
sent `{...existing(draft), to/cc/subject/body = NEW}`; the write normalizer
preferred the nested draft and persisted the OLD seed on three 200 OK PUTs
(audits `d50f53ca`, `17aedd92`, `b8d4719c`, `dd77d154`). This was a harness
seed-shape issue, not a failure of the ordinary panel or save transport.

The corrected, disclosed seed used the ordinary shape only
(`{to, cc, subject, body}`), with no nested `draft`. On that shape the same
ordinary UI autosave persisted every visible field and the fresh-context
reload matched the public GET and the durable audit row.

See `pure-function-proof.txt` for the module-level, DB-free demonstration of
both cases.
