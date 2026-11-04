# Fresh held-out two-order batch — test results

Executed source: `3ccad7a5a99afdcef7784f903b3744e36d86ea4b`.

## Batch checks

Each run passed **11/11** named finish checks (**22/22** batch): `same_run`,
`same_wait`, `restart_preserved_waiting`, `quote_total_145`,
`reconciliation_total_113`, `assignment_completed`, `requirements_satisfied`,
`artifact_applied`, `artifact_quote_145`, `artifact_reconciliation_113`,
`artifact_sha_matches`. The state files contain all 11 true checks; the earlier
10/10 summary omitted the separate `same_wait` check. Historical state bytes
were not altered.

| Run | Order | Result |
|---|---|---|
| `cfa9cccf-4049-4f7d-96c8-8d42b4ef48b4` | source authorized before restart | 11/11 |
| `88306561-92b4-492c-a6b3-00d0621c3d08` | restart while waiting, source authorized after restart | 11/11 |

## Focused regression

Command (backend root, `TESTING=1`):

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

Result: **133 passed** in 34.62 seconds. Full log: `focused-tests.log`.

## Scope

This batch establishes the fresh held-out content and both required event
orders at the controlled local scope. It does not establish independent
procurement evidence discovery/selection: the objective supplied the three
relevant authorized source references, so the successful typed role selection
is not a source-selection result. It also does not establish general adaptive
judgment, live-provider breadth, Linux/KVM, multi-worker/soak or whole-app
ORACLE behavior. Overall successor bundle acceptance remains withheld for combined review;
the runtime successor `5abbeaa48` records both worker repairs, and
packaging/source-attribution corrections are included in this evidence commit.
The failed HX same-job continuation bundle remains separate evidence.
