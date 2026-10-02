# Acceptance worlds → external drive: relocation runbook

**Status: NOT YET RUN.** The guard and interlock are in place; the data move
is deliberately paused because another session was still building worlds.

Target: move `backend/data/acceptance_worlds` (~69G, 37 worlds, 407k files,
10,993 internal symlinks) onto the Seagate drive, keeping the canonical path
working as a symlink. Reclaims ~69G on an internal disk at 96% capacity.

## Why a symlink and not a move

10,728 of the 10,993 internal symlinks are **absolute** and point back into the
canonical path, e.g.
`.../backend/data/acceptance_worlds/<world>/code/backend/<module>`.
A plain move leaves every one of them dangling. A symlink at the canonical path
keeps all of them resolving. This is not a preference — it is the requirement.

## Why the guard exists

Every launcher does `world.mkdir(parents=True, exist_ok=True)`. If the worlds
root is ever a plain local directory again, that mkdir succeeds against an empty
tree and the run "passes" against nothing. `core/world_storage_guard.py` runs
once in every launcher before any mkdir, and refuses:

- the expected volume is not mounted
- the volume name or UUID is not the configured one
- the worlds symlink is dangling
- the worlds root is a plain local directory while the config says drive-backed
- a maintenance lock is held

Config: `backend/config/world_storage.json` (outside the movable tree, because
`backend/data/` is gitignored *and* is the thing being moved).

## The interlock is a lock, not a flag

A lock file alone does not establish quiescence: a launcher can read "no
lock", pass preflight, be descheduled, and wake up after the window was
declared open. Nothing holds the check and the launch together. So the gate
is advisory locking:

- every launcher takes `flock(LOCK_SH)` after preflight and **holds it for its
  whole process lifetime** — i.e. across the entire check-to-launch window;
- `lock` takes `flock(LOCK_EX)` **blocking**, so it cannot complete until every
  registered launcher has exited.

`flock` is used rather than a flag because the kernel drops it when a process
dies: a SIGKILLed launcher cannot wedge a relocation shut, and there are no
stale locks to reap. Launchers take `LOCK_SH|LOCK_NB`, so one arriving during a
window is refused immediately with a readable reason instead of hanging. The
lock file is still written, both to carry the operator's reason string and to
keep refusing after the maintenance process exits.

```
python -m core.world_storage_guard lock --reason "..." --drain-timeout 60
```

`--drain-timeout 0` (the default) waits indefinitely. On timeout it refuses
and **names the PIDs still holding worlds open**:

```
MAINTENANCE WINDOW REFUSED
maintenance window CANNOT start: worlds are still in use.
  waited 60s for in-flight launchers to finish.
  still registered:
    pid 21108  launcher  scripts/orchestration_acceptance/run_isolated.py --name ...
```

Inspect at any time with `python -m core.world_storage_guard runners`.

## Pre-window

**Preserve destination-only evidence FIRST.** The stale copy holds 551.8M of
`atom-cycle-*.db.gz` snapshots that exist nowhere else. They are already
archived (see below), but re-check after any further copying:

```bash
venv314/bin/python scripts/orchestration_acceptance/worlds_delete_audit.py \
  --src ~/projects/atom/backend/data/acceptance_worlds \
  --dst "/Volumes/Seagate Portable Drive/projects/atom/backend/data/acceptance_worlds" \
  --evidence-archive "/Volumes/Seagate Portable Drive/worlds-evidence-archive"
```

Only proceed when the verdict is `no destination-only evidence found`.

Then:

```bash
cd ~/projects/atom/backend
venv314/bin/python -m core.world_storage_guard check          # must pass
venv314/bin/python -m core.world_storage_guard audit-symlinks --all
venv314/bin/python -m core.world_storage_guard runners         # expect none
../scripts/drive_status.sh
```

**Confirm no other session is building worlds.** Check for live holders:

```bash
lsof +D ~/projects/atom/backend/data/acceptance_worlds
```

If anything holds files there, stop and wait. Two sessions were active on
2026-09-27; a supervisor respawned killed processes within seconds, which is
why stopping processes alone is not a quiescing strategy.

## The window

Order matters: **lock first, then stop writers.** The lock is what stops new
launches; stopping writers is what releases the shared locks the window is
waiting on.

