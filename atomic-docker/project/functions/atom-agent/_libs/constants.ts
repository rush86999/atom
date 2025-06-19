// ================================================================================================
// Atom Agent Constants
// ================================================================================================

// IMPORTANT ASSUMPTIONS FOR GOOGLE CALENDAR INTEGRATION:
// 1. The following environment variables MUST be configured in the application's deployment environment:
//    - ATOM_GOOGLE_CALENDAR_CLIENT_ID: The Client ID obtained from Google Cloud Console for OAuth 2.0.
//    - ATOM_GOOGLE_CALENDAR_CLIENT_SECRET: The Client Secret obtained from Google Cloud Console.
//    - ATOM_GOOGLE_CALENDAR_REDIRECT_URI: The Redirect URI configured in Google Cloud Console.
//      This URI must point to an endpoint in this application responsible for handling the
//      OAuth 2.0 callback (e.g., /api/atom/auth/calendar/callback).
// 2. The Google Calendar API MUST be enabled for the project in the Google Cloud Console.
// ================================================================================================

// Google Calendar API credentials for Atom Agent
// These must be set in the environment.
export const ATOM_GOOGLE_CALENDAR_CLIENT_ID = process.env.ATOM_GOOGLE_CALENDAR_CLIENT_ID;
export const ATOM_GOOGLE_CALENDAR_CLIENT_SECRET = process.env.ATOM_GOOGLE_CALENDAR_CLIENT_SECRET;

// The redirect URI configured in Google Cloud Console for Atom Agent's calendar OAuth.
// This should point to a backend endpoint that will handle the OAuth callback.
// e.g., https://<your-app-domain>/api/atom/auth/calendar/callback
export const ATOM_GOOGLE_CALENDAR_REDIRECT_URI = process.env.ATOM_GOOGLE_CALENDAR_REDIRECT_URI;

export const GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token';
export const GOOGLE_CALENDAR_API_SCOPE = 'https://www.googleapis.com/auth/calendar';

// Potentially other constants for Atom agent can be added below
// e.g., API keys for email services, Zapier specific URLs (if not user-configured), etc.

// HubSpot API Key
// This must be set in the environment.
export const ATOM_HUBSPOT_API_KEY = process.env.ATOM_HUBSPOT_API_KEY || '';

// Slack Bot Token
// This must be set in the environment.
export const ATOM_SLACK_BOT_TOKEN = process.env.ATOM_SLACK_BOT_TOKEN || '';

// Slack Channel ID for HubSpot Notifications
// This must be set in the environment if Slack notifications for HubSpot actions are desired.
export const ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID = process.env.ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID || '';

// Default Slack Channel ID for "My Agenda" notifications, if user-specific DM is not used/available.
// Can be overridden by environment variable.
export const ATOM_DEFAULT_SLACK_CHANNEL_FOR_AGENDA = process.env.ATOM_DEFAULT_SLACK_CHANNEL_FOR_AGENDA || '';

// HubSpot Portal ID
// This must be set in the environment if generating direct links to HubSpot records (e.g., in Slack notifications).
export const ATOM_HUBSPOT_PORTAL_ID = process.env.ATOM_HUBSPOT_PORTAL_ID || '';

// Calendly Personal Access Token
// This must be set in the environment for Calendly integration.
export const ATOM_CALENDLY_PERSONAL_ACCESS_TOKEN = process.env.ATOM_CALENDLY_PERSONAL_ACCESS_TOKEN || '';

// Zoom Credentials for Server-to-Server OAuth
// These must be set in the environment for Zoom integration.
export const ATOM_ZOOM_ACCOUNT_ID = process.env.ATOM_ZOOM_ACCOUNT_ID || '';
export const ATOM_ZOOM_CLIENT_ID = process.env.ATOM_ZOOM_CLIENT_ID || '';
export const ATOM_ZOOM_CLIENT_SECRET = process.env.ATOM_ZOOM_CLIENT_SECRET || '';

