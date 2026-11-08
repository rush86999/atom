# LEAD REVIEW — BPE persistence write truth (finite)

Branch: `codex/bpe-persistence-write-truth-20261108`
Base: `b7639cd5c90cadd29542db51c4216ff9558c791e`

## Root cause

`BPEWorkspaceStore._write()` caught every exception — including an `OSError`
from `os.replace()` — logged at debug level, and returned `None`.
`save()` ignored that outcome and unconditionally returned `True` after
calling `_write()`. A failed replacement therefore reported a successful
persist even though the previous file was still the only content on disk.
The same path also abandoned the `mkstemp` temporary file whenever the write
or replacement failed.

## Repair (runtime)

`backend/core/bpe/persistence.py` only:

- `_write()` now returns `bool`. `True` is returned only after
  `os.replace()` returns successfully; any `mkdir`, `mkstemp`, `fdopen`,
  `json.dump`, or `os.replace` exception returns `False`.
- The file descriptor is closed explicitly if `os.fdopen()` fails before
  taking ownership of it.
- A `finally` block unlinks the attempt's temporary file on every failed
  path. A missing temp file is tolerated; cleanup errors are logged without
  changing the write result. On success the temp path is consumed by the
  replace, so cleanup is skipped.
- `save()` returns the `_write()` result, preserving the existing public
  `True`/`False` contract and all other valid save/load behavior: the
  oversized-snapshot rejection, corrupt-read degradation, LRU bound, and
  round-trip load are unchanged.
- No `fsync`, no new durability claim, no retry, no new store/schema/engine,
  and no global configuration change.

## Failure-first control inventory

1. **Replacement failure** — `os.replace()` raises `OSError` →
   `_write()` `False` → `save()` `False`.
2. **Write failure** — `mkdir`/`mkstemp`/`fdopen`/`json.dump` raises →
   `_write()` `False` → `save()` `False`.
3. **Previous-file preservation** — data is written only to the temp file;
   `os.replace()` is the final step, so any earlier failure leaves the
   previous file intact.
4. **No abandoned temporary file** — the `finally` cleanup removes the
   attempt's temp file after replacement or any write error.
5. **Truthful return** — the caller-visible `save()` result is the actual
   replacement outcome, not a post-hoc constant.
6. **Valid twin** — a successful save still returns `True` and loads back the
   same snapshot.

## Authored regression controls (not executed here)

`backend/tests/core/test_bpe_persistence_write_truth.py` — permanent pytest
controls using the real `BPEWorkspaceStore` and `tmp_path`, injecting failure
only at storage seams:

1. `test_replace_failure_returns_false_and_preserves_previous_file` —
   `os.replace` raises, `save()` is `False`, old bytes and `load()` content
   are unchanged, no `.tmp` remains.
2. `test_json_dump_failure_returns_false_and_preserves_previous_file` —
   `json.dump` raises mid-write, same preservation/cleanup/return checks.
3. `test_mkstemp_failure_returns_false_and_preserves_previous_file` —
   temp creation raises before any temp exists; old file preserved.
4. `test_mkdir_failure_returns_false_without_creating_temp` — a file blocks
   the store's parent directory; `save()` is `False`, blocker untouched.
5. `test_fdopen_failure_closes_fd_and_removes_temp_file` — `os.fdopen` raises,
   `save()` is `False`, old file preserved, no temp remains, and `fstat` on
   the captured descriptor raises `OSError` (descriptor closed on the
   ownership-failure path).
6. `test_valid_save_and_load_round_trip` — real workspace snapshot saves as
   `True`, loads back through `BPEWorkspace.from_dict`, and leaves no temp.
7. `test_save_succeeds_after_failed_replacement` — a failed replacement does
   not poison the store; a later valid save returns `True` and loads.

Root owns execution and acceptance; no Python or pytest was run here, and
none of these controls is labeled passing by the author.

## Caller implications

