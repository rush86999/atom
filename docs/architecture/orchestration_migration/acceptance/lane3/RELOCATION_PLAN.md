# Portable-drive relocation plan — reconciling both world copies

**Status: PLAN ONLY. Nothing in this document has been executed.** It is written
because the 13:27 relocation attempt died holding the interlock, and because the
copy already on the drive is stale. Executing it is a separate, deliberate
operation with its own approval.

Prepared 2026-09-27 by Lane 3. Read `STORAGE_RECOVERY_REPORT.md` first for the
current state.

## 1. Why this is not a copy

The obvious command is wrong here and would be destructive:

| | Local (authoritative) | Drive copy |
|---|---|---|
| Worlds | 37 | **35** |
| Size | 70G | 55G |
| Last written | Sep 26 22:59 (root mtime) | **Sep 26 21:34** |

The drive copy is from an **earlier** attempt and is already behind. Mirroring
local over it with `rsync --delete` or a fresh `cp` would be acceptable *only*
after an explicit reconciliation; the earlier review's warning applies directly:
the external copy may contain stale *or deleted* worlds, and a destructive mirror
against the broader portable tree is not acceptable.

## 2. The destination problem

Config already names a destination:

```
worlds.root        data/acceptance_worlds
link_target        /Volumes/Seagate Portable Drive/projects/atom/backend/data/acceptance_worlds
volume             Seagate Portable Drive, uuid 0C0C11D3-8011-4F04-A213-E3EFE642C992
```

Three things must be settled before anything is written:

1. **Is that the destination we want?** It already holds 35 worlds from a prior
   attempt. Writing into it in place means reconciling against unknown prior
   state. **Recommended: a new versioned destination**, e.g.
   `…/acceptance_worlds.v2`, so the old copy stays intact as a fallback and the
   reconciliation has a known-empty target. That costs 70G of drive space, which
   is not a constraint (1.6Ti free).
2. **Volume identity, not volume name.** `diskutil info` UUID
   `0C0C11D3-…` must match `world_storage.json` before a single byte is written.
   A renamed or substituted volume must fail closed, never silently recreate a
   local store.
3. **Local stays authoritative throughout.** The switch is the *last* step, and
   the rename-to-rollback-copy must not be deleted until the user approves it in
   writing with the reclaimed size stated.

## 3. Preconditions — all must hold

- `world_storage_guard check` passes with **no** maintenance lock.
- No launcher is running: `preview_v1` and `candidate_fix1` stopped via
  `preview_stack down`, recorded pids confirmed gone.
- `:3000` / `:8001` are left running, and there is positive evidence they do not
  use this worlds tree. **Fail closed if that evidence is unavailable** — do not
  infer it from the absence of an error.
- The destination volume is mounted and its UUID matches.
- Free space on the destination ≥ local worlds size × 1.2.
- The interlock is held for the whole of §4–§6.

## 4. Inventory before copying (read-only, both sides)

Produce and keep, for local and for the chosen destination:

- every world directory, with its real (symlink-resolved) path
- per-file **type, size and content hash** for retained files; not a file count
  and not a single manifest hash — those were called out as insufficient
- every internal symlink and its resolved target
- `MANIFEST.json` / `code_manifest.json` per world
- **SQLite integrity check plus a content hash for every `atom.db`**, and the
  presence and size of `-wal` / `-shm` siblings

Then compute a **reconciliation diff**, which is the deliverable of this step and
the reason not to just copy:

```
worlds only in local        -> copy forward
worlds only in destination  -> PRESERVE, report, ask; never delete silently
present in both, differing  -> report per-file; destination is not trusted
```

The "destination-only" bucket is the one that gets destroyed by a naive mirror.
It must be listed and explicitly dispositioned before any write.

## 5. Copy, and what must not be excluded

Copy source → destination with permissions and symlink targets preserved.
Include SQLite `-wal`/`-shm` files if present; do **not** delete them to make the
copy simpler.

Exclusions are only rebuildable caches, only after their processes have stopped:
`backend_root/.next*`, `__pycache__`, and the frontend farm distDirs inside
worlds. **Never exclude** logs, evidence, source, databases, fixtures, or
manifests as "churn". Keep an explicit accounting of every excluded path, with
counts and bytes.

Stop and report rather than continue if any file's hash differs between the
source read and the destination read after copy, or if any command exits non-zero.

## 6. Switch, as a two-step with rollback

The worlds root must become a symlink, and a symlink cannot replace a directory
atomically. So there is a brief missing-path interval and it must be handled
deliberately:

1. Verify the destination copy completely (step 4's inventory, re-run against it).
2. Run one representative smoke against the destination **before** switching, by
   pointing an explicit `DATABASE_URL` at it — no symlink involved.
3. Rename the local worlds root to a rollback name. **Do not delete it.**
4. Create the symlink at the canonical path.
5. Launch one world from the symlinked path and verify: DB writes and history,
   a workbook read, evidence, a retry pin, and a restart.
6. If anything fails, remove the symlink and rename the rollback copy back.

Record the storage relocation **separately from code fingerprints**. Physical
storage moving is not a production change and must not mint a new candidate
identity or force every world to be rebuilt.

## 7. Verification that matters

- `world_storage.json` `layout` flips to `drive_symlink` **only after** the
  symlink exists; the guard already rejects a plain local directory while
  `drive_symlink` is configured, which is the property that stops a launcher
  from silently mkdir-ing a fresh empty world when the drive is absent.
- A launcher preflight must refuse a missing volume, a UUID/name mismatch, and a
  dangling worlds symlink.
- **Test the missing-drive refusal with a controlled unavailable-target
  configuration** — not by unplugging a mounted, active database.
- Confirm code that resolves physical paths still passes identity checks
  (cwd, open DB path, loaded-module paths) when reached through the symlink.

## 8. Reclaim — and only on explicit approval

Renaming and symlinking reclaims **zero** bytes. The rollback copy keeps the
70G. After the smoke test passes:

1. Report the rollback directory's exact path and current size.
2. State the expected reclaimed bytes.
3. **Wait for the user to approve that specific deletion**, naming the path.
4. Only then delete that exact directory. No wildcards, no `rm -rf` on a
   computed path.
5. Measure actual free space afterwards and report the real number.

The portable drive must stay connected for subsequent runs. A world whose storage
vanished is not a recoverable state, and the guard is designed to make that loud
rather than silent.

## 9. What must never happen here

- No `git add -A`, no reset, no stash, no history rewrite.
- No deletion of any world as disk-pressure relief. Report pressure, resolve it
  deliberately.
- No stopping `:3000` / `:8001`.
- No `pkill -f`. Use recorded pids or `preview_stack --world <world> down`.
- No writing to the existing 35-world destination copy in place.
