import axios, { AxiosError } from 'axios';
import {
  ConfidentialClientApplication,
  Configuration,
  AuthenticationResult,
  LogLevel,
  PublicClientApplication,
  AuthorizationCodeRequest,
  AccountInfo,
  SilentFlowRequest,
} from '@azure/msal-node'; // Added PublicClientApplication and related types
import {
} from '@azure/msal-node';
import {
  // ATOM_MSGRAPH_CLIENT_ID, // Replaced by MSGRAPH_DELEGATED_CLIENT_ID
  // ATOM_MSGRAPH_CLIENT_SECRET, // Replaced by MSGRAPH_DELEGATED_CLIENT_SECRET
  // ATOM_MSGRAPH_TENANT_ID, // Replaced by MSGRAPH_DELEGATED_TENANT_ID
  // ATOM_MSGRAPH_AUTHORITY, // Replaced by MSGRAPH_DELEGATED_AUTHORITY
  // ATOM_MSGRAPH_SCOPES, // Replaced by MSGRAPH_DELEGATED_SCOPES
  // Import new Delegated Auth Constants from a central place if available, otherwise use process.env
  MSGRAPH_DELEGATED_CLIENT_ID,
  MSGRAPH_DELEGATED_CLIENT_SECRET,
  MSGRAPH_DELEGATED_AUTHORITY,
  MSGRAPH_DELEGATED_REDIRECT_URL,
  MSGRAPH_DELEGATED_SCOPES,
  MSTEAMS_TOKEN_ENCRYPTION_KEY,
} from '../atom-agent/_libs/constants'; // Adjusted path assuming constants are well-defined
import {
  MSGraphEvent,
  GraphSkillResponse,
  ListMSGraphEventsData,
  SkillError,
} from '../atom-agent/types'; // Adjusted path
import { logger } from '../_utils/logger';
import { createAdminGraphQLClient } from '../_utils/dbService';
// import { encrypt, decrypt } from '../_utils/encryption'; // TODO: Create and use a shared encryption utility

const MSGRAPH_API_BASE_URL = 'https://graph.microsoft.com/v1.0';

// MSAL ConfidentialClientApplication instance for the backend
let msalConfidentialClientApp: ConfidentialClientApplication | null = null;

// Database interaction functions (placeholders - to be implemented with actual DB calls)
// These would typically interact with a table like 'user_msteams_tokens'
// interface StoredTokenData {
//   encryptedAccessToken: string;
//   encryptedRefreshToken?: string | null;
//   accountJson: string; // Store MSAL AccountInfo as JSON
//   tokenExpiryTimestamp: Date;
// }

// TODO: Implement these functions properly
// These are conceptual and need to be implemented based on your DB schema and encryption utility
const getStoredUserMSTeamsTokens = async (userId: string): Promise<{ refreshToken: string; account: AccountInfo } | null> => {
  logger.debug(`[MSTeamsService] Attempting to fetch stored MS Teams tokens for user ${userId}.`);
  const adminClient = createAdminGraphQLClient();
  const query = `
    query GetMSTeamsToken($userId: String!) {
      user_tokens(where: {user_id: {_eq: $userId}, service: {_eq: "msteams"}}) {
        refresh_token
        account_json
      }
    }
  `;
  try {
    const data = await adminClient.request(query, { userId });
    if (data.user_tokens && data.user_tokens.length > 0) {
      const tokenRecord = data.user_tokens[0];
      if (!tokenRecord.refresh_token || !tokenRecord.account_json) return null;
      const refreshToken = decrypt(tokenRecord.refresh_token, MSTEAMS_TOKEN_ENCRYPTION_KEY!);
      const account = JSON.parse(tokenRecord.account_json) as AccountInfo;
      return { refreshToken, account };
    }
  } catch (error) {
    logger.error(`[MSTeamsService] Error fetching MS Teams tokens for user ${userId}:`, error);
  }
  return null;
};

