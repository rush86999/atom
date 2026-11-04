# Test results — BYOK incident-bound recovery

Source: `73cb1da513b2ecf6134b900ca3224750b48109a2`.

## Focused suite

Command from clean worktree `/private/tmp/atom-byok-epoch/backend`:

```
PYTHONDONTWRITEBYTECODE=1 TESTING=1 PYTHONPATH=$PWD python -B -m pytest \
  /private/tmp/test_verifier_byok_boundaries_2ed.py \
  /private/tmp/test_verifier_byok_recovery_epoch_77d.py \
  tests/test_workload_capability_routing.py tests/test_capability_routing.py \
  tests/test_pinned_planning_scope.py tests/test_pinned_planning_transport.py \
  tests/test_llm_service_task_type_forwarding.py tests/test_employee_proposal.py \
  tests/test_employee_adaptation_contract.py tests/test_employee_work_requests.py \
  tests/test_employee_work_request_bindings.py tests/test_learning_llm_router.py
```

Result: **162 passed, 423 warnings in 17.90s**. Log: `focused-tests.log`.

## Independent probes

- `verifier-boundaries.log`: **5 passed** (strict pin, semantic success,
  one-event unsafe, missing scope, decision-history scope).
- `verifier-recovery-epoch.log`: **1 passed** (old recovery does not release a
  newer unsafe incident).

## Controlled probe

`routing-probe.json`: economy Flash wins; explicit quality preference selects
the stronger eligible route; semantic-only success is `no_suitable`;
missing-workspace evidence is `{}`; one unsafe event quarantines; incident-bound
reviewed recovery returns the route to `selected`.

## Recovery epoch controls

- First quarantine → reviewed recovery → new unsafe incident → quarantine.
- Restart still quarantined (journal/file reads).
- Second reviewed recovery releases only the second incident.
- Duplicate recovery is idempotent.
- Missing/malformed incident IDs or missing ordering fail closed.
- Two scopes and unrelated workloads remain isolated.
- Capable-Flash economy and explicit quality preference twins remain covered.

No provider call, credential change, download or spend was made.
