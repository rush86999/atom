# ORACLE-01 atomic-scope repair — test results

Executed source: `82ac9681ad66b276a135ce06e1d2b7f03cbb30d9`
Previous source: `18e8af4a63a5f952e14a9c5f27dc81d6d313b918`
Base: `81c5962bd17b3ffa90cd5107d5b3134821c0ffa1`

Frozen extraction roots:

- Python 3.14: `/private/tmp/atom-oracle01-82ac-314/backend`
- Python 3.11: `/private/tmp/atom-oracle01-82ac-311/backend`

Every command ran from the corresponding extraction root with:

```sh
export PYTHONDONTWRITEBYTECODE=1
export TESTING=1
export PYTHONPATH=$PWD
PY314=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
PY311=python3.11
```

## Focused atomic + original gate

```sh
$PY314 -B -m pytest \
  tests/test_oracle_direct_canvas_writes.py \
  tests/test_verifier_canvas_scope_5eede.py \
  tests/test_verifier_canvas_scope_commit_18e8.py \
  -q --tb=short
```

Result: **55 passed** (`focused-314.log`). The same command with `$PY311`
gives **55 passed** (`focused-311.log`).

This is the original 45 controls plus 6 new direct atomic controls and the
verifier's 4 atomic interleavings.

## External independent probe on the frozen source

```sh
PYTHONPATH=$PWD:/private/tmp $PY314 -B -m pytest \
  /private/tmp/test_verifier_canvas_scope_commit_18e8.py -q --tb=short
```

Result: **4 passed** (`external-probe-314.log`).

## Affected selection

```sh
$PY314 -B -m pytest \
  tests/test_oracle_direct_canvas_writes.py \
  tests/test_verifier_canvas_scope_5eede.py \
  tests/test_verifier_canvas_scope_commit_18e8.py \
  tests/test_canvas_crud.py \
  tests/test_oracle_connected_mutations.py \
  tests/test_canvas_assignment_integration.py \
  tests/test_covpush_canvasroutes.py \
  tests/test_canvas_capability_service.py \
  tests/test_async_turn_continuation.py::TestRevisionAndReviewSemantics::test_exact_operation_replay_does_not_append_another_audit \
  -q --tb=short \
  --deselect tests/test_covpush_canvasroutes.py::TestCanvasWebSocket
```

Result: **187 passed, 8 deselected** (`affected-314.log`). The same selection
on Python 3.11 gives **187 passed, 8 deselected** (`affected-311.log`).

The 8 deselected tests are the known `TestCanvasWebSocket` fixture gap; they
are outside this repair and were not rerun.

## Adjacent canvas selection

```sh
$PY314 -B -m pytest \
  tests/test_acceptance_canvas_projection.py \
  tests/test_canvas_feedback_episode_integration.py \
  tests/test_canvas_connected_binding.py \
  -q --tb=short
```

Result: **34 passed** (`adjacent-314.log`). The same command with `$PY311`
gives **34 passed** (`adjacent-311.log`).

Affected + adjacent = **221 passed** on both versions. This is the previous
211 plus the 10 new atomic controls; selections overlap and are not added to
the focused 55.

## Independent verifier before

The verifier's atomic probe failed 4/4 on the previous source
`18e8af4a6`:

```text
verifier-atomic-before.log: 4 failed
```

The verifier's original focused 45 and affected/adjacent 211 passed on that
source:

```text
verifier-focused-before.log: 45 passed
verifier-affected-before.log: 211 passed
```

## Scope and exclusions

No unrelated full route/editor/WebSocket suite, model campaign, browser
session, live provider, PostgreSQL run or multi-worker soak was performed.
The known WebSocket class is deselected in the affected selection. No new
provider, credential, consent, spend, send, download or deployment authority
was used.
