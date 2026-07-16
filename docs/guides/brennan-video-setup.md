# Brennan.ca Use-Case Videos — Local Setup Guide

End-to-end setup for recording demo videos that show Atom acting as an **AI employee**
for a small metal-fabrication machinery distributor. Atom remembers leads, quotes,
vendor pricing, machine specs, inventory, and order history across conversations.

> **Audience:** the person recording the demos (local macOS dev machine).
> **Outcome:** 4 marketable videos, each a single natural-language command that runs
> a real workflow across Zoho + Outlook + Telegram + Office + OneDrive/WorkDrive + Shopify.

---

## 0. Prerequisites

| Tool | Why | Install |
|---|---|---|
| Python 3.11 + project venv | Backend | `backend/venv/bin/python` (already present) |
| Node 18+ | Next.js frontend | `brew install node` |
| ngrok | Public HTTPS for OAuth/webhooks | `brew install ngrok` |
| Chrome | Selenium B-roll recorder | `brew install --cask google-chrome` |

Start the backend and frontend in separate terminals:

```bash
# Terminal 1 — backend (port 8000)
cd backend && venv/bin/python -m uvicorn main_api_app:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — frontend (port 3000)
cd frontend-nextjs && npm run dev
```

---

## 1. ngrok tunnel (required for OAuth callbacks + Telegram webhooks)

```bash
ngrok http 8000
```

Note the forwarding URL, e.g. `https://abc123.ngrok-free.app`.
Atom already allowlists `.ngrok-free.app` hosts in its routing middleware, so the
tunnel routes correctly with no extra config.

You will use this URL for:
- **Telegram webhook** → `https://<ngrok>/api/telegram/webhook`
- **Microsoft OAuth redirect** → `https://<ngrok>/api/v1/auth/oauth/microsoft/callback`
- **Shopify OAuth redirect** → `https://<ngrok>/api/shopify/auth/callback`

> ngrok free URLs change on restart. For recording day, keep the tunnel up, or use a
> reserved domain (`ngrok http 8000 --domain=your-static.ngrok-free.app`).

---

## 2. Create the external app credentials

Create these **once**; the code fixes from Phase 1 make all of them work.

### 2a. Telegram bot (fastest — minutes)
1. Message **@BotFather** on Telegram → `/newbot` → choose a name → get the **bot token**.
2. (Optional) `/setsecret` to get a webhook secret token for request verification.
3. Register the webhook (one curl):
   ```bash
   curl -s "https://api.telegram.org/bot<TOKEN>/setWebhook" \
     -d "url=https://<ngrok>/api/telegram/webhook" \
     -d "secret_token=<SECRET>"
   ```

### 2b. Microsoft Azure AD app (Outlook + OneDrive)
1. Azure Portal → App registrations → New registration → **Accounts in any org + personal**.
2. Redirect URI (Web): `https://<ngrok>/api/v1/auth/oauth/microsoft/callback`
3. API permissions (Delegated): `Mail.ReadWrite`, `Mail.Send`, `Files.ReadWrite.All`,
   `offline_access`, `User.Read`.
4. Create a client secret. Note `Application (client) ID` + secret.

### 2c. Zoho API console (Inventory + Books + WorkDrive)
1. https://api-console.zoho.com → **Self Client** or **Server-based**.
2. Generate a token with these scopes:
   - `ZohoInventory.fullaccess.all`
   - `ZohoBooks.fullaccess.all`
   - `ZohoWorkDrive.files.ALL`   ← added in Phase 1
3. Note the **Org ID** for Inventory/Books (Zoho Admin → Organization Settings).
4. Regional endpoints: if your Zoho account is `.in`/`.eu`/`.com.au`, set
   `ZOHO_CRM_ACCOUNTS_URL` accordingly (default `https://accounts.zoho.com`).

> Zoho has no in-app OAuth callback route in Atom. Obtain the access/refresh token
> out-of-band (the Zoho self-client flow prints a grant token you exchange), then
> store it as a connection via the Connections UI or the `UserConnection` table.

