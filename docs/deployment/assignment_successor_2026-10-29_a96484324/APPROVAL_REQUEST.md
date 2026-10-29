# Deployment approval request — assignment successor a96484324

**Status:** READY FOR OWNER REVIEW. No production deployment is authorized or
running.

## What is being approved

Start one supervised single-user pilot from the frozen successor candidate:

- Audience: exactly `admin@example.com`; no other user.
- Product commit: `a9648432495f4f75f59bf4667cac3cb997d7f229`
- Release tag: `assignment-successor-2026-10-29-a96484324`
- Product tree SHA-256:
  `937d100838300c8ec703f5c8ee164f029acf4ecbe64d6a823bd994fa9070d8e6`
- Previous release / rollback target: `901e5d773` (tag
  `assignment-successor-2026-10-29`), preserved unchanged.
- Runtime: the prepared root built by
  `scripts/deployment/assignment_successor_2026-10-29_a96484324/prepare_release.py`.
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
  `docs/acceptance/evidence/durable_assignment_20261029/release-integration-a96484324/`.
- Package manifest:
  `docs/acceptance/assignment-successor-package-2026-10-29-a96484324/assignment_successor_manifest.json`.
- Deployment/rollback runbook:
  `docs/deployment/assignment_successor_2026-10-29_a96484324/DEPLOYMENT_RUNBOOK.md`.

## Gates that remain closed

1. `config/APPROVED` is absent. Production start/deploy refuses without the
   exact approval record.
2. Real-provider email sending remains unauthorized and must be tested
   separately with an approved recipient, exact payload, provider receipt,
   reconciliation and restart/no-duplicate checks.
3. No production deployment, credential change or source writeback is
   authorized here.

## Approval statement

Approver: ______________________  Date: ______________

I approve a supervised single-user deployment of the exact identity above,
with the recorded backup, rollback target, draft-only outbound policy and
limitations. Real-provider sending is not approved.

Signature / recorded approval: ______________________________

Create `config/APPROVED` with the same identity and date to enable deployment.
