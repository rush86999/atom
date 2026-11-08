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

## Path anchoring (traced and documented, not rewritten)

`DATA_DIR = Path(os.getenv("ATOM_BPE_DATA_DIR", "backend/data/bpe_workspaces"))`
is CWD-relative and resolved once at import. `__init__()` only substitutes
`DATA_DIR` when no explicit `data_dir` is supplied, and all three production
call sites construct `BPEWorkspaceStore()` with no directory. Consequently:

- started from the repo root, the default resolves to
  `<repo>/backend/data/bpe_workspaces` (the intended location);
- started from `backend/`, it resolves to
  `<repo>/backend/backend/data/bpe_workspaces`, diverging from the documented
  `backend/`-anchored store convention unless `ATOM_BPE_DATA_DIR` is absolute.

This is the known relative-path anchoring bug class in `AGENTS.md`. It is not
changed here because it is outside this write-outcome repair; a follow-up
should anchor the default to `backend/` (as `core.automation_settings` does)
or require an absolute env override. The authored controls use explicit
temporary directories, so they do not exercise the default path.

## Explicitly open (not claimed here)

- Callers do not log, retry, or otherwise act on a `False` save result.
- No fsync/durability guarantee and no multi-process locking semantics.
- Broader BPE/Oracle gaps and principal/workspace scope work are untouched.
