# Lead review — exact repeated external reply identity (implemented)

**IMPLEMENTED-NOTRUN.** This branch contains an authorized finite runtime
repair. No native test, app, server, model, provider, browser, credential or
live-data action was executed by the author. Root owns execution and
acceptance. No test here is claimed as passing.

Source lineage:

- baseline production: `c97dada13`;
- author-only test/review: `bf1d9bbd9`;
- root test-scaffold correction: `336f374f5`;
- root behavior probe: `a68d8e30a`;
- this repair commit: `codex/assignment-reply-identity-20261108` (exact hash in
  the handoff).

Only these files were changed by this repair:

- `backend/api/assignment_routes.py`
- `backend/core/assignment_executor.py`
- `backend/core/goals/goal_run_events.py` (existing event caller)
- `backend/tests/test_assignment_external_reply_identity.py`
- `LEAD_REVIEW.md`

No new table, store, engine, migration or parallel ledger was added.

## Implemented contract

### 1. Optional opaque `reply_id` reaches the shared executor

`AssignmentExternalResponse` now has `reply_id: Optional[str] = None`. The
public route passes it unchanged to `AssignmentExecutor.record_external_response`.
The value is never stripped, case-folded, Unicode-normalized or collapsed; two
IDs that differ only by case, leading/trailing space, or composing/decomposing
Unicode remain distinct. IDs are identity only, never authentication or
authority.

The event caller (`goal_run_events._resume_woken_run`) also passes an explicit
`event["reply_id"]` when present, and preserves the omitted-ID path when absent.

### 2. Explicit identity is strict

Every direct step-wait reply is evaluated inside one `mutate_assignment` CAS
callback. The callback re-reads the fresh assignment on every retry, then:

- binds an explicit ID to `run_id` / correlation / fact / subject scope;
- computes the canonical material digest from the complete submitted material;
- if the same ID + same material already produced an outcome, returns that
  outcome without a write, conflict entry, decision, wake or effect;
- if the same ID carries different material, returns `reply_conflict` before
  any state transition (the route maps it to HTTP 409);
- if the same explicit ID appears on another correlation/fact/subject, returns
  a scope conflict before any transition;
- if the wait is already settled and the identity is new/changed, refuses
  rather than certifying a replay.

An exact previously accepted reply is `already_applied` (explicit ID). A legacy
accepted replay keeps the historical `resumed` result while the job is still
in flight, or `already_applied` once terminal, but always sets
`replayed: true`. The route and event caller return immediately for
`already_applied` / `replayed`, so a duplicate never triggers a second
`execute`/`advance`.

### 3. Material digest

`_external_reply_material_sha256` hashes a canonical JSON object containing:

- correlation id, fact, subject, expected party;
- typed-binding flag and expected answer type;
- exact `response`, `source` and `evidence` text;
- `value`, with numeric values in explicitly typed numeric waits passed through
  the existing `_canonical_fact_value` (`5.0` and `5` compare equal); every
  other value is preserved as supplied.

The digest is never supplied by the caller and never built from the bounded
display projection. Presentation/conflict fields remain bounded separately.
Unsupported or oversized material fails closed as a typed `reply_conflict`
rather than hashing a truncated representation. Existing typed validation,
source-party validation and fresh source-fact resolution are preserved.

### 4. Omitted-ID compatibility

Omitted IDs are not a fixed per-correlation identity. A legacy reply derives
its identity from the exact material digest + wait scope. Therefore:

- an identical unkeyed retry matches the existing receipt and replays the prior
  outcome without another event;
- a changed unkeyed reply while the wait is open is a new event, so a legitimate
  partial reply followed by a corrected/full reply still completes the same job;
- after the wait has already been accepted, a changed unkeyed reply is not new
  authority: it reports the prior accepted outcome (`already_applied` when
  terminal, `resumed` + `replayed` while still in flight) and creates no second
  effect. This preserves the existing procurement-campaign replay contract.

Explicit-ID semantics remain strict in all cases.

### 5. Durable receipt history

The authoritative identity history is the existing wait step JSON:

```text
step["reply_receipts"] = [
  {
    reply_id, identity_kind, material_sha256,
    correlation_id, fact, subject,
    outcome, reason, message, at,
    conflict?              # bounded display copy only
  },
  ...
]
```

`reply_receipts` is append-only. It survives a fresh SQLAlchemy session and is
not limited by the public conflict projection, which remains `conflicts[-10:]`.
A replayed or refused reply does not append a receipt. An old identity beyond
ten display entries can still replay its original outcome or be refused for
changed material; it cannot silently become a new authority. There is no
arbitrary cap that permanently prevents a same-job complete answer.

Accepted replies also carry the same identity/digest plus the original wait
scope (`fact`, `subject`, `party`, `typed_binding`, `expected_answer_type`) in
`step["external_response"]`. This lets an exact replay be re-hashed after
`waiting` has been cleared, including after completion and restart.

### 6. CAS and authority

- All step-wait identity checks, terminal checks, material checks and receipt
  writes happen inside `TaskLifecycle.mutate_assignment`, i.e. under the
  existing task-version CAS. A pre-read is not used as authority.
- A private `_ExternalReplyStop` carries a replay/refusal result out of the CAS
  callback, so no task-version bump, decision or effect is written for a replay
  or refusal.
- Two concurrent same-ID/different-material writers cannot both wake: the CAS
  loser re-runs the callback on fresh state and sees the winner's receipt.
- The waiting operation is superseded only after a successful accepted-reply
  CAS write, and `_wake_run` is called only for a new accepted reply.
- Route `_scoped_run` still refuses foreign workspace/tenant callers before the
  executor is reached.
- Cancellation/terminal work refuses new or changed late identities; the
  existing terminal-refusal decision is retained.

