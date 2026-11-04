# Test results — BYOK workload capability routing

Source: `2edc28513415c980b8670568e472f1fa5e914514`
(product code stable at `d752d6bb4`).

## Focused suite

Command from clean worktree `/private/tmp/atom-byok-clean/backend`:

```
PYTHONDONTWRITEBYTECODE=1 TESTING=1 PYTHONPATH=$PWD python -B -m pytest \
  tests/test_workload_capability_routing.py tests/test_capability_routing.py \
  tests/test_pinned_planning_scope.py tests/test_pinned_planning_transport.py \
  tests/test_llm_service_task_type_forwarding.py tests/test_employee_proposal.py \
  tests/test_employee_adaptation_contract.py tests/test_employee_work_requests.py \
  tests/test_employee_work_request_bindings.py tests/test_employee_two_domain_campaign.py
```

Result: **119 passed, 337 warnings in 19.61s**. Log: `focused-tests.log`.

## Controlled routing probe

Command:

```
python scripts/acceptance/byok_capability_probe.py
```

Result: exit 0; JSON: `routing-probe.json`.

Observed:

1. Economy order: `fast/flash` before `frontier/expensive` despite lower
   static quality (90 vs 99), because both meet the profile floor and Flash
   has the lower expected satisfactory cost.
2. Explicit quality preference: `frontier/expensive` first.
3. Measured failure: `fast/flash` (1/6 success, retries, semantic failure)
   excluded; `frontier/expensive` remains.
4. No suitable: a quality-60-only pool returns `no_suitable`; it is not
   relaxed to the cheap route.
5. Strict pin: `fast/flash` eligible; `local/llama3.1:8b` at quality 75
   fails with the exact route recorded and no fallback.

## Production-path BPC controls

`tests/test_workload_capability_routing.py` includes controlled BPC pools:

- Flash wins economy ordering over an equal-quality expensive model.
- A quality-85 Flash remains eligible on `COMPLEX` when the profile floor is
  82, even though the generic complexity floor is higher.
- A quality-81 route is explicitly `no_suitable` against the 82 profile floor,
  with a persisted decision journal entry.

No provider call, credential change or model download was made.
