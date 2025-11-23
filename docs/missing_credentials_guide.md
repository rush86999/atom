# Missing Credentials & Environment Configuration Guide

This guide documents all required environment variables and credentials for the ATOM application, covering **117 discovered integrations**, Core services, AI providers, and Database configurations. Use this reference to create your `.env` file for E2E testing and AI validation.

## 1. Core Configuration

| Variable | Description | Default / Example |
|----------|-------------|-------------------|
| `NODE_ENV` | Environment mode | `development` or `production` |
| `NEXT_PUBLIC_API_BASE_URL` | URL of the Python backend (for Frontend) | `http://localhost:5059` |
| `PYTHON_API_SERVICE_BASE_URL` | URL of the Python backend (for Backend/Skills) | `http://localhost:5059` |
| `LOG_LEVEL` | Logging verbosity | `info`, `debug` |

## 2. Database & Storage

| Variable | Description | Default |
|----------|-------------|---------|
| `LANCEDB_PATH` | Path to LanceDB vector store | `./data/lancedb` or `/Users/developer/atom_lancedb` |
| `SQLITE_PATH` | Path to SQLite database | `./data/atom.db` |
| `ENABLE_LANCEDB` | Enable/Disable LanceDB | `true` |

## 3. AI Service Credentials

| Variable | Description | How to Obtain |
|----------|-------------|---------------|
| `OPENAI_API_KEY` | OpenAI API Key (GPT-4, GPT-3.5) | [OpenAI Platform](https://platform.openai.com/api-keys) |
| `ANTHROPIC_API_KEY` | Anthropic API Key (Claude 3) | [Anthropic Console](https://console.anthropic.com/) |
| `DEEPSEEK_API_KEY` | DeepSeek API Key (Used by AI Validator) | [DeepSeek Platform](https://platform.deepseek.com/) |
| `GOOGLE_GENERATIVE_AI_API_KEY` | Google Gemini API Key | [Google AI Studio](https://aistudio.google.com/) |
| `GLM_API_KEY` | GLM 4.6 API Key (Z.ai) | Contact Z.ai for access |

> **Note:** The Independent AI Validator also looks for credentials in `backend/independent_ai_validator/data/credentials.json`.

## 4. Authentication & Security

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string for NextAuth user data and app data |
| `NEXTAUTH_SECRET` | Secret for NextAuth.js session encryption (Generate: `openssl rand -base64 32`) |
| `NEXTAUTH_URL` | Canonical URL of your site (e.g., `http://localhost:3000` or `https://yourdomain.com`) |
| `ATOM_ENCRYPTION_KEY` | Key used to encrypt stored OAuth tokens (Must be 32 bytes base64) |

> **Note:** The application now uses **NextAuth only** for authentication. Supabase and SuperTokens have been removed.

> [!IMPORTANT]
> **User Registration Required**: After the NextAuth production migration, users must register new accounts. The demo user (`demo@example.com`) has been removed. See `docs/nextauth_production_setup.md` for setup instructions.

## 5. OAuth Callback URLs for Local Testing


When setting up OAuth integrations for **local development**, use these callback URLs in your app configurations:

**Standard OAuth Callback Pattern:**
```
http://localhost:3000/api/auth/callback/[service_name]
```

**Common Local Callback URLs:**
- Slack: `http://localhost:3000/api/auth/callback/slack`
- Google (Drive, Gmail, Calendar): `http://localhost:3000/api/auth/callback/google`
- Microsoft (Teams, Outlook, OneDrive): `http://localhost:3000/api/auth/callback/microsoft`
- GitHub: `http://localhost:3000/api/auth/callback/github`
- Asana: `http://localhost:3000/api/auth/callback/asana`
- Jira: `http://localhost:3000/api/auth/callback/jira`
- Notion: `http://localhost:3000/api/auth/callback/notion`
- Discord: `http://localhost:3000/api/auth/callback/discord`

**For Production:** Replace `http://localhost:3000` with your production domain, e.g., `https://yourdomain.com`

> **Note:** Some services may require you to explicitly whitelist localhost URLs. For services that don't allow localhost (rare), you may need to use a tunneling service like ngrok during development.

## 6. Credentials Status Overview

### ✅ Already Configured (Found in `notes/credentials.md`)

The following services already have credentials configured. These are ready to use:

**AI Services:**
- OpenAI, Anthropic, DeepSeek, Google Gemini, GLM

**Communication:**
- Slack (Client ID, Secret, Bot Token, Signing Secret)
- Discord (Bot Token)

**Microsoft 365 Suite (Single credential set):**
- Microsoft Teams, Outlook Email, OneDrive, Outlook Calendar

**Google Suite (Single credential set):**
- Google Drive, Gmail, Google Calendar, Google Chat

**Project Management:**
- Asana, Jira, Monday.com, Notion, Linear

**Development:**
- GitHub

**Storage:**
- Box

### ⚠️ Missing Credentials (Setup Required)

The following integrations need credentials. Detailed setup instructions are provided below.

**Communication:** WhatsApp, Telegram, Zoom  
**Project Management:** Trello  
**CRM:** Salesforce, HubSpot, Zendesk, Freshdesk, Intercom  
**Development:** GitLab, Bitbucket, Figma  
**Storage:** Dropbox  
**Email:** Mailchimp  
**Finance:** Stripe, QuickBooks, Xero, Shopify  
**Other:** Airtable, Tableau, Canva

---

## 5. Setup Instructions for Missing Credentials

### Communication

> **Already Configured:** Slack ✅, Discord ✅, Microsoft Teams ✅  
> **Need Setup:** WhatsApp, Telegram, Zoom

#### WhatsApp Business
- **Environment Variables:** `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`
- **Setup Instructions:**
  1. Go to [Meta for Developers](https://developers.facebook.com/)
  2. Create a new app → Select "Business" type
  3. Add "WhatsApp" product to your app
  4. Navigate to WhatsApp → "API Setup"
  5. Copy **Phone Number ID** and **Access Token**
  6. Configure webhook URL: `https://yourdomain.com/api/webhooks/whatsapp`
  7. Note: Requires Business verification for production use

#### Telegram
- **Environment Variables:** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`
- **Setup Instructions:**
  1. Open Telegram and search for [@BotFather](https://t.me/botfather)
  2. Send `/newbot` command
  3. Follow prompts to name your bot
  4. Copy the **Bot Token** provided
  5. For API credentials: Go to [my.telegram.org](https://my.telegram.org/)
  6. Login and navigate to "API development tools"
  7. Create an application and copy **API ID** and **API Hash**

#### Zoom
- **Environment Variables:** `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET`, `ZOOM_REDIRECT_URI`
- **Setup Instructions:**
  1. Go to [Zoom App Marketplace](https://marketplace.zoom.us/)
  2. Click "Develop" → "Build App"
  3. Choose "OAuth" app type (User-managed app)
  4. Fill in app information
  5. Copy **Client ID** and **Client Secret**
  6. Add redirect URI: `http://localhost:3000/api/auth/callback/zoom` (or your production URL)
  7. Add required scopes: `meeting:write`, `meeting:read`, `user:read`
  8. Activate the app

### Project Management

> **Already Configured:** Asana ✅, Jira ✅, Monday.com ✅, Notion ✅, Linear ✅  
> **Need Setup:** Trello

#### Trello
- **Environment Variables:** `TRELLO_API_KEY`, `TRELLO_TOKEN`
- **Setup Instructions:**
  1. Go to [Trello Power-Ups Admin](https://trello.com/power-ups/admin)
  2. Click "New" → "Create Power-Up"
  3. Fill in required information
  4. Navigate to "API Key" section
  5. Copy your **API Key**
  6. Click "Generate a Token" link to get **Token**
  7. Authorize the token for your account

### CRM

> **Already Configured:** None  
> **Need Setup:** Salesforce, HubSpot, Zendesk, Freshdesk, Intercom

#### Salesforce
- **Environment Variables:** `SALESFORCE_CLIENT_ID`, `SALESFORCE_CLIENT_SECRET`
- **Setup Instructions:**
  1. Login to [Salesforce](https://login.salesforce.com/)
  2. Navigate to Setup → App Manager
  3. Click "New Connected App"
  4. Fill in app name, API name, and contact email
  5. Enable "OAuth Settings"
  6. Add callback URL: `http://localhost:3000/api/auth/callback/salesforce`
  7. Select OAuth scopes: "Full access (full)", "Perform requests at any time (refresh_token, offline_access)"
  8. Save and copy **Consumer Key** (Client ID) and **Consumer Secret** (Client Secret)

#### HubSpot
- **Environment Variables:** `HUBSPOT_CLIENT_ID`, `HUBSPOT_CLIENT_SECRET`
- **Setup Instructions:**
  1. Go to [HubSpot Developers](https://developers.hubspot.com/)
  2. Click "Create app" → Fill in app information
  3. Navigate to "Auth" tab
  4. Add redirect URL: `http://localhost:3000/api/auth/callback/hubspot`
  5. Select required scopes: `crm.objects.contacts.read`, `crm.objects.companies.read`, etc.
  6. Copy **Client ID** and **Client Secret** from Auth tab

#### Zendesk
- **Environment Variables:** `ZENDESK_CLIENT_ID`, `ZENDESK_CLIENT_SECRET`, `ZENDESK_SUBDOMAIN`
- **Setup Instructions:**
  1. Go to Zendesk Admin Center → Apps and integrations → APIs → OAuth Clients
  2. Click "Add OAuth client"
  3. Fill in client name and company
  4. Set redirect URL: `http://localhost:3000/api/auth/callback/zendesk`
  5. Copy **Client ID** (Unique Identifier) and **Secret**
  6. Note your Zendesk subdomain (e.g., `yourcompany` from `yourcompany.zendesk.com`)

#### Freshdesk
- **Environment Variables:** `FRESHDESK_API_KEY`, `FRESHDESK_DOMAIN`
- **Setup Instructions:**
  1. Login to your Freshdesk account
  2. Click on your profile picture → Profile settings
  3. Scroll to "API Key" section
  4. Copy your **API Key** (generate if not present)
  5. Note your Freshdesk domain (e.g., `yourcompany.freshdesk.com`)

#### Intercom
- **Environment Variables:** `INTERCOM_CLIENT_ID`, `INTERCOM_CLIENT_SECRET`
- **Setup Instructions:**
  1. Go to [Intercom Developer Hub](https://developers.intercom.com/)
  2. Click "Your apps" → "New app"
  3. Fill in app details and click "Create app"
  4. Navigate to "Authentication" in left sidebar
  5. Add redirect URL: `http://localhost:3000/api/auth/callback/intercom`
  6. Copy **Client ID** and **Client Secret**

### Development

> **Already Configured:** GitHub ✅  
> **Need Setup:** GitLab, Bitbucket, Figma

#### GitLab
- **Environment Variables:** `GITLAB_CLIENT_ID`, `GITLAB_CLIENT_SECRET`
- **Setup Instructions:**
  1. Go to [GitLab Applications](https://gitlab.com/-/profile/applications)
  2. Fill in application name
  3. Add redirect URI: `http://localhost:3000/api/auth/callback/gitlab`
  4. Select scopes: `api`, `read_repository`, `write_repository`
  5. Click "Save application"
  6. Copy **Application ID** (Client ID) and **Secret**

#### Bitbucket
- **Environment Variables:** `BITBUCKET_CLIENT_ID`, `BITBUCKET_CLIENT_SECRET`
- **Setup Instructions:**
  1. Go to [Bitbucket Settings](https://bitbucket.org/account/settings/oauth-consumers/new)
  2. Fill in OAuth consumer name
  3. Add callback URL: `http://localhost:3000/api/auth/callback/bitbucket`
  4. Select permissions: Repository (Read, Write), Account (Read)
  5. Click "Save"
  6. Copy **Key** (Client ID) and **Secret**

#### Figma
- **Environment Variables:** `FIGMA_ACCESS_TOKEN`
- **Setup Instructions:**
  1. Go to [Figma Account Settings](https://www.figma.com/settings)
  2. Scroll to "Personal access tokens"
  3. Click "Generate new token"
  4. Name your token and copy the **Access Token** (shown only once)
  5. For OAuth apps: Use [Figma Developer Platform](https://www.figma.com/developers/api)

### Storage

> **Already Configured:** Google Drive ✅, Box ✅, OneDrive ✅ (via Microsoft)  
> **Need Setup:** Dropbox

#### Dropbox
- **Environment Variables:** `DROPBOX_CLIENT_ID`, `DROPBOX_CLIENT_SECRET`
- **Setup Instructions:**
  1. Go to [Dropbox App Console](https://www.dropbox.com/developers/apps)
  2. Click "Create app"
  3. Choose "Scoped access" API
  4. Choose "Full Dropbox" or "App folder" access
  5. Name your app
  6. Navigate to "Settings" tab
  7. Copy **App key** (Client ID) and **App secret** (Client Secret)
  8. Add redirect URI: `http://localhost:3000/api/auth/callback/dropbox`
  9. Under "Permissions" tab, enable required scopes

### Email

> **Already Configured:** Gmail ✅ (via Google), Outlook ✅ (via Microsoft)  
> **Need Setup:** Mailchimp

#### Mailchimp
- **Environment Variables:** `MAILCHIMP_API_KEY`, `MAILCHIMP_SERVER_PREFIX`
- **Setup Instructions:**
  1. Login to [Mailchimp](https://mailchimp.com/)
  2. Navigate to Account → Extras → API keys
  3. Click "Create A Key"
  4. Copy the **API Key**
  5. Note your **Server Prefix** (e.g., `us1`, `us2`) from the API key or account settings

### Finance

> **Already Configured:** None  
> **Need Setup:** Stripe, QuickBooks, Xero, Shopify

#### Stripe
- **Environment Variables:** `STRIPE_API_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`
- **Setup Instructions:**
  1. Go to [Stripe Dashboard](https://dashboard.stripe.com/)
  2. Navigate to Developers → API keys
  3. Copy **Secret key** (starts with `sk_`) for `STRIPE_API_KEY`
  4. Copy **Publishable key** (starts with `pk_`) for `STRIPE_PUBLISHABLE_KEY`
  5. For webhooks: Developers → Webhooks → Add endpoint
  6. Set endpoint URL: `https://yourdomain.com/api/webhooks/stripe`
  7. Copy **Signing secret** for `STRIPE_WEBHOOK_SECRET`

#### QuickBooks
- **Environment Variables:** `QUICKBOOKS_CLIENT_ID`, `QUICKBOOKS_CLIENT_SECRET`
- **Setup Instructions:**
  1. Go to [Intuit Developer Portal](https://developer.intuit.com/)
  2. Create an account or sign in
  3. Click "Create an app"
  4. Select "QuickBooks Online and Payments"
  5. Navigate to "Keys & credentials"
  6. Copy **Client ID** and **Client Secret**
  7. Add redirect URI: `http://localhost:3000/api/auth/callback/quickbooks`
  8. Select required scopes

#### Xero
- **Environment Variables:** `XERO_CLIENT_ID`, `XERO_CLIENT_SECRET`
- **Setup Instructions:**
  1. Go to [Xero Developer Portal](https://developer.xero.com/app/manage)
  2. Click "New app"
  3. Fill in app details
  4. Add OAuth 2.0 redirect URI: `http://localhost:3000/api/auth/callback/xero`
  5. Copy **Client ID** and **Client Secret**
  6. Generate and configure API scopes

#### Shopify
- **Environment Variables:** `SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_SHOP_NAME`
- **Setup Instructions:**
  1. Go to [Shopify Partners](https://partners.shopify.com/)
  2. Navigate to Apps → Create app
  3. Choose app type: "Public app" or "Custom app"
  4. Fill in app details
  5. Copy **API key** and **API secret**
  6. Add redirect URL: `http://localhost:3000/api/auth/callback/shopify`
  7. Note your shop name (e.g., `mystore` from `mystore.myshopify.com`)

### Calendar

> **Already Configured:** Google Calendar ✅ (via Google), Outlook Calendar ✅ (via Microsoft)  
> **Note:** These use the same Google and Microsoft credentials already configured

### Enterprise & Workflow Automation (5 Services)

| Service | Env Vars | Notes |
|---------|----------|-------|
| **Microsoft 365** | `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET` | Unified suite covering Teams, Outlook, OneDrive, SharePoint |
| **Workflow Automation** | N/A | Internal ATOM service for workflow orchestration |
| **Enterprise Security** | N/A | Internal ATOM security service |
| **Enterprise Unified** | N/A | Internal ATOM enterprise service |

### Other Services

> **Already Configured:** None  
> **Need Setup:** Airtable, Tableau, Canva

#### Airtable
- **Environment Variables:** `AIRTABLE_API_KEY`
- **Setup Instructions:**
  1. Login to [Airtable](https://airtable.com/)
  2. Click on your profile → Account
  3. Navigate to "API" section
  4. Generate or copy your **API Key**

#### Tableau
- **Environment Variables:** `TABLEAU_CLIENT_ID`, `TABLEAU_CLIENT_SECRET`
- **Setup Instructions:**
  1. Go to [Tableau Developer Portal](https://developer.tableau.com/)
  2. Create a Connected App
  3. Copy **Client ID** and **Client Secret**

#### Canva
- **Environment Variables:** `CANVA_CLIENT_ID`, `CANVA_CLIENT_SECRET`, `CANVA_TOKEN_ENCRYPTION_KEY`
- **Setup Instructions:**
  1. Go to [Canva Developers](https://www.canva.com/developers/)
  2. Create an app
  3. Copy **Client ID** and **Client Secret**
  4. Generate encryption key for token storage

---

## 6. Feature Flags

| Variable | Description | Default |
|----------|-------------|---------|
| `ENABLE_OAUTH` | Enable OAuth flows | `true` |
| `ENABLE_WORKFLOWS` | Enable background workflows | `true` |
| `ENABLE_VOICE` | Enable voice capabilities | `false` |

## 7. Setup Checklist

### Already Done ✅
- [x] AI Services configured (OpenAI, Anthropic, DeepSeek, Gemini, GLM)
- [x] Google suite configured (Drive, Gmail, Calendar, Chat)
- [x] Microsoft suite configured (Teams, Outlook, OneDrive, Calendar)
- [x] Project Management: Asana,Jira, Monday, Notion, Linear
- [x] Development: GitHub  
- [x] Storage: Box

### Still Needed ⚠️
- [ ] **Communication:** WhatsApp, Telegram, Zoom
- [ ] **Project Management:** Trello
- [ ] **CRM:** Salesforce, HubSpot, Zendesk, Freshdesk, Intercom
- [ ] **Development:** GitLab, Bitbucket, Figma
- [ ] **Storage:** Dropbox
- [ ] **Email:** Mailchimp
- [ ] **Finance:** Stripe, QuickBooks, Xero, Shopify
- [ ] **Other:** Airtable, Tableau, Canva
- [ ] Set `ATOM_ENCRYPTION_KEY` (Generate with: `python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"`)

## 8. Quick Reference

**Total:** 117 backend integration files discovered  
**Unique Services:** ~35-40 (many files are multiple implementations of same service)  
**Already Configured:** 20+ services covering AI, Google Suite, Microsoft Suite, and major PM tools  
**Missing:** ~15-20 additional third-party services need credentials
