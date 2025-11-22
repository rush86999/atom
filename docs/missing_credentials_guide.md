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

| Service | Env Vars | Setup Guide |
|---------|----------|-------------|
| **Slack** | `ATOM_SLACK_CLIENT_ID`, `ATOM_SLACK_CLIENT_SECRET`, `ATOM_SLACK_BOT_TOKEN`, `ATOM_SLACK_SIGNING_SECRET` | [Slack API](https://api.slack.com/apps) - Enable Socket Mode, add scopes: `channels:read`, `chat:write` |
| **Discord** | `ATOM_DISCORD_CLIENT_ID`, `ATOM_DISCORD_CLIENT_SECRET`, `ATOM_DISCORD_BOT_TOKEN` | [Discord Developer Portal](https://discord.com/developers/applications) |
| **Microsoft Teams** | `ATOM_MICROSOFT_CLIENT_ID`, `ATOM_MICROSOFT_CLIENT_SECRET`, `ATOM_MICROSOFT_TENANT_ID` | [Azure Portal](https://portal.azure.com/) - Register app with Teams permissions |
| **WhatsApp Business** | `ATOM_WHATSAPP_PHONE_NUMBER_ID`, `ATOM_WHATSAPP_ACCESS_TOKEN` | [Meta Business](https://business.facebook.com/) - WhatsApp Business API |
| **Telegram** | `ATOM_TELEGRAM_BOT_TOKEN`, `ATOM_TELEGRAM_API_ID`, `ATOM_TELEGRAM_API_HASH` | [Telegram BotFather](https://t.me/botfather) |
| **Google Chat** | `ATOM_GOOGLE_CLIENT_ID`, `ATOM_GOOGLE_CLIENT_SECRET` | [Google Cloud Console](https://console.cloud.google.com/) - Enable Chat API |
| **Zoom** | `ATOM_ZOOM_CLIENT_ID`, `ATOM_ZOOM_CLIENT_SECRET` | [Zoom Marketplace](https://marketplace.zoom.us/) - Create Server-to-Server OAuth app |

### Project Management (15 Services)

| Service | Env Vars | Setup Guide |
|---------|----------|-------------|
| **Asana** | `ATOM_ASANA_CLIENT_ID`, `ATOM_ASANA_CLIENT_SECRET` | [Asana Developer Console](https://app.asana.com/0/developer-console) |
| **Jira** | `ATOM_JIRA_CLIENT_ID`, `ATOM_JIRA_CLIENT_SECRET` | [Atlassian Developer Console](https://developer.atlassian.com/console/myapps/) |
| **Monday.com** | `ATOM_MONDAY_API_KEY` | [Monday.com Apps](https://monday.com/developers/v2) |
| **Notion** | `ATOM_NOTION_API_KEY`, `ATOM_NOTION_CLIENT_ID`, `ATOM_NOTION_CLIENT_SECRET` | [Notion Integrations](https://www.notion.so/my-integrations) |
| **Linear** | `ATOM_LINEAR_API_KEY` | [Linear Settings](https://linear.app/settings/api) |
| **Trello** | `ATOM_TRELLO_API_KEY`, `ATOM_TRELLO_TOKEN` | [Trello Power-Ups](https://trello.com/power-ups/admin) |

### CRM (12 Services)

| Service | Env Vars | Setup Guide |
|---------|----------|-------------|
| **Salesforce** | `ATOM_SALESFORCE_CLIENT_ID`, `ATOM_SALESFORCE_CLIENT_SECRET` | Salesforce Setup > App Manager > New Connected App |
| **HubSpot** | `ATOM_HUBSPOT_CLIENT_ID`, `ATOM_HUBSPOT_CLIENT_SECRET` | [HubSpot Developers](https://developers.hubspot.com/) |
| **Zendesk** | `ATOM_ZENDESK_CLIENT_ID`, `ATOM_ZENDESK_CLIENT_SECRET`, `ATOM_ZENDESK_SUBDOMAIN` | [Zendesk Admin](https://www.zendesk.com/developer/) |
| **Freshdesk** | `ATOM_FRESHDESK_API_KEY`, `ATOM_FRESHDESK_DOMAIN` | Freshdesk Profile > API Key |
| **Intercom** | `ATOM_INTERCOM_CLIENT_ID`, `ATOM_INTERCOM_CLIENT_SECRET` | [Intercom Developers](https://developers.intercom.com/) |

### Development (9 Services)

| Service | Env Vars | Setup Guide |
|---------|----------|-------------|
| **GitHub** | `ATOM_GITHUB_CLIENT_ID`, `ATOM_GITHUB_CLIENT_SECRET`, `ATOM_GITHUB_ACCESS_TOKEN` | [GitHub Developer Settings](https://github.com/settings/developers) |
| **GitLab** | `ATOM_GITLAB_CLIENT_ID`, `ATOM_GITLAB_CLIENT_SECRET` | [GitLab Applications](https://gitlab.com/-/profile/applications) |
| **Bitbucket** | `ATOM_BITBUCKET_CLIENT_ID`, `ATOM_BITBUCKET_CLIENT_SECRET` | [Bitbucket OAuth](https://support.atlassian.com/bitbucket-cloud/docs/use-oauth-on-bitbucket-cloud/) |
| **Figma** | `ATOM_FIGMA_ACCESS_TOKEN` | Figma Account Settings > Personal Access Tokens |

### Storage (8 Services)

| Service | Env Vars | Setup Guide |
|---------|----------|-------------|
| **Google Drive** | `ATOM_GOOGLE_CLIENT_ID`, `ATOM_GOOGLE_CLIENT_SECRET` | [Google Cloud Console](https://console.cloud.google.com/) - Enable Drive API |
| **Dropbox** | `ATOM_DROPBOX_CLIENT_ID`, `ATOM_DROPBOX_CLIENT_SECRET` | [Dropbox App Console](https://www.dropbox.com/developers/apps) |
| **Box** | `ATOM_BOX_CLIENT_ID`, `ATOM_BOX_CLIENT_SECRET` | [Box Developers](https://developer.box.com/) |
| **OneDrive** | `ATOM_MICROSOFT_CLIENT_ID`, `ATOM_MICROSOFT_CLIENT_SECRET` | [Azure Portal](https://portal.azure.com/) - Register app with Files.ReadWrite scope |

### Email (8 Services)

| Service | Env Vars | Setup Guide |
|---------|----------|-------------|
| **Gmail** | `ATOM_GOOGLE_CLIENT_ID`, `ATOM_GOOGLE_CLIENT_SECRET` | [Google Cloud Console](https://console.cloud.google.com/) - Enable Gmail API |
| **Outlook** | `ATOM_MICROSOFT_CLIENT_ID`, `ATOM_MICROSOFT_CLIENT_SECRET` | [Azure Portal](https://portal.azure.com/) - Add Mail.ReadWrite scope |
| **Mailchimp** | `ATOM_MAILCHIMP_API_KEY`, `ATOM_MAILCHIMP_SERVER_PREFIX` | Mailchimp Account > Extras > API Keys |

### Finance (6 Services)

| Service | Env Vars | Setup Guide |
|---------|----------|-------------|
| **Stripe** | `ATOM_STRIPE_API_KEY`, `ATOM_STRIPE_WEBHOOK_SECRET` | [Stripe Dashboard](https://dashboard.stripe.com/apikeys) |
| **QuickBooks** | `ATOM_QUICKBOOKS_CLIENT_ID`, `ATOM_QUICKBOOKS_CLIENT_SECRET` | [Intuit Developers](https://developer.intuit.com/) |
| **Xero** | `ATOM_XERO_CLIENT_ID`, `ATOM_XERO_CLIENT_SECRET` | [Xero Developer](https://developer.xero.com/app/manage) |
| **Shopify** | `ATOM_SHOPIFY_API_KEY`, `ATOM_SHOPIFY_API_SECRET`, `ATOM_SHOPIFY_SHOP_NAME` | [Shopify Partners](https://partners.shopify.com/) |

### Calendar (2 Services)

| Service | Env Vars | Setup Guide |
|---------|----------|-------------|
| **Google Calendar** | `ATOM_GOOGLE_CLIENT_ID`, `ATOM_GOOGLE_CLIENT_SECRET` | [Google Cloud Console](https://console.cloud.google.com/) - Enable Calendar API. Requires `backend/credentials.json` file |
| **Outlook Calendar** | `ATOM_MICROSOFT_CLIENT_ID`, `ATOM_MICROSOFT_CLIENT_SECRET` | [Azure Portal](https://portal.azure.com/) - Add Calendars.ReadWrite scope |

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
