# PR #664 non-gating UI journey repair

Status: **submitted for independent verification.** This closes the 12
non-gating UI failures recorded on the accepted PR #664 capture and the
separate eight role-UI copies of the same dashboard expectation.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/pr659-backend-ci-fix-20261105` |
| Accepted PR #664 head | `d17acd1d5` |
| First UI fixture commit | `437302cff` |
| Exact-scope/role follow-up | `83dc39c458a9fe4cb60d8e24cfd3f5fbe4ba25f8` |
| Observed CI | run `42161362480`, job `127707566246` |
| Final CI | run `42209447032`, job `127864183212` |
| Runtime | real backend + Next.js dev server in hosted e2e; no live model/provider/account operation |

## Failure families

| Family | Nodes | Cause | Fix |
|---|---|---|---|
| Dashboard copy | dashboard smoke, canonical journey, 8 role-UI | page copy is now `Your workspace` with the stable `dashboard-welcome-message` testid | assertions use the current copy; testid remains primary |
| Chat composer | 2 chat UI tests | composer changed from `input` to `textarea` | query textarea with input fallback |
| Core profile deferred surfaces | marketplace, builder, projects, integrations feature tests; 3 smoke routes | core release deliberately renders `NotInRelease` for deferred capabilities | read the real `/api/product/profile`; assert the exact `<label> is not part of this release` page when deferred, retain feature heading/search/name assertions when enabled |
| First-run onboarding | settings theme | global onboarding modal intercepted the theme control | suppress the modal only in feature-journey fixtures via `sessionStorage`; no onboarding/product change |

No route, role, permission or capability was broadened. No assertion was
deleted: each surface asserts either its real feature contract (full profile)
or its exact deferred-scope contract (core profile).

## Verification

| Gate | Before | After |
|---|---|---|
| `test_journey_ui_features.py` + page smoke + canonical journey | **12 failed, 16 passed** | **28 passed** |
| Role-UI shared pages | 8 failed (same dashboard copy) | **40 passed** |
| Gating API journey | 211 passed, 1 skipped, 1 xfailed | **211 passed, 1 skipped, 1 xfailed** |
| `backend-tests` | 606 passed, 1 skipped | **pass 5m29s** |
| All required checks | — | **pass** (syntax, frontend, boot, quickstart, Docker, GitGuardian, e2e) |

The final e2e job is green with zero failures in both non-gating blocks.

## Boundaries

- No production UI behavior changed; only test fixtures/page objects and
  assertions.
- No onboarding, product profile, RBAC or skill authority change.
- No live model/provider/browser account, credential, spend, send, download
  or deployment operation.
- No merge or deployment; PR #664 remains open for code-owner review.
