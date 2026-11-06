# Login-return callback repair — code/test evidence

Bounded repair of the captured deep-link loss. Source: `265610524` (PR #687).
Base main: `ace04c8b9`.

## Captured defect

Agent 4's accepted baseline (`/settings?a4dl=return20261106`) recorded:

1. unauthenticated protected destination → `/login` with an **absolute**
   `callbackUrl`;
2. same-account login → `/dashboard`, not the intended Settings page.

The login/signin/signup pages accept only same-app relative targets
(`/path?query`, never `//host`), so the absolute value was correctly rejected
by the consumer guard and the deep link was lost.

## Repair

Three producers now emit the safe relative target; the consumer guard,
profile/role gates and authentication transport are unchanged.

- `frontend-nextjs/middleware.ts`: `request.nextUrl.pathname + request.nextUrl.search`.
- `frontend-nextjs/lib/auth-headers.ts`: shared `loginCallbackPath()` =
  `pathname + search`, used by `handleSessionExpired`.
- `frontend-nextjs/lib/api.ts`: axios 401 interceptor uses the same helper.

## Gates

| Gate | Result |
|---|---|
| Gated auth command (middleware, helper, login, signin) | **56 passed** |
| Full auth Jest suite | **176 passed** |
| `npx tsc --noEmit` | clean |
| Hosted frontend-typecheck job 128084228917 | **56 passed** in the four gated suites |
| Hosted backend, syntax, boot, quickstart, GitGuardian | pass |
| Hosted e2e-journey / Docker | still running at capture; the CI worker owns terminal tracking |

Twins covered:

- captured `/settings?a4dl=return20261106` survives middleware → `/login`
  and `/auth/signin` as a relative path+query;
- `/workflows/123?tab=steps` survives;
- default `/dashboard` still reaches `/dashboard`;
- `https://evil.example.com/...` and `//evil.example.com/...` still fall back
  to `/dashboard`;
- session-expiry bounce preserves the relative deep link;
- auth pages do not loop.

Logs: `local-auth-gated.log`, `local-auth-suite.log`, `local-typecheck.log`,
`hosted-frontend-typecheck.log`.

## Source hashes

| File | Git blob | SHA-256 |
|---|---|---|
| `frontend-nextjs/middleware.ts` | `caddad96560023e7c49e2cbea94c92a83d2c34a4` | `c493975745364ca2a9ca156d163dca77dcab43fdaf2e280647ddfa1af34c42ec` |
| `frontend-nextjs/lib/auth-headers.ts` | `8e816b3a09179bbfc379d3e11e7603e9b1e598b4` | `ec2b9f540b383f5004fae47e473f7cfe568adb5c8bdb14a615498df76cbe9e78` |
| `frontend-nextjs/lib/api.ts` | `08aa4af2c94528991b2efb7a07c9fa6c7b17e0f0` | `c4add7af70fadb435c3cc664ab33a5169fead0a935c5f4276330b5133cb25782` |
| `frontend-nextjs/tests/middleware.test.ts` | `39863b87e3ef77ae22b57c261b9242677cf5f5ce` | `337ebd24e61ff0d5eb517098c12dd38666ffd8e768a4883fc2e496e31914f711` |
| `frontend-nextjs/tests/lib/auth-headers.test.ts` | `6d4902f05c48b110c0baf65afcc245ee3a806220` | `291713059a1aa5df5712ba05b36e911bff2ffd4c76f44958780f7e3a88c46f54` |
| `frontend-nextjs/tests/pages/__tests__/login.test.tsx` | `6189142c3368d3dba0e8a0edbb0c102f85243f14` | `0726e6fe30b73c051fd564f0bc94fb98d7273c307cec5ed80d40fdf86d8f10b3` |
| `frontend-nextjs/tests/auth/test-signin.test.tsx` | `32f06d7002f2863e64f1d413ef4161520c59e44e` | `3791e434bc94b9d2cd89094f27d64aa7c2de62b32117bc9bfd4981d4546f7419` |
| `.github/workflows/ci.yml` | `a2cbb33a30c30e2111b8506908000f40641ab2b8` | `7ee9ce376740ad9c39a3a67d6af67f128e0d4dd03b2f7bbd5eade59bbe36dd8d` |

Artifact hashes are in `verification.json`.

## Boundaries

- Unit/component and hosted frontend-job evidence, not a second browser
  acceptance. Agent 4 owns the captured chain's final user-boundary run and
  records the final URL plus same-account identity.
- No live provider/model/account, credential, SSO, production-world or
  deployment action; local paths/ports stay `localhost:3000`.
- The open-redirect guard and all auth/profile/role gates are unchanged.
