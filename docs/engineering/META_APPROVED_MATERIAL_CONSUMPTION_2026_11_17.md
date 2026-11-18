# Meta-agent durable approved-material consumption

**Date:** 2026-11-17
**Scope:** `core/atom_meta_agent.py` (Meta consumer only) + its whole-consumer
regression file. Reuses the shared seam `core/approved_action_material.py` (and
the existing HITL receipt / reviewer-authority / role helpers). No second
approval registry, validator, claim store or integration-specific matching was
added. `core/approved_action_material.py` and `core/generic_agent.py` are owned
by a separate repair workstream and were **not** modified here.

## Problem (reproduced at the real Meta entry, before the fix)

Root counter evidence: `/private/tmp/atom-meta-approved-material-counter-20261117.py`
(before/after logs in the same directory).

Driving the real `AtomMetaAgent._execute_tool_with_governance`, the real
`AgentGovernanceService.request_approval` writer and the real
`InterventionService.approve_intervention(..., modified_params=...)` decision
writer against a scratch SQLite store produced:

| | durable approved row | handler received |
|---|---|---|
| before | `{"query": "corrected-filter"}` | `{"query": "original-filter"}` |
| after | `{"query": "corrected-filter"}` | `{"query": "corrected-filter"}` |

The row was also stamped `workspace_id="default"`, `user_id=NULL` and carried
no `execution_id`/`actor_id` snapshot, so it bound only the agent id and the
tool — a status boolean, not a decision about this execution.

A second defect sat on the same path: the parallel batch filed HITL rows but
never passed their ids to the dispatch, so `pre_approved=True` skipped every
governance check *and* every approved payload for the whole batch.

## Meta approval consumers traced

| Surface | Code | Notes |
|---|---|---|
| Sequential tool dispatch | `_execute_tool_with_governance_unaudited` | files the row, waits, consumes |
| Parallel batch | `_execute_parallel_tools` → per-action dispatch | one row per reviewed action; all-or-nothing wait |
| Safety-judge escalation | same method (`JudgeVerdict.ESCALATE`) | second row for the same payload when the judge is enabled |
| Task-level never-autonomous admission | `_admit_never_autonomous_task` | **unchanged**: uses the shared `evaluate_task_admission` receipt + `warm_task_admission_receipt_denial`, already bound to execution/actor/task |
| Special tools / capability | `trigger_workflow`, `delegate_task`, `recruit_fleet`, `invoke_capability`, final `mcp.call_tool` | all consume the local effective payload (no separate approval) |

## Binding (producer and consumer share one resolution)

`AtomMetaAgent._approval_binding(context)`:

* **runtime agent** `atom_main` — a context `agent_id` (parent/orchestrator
  hint) can never re-target the approval on either side;
* **actor** — the server-bound `self.user.id`; context `user_id`/`actor_id` is
  only a fallback for legacy background callers with no authenticated
  principal;
* **scope** — `_governance_scope(self)` (the authenticated workspace and the
  tenant resolved by `execute_unaudited` from the `Workspace` row), never a
  caller-supplied workspace/tenant;
* **execution** — the durable `execution_id` the loop stamps into the dispatch
  context (also `run_id` fallback).

The producer writes all of these into the row's existing
`context_snapshot`/`user_id` columns via `request_approval`; the consumer passes
the same identity to `load_approved_material`, which re-reads the row, the
reviewer's CURRENT durable role/scope, the receipt (`reviewed_params` /
`approved_params`) and the live `params` before returning `effective_params`.

The governance service is now constructed with the instance scope and
`include_global_agent_id="atom_main"`, preserving the legitimate global
`atom_main` registry row for non-default workspaces while keeping maturity,
policy and budget decisions on the authenticated scope.

## Consumption flow

1. Freeze the reviewed request (deep copy) before governance/handler.
2. Re-run the current governance/budget/never decision, file the HITL row with
   the exact reviewed payload and the binding above.
3. Wait for the human decision (unchanged all-or-nothing semantics).
4. Consume the durable row through `load_approved_material`; refuse on any
   missing/foreign/changed/tampered binding.
5. Re-run the independent gates against CURRENT state (maturity, budget,
   recursion, never-autonomous rule revisions). A remaining-but-unchanged
   review requirement is accepted; a changed risk shape is not.
6. **Final authority fence after that awaited gate**: re-read the row once more
   and require the same `action_id` and effective digest. A reviewer/actor/
   scope/payload change during the await cannot be dispatched.
