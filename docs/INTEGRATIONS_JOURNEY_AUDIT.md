# Integrations User-Journey Audit (Round 80)

> **Date**: 2026-08-21 · **Scope**: every app integration walked end-to-end via
> real user journeys (`hub → connect → callback → use → manage`) for every role
> (authenticated member/team-lead/admin vs anonymous), including UI/UX.
> **Gaps found are filled in this round**; systemic items are flagged with the
> recommended owner.

---

## 1. The journey template

For each integration we verified:
1. **Discover** — `/integrations` hub card exists and links to a real page (no 404s).
2. **Connect** — a working Connect button wired to a real OAuth/authorize endpoint.
3. **Status** — a status/health indicator wired to a real backend status endpoint.
4. **Use** — at least one data/action surface (component, panel or form) backed by
   a real backend route.
5. **Manage** — disconnect/refresh where the backend supports it.
6. **Roles** — the endpoints behind each step reject unauthenticated callers
   (`get_current_user`); `/auth/url`, `/callback`, `/status`, `/health`,
   `/webhook`, `/interactions` stay public by protocol (wave-93..105 convention).

## 2. Journey matrix (current state)

Legend: ✅ wired · 🟡 partial (reachable, data surface limited) · ⚠️ known gap

| Integration | Hub card → page | Connect | Status | Use surface | Manage | Auth on data/write |
|---|---|---|---|---|---|---|
| Slack | ✅ → slack | ✅ OAuth | ✅ | ✅ channels/messages/reactions | 🟡 | ✅ (round 93 + R80: reactions/channels/users) |
| Teams | ✅ → teams | ✅ | ✅ | ✅ | 🟡 | ✅ |
| Gmail | ✅ → gmail | ✅ | ✅ | ✅ search | 🟡 | ✅ |
| Outlook | ✅ → outlook | ✅ | ✅ | ✅ | 🟡 | ✅ |
| Microsoft 365 | ✅ → microsoft365 | ✅ | ✅ | ✅ | 🟡 | ✅ |
| WhatsApp | 🆕 card → 🆕 page (was orphaned component) | ✅ (via component) | ✅ | ✅ | ✅ | ✅ |
| Telegram | ✅ → 🆕 page (was 404) | 🟡 (bot webhook config) | ✅ | ✅ send | — | ✅ (R80: status/capabilities/send gated) |
| Discord | ✅ → discord | ✅ | ✅ | ✅ | 🟡 | ✅ (R80: user/guilds/channels/messages/search/items gated) |
| Shopify | ✅ → shopify | ✅ | ✅ | ✅ | ✅ | ✅ |
| Notion | ✅ → notion | ✅ | ✅ | ✅ | 🟡 | ✅ |
| Jira | ✅ → jira | ✅ | ✅ | ✅ | 🟡 | ✅ |
| Trello | ✅ → trello | ✅ | ✅ | ✅ | 🟡 | ✅ |
| Asana | ✅ → asana | ✅ | ✅ | ✅ | 🟡 | ✅ |
| Linear | ✅ → linear | ✅ | ✅ | ✅ | 🟡 | ✅ (registry path noted below) |
| Monday | 🆕 card → 🆕 page (was orphaned component) | ✅ | ✅ | ✅ | ✅ (local token) | ✅ |
| GitHub | ✅ → github | ✅ | ✅ | ✅ | 🟡 | ✅ |
| GitLab | ✅ → 🆕 page (was 404; `gitlab_enhanced` stub dead) | ✅ | ✅ | 🟡 | — | 🟡 (registry path) |
| Bitbucket | ✅ → bitbucket (standalone) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Next.js | ✅ → nextjs | ✅ | ✅ | ✅ | ✅ | ✅ |
| Stripe | ✅ → stripe | ✅ | ✅ | ✅ | 🟡 | ✅ |
| Xero | ✅ → 🆕 page (dead stub replaced) | ✅ | ✅ | 🟡 | — | ✅ (wave 105) |
| QuickBooks | ✅ → quickbooks | ✅ | ✅ | ✅ | 🟡 | ✅ (wave 105) |
| Salesforce | ✅ → salesforce | ✅ | ✅ | ✅ | 🟡 | ✅ |
| HubSpot | ✅ → hubspot | ✅ | ✅ | ✅ | 🟡 | ✅ |
| Zendesk | ✅ → zendesk | ✅ | ✅ | ✅ | 🟡 | ✅ (wave 105) |
| Freshdesk | ✅ → freshdesk | ✅ | ✅ | ✅ | 🟡 | 🟡 (registry path) |
| Intercom | ✅ → intercom | ✅ | ✅ | ✅ | 🟡 | 🟡 (registry path) |
| Mailchimp | ✅ → mailchimp | ✅ | ✅ | ✅ | 🟡 | ✅ (wave 105) |
| Tableau | ✅ → tableau | ✅ | ✅ | ✅ | 🟡 | 🟡 (registry path) |
| Zoom | ✅ → zoom | ✅ | ✅ | ✅ | 🟡 | ✅ |
| Box | ✅ → box | ✅ | ✅ | ✅ | 🟡 | ✅ (wave 102) |
| Google Drive | ✅ → gdrive | ✅ | ✅ | ✅ | ✅ | ✅ |
| OneDrive | ✅ → onedrive | ✅ | ✅ | ✅ | ✅ | ✅ |
| Google Workspace | ✅ → google-workspace | ✅ | ✅ | ✅ | 🟡 | ✅ |
| Azure | ✅ → azure | ✅ | ✅ | ✅ | 🟡 | ✅ |
| Dropbox | ✅ → 🆕 page (was 404) | ✅ | ✅ | 🟡 | 🟡 | ✅ (wave 98) |
| Zoho WorkDrive | ✅ → zoho-workdrive | ✅ | ✅ | ✅ | 🟡 | ✅ (in-flight WIP) |
| Airtable | 🟡 stub page, no connect | ❌ | ⚠️ | — | — | — |
| Obsidian, Twilio, Okta, Workday, Webex, LinkedIn, Deepgram, SendGrid, Email, Signal, Line, Matrix, Messenger, Calendly, Figma, Pocket | no hub card / no page (API-only) | `load`-gated | — | — | — | ⚠️ registry-on-demand paths (see §4) |

