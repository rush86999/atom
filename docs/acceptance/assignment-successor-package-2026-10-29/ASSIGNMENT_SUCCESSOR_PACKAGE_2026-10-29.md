# Assignment successor release package — 2026-10-29

Status: **integrated, clean-source verified, not deployed.** Live OneDrive
start and live changed-source refresh remain blocked by owner
configuration/authorization, so this is not a claim that the live-connected
exit condition is closed.

## Exact source

| Item | Commit |
|---|---|
| Candidate source | `02822343d` |
| Runtime-tested source | `9a89471cc0f307130c733bd4485d689e6e83b35c` |
| Integrated teaching/OAuth runtime | `1d5e8d780` |
| Review repairs | `294fdf0ec` |
| Bounded taught job | `de25c5148` |
| Preserved connected guided candidate | `40b3367d9` |
| Preserved start boundary | `44b62a6bb` |
| Preserved correction pass | `322981bcc` |
| Preserved executor freeze | `efc4bc9d5` |

Branch: `whole-app/successor-f5f`.

The candidate is self-contained. The former owner teaching working-tree delta
(artifact-teaching store, lesson fields/routes, renderer support, OAuth
preflight and UI callers) is committed in `1d5e8d780`. The tracked
`.preview-instance` absolute symlinks were removed in `9a89471cc`.

Source manifest:
`docs/acceptance/assignment-successor-package-2026-10-29/source_manifest.json`.
It lists the required backend runtime, frontend components, configuration
template, acceptance harnesses and tests, with SHA256 identities. There are no
schema migrations and no checked-in artifact templates for this slice.

## Clean-source verification

Clean worktree from `02822343d`:
`/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-clean-02822343d`

The runtime-tested commit is `9a89471cc`; `9a89471cc..02822343d` is docs-only, so
the backend/frontend runtime bytes are identical.

Verified:

- clean `git status`; no borrowed working-tree files;
- `main_api_app` imports as `ATOM API`;
- artifact teaching normalizes the taught calculation keys;
- no `.env`, database, cache or `node_modules` in the clean worktree;
- no absolute symlinks; only four relative internal source symlinks;
- no credential values in the candidate diff;
- no live-data link.

Evidence:
`docs/acceptance/evidence/durable_assignment_20261029/clean-source/verification.json`.

## Supported claims

- Explicit advanced-form assignment setup remains supported.
- Guided scratch-catalog start with real Parquet rows, typed binding, full-frame
  sum/count, grounded artifact, controlled approval/outbox and restart/reopen.
- Supervisor-assigned connected work rechecks the requester’s active grant.
- Revoked access between start and a resumed read stops the read.
- Multi-source artifacts include evidence from every source row set; required
  calculation results must all appear.
- One bounded taught scalar method combining workbook retrieval, document/email
  evidence, a missing-information wait, grounded document and formatted draft,
  correction and restart.

## Not claimed

- Live OneDrive guided start against the previously ingested workbook.
- Live changed-byte refresh.
- Arbitrary taught methods, arbitrary multi-row calculations or arbitrary
  multi-source assignments.
- Live email send, deployment, credential change or source writeback.

## Claim boundaries

| Claim | Status |
|---|---|
| Scratch connected-data acceptance | Verified (`85.00`, `3`, reopened) |
| Bounded taught-method acceptance | Verified (`24.00 USD`, two sources, draft, reopened) |
| Live connected acceptance | Not run; authorization requested |
| Changed-source freshness | Not run; authorization requested |
| Live outbound acceptance | Not claimed; controlled outbox only |
| Deployment | Not performed |

Operational authorization:
`docs/acceptance/OPERATIONAL_AUTHORIZATION_2026-10-29.md` and its JSON companion.

See `docs/acceptance/ASSIGNMENT_START_2026-10-29.md`,
`docs/acceptance/ASSIGNMENT_REVIEW_2026-10-29.md` and
`docs/acceptance/LIVE_CONNECTED_GATE_2026-10-29.md`.

