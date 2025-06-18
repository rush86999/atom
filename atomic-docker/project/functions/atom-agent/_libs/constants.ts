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

// Hasura Connection (ensure these are set in your environment)
export const HASURA_GRAPHQL_URL = process.env.HASURA_GRAPHQL_URL; // Or specific e.g. process.env.HASURA_GRAPHQL_GRAPHQL_URL
export const HASURA_ADMIN_SECRET = process.env.HASURA_GRAPHQL_ADMIN_SECRET;

// Atom Agent Specific Identifiers for Token Storage
export const ATOM_CALENDAR_RESOURCE_NAME = 'google_atom_calendar';
export const ATOM_CLIENT_TYPE = 'atom_agent';

// Encryption key and IV for Atom agent's sensitive token storage
// MUST be set in the environment. Key should be 32 bytes (256 bits) for aes-256-cbc, IV should be 16 bytes (128 bits).
// Generate these securely (e.g., using crypto.randomBytes(32).toString('hex') and crypto.randomBytes(16).toString('hex'))
export const ATOM_TOKEN_ENCRYPTION_KEY = process.env.ATOM_TOKEN_ENCRYPTION_KEY;
export const ATOM_TOKEN_ENCRYPTION_IV = process.env.ATOM_TOKEN_ENCRYPTION_IV;

// ================================================================================================
// Atom Agent Gmail API Integration Constants
// ================================================================================================
// IMPORTANT ASSUMPTIONS FOR GMAIL INTEGRATION:
// 1. The following environment variables MUST be configured in the application's deployment environment:
//    - ATOM_GMAIL_CLIENT_ID: The Client ID obtained from Google Cloud Console for OAuth 2.0.
//    - ATOM_GMAIL_CLIENT_SECRET: The Client Secret obtained from Google Cloud Console.
//    - ATOM_GMAIL_REDIRECT_URI: The Redirect URI configured in Google Cloud Console for Gmail.
//      This URI must point to an endpoint like /api/atom/auth/email/callback.
// 2. The Gmail API MUST be enabled for the project in the Google Cloud Console.
// ================================================================================================

// Gmail API credentials for Atom Agent
// These must be set in the environment.
export const ATOM_GMAIL_CLIENT_ID = process.env.ATOM_GMAIL_CLIENT_ID;
export const ATOM_GMAIL_CLIENT_SECRET = process.env.ATOM_GMAIL_CLIENT_SECRET;

// The redirect URI configured in Google Cloud Console for Atom Agent's Gmail OAuth.
// This should point to a backend endpoint that will handle the OAuth callback for email.
// e.g., https://<your-app-domain>/api/atom/auth/email/callback
export const ATOM_GMAIL_REDIRECT_URI = process.env.ATOM_GMAIL_REDIRECT_URI;

// Define Gmail API Scopes
// Using a versatile set for reading, sending, and modifying emails.
export const GMAIL_API_SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.modify' // Allows reading, sending, labeling, archiving, etc.
];
export const ATOM_GMAIL_RESOURCE_NAME = 'google_atom_gmail';

// ================================================================================================
// Atom Agent Microsoft Graph API Integration Constants
// ================================================================================================
// IMPORTANT ASSUMPTIONS FOR MICROSOFT GRAPH INTEGRATION:
// 1. An application must be registered in Azure Active Directory (Azure AD) to obtain credentials.
// 2. The following environment variables MUST be configured in the application's deployment environment:
//    - ATOM_MSGRAPH_CLIENT_ID: The Application (client) ID from Azure AD.
//    - ATOM_MSGRAPH_CLIENT_SECRET: The Client Secret generated in Azure AD.
//    - ATOM_MSGRAPH_REDIRECT_URI: The Redirect URI configured in Azure AD.
//      This URI must point to an endpoint like /api/atom/auth/microsoft/callback.
//    - ATOM_MSGRAPH_TENANT_ID: (Optional, defaults to 'common') The Azure AD tenant ID.
//      'common' allows multi-tenant and personal Microsoft accounts.
//      Use a specific tenant ID to restrict to a single organization.
// 3. The required API permissions (scopes) MUST be configured in the Azure AD app registration
//    and consented to by a user or admin.
// ================================================================================================

// Microsoft Graph API credentials for Atom Agent
// These must be set in the environment after registering the application in Azure AD.
export const ATOM_MSGRAPH_CLIENT_ID = process.env.ATOM_MSGRAPH_CLIENT_ID;
export const ATOM_MSGRAPH_CLIENT_SECRET = process.env.ATOM_MSGRAPH_CLIENT_SECRET;

// The redirect URI configured in Azure AD for Atom Agent's Microsoft Graph OAuth.
// e.g., https://<your-app-domain>/api/atom/auth/microsoft/callback
export const ATOM_MSGRAPH_REDIRECT_URI = process.env.ATOM_MSGRAPH_REDIRECT_URI;

// Tenant ID for Microsoft Graph OAuth. Usually 'common' for multi-tenant applications
// allowing users from any organization or personal Microsoft accounts.
// Can be a specific tenant ID if restricted.
export const ATOM_MSGRAPH_TENANT_ID = process.env.ATOM_MSGRAPH_TENANT_ID || 'common';

// Define Microsoft Graph API Scopes
// Note: offline_access is critical for getting refresh tokens.
// User.Read is needed to get user's email address and basic profile.
export const MSGRAPH_API_SCOPES = [
    'User.Read',            // Read user's profile
    'Calendars.ReadWrite',  // Full access to calendars
    'Mail.ReadWrite',       // Full access to mail (read, write, delete, move)
    'Mail.Send',            // Permission to send mail
    'offline_access'        // Required to get refresh tokens for long-term access
];

// Microsoft Graph OAuth Endpoints are typically constructed dynamically by MSAL.
// Example authority URL:
// export const MSGRAPH_AUTHORITY = `https://login.microsoftonline.com/${ATOM_MSGRAPH_TENANT_ID}`;
export const ATOM_MSGRAPH_RESOURCE_NAME = 'microsoft_graph';

// Microsoft Graph OAuth Endpoints base
export const MSGRAPH_OAUTH_AUTHORITY_BASE = 'https://login.microsoftonline.com/';

// ================================================================================================
// Atom Agent SerpApi (Web Search) Integration Constants
// ================================================================================================
// IMPORTANT ASSUMPTIONS FOR SERPAPI INTEGRATION:
// 1. An API key must be obtained from SerpApi (https://serpapi.com).
// 2. The following environment variable MUST be configured in the application's deployment environment:
//    - ATOM_SERPAPI_API_KEY: The API key from SerpApi.
// ================================================================================================

// SerpApi Web Search API credentials for Atom Agent
// This must be set in the environment.
export const ATOM_SERPAPI_API_KEY = process.env.ATOM_SERPAPI_API_KEY;

// SerpApi base URL
export const SERPAPI_BASE_URL = 'https://serpapi.com/search';
// Default search engine can be 'google', can be specified in params.


// Potentially other constants for Atom agent can be added below
// e.g., API keys for other email services, Zapier specific URLs (if not user-configured), etc.
