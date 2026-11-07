# Browser info-wait driver — frozen Git blob source binding (2026-11-07)

Status: **PREPARATION ONLY.** No world, application server, browser, provider
shim process or live provider/model/account/credential was started. No
dependency was installed. Root owns the subsequent browser execution.

Source at this proof: `a580933337b835faa7580a2e95d53a4eafa9e319`.
Driver SHA-256: `273e62d83c806604940ae3a5e401cd90f503b03e646e5e0e97b9427937754214`.

## Blocker and fix

Root's verifier `/private/tmp/test_lead_browser_frozen_export_binding.py`
failed against the prior head because a bogus all-zero
`backend/api/agent_routes.py` hash present in **both** `export_tree` and
`code_manifest` was certified. Those two maps are self-generated, and
`preflight.source_revision` only reads the current HEAD; neither proves that
the exported bytes came from the frozen commit.

The binding now:

1. Reads the exact tracked `backend/` file set at `frozen_source_sha` with
   `git ls-tree -r -z --full-tree <sha> -- backend`.
2. Streams each Git blob through `git cat-file --batch`.
3. Requires the exported file bytes, `code_manifest` entry, and `export_tree`
   entry to equal that Git blob's SHA-256.
4. Refuses missing expected tracked files, unexpected untracked backend files,
   unsupported Git modes, and any manifest/export mismatch.
5. Explicitly allowlists only launcher-generated paths that are **absent from
   the frozen commit** (`backend/logs/`, `backend/data/`,
   `.pytest_cache/`, `__pycache__/`, `*.pyc`, test/dev SQLite files) and reports
   them. Tracked files under those prefixes are still audited against Git.
6. Records MANIFEST `source_revision` absence but never uses it as a pass; a
   present conflicting value fails.

## Preserved root negative

`root-browser-source-binding-negative.log` is root's original failing verifier
log. `root-negative-after-fix.log` is the same verifier run against this head:
**1 passed**. The original all-zero, self-consistent fake maps are also kept as
a local regression test (`test_original_self_consistent_fake_manifest_negative`).

## Focused tests

`identity-tests.log`: **17 passed**. The valid twin uses a real temporary Git
repository and real `git ls-tree`/`git cat-file` bytes; fake hashes cannot
certify by construction. Cases cover:

- unobserved / wrong / exact frontend cwd;
- valid actual-Git twin;
- consistent-but-wrong exported bytes;
- original self-consistent fake-manifest negative;
- missing exported tracked file;
- tampered export byte;
- wrong consistent manifest hashes;
- unexpected untracked backend file;
- explicitly allowlisted launcher-generated file;
- missing frozen commit;
- wrong health cwd and descriptor export;
- conflicting MANIFEST source revision and preflight-source mismatch.

## Actual source binding proof

`actual-git-binding.json` builds the export with the same
`run_isolated._working_tree_snapshot()` path used by the real world, extracts
it to a temporary directory, and compares it to Git blobs at the frozen commit:

- frozen source: `a580933337b835faa7580a2e95d53a4eafa9e319`
- expected tracked backend files: **7723**
- exported backend files: **7723**
- Git blobs checked: **7723**
- mismatches/missing/unexpected: none
- `ok: true`
- MANIFEST `source_revision` present: **false** (recorded, not used)

This is a source-binding proof only; it is not a world/server/browser run.

## Preflight

`preflight-run.log` and `preflight.json` report `ok=true` with `TESTING=1` and
explicit fresh scratch `DATABASE_URL`/`ATOM_DATA_DIR`/`ATOM_OFFICE_DIR`:
source HEAD `a58093333`, clean backend tree, five `ReActStep` envelopes, and
the existing `provider_shim.load_script` index. The only warnings are the
execute-only gaps in this worktree (`backend/venv314` and
`frontend-nextjs/node_modules` absent; not installed).

Compile, `--help`, and `pyflakes` are recorded in
`compile-help-pyflakes.log`.

Root may now execute the actual browser run from the prepared/frozen capture
worktree. The driver remains preparation/execute only; no browser was launched
here.
