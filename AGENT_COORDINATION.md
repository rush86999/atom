# Agent Coordination Doc

Multiple agents are working in this workspace concurrently. This doc is the shared
communication surface: **read it before you start, append to it when you finish.**

Ground rules:

- Append session entries at the bottom with a timestamp. Don't rewrite others' entries.
- Announce process restarts (backend/frontend/mock servers) in your entry.
- Avoid `git stash` for "check the baseline" workflows — it stashes *everyone's* WIP,
  not just yours. Prefer `git worktree add` for pristine-tree test runs.
- Run tests scoped to the files you touched; note any pre-existing failures you saw
  so others don't chase them.
- Backend restarts wipe in-memory caches; expect first-request warmup of ~10-15s.

---

## Environment snapshot (as of 2026-08-29 ~20:00)

| Thing | State | Owner/notes |
|---|---|---|
| Frontend dev server | `localhost:3000` (Turbopack) | was already running; not started by me |
| Backend | `localhost:8001`, uvicorn `main_api_app:app` | **restarted multiple times by multiple agents** (19:35:40 one agent, 19:53:52 PID 68204, …). Check `lsof -iTCP:8001 -sTCP:LISTEN` for the current PID before killing anything. Logs for my instance: `/tmp/backend_8001.log` |
| Frontend→backend URL | `.env.local`: `NEXT_PUBLIC_API_URL=http://localhost:8001` | |
| Microsoft mock Graph | `backend/scripts/microsoft_mock_server.py` (untracked) | belongs to the journey-test WIP; Brennan-fixture data comes from here |
| Test account | `dev.check@brennan.ca` / `DevCheck!2026` (user id `ced3e0f0-e813-426f-bb17-1795a969aa7e`) | created by me via the real register API for live verification — delete if unwanted |
| ZCode in-app browser | tab open at `/integrations/outlook`, logged in as dev.check | ⚠️ while verifying I found a JWT for a *different* user (`sub=8cce0c47-…`, resolves to "Rish Maniar" / journey user) stored under `auth_token` in that browser, alongside `user_email=dev.check@…`. I did **not** put it there. If you have a flow that logs in through `localhost:3000`, this may be yours. |

---

## Changes made this session (2026-08-29, agent: ZCode/coding session)

All changes are **uncommitted working-tree changes on `main`**, mixed in with the
pre-existing WIP. Nothing was committed.

### Backend

