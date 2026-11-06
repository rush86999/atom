# First-run onboarding completion — evidence

Bounded setup/user-journey successor from merged main `6a7e85c6d`.
Source checkpoint: `163f6b336`.

## What this proves

Feature journeys suppress the onboarding modal so it cannot intercept page
interactions; that does not prove onboarding completes. This test drives the
real first-run wizard for a fresh user:

1. UI login as a newly registered user;
2. Welcome → Profile → Connect → Ready without configuring a live provider;
3. click **Start Automating**;
4. verify `onboarding_completed=true` and `onboarding_step=completed` through
   `GET /api/onboarding/status`;
5. reload and assert the wizard does not reopen and the user remains on the
   authenticated dashboard.

No product/onboarding behavior changed. No live model/provider was used.

## Hosted result (run 42230206708)

| Job | Result |
|---|---|
| `backend-tests` 127933844980 | **611 passed, 1 skipped**; memory recall 1.0 |
| `e2e-journey` 127933845205 | API **211 passed, 1 skipped, 1 xfailed**; UI block **29 passed** (28 prior + onboarding); role UI **40 passed**; zero failures |
| syntax, frontend typecheck, app boot, quickstart, Docker, GitGuardian | pass |

The onboarding node passed in the hosted non-gating UI block:
`tests/test_journey_onboarding.py .`

Logs: `hosted-e2e.log`, `hosted-backend.log`, `onboarding-test-excerpt.log`.

## Source hashes

| File | Git blob | SHA-256 |
|---|---|---|
| `backend/tests/e2e_ui/tests/test_journey_onboarding.py` | `1697d741f4b3ac2b4a30a7dd4df5783ab5772af9` | `3b7dc7c0f3d14a802cbe51ce6b891726610ffb685095f94e1b6bd99dda725735` |
| `.github/workflows/ci.yml` | `f658728dac230492e788ab4dc14ffa90993fa923` | `76d21c0e12460583b5baa0cab6a0f67e53c5a59843147533f927499ed4225263` |

Artifact hashes are in `verification.json`.

## Boundaries

- Onboarding completion is proven through the real wizard and durable status;
  provider connection/configuration remains separate and was not exercised.
- The test is in the non-gating UI block. It does not promote onboarding to a
  gating check or change existing required checks.
- No live model/provider/account, credential, spend, send, download or
  deployment operation was used.
