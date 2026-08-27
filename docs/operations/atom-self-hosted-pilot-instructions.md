# Atom Self Hosted Pilot — Instructions

**For:** brennan.ca pilot operators (Rish + employees) · **Last updated:** 2026-08-20
**Everything below runs on the pilot Mac.** Backend: `http://localhost:8001` · Web UI: **`http://localhost:3001`** · Bot: **@brennan_atom_bot** on Telegram.

---

## 1. Daily startup

Open Terminal on the pilot Mac:

```bash
# Terminal 1 — backend
cd ~/projects/atom && make backend

# Terminal 2 — frontend (NOTE: --webpack is required on this Mac)
cd ~/projects/atom/frontend-nextjs
NODE_OPTIONS='--max-old-space-size=4096' npx next dev --webpack -p 3001
```

**Verify both are up:**
- Backend: open `http://localhost:8001/alive` → `{"status": "alive", ...}`
- UI: open **`http://localhost:3001`** → login page

> ⚠️ The UI is on **3001**, never 3000. If a browser ever sends you to
> `localhost:3000/...` (e.g. an old OAuth success redirect), just retype 3001.

**Sign in:** `admin@example.com` · password: `backend/logs/bootstrap_admin_password.txt` (first line). Change it under Settings → Account.

**What starts automatically with the backend:** Telegram polling bot (no public URL needed), memory assembler (with warm-up), nightly memory consolidation, Outlook email poller (60s interval).

---

## 1b. Data ingestion → training flow (how Brennan's data reaches the hire)

Connecting an app and enabling sync feeds the AI employee's memory; training
tasks then draw on that live data. The flow for every integration:

1. **Connect** (OAuth consent — see §2 below for Zoho/Outlook specifics).
   A Zoho grant covers CRM, Books, Inventory, Projects and WorkDrive in one
   consent; Microsoft covers Outlook mail (poller) and OneDrive files.