7. Replace the frozen request with `effective_params` for the handler, and only
   then grant any never-autonomous clearance (a refused approval leaves no
   clearance).
8. Stamp redacted provenance into the audit metadata: action id, reviewer id
   and role, reviewed/effective SHA-256, `material_changed`, the binding, and
   `dispatched` (true only at the real handler call). Payloads stay in the
   durable HITL row; the audit is not a second copy.

Parallel dispatch repeats steps 4–8 per reviewed action; a batch rejection
still executes nothing, and one refused action does not dispatch its payload
while the other (unreviewed) action proceeds.

## Refusals

* Ordinary refusals (missing proof, pending/revoked status, foreign
  agent/actor/scope, role denial, tamper, changed risk/budget/never policy)
  return an honest `Governance Error: approval ... could not authorize ...`
  observation. No handler ran; no original-args fallback.
* A revoked/inactive admitted actor returns the typed
  `failed_before_effect` / `terminal_authority_denial` envelope
  (`business_success: False`, `effect_state: "none"`,
  `requires_reconciliation: False`, `retryable: False`), which the existing
  Meta loop already halts on, so a model final answer cannot convert the
  refusal into a business success.
* The audit ledger classifies typed refusal envelopes as failures (previously
  only error strings were classified).

## Limits (explicit)

* The Meta path has no general durable mutation/operation-claim adapter
  (`TaskOperationRecord` is the generic-agent seam); no claim store was
  invented here. Consequences:
  * the same durable approval id can only be consumed by a caller that holds
    it (Meta never re-passes a consumed id);
  * every Meta dispatch files a fresh HITL row, so there is no automatic
    resend and no second execution without a new human decision;
  * there is no persisted “already dispatched” receipt for a Meta mutation
    after a process crash mid-call. Uncertain handler outcomes follow the
    existing handler/loop behavior; no retry is added.
* `core/approved_action_material` / `core/generic_agent` are under repair in a
  separate worktree; their known edge-gate failures are not claimed fixed
  here. This consumer uses the shared API as-is.
* Rows filed before this change carry no actor/execution binding and are
  refused (a fresh review is required) rather than treated as blanket
  authority.
* The safety-judge escalation consumes its own durable decision but, like
  before, does not re-run the governance gate a second time (it runs after the
  first gate and consumes the last authority read immediately before
  dispatch).
* No whole-app, quality, compliance or security certification is implied.

## Tests

`backend/tests/test_meta_approved_material_contract.py` (18 tests, real Meta
entry + real approval/decision writers + scratch SQLite; only the MCP leaf and
policy/judge verdicts are doubles):

* unchanged/edited read and edited declared mutation reach the handler exactly
  once; the caller's original request is preserved;
* parallel batch per-action effective material; tampered action refused while
  the rest runs; all-or-nothing rejection;
* runtime agent vs context agent hint; foreign-agent row refused;
* missing/pending/revoked/tampered/foreign-scope/reviewer-scope/inactive
  reviewer/role/mismatched-request refusals, all with no effect;
* actor revoked during the wait and during a later awaited gate (typed
  terminal refusal, no dispatch);
* changed complexity/budget/never rule revision refused before dispatch;
* safety-judge escalation consumes the edited decision;
* cold receipt + reviewer role readback;
* refusal is never a business success and leaks neither reviewed nor approved
  payload values.

CI selector + ledger entry: `Run Meta approved-material consumption controls`
in `.github/workflows/ci.yml`, mirrored in
`backend/tests/fixtures/ci_backend_additions.json`; all prior selectors, env
and ordering are unchanged (enforced by
`backend/tests/test_ci_backend_lane_contract.py`).

Known pre-existing baseline failures in this isolated-DB environment (verified
to fail identically on the base commit; not caused by this packet):
`test_covpush_w42_meta_toolgov.py::test_trigger_workflow_tool`,
four `test_covpush_w41b_meta_tools.py::TestQueryMemoryAndMentorship` tests,
`test_covpush_meta.py::TestReactStep::test_react_step_memory_assembly`,
`test_covpush_meta.py::TestRecordExecution::test_record_execution_success`,
`test_covpush_w98_gaps_a.py::TestWorkbookRuntime` recalc tests,
`test_covpush_w44b_meta_agent_execute.py::test_fleet_routing_force_enforce`,
the W30 chat-routing / W60 spawn/fleet/mentorship group,
`test_atom_meta_agent.py::test_spawn_failure_handling`, and
`test_bughunt_20260809_sbx.py` (hangs in this environment).
