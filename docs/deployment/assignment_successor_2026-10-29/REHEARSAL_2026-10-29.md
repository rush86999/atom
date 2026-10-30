# Assignment successor isolated deployment rehearsal — 2026-10-29

Status: **passed in an isolated runtime; live deployment remains unauthorized.**

## Identity exercised

- Product commit: `901e5d77348e0c7b85b1f1291cbeb0fc50eb2ff0`
- Tag: `assignment-successor-2026-10-29`
- Tested live runtime: `001f93472`
- Product tree SHA-256:
  `92d794b20400aa013019a602fc6dccfa2c3b53240ff63905dc40d80340d3937c`
- Frontend build: `QqBNj-ytvaFAwwCWX2M5F`
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
| Fresh assignment retrieval → calculation → artifact | Passed; new run, `216700.00`, grounded document | `fresh-before-restart.json` |
| Fresh assignment after restart | Passed; same run/artifact/hash | `fresh-after-restart.json` |
| Draft save/reopen | Passed; `email_draft` applied, same revision/hash after restart | `draft-smoke.json`, `draft-smoke-after.json` |
| Production send denial | Passed; HTTP 422 before run creation, no provider/outbox effect | `send-denial.json` |
| Recovery controls | Passed; 19 fake-service/command/approval/smoke controls | `launch-controls.json` |
| One-command deployment transaction | Passed | `deployment-receipt.json` |
| Code rollback C6 → C4 → C6 | Passed; database untouched | `rollback-rehearsal.json` |

The rehearsal used a SQLite copy of the real database and copied artifacts under
an isolated root. The live database was not written. A generated rehearsal
password was used only for the copied `admin@example.com` row; it is stored in
the runtime config mode 600 and is not in this repository.

## Scope confirmed

- `ATOM_DEPLOYMENT_AUDIENCE=single_user`
- `ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS=0`
- `ATOM_ASSIGNMENT_ALLOW_LIVE_SEND=0`
- `ATOM_EMAIL_SEND_DISABLED=1`
- `ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT` unset
- `ENABLE_SCHEDULER=false`, `ENABLE_INGESTION_SYNC=false`
- DeepSeek-only selected provider policy
- Microsoft client id/secret present (presence checked, never printed)
- One backend worker; one worker process per assignment
- Email outbound scope: **draft-and-approval only**; send denied before transport

## Remaining blocker

Live deployment is blocked on owner authorization. Create
`<root>/config/APPROVED` as JSON with `approver`, `approved_at`,
`release_tag` `assignment-successor-2026-10-29`, `product_commit`
`901e5d77348e0c7b85b1f1291cbeb0fc50eb2ff0`, `product_tree_sha256`
`92d794b20400aa013019a602fc6dccfa2c3b53240ff63905dc40d80340d3937c`,
`scope` `single_user` and `mode` `production`. Supply the pilot password file
and run `deploy_release.sh` without `--rehearsal`.

The originally named Zoho workbook remains inaccessible and outside this
release; production email sending is not authorized.
