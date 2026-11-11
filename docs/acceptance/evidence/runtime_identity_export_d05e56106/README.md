# Exported runtime identity — loaded bytes, never an ancestor checkout

Status: **frozen backend source/test candidate submitted for independent
review.** No merge or self-acceptance.

Base: current main `230231f5114612f4b31a602190c318667e94f2f1`  
First repair: `9d3d3de5a`  
Content-bound repair (this packet): `d05e56106806b6f331ff5c3b166848948e66bc10`

## Actual gaps

1. `capture_runtime_identity` derived `repo_dir` lexically as the parent of the
   loaded backend directory, then ran `git -C repo_dir rev-parse HEAD` without
   checking that Git's top-level was that same source root. An immutable
   acceptance export nested beneath `/Users/rushiparikh/projects/atom` therefore
   reported the canonical checkout's HEAD and dirty state. The retained UI
   launch's `ec69e24f...-dirty` health string versus its verified export
   `b4aa64ed...` demonstrated the mismatch. This was never proof the wrong
   product bytes ran, but it was not a truthful identity.
2. The first repair reused `MANIFEST.json` + `code_manifest.json` but only
   validated shapes/non-empty metadata and hashed the metadata files. Root's
   drift probe changed `code/backend/app.py` while keeping the original
   manifests; the capture still returned the same clean `export-sha256:...`
   identity with no error. Metadata shape is not byte integrity.
3. `run_isolated` printed `PINNED_REV` unconditionally in snapshot mode, so a
   `farm -> world/code @ 79b2a41032` line named a historical pin, not the
   working-tree export that was written.

## Repair

`backend/core/runtime_identity.py`:

- Git is trusted only when `git rev-parse --show-toplevel` resolves to the
  loaded source root. Otherwise the enclosing repository is recorded only as
  `ancestor_git_toplevel` for diagnosis and is never used as `revision` or
  `source_id`.
- Export/install identity reuses the existing `run_isolated` contract:
  `MANIFEST.json` pin + per-file `code_manifest.json`. No second provenance
  store.
- The actual export/loaded tree is verified:
  - every manifest path is relative, non-escaping, and a valid 64-hex entry;
  - every export file must exist under the export code root and match its
    hash; symlinks must stay inside that root;
  - every loaded backend code file must exist, resolve to the exact export
    file (no unrelated farm), and match the hash;
  - missing, changed, invalid, path-escaping, or extra loaded code reports
    `identity_kind="unknown"` with an explicit error — never a clean export
    identity;
  - mutable `data`/`logs` and narrow runtime artifacts (`.env` shadows,
    SQLite, logs, `.pyc`) are excluded from the loaded-code mapping; export
    bytes that are in the manifest are still verified.
- Native clean/dirty checkouts remain fully attributable. NoGit installs and
  unverifiable exports are `unknown`, not clean and not an ancestor revision.
- `RuntimeIdentity.as_dict()` remains additive: kinds, export/manifest hashes,
  verified/loaded counts, verified Git top-level, and ancestor diagnostic.
  Existing health/header/launch-descriptor shapes are preserved.

`backend/scripts/orchestration_acceptance/run_isolated.py`:

- Snapshot mode prints `farm -> world/code @ snapshot-sha256:<actual hash>`;
  archive mode keeps the pinned/refchecked `archive:<PINNED_REV>` label.

## Verification

| Check | Result |
|---|---|
| Failure-first temp-repo tests | **11 failed**; export reported ancestor HEAD/dirty |
| Root drift probe (original negative) | changed bytes still accepted as clean export |
| Identity tests after repair | **19 passed** |
| Focused identity + health routes | **63 passed** |
| Root drift probe after repair | after byte change: `unknown`, error `export file content changed: backend/app.py`; source id changed |
| Retained-world actual metadata boundary | **export verified**: 7,847 export files / 7,837 loaded code files, `export-sha256:86ff63fda943`, 2.23 s, no ancestor HEAD |
| Pre-existing task-lifecycle count failures | same 4 fail on clean baseline with the fix stashed; unrelated |

The retained-world check reads an existing isolated world's metadata and
exported files only. No world was built or deleted; no live DB, model,
provider, credential, send or spend was used.

## Permanent controls

- drift negative: same `source_id` must not survive changed bytes with retained
  manifests;
- missing file, changed file, unsafe path, invalid hash, extra loaded code,
  unrelated farm;
- unchanged snapshot, archive, symlink-farm and runtime-artifact valid twins;
- native clean/dirty; noGit install; missing/malformed/conflicting manifests;
- snapshot/archive build-label test.

## Boundaries

- Backend source/tests only; no schema, router, store, dependency or new
  provenance engine.
- No browser rerun for the historic UI capture; that raw evidence and its
  explicitly incomplete raw-health disclosure remain unchanged.
- Root owns integration and final review; no merge.
