# Consolidated integrated test results

## Quote / service / exception journey (17 checks)

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | promoted document lesson is explicit and source-bound | PASS | {"proposal": 200, "promote": 200} |
| 2 | quote receipt starts an ordinary assignment | PASS | {"run_id": "c6186761-b0cb-4b5c-bce6-a5765a1a5f22", "status": "waiting"} |
| 3 | real backend restart preserves the prepared action | PASS | {"old_backend_pid": 81498, "new_backend_pid": 81886, "old_frontend_pid": 81514, "new_frontend_pid": 81903} |
| 4 | prepared action survives restart without dispatch | PASS | {"pending_steps": [{"step_id": "action-publish", "status": "awaiting_approval"}], "before_restart": {"operation_id": "691d0af0-3ad7-4d83-9a64-e2bd3ebda516", "payload_sha256": "b8ad |
| 5 | quote assignment completes after action approval | PASS | {"status": "completed", "steps": ["receipt", "artifact", "guard-publish", "action-publish"]} |
| 6 | quote document artifact is attached | PASS | [{"deliverable_id": "del-document", "kind": "document", "description": "document from canvas 71b74821-0402-4be7-b849-70d1a656a3f6", "required": true, "step_id": "artifact", "status |
| 7 | quote document contains the server total and provenance | PASS | {"bytes": 37254} |
| 8 | quote document consumes the promoted lesson | PASS | {"font": "Georgia", "size_pt": 18.0} |
| 9 | declared registered action has readback evidence | PASS | {"step": [{"step_id": "action-publish", "title": "Execute declared action publish", "operation_type": "outbound", "adapter": "canvas.action", "depends_on": ["guard-publish"], "requ |
| 10 | duplicate continuation does not dispatch the action again | PASS | {"approve_status": 404, "before_remote": "d398c22a-88e4-47eb-94ee-359832d5b7b4", "after_remote": "d398c22a-88e4-47eb-94ee-359832d5b7b4", "audit_count_before_duplicate": 1, "audit_c |
| 11 | source change produces a new server receipt | PASS | {"row_count": 2, "aggregates": {"line_total": "450.00"}} |
| 12 | old source receipt is refused after the change | PASS | {"status": 409, "error": "stale_revision"} |
| 13 | service proposal completes with a document artifact | PASS | {"status": "completed"} |
| 14 | service document carries the CAD total and lesson | PASS | {"bytes": 37245, "font": "Georgia", "size_pt": 18.0} |
| 15 | exception queue completes with a document artifact | PASS | {"status": "completed"} |
| 16 | exception document carries the counts and lesson | PASS | {"bytes": 37228, "font": "Georgia", "size_pt": 18.0} |
| 17 | cancelled action assignment is terminal | PASS | {"status": 200} |

Result: **passed**, 17/17.

## Invoice → Books journey (12 checks)

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | invoice bytes parse through the normal document route | PASS | {"method": "fallback", "chars": 213, "document_id": "85463913-d5b9-4e02-9d8d-5c8973032410"} |
| 2 | invoice facts are extracted from the returned bytes | PASS | {"vendor": "Acme", "total": "120.00", "lines": [{"description": "Parts", "amount": "100.00", "account_label": "Parts"}, {"description": "Freight", "amount": "20.00", "account_label |
| 3 | normal assignment starts from the invoice facts | PASS | {"run_id": "16abe130-4812-402a-ba2e-2d411f75d165", "status": null} |
| 4 | vendor, CoA and balanced proposal resolve before approval | PASS | {"create": "awaiting_approval", "vendor": "applied", "accounts": "applied", "propose": "applied"} |
| 5 | proposal is exact, balanced and not yet posted | PASS | {"status": "proposed", "total": "120.00", "duplicate_key": "zoho_books|org-1|bill|INV-IN-1"} |
| 6 | real backend restart preserves the pending approval | PASS | {"old_backend_pid": 82375, "new_backend_pid": 82601, "old_frontend_pid": 82394, "new_frontend_pid": 82618} |
| 7 | reopened assignment still awaits the same approval | PASS | {"status": "awaiting_approval", "operation_id": "ccbd3508-f302-47c6-b112-c0ba601bcdd6"} |
| 8 | approval is accepted once | PASS | {"status": "approved", "operation": {"schema_version": 1, "operation_id": "ccbd3508-f302-47c6-b112-c0ba601bcdd6", "objective_id": "8a632db9-be28-4c76-a618-d957561fb2dc", "objective |
| 9 | one registered Books create completes with readback | PASS | {"status": "applied", "remote_id": "bill-controlled-1", "verification": {"effect": "observed", "status": "verified", "checked_fields": ["vendor_id", "currency_code", "date", "due_d |
| 10 | provider effect count is exactly one | PASS | {"before": 0, "after": 1, "readbacks": 1} |
| 11 | duplicate continuation is refused without a second effect | PASS | {"approve_status": 404, "creates": 1} |
| 12 | same invoice is refused as a duplicate without a second create | PASS | {"creates": 1, "step_status": "failed", "message": "registered action connected.books.create_bill did not apply: duplicate"} |

Result: **passed**, 12/12.

## Suites

| Suite | Command | Result | Log |
|---|---|---|---|
| Backend combined (27 files) | `TESTING=1 pytest <27 files> -q` | **454 passed** | `backend-tests.log` |
| Frontend canvas panels | `jest CanvasCapabilityAssessment CanvasCapabilityDerive CanvasCapabilityRules --runInBand` | **7 passed** | `frontend-tests.log` |

## Effect counts

- Quote action: remote id `d398c22a-88e4-47eb-94ee-359832d5b7b4`; `canvas_audit` **1 → 1** across duplicate approval; approval refused `404`.
- Books: one `connected.books.create_bill`, `creates=1`, `readbacks=1`; second assignment refuses with a duplicate message and `creates` stays 1; step status `failed` (proven no effect).
- Restart: the pending approval operation id is unchanged in both journeys.
- Oracle registry union: 16 verifiers; inventory 6/6 external and 9/9 local registered action mutations.
