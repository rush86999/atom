# Employee wait-choice — semantic policy guard

2026-11-04, America/Toronto.

**Status: the wait-choice consumer now rejects a parsed wait that contradicts
trusted readiness or the allowed decision policy. The original schema-recovery
replay remains preserved as schema evidence; its wait choice is not re-labeled
as satisfactory. No new model/UI inference campaign was run.**

This is the bounded semantic guard requested after the `5cc897dbb`/`8cbed19fc`
review. The prior repair proved the captured no-result was a schema/validation
failure and gave the model a focused typed wait instance. It did **not** prove
that a parsed wait was a correct business choice: the captured replay waited
for a current invoice already present in the accepted pool, with the
prerequisite marked `ambiguous`, no missing roles, all authorized sources read,
and only `clarify`/`retain` allowed.

Prompt wording asked the model not to do that; the consumer still adopted it.
The guard now enforces the trusted contract before adoption.

| Item | Value |
|---|---|
| Semantic-guard source | `0a9df5377` (`fix(employee): guard wait choices against trusted readiness`) |
| Integrated feedback source | `e4f3733c1` (`fix(employee): attribute wait-choice feedback to the exact generation`) |
| Original schema-recovery source | `5cc897dbb`; evidence `8cbed19fc` |
| Original negative | `employee_byok_auto_selection_0e04286b2` |
| Affected suite | **367 passed** at `e4f3733c1` |
| Guard-focused suite | **19 passed** (17 wait-choice, 1 route twin, 1 independent probe) |
| Inference / replay used for this guard | **None** |

## What is rejected

Before adoption, an expanded `await_evidence` proposal is checked against the
trusted context and assignment:

- `allowed_proposal_kinds` does not include `replan`;
- the blocked capability is `ambiguous`;
- the blocked capability is already `ready`;
- a `missing` capability names no missing external role;
- authorized unread evidence remains for the missing role;
- a ready independent operation exists;
- an explicitly named `blocks_operation` contradicts the trusted missing
  prerequisite;
- no `blocks_operation` is named and more than one trusted missing
  prerequisite exists.

A genuine absent external fact is still a valid wait when the trusted policy
allows `replan`, even after every authorized source has been read and no
independent operation is ready.

An explicit contradictory `blocks_operation` is not silently replaced with the
first candidate. The compiler derives the blocked label and known subject only
when the choice is unique. The model still owns the wait/clarify/retain choice,
fact, subject and expected source; the compiler owns durable wait ids,
blocked-operation labels, subject binding, arithmetic and authority.

## What happens on rejection

The rejected model proposal is not adopted and is not credited as business
success. The deterministic fallback:

- retains the existing applied results and unresolved requirements;
- returns `clarify` (or `retain` when the trusted policy excludes clarify);
- records the policy errors and `failure_stage=wait_choice_policy` separately
  from a technical fallback;
- leaves the targeted question available to the public advance route, which
  persists it instead of silently dropping a deterministic proposal.

The public route does not create an `assignment.wait` step for a rejected wait.
The route twin in `tests/test_assignment_routes.py` proves this against the
real advance endpoint: a model wait that the guard rejects leaves the applied
purchase-order/receiving results intact, persists the targeted invoice
question, and does not put the job into a waiting state.

## Feedback integration

The feedback layer now recognizes `model_wait_choice` as a model origin, but a
parsed wait/clarify is **not** automatically a business success:

- an unresolved parsed decision is annotated `business_outcome=unresolved` and
  excluded from capability evidence;
- a rejected wait is recorded as a semantic failure, never credited to the
  deterministic fallback;
- an explicit validated-decision path exists for a caller that supplies
  `business_decision_validated=True`; parsing alone never sets it;
- business annotations bind to the exact generation receipt (tenant,
  workspace, provider, model, profile/version) and refuse orphan/mismatched
  writes;
- the request-owned provenance carrier preserves a child call's served route
  and `routing_result_id` across `asyncio.wait_for`.

## Finite policy matrix

All cases are controlled consumer/route tests; no provider or model inference
is used.

| Case | Result |
|---|---|
| All-read ambiguity, policy `clarify`/`retain` only | deterministic clarify/retain, no work request |
| Missing prerequisite with no named role | deterministic clarify, no work request |
| Unread authorized evidence can answer | read-first refusal, no wait |
| Ready independent operation exists | wait refused, no wait step |
| Explicit wrong `blocks_operation` | contradiction refusal, no silent replacement |
| No blocked operation with multiple missing prerequisites | ambiguity refusal |
| Genuine missing external record, all sources read, replan allowed | model wait accepted |
| Model clarification | accepted without a wait |
| True no-result | deterministic, applied receipts and unresolved requirement retained |
| Public advance route with forbidden wait | not adopted/persisted; applied results and targeted question retained |
| Parsed wait feedback | unresolved, not a success sample |
| Rejected wait feedback | semantic failure, not fallback credit |

## Limits

- This is a bounded consumer/route policy result, not a general adaptive
  judgment or model-quality claim.
- The original captured replay's semantic choice remains withheld. This guard
  rejects the same structured policy violation in a controlled probe; it does
  not claim the original model would choose differently.
- No served multi-model comparison, live connector breadth, Linux/KVM or
  multi-worker/soak claim follows.
- No new provider, credential, spend, send, download, deployment or broad
  inference campaign was used.
