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

# LEAD_REVIEW — finite BPE note/commit outcome repair

Status: **AUTHOR-ONLY / NOT EXECUTED**. No product code, pytest, server,
model, provider, install, or credential/env inspection was performed. Root owns
all runtime gates and acceptance. Nothing here is a self-acceptance claim.

## Root negative being closed

Root's confirmed evidence (`/private/tmp/root-workspace-note-independent-main27a.log`,
original probe copied locally as `ROOT_NOTE_PROBE.py`):

- a legitimate `workspace.note` really lands in the scoped BPE buffer;
- the normal Generic consumer has no registered postcondition verifier, so it
  rewrites the landed observation to `status=uncertain`,
  `requires_reconciliation=True`, marks the durable claim `uncertain_effect`;
- the episode close-out then **drains/drops** the pending note;
- an empty note refusal is also relabelled `uncertain` instead of staying a
  proven pre-effect no-effect.

`Original2FAIL5PASS5SKIP` is historical context, not a result of this branch.

## What changed and why

### 1. Producer-owned durable receipt inside existing BPE state

`backend/core/bpe/workspace.py`

- `BPEWorkspace` now carries a bounded `operation_receipts` list
  (`MAX_OPERATION_RECEIPTS = 64`) with `record_operation_receipt()` /
  `find_operation_receipt()`.
- Receipts are ordinary workspace state: they serialize through the existing
  `to_dict`/`from_dict` and therefore through the existing per-workspace JSON
  file (`core/bpe/persistence.py`). No new DB, table, store, or router.
- Duplicate `(action, operation_id)` receipts are idempotent: the first
  receipt wins, so a retry cannot rewrite the binding.

`backend/core/bpe/actions.py`

- Added canonical material helpers shared by producer, request freeze, and
  verifier: `canonical_note_content`, `canonical_commit_material`,
  `note_material`, `bpe_material_sha256`.
- `workspace.note` and `workspace.commit`, when they run with a server-owned
  `operation_id`, now record a receipt binding:
  `operation_id`, `action`, `workspace_id`, `agent_id`, `scope_key`,
  `actor_id` (when the scope has an authenticated principal), canonical
  `material`, `material_sha256`, and for commit the resolved subgoal title.
- The receipt is written through the existing `BPEWorkspaceStore.save()`.
  Persistence failure is not hidden: the file has no receipt, so the oracle
  below refuses to certify and the consumer stays uncertain.
- Empty note and invalid/empty commit material are validated **before**
  workspace creation or authority claim and return a typed
  `action_result=not_applied`, `effect_possible=False` envelope. They remain
  proven no-effect refusals, not uncertainty.
- The successful handler result shape is deliberately unchanged (note still
  returns `{success, buffered}`; commit retains its historical result), which
  preserves older diagnostics that assert the exact shape.

### 2. Server-frozen scope/material without model authority

`backend/core/oracle/request_expectations.py`

- `build_request_expectations(..., bpe_scope=...)` adds
  `_oracle_expected_bpe_{workspace_id,agent_id,scope_key,actor_id,material,
  material_sha256}` for `workspace.note` / `workspace.commit`.
- The material is the canonical producer transform (strip + 400-char cap for
  notes; stripped/200-char title + status for commits), so a changed request
  cannot compare equal.
- The namespace comes from the caller's server-resolved `bpe_scope`, never
  from model-visible arguments. `GenericAgent` passes it only after
  `core.bpe.actions.resolve_scope(context)` succeeds.

`backend/core/generic_agent.py`

- `_frozen_request_expectations` resolves the BPE namespace from the trusted
  dispatch context for these two actions and passes it to the shared builder.
  This is the same resolution used by prompt render and close-out, so the
  handler, oracle, and close-out address one namespace.

### 3. Independent readback verifier

`backend/core/oracle/postcondition_verifiers.py`

- Registered `workspace.note` and `workspace.commit` postconditions.
- The verifier ignores the tool result envelope. It re-loads the persisted
  workspace JSON from disk using the **frozen** workspace/agent/run and:
  - requires a receipt for the exact action + operation id;
  - compares receipt operation, workspace, agent, run/scope, actor, material,
    and material digest against the frozen request (partial receipts fail);
  - for notes, requires the exact content to be present in reloaded
    pending notes (or consolidated Experience, so a post-consolidation replay
    still re-reads the same fact);
  - for commits, requires the authorized subgoal/status in reloaded Progress.
- A prior same-content note, wrong user/workspace/agent/run, changed material,
  missing/partial receipt, forged output echo, or in-memory-only state cannot
  certify the request.

