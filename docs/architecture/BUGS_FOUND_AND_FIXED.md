# Bugs Found and Fixed via User-Journey Testing

A consolidated record of the real bugs the end-to-end user-journey suite
uncovered while hardening Atom for real-world usage, organized by area. Each
entry lists the **symptom**, **root cause**, **fix**, and the commit that
landed it — so future contributors can understand *why* the code is the way it
is and avoid reintroducing the same defects.

This is reference material, not a changelog. For how to run the suite that
catches regressions on these, see
[`backend/tests/e2e_ui/JOURNEY_TESTS.md`](../../backend/tests/e2e_ui/JOURNEY_TESTS.md).

---

## Backend — router wiring (`main_api_app.py`)

Several routers were mounted with a prefix that combined with their own
in-router prefix to produce doubled, unreachable paths. FastAPI concatenates
the `include_router(prefix=...)` with the router's own `APIRouter(prefix=...)`,
so a router that already declares its prefix must be included **bare**.

### 1. `agent_router` double-prefix — `agent:view`/`run`/`manage` 404
- **Symptom:** `/api/v1/agents/...` returned 404; the real path was
  `/api/v1/agents/api/agents/...`. The Agents Control Center couldn't load.
- **Root cause:** `api/agent_routes.py` declares `prefix="/api/agents"`, and
  `main_api_app.py` included it with `prefix="/api/v1/agents"`.
- **Fix:** include `agent_router` with no prefix (the in-router prefix already
  matches what the frontend calls). `commit bb95cc307`.

### 2. `user_mgmt_router` double-prefix — `/api/users/me` 404
- **Symptom:** `/api/users/me` 404'd; real path was `/api/v1/api/users/me`.
- **Root cause:** `api/user_management_routes.py` has `prefix="/api/users"`,
  included with `prefix="/api/v1"`.
- **Fix:** include bare. `commit bb95cc307`.

### 3. `workflow_template_router` double-mount + double-prefix
- **Symptom:** marketplace + workflow builder couldn't list templates
  (`/api/workflow-templates`); the real path was doubled and the router was
  mounted twice.
- **Root cause:** the router has `prefix="/api/workflow-templates"`; it was
  included both at module level with `/api/v1/workflows/templates` AND again
  in a lifespan block with `/api/workflow-templates`.
- **Fix:** one bare include. `commit bb95cc307`.

### 4. Duplicate router mounts (4 routers)
- **Symptom:** duplicate route registrations / OpenAPI entries.
- **Root cause:** `core/workflow_endpoints` mounted 3×, `canvas_skill_router`
  3×, `system_health_router` 2×, and the enterprise/public-marketplace blocks
  were dead `try/except` shells.
- **Fix:** one mount each; removed the dead `public_marketplace_routes` import
  (the module never existed — its ImportError was silently swallowed every
  startup). `commit bb95cc307`.

### 5. Preferences route path doubled
- **Symptom:** settings theme changes didn't persist; the frontend called
  `/api/v1/preferences` but the real path was `/api/v1/preferences/preferences`.
- **Root cause:** `core/user_preference_routes.py` routes were `/preferences`
  and `/preferences/{key}`, mounted at `prefix="/api/v1/preferences"`.
- **Fix:** route paths `""` and `/{key}` so the mounted paths become
  `/api/v1/preferences` and `/api/v1/preferences/{key}`. `commit bb95cc307`.

---

## Backend — logic

### 6. Skill import returned 500 (`'coroutine' object is not subscriptable`)
- **Symptom:** `POST /api/skills/import` always 500'd.
- **Root cause:** `SkillSecurityScanner.scan_skill` is `async`, but
  `SkillRegistryService.import_skill` (sync) called it without `await`, then
  subscripted the coroutine.
- **Fix:** made `import_skill` async and `await`ed the scan. `commit bb95cc307`.

### 7. `IntegrationRegistry.get_service_instance` missing
- **Symptom:** universal integration execution failed for jira/asana/linear/
  monday/salesforce/hubspot/etc. with `'IntegrationRegistry' object has no
  attribute 'get_service_instance'`.
- **Root cause:** `integrations/universal_integration_service.py` calls a
  method that was never defined on `IntegrationRegistry`.
