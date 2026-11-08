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

# LEAD REVIEW — persisted BPE namespace identity (finite)

Status: **AUTHOR-ONLY / NOT EXECUTED**. No product code, pytest, server,
model, provider, install, migration or credential/env inspection was performed
here. Root owns every runtime gate and the acceptance decision.

## Confirmed defect (bounded)

The evidence packet explicitly left **filename/key collision behavior** open
(`docs/engineering/evidence/bpe_scope_persistence_multiday_1415a855a/README.md`
§Remaining boundaries). The store had two non-injective namespace encodings:

- the file name replaced every character outside `[A-Za-z0-9_-]` with `_`, so
  e.g. `personal:user` and `personal_user` shared one file;
- the inner key joined `agent_id` and `scope_key` with `|`, so
  `("agent|scope", "")` and `("agent", "scope|")` shared one slot.

In addition, `load()` returned any entry found under the computed key without
checking the identity embedded in the snapshot, and `get_workspace()` restored
that snapshot using its embedded identity while caching it under the requested
registry key. A stale/tampered snapshot could therefore be addressed as one
namespace while carrying another namespace's state.

## Repair (runtime, file-based storage only)

`backend/core/bpe/persistence.py`

- Added one canonical `namespace_identity(workspace_id, agent_id, scope_key)`
  normalization, identical to the workspace/API defaults.
- File names are now injective while preserving the historic spelling:
  lowercase safe ids `[a-z0-9_-]{1,120}` keep `<id>.json`; every other id uses
  `~<sha256>.json`. The `~`/safe-alphabet split means an encoded name can never
  equal a pass-through name, and mixed-case ids no longer alias on
  case-insensitive filesystems. This also keeps traversal-shaped ids inside
  the store directory.
- Inner keys preserve the historic `<agent_id>|<scope_key>` spelling when
  neither component contains `|`. Otherwise both components are urlsafe
  base64-encoded inside `v2|<b64(agent)>|<b64(scope)>`; base64 cannot contain
  `|`, so this cannot collide with a legacy one-separator key.
- `save()` stamps the canonical triple into the stored entry, so the file
  name, inner key and embedded identity always agree. A pre-repair lossy-named
  file is used only as a read-through source when the canonical file does not
  exist; every scope whose embedded `workspace_id` equals this workspace is
  carried into the canonical file, while foreign workspace entries are left
  untouched in the old file. The old file is never moved, rewritten or
  deleted.
- `load()` looks up the injective key, falls back to the legacy key only when
  the new key is absent, and then requires the embedded
  `(workspace_id, agent_id, scope_key)` to equal the requested triple. A
  mismatch is logged and refused (`None`) instead of being returned.

`backend/core/bpe/workspace.py`

- `get_workspace()` re-checks the restored object's identity against the
  requested registry key. A mismatched snapshot never enters the cache; the
  store starts a fresh workspace for the requested namespace.

No new store, schema, engine, router or migration. The truthful-write result,
temporary-file cleanup, backend path anchoring and current-principal scope
foundations are unchanged. Safe lowercase namespaces keep their exact existing
file name and inner key.

## Authored controls (not executed here)

`backend/tests/core/test_bpe_persistence_namespace_identity.py` — real
`BPEWorkspaceStore`/registry on `tmp_path`; no storage seam is faked:

1. `test_safe_namespace_keeps_historic_filename_and_key` — `w.json` and
   `a|s` are unchanged, and the stamped identity is exact.
2. `test_lossy_workspace_filenames_cannot_collide` — `personal:user-1`,
   `personal_user-1` and `personal/user-1` produce three paths and three
   independently loadable states.
3. `test_mixed_case_workspace_names_cannot_share_a_file` — `workspace` and
   `Workspace` stay distinct on a case-insensitive filesystem.
4. `test_scope_separator_collisions_are_distinct` (two parameterized pairs) —
   legacy `agent|scope|` collisions persist and load as two namespaces.
5. `test_embedded_identity_mismatch_is_refused` (workspace, agent and scope
   variants) — a tampered embedded field makes `load()` return `None`.
