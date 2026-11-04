# Results — original held-out job recovery 8995f433d

Executed source: `8995f433d6fbf2f76a637f7fdce2c2cbf96550e7`.
Run: `367efddf-c4b3-4e02-9ab2-23c737fd162e` (the frozen
`employee_g5_heldout_timeout_6bc97759284` job).

## Focused regression

Command (backend root, controlled `TESTING=1` environment):

```
python -m pytest \
  /private/tmp/test_verifier_byok_incident_identity_73c.py \
  /private/tmp/test_verifier_byok_boundaries_2ed.py \
  /private/tmp/test_verifier_byok_recovery_epoch_77d.py \
  /private/tmp/test_verifier_employee_completion_6db.py \
  /private/tmp/test_verifier_employee_subject_70a.py \
  /private/tmp/test_verifier_employee_empty_subject_a2c.py \
  tests/test_workload_incident_identity.py \
  tests/test_workload_capability_routing.py \
  tests/test_capability_routing.py \
  tests/test_pinned_planning_scope.py \
  tests/test_pinned_planning_transport.py \
  tests/test_llm_service_task_type_forwarding.py \
  tests/test_learning_llm_router.py \
  tests/test_employee_proposal.py \
  tests/test_employee_adaptation_contract.py \
  tests/test_employee_compact_adaptation.py \
  tests/test_employee_work_requests.py \
  tests/test_employee_work_request_bindings.py \
  tests/test_employee_work_request_matrix.py \
  tests/test_employee_business_requirements.py \
  tests/test_employee_durable_wait_g5.py \
  tests/test_employee_two_domain_campaign.py \
  tests/test_assignment_routes.py \
  tests/test_assignment_executor.py \
  tests/test_employee_evidence_change_g5.py \
  tests/test_employee_evidence_reassessment_g5.py \
  tests/test_employee_outcome.py \
  tests/test_employee_patch_invariants.py \
  tests/test_structured_cancellation.py \
  -q
```

Result: **422 passed** in 111.33 seconds. Full log: `focused-tests.log`.

## Provenance correction

The manifest source hash for `backend/core/employee_adaptation.py` was
corrected from `dd3fe402c5cc…` to `291676860ff6…`. The former was collected
from the working tree after the later concurrent commit `fd6b929f3`; the
latter is `git show 8995f433d:backend/core/employee_adaptation.py`. The
retained launch record proves the loaded source: `server.log` records
`source_id=8995f433d6fb revision=8995f433d6fb dirty=False (0 modified, 0
untracked)`, and `launch.log` records `source=8995f433d6fb`. The backend was
not reloaded, and the recovery call (`19:27:47Z`) preceded the later commit
(`19:30:28Z`). The superseded hash and reason are preserved in
`MANIFEST.json` under `provenance`.

## Compact attempt diagnostics

| Attempt | Source | Prompt chars | Model seconds | Outcome |
|---|---|---:|---:|---|
| Schema echo | `3b3f9ef92` | 5,669 | 32.06 | No proposal. The served model returned instructor's injected schema (`$defs`, `properties`, `required`, `title`, `type`); backend log records 7 validation errors. Deterministic fallback retained the blocked job. |
| Recovery | `8995f433d` | 5,997 | 57.67 | Valid `model_compact` replan with the accepted invoice/PO/receiving step IDs and USD. Adoption applied; pre-dispatch wall-budget refusal preserved; owner extension + retry completed 140.25 and the artifact. |

Both calls used the pinned route `ollama/llama3.1:8b` and the separately declared
`employee_adaptive_planning_compact` v2026-11-04.1 profile. There was no
provider substitution, hidden retry, repair call or unpinned escape.

Raw traces:

- `attempts-schema-echo.jsonl` — dispatch, no-result and deterministic summary
  for the schema-echo attempt.
- `attempts-compact.jsonl` — one compact dispatch and one parsed proposal for
  the recovery.
- `server.log` — provider-side validation trace for the schema echo and the
  successful parsed call.

## Budget boundary and recovery

`advance.json` preserves the first recovery outcome: the compact proposal was
adopted and `invoice-reconcile` was added at revision 6, but the executor
refused the step **before dispatch** with
`assignment_budget_exhausted` (`attempts=0`). The 900 s wall budget had elapsed
while the job was blocked during the offline diagnostic gap.

`budget-extension.json` records the owner action through the public
increase-only route: `max_wall_seconds` 900 → 3600, with the requester and
reason stored on the durable assignment. `retry.json` records the supported
retry of the never-dispatched step and the resulting completed assignment. No
database file was edited.

## Final verified state

`verification.json` records **19/19** checks passed:

- same run and assignment identity;
- same wait identity (`await-ca15973cbdcbe5ff480c`, purchase order PO-7302);
- quote **96.30 USD** and original quote operation retained;
- dependent reconciliation **140.25 USD** with a verified receipt;
- assignment completed at revision 6;
- business-result criterion declared;
- all required business requirements satisfied (1/1);
- overall business outcome satisfied;
- requested document applied, contains both 96.30 and 140.25, sha256 matches;
- no applied external effect;
- served route local only;
- one compact dispatch, no repair/fallback, 57.67 s < 240 s bound;
- owner budget extension recorded and pre-dispatch refusal preserved.

Artifact: `review.docx`, 37,549 bytes, sha256
`609281eb3bdc5dd4a42ea14cc389fb60775271bb5225f017a4a2b2fe88474e2b`.

## Scope

This is a same-job recovery of a known-value held-out job. It does not
establish a fresh unseen-value held-out qualification, alternate served event
ordering, procurement evidence selection, broad model judgment or full G5.
