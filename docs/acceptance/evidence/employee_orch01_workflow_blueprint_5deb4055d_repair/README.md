# ORCH-01 consumer repair — executable binding, durable resume, honest finalization

Status: **repair submitted for independent verification.** The previous
submission (source `4d3fb66c5`, evidence `0a850d14d`) is withheld. This bundle
addresses the three consumer contracts in
`VERIFIER_ORCH01_4D3F_CONSUMER_REPAIR_20261105.md`. ORCH-02/07 remain read-only
preparation; no accepted lane is reopened.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/orch01-blueprint-20261105` |
| Base | `81c5962bd17b3ffa90cd5107d5b3134821c0ffa1` |
| Previous withheld source | `4d3fb66c54a20cc8a864bfbea45967a8429ebdf8` |
| Previous evidence commit | `0a850d14d8c85a62a72d95c93355f5b23766a0ab` |
| Parent repair source | `e7f551bc8449dfccf4120e9b7ba298fe49fca258` |
| Executed source | `5deb4055d8530e6b75103ebc34a080025feafd74` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | real scratch SQLite with fresh sessions; controlled governance/effect seams |
| Model/provider/browser calls | none |

The parent repair source established the compiler binding, durable resume
consumer and finalizer. `513e056b4` completes the fresh-process path: it loads
the persisted blueprint by execution/definition identity when no in-memory
registration exists, explicitly binds `execution_id` in the approval material,
bridges the HITL queue to the advanced checkpoint consumer, persists
`completed_at`, and includes waiting-approval executions in the workflow
approval pending list. `5deb4055d` then closes the complete-binding matrix: one
strict validator requires the full versioned execution/definition/guarded/
input/scope tuple and refuses partial or contradictory reviews. Legacy rows
without the exact binding version remain readable/listable but are not
executable authority for a new server-required checkpoint.

## The three withheld contracts, repaired

### A. Unsupported actions were rewritten to create

**Before:** the compiler validated service/action words against allowlists and
then mapped every mutating entity to `parameters.action="create"`. A declared
`service=knowledge, action=delete, kind=write` compiled `execution_ready=true`
with a different executable effect.

**Repair:**

- The executor owns the entity operation contract
  (`ENTITY_EXECUTABLE_ACTIONS = create, update, query, lookup`).
  `_execute_entity_node` refuses anything outside that set.
- The compiler resolves a declared entity operation against that contract.
  Supported operations are preserved exactly. An unsupported operation (for
  example `delete`) stays declared and makes the design
  `execution_ready=false` with an honest blocker; it is never silently
  rewritten to `create`.
- A declared skill/agent `service.action` pair must exist in the real
  `core.action_registry` (including connector namespaces) or the design is
  non-executable. The allowlists remain design vocabulary only.
- Every server-required approval step carries an immutable `guarded_digest`
  over the guarded step parameters/next steps, so a changed reviewed effect
  cannot reuse an old approval receipt.

### B. Public resume bypassed the durable checkpoint

**Before:** `resume_workflow` marked a waiting result completed and followed
successors without reading the bound `HITLAction`. Pending and rejected
approvals still dispatched the controlled write. The definition was found by
scanning for the first workflow containing the step id.

**Repair:**

- `resume_workflow` routes server-required checkpoints through the same
  authoritative consumer as initial dispatch with `require_durable=True`.
  The durable `HITLAction` is the authority.
- Pending, rejected, expired, missing, unreadable or mismatched review
  releases zero descendants. Only an actual matching approval may release the
  branch. Missing/mismatched material is `unavailable` and never creates a
  replacement approval on resume.
- The workflow definition is resolved from the execution/definition identity
  (`_workflow_definition_id`). If the process has no in-memory registration,
  the persisted blueprint is loaded by definition id inside the authenticated
  workspace/tenant. It never scans for a matching step id, so a decoy workflow
  with the same approval step id cannot release the execution.
- Approval material binds execution id, definition id/digest, step id,
  guarded step/digest, input digest, workspace and tenant. New rows carry the
  execution/definition binding. New checkpoints carry
  `binding_version=server-required-v2`; one strict validator requires every
  execution, definition, step, guarded-material and scope value to be present,
  non-empty and exactly equal to the authoritative execution material and the
  durable row columns. Legacy rows without that exact version remain
  readable/listable but are not executable authority; a fresh matching review
  is required.
- The workflow approval route loads the scoped durable row, rejects foreign
  execution/step/definition bindings, approves or rejects through the existing
  `InterventionService` role/status policy, and resumes the registered
  orchestrator. `core.hitl_resume` bridges advanced `WorkflowExecution`
  actions through the same consumer instead of the legacy workflow-engine
  state store.
- Legacy non-server-required confidence waits without a durable row keep their
  documented pre-repair compatibility path; they never waive a server-required
  checkpoint.

### C. Outer finalization turned denial into completion

**Before:** `execute_workflow` completed any context that was not
`WAITING_APPROVAL`, overwriting `FAILED`/blocked outcomes. `_continue_workflow`
had the same pattern.

**Repair:**

- `execute_workflow` finalizes as completed only when the context is still
  `RUNNING` after the start traversal. Failed/cancelled/waiting outcomes are
  preserved.
- `_continue_workflow` checks the actual step results for failed/error/blocked/
  rejected/expired/cancelled/unavailable/unresolved/waiting/paused and preserves
  that outcome. Only a still-running context with successful required work may
  complete.
- A caught checkpoint error or stopped branch is never reported as completed.

## Controls

The focused gate is **89 passed on Python 3.14 and 3.11**:

- 33 ORCH-01 compiler/checkpoint controls (`test_orch01_workflow_blueprint.py`
  + `test_orch01_checkpoint_contract.py`, including unsupported/supported
  entity operation, action-registry binding, guarded-digest and full-completion
  controls);
- the verifier's 4 negative cases (`test_verifier_orch01_binding_resume_4d3f.py`):
  unsupported delete, pending resume, rejected resume and blocked top-level
  completion;
- 11 real durable resume/finalization controls using real scratch `HITLAction`
  rows and fresh sessions (`test_orch01_resume_durable.py` +
  `test_orch01_real_checkpoint_contract.py`): pending refusal, exact approval
  -> one effect, duplicate no effect, rejected refusal, changed reviewed
  material, same-step-id decoy workflow, persisted-definition fresh-process
  resume, HITL-queue approve/reject, route scope/binding, blocked-successor
  finalization and full completion;
- 19 workflow approval route controls.

The affected workflow/approval caller selection is **654 passed, 2
pre-existing failures** on both Python 3.14 and 3.11. The two failures
(`test_round67_workflow_governance.py::...attribution...` and
`test_round19_workflow_security.py::...no_str_e...`) reproduce on the
withheld source `4d3fb66c5` and are not caused by this repair.

## Independent negatives before/after

The verifier's four negative cases failed on the withheld source
(`verifier-binding-resume-before.log`, 4 failed) and pass on the repair source.
The prior 28 controls remain green (`verifier-contract-before.log`); the final
combined probes are 27 passed on Python 3.14 and 3.11
(`verifier-probes-final-314.log`, `verifier-probes-final-311.log`).

## Pre-existing exclusions

- The two disclosed `TestWorkflowSchedulerCriticalNodes` timing failures
  reproduce on the unchanged accepted baseline
  (`base-scheduler-pre-existing.log`). They are not in the repair selection.
- The two round67/round19 failures above reproduce on the withheld source
  (`base-round67-round19-pre-existing.log`).
- No broad 647/model/UI campaign was rerun. Historical `111/123`, served
  candidate scores and tags are unchanged.

## Boundaries

- No new model, provider, credential, spend, send, download or deployment
  authority.
- No new review store or engine; the repair uses the existing
  `HITLAction`/`InterventionService`/governance mechanism.
- A reviewable design and an executable workflow remain separate states;
  unbound or unsupported designs are non-executable and unregistered.
- PostgreSQL concurrency/soak, execution quality, scheduling reliability and
  fleet recruitment are not claimed.
- ORCH-02/07 remain read-only preparation until this finite slice is accepted.
- Accepted feedback/wait and employee episode lanes remain closed.

## Artifacts

`focused-*.log`, `affected-*.log`, `verifier-binding-resume-before.log`,
`verifier-contract-before.log`, `verifier-review-binding-before.log`,
`verifier-probes-final-314.log`, `verifier-probes-final-311.log`,
`base-scheduler-pre-existing.log`,
`base-round67-round19-pre-existing.log`, `README.md`, `TEST_RESULTS.md`,
`verification.json`, `contracts.json`. `MANIFEST.json` records the SHA-256 of
every artifact and changed source file.
