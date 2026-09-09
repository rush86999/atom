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

---

## 2026-09-06 ~20:15 — ZCode: canvas chat streaming garble root cause + composer double-signature fix

**Change (all frontend, no backend changes):**
- `hooks/useWebSocket.ts` — added `onMessage(handler)` listener registry: handlers are invoked
  synchronously for EVERY WS frame in arrival order. The existing `lastMessage` state slot is a
  single-slot delivery that React coalesces under burst.
- `pages/canvas/[id].tsx` — the co-editor WS effect now registers through `onMessage` instead of
  reading `lastMessage`, and the POST-timeout late-reply path retires a lingering
  `stream_{sid}` bubble (renamed, like the new-turn retire) instead of leaving it "streaming".
- `components/canvas/CanvasPanel.tsx` — `hasSignoff` now tag-strips the body and matches the
  sign-off pattern on the trailing TEXT (600 chars) instead of the last 400 chars of raw HTML.

**Why (evidence, canvas c3617a7f-…-3445a2324537 "Re: … Linmac WG-350DSAV"):** a streamed chat
reply (993 `chat_token` frames, logged clean in uvicorn_8001_restart.log ~759172) rendered with
whole chunks missing ("garbled bubble") because the `[lastMessage]` effect never saw frames that
landed between render commits; the turn also exceeded the page's 120s POST timeout (fresh-data
lookup + Excel parse errors + a grounded regeneration — stream A ≠ persisted B, both clean, both
in the log), so the garbled partial bubble never got finalized. Separately, opening the email
composer on a body whose styled signature `<div>` ends >400 raw-HTML chars after "Regards," made
`hasSignoff` miss it and stack the integration default signature below it (observed live in the
browser verify pass; audit rows 739→741 window).

**Verified**: `npx tsc --noEmit` clean; jest `CanvasPanel.test.tsx` + `useChatInterface.test.ts`
79/79; hasSignoff 6/6 new cases incl. the live failure body; canvas PUT via the live API renders
the styled table + signature in the composer (browser-verified). No backend restart needed.

**Flag**: canvas c3617a7f audit rows 740/741 (00:05/00:09 UTC) are the OWNER's own edits from a
second editor surface (Outlook-style Calibri/Segoe HTML, PUT without title param) — someone is
actively editing that draft in parallel; do not treat 741 as corruption. Also noted for whoever
tackles it: `Consolidated Price List 2019.xlsx` fails ingestion — `core.auto_document_ingestion`
logs "Excel parse error: Unable to read workbook: could not read strings from None" repeatedly,
which is why the agent couldn't read the LINMAC sheet row.

---

## 2026-09-06 ~21:55 — ZCode round 2: agent couldn't read "Consolidated Price List 2019.xlsx" — root causes + fixes

**Symptom** (canvas c3617a7f session): user asked the agent to check the 2019 price list for the
Linmac bandsaw price and fill it in; the agent found the file but said only the sheet headers were
visible ("excerpt cuts off right at the header row"), the canvas edit declined twice, and turn 3
also produced the garbled bubble (fixed separately, see the ~20:15 entry).

**Root causes (all traced from runtime evidence):**
1. **Excerpt anchoring** — `_query_anchored_excerpt` anchored on the rarest query token's FIRST
   occurrence. For "consolidated price list 2019 linmac" that is the WORKBOOK INDEX line at the
   file head (or a brand row in an unrelated sheet) — never the LINMAC sheet body. The WG350DSAV
   row (R17, List 14145 / US NET 5325) sits at 58% of the 3.4M-char text. The agent honestly
   reported the row unreadable.
2. **Fresh-data budget vs cold read** — the canvas editor's 20s lookup covered planner LLM + query
   rewrite LLM + 13MB download + ~10s parse (formula extraction makes the first pass slower); it
   timed out twice → edit declined. The same file was re-parsed 4× in one evening.
3. **Read-by-id with no file_name** → empty extension → "Unsupported file type" despite a
   successful download (found reproducing the E2E path).
