# Source identity reconciliation — browser custom Hire

Status: **executed product bytes attributed; raw health payload not preserved.**

The browser join's controls passed 23/23, but its launch line reported health
`source_id=ec69e24f4385-dirty.d48ca` while the captured product source was
`708d4d6a5` and the evidence head was `416094ffb`. That string is **not** the
loaded snapshot. It is inherited canonical-repo metadata.

## Why `ec69e24f4385-dirty...` appeared

`core.runtime_identity.capture_runtime_identity()` derives `repo_dir` as the
parent of the loaded backend directory. In the isolated world the loaded module
is `<world>/backend_root/core/runtime_identity.py`, so `repo_dir` is the world
directory. `git -C <world> rev-parse HEAD` walks up to the enclosing canonical
repo `/Users/rushiparikh/projects/atom` and returns that repo's HEAD and dirty
state.

Confirmed now:

- canonical HEAD: `ec69e24f4385727cf6a97270ed66eb9b56262c06`
- canonical status: 83 modified, 54 untracked (same counts as the run log)
- canonical digest now: `8f488a4d9e78` (at run: `d48cacd2123b`; the live
  canonical worktree changed after the run, so its digest moved)

The health identity therefore describes the ambient canonical checkout, not
the world export. It must not be used to attribute the executed code.

## Why `79b2a41032` appeared in the build log

`[world] built: ... farm -> world/code @ 79b2a41032` prints the module constant
`PINNED_REV` unconditionally in `run_isolated.py`. In snapshot mode the export
is the working-tree tar, not that historical commit. The export's actual
identity is the recorded `code_snapshot_sha256`:

```
b4aa64edb48cc5f24ed318afb627fc5a700c795f3f5626b6b0fa654455f5be49
```

Recomputing the backend working-tree snapshot now gives the same hash, so the
executed backend bytes are the recorded snapshot.

## Executed bytes against frozen refs

| Surface | Evidence | Result |
|---|---|---|
| Backend snapshot | world MANIFEST `code_snapshot_sha256` == recomputed working-tree snapshot | `b4aa64ed...` match |
| Backend product files | current files == `708d4d6a5` for custom route, decision service, onboarding route, runtime identity, health app | all match |
| Frontend run-time tree | run capture dirty list has no `frontend-nextjs` entry; `416094ffb` frontend files == `708d4d6a5` | all match |
| Frontend copy source | `case5_browser_recovery.start_frontend_copy` copied the worktree `frontend-nextjs`; no untracked frontend source | source-bound |

The browser run predates the receipt-binding repair. The current
`lib/agent-onboarding-api.ts` is the post-repair source; the browser run used
the clean `416094ffb` tree, which is byte-identical to `708d4d6a5`.

## Health payload completeness

Not preserved: the raw `/api/health` JSON and the world's
`launch_descriptor.json` were not copied before the disposable world was
removed. What is preserved:

- backend PID `40591`;
- working directory `<world>/backend_root` (server log);
- health `source_id`/revision/dirty counts used by the launcher (server log);
- the launcher's health check validated `identity.cwd` equals the expected
  world backend root before returning.

So **health-payload attribution is incomplete on the raw-payload field**, while
product-code attribution is proven by the snapshot and file hashes above.

## Exact mapping

| Item | Truthful identity |
|---|---|
| Browser-run frontend | `708d4d6a5` (via clean `416094ffb` tree) |
| Browser-run backend | `708d4d6a5` backend (snapshot `b4aa64ed...`; unchanged from base `38dae97a6`) |
| Health `source_id` | ambient canonical repo `ec69e24f4385-dirty...`; not executed code |
| Build-log `79b2a41032` | hardcoded `PINNED_REV` print in snapshot mode; not the export |
| Raw health payload | not preserved; attribution incomplete |
| Browser controls | PASS 23/23 |
| Receipt-binding repair | `31a82b316`; post-browser; no browser rerun |