## 3. Gaps FILLED this round (Round 80)

### Backend (TDD — red tests first, `tests/test_round80_integration_journey_auth.py`, 33 tests)
| # | Gap | Fix |
|---|---|---|
| G1 | `POST /api/v1/external-integrations/execute` + list/details had **zero auth** — anonymous execution of arbitrary Node-bridge actions with caller-supplied credentials | `get_current_user` on all 3 endpoints (`integrations/bridge/external_integration_routes.py`) |
| G2 | `GET /api/integrations/stats` exposed circuit-breaker internals anonymously | auth-gated (`main_api_app.py`) |
| G2b | `/api/billing/webhook` legacy alias imported a **nonexistent module** inside a swallowed `try/except` that logged a false "✓ Loaded" | dead block removed + comment; pinned fail-closed 404 test |
| G3 | `twitter_routes` — `POST /tweets` (write) + 2 reads had no auth | gated (status/health stay public) |
| G4 | `bamboohr_routes` — employee **CRUD + time-off reads** had no auth | gated |
| G5 | `discord_routes` — `POST /channels/{id}/messages` (write) + user/guilds/channels/search/items had no auth | gated (`get_current_user` aliased to avoid the local service helper of the same name) |
| G6 | `slack_routes` — `/channels`, `/channels/{id}`, `/users/{id}`, `POST /reactions/add` (write) had no auth (send/search were wave-93 gated) | gated |

### Data ingestion → AI-employee memory relevance (`tests/test_round80_ingestion_role_relevance.py`, 11 tests)
**Finding**: the "AI employee" is an `AgentRegistry` row (`category` = role, `specialty` = responsibility), but ingested org data was stored workspace-scoped with **no role/agent attribution** — every employee recalled the same documents, and `data_ingestion_routes` carried **8 dead `agent_id` params** that were never used.

