# Missing Credentials & Environment Configuration Guide

This guide documents all required environment variables and credentials for the ATOM application, covering **117 discovered integrations**, Core services, AI providers, and Database configurations. Use this reference to create your `.env` file for E2E testing and AI validation.

## 1. Core Configuration

| Variable | Description | Default / Example |
|----------|-------------|-------------------|
| `NODE_ENV` | Environment mode | `development` or `production` |
| `NEXT_PUBLIC_API_BASE_URL` | URL of the Python backend (for Frontend) | `http://localhost:8000` |
| `PYTHON_API_SERVICE_BASE_URL` | URL of the Python backend (for Backend/Skills) | `http://localhost:8000` |
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

> [!NOTE]
> **Authentication Methods:**
> *   **AI Providers (BYOK):** Use **API Keys** (copy-paste). This is standard for LLM providers like OpenAI and Anthropic. Keys are encrypted using `BYOK_ENCRYPTION_KEY`.
> *   **Third-Party Apps:** Use **OAuth 2.0** (Connect button). This is standard for user-facing apps like Slack, Google, and Salesforce. Tokens are encrypted using `ATOM_ENCRYPTION_KEY`.

## 4. Authentication & Security

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string for NextAuth user data and app data |
| `NEXTAUTH_SECRET` | Secret for NextAuth.js session encryption (Generate: `openssl rand -base64 32`) |
| `NEXTAUTH_URL` | Canonical URL of your site (e.g., `http://localhost:3000` or `https://yourdomain.com`) |
| `ATOM_ENCRYPTION_KEY` | Key used to encrypt stored OAuth tokens (Must be 32 bytes base64) |
| `BYOK_ENCRYPTION_KEY` | Key used to encrypt AI Provider keys (Must be 32 bytes base64) |

> **Note:** The application now uses **NextAuth only** for authentication. Supabase and SuperTokens have been removed.

> [!IMPORTANT]
> **User Registration Required**: After the NextAuth production migration, users must register new accounts. The demo user (`demo@example.com`) has been removed. See `docs/nextauth_production_setup.md` for setup instructions.

## 5. OAuth Callback URLs - Standardized Pattern

### Standard Pattern

All OAuth integrations use the **standardized callback pattern**:

```
http://localhost:3000/api/integrations/[service]/callback
```

**For Production:** Replace `http://localhost:3000` with your production domain:
```
https://yourdomain.com/api/integrations/[service]/callback
```

### OAuth Callback URL Reference

Use these exact URLs when configuring OAuth apps in provider dashboards:

| Service | Local Development | Production |
|---------|-------------------|------------|
| **Communication** |  |  |
| Slack | `http://localhost:3000/api/integrations/slack/callback` | `https://yourdomain.com/api/integrations/slack/callback` |
| Zoom | `http://localhost:3000/api/integrations/zoom/callback` | `https://yourdomain.com/api/integrations/zoom/callback` |
| MS Teams | `http://localhost:3000/api/integrations/msteams/callback` | `https://yourdomain.com/api/integrations/msteams/callback` |
| **Google Services** |  |  |
| Gmail | `http://localhost:3000/api/integrations/gmail/callback` | `https://yourdomain.com/api/integrations/gmail/callback` |
| Google Drive | `http://localhost:3000/api/integrations/google/callback` | `https://yourdomain.com/api/integrations/google/callback` |
| Google Calendar | `http://localhost:3000/api/integrations/google/callback` | `https://yourdomain.com/api/integrations/google/callback` |
| **Project Management** |  |  |
| Jira | `http://localhost:3000/api/integrations/jira/callback` | `https://yourdomain.com/api/integrations/jira/callback` |
| Linear | `http://localhost:3000/api/integrations/linear/callback` | `https://yourdomain.com/api/integrations/linear/callback` |
| Notion | `http://localhost:3000/api/integrations/notion/callback` | `https://yourdomain.com/api/integrations/notion/callback` |
| Monday | `http://localhost:3000/api/integrations/monday/callback` | `https://yourdomain.com/api/integrations/monday/callback` |
| **CRM** |  |  |
| Salesforce | `http://localhost:3000/api/integrations/salesforce/callback` | `https://yourdomain.com/api/integrations/salesforce/callback` |
| HubSpot | `http://localhost:3000/api/integrations/hubspot/callback` | `https://yourdomain.com/api/integrations/hubspot/callback` |
| Zendesk | `http://localhost:3000/api/integrations/zendesk/callback` | `https://yourdomain.com/api/integrations/zendesk/callback` |
| **Development** |  |  |
| GitHub | `http://localhost:3000/api/integrations/github/callback` | `https://yourdomain.com/api/integrations/github/callback` |
| GitLab | `http://localhost:3000/api/integrations/gitlab/callback` | `https://yourdomain.com/api/integrations/gitlab/callback` |
| Bitbucket | `http://localhost:3000/api/integrations/bitbucket/callback` | `https://yourdomain.com/api/integrations/bitbucket/callback` |
| **Finance** |  |  |
| QuickBooks | `http://localhost:3000/api/integrations/quickbooks/callback` | `https://yourdomain.com/api/integrations/quickbooks/callback` |
| Xero | `http://localhost:3000/api/integrations/xero/callback` | `https://yourdomain.com/api/integrations/xero/callback` |
| Stripe | `http://localhost:3000/api/integrations/stripe/callback` | `https://yourdomain.com/api/integrations/stripe/callback` |
| **Cloud Storage** |  |  |
| Azure | `http://localhost:3000/api/integrations/azure/callback` | `https://yourdomain.com/api/integrations/azure/callback` |

