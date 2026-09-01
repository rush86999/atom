# Agent Coordination

Live coordination doc for multiple agents working in this repo in parallel.
**Read this before making changes, and append your session when you start and
finish.** Keep entries factual and dated; never delete another session's
notes — mark superseded items with ~~strikethrough~~ or a "SUPERSEDED" note.

Ground rules:

1. Before editing a file, check the **Active sessions** table — if another
   session lists it, coordinate through a note here or pick different files.
2. Commit often in small, well-scoped commits; do not commit files listed by
   another active session without their note.
3. If a file you are editing changes under you (Edit tool "file modified"
   error), re-read it and check this doc before continuing — someone may be
   mid-refactor.
4. Record anything cross-cutting you change (env vars, route mounts, shared
   fixtures) — other agents' tests may depend on it.
5. **The shared dev backend on `:8001`**: always (re)start it with
   `scripts/start-backend.sh --daemon --force` — the script exports
   `BYPASS_RATE_LIMIT=1`, which the journey suites need (they register ~30
   users). A plain `uvicorn` restart leaves the register limiter on and
   every journey test 429s. Note your restart in this doc.

---

## Active sessions

| Session | Focus | Files owned (do not refactor in parallel) | Status |
|---|---|---|---|
| Integrations e2e journeys (2026-08-29) | End-to-end user-journey coverage for all integrations; see "Session: integrations-e2e" below | `backend/api/oauth_routes.py`, `backend/core/oauth_handler.py`, `backend/integrations/outlook_service.py`, `backend/api/data_ingestion_routes.py`, `backend/core/integrations/adapters/zoho.py`, `backend/main_api_app.py` (dotenv + workdrive mount), `backend/scripts/*mock_server*.py`, `backend/tests/e2e_ui/tests/test_journey_*.py` | COMPLETE — all suites green; see "Final results" |

---

## Session: integrations-e2e (started 2026-08-29)

Goal: the `/integrations` user journey (hub → connect → status → use →
disconnect) actually tested end-to-end for every integration, Outlook and
Zoho first.

### Landed so far (uncommitted on `main` at the time of writing)

Production fixes (each was a real journey-blocking bug):

- `backend/api/oauth_routes.py`
  - `oauth_initiate` now reads the `Authorization: Bearer` header (was
    query-param-only → every header-authenticated initiate 401'd; blocked the
    Zoho journey end-to-end).
  - `revoke_oauth_token` now revokes the `IntegrationToken` fan-out rows
    (microsoft → microsoft+outlook; zoho → 5-provider suite). Disconnect
    previously left the hub "connected" and data routes working.
  - Zoho connect's background sync now passes `workspace_id`/`tenant_id` as
    keyword args via `core.personal_scope` resolvers (tenant_id was bound
    positionally to `workspace_id`, so post-connect syncs ran
    unauthenticated).
  - New `_TOKEN_FANOUT` module constant.
- `backend/main_api_app.py`
  - `load_env()` no longer `override=True`: explicit process env
    (DATABASE_URL, provider creds, e2e harness) must beat `.env` files. The
    old behavior silently discarded both, and the Zoho journey was running
    against the dev DB instead of its fresh tmp DB.
  - Zoho WorkDrive router mounted at its own declared prefix
    `/api/zoho-workdrive` (was double-prefixed under `/api/v1/integrations/...`
    and unreachable; the hub page + next.config rewrite target this path).
- `backend/core/oauth_handler.py`
  - `MICROSOFT_AUTHORITY_BASE` env override for the Microsoft authorize/token
    endpoints (mirrors `ZOHO_ACCOUNTS_BASE`).
  - Generic `{PREFIX}_AUTHORIZE_URL` / `{PREFIX}_TOKEN_URL` overrides derived
    from each `OAuthConfig`'s client-id env name (`GOOGLE_CLIENT_ID` →
    `GOOGLE_AUTHORIZE_URL`; `TRELLO_API_KEY` → `TRELLO_AUTHORIZE_URL`).
- `backend/integrations/outlook_service.py` — `MICROSOFT_GRAPH_BASE_URL`
  env override for the Graph base URL + refresh authority URL.
- `backend/integrations/atom_communication_ingestion_pipeline.py` — the
  Outlook poller's Graph URL honors the same env override.
- `backend/core/integrations/adapters/zoho.py` — `_load_token` falls back to
  any *active* provider grant when the workspace-scoped lookup misses
  (workspace-convention drift used to produce unauthenticated syncs).
