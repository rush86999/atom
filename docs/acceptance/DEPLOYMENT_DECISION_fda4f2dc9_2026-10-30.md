# Deployment decision — successor fda4f2dc9

Status: **requested; not authorized.** No production start, source stop,
approval record, credential change or real send occurred.

## Exact package

| Item | Value |
|---|---|
| Prepared root | `/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-30-fda4f2dc9` |
| Product commit | `fda4f2dc9376f20a6e10de6d7d1e55cf16eeffd4` |
| Release tag | `assignment-successor-2026-10-30-fda4f2dc9` |
| Product tree | `92924cd8f8f3cffa8e884a9a7fecc5f820f4f5ce8acbba60fdd257975df614fa` |
| Rollback | `901e5d77348e0c7b85b1f1291cbeb0fc50eb2ff0` |
| Frontend build | `7Y8qAVXDNHG0Q9YDMKwb4` |
| Kit tree | `5c58bdd36c109b11b14efb6ccf6d8f5410662beb930c7e08a8e2de24bea3ca26` |
| Outbound | draft-and-approval only; `send_authorized=false` |

## Complete authorized operation

This request is for the whole operation, not only `start`:

1. **Verify the source service** using
   `SOURCE_SERVICE_SHUTDOWN_SCOPE_fda4f2dc9.md`: PID `19046`, command, CWD
   `atom-releases/c912375de/backend`, source DB handles, `8001` listener,
   service commit `c912375de...`, and no supervisor that would reopen it.
2. **Stop only that verified process** with `SIGTERM`, then prove no source
   DB/WAL holder and port `8001` free. No other uvicorn process is in scope.
3. **Refresh while quiescent**: data handoff, memory handoff, verification,
   freshness/quiescence check.
4. **Deploy exact product** `fda4f2dc9` through the reversible transaction.
5. **Run fresh authenticated work**, restart agreement, provider-policy and
   send-denial checks, and rollback verification.
6. **On failure, restore the intended source service configuration** from
   `SOURCE_SERVICE_SHUTDOWN_SCOPE_fda4f2dc9.md` in addition to the code
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
  "release_tag": "assignment-successor-2026-10-30-fda4f2dc9",
  "product_commit": "fda4f2dc9376f20a6e10de6d7d1e55cf16eeffd4",
  "product_tree_sha256": "92924cd8f8f3cffa8e884a9a7fecc5f820f4f5ce8acbba60fdd257975df614fa",
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
RELEASE_ROOT=/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-30-fda4f2dc9 \
RELEASE_PYTHON=/Users/rushiparikh/projects/atom/backend/venv/bin/python \
ATOM_SMOKE_PASSWORD_FILE=/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-30-fda4f2dc9/config/pilot_password \
/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-30-fda4f2dc9/current/scripts/deploy_release.sh
```

The transaction runs approval → freshness/quiescence → preflight → verified
backup → freshness recheck → scoped stop → stopped preflight → freshness
recheck → start → normal-auth smoke → representative assignment → fresh
retrieval/calculation/artifact → provider policy → send denial → scoped restart
→ reopen/compare → final health → atomic receipt.

## Why this is reviewable

- 581 release-affected tests passed (2 skipped); 127 targeted core tests passed;
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

## Bounded external research

`external.research` is implemented through the shared action registry and durable executor. It dispatches only registered read-only actions, validates required result fields, records retrieved content as evidence with action/arguments/time provenance, and turns a missing result into a typed `external_research` obligation. Resolving the obligation resumes the same assignment and supplies evidence only; it never changes teaching or authority. Current tests cover success, typed obligation/resume, write-action refusal and teaching preservation.
