# Brennan.ca Local Pilot — AI Teammates for a Small Business

**Status:** Proposed (2026-08-17) · **Duration:** 4 weeks + demo day · **Deployment:** single-org, one self-hosted box (Personal Edition stack), remote employees over HTTPS/Telegram · **Business:** brennan.ca (metal fabrication distributor, owner-operated, remote team)

**Goal:** run a real pilot with brennan.ca employees using Atom as advertised in the main README — *autonomous AI teammates per employee role* — on the business's actual app stack, produce a demo that shows value to other users, and validate the journey that a future multitenant SaaS would repeat.

**Success criteria (decide by end of week 4):**

| # | Criterion | Target |
|---|---|---|
| 1 | Employee adoption | ≥ 3 of 4 roles actively delegating tasks weekly |
| 2 | Real workflows completed end-to-end | ≥ 2 quotes and ≥ 2 invoices processed with HITL approval |
| 3 | Cycle time | Email inquiry → sent quote in < 15 min (vs. hours today) |
| 4 | Trust | Zero outbound actions without approval; audit trail clean |
| 5 | Agent progression | ≥ 2 teammates graduate Student → Intern tier |
| 6 | Qualitative | Employees rate the teammates "would keep using" in feedback session |

---

## 1. Existing assets in this repo (use them)

The repo already contains a brennan.ca-specific demo kit — this pilot upgrades it from *scripted demo* to *live system on real data*:

| Asset | Path | Use in pilot |
|---|---|---|
| Role storyboards (4 videos) | `demo/brennan/storyboards/01..04-*.md` | Demo-day scripts; teammate job descriptions |
| Business doc templates | `demo/brennan/templates/{Quote,Invoice,PurchaseOrder,SpecSheet}.docx`, `PriceList.xlsx` | Template-fill workflows via OneDrive/WorkDrive |
| Seed data loader | `demo/brennan/seed_data.py` | Week-1 rehearsal data (products/customers into the knowledge graph) |
| Outlook automation (brennan-coded) | `backend/outlook_automation_service.py` | Quote/invoice email flows — note it contains brennan.ca hard-coding |
| Org-sharing runbook | `docs/architecture/ORG_SHARING_SETUP.md` + `ORG_INGESTION_SHARING_PLAN.md` | Phase 5 (SAS precursor dogfooding) |
| Personal Edition runbook | `docs/operations/personal-edition.md` | Base deployment |
| Agent training/graduation docs | `docs/agents/training.md`, `docs/agents/graduation.md` | Teammate maturity progression |
| Messaging setup | `docs/integrations/IM_ADAPTER_SETUP.md`, `docs/guides/MESSAGING_PLATFORMS.md` | Telegram channel setup |

## 2. Pilot architecture

