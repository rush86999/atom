# Agent coordination: integration "connected" state migration

**Status: COMPLETE (2026-08-29).** All integration pages/components consume `GET /api/integrations/connection-status`; all 22 related test suites green (483/483 tests); `tsc --noEmit` clean; backend tests 10/10. The "In-flight" section below is kept as reference for the patterns used.

**Owner session:** the one that fixed `/integrations/outlook` showing a false "Connected" (2026-08-29)
**Purpose:** prevent clobbering between concurrent agents working in this tree, and document the connection-status contract.

---

## TL;DR for other agents

1. If you touch **any** integration page/component test in `frontend-nextjs/components/__tests__/*Integration.test.tsx`: the components no longer decide "connected" from `/api/integrations/<slug>/health`. They call **`GET /api/integrations/connection-status`** and read `providers.<id>.connected`. MSW-based tests need a `connection-status` handler (see "Test migration" below).
2. Between ~19:40–19:50 local time, **12 test files in `components/__tests__/` were bulk-reverted** while I was editing them (all mtimes identical, my edits gone). If that was your tooling, please don't bulk-revert that directory again without checking this doc — my component changes depend on matching test updates.
3. Don't "fix" components fetching `/api/integrations/connection-status` by switching them back to `/health`. The `/health` routes are liveness stubs that return 200 unconditionally — that's the bug this migration removes.

---

## Background: what was broken

Every integration detail page showed "Connected" for any logged-in user because:

- `OutlookIntegration.tsx` (and 15 sibling components) set `connected = true` whenever `/api/integrations/<slug>/health` returned HTTP 200.
- Those `/health` routes (e.g. `backend/integrations/outlook_routes.py:582`) are service-liveness stubs — `{"status": "healthy"}`, always 200, no token check.

Ground truth at diagnosis time: `user_connections`, `tenant_integrations`, `integration_tokens`, `oauth_tokens` all empty; env has only Microsoft OAuth **setup** vars (client id/secret), no access tokens. So nothing was connected, yet every page said "Connected".

## What I changed

### Backend — `backend/api/integration_status_routes.py`

This file already had `GET /api/integrations/connection-status` (UserConnection + TenantIntegration + env credentials). I added a missing truth source:

- **`IntegrationToken` rows** (step 3 in `_connection_sources`) — the generic OAuth callback (`backend/api/oauth_routes.py`) persists Microsoft/Google/Zoho grants there (providers `"microsoft"` + `"outlook"`, `"google"`, `zoho_*` fan-out), **not** as `UserConnection` rows. Without this, a real OAuth connect would still show "not connected".
- `_IT_PROVIDER_ALIASES` maps provider → catalog ids: `"microsoft"` → microsoft365/outlook/onedrive/teams (one Graph consent), `"google"` → gmail/gdrive/google-workspace, `zoho_*` → the zoho-* catalog ids. Unlisted providers map 1:1.

Note: this file also gained `/health-status` and `/ingestion-status` endpoints from **another workstream** while I was editing — those are not mine, I only added the `IntegrationToken` source above.

### Frontend — components migrated to `connection-status`

Each `checkConnection()` now fetches `/api/integrations/connection-status` with `authHeaders()` and sets connected only from `providers.<id>.connected === true`. The `if (isConnected) { ...loadX() }` guards wrap the original side-effect calls. Files (all verified with `tsc --noEmit` and live-page spot checks):

| File | provider id |
|---|---|
| `components/OutlookIntegration.tsx` | `outlook` |
| `components/AsanaIntegration.tsx` | `asana` |
| `components/AzureIntegration.tsx` | `azure` |
| `components/BoxIntegration.tsx` | `box` |
| `components/DiscordIntegration.tsx` | `discord` (custom shape: `setIsConnected`) |
| `components/GitHubIntegration.tsx` | `github` |
| `components/GoogleWorkspaceIntegration.tsx` | `google-workspace` |
| `components/JiraIntegration.tsx` | `jira` |
| `components/LinearIntegration.tsx` | `linear` |
| `components/Microsoft365Integration.tsx` | `microsoft365` |
| `components/NotionIntegration.tsx` | `notion` |
| `components/QuickBooksIntegration.tsx` | `quickbooks` |
| `components/SlackIntegration.tsx` | `slack` (useCallback variant) |
| `components/TeamsIntegration.tsx` | `teams` |
| `components/TrelloIntegration.tsx` | `trello` |
| `components/ZendeskIntegration.tsx` | `zendesk` |
| `components/ZoomIntegration.tsx` | `zoom` |
| `pages/integrations/salesforce.tsx` | `salesforce` (added `authHeaders` import — it previously sent no auth at all) |
| `pages/integrations/bitbucket.tsx` | `bitbucket` (keeps localStorage-token signal from its own authorize flow; health stub dropped) |

