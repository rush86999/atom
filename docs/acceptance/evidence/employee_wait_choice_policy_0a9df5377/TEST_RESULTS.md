# Wait-choice semantic guard — test results

Executed 2026-11-04, America/Toronto. No model/provider call was made for this
bundle.

## Sources

| Role | Commit |
|---|---|
| Semantic guard | `0a9df5377` |
| Integrated feedback attribution | `e4f3733c1` |
| Prior schema recovery (preserved) | `5cc897dbb` / evidence `8cbed19fc` |
| Original negative (preserved) | `employee_byok_auto_selection_0e04286b2` |

## Guard-focused run

Command, from `backend/` with `TESTING=1 PYTHONPATH=$PWD`:

```text
pytest tests/test_employee_wait_choice.py \
  tests/test_assignment_routes.py::test_advance_route_does_not_adopt_a_policy_forbidden_wait \
  /private/tmp/test_verifier_wait_policy_5cc.py -q
```

Result: **19 passed** at `e4f3733c1` (`guard-tests.log`). The same trio was run
against the isolated `0a9df5377` tree before the feedback merge: **19 passed**
(`guard-commit-tests.log`).

The independent verifier probe is included as `probe.py`; it asserts that an
all-read ambiguity with only `clarify`/`retain` allowed cannot expand into a
wait and leaves no `work_request`. Its standalone run is **1 passed**
(`probe.log`).

## Affected suite

Command, from `backend/` with `TESTING=1 PYTHONPATH=$PWD`:

```text
pytest tests/test_employee_wait_choice.py \
  tests/test_employee_business_feedback.py \
  tests/test_employee_adaptation_contract.py \
  tests/test_employee_compact_adaptation.py \
  tests/test_employee_proposal.py \
  tests/test_employee_work_requests.py \
  tests/test_employee_work_request_bindings.py \
  tests/test_employee_work_request_matrix.py \
  tests/test_employee_prerequisite_eligibility.py \
  tests/test_employee_durable_wait_g5.py \
  tests/test_employee_byok_consumer_routing.py \
  tests/test_assignment_routes.py \
  tests/test_assignment_executor.py \
  tests/test_employee_outcome.py \
  tests/test_employee_evidence_change_g5.py \
  tests/test_structured_cancellation.py \
  tests/test_workload_capability_routing.py \
  /private/tmp/test_verifier_wait_policy_5cc.py -q
```

Result: **367 passed** in 129.73 s (`focused-tests.log`).

## Policy cases pinned

`tests/test_employee_wait_choice.py` has 17 tests. The new policy controls
cover:

- all-read ambiguity with `allowed_proposal_kinds=['clarify','retain']` →
  deterministic clarify/retain, no `work_request`;
- `status=missing` with no named missing role → clarify;
- unread authorized evidence for the missing role → read-first refusal;
- ready independent operation → wait refused;
- explicit contradictory `blocks_operation` → refusal, no replacement;
- omitted blocked operation with multiple missing prerequisites → refusal;
- genuine missing external record after all sources are read and `replan`
  allowed → model wait accepted;
- model clarification accepted without a wait;
- the captured empty-`blocks`/untyped-`new_steps` instance is still rejected
  by the existing proposal contract;
- true no-result retains applied receipts and unresolved requirements;
- a valid wait still expands to a typed `await_evidence` request.

The public route twin
(`test_advance_route_does_not_adopt_a_policy_forbidden_wait`) proves:

- the forbidden wait is not adopted or persisted as an `assignment.wait` step;
- the assignment does not enter `waiting`;
- the applied purchase-order and receiving results remain applied;
- the targeted invoice question is persisted as an open obligation.

## Feedback integration controls

The integrated feedback suite covers:

- `model_wait_choice` is a recognized model origin;
- a parsed, unresolved wait is annotated `business_outcome=unresolved` and is
  excluded from capability evidence;
- a rejected wait is recorded as a semantic failure, not as fallback credit;
- an explicit `business_decision_validated=True` decision can be recorded as a
  scoped positive decision; parsing alone never sets that flag;
- business writes bind to the exact generation receipt and refuse
  orphan/mismatched annotations;
- transport cost/latency survive annotation;
- request-owned provenance preserves the child call's served route and
  `routing_result_id`.

## Exact original boundary

The prior evidence remains unchanged. The captured replay chose `replan` →
`await_evidence` for the current supplier invoice on `PO-SEL-520`, even though
the accepted pool contained a current invoice candidate. That replay is
preserved as schema-recovery evidence. This bundle does not claim the original
model would have chosen differently; it proves the consumer now refuses that
structured policy violation.

## Scope

This is a controlled consumer/route guard. It does not qualify broad adaptive
judgment, served multi-model quality, live connector breadth, Linux/KVM or
multi-worker/soak.
