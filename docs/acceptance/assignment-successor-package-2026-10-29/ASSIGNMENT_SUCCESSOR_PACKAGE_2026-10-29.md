# Assignment successor release package — 2026-10-29

Status: **integrated, clean-source verified, live gates passed, not deployed.**
The approved Microsoft configuration was restored and token resolution is
valid. The named Zoho WorkDrive workbook remains inaccessible and its failed
gate is preserved unchanged; the live gates use an explicitly predeclared
Microsoft Outlook attachment and a separate disposable OneDrive workbook.
Live connected retrieval, controlled approval/outbox, restart/reopen and a
changed-byte refresh all passed. Nothing was sent and nothing was deployed.

## Exact source

| Item | Commit |
|---|---|
| Candidate source | `058e38ddb` |
| Runtime-tested source | `e4c11c354` |
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

Clean worktree from `058e38ddb`:
`/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-clean-058e38ddb`

The runtime-tested commit is `e4c11c354`; `058e38ddb` is that runtime plus
live-boundary evidence/docs. Clean-source focused, bounded and connected-scratch
tests pass.

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
- **Live connected Microsoft source:** the predeclared Outlook attachment
  `HARSLE press brake stock price list.xlsx` (catalog
  `00399616-42f7-4f7d-8867-822752b15a46`, sheet `库存产品`, `Price`, 8 rows)
  was fetched from Microsoft Graph with the normal token resolver. Its SHA-1
  `e0a7fb8a1b4757b7f6bef882b19cc4588d66246e` matches the active catalog
  version and its actual values sum to `216700`. The guided browser run
  calculated `216700.00`, produced a grounded document, was approved through
  the controlled outbox, and reopened after a backend restart.
- **Live changed-byte refresh:** one separately authorized disposable OneDrive
  workbook changed from `50.00` to `60.00`. The old version binding was refused
  with `stale_source_version`; the new SHA-1
  `54342175548dc1f4272d2a50a7c302a6b2a990a4` was ingested as 2/2 sheets with
  formula sidecar `D2/D3 = Inputs!B*Inputs!C`, calculated `60.00` across two
  rows, produced a fresh artifact, and reopened after restart.
- **Controlled approval/outbox:** exercised with a local JSONL outbox; no
  production email transport was enabled.

## Not claimed

- Live OneDrive guided start against the originally named Zoho
  `Consolidated Price List 2019.xlsx`; that workbook remains inaccessible.
- Normal login-form acceptance. The browser used a real signed user session;
  the login form itself was not exercised.
- Arbitrary taught methods, arbitrary multi-row calculations or arbitrary
  multi-source assignments.
- Live email send, deployment, credential change or source writeback.

## Claim boundaries

| Claim | Status |
|---|---|
| Scratch connected-data acceptance | Verified (`85.00`, `3`, reopened) |
| Bounded taught-method acceptance | Verified (`24.00 USD`, two sources, draft, reopened) |
| Live connected acceptance | Verified: Outlook attachment, direct Graph hash match, `216700.00`, browser approved/reopened |
| Changed-source freshness | Verified: disposable OneDrive workbook `50.00` → `60.00`, stale old version refused |
| Live outbound acceptance | Controlled outbox only; no production send |
| Deployment | Not performed |
| Named Zoho workbook | Not revalidated; failed gate preserved unchanged |

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

Current live preflight is `configured=true`; the stored Microsoft grant resolves
`state=valid` with a token available and no reconnect required. Expired access
is refused as `source_access_expired`, never relabeled revoked consent.

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

- Clean-source focused backend: 135 passed (historical clean-source commit)
- Current live-fix focused backend: 88 passed
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

## Live execution record

- Microsoft client configuration restored; preflight `configured=true`.
- Token resolution `state=valid`, token available, no reconnect, checked before
  each live upload and once more after the gates.
- The predeclared Outlook attachment was fetched read-only from Microsoft Graph.
  SHA-1 `e0a7fb8a1b4757b7f6bef882b19cc4588d66246e` matched the active catalog
  version; actual values summed to `216700`.
- Live guided browser run: discovery → typed binding → sum `216700.00` →
  grounded document → controlled approval/outbox → backend restart → reopened
  completed with the artifact still present.
- Changed-byte refresh: disposable OneDrive item
  `01P3INOW3LZH7VV3BVJNEI5VCSUGOJCZ5U` uploaded at `50.00`, changed to `60.00`;
  eTag/cTag incremented; the old `5cea…` binding was refused as
  `stale_source_version`; the new `543421…` version calculated `60.00` across
  two rows, produced a fresh artifact, and reopened after restart.
- Catalog repair: multi-sheet supersession now links each old row to the new row
  for the same sheet instead of an arbitrary batch member. The live Calc pointer
  was corrected after a pre-repair snapshot.
- Reproduced defect fixed: expired access tokens now raise
  `source_access_expired`.
- Default-workspace normalization: a real user with null workspace/tenant now
  resolves to the effective `default` scope.
- Cached Parquet rows were not used for the changed-source gate; the Zoho rows
  were not substituted. No replacement catalog or grant was seeded for the
  named Zoho workbook.
- The failed Zoho gate and all earlier evidence remain unchanged at
  `evidence/durable_assignment_20261029/live-connected/gate-result.json`.

## Rollout

1. Deploy only from clean source commit `058e38ddb`; do not copy local
   working-tree files.
2. Run the focused suite and AssignmentPanel tests on the release source.
3. Run the four Playwright specs in isolated scratch worlds.
4. Run the connected scratch acceptance and bounded taught job.
5. The live gates have passed for the predeclared Microsoft Outlook attachment and
   the separately authorized disposable OneDrive workbook. Do not extend those
   claims to the named Zoho workbook or to normal login-form acceptance.
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

## Remaining blockers and limits

- The originally named Zoho WorkDrive price list remains inaccessible; its
  expired token was not repaired and its failed gate is preserved. The passing
  live gate uses the predeclared Microsoft replacement, not the Zoho workbook.
- Normal login-form acceptance was not exercised. The browser qualification used
  a real signed user session.
- No production email send, deployment, credential change or source writeback
  was performed.

The operational authorization and execution record is
`docs/acceptance/OPERATIONAL_AUTHORIZATION_2026-10-29.md`. Historical OneDrive
provenance is qualified in
`docs/acceptance/LIVE_PROVENANCE_RECONCILIATION_2026-10-29.md`.
