# WA-075 — Signed-in settings acceptance

**Status: superseded — 29/29 checks pass on clean
`a53b56fdc32bd1447a7fe5285efee8f1be20a409` (2026-11-14).** The harness was
implemented and first replayed on the isolated scratch world on 2026-11-13:
25 checks passed, 2 capabilities were genuinely absent in that build (sessions
list, 2FA enable/disable routing), and 1 derived check was skipped because
there was no session row to revoke — exit `3`. After the 2FA routing fix, the
same-day re-run passed 27 checks with the Sessions gap still open — exit `3`.
The superseding capture (run `wa075-20261114070119-89e3cb`) passed all 29
checks with no `missing` or `skipped` entries; see §8. The 2026-11-13 sections
are retained as history. Evidence is kept outside the repository (private);
this document records the method, the observed results and the non-claims, not
the raw capture.

Ledger item (unchanged by this document — both ledgers are generated):

> `WA-075 · platform · Open Account/AI/Sessions/Routing/Local Models settings ·
> partial · No setting was saved and reloaded. · Save and restore one
> preference per tab.`

The 2026-11-14 result in §8 — every tab saved and restored a preference — is
the evidence that resolves the `partial` reason; the generated ledger row is
not edited here.

---

## 1. What this proves (and what it does not)

The acceptance boundary is the **browser a signed-in operator uses**. Each
check is one visible control plus the durable effect it claims, read back
through the public API:

| Tab | Reversible control / real data | Proof |
|---|---|---|
| Account | password rotation | save through the form, forced re-auth, old credential rejected, new credential accepted, tab reloads, original password restored and verified |
| Account | 2FA surface | status read + reachability of the tab's setup call; full enable→reload→disable round trip only with `--exercise-2fa` |
| AI | provider routing policy | save a policy, reload, compare UI state and `GET /api/ai/provider-policy`, restore the captured baseline |
| Sessions | disposable secondary session | second browser signs in through the real form; the tab must list both live sign-ins and revoke the disposable one |
| Routing | real telemetry | `GET /api/chat/routing-stats` payload must equal the rendered numbers; Refresh must fetch again; empty telemetry must stay empty |
| Local Models | disposable provider | register through the form at an RFC 2606 `.invalid` host, survive reload, delete, provider set returns to baseline; the provider is never contacted |

Design note: the backend rejects loopback/private `base_url` values
(`backend/api/routes/local_model_routes.py:106-121`), so the disposable
fixture is a DNS name under `.invalid` rather than `127.0.0.1`. Discover and
Test are never clicked; the run asserts zero requests to that host.

Non-claims:

- No live database, live credential, external model provider, chat/completion,
  Discover, Test or provider probe is used. The only egress permitted is the
  scratch frontend/backend origins; a `.invalid` host is registered but never
  contacted.
- Routing telemetry is not seeded. A scratch world with no feedback samples
  legitimately shows `0`, and that is recorded as `telemetry_empty: true`, not
  as a product win.
- Local Models proves registration/persistence/deletion, not model quality or
  Ollama availability.
- The 2FA round trip and the password rotation write real state to the scratch
  world. They are bounded and restored; the world remains disposable.

Status vocabulary per check:

| status | meaning |
|---|---|
| `pass` | proven at the user boundary |
| `fail` | the product contradicted the check |
| `missing` | the capability is absent in this build; exact HTTP/status/text recorded |
| `skipped` | a precondition (role band, operator flag) was not met, with the reason |

Exit codes: `0` all pass · `1` at least one `fail` · `2` fatal (world/auth
unreachable, identity unverified, or a secret would have been persisted) · `3`
no failures but at least one `missing` · `4` no failures but a required check
was `skipped` (the capture is incomplete).

---

## 2. Reuse (no new engine)