2. **Sync scoped to the hire**: `POST /api/data-ingestion/sync/zoho?agent_id=<hire>&force=true`
   (auto-sync runs hourly; Outlook's poller runs every minute). Records land
   in agent memory **role-tagged** (the hire's category — Sales for the SDR)
   and **freshness-stamped** (`source_modified_at` / `last_verified_at` /
   `freshness_status`), so role-aware recall surfaces the right records and
   stale ones are detectable.
3. **What lands where**: CRM leads/deals → memory + the `sales_leads` /
   `sales_deals` ledger (dashboard KPIs read these); Books invoices,
   inventory items/orders, project tasks → memory + business facts;
   WorkDrive team folders (H Drive, Accounting, …) and OneDrive files →
   metadata records + parsed document content for searchable types
   (.pdf/.docx/.xlsx/.csv/.txt) through the freshness-tracked ingestion path.
4. **Train against it**: tasks like "review the newest Zoho leads and draft
   outreach" or "check the Gary Payable spreadsheet" exercise exactly what
   was ingested. Blocked attempts on gated capabilities become training
   proposals (/approvals).

**Zoho Flow (the automation app)** pushes events straight in: point a Flow
"Webhook" task at `POST /api/webhooks/zoho-flow?agent_id=<hire>` with
`Authorization: Bearer $ZOHOFLOW_WEBHOOK_SECRET`. Records ingest
(role/freshness-stamped) and fire the domain trigger — a STUDENT hire gets
blocked into a training proposal automatically.

Supported today through the same pipeline: **zoho, onedrive, gmail,
google_calendar, google_drive, hubspot, salesforce, slack, notion, jira,
zendesk, shopify, telegram**. A Brennan-like stack is Zoho + Microsoft
(Outlook/OneDrive); swap in HubSpot/Salesforce/G Drive and the flow is
identical — connect, enable sync, role-scope, train.

---

## 2. Connecting apps (one-time)

### ✅ Outlook / Microsoft 365 — ALREADY CONNECTED

Done 2026-08-20. Azure app **"Atom Self Hosted Pilot"** (single-tenant), tenant
`8899c7a5-b671-4f16-bb48-15d5e78158af`, token stored with auto-refresh.
**539 real emails** already in memory; the poller syncs new mail every minute.

If it ever needs reconnecting (token revoked, secret rotated):
1. Ask ZCode/agent: "mint a fresh Microsoft OAuth URL"
2. Open the URL **within 10 minutes** (it is time-signed — this bit us once)
3. Sign in with the brennan.ca account → Accept → you land on a callback page
4. Verify: `http://localhost:8001/api/v1/auth/oauth/tokens` shows provider `microsoft`, status `active`

### ⏳ Zoho (Books + Inventory + CRM + WorkDrive) — automatic OAuth flow

No grant codes, no console copy-paste. One-time app registration, then the
same click-through flow as Outlook:

1. **api-console.zoho.com** (brennan.ca Zoho login) → **Add Client → Server-based Application**
   - Client Name: `Atom`
   - Homepage URL: `http://localhost:3001`
   - Authorized Redirect URI: `http://localhost:8001/api/v1/auth/oauth/zoho/callback`
2. Copy **Client ID + Client Secret** (Client Secret tab) → set in
   `~/projects/atom/.env` (`ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`; also
   `ZOHO_ACCOUNTS_BASE=https://accounts.zoho.xx` matching the DC in the URL bar)
3. Connect: open `http://localhost:8001/api/v1/auth/oauth/zoho/initiate` (via
   a browser logged into the pilot UI) → sign in to Zoho → Accept → the
   callback stores refresh tokens automatically for all four services.
4. Verify: `http://localhost:8001/api/v1/auth/oauth/tokens` shows provider `zoho`, status `active`.

**Region (DC) rules — learned 2026-08-26 the hard way on `accounts.zohocloud.ca`:**
- Clients are **DC-scoped**. Create the client on the console of the account's
  HOME DC (`api-console.zohocloud.ca` for Canada), not `api-console.zoho.com` —
  otherwise the authorize flow fails with `Invalid Redirect Uri` after the
  cross-DC sign-in hop, even though the client id looks valid.
- `ZOHO_ACCOUNTS_BASE` must match that DC; the token exchange hits the same
  base, and the token response's `api_domain` is stored per-connection so the
  data plane (CRM/Books services) targets the right regional API automatically
  (also overridable via `ZOHO_DEFAULT_API_DOMAIN`).
- `ZOHO_OAUTH_SCOPES` now drives the consent scope list (comma-separated;
  `offline_access` filtered out — Zoho uses `access_type=offline`). Verified
  valid names: `ZohoCRM.modules.ALL`, `ZohoCRM.org.READ`,
  `ZohoBooks.fullaccess.all`, `ZohoInventory.fullaccess.all`,
  `WorkDrive.files.ALL`, `WorkDrive.teamfolders.ALL`. NOTE: **Projects has no
  `fullaccess.all`** — use `ZohoProjects.portals.all,ZohoProjects.projects.all`.
  One unknown scope fails the whole authorize with `Invalid OAuth Scope`.
- Zoho rate-limits rapid authorize attempts ("Maximum request limit reached");
  the error clears after ~10-15 min, so don't loop scope probing.

> A Zoho **Self Client** cannot drive this flow (no redirect URI — only
> console "Generate Code" grant codes, which expire in 10 min). Use server-based.

### ⏳ Shopify — ~10 minutes

1. Shopify admin → **Settings → Apps and sales channels → Develop apps → Create an app**
2. **Configuration → Admin API scopes**: `read_products`, `read_orders`, `read_inventory`, `write_draft_orders`, `write_fulfillments`
3. **Install app** → copy the **Admin API access token** (`shpat_…`)
4. Hand the agent: token + your `brennan.ca` my-shopify domain

---

## 3. Using Atom day-to-day

### Telegram (the daily driver)
Message **@brennan_atom_bot** from your phone. Every employee must send `/start`
once (bots cannot message people first). Answers draw on memory: your real
emails, products, prices, customers, and past agent work.

### Web UI (`http://localhost:3001`)
- **Chat** — same brain as the bot. Each answer shows a **"🧠 Context used"**
  link — click it to see exactly what memory the agent recalled (the trust check).
- **Approvals** — actions paused for your decision (e.g. sending an email).
  Approve/Reject with one click; the page auto-refreshes.
- **Admin → User Management** — create employee accounts (email + initial
  password + role). Employees change passwords under Settings → Account.
- **Settings** — Account (password + 2FA), Advanced → AI Providers (keys).
- **Agents** — the four role teammates and their maturity tiers.

### Creating an employee account (when Phase 3 starts)
Admin → User Management → **+ Add employee** → email, initial password, role →
Create. Send them: the UI URL, their password, and the bot link (they `/start` it).

---

## 4. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Site can't be reached" on `localhost:3000` | Wrong port — UI is on **3001** | Retype `http://localhost:3001` |
| OAuth URL fails with a Microsoft error page | URL was time-signed and expired (>10 min) | Ask for a fresh URL |
| OAuth consent accepted but lands on error | Success redirect went to :3000 (old config) | The connection actually SUCCEEDED — check `/api/v1/auth/oauth/tokens` |
| Bot not responding | Backend down, or poller not started | Check `http://localhost:8001/alive`; restart backend (§1) |
| Frontend build error mentioning Turbopack | `next dev` without `--webpack` on this Mac | Use the exact command in §1 |
| Bot answers without remembering | Memory assembly off / store empty | Restart backend; check the 🧠 drawer in the web chat |
| `docker` commands fail | Docker Desktop is broken on this Mac (known) | Use the native path in §1; docker is not needed for the pilot |

---

## 5. What's where (for the person operating the Mac)

| Thing | Location |
|---|---|
| All configuration/secrets | `~/projects/atom/.env` (git-ignored — **back this up**) |
| Database (users, tokens, graph, facts) | `~/projects/atom/data/atom.db` |
| Vector memory (emails, docs, episodes) | `~/projects/atom/data/atom_memory/` |
| Admin password (bootstrap) | `backend/logs/bootstrap_admin_password.txt` |
| Backend log | `/tmp/atom-backend.log` |
| Frontend log | `/tmp/atom-frontend.log` |
| Nightly backup (recommended) | copy `data/` + `.env` to an external drive |

**Never commit `.env` or `data/`** — both are git-ignored; keep it that way.
