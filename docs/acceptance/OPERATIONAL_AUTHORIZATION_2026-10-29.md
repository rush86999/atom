# Operational authorization request — connected assignment live gates

Status: **authorization granted; configuration restored; both predeclared live
gates passed; named Zoho workbook remains inaccessible and preserved as
blocked.** No secret values are included here. No live send, source
modification or deployment has been performed.

Candidate: `9a89471cc0f307130c733bd4485d689e6e83b35c`.
Clean-source verification:
`docs/acceptance/evidence/durable_assignment_20261029/clean-source/verification.json`.

## Purpose

This single authorization covers the remaining operational work only:

1. restore the existing approved Microsoft client configuration;
2. allow normal OAuth renewal, without user reconnect;
3. run the genuine connected guided-start gate;
4. create and modify one disposable test workbook;
5. run changed-source sync, calculation/assessment invalidation and restart.

It does **not** authorize production price-list changes, real email send,
credential rotation/creation, deployment or general source writeback.

## Execution record

- Approved Microsoft client settings restored; preflight `configured=true`.
- Token resolution: `state=valid`, token available, no reconnect required,
  checked before each live operation.
- The named Zoho price-list workbook remained inaccessible (expired access).
  Its failed gate is preserved at
  `evidence/durable_assignment_20261029/live-connected/gate-result.json`;
  Zoho was not repaired.
- A predeclared Microsoft Outlook attachment replaced it for the live gate:
  catalog `00399616-42f7-4f7d-8867-822752b15a46`, sheet `库存产品`, `Price`,
  8 rows, sum `216700`. A direct Graph fetch with the normal resolver matched
  the active SHA-1 `e0a7fb8a1b4757b7f6bef882b19cc4588d66246e`.
- Guided browser run: `216700.00`, grounded document, controlled approval/outbox,
  backend restart, reopened completed.
- Separately authorized disposable OneDrive workbook
  `01P3INOW3LZH7VV3BVJNEI5VCSUGOJCZ5U` changed `50.00` → `60.00`; the old
  `5cea…` binding was refused as `stale_source_version`; the new `543421…`
  version calculated `60.00` across two rows, rendered a fresh artifact and
  reopened after restart.
- Cached Parquet rows were not substituted for the named Zoho workbook; no
  replacement catalog/grant was seeded for it. The production price list was
  not modified.
- Reproduced defect fixed: expired access tokens are refused with
  `source_access_expired`.
- No production email send or deployment was performed; outbound remained a
  local controlled outbox.

## 1. Configuration restoration

Existing approved private source:

```
/Users/rushiparikh/projects/atom/backend/.env
```

Runtime destination for the isolated qualification process:

```
/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-whole-app/backend/.env
```

If qualification runs from the clean candidate, use that worktree's
`backend/.env` instead; do not copy secrets into the source tree.

Keys restored, presence only:

- `MICROSOFT_CLIENT_ID`
- `MICROSOFT_CLIENT_SECRET`
- `MICROSOFT_TENANT_ID` (if present in the approved source)

Prepared command:

```bash
python scripts/acceptance/restore_private_microsoft_config.py \
  --source /Users/rushiparikh/projects/atom/backend/.env \
  --destination /private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-whole-app/backend/.env
```

The script backs up the destination, writes only those keys, prints presence
only, and never prints values. No credential is created or rotated.

After restore:

```bash
cd backend
python - <<'PY'
from core.oauth_config_preflight import microsoft_client_config_state
print(microsoft_client_config_state())
PY
```

Expected: `configured: true`, no placeholders. Never print the values.

## 2. Normal OAuth renewal

Use the repaired shared resolver; do not create a legacy fallback and do not
reconnect the user merely to hide a client error.

Required states:

- `refreshed` (or an already valid access token), not `invalid_client`;
- replacement refresh token persisted securely if returned;
- no scope expansion;
- one authorized read succeeds.

Stop if the resolver reports `invalid_client`, `invalid_grant`,
`requires_reconnect`, `source_permission_revoked` or `source_disconnected`.

## 3. Live guided-start gate

Use the genuine connected catalog and the previously ingested workbook. Do not
seed a replacement catalog row, materialization, grant or fake token.

Workbook: `Consolidated Price List 2019.xlsx`
Sheet: `US$ SCOTCH PARTS`
Prior full-set reference: `9,958,743.62` for the sum of `Unit Price` across
11,219 rows.

Normal browser path (no auth override):

1. Sign in normally to the real app.
2. Use the normal Assignments surface in the Chat workspace, with the
   connected employee agent.
3. Objective:
   `In workbook Consolidated Price List 2019.xlsx only, on sheet US$ SCOTCH PARTS, what is the sum of Unit Price?`
4. Enable **Discover an authorized resource from a scope**.
5. Scope: `US$ SCOTCH PARTS`.
6. Deliverable: document.
7. Test recipient: `live-acceptance@example.invalid` (controlled outbox only;
   no real send).
