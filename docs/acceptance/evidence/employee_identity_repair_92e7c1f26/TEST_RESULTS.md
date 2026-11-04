# Focused identity repair — test results

Source: `92e7c1f26ee70b79b4f6c1ad332769e5329294de`

## Focused affected suite

Command from clean worktree `/private/tmp/atom-integrated-92e/backend`:

```
PYTHONDONTWRITEBYTECODE=1 TESTING=1 PYTHONPATH=$PWD python -B -m pytest \
  /private/tmp/test_verifier_byok_incident_identity_73c.py \
  /private/tmp/test_verifier_byok_boundaries_2ed.py \
  /private/tmp/test_verifier_byok_recovery_epoch_77d.py \
  /private/tmp/test_verifier_employee_completion_6db.py \
  /private/tmp/test_verifier_employee_subject_70a.py \
  tests/test_workload_incident_identity.py \
  tests/test_workload_capability_routing.py tests/test_capability_routing.py \
  tests/test_pinned_planning_scope.py tests/test_pinned_planning_transport.py \
  tests/test_llm_service_task_type_forwarding.py \
  tests/test_learning_llm_router.py tests/test_employee_proposal.py \
  tests/test_employee_adaptation_contract.py \
  tests/test_employee_work_requests.py \
  tests/test_employee_work_request_bindings.py \
  tests/test_employee_work_request_matrix.py \
  tests/test_employee_business_requirements.py \
  tests/test_employee_durable_wait_g5.py \
  tests/test_employee_two_domain_campaign.py \
  tests/test_assignment_routes.py tests/test_assignment_executor.py \
  tests/test_employee_evidence_change_g5.py \
  tests/test_employee_evidence_reassessment_g5.py \
  tests/test_employee_outcome.py tests/test_employee_patch_invariants.py
```

Result: **402 passed, 921 warnings in 100.65s**. Log: `focused-tests.log`.

## Independent subject probe

`/private/tmp/test_verifier_employee_subject_70a.py`:

- `PO-88410` vs required `PO-8841`: rejected
- `PO-884` vs required `PO-8841`: rejected
- `PO-other` + `invoice_id=PO-8841`: rejected

Result: **3 passed**. Log: `verifier-subject.log`.

## Added boundary matrix

`tests/test_employee_business_requirements.py` covers:

- exact positive twin;
- longer and shorter PO prefixes;
- swapped PO/invoice namespaces;
- leading zeros and punctuation;
- wrong invoice identity with the correct PO;
- missing observed identity;
- every required identity must match;
- ambiguous accepted PO candidates bind no identity;
- public status route negative/positive twins;
- fresh-session lifecycle durability of the structured requirement.

`tests/test_employee_durable_wait_g5.py` asserts the compiler-bound
`{"po_id": "PO-8841", "invoice_id": "INV-7"}` identity.

## Frontend

- AssignmentPanel: **9 passed** (`frontend-panel.log`)
- `tsc --noEmit --incremental false`: exit 0 (`frontend-tsc.log`)

## Preserved episode

The accepted episode remains at source
`70a74cd02b5d12acc6b6fead3215196e155640f8`, evidence
`4fd8951cc20cfe20063da336029d421843220e51`. No UI/model rerun was performed
for this focused repair; its artifact hash and operation identities are
unchanged.