// Microsoft Graph API Credentials for MS Teams Integration
// These must be set in the environment for MS Teams/Graph integration.
export const ATOM_MSGRAPH_CLIENT_ID = process.env.ATOM_MSGRAPH_CLIENT_ID || '';
export const ATOM_MSGRAPH_CLIENT_SECRET = process.env.ATOM_MSGRAPH_CLIENT_SECRET || '';
export const ATOM_MSGRAPH_TENANT_ID = process.env.ATOM_MSGRAPH_TENANT_ID || '';
// Authority is usually constructed as https://login.microsoftonline.com/<TENANT_ID>
export const ATOM_MSGRAPH_AUTHORITY = `https://login.microsoftonline.com/${process.env.ATOM_MSGRAPH_TENANT_ID || 'common'}`;
// Define necessary scopes for MS Graph API calls (e.g., reading calendar events, online meetings)
export const ATOM_MSGRAPH_SCOPES = (process.env.ATOM_MSGRAPH_SCOPES || 'https://graph.microsoft.com/.default').split(',');

// Stripe Secret Key
// This must be set in the environment for Stripe integration.
export const ATOM_STRIPE_SECRET_KEY = process.env.ATOM_STRIPE_SECRET_KEY || '';

// QuickBooks Online (QBO) Credentials and Settings
// These must be set in the environment for QBO integration.
export const ATOM_QB_CLIENT_ID = process.env.ATOM_QB_CLIENT_ID || '';
export const ATOM_QB_CLIENT_SECRET = process.env.ATOM_QB_CLIENT_SECRET || '';
export const ATOM_QB_ENVIRONMENT = (process.env.ATOM_QB_ENVIRONMENT || 'sandbox') as 'sandbox' | 'production';
export const ATOM_QB_REDIRECT_URI = process.env.ATOM_QB_REDIRECT_URI || '';
// Path to a file where QBO tokens (access token, refresh token, realmId, expiry) will be stored.
// Ensure this path is writable by the application and secure.
// For serverless functions, this might need to be a location like /tmp/ or a database.
export const ATOM_QB_TOKEN_FILE_PATH = process.env.ATOM_QB_TOKEN_FILE_PATH || './qb_tokens.json';
// Scopes: com.intuit.quickbooks.accounting (for accounting tasks)
// Other scopes like com.intuit.quickbooks.payment may be needed for payments.
// openid profile email phone address are for user info.
export const ATOM_QB_SCOPES = (process.env.ATOM_QB_SCOPES || 'com.intuit.quickbooks.accounting openid profile email phone address').split(' ');

// OpenAI API Key for NLU Service
// This must be set in the environment for Natural Language Understanding capabilities.
export const ATOM_OPENAI_API_KEY = process.env.ATOM_OPENAI_API_KEY || '';

// OpenAI Model Name for NLU
// Specifies the model to be used for NLU tasks, preferably one that supports JSON mode.
export const ATOM_NLU_MODEL_NAME = process.env.ATOM_NLU_MODEL_NAME || 'gpt-3.5-turbo-1106';

// Hasura GraphQL Endpoint Configuration
// These must be set in the environment for GraphQL communication.
export const HASURA_GRAPHQL_URL = process.env.HASURA_GRAPHQL_URL || '';
export const HASURA_ADMIN_SECRET = process.env.HASURA_ADMIN_SECRET || '';

// SerpApi API Key for Web Search
// This must be set in the environment for real web search capabilities.
export const ATOM_SERPAPI_API_KEY = process.env.ATOM_SERPAPI_API_KEY || '';

// Notion API Token and Database IDs
// These must be set for Notion integration (note-taking, research agent).
export const NOTION_API_TOKEN = process.env.NOTION_API_TOKEN || '';
export const NOTION_NOTES_DATABASE_ID = process.env.NOTION_NOTES_DATABASE_ID || ''; // General notes
export const NOTION_RESEARCH_PROJECTS_DB_ID = process.env.NOTION_RESEARCH_PROJECTS_DB_ID || '';
export const NOTION_RESEARCH_TASKS_DB_ID = process.env.NOTION_RESEARCH_TASKS_DB_ID || '';

// Deepgram API Key for Transcription
// This must be set for audio transcription features.
export const DEEPGRAM_API_KEY = process.env.DEEPGRAM_API_KEY || '';

// Python API Service URLs
// Base URLs for the Python Flask services that handle research and note-taking logic.
// Example for local development: http://localhost:5056
export const PYTHON_RESEARCH_API_URL = process.env.PYTHON_RESEARCH_API_URL || '';
// Example for local development: http://localhost:5057
export const PYTHON_NOTE_API_URL = process.env.PYTHON_NOTE_API_URL || '';