const storeUserMSTeamsTokens = async (userId: string, authResult: AuthenticationResult): Promise<void> => {
  logger.debug(`[MSTeamsService] Storing MS Teams tokens for user ${userId}.`);
  if (!authResult.account) {
    logger.error('[MSTeamsService] Account info missing in AuthenticationResult. Cannot store tokens.');
    throw new Error('Account info missing, cannot store tokens.');
  }
  const accessToken = encrypt(authResult.accessToken, MSTEAMS_TOKEN_ENCRYPTION_KEY!);
  const refreshToken = authResult.refreshToken ? encrypt(authResult.refreshToken, MSTEAMS_TOKEN_ENCRYPTION_KEY!) : null;
  const accountJson = JSON.stringify(authResult.account);
  const expiry = authResult.expiresOn;

  const adminClient = createAdminGraphQLClient();
  const mutation = `
    mutation UpsertMSTeamsToken($userId: String!, $accessToken: String!, $refreshToken: String, $accountJson: jsonb!, $expiry: timestamptz!) {
      insert_user_tokens(objects: {user_id: $userId, service: "msteams", access_token: $accessToken, refresh_token: $refreshToken, account_json: $accountJson, expires_at: $expiry}, on_conflict: {constraint: user_tokens_user_id_service_key, update_columns: [access_token, refresh_token, account_json, expires_at]}) {
        affected_rows
      }
    }
  `;
  try {
    await adminClient.request(mutation, { userId, accessToken, refreshToken, accountJson, expiry });
    logger.info(`[MSTeamsService] Tokens for user ${userId} stored/updated successfully.`);
  } catch (error) {
    logger.error(`[MSTeamsService] Error storing MS Teams tokens for user ${userId}:`, error);
  }
};


function initializeConfidentialClientApp(): ConfidentialClientApplication | null {
  if (msalConfidentialClientApp) {
    return msalConfidentialClientApp;
  }

  if (!MSGRAPH_DELEGATED_CLIENT_ID || !MSGRAPH_DELEGATED_AUTHORITY || !MSGRAPH_DELEGATED_CLIENT_SECRET) {
    logger.error('[MSTeamsService] MS Graph API delegated client credentials not fully configured.');
    return null;
  }
  if (!MSTEAMS_TOKEN_ENCRYPTION_KEY) {
    // This check is crucial because if the key is missing, we can't decrypt/encrypt tokens for storage.
    logger.error('[MSTeamsService] MSTEAMS_TOKEN_ENCRYPTION_KEY is not configured. Cannot proceed with token operations.');
    // Depending on desired behavior, you might throw an error or return null.
    // For service initialization, returning null is safer.
    return null;
  }


  const msalConfig: Configuration = {
    auth: {
      clientId: MSGRAPH_DELEGATED_CLIENT_ID,
      authority: MSGRAPH_DELEGATED_AUTHORITY,
      clientSecret: MSGRAPH_DELEGATED_CLIENT_SECRET,
    },
    system: {
      loggerOptions: {
        loggerCallback(loglevel, message, containsPii) {
          // Avoid logging tokens or PII in production
          if (!containsPii) logger.debug(`[MSAL-${LogLevel[loglevel]}] ${message}`);
        },
        piiLoggingEnabled: false, // Set to true ONLY for local debugging of auth flows
        logLevel: LogLevel.Warning, // Adjust as needed: Error, Warning, Info, Verbose
      },
    },
  };
  msalConfidentialClientApp = new ConfidentialClientApplication(msalConfig);
  logger.info('[MSTeamsService] MSAL ConfidentialClientApplication initialized for delegated flow.');
  return msalConfidentialClientApp;
}

export interface MSGraphUserTokenDetails {
  accessToken: string;
  userAadObjectId: string | null; // AAD Object ID
  userPrincipalName: string | null; // UPN
  accountInfo?: AccountInfo; // The raw account info for further use if needed
}