8. Start.
9. Verify discovery selected the intended sheet among actual catalog
   distractors. If several remain plausible, stop and record the honest
   clarification; do not pick by order.
10. Verify the plan, retrieval, calculation and grounded document:
    - resource identity is the real catalog entry;
    - source version is the active upstream version;
    - coverage is complete for the sheet;
    - result is `9,958,743.62` for the full sheet, not a display page;
    - document contains the result and actual source references.
11. Approve the concrete controlled payload; verify one controlled outbox line
    with the result and source.
12. Restart the qualification backend and re-read the same assignment and
    artifact; they must agree.

Qualification process configuration:

```
ATOM_DATA_DIR=<real runtime data root>
ATOM_OFFICE_DIR=<owned office root>
ATOM_ASSIGNMENT_OUTPUT_DIR=<owned assignment output root>
ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS=0
ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT=1   # qualification only
```

Use an owned port/process; do not kill or overwrite the owner's normal runtime.
No production send adapter is authorized.

Evidence destination:
`docs/acceptance/evidence/durable_assignment_20261029/live-connected/guided/`.

Capture: request, run id, catalog identity, source version, coverage, plan
revision, result, artifact hash/text, approval id, outbox line, restart status.

## 4. Disposable changed-source gate

Exact test-only location:

```
Folder: AtomAcceptance/connected-refresh-20261029-0120Z
File:   refresh_probe_f5f_20261029.xlsx
```

The folder/file are new, uniquely named, test-only and safe to delete. No other
OneDrive item is created or modified.

Prepared local fixtures:

- `docs/acceptance/evidence/connected_core_20261028/disposable_source/refresh_probe_f5f_baseline.xlsx`
- `.../refresh_probe_f5f_changed_expected.xlsx`
- `.../refresh_probe_f5f_manifest.json`

Baseline:

- `Inputs!B2=2`, `Inputs!B3=3`, unit price `10.00`;
- `Calc` formula cells `D2=Inputs!B2*Inputs!C2`, `D3=Inputs!B3*Inputs!C3`;
- total `50.00`; decisions `APPROVE` for PROBE-001, `REVIEW` for PROBE-002.

One authorized change:

- `Inputs!B2`: `2 → 3` only;
- expected `D2=30`, `D3=30`; total `60.00`;
- expected decisions `REVIEW`, `REVIEW`.

Procedure after Part A passes:

1. Upload the baseline workbook to the exact test location.
2. Sync it; capture item id, version/hash, coverage and formula sidecar.
3. Calculate `50.00`; assess `APPROVE/REVIEW`; save an artifact/export and
   reopen it.
4. Replace only that test file with the changed workbook.
5. Sync again; verify new upstream version, new materialization, prior version
   superseded, and prior provenance retained.
6. Verify affected calculation/assessment/artifact reuse is invalidated.
7. Re-bind; calculate `60.00`; assess `REVIEW/REVIEW`; save/reopen the fresh
   artifact.
8. Restart and verify the new binding, new result, assessment and artifact
   agree. Do not reuse the old result.

Evidence destination:
`docs/acceptance/evidence/durable_assignment_20261029/live-connected/changed-source/`.

## 5. Exclusions

- No production price-list modification.
- No email send or provider delivery; controlled outbox only.
- No credential creation/rotation, user reconnect or legacy fallback.
- No deployment, release tag or production runtime restart.
- No replacement catalog/grant rows.
- No broad browser campaign or unrelated test expansion.

## 6. Stop conditions

Stop immediately and preserve evidence if:

- client config is reported missing or placeholder after restore;
- renewal returns `invalid_client`/`invalid_grant`/`requires_reconnect`;
- discovery is ambiguous or selects an unintended sheet;
- source version/coverage is stale or incomplete;
- the result disagrees with the full-sheet reference;
- an artifact lacks the result/source or is not reopenable;
- approval payload or outbox body disagrees with the artifact;
- any production file, recipient or credential is touched unexpectedly.

## 7. Rollback / recovery

- Restore the qualification backend `.env` from its timestamped backup.
- Stop the qualification process; do not alter the owner's normal runtime.
- Do not delete the disposable OneDrive file until evidence is captured.
- Do not restore the database unless corruption is demonstrated; see
  `docs/acceptance/assignment-successor-package-2026-10-29/ASSIGNMENT_SUCCESSOR_PACKAGE_2026-10-29.md`.
- Code rollback target remains `294fdf0ec` (preserves security repairs); never
  automatically overwrite newer user work.

## Authorization phrase

To proceed, authorise exactly:

> I authorize the combined operational procedure in
> `docs/acceptance/OPERATIONAL_AUTHORIZATION_2026-10-29.md`: restore the
> existing approved Microsoft client configuration, allow normal renewal, run
> the genuine connected guided-start gate, and create/modify only the named
> disposable test workbook for changed-source verification. No production
> price-list change, real send, credential rotation or deployment.
