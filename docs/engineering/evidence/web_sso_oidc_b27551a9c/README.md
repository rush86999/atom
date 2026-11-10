# Full-app SSO web handoff browser proof — b27551a9c

## Identity

- Candidate source: `b27551a9cb78ca080e97d4e8955bef49a1e220e3`
  (clean candidate; **not** main, not a merge/push/deploy claim)
- Verified task durability implementation carried in the candidate:
  `f5a2413ce07bfd180b64ca58d861f9b9898cb9a5`
- Referrer-policy repair verified independently by root at successor
  `86053d3a70627065784819a41273939775c65e1c`
- Executed harness: `browser_sso_oidc.py`,
  sha256 `5228fb27ab7acc6dcd74ff0608c04e641ba4c129524630268978daac8fd75bb4`
  (packet bytes = executed bytes)
- Build: optimized Next `16.2.2`, Node `v20.20.2`, build id
  `gUNpk4hsJ2bFpZNTMyvcD`, exit `0`, `27.0s`
- Runtime: production build over **HTTP loopback only** —
  `localhost:18371` frontend, `127.0.0.1:18370` backend,
  `127.0.0.1:18372` controlled OIDC issuer.
- No TLS, production-environment, live identity-provider or deployed-transport
  claim is made.

## What was exercised

One ordinary controlled-loopback OIDC browser episode, with no product edits:

1. Fresh isolated browser context: cookies and local/session storage empty
   before app bootstrap.
2. Normal admin bootstrap/login (`200`, role `workspace_admin`).
3. The admin config API correctly returned `403` for `workspace_admin`
   (`Permission.SYSTEM_ADMIN` policy boundary). No role/status/onboarding
   grant, database write, cookie injection or mocked auth handler was used.
   The supported single-tenant environment OIDC settings
   (`ATOM_OIDC_ISSUER` / `CLIENT_ID` / `CLIENT_SECRET` / `ENABLED`) were the
   first-class configuration path.
4. UI `/login?callbackUrl=%2Fsettings%3Fsso%3Dverified` → one SSO button
   click → real backend `302` web login → real controlled issuer
   `/authorize` → real web callback `302` → opaque handoff landing →
   same-origin `POST` exchange with real `Origin` and browser cookie →
   installed NextAuth SDK credentials bridge → same canonical backend User →
   exact `/settings?sso=verified`.
5. The callback code was removed from the visible URL before the exchange.
   No bearer appeared in the URL or HTML.
6. Settings was reloaded and kept the exact path/query.

The issuer is the repository's controlled provider with PKCE S256 checked
in-process. No live provider, account, consent, model, SMTP send, spend or
deployment action was used.

## Restart extension (actual, gated)

The owned controlled issuer's real `/authorize` `302` was gated **before the
response was written** (not a mocked/fake response). While the browser waited,
only the owned backend was stopped and relaunched on the same world, source
and environment. The gate was then released and the actual callback/exchange
continued.

- `issuer_gate_entered_before_302`: true
- `issuer_gate_released_after_restart`: true
- `restart_health`: true
- `restart_extension_ok`: true
- `exchange_after_restart`: true
- old backend pid `67598` → new backend pid `67682`, old process terminal,
  restart attempt `1`
- `restart_gap`: false

Root independently re-read the old/new restart pid, `old_terminal`, health
and the single post-restart exchange. The `restart.gate` snapshot in
`verification.json` was copied immediately after the release signal, before
the issuer thread wrote `released=true`; the later
`issuer_gate_released_after_restart` check and the completed exchange are the
authoritative release evidence.

## Boundary results — 31 checks, all true

The exact matrix is in `boundary_checks.json`. Count: **31** (not 32); every
value is `true`. The matrix covers:

- canonical `/me` / NextAuth session / decoded SDK / DB id agreement and one
  canonical SSO user;
- encrypted SDK session cookie (not the raw bearer) with the same backend
  generation;
- exact Settings path/query before and after reload;
- callback code removed before the exchange, no bearer in URL/HTML;
- one exchange, one SDK callback, one issuer authorize, one issuer token,
  zero browser password logins;
- 31st control `restart_extension_ok` true;
- zero browser password logins;
- header and configuration controls below.

## Sensitive response headers

Observed on the actual browser events (method/path/status keyed, independent of
the route object):

| Response | Status | Cache-Control | Referrer-Policy |
|---|---|---|---|
| `GET /api/auth/sso/oidc/web/callback` | 302 | `no-store` | `no-referrer` |
| `GET /auth/sso/callback` (landing document) | 200 | `no-store` | `no-referrer` |
| `POST /api/auth/sso/oidc/web/exchange` | 200 | `no-store` | `no-referrer` |

The backend callback/exchange headers come from `api.sso_oidc_routes`. The
landing document headers come from the existing frontend middleware. The
shared security-header middleware now preserves the explicitly stricter
`no-referrer` instead of overwriting it (root-verified at `86053d3a7`).

## Session, cookie and database

