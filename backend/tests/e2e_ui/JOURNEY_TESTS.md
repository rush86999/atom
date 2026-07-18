# Atom User-Journey E2E Tests

A realistic, end-to-end test suite that walks through the full Atom application
the way a real user would — exercising every major feature surface and the
backend APIs underneath. Tests run against the **full app** (`main_api_app:app`),
not the minimal `main.py`.

## Suite layout

| File | What it covers |
|---|---|
| `tests/test_user_journey.py` | **Canonical full journey** — one ordered flow: UI login → dashboard → agents → chat → canvas → marketplace → workflow builder → projects → integrations → settings (theme persistence) → logout → protected-route redirect. |
| `tests/test_journey_auth.py` | UI login, register, bad-credentials, protected-route redirect, next-auth session establishment. |
| `tests/test_journey_api_features.py` | Backend feature lifecycle via authenticated HTTP: skills (import→list→get→delete), workflows, projects/unified-tasks, preferences round-trip, agents, canvas. |
| `tests/test_journey_ui_features.py` | Each major page rendered independently: agents, chat, canvas, marketplace, workflow builder, projects, integrations hub, settings persistence. |
| `tests/test_journey_page_smoke.py` | Parametrized: loads **every sidebar route** (18 routes) and asserts it renders for an authenticated user. |
| `tests/test_journey_integrations_health.py` | Parametrized health-check across 13 integrations; reports (xfail) any whose health route isn't wired up. |
| `tests/test_journey_permission_matrix.py` | **RBAC contract + permission enforcement** across all 8 roles. Locks the role→permission mapping, asserts each enforced permission (AGENT_VIEW/RUN/MANAGE) allows/denies the right roles, and documents the gap that WORKFLOW/USER/SYSTEM permissions are never enforced. |
| `tests/test_journey_role_api.py` | **8 roles × 9 core read endpoints** (72 cases) — every role can read every feature without a 5xx crash or 401 on a valid token. |
| `tests/test_journey_role_ui.py` | **Every role logs in via the UI** and loads the shared authenticated pages (dashboard, settings, agents, canvas) without bouncing to /login. |

Supporting code:
- `pages/journey_pages.py` — page objects using real selectors (role/text/placeholder), verified against the running UI.
- `fixtures/journey_fixtures.py` — API-first user setup + an `authed_page` fixture that performs a real UI login (needed because session-gated pages require a next-auth session, not just a localStorage token).

## Preconditions

1. **Full backend** on `http://localhost:8001`:
   ```bash
   PYTHONPATH=$PWD:$PWD/backend DISABLE_AUTH_RATE_LIMIT=1 \
     backend/venv/bin/python -m uvicorn main_api_app:app --port 8001 --host 127.0.0.1
   ```
   `DISABLE_AUTH_RATE_LIMIT=1` lifts the 3-registrations/5-min limit so the
   suite can create its per-test users. (Do **not** use `TESTING=1` for this —
   that env var also switches `core/database.py` to a schema-incompatible
   test database.)

2. **Frontend** on `http://localhost:3001` with `NEXT_PUBLIC_API_URL=http://localhost:8001`.

3. **Playwright driver** — the bundled node binary may be missing; point at the
   system node:
   ```bash
   export PLAYWRIGHT_NODEJS_PATH="$(which node)"
   ```

## Running

```bash
# Full journey suite (~2 min):
cd backend/tests/e2e_ui
../../venv/bin/python -m pytest tests/test_journey_*.py tests/test_user_journey.py

# Just the canonical end-to-end flow:
../../venv/bin/python -m pytest tests/test_user_journey.py -v

# A single feature area:
../../venv/bin/python -m pytest tests/test_journey_auth.py -v

# One sidebar route (for debugging):
../../venv/bin/python -m pytest tests/test_journey_page_smoke.py -k "canvas"
```

Expected result: **47 passed, 4 xfailed**. The xfails are integrations whose
health route isn't exposed yet (gdrive, gmail, jira, nextjs) — surfaced, not
hidden.

## Role-based coverage (all 8 roles)

The `test_journey_role_*` files exercise the app for every `UserRole`:
`super_admin`, `owner`, `admin`, `workspace_admin`, `team_lead`, `member`,
`viewer`, `guest`. Run them together:

```bash
../../venv/bin/python -m pytest tests/test_journey_role_api.py \
  tests/test_journey_role_ui.py tests/test_journey_permission_matrix.py -v
```

Role fixtures live in `fixtures/journey_fixtures.py`:
- `role_credentials` (parametrized via `ALL_ROLES`) — registers a user, sets
  its role in the DB the backend reads, returns a token.
- `role_authed_page` — a Playwright page logged in as the parametrized role.
- `all_role_headers` — one user per role in a single fixture.

### Findings these journeys surfaced (and fixed)

1. **`owner`/`admin`/`viewer` had no permissions** (`core/rbac_service.py`).
   They were absent from `_get_role_permissions()`, so they silently got an
   empty set — worse than `guest`. `/agents` enforces `AGENT_VIEW` → those
   roles got 403 → the page broke for them. **Fixed**: added sensible
   permission ladders (guest ⊆ viewer ⊆ member ⊆ team_lead ⊆ admin ⊆
   workspace_admin ⊆ owner). The `test_all_defined_roles_have_permissions`
   and `test_role_hierarchy_is_monotonic` regression guards prevent it
   returning.
2. **Only `AGENT_*` permissions are actually enforced.** `WORKFLOW_VIEW/RUN/
   MANAGE`, `USER_VIEW/MANAGE`, and `SYSTEM_ADMIN` are defined and granted to
   roles, but no router calls `require_permission(...)` for them — so every
   authenticated user can perform those actions regardless of role. Documented
   by `test_known_gap_permission_is_never_enforced` (will fail when enforcement
   is added, prompting wiring-up of matrix cases).

### Coverage note

Measured coverage of `api/`+`core/`+`integrations/` is **~10%** (baseline:
unit tests, 254 passing). E2E journeys verify real user-facing behavior across
all roles but, by design, hit only the happy path of each endpoint — deep
service-layer branches are better reached by unit tests. The journeys' value
is *behavioral* coverage (does the app work for each role?) rather than line
coverage. Grow line coverage by adding unit tests for service internals.
