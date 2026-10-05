# Lane 1 — Task correction and evidence-bound delivery

Date: 2026-09-27. Assigned to the existing backend correction agent. Implementation and verification remain required; this document is not a completion claim.

## Objective

Make a user-requested replacement update the durable objective, retrieval inputs, evidence and displayed answer consistently. Preserve the measured preview until a separately fingerprinted candidate passes. Do not wait for frontend streaming work to verify HTTP behavior.

Read `AGENTS.md`, `CLAUDE.md`, coordination, `RESUMED_AGENT_REVIEW_2026_09_27.md`, and `LIFECYCLE_EVIDENCE_CLOSEOUT_PLAN_2026_09_26.md`. Historical resume notes contain superseded explanations; current code and exact runtime evidence decide.

## Exclusive edit scope

Existing staged/in-flight ownership stays with this lane:

- `backend/core/chat_tool_planner.py`
- `backend/integrations/chat_orchestrator.py`
- `backend/scripts/orchestration_acceptance/task_correction_acceptance.py`
- `backend/tests/test_reply_leg_name_safety.py`
- `backend/tests/test_workbook_structured_delivery.py`
- `backend/tests/test_task_correction_routing.py`

Related `core/pending_file_task.py`, `core/answer_presentation.py`, and `core/task_lifecycle.py` may be edited only after checking current coordination and announcing the specific scope. Do not overwrite another active change.

Do not edit frontend hooks, general acceptance launcher/storage machinery, or other lanes' reports. Lane 3 can propose evaluator changes but must not edit your correction runner while you own it. Record any ownership transfer explicitly.

## Current evidence

The reviewed staged work already includes revised-target precedence, persistence of a complete revised ask, current-turn structured-record scoping, durable requested targets, and protection against misrouting file corrections to Tasks. Inspect and finish it; do not implement a second mechanism.

The reviewed 0/4 correction result is from an older candidate and does not measure the staged implementation. It is neither proof the new code fails nor evidence it passes.

## Required behavior

1. Resolve the active objective through existing continuation mechanisms.
2. Validate the set edit; preserve unchanged entities and their order.
3. Persist a new task revision before executing its read. Retain historical revisions/evidence unchanged.
4. Build retrieval inputs from the new revision, not the original stored ask or a union of past lists.
5. Bind current operation/attempt/revision to the resulting structured evidence.
6. Render and finalize against the selected evidence. A formatting operation may deliberately reuse evidence by identity; it must not masquerade as a read.
7. Persist the new delivery and preserve previous messages and transport pins.

For a recognized correction, internal failures must not fall through to an unrelated mutating task-creation lane. Return an honest incomplete result. Preserve legitimate standalone task creation with a negative control; do not globally disable Tasks or add a replacement-keyword router.

Incoming entities need not exist. Use independently labeled fixtures: a found incoming item requires its own identity/value bindings; an absent item requires successful coverage and an honest absence outcome; a failed read remains failed. Do not fabricate a value to satisfy the replacement test.

## Implementation sequence

1. Trace one correction through routing, revision persistence, actual retrieval, evidence selection and response. Capture the first divergence.
2. Verify `_turn_structured_record` has the exact schema consumed by presentation/validation on prefetch, planned read and direct-read branches. Test scope execution so a swallowed NameError cannot silently route elsewhere.
3. Finish the smallest general fix using the existing mechanisms. Preserve all staged work and inspect the complete combined diff.
4. Strengthen the correction runner with Lane 3's review. Actual retrieval requires invocation evidence, not merely a changed attempt ID or historical `new_read` stamp.
5. Run targeted and relevant neighboring tests with isolated stores. No ad-hoc live DB access.
6. Hand the candidate hashes and results to Lane 3 for the frozen public/browser run. Do not rebuild its active world independently.

## Acceptance

Additional source-review risks to reproduce before promotion:

- The current revision-error handler near the direct-read path clears `_objective_edit` after `revise_objective` fails, but then appears to continue into `begin_retrieval_turn` with revised targets. Verify actual control flow. Inject revision persistence failure and require zero retrieval and zero fallback task creation; a comment claiming fail-closed behavior is insufficient.
- `_stored_requested_items` can prefer cached result items over pending-task items. Test failed reread after a successful revision, followed by formatting/re-search/reload, for resurrection of the old set.
- Inspect `structured_for()` in the correction runner: missing execution identity must not select latest, and duplicate matches must fail rather than select the first row.
- Do not derive expected absence from a helper that skips unreadable parquets, scans unrelated datasets, or returns false when nothing was readable. Freeze source-scoped expectations independently; failed/incomplete inspection is unknown.
- Validator `ok` does not establish value correctness when `values_grounded` is advisory. The acceptance test must independently verify the factual values and bases.

- Base lookup → replacement → formatting → explicit re-search → reload all preserve the independently expected revised set.
- Current durable entities and output are each compared to the expected set, not only to each other.
- Replacement creates no unrelated Tasks row or other mutation.
- Formatting invokes no retrieval and preserves the previous message by exact ID/hash.
- Re-search records a real invocation; unchanged source revision is valid.
- Found/ambiguous/absent/failed incoming outcomes are correctly distinguished.
- Empty answers cannot pass “outgoing item removed” as successful correction.
- Wrong cell, basis, value, stale record and sibling execution evidence fail negative controls.
- History uniqueness is checked by request/execution/message identity and expected roles, not a hardcoded total row count.
- Old request IDs replay original pins; a correction is a new intended request.

## Handoff

Provide scoped file list/hashes, tested source identity, test commands/results, schema/contract changes, fixture expectations, and remaining limitations. Do not stage or commit unrelated files. Update only this lane's status in coordination; preserve the shared measured preview. Completion requires Lane 3's public-boundary result, not helper tests alone.
