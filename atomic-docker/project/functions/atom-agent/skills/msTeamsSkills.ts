import axios, { AxiosError } from 'axios';
import {
  ConfidentialClientApplication,
  Configuration,
  AuthenticationResult,
  LogLevel,
} from '@azure/msal-node';
import {
  ATOM_MSGRAPH_CLIENT_ID,
  ATOM_MSGRAPH_CLIENT_SECRET,
  ATOM_MSGRAPH_TENANT_ID,
  ATOM_MSGRAPH_AUTHORITY,
  ATOM_MSGRAPH_SCOPES,
} from '../_libs/constants';
import {
  MSGraphEvent,
  ListMSTeamsMeetingsResponse,
  GetMSTeamsMeetingDetailsResponse,
  // MSGraphTokenResponse is implicitly handled by AuthenticationResult from msal-node
} from '../types';

const MSGRAPH_API_BASE_URL = 'https://graph.microsoft.com/v1.0';

let msalClientApp: ConfidentialClientApplication | null = null;
let msGraphAccessToken: { token: string; expiresOnTimestamp: number } | null = null;

// Export for testing token cache reset
export const resetMSGraphTokenCache = () => {
  msGraphAccessToken = null;
  // msalClientApp is not reset here as its configuration is static based on constants
};


function getMsalClient(): ConfidentialClientApplication | null {
  if (msalClientApp) {
    return msalClientApp;
  }

  if (!ATOM_MSGRAPH_CLIENT_ID || !ATOM_MSGRAPH_AUTHORITY || !ATOM_MSGRAPH_CLIENT_SECRET) {
    console.error('MS Graph API client credentials (Client ID, Authority, Client Secret) not configured.');
    return null;
  }

  const msalConfig: Configuration = {
    auth: {
      clientId: ATOM_MSGRAPH_CLIENT_ID,
      authority: ATOM_MSGRAPH_AUTHORITY, // e.g., https://login.microsoftonline.com/YOUR_TENANT_ID
      clientSecret: ATOM_MSGRAPH_CLIENT_SECRET,
    },
    system: {
      loggerOptions: { // Optional: Configure logging for MSAL
        loggerCallback(loglevel, message, containsPii) {
          // console.log(`MSAL Log (Level ${loglevel}): ${message}`);
        },
        piiLoggingEnabled: false,
        logLevel: LogLevel.Warning, // Adjust as needed: Error, Warning, Info, Verbose, Trace
      },
    },
  };
  msalClientApp = new ConfidentialClientApplication(msalConfig);
  return msalClientApp;
}

async function getMSGraphToken(): Promise<string | null> {
  if (msGraphAccessToken && Date.now() < msGraphAccessToken.expiresOnTimestamp) {
    return msGraphAccessToken.token;
  }

  const clientApp = getMsalClient();
  if (!clientApp) {
    console.error('MSAL client application could not be initialized.');
    return null;
  }

  if (!ATOM_MSGRAPH_SCOPES || ATOM_MSGRAPH_SCOPES.length === 0) {
      console.error('MS Graph API scopes are not configured.');
      return null;
  }

  const tokenRequest = {
    scopes: ATOM_MSGRAPH_SCOPES, // e.g., ['https://graph.microsoft.com/.default']
  };

  try {
    const response: AuthenticationResult | null = await clientApp.acquireTokenByClientCredential(tokenRequest);
    if (response && response.accessToken && response.expiresOn) {
      // Store the token and its expiry time (with a 5-minute buffer)
      msGraphAccessToken = {
        token: response.accessToken,
        expiresOnTimestamp: response.expiresOn.getTime() - 300000, // 5 minutes buffer
      };
      console.log('Successfully obtained new MS Graph access token.');
      return response.accessToken;
    } else {
      console.error('Failed to acquire MS Graph token. Response was null or invalid.');
      msGraphAccessToken = null;
      return null;
    }
  } catch (error) {
    console.error('Error acquiring MS Graph token by client credential:', error);
    msGraphAccessToken = null;
    return null;
  }
}