export async function getDelegatedMSGraphTokenForUser(userId: string): Promise<GraphSkillResponse<MSGraphUserTokenDetails>> {
  const clientApp = initializeConfidentialClientApp();
  if (!clientApp) {
    const errorMsg = 'MSAL client application could not be initialized.';
    logger.error(`[MSTeamsService] ${errorMsg}`);
    return { ok: false, error: { code: 'MSGRAPH_CONFIG_ERROR', message: errorMsg } };
  }

  if (!MSTEAMS_TOKEN_ENCRYPTION_KEY) {
    logger.error('[MSTeamsService] MSTEAMS_TOKEN_ENCRYPTION_KEY is not configured. Cannot get/refresh tokens.');
    return { ok: false, error: { code: 'MSGRAPH_CONFIG_ERROR', message: 'Token encryption key not configured.'}};
  }

  const storedTokenInfo = await getStoredUserMSTeamsTokens(userId);
  if (!storedTokenInfo || !storedTokenInfo.account || !storedTokenInfo.refreshToken) {
    logger.warn(`[MSTeamsService] No stored MS Teams refresh token or account info for user ${userId}. User needs to authenticate.`);
    return { ok: false, error: { code: 'MSGRAPH_AUTH_REQUIRED', message: 'User authentication required for MS Teams (no refresh token or account info).' } };
  }

  try {
    // MSAL's acquireTokenSilent will use a cached access token if valid,
    // or use the refresh token to get a new access token if the cached one is expired.
    const silentRequest: SilentFlowRequest = {
      account: storedTokenInfo.account, // AccountInfo object from when token was first acquired
      scopes: MSGRAPH_DELEGATED_SCOPES!, // Ensure scopes are defined as an array
      forceRefresh: false, // Set to true only if you suspect the cached AT is stale but not expired
    };

    let authResult: AuthenticationResult | null = null;
    try {
        logger.debug(`[MSTeamsService] Attempting to acquire token silently for user ${userId} with account ${storedTokenInfo.account.homeAccountId}`);
        authResult = await clientApp.acquireTokenSilent(silentRequest);
    } catch (error: any) {
        logger.warn(`[MSTeamsService] Silent token acquisition failed for user ${userId} (Error: ${error.errorCode || error.name}). Attempting refresh via stored refresh token if applicable.`);
        // Check if error is due to needing a refresh token or if it's an InteractionRequired error
        // Some errors (like no_tokens_found) might mean we should try acquireTokenByRefreshToken
        if (error.name === "ClientAuthError" && (error.errorCode === "no_tokens_found" || error.errorCode === "token_expired_error" || error.message?.includes(" Při pokusu o získání tokenu z mezipaměti nebyl nalezen žádný platný přístupový token."))) {
            // The last error message is an example of a localized error that might indicate no valid AT in cache.
            try {
                logger.info(`[MSTeamsService] Attempting acquireTokenByRefreshToken for user ${userId}.`);
                const refreshTokenRequest = {
                    refreshToken: storedTokenInfo.refreshToken,
                    scopes: MSGRAPH_DELEGATED_SCOPES!,
                };
                authResult = await clientApp.acquireTokenByRefreshToken(refreshTokenRequest);
            } catch (refreshError: any) {
                logger.error(`[MSTeamsService] Failed to acquire token by refresh token for user ${userId}:`, refreshError);
                // If refresh token itself is invalid/expired, user must re-authenticate.
                 if (refreshError.name === "InteractionRequiredAuthError" || refreshError.errorCode === 'invalid_grant' || refreshError.message?.includes("AADSTS70008")) { // invalid_grant or similar
                    return { ok: false, error: { code: 'MSGRAPH_INTERACTION_REQUIRED', message: 'Refresh token invalid or expired. User must re-authenticate with Microsoft Teams.'}};
                }
                return { ok: false, error: { code: 'MSGRAPH_REFRESH_FAILED', message: `Failed to refresh token: ${refreshError.message}`, details: refreshError } };
            }
        } else {
            throw error; // Re-throw other silent errors not handled by refresh token attempt
        }
    }

    if (authResult && authResult.accessToken) {
      // Account object in authResult might be updated (e.g. if tokens were refreshed with a new account state from IdP)
      await storeUserMSTeamsTokens(userId, authResult);
      logger.info(`[MSTeamsService] Successfully acquired/refreshed token for user ${userId}.`);

      let userAadObjectId: string | null = null;
      let userPrincipalName: string | null = null;

      if (authResult.account) {
        // Prefer oid from idTokenClaims if available
        if (authResult.account.idTokenClaims?.oid) {
          userAadObjectId = authResult.account.idTokenClaims.oid;
        } else if (authResult.account.homeAccountId) {
          // homeAccountId is usually <OID>.<TID>
          userAadObjectId = authResult.account.homeAccountId.split('.')[0];
        }
        userPrincipalName = authResult.account.username; // Usually UPN

        logger.info(`[MSTeamsService] Extracted AAD OID: ${userAadObjectId}, UPN: ${userPrincipalName} from MSAL AccountInfo for user ${userId}.`);

        // Optional: Verify/fetch with /me if needed, or if specific claims are missing
        // For instance, if only homeAccountId was available and not idTokenClaims.oid,
        // and you wanted to be certain or get other details like display name.
        // For now, we rely on the MSAL account object.
        // if (!userAadObjectId && authResult.accessToken) { /* ... call /me ... */ }
      }

      return {
        ok: true,
        data: {
          accessToken: authResult.accessToken,
          userAadObjectId: userAadObjectId,
          userPrincipalName: userPrincipalName,
          accountInfo: authResult.account // Pass the full accountInfo if the caller might need it
        }
      };
    } else {
      logger.warn(`[MSTeamsService] Token acquisition yielded null/empty accessToken for user ${userId} without throwing. This is unexpected.`);
      return { ok: false, error: { code: 'MSGRAPH_AUTH_UNEXPECTED_NO_TOKEN', message: 'Token acquisition returned no access token unexpectedly.' } };
    }
  } catch (error: any) {
    logger.error(`[MSTeamsService] General error in getDelegatedMSGraphTokenForUser for ${userId}:`, error);
    if (error.name === 'InteractionRequiredAuthError' || (error.name === 'ClientAuthError' && error.errorCode === 'no_account_in_silent_request')) {
        // This error means the user needs to go through the interactive sign-in process again.
        return { ok: false, error: { code: 'MSGRAPH_INTERACTION_REQUIRED', message: 'User interaction required. Please re-authenticate with Microsoft Teams.' } };
    }
    return { ok: false, error: { code: 'MSGRAPH_AUTH_ERROR', message: `Failed to acquire MS Graph token for user ${userId}: ${error.message}`, details: error } };
  }
}