6. `test_tampered_snapshot_is_not_restored_under_requested_namespace` — a
   fresh registry gets an empty workspace with the requested identity, never
   the tampered state.
7. `test_valid_awkward_namespace_survives_registry_restart` — an encoded
   `personal:`/`|` namespace round-trips through a cold registry.
8. `test_legacy_lossy_file_is_read_without_being_moved_or_deleted` — the old
   file is readable, its bytes remain unchanged and the first save writes the
   canonical file.
9. `test_legacy_colliding_file_cannot_lend_a_foreign_namespace` — only the
   target workspace's entries are read/written; the foreign entry is refused
   and remains untouched in the legacy file.
10. `test_traversal_shaped_workspace_ids_stay_inside_the_store` — `../`,
    absolute and separator-shaped ids all resolve inside `data_dir`.

Root owns execution and acceptance; none of these is labeled passing by the
author.

## Exact negatives / compatibility preserved

- `BPEWorkspaceStore.save()` still returns `True` only after a successful
  replacement and `False` on any write failure; the earlier failure-first
  controls are unchanged.
- The existing safe save/load round-trip, LRU bound, oversized rejection,
  corrupt-file degradation and lazy restore controls are unchanged because
  safe lowercase ids keep their historic file/key spelling.
- Explicit `data_dir` values (including `tmp_path`) and backend-relative
  `ATOM_BPE_DATA_DIR` resolution are unchanged.
- Refusals remain `None` from `load`/fresh state from `get_workspace`; no
  success wrapper or silent re-homing was added.

## Explicitly open (not claimed here)

- Old files that already collapsed several namespaces into one lossy name are
  not merged, guessed or migrated. Each readable entry is admitted only when
  its embedded identity proves the requested namespace; foreign entries stay
  untouched in the legacy file.
- Concurrent writers, multi-process/worker last-writer-wins, fsync/crash
  durability, caller handling of `False` persistence, note/commit Oracle
  receipts, hot runtime settings and PostgreSQL/soak remain open.
- This is a code-and-control delivery only. The earlier evidence packet's
  "filename/key collision behavior" item is repaired in source but is not
  claimed verified until root executes these controls.
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

---

# LEAD REVIEW — strict persisted-entry identity (namespace follow-up)

Status: **AUTHOR-ONLY / NOT EXECUTED**. No Python, pytest, server, model,
provider, install, migration or credential/env inspection was run here. Root
owns execution and acceptance.

## Root negative being closed

At integrated source `b86a7dbe6`, a real store file `default.json` containing:

```json
{"agent|": {"progress": [{"title": "unbound record"}]}}
```

loaded under `default/agent/empty`. The entry has no stored identity at all,
but `_snapshot_identity` fed missing fields through the caller-facing
`namespace_identity` normalizer, which supplied `"default"`, `"agent"` and
`""`. That made absent data look like explicit persisted authority.

## Repair

`backend/core/bpe/persistence.py`

- Added `stored_namespace_identity(snapshot)`, a strict validator for
  **stored** entries:
  - `workspace_id`, `agent_id` and `scope_key` must all be explicit keys in
    the entry;
  - all three values must be strings;
  - `workspace_id` and `agent_id` must be non-empty;
  - `scope_key` may be empty.
- Missing, `None`, boolean, numeric, list/dict and other container values now
  return `None`; they are never coerced into a namespace.
- `_snapshot_identity`/`_snapshot_workspace_id` use this strict validator, so
  `load()` refuses the root-negative entry and also refuses malformed legacy
  entries during read-through instead of carrying them forward.
- `load()` still normalizes its **caller arguments** through
  `namespace_identity`, preserving existing `None`/empty/default request
  behavior. Only the stored side is strict.
- `save()` now rejects a snapshot whose stored identity fields are absent or
  ill-typed (`False`, no file write). It never manufactures a default entry.
  The existing truthful replacement result, temporary-file cleanup and
  injective path/key encodings are unchanged.

`backend/core/bpe/workspace.py`

