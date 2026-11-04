# Test results — employee G5 remaining normal-app behaviors

Source: `55eb68aa30be5f698f11a6b2da19628a4f902d97`

## Focused backend suite

Command (from `backend/`, using the local Python 3.14 venv):

```
PYTHONDONTWRITEBYTECODE=1 TESTING=1 PYTHONPATH=$PWD python -B -m pytest \
  /private/tmp/test_verifier_terms_20f.py \
  /private/tmp/test_verifier_typed_work_2ce.py \
  /private/tmp/test_verifier_g5_evidence_eligibility_a9.py \
  /private/tmp/test_verifier_g5_currency_7df.py \
  /private/tmp/test_verifier_document_freshness_9f3.py \
  /private/tmp/test_verifier_extraction_labels_2e086.py \
  tests/test_assignment_routes.py tests/test_assignment_executor.py \
  tests/test_employee_proposal.py tests/test_employee_adaptation_contract.py \
  tests/test_employee_work_requests.py \
  tests/test_employee_work_request_bindings.py \
  tests/test_employee_two_domain_campaign.py tests/test_employee_outcome.py \
  tests/test_employee_patch_invariants.py tests/test_employee_proof_binding.py \
  tests/test_employee_prerequisite_eligibility.py \
  tests/test_employee_g5_campaign_guard.py \
  tests/test_employee_document_freshness.py
```

Result: **305 passed, 617 warnings in 66.05s**. Full log:
`focused-tests.log`.

The new regression control is
`tests/test_assignment_executor.py::test_approval_clears_the_matching_human_input_wait`.
It proves the assignment approval wait is entered as `human_input` with exact
`hitl_id`/`correlation_id` identity, and approving the prepared effect
consumes that wait before reconciliation.

## Normal-app campaign

Command:

```
python scripts/acceptance/employee_g5_remaining_normal_app.py \
  --out /private/tmp/g5-remaining-clean --port 8099
```

Result: **18/18 checks passed**. Full log: `harness-run.log`; structured
report: `report.json`.

Checks:

1. normal upload creates the authorized source;
2. artifact objective completes only with an applied artifact;
3. artifact criterion is required and met;
4. artifact bytes match the recorded sha256;
5. artifact content has the exact total, lines and source;
6. independent branches complete while the wait stays open;
7. independent branches have distinct operation receipts;
8. only the affected branch is re-evaluated;
9. unrelated receipt and waiting operation are retained;
10. late response after cancellation is refused;
11. completed branch receipts survive cancellation;
12. controlled outbound awaits explicit approval;
13. provider accepted then lost confirmation;
14. exactly one controlled effect exists;
15. uncertain original operation survives restart;
16. restart creates no second effect;
17. original operation reconciles to applied;
18. reconciled assignment completes without a resend.

## Evidence files

- `report.json` — full structured run/operation/receipt evidence and serving
  identity before/after restart.
- `customer-quote.docx` — exact rendered artifact bytes.
- `outbox.jsonl` — the single controlled effect.
- `server.log` — real application backend log for the world.
- `REPORT.md` — compact check summary.