1. **Cross-user token leak fixed — behavior change**
   - `backend/integrations/outlook_service.py` `_get_access_token()`: removed the
     "fallback to any active outlook/microsoft token" query. A user with no own
     active `IntegrationToken` row now gets `None` → routes return
     `{"data": [], "count": 0}` instead of **another user's mailbox/calendar**
     (reproduced live before the fix: a fresh user got 50 events from the journey
     user's token).
   - Same leak removed in `backend/integrations/zoho_workdrive_service.py`
     (cross-user fallback) and `backend/integrations/chat_orchestrator.py`
     `_try_zoho_crm_write` (now filters `IntegrationToken.user_id == user_id`).
   - **If your code/tests relied on the any-user fallback, they will now see
     empty results.** Verified live after fix: unconnected user gets
     `count: 0` from `POST /api/integrations/outlook/events`.
   - Intentionally NOT changed: the workspace adapters in
     `core/integrations/adapters/*` (documented "single-operator semantics"
     fallbacks) and tenant-scoped zoho services — flagged, not touched.

2. **Event-loop blockers fixed** (one of these froze the backend for 21+ min —
   main thread stuck in a blocking SSL read; every route timed out until restart)
   - `backend/api/agent_control_routes.py` `restart_atom`: `time.sleep(2)` →
     `await asyncio.sleep(2)`.
   - `backend/integrations/outlook_integration.py`: added `timeout=15` to 4 sync
     `requests` calls inside `async def` methods (no timeout = can block the loop
     forever).
   - `backend/integrations/notion_routes.py`: added `timeout=15` to 4 sync calls.
   - ⚠️ Root cause of the original hang was NOT conclusively identified (no
     py-spy on macOS without sudo). If the backend freezes again: `sample <pid>`
     and look for `_ssl__SSLSocket_read` / `PySSL_select` on the main thread,
     then audit recently-changed code for sync `requests.*` without timeout
     inside `async def`.

### Frontend

3. **Crash fix** (`components/OutlookIntegration.tsx`): the reported
   `Cannot read properties of undefined (reading 'charAt')` came from rendering
   raw Microsoft Graph attendees (`{emailAddress:{name,address}}`) as
   `{name,email}`. Added `normalizeOutlookEvent()` (mirrors the existing
   `normalizeOutlookEmail` pattern) applied in `loadEvents`; it also maps
   `location.displayName` and snake_case `show_as`/`is_all_day`. Avatar fallback
   is now `(name || email || "?").charAt(0).toUpperCase()`.

4. **Tests updated** (`components/__tests__/OutlookIntegration.test.tsx`): mocks
   migrated from the dead `GET /api/integrations/outlook/health` to
   `GET /api/integrations/connection-status` returning
   `{providers:{outlook:{connected:true}}}`; first test now awaits its async
   loads (in-flight MSW aborts were leaking console errors into the next test).
   Suite: 21/21 passing. `tsc --noEmit` clean.

---

## Git state notes (important)

- `stash@{0}` **"baseline-check2"** is a full snapshot of the entire working tree
  (everyone's WIP + my fixes) that I took to run a HEAD-baseline test comparison.
  A pop of it failed partway; I restored the tree with
  `git checkout stash@{0} -- .` and verified all content is back
  (89 files, all fixes present, suites re-run green). **Safe to
  `git stash drop stash@{0}`** once you confirm `git diff --stat` looks right to
  you (~89 files). `stash@{1}` "r84-wip" and below predate this session — untouched.
- Pre-existing test failures seen at HEAD (not caused by the above):
  `tests/test_covpush_w92_outlook_routes.py` — 61/64 fail, tests still target the
  old `/api/outlook` prefix (current mount is `/api/integrations/outlook`).
  `tests/test_covpush_bigfour.py` (7 fails, governance/linear tests) and
  `test_covpush_mail_office`/`test_bughunt_*` — failing at HEAD identically.

---

## Open items / needs an owner

1. ~~Stale foreign JWT in the in-app browser localStorage~~ **RESOLVED
   2026-08-29 late**: the "foreign" JWT (sub `8cce0c47-…`) belonged to the
   journey-test user whose `microsoft`/`outlook` IntegrationToken rows exist in
   `data/atom.db`. It was replaced by a clean dev.check session; nothing to fix.
   Note: multiple agents appear to share this browser profile — don't trust
   ambient localStorage identity, always check the JWT `sub`.
2. **Original hang root cause** — see backend note 2. The class-fix (timeouts)
   bounds any future stall to seconds, but the specific offender is unknown.
3. The untracked WIP files (`microsoft_mock_server.py`, journey tests,
   `IngestionStatusPanel.tsx` etc.) belong to the integration-journey work —
   I didn't touch them beyond reading.
4. ~~Live verification interrupted~~ **COMPLETED 2026-08-29 late** — see session
   log below.
5. Heads-up for whoever owns `integrations/outlook_service.py`: new commits
   landed on main during this session (`0f7ad4925` "add AZURE/OUTLOOK env
   fallbacks", `741e6a04e` "/events route alias", `9f0b8c0c2`). My per-user
   fix in `_get_access_token` is still present in the working tree — keep it
   if you refactor; the any-user token fallback was a real cross-user leak
   (reproduced before the fix).

---

## Session log

- **2026-08-29 ~19:00-20:00 — ZCode session (this doc's author)**
  Fixed Outlook attendee crash (frontend normalize layer), updated component
  tests to `connection-status`, diagnosed + restarted hung backend on 8001
  (twice), fixed cross-user token fallbacks (outlook/zoho workdrive/chat
  orchestrator), added timeouts to sync HTTP in async contexts, created
  `dev.check@brennan.ca` test user. Verified: 46+309+21 relevant tests green;
  live API checks scoped per-user. Left `stash@{0}` as tree backup (see above).

- **2026-08-29 ~20:30 — ZCode session, continuation**
  Completed the interrupted live verification. Along the way I misread a
  "regression": dev.check's `POST /events` returning 50 events was NOT the
  old leak — by then dev.check had its **own** active `outlook` IntegrationToken
  row in `data/atom.db` (someone ran a mock OAuth connect for it; thanks).
  Final state, all verified live in the browser as dev.check: page renders
  Connected, Calendar tab renders 50 mock events end-to-end through
  `normalizeOutlookEvent` — attendee initial avatars, `location.displayName`,
  `busy` badges from `show_as`, datetimes — with **no error overlay** (this was
  the exact code path of the original `charAt` crash). Backend serving this was
  PID 68204 (started 19:53:52, not by me) and it contains the per-user fix.
  No code changes made in this continuation — verification + doc updates only.

- **2026-08-31 ~11:20-11:40 EDT — ZCode session (canvas RCA + LLM failover fixes)**
  Root-caused the canvas `e7249cf9` "Could not reach the agent" failures. Files touched:
  `core/provider_health_monitor.py` + `core/llm/byok_handler.py` (connection-failure circuit
  breaker, threshold 1 / 60s cooldown — dead providers were re-paid connect-timeout cascades in
  EVERY LLM stage because failure recording sat after the `continue`), `core/chat_canvas_editor.py`
  + `integrations/chat_orchestrator.py` (`CanvasPlanUnavailable`: plan-step LLM failure now replies
  honestly instead of falling through to intent routing — that misroute fabricated edit-success
  claims and created junk TASKS; also backfills missing `chat_sessions` rows, fixes the per-turn
  `episode_segmentation_service: Session … not found` errors), `frontend-nextjs/pages/canvas/[id].tsx`
  (on client timeout, polls chat history ~60s for the late reply instead of instant error — the
  reply was often already in the DB).
  **Restarted the backend on 8001 three times** (11:26, and 11:38 → PID 36227); the 11:31 restart
  was NOT mine (another agent, unannounced — no doc entry). First-request warmup applies.
  Test notes: `test_provider_health_monitor.py` + `test_byok_handler.py` + `test_chat_canvas_editor.py`
  green (my changes); pre-existing failures NOT mine: 3 event-loop failures in
  `test_chat_canvas_editor.py` (`journey_events`, 2× `feedback`) fail on the clean tree too, and 2
  `canvas-detail.test.tsx` feedback tests fail from the in-flight uncommitted frontend WIP (I
  verified my edits pass those tests in isolation on a clean tree).
  Heads-up: AtlasCloud `ollama/mistral-large-instruct-2407` was connection-dead all day — with the
  breaker it now gets benched after 1 failure; expect `Circuit breaker OPEN for provider ollama`
  in the log. Outlook Mail.Send still 403 ErrorAccessDenied (unchanged, needs token re-consent).

- **2026-08-31 ~12:10-12:40 EDT — ZCode session (same as above), Mail.Send send-blocker**
  Root cause of the canvas email-send 403: the user's Outlook consent grant (minted 06:27 EDT)
  predates `b3767fbf6` (08:28 EDT) which added `Mail.Send` to `MICROSOFT_OAUTH_CONFIG` — refreshes
  never expand scopes, so `/me/sendMail` kept returning 403 ErrorAccessDenied. Fixes in
  `integrations/outlook_service.py` (fail-fast consent precheck: `last_send_error` +
  `_get_connection_scope`/`_scope_grants`) and `core/canvas_email_service.py` (actionable
  "reconnect Outlook" error + `needs_reconnect` flag in the response AND the canvas_audit reason).
  Live-verified against the real token row: the send now blocks with the reconnect message instead
  of a Graph 403. Azure app registration validated to ACCEPT the Mail.Send scope (authorize probe
  returned a login page, no AADSTS), so user re-consent will grant it. 4 new unit tests; 
  `test_covpush_outlook.py` + `test_email_policy.py` green (207). Pre-existing, not mine:
  5 failures in `test_covpush_emailcrm.py` (identical on clean tree), 3 event-loop failures in
  `test_chat_canvas_editor.py`. **I did NOT restart the backend this session** — another agent
  replaced 8001 with PID 43255 at 12:24, which already includes the above code.
  **Action needed by the human**: reconnect Outlook in Settings → Integrations to mint a
  Mail.Send token; then re-approve the email send.

- **2026-08-31 ~12:45-13:15 EDT — ZCode session (same as above), disconnect/reconnect UX**
  User asked for disconnect+reconnect after wrong auth. Found: backend DELETE
  `/api/v1/auth/oauth/tokens/microsoft` already fans out to [microsoft, outlook] rows, and the
  OAuth callback UPSERTS (revoked row → active with new scope) — so both primitives existed.
  Fixed the frontend: `Microsoft365Integration.tsx` Connect button pointed at
  `/api/integrations/microsoft365/auth/start` — a route that DOES NOT EXIST (legacy mock flow,
  MICROSOFT_365_CLIENT_ID defaults "mock_client_id"); now uses the canonical
  `/api/v1/auth/oauth/microsoft/authorize?token=<jwt>`. Added Reconnect + Disconnect buttons,
  a missing-Mail.Send scope warning banner (reads GET /tokens which now returns `scope`),
  and the canvas email composer offers "Reconnect Outlook now?" when a send fails with
  needs_reconnect. Restarted 8001 (13:13 EDT → PID 50957). Suites: w81a back to its
  7 pre-existing failures only, outlook+policy 207 green, canvas-detail 46/46 pass.

---

## 2026-09-01 — ZCode session: Phase 0 Task 1 (Outlook poller token plumbing)

**Change** (working tree, uncommitted): `integrations/atom_communication_ingestion_pipeline.py`
— `IngestionConfig.user_id` field; `start_outlook_poller`/`start_poller` accept `user_id` and
store it in the stream config (idempotent re-start refreshes it); `_fetch_outlook_messages`
now resolves the token for the configured user instead of `user_id=None`. Callers:
`api/oauth_routes.py` passes `current_user.id` on Microsoft connect; `main_api_app.py`
startup recovery passes the active IntegrationToken owner's user_id.

**Why**: the 2026-08-29 cross-user-fallback removal left the poller calling
`_get_access_token(user_id=None)`, which returns None by design → poller never fetched mail
(single user included). No behavior regressions: no-cross-user-fallback rule untouched;
without a configured user the poller still skips with the same warning.

**Verified**: `tests/test_email_api_ingestion.py` 21/21 (2 new regression tests, red first).
No restart performed. Next: Tasks 0.2 (poll interval env) and 0.3 (email secrets redaction).

---

## 2026-09-01 — ZCode session: Phase 0 Tasks 2-3 (poll interval env + email redaction)

**Change** (working tree, uncommitted): `integrations/atom_communication_ingestion_pipeline.py`
— `start_outlook_poller` interval default now reads `ATOM_OUTLOOK_POLL_SECONDS`
(60s default, 15s floor, explicit arg wins); `_normalize_message_impl` email branch
(EMAIL/GMAIL/OUTLOOK — shared choke point for poller + webhook paths) runs
`SecretsRedactor` on body content before storage, kill switch `ATOM_EMAIL_REDACTION_ENABLED`.
Env docs: `CLAUDE.md`, `docs/reference/ENVIRONMENT_VARIABLES.md`.

**Verified**: `tests/test_email_api_ingestion.py` 24/24, `tests/test_ingestion_status_routes.py`
25/25 (start_poller signature change did not break the other consumer). Phase 0 complete —
next: Phase 1 (provenance spotlighting) or Phase 2 (drive tree) on request.

---

## 2026-09-01 — ZCode review round 2: ingestion isolation + retrieval boundary

**Change**: `atom_communication_ingestion_pipeline.py` — (a) per-owner cursors are the ONLY
cursor source: a first-time owner starts from its own initial-sync window, never the global
`last_fetch_outlook` key (a new owner inheriting another mailbox's watermark skipped its older
mail); (b) `$orderBy=receivedDateTime desc` on the Graph walk so paging order is deterministic
(400 → retry unsorted + flag order untrusted); on page-cap truncation the watermark moves to the
OLDEST consumed timestamp (provable boundary) instead of `newest`, which jumped past unconsumed
pages; (c) `search_communications(owner_user_id=...)` + module helper
`_filter_communication_records_by_owner` enforce the mailbox boundary on retrieval: records
stamped for a different owner are dropped, ownerless (legacy/unstamped) records stay visible.
`documents_hybrid` conversations leg, `memory_context_assembler._knowledge_leg`,
`assemble_memory_context(user_id=...)` and the chat orchestrator thread the request-scoped
identity through to that filter. `memory_context_assembler` fake-legged tests updated for the
new kwarg.

**Why**: Greptile re-review (score 1/5) flagged the three remaining holes with evidence.

**Verified**: `tests/test_email_api_ingestion.py` 33/33 (new: boundary-watermark truncation,
no-inheritance, owner-filter), `tests/core/test_knowledge_spotlighting.py` 10/10 (owner
threading), assembler/agents/status/memory-index 126/126. py_compile clean. fetch-state file
pollution made the new-owner test order-sensitive — the test now clears its own per-owner key
first (test residue under `backend/data/` is gitignored).
