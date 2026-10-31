# Launcher safety evidence

The launcher (`scripts/acceptance/launch_integrated_local_candidate.sh`) was
exercised on an isolated world under the configured acceptance-worlds root on
ports 8072/3132. The existing service on 8001 was untouched.

## Refusals before any write

- Protected repo path (`backend/data`) -> `REFUSED`, exit 2, no world created.
- Repo root -> `REFUSED`, exit 2.
- Existing non-empty world without `.atom-integrated-world.json` -> `REFUSED`,
  exit 2, no write.
- Occupied frontend port -> `REFUSED`, exit 2, no world created.
- Reusing a world with a live backend PID -> `REFUSED`, exit 2.

## Successful start and exact identity

- `core.world_storage_guard check` passed.
- `storage_policy space` passed.
- Backend `/health` was HTTP-successful and reported the exact child PID,
  backend CWD, database path, port, source ID and instance ID.
- Frontend `/api/health` reported `service=atom-frontend`, `status=healthy`.
- `.atom-secret` and `.atom-integrated-world.json` were mode 0600.
- The backend and frontend PIDs were the ones started by this invocation.

## Failure cleanup

A competing listener was started on the frontend port after validation. The
launcher started the backend, failed to bind the frontend, and stopped only the
backend PID it started; the competing listener remained alive. This proves the
trap does not kill an unrelated process or the existing 8001 service.

## Preserved limitation

The successful run used source ID `d57bb66f6796-dirty…` because the launcher
changes were not yet committed at test time. The final code/evidence commit is
`16c113880`; the identity check is the same code path.
