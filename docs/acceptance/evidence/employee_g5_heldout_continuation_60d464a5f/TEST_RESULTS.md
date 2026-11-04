# Held-out continuation — test results

Executed source for the recovery: `b16172c8df3a5244f7748282469673b1ee02f294`.
Evidence tip: `60d464a5f1ac4be51a46c3c2f9bfa858c4c3c9d1`.

## Recovery checks

`state.json` records 9/9 checks passed:

- same run and wait identity preserved;
- quote 125.00 with the original operation id preserved;
- reconciliation 101.00;
- assignment completed;
- all business requirements satisfied;
- requested document applied with both totals;
- document sha256 matched.

## Focused regression

Command (backend root, controlled world/`TESTING=1`):

```
python -m pytest \
  tests/test_employee_adaptation_contract.py \
  tests/test_employee_compact_adaptation.py \
  tests/test_employee_business_requirements.py \
  tests/test_employee_durable_wait_g5.py \
  tests/test_employee_work_request_bindings.py \
  tests/test_employee_g5_model_proposal.py \
  tests/test_employee_prerequisite_eligibility.py \
  tests/test_employee_evidence_change_g5.py \
  tests/test_structured_cancellation.py \
  tests/test_workload_capability_routing.py \
  tests/test_pinned_planning_scope.py \
  tests/test_assignment_routes.py::test_budget_extension_raises_limits_without_restarting_the_job \
  -q
```

Result: **130 passed** in 35.34 seconds. Full log: `focused-tests.log`.

The accepted `2eb433f41` 410-test result is not replayed; those controls remain
at their original source. This focused neighborhood covers the changed
runtime, compact context, identity/empty-scope completion guards and the new
budget-extension route.

## Attempt diagnostics

| Attempt | Prompt chars | Model seconds | Outcome |
|---|---:|---:|---|
| 1 | 5,662 | 20.50 | malformed compact output (`$ref` evidence, numeric field-map value) |
| 2 | 5,875 | 11.22 | valid typed replan; adoption refused for missing observation ids |
| 3 | 5,875 | 4.28 | valid typed replan; adoption applied; wall budget reached before the dependent step |

The first two failures are preserved in `attempts-compact-1.jsonl` and
`attempts-compact-2.jsonl`. The third successful compact call is in
`attempts-compact-3.jsonl`. Token usage was present in the provider trace;
the evidence-tip journal change only prevents numeric token counts from being
redacted as secrets.