## Configuration

Production:

- `ATOM_DATA_DIR` and `ATOM_OFFICE_DIR` point at owned storage;
- `ATOM_ASSIGNMENT_OUTPUT_DIR` optional under office storage;
- `ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS` unset/0;
- `ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT` unset;
- Microsoft client id/secret present before any live refresh.

Test-only:

- `ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS=1` only in isolated fixture tests;
- controlled outbox only with `ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT=1`.

Current live preflight is `configured=false`, missing
`MICROSOFT_CLIENT_ID` and `MICROSOFT_CLIENT_SECRET`; the stored grant is not
treated as revoked.

## Verification commands

```bash
cd backend
TESTING=1 ATOM_DATA_DIR=<scratch> pytest \
  tests/test_assignment_routes.py \
  tests/test_assignment_resource_boundary.py \
  tests/test_assignment_executor.py \
  tests/test_assignment_launcher_guard.py \
  tests/test_fingerprint_identity.py \
  tests/test_operation_binding.py \
  tests/test_goal_run_events.py \
  tests/test_hitl_approvals_journey.py \
  tests/test_hitl_resume.py \
  tests/test_artifact_teaching_context.py -q

python scripts/assignment_connected_acceptance.py
```

Browser specs:

```bash
cd frontend-nextjs
npx playwright test e2e/assignment-guided.spec.ts --workers=1
npx playwright test e2e/assignment-guided-reopen.spec.ts --workers=1
npx playwright test e2e/assignment-durable.spec.ts --workers=1
npx playwright test e2e/assignment-durable-reopen.spec.ts --workers=1
```

## Verification results

- Clean-source focused backend: 134 passed
- Clean-source bounded taught job: 1 passed
- Clean-source connected scratch: `85.00`, `3`, both reopened
- Assignment component: 3 passed
- Guided browser start/reload: 1 passed
- Guided browser after restart: 1 passed
- Explicit browser start/reload: 1 passed
- Explicit browser after restart: 1 passed
- TypeScript: clean
- Frontend source: byte-identical to the previously tested working tree; no
  separate clean `node_modules` install was performed

## Rollout

1. Deploy only from clean source commit `9a89471cc`; do not copy local
   working-tree files.
2. Run the focused suite and AssignmentPanel tests on the release source.
3. Run the four Playwright specs in isolated scratch worlds.
4. Run the connected scratch acceptance and bounded taught job.
5. Keep live-connected and changed-source gates closed until the owner supplies
   client configuration and the exact disposable-source authorization.
6. Do not enable controlled transport or internal paths in production.

## Rollback

### Code rollback

Reviewed target: `294fdf0ec`. It preserves the security/resource repairs but
drops the bounded taught-method/integration delta. Do not roll back below
`294fdf0ec` without re-accepting the findings in
`ASSIGNMENT_REVIEW_2026-10-29.md`.

### Disabling assignments

No assignment-specific kill switch exists. Operationally deny
`/api/assignments*` at the edge and hide the Assignments tab. Do **not** delete
GoalRun/task_lifecycle rows or artifacts; leave them durable for later resume.
A code rollback should retain the assignment routes in a disabled/unmounted
state only if the edge cannot enforce the denial.

### Database/artifact compatibility

No schema migration was added. Assignment state is additive JSON in the
existing GoalRun `task_lifecycle` record; artifacts are files under the owned
output root. Older code must not delete durable rows or artifacts. Newer plan
fields are additive; do not rewrite them during rollback.

### Data restore

Use the existing `core.db_safety` snapshots only after demonstrated corruption.
Restore to a copy first, verify row counts, assignment identities, source
versions and artifact hashes, then require owner approval before replacing the
live database. Never automatically overwrite newer user work with an older
database.

## Remaining blockers

- Microsoft client configuration absent.
- Live OneDrive guided start not run.
- Disposable changed-source authorization not granted.

The combined operational authorization request is
`docs/acceptance/OPERATIONAL_AUTHORIZATION_2026-10-29.md`.
