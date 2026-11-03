# Presentation binding repair — results

Executed source: `0d8767e3ac2494dd7a4b88ffc790f898035e8586` (clean).

## Independent negative controls

`local-present-probe.log`: **3 passed**.

| Control | Expected |
|---|---|
| Approved markdown `350.00`, audit same title but `999.00` | uncertain |
| Approved chart y=350, audit same type/count but y=999 | uncertain |
| New operation, old audit with identical content | uncertain |

Positive twins, handler argument mutation, forged returned digest, missing
audit, missing material, wrong canvas/workspace, same-content old audit and
concurrent presentations are covered in:

- `tests/test_oracle_canvas_postcondition.py`
- `tests/test_oracle_effect_families.py`
- `tests/test_presentation_binding_controls.py`
- `tests/test_canvas_present_actions.py`

## Combined backend matrix

```text
TESTING=1 PYTHONPATH=backend pytest <18 files> -q
```

Result: **288 passed** (`backend-tests.log`), including all original, adjacent
and immutable-request oracle probes plus the three local-present controls.

## Frontend

Result: **7 passed** (`frontend-tests.log`).

## Normal-app quote/service/exception

Log: `quote-journey.log`; result: `quote-journey-result.json`.

Result: **17/17 passed**. Pending operation/payload identity is preserved
across the real process restart; action audit count is 1 before and 1 after
duplicate approval; quote `350.00`, service `630.00 CAD`, exception
`3 / 170.00`; all three DOCX files consume Georgia 18 and carry receipt
provenance.

## Invoice-to-Books

Log: `bookkeeping-journey.log`; result: `bookkeeping-result.json`.

Result: **12/12 passed**. One governed Books create `bill-controlled-1`,
verified material readback, creates `0 → 1`, readbacks 1, duplicate approval
404 and repeat invoice refused with no second create.

## Oracle registry and inventory

`oracle-registry.txt`: 16 loaded verifiers.

`oracle-whole-app-inventory/inventory.json`:

| Class | Count | Covered |
|---|---:|---:|
| External/provider mutations | 6 | 6 |
| Local durable mutations | 8 | 8 |
| Plan-output validators | 1 | structural only |
| Mutating HTTP declarations | 827 | unqualified |
| Provider write methods | 311 | unqualified |

`goals.decompose` is classified as plan-output validation, not persisted
execution proof.

## Boundaries

No live provider action. No whole-app ORACLE-01 closure, model-quality, soak,
multi-worker or live-provider claim.