**Recommended: one central instance, employees as users** (not one instance per employee). Employees are **remote** — there is no LAN, so all access rides HTTPS through a Cloudflare Tunnel and the web UI sits behind Cloudflare Access (zero-trust email-OTP login in front of Atom's own login).

```
      remote employees (home networks)
        │                               │ Telegram DMs / group chat
        │ (Phase 3 only: web UI over    ▼
        │  Cloudflare Tunnel + Access)  ┌──────────────────────────┐
        │                               │  Telegram long-polling   │
        │                               │  (outbound-only, no      │
        │                               │  public URL needed)      │
        │                               └────────────┬─────────────┘
        ▼                                            ▼
   ┌─────────────────────────────────────────────────────────┐
   │  Atom instance (one always-on box)                       │
   │  ATOM_EDITION=enterprise · SQLite + LanceDB + fastembed  │
   │  LLM: BYOK (OpenCode Go / OpenAI)                        │
   └─────────────────────────────────────────────────────────┘
```

- **Why central:** all employees share one org context naturally; one set of OAuth connections; episodic memory and knowledge graph are shared; ops burden is one box, not N. Personal Edition compose (SQLite + LanceDB, no Postgres/Redis) is sufficient for a team of ~5.
- **Where the box lives (owner's call):** (a) the owner's always-on machine at home, or (b) a small cloud VM — the repo ships a DigitalOcean 1-click template and `fly.toml`. Either way it stays "local for now" in the sense that matters: self-hosted, single-tenant, your keys. A VM avoids home-uplink/NAT issues and is easier to back up; pick whichever stays up reliably.
- **Telegram needs NO public URL (updated 2026-08-17):** the bot runs in long-polling mode (`TELEGRAM_POLLING_ENABLED=true`, new `TelegramPollingWorker`) — outbound-only, survives reboots/IP changes with nothing to re-register. Webhook mode via tunnel remains available for server deployments (`docs/integrations/IM_ADAPTER_SETUP.md`).
- **Public hostnames are a Phase 3 need, not Phase 1:** only when employees log into the web UI remotely do we add a Cloudflare Tunnel (`app.<domain>` → :3001, `api.<domain>` → :8001, both behind Cloudflare Access). The frontend's `NEXT_PUBLIC_API_URL` is a *browser-side* setting, so remote browsers must reach the backend directly — set it to `https://api.<domain>` at that point. **Domain decision:** `atomagentos.com` is reserved for the multitenant SaaS sister app (not this pilot). `brennan.ca` hosts the Shopify storefront plus M365/Proofpoint email and Zoho records — migrating its nameservers is a deliberate post-pilot project (record manifest captured 2026-08-17: Shopify A 23.227.38.65 + www CNAME, Proofpoint MX, SPF incl. outlook.com + zoho-inventory.ca, MS + Zoho verification TXTs). For Phase 3, a ~$10 dedicated domain in the existing Cloudflare account is the zero-risk option.
- **Telegram-first for remote staff:** the bot DM/group is the daily driver (no login friction); the web UI is for Canvas, dashboards, and approvals. The repo also has a React Native companion app (`mobile/`) as an optional later addition.
- **Multi-user:** set `ATOM_EDITION=enterprise` — Personal edition defaults to single-user, Telegram-only IM (`backend/core/package_feature_service.py:197` detects edition from env). Each employee gets a user account via admin panel (`docs/guides/ADMINISTRATORS/USER_MANAGEMENT.md`).
- **Alternative deferred to Phase 5:** the new org-sharing hub/member model (each employee runs their own local instance and pulls signed ingestion bundles from a hub). A remote workforce actually maps *better* to this than a shared office did — every member laptop is already an island. It's still deferred: for a time-boxed pilot, one box + two hostnames beats N instances + a key ceremony. See §8.

## 3. App-by-app integration plan (with web research)

| App | Atom connector | Auth setup | Limits / gotchas | Phase |
|---|---|---|---|---|
| **Telegram** (replaces WhatsApp) | `atom_telegram_integration.py` + IM adapter + ingestion fetcher + new `TelegramPollingWorker` | @BotFather → bot token; `TELEGRAM_POLLING_ENABLED=true` (no public URL). Webhook mode optional for servers | Privacy mode ON by default → bot only sees commands/mentions in groups; run `/setprivacy` → Disable in BotFather or promote bot to group admin. Bots **cannot DM a user first** — every employee must `/start` the bot once. Bots never see other bots' messages. **Live as of 2026-08-17: @brennan_atom_bot on polling mode.** | 1 ✅ |
| **Outlook** | `microsoft365_service.py` (Microsoft Graph) | Azure app registration; delegated `Mail.Read`, `Mail.Send`, `Files.Read` | Graph allows ~10k req/10 min per user per app; send limit ~150 mails/15 min per tenant — far above pilot needs. Consumer outlook.com accounts only support delegated access; a Microsoft 365 work tenant is cleaner. | 1 |
| **OneDrive** | `core/integrations/adapters/onedrive.py` + `auto_document_ingestion.py` | Same Azure app; `Files.Read.All` | Store the 5 brennan templates + live documents folder; ingestion handles docx/xlsx/pdf via docling. | 1 |
| **Word / Excel** (files) | docling parsing, `modify_word_document`, workbook runtime, Canvas co-editing | n/a (files come via OneDrive/WorkDrive/local upload) | This is a flagship demo capability — template fill + formula-evaluating Excel. No API dependency. | 2 |
| **Zoho Books** | `zoho_books_service.py` | Zoho API Console OAuth 2.0 client (Books scope); note your data center (US `.com` vs regional) when picking token endpoints | ~100 req/min per org; daily caps by plan: Free 1,000 / Standard 2,000 / Professional 5,000 / Premium+ 10,000. Max 20 refresh tokens per user — **don't re-consent repeatedly** or the oldest token silently dies. | 1 |
| **Zoho Inventory** | `zoho_inventory_service.py` | Same Zoho OAuth client, Inventory scopes | Brennan seed notes Zoho product/item write-back is read-only in current adapters — fine for pilot (we read items/stock, write documents via Atom). | 1 |
| **Zoho CRM** | `zoho_crm_service.py` + universal adapter (already wired into `hybrid_data_ingestion.py`) | Same client, CRM scopes | CRM uses a credit-based rate-limit system (not flat counts); keep ingestion intervals modest (hourly is plenty). | 1 |
| **Zoho Drive (WorkDrive)** | `zoho_workdrive_service.py` + `auto_document_ingestion.py` | Same client, WorkDrive scopes | Use as the shared template/document home alongside OneDrive (pick one as primary to avoid duplicate ingestion). | 1 |
| **Shopify** (website) | `shopify_service.py` (products/orders/customers/inventory reads; draft orders, fulfillments, refund calc writes; webhooks; `full_sync`) + hybrid ingestion fetcher | Custom app in Shopify admin (Admin API token) or OAuth flow (`SHOPIFY_API_KEY`/`SECRET`/`SHOP_DOMAIN`); webhooks need the same public URL as Telegram | **Website management in pilot = read + order ops**: sync site products/prices/stock into the graph, catch price/stock mismatches vs Zoho + price list, monitor orders, create fulfillments on ship. No product create/update op exists — real listing edits would need a small adapter addition (post-pilot). | 1 |
| **WhatsApp** | connector exists (`whatsapp_business_integration.py`) but **not used in pilot** | — | Registration pain is real: Meta business verification, document-consistency rejections, and registrations blocked even after verification (see Sources). Cloud API also requires pre-approved templates. Revisit post-pilot if customers demand it. | dropped |

**Zoho OAuth one-time setup (single console session):** register **one** self-client in the Zoho API Console with Books + Inventory + CRM + WorkDrive scopes → generate grant code → exchange for refresh token → store via Settings → Integrations (tokens encrypted at rest, Fernet/`BYOK_ENCRYPTION_KEY`). Total: ~30 min.

**Ingestion wiring:** enable auto-sync via `/api/data-ingestion/*` (`docs` in `backend/api/data_ingestion_routes.py`) for: `telegram`, `onedrive`, `zoho_crm` (universal adapter path), plus document auto-ingestion for OneDrive/WorkDrive. Sensitivity ladder: mark Books/Inventory data `internal`, customer PII `confidential` (exports exclude confidential+ by default).

## 4. The four AI teammates

One specialty agent per employee role, matching the storyboards and the README's "team of specialty agents" promise. Train via the 4-tier maturity model (`docs/agents/training.md`), graduate via episodic-memory readiness scores (`docs/agents/graduation.md`).

| Teammate | Serves | Signature workflow (storyboard) | Start tier | HITL gate |
|---|---|---|---|---|
| **Sales Coordinator** | sales/owner | Email inquiry → recall customer → fill `Quote.docx` → Outlook send → 3-day follow-up nudge (`01-sales-coordinator.md`) | Student | Send email |
| **Bookkeeper** | finance | Vendor invoice email → extract totals → match Zoho Books → flag discrepancies → draft `Invoice.docx` (`02-bookkeeper.md`) | Student | Any Books write |
| **Applications Engineer** | technical sales | Spec request → pull product specs from ingested SpecSheets/PriceList → generate technical response + SpecSheet.docx (`03-applications-engineer.md`) | Student | Send email |
| **Shipping/Inventory Clerk** | operations | Order → check Zoho Inventory stock → draft PO/Shipping docs → archive to OneDrive/WorkDrive (`04-shipping-inventory-clerk.md`) | Student | Send to vendor |

Weekly rhythm: review each teammate's blocked-trigger proposals and supervision sessions (`backend/core/student_training_service.py`), approve promotions as readiness scores clear the bar, adjust capability bindings so no teammate exceeds its tier floor.

## 5. Rollout schedule

### Phase 0 — Setup (Days 1–2, owner + whoever runs IT) — **✅ done 2026-08-17 (native dev path on owner's Mac; see Ops notes)**
1. ~~Provision box + docker compose~~ Owner's Mac, native path (`make setup` + uvicorn + `next dev --webpack`) — Docker Desktop was dead on this machine (backend IPC failures since Aug 15).
2. ✅ LLM key (`OPENCODE_API_KEY` via OpenCode Go — env keys count as BYOK after the AGPL fix), secrets generated.
3. ~~Cloudflare Tunnel~~ Not needed: Telegram runs in polling mode (`TELEGRAM_POLLING_ENABLED=true`); tunnel + `app/api` hostnames deferred to Phase 3 with the domain decision (see §2).
4. Employee accounts + bot `/start` links — pending Phase 3 (bot already live: @brennan_atom_bot).
5. ✅ `demo/brennan/seed_data.py` loaded (8 entities, 6 relationships in the live graph; meta agent `atom_main` registered at SUPERVISED with agent-wide default tier).

### Phase 1 — Connect the stack (Days 3–5)
Order matters — cheapest wins first:
1. **Telegram** (30 min): BotFather bot, disable privacy mode, employees `/start` it, UserAccount bindings map Telegram identity → user.
2. **Outlook + OneDrive** (1 hr): one Azure app registration, delegated scopes, connect in Settings → Integrations; upload brennan templates to OneDrive.
3. **Zoho** (1 hr): single API Console client for Books/Inventory/CRM/WorkDrive (see §3).
4. Enable ingestion syncs (hourly), run initial backfill, verify hybrid search: `documents.search` should surface a real customer, a real product, and a real email thread.

### Phase 2 — Build & train teammates (Week 2)
1. Create the 4 agents with role personas + capability bindings from §4.
2. **Rehearse each storyboard live** against seeded data; every outbound action goes through HITL approval — this trains the supervision corpus.
3. Swap seeded data for real ingested data (real Zoho items, real email history); re-run the 4 workflows; capture screenshots/video for the demo.
4. Tune: add blocked-trigger rules where the teammates overreach; add memory rules for customer quirks.

### Phase 3 — Employee onboarding (Weeks 3–4)
1. 45-min hands-on **video call** per employee using `docs/guides/USER_TRAINING_GUIDE.md` + their role storyboard; everyone joins from their own machine, `/start`s the bot, and logs into the web UI once (Access OTP + Atom login).
2. Each employee delegates 2–3 real tasks/day — Telegram is the default channel for remote staff; web UI for Canvas/approvals; approvals happen in-band.
3. Weekly 30-min review: agent proposals, graduations, feedback (keep a simple log — it feeds demo day and the SaaS decision).

### Phase 4 — Demo day (end of Week 4)
Run storyboard 1 live on a **real inquiry** (have one staged), then show: Canvas step-by-step execution → HITL approval → sent email in Outlook → memory recall ("Atom remembered the quote, the budget, and the 8-week deadline"). Close with the metrics table from §6. Record it using the storyboard timings (~2:30 per scenario).

### Phase 5 — Post-pilot (only on success)
Dogfood org-sharing hub/member (§8) with 1–2 employees running their own instances; then make the SaaS go/no-go decision.

## 6. Value metrics to capture

| Metric | Source |
|---|---|
| Quote turnaround time (inquiry → sent) | Storyboard run timestamps |
| Invoice discrepancy catches | Bookkeeper workflow logs |
| Tasks delegated per employee per week | Messaging/audit trail |
| HITL approval override rate (proxy for trust) | Approval queue stats |
| Hours saved/week per role (self-reported) | Weekly review log |
| Agent tier progression | Graduation readiness scores |

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Telegram bot silent in groups (privacy mode default) | `/setprivacy` → Disable **before** adding to groups, or make it admin; verify in BotFather |
| Employees never `/start` the bot → no proactive DMs | Onboarding checklist step; bot broadcasts not possible until first contact |
| Zoho refresh token invalidated (>20 consents) | Connect once centrally; document the token in the ops vault; don't re-consent |
| Zoho daily API cap (1k–10k by plan) | Hourly sync intervals; delta syncs only; 429 backoff already handled by adapters |
| Confidential financial data in agent memory | Sensitivity tags (`confidential` excluded from org exports), sandbox default-on, egress allowlist |
| WhatsApp holdouts among staff | Web UI is the fallback channel; WhatsApp connector exists for a later phase |
| Instance exposed to the internet (remote staff) | Cloudflare Access in front of both hostnames, HTTPS-only, strong per-employee Atom credentials, audit trail reviewed weekly; tunnel exposes nothing else on the box |
| Single box = single point of failure (all remote work stops if it dies) | Prefer a cloud VM with snapshots; nightly backup of `./data` (SQLite + LanceDB) + `.env`; restore is a re-`up` on any new box |
| brennan.ca hard-coding in `outlook_automation_service.py` | Fine for this pilot (it *is* brennan.ca); clean up before any external/SaaS use |

## 8. Path to multitenant SaaS (the "same journey")

**Ops notes discovered during initial bring-up (2026-08-17, macOS native path):**

- The backend loads `backend/.env` first, then repo-root `.env` (previously only the root file was read, contradicting every quick-start doc). **Keep `DATABASE_URL` identical in both** — a mismatch silently swaps databases mid-restart (this bit us: the server flipped to a stale `atom_dev.db`; both files now pin `sqlite:///./data/atom.db`).
- ~~The bootstrap `default` tenant is created with `plan_type='free'`, which routes LLM requests through free-tier model allow-lists and filters out OpenCode Go models even with a valid env key~~ **Fixed in code (2026-08-17):** env-configured API keys are now treated as BYOK and are never plan-restricted in the AGPL self-hosted edition (`BYOKHandler.env_key_providers`, `backend/core/llm/byok_handler.py`). The DB workaround (`UPDATE tenants SET plan_type='enterprise' WHERE id='default';`) is only needed on pre-fix installs.
- Frontend on Rosetta/x64 Node needs `npx next dev --webpack -p 3001` (Turbopack has no native bindings).
- Telegram runs in **polling mode** (`TELEGRAM_POLLING_ENABLED=true`) — no tunnel/domain. Webhook mode, if ever used, needs: `ATOM_TELEGRAM_WEBHOOK_SECRET` (fail-closed), hostname in `ALLOWED_HOSTS`, and the full stacked route `/api/v1/integrations/telegram/api/telegram/webhook`. `*.trycloudflare.com` hosts are exempt from tenant-subdomain routing and `/webhook` paths from CSRF (committed upstream).
- The meta agent must be ≥ SUPERVISED to act (STUDENT capabilities are blocked at invocation). `atom_main` is registered in `agent_registry` at `supervised` with `capability_maturities: {"*": "supervised"}` (agent-wide default tier; per-capability entries override). Role teammates should still start at STUDENT — that's the training story.
- The `default` workspace has `learning_phase_completed=1` (graduated), so outbound Telegram sends don't pause for HITL. Flip to 0 to restore approval gating — note the HITL queue consumer/UI is not wired yet; approvals land in `hitl_actions` unprocessed.
- Fixes pushed to main from this bring-up: `bb385696b` (env-key BYOK + backend/.env loading), `148538e5b` (tunnel host + webhook CSRF exemptions), `9edc9f4d7` (Telegram inbound pipeline: governance cache call, orchestrator init, workspace id), `aabcf45e5` (meta agent capability gating + `*` default tier), `5ff589a3f` (Telegram polling worker).
- **Memory unification P0 (2026-08-19, `7f55636ca`):** chat/IM surfaces now retrieve memory at turn time (`MEMORY_CONTEXT_ASSEMBLY`, default on; startup warm-up preloads embedding models — first-turn legs used to time out on cold model loads). Live-verified: "ACME Fab inquiry" and "AccurPress $84,500, SKU BP-50T" answered from the knowledge graph through normal chat. Note: the brennan seed now loads into workspace `default` (the active one) in addition to `brennan-demo`. Plan of record: `docs/architecture/AGENT_MEMORY_UNIFICATION_PLAN.md` (P1 next: meta-agent tool equality, episode table unification, cross-engine `memory.search`).
- **Hybrid search + VFS verified (2026-08-19, `41c1e8b38` + `74301215d`):** document upload, `documents.search` (bm25_vector_rrf mode), and VFS ls/cat/grep all live-verified. Fixes: embedding provider wiring (fastembed honored, vector column 384), explicit-schema table creation, VFS root-grep, ILIKE-fallback tokenization. Applied manually to the live DB: the `20260808_add_documents_fts` migration SQL (FTS5 tables + backfill + sync triggers). Conversations leg + `knowledge/conversations` VFS subtree shipped (P1.3 first slice); **known blocker:** the comm store's sentence-transformers/torch install is broken in this venv (`libtorch_cpu.dylib` missing) so comm embeddings are zero vectors and the leg returns empty until torch is reinstalled — legs degrade gracefully. Telegram polling now persists inbound messages to the comms store (fire-and-forget), matching webhook mode.

1. **This pilot** = one org, one central instance, real data, real users → proves teammate value.
2. **Org-sharing dogfood** (Phase 5) = same org split across member instances: hub egress policy (`ATOM_ORG_HUB_MAX_SENSITIVITY`, `ATOM_ORG_HUB_SOURCE_ALLOWLIST`), per-member `atom_sk_*` gateway keys, Ed25519 key ceremony, signed delta bundles with sensitivity ceilings (`docs/architecture/ORG_SHARING_SETUP.md`). This exercises account/key lifecycle and data-partitioning semantics at org scale.
3. **SaaS** = repeat the journey per tenant: move to the Postgres production path (`docs/operations/postgresql-production.md`), tenant isolation per `docs/architecture/TENANT_ID_STRATEGY.md` enterprise mode, hosted OAuth per tenant org, billing on gateway keys. Note: `ATOM_ORG_*` flags are not yet in `.env.example` — add them when Phase 5 starts.

## Sources (web research, Aug 2026)

- Zoho Books API/OAuth & limits — [Zoho Books OAuth](https://www.zoho.com/books/oauth/), [APIDEck rate limits](https://www.apideck.com/blog/how-to-get-your-zoho-books-api-key), [Endgrate](https://endgrate.com/blog/using-the-zoho-books-api-to-get-customers-in-python), [Satva accounting-API guide](https://satvasolutions.com/blog/saas-leaders-guide-api-rate-limits-in-accounting-platforms)
- Zoho CRM credit-based limits — [Zoho CRM API limits](https://www.zoho.com/crm/developer/docs/api/v8/api-limits.html)
- Telegram bot constraints — [Telegram Bots FAQ](https://core.telegram.org/bots/faq), [group privacy mode explainer](https://www.teleme.io/articles/group_privacy_mode_of_telegram_bots?hl=en), [group-message troubleshooting](https://community.latenode.com/t/telegram-bot-not-detecting-messages-from-group-conversations-how-to-fix/21633)
- WhatsApp Business API registration pain — [Reddit: verified but can't register](https://www.reddit.com/r/WhatsappBusinessAPI/comments/1scbfgr/business_verified_but_i_still_cant_register_a/), [Wassenger: pre-verification limits](https://wassenger.com/blog/en/whatsapp-business-api-without-verification), [Latenode: blocked registration](https://community.latenode.com/t/whatsapp-business-api-setup-blocked-mysterious-error-message-about-prohibited-advertising/14886), [Gurusup setup guide](https://gurusup.com/blog/setup-whatsapp-api)
- Microsoft Graph — [permissions reference](https://learn.microsoft.com/en-us/graph/permissions-reference), [mail API overview](https://learn.microsoft.com/en-us/graph/api/resources/mail-api-overview?view=graph-rest-1.0), [throttling guidance](https://learn.microsoft.com/en-us/graph/throttling), [service-specific limits](https://learn.microsoft.com/en-us/graph/throttling-limits)
