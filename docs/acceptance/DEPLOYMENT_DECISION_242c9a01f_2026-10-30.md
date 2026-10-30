# Deployment decision — successor 242c9a01f

Status: **requested; not authorized.** No production start, approval record,
credential change or real send occurred.

## Exact package

| Item | Value |
|---|---|
| Prepared root | `/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-30-242c9a01f` |
| Product commit | `242c9a01ff9aebb0467ad7a619ea7e4e468f454d` |
| Release tag | `assignment-successor-2026-10-30-242c9a01f` |
| Product tree | `c20bb599ff7ab65913f42cd14a5a93012b6817c93b6b0b5eddfb7c056e24c9b7` |
| Rollback | `901e5d77348e0c7b85b1f1291cbeb0fc50eb2ff0` |
| Frontend build | `K3N6o-mTkpSVJ7sj00FLu` |
| Kit tree | `629f369dfc98472e786b0e9ba2499f95958ffdf6abfbd349401e1d220f061de5` |
| Outbound | draft-and-approval only; `send_authorized=false` |

## Why this is reviewable

- 578 release-affected tests passed (2 skipped); 127 targeted core tests passed;
  22 deployment-kit controls passed.
- Four current mapping browser flows passed on this product (B `35.00`, C
  `75.00`, correction `100.00 -> 80.00`, waiting restart `35.00`).
- Data handoff: 16,305 operations, 0 binding mismatches; 21 missing historical
  paths visible; required memory exported; omitted archives explicit.
- Rollback to `901e5d773` verified against the refreshed data with no database
  restore and no new interactive approval.
- Freshness/quiescence gate implemented and exercised, including stale
  post-backup and pre-activation controls.

## Exact command authorization would permit

After the owner supplies `config/pilot_password`, creates `config/APPROVED`
with the identity above, and stops the live source writer (or authorizes an
equivalent quiescence window):

```bash
RELEASE_ROOT=/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-30-242c9a01f \
RELEASE_PYTHON=/Users/rushiparikh/projects/atom/backend/venv/bin/python \
ATOM_SMOKE_PASSWORD_FILE=/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-30-242c9a01f/config/pilot_password \
/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-30-242c9a01f/current/scripts/deploy_release.sh
```

The transaction runs approval → freshness/quiescence → preflight → verified
backup → freshness recheck → scoped stop → stopped preflight → freshness
recheck → start → normal-auth smoke → representative assignment → fresh
retrieval/calculation/artifact → provider policy → send denial → scoped restart
→ reopen/compare → final health → atomic receipt.

## Stop conditions

- missing approval or pilot password;
- source writer still active (the gate refuses);
- any source change after the snapshot (refresh first);
- failed preflight, backup, startup, auth, assignment, restart or receipt;
- any attempt to enable real sending.

## Remaining separate request

Real-provider sending is **not** authorized by this decision. The separate
qualification request remains
`docs/acceptance/REAL_PROVIDER_SEND_QUALIFICATION_2026-10-29.md`.