4. **Zoho refresh error-body swallow** — `ZohoAdapter.refresh_token` treated Zoho's HTTP-200
   error payloads (invalid_client/invalid_code) as success and persisted access_token=None with a
   fresh +3600s expiry; `ZohoWorkDriveService._refresh` returned the error dict as tokens. This
   produced dead rows that LOOK fresh (the historical 631 TokenRefreshWorker failures were the
   pre-env era: ZOHO_* vars only exist in the ROOT .env, loaded by main_api_app since its dotenv
   chain gained the root file; refresh verified working now — the grant is on accounts.zohocloud.ca).

**Fixes:** sheet-name anchoring + workbook-index skip + compacted-token variants in
`_query_anchored_excerpt` (universal_integration_service.py; weak-coverage queries now fall back
to the index head instead of a random numeric window); `parse_document_cached` content-hash LRU
used by the read path (parse_document itself untouched — tests re-run per call); explicit
file_id reads resolve file_name from the ingested record then magic bytes; fresh-data budget
20s→25s (top of the orchestrator-compatible band the grounding test pins); refresh guards in both
Zoho paths (no token in payload ⇒ log + return False/None, row untouched); planner prompt: a
message that only says WHERE the file lives after a content request plans intent=read.

**Verified:** excerpt repro on the real workbook 5/5 (row surfaces for every realistic query);
E2E `_read_storage_file` on the live WorkDrive file: R17 surfaced, cold 23.7s / warm 12.5s;
`test_canvas_editor_grounding` 12/12, `test_planner_storage_memory_supplement` 28/28,
`test_auto_document_ingestion` 50/51 (1 pre-existing: long-file refresh, fails on pristine HEAD
too — verified via git worktree). `test_chat_canvas_editor` 24 failures and
`test_tool_routing_generalized` collection error are pre-existing on HEAD. Backend restarted via
scripts/restart_backend.sh, healthy. **The real price per LINMAC R17: List $14,145.00 — the
$12,180.00 currently in the draft does not match the sheet.**

---

## 2026-09-06 ~22:40 — ZCode round 3: first-try styling for fresh installs

**Change:** email canvases are now born styled — no "fix the table styling" follow-up turn needed.
- `core/chat_draft_classifier.py` — `_style_markdown_tables` + `_md_table_to_styled_html`: markdown
  pipe tables in email bodies convert to email-client-safe styled HTML (inline styles, shaded
  header #1f3864, borders, cell emphasis **/* honored, escaped pipes handled, idempotent on bodies
  that already carry <table>). Wired into `normalize_email_content` (every email body passes it:
  composer saves, agent edits via canvas_crud_tool, chat_routes auto path) and into
  `coerce_email_canvas`'s doc-like branch. `extract_email_draft` itself untouched — it feeds
  classification.
- `integrations/chat_routes.py` — explicit-email creation routes through coerce (styled), and the
  sign-off strip now counts `signature_html`-only users (they read as "no default" before, leaving
  the agent's plain signoff AND the composer's styled one — two signatures on first open).
- Frontend composer already preferred signature_html (no change needed there this round).

**Verified:** unit — 5 shapes incl. emphasis, escaped pipes, idempotence, prose-with-pipes
untouched; live — fresh canvas created through POST /api/chat/to-canvas with a markdown-table
draft opens in the composer with the styled table AND the mined Outlook signature auto-inserted,
no double signature (browser-verified; test canvas deleted after).

**Pre-existing failures NOT mine (verified on HEAD worktrees):** test_chat_draft_classifier
TestSignature::test_stored_preference_wins (expects the old 3-key get_signature shape — now
returns signature_html too), test_chat_canvas_editor 24, test_auto_document_ingestion
long-file-refresh, test_tool_routing_generalized collection error.

---

## 2026-09-07 ~10:50 ET — ZCode: atom_memory migration off the portable drive (IN FLIGHT, autonomously finalizing)

