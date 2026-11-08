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
