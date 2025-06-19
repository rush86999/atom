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
  // ListMSTeamsMeetingsResponse, // Superseded by GraphSkillResponse<ListMSGraphEventsData>
  // GetMSTeamsMeetingDetailsResponse, // Superseded by GraphSkillResponse<MSGraphEvent>
  GraphSkillResponse, // New generic response type
  ListMSGraphEventsData, // New data payload type for listing events
  SkillError, // Standardized error type
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

async function getMSGraphToken(): Promise<GraphSkillResponse<string>> {
  if (msGraphAccessToken && Date.now() < msGraphAccessToken.expiresOnTimestamp) {
    console.log('Using cached MS Graph access token.');
    return { ok: true, data: msGraphAccessToken.token };
  }

  const clientApp = getMsalClient();
  if (!clientApp) {
    const errorMsg = 'MSAL client application could not be initialized due to missing configuration.';
    console.error(errorMsg);
    return { ok: false, error: { code: 'MSGRAPH_CONFIG_ERROR', message: errorMsg } };
  }

  if (!ATOM_MSGRAPH_SCOPES || ATOM_MSGRAPH_SCOPES.length === 0) {
      const errorMsg = 'MS Graph API scopes are not configured.';
      console.error(errorMsg);
      return { ok: false, error: { code: 'MSGRAPH_CONFIG_ERROR', message: errorMsg } };
  }

  const tokenRequest = {
    scopes: ATOM_MSGRAPH_SCOPES,
  };

  try {
    console.log('Requesting new MS Graph access token...');
    const response: AuthenticationResult | null = await clientApp.acquireTokenByClientCredential(tokenRequest);
    if (response && response.accessToken && response.expiresOn) {
      msGraphAccessToken = {
        token: response.accessToken,
        expiresOnTimestamp: response.expiresOn.getTime() - 300000, // 5 minutes buffer
      };
      console.log('Successfully obtained new MS Graph access token.');
      return { ok: true, data: response.accessToken };
    } else {
      console.error('Failed to acquire MS Graph token. Response was null or invalid.');
      msGraphAccessToken = null;
      return { ok: false, error: { code: 'MSGRAPH_AUTH_ERROR', message: 'Failed to acquire MS Graph token from MSAL.', details: response } };
    }
  } catch (error: any) {
    console.error('Error acquiring MS Graph token by client credential:', error);
    msGraphAccessToken = null;
    // Attempt to get more specific error information from MSAL error
    const errorCode = error.errorCode || 'MSGRAPH_AUTH_REQUEST_FAILED';
    const errorMessage = error.errorMessage || error.message || 'Error acquiring MS Graph token.';
    return { ok: false, error: { code: errorCode, message: errorMessage, details: error } };
  }
}

export async function listMicrosoftTeamsMeetings(
  userPrincipalNameOrId: string,
  options?: {
    limit?: number;
    nextLink?: string;
    filterForTeams?: boolean;
  }
): Promise<GraphSkillResponse<ListMSGraphEventsData>> {
  console.log(`listMicrosoftTeamsMeetings called for user: ${userPrincipalNameOrId}, options:`, options);

  if (!userPrincipalNameOrId) {
    return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'userPrincipalNameOrId is required.' }};
  }

  const tokenResponse = await getMSGraphToken();
  if (!tokenResponse.ok || !tokenResponse.data) {
    return { ok: false, error: tokenResponse.error || { code: 'MSGRAPH_AUTH_ERROR', message: 'Failed to obtain MS Graph access token for listing meetings.'} };
  }
  const token = tokenResponse.data;

  let requestUrl = options?.nextLink;

  if (!requestUrl) {
    const selectParams = 'id,subject,start,end,isOnlineMeeting,onlineMeeting,webLink,bodyPreview';
    const orderByParams = 'start/dateTime ASC';
    const topParams = options?.limit || 10;
    let filterParamsValue = '';

    if (options?.filterForTeams !== false) {
        filterParamsValue = `isOnlineMeeting eq true and onlineMeeting/onlineMeetingProvider eq 'teamsForBusiness'`;
    }

    const queryParams = new URLSearchParams();
    queryParams.append('$select', selectParams);
    queryParams.append('$orderby', orderByParams);
    queryParams.append('$top', topParams.toString());
    if (filterParamsValue) {
        queryParams.append('$filter', filterParamsValue);
    }
    requestUrl = `${MSGRAPH_API_BASE_URL}/users/${userPrincipalNameOrId}/calendar/events?${queryParams.toString()}`;
  }

  try {
    const response = await axios.get(requestUrl, { // MS Graph returns 'value' for items and '@odata.nextLink'
      headers: { 'Authorization': `Bearer ${token}` },
    });

    return {
      ok: true,
      data: {
        events: response.data.value as MSGraphEvent[],
        nextLink: response.data['@odata.nextLink'] || undefined,
      }
    };
  } catch (error: any) {
    const axiosError = error as AxiosError;
    console.error(`Error listing MS Teams meetings for user ${userPrincipalNameOrId}:`, axiosError.message);
    const errorData = axiosError.response?.data as any; // MS Graph errors are often in errorData.error
    return {
      ok: false,
      error: {
        code: errorData?.error?.code || 'MSGRAPH_API_ERROR',
        message: errorData?.error?.message || axiosError.message || 'Failed to list MS Teams meetings',
        details: errorData?.error || errorData
      }
    };
  }
}

export async function getMicrosoftTeamsMeetingDetails(
  userPrincipalNameOrId: string,
  eventId: string
): Promise<GraphSkillResponse<MSGraphEvent>> {
  console.log(`getMicrosoftTeamsMeetingDetails called for user: ${userPrincipalNameOrId}, eventId: ${eventId}`);

  if (!userPrincipalNameOrId || !eventId) {
    return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'userPrincipalNameOrId and eventId are required.' }};
  }

  const tokenResponse = await getMSGraphToken();
  if (!tokenResponse.ok || !tokenResponse.data) {
    return { ok: false, error: tokenResponse.error || { code: 'MSGRAPH_AUTH_ERROR', message: 'Failed to obtain MS Graph access token for getting meeting details.'} };
  }
  const token = tokenResponse.data;

  const selectParams = 'id,subject,start,end,isOnlineMeeting,onlineMeeting,webLink,bodyPreview,body,attendees,location,locations,organizer';
  const requestUrl = `${MSGRAPH_API_BASE_URL}/users/${userPrincipalNameOrId}/events/${eventId}?$select=${selectParams}`;

  try {
    const response = await axios.get<MSGraphEvent>(requestUrl, { // Expecting a single MSGraphEvent
      headers: { 'Authorization': `Bearer ${token}` },
    });
    return { ok: true, data: response.data };
  } catch (error: any) {
    const axiosError = error as AxiosError;
    console.error(`Error getting MS Teams meeting details for event ${eventId}, user ${userPrincipalNameOrId}:`, axiosError.message);
    const errorData = axiosError.response?.data as any; // MS Graph errors are often in errorData.error

    if (axiosError.response?.status === 404) {
      return {
          ok: false,
          error: {
              code: 'EVENT_NOT_FOUND',
              message: `Meeting event not found (ID: ${eventId}). ${errorData?.error?.message || ''}`.trim(),
              details: errorData?.error || errorData
          }
      };
    }
    return {
      ok: false,
      error: {
        code: errorData?.error?.code || 'MSGRAPH_API_ERROR',
        message: errorData?.error?.message || axiosError.message || 'Failed to get MS Teams meeting details',
        details: errorData?.error || errorData
      }
    };
  }
}