### 4. Honest close-out

`backend/core/generic_agent.py`, `backend/core/atom_meta_agent.py`

- Successful runs still call the normal `consolidate_workspace_notes()`.
- Failed/unresolved runs now **preserve** pending notes
  (`{"preserved_notes": n}`) instead of draining the only copy. This is what
  keeps a landed-but-unconfirmed note recoverable.
- Success is still decided by the existing public finalization join; a
  harness-note receipt never substitutes for a completed business objective.

## Existing mechanisms reused (no parallel implementation)

- Unified action registry (`core.action_registry`) — same registration/dispatch.
- Existing `TaskOperationRecord` claim (`core.outbound_operation_claim` via
  `GenericAgent`) — exact retry/no second dispatch, changed-material conflict,
  uncertain-no-resend. The producer receipt is file state; the claim is DB
  state. The code does **not** claim a cross-store atomic commit.
- Existing postcondition oracle contract (`core.oracle`) — independent
  readback, no self-grading.
- Existing BPE JSON persistence (`core/bpe/persistence.py`) — file-based local
  storage remains first-class, with root/backend path anchoring untouched.
- Existing shared request-expectation builder (`core.oracle.request_expectations`)
  — one server-owned freeze path for Generic and the assignment adapter.
- Actor binding is enforced in two layers: the durable `TaskOperationRecord`
  claim includes actor identity for every Generic operation; the file receipt
  also records the authenticated principal when the BPE scope has one
  (server-bound agent runs may legitimately have no user principal).

