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
| `PYTHON=python3.11 make setup` | **97 s** | Fresh venv, backend deps, frontend deps, `.env`. |
| `make dev` with port override | **95 s** to backend + frontend health | First frontend compile included. |
| `make sample PORT=8101 FE_PORT=3101` | **16 s** | `status: passed`, result `232990.00`. |
| Browser login + first Assignments visit | **54 s** | Sample job visible on the first visit after the token fix. |

**Measured complete journey (warm caches): ~4 min 22 s**, including the failed
default-Python attempt. The **15-minute** figure remains the target for a cold
network install, not a measured guarantee.

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

## Remaining honest limitations

- Cold-cache install time is not measured; 15 minutes remains a target.
- A clean host with free `8001`/`3001` avoids the override path, but the
  override path now works through the documented commands.
- Model-backed features still require a configured provider; the sample job is
  deterministic and does not prove model quality.
- No live send or connector write is performed by this test.