- **Fix:** added `get_service_instance(connector_id, tenant_id)` that resolves
  the class via `get_service_class` and instantiates it. `commit bb95cc307`.

### 8. CORS blocked the E2E frontend origin
- **Symptom:** every browser→backend call failed with "Failed to fetch"
  (CORS preflight returned 400).
- **Root cause:** `main_api_app.py` `ALLOWED_ORIGINS` omitted `localhost:3001`
  (the E2E/dev frontend port); with `allow_credentials=True`, Starlette
  rejects unknown origins with 400.
- **Fix:** added `http://localhost:3001` + `127.0.0.1:3001`. `commit bb95cc307`.

### 9. Auth rate-limit blocked the test suite
- **Symptom:** the journey suite (which creates many test users) hit the
  3-registrations/5-min limit.
- **Root cause:** no way to lift the limit without `TESTING=1`, which also
  switches `core/database.py` to a schema-incompatible test DB.
- **Fix:** dedicated `DISABLE_AUTH_RATE_LIMIT` env flag, deliberately
  independent of `TESTING` (documented in `backend/.env.example`).
  `commit bb95cc307`.

---

## Frontend

### 10. UI login never established a next-auth session
- **Symptom:** session-gated pages (`/chat`, etc.) redirected to `/login`
  immediately after logging in.
- **Root cause:** `pages/login.tsx` did a raw `fetch('/api/auth/login')` and
  set `localStorage.auth_token`, but never called `signIn("credentials")` —
  so next-auth had no session and `useSession()` returned unauthenticated.
- **Fix:** call `signIn("credentials", { redirect: false })`, then mirror the
  token to localStorage via `getSession()` (no redundant second login fetch).
  `commits bb95cc307, 05df61fcc`.

### 11. Agents page crashed (`agents.find is not a function`)
- **Symptom:** `/agents` rendered a blank page; console showed
  `agents.find is not a function`.
- **Root cause:** backend returns `{success, data: [...]}` (BaseAPIRouter
  wrapper), but `pages/agents/index.tsx` did `setAgents(data)` expecting a
  bare array, then called `.find()` on the wrapper object.
- **Fix:** unwrap `.data` (accept both wrapped and bare-array shapes).
  `commit bb95cc307`.

### 12. WebSocket + Preferences hardcoded `localhost:8000`
- **Symptom:** against a backend on any other port (e.g. the full app on
  8001), live updates and settings silently failed.
- **Root cause:** `hooks/useWebSocket.ts` and
  `components/Settings/PreferencesTab.tsx` hardcoded the URL.
- **Fix:** derive from `NEXT_PUBLIC_API_URL`. `commit bb95cc307`.

### 13. `signin.tsx` syntax error blocked `next build`
- **Symptom:** `next build` failed with
  `Expected ';', '}' or <eof>` at `pages/auth/signin.tsx:59`.
- **Root cause:** a literal `` `r`n `` (a broken escape) corrupted the line.
- **Fix:** replaced with a real newline. `commit 556fd484b`.

---

## RBAC (`core/rbac_service.py`)

### 14. `owner`/`admin`/`viewer` had no permissions (worse than `guest`)
- **Symptom:** those roles got 403 on `/agents` (which enforces `AGENT_VIEW`)
  and the page broke for them.
- **Root cause:** the three roles were absent from
  `_get_role_permissions()`, so they fell through to an **empty** permission
  set — less access than `guest`.
- **Fix:** added a proper permission ladder
  (guest ⊆ viewer ⊆ member ⊆ team_lead ⊆ admin ⊆ workspace_admin ⊆ owner;
  super_admin implicit). Regression guards in
  `test_journey_permission_matrix.py` (`test_all_defined_roles_have_permissions`,
  `test_role_hierarchy_is_monotonic`) prevent it returning.
  `commit 692ec0332`.

### 15. Only `AGENT_*` permissions are actually enforced (open finding)
- **Symptom:** none directly — this is an authorization gap.
- **Root cause:** `WORKFLOW_VIEW/RUN/MANAGE`, `USER_VIEW/MANAGE`, and
  `SYSTEM_ADMIN` are defined and granted to roles, but **no router calls
  `require_permission(...)` for them** — so every authenticated user can
  perform those actions regardless of role.
