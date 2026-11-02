# Presentation-binding repair — test results

## Normal-app quote/service/exception (17 checks)

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | promoted document lesson is explicit and source-bound | PASS | {"proposal": 200, "promote": 200} |
| 2 | quote receipt starts an ordinary assignment | PASS | {"run_id": "28fe7012-1511-4115-8182-d5a2305c1a91", "status": "waiting"} |
| 3 | real backend restart preserves the prepared action | PASS | {"old_backend_pid": 87251, "new_backend_pid": 87678, "old_frontend_pid": 87264, "new_frontend_pid": 87698} |
| 4 | prepared action survives restart without dispatch | PASS | {"pending_steps": [{"step_id": "action-publish", "status": "awaiting_approval"}], "before_restart": {"operation_id": "3fbb4144-9839-4570-8457-23d2a0072c33", "pa |
| 5 | quote assignment completes after action approval | PASS | {"status": "completed", "steps": ["receipt", "artifact", "guard-publish", "action-publish"]} |
| 6 | quote document artifact is attached | PASS | [{"deliverable_id": "del-document", "kind": "document", "description": "document from canvas aa559ad1-6922-4544-9f22-d3a259bc3a08", "required": true, "step_id": |
| 7 | quote document contains the server total and provenance | PASS | {"bytes": 37252} |
| 8 | quote document consumes the promoted lesson | PASS | {"font": "Georgia", "size_pt": 18.0} |
| 9 | declared registered action has readback evidence | PASS | {"step": [{"step_id": "action-publish", "title": "Execute declared action publish", "operation_type": "outbound", "adapter": "canvas.action", "depends_on": ["gu |
| 10 | duplicate continuation does not dispatch the action again | PASS | {"approve_status": 404, "before_remote": "da30ae31-3d2f-4b10-a6cf-60748b5c0318", "after_remote": "da30ae31-3d2f-4b10-a6cf-60748b5c0318", "audit_count_before_dup |
| 11 | source change produces a new server receipt | PASS | {"row_count": 2, "aggregates": {"line_total": "450.00"}} |
| 12 | old source receipt is refused after the change | PASS | {"status": 409, "error": "stale_revision"} |
| 13 | service proposal completes with a document artifact | PASS | {"status": "completed"} |
| 14 | service document carries the CAD total and lesson | PASS | {"bytes": 37250, "font": "Georgia", "size_pt": 18.0} |
| 15 | exception queue completes with a document artifact | PASS | {"status": "completed"} |
| 16 | exception document carries the counts and lesson | PASS | {"bytes": 37234, "font": "Georgia", "size_pt": 18.0} |
| 17 | cancelled action assignment is terminal | PASS | {"status": 200} |

Result: **passed**, 17/17.

## Oracle presentation controls

| Control | Result | Log |
|---|---|---|
| Supplied negative probes: wrong markdown (same title), wrong chart values (same count), old audit | **3 passed** | `negative-probe.log` |
| Exact material/operation family + forged digest + concurrent + old audit + missing audit + pre-dispatch missing material + handler mutation + positive twin | **28 passed** | `focused-controls.log` |

## Suites

| Suite | Command | Result | Log |
|---|---|---|---|
| Backend combined (28 files) | `TESTING=1 pytest <28 files> -q` | **470 passed** | `backend-tests.log` |
| Frontend canvas panels | `jest CanvasCapabilityAssessment CanvasCapabilityDerive CanvasCapabilityRules --runInBand` | **7 passed** | `frontend-tests.log` |

## Effect and identity checks

- Action remote id `da30ae31-3d2f-4b10-a6cf-60748b5c0318`; audit row operation id `3fbb4144-9839-4570-8457-23d2a0072c33` (the same pending operation across restart); `canvas_audit` **1 before and 1 after** duplicate approval.
- Pending operation id and payload digest `859e4a9c…` identical before/after restart, `remote_id=null`.
- Documents: quote `ae65495b…` (350.00), service `e148adc5…` (630.00 CAD), exception `b9401870…` (3/170.00); Georgia 18.
- Oracle inventory: 6/6 external, 8/8 local durable mutations, 1/1 structural plan output; 827 HTTP mutation declarations and 311 provider writes remain unqualified.

## Invoice → Books rerun (12 checks)

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | invoice bytes parse through the normal document route | PASS | {"method": "fallback", "chars": 213, "document_id": "0d984ba3-bbf6-41ac-9055-593133c042e0"} |
| 2 | invoice facts are extracted from the returned bytes | PASS | {"vendor": "Acme", "total": "120.00", "lines": [{"description": "Parts", "amount": "100.00", "account_label": "Parts"}, {"description": "Fre |
| 3 | normal assignment starts from the invoice facts | PASS | {"run_id": "e0866476-a192-46cb-8c42-ad2fe37efb5a", "status": null} |
| 4 | vendor, CoA and balanced proposal resolve before approval | PASS | {"create": "awaiting_approval", "vendor": "applied", "accounts": "applied", "propose": "applied"} |
| 5 | proposal is exact, balanced and not yet posted | PASS | {"status": "proposed", "total": "120.00", "duplicate_key": "zoho_books|org-1|bill|INV-IN-1"} |
| 6 | real backend restart preserves the pending approval | PASS | {"old_backend_pid": 88008, "new_backend_pid": 88410, "old_frontend_pid": 88030, "new_frontend_pid": 88442} |
| 7 | reopened assignment still awaits the same approval | PASS | {"status": "awaiting_approval", "operation_id": "ddb56a44-00b7-4940-9fdb-8905c9a64dc8"} |
| 8 | approval is accepted once | PASS | {"status": "approved", "operation": {"schema_version": 1, "operation_id": "ddb56a44-00b7-4940-9fdb-8905c9a64dc8", "objective_id": "54747bd0- |
| 9 | one registered Books create completes with readback | PASS | {"status": "applied", "remote_id": "bill-controlled-1", "verification": {"effect": "observed", "status": "verified", "checked_fields": ["ven |
| 10 | provider effect count is exactly one | PASS | {"before": 0, "after": 1, "readbacks": 1} |
| 11 | duplicate continuation is refused without a second effect | PASS | {"approve_status": 404, "creates": 1} |
| 12 | same invoice is refused as a duplicate without a second create | PASS | {"creates": 1, "step_status": "failed", "message": "registered action connected.books.create_bill did not apply: duplicate"} |

Result: **passed**, 12/12.
