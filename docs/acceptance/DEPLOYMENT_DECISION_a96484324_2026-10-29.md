# Deployment decision — assignment successor a96484324

Status: **one reversible single-user deployment requested; not authorized.**
No deployment, approval-file creation, real send, credential change or source
writeback has occurred.

## Exact authorization requested

Authorize one supervised deployment of the frozen candidate:

| Item | Value |
|---|---|
| Product commit | `a9648432495f4f75f59bf4667cac3cb997d7f229` |
| Release tag | `assignment-successor-2026-10-29-a96484324` |
| Product tree SHA-256 | `937d100838300c8ec703f5c8ee164f029acf4ecbe64d6a823bd994fa9070d8e6` |
| Rollback target | `901e5d77348e0c7b85b1f1291cbeb0fc50eb2ff0` (tag `assignment-successor-2026-10-29`) |
| Intended root | `/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-29-a96484324` |
| API / UI ports | `127.0.0.1:8071` / `127.0.0.1:3130` |
| Account | `admin@example.com` only |
| Data / artifacts | `<root>/data/atom.db`, `<root>/data/office`, `<root>/data/sheet_datasets`, `<root>/data/email_attachments` |
| Frontend build | `LZy8An7y4FAIM7H5yyRJD` (prepared package; see `RELEASE_IDENTITY.json`) |
| Audience / mode | `single_user` / `production` |
| Outbound scope | draft-and-approval only; send **not** authorized |

Production approval record (`<root>/config/APPROVED`) must be JSON containing:

```json
{
  "approver": "<owner identity>",
  "approved_at": "<ISO date>",
  "release_tag": "assignment-successor-2026-10-29-a96484324",
  "product_commit": "a9648432495f4f75f59bf4667cac3cb997d7f229",
  "product_tree_sha256": "937d100838300c8ec703f5c8ee164f029acf4ecbe64d6a823bd994fa9070d8e6",
  "scope": "single_user",
  "mode": "production"
}
```

Every field is validated against `RELEASE_IDENTITY.json` before backup or
shutdown. File existence alone is not approval. This report does **not** create
that file.

## Exact command authorization would permit

After review and after the owner creates `config/APPROVED` and supplies the
pilot password file:

```bash
RELEASE_ROOT=/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-29-a96484324 \
RELEASE_PYTHON=/Users/rushiparikh/projects/atom/backend/venv/bin/python \
ATOM_SMOKE_PASSWORD_FILE=/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-29-a96484324/config/pilot_password \
/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-29-a96484324/current/scripts/deploy_release.sh
```

The transaction runs: approval check → preflight → verified SQLite backup →
scoped stop → stopped preflight → start → normal-auth smoke → representative
assignment reopen → fresh retrieval/calculation/artifact assignment →
provider-policy check → send-denial-before-transport check → scoped restart →
reopen/compare both assignments → final health → atomic deployment receipt.

Expected duration: **10–20 minutes** on this workstation, plus up to ~5 minutes
if a post-shutdown failure triggers the rollback attempt.

## Failure and rollback bounds

- Recovery is armed **before** the first disruptive operation.
- Pre-shutdown failures leave the running service untouched.
- After shutdown, any failure (stop/start, auth, assignment/artifact assertion,
  restart agreement, receipt publication) triggers a verified code rollback to
  `901e5d773`.
- Rollback failure is written to `run/deployment_failure.json`; it is never
  hidden behind a success exit.
- The database is **never** restored automatically; newer user data is
  preserved.
- The final deployment receipt is published atomically only after all checks.
- **No production rollback has occurred.** The rollback path is exercised in
  isolated kit controls; a full isolated C6→C4→C6 rollback was previously
  demonstrated for `901e5d773`, not for this candidate in production.

## Separate sending qualification

Real-provider sending is a distinct gate and is **not** part of this
deployment authorization. The prepared plan is
`docs/acceptance/REAL_PROVIDER_SEND_QUALIFICATION_2026-10-29.md`.

Still missing before any real send:
- approved sending account/UPN and tenant;
- `Mail.Send` delegated grant (or separately reviewed app permission);
- approved external test recipient;
- exact subject/body/attachment bytes and SHA-256;
- approver identity and bounded send window;
- provider-receipt/Sent-Items access for reconciliation;
- reconciliation window and retry decision owner;
- data-retention decision for the test message.

Drafting or approving a draft is not send permission. Provider acceptance is
not recipient delivery.

## Evidence and ledger

- Package manifest:
  `docs/acceptance/assignment-successor-package-2026-10-29-a96484324/assignment_successor_manifest.json`
- Packaged smoke/restart/backup receipts:
  `docs/acceptance/evidence/durable_assignment_20261029/release-integration-a96484324-final/`
- Goal audit: `docs/acceptance/GOAL_COMPLETION_AUDIT_2026-10-29.md`
- Durable ledger: `docs/acceptance/PRODUCT_GOAL_LEDGER_2026-10-29.md`

## Remaining limitations

Goal 3 is demonstrated only for the tested mapping workflows. Goal 11 remains
Partial/Blocked until real-provider qualification passes. Goal 12 remains
deployment-unverified until the authorized transaction above runs. Goals 5 and
9 remain bounded subsets; goals 1, 3, 4, 8 and 10 retain the limitations stated
in the audit and ledger.
