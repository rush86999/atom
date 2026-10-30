# Assignment successor release package — a96484324

Status: **frozen successor candidate; production root prepared with data and
required memory; rollback target prepared and actually started in isolation;
four mapping browser flows and 508 release-affected regressions passed;
deployment requested, not authorized. `config/APPROVED` and
`config/pilot_password` are still absent.** The previous frozen release `901e5d773` and all prior evidence
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
Mapping regressions: **98 passed**. Release-affected regressions: **508 passed,
2 skipped** on the same product commit.

## Packaged smoke

The isolated packaged runtime used the same scratch stores, a normal login, and
the packaged frontend/backend at the frozen commit. It:

- reopened an existing taught workbook-B assignment and its artifact
  (`9edba384...`);
- created one new mapping assignment, confirmed `Amount`, and completed at
  `35.00 USD` with one accepted mapping update (revision 2 -> 3 in the seeded
  world);
- created a second fresh read-only assignment through the public API,
  calculated `35.00 USD`, rendered a grounded document and reopened it after
  restart with the same artifact hash;
- verified the selected provider policy is DeepSeek only
  (`deepseek` / `deepseek-flash`);
- proved an outbound assignment is refused with HTTP 422 before run creation
  (`ATOM_ASSIGNMENT_ALLOW_LIVE_SEND=0`, `ATOM_EMAIL_SEND_DISABLED=1`);
- restarted the packaged backend and reopened both assignments, results and
  artifacts with identical identity/hash and no restart disagreement.

The full isolated deployment transaction also passed: approval check, preflight,
verified backup, scoped stop/start, fresh normal-browser authentication, existing
teaching assignment reopen, fresh calculation/artifact assignment, provider
policy, send denial, scoped restart and restart agreement. The first transaction
attempt failed at the browser onboarding modal and is preserved; the repaired
harness passed. The rehearsal root was a first release with no previous link, so
that transaction did not exercise automatic rollback.

Receipts:
`docs/acceptance/evidence/durable_assignment_20261029/release-integration-a96484324-transaction/`
(`deployment-receipt.json`, `auth-smoke/`, `assignment-before/after-restart.json`,
`fresh-before/after-restart.json`, `failed-attempt.json`, `evidence-manifest.json`).
Component-level mapping/fresh receipts remain under
`release-integration-a96484324-final/`.

## Production root and memory handoff

The prepared production root now exists at
`/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-29-a96484324`.
It contains the exact product release, the real `901e5d773` rollback release,
the authoritative SQLite/artifact handoff, and a read-only logical export of the
required LanceDB tables. The 7.23 GiB communication archive and 29.5 GiB
legacy `default_shared` workspace remain at the source and are explicitly
omitted; their historical email/context is not searchable in the production
copy. A logical freshness baseline (389 SQLite tables, memory versions and
referenced files) now guards the cutover, and 21 pre-existing missing
historical dataset paths remain visible as retrieval gaps with their affected
resources and retrieval consequence.

Preparation report:
`docs/acceptance/PRODUCTION_PACKAGE_PREPARATION_a96484324_2026-10-30.md`.

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
records that release as `previous`. The isolated first-release rehearsal root
had no previous link, so automatic rollback was not exercised there; the 19 kit
controls cover the failure path, and the earlier full C6 -> C4 -> C6 rehearsal
was on `901e5d773`, not production.

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
