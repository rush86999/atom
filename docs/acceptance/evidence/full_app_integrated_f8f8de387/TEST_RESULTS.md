# Integrated candidate results

Executed source: `f8f8de387bfb8979bf9e2d17779f71b53bcb982d` (clean).

## Combined backend matrix

```text
TESTING=1 PYTHONPATH=backend pytest \
  tests/test_oracle_effect_families.py \
  tests/test_oracle_canvas_postcondition.py \
  tests/test_oracle_connected_mutations.py \
  tests/test_canvas_present_actions.py \
  tests/unit/test_brennan_bookkeeping_registered.py \
  tests/unit/test_brennan_bookkeeping_proposal.py \
  tests/test_assignment_executor.py \
  tests/test_canvas_assignment_integration.py \
  tests/test_canvas_typed_fields.py \
  tests/test_canvas_capability_service.py \
  tests/test_tool_error_memento_lifecycle.py \
  tests/test_memento_candidate_review.py \
  tests/unit/test_serialization_budget.py \
  tests/test_assignment_routes.py \
  /private/tmp/test_verifier_oracle_boundaries.py \
  /private/tmp/test_verifier_oracle_repair_boundaries.py \
  /private/tmp/test_verifier_oracle_immutable_request.py -q
```

Result: **269 passed** (`backend-tests.log`).

This includes the original, adjacent and immutable-request oracle probes; the
new effect-family positives/negatives and adapter consumption; connected
readback; bookkeeping proposal/registered action; assignment/executor; canvas
assignment/typed/capability; one-lifecycle Memento; and serialization.

## Frontend

```text
npx jest components/canvas/__tests__/CanvasCapabilityRules.test.tsx \
  components/canvas/__tests__/CanvasCapabilityDerive.test.tsx \
  components/canvas/__tests__/CanvasCapabilityAssessment.test.tsx \
  --runInBand --silent
```

Result: **7 passed** (`frontend-tests.log`).

## Normal-app quote/service/exception journey

Log: `quote-journey.log`; result: `quote-journey-result.json`.

Result: **17/17 passed**. Key measurements:

- pending operation id `1bb1d5a8-...` and payload digest `9041dc6a...`
  identical before/after the real process restart; status still
  `awaiting_approval`, `remote_id=null`;
- action remote id `8502d15f-...`; `canvas_audit` rows **1 before / 1 after**
  duplicate approval; duplicate approval `404`;
- quote DOCX `350.00`, service DOCX `630.00 CAD`, exception DOCX `3 / 170.00`;
  all consume Georgia 18 and carry receipt provenance.

## Invoice-to-Books journey

Log: `bookkeeping-journey.log`; result: `bookkeeping-result.json`.

Result: **12/12 passed**. Key measurements:

- invoice bytes parsed and uploaded through the normal document routes;
- extracted facts: Acme, `INV-IN-1`, USD, `120.00`, two lines (Parts 100.00,
  Freight 20.00);
- vendor and complete CoA resolved; proposal status `proposed`, total `120.00`,
  duplicate key `zoho_books|org-1|bill|INV-IN-1`, payment not posted;
- real backend restart preserves the same pending approval operation;
- one create `bill-controlled-1`; material readback `verified`; provider effect
  count `0 -> 1`; readback count 1;
- duplicate approval `404`, creates unchanged at 1;
- repeat assignment for the same invoice fails with duplicate, creates
  unchanged at 1.

Books state: `books-state.json` (`creates=1`, `readbacks=1`).

## Oracle registry and inventory

`oracle-registry.txt`: 16 loaded verifiers.

`oracle-whole-app-inventory/inventory.json`:

| Class | Count | Covered |
|---|---:|---:|
| Registered actions | 90 | — |
| External/provider mutations | 6 | 6 |
| Local durable mutations | 9 | 9 |
| Mutating HTTP declarations | 827 | unqualified |
| Provider write methods | 311 | unqualified |

## Boundaries

No live provider action. The 827 HTTP declarations are discovery candidates,
not proven reachable writes. No whole-app ORACLE-01 closure, model-quality,
soak, multi-worker or live-provider claim is made.
