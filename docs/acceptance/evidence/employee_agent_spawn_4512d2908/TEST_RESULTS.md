# Spawned-agent creation — test results

Executed source: `4512d2908`  
Base: `492e41ea1d2e04be13f2f0eb265e6109852c0b60`

Every command ran through the bounded gate with `TESTING=1`,
`PYTEST_CURRENT_TEST=1`, explicit scratch SQLite `DATABASE_URL`, scratch
`ATOM_DATA_DIR`/`ATOM_OFFICE_DIR`/`ATOM_LANCEDB_PATH`/`LANCEDB_URI`,
`PYTHONPATH=/private/tmp/root-py311-plugins:$PWD`, and
`-p no:randomly -p pytest_freezegun`.

## Failure-first on clean `492e41ea1`

The new `tests/api/test_agent_spawn_goal14.py` was copied into a clean
baseline worktree; no product code changed.

Result: **10 failed / 1 passed** (`failure-first-base492.log`).

The failures show the legacy default scope, module/class upsert collapse,
missing operation/audit/replay, `atom_specialty_init` reset, and
non-durable ephemeral response.

## Personal-scope runtime probe before the resolver fix

With `PERSONAL_WORKSPACE_ID="personal-ws"` /
`PERSONAL_TENANT_ID="personal-tenant"` and a null-workspace/null-tenant admin:

Result: **2 failed / 11 passed** (`personal-scope-before.log`).

The route captured `default` while the shared writer created the agent in the
personal scope. After switching the route to the existing resolvers, both
tests pass in the focused matrix.

## Focused route matrix

```sh
python3.11 -m pytest tests/api/test_agent_spawn_goal14.py \
  -q --tb=short --timeout=300 --timeout-method=thread
```

Result: **13 passed** (`focused-after.log`); exact additive CI env also
**13 passed**.

Spawn/MCP subset: **16 passed** (`spawn-mcp-focused.log`).

Existing spawn/Atom/MCP consumer subset (`-k spawn`): **41 passed**
(`spawn-consumers-focused.log`).

## Affected selection

The affected selection includes the new route matrix, agent route/coverage,
spawn/Atom/MCP consumers, custom/guided create, decision contract,
governance and CI lane contract.

Result: **888 passed, 6 skipped, 9 deselected** (`affected-after.log`).

Deselections:

- the same 7 failures reproduced on clean `492e41ea1`
  (`baseline-pre-existing-7.log`);
- two `fpdf`-missing environment tests
  (`affected-environment-seams.log`).

No candidate-added product failures.

## CI

- Additive step (`Run spawned agent authority and receipt controls`):
  **13 passed**.
- Lane contract (`test_ci_backend_lane_contract.py` +
  `test_quickstart_matrix_contract.py`): **41 passed**
  (`ci-lane-contract.log`).
- `backend/tests/fixtures/ci_backend_additions.json` and
  `.github/workflows/ci.yml` carry the identical object; the immutable
  baseline file was not edited.

## Boundaries

No live model/provider/DB/credential/send/spend/deploy/dependency, no
budget/BYOK file, no new table/store, no deleted/skipped/xfailed test.
