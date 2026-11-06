# Agent 3 independent review — PR687 auth deep-link preservation

Reviewer: Agent 3 (independent verification), 2026-11-06. PR #687
(`codex/auth-relative-callback-20261106`, head `4620c76a1`), OPEN,
not draft, owner-authored, targeting `main`; merge-base with current main
`3925cf359` — clean 7-file diff, no drift. No evidence bundle accompanies
the PR; this review is the independent record. Recommendation to the lead;
owner review/merge authority remains separate.

## 1. User contract reviewed

A logged-out user hitting a protected deep link must return to that exact
path+query after signing in — and an attacker-supplied `callbackUrl` must
never leave the app. Chain: producers (auth middleware bounce, axios 401
interceptor, `handleSessionExpired`) hand `/login` a **relative**
`pathname+search`; the login consumers accept only same-app relative targets
(`startsWith('/') && !startsWith('//')`) and fall back to `/dashboard`
otherwise.

## 2. Change under review

- `middleware.ts`: unauthenticated bounce sets `callbackUrl` to
  `${request.nextUrl.pathname}${request.nextUrl.search}` instead of the
  absolute `request.url` (which the consumer guard refused — every deep link
  silently fell back to `/dashboard`; that is the repaired defect).
- `lib/auth-headers.ts`: new `loginCallbackPath()` (path+query only);
  `handleSessionExpired` uses it with injectable location/navigate; the
  `/login`-and-`/auth/` self-bounce guard unchanged.
- `lib/api.ts`: axios 401 interceptor uses `loginCallbackPath()`.
- `.github/workflows/ci.yml`: new jest regression gate over four suites.
- Tests: `tests/middleware.test.ts` (new, 4), `tests/lib/auth-headers.test.ts`
  (new, 5), `tests/pages/__tests__/login.test.tsx` (+1 relative-honored twin;
  existing external-URL and `//host` refusal twins retained).

## 3. Trace (consumers, parallel writers, shared callers)

- All three fixed producers verified on the head; **no absolute producer
  remains** for the `/login` surface (`git grep` for the old patterns: zero
  hits outside tests).
- Consumer guards confirmed present and identical on all three login
  surfaces: `pages/login.tsx:66`, `pages/auth/signup.tsx:60`,
  `pages/auth/signin.tsx:40`.
- Every `handleSessionExpired()` call site (IngestionStatusPanel,
  agents/index ×7) uses default arguments and inherits the fix.
- Social sign-in buttons hardcode `callbackUrl: '/dashboard'` — unaffected.
- Residual producer outside the PR:
  `pages/api/integrations/google-workspace/auth/start.ts:18` emits
  `req.url` toward `/auth/signin` — Node API-route `req.url` is path-relative,
  so the consumer guard honors it (returns to the flow start); observed, not
  a defect, unchanged by this PR.

## 4. Independent execution (Node v20.19.6, npm 10.8.2, fresh `npm ci` from lockfile in an isolated worktree)

- The PR's exact CI gate, once: **4 suites, 53/53 passed** in 4.2s.
- Agent 3 probe (genuinely missing case): the `/auth/signin` consumer guard
  had **no callbackUrl twins at all** — and it is the live return target of
  producers this PR does not touch (integration OAuth start/callback). Added
  `tests/auth/agent3-signin-callback-guard.test.tsx`: relative
  `/integrations/salesforce?step=2` honored; `//evil.example.com/phish`
  refused to `/dashboard`; `https://evil.example.com/phish` refused to
  `/dashboard`.
- Decisive combined gate, once: **5 suites, 56/56 passed** in 3.35s (log:
  `jest-gate-node20.log`).

One probe-authoring iteration (first draft clicked an ambiguous
`/sign in/i` role selector colliding with the social buttons; switched to
the `button[type="submit"]` selector) — harness error, corrected, no
product implication.

## 5. Exclusions (recorded, not certified)

- jsdom/MSW test environment: no real browser round-trip, real network or
  real NextAuth session is qualified — ordinary-browser journey evidence
  stays Agent 4's lane.
- `pages/auth/signup.tsx` has the same consumer guard but **no test file at
  all** (no signup page test exists in the tree). Recorded as a sibling
  observation for the lead; not added here — signup is not a return target
  of any producer touched by this PR.
- Middleware matcher configuration, session/token validation and the
  `/dashboard` fallback behavior are unchanged by this PR and out of scope.

## 6. Recommendation to the lead

**Accept PR687 at its tested scope** (subject to the owner's code-owner
review and merge): the deep-link chain reproduces end-to-end at the unit/
integration boundary on this runtime, the open-redirect twins hold at the
login consumer, and the one genuinely missing sibling guard (signin) is now
pinned by an added probe. Non-blocking follow-ups for lead ranking: a
signup-page guard twin (no test file exists), and the google-workspace
producer's `req.url` callback could be made explicit (`/integrations/...`)
for consistency.
