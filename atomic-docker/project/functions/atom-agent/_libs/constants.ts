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

// HubSpot Portal ID
// This must be set in the environment if generating direct links to HubSpot records (e.g., in Slack notifications).
export const ATOM_HUBSPOT_PORTAL_ID = process.env.ATOM_HUBSPOT_PORTAL_ID || '';

// Calendly Personal Access Token
// This must be set in the environment for Calendly integration.
export const ATOM_CALENDLY_PERSONAL_ACCESS_TOKEN = process.env.ATOM_CALENDLY_PERSONAL_ACCESS_TOKEN || '';