- `backend/core/generic_agent.py:1006` and
  `backend/core/atom_meta_agent.py:1831` call `save()` inside
  `try/except`, but do not inspect the boolean. Because `save()` has never
  raised, those blocks silently accepted a false success. This fix makes the
  outcome truthful for those callers but deliberately leaves their
  in-memory fallback/no-logging behavior unchanged; surfacing or retrying
  `False` is outside this bounded fix.
- `backend/core/bpe/workspace.py:455` uses `load()` on a registry miss; the
  read path is untouched.
- `backend/tests/core/test_bpe_evolution.py` uses explicit temporary
  directories and its valid save/load, LRU, oversized-rejection, and corrupt
  read twins remain valid.

## Path anchoring repair

**Defect.** `DATA_DIR = Path(os.getenv("ATOM_BPE_DATA_DIR",
"backend/data/bpe_workspaces"))` was resolved against the launch CWD at
import. The three production call sites (`generic_agent.py:1006`,
`atom_meta_agent.py:1831`, `workspace.py:455`) construct
`BPEWorkspaceStore()` with no directory, so a repo-root launch used
`<repo>/backend/data/bpe_workspaces` while a `backend/` launch used
`<repo>/backend/backend/data/bpe_workspaces`.

**Repair**

- `DEFAULT_DATA_DIR` is now the backend-relative `data/bpe_workspaces`.
  `_resolve_data_dir()` joins relative values to the backend directory
  (computed from `__file__`, not the CWD), mirroring
  `core.lancedb_handler._resolve_local_db_path` and the
  `core.automation_settings` backend-relative convention.
- Absolute paths pass through unchanged.
- For compatibility with the previously documented
  `backend/data/bpe_workspaces` spelling, a leading `backend/` component is
  treated as the repo-root marker and dropped before backend anchoring, so
  that legacy relative value still resolves to the same effective path.
- An explicit `data_dir=` argument is used exactly as supplied (including
  test `tmp_path` directories and explicitly relative test directories); it
  is not re-anchored.
- `settings_catalog.ATOM_BPE_DATA_DIR` now advertises the canonical
  `data/bpe_workspaces` default and documents the relative/absolute/legacy
  semantics. Its resolved effective path is unchanged:
  `<repo>/backend/data/bpe_workspaces` from either launch directory.
- Nothing is moved, copied, merged, deleted or migrated; no operator store
  is read. The old `backend/backend/data/...` path was never the documented
  default, so no compatibility alias is created for it.
- `DATA_DIR` is still resolved once at import from the environment (the
  existing behavior). The runtime-settings DB/UI row for this key is not
  consulted by store construction; that pre-existing configuration gap is
  documented below rather than silently changed.

## Path-anchoring controls (authored, not executed)

`backend/tests/core/test_bpe_persistence_path_anchoring.py` — read-only
path-resolution controls; no store save/load/migration:

1. `test_default_store_is_identical_from_repo_root_and_backend` — clean
   subprocess imports from both launch directories resolve to
   `<backend>/data/bpe_workspaces`.
2. `test_configured_catalog_default_matches_canonical_default` — catalog
   default equals the runtime constant and resolves to the documented path.
3. `test_default_helper_reads_relative_override` — a configured relative
   value resolves against backend.
4. `test_absolute_override_is_preserved_from_either_cwd` — absolute values
   pass through from both launches.
5. `test_relative_override_is_backend_relative` — relative values resolve to
   the same backend-relative path from both launches.
6. `test_legacy_documented_default_spelling_remains_compatible` — the old
   `backend/data/bpe_workspaces` relative spelling resolves to the same
   effective path.
7. `test_explicit_data_dir_is_used_as_supplied` — explicit `tmp_path` and
   explicit relative test directories are preserved.

Root owns execution and acceptance; none of these are labeled passing by the
author.

## Explicitly open (not claimed here)

- Callers do not log, retry, or otherwise act on a `False` save result.
- The runtime-settings DB/UI row for `ATOM_BPE_DATA_DIR` is still not
  consumed by store construction; only the environment value present at
  import time is used. This is a pre-existing configuration gap, not part of
  this path-anchoring repair.