## Tests authored (not executed)

`backend/tests/test_assignment_external_reply_identity.py` now covers:

- the public changed-`r1` failure-first control;
- same explicit ID / same material idempotency, including canonical `5.0` -> `5`;
- new explicit ID resumes the same job once;
- late new identity after completion is refused, not `already_applied`;
- cancellation and foreign-workspace refusal with fresh-session readback;
- field-class contradictions: changed response, source, evidence and value
  under the same ID each refuse before transition;
- opaque-ID twins differing only by case, leading space or Unicode composition;
- omitted-ID partial -> corrected/full compatibility, with identical-retry
  idempotency;
- 12 conflict events: 10-entry display bound, full receipt history, replay of
  the old ID, changed-material conflict, and fresh-session readback;
- stale wait-scope conflict;
- deterministic CAS interleaving: a competing writer inserts a receipt between
  the outer read and the actual callback; the same-ID request must refuse.

Root also retains the independent behavior-only probe
`test_root_assignment_reply_material_probe.py`. No assertions were weakened to
fit the implementation.

## Established practice cited

- AWS EC2 API idempotency: a client token is bound to unchanged request
  parameters; reusing it with different parameters is an error.
  <https://docs.aws.amazon.com/ec2/latest/devguide/ec2-api-idempotency.html>
- Temporal message handling: duplicate delivery and interleavings are handled
  by deduplication/identity, not by trusting arrival order.
  <https://docs.temporal.io/handling-messages>

The implementation reuses the repository's SQLite lifecycle CAS rather than
adding Temporal or an in-memory lock as database authority.

## Remaining limitations / honest gaps

1. **Gap/question waits are not in this identity slice.** `record_external_response`
   still delegates unresolved-question replies to the existing `resolve_gap`
   path. Reply identity receipts apply to direct step waits. Full multi-fact
   coordination, including identity over question waits, remains open.
2. **Legacy after-settlement compatibility is intentionally looser than explicit
   IDs.** A changed unkeyed reply after the wait is already accepted reports the
   prior accepted outcome rather than creating a new event. This preserves the
   existing procurement-campaign replay test and prevents a new effect; explicit
   IDs remain strict. While the wait is open, changed unkeyed material is still
   a new event.
3. **Oversized material fails closed.** The existing canonical fingerprint
   validator bounds string/depth/byte size. Material outside those bounds is
   refused as `reply_conflict`; it is never truncated into the digest.
4. **Receipt history growth is append-only.** Public conflict display remains
   bounded at ten, but the authoritative receipt list is not capped. A future
   compaction must preserve authoritative lookup (or otherwise fail closed) and
   must not silently evict an identity into new authority.
5. **Pre-repair accepted waits without receipts are not certified as exact
   replays.** A settled wait with no receipt gets terminal refusal for a new
   reply rather than a fabricated idempotent replay. This is a deliberate
   migration boundary.
6. No native test was run. Root must execute the focused file and the existing
   assignment suites, reproduce the original failure before repair evidence,
   and accept or reject the result.

## Verification status

**IMPLEMENTED-NOTRUN.** Root executes. The author makes no pass claim.


## Root independent verification and legacy follow-through

Frozen381 passed16 focused controls, including the original root public changed-explicit-ID negative. Root then tested the documented legacy terminal exception at70512246b: changed unkeyed material received HTTP200/already_applied on a completed assignment. This is not an exact replay and was misleading even though it did not create a second effect. The original failing log/spec/exit is retained at root-assignment-reply-legacy-negative. Root removed that exception: material-derived legacy identity must match the original digest just like any exact retry; changed late input reaches existing terminal refusal. Legitimate unkeyed partial->corrected answers while waiting remain allowed. No business-result, authority, artifact or source-readiness check is weakened. Retest/affected gates remain required. Direct gap/question resolution remains a separately open compatibility/integration row, not full coordination acceptance.


## Root verification at fa6a047f6

The seven-module affected assignment/executor/routes/durable-wait/source-
continuation/event selection passes 220/220 on Python 3.14 and 3.11. The
source remained fa6a047f67ad762b5c04e97ea3a8124ea323a004 for both runs.
This includes the permanent external reply identity and independent changed-
material probes, now added to the existing source-continuation CI step.
Raw logs/specs/exits remain at root-assignment-reply-fa6-affected (3.14) and
root-assignment-reply-fa6-affected-py311 (3.11) in retained scratch evidence.
The 3.14 completed world was byte-verified into the portable-drive archive
before removing its internal uncompressed copy.

Scope: direct-step replies only. The question/gap response path is under a
separate read-only review; no general repeated-partial or days-long coordination
claim follows from these controls. No live model/provider/effect was used.


## Independent caller audit: two-domain campaign expectation

DeepSeek's read-only review identified a caller control outside the original
seven-module 220-test selection. Executing it unchanged at da280ff17 gives
1 failed / 3 passed: the procurement campaign calls a changed terminal answer
"exact replay" and expects already_applied. This contradicts the intentionally
repaired exact-material contract. The test now has both twins: original
accepted material must replay; changed material must return terminal while
keeping the completed assignment and one bill effect. No runtime guard was
relaxed. The campaign is added to the existing CI step. Earlier220 results
remain accurate for their named selection and are not expanded retroactively.


# Merged foundation review history (retained, source-bound)

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


## Root main integration

Integrated main33ab6c5 normally. Only the independently added LEAD_REVIEW
files conflicted; both complete histories remain above. Assignment runtime
and all previously verified assignment tests are unchanged from e65c2ac88.
The CI union keeps the current-main BPE/RPC controls and the exact-reply and
two-domain campaign modules. Fresh hosted checks apply to this new head.