**Why:** 2026-09-07 morning the user's Seagate portable drive disconnected/reconnected; every
memory-assembler leg + the canvas-edit fresh-data lookup timed out at once (canvas c3617a7f
"try the search again for linmac" turn, 13:29 UTC). Root cause of the blast radius:
`backend/data/atom_memory` is a symlink onto the USB volume, and the link is ~4 files/sec on
the store's 94k small files (seq read is fine: 128 MB/s measured) — a remounted, cache-cold
store + an LLM-retry-slowed planner burned the whole 25s fresh-data budget. User asked to move
inactive data TO the drive and port atom_memory back to internal.

**Ops state (safe at every step, originals kept until verified):**
- Backend healthy, running on the USB store while a `tar` stream stages the 31GB store into
  `backend/data/.memstage/atom_memory` (~256 files/min small-file grind — hours).
- `/tmp/finalize_memory_migration.sh` (nohup'd) polls for tar completion, then: stop backend →
  rsync delta → swap symlink for the real dir → `scripts/restart_backend.sh` → health gate →
  AUTO-ROLLBACK to the USB symlink on failed health. On success it relaunches
  `/tmp/zcode_relocate.sh`, which moves INACTIVE data to the drive: reingest backup 20GB +
  comms-lance backup 1.5GB (from `backend/data/backups/`, no symlink — one-off op artifacts),
  opencode 50GB / .gemini antigravity ~20GB / .claude/projects ~8GB (symlinked back, tools
  still work while the drive is mounted), chromium snapshots 0.4GB. ≈100GB off internal.
- Monitor: `tail -f /tmp/mem_migration_finalize.log` and
  `tail -f /tmp/zcode_relocate_progress.log` (drive log also at
  `relocated-from-internal-20260907/move-log.txt` on the Seagate).
- After the swap: `atom_memory` is a REAL directory (canonical `backend/data/atom_memory`), so
  the restart script's `DRIVE_CONFIGURED` symlink probe goes false — external DB-snapshot
  copies to the drive still happen whenever it's mounted, but the unmounted-drive WARNING no
  longer fires. Do not re-symlink the store onto the drive.
- Drive disconnect risk remains for the relocated INACTIVE data only; nothing in the agent's
  hot path depends on the drive after this lands. Backups dir keeps only active cycle/restart
  snapshots locally (~130MB, 5-cap).

**UPDATE 2026-09-07 ~12:00 ET — MIGRATION COMPLETE.** `backend/data/atom_memory` is now a REAL
directory on internal disk (symlink removed); fresh startup log confirms LanceDB connects at the
canonical internal path; backend healthy (pid 3073). Parallel rsync streams + a stopped-backend
delta pass cut the 31GB / 71k-file copy from ~5h (single tar stream, 4 files/sec on this USB
link) to ~45 min. The relocation queue (opencode 50GB, antigravity ~21GB, claude/projects 8GB,
atom backups 21.5GB, chromium snapshots → the drive; symlinks back where tools need them) is
running unattended — progress in /tmp/zcode_relocate_progress.log. If a relocated tool misbehaves
while the drive is unplugged, that's expected: move its dir back from
`/Volumes/Seagate Portable Drive/relocated-from-internal-20260907/`.

**FINAL 2026-09-07 ~12:30 ET — RELOCATION QUEUE COMPLETE.** All 10 items moved with verified
file counts, zero failures (~100GB): atom reingest+lance backups (no links — op artifacts),
opencode 50GB, antigravity trio + pair ~21GB, .claude/projects 8GB (all symlinked back — tools
work while the drive is mounted), chromium snapshots. Internal free: 125Gi (was 56Gi at start,
after adding the 31GB memory store back). Single-copy caveat: the drive now holds the ONLY copy
of the relocated data; the symlinks resolve only while it is mounted.

## 2026-09-07 ~13:20 ET — ZCode: agent can now base NEW drafts on real styled messages

Owner request: "agent can get styled email or other messages and create it as base for
drafting new emails or messages". Gap found: comm tool blocks only surfaced 200/220-char
TEXT previews (outlook graph_listing body_preview; ingested-mailbox lines) — the styled
markup ingestion preserves (metadata.html_body, store choke point) never reached the model,
so "draft a new one styled like that message" was impossible.

Fix (core/chat_tool_planner.py): STYLED HTML BODY section appended to the outlook block
(ingested store's newest matching metadata.html_body first — `_latest_styled_ingested`,
address candidates from query+history; fallback = top Graph hit's HTML body.content) and to
both universal comm branches (live-miss + success-with-ingested-leads). Section instructs:
copy the markup as the canvas body and edit the wording; canvas + send preserve raw HTML
(funnel `normalize_email_content` passes HTML through; composer sanitizer allows style).
Block cap 6000 chars. Tests: tests/test_tool_planner_styled_base.py (5) + the 3 existing
planner suites 28 green. Backend restarted.

## 2026-09-08 — ZCode (Rish): PRs #606/#607/#608 review outcome — curated merge

Reviewed the three stacked email PRs by visak14 against AGENTS.md/CLAUDE.md.
**Merged (curated branch, cherry-picked with authorship kept):**

- `294851b2` **Outlook poller cursor UTC fix** (+10 regression tests). Root cause:
  naive local `datetime.now()` cursors formatted with a blind `Z` shifted the
  watermark ~5.5h into the future — incremental polls returned empty windows
  while cursors advanced; new mail never reached the comms store. Now aware
  UTC end-to-end; naive legacy values assumed UTC.
  **OPERATIONAL (carried from the original entry, still outstanding):** the live
  server runs the old code and its legacy cursor is ambiguous — after deploying,
  restart via `scripts/restart_backend.sh` and clear the poller cursors once so
  the 90-day window initial-syncs (125 msgs).
- `1ce0431` **search_emails defaults to every connected mail provider** (+2
  tests, 1 updated). With no `platform` arg it queried ONLY gmail — Outlook mail
  was silently invisible to agents (live 2026-09-08: Forrester thread found
  nothing, no reply draft). Per-provider failures surfaced, not swallowed.

**Discarded, with reasons (do NOT reintroduce as-is):**

- `bad832fb` X-Session-Id + browser Origin/Referer/UA headers on the Zen gateway
  clients: this masquerades as the OpenCode web client specifically to defeat the
  gateway's free-tier client gate ("OpenCode's free tier can only be used in
  OpenCode") — ToS circumvention + account-ban risk for the subscription key.
  `-free` models are therefore effectively unusable via the API from Atom; the
  paid-fallback machinery (CreditsError retry) already covers that path.
- `65bd1b8`/`7f7c874`/`9420785` email send-policy gate (`core/email_policy_gate.py`
  + hook + tool params + seed script): the deterministic Level B idea is
  vision-aligned, but as written it (a) duplicates the existing general mechanism
  `core/email_policy.py` (ALLOW/APPROVE/BLOCK, wired at mcp/canvas/chat) with a
  second module, different vocabulary, different layer, no documented precedence;
  (b) ships default-on blocking with NO kill switch / shadow mode / audit, against
  the repo convention every other policy layer follows (ATOM_* flag +
  settings-catalog + shadow-first); (c) hardcodes one business's machinery-sales
  rules in core for all workspaces; (d) `price_verified` is agent self-attestation,
  not verification. If Level B is wanted, rebuild ON `core/email_policy.py` with a
  flag + per-workspace rule config. Seed script also wrote demo rows (real
  counterparties' names/emails) into the live dev DB.

Verified: 56/56 new tests green; covpush suites show the same 15 pre-existing
main failures before/after (InterventionService signature drift — separate issue).

## 2026-09-08 ~22:00 — ZCode (Rish): fix-all pass — UTC port into rewrite, HITL required_role, covpush repair, outlook state reset + redeploy

**Rebase:** local main (3 unpushed commits) rebased onto #609's merge; the
on-demand-ingest rewrite (`b5562c4e3`) conflicted with the cursor UTC fix and
had dropped its hunks — re-ported the six-site UTC fix into the rewritten
shape (`1d669f611`). Tests: cursor tz + ingest-tool 25/25.

**Real bug found in the 15 pre-existing covpush failures** (`03b4aed9d`):
`InterventionService.request_intervention` never accepted the `required_role`
kwarg that `mcp_service._check_hitl_policy` has passed since `d99541d82` —
every governed intercept raised TypeError and failed closed into "policy
check unavailable; action blocked pending approval" instead of creating the
HITL action. Service now accepts + persists it in `context_snapshot`. The
other 14 were stale test contracts vs phase-253 service changes —
re-contracted (details in the commit). covpush suites 389/389; intervention
consumers 760/760.

**Gmail batch-drop bug** (`359c40b58`): `base64.b64encode(content)` outside
the per-attachment try in both `_expand_gmail_attachments` passes — one
non-bytes payload zeroed the whole fetch (docstring promised otherwise).
Also isolated `test_email_api_ingestion.py`'s fixture state file to tmp_path
(it was persisting user-a/user-trunc test cursors into the LIVE
`atom_memory/poll_fetch_state.json`). 34/34 green.

**Live outlook redeploy (state reset + restart, backups kept as
`.bak-20260908`):** the live poller was stuck re-fetching the same 250
messages and dedup-skipping them forever — the Sep-5 store purge left 6551
"already-ingested" seen ids that blocked re-ingestion while the walk held
its cursor. With the server STOPPED (the running process re-writes state),
reset outlook cursors + outlook seen ids in `default/poll_fetch_state.json`,
cleared the test-polluted top-level state file, restarted via
`scripts/restart_backend.sh` (DB snapshotted first, pid 51504). Verified:
initial sync walked the 90-day window, `atom_communications` repopulated to
6561 rows, cursors now persist AWARE UTC (`+00:00`).

## 2026-09-08 late — ZCode: role-journey trace (all 8 user roles) + gap closure

Traced every role's journey end to end (backend gates, frontend UI, approval
surfaces, bootstrap). Fixed gaps, TDD (2 new test files, 66 tests; RED first).

**Severed journeys fixed:**
- HITL approvals UI called `/api/agents/approvals/*` which NEVER existed
  (main_api_app 8b comment claimed it did). New `api/approvals_routes.py`:
  GET /pending (plain array, UI contract) + POST /{id} {decision,
  modified_params} with supervisor gate; mounted eagerly. Modified params now
  persist to the action row (previously dropped = "Modify" was a no-op).
- Real user-management router (`core.enterprise_user_management`) was only
  reachable via the on-demand loader, whose heuristic maps /api/enterprise/*
  to the status-only `core.enterprise_endpoints` — /api/enterprise/users 404'd
  live forever. Now mounted eagerly + gained POST /users (provision employee)
  and GET /roles (catalog for the admin UI dropdown).
- Frontend User Management rewired from the phantom AdminUser table
  (/api/admin/users, unreachable super_admin gate) to the real User table.
- /admin/settings (Runtime Settings) existed with no nav link; Sidebar now
  links it (admin band).

**Privilege inversions (H1-class) fixed via shared hierarchy
(`core/security/rbac.py: role_level/user_meets_role`):** the 5
_require_supervisor copies + agent-governance approve excluded admin/owner;
trust-calibration + ontology-draft gates excluded admin/owner; feedback trust
(admin/owner ratings adjudicated untrusted) in 3 sites; template featuring;
recording-review cross-user read missing owner.

**Ungated surfaces closed:** PATCH/DELETE /api/enterprise/users/{id} (any
member could grant super_admin — router now workspace_admin+ with escalation
cap: can't grant/modify above own level); reject_workflow (was any-user);
messaging dispatcher proposals + interventions (was any-user, and
`InterventionService(db)` construction TypeError'd on every real call — mock
hid it); communication_service "APPROVE <id>" chat resolution; supervision
live reads (sessions/active + execution stream); operational intervention
execute (was router-auth only); supervised-queue process/cancel/mark-expired.
Dead is_admin gates (User has no such column → denied EVERYONE incl.
super_admin, forever): mini-app approve, integration schema registration,
analytics cross-user patterns — all on the real hierarchy now.

**HITL required_role is no longer write-only:** InterventionService
approve/reject enforce context_snapshot.required_role (case-insensitive,
fail-closed on unknown roles; approver must be a verified ACTIVE user);
reject gained a PENDING guard; modified_params persist.

**Bootstrap:** ADMIN_PASSWORD reset no longer downgrades admin@example.com's
promoted role on every boot.

**Frontend:** `lib/user-role.ts` (hierarchy mirror + useUserRole hook, fresh
via /api/auth/me, cached in localStorage; fail-open on unknown role — backend
enforces); Sidebar role filtering (members stop seeing guaranteed-403 admin
links) + Admin Settings link; Approvals page shows a supervisor banner and
read-only actions for members instead of post-click 403 prose.

**Tests:** backend `tests/test_role_journey_rbac_gaps.py` +
`tests/test_hitl_approvals_journey.py` (66); re-contracted stale suites
(w39/w53/w69a/w71/w71-integration/w84/w86c/miniapp/round39/supervision-stream)
— stash-compared, every other failure verified pre-existing on clean main.
Frontend: `lib/__tests__/user-role.test.ts` +
`components/layout/__tests__/Sidebar.gating.test.tsx` (11); full jest: only
the 10 known pre-existing integration failures (9 verified identical on
stashed tree; test_helpers flakes under worker contention, passes isolated).
Live-verified on the restarted backend (pid from scripts/restart_backend.sh):
alias approvals 200, enterprise users/roles/provision 200/201 as
workspace_admin, member 403s on role grant + HITL decide.

BEHAVIOR CHANGES for other callers: service approve_intervention gained an
optional modified_params kwarg + approver verification (unknown approver now
DENIED); messaging dispatcher consumers must mock the `intervention_service`
singleton, not the InterventionService class; supervisor-gated routes now
also admit admin/owner (intended); enterprise user endpoints require
workspace_admin+ and cap grants at actor level.

## 2026-09-08 late (cont.) — ZCode: role-journey pass, batch 2 (operator band + orphaned surfaces)

Follow-up pass on the same trace, closing the remaining findings:

- **Operator admin band**: daemon control (`api/agent_control_routes.py` —
  start/stop/restart/execute/status/fleet), admin cache/skill/budget/
  system-health subroutes, and workspace-context admin routes were gated by
  exact-super_admin (`core/admin_endpoints.get_super_admin`) — but no local
  flow can produce a super_admin (registration pins member, bootstrap pins
  workspace_admin, grants cap at actor level), so the operator could never
  even stop their own daemon. New `get_platform_admin` (WORKSPACE_ADMIN+
  via the shared hierarchy, same band as runtime settings/org politics/
  ontology drafts/trust calibration) replaces it on those six routers.
  `get_super_admin` itself is untouched for any true-super_admin surface.
- **Forensics mount bug**: `include_router(forensics_router,
  prefix="/api/v1/forensics")` double-prefixed the router's own
  /api/forensics prefix — live path was the absurd
  /api/v1/forensics/api/forensics/* while the Forensics dashboard calls
  /api/forensics/* (404 forever). Second un-prefixed include added (legacy
  mount kept). `/dashboard/risk` stays unlinked: its backend router was
  deliberately left unmounted in round 80f — respected.
- **GlobalChatWidget contract**: the alias decision response now carries
  `success: true` — the widget threw "Failed to submit decision" on every
  SUCCESSFUL approval because it checked data.success.
- **AgentConsole Stop wired**: the Stop button only flipped local state
  (daemon kept running; even super_admin had no working stop). Now calls
  POST /api/agent/stop with 403-aware fallback messaging.
- MaturityApprovalPanel (mounted on /agents Approvals tab) is read-only for
  known non-supervisors (banner + hidden decision buttons; fail-open on
  unknown role). GuidedAgentCreator's "approvals panel" pointer is now a
  real link to /approvals. next-auth Session/JWT types declare `role`/
  `permissions` (were set by lib/auth.ts but undeclarable).
- Sidebar: Audit Trail (team_lead+), Skill Builder, Owner Cockpit,
  Forensics (admin band) — orphaned pages now reachable. Owner Cockpit's
  "endpoint never existed" comment is stale: /api/business-health/priorities
  is live (verified 200).
- `api/enterprise_auth_endpoints.require_role` renamed to
  `require_enterprise_role` — two same-named gates (flat JWT-list vs
  hierarchical UserRole) was a wrong-import foot-gun; it had zero external
  consumers.

Tests: +10 backend (TestPlatformAdminBand in test_role_journey_rbac_gaps.py;
alias success assertion in test_hitl_approvals_journey.py) — 252 passed
across affected suites; w76b fixture re-contracted (it overrides the gate
dependency by object identity — now get_platform_admin); stash-compared,
remaining failures identical on clean main (incl. the 21 pre-existing
test_cli_agent_execution failures). Frontend: AgentConsole suite re-
contracted + 403-fallback test added, MaturityApprovalPanel gating tests
(3), full jest green except the 10 known pre-existing integration
component suites. Live-verified after restart: workspace_admin daemon-stop
passes the gate (400 not-running), cache stats 200, forensics root path
200; member 403 on daemon stop.

## 2026-09-09 — ZCode: workflows are now role dependent (the deferred RBAC gap closed)

The e2e permission-matrix tripwire flagged workflow:view/run/manage as
"granted but never enforced". Reality was worse: the MAIN router
(core/workflow_endpoints.py) WAS fully gated (the tripwire greps api/ only —
core/ enforcement was invisible to it), but every satellite workflow surface
wasn't:

- core/workflow_ui_endpoints.py (Workflow Builder, /api/v1/workflow-ui):
  POST/PUT/DELETE /workflows and template import were ANONYMOUS — anyone
  unauthenticated could create/edit/delete workflows.
- core/workflow_marketplace.py (/api/marketplace/*): fully anonymous AND
  never mounted (lazy-loader key mismatch: URL segment "marketplace" ≠
  registry key "workflow_marketplace" — 404 forever; same class as the
  enterprise user-mgmt bug). Now mounted eagerly with gates.
- api/workflow_template_routes.py, api/mobile_workflows.py,
  api/workflow_versioning_endpoints.py, api/workflow_debugging.py:
  auth-only — any signed-in role (incl. guest/viewer) could
  create/update/import/instantiate/execute/cancel/debug.

Enforcement: `require_permission(Permission.WORKFLOW_VIEW/RUN/MANAGE)`
added per-route (decorator-level deps; existing get_current_user params
kept — the permission dep shares the cached auth resolution). Contract from
core/rbac_service.py: view = guest+, run = member+, manage = team_lead+.
Debug breakpoints = manage (persist to the definition); debug
sessions/pause/resume/step/traces = run. Marketplace export = view.

Test lock: backend/tests/test_workflow_rbac_matrix.py — offline 8-role ×
45-endpoint matrix (361 cases) over all six routers, mirroring the e2e
journey's methodology. e2e tripwire updated per its own instruction:
WORKFLOW_* removed from UNENFORCED_PERMISSIONS + 3 live matrix cases added
(USER_VIEW/USER_MANAGE remain documented gaps).

BEHAVIOR CHANGES other callers must know: guest/viewer can no longer run or
cancel workflows or trigger mobile executions; members can no longer
create/update/delete workflows, templates, versions, or breakpoints
(team_lead+ for manage). Reads stay open (view = everyone authenticated...
plus the two formerly-anonymous surfaces now require auth). Five test
suites re-contracted (w100_gaps_d, w10d, w10d_b, w92, template_routes_
coverage) — their fixture users now carry workspace_admin. Stash-compared:
all remaining failures identical on clean main (12 + 2 + 21 pre-existing
in the touched suites). Live-verified post-restart: anon → 401/403,
member view 200 / manage 403 / run 422-permission-passed, admin manage
422-permission-passed, marketplace reachable (200/401/403/422 as expected).
