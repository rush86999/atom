# Pilot release restore — 2026-10-26

**Scope:** restore the recorded `c912375de` pilot into a durable release
location, using the existing live data/configuration. No repair-branch
deployment. No live DB reset.

## What was wrong

PID `54976` was listening on `:8001` but was not a healthy app:

- CWD reported `atom-named-document-routing/backend`; the source tree was gone
  and only `data/` remained.
- `/api/health` returned the HTTP error envelope
  `Internal server error — [Errno 2] No such file or directory`.
- A listening socket was therefore being mistaken for availability.

## Durable release

- Release path: `/Users/rushiparikh/projects/atom-releases/c912375de`
- Code: `git archive c912375de backend` (recorded commit
  `c912375de81b55465e61fe468bf0bc2b405fd206`)
- Live data/config linked, not copied or reset:
  - `backend/data` -> `/Users/rushiparikh/projects/atom/backend/data`
  - `backend/.env` -> live `.env`
  - `backend/venv314` -> live venv
  - live `config/` copied into the release `backend/config/`
  - `chat_sessions.json` copied to the release (live file not rewritten)
- Release-scoped BYOK config: `config/byok_config.release.json`; the
  `opencode-go`/`opencode` providers point at
  `https://opencode.ai/zen/go/v1` with `deepseek-v4.1-flash`. The live
  `byok_config.json` was not modified.
- Release identity: `/Users/rushiparikh/projects/atom-releases/c912375de/RELEASE_IDENTITY.json`.

## DB snapshot before stopping the stale process

`backend/data/backups/atom-pre-release-c912375de-20261026-073423.db.gz`
(141,868,095 bytes; uncompressed `.db` also retained). The snapshot opens and
contains 1,041 chat sessions, 5,464 messages, 3,754 ingested documents,
474 dataset entries and 9 agent-registry rows.

## Launch and health

- Stopped only PID `54976`; port 8001 released.
- Launched the release as PID `33426` on `:8001`.
- `/api/health`: `healthy`; database, redis, vector store `operational`;
  `cwd=/Users/rushiparikh/projects/atom-releases/c912375de/backend`;
  `database=.../backend/data/atom.db`; `byok_key_store=.../config/byok_keys.json`.
- The release has no `.git`, so the health `revision` is `unknown`; the
  archived commit is recorded in `RELEASE_IDENTITY.json`.

## Sign-in and sourced answer

- A fresh product user registered and signed in successfully:
  `pilot-smoke-95356c1106@example.com`, user
  `df807f58-359b-416c-a5eb-60cf53098ad6`, workspace
  `f1dd90d9-2f0c-4454-9b12-fe01a6ab154c`.
- Uploaded `pilot_release_smoke_c61b121f.txt` through the product
  (`/api/document-ingestion/upload`, HTTP 200, 126 chars indexed).
- Chat `ba8febe5-2ce0-4e03-b531-f2fae7907801` answered
  `CEDAR-55` and cited `pilot_release_smoke_c61b121f.txt`. The answer was
  served by the deterministic document path (`provider=structured`,
  `model=deterministic`), not by the model route.
- The admin bootstrap password in
  `backend/logs/bootstrap_admin_password.txt` **does not verify** against the
  `admin@example.com` bcrypt hash (checked read-only). Admin sign-in was not
  verified and the password was not reset.

## Remaining observations

- `:18100` is a different dev world at `68729ebe…`; `:8121` is the frozen
  worktree at `4b0bed79e…` and reports degraded. Neither was restarted.
- The `opencode-go` release route was staged but the deterministic smoke
  answer did not exercise model judgment.
- The saved-lookup repair branch is **not deployed** to this pilot.
