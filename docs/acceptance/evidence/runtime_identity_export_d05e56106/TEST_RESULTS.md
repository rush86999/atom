# Exported runtime identity — test results

Executed source: `d05e56106806b6f331ff5c3b166848948e66bc10`  
First repair: `9d3d3de5a`  
Base/current main: `230231f5114612f4b31a602190c318667e94f2f1`

Python 3.14 (`backend/venv314` linked from the existing install; no new
dependency). Scratch temporary repositories/files only. No app DB, live
account, model, provider, credential, send or spend.

## Failure-first: ancestor checkout leaks into an export

Command:

```
TESTING=1 python -m pytest backend/tests/test_runtime_identity_export.py -q
```

Before the repair (`failure-first-ancestor.log`): **11 failed**.

The decisive first case created a temp Git ancestor with HEAD + dirty state,
then an export beneath it with its own `MANIFEST.json`/`code_manifest.json`.
`capture_runtime_identity(cwd=<export>/backend)` reported the **ancestor**
revision and dirty digest instead of the export.

## Root drift negative and after-gate

Root's original probe changed `code/backend/app.py` while keeping the original
manifests. Original negative (`root-drift-probe-original-negative.json`):

```
first:      kind=export, source_id=export-sha256:559037ec5185, error=null
after_drift kind=export, source_id=export-sha256:559037ec5185, error=null
same_id_after_changed_bytes=true
accepted_changed_export=true
```

After the content-bound repair (`root-drift-probe-after.json`):

```
first:      kind=export, source_id=export-sha256:76b0c7c37c72, error=null
after_drift kind=unknown, source_id=unknown,
            error=export file content changed: backend/app.py
same_id_after_changed_bytes=false
accepted_changed_export=false
```

## After repair

```
TESTING=1 python -m pytest \
  backend/tests/test_runtime_identity_export.py \
  backend/tests/api/test_health_routes.py -q
```

Result: **63 passed** (`focused-d05e56106.log`).

The 19 identity controls cover:

- native clean checkout, native dirty checkout;
- export nested under a dirty ancestor (must not claim it);
- unchanged snapshot, archive, symlink-farm and runtime-artifact twins;
- drift negative with retained manifests;
- missing file, changed file, unsafe path escape, invalid hash, missing
  `code_manifest`, missing/malformed/conflicting `MANIFEST`;
- extra loaded code and an unrelated farm;
- noGit install;
- snapshot vs archive build-label print.

## Actual retained-world metadata boundary

Read-only against an existing isolated world
(`actual-retained-world-identity.json`):

```
identity_kind=export
source_id=export-sha256:86ff63fda943
export_sha256=86ff63fda943c572b35208377076ada28082075aeca2f8cf00c6dd617e131078
export_verified_files=7847
export_loaded_files=7837
ancestor_git_toplevel=/Users/rushiparikh/projects/atom
ancestor_head_rejected=true
elapsed=2.229s
error=null
```

This is a metadata/byte-integrity boundary on a retained world, not a new
browser or employee journey. No world was built or deleted.

## Pre-existing unrelated failures

A broader run including `backend/tests/test_task_lifecycle.py` produced
199 passed / 4 failed. The same 4 failures reproduce with this fix stashed on
the same clean base (`task-lifecycle-baseline-4-preexisting-failures.log`).
They are count/retrieval fixture failures, not caused by this change.

## Boundaries

No schema/router/store/dependency change; no second provenance engine; no live
DB/model/provider/credential/send/spend; no world build or deletion; no merge.
