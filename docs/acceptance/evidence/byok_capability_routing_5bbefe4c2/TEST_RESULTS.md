# Test results — BYOK durable incident identity

Source: `5bbefe4c2d84ba62673bd298a0561d0c3aa434de`.

## Focused suite

Command from clean worktree `/private/tmp/atom-byok-identity/backend`:

```
PYTHONDONTWRITEBYTECODE=1 TESTING=1 PYTHONPATH=$PWD python -B -m pytest \
  /private/tmp/test_verifier_byok_incident_identity_73c.py \
  /private/tmp/test_verifier_byok_boundaries_2ed.py \
  /private/tmp/test_verifier_byok_recovery_epoch_77d.py \
  tests/test_workload_incident_identity.py \
  tests/test_workload_capability_routing.py tests/test_capability_routing.py \
  tests/test_pinned_planning_scope.py tests/test_pinned_planning_transport.py \
  tests/test_llm_service_task_type_forwarding.py tests/test_employee_proposal.py \
  tests/test_employee_adaptation_contract.py tests/test_employee_work_requests.py \
  tests/test_employee_work_request_bindings.py tests/test_learning_llm_router.py
```

Result: **168 passed, 452 warnings in 17.87s**. Log: `focused-tests.log`.

## Independent probes

- `verifier-incident-identity.log`: **1 passed** — production loader keeps the
  exact incident identity/review when a successful feedback row is inserted.
- `verifier-boundaries.log`: **5 passed** — strict pin, semantic outcome,
  one-event unsafe, missing scope, scoped history.
- `verifier-recovery-epoch.log`: **1 passed** — old review does not clear a
  newer unsafe incident.

## Production-loader identity controls

`tests/test_workload_incident_identity.py` (5 tests):

1. New success row inserted ahead of an unchanged unsafe row: incident ID is
   unchanged; existing review remains effective.
2. Unrelated row and reversed row order: incident ID/review unchanged.
3. New unsafe observation after review: route re-quarantines; second reviewed
   recovery releases only that incident; duplicate recovery idempotent.
4. Same row ID with changed material (unsafe → semantic): new incident ID; old
   review does not mark the changed observation reviewed.
5. Legacy row without row ID or trustworthy creation ordering: identity is
   marked unreliable; recovery cannot release it.

The controlled probe also keeps economy-Flash, explicit quality preference,
semantic no-suitable, missing-scope, single-unsafe and reviewed-recovery
behavior.

No provider call, credential change, download or spend was made.