export async function generateTeamsAuthUrl(userIdForContext: string, state?: string): Promise<string | null> {
  const clientApp = initializeConfidentialClientApp(); // Correctly use the confidential client app
  if (!clientApp) {
    logger.error('[MSTeamsService] MSAL client not initialized, cannot generate auth URL.');
    return null;
  }

  if (!MSGRAPH_DELEGATED_SCOPES || MSGRAPH_DELEGATED_SCOPES.length === 0) {
    logger.error('[MSTeamsService] MSGRAPH_DELEGATED_SCOPES are not configured.');
    return null;
  }
  if (!MSGRAPH_DELEGATED_REDIRECT_URL) {
    logger.error('[MSTeamsService] MSGRAPH_DELEGATED_REDIRECT_URL is not configured.');
    return null;
  }

  try {
    const authCodeUrlParameters = {
      scopes: MSGRAPH_DELEGATED_SCOPES,
      redirectUri: MSGRAPH_DELEGATED_REDIRECT_URL,
      state: state, // For CSRF protection; should be generated, temporarily stored, and validated by caller on callback
    };
    const authUrl = await clientApp.getAuthCodeUrl(authCodeUrlParameters);
    logger.info(`[MSTeamsService] Generated MS Teams auth URL for context user: ${userIdForContext}.`);
    return authUrl;
  } catch (error: any) {
    logger.error(`[MSTeamsService] Error generating MS Teams auth URL for context user ${userIdForContext}:`, error);
    return null;
  }
}

export async function handleTeamsAuthCallback(userId: string, authorizationCode: string): Promise<GraphSkillResponse<boolean>> {
  const clientApp = initializeConfidentialClientApp(); // Correctly use the confidential client app
  if (!clientApp) {
    logger.error('[MSTeamsService] MSAL client not initialized, cannot handle auth callback.');
    return { ok: false, error: { code: 'MSGRAPH_CONFIG_ERROR', message: 'MSAL client not initialized.' } };
  }

  if (!MSTEAMS_TOKEN_ENCRYPTION_KEY) {
    logger.error('[MSTeamsService] MSTEAMS_TOKEN_ENCRYPTION_KEY is not configured. Cannot store tokens post callback.');
    return { ok: false, error: { code: 'MSGRAPH_CONFIG_ERROR', message: 'Token encryption key not configured for callback.'}};
  }
   if (!MSGRAPH_DELEGATED_SCOPES || MSGRAPH_DELEGATED_SCOPES.length === 0) {
    logger.error('[MSTeamsService] MSGRAPH_DELEGATED_SCOPES are not configured for callback token request.');
    return { ok: false, error: { code: 'MSGRAPH_CONFIG_ERROR', message: 'Scopes not configured for callback.'}};
  }
  if (!MSGRAPH_DELEGATED_REDIRECT_URL) {
    logger.error('[MSTeamsService] MSGRAPH_DELEGATED_REDIRECT_URL is not configured for callback token request.');
    return { ok: false, error: { code: 'MSGRAPH_CONFIG_ERROR', message: 'Redirect URL not configured for callback.'}};
  }


  try {
    const tokenRequest: AuthorizationCodeRequest = {
      code: authorizationCode,
      scopes: MSGRAPH_DELEGATED_SCOPES,
      redirectUri: MSGRAPH_DELEGATED_REDIRECT_URL,
    };
    const authResult = await clientApp.acquireTokenByCode(tokenRequest);

    if (authResult && authResult.accessToken && authResult.account) {
      await storeUserMSTeamsTokens(userId, authResult); // Uses placeholder
      logger.info(`[MSTeamsService] Successfully handled MS Teams auth callback and initiated token storage for user ${userId}.`);
      return { ok: true, data: true };
    } else {
      logger.error(`[MSTeamsService] Failed to acquire token by code for user ${userId}. AuthResult invalid or account missing.`, authResult);
      return { ok: false, error: { code: 'MSGRAPH_AUTH_CALLBACK_FAILED', message: 'Could not process auth code or vital token/account info missing.' } };
    }
  } catch (error: any) {
    logger.error(`[MSTeamsService] Error in handleTeamsAuthCallback for user ${userId}:`, error);
    // Provide more specific error if MSAL gives one (e.g. invalid_grant for used/expired code)
    const errorCode = error.errorCode || 'MSGRAPH_AUTH_ERROR';
    return { ok: false, error: { code: errorCode, message: `Callback handling error: ${error.message}`, details: error } };
  }
}