export async function listMicrosoftTeamsMeetings(
  userPrincipalNameOrId: string, // e.g., "me" or "user@example.com" or user's object ID
  options?: {
    limit?: number;
    nextLink?: string; // For pagination using @odata.nextLink
    filterForTeams?: boolean; // Default true, to filter for actual Teams meetings
    // Additional filters like date ranges can be added via OData $filter query if needed
    // e.g., filter?: "start/dateTime ge '2024-03-01T00:00:00Z' and end/dateTime le '2024-03-31T23:59:59Z'"
  }
): Promise<ListMSTeamsMeetingsResponse> {
  console.log(`listMicrosoftTeamsMeetings called for user: ${userPrincipalNameOrId}, options:`, options);
  const token = await getMSGraphToken();
  if (!token) {
    return { ok: false, error: 'Failed to obtain MS Graph access token.' };
  }

  let requestUrl = options?.nextLink; // Use nextLink directly if provided for pagination

  if (!requestUrl) {
    const selectParams = 'id,subject,start,end,isOnlineMeeting,onlineMeeting,webLink,bodyPreview';
    const orderByParams = 'start/dateTime ASC';
    const topParams = options?.limit || 10;

    let filterParams = '';
    if (options?.filterForTeams !== false) { // Default to true
        // This filter ensures it's an online meeting AND specifically a Teams meeting.
        filterParams = `$filter=isOnlineMeeting eq true and onlineMeeting/onlineMeetingProvider eq 'teamsForBusiness'`;
    }
    // Example for date range filter if it were added to options:
    // if (options?.filter) { filterParams = filterParams ? `${filterParams} and ${options.filter}` : `$filter=${options.filter}`; }


    requestUrl = `${MSGRAPH_API_BASE_URL}/users/${userPrincipalNameOrId}/calendar/events?$select=${selectParams}&$orderby=${orderByParams}&$top=${topParams}`;
    if (filterParams) {
        requestUrl += `&${filterParams}`;
    }
  }

  try {
    const response = await axios.get(requestUrl, {
      headers: { 'Authorization': `Bearer ${token}` },
    });

    return {
      ok: true,
      events: response.data.value as MSGraphEvent[],
      nextLink: response.data['@odata.nextLink'] || undefined, // OData pagination link
    };
  } catch (error) {
    const axiosError = error as AxiosError;
    console.error(`Error listing MS Teams meetings for user ${userPrincipalNameOrId}:`, axiosError.message);
    const errorResponse = axiosError.response?.data as any;
    return {
      ok: false,
      error: errorResponse?.error?.message || axiosError.message || 'Failed to list MS Teams meetings',
    };
  }
}

export async function getMicrosoftTeamsMeetingDetails(
  userPrincipalNameOrId: string,
  eventId: string
): Promise<GetMSTeamsMeetingDetailsResponse> {
  console.log(`getMicrosoftTeamsMeetingDetails called for user: ${userPrincipalNameOrId}, eventId: ${eventId}`);
  const token = await getMSGraphToken();
  if (!token) {
    return { ok: false, error: 'Failed to obtain MS Graph access token.' };
  }

  // Select more comprehensive details for a single event
  const selectParams = 'id,subject,start,end,isOnlineMeeting,onlineMeeting,webLink,bodyPreview,body,attendees,location,locations,organizer';
  const requestUrl = `${MSGRAPH_API_BASE_URL}/users/${userPrincipalNameOrId}/events/${eventId}?$select=${selectParams}`;

  try {
    const response = await axios.get(requestUrl, {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    return { ok: true, event: response.data as MSGraphEvent };
  } catch (error) {
    const axiosError = error as AxiosError;
    console.error(`Error getting MS Teams meeting details for event ${eventId}, user ${userPrincipalNameOrId}:`, axiosError.message);
    const errorResponse = axiosError.response?.data as any;

    if (axiosError.response?.status === 404) {
      return { ok: false, error: `Meeting event not found (ID: ${eventId}). ${errorResponse?.error?.message || ''}`.trim() };
    }
    return {
      ok: false,
      error: errorResponse?.error?.message || axiosError.message || 'Failed to get MS Teams meeting details',
    };
  }
}
