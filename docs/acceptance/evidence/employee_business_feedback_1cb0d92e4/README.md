# Evaluated business outcomes → scoped feedback → changed routing decision

2026-11-04, America/Toronto.

**Status: the employee consumer's deterministic business evaluation is persisted
on the exact model generation, the capability selector reads it in the
attempt's profile/scope, and the next unpinned decision excludes the failed
route and serves one eligible alternative.** This is controlled scratch-DB
evidence through the real `propose_employee_work` → `LLMService` →
`BYOKHandler` path with only the provider transport doubled. No live model
inference, provider, credential, spend, download or deployment was used.

| Item | Value |
|---|---|
| Executed source | `1cb0d92e4180340dfe7a9d4e2b538fff954ab8e8` |
| Consumer | `propose_employee_work` / `propose_adaptation` |
| Feedback store | scratch SQLite `LLMRoutingFeedback` table |
| Profile | `employee_evidence_selection` v`2026-11-04.1` |
| Failed route | `local_ctrl1234/llama3.1:8b` |
| Next served route | `local_pricey/pricey-model` |
| Feedback controls | **6 passed** |
| Focused affected regression | **212 passed** |
| Broader employee/assignment regression | **180 passed** |

## The gap this closes

`llm_routing_feedback` already recorded transport outcomes: the model answered,
parsed, or failed. It did not record whether the employee's proposal or business
result was correct. The capability selector therefore had no measured business
evidence to act on; tests that injected `load_feedback_evidence` proved the
selector, not the consumer boundary.

The exported procurement summary's stage/outcome labels were corrected
separately at `d6a561b2b` (compact reconciliation is `adaptation/replan`, not
`evidence_selection/clarification`). Original state files and traces are
unchanged; no inference was replayed.

## What the consumer now persists

The handler publishes the generation identity (`routing_result_id`) through the
call-local provenance carrier. The employee consumer annotates **that exact
row** with:

- `capability_profile` / `profile_version` (the server-selected workload);
- `workspace_id` / `tenant_id`;
- `route_provider` / `model_id`;
- `failure_kind` (`wrong_evidence_selection`, `invalid_plan_reference`,
  `wrong_field_mapping`, `unsatisfactory_business_result`, or `""` for a
  satisfied result);
- `business_outcome`, `business_stage`, `business_rule`;
- `attempt_id`, repair attribution, selected sources and adoption status where
  the consumer knows them.

Rules enforced at the boundary:

- A deterministic fallback is **never** credited as model success.
- A provider/deadline/no-suitable/schema failure is **never** relabelled as a
  semantic business failure; the handler's transport row already owns it.
- Missing evidence is not automatically a model failure. Only deterministic
  rejections (invalid source, invalid plan reference, wrong mapping) or an
  explicit task outcome are recorded.
- A business success requires a model-owned source and `objective_met=True`.
- A business failure requires `objective_met=False` **and** the outcome's own
  failure diagnosis naming the capability layer; configuration/delivery
  failures remain unknown for routing evidence.

## Scoping repair

The structured ranking call now passes the handler's own workspace to
`load_feedback_evidence`. It previously used the router's cache default
(`"default"`), so workspace-scoped business rows were invisible to the next
decision. The control that proves the loop fails without this repair.

## Proof sequence

`feedback-proof.json` is produced by `proof.py` at the executed source:

1. Three served model generations return schema-valid proposals that the
   consumer rejects as `wrong_evidence_selection`.
2. Each rejection annotates its own outcome row: `success=false`,
   `quality_satisfied=false`, profile/version/scope/provider/model and
   `failure_kind=wrong_evidence_selection`.
3. A fresh capability-evidence read aggregates **3 samples / 0 successes /
   3 semantic failures** for `local_ctrl1234/llama3.1:8b`.
4. The next unpinned consumer decision excludes that route and serves the one
   eligible alternative `local_pricey/pricey-model`.

The `test_employee_business_feedback.py` controls also cover:

- the post-execution business-result path (`objective_met=False`,
  capability-owned failure) changing the next decision;
- a satisfied business outcome annotating the same generation without
  duplicating the row;
- workspace, tenant and profile-version isolation, with missing quality
  remaining unknown rather than failed;
- compact evaluation staying in `employee_adaptive_planning_compact`, never
  becoming an evidence-selection sample;
- deterministic fallback success being refused model credit;
- bounded same-route retry (1–2 calls), no sweep back to the excluded route.

## Boundaries

- Scratch SQLite and doubled provider transport; this is not live multi-model
  inference or served multi-model quality.
- Three evaluations are used because the profile's declared evidence floor is
  three samples; the evidence is measured, not a one-off label.
- One eligible alternative is served; no broad escalation or multi-route sweep
  is claimed.
- Exact qualification pins and the one-escalation policy are unchanged and
  covered by the existing pinned-planning/workload controls.
- Historical `111/123`, planner `5/5`, goal router `1/2` and alignment gap
  `3.0` remain unchanged. General adaptive judgment and served multi-model
  comparison remain unqualified.

## Artifacts

- `feedback-proof.json` — persisted rows, aggregated evidence and next decision.
- `proof.py` — deterministic reproducer (no live model).
- `business-feedback-tests.log` — 6 feedback controls.
- `focused-affected.log` — 212 affected routing/feedback/employee tests.
- `broader-employee.log` — 180 employee/assignment tests.
- `MANIFEST.json` — source and artifact hashes.
