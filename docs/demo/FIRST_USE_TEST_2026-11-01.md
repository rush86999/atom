# Fresh-user first-use test — 2026-11-01

**Status: passed after successor-branch repairs.** The accepted tag and its
evidence manifest were not modified.

## Test setup

- Fresh git worktree at `8b1abd7e6` (successor branch), no `backend/venv`,
  no `frontend-nextjs/node_modules`, no `.env`, fresh `atom_dev.db`.
- macOS, Python 3.11, Node 20.19.
- Ports `8001`/`3001` were already occupied on this host, so the documented
  override path (`BACKEND_PORT=8101 FRONTEND_PORT=3101`) was used.
- Package caches were warm (pip/npm). A cold-network install was not measured.

## Measured journey

| Step | Result | Notes |
|---|---|---|
| Default `make setup` | refused in ~5 s | Default `python3` was 3.14; the bootstrap named the supported interpreter. Fixed by documenting `PYTHON=python3.11 make setup`. |
| `PYTHON=python3.11 make setup` | **102 s** | Fresh venv, backend deps, frontend deps, `.env`. |
| `make dev` with port override | **96 s** to backend + frontend health | First frontend compile included. |
| `make sample PORT=8101 FE_PORT=3101` | **17 s** | `status: passed`, result `232990.00`. |
| Browser login + first Assignments visit | **100 s** | Sample job visible on the first visit; the first Assignments data load takes several seconds on a cold dev compile and does not need a reload. |

**Measured complete journey (warm caches): ~5 min 15 s** across the four steps.
The failed default-Python attempt added ~5 s in the earlier exploratory run.
The **15-minute** figure remains the target for a cold network install, not a
measured guarantee.

## Confusing steps and failures found

1. **Default Python too new.** `make setup` refused 3.14 with a clear message,
   but the README/demo did not previously state the `PYTHON=python3.11`
   override. Fixed in README and demo.
2. **Port override broke CORS.** The backend started on `8101` without the
   `3101` frontend origin, so browser login showed “Unable to connect.” Fixed in
   `scripts/dev.sh` by setting `ADDITIONAL_ALLOWED_ORIGINS` and `ALLOWED_HOSTS`
   from the effective ports.
3. **Port override broke the client API base.** `.env.local` still baked
   `http://localhost:8001`, so browser data reads hit the wrong backend. Fixed
   by rewriting `NEXT_PUBLIC_API_URL` to the started backend port in `dev.sh`.
4. **Empty Assignments on first login.** The page mounted before the NextAuth
   bridge wrote `auth_token`, fetched unauthenticated, and stayed empty until a
   manual reload. Fixed in `AssignmentPanel` by re-running the three reads once
   the token appears.
5. **One-line `.env.local` aborted the launcher.** The rewrite used
   `grep -v` under `set -e`; a single-line file returned 1. Guarded with
   `|| true`.

## Evidence

- `docs/demo/evidence/first-use-assignments.png` — sample job visible under
  Assignments on the first visit.
- `/tmp/fresh-final-sample.log` (local run) — `status: passed`, `232990.00`.

## Post-journey focused check — launcher memory path

The measured journey above ran at `8b1abd7e6`. A later focused check at
`d8120737e` (current successor HEAD at the time) covers the launcher memory
path that the journey did not exercise:

- Finding: the launcher exported `LANCEDB_URI` but workspace handlers read
  `LANCEDB_URI_BASE`, falling back to `./data/atom_memory` and anchoring to
  `backend/` — the repository-shared memory root.
- Fix: both variables point at `<world>/data/atom_memory`. No shared memory was
  copied, deleted or migrated.
- Verification on fresh world `first_use_smoke_20261101`, backend 8086 /
  frontend 3146: the log resolves to
  `<world>/data/atom_memory/default_shared`; zero repository-shared path
  occurrences.
- Same check: login → Assignments on the first visit loads without a reload
  (Demo Assistant selectable, agents page reachable, no page errors).

Evidence: `docs/acceptance/evidence/first_use_smoke_20261101/`. This is a
focused launcher/first-use check after the measured journey; the full install
and sample job were not repeated after the memory-path fix.

## Remaining honest limitations

- Cold-cache install time is not measured; 15 minutes remains a target.
- A clean host with free `8001`/`3001` avoids the override path, but the
  override path now works through the documented commands.
- Model-backed features still require a configured provider; the sample job is
  deterministic and does not prove model quality.
- No live send or connector write is performed by this test.
