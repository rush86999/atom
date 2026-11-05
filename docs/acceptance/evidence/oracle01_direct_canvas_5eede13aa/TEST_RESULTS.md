# ORACLE-01 direct canvas save/restore — test results

Executed source: `5eede13aa7a2f765619dbd54251eaa2954d778dd`
Base: `81c5962bd17b3ffa90cd5107d5b3134821c0ffa1`
Frozen extraction roots:

- Python 3.14: `/private/tmp/atom-oracle01-5ee-314/backend`
- Python 3.11: `/private/tmp/atom-oracle01-5ee-311/backend`

Every command below ran from the corresponding extraction root with:

```sh
export PYTHONDONTWRITEBYTECODE=1
export TESTING=1
export PYTHONPATH=$PWD
PY314=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
PY311=python3.11
```

## Python 3.14

### Direct route family

```sh
$PY314 -B -m pytest tests/test_oracle_direct_canvas_writes.py -q --tb=short
```

Result: **24 passed** (`direct-314.log`).

### Canvas/oracle neighborhood

```sh
$PY314 -B -m pytest \
  tests/test_oracle_direct_canvas_writes.py \
  tests/test_covpush_canvasroutes.py \
  tests/test_canvas_crud.py \
  tests/test_canvas_assignment_integration.py \
  tests/test_oracle_connected_mutations.py \
  tests/test_acceptance_canvas_projection.py \
  tests/contract/test_canvas_api_contract.py \
  tests/test_canvas_capability_service.py \
  tests/test_canvas_feedback_episode_integration.py \
  -q --tb=short \
  --deselect tests/test_covpush_canvasroutes.py::TestCanvasWebSocket
```

Result: **207 passed, 8 deselected** (`canvas-neighborhood-314.log`).

### Canvas action/async controls

```sh
$PY314 -B -m pytest \
  tests/core/test_action_registry_coverage.py \
  tests/test_async_turn_continuation.py \
  -k canvas -q --tb=short
```

Result: **11 passed, 131 deselected** (`canvas-actions-314.log`).

### Accepted feedback/wait regression

```sh
$PY314 -B -m pytest \
  tests/test_capability_evidence_classification.py \
  tests/test_employee_business_feedback.py \
  tests/test_employee_feedback_interleaving.py \
  tests/test_employee_wait_choice.py \
  tests/test_assignment_routes.py \
  tests/test_employee_byok_consumer_routing.py \
  tests/test_workload_capability_routing.py \
  tests/test_workload_incident_identity.py \
  tests/test_correction_lifecycle_end_to_end.py \
  tests/test_grounding_pass_marker.py \
  tests/test_fabrication_accounting.py \
  tests/test_learning_llm_router.py \
  tests/test_routing_db_persistence.py \
  tests/test_generation_retry_identity.py \
  -q --tb=short
```

Result: **263 passed** (`feedback-regression-314.log`).

## Python 3.11

The 3.11 extraction omits `tests/contract/test_canvas_api_contract.py` because
the environment has no `schemathesis` module.

### Direct route family

```sh
$PY311 -B -m pytest tests/test_oracle_direct_canvas_writes.py -q --tb=short
```

Result: **24 passed** (`direct-311.log`).

### Canvas/oracle neighborhood

```sh
$PY311 -B -m pytest \
  tests/test_oracle_direct_canvas_writes.py \
  tests/test_covpush_canvasroutes.py \
  tests/test_canvas_crud.py \
  tests/test_canvas_assignment_integration.py \
  tests/test_oracle_connected_mutations.py \
  tests/test_acceptance_canvas_projection.py \
  tests/test_canvas_capability_service.py \
  tests/test_canvas_feedback_episode_integration.py \
  -q --tb=short \
  --deselect tests/test_covpush_canvasroutes.py::TestCanvasWebSocket
```

Result: **181 passed, 8 deselected** (`canvas-neighborhood-311.log`).

The 3.14 run has 26 more passes, exactly the 26 tests in the excluded contract
module (`207 - 181 = 26`).

### Canvas action/async controls

```sh
$PY311 -B -m pytest \
  tests/core/test_action_registry_coverage.py \
  tests/test_async_turn_continuation.py \
  -k canvas -q --tb=short
```

Result: **11 passed, 131 deselected** (`canvas-actions-311.log`).

### Accepted feedback/wait regression

```sh
$PY311 -B -m pytest \
  tests/test_capability_evidence_classification.py \
  tests/test_employee_business_feedback.py \
  tests/test_employee_feedback_interleaving.py \
  tests/test_employee_wait_choice.py \
  tests/test_assignment_routes.py \
  tests/test_employee_byok_consumer_routing.py \
  tests/test_workload_capability_routing.py \
  tests/test_workload_incident_identity.py \
  tests/test_correction_lifecycle_end_to_end.py \
  tests/test_grounding_pass_marker.py \
  tests/test_fabrication_accounting.py \
  tests/test_learning_llm_router.py \
  tests/test_routing_db_persistence.py \
  tests/test_generation_retry_identity.py \
  -q --tb=short
```

Result: **263 passed** (`feedback-regression-311.log`).

## Base-source pre-existing failures

These ran from an archive of `81c5962bd` at
`/private/tmp/atom-base-81c/backend`.

### WebSocket fixture gap

```sh
$PY314 -B -m pytest \
  tests/test_covpush_canvasroutes.py::TestCanvasWebSocket \
  -q --tb=line
```

Result on the base: **4 failed, 4 passed** (`base-ws-pre-existing.log`). The
fixture mounts `api.canvas_routes.router` but not `ws_router`.

### Editor/action-registry/async failures

```sh
$PY314 -B -m pytest \
  tests/test_async_turn_continuation.py \
  tests/core/test_action_registry_coverage.py \
  tests/test_chat_canvas_editor.py \
  tests/test_canvas_app_editor_fixes.py \
  tests/test_canvas_broadcast_channels.py \
  tests/test_canvas_comparison_attribution.py \
  tests/test_canvas_connected_binding.py \
  tests/test_canvas_conversation_root_causes.py \
  tests/test_canvas_ctx_store_fallback.py \
  -q --tb=line
```

Result on the base: **18 failed, 319 passed**
(`base-editor-pre-existing.log`). The same 18 failures reproduce with the
slice applied; they are outside the claimed route family.
