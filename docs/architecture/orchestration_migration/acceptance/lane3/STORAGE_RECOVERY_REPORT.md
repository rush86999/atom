# Storage recovery and preview restore — 2026-09-27

**This document is about recovery only.** It contains no acceptance result and no
readiness claim. Acceptance evidence lives in `browser_final/`, `streaming*/`,
`CASE_ACCOUNTING_C00_C26.md` and is unchanged by anything here.

## 1. What was wrong, in order

| When | What | Who |
|---|---|---|
| ~13:20 | Both preview stacks were killed by `pkill -f pytest`. The pattern matched the invoking shell's own command line as well as the target, so the process group went with it. | **Lane 3's error** |
| 13:27:25 | A maintenance interlock was taken: `relocating acceptance_worlds to external drive`, holder pid 10313, `drained: false`. | storage-guard writer |
| after | That holder died, orphaning the lock. Every launcher then refused. | — |

The two are independent. Even with the previews still up, the orphaned lock
would have blocked every launch.

## 2. Checks performed before touching anything

| Check | Result |
|---|---|
| Maintenance holder process | pid 10313 **gone** (`ps`) |
| Registry lock (the guard's atomic gate) | file present, **0 bytes, nobody holds it** (`lsof`) — free |
| Relocation / copy process | none. `ps` matched only Google Drive's Finder extension, a Codex renderer and macOS agents |
| Worlds root | still a real **local** directory, mtime Sep 26 22:59, 37 worlds, 70G |
| Storage config | still `layout: "local"` — the switch never happened |
| Destination on the drive | 35 worlds / 55G, mtime **Sep 26 21:34** — *yesterday's* copy, already behind local |
| Both databases | intact on disk (preview_v1 408MB, candidate_fix1 513MB) |

Nothing had been moved. The holder died with `drained: false`.

## 3. Evidence preserved before the change

Copied to `storage_recovery_20260927/`:

- `maintenance.lock.asfound` — the lock record exactly as found, including
  `acquired_at_iso`, `pid 10313`, `drained: false`, and the reason string
- `world_storage.json.asfound` — the storage config, verified **byte-identical**
  to the live file after the release (diff clean)

## 4. How the lock was released

The guard has a supported release path, and the guard's own refusal message
names it:

```
python -m core.world_storage_guard release --yes
```

`--yes` is a required safety flag, so an accidental release is not possible.
**The lock record was not edited by hand** — the supported CLI removed the file
and released the flock. This is the only supported mechanism that exists, so no
proposed manual change was needed.

`world_storage_guard check` then reports `world storage preflight OK` /
`no maintenance lock`.

## 5. What was deliberately NOT done

- No world was moved, copied, mirrored or deleted.
- The external copy on the Seagate drive was **not** touched in any way.
- `layout` stayed `local`; local worlds remain authoritative.
- No `git add -A`, no reset, no stash, no history rewrite.
- No broad pattern kill was used again. Process control is by recorded PID or
  `preview_stack.py --world <world> down`.

## 6. Restore

Both previews were relaunched with `preview_stack.py up --reuse-run` against
their **recorded** run directories and ports, so no world was rebuilt and no new
candidate identity was minted.

`preview_v1` was restored first. It is pointed at its recorded legacy farm
(`frontend-nextjs/.preview-instance`, distDir `.next-preview`) via `--farm`,
because that is the farm its recorded frontend was built in.

| | `preview_v1` (preserved) | `candidate_fix1` |
|---|---|---|
| Frontend | **http://localhost:3101** (pid 18307) | **http://localhost:3102** (pid 19447) |
| Backend | http://127.0.0.1:8051 (pid 18184) | http://127.0.0.1:8071 (pid 19275) |
| Run dir | `run-75c6ae75fb08` | `run-7325767729a0` |
| Open DB | `preview_v1/runs/run-75c6ae75fb08/data/atom.db` | `candidate_fix1/runs/run-7325767729a0/data/atom.db` |
| Not holding the live dev DB | confirmed | confirmed |
| `verify` | **10/10** | **10/10** |
| Streaming | `ATOM_CHAT_STREAMING='true'` — **effective** | `ATOM_CHAT_STREAMING='true'` — **effective** |
| Frontend intent | `requested` | `requested` |

`verify` proves process identity, cwd, the database the process actually has
**open** (via `lsof`), that it is *not* holding `backend/data/atom.db`, that the
frontend answers, and that its compiled client bundle references its own backend
origin rather than the other preview's.

### Two consequences worth stating

1. **`:3101` now has working streaming.** It was launched with
   `ATOM_CHAT_STREAMING=1`, which the orchestrator does not honour, so its
   streaming had never run. Relaunching through the fixed launcher gives it
   `=true`. That is a fix, not a regression, but it *is* a behaviour change from
   its recorded configuration.
2. **`:3101` login was set.** Its admin password was the developer's original
   and had never been set — the earlier browser run recorded
   `login.attempted: false` because it drove a seeded session token. A preview
   that answers `/health` but rejects every login is not usable, so the same
   guarded, disposable-world-only password set that `preview_login.py` performs
   was applied. Credentials: `admin@example.com` / `preview-only-local-2026`
   (value never logged). Confirmed working: HTTP 200, 225-char bearer token, and
   a real chat turn returned `success: true`.

Both were confirmed with a **live turn**, not just structural checks:
`preview_v1` answered a real question on execution `e33e817e`, and the recovered
candidate streamed 23 `chat_token` frames with the concatenated text
byte-identical to the delivered answer (16/16 streaming checks).

The user's own `:3000` / `:8001` were never touched at any point.

## 7. Process control going forward

```
# stop (supported, by world)
backend/venv314/bin/python backend/scripts/orchestration_acceptance/preview_stack.py \
  --world preview_v1 down
backend/venv314/bin/python backend/scripts/orchestration_acceptance/preview_stack.py \
  --world candidate_fix1 down
```

Recorded PIDs at the time of writing — the launch **parent**, which is what
`preview_stack down` signals:

| World | Backend | Frontend parent | Next server actually holding the port |
|---|---|---|---|
| `preview_v1` | **18184** | **18307** | 18408 |
| `candidate_fix1` | **19275** | **19447** | 19455 |

Next 16 forks a `next-server` child that owns the listening socket, so the
listening PID is not the PID in `preview_stack.json` and not the one to signal —
signal the parent. All four go stale on restart; read current values from
`backend/data/acceptance_worlds/<world>/preview_stack.json` rather than trusting
this table.

Never use `pkill -f <pattern>` here. The pattern matches the invoking shell's own
command line, so it kills the caller. That is exactly how both previews went
down.

## 8. Open risk left behind

The orphaned lock was not a one-off. `release_maintenance_lock()` unlinks the
file unconditionally and never checks whether the recorded pid is still alive,
and the lock message offers `release` with no mention of verifying the holder
first. So any agent that dies mid-relocation leaves every launcher blocked until
a human notices. Two cheap hardening options, **not applied** because they touch
the storage-guard writer's file and its behaviour is a deliberate design choice:

- refuse `release` when the recorded pid is alive, and require `--force` to
  override;
- have the refusal message say "if the holder is gone, release it" and name the
  verification step.

Also unresolved and out of scope here: `source_id` moved for both worlds
(`d45d564abdfc`, `01b47729575c`) because it digests the live working tree rather
than the loaded code. Loaded module hashes are the real identity.