- The only production restoration consumer, `get_workspace()`, now calls
  `stored_namespace_identity(snapshot)` before `BPEWorkspace.from_dict()`.
  `from_dict()` has no namespace-request context and is retained as an
  object-level materializer with its existing defaults; it is never allowed
  to decide persisted authority. A missing/mismatched stored identity starts a
  fresh workspace in the requested registry slot.

Parallel restoration consumers traced: `generic_agent.py` and
`atom_meta_agent.py` only **save** `BPEWorkspace.to_dict()` state;
`api/bpe_routes.py` reads the in-process snapshot, not the file store; direct
test use of `BPEWorkspace.from_dict()` is object-level and unchanged. No other
production file-store restore path exists.

## Authored controls added

`backend/tests/core/test_bpe_persistence_namespace_identity.py`

1. `test_missing_stored_identity_is_not_defaulted_into_authority` — the exact
   root negative: `default.json` / `agent|` with no identity fields yields
   `load(...) is None`; `get_workspace("default", "agent", "")` starts empty
   rather than adopting the record.
2. `test_each_missing_stored_identity_field_is_refused` — each of the three
   fields removed independently is refused.
3. `test_non_string_stored_identity_is_refused` — `None`, `True`, `False`,
   `0`, `1`, `1.5`, `[]` and `{}` are refused for each identity field.
4. `test_empty_workspace_or_agent_is_refused` — empty workspace or agent is
   refused, while empty scope remains valid.
5. `test_save_refuses_missing_stored_identity_without_overwriting` — a
   malformed snapshot returns `False`, leaves the existing file bytes intact,
   and creates no implicit `default.json`.
6. `test_explicit_default_empty_scope_snapshot_still_loads` — a valid
   historical entry with explicit `default` / `agent` / `""` fields loads via
   `load(None, None, None)` and through `get_workspace(None, None, None)`.

Existing namespace-collision, path-encoding, write-truth, path-anchoring and
current-principal controls are unchanged.

## Preserved compatibility / exact negatives

- Caller normalization remains: `load(None, None, None)`,
  `get_workspace(None, None, None)` and empty caller arguments still address
  `default/agent/empty`.
- Valid historical snapshots with explicit matching string fields still load,
  including the default/empty-scope case.
- Legacy files are read-through only and their bytes are untouched; malformed
  entries are simply not admitted.
- Existing safe filenames/keys, truthful `save()` result, temporary cleanup,
  explicit `data_dir`, backend-relative anchoring and all prior controls are
  preserved.

## Explicitly open

- Malformed historical entries are refused rather than migrated, repaired or
  deleted; no live store data was touched.
- Concurrent writers, multi-process last-writer-wins, fsync/crash durability,
  note/commit Oracle receipts, hot runtime settings and PostgreSQL/soak remain
  open and unchanged.
- No runtime result is claimed here. Root must execute the controls and the
  wider BPE selection at the exact accepted head.

---

# LEAD REVIEW — truthful RPC failure consumer/journey integration repair

Status: **AUTHOR-ONLY / NOT EXECUTED**. No Python, pytest, app, server,
provider, npm/install, browser or live-DB command was run here. Root owns
execution and acceptance.

## Exact hosted failure at head `222587fd7`

- PR 764 primary selection: **904 passed, 1 skipped** (unchanged from local).
- All later groups passed until the MINI03 journey:
  **1 failed / 7 passed / 1 skipped** at
  `backend/tests/integration/journeys/test_mini_app_harness_journey.py:145`
  → helper at line 92.
- The failing call was `mini_app_write_logic` with
  `BAD_SYNTAX = "def broken(:"`. The real response was:

  ```json
  {"success": false,
   "data": {"success": false,
            "error": "SyntaxError: invalid syntax (<unknown>, line 1)"},
   "action": "mini_app_write_logic"}
  ```

- The journey helper required `success is True` for **every** call, including
  this intentional negative, so it failed on a truthful envelope before the
  test could assert the handler's own error. The older mainc97 wrapper only
  asserted transport success; it did not exercise this cross-caller contract.
  This is not an unrelated failure, and neither prior result is erased.