The `/integrations` **index** page already consumed `connection-status` before I started (different workstream) — its `healthUrls` fetches now only feed the display "health" field, not `connected`. That's intentional; leave as is.

### Verified already

- `tsc --noEmit`: clean for all files above.
- Backend: `pytest tests/test_integration_health_status_routes.py` → 10 passed (with my `IntegrationToken` change in place).
- DB-level check: no rows → outlook not connected; simulated `IntegrationToken` row → connected via `oauth_token` (rolled back).
- Live pages via browser: `/integrations/outlook`, `/integrations/github`, `/integrations/teams`, `/integrations/slack`, `/integrations/salesforce` all render truthful "Disconnected"/Connect gates with the restarted backend on :8001.
- Backend was restarted twice via `scripts/stop-backend.sh` + `scripts/start-backend.sh --daemon` (it does not run with `--reload`); latest restart includes my alias change.

## In-flight: component test migration — RESOLVED

Final state (all green): 14 MSW suites in `components/__tests__/` + Zendesk (also MSW) + 3 suites in `tests/integrations/` + `tests/pages/__tests__/integrations-bitbucket.test.tsx` + `tests/pages/__tests__/integrations-index.test.tsx` — **483/483 tests pass**.

The patterns that made them green (reuse for any new integration test):

1. Default MSW handler: `rest.get('/api/integrations/connection-status', ...)` returning `{ providers: { <id>: { connected: true, source: 'user_connection' } } }` (quote hyphenated ids).
2. Disconnect simulations: point overrides at `/connection-status` — non-200/network-error bodies are fine; the component treats all of them as "not connected".
3. The component catch logs `'Connection status check failed:'` (Discord kept its own `'Connection check failed:'`).
4. QuickBooks' `beforeAll` MSW warm-up must hit a GLOBALLY handled route (`/api/health` in `tests/mocks/handlers.ts`) — per-file handlers aren't registered yet at that point.
5. `tests/pages/__tests__/integrations-bitbucket.test.tsx`: the page treats a stored `bitbucket_access_token` as connected even if the status call fails (its own OAuth flow's real credential); async status check means the badge lands after first paint — use `waitFor`; flush with `await act(async () => {...})` before asserting connected state (the ingestion panel + status check update state outside act, and with `console.error` mocked React defers those commits).
6. `tests/pages/__tests__/integrations-index.test.tsx`: the hub's "connected" comes from `connection-status`; health probes only flip connected cards between healthy/error. Cards with no connection render "unknown" — never "error". Health probes now send `authHeaders()` (assert the call shape with the headers arg).

## File map to avoid clobbering

**Mine (this migration):** the 19 component/page files listed above, `backend/api/integration_status_routes.py` (only the `IntegrationToken` source + `_IT_PROVIDER_ALIASES` + docstring bullet 3), and the 14 test files listed above.

**Others' in-flight work I saw and did not touch:** `IngestionStatusPanel.tsx` / `WithIngestionStatus.tsx` + their tests, `IntegrationHealthDashboard*`, backend ingestion/OAuth/token-refresher changes (`oauth_routes.py`, `token_refresher.py`, `core/oauth_handler.py`, `integration_health_endpoints.py`, `atom_communication_ingestion_pipeline.py`, …).

If you bulk-revert or regenerate any file in my list, please re-add the `connection-status` behavior afterwards (or ping the user to rerun my codemods).

## Operational notes

- Backend on :8001 runs **without** `--reload`; use `scripts/stop-backend.sh` + `scripts/start-backend.sh --daemon` after backend edits. Frontend on :3000 hot-reloads.
- The live check used the in-app browser session logged in as `ui-check-0829@example.com` (scratch user; a first-run onboarding modal may be up — Escape dismisses, don't complete it).
