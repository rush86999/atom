# Canvas lifecycle lead evidence 8e4b494d7 — test results

Executed source: `8e4b494d722b5ca07c79cc487adab65e1350f2b8`
Baseline source: `27a1830a27e73ed30124a82d01bb710e26bc7113` (backend tree
`5a8ff02bf90dafe34e99cf564d50f8929b7fec17` = main `8ded0023…` backend tree)
Main-equivalent source: `8ded00232c30961a990e675e06ec672ef6a43910`

These commands were executed by root through
`/private/tmp/atom-agent-cli/run_bounded_test_gate.py` with an isolated scratch
SQLite root (`TESTING=1`, a scratch `DATABASE_URL`, and scratch data/office/
lance/output directories). Each runner set `PYTHONDONTWRITEBYTECODE=1`. The
exact `command` arrays are retained verbatim in the corresponding
`.spec.json` files.

## 1. Independent root probe — 9 passed on candidate

Command array from `candidate-independent-8e4.spec.json`:

```sh
/private/tmp/atom-agent-cli/run_bounded_test_gate.py \
  --cwd /private/tmp/atom-canvas-lifecycle-20261107/backend \
  --profile bounded \
  -- /Users/rushiparikh/projects/atom/backend/venv314/bin/python -m pytest \
     /private/tmp/atom-current-claim-audit-20261107/docs/engineering/probes/canvas_lifecycle_scope_root_2026_11_07.py \
     -q --tb=short -p no:cacheprovider \
     --basetemp=/private/tmp/root-feedback-sqlite-ta6loftx/pytest
```

Result: **9 passed** (`candidate-independent-8e4.log`), exit 0
(`candidate-independent-8e4.exit.json`).

The probe is retained byte-for-byte as `independent-probe.py`; its origin is
the docs branch `codex/current-claim-reconciliation-20261107` at
`de180672830e66e49ed87bcf4f7abedf9ff0f199`, blob
`ede2276fa2292558d77ed2b12928b887d1d6414d`.

### Baseline for the same probe — 4 failed, 5 passed

Command array from `baseline-portable-4fail5pass.spec.json`:

```sh
/private/tmp/atom-agent-cli/run_bounded_test_gate.py \
  --cwd /private/tmp/atom-oracle-refresh-20261107/backend \
  --profile bounded \
  -- /Users/rushiparikh/projects/atom/backend/venv314/bin/python -m pytest \
     /private/tmp/atom-current-claim-audit-20261107/docs/engineering/probes/canvas_lifecycle_scope_root_2026_11_07.py \
     -q --tb=short -p no:cacheprovider \
     --basetemp=/private/tmp/root-wait-source-final-review-q0pnq9nk/pytest
```

Result: **4 failed, 5 passed** (`baseline-portable-4fail5pass.log`), exit 1
(`baseline-portable-4fail5pass.exit.json`).

Failing cases (exactly the four current-foreign-scope former-coeditor cases):

```text
test_former_coeditor_current_foreign_scope_has_zero_effect[delete-tenant]
test_former_coeditor_current_foreign_scope_has_zero_effect[delete-workspace]
test_former_coeditor_current_foreign_scope_has_zero_effect[undelete-tenant]
test_former_coeditor_current_foreign_scope_has_zero_effect[undelete-workspace]
```

The baseline log shows every one returned HTTP 200 and appended an effect
instead of refusing. The five passing cases are the supported owner/same-scope
coeditor twins (4) and the stranger refusal (1). The baseline is retained as a
failure baseline; it is not relabeled as a pass.

## 2. Native product suite — 31 passed on candidate

Command array from `candidate-native-8e4.spec.json`:

```sh
/private/tmp/atom-agent-cli/run_bounded_test_gate.py \
  --cwd /private/tmp/atom-canvas-lifecycle-20261107/backend \
  --profile bounded \
  -- /Users/rushiparikh/projects/atom/backend/venv314/bin/python -m pytest \
     tests/test_canvas_lifecycle_verified.py \
     -q --tb=short -p no:cacheprovider \
     --basetemp=/private/tmp/root-feedback-sqlite-ewbmb9o1/pytest
```

