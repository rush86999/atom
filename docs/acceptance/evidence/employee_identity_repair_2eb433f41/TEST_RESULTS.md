# Focused empty-scope identity repair — test results

Source: `2eb433f41fdcaeca1a51dd774bfe6bea5b9791be`

## Focused affected suite

Command from clean worktree `/private/tmp/atom-integrated-2eb/backend`:

```
PYTHONDONTWRITEBYTECODE=1 TESTING=1 PYTHONPATH=$PWD python -B -m pytest \
  /private/tmp/test_verifier_byok_incident_identity_73c.py \
  /private/tmp/test_verifier_byok_boundaries_2ed.py \
  /private/tmp/test_verifier_byok_recovery_epoch_77d.py \
  /private/tmp/test_verifier_employee_completion_6db.py \
  /private/tmp/test_verifier_employee_subject_70a.py \
  /private/tmp/test_verifier_employee_empty_subject_a2c.py \
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

Result: **410 passed, 937 warnings in 94.71s**. Log: `focused-tests.log`.

## Empty-scope probe

`/private/tmp/test_verifier_employee_empty_subject_a2c.py` plus the prior
wrong-subject probe: **5 passed**. Log: `verifier-empty-subject.log`.

- `quote_calculation` with no subject/identity and no receipts: unresolved
- `invoice_reconciliation` with no subject/identity and no receipts: unresolved
- empty invoice scope with an exact invoice receipt: still unresolved
- unscoped quote with a verified quote receipt: satisfied
- unscoped quote with an unrelated or failed receipt: unresolved
- wrong PO/subject receipts: rejected
- exact namespaced PO/invoice receipt: satisfied

## Added controls

- no result, unrelated result, failed/unapplied result, missing scoped identity,
  exact result, wrong identity;
- public status route empty-scope negative and exact positive;
- artifact guard refuses missing-scope and wrong-subject report publication,
  allows the exact positive;
- fresh-session lifecycle requirement durability;
- `business_requirement_views` reports `unresolved` with an exact-record next
  action for missing invoice identity.

## Frontend

- AssignmentPanel: **9 passed** (`frontend-panel.log`)
- `tsc --noEmit --incremental false`: exit 0 (`frontend-tsc.log`)

## Preserved episode

The supported episode remains source
`70a74cd02b5d12acc6b6fead3215196e155640f8`, evidence
`4fd8951cc20cfe20063da336029d421843220e51`; no UI/model rerun was performed.
