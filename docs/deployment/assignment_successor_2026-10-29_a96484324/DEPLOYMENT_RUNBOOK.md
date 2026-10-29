# Assignment successor deployment runbook — a96484324 candidate

Status: **successor candidate frozen at a96484324; packaged smoke and isolated
rehearsal passed (see REHEARSAL_2026-10-29-a96484324.md); deployment is not
authorized.**

## Exact release identity

| Item | Value |
|---|---|
| Deployable product commit | `a9648432495f4f75f59bf4667cac3cb997d7f229` |
| Release tag | `assignment-successor-2026-10-29-a96484324` |
| Tested runtime | `a96484324` |
| Product tree paths | `backend/`, `frontend-nextjs/` |
| Product tree SHA-256 | `937d100838300c8ec703f5c8ee164f029acf4ecbe64d6a823bd994fa9070d8e6` |

`a96484324` is the frozen successor candidate on top of the previous
`assignment-successor-2026-10-29` release (`901e5d773`). It adds mapping
rejection/restart recovery and the complete authority controls while retaining
the prior confirmation, unit-authority, correction and draft-only send policy.
The previous release tag and evidence remain untouched. The `backend/` +
`frontend-nextjs/` tree checksum is recorded and rechecked by preflight. The
deployment kit is an overlay and is checksummed separately, so `/api/health`
always reports the product commit actually loaded.

## Release scope

- One declared operator (`admin@example.com`), one workstation.
- One backend worker process; one worker process per assignment is the verified
  topology. Do not add `--workers`.
- `ATOM_DEPLOYMENT_AUDIENCE=single_user`; multi-user is refused.
- Microsoft client configuration is required for live refresh; the packaged
  smoke did not exercise a provider and no credential was changed.
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
python scripts/deployment/assignment_successor_2026-10-29_a96484324/prepare_release.py \
  --repo <repo> \
  --root /Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-29-a96484324 \
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
- `ATOM_ASSIGNMENT_ALLOW_LIVE_SEND=0`;
- `ATOM_EMAIL_SEND_DISABLED=1` (trusted server-side draft-only gate);
- `ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT` unset;
- `ENABLE_SCHEDULER=false`, `ENABLE_INGESTION_SYNC=false`;
- DeepSeek-only selected provider policy;
- `ALLOWED_ORIGINS` for the declared frontend origin.

`config/secrets.env` must be supplied by the owner with the Microsoft client
id/secret (and any provider credential) in mode 600. `preflight` checks presence
only and never prints values.

## Packaged mapping + taught-assignment smoke

After `prepare_release.py` and a rehearsal `start`, run the packaged smoke
against the same authenticated API:

```bash
python .../smoke_mapping_taught.py \
  --api-base http://127.0.0.1:8071 \
  --password-file <root>/config/rehearsal_admin_password \
  --agent-id map-agent \
  --existing-objective "Mapping B sum Price" \
  --expected-existing-sum 35.00 \
  --dataset-name <seeded workbook-B dataset> \
  --source outlook --external-id fixture-b \
  --source-version <seeded source version> --sheet Sheet1 \
  --expected-mapping-sum 35.00 \
  --expected-mapping-revision 3 \
  --out <root>/run/mapping-taught-smoke.json
```

It reopens the existing taught assignment and artifact, creates one new
workbook-B mapping assignment, confirms `Amount`, verifies `35.00 USD` and one
accepted mapping update (revision 2 -> 3 when seeded from the tested workbook-B
world), checks the selected DeepSeek provider policy, and proves an outbound
assignment is refused with HTTP 422 without creating a run. Use
`--verify-snapshot` after a scoped restart to compare the same assignment,
result, artifact and source provenance.

## Preflight, backup, deployment

```bash
python .../release_tool.py --root <root> preflight --ignore-running-ports
python .../release_tool.py --root <root> backup --label predeploy
python .../release_tool.py --root <root> stop
python .../release_tool.py --root <root> preflight
python .../release_tool.py --root <root> start
```

`start` refuses without a production `config/APPROVED` JSON record. The record
must contain `approver`, `approved_at`, `release_tag`, `product_commit`,
`product_tree_sha256`, `scope` (`single_user`) and `mode` (`production`), all
matching `RELEASE_IDENTITY.json`. A rehearsal record is accepted only with
`--rehearsal` and can never authorize production. `start` launches one uvicorn
process and the prebuilt frontend, then asserts
`/api/health.identity.revision` equals the release commit and `dirty=false`.
A startup failure stops only the recorded PIDs.

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

`deploy_release.sh` arms recovery **before** the first potentially disruptive
operation. It tracks shutdown started, previous service stopped, candidate
started, deployment committed and rollback active. Pre-shutdown failures leave
the running service alone. After shutdown, any failure (partial stop, unexpected
exit, candidate start, authentication, assignment/receipt verification, restart
or receipt publication) attempts a verified code rollback. Rollback failure is
logged and written to `run/deployment_failure.json`; it is never hidden behind
a success exit. The guard remains armed until final health checks and atomic
receipt publication succeed. The database is never restored automatically.

The transaction runs normal auth, the persistence check, a **fresh read-only
assignment** through retrieval → calculation → grounded artifact, a scoped
restart, then reopens both the persistence assignment and the fresh result.
`smoke_assignment.py` rejects non-completed status, non-applied required
deliverables, missing/altered artifact bytes, absent provenance and missing
expected content.

Production and rehearsal arguments are constructed once; `--rehearsal` is
appended only in rehearsal mode. Production approval is validated against the
exact tag, commit and product-tree checksum before backup or shutdown.

## Outbound scope

For this initial release, email is **draft-and-approval**, not send. The
controlled outbox is not enabled in production config. The server-side
`ATOM_EMAIL_SEND_DISABLED=1` gate blocks canvas/Outlook transports before any
provider call, and assignment planning refuses `email.send_outlook` unless
`ATOM_ASSIGNMENT_ALLOW_LIVE_SEND=1`; neither client fields nor ordinary approval
can override this. If production sending is required for launch, it needs a
separate authorization and one real-provider test covering an approved
recipient, exact body and attachment, provider receipt, reconciliation and
restart/no-duplicate checks. Do not send without that authorization.

## Remaining blocker

Deployment is blocked only on owner authorization. The precise action is:

1. Review this runbook, `RELEASE_IDENTITY.json` and the preflight/deployment
   receipts.
2. Create `<root>/config/APPROVED` as JSON containing `approver`,
   `approved_at`, `release_tag` `assignment-successor-2026-10-29-a96484324`,
   `product_commit` `a9648432495f4f75f59bf4667cac3cb997d7f229`,
   `product_tree_sha256`
   `937d100838300c8ec703f5c8ee164f029acf4ecbe64d6a823bd994fa9070d8e6`,
   `scope` `single_user` and `mode` `production`. File existence alone is not
   approval; every field is checked by `approval-check` before backup/shutdown.
3. Supply the pilot password file path and run `deploy_release.sh` without
   `--rehearsal`.

No Zoho repair, model change, real email send, source writeback or deployment is
performed by this package.