Result: **31 passed** (`candidate-native-8e4.log`), exit 0
(`candidate-native-8e4.exit.json`).

## 3. Affected regression selection — 175 passed, 2 failed

Command array from `candidate-affected-8e4.spec.json`:

```sh
/private/tmp/atom-agent-cli/run_bounded_test_gate.py \
  --cwd /private/tmp/atom-canvas-lifecycle-20261107/backend \
  --profile heavy \
  -- /Users/rushiparikh/projects/atom/backend/venv314/bin/python -m pytest \
     tests/test_canvas_crud.py \
     tests/test_oracle_direct_canvas_writes.py \
     tests/test_oracle_canvas_postcondition.py \
     tests/test_generic_real_mcp_budget_contract.py \
     tests/test_budget_caller_transaction_contract.py \
     tests/test_r79_action_registry_rpc.py \
     tests/core/test_action_registry_coverage.py \
     -q --tb=short -p no:cacheprovider \
     --basetemp=/private/tmp/root-feedback-sqlite-qwv4lflw/pytest
```

Result: **175 passed, 2 failed** (`candidate-affected-8e4.log`), exit 1
(`candidate-affected-8e4.exit.json`).

Command array from `baseline-affected-main27a.spec.json` (identical file list,
main-equivalent backend):

```sh
/private/tmp/atom-agent-cli/run_bounded_test_gate.py \
  --cwd /private/tmp/atom-oracle-refresh-20261107/backend \
  --profile heavy \
  -- /Users/rushiparikh/projects/atom/backend/venv314/bin/python -m pytest \
     tests/test_canvas_crud.py \
     tests/test_oracle_direct_canvas_writes.py \
     tests/test_oracle_canvas_postcondition.py \
     tests/test_generic_real_mcp_budget_contract.py \
     tests/test_budget_caller_transaction_contract.py \
     tests/test_r79_action_registry_rpc.py \
     tests/core/test_action_registry_coverage.py \
     -q --tb=short -p no:cacheprovider \
     --basetemp=/private/tmp/root-feedback-sqlite-h7yyfhp4/pytest
```

Result: **175 passed, 2 failed** (`baseline-affected-main27a.log`), exit 1
(`baseline-affected-main27a.exit.json`).

`affected-comparison.json` is the authoritative exact-ID comparison. It records
`identical_failure_ids: true` and the same two failures on both sources:

```text
tests/test_r79_action_registry_rpc.py::TestRpcRouteAuthenticated::test_list_actions_includes_registered_names
tests/core/test_action_registry_coverage.py::TestDocumentsSearchAction::test_search_legacy_path_flag_off
```

Candidate summary: `2 failed, 175 passed, 414 warnings in 31.57s`.
Baseline summary: `2 failed, 175 passed, 413 warnings in 32.89s`.

These two failures are pre-existing in the affected selection and are not
canvas lifecycle regressions. They are not claimed as passing.

## 4. Count discipline

The numbers above are not additive:

- independent probe candidate: 9 passed (4 new scope negatives + 5 preserved
  controls);
- independent probe baseline: 4 failed, 5 passed (the same 5 preserved
  controls);
- native suite: 31 passed (supporting product-authored evidence);
- affected candidate: 175 passed, 2 failed;
- affected baseline: 175 passed, 2 failed.

No total such as `9 + 31 + 175` or `175 + 5` is a capability claim. Overlapping
tests and baseline passes are not counted as new capability. The independent
new-capability result is only the four former-coeditor current-foreign-scope
negatives now passing, with the five supported/stranger controls preserved.

## 5. Runner label

The root helper runner prints `Actual SQLite feedback gate exit: <code>`. That
is an inherited generic runner label, not a test name or an SQLite-feedback
claim. The actual scope is the spec command and its named files. See
`README.md`.

## 6. Not run / not claimed

- No live provider, browser, PostgreSQL, multi-worker or soak run.
- No whole-app ORACLE coverage.
- No merge, deploy, send, spend or review-comment action.
- No normal-login/browser qualification for the mounted-route probe; the
  current-user dependency is injected by the probe.
