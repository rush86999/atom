# Full-app journey results

Executed source: `6f697cd9d` (clean tree).

## Browser journey

Command:
```text
python scripts/acceptance/full_app_quote_journey.py \
  --frontend http://127.0.0.1:3137 \
  --api http://127.0.0.1:8096 \
  --password-file <world>/canvas-password.txt \
  --agent-id 5ef8be20-1528-42d2-86e0-5c932c4a45e4 \
  --out-dir <world>/evidence/journey-clean-6f697cd9d
```

Result: **15/15 checks passed** (`result.json`). The run includes a real
backend/frontend restart (`old_backend_pid != new_backend_pid`) and a clean
runtime identity (`dirty=False`).

## Focused regression

```text
TESTING=1 PYTHONPATH=backend pytest \
  tests/test_canvas_assignment_integration.py \
  tests/test_canvas_typed_fields.py \
  tests/test_canvas_capability_service.py \
  tests/test_assignment_executor.py -q
```

Result: **139 passed** (`focused-backend.log`).

## Frontend

```text
npx jest components/canvas/__tests__/CanvasCapabilityRules.test.tsx \
  components/canvas/__tests__/CanvasCapabilityDerive.test.tsx \
  components/canvas/__tests__/CanvasCapabilityAssessment.test.tsx \
  --runInBand --silent
```

Result: **7 passed** (`frontend.log`).

## Artifact checks

- `quote-document.bin` is the downloaded DOCX; its content includes the
  server-calculated `350.00` total and the receipt provenance.
- `quote-journey.png` is the full-page browser evidence.
- The promoted lesson is consumed (`Georgia`, 18 pt) in the downloaded
  document.
- The declared action step is `applied` with a non-empty `remote_id`; duplicate
  approval does not change it.

## Boundaries

No live provider action. The bookkeeping supplier-invoice-to-Zoho-Books loop
and whole-app ORACLE mutation-surface coverage remain separate open work.
