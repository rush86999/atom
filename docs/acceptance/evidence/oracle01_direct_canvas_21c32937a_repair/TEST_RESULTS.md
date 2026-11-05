# ORACLE-01 direct canvas repair — test results

Executed source: `21c32937a87544f7ba2249f76c5be605d039bc17`
Base: `81c5962bd17b3ffa90cd5107d5b3134821c0ffa1`
Frozen extraction roots:

- Python 3.14: `/private/tmp/atom-oracle01-21c-314/backend`
- Python 3.11: `/private/tmp/atom-oracle01-21c-311/backend`

Every command ran from the corresponding extraction root with:

```sh
export PYTHONDONTWRITEBYTECODE=1
export TESTING=1
export PYTHONPATH=$PWD
PY314=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
PY311=python3.11
```

## Python 3.14

### Focused repair matrix

The 39 direct controls plus the independent verifier's 6 probe cases
(4 parametrized foreign-scope cases, stale-mirror no-change and
old-identical-audit):

```sh
$PY314 -B -m pytest \
  tests/test_oracle_direct_canvas_writes.py \
  tests/test_verifier_canvas_scope_5eede.py \
  -q --tb=short
```

Result: **45 passed** (`focused-314.log`).

### Affected CRUD/oracle/assignment/canvas controls

```sh
$PY314 -B -m pytest \
  tests/test_oracle_direct_canvas_writes.py \
  tests/test_verifier_canvas_scope_5eede.py \
  tests/test_canvas_crud.py \
  tests/test_oracle_connected_mutations.py \
  tests/test_canvas_assignment_integration.py \
  tests/test_covpush_canvasroutes.py \
  tests/test_canvas_capability_service.py \
  tests/test_async_turn_continuation.py::TestRevisionAndReviewSemantics::test_exact_operation_replay_does_not_append_another_audit \
  -q --tb=short \
  --deselect tests/test_covpush_canvasroutes.py::TestCanvasWebSocket
```

Result: **177 passed, 8 deselected** (`affected-314.log`).

### Adjacent canvas projection/feedback/connected

```sh
$PY314 -B -m pytest \
  tests/test_acceptance_canvas_projection.py \
  tests/test_canvas_feedback_episode_integration.py \
  tests/test_canvas_connected_binding.py \
  -q --tb=short
```

Result: **34 passed** (`adjacent-314.log`).

### Route-coverage patch seams

```sh
$PY314 -B -m pytest \
  tests/api/test_canvas_routes_coverage_w51.py::TestCanvasCRUD::test_update_canvas_success \
  tests/api/test_canvas_routes_coverage_w51.py::TestCanvasCRUD::test_update_canvas_error \
  tests/test_covpush_regtrio.py::TestCanvasActions::test_canvas_update_success \
  -q --tb=short
```

Result: **3 passed** (`patch-seams-314.log`).

### Full route-coverage file (pre-existing failures)

```sh
$PY314 -B -m pytest tests/api/test_canvas_routes_coverage_w51.py \
  -q --tb=line
```

Result: **53 passed, 5 failed** (`routes-w51-314.log`). The 5 failures are
pre-existing: fork success, logic not-found and 3 WebSocket cases. The same 5
fail on the base (`base-routes-w51-pre-existing.log`).

## Python 3.11

### Focused repair matrix

```sh
$PY311 -B -m pytest \
  tests/test_oracle_direct_canvas_writes.py \
  tests/test_verifier_canvas_scope_5eede.py \
  -q --tb=short
```

Result: **45 passed** (`focused-311.log`).

### Affected CRUD/oracle/assignment/canvas controls

```sh
$PY311 -B -m pytest \
  tests/test_oracle_direct_canvas_writes.py \
  tests/test_verifier_canvas_scope_5eede.py \
  tests/test_canvas_crud.py \
  tests/test_oracle_connected_mutations.py \
  tests/test_canvas_assignment_integration.py \
  tests/test_covpush_canvasroutes.py \
  tests/test_canvas_capability_service.py \
  tests/test_async_turn_continuation.py::TestRevisionAndReviewSemantics::test_exact_operation_replay_does_not_append_another_audit \
  -q --tb=short \
  --deselect tests/test_covpush_canvasroutes.py::TestCanvasWebSocket
```

Result: **177 passed, 8 deselected** (`affected-311.log`).

## Base-source pre-existing comparisons

All commands below ran from `/private/tmp/atom-base-81c/backend`, an archive of
`81c5962bd`.

### Route-coverage failures

```sh
$PY314 -B -m pytest \
  tests/api/test_canvas_routes_coverage_w51.py::TestForkCanvas::test_fork_success \
  tests/api/test_canvas_routes_coverage_w51.py::TestCanvasLogic::test_get_logic_not_found \
  tests/api/test_canvas_routes_coverage_w51.py::TestCanvasStateWebSocketEndToEnd::test_ws_broadcast_loop_and_persist \
  tests/api/test_canvas_routes_coverage_w51.py::TestCanvasStateWebSocketErrors::test_ws_persist_failure_swallowed \
  tests/api/test_canvas_routes_coverage_w51.py::TestCanvasStateWebSocketErrors::test_ws_broadcast_error_disconnects \
  -q --tb=line
```

Result: **5 failed** (`base-routes-w51-pre-existing.log`).

### Canvas editor

```sh
$PY314 -B -m pytest tests/test_chat_canvas_editor.py -q --tb=line
```

Result on base: **14 failed, 91 passed**
(`base-editor-pre-existing.log`). The repair source has the same result.

### VFS/document search

```sh
$PY314 -B -m pytest \
  tests/test_covpush_regtrio.py::TestVfsHelpers::test_ensure_vfs_registered_registers_provider \
  tests/test_covpush_regtrio.py::TestDocumentsSearchAction::test_legacy_path_when_vfs_disabled \
  -q --tb=line
```

Result on base: **2 failed** (`base-regtrio-pre-existing.log`).

### WebSocket fixture gap

```sh
$PY314 -B -m pytest \
  tests/test_covpush_canvasroutes.py::TestCanvasWebSocket \
  -q --tb=line
```

Result on base: **4 failed, 4 passed**
(`base-ws-pre-existing.log`). The fixture mounts `router`, not `ws_router`.
