# Assignment successor isolated deployment rehearsal — 2026-10-29

Status: **passed in an isolated runtime; live deployment remains unauthorized.**

## Identity exercised

- Product commit: `ef95ceb3194ec92c51e64941d7bb364c0b8b0e75`
- Tag: `assignment-successor-2026-10-29`
- Tested live runtime: `001f93472`
- Product tree SHA-256:
  `12060bee618e7a58a98324f682d39077c144c19a6fb7d22d77de8179237dbb9e`
- Frontend build: `i_Co6JD6WAcOXWZyMudPw`
- Health identity returned the exact product commit with `dirty=false`.

## Results

| Check | Result | Evidence |
|---|---|---|
| Preflight identity/config/ports | Passed | `preflight.json` |
| Fresh verified backup | Passed; SQLite integrity OK; 557 goal runs preserved | `backup-manifest.json` |
| Scoped start | Passed; one backend, one frontend, health identity matched | `startup-receipt.json` |
| Normal login form (fresh context, no injected session) | Passed | `auth-smoke/auth-smoke.json` |
| Workspace + completed assignment + artifact | Passed; artifact SHA-256 `318a675…` | `auth-smoke/assignment-open.png` |
| Logout / token revocation | Passed; old token returned 401 | `auth-smoke/signed-out.png` |
| Second login and workspace access | Passed | `auth-smoke/signed-in-again.png` |
| Representative assignment reopen | Passed; `216700.00`, 8 rows | `assignment-before-restart.json` |
| Restart agreement | Passed; run/assignment/status/artifact/source versions identical | `assignment-after-restart.json` |
| One-command deployment transaction | Passed | `deployment-receipt.json` |
| Code rollback C6 → C4 → C6 | Passed; database untouched | `rollback-rehearsal.json` |

The rehearsal used a SQLite copy of the real database and copied artifacts under
an isolated root. The live database was not written. A generated rehearsal
password was used only for the copied `admin@example.com` row; it is stored in
the runtime config mode 600 and is not in this repository.

## Scope confirmed

- `ATOM_DEPLOYMENT_AUDIENCE=single_user`
- `ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS=0`
- `ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT` unset
- `ENABLE_SCHEDULER=false`, `ENABLE_INGESTION_SYNC=false`
- DeepSeek-only selected provider policy
- Microsoft client id/secret present (presence checked, never printed)
- One backend worker; one worker process per assignment
- Email outbound scope: **draft-and-approval only**; no send test

## Remaining blocker

Live deployment is blocked only on owner authorization. Create
`<root>/config/APPROVED` with the approver, date,
`assignment-successor-2026-10-29`, and product commit
`ef95ceb3194ec92c51e64941d7bb364c0b8b0e75`, supply the pilot password file,
and run `deploy_release.sh` without `--rehearsal`.

The originally named Zoho workbook remains inaccessible and outside this
release; production email sending is not authorized.
