# Test results — BYOK boundary repair

Source: `77d13377eab576d3356007c0e628cbf072b5f9d5`.

## Focused suite

Command from clean worktree `/private/tmp/atom-byok-repair2/backend`:

```
PYTHONDONTWRITEBYTECODE=1 TESTING=1 PYTHONPATH=$PWD python -B -m pytest \
  /private/tmp/test_verifier_byok_boundaries_2ed.py \
  tests/test_workload_capability_routing.py tests/test_capability_routing.py \
  tests/test_pinned_planning_scope.py tests/test_pinned_planning_transport.py \
  tests/test_llm_service_task_type_forwarding.py tests/test_employee_proposal.py \
  tests/test_employee_adaptation_contract.py tests/test_employee_work_requests.py \
  tests/test_employee_work_request_bindings.py tests/test_learning_llm_router.py
```

Result: **160 passed, 419 warnings in 16.77s**. Log: `focused-tests.log`.

## Independent verifier boundary probes

`verifier-boundaries.log`: **5 passed**.

- Strict capability pin does not escape through `pinned_structured_call`; only
  the pinned route is called and the result is `None`.
- Semantic transport success (`success=true`, `quality_satisfied=false`) is
  `no_suitable`.
- One `unsafe_action` below the sample floor is `no_suitable`.
- Missing workspace evidence is not adopted for the reader.
- Provider-policy route hides another workspace/tenant decision.

## Controlled probe

`routing-probe.json`:

- Flash wins economy ordering against a much more expensive equal-quality
  route.
- Explicit quality preference selects the stronger eligible route.
- Measured failure excludes the failing route.
- A semantic-only success pool returns `no_suitable`.
- Missing workspace evidence yields `{}`.
- One unsafe event yields `no_suitable` with `measured_unsafe_action`.
- Reviewed recovery returns the route to `selected`.
- Good pin exact; bad pin failed with no fallback.

## Known separate failure

The two-domain wait campaign test fails at `9a342109b` with
`already_applied` vs `terminal`; the same failure reproduces in a clean
worktree without these BYOK changes. It is Agent 1's durable-wait work and is
excluded from this focused BYOK suite. Full G5 remains open.
