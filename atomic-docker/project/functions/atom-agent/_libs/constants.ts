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


// Potentially other constants for Atom agent can be added below
// e.g., API keys for email services, Zapier specific URLs (if not user-configured), etc.