| Piece | Role |
|---|---|
| `scripts/acceptance/browser_core_surface.mjs` | the established world contract: `ATOM_FRONTEND_URL` / `ATOM_BACKEND_URL`, scratch login, installed Chrome, frontend-wait retry, error collection |
| `scripts/acceptance/lib/core_surface_session.mjs` | those primitives extracted verbatim; `browser_core_surface.mjs` keeps its behaviour and now imports them |
| `scripts/acceptance/browser_settings_acceptance.mjs` | **new** WA-075 driver (Playwright, no dependencies beyond the workspace's own Playwright) |
| `scripts/acceptance/lib/settings_contract.mjs` | **new** pure helpers (RFC 6238 TOTP, policy normalization, routing-stat normalization) unit-tested without a browser |
| `scripts/acceptance/browser_settings_preflight.py` | **new** preflight/refusal report; launches nothing, writes only `--report` |
| `scripts/acceptance/launch_integrated_local_candidate.sh` | unchanged; the supported way to serve the scratch world (validates the world path, runs `core.world_storage_guard`, `storage_policy space`, then starts backend + built frontend and verifies the serving identity) |
| `scripts/acceptance/validate_local_world.py` | world/live-DB/port/space contract used by both the launcher and the preflight |
| `core.world_storage_guard` | worlds-root volume/layout preflight and maintenance interlock; bypass is refused |
| `scripts/acceptance/scratch_admin_password.py` | recovery helper if a password rotation is interrupted; now accepts any `<world>/atom.db` under the configured worlds root and still refuses the live DB |

No shell launcher of its own: WA-075 uses the existing integrated-local
launcher so the world identity, marker, pid safety and health-identity checks
stay in one place.

---

## 3. World and credential contract

The world is a **fresh scratch world** under the configured worlds root
(`backend/config/world_storage.json` → `backend/data/acceptance_worlds`), not
the long-lived dev world.

`ATOM_WORLD_STORAGE_PATHS` relocates *all four* guard paths (config, maintenance
lock, registry lock, runner records) for an isolated run. Export it in the same
shell for the preflight, the launcher and the recovery helper: every one of
them resolves the config through `core.world_storage_guard.load_config`, so they
cannot validate different roots. An isolated run on a private scratch config
therefore uses:

```bash
export ATOM_WORLD_STORAGE_PATHS=/private/tmp/<run>/isolated-config   # holds world_storage.json
export WORLD=/private/tmp/<run>/isolated-worlds/wa075_settings
```

```bash
export PYTHON=/path/to/backend/venv314/bin/python     # existing interpreter
export ATOM_FRONTEND_DIR=<dir-with-a-built-frontend>  # .next/BUILD_ID present
export ADMIN_PASSWORD="$(cat /path/to/0600/wa075-admin-password)"
export NEXTAUTH_SECRET="$(cat /path/to/0600/wa075-web-secret)"  # real web session
export BACKEND_PORT=8105 FRONTEND_PORT=3001

# No provider credential may reach the world. python-dotenv never overwrites a
# present key, so empty values neutralize backend/.env for this shell.
for v in OPENAI_API_KEY ANTHROPIC_API_KEY GOOGLE_API_KEY OPENROUTER_API_KEY \
         DEEPSEEK_API_KEY GEMINI_API_KEY GROQ_API_KEY TOGETHER_API_KEY \
         OPENCODE_API_KEY MISTRAL_API_KEY XAI_API_KEY; do export "$v="; done

bash scripts/acceptance/launch_integrated_local_candidate.sh
```

The launcher already sets `ATOM_LOCAL_ONLY=true`, disables the scheduler and
integration sync, and pins the world DB/data/office/memory paths. The frontend
must have been **built with the same API origin** as `BACKEND_PORT`; the driver
records the origin of every `/api/` request and a stale build is visible as
`backend_cors` vs `next_proxy` plus the foreign-origin list.

`NEXTAUTH_SECRET` is required for the disposable secondary session: the real
login form establishes the NextAuth web session that `/api/auth/sessions`
reads. Without it the driver records `sessions.disposable_secondary_session`
as `missing` with the login page's own error text.

`NEXTAUTH_URL` must be pinned to the scratch frontend origin
(`http://127.0.0.1:3001`). NextAuth's development default is
`http://localhost:3000`, so an unpinned run makes the client poll
`/api/auth/session` on whatever else answers that port — a real cross-origin
leak that the run-scope guard reports as `run.no_foreign_api_origin` failure.
One replay observed exactly that before the variable was pinned; the final
run had zero foreign `/api/` requests.

**Never** point `DATABASE_URL` at `backend/data/atom.db`; both the preflight and
`validate_local_world.py` refuse it. Do not set
`ATOM_WORLD_STORAGE_BYPASS`.

---

## 4. Preflight

```bash
$PYTHON scripts/acceptance/browser_settings_preflight.py \
  --world "$WORLD" \
  --admin-password-file /path/to/0600/wa075-admin-password \
  --frontend-dir "$ATOM_FRONTEND_DIR" \
  --backend-port 8105 --frontend-port 3001 \
  --report /scratch/wa075/preflight.json
```

It reports, as one JSON object and without writing the world:

- the git source identity and tracked-dirty count;
- world layout / live-DB refusal / **the canonical configured worlds root**,
  resolved through the same `core.world_storage_guard.load_config` +
  `ATOM_WORLD_STORAGE_PATHS` contract the guard uses (the report records the
  config path and whether it was relocated);
- `core.world_storage_guard` verdict (bypass refused);
- dependency inventory (`uvicorn`, `fastapi`, SQLAlchemy, Python Playwright,
  node, `Google Chrome.app`, the frontend's `node_modules` and Playwright ESM,
  `.next/BUILD_ID`, `NEXTAUTH_SECRET` presence);
- port availability;
- **which tabs can be proven** and why any cannot (e.g.
  `ATOM_LLM_PROVIDER_POLICY` set ⇒ the AI policy is installation-managed and
  the UI save is disabled).

It never records the password value, only the file path and its mode.

---

## 5. Run the acceptance

```bash
ATOM_FRONTEND_URL=http://127.0.0.1:3001 \
ATOM_BACKEND_URL=http://127.0.0.1:8105 \
ATOM_WA075_WORLD="$WORLD" \
ATOM_SCOPE_EMAIL=admin@example.com \
ATOM_SCOPE_PASSWORD="$(cat /path/to/0600/wa075-admin-password)" \
NEXTAUTH_URL=http://127.0.0.1:3001 \
node scripts/acceptance/browser_settings_acceptance.mjs \
  --out /scratch/wa075/signed-in-settings.json
```

`NEXTAUTH_URL` must also be set for the frontend server process, not only this
command. `ATOM_CHROME_EXECUTABLE` optionally pins an existing Chrome/Chromium
binary when the installed `Google Chrome.app` is unsuitable on this host (the
replay used the already-cached arm64 Playwright headless shell because the
x64 Chrome build runs under Rosetta here and exited mid-run). Nothing is
downloaded or installed either way, and the chosen executable is recorded in
the evidence.

Before any setting is read or changed, the driver pins both origins to
loopback (known dev/service ports such as `3000`/`3002`/`8000`/`8001`/`8080` are
refused) and calls `GET /health`: the backend's `identity` must report the
pinned port, `cwd` `<repo>/backend`, and `database` `<ATOM_WA075_WORLD>/atom.db`,
and `GET /api/health` on the frontend must identify `atom-frontend`. A mismatch
is fatal (exit `2`) and nothing is mutated.

Flags: `--no-screenshots` (smaller evidence), `--exercise-2fa` (enable/reload/
disable round trip when the tab's setup route is reachable; a direct backend
disable is attempted if the UI path leaves 2FA on),
`--skip-account-password` (read-only Account coverage), `--timeout-ms`.

AI policy detail: a fresh scratch world has no configured provider key, so the
tab renders no provider checkboxes. The reversible change exercised there is
therefore the **mode** (`Automatic` ↔ `Only selected providers` with the empty
allowed set the UI actually submits), saved through the page, reloaded, and
restored. When the world does render providers, their checkboxes are included
in the comparison; if the baseline names a provider the tab cannot render, the
restore uses the same public PUT the page uses and records
`ui_restore_possible: false`.

Ordering is deliberate: AI → Routing → Local Models → Sessions → Account.
The primary browser signs in through the **real login form** (falling back to
the `browser_core_surface` token contract only if no web session can be
established; the report records which path was used and why the other failed).
Account runs last because a committed password change revokes every token.
The disposable secondary session is closed in a `finally`; the disposable
provider is deleted through the page and, if a step aborted, through the same
public DELETE the page uses; the provider policy is re-asserted against the
captured baseline after the AI checks; the original password is re-asserted at
the credentials boundary in a `finally`.

Evidence is one JSON file (`schema: atom-wa075-signed-in-settings-1`):
per-check `id/area/description/status/reason/evidence`, a normalized
`summary`, the API request log (method/path/status/origin, no headers,
bodies or credentials), captured JSON bodies only for the four asserted
non-auth endpoints (`/api/chat/routing-stats`, `/api/ai/provider-policy`,
`/api/ai/providers`, `/api/local-models`) with sensitive keys redacted,
page/console errors (query strings stripped), cleanup results, and the explicit
non-claims list. Raw `/api/auth/*` bodies — login, `/api/auth/me`, sessions,
password change and 2FA setup — are **never** persisted, and a final scan
refuses to write the file if any registered secret value (scratch password,
bearer token, rotated password, 2FA secret) appears. Screenshots are optional
and one per tab.

---

## 6. Replay result (2026-11-13)

The capture ran on a fresh scratch world under the **relocated** storage config
(`ATOM_WORLD_STORAGE_PATHS=/private/tmp/<run>/isolated-config` →
`/private/tmp/<run>/isolated-worlds/wa075-settings-replay`), backend on
`127.0.0.1:8105`, frontend `next dev` on `127.0.0.1:3001`. Before any setting
was touched the driver verified the backend identity (`pid`, `port`, `cwd`
`<repo>/backend`, `database` `<world>/atom.db`, `source_id`), the
`atom-frontend` health identity, and loopback-only origins. Provider credential
variables were blanked; nothing was installed.

`node …/browser_settings_acceptance.mjs` → **exit 3**: 25 pass, 0 fail,
2 missing, 1 skipped. `run.no_foreign_api_origin`: pass (0 foreign `/api/`
requests). Evidence lives outside the repository; only allowlisted bodies were
persisted and the secret scan found no password, bearer token or JWT.

| Tab | Result | Observed evidence |
|---|---|---|
| Account | 5 pass, 1 missing | profile read-back matches `/api/auth/me`; password change `POST → 200` with re-auth, old credential rejected, new accepted, reload passes, original restored and verified. 2FA status `200` (`enabled: false`), `POST /api/auth/2fa/setup → 400` (not routed) ⇒ `account.two_factor_surface` missing; enable/disable were never exercised. |
| AI | 5 pass | baseline `automatic` (an earlier run started from the legacy `unset` default; treated as behaviorally identical and recorded); `Only selected providers` saved through the page (`PUT → 200`, empty allowed set), survived reload, UI/API equal, restored through the UI (`PUT → 200`). |
| Sessions | 2 pass, 1 missing, 1 skipped | both the primary and the disposable secondary signed in through the real form and loaded the tab; `GET /api/auth/sessions → 500`; `GET /api/users/sessions → 200` with **0 rows** ⇒ `sessions.list_reflects_live_sessions` missing; `sessions.revoke_disposable` skipped (no row). |
| Routing | 5 pass | real `/api/chat/routing-stats` payload rendered exactly (0 feedback samples, `enabled: false`, `ema_enabled: false`), Refresh issued a second GET and the render followed it, the "Learning Router is off" banner agrees, empty telemetry reported as empty. |
| Local Models | 5 pass | disposable provider at `http://wa075-disposable.invalid/v1` registered through the form, survived reload, deleted through the card, provider set returned to baseline, and zero requests reached that host or any non-loopback API origin. |

### Remaining product gaps (confirmed, not repaired here)

1. **Sessions cannot list anything in a Personal/SQLite world.**
   `frontend-nextjs/pages/api/auth/sessions.ts` runs a Postgres-only query and
   the route 500s; independently, no production code writes `UserSession` rows,
   so the registry is `[]` even behind Postgres. Observed exactly as predicted.
2. **The Account tab's 2FA enable/disable controls are not routed.**
   `backend/api/auth_2fa_routes.py` defines `status/setup/enable/disable`, but
   `frontend-nextjs/next.config.js` rewrites only
   `/api/auth/:service/{authorize,initiate,status,disconnect}`. `GET status`
   works; `POST setup` falls into the NextAuth catch-all (400). `--exercise-2fa`
   remains unreachable until a proxy route exists.

A run with `"summary": {"ok": true}` and no `missing`/`skipped` entries would
close WA-075. The two gaps above are the only blockers observed here.

**Concurrent work, not part of this replay:** while this acceptance was running,
an uncommitted edit to `frontend-nextjs/next.config.js` (explicit
`afterFiles` rewrites for `/api/auth/2fa/{setup,enable,disable}`) and
`frontend-nextjs/tests/next-config-2fa-rewrite.test.ts` appeared in the working
tree. It was **not** present when the frontend process for this capture started
and was left untouched. If that change is accepted, restart the scratch
frontend and re-run the Account tab: `account.two_factor_surface` should move
from `missing` to `pass`, and `--exercise-2fa` should become reachable.

### Review corrections verified in this replay

- **Canonical storage root.** Preflight, `validate_local_world.py` and the
  recovery helper now resolve the config through
  `core.world_storage_guard.load_config` at the guard's own path, honouring
  `ATOM_WORLD_STORAGE_PATHS`; the guard, launcher validation and preflight all
  agreed on the relocated root.
- **Required skips are incomplete.** A skipped check now yields
  `summary.incomplete: true`, `completeness: "incomplete"` and exit `4` when no
  failure/missing has higher precedence; the replay reports `incomplete: true`
  and exits `3` because two capabilities are also missing.
- **Allowlisted evidence only.** Bodies are persisted only for
  `/api/chat/routing-stats`, `/api/ai/provider-policy`, `/api/ai/providers` and
  `/api/local-models`, with sensitive keys redacted. No `/api/auth/*` body is
  captured; 2FA setup records only its status (`setup_body_persisted: false`);
  a registered-secret scan refuses to write any file containing the scratch
  password, bearer token, rotated password or 2FA secret.
- **Pinned origins and identity before mutations.** Origins must be loopback
  and must not be known dev ports; the backend must report
  `<ATOM_WA075_WORLD>/atom.db`, the pinned port and `<repo>/backend` as its
  `cwd`, and the frontend must identify as `atom-frontend`; otherwise the
  driver exits `2` before login or any save.
- **Playwright reuse.** The driver imported
  `/Users/rushiparikh/projects/atom/frontend-nextjs/node_modules/playwright/index.mjs`
  and used the already-cached arm64 headless shell through
  `ATOM_CHROME_EXECUTABLE`. The installed Google Chrome is an x64 build running
  under Rosetta on this arm64 host; two earlier attempts ended with Chrome
  closing mid-run. No browser or dependency was downloaded.
- **Blocking onboarding dialog.** The fresh admin's session-scoped "Welcome to
  Atom" modal covers the settings controls. The driver dismisses it through the
  UI (Escape; control fallback) and records each appearance/dismissal; it does
  not pre-set the dismissal flag.

### Unit coverage that ran

`python -m pytest scripts/tests/test_browser_settings_acceptance_preflight.py`
— **33 tests**, no world/browser/database:

- every WA-075 check id is present and explicit (including the run-scope
  foreign-origin guard and the identity-before-login ordering);
- the driver reuses `lib/core_surface_session.mjs` and
  `lib/settings_contract.mjs`, imports Chrome/Playwright from the workspace,
  names no live/external host, reads no provider credential, and shells out to
  nothing; a pinned browser executable is allowed but never installed;
- missing capabilities (exit `3`), required skips (exit `4`, `incomplete`) and
  failures (exit `1`) are distinct;
- the evidence allowlist contains no `/api/auth` path and `setup_body_sample`
  is never persisted;
- TOTP matches RFC 6238 SHA-1 vectors (`287082` / `081804`); policy
  normalization treats legacy `unset` as `automatic`; routing normalizers are
  exact;
- the preflight resolves the guard's relocated config, refuses the live DB, the
  repo root, paths outside the worlds root, and a storage-guard bypass; it
  records the password file's mode but never its value; it creates nothing
  without `--report`;
- the password-recovery helper honours the relocated root, accepts only
  `<world>/atom.db` under it and still refuses the live DB.

---

## 7. PR 920 re-run (2026-11-13, second capture)

After `6c567d284` (Route Settings 2FA actions to the backend before NextAuth)
landed at HEAD, the acceptance was re-run on a fresh portable-scratch world
(`ATOM_WORLD_STORAGE_PATHS` → the run's `isolated-config`, worlds root on the
portable drive) with a disposable backend (`uvicorn`, `127.0.0.1:8105`,
health-identity verified before any mutation) and `next dev --webpack` on
`127.0.0.1:3001` with `NEXT_PUBLIC_API_URL` pinned to the isolated backend,
`NEXTAUTH_URL` pinned to the scratch origin, provider credentials blanked.
`next dev` (Turbopack default) refuses this worktree's shared `node_modules`
symlink ("points out of the filesystem root"); `--webpack` + the config's
`externalDir` experiment runs cleanly. `node …/browser_settings_acceptance.mjs
--exercise-2fa` → **exit 3**: **27 pass, 0 fail, 1 missing, 1 skipped**.

The gap this run closes — `--exercise-2fa` is now reachable and the round trip
passes at the user boundary:

| Check | Result | Observed evidence |
|---|---|---|
| `account.two_factor_surface` | **pass** | `GET /api/auth/2fa/status → 200` (`enabled: false`); `POST /api/auth/2fa/setup → 200` with a pending secret via the new afterFiles rewrites (previously fell into the NextAuth catch-all, 400). |
| `account.two_factor_reversible` | **pass** | setup → enable (`POST /api/auth/2fa/enable → 200` with an RFC 6238 TOTP code computed from the returned secret, backup codes delivered once), enabled state shown after a tab reload, disable (`POST /api/auth/2fa/disable → 200`), disabled state shown again, `enabled_after_check: false`. The secret value is registered for the evidence redaction scan only and is never persisted (`secret_recorded: false`). |

The remaining missing/skipped pair is the known Sessions gap (SQLite world:
`GET /api/auth/sessions → 500` Postgres-only route; no `UserSession` writer),
unchanged by this PR. `run.no_foreign_api_origin`: pass (0 foreign `/api/`
requests); the disposable provider and policy baselines were restored; no
credential, bearer token, rotated password or TOTP/2FA secret appears in the
evidence (registered-secret scan passed; no `/api/auth/*` body captured).

### Harness fix found by this run (driver, not product)

The first capture of this re-run recorded `account.two_factor_surface` as
`missing` even though the setup call already answered `200`: the driver sliced
the response body to 300 chars **before** `JSON.parse`, and a successful setup
body (~385 chars: `secret`, `otpauth_url`, `operation_id`, `status`,
`verification`) never fits, so `reachable` was structurally unreachable.
`browser_settings_acceptance.mjs` now parses the full body (truncation kept
only for non-JSON error notes) and the failure reason is data-driven instead
of asserting an unrouted catch-all. Reproduction before the fix: the same
`page.request.post` call returned `200` with `secret` present. The 33
source-contract tests in `scripts/tests/` still pass.

### Build-cache note (next dev)

`NEXT_DIST_DIR` cannot move the dev cache outside the project root in this
Next build: an absolute value is resolved relative to the project root (it
created a stray `frontend-nextjs/Volumes/…` tree), a `../`-relative value and
a symlinked distDir both break server-page module resolution (webpack emits
dist-relative module paths; a symlinked dist resolves through its realpath on
the drive, where no `node_modules` exists upward), and `--preserve-symlinks`
404s every route. Both stray artifacts were removed and `next-env.d.ts`
restored; the worktree's pre-existing `.next/dev` was left untouched. Putting
the `next dev` cache on the portable drive needs a `next.config.js` change and
was **not** attempted here (the file is under review in PR 920).

## 8. Superseding result (2026-11-14): 29/29

This is the current result; it supersedes §6 and §7, which remain as history
for their earlier source states.

| Field | Value |
|---|---|
| Source | clean `a53b56fdc32bd1447a7fe5285efee8f1be20a409` (`Ground fleet reports in specialist and dispatch evidence (#935)`) |
| Run id | `wa075-20261114070119-89e3cb` |
| Checks | **29 of 29 pass** — 0 fail, 0 missing, 0 skipped; exit `0` by the §1 contract |
| API traffic | **409** API requests recorded by the driver |
| External traffic | **0** external browser requests observed by the driver |
| 2FA | full setup → enable → reload → disable round trip passed |
| Stack | isolated macOS backend/frontend with the repaired pinned LanceDB 0.38.0 overlay |

On the same 29-check inventory as §7, every check passed, including the
Sessions `missing`/`skipped` pair that was the last blocker there. This meets
the closing condition stated at the end of §6: no `missing` and no `skipped`
entries remain.

Why the last gap closed: `d253602f1` ("Connect Settings Active Sessions to
durable revocation", #923) is in this source and is the session inventory and
revocation work; `6c567d284`, which made the 2FA round trip reachable for §7,
is also in it.

Stack notes:

- Same isolated shape as §6/§7: loopback scratch backend and frontend, scratch
  world, health identity verified before any setting was read or changed, and
  provider credentials blanked.
- The pinned LanceDB 0.38.0 overlay was repaired for this run. That is part of
  the run environment, not a change to the source under test.
- The 409 API requests all stayed within the scratch origins; zero external
  browser requests were observed, and the `.invalid` disposable provider was
  never contacted.

Scope of this addition: summary metadata only. No raw network bodies,
screenshots, per-request payloads, credentials, bearer tokens, TOTP/2FA
secrets, or account identifiers are recorded here. §6 and §7 are unedited
history and do not describe the current result.

## 9. Teardown / recovery

- Stop the launcher's processes (`backend.pid` / `frontend.pid` under the
  world) and confirm the ports are free; never kill unrelated processes.
- A scratch world is disposable; delete it through
  `scripts/orchestration_acceptance/storage_policy.py inventory` → reviewed
  digest → `apply`, not by hand.
- If a password rotation is interrupted (SIGKILL before the `finally`), the
  world's admin password is the rotated value that was never written down.
  Recover only that world:

  ```bash
  DATABASE_URL="sqlite:///$WORLD/atom.db" \
  SCRATCH_ADMIN_PASSWORD="$(cat /path/to/0600/new-password)" \
  $PYTHON scripts/acceptance/scratch_admin_password.py
  ```

  This refuses the live DB and anything that is not `<world>/atom.db` under the
  configured worlds root. `SCRATCH_USER_EMAIL` defaults to `admin@example.com`.