### 2d. Shopify dev store
1. Create a **development store** (Shopify Partners dashboard).
2. Apps → Develop → Create a custom app → note API key + secret.
3. In the store, add a few sample products (press brake, fiber laser, plasma cutter,
   spare parts) with stock levels. (The `seed_demo.py` script below seeds these into
   Atom's knowledge graph directly, but having them in Shopify makes the sync realistic.)

### 2e. Google Cloud app (Google Drive — now real, not deferred)
1. Google Cloud Console → APIs & Services → enable the **Google Drive API**.
2. Credentials → Create OAuth client ID (Web application).
3. Authorized redirect URI: `https://<ngrok>/api/v1/auth/oauth/google/callback`
4. The required scopes (`drive.readonly`, `drive.file`, `spreadsheets`, `gmail`,
   `calendar`, `userinfo.email`) are requested automatically by Atom's OAuth handler.
5. Note the Client ID + Secret (same `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` used
   for Gmail/Calendar).

---

## 3. Environment variables

Append to `backend/.env` (copy from `backend/.env.example` if starting fresh):

```ini
# --- ngrok-derived (replace <ngrok> with your tunnel URL) ---
FRONTEND_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,https://<ngrok>.ngrok-free.app

# --- Telegram ---
TELEGRAM_BOT_TOKEN=<from BotFather>
TELEGRAM_SECRET_TOKEN=<from /setsecret>
TELEGRAM_WEBHOOK_URL=https://<ngrok>/api/telegram/webhook

# --- Microsoft (Outlook + OneDrive) ---
MICROSOFT_CLIENT_ID=<azure app id>
MICROSOFT_CLIENT_SECRET=<azure secret>
MICROSOFT_REDIRECT_URI=https://<ngrok>/api/v1/auth/oauth/microsoft/callback

# --- Zoho (Inventory + Books + WorkDrive) ---
ZOHO_CLIENT_ID=<zoho client id>
ZOHO_CLIENT_SECRET=<zoho secret>
ZOHO_REDIRECT_URI=https://<ngrok>/api/zoho-workdrive/callback
ZOHO_ORG_ID=<your org id>
ZOHO_CRM_ACCOUNTS_URL=https://accounts.zoho.com

# --- Shopify ---
SHOPIFY_API_KEY=<shopify key>
SHOPIFY_API_SECRET=<shopify secret>
SHOPIFY_SHOP_NAME=<your-store>.myshopify.com
SHOPIFY_ACCESS_TOKEN=<shopify admin token>
SHOPIFY_WEBHOOK_SECRET=<choose a secret>

# --- Google (Drive + Gmail + Calendar — same app covers all) ---
GOOGLE_CLIENT_ID=<google client id>
GOOGLE_CLIENT_SECRET=<google secret>
GOOGLE_REDIRECT_URI=https://<ngrok>/api/v1/auth/oauth/google/callback
# GOOGLE_DRIVE_ACCESS_TOKEN=<optional standalone Drive token for dev>

# --- Memory (turn-fact extraction) ---
# CRITICAL: extraction is OFF by default in code defaults; must enable.
TURN_FACT_EXTRACTION_ENABLED=true
TURN_FACT_PRE_COMPRESS_ENABLED=true
TURN_FACT_VECTOR_RECALL_ENABLED=true
TURN_FACT_MAX_PER_TURN=5

# --- At least ONE LLM provider key (cheapest = fast tier for memory extraction) ---
# DeepSeek, Groq, or Gemini Flash are cheapest. Any one is sufficient.
DEEPSEEK_API_KEY=<key>
# ...or GROQ_API_KEY / GOOGLE_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY

# --- Start the ingestion scheduled-sync loop (pulls integrations into memory) ---
ENABLE_INGESTION_SYNC=true
```

> **Why `ENABLE_INGESTION_SYNC=true`?** Phase 1 wired the scheduled-sync loop to app
> startup, gated behind this flag. With it on, Shopify/OneDrive/Telegram/Zoho data is
> periodically pulled into the knowledge graph so the agent "remembers" automatically.

---

## 4. Connect the integrations (OAuth flows)

With the backend running, connect each app so Atom stores a token:

```bash
# Microsoft (Outlook + OneDrive) — initiates OAuth in the browser
open "http://localhost:8000/api/v1/auth/oauth/microsoft/initiate"

# Google (Drive + Gmail + Calendar) — initiates OAuth in the browser
open "http://localhost:8000/api/v1/auth/oauth/google/initiate"

# Telegram — already connected via webhook (step 2a); send the bot a message to test.

# Zoho — token obtained out-of-band; save as a connection via the UI or API:
curl -X POST http://localhost:8000/api/connections \
  -H "Content-Type: application/json" \
  -d '{"integration_id":"zoho","name":"Zoho","credentials":{"access_token":"<TOKEN>","refresh_token":"<REFRESH>","api_domain":"https://www.zohoapis.com","organization_id":"<ORG_ID>"}}'

# Shopify — OAuth via the callback route
open "http://localhost:8000/api/shopify/auth/url"
```

---

## 5. Seed demo data + templates

```bash
cd backend && venv/bin/python scripts/brennan/seed_demo.py
```

This seeds (see `demo/brennan/` for the data):
- **Knowledge graph:** brennan.ca products, a sample customer, a vendor, and seed leads
  (so the agent has something to remember before recording).
- **Office templates** copied into `demo/brennan/templates/`:
  `Quote.docx`, `Invoice.docx`, `PurchaseOrder.docx`, `PriceList.xlsx`, `SpecSheet.docx`
  with literal placeholder tokens the agent's `modify_word_document` / `write_excel_cell`
  tools target.

---

## 6. Verify memory works (record-day smoke test)

Before recording, confirm the "remembers" story is real:

```bash
cd backend && venv/bin/python scripts/brennan/verify_memory.py
```

This checks:
1. Turn-fact extraction is on and the LLM provider responds (else the circuit breaker trips).
2. `turn_facts`, `agent_reasoning_steps_fts`, and `graph_nodes` tables exist.
3. A seeded knowledge-graph entity is retrievable.
4. The agent's maturity is above STUDENT (memory tools need ≥ INTERN; else read-only).

If the agent is stuck at STUDENT, graduate it via the UI (Agents → promote) or:

```bash
curl -X POST http://localhost:8000/api/v1/agents/<agent_id>/graduate \
  -H "Content-Type: application/json" -d '{"to_maturity":"SUPERVISED"}'
```

---

## 7. The 4 video flows

Each is a single command to the agent. See `demo/brennan/storyboards/` for scripts.

| # | Role | One-liner command | Memory it builds/recalls |
|---|---|---|---|
| 1 | **Sales Coordinator** | "ACME Fab asked for a quote on the 50-ton press brake. Create a quote and email it." | lead + quote line items (Office→memory) |
| 2 | **Bookkeeper** | "Shopify order #1001 just closed. Invoice it in Zoho Books and email the PDF." | order/invoice + shipping data (Outlook learner) |
| 3 | **Applications Engineer** | "ACME's asking if the laser cutter handles 20mm steel. Check with the vendor and reply." | vendor specs/pricing (WorkDrive/Office→memory) |
| 4 | **Shipping & Inventory Clerk** | "Sync press-brake stock to Shopify and tell me on Telegram if anything's low." | live inventory levels (Shopify/Zoho ingestion) |

---

## 8. Record B-roll (optional)

```bash
# Fix applied in Phase 6: output dir is now configurable via DEMO_OUTPUT_DIR
DEMO_OUTPUT_DIR=./demo/brennan/recordings python tests/record_demo.py
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Agent "forgets" between turns | `TURN_FACT_EXTRACTION_ENABLED=true` not loaded, or no LLM key set, or agent maturity = STUDENT |
| OneDrive/Outlook calls 401 | Token expired; ConnectionService auto-refreshes — check the connection is saved with a `refresh_token` |
| Telegram webhook not firing | ngrok URL changed; re-run the `setWebhook` curl from §2a |
| `NoProvidersConfiguredError` | Set at least one `*_API_KEY` env var (§3) |
| Shopify webhook 403 | `SHOPIFY_WEBHOOK_SECRET` mismatch |