| # | Fix |
|---|---|
| R1 | `IngestedDocument.role` (nullable, indexed) + guarded migration `20260821_add_ingested_docs_role.py` |
| R2 | `AutoDocumentIngestionService.process_file_bytes(..., role=)` stamps `metadata.role` into the `documents` (LanceDB) recall surface |
| R3 | `HybridDataIngestionService.sync_integration_data(..., role=)` stamps `metadata.role` into `integration_*` tables; threaded through the OneDrive/GDrive fetchers to `process_file_bytes` |
| R4 | `WorldModelService._recall_general_knowledge()` — recall **prefers docs tagged with the agent's role** (lowercased `category`) and tops up with untagged general knowledge (role scoping is additive, never exclusive) |
| R5 | `POST /api/data-ingestion/sync/{integration}?agent_id=<id>` now resolves the AI employee's role and tags the sync — the first of the 8 dead `agent_id` params wired |

### Frontend (UI/UX — 10 jest tests in `tests/pages/integrations-journey-gap-fill.test.tsx` + `tests/components/integrations-IntegrationStatusCard.test.tsx`)
| # | Gap | Fix |
|---|---|---|
| F1 | Hub cards for **dropbox, telegram, gitlab → 404** (no pages; `gitlab_enhanced` was a dead stub) | Real pages (`/integrations/{dropbox,telegram,gitlab}`) wired to real status + OAuth endpoints via a shared `IntegrationStatusCard` |
| F2 | **xero.tsx was a dead stub** with an inert Connect button | Real page (`/integrations/xero`) |
| F3 | **Monday + WhatsApp components were fully built but orphaned** (no page, no hub card) | `pages/integrations/{monday,whatsapp}.tsx` wrappers + hub cards |
| F4 | Orphaned **DropboxManager / ThirdPartyIntegrations / AtomAgentSettings / UnifiedServicesManager** | documented; Dropbox reachable via the new page (manager itself requires a NextAuth session the app doesn't provide — see §4) |

### Round 80b — the endpoints behind the new pages were 404/500 in the real app (fixed)
| # | Gap | Fix |
|---|---|---|
| B1 | `integration_health_endpoints.get_integration_health` used `logger.debug` without defining `logger` → **every `/api/{app}/status` through the legacy stub 500'd** (`NameError`), breaking the hub health surface | `logger = logging.getLogger(__name__)` added (RED: 8/8 probes failed → GREEN) |
| B2 | dropbox/gitlab/monday/telegram/whatsapp/xero routers were registry-**lazy**, so at boot the legacy health stub shadowed their status paths with fake data and the real endpoints 404'd (my F1/F2 pages called them) | "FORCED JOURNEY ROUTER REGISTRATION" boot block mounts the 6 at their declared root prefixes (`main_api_app.py`), before the legacy stub — real routes win |
| B3 | `dropbox_service` did `import dropbox` (SDK optional — commented out in requirements) → registry reported dropbox "not available" → **all `/api/dropbox/*` 404'd** even for SDK-free OAuth endpoints | try/except guard + `_current_dropbox()` lazy re-resolution (`sys.modules`) — boot works without the SDK, wave-93 test fakes stay inert-compatible, SDK paths fail with a clear message |
| B4 | Next.js had no rewrites for the bare `/api/{dropbox,gitlab,monday,telegram,whatsapp,xero}` prefixes → the new pages' fetches 404'd at the Next layer | `next.config.js` rewrites (same convention as the other bare prefixes; normalized to `NEXT_PUBLIC_API_URL` at build) |

`tests/test_round80b_journey_endpoints.py` (8 tests): xero real-payload 200, dropbox oauth/status+url 200, gitlab status+auth/url 200, monday auth/url 200, telegram status present (401 without token), whatsapp health fail-closed-not-404, legacy stub never 500s. Regression battery incl. boot mounts + wave-93/98 dropbox suites: 87 passed in one process.

## 4. Systemic findings (recommended follow-ups — NOT fully resolvable in one pass)

1. **Dead-port proxy plumbing (HIGH)** — ~120 `frontend-nextjs/pages/api/integrations/*.ts` handlers proxy to `PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058'` (health: `:5059`), but the canonical backend runs on **:8000** (`next.config.js` rewrites). These handlers shadow the rewrites, target a dead port, and **do not forward the user's `Authorization` header** — so many data calls in existing pages (slack channels/messages, xero invoices, salesforce leads…) fail end-to-end today. Recommendation: make the shared handler pattern forward `Authorization` + default `PYTHON_API_SERVICE_BASE_URL` to `:8000` (or delete the handlers and rely on rewrites), then re-run the journey matrix.
2. **Discord double-prefix mount** — `main_api_app.py` mounts `discord_router` with prefix `/api/v1/integrations/discord` while the router itself declares `/api/discord` → real route is `/api/v1/integrations/discord/api/discord/...`. The frontend page calls neither. Fix the mount or the prefix.
3. **Registry-on-demand integrations still unauthenticated when loaded** (`load` is auth-gated, but once loaded the routers are bare): `linear`, `tableau`, `freshdesk`, `intercom`, `twilio`, `linkedin`, `obsidian`, `okta`, `workday`, `webex`, `deepgram`, `email`, `sendgrid`. Apply the wave-93..105 gate pattern (data/write → `get_current_user`; auth/url, status, health, webhook stay public). *(Round 80b progress: dropbox/gitlab/monday/telegram/whatsapp/xero are now boot-mounted with the R80 gates; the auto-load middleware additionally mounts any registry router on first hit at `/api/v1/integrations/{name}/...`, which double-prefixes routers that declare their own root prefix — see item 2.)*
4. **Orphaned API surface** — `api/integration_dashboard_routes.py` (`/api/integrations/dashboard`, 14 endpoints, mostly unauthenticated) is never mounted; mount or archive. `api/meeting_routes.py`, `api/recording_review_routes.py`, `api/risk_routes.py`, `api/learning_plan_routes.py`, `api/integrations/memory_backfill_routes.py` also never mounted (see `docs/architecture/` for intent).
5. **Governance decorator drift** — `@require_governance(action_complexity=…)` passes kwargs `AgentGovernanceService.can_perform_action` no longer accepts (`api_governance.py:438`), so ingestion routes wrapped in it 500 in bare mounts. Either reconcile the decorator with the service signature or drop the unused kwargs.
6. **Zoho OAuth callback map** — verified complete (fan-out + `api_domain` persistence in `_handle_callback_logic`); covered by in-flight WIP tests (`test_zoho_user_journey.py`, `test_zoho_oauth_provider_keys.py`).

## 5. Role model (what "every role" means here)

- `get_current_user` (JWT, ACTIVE-only, jti revocation) gates every integration data/write endpoint — anonymous is rejected; any authenticated role (MEMBER..SUPER_ADMIN) can connect/use integrations.
- Integration endpoints do not use `require_admin` by design: connecting a service is a normal member action. Admin-only surfaces (gatekeeper, stage-router automation, workspace context) keep their own `require_super_admin`/`_require_admin` gates.
- Governance (agent maturity) applies at agent-execution time, not at the integration HTTP surface.
- **Round 80 addition**: ingested data is now tagged with the AI employee's role (`AgentRegistry.category`) so an employee's *memory* is relevant to their work/role/responsibilities; recall is role-preferred + untagged top-up (additive, graceful).

## 6. How to re-run the audit

```bash
# Backend journeys (auth + role-relevance)
PYTHONPATH=$PWD pytest tests/test_round80_integration_journey_auth.py \
                  tests/test_round80_ingestion_role_relevance.py -v
# Frontend journeys (new pages + status card)
cd frontend-nextjs && npx jest tests/pages/integrations-journey-gap-fill.test.tsx \
                  tests/components/integrations-IntegrationStatusCard.test.tsx
```
Manual smoke: `/integrations` → click each card → page renders status + Connect; connect flows redirect to the real OAuth URL.