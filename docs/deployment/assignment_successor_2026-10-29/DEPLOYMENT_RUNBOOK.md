# Assignment successor deployment runbook — 2026-10-29

Status: **release candidate prepared; isolated rehearsal passed; deployment is
not authorized.**

## Exact release identity

| Item | Value |
|---|---|
| Deployable product commit | `ef95ceb3194ec92c51e64941d7bb364c0b8b0e75` |
| Release tag | `assignment-successor-2026-10-29` |
| Tested live runtime | `001f93472` |
| Product tree paths | `backend/`, `frontend-nextjs/` |
| Product tree SHA-256 | `12060bee618e7a58a98324f682d39077c144c19a6fb7d22d77de8179237dbb9e` |

`ef95ceb31` is the freeze commit `afa932756` plus three release-scope
corrections found during isolated packaging: the durable-assignment route is
mapped to the existing `activity` capability (so `/assignments` is reachable in
the core surface), normal sign-out now calls the existing backend logout
endpoint so the old JWT is revoked, and the deployment kit is added. Product
code is otherwise the same as the live-tested `001f93472`; the `backend/` +
`frontend-nextjs/` tree checksum is recorded and rechecked by preflight. The
deployment kit is an overlay and is checksummed separately, so `/api/health`
always reports the product commit actually loaded.

The stale instruction naming `9a89471cc` is historical: that commit removed
preview symlinks and predates the teaching/OAuth integration, live fixes and
release profile correction. Do not deploy it.

## Release scope

- One declared operator (`admin@example.com`), one workstation.
- One backend worker process; one worker process per assignment is the verified
  topology. Do not add `--workers`.
- `ATOM_DEPLOYMENT_AUDIENCE=single_user`; multi-user is refused.
- Microsoft refresh configuration present; token renewal uses the normal
  resolver. No credentials are printed.
- Assignment retrieval and artifact creation/reopen are supported.
- **Outbound is draft-and-approval only.** Controlled-outbox evidence proves
  orchestration, approval and duplicate prevention, not production delivery.
  No production send is authorized by this release.

## Package layout

```
<root>/
  RELEASE_IDENTITY.json
  current -> releases/<commit>
  previous -> releases/<prior commit>
  releases/<commit>/{app,frontend,scripts,docs}
  config/{env.release,secrets.env,APPROVED}
  data/{atom.db,office/,sheet_datasets/,email_attachments/,atom_memory/}
  backups/<label>-<timestamp>/
  logs/
  run/
```

`releases/<commit>/app` is a shallow git clone at the release tag, so
`/api/health` reports the frozen revision with `dirty=false`. `config/secrets.env`
is mode 600 and is never committed. `data/` is durable and remains outside the
release directory; code rollback never rewrites it.

## Build the package

```bash
python scripts/deployment/assignment_successor_2026-10-29/prepare_release.py \
  --repo <repo> \
  --root /Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-29 \
  --api-origin http://127.0.0.1:8071 \
  --node-modules <frontend node_modules>
```

The script verifies the tag resolves to the exact commit, the product tree
checksum matches the tested tree, the app is clean, builds the standalone
frontend, copies the kit/docs overlay and writes `RELEASE_IDENTITY.json`.
It does not copy production data unless `--seed-data-from` is explicitly used
for an isolated rehearsal.

## Production configuration

`config/env.release` is generated with:

- `ATOM_DATA_DIR`, `DATABASE_URL`, `ATOM_OFFICE_DIR`,
  `ATOM_ASSIGNMENT_OUTPUT_DIR`, `ATOM_EMAIL_ATTACHMENT_DIR` under the durable
  root;
- `ATOM_DEPLOYMENT_AUDIENCE=single_user`, `ATOM_PILOT_USER_EMAIL=admin@example.com`;
- `ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS=0`;
- `ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT` unset;
- `ENABLE_SCHEDULER=false`, `ENABLE_INGESTION_SYNC=false`;
- DeepSeek-only selected provider policy;
- `ALLOWED_ORIGINS` for the declared frontend origin.

`config/secrets.env` must be supplied by the owner with the Microsoft client
id/secret (and any provider credential) in mode 600. `preflight` checks presence
only and never prints values.

## Preflight, backup, deployment

```bash
python .../release_tool.py --root <root> preflight --ignore-running-ports
python .../release_tool.py --root <root> backup --label predeploy
python .../release_tool.py --root <root> stop
python .../release_tool.py --root <root> preflight
python .../release_tool.py --root <root> start
```

`start` refuses without `config/APPROVED`, starts one uvicorn process and the
prebuilt frontend, then asserts `/api/health.identity.revision` equals the
release commit and `dirty=false`. A startup failure stops only the recorded
PIDs.

`backup` uses SQLite's backup API, runs `PRAGMA integrity_check`, records row
counts and SHA-256 of every file. `atom_memory` is excluded by default because
it is large; pass `--include-memory` when a full vector-store snapshot is
required. A backup is never restored automatically.

## Normal authentication smoke

`smoke_auth.py` starts a fresh browser context with no injected session or
cookies. It uses the real `/login` form, verifies dashboard/workspace access,
opens an existing completed assignment and its listed artifact, signs out via
`dashboard-logout-button`, confirms the old token is refused with 401 and local
storage is cleared, then signs in again through the same form and reopens the
assignment list.

The owner supplies `ATOM_SMOKE_PASSWORD_FILE` (mode 600). The isolated rehearsal
uses a scratch database copy and a generated rehearsal password; never reuse
that against production.

## Representative assignment and restart

`smoke_assignment.py` logs in normally, reads one completed assignment from
`/api/assignments?include_terminal=true`, verifies `completed`, the document
artifact exists, its SHA-256, and the expected result text. After a scoped
stop/start, the same command with `--compare-to` must show identical run id,
assignment id, status, plan revision, artifact path/hash and source versions.
No new assignment, send, or outbox record is created.

## Reversible deployment transaction

`deploy_release.sh` performs preflight, a fresh verified backup, scoped stop,
start, auth smoke, representative assignment, restart agreement, and writes
`run/deployment_receipt.json`. On any failure after start it invokes
`release_tool.py rollback`: stop, flip `current` back to `previous`, start and
verify health. It never restores the database and never overwrites newer user
data. A manual rollback is the same subcommand.

## Outbound scope

For this initial release, email is **draft-and-approval**, not send. The
controlled outbox is not enabled in production config. If production sending is
required for launch, it needs a separate authorization and one real-provider
test covering an approved recipient, exact body and attachment, provider
receipt, reconciliation and restart/no-duplicate checks. Do not send without
that authorization.

## Remaining blocker

Deployment is blocked only on owner authorization. The precise action is:

1. Review this runbook, `RELEASE_IDENTITY.json` and the preflight/deployment
   receipts.
2. Create `<root>/config/APPROVED` containing the approver, date, release tag
   `assignment-successor-2026-10-29`, product commit
   `ef95ceb3194ec92c51e64941d7bb364c0b8b0e75`, and the declared single-user
   scope.
3. Supply the pilot password file path and run `deploy_release.sh` without
   `--rehearsal`.

No Zoho repair, model change, real email send, source writeback or deployment is
performed by this package.