- No fsync/durability guarantee and no multi-process locking semantics.
- Oracle note honesty, broader BPE/Oracle gaps, and principal/workspace scope
  work remain untouched and are not claimed fixed.

---

# Multi-day CI failure investigation/repair — lead review

## Exact hosted evidence

- Baseline: `543138cb5` (`codex/bpe-multiday-ci-20261108`).
- Normal CI run `42440697910`, backend job `128609111550`.
- Result: 799 passed, 3 failed, 1 skipped; the only failures are
  `tests/test_generic_information_multiday_contract.py`
  (`reply after 3 days`, `reply after 14 days`, `two 7-day waits`).
- Public symptom: resumed answer returns HTTP 503
  `AGENT_EXECUTION_UNCERTAIN`; the cancellation twin still returns 409 and
  passes.

The hosted log identifies the concrete cause before the public 503:

```
2026-11-11 03:05:41 [ ERROR] tasks.create failed: Unable to generate
pydantic-core schema for <class 'freezegun.api.FakeDatetime'> ...
2026-11-11 03:05:41 [ INFO] Recorded outcome for a1: failure
... POST /api/agents/a1/jobs/<id>/answer "HTTP/1.1 503 Service Unavailable"
```

## Cause

The multi-day module freezes the clock for its tests
(`pytestmark = pytest.mark.freeze_time(real_asyncio=True)`). On resume, the
real `tasks.create` registered action runs for the first time in that process
and its handler (`core/action_registry.py:_tasks_create`) lazily imports
`core.board_service`, which imports `api/schemas/board_schemas.py`.

`api/schemas/board_schemas.py` uses postponed annotations and declares
`TaskCreate.due_at: Union[datetime, None]`. Pydantic resolves that annotation
when the model class is created. Because the first import happened inside the
frozen resumed pass, `from datetime import datetime` resolved to
`freezegun.api.FakeDatetime`; Pydantic cannot build a core schema for it, the
import fails, and the handler's `except Exception` returns
`{"success": False, "error": "Task creation failed"}`. The framework then
honestly marks the declared mutation uncertain and the public answer is 503.

This is a controlled-clock import-order artifact, not a production business or
Oracle defect. In the hosted process no primary-selection module had imported
`api.schemas.board_schemas` before the frozen pass. A local standalone run can
only pass if that module was already resident (or the plugin invocation
differed); the hosted log is direct evidence of the lazy import happening under
freeze.

## Repair

`backend/tests/test_generic_information_multiday_contract.py` now imports the
real production handler module (`core.board_service`, which builds the real
`TaskCreate` schema) at module collection time, before any test-level freeze.
The resumed `tasks.create` therefore runs the real action and the default
Oracle verifies the real board row, exactly as the original assertions require.

No production code, assertion, receipt, Oracle verifier, job identity, wait
identity, or simulated 3/14/7+7-day behavior changed. There is no bypass,
fallback, retry, skip/xfail, test deletion, or out-of-process test.

## Isolation control

`test_action_schema_was_built_with_real_datetime` runs under the same frozen
marker and asserts that `TaskCreate.due_at` was built from the real `datetime`
class, not `FakeDatetime`. It invokes no server, action, or model. If the
module-level preload is removed, this control fails with the same Pydantic
error that broke the hosted acceptance path; with the preload it proves the
production schema is the one being exercised.

Falsifiable prediction: on the exact primary selection, all three previously
failing multi-day cases pass, the cancellation twin remains green, and the new
control passes. A failure would mean a second frozen-time lazy import exists;
the next observation is the first line of the new Pydantic/import error, not a
business/Oracle assertion change.

## Root-owned validation remaining

Code/test authoring is complete; no Python, pytest, server, model, provider, or
install command was executed here. Root must serially run the exact primary
selection and then the full backend gate. This repair is not accepted until
root verifies it at the exact head.
