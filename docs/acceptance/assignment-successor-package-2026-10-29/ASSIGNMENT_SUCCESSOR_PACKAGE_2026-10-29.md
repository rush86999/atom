# Assignment successor deployment package — 2026-10-29

Status: **prepared, not deployed.** The code candidate and controlled evidence
are ready. Live OneDrive start and live changed-source refresh remain blocked
by owner configuration/authorization, so this is not a claim that the
live-connected exit condition is closed.

## Exact source

| Item | Commit |
|---|---|
| Candidate source | `de25c5148` |
| Review repairs | `294fdf0ec` |
| Preserved connected guided candidate | `40b3367d9` |
| Preserved start boundary | `44b62a6bb` |
| Preserved correction pass | `322981bcc` |
| Preserved executor freeze | `efc4bc9d5` |

Branch: `whole-app/successor-f5f`.

The scoped commits do **not** collect the owner teaching working-tree delta.
The candidate runtime requires these files, bound by SHA256 in
`docs/acceptance/assignment-successor-package-2026-10-29/assignment_successor_manifest.json`:

- `backend/core/artifact_teaching.py`
- `backend/core/student_learning_service.py`
- `backend/core/office_service.py`

The owner must commit/merge that delta before a clean release checkout. This is
the main packaging blocker.

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

- Focused backend: 134 passed
- Assignment component: 3 passed
- Guided browser start/reload: 1 passed
- Guided browser after restart: 1 passed
- Explicit browser start/reload: 1 passed
- Explicit browser after restart: 1 passed
- Connected scratch acceptance: passed (`85.00`, `3`, both reopened)
- Bounded taught job: passed (`24.00 USD`, two sources, formatted draft,
  reopened)
- TypeScript: clean

## Rollout

1. Owner commits/merges the bound teaching delta.
2. Re-run the focused suite and the AssignmentPanel tests on the release
   branch.
3. Re-run the four Playwright specs in isolated scratch worlds.
4. Re-run the connected scratch acceptance and bounded taught job.
5. Keep live-connected and changed-source gates closed until the owner supplies
   client configuration and the exact disposable-source authorization.
6. Do not enable controlled transport or internal paths in production.

## Rollback

The preserved candidate is `40b3367d9`. Rolling back the review repairs
reintroduces the reproduced findings in `ASSIGNMENT_REVIEW_2026-10-29.md`;
prefer rolling back only the bounded taught-job commit (`de25c5148`) if
necessary.

## Remaining blockers

- Microsoft client configuration absent.
- Live OneDrive guided start not run.
- Disposable changed-source authorization not granted.
- Owner teaching working-tree delta not committed to the release branch.
