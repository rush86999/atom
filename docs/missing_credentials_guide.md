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

## 4. Security & Encryption

| Variable | Description |
|----------|-------------|
| `ATOM_ENCRYPTION_KEY` | Key used to encrypt stored tokens (Must be 32 bytes base64) |
| `NEXTAUTH_SECRET` | Secret for NextAuth.js session encryption |

## 5. Integration Credentials (117 Services)

ATOM supports **117 integrations** across 12 categories. Most follow a standard naming convention for OAuth credentials:

**Standard Convention:**
- Client ID: `ATOM_[SERVICE_NAME]_CLIENT_ID`
- Client Secret: `ATOM_[SERVICE_NAME]_CLIENT_SECRET`
- API Key: `ATOM_[SERVICE_NAME]_API_KEY`
- Redirect URI: `http://localhost:3000/api/auth/callback/[service_name]`

### Communication (34 Services)

#### Slack
- **Environment Variables:** `ATOM_SLACK_CLIENT_ID`, `ATOM_SLACK_CLIENT_SECRET`, `ATOM_SLACK_BOT_TOKEN`, `ATOM_SLACK_SIGNING_SECRET`
- **Setup Instructions:**
  1. Go to [Slack API Apps](https://api.slack.com/apps)
  2. Click "Create New App" → "From scratch"
  3. Name your app and select your workspace
  4. Navigate to "OAuth & Permissions" → Add redirect URL: `http://localhost:3000/api/auth/callback/slack`
  5. Under "Scopes" → Add Bot Token Scopes: `channels:read`, `channels:history`, `chat:write`, `users:read`
  6. Install app to workspace
  7. Copy **Client ID**, **Client Secret** from "Basic Information"
  8. Copy **Bot User OAuth Token** from "OAuth & Permissions"
  9. Copy **Signing Secret** from "Basic Information"

#### Discord
- **Environment Variables:** `ATOM_DISCORD_CLIENT_ID`, `ATOM_DISCORD_CLIENT_SECRET`, `ATOM_DISCORD_BOT_TOKEN`
- **Setup Instructions:**
  1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
  2. Click "New Application" and name it
  3. Navigate to "OAuth2" → Copy **Client ID** and **Client Secret**
  4. Add redirect URL: `http://localhost:3000/api/auth/callback/discord`
  5. Navigate to "Bot" → Click "Add Bot"
  6. Copy the **Bot Token** (click "Reset Token" if needed)
  7. Enable required bot permissions: "Send Messages", "Read Message History"

#### Microsoft Teams
- **Environment Variables:** `ATOM_MICROSOFT_CLIENT_ID`, `ATOM_MICROSOFT_CLIENT_SECRET`, `ATOM_MICROSOFT_TENANT_ID`
- **Setup Instructions:**
  1. Go to [Azure Portal](https://portal.azure.com/) → Azure Active Directory
  2. Navigate to "App registrations" → "New registration"
  3. Name your app, select supported account types
  4. Add redirect URI: `http://localhost:3000/api/auth/callback/microsoft`
  5. Copy **Application (client) ID** and **Directory (tenant) ID**
  6. Navigate to "Certificates & secrets" → "New client secret"
  7. Copy the **Secret Value** immediately (shown only once)
  8. Navigate to "API permissions" → Add: `Team.ReadBasic.All`, `Channel.ReadBasic.All`, `Chat.ReadWrite`
  9. Enable "Allow public client flows" under "Authentication"

#### WhatsApp Business
- **Environment Variables:** `ATOM_WHATSAPP_PHONE_NUMBER_ID`, `ATOM_WHATSAPP_ACCESS_TOKEN`
- **Setup Instructions:**
  1. Go to [Meta for Developers](https://developers.facebook.com/)
  2. Create a new app → Select "Business" type
  3. Add "WhatsApp" product to your app
  4. Navigate to WhatsApp → "API Setup"
  5. Copy **Phone Number ID** and **Access Token**
  6. Configure webhook URL: `https://yourdomain.com/api/webhooks/whatsapp`
  7. Note: Requires Business verification for production use

#### Telegram
- **Environment Variables:** `ATOM_TELEGRAM_BOT_TOKEN`, `ATOM_TELEGRAM_API_ID`, `ATOM_TELEGRAM_API_HASH`
- **Setup Instructions:**
  1. Open Telegram and search for [@BotFather](https://t.me/botfather)
  2. Send `/newbot` command
  3. Follow prompts to name your bot
  4. Copy the **Bot Token** provided
  5. For API credentials: Go to [my.telegram.org](https://my.telegram.org/)
  6. Login and navigate to "API development tools"
  7. Create an application and copy **API ID** and **API Hash**

#### Google Chat
- **Environment Variables:** Uses `ATOM_GOOGLE_CLIENT_ID`, `ATOM_GOOGLE_CLIENT_SECRET`
- **Setup Instructions:**
  1. Go to [Google Cloud Console](https://console.cloud.google.com/)
  2. Create a new project or select existing
  3. Enable "Google Chat API" from API Library
  4. Navigate to "Credentials" → "Create Credentials" → "OAuth client ID"
  5. Application type: "Web application"
  6. Add redirect URI: `http://localhost:3000/api/auth/callback/google`
  7. Copy **Client ID** and **Client Secret**
  8. Configure OAuth consent screen with required scopes

#### Zoom
- **Environment Variables:** `ATOM_ZOOM_CLIENT_ID`, `ATOM_ZOOM_CLIENT_SECRET`, `ATOM_ZOOM_ACCOUNT_ID`
- **Setup Instructions:**
  1. Go to [Zoom App Marketplace](https://marketplace.zoom.us/)
  2. Click "Develop" → "Build App"
  3. Choose "Server-to-Server OAuth" app type
  4. Fill in app information
  5. Copy **Account ID**, **Client ID**, and **Client Secret**
  6. Add required scopes: `meeting:write`, `meeting:read`, `user:read`
  7. Activate the app

### Project Management (15 Services)

#### Asana
- **Environment Variables:** `ATOM_ASANA_CLIENT_ID`, `ATOM_ASANA_CLIENT_SECRET`
- **Setup Instructions:**
  1. Go to [Asana Developer Console](https://app.asana.com/0/developer-console)
  2. Click "Create new app"
  3. Fill in app name and description
  4. Copy **Client ID** and **Client Secret**
  5. Add redirect URL: `http://localhost:3000/api/auth/callback/asana`
  6. Request required scopes during OAuth flow

#### Jira
- **Environment Variables:** `ATOM_JIRA_CLIENT_ID`, `ATOM_JIRA_CLIENT_SECRET`
- **Setup Instructions:**
  1. Go to [Atlassian Developer Console](https://developer.atlassian.com/console/myapps/)
  2. Click "Create" → "OAuth 2.0 integration"
  3. Name your app and add redirect URL: `http://localhost:3000/api/auth/callback/jira`
  4. Copy **Client ID** and **Client Secret**
  5 Navigate to "Permissions" → Add scopes: `read:jira-work`, `write:jira-work`
  6. Distribute app to your Jira site

#### Monday.com
- **Environment Variables:** `ATOM_MONDAY_API_KEY`
- **Setup Instructions:**
  1. Go to [Monday.com](https://monday.com/) and login
  2. Click your avatar → "Developers"
  3. Click "My Access Tokens" → "Generate"
  4. Name your token and select required scopes
  5. Copy the **API Token** (shown only once)
  6. Alternatively, use OAuth: [Monday Apps](https://monday.com/developers/apps)

#### Notion
- **Environment Variables:** `ATOM_NOTION_API_KEY`, `ATOM_NOTION_CLIENT_ID`, `ATOM_NOTION_CLIENT_SECRET`
- **Setup Instructions:**
  1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
  2. Click "New integration"
  3. Name your integration and select associated workspace
  4. Copy the **Internal Integration Token** (for `ATOM_NOTION_API_KEY`)
  5. For OAuth: Go to "Distribution" → Enable "Public integration"
  6. Copy **OAuth Client ID** and **OAuth Client Secret**
  7. Add redirect URI: `http://localhost:3000/api/auth/callback/notion`

#### Linear
- **Environment Variables:** `ATOM_LINEAR_API_KEY`
- **Setup Instructions:**
  1. Go to [Linear Settings](https://linear.app/settings/api)
  2. Scroll to "Personal API keys"
  3. Click "Create key"
  4. Name your key and copy the **API Key** (shown only once)
  5. For OAuth: Create an OAuth application in settings
  6. Copy Client ID and Client Secret

#### Trello
- **Environment Variables:** `ATOM_TRELLO_API_KEY`, `ATOM_TRELLO_TOKEN`
- **Setup Instructions:**
  1. Go to [Trello Power-Ups Admin](https://trello.com/power-ups/admin)
  2. Click "New" → "Create Power-Up"
  3. Fill in required information
  4. Navigate to "API Key" section
  5. Copy your **API Key**
  6. Click "Generate a Token" link to get **Token**
  7. Authorize the token for your account

### CRM (12 Services)

#### Salesforce
- **Environment Variables:** `ATOM_SALESFORCE_CLIENT_ID`, `ATOM_SALESFORCE_CLIENT_SECRET`
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
- **Environment Variables:** `ATOM_HUBSPOT_CLIENT_ID`, `ATOM_HUBSPOT_CLIENT_SECRET`
- **Setup Instructions:**
  1. Go to [HubSpot Developers](https://developers.hubspot.com/)
  2. Click "Create app" → Fill in app information
  3. Navigate to "Auth" tab
  4. Add redirect URL: `http://localhost:3000/api/auth/callback/hubspot`
  5. Select required scopes: `crm.objects.contacts.read`, `crm.objects.companies.read`, etc.
  6. Copy **Client ID** and **Client Secret** from Auth tab

#### Zendesk
- **Environment Variables:** `ATOM_ZENDESK_CLIENT_ID`, `ATOM_ZENDESK_CLIENT_SECRET`, `ATOM_ZENDESK_SUBDOMAIN`
- **Setup Instructions:**
  1. Go to Zendesk Admin Center → Apps and integrations → APIs → OAuth Clients
  2. Click "Add OAuth client"
  3. Fill in client name and company
  4. Set redirect URL: `http://localhost:3000/api/auth/callback/zendesk`
  5. Copy **Client ID** (Unique Identifier) and **Secret**
  6. Note your Zendesk subdomain (e.g., `yourcompany` from `yourcompany.zendesk.com`)

#### Freshdesk
- **Environment Variables:** `ATOM_FRESHDESK_API_KEY`, `ATOM_FRESHDESK_DOMAIN`
- **Setup Instructions:**
  1. Login to your Freshdesk account
  2. Click on your profile picture → Profile settings
  3. Scroll to "API Key" section
  4. Copy your **API Key** (generate if not present)
  5. Note your Freshdesk domain (e.g., `yourcompany.freshdesk.com`)

#### Intercom
- **Environment Variables:** `ATOM_INTERCOM_CLIENT_ID`, `ATOM_INTERCOM_CLIENT_SECRET`
- **Setup Instructions:**
  1. Go to [Intercom Developer Hub](https://developers.intercom.com/)
  2. Click "Your apps" → "New app"
  3. Fill in app details and click "Create app"
  4. Navigate to "Authentication" in left sidebar
  5. Add redirect URL: `http://localhost:3000/api/auth/callback/intercom`
  6. Copy **Client ID** and **Client Secret**

### Development (9 Services)

#### GitHub
- **Environment Variables:** `ATOM_GITHUB_CLIENT_ID`, `ATOM_GITHUB_CLIENT_SECRET`, `ATOM_GITHUB_ACCESS_TOKEN`
- **Setup Instructions:**
  1. Go to [GitHub Settings](https://github.com/settings/developers) → "OAuth Apps"
  2. Click "New OAuth App"
  3. Fill in application name and homepage URL
  4. Set callback URL: `http://localhost:3000/api/auth/callback/github`
  5. Click "Register application"
  6. Copy **Client ID** and generate/copy **Client Secret**
  7. For Personal Access Token: Settings → Developer settings → Personal access tokens → Generate new token
  8. Select scopes: `repo`, `workflow`, `admin:org`

#### GitLab
- **Environment Variables:** `ATOM_GITLAB_CLIENT_ID`, `ATOM_GITLAB_CLIENT_SECRET`
- **Setup Instructions:**
  1. Go to [GitLab Applications](https://gitlab.com/-/profile/applications)
  2. Fill in application name
  3. Add redirect URI: `http://localhost:3000/api/auth/callback/gitlab`
  4. Select scopes: `api`, `read_repository`, `write_repository`
  5. Click "Save application"
  6. Copy **Application ID** (Client ID) and **Secret**

#### Bitbucket
- **Environment Variables:** `ATOM_BITBUCKET_CLIENT_ID`, `ATOM_BITBUCKET_CLIENT_SECRET`
- **Setup Instructions:**
  1. Go to [Bitbucket Settings](https://bitbucket.org/account/settings/oauth-consumers/new)
  2. Fill in OAuth consumer name
  3. Add callback URL: `http://localhost:3000/api/auth/callback/bitbucket`
  4. Select permissions: Repository (Read, Write), Account (Read)
  5. Click "Save"
  6. Copy **Key** (Client ID) and **Secret**

#### Figma
- **Environment Variables:** `ATOM_FIGMA_ACCESS_TOKEN`
- **Setup Instructions:**
  1. Go to [Figma Account Settings](https://www.figma.com/settings)
  2. Scroll to "Personal access tokens"
  3. Click "Generate new token"
  4. Name your token and copy the **Access Token** (shown only once)
  5. For OAuth apps: Use [Figma Developer Platform](https://www.figma.com/developers/api)

### Storage (8 Services)

#### Google Drive
- **Environment Variables:** `ATOM_GOOGLE_CLIENT_ID`, `ATOM_GOOGLE_CLIENT_SECRET`
- **Setup Instructions:**
  1. Go to [Google Cloud Console](https://console.cloud.google.com/)
  2. Create a new project or select existing
  3. Navigate to "APIs & Services" → "Library"
  4. Search and enable "Google Drive API"
  5. Go to "Credentials" → "Create Credentials" → "OAuth client ID"
  6. Configure OAuth consent screen if prompted
  7. Application type: "Web application"
  8. Add authorized redirect URI: `http://localhost:3000/api/auth/callback/google`
  9. Click "Create" and copy **Client ID** and **Client Secret**
  10. Download credentials JSON and save as `backend/credentials.json`

#### Dropbox
- **Environment Variables:** `ATOM_DROPBOX_CLIENT_ID`, `ATOM_DROPBOX_CLIENT_SECRET`
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

#### Box
- **Environment Variables:** `ATOM_BOX_CLIENT_ID`, `ATOM_BOX_CLIENT_SECRET`
- **Setup Instructions:**
  1. Go to [Box Developer Console](https://app.box.com/developers/console)
  2. Click "Create New App" → "Custom App"
  3. Choose "Standard OAuth 2.0 (User Authentication)"
  4. Name your app and click "Create App"
  5. Navigate to "Configuration" tab
  6. Copy **Client ID** and **Client Secret**
  7. Add redirect URI: `http://localhost:3000/api/auth/callback/box`
  8. Under "Application Scopes", select required permissions

#### OneDrive / Microsoft
- **Environment Variables:** Uses `ATOM_MICROSOFT_CLIENT_ID`, `ATOM_MICROSOFT_CLIENT_SECRET`
- **Setup Instructions:**
  1. Use the same Azure app created for Microsoft Teams (see Communication section)
  2. In Azure Portal, navigate to your app → "API permissions"
  3. Add Microsoft Graph permissions: `Files.ReadWrite`, `Files.ReadWrite.All`
  4. Grant admin consent for the permissions
  5. OneDrive will use the same credentials as Microsoft 365 services

### Email (8 Services)

#### Gmail
- **Environment Variables:** Uses `ATOM_GOOGLE_CLIENT_ID`, `ATOM_GOOGLE_CLIENT_SECRET`
- **Setup Instructions:**
  1. Use the same Google Cloud project as Google Drive
  2. Enable "Gmail API" from API Library
  3. Same OAuth credentials work for both Gmail and Drive
  4. Ensure OAuth consent screen includes Gmail scopes
  5. Required scopes: `https://www.googleapis.com/auth/gmail.readonly`, `https://www.googleapis.com/auth/gmail.send`

#### Outlook
- **Environment Variables:** Uses `ATOM_MICROSOFT_CLIENT_ID`, `ATOM_MICROSOFT_CLIENT_SECRET`
- **Setup Instructions:**
  1. Use the same Azure app as Microsoft Teams/OneDrive
  2. Add Microsoft Graph permissions: `Mail.ReadWrite`, `Mail.Send`
  3. Same credentials work across all Microsoft 365 services

#### Mailchimp
- **Environment Variables:** `ATOM_MAILCHIMP_API_KEY`, `ATOM_MAILCHIMP_SERVER_PREFIX`
- **Setup Instructions:**
  1. Login to [Mailchimp](https://mailchimp.com/)
  2. Navigate to Account → Extras → API keys
  3. Click "Create A Key"
  4. Copy the **API Key**
  5. Note your **Server Prefix** (e.g., `us1`, `us2`) from the API key or account settings

### Finance (6 Services)

#### Stripe
- **Environment Variables:** `ATOM_STRIPE_API_KEY`, `ATOM_STRIPE_PUBLISHABLE_KEY`, `ATOM_STRIPE_WEBHOOK_SECRET`
- **Setup Instructions:**
  1. Go to [Stripe Dashboard](https://dashboard.stripe.com/)
  2. Navigate to Developers → API keys
  3. Copy **Secret key** (starts with `sk_`) for `ATOM_STRIPE_API_KEY`
  4. Copy **Publishable key** (starts with `pk_`) for `ATOM_STRIPE_PUBLISHABLE_KEY`
  5. For webhooks: Developers → Webhooks → Add endpoint
  6. Set endpoint URL: `https://yourdomain.com/api/webhooks/stripe`
  7. Copy **Signing secret** for `ATOM_STRIPE_WEBHOOK_SECRET`

#### QuickBooks
- **Environment Variables:** `ATOM_QUICKBOOKS_CLIENT_ID`, `ATOM_QUICKBOOKS_CLIENT_SECRET`
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
- **Environment Variables:** `ATOM_XERO_CLIENT_ID`, `ATOM_XERO_CLIENT_SECRET`
- **Setup Instructions:**
  1. Go to [Xero Developer Portal](https://developer.xero.com/app/manage)
  2. Click "New app"
  3. Fill in app details
  4. Add OAuth 2.0 redirect URI: `http://localhost:3000/api/auth/callback/xero`
  5. Copy **Client ID** and **Client Secret**
  6. Generate and configure API scopes

#### Shopify
- **Environment Variables:** `ATOM_SHOPIFY_API_KEY`, `ATOM_SHOPIFY_API_SECRET`, `ATOM_SHOPIFY_SHOP_NAME`
- **Setup Instructions:**
  1. Go to [Shopify Partners](https://partners.shopify.com/)
  2. Navigate to Apps → Create app
  3. Choose app type: "Public app" or "Custom app"
  4. Fill in app details
  5. Copy **API key** and **API secret**
  6. Add redirect URL: `http://localhost:3000/api/auth/callback/shopify`
  7. Note your shop name (e.g., `mystore` from `mystore.myshopify.com`)

### Calendar (2 Services)

#### Google Calendar
- **Environment Variables:** Uses `ATOM_GOOGLE_CLIENT_ID`, `ATOM_GOOGLE_CLIENT_SECRET`
- **Setup Instructions:**
  1. Use same Google Cloud project as Drive/Gmail
  2. Enable "Google Calendar API" from API Library
  3. Same OAuth credentials work for all Google services
  4. Required scope: `https://www.googleapis.com/auth/calendar`
  5. Download credentials as `backend/credentials.json`

#### Outlook Calendar
- **Environment Variables:** Uses `ATOM_MICROSOFT_CLIENT_ID`, `ATOM_MICROSOFT_CLIENT_SECRET`
- **Setup Instructions:**
  1. Use same Azure app as Teams/Outlook
  2. Ensure `Calendars.ReadWrite` permission is added
  3. Same credentials work for all Microsoft 365 services

### Enterprise & Workflow Automation (5 Services)

| Service | Env Vars | Notes |
|---------|----------|-------|
| **Microsoft 365** | `ATOM_MICROSOFT_CLIENT_ID`, `ATOM_MICROSOFT_CLIENT_SECRET` | Unified suite covering Teams, Outlook, OneDrive, SharePoint |
| **Workflow Automation** | N/A | Internal ATOM service for workflow orchestration |
| **Enterprise Security** | N/A | Internal ATOM security service |
| **Enterprise Unified** | N/A | Internal ATOM enterprise service |

### AI & Voice (7 Services)

| Service | Env Vars | Notes |
|---------|----------|-------|
| **AI Enhanced Service** | Uses `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` | Leverages configured AI providers |
| **Voice AI Service** | Uses configured AI services | Text-to-speech and speech-to-text |
| **Video AI Service** | Uses configured AI services | Video processing and analysis |

### Industry Customizations (3 Services)

| Service | Env Vars | Notes |
|---------|----------|-------|
| **Healthcare Customization** | N/A | HIPAA-compliant workflows |
| **Education Customization** | N/A | FERPA-compliant workflows |
| **Finance Customization** | N/A | SOX-compliant workflows |

### Other Services (8)

| Service | Env Vars | Setup Guide |
|---------|----------|-------------|
| **Airtable** | `ATOM_AIRTABLE_API_KEY` | Airtable Account > API Documentation |
| **Tableau** | `ATOM_TABLEAU_CLIENT_ID`, `ATOM_TABLEAU_CLIENT_SECRET` | [Tableau Developer](https://developer.tableau.com/) |

## 6. Feature Flags

| Variable | Description | Default |
|----------|-------------|---------|
| `ENABLE_OAUTH` | Enable OAuth flows | `true` |
| `ENABLE_WORKFLOWS` | Enable background workflows | `true` |
| `ENABLE_VOICE` | Enable voice capabilities | `false` |

## 7. Setup Checklist

1. [ ] Set `OPENAI_API_KEY` (Critical for basic functionality)
2. [ ] Set `ATOM_ENCRYPTION_KEY` (Critical for token storage)
3. [ ] Configure `LANCEDB_PATH` if using local vector search
4. [ ] Add integration credentials as needed for features you are testing
5. [ ] For Google services, ensure `backend/credentials.json` is present
6. [ ] For Microsoft services, enable "Allow public client flows" in Azure Portal

## 8. Quick Reference: Integration Count by Category

- Communication: 34 services
- Project Management: 15 services
- CRM: 12 services
- Development: 9 services
- Email: 8 services
- Storage: 8 services
- Other: 8 services
- AI: 7 services
- Finance: 6 services
- Enterprise: 5 services
- Industry: 3 services
- Calendar: 2 services

**Total: 117 integrations**
