# ORCH-01 consumer repair — test results

Executed source: `620476fb41c58dc95e6936bc875379a01d64a3f3`
Base: `81c5962bd17b3ffa90cd5107d5b3134821c0ffa1`
Previous withheld source: `4d3fb66c54a20cc8a864bfbea45967a8429ebdf8`

Frozen extraction roots:

- Python 3.14: `/private/tmp/atom-orch01-513-314/backend`
- Python 3.11: `/private/tmp/atom-orch01-513-311/backend`

Every command ran from the corresponding extraction root with:

```sh
export PYTHONDONTWRITEBYTECODE=1
export TESTING=1
export PYTHONPATH=$PWD
PY314=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
PY311=python3.11
```

## Focused repair gate

```sh
$PY314 -B -m pytest \
  tests/test_orch01_workflow_blueprint.py \
  tests/test_orch01_checkpoint_contract.py \
  tests/test_verifier_orch01_binding_resume_4d3f.py \
  tests/test_orch01_resume_durable.py \
  tests/test_orch01_real_checkpoint_contract.py \
  tests/test_covpush_w105_workflow_approval_routes.py \
  -q --tb=short
```

Result: **67 passed** (`focused-314.log`). The same command with `$PY311`
gives **67 passed** (`focused-311.log`).

This gate contains the 33 compiler/checkpoint controls, the verifier's 4
negative cases, 11 real durable HITL/fresh-session controls and 19 workflow
approval route controls.

The real controls include persisted-blueprint fresh-process resume, the HITL
queue approve/reject bridge, pending/rejected refusal, changed reviewed
material, a same-step-id decoy workflow, route scope/binding, blocked-successor
finalization and full completion.

## Affected workflow/approval callers

```sh
$PY314 -B -m pytest \
  tests/test_orch01_workflow_blueprint.py \
  tests/test_orch01_checkpoint_contract.py \
  tests/test_verifier_orch01_binding_resume_4d3f.py \
  tests/test_orch01_resume_durable.py \
  tests/test_orch01_real_checkpoint_contract.py \
  tests/test_covpush_w105_workflow_approval_routes.py \
  tests/test_advanced_workflow_system.py \
  tests/test_advanced_workflows_simple.py \
  tests/test_covpush_w28_advanced_workflow.py \
  tests/test_covpush_w29_workflow_engine_graph.py \
  tests/test_covpush_w21_workflow_engine.py \
  tests/test_covpush_w63_workflow_ui_endpoints.py \
  tests/test_covpush_w103_workflow_composer.py \
  tests/test_covpush_w103_workflow_templates.py \
  tests/test_covpush_w109_workflow_templates.py \
  tests/test_workflow_realization.py \
  tests/test_hitl_approvals_journey.py \
  tests/test_round67_workflow_governance.py \
  tests/test_round68_workflow_trigger_paths.py \
  tests/test_round89_workflow_execution_scope.py \
  tests/test_round19_workflow_security.py \
  -q --tb=short
```

Result: **632 passed, 2 failed** (`affected-314.log`). The same selection on
Python 3.11 gives **632 passed, 2 failed** (`affected-311.log`).

The two failures are pre-existing on the withheld source
`4d3fb66c5`:

- `tests/test_round67_workflow_governance.py::TestWorkflowMCPGovernance::test_mcp_action_passes_attribution_and_does_not_leak`
- `tests/test_round19_workflow_security.py::TestAdvancedWorkflowEndpointsNoStrELeak::test_no_str_e_in_exceptions`

`base-round67-round19-pre-existing.log` records both failing on `4d3fb66c5`
without the repair.

## Independent verifier negatives

The verifier's four negative cases on the withheld source:

```text
verifier-binding-resume-before.log: 4 failed
```

They pass on the repair source inside the focused gate above.

The prior 28-control contract probe on the withheld source:

```text
verifier-contract-before.log: 28 passed
```

The repair preserves those controls.

Final combined verifier probes (the prior contract probe plus the four new
negative cases) on the executed source:

```text
verifier-probes-final-314.log: 7 passed
verifier-probes-final-311.log: 7 passed (-p no:randomly)
```

Python 3.11 used `-p no:randomly` because the external probe paths trigger a
pytest-randomly/thinc seed error before test setup; the tracked controls run
under the normal configuration in `focused-311.log`.

## Known baseline scheduler timing failures

`base-scheduler-pre-existing.log` records the two disclosed
`TestWorkflowSchedulerCriticalNodes` timing failures on the unchanged accepted
baseline. They are not in the repair selection and are not claimed as a
647/647 pass.

## No model/browser campaign

No model call, browser session, live provider, credential, spend, send,
download or deployment was used. The repair is deterministic compiler/consumer
work on real scratch SQLite and fresh sessions.
