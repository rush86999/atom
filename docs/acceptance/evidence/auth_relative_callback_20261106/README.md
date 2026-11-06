# Login-return callback repair — code/test evidence

Bounded repair of the captured deep-link loss. Source: `aa731a9f5` (PR #687,
merged as `aadb75ec1`). Base main: `66e09c5ee`.

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

| File | Git blob (short) |
|---|---|
| `frontend-nextjs/middleware.ts` | `caddad965600` |
| `frontend-nextjs/lib/auth-headers.ts` | `8e816b3a0917` |
| `frontend-nextjs/lib/api.ts` | `08aa4af2c945` |
| `frontend-nextjs/pages/auth/signin.tsx` | `29c31972ce90` |
| `frontend-nextjs/tests/middleware.test.ts` | `39863b87e3ef` |
| `frontend-nextjs/tests/lib/auth-headers.test.ts` | `6d4902f05c48` |
| `frontend-nextjs/tests/pages/__tests__/login.test.tsx` | `6189142c3368` |
| `frontend-nextjs/tests/auth/test-signin.test.tsx` | `529c0cc5998b` |
| `.github/workflows/ci.yml` | `a2cbb33a30c3` |

Short Git blob prefixes are recorded; the full blob is resolvable from the
source commit and path (`git rev-parse <commit>:<path>`). Long hex strings are
intentionally omitted because GitGuardian's `Generic High Entropy Secret`
detector false-positived on the earlier artifact hashes; those were content
hashes, not credentials.

Artifact short blob IDs are in `verification.json`.

## Boundaries

- Unit/component and hosted frontend-job evidence, not a second browser
  acceptance. Agent 4's captured-chain verification is the user-boundary
  record; no browser rerun is needed for this packaging-only correction.
- No live provider/model/account, credential, SSO, production-world or
  deployment action; local paths/ports stay `localhost:3000`.
- The open-redirect guard and all auth/profile/role gates are unchanged.