- **Status:** **documented, not yet fixed.** `test_known_gap_permission_is_
  never_enforced` in the permission matrix will fail (prompting wiring-up)
  when enforcement is added. See
  [JOURNEY_TESTS.md → Findings](../../backend/tests/e2e_ui/JOURNEY_TESTS.md#findings-these-journeys-surfaced-and-fixed).

---

## CI / Docker

### 16. `conftest.py` crashed pytest on test failure (`page.video` is None)
- **Symptom:** when any browser journey failed in CI, pytest itself crashed
  with `INTERNALERROR: 'NoneType' object has no attribute 'path'` (exit 3),
  masking the real test result.
- **Root cause:** the failure-reporting hook called `page.video.path()` but
  `page.video` is `None` for fixtures that build their own browser context
  without `record_video_dir` (the journey `authed_page` fixtures).
- **Fix:** guard `page.video`. `commit ba1df0728`.

### 17. Role fixtures `no such table: users`
- **Symptom:** all role-parametrized tests errored in CI with
  `sqlite3.OperationalError: no such table: users`.
- **Root cause:** the fixtures resolved the relative `DATABASE_URL` from
  `__file__`, but the backend (cwd `backend/`) and the test step
  (cwd `backend/tests/e2e_ui`) resolved `sqlite:///test_e2e.db` against
  different cwds → the test wrote to an empty file.
- **Fix:** (a) `_set_user_role` now uses the backend's own
  `core.database.SessionLocal` (no path guessing); (b) CI uses an **absolute**
  `DATABASE_URL` for both backend and test step so they share one file.
  `commit 4e38760ca`.

### 18. Dashboard `is_loaded()` raced React hydration
- **Symptom:** `test_ui_login_lands_on_dashboard` failed in CI even though the
  page redirected to `/dashboard` and the H1 was in the DOM.
- **Root cause:** `is_visible()` returned False during pre-hydration SSR state
  (`title=''`) even though the heading was attached.
- **Fix:** `is_loaded()` uses `wait_for(state="attached")`, confirming the
  dashboard shell rendered without depending on hydration/visibility timing.
  `commit 5076daa4c`.

### 19. Screenshot artifact upload was empty (debugging blind)
- **Symptom:** the `e2e-screenshots` artifact was always empty (just
  `__init__.py`), making CI failures impossible to diagnose visually.
- **Root cause:** (a) `upload-artifact` runs at workspace root, not the job's
  `working-directory`, so the relative path resolved to a nonexistent nested
  dir; (b) screenshot filenames contained `[chromium]` brackets, which broke
  the artifact glob.
- **Fix:** absolute `${{ github.workspace }}` upload path; strip brackets from
  screenshot filenames. Added a page-state diagnostic print to
  `DashboardJourneyPage.is_loaded()` for text-based debugging.
  `commits 219964c3e, 219964c3e`.

---

## Lessons (conventions to prevent recurrence)

1. **Never include a router with a prefix it already declares.** If a router
   has `APIRouter(prefix="/api/foo")`, include it bare. Doubled prefixes are
   the single most common routing bug here.
2. **Don't write to the DB from tests by guessing the file path.** Use the
   backend's own `core.database.SessionLocal`, and in CI use an absolute
   `DATABASE_URL` so cross-process resolution agrees.
3. **Async scanners/LLM calls must be awaited.** A sync caller of an `async`
   method gets a coroutine, not a result — and the error often surfaces far
   from the call site.
4. **Backend response shape is `{success, data, ...}`.** Frontend code that
   expects a bare array/object must unwrap `.data`.
5. **E2E `is_loaded()` checks should use `wait_for(state="attached")` or
   `wait_for_selector`, not bare `is_visible()`.** SSR content is in the DOM
   before hydration; visibility can lag.
6. **New roles added to `UserRole` must be added to `_get_role_permissions()`.**
   The regression guard enforces this.
7. **Keep CI artifacts debuggable:** absolute upload paths, no glob-special
   chars in filenames, and a text diagnostic when an assertion fails.