// Existing meeting functions need to be adapted to use getDelegatedMSGraphTokenForUser
// For example:
export async function listMicrosoftTeamsMeetings(
  atomUserId: string, // Changed from userPrincipalNameOrId to Atom's internal userId
  options?: {
    limit?: number;
    nextLink?: string;
    filterForTeamsMeetings?: boolean; // More descriptive name
  }
): Promise<GraphSkillResponse<ListMSGraphEventsData>> {
  logger.debug(`[MSTeamsService] listMicrosoftTeamsMeetings called for Atom user: ${atomUserId}, options:`, options);

  const tokenResponse = await getDelegatedMSGraphTokenForUser(atomUserId);
  if (!tokenResponse.ok || !tokenResponse.data) {
    return { ok: false, error: tokenResponse.error || { code: 'MSGRAPH_AUTH_ERROR', message: 'Failed to obtain MS Graph access token for listing meetings.'} };
  }
  const token = tokenResponse.data;

  let requestUrl = options?.nextLink;

  if (!requestUrl) {
    const selectParams = 'id,subject,start,end,isOnlineMeeting,onlineMeeting,webLink,bodyPreview';
    const orderByParams = 'start/dateTime ASC'; // Graph API uses PascalCase for OData query params
    const topParams = options?.limit || 10;
    let filterParamsValue = '';

    // Filter for actual Teams meetings if requested, otherwise fetch all calendar events for the user
    if (options?.filterForTeamsMeetings === true) {
        filterParamsValue = `isOnlineMeeting eq true and onlineMeeting/onlineMeetingProvider eq 'teamsForBusiness'`;
    }

    const queryParams = new URLSearchParams();
    queryParams.append('$select', selectParams);
    queryParams.append('$orderBy', orderByParams); // Corrected from '$orderby'
    queryParams.append('$top', topParams.toString());
    if (filterParamsValue) {
        queryParams.append('$filter', filterParamsValue);
    }
    // Use '/me/calendar/events' for delegated permissions to get events from the signed-in user's primary calendar
    requestUrl = `${MSGRAPH_API_BASE_URL}/me/calendar/events?${queryParams.toString()}`;
  }

  try {
    logger.debug(`[MSTeamsService] Requesting meetings from MS Graph: ${requestUrl}`);
    const response = await axios.get(requestUrl, {
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
    logger.error(`[MSTeamsService] Error listing MS Teams meetings for Atom user ${atomUserId}:`, axiosError.message, axiosError.response?.data);
    const errorData = axiosError.response?.data as any;
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
  atomUserId: string, // Changed from userPrincipalNameOrId to Atom's internal userId
  eventId: string
): Promise<GraphSkillResponse<MSGraphEvent>> {
  logger.debug(`[MSTeamsService] getMicrosoftTeamsMeetingDetails called for Atom user: ${atomUserId}, eventId: ${eventId}`);

  const tokenResponse = await getDelegatedMSGraphTokenForUser(atomUserId);
  if (!tokenResponse.ok || !tokenResponse.data) {
    return { ok: false, error: tokenResponse.error || { code: 'MSGRAPH_AUTH_ERROR', message: 'Failed to obtain MS Graph access token for meeting details.'} };
  }
  const token = tokenResponse.data;

  const selectParams = 'id,subject,start,end,isOnlineMeeting,onlineMeeting,webLink,bodyPreview,body,attendees,location,locations,organizer';
  // Use '/me/events/{id}' for delegated permissions to get a specific event from the signed-in user's default calendar
  const requestUrl = `${MSGRAPH_API_BASE_URL}/me/events/${eventId}?$select=${selectParams}`;

  try {
    logger.debug(`[MSTeamsService] Requesting meeting details from MS Graph: ${requestUrl}`);
    const response = await axios.get<MSGraphEvent>(requestUrl, {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    return { ok: true, data: response.data };
  } catch (error: any) {
    const axiosError = error as AxiosError;
    logger.error(`[MSTeamsService] Error getting MS Teams meeting details for event ${eventId}, Atom user ${atomUserId}:`, axiosError.message, axiosError.response?.data);
    const errorData = axiosError.response?.data as any;
     if (axiosError.response?.status === 404) {
      return { ok: false, error: { code: 'EVENT_NOT_FOUND', message: `Meeting event not found (ID: ${eventId}). Details: ${errorData?.error?.message || ''}`.trim()}};
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

// Placeholder for msalClientApp, this was the old one for client credentials, can be removed.
// let msalClientApp: ConfidentialClientApplication | null = null;


// --- New functions for chat message interactions ---

/**
 * Defines the structure for a Teams message object within the agent.
 * This should align with what the agent needs and what Graph API provides.
 */
export interface AgentMSTeamsMessage {
  id: string;
  chatId?: string; // For 1:1 or group chats
  channelId?: string; // For channel messages (within a team)
  teamId?: string; // For channel messages
  replyToId?: string; // ID of the message this one is a reply to
  userId?: string; // Sender's AAD User ID
  userName?: string; // Sender's display name
  content: string; // HTML content of the message
  contentType: 'html' | 'text';
  createdDateTime: string; // ISO 8601
  lastModifiedDateTime?: string; // ISO 8601
  webUrl?: string; // Permalink
  attachments?: { id: string; name?: string; contentType?: string; contentUrl?: string; size?: number; }[];
  mentions?: { id: number; mentionText?: string; mentioned?: { user?: { id: string; displayName?: string; userIdentityType?: string; }; }; }[];
  raw?: any; // Store the raw Graph API message object
}

/**
 * Searches Microsoft Teams messages using the Graph Search API.
 * @param atomUserId Atom's internal user ID.
 * @param searchQuery KQL query string.
 * @param maxResults Maximum number of messages to return.
 * @returns A promise resolving to an array of AgentMSTeamsMessage objects.
 */
export async function searchTeamsMessages(
  atomUserId: string,
  searchQuery: string, // This will be the KQL query string
  maxResults: number = 20,
  userAadObjectId?: string // Optional: AAD Object ID of the user for more specific queries
): Promise<GraphSkillResponse<AgentMSTeamsMessage[]>> {
  logger.debug(`[MSTeamsService] searchTeamsMessages called for Atom user ${atomUserId}, query: "${searchQuery}", maxResults: ${maxResults}, userAadObjectId: ${userAadObjectId}`);

  const tokenResponse = await getDelegatedMSGraphTokenForUser(atomUserId);
  if (!tokenResponse.ok || !tokenResponse.data) {
    return { ok: false, error: tokenResponse.error || { code: 'MSGRAPH_AUTH_ERROR', message: 'Failed to obtain MS Graph token for searching messages.'} };
  }
  const token = tokenResponse.data;

  // KQL query construction will now happen in the calling layer (e.g., Hasura action, or msTeamsSkills.ts)
  // if userAadObjectId is to be dynamically inserted.
  // For this function, searchQuery is assumed to be the final KQL.
  // If userAadObjectId is provided, the caller should have already incorporated it into searchQuery.
  // This function's responsibility is to execute the provided KQL.

  // Example of how a caller might construct KQL if it had userAadObjectId:
  // let finalKql = searchQuery; // searchQuery would be just date range parts
  // if (userAadObjectId) {
  //   finalKql = `(from:"${userAadObjectId}" OR mentions:"${userAadObjectId}") AND ${searchQuery}`;
  // }
  // logger.info(`[MSTeamsService] Effective KQL for search: ${finalKql}`);

  const searchRequest = {
    requests: [
      {
        entityTypes: ['chatMessage'],
        query: {
          queryString: searchQuery, // Use the passed searchQuery directly
        },
        from: 0,
        size: maxResults,
        sortProperties: [
          { name: "createdDateTime", isDescending: true }
        ]
      },
    ],
  };

  const requestUrl = `${MSGRAPH_API_BASE_URL}/search/query`;

  try {
    // Log the actual KQL query being sent to Graph API
    logger.info(`[MSTeamsService] Executing Graph Search API with KQL: "${searchQuery}" for user ${atomUserId}`);
    const response = await axios.post(requestUrl, searchRequest, {
      headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
    });

    const messages: AgentMSTeamsMessage[] = [];
    if (response.data && response.data.value && response.data.value.length > 0) {
      const searchHitsContainers = response.data.value[0]?.hitsContainers;
      if (searchHitsContainers && searchHitsContainers.length > 0) {
        searchHitsContainers.forEach((container: any) => {
          if (container.hits) {
            container.hits.forEach((hit: any) => {
              const resource = hit.resource;
              if (resource) {
                messages.push({
                  id: resource.id,
                  chatId: resource.chatId,
                  channelId: resource.channelIdentity?.channelId,
                  teamId: resource.channelIdentity?.teamId,
                  replyToId: resource.replyToId,
                  userId: resource.from?.user?.id,
                  userName: resource.from?.user?.displayName,
                  content: resource.body?.content,
                  contentType: resource.body?.contentType,
                  createdDateTime: resource.createdDateTime,
                  lastModifiedDateTime: resource.lastModifiedDateTime,
                  webUrl: resource.webUrl,
                  // attachments: resource.attachments, // Graph search might not return full attachments here
                  // mentions: resource.mentions,
                  raw: resource,
                });
              }
            });
          }
        });
      }
    }
    logger.info(`[MSTeamsService] Found ${messages.length} Teams messages for query "${searchQuery}" for Atom user ${atomUserId}.`);
    return { ok: true, data: messages };

  } catch (error: any) {
    const axiosError = error as AxiosError;
    logger.error(`[MSTeamsService] Error searching Teams messages for Atom user ${atomUserId}:`, axiosError.message, axiosError.response?.data);
    const errorData = axiosError.response?.data as any;
    return {
      ok: false,
      error: {
        code: errorData?.error?.code || 'MSGRAPH_SEARCH_API_ERROR',
        message: errorData?.error?.message || axiosError.message || 'Failed to search Teams messages',
        details: errorData?.error || errorData
      }
    };
  }
}


/**
 * Gets the content of a specific chat message (1:1 or group chat).
 * @param atomUserId Atom's internal user ID.
 * @param chatId The ID of the chat.
 * @param messageId The ID of the message.
 * @returns A promise resolving to an AgentMSTeamsMessage object or null.
 */
export async function getTeamsChatMessageContent(
  atomUserId: string,
  chatId: string,
  messageId: string
): Promise<GraphSkillResponse<AgentMSTeamsMessage | null>> {
  logger.debug(`[MSTeamsService] getTeamsChatMessageContent for user ${atomUserId}, chatId: ${chatId}, messageId: ${messageId}`);
  const tokenResponse = await getDelegatedMSGraphTokenForUser(atomUserId);
  if (!tokenResponse.ok || !tokenResponse.data) return { ok: false, error: tokenResponse.error };
  const token = tokenResponse.data;

  // The fields selected here should match the AgentMSTeamsMessage interface
  const selectFields = "id,replyToId,from,body,createdDateTime,lastModifiedDateTime,webUrl,attachments,mentions,chatId";
  const requestUrl = `${MSGRAPH_API_BASE_URL}/me/chats/${chatId}/messages/${messageId}?$select=${selectFields}`;

  try {
    const response = await axios.get(requestUrl, { headers: { 'Authorization': `Bearer ${token}` } });
    const rawMsg = response.data;
    const message: AgentMSTeamsMessage = {
      id: rawMsg.id,
      chatId: rawMsg.chatId, // Will be populated by this endpoint
      replyToId: rawMsg.replyToId,
      userId: rawMsg.from?.user?.id,
      userName: rawMsg.from?.user?.displayName,
      content: rawMsg.body?.content,
      contentType: rawMsg.body?.contentType,
      createdDateTime: rawMsg.createdDateTime,
      lastModifiedDateTime: rawMsg.lastModifiedDateTime,
      webUrl: rawMsg.webUrl,
      attachments: rawMsg.attachments?.map((att: any) => ({
          id: att.id, name: att.name, contentType: att.contentType, contentUrl: att.contentUrl, size: att.size
      })),
      mentions: rawMsg.mentions?.map((men:any) => ({
          id: men.id, mentionText: men.mentionText, mentioned: men.mentioned
      })),
      raw: rawMsg,
    };
    return { ok: true, data: message };
  } catch (error: any) {
    const axiosError = error as AxiosError;
    logger.error(`[MSTeamsService] Error getting chat message content (chat ${chatId}, msg ${messageId}):`, axiosError.message, axiosError.response?.data);
    const errorData = axiosError.response?.data as any;
    if (axiosError.response?.status === 404) return { ok: false, error: { code: 'MSGRAPH_MESSAGE_NOT_FOUND', message: 'Chat message not found.'}};
    return { ok: false, error: { code: errorData?.error?.code || 'MSGRAPH_API_ERROR', message: errorData?.error?.message || 'Failed to get chat message content'}};
  }
}

/**
 * Gets the content of a specific channel message.
 * @param atomUserId Atom's internal user ID.
 * @param teamId The ID of the team.
 * @param channelId The ID of the channel.
 * @param messageId The ID of the message.
 * @returns A promise resolving to an AgentMSTeamsMessage object or null.
 */
export async function getTeamsChannelMessageContent(
  atomUserId: string,
  teamId: string,
  channelId: string,
  messageId: string
): Promise<GraphSkillResponse<AgentMSTeamsMessage | null>> {
  logger.debug(`[MSTeamsService] getTeamsChannelMessageContent for user ${atomUserId}, team ${teamId}, channel ${channelId}, msg ${messageId}`);
  const tokenResponse = await getDelegatedMSGraphTokenForUser(atomUserId);
  if (!tokenResponse.ok || !tokenResponse.data) return { ok: false, error: tokenResponse.error };
  const token = tokenResponse.data;

  const selectFields = "id,replyToId,from,body,createdDateTime,lastModifiedDateTime,webUrl,attachments,mentions,channelIdentity";
  const requestUrl = `${MSGRAPH_API_BASE_URL}/teams/${teamId}/channels/${channelId}/messages/${messageId}?$select=${selectFields}`;

  try {
    const response = await axios.get(requestUrl, { headers: { 'Authorization': `Bearer ${token}` } });
    const rawMsg = response.data;
    const message: AgentMSTeamsMessage = {
      id: rawMsg.id,
      teamId: rawMsg.channelIdentity?.teamId,
      channelId: rawMsg.channelIdentity?.channelId,
      replyToId: rawMsg.replyToId,
      userId: rawMsg.from?.user?.id,
      userName: rawMsg.from?.user?.displayName,
      content: rawMsg.body?.content,
      contentType: rawMsg.body?.contentType,
      createdDateTime: rawMsg.createdDateTime,
      lastModifiedDateTime: rawMsg.lastModifiedDateTime,
      webUrl: rawMsg.webUrl,
      attachments: rawMsg.attachments?.map((att: any) => ({
          id: att.id, name: att.name, contentType: att.contentType, contentUrl: att.contentUrl, size: att.size
      })),
      mentions: rawMsg.mentions?.map((men:any) => ({
          id: men.id, mentionText: men.mentionText, mentioned: men.mentioned
      })),
      raw: rawMsg,
    };
    return { ok: true, data: message };
  } catch (error: any) {
    const axiosError = error as AxiosError;
    logger.error(`[MSTeamsService] Error getting channel message content (team ${teamId}, channel ${channelId}, msg ${messageId}):`, axiosError.message, axiosError.response?.data);
    const errorData = axiosError.response?.data as any;
    if (axiosError.response?.status === 404) return { ok: false, error: { code: 'MSGRAPH_MESSAGE_NOT_FOUND', message: 'Channel message not found.'}};
    return { ok: false, error: { code: errorData?.error?.code || 'MSGRAPH_API_ERROR', message: errorData?.error?.message || 'Failed to get channel message content'}};
  }
}

// Note: getTeamsMessagePermalink is implicitly handled by the `webUrl` property
// in the AgentMSTeamsMessage when messages are fetched. No separate function needed
// unless a specific API call for permalink generation is preferred or required for some edge cases.