- `backend/api/data_ingestion_routes.py` — sync endpoint no longer 500s when
  a sync is skipped (bool fed to a `str` response field).

Tests:

- New `backend/scripts/microsoft_mock_server.py` + `backend/tests/e2e_ui/tests/test_journey_outlook_integration.py`
  (browser consent → tokens → hub status → emails/calendar/contacts/tasks/
  profile → disconnect; GREEN).
- New `backend/scripts/generic_oauth_mock_server.py` + `backend/tests/e2e_ui/tests/test_journey_all_integrations.py`
  (parametrized connect/status/disconnect for google, slack, github, asana,
  notion, dropbox, box, salesforce, linkedin, whatsapp; trello initiate-only
  — OAuth1; plus the env-keyed half of the catalog via `connection-status`).
- `test_journey_zoho_integration.py` updated: R88 credential isolation
  (member must NOT receive token rows), sync retry instead of racing the
  background sync, idempotent-reingest note (GREEN).
- `test_oauth_initiate_token_identity.py` +2 (Bearer header path).
- `test_oauth_config_url_overrides.py` new (override derivation).
- `test_covpush_outlook.py` / `test_covpush_mail_office.py` made hermetic
  (they depended on the ambient `backend/.env` being absent).

Docs: `backend/tests/e2e_ui/JOURNEY_TESTS.md` rows for the new modules.

### Known collisions with parallel work (heads-up)

- Commit `e2e34dffc` / `53e93ae52` / `6eb12b7cc` landed mid-session
  (integration_status_routes, embedding registry, DATABASE_URL anchoring) —
  this session's work is compatible with all three.
- `backend/integrations/outlook_service.py` `_refresh_access_token` was
  changed by another session mid-flight (`.first()` → `.all()` fan-out to
  both provider rows). The change is good; `test_covpush_outlook.py`'s mock
  was updated here to serve `.all()` accordingly.
- The dev backend on `:8001` was restarted twice with
  `scripts/start-backend.sh --daemon --force` to pick up fixes (pids
  changed). If you rely on :8001, restart it after pulling this session's
  changes.

### Debugging notes (resolved during the all-integrations work)

- The run-2 "initiate 401s" did not recur in runs 3–4 once the fixture
  redirect URIs pointed at the real backend port (a port-0 placeholder made
  the consent button navigate to an unroutable address) and the OAuthConfig
  override prefix for `TRELLO_API_KEY` was derived correctly. `oauth_initiate`
  now logs swallowed resolver exceptions instead of turning them into
  undocumented 401s — if the flake returns, the child backend log will name
  it.
- The generic mock originally issued one constant refresh token for every
  provider. `oauth_tokens.refresh_token_hash` is UNIQUE, so the second
  provider's callback died with `IntegrityError` → 500 and stored nothing.
  The mock now issues unique tokens per grant (matching real providers).

### Open question

None currently.

### Final results (2026-08-29)

| Suite | Result |
|---|---|
| `test_journey_outlook_integration.py` (browser consent → tokens → hub → data → disconnect) | 2 passed |
| `test_journey_zoho_integration.py` (browser consent → 5-provider fan-out → sync → chat recall) | 2 passed |
| `test_journey_all_integrations.py` (10 OAuth providers full journey + trello initiate + env-keyed catalog + mock contract) | 13 passed |
| `test_journey_integrations_health.py` (32 catalog health routes) | 31 passed, 1 xfailed (documented `nextjs`) |
| Units around the changed code | 370 passed |

Known unrelated pre-existing failure: `tests/test_llm_oauth_handler.py` (2,
fail identically on a clean checkout — LLM-provider OAuth, not integrations).

### How to verify this session's work

```bash
# Self-contained journey suites (~2 min each; no external services):
cd backend/tests/e2e_ui
../../venv/bin/python -m pytest tests/test_journey_outlook_integration.py \
    tests/test_journey_zoho_integration.py -v
../../venv/bin/python -m pytest tests/test_journey_all_integrations.py -v

# Units around the changed code:
cd backend && venv/bin/python -m pytest \
    tests/test_oauth_initiate_token_identity.py \
    tests/test_round71_oauth_routes_auth.py \
    tests/test_oauth_config_url_overrides.py \
    tests/test_covpush_outlook.py tests/test_covpush_mail_office.py \
    tests/unit/api/test_oauth_routes.py -q
```

---

## Append your session below this line

(Format: `## Session: <name> (<date>)` + Goal / Files owned / Notes / Status.)