## Contract decision

`backend/api/rpc_routes.py` intentionally propagates an explicit in-handler
`success: false` to the outer envelope. That generic behavior stays
byte-for-byte unchanged: no action-name exception, no hidden `data.success`,
no waived gate, no skip/xfail/removal. The repair fixes the **consumer
class**:

1. **Journey** — `_rpc(..., expected_success=True)` now asserts the outer
   envelope equals the expected outcome and returns `data`. Only the four
   intended negatives pass `expected_success=False` (bad Python, dev-run
   unavailable, stateful run unavailable, install-before-publish). Every
   nested error/status/assertion is retained. After bad syntax the journey now
   also proves no rejected write landed: the controller source is still
   `STARTER` and logic history is exactly `[1]` with the `STARTER` preview.
   `mini_app_run_tests` remains an outer-success report surface and explicitly
   keeps `data.success: true`, `total: 1`, `passed: 0`, `all_passed: false`,
   per-case unavailable error, and the absence of fabricated `stdout`/`state`.
   Product runtime/hypervisor availability is untouched.
2. **Shared client** — `RpcError` gains additive `actionResult`, set only for a
   body-level `{success: false}` envelope from `body.data`. It still throws on
   outer failure, keeps `action`, `status`, `details`, the generic message and
   transport-safe HTTP/network mapping. `body.data.error` is never promoted to
   the global message, and no integration-name logic was added.
3. **MiniAppHarness** — a small local typed extractor reads
   `RpcError.actionResult` only when the handler itself reported
   `success: false` and supplied a string `error`. Scaffold, dev-run, publish
   and install catches use that already-exposed safe error and otherwise fall
   back to the existing generic `RpcError` message. HTTP/unknown/raw axios or
   server detail is never rendered. The direct PUT save catch keeps its
   existing `detail` contract; no feature is force-enabled.
4. **Frontend gates** — new tests:
   - `frontend-nextjs/tests/lib/rpc-client-failure.test.ts` (success
     passthrough; semantic failure in `actionResult` with operation/audit
     metadata; generic non-promoted message; HTTP 500 detail confined to
     `details`; network failures have no `actionResult`);
   - `frontend-nextjs/tests/components/mini-app-harness-rpc-failure.test.tsx`
     (rendered SyntaxError and sanitized runtime-unavailable semantic
     failures; install catch; HTTP 500 generic/not rendered; a non-failure
     `actionResult.error` is not trusted; successful dev-run positive twin).
   Both are selected by a new step in the existing `frontend-typecheck` CI job:
   `npx jest tests/lib/rpc-client-failure.test.ts
   tests/components/mini-app-harness-rpc-failure.test.tsx --runInBand
   --no-coverage`.

## Why expected-negative assertions get stricter, not weaker

Before, the helper encoded "the outer envelope must be true" for all calls.
The intentional negatives could only pass by misrepresenting the backend
contract or by removing their assertions. Now each negative declares its
expected outcome and still asserts the handler's nested failure plus its exact
error, while the bad-syntax case additionally proves the invalid source was
not persisted and no checkpoint/version was appended. No gate was relaxed and
no test was skipped or deleted.

## Files changed (owned only)

- `backend/tests/integration/journeys/test_mini_app_harness_journey.py`
- `frontend-nextjs/lib/rpc-client.ts`
- `frontend-nextjs/components/canvas/MiniAppHarness.tsx`
- `frontend-nextjs/tests/lib/rpc-client-failure.test.ts` (new)
- `frontend-nextjs/tests/components/mini-app-harness-rpc-failure.test.tsx` (new)
- `.github/workflows/ci.yml`
- `LEAD_REVIEW.md` (this append)

No backend runtime, policy, authority, BPE, Oracle, provider, engine,
`api/rpc_routes.py`, or existing root-scope bytes were changed.

## Root validation remaining

Root must run the journey under both Python selections, run the new frontend
Jest selection (and the wider frontend gate if required), and recheck all
exact-head hosted checks before any merge. This handoff claims no execution.
