# Web authentication browser episode

## Source and build identity

- Frozen product source: `3673b07bfc28a9541237a5bebe085c49ad6155ba`
- Executed app bytes: Next `16.2.2`, Node `v20.20.2`, build id `x2CUoJu61foFf1UK93q73`
- Build command: existing heavy gate -> `next build`, exit `0`, duration `30.0s`
- Runtime: production build served over explicit HTTP loopback (`localhost:18321` frontend, `127.0.0.1:18320` backend). No TLS/production-environment claim.
- Harness executed: `browser_auth_episode.py`, sha256 `a69af452759cdbf6d341821ef134ac9d657ecb7c4fe198e7188dce04d346e849`
- No product code was edited for this packet.

## Harness successor

The first private harness (`0f1916c876055b60b23904d0b91db9ec0027d17a8f2522e2eb69122ad206b7fe`) failed after the deep-link redirect because it discarded the captured `callbackUrl` and signed in at `/login` without that query. That is a harness defect, not a product failure. Its public failure record and private world are retained outside the repo:

- `/private/tmp/root-web-auth-browser-harness-v1-failed-20261109`
- `/private/tmp/root-web-auth-browser-world-20261109-dq_jw2j7`

The corrected successor `a69af452759cdbf6d341821ef134ac9d657ecb7c4fe198e7188dce04d346e849` passed and is the harness in this packet. Root-reviewed harness fixes: pass the captured callback into the deep-link sign-in, compare Secure against cookie/config rather than assuming false on HTTP, and use real `COUNT(*)`/stable IDs for duplicate detection.

## Command actually run

```text
python3 /private/tmp/root-web-auth-browser-harness-20261109.py
exit 0
```

The harness invoked the existing heavy gate for `next build` and installed Chrome `156.0.8078.80`.

2FA was not exercised live. Existing 2FA/twin suites were run instead:

```text
bounded gate -> jest tests/auth/test-signin.test.tsx tests/pages/__tests__/login.test.tsx
edge: 55/55 passed, exit 0
```

## Required boundary results

- Fresh isolated browser context: cookies, localStorage and sessionStorage all empty before UI registration.
- UI registration at `/auth/signup`: one backend `POST /api/auth/register`, one NextAuth credentials callback, landed `/dashboard`; scratch DB rows before `0`, after `1`.
- Onboarding completed through visible UI controls only; `POST /api/onboarding/update` 200; scratch DB `onboarding_completed=true`, `onboarding_step=completed`.
- Protected Settings: exact URL `/settings?a4dl=return20261109` before and after reload.
- SDK session cookie: `__Secure-next-auth.session-token`, HttpOnly, Secure, SameSite=Lax, host-only, one chunk, 5-segment JWE; value was not the raw 3-segment backend JWT.
- Canonical IDs: `/api/auth/me` id, `/api/auth/session` id, and SDK-decoded id agreed; SDK session backend generation matched the raw backend generation privately; legacy `auth_token` cookie was present but not counted as the SDK session.
- UI logout: SDK cookie cleared, `/api/auth/session` returned no user, raw token cleared, explicit logout marker set.
- Same-account UI sign-in through `/login` (default) and `/auth/signin` (default): each performed exactly one backend `POST /api/auth/login` and one SDK callback; both reached `/dashboard`.
- Deep link: unauthenticated `/settings?a4dl=return20261109` redirected to `/login?callbackUrl=...`; login landed exactly `/settings?a4dl=return20261109`.
- Scratch DB: exactly one synthetic user row, same ID as registration; duplicate rows `0`.
- Browser network: `777` requests, external requests aborted `0`, failed `27`, console errors `16`, page errors `0`.
- Backend login count was exactly `3` for the three UI sign-ins; no second password login was used to bridge the SDK. Registration used one register call and one SDK callback.

## Testing disclosure

`TESTING=1` was the runtime value with a fixed scratch `DATABASE_URL` and `ATOM_DATA_DIR`. The wrapper imported `main_api_app` with `TESTING=0` only for that import so the explicit fresh scratch database was honored; `core.database` would otherwise force the shared `backend/test_integration.db`. It restored `TESTING=1` before serving. This is a harness necessity, not a production-environment claim.

## Screenshots

Seven screenshots are in `screenshots/`. They are UI states only. The Settings screenshot before reload and after deep-link login are identical (`04-settings.png` and `07-deep-link-settings.png`).

## Private evidence

Raw logs, environment, DB, tokens, account credentials and private comparisons stay in 0700 scratch worlds with 0600 files:

- `/private/tmp/root-web-auth-browser-world-20261109-tqz_li_m`
- `/private/tmp/root-web-auth-browser-world-20261109-dq_jw2j7` (harness-v1 failure)
- `/private/tmp/root-web-auth-browser-harness-v1-failed-20261109`

No raw logs, env, DB, cookie/token values, passwords, auth codes/state or private cookies are committed or printed here.

## Limits

- HTTP loopback only; Chromium accepts the Secure cookie on loopback, but this packet does not claim HTTPS/production transport.
- Google/GitHub/SSO handoff and live 2FA were not exercised.
- No provider/model calls, connector consent, sends, spend or deployment.