```bash
cd ~/projects/atom/backend

# 1. Interlock. Blocks NEW launches and waits for in-flight ones to drain.
venv314/bin/python -m core.world_storage_guard lock \
    --reason "relocating acceptance_worlds to external drive" --drain-timeout 120

# 2. Stop the writers the lock named. Re-check `runners` until empty —
#    a respawn here means something bypassed the interlock.
venv314/bin/python -m core.world_storage_guard runners
lsof +D ~/projects/atom/backend/data/acceptance_worlds

# 3. Sync. -a preserves the 10,993 symlinks. NEVER -L or cp -R: following
#    those links expands 69G into hundreds of GB.
rsync -a --delete \
  ~/projects/atom/backend/data/acceptance_worlds/ \
  "/Volumes/Seagate Portable Drive/projects/atom/backend/data/acceptance_worlds/"

# 4. Verify content — not just counts.
venv314/bin/python scripts/orchestration_acceptance/worlds_migration_verify.py \
  --src ~/projects/atom/backend/data/acceptance_worlds \
  --dst "/Volumes/Seagate Portable Drive/projects/atom/backend/data/acceptance_worlds"

# 5. Rename local -> rollback copy (a rename, so this costs no extra space),
#    then put the symlink in place.
cd ~/projects/atom/backend/data
mv acceptance_worlds acceptance_worlds.rollback-20260927
ln -s "/Volumes/Seagate Portable Drive/projects/atom/backend/data/acceptance_worlds" \
      acceptance_worlds

# 6. Flip the config so the guard REQUIRES the symlink from now on.
#    (edit layout: "local" -> "drive_symlink" in backend/config/world_storage.json)

# 7. Verify: db writes, workbook reads, restart.
venv314/bin/python -m core.world_storage_guard check

# 8. Release the interlock.
venv314/bin/python -m core.world_storage_guard release --yes
```

## Preserved evidence (done 2026-09-27)

All eight destination-only snapshots were copied to a timestamped archive on
the same volume but **outside** the sync target, and verified:

```
/Volumes/Seagate Portable Drive/worlds-evidence-archive/20260927-103625/
  MANIFEST.json        original path, bytes, sha256 per item
  MANIFEST.sha256      checksum of the manifest itself
  payload/             the 8 .db.gz files, original relative paths preserved
```

Total 578,587,540 bytes. Each file was re-hashed after copying and compared to
the source, and the archived copies were then re-verified a second time,
independently of the tool that wrote them. All 8 identical.

```bash
cd "/Volumes/Seagate Portable Drive/worlds-evidence-archive/20260927-103625"
shasum -a 256 -c MANIFEST.sha256
```

The archive tool refuses to write inside the rsync target (that copy would be
destroyed by the next `--delete`) and refuses to overwrite an existing
timestamped archive.

## Deleting the rollback copy is a SEPARATE, APPROVED step

`acceptance_worlds.rollback-20260927` is the only local copy. Deleting it is
what actually reclaims the ~69G. Do not remove it as part of the move, and do
not remove it in the same sitting as the smoke test.

```
SEPARATE STEP, AFTER the preview smoke test passes and a human approves:
  rm -rf ~/projects/atom/backend/data/acceptance_worlds.rollback-20260927
```

## `rsync --delete` and destination-only evidence

`rsync --delete` removes every destination-only path. Because the destination
is a stale snapshot, some of those are not junk — they are the last copy of a
record the source has since dropped. `worlds_delete_audit.py` classifies them
and **exits 1** while any unpreserved evidence remains:

- **droppable** — regenerable build output (`.next/`, `node_modules/`, `__pycache__/`)
- **review** — ambiguous; needs a human call
- **evidence** — would be the last copy; blocks

Bare `.json` counts as evidence deliberately: in this tree a JSON file is a
manifest, a catalog, a run descriptor, or a captured result. So do
`*.db.gz` / `*/backups/` — a gzip'd SQLite snapshot is not scratch, whatever
its extension. An earlier version of this classifier filed 551.8M of
`atom-cycle-*.db.gz` under "review" purely because of the `.gz` extension;
running it against the real trees is what caught that.

With `--evidence-archive`, an entry backed by a **re-verified** archived copy
moves to a PRESERVED bucket and stops blocking. Preservation is re-checked by
re-hashing the archived file against its manifest, and a manifest that fails
its own `MANIFEST.sha256` is ignored rather than believed.

## The limit of any startup check

A preflight describes one instant. It cannot protect a world that is already
running when the drive is unplugged, and nothing here tries to: the resulting
`EIO`/`ENOENT` is meant to propagate. Do not add retries or exception
swallowing around worlds I/O — a loud failure is the only signal that the
drive went away mid-run.

Operational consequence: **the drive must stay mounted for the whole time a
preview or acceptance run is live.**
