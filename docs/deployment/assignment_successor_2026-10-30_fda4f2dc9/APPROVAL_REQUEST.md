# Deployment approval request — assignment successor fda4f2dc9

**Status:** READY FOR OWNER REVIEW. No production deployment is authorized or
running.

## What is being approved

Start one supervised single-user pilot from the frozen successor candidate:

- Audience: exactly `admin@example.com`; no other user.
- Product commit: `fda4f2dc9376f20a6e10de6d7d1e55cf16eeffd4`
- Release tag: `assignment-successor-2026-10-30-fda4f2dc9`
- Product tree SHA-256:
  `92924cd8f8f3cffa8e884a9a7fecc5f820f4f5ce8acbba60fdd257975df614fa`
- Source shutdown scope: verified PID `19046` (`atom-c912375de`, CWD
  `atom-releases/c912375de/backend`, source DB
  `atom/backend/data/atom.db`, port `8001`, no supervisor). The approval record
  must include the exact `source_shutdown_scope` from
  `config/source_shutdown_scope.json`; see
  `docs/acceptance/SOURCE_SERVICE_SHUTDOWN_SCOPE_fda4f2dc9.md`.
- Previous release / rollback target: `901e5d773` (tag
  `assignment-successor-2026-10-29`), preserved unchanged.
- Runtime: the prepared root built by
  `scripts/deployment/assignment_successor_2026-10-30_fda4f2dc9/prepare_release.py`.
- Ports: backend `127.0.0.1:8071`, frontend `127.0.0.1:3130`.
- Outbound scope: draft-and-approval only. Real-provider sending is **not**
  authorized by this request.

## Evidence supplied

- Four browser flows on the frozen product: workbook B `35.00`, workbook C
  `75.00`, correction `100.00 -> 80.00`, reject/restart/confirm `35.00`.
- Authority controls: 5 focused route tests; 98 affected regressions.
- Packaged smoke: existing taught assignment + artifact reopen, mapping flow,
  DeepSeek provider policy, draft-only send denial, restart agreement.
- Isolated preflight, verified backup, startup receipt and final health:
  `docs/acceptance/evidence/durable_assignment_20261029/release-integration-fda4f2dc9/`.
- Package manifest:
  `docs/acceptance/assignment-successor-package-2026-10-29-fda4f2dc9/assignment_successor_manifest.json`.
- Deployment/rollback runbook:
  `docs/deployment/assignment_successor_2026-10-30_fda4f2dc9/DEPLOYMENT_RUNBOOK.md`.

## Gates that remain closed

1. `config/APPROVED` is absent. Production start/deploy refuses without the
   exact approval record.
2. Real-provider email sending remains unauthorized and must be tested
   separately with an approved recipient, exact payload, provider receipt,
   reconciliation and restart/no-duplicate checks.
3. No production deployment, credential change or source writeback is
   authorized here.

## Complete operation

This approval covers: verify PID `19046`; stop only that verified source
service; prove quiescence; refresh data/memory while quiescent; deploy exact
`fda4f2dc9`; run fresh authenticated work, restart agreement and rollback
verification; and on failure restore the exact source service configuration
(not merely start rollback code). The source stop is not authorized until the
owner also approves the shutdown scope.

## Approval statement

Approver: ______________________  Date: ______________

I approve a supervised single-user deployment of the exact identity above,
with the recorded backup, rollback target, draft-only outbound policy and
limitations. Real-provider sending is not approved.

Signature / recorded approval: ______________________________

Create `config/APPROVED` with the same identity and date to enable deployment.
