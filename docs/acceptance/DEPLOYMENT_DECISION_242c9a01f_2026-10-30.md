# Deployment decision — successor 242c9a01f

Status: **requested; not authorized.** No production start, source stop,
approval record, credential change or real send occurred.

## Exact package

| Item | Value |
|---|---|
| Prepared root | `/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-30-242c9a01f` |
| Product commit | `242c9a01ff9aebb0467ad7a619ea7e4e468f454d` |
| Release tag | `assignment-successor-2026-10-30-242c9a01f` |
| Product tree | `c20bb599ff7ab65913f42cd14a5a93012b6817c93b6b0b5eddfb7c056e24c9b7` |
| Rollback | `901e5d77348e0c7b85b1f1291cbeb0fc50eb2ff0` |
| Frontend build | `K3N6o-mTkpSVJ7sj00FLu` |
| Kit tree | `d72546d36f20af1c780ca526635d8c1ee764d28eb46230a11d5b0563835157e5` |
| Outbound | draft-and-approval only; `send_authorized=false` |

## Complete authorized operation

This request is for the whole operation, not only `start`:

1. **Verify the source service** using
   `SOURCE_SERVICE_SHUTDOWN_SCOPE_242c9a01f.md`: PID `19046`, command, CWD
   `atom-releases/c912375de/backend`, source DB handles, `8001` listener,
   service commit `c912375de...`, and no supervisor that would reopen it.
2. **Stop only that verified process** with `SIGTERM`, then prove no source
   DB/WAL holder and port `8001` free. No other uvicorn process is in scope.
3. **Refresh while quiescent**: data handoff, memory handoff, verification,
   freshness/quiescence check.
4. **Deploy exact product** `242c9a01f` through the reversible transaction.
5. **Run fresh authenticated work**, restart agreement, provider-policy and
   send-denial checks, and rollback verification.
6. **On failure, restore the intended source service configuration** from
   `SOURCE_SERVICE_SHUTDOWN_SCOPE_242c9a01f.md` in addition to the code
   rollback. Do not leave `atom-c912375de` unavailable.

## Approval binding

The production `config/APPROVED` must include the exact
`source_shutdown_scope` object from
`config/source_shutdown_scope.json`. The validator now refuses production
approval if it is missing or differs. Example:

```json
{
  "approver": "<owner>",
  "approved_at": "2026-10-30",
  "release_tag": "assignment-successor-2026-10-30-242c9a01f",
  "product_commit": "242c9a01ff9aebb0467ad7a619ea7e4e468f454d",
  "product_tree_sha256": "c20bb599ff7ab65913f42cd14a5a93012b6817c93b6b0b5eddfb7c056e24c9b7",
  "scope": "single_user",
  "mode": "production",
  "source_shutdown_scope": {
    "pid": 19046,
    "service": "atom-c912375de",
    "commit": "c912375de81b55465e61fe468bf0bc2b405fd206",
    "database": "/Users/rushiparikh/projects/atom/backend/data/atom.db",
    "restore_command": "/Users/rushiparikh/projects/atom/backend/venv314/bin/python -m uvicorn main_api_app:app --host 0.0.0.0 --port 8001 --timeout-keep-alive 75"
  }
}
```

The owner must create `config/pilot_password` securely; never paste the
password into chat or commit it.

## Exact deployment command

After approval, password, and the authorized source stop/refresh:

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

## Why this is reviewable

- 578 release-affected tests passed (2 skipped); 127 targeted core tests passed;
  25 deployment-kit controls passed.
- Four current mapping browser flows passed on this product: B `35.00`, C
  `75.00`, correction `100.00 -> 80.00`, waiting restart `35.00`.
- Data: 50/481/557 rows; 1,205 files; 16,305 operations, 0 binding mismatches;
  21 missing historical paths visible; required memory exported; omitted
  archives explicit.
- Rollback to `901e5d773` verified against refreshed data with no database
  restore and no new interactive approval.
- Exact attachment-byte approval binding is implemented and tested.

## Remaining non-deployment decisions

- **Real-provider sending**: separately unauthorized. Request:
  `REAL_PROVIDER_SEND_QUALIFICATION_2026-10-29.md`.
- **Autonomous third-party research**: explicitly unclaimed. The owner must
  either authorize a bounded read-only provider/tool workflow or explicitly
  agree to defer it; see `RESEARCH_SCOPE_DECISION_2026-10-30.md`.
- **Formula text**: the current cross-sheet test proves formula **text
  preservation**, not evaluation. Formula evaluation is claimed only for the
  supported engine subset; broader Excel compatibility remains unclaimed.
