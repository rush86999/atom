# Assignment successor release package — a96484324

Status: **frozen successor candidate; four mapping browser flows passed; 98
affected regressions passed; packaged smoke passed; deployment requested, not
authorized.** The previous frozen release `901e5d773` and all prior evidence
remain unchanged. Nothing was deployed, sent through a real provider, or written
back to a source.

## Exact source

| Item | Value |
|---|---|
| Deployable product commit | `a9648432495f4f75f59bf4667cac3cb997d7f229` |
| Release tag | `assignment-successor-2026-10-29-a96484324` |
| Product tree SHA-256 | `937d100838300c8ec703f5c8ee164f029acf4ecbe64d6a823bd994fa9070d8e6` |
| Previous frozen release | `901e5d77348e0c7b85b1f1291cbeb0fc50eb2ff0` (tag `assignment-successor-2026-10-29`) |
| Branch | `whole-app/successor-f5f` |

The successor adds mapping rejection/restart recovery, source/teaching revision
checks, idempotent replay, conflicting replay refusal, and the remaining
authority controls on top of the previous confirmation/unit/correction work. It
does not rewrite the previous release tag or evidence.

Manifest:
`docs/acceptance/assignment-successor-package-2026-10-29-a96484324/assignment_successor_manifest.json`.
Source manifest:
`docs/acceptance/assignment-successor-package-2026-10-29-a96484324/source_manifest.json`.

## Browser results on the frozen candidate

| Flow | Result | Evidence |
|---|---|---|
| Workbook B confirmation | `35.00 USD` | `mapping-browser-b/attempts/c78b9a0c-4d4b-4ef6-97e5-4be56fa31449/result.json` |
| Workbook C explicit unit | `75.00 USD`, `user_confirmed` | `mapping-browser-c/attempts/a228e80a-1980-4d9c-8489-6295ca38abce/result.json` |
| Correction | `100.00 -> 80.00`, mapping revision 3 | `mapping-browser-correction/attempts/0f8db7bb-f3d2-4d5f-8ec5-768dd677843e/result.json` |
| Reject -> backend restart -> confirm | same request, `35.00 USD`, mapping revision 2 | `mapping-browser-waiting-restart/attempts/a8b27ce5-ead8-4a9f-8b21-8069e088486e/result.json` |

Authority controls: wrong request/assignment, forged column, stale source
(payload and current source), stale teaching, wrong workspace, incompatible
unit, rejection, identical replay without duplicate work, conflicting replay,
and ambiguous concept/source identity. Focused controls: **5 passed**.
Affected regressions: **98 passed** on the same product commit.

## Packaged smoke

The isolated packaged runtime used the same scratch stores, a normal login, and
the packaged frontend/backend at the frozen commit. It:

- reopened an existing taught workbook-B assignment and its artifact
  (`9edba384...`);
- created one new mapping assignment, confirmed `Amount`, and completed at
  `35.00 USD` with one accepted mapping update (revision 2 -> 3 in the seeded
  world);
- verified the selected provider policy is DeepSeek only
  (`deepseek` / `deepseek-flash`);
- proved an outbound assignment is refused with HTTP 422 before run creation
  (`ATOM_ASSIGNMENT_ALLOW_LIVE_SEND=0`, `ATOM_EMAIL_SEND_DISABLED=1`);
- restarted the packaged backend and reopened both assignments, results and
  artifacts with identical identity/hash and no restart disagreement.

Receipts:
`docs/acceptance/evidence/durable_assignment_20261029/release-integration-a96484324/`
(`preflight.json`, `startup-receipt.json`, `mapping-taught-smoke.json`,
`mapping-taught-smoke-after-restart.json`, `backup-manifest.json`,
`final-status.json`, `evidence-manifest.json`).

## Release and rollback package

Deployment kit:
`scripts/deployment/assignment_successor_2026-10-29_a96484324/`.
Runbook:
`docs/deployment/assignment_successor_2026-10-29_a96484324/DEPLOYMENT_RUNBOOK.md`.
Rehearsal record:
`docs/deployment/assignment_successor_2026-10-29_a96484324/REHEARSAL_2026-10-29-a96484324.md`.

The kit is an overlay, checksummed separately from the product tree. It clones
the exact release tag, builds the standalone frontend, validates the source
manifest and product-tree checksum, supports a verified SQLite backup, scoped
start/stop, one-command deployment and code rollback. The database is never
restored automatically. The rollback target for this candidate is the previous
frozen release `901e5d773`; a successor deployment over the existing pilot root
records that release as `previous`.

## Authorization request

The deployment approval request is
`docs/deployment/assignment_successor_2026-10-29_a96484324/APPROVAL_REQUEST.md`.
`config/APPROVED` is intentionally absent. Deployment remains unauthorized.

## Not claimed

- Real-provider email sending. This release remains draft-and-approval only;
  the server-side gate refuses send before transport. A separately authorized
  real-provider test remains open.
- Automatic understanding of arbitrary schemas or every possible authority
  surface.
- Arbitrary Excel formula compatibility.
- Any deployment, credential change or source writeback.