Research citation used by root: LangGraph persistence guidance separates thread
checkpoints from scoped durable shared information
(https://docs.langchain.com/oss/python/langgraph/persistence). This informed
the "exact operation/run receipt re-read from durable state, not the model's
message/result" split. No LangGraph dependency or proof is claimed.

## Control inventory (authored, NOT executed)

`backend/tests/test_bpe_note_commit_outcome.py`

Failure-first / root-negative twins:

1. `test_landed_note_is_independently_verified_then_consolidated` — landed note
   is `success` + `oracle_verified`, claim `succeeded`, durable receipt exists,
   real consolidation promotes it, reloaded store has Experience.
2. `test_empty_note_is_a_pre_effect_refusal` — no append, typed
   `not_applied`, claim `failed_before_effect`, no uncertainty ledger.
3. `test_commit_without_title_or_with_invalid_status_is_pre_effect` — same
   refusal posture for commit, Progress unchanged.
4. `test_persistence_failure_stays_uncertain_and_preserves_the_note` — save
   failure keeps uncertainty, `uncertain_effect`, and the in-memory note.
5. `test_execute_closeout_preserves_unresolved_note` — real `execute()` with a
   first-write persistence failure: status remains `uncertain`, close-out
   reports `preserved_notes`, and the second real write leaves the note
   recoverable in the durable file.

Valid twins / negative proof:

6. `test_registered_shape_and_read_twin_stay_usable` — real registrations and
   verifier presence; `workspace.track` read twin unaffected.
7. `test_exact_retry_replays_without_duplicating_the_note` — same operation is
   replayed; handler called once; one pending note; verified.
8. `test_commit_is_verified_persisted_and_status_update_is_read_back` — commit
   add + status update both verified against reloaded Progress.
9. `test_prior_same_content_without_this_operation_receipt_is_not_proof`.
10. `test_forged_result_echo_cannot_certify_without_durable_state`.
11. `test_wrong_operation_scope_or_principal_receipt_is_refuted` — operation,
    workspace, agent, run, and actor bindings, parameterized.
12. `test_changed_material_for_same_operation_is_refuted`.
13. `test_partial_receipt_is_refuted`.
14. `test_in_memory_only_state_is_not_durable_proof`.
15. `test_commit_changed_material_same_operation_is_refuted`.
16. `test_durable_readback_shape_is_plain_json` — proof lives in the existing
    BPE JSON file, not a new store.

The tests use real scratch SQLite claims, the real action registry, the real
Generic outcome consumer, and the real BPE JSON store. They do not monkeypatch
an oracle verdict flag.

## Integration / remaining limits (honest)

- **Single-writer file semantics remain.** `BPEWorkspaceStore` is a whole-file
  read/modify/write JSON store. A concurrent writer can still last-writer-win.
  The receipt makes the *observed* operation provable after the write; it does
  not make the DB claim and file write atomic. Reconcile from the durable claim
  + file; do not assume cross-store atomicity.
- **Broader-than-HITL boundary not re-proved here.** Tests isolate the outcome
  consumer with `pre_approved=True`, matching the existing mutation-contract
  suite; governance/HITL behavior is unchanged and out of scope.
- **PostgreSQL / multiworker / fsync / soak remain unqualified** as stated by
  the work order. Only local SQLite scratch claim behavior and local JSON file
  readback are covered by these controls.
- **Legacy callers without a server-owned operation id** keep the historical
  in-memory behavior (no receipt, no oracle proof). The normal Generic
  dispatch path always supplies/mints one for declared mutations.
- **Consolidation failure after a verified note** still follows the existing
  consolidator contract; the new verifier proves the note landed and the note
  is preserved on non-success, but it does not invent a second retry engine.
- The assignment adapter only gets BPE proof if it supplies `bpe_scope`; this
  change did not broaden provider/send/spend/deployment authority.

## Falsifiable result

On this branch, a root run of the work order's external probe should lose both
historical failures: `test_landed_note_must_not_force_uncertain_or_drop_the_note`
and `test_empty_note_is_a_pre_effect_refusal` should pass, while the 5 PASS / 5
SKIP valid twins remain intact. If any landed note still reports `uncertain`,
or an empty note still reports `uncertain`, or the note is dropped after an
unresolved run, this repair failed. Conversely, if a prior same-content note,
wrong scope/actor, changed material, partial receipt, or forged result echo is
accepted as verified, the verifier is too weak and this repair failed.

---

# LEAD REVIEW — root integration rerun at `eb3e2168b` (test-double + isolation repair)

Status: **AUTHOR-ONLY / NOT EXECUTED**. Root ran the integrated module plus the
original external probe at `eb3e2168b` and retained
`/private/tmp/root-bpe-note-eb3-independent.log`: **2 failed, 25 passed,
5 skipped**. This section records the two failures, the trace, and the
test-only repair. No production source changed in this round.

## Failure 1 — exact-retry test double rejected the real call signature

Observed: `test_exact_retry_replays_without_duplicating_the_note` failed on the
first `oracle_verified` assertion with an `uncertain` envelope before the
handler was reached.

Trace: the production consumer invokes the MCP leaf as
`self.mcp.call_tool(tool_name, copy.deepcopy(authorized),
context=handler_context)`. The authored double was
`async def leaf(tool, arguments, inner_context=None)`, so the `context=`
keyword raised `TypeError` after `dispatch_started=True`. The post-dispatch
exception path correctly treated that as ambiguous and exposed `uncertain`.

Repair: **test double only**. The leaf now accepts
`async def leaf(tool, arguments, context=None)` and forwards that context to
the real registry. The exact-retry business assertions are unchanged: first
result independently verified, one handler call, second result replayed with
no second dispatch, one pending note, claim `succeeded`.

## Failure 2 — external probe storage isolation (documented, probe unchanged)

Observed: external
`test_note_material_is_stripped_and_truncated_to_400` saw
`{'success': True, 'buffered': 2}`.

Trace: the external probe's autouse fixture calls `reset_registry()` but does
not bind `bpe_persistence.DATA_DIR`. `reset_registry()` only clears the
process cache; the next `get_workspace()` lazily restores the durable JSON
snapshot. The probe's earlier landed-note control persists to the default
store at the same `(workspace, agent, session)` keys, so the material control
restores that pending note and appends a second one.

Decision: the original external author-only probe stays unchanged. Clearing
pending notes on `reset_registry()` or otherwise wiping production state would
be broad production behavior change and is explicitly rejected. The correct
fix is per-test storage isolation in the probe fixture (bind
`bpe_persistence.DATA_DIR` to a `tmp_path`), which root can apply separately
if desired.

Our module now does exactly that in its own autouse fixture and adds permanent
controls:

- `test_per_test_storage_isolation_binds_the_store_to_tmp_path` — every case
  binds `DATA_DIR` to this test's `tmp_path`, and another test's scope is
  invisible.
- `test_reset_registry_restores_only_the_current_isolated_store` — restore is
  real, but only from this test's root.
- `test_note_material_transform_is_isolated_like_the_external_probe` — the
  external transform reports `buffered=1` under isolation.
- `test_shared_store_without_storage_isolation_would_restore_prior_buffer` —
  reproduces the external probe's `buffered=2` sequence under a temporary
  shared root only; it documents why fixture isolation, not production
  clearing, is the remedy.

Expected root behavior after this commit: our module no longer leaks into any
default store. The external probe's own material control remains subject to
its unchanged fixture if it is run after its own persisted-note control in a
shared store; that is disclosed here rather than hidden by production code.

## New current-User / DB-session authority controls

Traced consumers: `api/rpc_routes.call_action` builds
`{"user", "user_id", "db"}` from the authenticated dependency;
`core.bpe.actions.resolve_scope` branch 1 re-reads that User row
(`_fresh_active_user`), builds the canonical `user:<id>` namespace
(`_build_user_scope`), and refuses a presented row whose workspace no longer
matches current authority. The handler then claims the principal inside the
write transaction; the receipt records `actor_id` when the scope has one.

Added real scratch `Tenant` / `Workspace` / `User` controls (no fake actor
strings, no authority weakening):

- `test_current_user_authority_accepts_active_actor_through_registered_handler`
  — active current User + fresh DB session, RPC-shaped context, real handler
  append/persist, `user:<id>` scope, receipt `actor_id` bound to the principal.
- `test_current_user_authority_refuses_without_a_db_session` — User object but
  no DB session → `scope_principal_unverified`, typed no-effect, no buffer or
  durable state.
- `test_current_user_authority_refuses_stale_workspace_after_change` — a
  detached stale User row presented with a fresh DB session after the current
  row moved to another real Workspace → `scope_authority_changed`, typed
  no-effect in both old and new namespaces.

These are authority controls, not replacements for the existing
`pre_approved=True` outcome-consumer matrix; the latter still isolates
governance while the new controls exercise real current-User re-read and
refusal behavior.

## Round-2 falsifiable result

- `test_exact_retry_replays_without_duplicating_the_note` should now pass with
  the original business assertions.
- Every case in `test_bpe_note_commit_outcome.py` should run without touching
  the repository default BPE store; the isolation controls should pass.
- The new real-User controls should pass: active current principal accepted;
  missing DB and changed workspace refused with typed no-effect.
- The external material control is expected to remain a fixture-isolation
  issue unless its own runner binds `DATA_DIR` per test; it is not repaired by
  changing production restore/clear semantics.
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

# LEAD REVIEW — admitted governance tier + current BPE actor (finite stage)

Status: **AUTHOR-ONLY / NOT EXECUTED**. No Python, pytest, app, server, model,
provider, install, migration, live data or credential action was run here.
Root owns runtime gates and acceptance. Nothing here is a self-acceptance
claim.

## Root-confirmed defects being closed

1. `admit_agent_run()` CASed `AgentRegistry.status` to `running`, then
   `GenericAgent._execute_impl()` re-read that transient row and froze it as
   `tier_at_issuance`. The sandbox correctly treats `running` as unknown and
   fell back to `student`, refusing the real `workspace.note` leaf.
2. A server-bound admitted BPE action carried no current-actor verification
   when the long-lived dispatch context had no DB session. The actor could
   therefore not be re-read as disabled/moved between admission and effect.

## Repair — server-owned tier

`backend/core/governance_tier.py` (normalisation helper only, not a policy
engine/store/table):

- canonical tiers are exactly `student/intern/supervised/autonomous`;
- `running`/`idle`/`success`/other runtime labels are never a tier;
- `effective_governance_tier()` only narrows: an issued tier is a ceiling, a
  current lower canonical tier wins, a disabled row fails closed to `student`,
  and unknown material produces an explicit restricted/unverified source.

`backend/core/agent_decision_write_service.py`:

- captures canonical maturity **before** the status CAS;
- persists `governance_tier`, `governance_tier_source` and raw `prior_status`
  in the existing `AgentJob.result_summary` and admission `AuditLog.extra`;
- does **not** newly reject legacy `idle`/`success` labels. Those are admitted
  under an explicit `legacy_unverified` marker; dispatch then applies the
  student ceiling. No autonomous tier is inferred from runtime state or
  confidence.

`backend/api/agent_routes.py`:

- `_TRUSTED_CONTEXT_KEYS` now reserves `tier`, `tier_at_issuance`,
  `governance_tier`, `governance_tier_source`, `_trusted_governance_tier`,
  `provenance`, `canvas_provenance` and `_bpe_principal_scope`; request-body
  values are overwritten from the durable namespace (not `setdefault`);
- `_admitted_governance_tier()` reconciles new job material against the
  admission receipt. New jobs must agree on tier/source/prior status. Legacy
  jobs reconcile only an existing canonical receipt `prior_status` or a
  current canonical registry row; otherwise they carry an explicit restricted
  legacy marker, never a fabricated issued tier.
- dispatch and resume fail closed with `governance_tier_unverified` only on
  contradictory/tampered material; the job and agent status are settled and
  restored through the existing finalizers.

`backend/core/generic_agent.py`:

- the transient `running` row is no longer used as a tier;
- only the server-bound `_trusted_governance_tier` is accepted as issued
  authority, then current demotion/revocation narrows it;
- `_run_maturity` (custom-action discovery) now uses that same resolved tier,
  not the execution-state row.

`backend/core/atom_meta_agent.py`:

- the meta caller now rebuilds its tier from the trusted registry value and
  fails closed to `student`; the previous exception fallback to `autonomous`
  and caller-authoritative `setdefault` are removed.

## Repair — current BPE actor and stable identity

`backend/core/bpe/actions.py`:

- `stable_run_scope_key()` makes the durable `job_id` the BPE key for admitted
  runs, so initial and resumed/fresh-session passes address one namespace;
  non-admitted chat runs keep the server chat-session key.
- a server-bound `scoped_user_id` is now always re-read through the existing
  `_fresh_active_user` / `_build_user_scope` / workspace-tenant checks. When
  the long-lived context has no DB session, a bounded owned
  `get_db_session()` is opened for resolution and for the write claim, then
  closed. No session is stored on the context across model calls or HITL
  waits.
- an admitted principal can no longer fall through to the anonymous/server
  branch; missing/unverifiable authority is a typed `scope_principal_*`
  no-effect. Legacy server-bound callers without a `user_id` are unchanged.

`backend/core/generic_agent.py` / `backend/core/atom_meta_agent.py`:

- the trusted BPE scope is bound with the admitted `actor_id` and the stable
  run key; prompt render, episode reset, close-out and mutation all resolve
  through the same helper.

## Authored controls (NOT executed)

`backend/tests/test_bpe_governance_tier_issuance.py`:

1. all four canonical tiers are persisted in job + receipt and restored after
   the run;
2. legacy `idle`/`success`/`unknown` statuses remain usable under the
   restricted student ceiling, with `governance_tier=None` and
   `legacy_unverified` source — never autonomous;
3. `running` is an execution state, not an admission tier (existing
   `ALREADY_RUNNING` conflict preserved);
4. forged body `tier`, `tier_at_issuance`, `governance_tier`, provenance,
   canvas-provenance and BPE scope are rebuilt from admission; the effective
   tier is the canonical low tier and the stable scope is the real job key;
5. initial and resumed trusted contexts for the SAME job agree on the issued
   tier/source across fresh sessions;
6. effective-tier narrowing covers running, demotion, revocation, unknown
   runtime state and legacy current-only material;
7. the stable run key prefers the durable job id;
8. a server-bound active actor appends through a bounded owned session;
   disabled and moved actors return typed no-effect with zero new note;
9. the root public positive/negative twins: real scratch team-lead reviewer,
   real `InterventionService.approve_intervention`, persisted
   approved/`reviewed_by`, original production `_wait_for_approval`; positive
   lands the note at `tier_at_issuance=autonomous`, revoked actor writes zero
   note. No approval is mocked or waived.

`backend/tests/test_round81b_journey_followups.py` was honestly re-contracted:
its old `test_caller_values_authoritative` encoded the defect (caller tier
accepted). It now asserts caller `tier`/`tier_at_issuance` are not
authoritative and the canonical registry tier wins. The other G9 assertions
(identity stamping, DB-error student fallback) are unchanged.

CI: the new module is a permanent backend step in `.github/workflows/ci.yml`.

## Cross-caller behavior change (explicit)

- Direct `GenericAgent.execute()` callers can no longer raise/lower the sandbox
  tier by putting `tier`/`tier_at_issuance` in `context`; the canonical current
  registry row (or a server-owned admission tier) decides.
- Legacy non-canonical agent statuses are admitted under a student ceiling
  instead of being interpreted by the sandbox issuer as an arbitrary value.
- Atom meta-agent no longer falls back to `autonomous` on registry errors.
- Admitted BPE runs use the durable `job_id` as scope key, so a resume/fresh
  session continues the same buffer rather than minting a new one.

## Preserved / explicitly open

- All sandbox, capability, role, authority, approval, budget, Oracle and
  strict route gates remain enabled; no wildcard grant, whitelist disable,
  forced policy, fake Agent row or fake approval was added.
- Existing BPE receipts, typed refusals, exact hashes/scopes, unresolved-note
  preservation, scope encoding and truthful write failure are untouched.
- Pre-repair pending jobs without canonical job material are reconciled only
  from a canonical receipt/current row; otherwise they get the restricted
  legacy marker and `review_agent_maturity` next action. They are not silently
  promoted.
- No file-vs-SQL atomicity, multiworker, crash, PostgreSQL or fsync guarantee
  is claimed. Root must execute the new controls and the wider accepted
  selection; no result is claimed here.
