# Login-return callback repair — code/test evidence

Bounded repair of the captured deep-link loss. Source: `aa731a9f5` (PR #687).
Base main: `66e09c5ee`.

## Captured defect

Agent 4's accepted baseline (`/settings?a4dl=return20261106`) recorded:

1. unauthenticated protected destination → `/login` with an **absolute**
   `callbackUrl`;
2. same-account login → `/dashboard`, not the intended Settings page.

The login/signin/signup pages accept only same-app relative targets
(`/path?query`, never `//host`), so the absolute value was correctly rejected
by the consumer guard and the deep link was lost.

## Repair

All redirect producers and the `/auth/signin` consumers now emit the safe
relative target; the consumer guard, profile/role gates and authentication
transport are unchanged.

- `frontend-nextjs/middleware.ts`: `request.nextUrl.pathname + request.nextUrl.search`.
- `frontend-nextjs/lib/auth-headers.ts`: shared `loginCallbackPath()` =
  `pathname + search`, used by `handleSessionExpired`.
- `frontend-nextjs/lib/api.ts`: axios 401 interceptor uses the same helper.
- `frontend-nextjs/pages/auth/signin.tsx`: the password form, Google/GitHub
  buttons and existing-session redirect share the same open-redirect-safe
  `safeDest`.

## Gates

| Gate | Result |
|---|---|
| Gated auth command (middleware, helper, login, signin) | **59 passed** |
| Full auth Jest suite | **179 passed** |
| `npx tsc --noEmit` | clean |
| Hosted frontend-typecheck job 128089878538 | **59 passed** in the four gated suites |
| PR #687 hosted backend, syntax, boot, quickstart, e2e, Docker, GitGuardian | all pass at `aa731a9f5` |

Twins covered:

- captured `/settings?a4dl=return20261106` survives middleware → `/login`,
  `/auth/signin` password, Google, GitHub and the existing-session redirect;
- `/workflows/123?tab=steps` survives;
- default `/dashboard` still reaches `/dashboard`;
- `https://evil.example.com/...` and `//evil.example.com/...` still fall back
  to `/dashboard`;
- session-expiry bounce preserves the relative deep link;
- auth pages do not loop.

Logs: `local-auth-gated.log`, `local-auth-suite.log`, `local-typecheck.log`,
`hosted-frontend-typecheck.log`.

## Source identities

| File | Git blob |
|---|---|
| `frontend-nextjs/middleware.ts` | `caddad96560023e7c49e2cbea94c92a83d2c34a4` |
| `frontend-nextjs/lib/auth-headers.ts` | `8e816b3a09179bbfc379d3e11e7603e9b1e598b4` |
| `frontend-nextjs/lib/api.ts` | `08aa4af2c94528991b2efb7a07c9fa6c7b17e0f0` |
| `frontend-nextjs/pages/auth/signin.tsx` | `29c31972ce90a22e478a633a6c9e106556dd62ae` |
| `frontend-nextjs/tests/middleware.test.ts` | `39863b87e3ef77ae22b57c261b9242677cf5f5ce` |
| `frontend-nextjs/tests/lib/auth-headers.test.ts` | `6d4902f05c48b110c0baf65afcc245ee3a806220` |
| `frontend-nextjs/tests/pages/__tests__/login.test.tsx` | `6189142c3368d3dba0e8a0edbb0c102f85243f14` |
| `frontend-nextjs/tests/auth/test-signin.test.tsx` | `529c0cc5998b40241217c89b4331619568313453` |
| `.github/workflows/ci.yml` | `a2cbb33a30c30e2111b8506908000f40641ab2b8` |

Git blob IDs are the content identity. The 64-character SHA-256 strings are
intentionally not repeated in this packet: they are recomputable from the
committed blob and were the source of the `Generic High Entropy Secret`
false positive in the superseded evidence PR #690.

Artifact Git blob IDs are in `verification.json`.

## Boundaries

- Unit/component and hosted frontend-job evidence, not a second browser
  acceptance. Agent 4's captured-chain verification is the user-boundary
  record; no browser rerun is needed for this packaging-only correction.
- No live provider/model/account, credential, SSO, production-world or
  deployment action; local paths/ports stay `localhost:3000`.
- The open-redirect guard and all auth/profile/role gates are unchanged.