> **Note:** Some services may require you to explicitly whitelist localhost URLs. For services that don't allow localhost, you may need to use a tunneling service like ngrok during development.

> **Migration Notice:** We're standardizing all OAuth callbacks to `/api/integrations/[service]/callback`. Legacy URLs (e.g., `/api/hubspot/oauth/callback`) will redirect automatically for backward compatibility.


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
- **Environment Variables:** `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET`
- **OAuth Callback URL:** `http://localhost:3000/api/integrations/zoom/callback`
- **Setup Instructions:**
  1. Go to [Zoom App Marketplace](https://marketplace.zoom.us/)
  2. Click "Develop" → "Build App"
  3. Choose "OAuth" app type (User-managed app)
  4. Fill in app information
  5. Copy **Client ID** and **Client Secret**
  6. Add redirect URI: 
     - Local: `http://localhost:3000/api/integrations/zoom/callback`
     - Production: `https://yourdomain.com/api/integrations/zoom/callback`
  7. Add required scopes: `meeting:write`, `meeting:read`, `user:read`
  8. Activate the app

### Project Management

> **Already Configured:** Asana ✅, Jira ✅, Monday.com ✅, Notion ✅, Linear ✅  
> **Need Setup:** Trello

#### Trello
- **Environment Variables:** `TRELLO_API_KEY`, `TRELLO_CLIENT_SECRET`
- **OAuth Callback URL:** `http://localhost:3000/api/integrations/trello/callback`
- **Setup Instructions:**
  1. Go to [Trello Power-Ups Admin](https://trello.com/power-ups/admin)
  2. Click "New" → "Create Power-Up"
  3. Fill in required information
  4. Navigate to "API Key" section
  5. Copy your **API Key** (this is your Client ID)
  6. Click "Generate a new Secret" to get your **Client Secret**
  7. Add Allowed Origin: `http://localhost:3000` (and your production domain)
  8. Note: Trello uses a custom OAuth 1.0a implementation or their new OAuth 2.0 flow. We use the standard 3-legged OAuth flow.

### CRM

> **Already Configured:** None  
> **Need Setup:** Salesforce, HubSpot, Zendesk, Freshdesk, Intercom

#### Salesforce (Configured ✅)
- **Environment Variables:** `SALESFORCE_CLIENT_ID`, `SALESFORCE_CLIENT_SECRET`
- **Credentials:**
  - Client ID: `INSERT_CLIENT_ID`
  - Client Secret: `INSERT_CLIENT_SECRET`
- **OAuth Callback URL:** `http://localhost:3000/api/integrations/salesforce/callback`

#### HubSpot (Configured ✅)
- **Environment Variables:** `HUBSPOT_CLIENT_ID`, `HUBSPOT_CLIENT_SECRET`
- **Credentials:**
  - Client ID: `INSERT_CLIENT_ID`
  - Client Secret: `INSERT_CLIENT_SECRET`
- **OAuth Callback URL:** `http://localhost:3000/api/integrations/hubspot/callback`

#### Zendesk (Configured ✅)
- **Environment Variables:** `ZENDESK_CLIENT_ID`, `ZENDESK_CLIENT_SECRET`, `ZENDESK_SUBDOMAIN`
- **Credentials:**
  - Client ID: `INSERT_CLIENT_ID`
  - Client Secret: `INSERT_CLIENT_SECRET`
  - Subdomain: `INSERT_SUBDOMAIN`
- **OAuth Callback URL:** `http://localhost:3000/api/integrations/zendesk/callback`

#### Freshdesk (Skipped by user)
- **Environment Variables:** `FRESHDESK_CLIENT_ID`, `FRESHDESK_CLIENT_SECRET`, `FRESHDESK_DOMAIN`
- **OAuth Callback URL:** `http://localhost:3000/api/integrations/freshdesk/callback`

#### Intercom (Configured ✅)
- **Environment Variables:** `INTERCOM_CLIENT_ID`, `INTERCOM_CLIENT_SECRET`
- **Credentials:**
  - Client ID: `INSERT_CLIENT_ID`
  - Client Secret: `INSERT_CLIENT_SECRET`
- **OAuth Callback URL:** `http://localhost:3000/api/integrations/intercom/callback`

### Development

> **Already Configured:** GitHub ✅  
> **Need Setup:** GitLab, Bitbucket, Figma

#### GitLab (Configured ✅)
- **Environment Variables:** `GITLAB_CLIENT_ID`, `GITLAB_CLIENT_SECRET`
- **Credentials:**
  - Client ID: `INSERT_CLIENT_ID`
  - Client Secret: `INSERT_CLIENT_SECRET`
- **OAuth Callback URL:** `http://localhost:3000/api/integrations/gitlab/callback`

#### Bitbucket (Configured ✅)
- **Environment Variables:** `BITBUCKET_CLIENT_ID`, `BITBUCKET_CLIENT_SECRET`
- **Credentials:**
  - Client ID: `INSERT_CLIENT_ID`
  - Client Secret: `INSERT_CLIENT_SECRET`
- **OAuth Callback URL:** `http://localhost:3000/api/integrations/bitbucket/callback`

#### Figma
- **Environment Variables:** `FIGMA_CLIENT_ID`, `FIGMA_CLIENT_SECRET`
- **OAuth Callback URL:** `http://localhost:3000/api/integrations/figma/callback`
- **Setup Instructions:**
  1. Go to [Figma Developer Platform](https://www.figma.com/developers/apps)
  2. Click "Create new app" or select an existing app
  3. Navigate to "OAuth" settings
  4. Add **Redirect URI**:
     - Local: `http://localhost:3000/api/integrations/figma/callback`
     - Production: `https://yourdomain.com/api/integrations/figma/callback`
  5. Copy your **Client ID** and **Client Secret**
  6. Set environment variables:
     ```
     FIGMA_CLIENT_ID=your_client_id
     FIGMA_CLIENT_SECRET=your_client_secret
     ```
  7. **Required Scopes:** `file:read` (minimum), add `file:write` or `webhooks` as needed

### Storage

> **Already Configured:** Google Drive ✅, Box ✅, OneDrive ✅ (via Microsoft)  
> **Need Setup:** Dropbox

#### Dropbox
- **Environment Variables:** `DROPBOX_CLIENT_ID`, `DROPBOX_CLIENT_SECRET`
- **OAuth Callback URL:** `http://localhost:3000/api/integrations/dropbox/callback`
- **Setup Instructions:**
  1. Go to [Dropbox App Console](https://www.dropbox.com/developers/apps)
  2. Click "Create app"
  3. Choose "Scoped access" API
  4. Choose "Full Dropbox" or "App folder" access type
  5. Name your app
  6. Navigate to "Settings" tab
  7. Copy **App key** (Client ID) and **App secret** (Client Secret)
  8. Add **Redirect URI**:
     - Local: `http://localhost:3000/api/integrations/dropbox/callback`
     - Production: `https://yourdomain.com/api/integrations/dropbox/callback`
  9. Under "Permissions" tab, enable required scopes:
     - `files.metadata.read` - View file and folder metadata
     - `files.content.read` - View content of your Dropbox files
     - `files.content.write` - Edit content of your Dropbox files
     - `account_info.read` - View account information
  10. Set environment variables:
      ```
      DROPBOX_CLIENT_ID=your_app_key
      DROPBOX_CLIENT_SECRET=your_app_secret
      ```

### Email

> **Already Configured:** Gmail ✅ (via Google), Outlook ✅ (via Microsoft)  
> **Need Setup:** Mailchimp

#### Mailchimp (Configured ✅)
- **Environment Variables:** `MAILCHIMP_CLIENT_ID`, `MAILCHIMP_CLIENT_SECRET`
- **Credentials:**
  - Client ID: `INSERT_CLIENT_ID`
  - Client Secret: `INSERT_CLIENT_SECRET`
- **OAuth Callback URL:** `http://localhost:3000/api/integrations/mailchimp/callback`

### Finance

> **Already Configured:** None  
> **Need Setup:** Stripe, QuickBooks, Xero, Shopify

#### Stripe
- **Environment Variables:** `STRIPE_CLIENT_ID`, `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`
- **OAuth Callback URL:** `http://localhost:3000/api/integrations/stripe/callback`
- **Setup Instructions:**
  1. Go to [Stripe Dashboard](https://dashboard.stripe.com/)
  2. Navigate to Settings → Connect → Settings
  3. Enable "Standard" accounts (or Express/Custom as needed)
  4. Add Redirect URI:
     - Local: `http://localhost:3000/api/integrations/stripe/callback`
     - Production: `https://yourdomain.com/api/integrations/stripe/callback`
  5. Copy **Live mode client ID** (or Test mode client ID) for `STRIPE_CLIENT_ID`
  6. Go to Developers → API keys
  7. Copy **Secret key** (`sk_...`) and **Publishable key** (`pk_...`)
  8. For webhooks: Developers → Webhooks → Add endpoint (`/api/webhooks/stripe`) and get Signing Secret

#### QuickBooks
- **Environment Variables:** 
  - `QUICKBOOKS_CLIENT_ID` - Your QuickBooks app client ID
  - `QUICKBOOKS_CLIENT_SECRET` - Your QuickBooks app client secret
  - `QUICKBOOKS_REDIRECT_URI` - OAuth callback URL (must match Intuit app settings)
  - `QUICKBOOKS_ENVIRONMENT` - `sandbox` or `production` (default: `sandbox`)
- **OAuth Callback URL:** `http://localhost:3000/api/integrations/quickbooks/callback`
- **Setup Instructions:**
  1. Go to [Intuit Developer Portal](https://developer.intuit.com/)
  2. Create an account or sign in with your Intuit ID
  3. Click "My Apps" → **"Create an app"**
  4. Select **"QuickBooks Online and Payments"** as the platform
  5. Fill in app information:
     - **App name**: Your app name (e.g., "ATOM Integration")
     - **App description**: Brief description of your integration
  6. Navigate to **"Keys & credentials"** tab (or "Development" tab)
  7. Copy your **Client ID** and **Client Secret**
     - Note: Use "Development" keys for testing, "Production" keys for live use
  8. Add **Redirect URI**:
     - Local: `http://localhost:3000/api/integrations/quickbooks/callback`
     - Production: `https://yourdomain.com/api/integrations/quickbooks/callback`
  9. **Required Scopes** (automatically included with QuickBooks Online API):
     - `com.intuit.quickbooks.accounting` - Access to accounting data
     - `com.intuit.quickbooks.payment` - Access to payment data (if using payments)
  10. Set environment variables:
      ```
      QUICKBOOKS_CLIENT_ID=your_client_id
      QUICKBOOKS_CLIENT_SECRET=your_client_secret
      QUICKBOOKS_REDIRECT_URI=http://localhost:3000/api/integrations/quickbooks/callback
      QUICKBOOKS_ENVIRONMENT=sandbox
      ```
  11. **Important Notes:**
      - QuickBooks uses OAuth 2.0 with OpenID Connect
      - Access tokens expire after 1 hour; refresh tokens last 100 days
      - You must request a new refresh token before the 100-day expiration
      - Test with QuickBooks Sandbox companies before production
      - Production apps require Intuit approval (app review process)
      - For production, change `QUICKBOOKS_ENVIRONMENT=production` and update redirect URI


#### Xero (Configured ✅)
- **Environment Variables:** `XERO_CLIENT_ID`, `XERO_CLIENT_SECRET`
- **Credentials:**
  - Client ID: `INSERT_CLIENT_ID`
  - Client Secret: `INSERT_CLIENT_SECRET`
- **OAuth Callback URL:** `http://localhost:3000/api/integrations/xero/callback`

#### Shopify (Configured ✅)
- **Environment Variables:** `SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_SHOP_NAME`
- **Credentials:**
  - API Key: `INSERT_API_KEY`
  - API Secret: `INSERT_API_SECRET`
  - Shop Name: `INSERT_SHOP_NAME`
- **OAuth Callback URL:** `http://localhost:3000/api/integrations/shopify/callback`

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
- **Environment Variables:** `AIRTABLE_CLIENT_ID`, `AIRTABLE_CLIENT_SECRET`
- **OAuth Callback URL:** `http://localhost:3000/api/integrations/airtable/callback`
- **Setup Instructions:**
  1. Go to [Airtable Builder Hub](https://airtable.com/create/oauth)
  2. Click "Create new OAuth integration"
  3. Fill in name and details
  4. Add Redirect URI:
     - Local: `http://localhost:3000/api/integrations/airtable/callback`
     - Production: `https://yourdomain.com/api/integrations/airtable/callback`
  5. Select Scopes: `data.records:read`, `data.records:write`, `schema.bases:read`
  6. Save and copy **Client ID** and **Client Secret**
  7. **Note:** Airtable API Keys are deprecated. Use OAuth.

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
