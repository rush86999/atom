# Assignment successor isolated rehearsal — fda4f2dc9

Status: **full isolated deployment transaction passed in a packaged runtime;
production deployment remains unauthorized.**

## Identity exercised

- Product commit: `fda4f2dc9376f20a6e10de6d7d1e55cf16eeffd4`
- Tag: `assignment-successor-2026-10-30-fda4f2dc9`
- Product tree SHA-256:
  `92924cd8f8f3cffa8e884a9a7fecc5f820f4f5ce8acbba60fdd257975df614fa`
- Frontend build: `LZy8An7y4FAIM7H5yyRJD`
- Health identity returned the exact product commit with `dirty=false`.

## Results

| Check | Result | Evidence |
|---|---|---|
| Preflight identity/config/ports | Passed | `release-integration-fda4f2dc9-transaction/preflight.json` |
| Verified SQLite backup | Passed; integrity OK; row counts preserved | `release-integration-fda4f2dc9-transaction/backup-manifest.json` |
| Scoped start | Passed; one backend, one frontend, exact health identity | `release-integration-fda4f2dc9-transaction/startup-receipt.json` |
| Existing taught assignment reopen | Passed; completed, artifact `9edba384...` | `release-integration-fda4f2dc9-transaction/assignment-before-restart.json` |
| Mapping flow | Passed; `Amount`, `35.00 USD`, mapping revision 3 | same |
| Fresh read-only assignment | Passed; `35.00 USD`, grounded document, new run | `release-integration-fda4f2dc9-transaction/fresh-before-restart.json` |
| Provider policy | Passed; selected DeepSeek, `deepseek-flash` | same |
| Draft-only send denial | Passed; HTTP 422 before run creation; no run delta | same |
| Scoped restart | Passed; same assignments/results/artifacts | `release-integration-fda4f2dc9-transaction/assignment-after-restart.json` |
| Fresh assignment after restart | Passed; same run/artifact/hash | `release-integration-fda4f2dc9-transaction/fresh-after-restart.json` |
| Restart agreement | Passed; no mismatches for mapping or fresh work | same |
| Final health | Passed; exact revision, `dirty=false` | `release-integration-fda4f2dc9-transaction/final-status.json` |
| Deployment kit controls | 19 passed | `release-integration-fda4f2dc9-transaction/kit-tests.log` |
| Full deployment transaction | Passed; approval, preflight, backup, stop/start, auth, assignment, fresh work, provider policy, send denial, restart, receipt | `release-integration-fda4f2dc9-transaction/deployment-receipt.json` |
| First transaction attempt | Failed at onboarding modal; preserved, then repaired | `release-integration-fda4f2dc9-transaction/failed-attempt.json` |

The rehearsal used a controlled workbook-B seed world copied into the isolated
package data root. The live database was not written. No real provider send,
credential change or source writeback occurred.

Rollback scope: the 19 deployment-kit controls include failure/approval/command
and recovery assertions. The isolated transaction root was a first release with
no `previous` link, so automatic rollback was not exercised in that transaction.
A full C6 -> C4 -> C6 transaction was previously exercised in isolation for
`901e5d773`, not for this candidate and not in production. No production
rollback has occurred.

## Scope confirmed

- `ATOM_DEPLOYMENT_AUDIENCE=single_user`
- `ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS=0`
- `ATOM_ASSIGNMENT_ALLOW_LIVE_SEND=0`
- `ATOM_EMAIL_SEND_DISABLED=1`
- `ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT` unset
- `ENABLE_SCHEDULER=false`, `ENABLE_INGESTION_SYNC=false`
- DeepSeek-only selected provider policy
- One backend worker; one worker process per assignment
- Email outbound scope: **draft-and-approval only**; send denied before transport

## Remaining blocker

Production deployment is blocked on owner authorization. Review the runbook and
create `<root>/config/APPROVED` with the exact tag, commit and product-tree
checksum. Real-provider sending remains a separate, unauthorized gate.