- Cookie: `__Secure-next-auth.session-token`, one chunk, HttpOnly, Secure,
  SameSite `Lax`, host-only, 5-segment JWE; value is not the raw 3-segment
  backend JWT; transport is HTTP loopback (no TLS claim).
- `/api/auth/session` and `/api/auth/me` both returned `200`; their user id
  matched each other, the decoded SDK id and the single DB row.
- Read-only SQL confirmed exactly **one** SSO account with
  `hashed_password IS NULL` (column is `hashed_password`, not
  `password_hash`), role `member`, status `active`, tenant present, and no
  NextAuth adapter tables.
- Total scratch users: 2 (bootstrap admin + one JIT SSO user).

## Logout

All four controls true: SDK cookie absent, raw compatibility token absent,
`/api/auth/session` user absent, explicit logout marker present. No hidden
token fallback.

## Root independent header test

At `86053d3a70627065784819a41273939775c65e1c`, root independently ran the
referrer-policy controls with the normal repository conftest:
**37 selected / 37 passed, 120 deselected**. Summary in
`root_header_test_summary.json`; the raw log stays on the private path named
there and is not published.

## Root merged-source integration gate

On candidate `b27551a9cb78ca080e97d4e8955bef49a1e220e3`, root also ran the
combined auth/task selection under the normal repository conftest with an
isolated scratch database:

**65 passed, 0 failed, 120 deselected, 378 warnings, 44.47s, exit 0.**

`source_before == source_after` (the run did not change source). The selection
includes 35 Referrer-Policy cases, 2 real-router SSO header controls and 28
durable task tests. Summary: `root_integration_gate_summary.json`; the exact
private command/result and tests log remain private and are named there.

## Mechanical harness self-test / probe

`mechanical_selftest/capture_selftest.py` is the no-browser harness check.
Its recorded result (`mechanical_selftest/result.json`) proves:

- the atomic failure checkpoint keeps the full True/False/None matrix,
  failure/unknown names, safe URL key names, header records, navigation and
  screenshot reference;
- header capture is keyed by method/path/status, so redirect/landing
  responses cannot be silently dropped and a missing record is `None`, never
  a false product claim;
- the owned issuer really withholds its `/authorize` `302` until the gate is
  released, then sends the unchanged real `302` with a real authorization
  code.

No browser is launched by this self-test.

## Exact source manifest

`MANIFEST.json` records the candidate-bound SHA-256 of every product source
file the proof depends on (the two security-header variants and shared helper,
the SSO route, controlled provider, auth/database/models/config, the SSO
tests, the frontend callback/login/SSO helper/middleware, and Next config).
All packet artifacts are Git-tracked in this directory; no canonical artifact
is omitted as ignored.

## Preserved history and baseline discipline

- The earlier negative SSO worlds remain distinct and preserved:
  `/private/tmp/root-web-sso-oidc-world-6ajr8f6j` (v1 callback URL loss),
  `/private/tmp/root-web-sso-oidc-world-1y0gecfl` (v2 Settings reached,
  truncated diagnostic), and
  `/private/tmp/root-web-sso-oidc-world-5wfunhu6` (v3 full matrix with the
  genuine exchange `Referrer-Policy` defect).
- The source-134 functional positives (Settings/reload, canonical ids,
  encrypted SDK, one exchange/token, zero password logins) are **not**
  relabelled or erased by this later candidate proof.
- The post-commit stash push/pop incident was **not** a valid baseline and is
  excluded from every claim here. This packet makes no worker baseline claim;
  root owns pre-fix baseline qualification.
- Historical scope is unchanged: **143** claim identities, **18** goal-map
  rows, app not declared complete.

## Testing disclosure

- Scratch runtime `TESTING=1` with explicit `DATABASE_URL` and
  `ATOM_DATA_DIR` in a private `0700` world.
- `TESTING=0` was set only for the `main_api_app` import phase so the
  explicit fresh scratch database was honored; `TESTING=1` was restored
  before serving. This is a harness necessity, not a production claim.
- No live database was read or written.

## Screenshots

Four UI-state screenshots are included. They were inspected: no token, code,
state, password or cookie value is visible. The Settings screenshots show the
synthetic display name and a **truncated** email prefix
(`sso-web-20261109215...`); the full random identity is not published.

## Private evidence

Raw logs, backend/frontend environments, the scratch database, cookies,
tokens, codes and state remain in the private `0700` world:

- `/private/tmp/root-web-sso-oidc-world-3c0erbp_`

The root review artifact is copied as `root_independent_review.json`. No raw
HAR, environment, DB, auth log, cookie value or token is published.

## Limits

- HTTP loopback only; no TLS or deployed production transport.
- Controlled local OIDC issuer, not a live IdP/consent.
- One controlled SSO user boundary; not general SSO, PostgreSQL concurrency,
  soak, multi-tenant SaaS or app completion.
- Task durability evidence remains its own controlled API/service packet
  (`web_chat_task_durability_f5a2413ce`); this browser packet does not turn it
  into a Tasks browser acceptance.
- No model/provider, send, spend, install, deployment, PR, merge or push is
  part of this packet.
