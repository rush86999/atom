import axios from 'axios';
import { ConfidentialClientApplication, LogLevel, } from '@azure/msal-node'; // Added PublicClientApplication and related types
import { 
// ATOM_MSGRAPH_CLIENT_ID, // Replaced by MSGRAPH_DELEGATED_CLIENT_ID
// ATOM_MSGRAPH_CLIENT_SECRET, // Replaced by MSGRAPH_DELEGATED_CLIENT_SECRET
// ATOM_MSGRAPH_TENANT_ID, // Replaced by MSGRAPH_DELEGATED_TENANT_ID
// ATOM_MSGRAPH_AUTHORITY, // Replaced by MSGRAPH_DELEGATED_AUTHORITY
// ATOM_MSGRAPH_SCOPES, // Replaced by MSGRAPH_DELEGATED_SCOPES
// Import new Delegated Auth Constants from a central place if available, otherwise use process.env
MSGRAPH_DELEGATED_CLIENT_ID, MSGRAPH_DELEGATED_CLIENT_SECRET, MSGRAPH_DELEGATED_AUTHORITY, MSGRAPH_DELEGATED_REDIRECT_URL, MSGRAPH_DELEGATED_SCOPES, MSTEAMS_TOKEN_ENCRYPTION_KEY, } from '../atom-agent/_libs/constants'; // Adjusted path assuming constants are well-defined
import { logger } from '../_utils/logger';
import { createAdminGraphQLClient } from '../_utils/dbService';
// import { encrypt, decrypt } from '../_utils/encryption'; // TODO: Create and use a shared encryption utility
const MSGRAPH_API_BASE_URL = 'https://graph.microsoft.com/v1.0';
// MSAL ConfidentialClientApplication instance for the backend
let msalConfidentialClientApp = null;
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
const getStoredUserMSTeamsTokens = async (userId) => {
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
            if (!tokenRecord.refresh_token || !tokenRecord.account_json)
                return null;
            const refreshToken = decrypt(tokenRecord.refresh_token, MSTEAMS_TOKEN_ENCRYPTION_KEY);
            const account = JSON.parse(tokenRecord.account_json);
            return { refreshToken, account };
        }
    }
    catch (error) {
        logger.error(`[MSTeamsService] Error fetching MS Teams tokens for user ${userId}:`, error);
    }
    return null;
};
const storeUserMSTeamsTokens = async (userId, authResult) => {
    logger.debug(`[MSTeamsService] Storing MS Teams tokens for user ${userId}.`);
    if (!authResult.account) {
        logger.error('[MSTeamsService] Account info missing in AuthenticationResult. Cannot store tokens.');
        throw new Error('Account info missing, cannot store tokens.');
    }
    const accessToken = encrypt(authResult.accessToken, MSTEAMS_TOKEN_ENCRYPTION_KEY);
    const refreshToken = authResult.refreshToken
        ? encrypt(authResult.refreshToken, MSTEAMS_TOKEN_ENCRYPTION_KEY)
        : null;
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
        await adminClient.request(mutation, {
            userId,
            accessToken,
            refreshToken,
            accountJson,
            expiry,
        });
        logger.info(`[MSTeamsService] Tokens for user ${userId} stored/updated successfully.`);
    }
    catch (error) {
        logger.error(`[MSTeamsService] Error storing MS Teams tokens for user ${userId}:`, error);
    }
};
function initializeConfidentialClientApp() {
    if (msalConfidentialClientApp) {
        return msalConfidentialClientApp;
    }
    if (!MSGRAPH_DELEGATED_CLIENT_ID ||
        !MSGRAPH_DELEGATED_AUTHORITY ||
        !MSGRAPH_DELEGATED_CLIENT_SECRET) {
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
    const msalConfig = {
        auth: {
            clientId: MSGRAPH_DELEGATED_CLIENT_ID,
            authority: MSGRAPH_DELEGATED_AUTHORITY,
            clientSecret: MSGRAPH_DELEGATED_CLIENT_SECRET,
        },
        system: {
            loggerOptions: {
                loggerCallback(loglevel, message, containsPii) {
                    // Avoid logging tokens or PII in production
                    if (!containsPii)
                        logger.debug(`[MSAL-${LogLevel[loglevel]}] ${message}`);
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
export async function getDelegatedMSGraphTokenForUser(userId) {
    const clientApp = initializeConfidentialClientApp();
    if (!clientApp) {
        const errorMsg = 'MSAL client application could not be initialized.';
        logger.error(`[MSTeamsService] ${errorMsg}`);
        return {
            ok: false,
            error: { code: 'MSGRAPH_CONFIG_ERROR', message: errorMsg },
        };
    }
    if (!MSTEAMS_TOKEN_ENCRYPTION_KEY) {
        logger.error('[MSTeamsService] MSTEAMS_TOKEN_ENCRYPTION_KEY is not configured. Cannot get/refresh tokens.');
        return {
            ok: false,
            error: {
                code: 'MSGRAPH_CONFIG_ERROR',
                message: 'Token encryption key not configured.',
            },
        };
    }
    const storedTokenInfo = await getStoredUserMSTeamsTokens(userId);
    if (!storedTokenInfo ||
        !storedTokenInfo.account ||
        !storedTokenInfo.refreshToken) {
        logger.warn(`[MSTeamsService] No stored MS Teams refresh token or account info for user ${userId}. User needs to authenticate.`);
        return {
            ok: false,
            error: {
                code: 'MSGRAPH_AUTH_REQUIRED',
                message: 'User authentication required for MS Teams (no refresh token or account info).',
            },
        };
    }
    try {
        // MSAL's acquireTokenSilent will use a cached access token if valid,
        // or use the refresh token to get a new access token if the cached one is expired.
        const silentRequest = {
            account: storedTokenInfo.account, // AccountInfo object from when token was first acquired
            scopes: MSGRAPH_DELEGATED_SCOPES, // Ensure scopes are defined as an array
            forceRefresh: false, // Set to true only if you suspect the cached AT is stale but not expired
        };
        let authResult = null;
        try {
            logger.debug(`[MSTeamsService] Attempting to acquire token silently for user ${userId} with account ${storedTokenInfo.account.homeAccountId}`);
            authResult = await clientApp.acquireTokenSilent(silentRequest);
        }
        catch (error) {
            logger.warn(`[MSTeamsService] Silent token acquisition failed for user ${userId} (Error: ${error.errorCode || error.name}). Attempting refresh via stored refresh token if applicable.`);
            // Check if error is due to needing a refresh token or if it's an InteractionRequired error
            // Some errors (like no_tokens_found) might mean we should try acquireTokenByRefreshToken
            if (error.name === 'ClientAuthError' &&
                (error.errorCode === 'no_tokens_found' ||
                    error.errorCode === 'token_expired_error' ||
                    error.message?.includes(' Při pokusu o získání tokenu z mezipaměti nebyl nalezen žádný platný přístupový token.'))) {
                // The last error message is an example of a localized error that might indicate no valid AT in cache.
                try {
                    logger.info(`[MSTeamsService] Attempting acquireTokenByRefreshToken for user ${userId}.`);
                    const refreshTokenRequest = {
                        refreshToken: storedTokenInfo.refreshToken,
                        scopes: MSGRAPH_DELEGATED_SCOPES,
                    };
                    authResult =
                        await clientApp.acquireTokenByRefreshToken(refreshTokenRequest);
                }
                catch (refreshError) {
                    logger.error(`[MSTeamsService] Failed to acquire token by refresh token for user ${userId}:`, refreshError);
                    // If refresh token itself is invalid/expired, user must re-authenticate.
                    if (refreshError.name === 'InteractionRequiredAuthError' ||
                        refreshError.errorCode === 'invalid_grant' ||
                        refreshError.message?.includes('AADSTS70008')) {
                        // invalid_grant or similar
                        return {
                            ok: false,
                            error: {
                                code: 'MSGRAPH_INTERACTION_REQUIRED',
                                message: 'Refresh token invalid or expired. User must re-authenticate with Microsoft Teams.',
                            },
                        };
                    }
                    return {
                        ok: false,
                        error: {
                            code: 'MSGRAPH_REFRESH_FAILED',
                            message: `Failed to refresh token: ${refreshError.message}`,
                            details: refreshError,
                        },
                    };
                }
            }
            else {
                throw error; // Re-throw other silent errors not handled by refresh token attempt
            }
        }
        if (authResult && authResult.accessToken) {
            // Account object in authResult might be updated (e.g. if tokens were refreshed with a new account state from IdP)
            await storeUserMSTeamsTokens(userId, authResult);
            logger.info(`[MSTeamsService] Successfully acquired/refreshed token for user ${userId}.`);
            let userAadObjectId = null;
            let userPrincipalName = null;
            if (authResult.account) {
                // Prefer oid from idTokenClaims if available
                if (authResult.account.idTokenClaims?.oid) {
                    userAadObjectId = authResult.account.idTokenClaims.oid;
                }
                else if (authResult.account.homeAccountId) {
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
                    accountInfo: authResult.account, // Pass the full accountInfo if the caller might need it
                },
            };
        }
        else {
            logger.warn(`[MSTeamsService] Token acquisition yielded null/empty accessToken for user ${userId} without throwing. This is unexpected.`);
            return {
                ok: false,
                error: {
                    code: 'MSGRAPH_AUTH_UNEXPECTED_NO_TOKEN',
                    message: 'Token acquisition returned no access token unexpectedly.',
                },
            };
        }
    }
    catch (error) {
        logger.error(`[MSTeamsService] General error in getDelegatedMSGraphTokenForUser for ${userId}:`, error);
        if (error.name === 'InteractionRequiredAuthError' ||
            (error.name === 'ClientAuthError' &&
                error.errorCode === 'no_account_in_silent_request')) {
            // This error means the user needs to go through the interactive sign-in process again.
            return {
                ok: false,
                error: {
                    code: 'MSGRAPH_INTERACTION_REQUIRED',
                    message: 'User interaction required. Please re-authenticate with Microsoft Teams.',
                },
            };
        }
        return {
            ok: false,
            error: {
                code: 'MSGRAPH_AUTH_ERROR',
                message: `Failed to acquire MS Graph token for user ${userId}: ${error.message}`,
                details: error,
            },
        };
    }
}
export async function generateTeamsAuthUrl(userIdForContext, state) {
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
    }
    catch (error) {
        logger.error(`[MSTeamsService] Error generating MS Teams auth URL for context user ${userIdForContext}:`, error);
        return null;
    }
}
export async function handleTeamsAuthCallback(userId, authorizationCode) {
    const clientApp = initializeConfidentialClientApp(); // Correctly use the confidential client app
    if (!clientApp) {
        logger.error('[MSTeamsService] MSAL client not initialized, cannot handle auth callback.');
        return {
            ok: false,
            error: {
                code: 'MSGRAPH_CONFIG_ERROR',
                message: 'MSAL client not initialized.',
            },
        };
    }
    if (!MSTEAMS_TOKEN_ENCRYPTION_KEY) {
        logger.error('[MSTeamsService] MSTEAMS_TOKEN_ENCRYPTION_KEY is not configured. Cannot store tokens post callback.');
        return {
            ok: false,
            error: {
                code: 'MSGRAPH_CONFIG_ERROR',
                message: 'Token encryption key not configured for callback.',
            },
        };
    }
    if (!MSGRAPH_DELEGATED_SCOPES || MSGRAPH_DELEGATED_SCOPES.length === 0) {
        logger.error('[MSTeamsService] MSGRAPH_DELEGATED_SCOPES are not configured for callback token request.');
        return {
            ok: false,
            error: {
                code: 'MSGRAPH_CONFIG_ERROR',
                message: 'Scopes not configured for callback.',
            },
        };
    }
    if (!MSGRAPH_DELEGATED_REDIRECT_URL) {
        logger.error('[MSTeamsService] MSGRAPH_DELEGATED_REDIRECT_URL is not configured for callback token request.');
        return {
            ok: false,
            error: {
                code: 'MSGRAPH_CONFIG_ERROR',
                message: 'Redirect URL not configured for callback.',
            },
        };
    }
    try {
        const tokenRequest = {
            code: authorizationCode,
            scopes: MSGRAPH_DELEGATED_SCOPES,
            redirectUri: MSGRAPH_DELEGATED_REDIRECT_URL,
        };
        const authResult = await clientApp.acquireTokenByCode(tokenRequest);
        if (authResult && authResult.accessToken && authResult.account) {
            await storeUserMSTeamsTokens(userId, authResult); // Uses placeholder
            logger.info(`[MSTeamsService] Successfully handled MS Teams auth callback and initiated token storage for user ${userId}.`);
            return { ok: true, data: true };
        }
        else {
            logger.error(`[MSTeamsService] Failed to acquire token by code for user ${userId}. AuthResult invalid or account missing.`, authResult);
            return {
                ok: false,
                error: {
                    code: 'MSGRAPH_AUTH_CALLBACK_FAILED',
                    message: 'Could not process auth code or vital token/account info missing.',
                },
            };
        }
    }
    catch (error) {
        logger.error(`[MSTeamsService] Error in handleTeamsAuthCallback for user ${userId}:`, error);
        // Provide more specific error if MSAL gives one (e.g. invalid_grant for used/expired code)
        const errorCode = error.errorCode || 'MSGRAPH_AUTH_ERROR';
        return {
            ok: false,
            error: {
                code: errorCode,
                message: `Callback handling error: ${error.message}`,
                details: error,
            },
        };
    }
}
// Existing meeting functions need to be adapted to use getDelegatedMSGraphTokenForUser
// For example:
export async function listMicrosoftTeamsMeetings(atomUserId, // Changed from userPrincipalNameOrId to Atom's internal userId
options) {
    logger.debug(`[MSTeamsService] listMicrosoftTeamsMeetings called for Atom user: ${atomUserId}, options:`, options);
    const tokenResponse = await getDelegatedMSGraphTokenForUser(atomUserId);
    if (!tokenResponse.ok || !tokenResponse.data) {
        return {
            ok: false,
            error: tokenResponse.error || {
                code: 'MSGRAPH_AUTH_ERROR',
                message: 'Failed to obtain MS Graph access token for listing meetings.',
            },
        };
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
            headers: { Authorization: `Bearer ${token}` },
        });
        return {
            ok: true,
            data: {
                events: response.data.value,
                nextLink: response.data['@odata.nextLink'] || undefined,
            },
        };
    }
    catch (error) {
        const axiosError = error;
        logger.error(`[MSTeamsService] Error listing MS Teams meetings for Atom user ${atomUserId}:`, axiosError.message, axiosError.response?.data);
        const errorData = axiosError.response?.data;
        return {
            ok: false,
            error: {
                code: errorData?.error?.code || 'MSGRAPH_API_ERROR',
                message: errorData?.error?.message ||
                    axiosError.message ||
                    'Failed to list MS Teams meetings',
                details: errorData?.error || errorData,
            },
        };
    }
}
export async function getMicrosoftTeamsMeetingDetails(atomUserId, // Changed from userPrincipalNameOrId to Atom's internal userId
eventId) {
    logger.debug(`[MSTeamsService] getMicrosoftTeamsMeetingDetails called for Atom user: ${atomUserId}, eventId: ${eventId}`);
    const tokenResponse = await getDelegatedMSGraphTokenForUser(atomUserId);
    if (!tokenResponse.ok || !tokenResponse.data) {
        return {
            ok: false,
            error: tokenResponse.error || {
                code: 'MSGRAPH_AUTH_ERROR',
                message: 'Failed to obtain MS Graph access token for meeting details.',
            },
        };
    }
    const token = tokenResponse.data;
    const selectParams = 'id,subject,start,end,isOnlineMeeting,onlineMeeting,webLink,bodyPreview,body,attendees,location,locations,organizer';
    // Use '/me/events/{id}' for delegated permissions to get a specific event from the signed-in user's default calendar
    const requestUrl = `${MSGRAPH_API_BASE_URL}/me/events/${eventId}?$select=${selectParams}`;
    try {
        logger.debug(`[MSTeamsService] Requesting meeting details from MS Graph: ${requestUrl}`);
        const response = await axios.get(requestUrl, {
            headers: { Authorization: `Bearer ${token}` },
        });
        return { ok: true, data: response.data };
    }
    catch (error) {
        const axiosError = error;
        logger.error(`[MSTeamsService] Error getting MS Teams meeting details for event ${eventId}, Atom user ${atomUserId}:`, axiosError.message, axiosError.response?.data);
        const errorData = axiosError.response?.data;
        if (axiosError.response?.status === 404) {
            return {
                ok: false,
                error: {
                    code: 'EVENT_NOT_FOUND',
                    message: `Meeting event not found (ID: ${eventId}). Details: ${errorData?.error?.message || ''}`.trim(),
                },
            };
        }
        return {
            ok: false,
            error: {
                code: errorData?.error?.code || 'MSGRAPH_API_ERROR',
                message: errorData?.error?.message ||
                    axiosError.message ||
                    'Failed to get MS Teams meeting details',
                details: errorData?.error || errorData,
            },
        };
    }
}
/**
 * Searches Microsoft Teams messages using the Graph Search API.
 * @param atomUserId Atom's internal user ID.
 * @param searchQuery KQL query string.
 * @param maxResults Maximum number of messages to return.
 * @returns A promise resolving to an array of AgentMSTeamsMessage objects.
 */
export async function searchTeamsMessages(atomUserId, searchQuery, // This will be the KQL query string
maxResults = 20, userAadObjectId // Optional: AAD Object ID of the user for more specific queries
) {
    logger.debug(`[MSTeamsService] searchTeamsMessages called for Atom user ${atomUserId}, query: "${searchQuery}", maxResults: ${maxResults}, userAadObjectId: ${userAadObjectId}`);
    const tokenResponse = await getDelegatedMSGraphTokenForUser(atomUserId);
    if (!tokenResponse.ok || !tokenResponse.data) {
        return {
            ok: false,
            error: tokenResponse.error || {
                code: 'MSGRAPH_AUTH_ERROR',
                message: 'Failed to obtain MS Graph token for searching messages.',
            },
        };
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
                sortProperties: [{ name: 'createdDateTime', isDescending: true }],
            },
        ],
    };
    const requestUrl = `${MSGRAPH_API_BASE_URL}/search/query`;
    try {
        // Log the actual KQL query being sent to Graph API
        logger.info(`[MSTeamsService] Executing Graph Search API with KQL: "${searchQuery}" for user ${atomUserId}`);
        const response = await axios.post(requestUrl, searchRequest, {
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
        });
        const messages = [];
        if (response.data &&
            response.data.value &&
            response.data.value.length > 0) {
            const searchHitsContainers = response.data.value[0]?.hitsContainers;
            if (searchHitsContainers && searchHitsContainers.length > 0) {
                searchHitsContainers.forEach((container) => {
                    if (container.hits) {
                        container.hits.forEach((hit) => {
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
    }
    catch (error) {
        const axiosError = error;
        logger.error(`[MSTeamsService] Error searching Teams messages for Atom user ${atomUserId}:`, axiosError.message, axiosError.response?.data);
        const errorData = axiosError.response?.data;
        return {
            ok: false,
            error: {
                code: errorData?.error?.code || 'MSGRAPH_SEARCH_API_ERROR',
                message: errorData?.error?.message ||
                    axiosError.message ||
                    'Failed to search Teams messages',
                details: errorData?.error || errorData,
            },
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
export async function getTeamsChatMessageContent(atomUserId, chatId, messageId) {
    logger.debug(`[MSTeamsService] getTeamsChatMessageContent for user ${atomUserId}, chatId: ${chatId}, messageId: ${messageId}`);
    const tokenResponse = await getDelegatedMSGraphTokenForUser(atomUserId);
    if (!tokenResponse.ok || !tokenResponse.data)
        return { ok: false, error: tokenResponse.error };
    const token = tokenResponse.data;
    // The fields selected here should match the AgentMSTeamsMessage interface
    const selectFields = 'id,replyToId,from,body,createdDateTime,lastModifiedDateTime,webUrl,attachments,mentions,chatId';
    const requestUrl = `${MSGRAPH_API_BASE_URL}/me/chats/${chatId}/messages/${messageId}?$select=${selectFields}`;
    try {
        const response = await axios.get(requestUrl, {
            headers: { Authorization: `Bearer ${token}` },
        });
        const rawMsg = response.data;
        const message = {
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
            attachments: rawMsg.attachments?.map((att) => ({
                id: att.id,
                name: att.name,
                contentType: att.contentType,
                contentUrl: att.contentUrl,
                size: att.size,
            })),
            mentions: rawMsg.mentions?.map((men) => ({
                id: men.id,
                mentionText: men.mentionText,
                mentioned: men.mentioned,
            })),
            raw: rawMsg,
        };
        return { ok: true, data: message };
    }
    catch (error) {
        const axiosError = error;
        logger.error(`[MSTeamsService] Error getting chat message content (chat ${chatId}, msg ${messageId}):`, axiosError.message, axiosError.response?.data);
        const errorData = axiosError.response?.data;
        if (axiosError.response?.status === 404)
            return {
                ok: false,
                error: {
                    code: 'MSGRAPH_MESSAGE_NOT_FOUND',
                    message: 'Chat message not found.',
                },
            };
        return {
            ok: false,
            error: {
                code: errorData?.error?.code || 'MSGRAPH_API_ERROR',
                message: errorData?.error?.message || 'Failed to get chat message content',
            },
        };
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
export async function getTeamsChannelMessageContent(atomUserId, teamId, channelId, messageId) {
    logger.debug(`[MSTeamsService] getTeamsChannelMessageContent for user ${atomUserId}, team ${teamId}, channel ${channelId}, msg ${messageId}`);
    const tokenResponse = await getDelegatedMSGraphTokenForUser(atomUserId);
    if (!tokenResponse.ok || !tokenResponse.data)
        return { ok: false, error: tokenResponse.error };
    const token = tokenResponse.data;
    const selectFields = 'id,replyToId,from,body,createdDateTime,lastModifiedDateTime,webUrl,attachments,mentions,channelIdentity';
    const requestUrl = `${MSGRAPH_API_BASE_URL}/teams/${teamId}/channels/${channelId}/messages/${messageId}?$select=${selectFields}`;
    try {
        const response = await axios.get(requestUrl, {
            headers: { Authorization: `Bearer ${token}` },
        });
        const rawMsg = response.data;
        const message = {
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
            attachments: rawMsg.attachments?.map((att) => ({
                id: att.id,
                name: att.name,
                contentType: att.contentType,
                contentUrl: att.contentUrl,
                size: att.size,
            })),
            mentions: rawMsg.mentions?.map((men) => ({
                id: men.id,
                mentionText: men.mentionText,
                mentioned: men.mentioned,
            })),
            raw: rawMsg,
        };
        return { ok: true, data: message };
    }
    catch (error) {
        const axiosError = error;
        logger.error(`[MSTeamsService] Error getting channel message content (team ${teamId}, channel ${channelId}, msg ${messageId}):`, axiosError.message, axiosError.response?.data);
        const errorData = axiosError.response?.data;
        if (axiosError.response?.status === 404)
            return {
                ok: false,
                error: {
                    code: 'MSGRAPH_MESSAGE_NOT_FOUND',
                    message: 'Channel message not found.',
                },
            };
        return {
            ok: false,
            error: {
                code: errorData?.error?.code || 'MSGRAPH_API_ERROR',
                message: errorData?.error?.message || 'Failed to get channel message content',
            },
        };
    }
}
// Note: getTeamsMessagePermalink is implicitly handled by the `webUrl` property
// in the AgentMSTeamsMessage when messages are fetched. No separate function needed
// unless a specific API call for permalink generation is preferred or required for some edge cases.
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic2VydmljZS5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInNlcnZpY2UudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxLQUFxQixNQUFNLE9BQU8sQ0FBQztBQUMxQyxPQUFPLEVBQ0wsNkJBQTZCLEVBRzdCLFFBQVEsR0FLVCxNQUFNLGtCQUFrQixDQUFDLENBQUMsa0RBQWtEO0FBRTdFLE9BQU87QUFDTCxxRUFBcUU7QUFDckUsNkVBQTZFO0FBQzdFLHFFQUFxRTtBQUNyRSxxRUFBcUU7QUFDckUsK0RBQStEO0FBQy9ELG1HQUFtRztBQUNuRywyQkFBMkIsRUFDM0IsK0JBQStCLEVBQy9CLDJCQUEyQixFQUMzQiw4QkFBOEIsRUFDOUIsd0JBQXdCLEVBQ3hCLDRCQUE0QixHQUM3QixNQUFNLCtCQUErQixDQUFDLENBQUMsb0RBQW9EO0FBTzVGLE9BQU8sRUFBRSxNQUFNLEVBQUUsTUFBTSxrQkFBa0IsQ0FBQztBQUMxQyxPQUFPLEVBQUUsd0JBQXdCLEVBQUUsTUFBTSxxQkFBcUIsQ0FBQztBQUMvRCwrR0FBK0c7QUFFL0csTUFBTSxvQkFBb0IsR0FBRyxrQ0FBa0MsQ0FBQztBQUVoRSw4REFBOEQ7QUFDOUQsSUFBSSx5QkFBeUIsR0FBeUMsSUFBSSxDQUFDO0FBRTNFLHlGQUF5RjtBQUN6Rix5RUFBeUU7QUFDekUsOEJBQThCO0FBQzlCLGtDQUFrQztBQUNsQywyQ0FBMkM7QUFDM0MsMkRBQTJEO0FBQzNELGdDQUFnQztBQUNoQyxJQUFJO0FBRUosMkNBQTJDO0FBQzNDLGlHQUFpRztBQUNqRyxNQUFNLDBCQUEwQixHQUFHLEtBQUssRUFDdEMsTUFBYyxFQUNrRCxFQUFFO0lBQ2xFLE1BQU0sQ0FBQyxLQUFLLENBQ1Ysd0VBQXdFLE1BQU0sR0FBRyxDQUNsRixDQUFDO0lBQ0YsTUFBTSxXQUFXLEdBQUcsd0JBQXdCLEVBQUUsQ0FBQztJQUMvQyxNQUFNLEtBQUssR0FBRzs7Ozs7OztHQU9iLENBQUM7SUFDRixJQUFJLENBQUM7UUFDSCxNQUFNLElBQUksR0FBRyxNQUFNLFdBQVcsQ0FBQyxPQUFPLENBQUMsS0FBSyxFQUFFLEVBQUUsTUFBTSxFQUFFLENBQUMsQ0FBQztRQUMxRCxJQUFJLElBQUksQ0FBQyxXQUFXLElBQUksSUFBSSxDQUFDLFdBQVcsQ0FBQyxNQUFNLEdBQUcsQ0FBQyxFQUFFLENBQUM7WUFDcEQsTUFBTSxXQUFXLEdBQUcsSUFBSSxDQUFDLFdBQVcsQ0FBQyxDQUFDLENBQUMsQ0FBQztZQUN4QyxJQUFJLENBQUMsV0FBVyxDQUFDLGFBQWEsSUFBSSxDQUFDLFdBQVcsQ0FBQyxZQUFZO2dCQUFFLE9BQU8sSUFBSSxDQUFDO1lBQ3pFLE1BQU0sWUFBWSxHQUFHLE9BQU8sQ0FDMUIsV0FBVyxDQUFDLGFBQWEsRUFDekIsNEJBQTZCLENBQzlCLENBQUM7WUFDRixNQUFNLE9BQU8sR0FBRyxJQUFJLENBQUMsS0FBSyxDQUFDLFdBQVcsQ0FBQyxZQUFZLENBQWdCLENBQUM7WUFDcEUsT0FBTyxFQUFFLFlBQVksRUFBRSxPQUFPLEVBQUUsQ0FBQztRQUNuQyxDQUFDO0lBQ0gsQ0FBQztJQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7UUFDZixNQUFNLENBQUMsS0FBSyxDQUNWLDREQUE0RCxNQUFNLEdBQUcsRUFDckUsS0FBSyxDQUNOLENBQUM7SUFDSixDQUFDO0lBQ0QsT0FBTyxJQUFJLENBQUM7QUFDZCxDQUFDLENBQUM7QUFFRixNQUFNLHNCQUFzQixHQUFHLEtBQUssRUFDbEMsTUFBYyxFQUNkLFVBQWdDLEVBQ2pCLEVBQUU7SUFDakIsTUFBTSxDQUFDLEtBQUssQ0FBQyxxREFBcUQsTUFBTSxHQUFHLENBQUMsQ0FBQztJQUM3RSxJQUFJLENBQUMsVUFBVSxDQUFDLE9BQU8sRUFBRSxDQUFDO1FBQ3hCLE1BQU0sQ0FBQyxLQUFLLENBQ1YscUZBQXFGLENBQ3RGLENBQUM7UUFDRixNQUFNLElBQUksS0FBSyxDQUFDLDRDQUE0QyxDQUFDLENBQUM7SUFDaEUsQ0FBQztJQUNELE1BQU0sV0FBVyxHQUFHLE9BQU8sQ0FDekIsVUFBVSxDQUFDLFdBQVcsRUFDdEIsNEJBQTZCLENBQzlCLENBQUM7SUFDRixNQUFNLFlBQVksR0FBRyxVQUFVLENBQUMsWUFBWTtRQUMxQyxDQUFDLENBQUMsT0FBTyxDQUFDLFVBQVUsQ0FBQyxZQUFZLEVBQUUsNEJBQTZCLENBQUM7UUFDakUsQ0FBQyxDQUFDLElBQUksQ0FBQztJQUNULE1BQU0sV0FBVyxHQUFHLElBQUksQ0FBQyxTQUFTLENBQUMsVUFBVSxDQUFDLE9BQU8sQ0FBQyxDQUFDO0lBQ3ZELE1BQU0sTUFBTSxHQUFHLFVBQVUsQ0FBQyxTQUFTLENBQUM7SUFFcEMsTUFBTSxXQUFXLEdBQUcsd0JBQXdCLEVBQUUsQ0FBQztJQUMvQyxNQUFNLFFBQVEsR0FBRzs7Ozs7O0dBTWhCLENBQUM7SUFDRixJQUFJLENBQUM7UUFDSCxNQUFNLFdBQVcsQ0FBQyxPQUFPLENBQUMsUUFBUSxFQUFFO1lBQ2xDLE1BQU07WUFDTixXQUFXO1lBQ1gsWUFBWTtZQUNaLFdBQVc7WUFDWCxNQUFNO1NBQ1AsQ0FBQyxDQUFDO1FBQ0gsTUFBTSxDQUFDLElBQUksQ0FDVCxvQ0FBb0MsTUFBTSwrQkFBK0IsQ0FDMUUsQ0FBQztJQUNKLENBQUM7SUFBQyxPQUFPLEtBQUssRUFBRSxDQUFDO1FBQ2YsTUFBTSxDQUFDLEtBQUssQ0FDViwyREFBMkQsTUFBTSxHQUFHLEVBQ3BFLEtBQUssQ0FDTixDQUFDO0lBQ0osQ0FBQztBQUNILENBQUMsQ0FBQztBQUVGLFNBQVMsK0JBQStCO0lBQ3RDLElBQUkseUJBQXlCLEVBQUUsQ0FBQztRQUM5QixPQUFPLHlCQUF5QixDQUFDO0lBQ25DLENBQUM7SUFFRCxJQUNFLENBQUMsMkJBQTJCO1FBQzVCLENBQUMsMkJBQTJCO1FBQzVCLENBQUMsK0JBQStCLEVBQ2hDLENBQUM7UUFDRCxNQUFNLENBQUMsS0FBSyxDQUNWLGtGQUFrRixDQUNuRixDQUFDO1FBQ0YsT0FBTyxJQUFJLENBQUM7SUFDZCxDQUFDO0lBQ0QsSUFBSSxDQUFDLDRCQUE0QixFQUFFLENBQUM7UUFDbEMsb0dBQW9HO1FBQ3BHLE1BQU0sQ0FBQyxLQUFLLENBQ1Ysd0dBQXdHLENBQ3pHLENBQUM7UUFDRiwwRUFBMEU7UUFDMUUsdURBQXVEO1FBQ3ZELE9BQU8sSUFBSSxDQUFDO0lBQ2QsQ0FBQztJQUVELE1BQU0sVUFBVSxHQUFrQjtRQUNoQyxJQUFJLEVBQUU7WUFDSixRQUFRLEVBQUUsMkJBQTJCO1lBQ3JDLFNBQVMsRUFBRSwyQkFBMkI7WUFDdEMsWUFBWSxFQUFFLCtCQUErQjtTQUM5QztRQUNELE1BQU0sRUFBRTtZQUNOLGFBQWEsRUFBRTtnQkFDYixjQUFjLENBQUMsUUFBUSxFQUFFLE9BQU8sRUFBRSxXQUFXO29CQUMzQyw0Q0FBNEM7b0JBQzVDLElBQUksQ0FBQyxXQUFXO3dCQUNkLE1BQU0sQ0FBQyxLQUFLLENBQUMsU0FBUyxRQUFRLENBQUMsUUFBUSxDQUFDLEtBQUssT0FBTyxFQUFFLENBQUMsQ0FBQztnQkFDNUQsQ0FBQztnQkFDRCxpQkFBaUIsRUFBRSxLQUFLLEVBQUUscURBQXFEO2dCQUMvRSxRQUFRLEVBQUUsUUFBUSxDQUFDLE9BQU8sRUFBRSxrREFBa0Q7YUFDL0U7U0FDRjtLQUNGLENBQUM7SUFDRix5QkFBeUIsR0FBRyxJQUFJLDZCQUE2QixDQUFDLFVBQVUsQ0FBQyxDQUFDO0lBQzFFLE1BQU0sQ0FBQyxJQUFJLENBQ1QscUZBQXFGLENBQ3RGLENBQUM7SUFDRixPQUFPLHlCQUF5QixDQUFDO0FBQ25DLENBQUM7QUFTRCxNQUFNLENBQUMsS0FBSyxVQUFVLCtCQUErQixDQUNuRCxNQUFjO0lBRWQsTUFBTSxTQUFTLEdBQUcsK0JBQStCLEVBQUUsQ0FBQztJQUNwRCxJQUFJLENBQUMsU0FBUyxFQUFFLENBQUM7UUFDZixNQUFNLFFBQVEsR0FBRyxtREFBbUQsQ0FBQztRQUNyRSxNQUFNLENBQUMsS0FBSyxDQUFDLG9CQUFvQixRQUFRLEVBQUUsQ0FBQyxDQUFDO1FBQzdDLE9BQU87WUFDTCxFQUFFLEVBQUUsS0FBSztZQUNULEtBQUssRUFBRSxFQUFFLElBQUksRUFBRSxzQkFBc0IsRUFBRSxPQUFPLEVBQUUsUUFBUSxFQUFFO1NBQzNELENBQUM7SUFDSixDQUFDO0lBRUQsSUFBSSxDQUFDLDRCQUE0QixFQUFFLENBQUM7UUFDbEMsTUFBTSxDQUFDLEtBQUssQ0FDViw2RkFBNkYsQ0FDOUYsQ0FBQztRQUNGLE9BQU87WUFDTCxFQUFFLEVBQUUsS0FBSztZQUNULEtBQUssRUFBRTtnQkFDTCxJQUFJLEVBQUUsc0JBQXNCO2dCQUM1QixPQUFPLEVBQUUsc0NBQXNDO2FBQ2hEO1NBQ0YsQ0FBQztJQUNKLENBQUM7SUFFRCxNQUFNLGVBQWUsR0FBRyxNQUFNLDBCQUEwQixDQUFDLE1BQU0sQ0FBQyxDQUFDO0lBQ2pFLElBQ0UsQ0FBQyxlQUFlO1FBQ2hCLENBQUMsZUFBZSxDQUFDLE9BQU87UUFDeEIsQ0FBQyxlQUFlLENBQUMsWUFBWSxFQUM3QixDQUFDO1FBQ0QsTUFBTSxDQUFDLElBQUksQ0FDVCw4RUFBOEUsTUFBTSwrQkFBK0IsQ0FDcEgsQ0FBQztRQUNGLE9BQU87WUFDTCxFQUFFLEVBQUUsS0FBSztZQUNULEtBQUssRUFBRTtnQkFDTCxJQUFJLEVBQUUsdUJBQXVCO2dCQUM3QixPQUFPLEVBQ0wsK0VBQStFO2FBQ2xGO1NBQ0YsQ0FBQztJQUNKLENBQUM7SUFFRCxJQUFJLENBQUM7UUFDSCxxRUFBcUU7UUFDckUsbUZBQW1GO1FBQ25GLE1BQU0sYUFBYSxHQUFzQjtZQUN2QyxPQUFPLEVBQUUsZUFBZSxDQUFDLE9BQU8sRUFBRSx3REFBd0Q7WUFDMUYsTUFBTSxFQUFFLHdCQUF5QixFQUFFLHdDQUF3QztZQUMzRSxZQUFZLEVBQUUsS0FBSyxFQUFFLHlFQUF5RTtTQUMvRixDQUFDO1FBRUYsSUFBSSxVQUFVLEdBQWdDLElBQUksQ0FBQztRQUNuRCxJQUFJLENBQUM7WUFDSCxNQUFNLENBQUMsS0FBSyxDQUNWLGtFQUFrRSxNQUFNLGlCQUFpQixlQUFlLENBQUMsT0FBTyxDQUFDLGFBQWEsRUFBRSxDQUNqSSxDQUFDO1lBQ0YsVUFBVSxHQUFHLE1BQU0sU0FBUyxDQUFDLGtCQUFrQixDQUFDLGFBQWEsQ0FBQyxDQUFDO1FBQ2pFLENBQUM7UUFBQyxPQUFPLEtBQVUsRUFBRSxDQUFDO1lBQ3BCLE1BQU0sQ0FBQyxJQUFJLENBQ1QsNkRBQTZELE1BQU0sWUFBWSxLQUFLLENBQUMsU0FBUyxJQUFJLEtBQUssQ0FBQyxJQUFJLCtEQUErRCxDQUM1SyxDQUFDO1lBQ0YsMkZBQTJGO1lBQzNGLHlGQUF5RjtZQUN6RixJQUNFLEtBQUssQ0FBQyxJQUFJLEtBQUssaUJBQWlCO2dCQUNoQyxDQUFDLEtBQUssQ0FBQyxTQUFTLEtBQUssaUJBQWlCO29CQUNwQyxLQUFLLENBQUMsU0FBUyxLQUFLLHFCQUFxQjtvQkFDekMsS0FBSyxDQUFDLE9BQU8sRUFBRSxRQUFRLENBQ3JCLHdGQUF3RixDQUN6RixDQUFDLEVBQ0osQ0FBQztnQkFDRCxzR0FBc0c7Z0JBQ3RHLElBQUksQ0FBQztvQkFDSCxNQUFNLENBQUMsSUFBSSxDQUNULG1FQUFtRSxNQUFNLEdBQUcsQ0FDN0UsQ0FBQztvQkFDRixNQUFNLG1CQUFtQixHQUFHO3dCQUMxQixZQUFZLEVBQUUsZUFBZSxDQUFDLFlBQVk7d0JBQzFDLE1BQU0sRUFBRSx3QkFBeUI7cUJBQ2xDLENBQUM7b0JBQ0YsVUFBVTt3QkFDUixNQUFNLFNBQVMsQ0FBQywwQkFBMEIsQ0FBQyxtQkFBbUIsQ0FBQyxDQUFDO2dCQUNwRSxDQUFDO2dCQUFDLE9BQU8sWUFBaUIsRUFBRSxDQUFDO29CQUMzQixNQUFNLENBQUMsS0FBSyxDQUNWLHNFQUFzRSxNQUFNLEdBQUcsRUFDL0UsWUFBWSxDQUNiLENBQUM7b0JBQ0YseUVBQXlFO29CQUN6RSxJQUNFLFlBQVksQ0FBQyxJQUFJLEtBQUssOEJBQThCO3dCQUNwRCxZQUFZLENBQUMsU0FBUyxLQUFLLGVBQWU7d0JBQzFDLFlBQVksQ0FBQyxPQUFPLEVBQUUsUUFBUSxDQUFDLGFBQWEsQ0FBQyxFQUM3QyxDQUFDO3dCQUNELDJCQUEyQjt3QkFDM0IsT0FBTzs0QkFDTCxFQUFFLEVBQUUsS0FBSzs0QkFDVCxLQUFLLEVBQUU7Z0NBQ0wsSUFBSSxFQUFFLDhCQUE4QjtnQ0FDcEMsT0FBTyxFQUNMLG1GQUFtRjs2QkFDdEY7eUJBQ0YsQ0FBQztvQkFDSixDQUFDO29CQUNELE9BQU87d0JBQ0wsRUFBRSxFQUFFLEtBQUs7d0JBQ1QsS0FBSyxFQUFFOzRCQUNMLElBQUksRUFBRSx3QkFBd0I7NEJBQzlCLE9BQU8sRUFBRSw0QkFBNEIsWUFBWSxDQUFDLE9BQU8sRUFBRTs0QkFDM0QsT0FBTyxFQUFFLFlBQVk7eUJBQ3RCO3FCQUNGLENBQUM7Z0JBQ0osQ0FBQztZQUNILENBQUM7aUJBQU0sQ0FBQztnQkFDTixNQUFNLEtBQUssQ0FBQyxDQUFDLG9FQUFvRTtZQUNuRixDQUFDO1FBQ0gsQ0FBQztRQUVELElBQUksVUFBVSxJQUFJLFVBQVUsQ0FBQyxXQUFXLEVBQUUsQ0FBQztZQUN6QyxrSEFBa0g7WUFDbEgsTUFBTSxzQkFBc0IsQ0FBQyxNQUFNLEVBQUUsVUFBVSxDQUFDLENBQUM7WUFDakQsTUFBTSxDQUFDLElBQUksQ0FDVCxtRUFBbUUsTUFBTSxHQUFHLENBQzdFLENBQUM7WUFFRixJQUFJLGVBQWUsR0FBa0IsSUFBSSxDQUFDO1lBQzFDLElBQUksaUJBQWlCLEdBQWtCLElBQUksQ0FBQztZQUU1QyxJQUFJLFVBQVUsQ0FBQyxPQUFPLEVBQUUsQ0FBQztnQkFDdkIsNkNBQTZDO2dCQUM3QyxJQUFJLFVBQVUsQ0FBQyxPQUFPLENBQUMsYUFBYSxFQUFFLEdBQUcsRUFBRSxDQUFDO29CQUMxQyxlQUFlLEdBQUcsVUFBVSxDQUFDLE9BQU8sQ0FBQyxhQUFhLENBQUMsR0FBRyxDQUFDO2dCQUN6RCxDQUFDO3FCQUFNLElBQUksVUFBVSxDQUFDLE9BQU8sQ0FBQyxhQUFhLEVBQUUsQ0FBQztvQkFDNUMsdUNBQXVDO29CQUN2QyxlQUFlLEdBQUcsVUFBVSxDQUFDLE9BQU8sQ0FBQyxhQUFhLENBQUMsS0FBSyxDQUFDLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDO2dCQUNuRSxDQUFDO2dCQUNELGlCQUFpQixHQUFHLFVBQVUsQ0FBQyxPQUFPLENBQUMsUUFBUSxDQUFDLENBQUMsY0FBYztnQkFFL0QsTUFBTSxDQUFDLElBQUksQ0FDVCx1Q0FBdUMsZUFBZSxVQUFVLGlCQUFpQixtQ0FBbUMsTUFBTSxHQUFHLENBQzlILENBQUM7Z0JBRUYsK0VBQStFO2dCQUMvRSwrRUFBK0U7Z0JBQy9FLHVFQUF1RTtnQkFDdkUsK0NBQStDO2dCQUMvQyw2RUFBNkU7WUFDL0UsQ0FBQztZQUVELE9BQU87Z0JBQ0wsRUFBRSxFQUFFLElBQUk7Z0JBQ1IsSUFBSSxFQUFFO29CQUNKLFdBQVcsRUFBRSxVQUFVLENBQUMsV0FBVztvQkFDbkMsZUFBZSxFQUFFLGVBQWU7b0JBQ2hDLGlCQUFpQixFQUFFLGlCQUFpQjtvQkFDcEMsV0FBVyxFQUFFLFVBQVUsQ0FBQyxPQUFPLEVBQUUsd0RBQXdEO2lCQUMxRjthQUNGLENBQUM7UUFDSixDQUFDO2FBQU0sQ0FBQztZQUNOLE1BQU0sQ0FBQyxJQUFJLENBQ1QsOEVBQThFLE1BQU0sd0NBQXdDLENBQzdILENBQUM7WUFDRixPQUFPO2dCQUNMLEVBQUUsRUFBRSxLQUFLO2dCQUNULEtBQUssRUFBRTtvQkFDTCxJQUFJLEVBQUUsa0NBQWtDO29CQUN4QyxPQUFPLEVBQUUsMERBQTBEO2lCQUNwRTthQUNGLENBQUM7UUFDSixDQUFDO0lBQ0gsQ0FBQztJQUFDLE9BQU8sS0FBVSxFQUFFLENBQUM7UUFDcEIsTUFBTSxDQUFDLEtBQUssQ0FDVix5RUFBeUUsTUFBTSxHQUFHLEVBQ2xGLEtBQUssQ0FDTixDQUFDO1FBQ0YsSUFDRSxLQUFLLENBQUMsSUFBSSxLQUFLLDhCQUE4QjtZQUM3QyxDQUFDLEtBQUssQ0FBQyxJQUFJLEtBQUssaUJBQWlCO2dCQUMvQixLQUFLLENBQUMsU0FBUyxLQUFLLDhCQUE4QixDQUFDLEVBQ3JELENBQUM7WUFDRCx1RkFBdUY7WUFDdkYsT0FBTztnQkFDTCxFQUFFLEVBQUUsS0FBSztnQkFDVCxLQUFLLEVBQUU7b0JBQ0wsSUFBSSxFQUFFLDhCQUE4QjtvQkFDcEMsT0FBTyxFQUNMLHlFQUF5RTtpQkFDNUU7YUFDRixDQUFDO1FBQ0osQ0FBQztRQUNELE9BQU87WUFDTCxFQUFFLEVBQUUsS0FBSztZQUNULEtBQUssRUFBRTtnQkFDTCxJQUFJLEVBQUUsb0JBQW9CO2dCQUMxQixPQUFPLEVBQUUsNkNBQTZDLE1BQU0sS0FBSyxLQUFLLENBQUMsT0FBTyxFQUFFO2dCQUNoRixPQUFPLEVBQUUsS0FBSzthQUNmO1NBQ0YsQ0FBQztJQUNKLENBQUM7QUFDSCxDQUFDO0FBRUQsTUFBTSxDQUFDLEtBQUssVUFBVSxvQkFBb0IsQ0FDeEMsZ0JBQXdCLEVBQ3hCLEtBQWM7SUFFZCxNQUFNLFNBQVMsR0FBRywrQkFBK0IsRUFBRSxDQUFDLENBQUMsNENBQTRDO0lBQ2pHLElBQUksQ0FBQyxTQUFTLEVBQUUsQ0FBQztRQUNmLE1BQU0sQ0FBQyxLQUFLLENBQ1YseUVBQXlFLENBQzFFLENBQUM7UUFDRixPQUFPLElBQUksQ0FBQztJQUNkLENBQUM7SUFFRCxJQUFJLENBQUMsd0JBQXdCLElBQUksd0JBQXdCLENBQUMsTUFBTSxLQUFLLENBQUMsRUFBRSxDQUFDO1FBQ3ZFLE1BQU0sQ0FBQyxLQUFLLENBQ1YsK0RBQStELENBQ2hFLENBQUM7UUFDRixPQUFPLElBQUksQ0FBQztJQUNkLENBQUM7SUFDRCxJQUFJLENBQUMsOEJBQThCLEVBQUUsQ0FBQztRQUNwQyxNQUFNLENBQUMsS0FBSyxDQUNWLG9FQUFvRSxDQUNyRSxDQUFDO1FBQ0YsT0FBTyxJQUFJLENBQUM7SUFDZCxDQUFDO0lBRUQsSUFBSSxDQUFDO1FBQ0gsTUFBTSxxQkFBcUIsR0FBRztZQUM1QixNQUFNLEVBQUUsd0JBQXdCO1lBQ2hDLFdBQVcsRUFBRSw4QkFBOEI7WUFDM0MsS0FBSyxFQUFFLEtBQUssRUFBRSxvR0FBb0c7U0FDbkgsQ0FBQztRQUNGLE1BQU0sT0FBTyxHQUFHLE1BQU0sU0FBUyxDQUFDLGNBQWMsQ0FBQyxxQkFBcUIsQ0FBQyxDQUFDO1FBQ3RFLE1BQU0sQ0FBQyxJQUFJLENBQ1Qsa0VBQWtFLGdCQUFnQixHQUFHLENBQ3RGLENBQUM7UUFDRixPQUFPLE9BQU8sQ0FBQztJQUNqQixDQUFDO0lBQUMsT0FBTyxLQUFVLEVBQUUsQ0FBQztRQUNwQixNQUFNLENBQUMsS0FBSyxDQUNWLHdFQUF3RSxnQkFBZ0IsR0FBRyxFQUMzRixLQUFLLENBQ04sQ0FBQztRQUNGLE9BQU8sSUFBSSxDQUFDO0lBQ2QsQ0FBQztBQUNILENBQUM7QUFFRCxNQUFNLENBQUMsS0FBSyxVQUFVLHVCQUF1QixDQUMzQyxNQUFjLEVBQ2QsaUJBQXlCO0lBRXpCLE1BQU0sU0FBUyxHQUFHLCtCQUErQixFQUFFLENBQUMsQ0FBQyw0Q0FBNEM7SUFDakcsSUFBSSxDQUFDLFNBQVMsRUFBRSxDQUFDO1FBQ2YsTUFBTSxDQUFDLEtBQUssQ0FDViw0RUFBNEUsQ0FDN0UsQ0FBQztRQUNGLE9BQU87WUFDTCxFQUFFLEVBQUUsS0FBSztZQUNULEtBQUssRUFBRTtnQkFDTCxJQUFJLEVBQUUsc0JBQXNCO2dCQUM1QixPQUFPLEVBQUUsOEJBQThCO2FBQ3hDO1NBQ0YsQ0FBQztJQUNKLENBQUM7SUFFRCxJQUFJLENBQUMsNEJBQTRCLEVBQUUsQ0FBQztRQUNsQyxNQUFNLENBQUMsS0FBSyxDQUNWLHFHQUFxRyxDQUN0RyxDQUFDO1FBQ0YsT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxzQkFBc0I7Z0JBQzVCLE9BQU8sRUFBRSxtREFBbUQ7YUFDN0Q7U0FDRixDQUFDO0lBQ0osQ0FBQztJQUNELElBQUksQ0FBQyx3QkFBd0IsSUFBSSx3QkFBd0IsQ0FBQyxNQUFNLEtBQUssQ0FBQyxFQUFFLENBQUM7UUFDdkUsTUFBTSxDQUFDLEtBQUssQ0FDViwwRkFBMEYsQ0FDM0YsQ0FBQztRQUNGLE9BQU87WUFDTCxFQUFFLEVBQUUsS0FBSztZQUNULEtBQUssRUFBRTtnQkFDTCxJQUFJLEVBQUUsc0JBQXNCO2dCQUM1QixPQUFPLEVBQUUscUNBQXFDO2FBQy9DO1NBQ0YsQ0FBQztJQUNKLENBQUM7SUFDRCxJQUFJLENBQUMsOEJBQThCLEVBQUUsQ0FBQztRQUNwQyxNQUFNLENBQUMsS0FBSyxDQUNWLCtGQUErRixDQUNoRyxDQUFDO1FBQ0YsT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxzQkFBc0I7Z0JBQzVCLE9BQU8sRUFBRSwyQ0FBMkM7YUFDckQ7U0FDRixDQUFDO0lBQ0osQ0FBQztJQUVELElBQUksQ0FBQztRQUNILE1BQU0sWUFBWSxHQUE2QjtZQUM3QyxJQUFJLEVBQUUsaUJBQWlCO1lBQ3ZCLE1BQU0sRUFBRSx3QkFBd0I7WUFDaEMsV0FBVyxFQUFFLDhCQUE4QjtTQUM1QyxDQUFDO1FBQ0YsTUFBTSxVQUFVLEdBQUcsTUFBTSxTQUFTLENBQUMsa0JBQWtCLENBQUMsWUFBWSxDQUFDLENBQUM7UUFFcEUsSUFBSSxVQUFVLElBQUksVUFBVSxDQUFDLFdBQVcsSUFBSSxVQUFVLENBQUMsT0FBTyxFQUFFLENBQUM7WUFDL0QsTUFBTSxzQkFBc0IsQ0FBQyxNQUFNLEVBQUUsVUFBVSxDQUFDLENBQUMsQ0FBQyxtQkFBbUI7WUFDckUsTUFBTSxDQUFDLElBQUksQ0FDVCxxR0FBcUcsTUFBTSxHQUFHLENBQy9HLENBQUM7WUFDRixPQUFPLEVBQUUsRUFBRSxFQUFFLElBQUksRUFBRSxJQUFJLEVBQUUsSUFBSSxFQUFFLENBQUM7UUFDbEMsQ0FBQzthQUFNLENBQUM7WUFDTixNQUFNLENBQUMsS0FBSyxDQUNWLDZEQUE2RCxNQUFNLDBDQUEwQyxFQUM3RyxVQUFVLENBQ1gsQ0FBQztZQUNGLE9BQU87Z0JBQ0wsRUFBRSxFQUFFLEtBQUs7Z0JBQ1QsS0FBSyxFQUFFO29CQUNMLElBQUksRUFBRSw4QkFBOEI7b0JBQ3BDLE9BQU8sRUFDTCxrRUFBa0U7aUJBQ3JFO2FBQ0YsQ0FBQztRQUNKLENBQUM7SUFDSCxDQUFDO0lBQUMsT0FBTyxLQUFVLEVBQUUsQ0FBQztRQUNwQixNQUFNLENBQUMsS0FBSyxDQUNWLDhEQUE4RCxNQUFNLEdBQUcsRUFDdkUsS0FBSyxDQUNOLENBQUM7UUFDRiwyRkFBMkY7UUFDM0YsTUFBTSxTQUFTLEdBQUcsS0FBSyxDQUFDLFNBQVMsSUFBSSxvQkFBb0IsQ0FBQztRQUMxRCxPQUFPO1lBQ0wsRUFBRSxFQUFFLEtBQUs7WUFDVCxLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLFNBQVM7Z0JBQ2YsT0FBTyxFQUFFLDRCQUE0QixLQUFLLENBQUMsT0FBTyxFQUFFO2dCQUNwRCxPQUFPLEVBQUUsS0FBSzthQUNmO1NBQ0YsQ0FBQztJQUNKLENBQUM7QUFDSCxDQUFDO0FBRUQsdUZBQXVGO0FBQ3ZGLGVBQWU7QUFDZixNQUFNLENBQUMsS0FBSyxVQUFVLDBCQUEwQixDQUM5QyxVQUFrQixFQUFFLCtEQUErRDtBQUNuRixPQUlDO0lBRUQsTUFBTSxDQUFDLEtBQUssQ0FDVixxRUFBcUUsVUFBVSxZQUFZLEVBQzNGLE9BQU8sQ0FDUixDQUFDO0lBRUYsTUFBTSxhQUFhLEdBQUcsTUFBTSwrQkFBK0IsQ0FBQyxVQUFVLENBQUMsQ0FBQztJQUN4RSxJQUFJLENBQUMsYUFBYSxDQUFDLEVBQUUsSUFBSSxDQUFDLGFBQWEsQ0FBQyxJQUFJLEVBQUUsQ0FBQztRQUM3QyxPQUFPO1lBQ0wsRUFBRSxFQUFFLEtBQUs7WUFDVCxLQUFLLEVBQUUsYUFBYSxDQUFDLEtBQUssSUFBSTtnQkFDNUIsSUFBSSxFQUFFLG9CQUFvQjtnQkFDMUIsT0FBTyxFQUFFLDhEQUE4RDthQUN4RTtTQUNGLENBQUM7SUFDSixDQUFDO0lBQ0QsTUFBTSxLQUFLLEdBQUcsYUFBYSxDQUFDLElBQUksQ0FBQztJQUVqQyxJQUFJLFVBQVUsR0FBRyxPQUFPLEVBQUUsUUFBUSxDQUFDO0lBRW5DLElBQUksQ0FBQyxVQUFVLEVBQUUsQ0FBQztRQUNoQixNQUFNLFlBQVksR0FDaEIsd0VBQXdFLENBQUM7UUFDM0UsTUFBTSxhQUFhLEdBQUcsb0JBQW9CLENBQUMsQ0FBQyxtREFBbUQ7UUFDL0YsTUFBTSxTQUFTLEdBQUcsT0FBTyxFQUFFLEtBQUssSUFBSSxFQUFFLENBQUM7UUFDdkMsSUFBSSxpQkFBaUIsR0FBRyxFQUFFLENBQUM7UUFFM0Isa0dBQWtHO1FBQ2xHLElBQUksT0FBTyxFQUFFLHNCQUFzQixLQUFLLElBQUksRUFBRSxDQUFDO1lBQzdDLGlCQUFpQixHQUFHLHVGQUF1RixDQUFDO1FBQzlHLENBQUM7UUFFRCxNQUFNLFdBQVcsR0FBRyxJQUFJLGVBQWUsRUFBRSxDQUFDO1FBQzFDLFdBQVcsQ0FBQyxNQUFNLENBQUMsU0FBUyxFQUFFLFlBQVksQ0FBQyxDQUFDO1FBQzVDLFdBQVcsQ0FBQyxNQUFNLENBQUMsVUFBVSxFQUFFLGFBQWEsQ0FBQyxDQUFDLENBQUMsNEJBQTRCO1FBQzNFLFdBQVcsQ0FBQyxNQUFNLENBQUMsTUFBTSxFQUFFLFNBQVMsQ0FBQyxRQUFRLEVBQUUsQ0FBQyxDQUFDO1FBQ2pELElBQUksaUJBQWlCLEVBQUUsQ0FBQztZQUN0QixXQUFXLENBQUMsTUFBTSxDQUFDLFNBQVMsRUFBRSxpQkFBaUIsQ0FBQyxDQUFDO1FBQ25ELENBQUM7UUFDRCwrR0FBK0c7UUFDL0csVUFBVSxHQUFHLEdBQUcsb0JBQW9CLHVCQUF1QixXQUFXLENBQUMsUUFBUSxFQUFFLEVBQUUsQ0FBQztJQUN0RixDQUFDO0lBRUQsSUFBSSxDQUFDO1FBQ0gsTUFBTSxDQUFDLEtBQUssQ0FDVix1REFBdUQsVUFBVSxFQUFFLENBQ3BFLENBQUM7UUFDRixNQUFNLFFBQVEsR0FBRyxNQUFNLEtBQUssQ0FBQyxHQUFHLENBQUMsVUFBVSxFQUFFO1lBQzNDLE9BQU8sRUFBRSxFQUFFLGFBQWEsRUFBRSxVQUFVLEtBQUssRUFBRSxFQUFFO1NBQzlDLENBQUMsQ0FBQztRQUNILE9BQU87WUFDTCxFQUFFLEVBQUUsSUFBSTtZQUNSLElBQUksRUFBRTtnQkFDSixNQUFNLEVBQUUsUUFBUSxDQUFDLElBQUksQ0FBQyxLQUF1QjtnQkFDN0MsUUFBUSxFQUFFLFFBQVEsQ0FBQyxJQUFJLENBQUMsaUJBQWlCLENBQUMsSUFBSSxTQUFTO2FBQ3hEO1NBQ0YsQ0FBQztJQUNKLENBQUM7SUFBQyxPQUFPLEtBQVUsRUFBRSxDQUFDO1FBQ3BCLE1BQU0sVUFBVSxHQUFHLEtBQW1CLENBQUM7UUFDdkMsTUFBTSxDQUFDLEtBQUssQ0FDVixrRUFBa0UsVUFBVSxHQUFHLEVBQy9FLFVBQVUsQ0FBQyxPQUFPLEVBQ2xCLFVBQVUsQ0FBQyxRQUFRLEVBQUUsSUFBSSxDQUMxQixDQUFDO1FBQ0YsTUFBTSxTQUFTLEdBQUcsVUFBVSxDQUFDLFFBQVEsRUFBRSxJQUFXLENBQUM7UUFDbkQsT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxTQUFTLEVBQUUsS0FBSyxFQUFFLElBQUksSUFBSSxtQkFBbUI7Z0JBQ25ELE9BQU8sRUFDTCxTQUFTLEVBQUUsS0FBSyxFQUFFLE9BQU87b0JBQ3pCLFVBQVUsQ0FBQyxPQUFPO29CQUNsQixrQ0FBa0M7Z0JBQ3BDLE9BQU8sRUFBRSxTQUFTLEVBQUUsS0FBSyxJQUFJLFNBQVM7YUFDdkM7U0FDRixDQUFDO0lBQ0osQ0FBQztBQUNILENBQUM7QUFFRCxNQUFNLENBQUMsS0FBSyxVQUFVLCtCQUErQixDQUNuRCxVQUFrQixFQUFFLCtEQUErRDtBQUNuRixPQUFlO0lBRWYsTUFBTSxDQUFDLEtBQUssQ0FDViwwRUFBMEUsVUFBVSxjQUFjLE9BQU8sRUFBRSxDQUM1RyxDQUFDO0lBRUYsTUFBTSxhQUFhLEdBQUcsTUFBTSwrQkFBK0IsQ0FBQyxVQUFVLENBQUMsQ0FBQztJQUN4RSxJQUFJLENBQUMsYUFBYSxDQUFDLEVBQUUsSUFBSSxDQUFDLGFBQWEsQ0FBQyxJQUFJLEVBQUUsQ0FBQztRQUM3QyxPQUFPO1lBQ0wsRUFBRSxFQUFFLEtBQUs7WUFDVCxLQUFLLEVBQUUsYUFBYSxDQUFDLEtBQUssSUFBSTtnQkFDNUIsSUFBSSxFQUFFLG9CQUFvQjtnQkFDMUIsT0FBTyxFQUFFLDZEQUE2RDthQUN2RTtTQUNGLENBQUM7SUFDSixDQUFDO0lBQ0QsTUFBTSxLQUFLLEdBQUcsYUFBYSxDQUFDLElBQUksQ0FBQztJQUVqQyxNQUFNLFlBQVksR0FDaEIsb0hBQW9ILENBQUM7SUFDdkgscUhBQXFIO0lBQ3JILE1BQU0sVUFBVSxHQUFHLEdBQUcsb0JBQW9CLGNBQWMsT0FBTyxZQUFZLFlBQVksRUFBRSxDQUFDO0lBRTFGLElBQUksQ0FBQztRQUNILE1BQU0sQ0FBQyxLQUFLLENBQ1YsOERBQThELFVBQVUsRUFBRSxDQUMzRSxDQUFDO1FBQ0YsTUFBTSxRQUFRLEdBQUcsTUFBTSxLQUFLLENBQUMsR0FBRyxDQUFlLFVBQVUsRUFBRTtZQUN6RCxPQUFPLEVBQUUsRUFBRSxhQUFhLEVBQUUsVUFBVSxLQUFLLEVBQUUsRUFBRTtTQUM5QyxDQUFDLENBQUM7UUFDSCxPQUFPLEVBQUUsRUFBRSxFQUFFLElBQUksRUFBRSxJQUFJLEVBQUUsUUFBUSxDQUFDLElBQUksRUFBRSxDQUFDO0lBQzNDLENBQUM7SUFBQyxPQUFPLEtBQVUsRUFBRSxDQUFDO1FBQ3BCLE1BQU0sVUFBVSxHQUFHLEtBQW1CLENBQUM7UUFDdkMsTUFBTSxDQUFDLEtBQUssQ0FDVixxRUFBcUUsT0FBTyxlQUFlLFVBQVUsR0FBRyxFQUN4RyxVQUFVLENBQUMsT0FBTyxFQUNsQixVQUFVLENBQUMsUUFBUSxFQUFFLElBQUksQ0FDMUIsQ0FBQztRQUNGLE1BQU0sU0FBUyxHQUFHLFVBQVUsQ0FBQyxRQUFRLEVBQUUsSUFBVyxDQUFDO1FBQ25ELElBQUksVUFBVSxDQUFDLFFBQVEsRUFBRSxNQUFNLEtBQUssR0FBRyxFQUFFLENBQUM7WUFDeEMsT0FBTztnQkFDTCxFQUFFLEVBQUUsS0FBSztnQkFDVCxLQUFLLEVBQUU7b0JBQ0wsSUFBSSxFQUFFLGlCQUFpQjtvQkFDdkIsT0FBTyxFQUNMLGdDQUFnQyxPQUFPLGVBQWUsU0FBUyxFQUFFLEtBQUssRUFBRSxPQUFPLElBQUksRUFBRSxFQUFFLENBQUMsSUFBSSxFQUFFO2lCQUNqRzthQUNGLENBQUM7UUFDSixDQUFDO1FBQ0QsT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxTQUFTLEVBQUUsS0FBSyxFQUFFLElBQUksSUFBSSxtQkFBbUI7Z0JBQ25ELE9BQU8sRUFDTCxTQUFTLEVBQUUsS0FBSyxFQUFFLE9BQU87b0JBQ3pCLFVBQVUsQ0FBQyxPQUFPO29CQUNsQix3Q0FBd0M7Z0JBQzFDLE9BQU8sRUFBRSxTQUFTLEVBQUUsS0FBSyxJQUFJLFNBQVM7YUFDdkM7U0FDRixDQUFDO0lBQ0osQ0FBQztBQUNILENBQUM7QUF5Q0Q7Ozs7OztHQU1HO0FBQ0gsTUFBTSxDQUFDLEtBQUssVUFBVSxtQkFBbUIsQ0FDdkMsVUFBa0IsRUFDbEIsV0FBbUIsRUFBRSxvQ0FBb0M7QUFDekQsYUFBcUIsRUFBRSxFQUN2QixlQUF3QixDQUFDLGdFQUFnRTs7SUFFekYsTUFBTSxDQUFDLEtBQUssQ0FDViw2REFBNkQsVUFBVSxhQUFhLFdBQVcsa0JBQWtCLFVBQVUsc0JBQXNCLGVBQWUsRUFBRSxDQUNuSyxDQUFDO0lBRUYsTUFBTSxhQUFhLEdBQUcsTUFBTSwrQkFBK0IsQ0FBQyxVQUFVLENBQUMsQ0FBQztJQUN4RSxJQUFJLENBQUMsYUFBYSxDQUFDLEVBQUUsSUFBSSxDQUFDLGFBQWEsQ0FBQyxJQUFJLEVBQUUsQ0FBQztRQUM3QyxPQUFPO1lBQ0wsRUFBRSxFQUFFLEtBQUs7WUFDVCxLQUFLLEVBQUUsYUFBYSxDQUFDLEtBQUssSUFBSTtnQkFDNUIsSUFBSSxFQUFFLG9CQUFvQjtnQkFDMUIsT0FBTyxFQUFFLHlEQUF5RDthQUNuRTtTQUNGLENBQUM7SUFDSixDQUFDO0lBQ0QsTUFBTSxLQUFLLEdBQUcsYUFBYSxDQUFDLElBQUksQ0FBQztJQUVqQyx5R0FBeUc7SUFDekcsb0RBQW9EO0lBQ3BELGlFQUFpRTtJQUNqRSxtR0FBbUc7SUFDbkcsaUVBQWlFO0lBRWpFLHlFQUF5RTtJQUN6RSw0RUFBNEU7SUFDNUUseUJBQXlCO0lBQ3pCLGtHQUFrRztJQUNsRyxJQUFJO0lBQ0oseUVBQXlFO0lBRXpFLE1BQU0sYUFBYSxHQUFHO1FBQ3BCLFFBQVEsRUFBRTtZQUNSO2dCQUNFLFdBQVcsRUFBRSxDQUFDLGFBQWEsQ0FBQztnQkFDNUIsS0FBSyxFQUFFO29CQUNMLFdBQVcsRUFBRSxXQUFXLEVBQUUsc0NBQXNDO2lCQUNqRTtnQkFDRCxJQUFJLEVBQUUsQ0FBQztnQkFDUCxJQUFJLEVBQUUsVUFBVTtnQkFDaEIsY0FBYyxFQUFFLENBQUMsRUFBRSxJQUFJLEVBQUUsaUJBQWlCLEVBQUUsWUFBWSxFQUFFLElBQUksRUFBRSxDQUFDO2FBQ2xFO1NBQ0Y7S0FDRixDQUFDO0lBRUYsTUFBTSxVQUFVLEdBQUcsR0FBRyxvQkFBb0IsZUFBZSxDQUFDO0lBRTFELElBQUksQ0FBQztRQUNILG1EQUFtRDtRQUNuRCxNQUFNLENBQUMsSUFBSSxDQUNULDBEQUEwRCxXQUFXLGNBQWMsVUFBVSxFQUFFLENBQ2hHLENBQUM7UUFDRixNQUFNLFFBQVEsR0FBRyxNQUFNLEtBQUssQ0FBQyxJQUFJLENBQUMsVUFBVSxFQUFFLGFBQWEsRUFBRTtZQUMzRCxPQUFPLEVBQUU7Z0JBQ1AsYUFBYSxFQUFFLFVBQVUsS0FBSyxFQUFFO2dCQUNoQyxjQUFjLEVBQUUsa0JBQWtCO2FBQ25DO1NBQ0YsQ0FBQyxDQUFDO1FBRUgsTUFBTSxRQUFRLEdBQTBCLEVBQUUsQ0FBQztRQUMzQyxJQUNFLFFBQVEsQ0FBQyxJQUFJO1lBQ2IsUUFBUSxDQUFDLElBQUksQ0FBQyxLQUFLO1lBQ25CLFFBQVEsQ0FBQyxJQUFJLENBQUMsS0FBSyxDQUFDLE1BQU0sR0FBRyxDQUFDLEVBQzlCLENBQUM7WUFDRCxNQUFNLG9CQUFvQixHQUFHLFFBQVEsQ0FBQyxJQUFJLENBQUMsS0FBSyxDQUFDLENBQUMsQ0FBQyxFQUFFLGNBQWMsQ0FBQztZQUNwRSxJQUFJLG9CQUFvQixJQUFJLG9CQUFvQixDQUFDLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztnQkFDNUQsb0JBQW9CLENBQUMsT0FBTyxDQUFDLENBQUMsU0FBYyxFQUFFLEVBQUU7b0JBQzlDLElBQUksU0FBUyxDQUFDLElBQUksRUFBRSxDQUFDO3dCQUNuQixTQUFTLENBQUMsSUFBSSxDQUFDLE9BQU8sQ0FBQyxDQUFDLEdBQVEsRUFBRSxFQUFFOzRCQUNsQyxNQUFNLFFBQVEsR0FBRyxHQUFHLENBQUMsUUFBUSxDQUFDOzRCQUM5QixJQUFJLFFBQVEsRUFBRSxDQUFDO2dDQUNiLFFBQVEsQ0FBQyxJQUFJLENBQUM7b0NBQ1osRUFBRSxFQUFFLFFBQVEsQ0FBQyxFQUFFO29DQUNmLE1BQU0sRUFBRSxRQUFRLENBQUMsTUFBTTtvQ0FDdkIsU0FBUyxFQUFFLFFBQVEsQ0FBQyxlQUFlLEVBQUUsU0FBUztvQ0FDOUMsTUFBTSxFQUFFLFFBQVEsQ0FBQyxlQUFlLEVBQUUsTUFBTTtvQ0FDeEMsU0FBUyxFQUFFLFFBQVEsQ0FBQyxTQUFTO29DQUM3QixNQUFNLEVBQUUsUUFBUSxDQUFDLElBQUksRUFBRSxJQUFJLEVBQUUsRUFBRTtvQ0FDL0IsUUFBUSxFQUFFLFFBQVEsQ0FBQyxJQUFJLEVBQUUsSUFBSSxFQUFFLFdBQVc7b0NBQzFDLE9BQU8sRUFBRSxRQUFRLENBQUMsSUFBSSxFQUFFLE9BQU87b0NBQy9CLFdBQVcsRUFBRSxRQUFRLENBQUMsSUFBSSxFQUFFLFdBQVc7b0NBQ3ZDLGVBQWUsRUFBRSxRQUFRLENBQUMsZUFBZTtvQ0FDekMsb0JBQW9CLEVBQUUsUUFBUSxDQUFDLG9CQUFvQjtvQ0FDbkQsTUFBTSxFQUFFLFFBQVEsQ0FBQyxNQUFNO29DQUN2Qiw0RkFBNEY7b0NBQzVGLCtCQUErQjtvQ0FDL0IsR0FBRyxFQUFFLFFBQVE7aUNBQ2QsQ0FBQyxDQUFDOzRCQUNMLENBQUM7d0JBQ0gsQ0FBQyxDQUFDLENBQUM7b0JBQ0wsQ0FBQztnQkFDSCxDQUFDLENBQUMsQ0FBQztZQUNMLENBQUM7UUFDSCxDQUFDO1FBQ0QsTUFBTSxDQUFDLElBQUksQ0FDVCwwQkFBMEIsUUFBUSxDQUFDLE1BQU0sOEJBQThCLFdBQVcsbUJBQW1CLFVBQVUsR0FBRyxDQUNuSCxDQUFDO1FBQ0YsT0FBTyxFQUFFLEVBQUUsRUFBRSxJQUFJLEVBQUUsSUFBSSxFQUFFLFFBQVEsRUFBRSxDQUFDO0lBQ3RDLENBQUM7SUFBQyxPQUFPLEtBQVUsRUFBRSxDQUFDO1FBQ3BCLE1BQU0sVUFBVSxHQUFHLEtBQW1CLENBQUM7UUFDdkMsTUFBTSxDQUFDLEtBQUssQ0FDVixpRUFBaUUsVUFBVSxHQUFHLEVBQzlFLFVBQVUsQ0FBQyxPQUFPLEVBQ2xCLFVBQVUsQ0FBQyxRQUFRLEVBQUUsSUFBSSxDQUMxQixDQUFDO1FBQ0YsTUFBTSxTQUFTLEdBQUcsVUFBVSxDQUFDLFFBQVEsRUFBRSxJQUFXLENBQUM7UUFDbkQsT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxTQUFTLEVBQUUsS0FBSyxFQUFFLElBQUksSUFBSSwwQkFBMEI7Z0JBQzFELE9BQU8sRUFDTCxTQUFTLEVBQUUsS0FBSyxFQUFFLE9BQU87b0JBQ3pCLFVBQVUsQ0FBQyxPQUFPO29CQUNsQixpQ0FBaUM7Z0JBQ25DLE9BQU8sRUFBRSxTQUFTLEVBQUUsS0FBSyxJQUFJLFNBQVM7YUFDdkM7U0FDRixDQUFDO0lBQ0osQ0FBQztBQUNILENBQUM7QUFFRDs7Ozs7O0dBTUc7QUFDSCxNQUFNLENBQUMsS0FBSyxVQUFVLDBCQUEwQixDQUM5QyxVQUFrQixFQUNsQixNQUFjLEVBQ2QsU0FBaUI7SUFFakIsTUFBTSxDQUFDLEtBQUssQ0FDVix3REFBd0QsVUFBVSxhQUFhLE1BQU0sZ0JBQWdCLFNBQVMsRUFBRSxDQUNqSCxDQUFDO0lBQ0YsTUFBTSxhQUFhLEdBQUcsTUFBTSwrQkFBK0IsQ0FBQyxVQUFVLENBQUMsQ0FBQztJQUN4RSxJQUFJLENBQUMsYUFBYSxDQUFDLEVBQUUsSUFBSSxDQUFDLGFBQWEsQ0FBQyxJQUFJO1FBQzFDLE9BQU8sRUFBRSxFQUFFLEVBQUUsS0FBSyxFQUFFLEtBQUssRUFBRSxhQUFhLENBQUMsS0FBSyxFQUFFLENBQUM7SUFDbkQsTUFBTSxLQUFLLEdBQUcsYUFBYSxDQUFDLElBQUksQ0FBQztJQUVqQywwRUFBMEU7SUFDMUUsTUFBTSxZQUFZLEdBQ2hCLGdHQUFnRyxDQUFDO0lBQ25HLE1BQU0sVUFBVSxHQUFHLEdBQUcsb0JBQW9CLGFBQWEsTUFBTSxhQUFhLFNBQVMsWUFBWSxZQUFZLEVBQUUsQ0FBQztJQUU5RyxJQUFJLENBQUM7UUFDSCxNQUFNLFFBQVEsR0FBRyxNQUFNLEtBQUssQ0FBQyxHQUFHLENBQUMsVUFBVSxFQUFFO1lBQzNDLE9BQU8sRUFBRSxFQUFFLGFBQWEsRUFBRSxVQUFVLEtBQUssRUFBRSxFQUFFO1NBQzlDLENBQUMsQ0FBQztRQUNILE1BQU0sTUFBTSxHQUFHLFFBQVEsQ0FBQyxJQUFJLENBQUM7UUFDN0IsTUFBTSxPQUFPLEdBQXdCO1lBQ25DLEVBQUUsRUFBRSxNQUFNLENBQUMsRUFBRTtZQUNiLE1BQU0sRUFBRSxNQUFNLENBQUMsTUFBTSxFQUFFLHFDQUFxQztZQUM1RCxTQUFTLEVBQUUsTUFBTSxDQUFDLFNBQVM7WUFDM0IsTUFBTSxFQUFFLE1BQU0sQ0FBQyxJQUFJLEVBQUUsSUFBSSxFQUFFLEVBQUU7WUFDN0IsUUFBUSxFQUFFLE1BQU0sQ0FBQyxJQUFJLEVBQUUsSUFBSSxFQUFFLFdBQVc7WUFDeEMsT0FBTyxFQUFFLE1BQU0sQ0FBQyxJQUFJLEVBQUUsT0FBTztZQUM3QixXQUFXLEVBQUUsTUFBTSxDQUFDLElBQUksRUFBRSxXQUFXO1lBQ3JDLGVBQWUsRUFBRSxNQUFNLENBQUMsZUFBZTtZQUN2QyxvQkFBb0IsRUFBRSxNQUFNLENBQUMsb0JBQW9CO1lBQ2pELE1BQU0sRUFBRSxNQUFNLENBQUMsTUFBTTtZQUNyQixXQUFXLEVBQUUsTUFBTSxDQUFDLFdBQVcsRUFBRSxHQUFHLENBQUMsQ0FBQyxHQUFRLEVBQUUsRUFBRSxDQUFDLENBQUM7Z0JBQ2xELEVBQUUsRUFBRSxHQUFHLENBQUMsRUFBRTtnQkFDVixJQUFJLEVBQUUsR0FBRyxDQUFDLElBQUk7Z0JBQ2QsV0FBVyxFQUFFLEdBQUcsQ0FBQyxXQUFXO2dCQUM1QixVQUFVLEVBQUUsR0FBRyxDQUFDLFVBQVU7Z0JBQzFCLElBQUksRUFBRSxHQUFHLENBQUMsSUFBSTthQUNmLENBQUMsQ0FBQztZQUNILFFBQVEsRUFBRSxNQUFNLENBQUMsUUFBUSxFQUFFLEdBQUcsQ0FBQyxDQUFDLEdBQVEsRUFBRSxFQUFFLENBQUMsQ0FBQztnQkFDNUMsRUFBRSxFQUFFLEdBQUcsQ0FBQyxFQUFFO2dCQUNWLFdBQVcsRUFBRSxHQUFHLENBQUMsV0FBVztnQkFDNUIsU0FBUyxFQUFFLEdBQUcsQ0FBQyxTQUFTO2FBQ3pCLENBQUMsQ0FBQztZQUNILEdBQUcsRUFBRSxNQUFNO1NBQ1osQ0FBQztRQUNGLE9BQU8sRUFBRSxFQUFFLEVBQUUsSUFBSSxFQUFFLElBQUksRUFBRSxPQUFPLEVBQUUsQ0FBQztJQUNyQyxDQUFDO0lBQUMsT0FBTyxLQUFVLEVBQUUsQ0FBQztRQUNwQixNQUFNLFVBQVUsR0FBRyxLQUFtQixDQUFDO1FBQ3ZDLE1BQU0sQ0FBQyxLQUFLLENBQ1YsNkRBQTZELE1BQU0sU0FBUyxTQUFTLElBQUksRUFDekYsVUFBVSxDQUFDLE9BQU8sRUFDbEIsVUFBVSxDQUFDLFFBQVEsRUFBRSxJQUFJLENBQzFCLENBQUM7UUFDRixNQUFNLFNBQVMsR0FBRyxVQUFVLENBQUMsUUFBUSxFQUFFLElBQVcsQ0FBQztRQUNuRCxJQUFJLFVBQVUsQ0FBQyxRQUFRLEVBQUUsTUFBTSxLQUFLLEdBQUc7WUFDckMsT0FBTztnQkFDTCxFQUFFLEVBQUUsS0FBSztnQkFDVCxLQUFLLEVBQUU7b0JBQ0wsSUFBSSxFQUFFLDJCQUEyQjtvQkFDakMsT0FBTyxFQUFFLHlCQUF5QjtpQkFDbkM7YUFDRixDQUFDO1FBQ0osT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxTQUFTLEVBQUUsS0FBSyxFQUFFLElBQUksSUFBSSxtQkFBbUI7Z0JBQ25ELE9BQU8sRUFDTCxTQUFTLEVBQUUsS0FBSyxFQUFFLE9BQU8sSUFBSSxvQ0FBb0M7YUFDcEU7U0FDRixDQUFDO0lBQ0osQ0FBQztBQUNILENBQUM7QUFFRDs7Ozs7OztHQU9HO0FBQ0gsTUFBTSxDQUFDLEtBQUssVUFBVSw2QkFBNkIsQ0FDakQsVUFBa0IsRUFDbEIsTUFBYyxFQUNkLFNBQWlCLEVBQ2pCLFNBQWlCO0lBRWpCLE1BQU0sQ0FBQyxLQUFLLENBQ1YsMkRBQTJELFVBQVUsVUFBVSxNQUFNLGFBQWEsU0FBUyxTQUFTLFNBQVMsRUFBRSxDQUNoSSxDQUFDO0lBQ0YsTUFBTSxhQUFhLEdBQUcsTUFBTSwrQkFBK0IsQ0FBQyxVQUFVLENBQUMsQ0FBQztJQUN4RSxJQUFJLENBQUMsYUFBYSxDQUFDLEVBQUUsSUFBSSxDQUFDLGFBQWEsQ0FBQyxJQUFJO1FBQzFDLE9BQU8sRUFBRSxFQUFFLEVBQUUsS0FBSyxFQUFFLEtBQUssRUFBRSxhQUFhLENBQUMsS0FBSyxFQUFFLENBQUM7SUFDbkQsTUFBTSxLQUFLLEdBQUcsYUFBYSxDQUFDLElBQUksQ0FBQztJQUVqQyxNQUFNLFlBQVksR0FDaEIseUdBQXlHLENBQUM7SUFDNUcsTUFBTSxVQUFVLEdBQUcsR0FBRyxvQkFBb0IsVUFBVSxNQUFNLGFBQWEsU0FBUyxhQUFhLFNBQVMsWUFBWSxZQUFZLEVBQUUsQ0FBQztJQUVqSSxJQUFJLENBQUM7UUFDSCxNQUFNLFFBQVEsR0FBRyxNQUFNLEtBQUssQ0FBQyxHQUFHLENBQUMsVUFBVSxFQUFFO1lBQzNDLE9BQU8sRUFBRSxFQUFFLGFBQWEsRUFBRSxVQUFVLEtBQUssRUFBRSxFQUFFO1NBQzlDLENBQUMsQ0FBQztRQUNILE1BQU0sTUFBTSxHQUFHLFFBQVEsQ0FBQyxJQUFJLENBQUM7UUFDN0IsTUFBTSxPQUFPLEdBQXdCO1lBQ25DLEVBQUUsRUFBRSxNQUFNLENBQUMsRUFBRTtZQUNiLE1BQU0sRUFBRSxNQUFNLENBQUMsZUFBZSxFQUFFLE1BQU07WUFDdEMsU0FBUyxFQUFFLE1BQU0sQ0FBQyxlQUFlLEVBQUUsU0FBUztZQUM1QyxTQUFTLEVBQUUsTUFBTSxDQUFDLFNBQVM7WUFDM0IsTUFBTSxFQUFFLE1BQU0sQ0FBQyxJQUFJLEVBQUUsSUFBSSxFQUFFLEVBQUU7WUFDN0IsUUFBUSxFQUFFLE1BQU0sQ0FBQyxJQUFJLEVBQUUsSUFBSSxFQUFFLFdBQVc7WUFDeEMsT0FBTyxFQUFFLE1BQU0sQ0FBQyxJQUFJLEVBQUUsT0FBTztZQUM3QixXQUFXLEVBQUUsTUFBTSxDQUFDLElBQUksRUFBRSxXQUFXO1lBQ3JDLGVBQWUsRUFBRSxNQUFNLENBQUMsZUFBZTtZQUN2QyxvQkFBb0IsRUFBRSxNQUFNLENBQUMsb0JBQW9CO1lBQ2pELE1BQU0sRUFBRSxNQUFNLENBQUMsTUFBTTtZQUNyQixXQUFXLEVBQUUsTUFBTSxDQUFDLFdBQVcsRUFBRSxHQUFHLENBQUMsQ0FBQyxHQUFRLEVBQUUsRUFBRSxDQUFDLENBQUM7Z0JBQ2xELEVBQUUsRUFBRSxHQUFHLENBQUMsRUFBRTtnQkFDVixJQUFJLEVBQUUsR0FBRyxDQUFDLElBQUk7Z0JBQ2QsV0FBVyxFQUFFLEdBQUcsQ0FBQyxXQUFXO2dCQUM1QixVQUFVLEVBQUUsR0FBRyxDQUFDLFVBQVU7Z0JBQzFCLElBQUksRUFBRSxHQUFHLENBQUMsSUFBSTthQUNmLENBQUMsQ0FBQztZQUNILFFBQVEsRUFBRSxNQUFNLENBQUMsUUFBUSxFQUFFLEdBQUcsQ0FBQyxDQUFDLEdBQVEsRUFBRSxFQUFFLENBQUMsQ0FBQztnQkFDNUMsRUFBRSxFQUFFLEdBQUcsQ0FBQyxFQUFFO2dCQUNWLFdBQVcsRUFBRSxHQUFHLENBQUMsV0FBVztnQkFDNUIsU0FBUyxFQUFFLEdBQUcsQ0FBQyxTQUFTO2FBQ3pCLENBQUMsQ0FBQztZQUNILEdBQUcsRUFBRSxNQUFNO1NBQ1osQ0FBQztRQUNGLE9BQU8sRUFBRSxFQUFFLEVBQUUsSUFBSSxFQUFFLElBQUksRUFBRSxPQUFPLEVBQUUsQ0FBQztJQUNyQyxDQUFDO0lBQUMsT0FBTyxLQUFVLEVBQUUsQ0FBQztRQUNwQixNQUFNLFVBQVUsR0FBRyxLQUFtQixDQUFDO1FBQ3ZDLE1BQU0sQ0FBQyxLQUFLLENBQ1YsZ0VBQWdFLE1BQU0sYUFBYSxTQUFTLFNBQVMsU0FBUyxJQUFJLEVBQ2xILFVBQVUsQ0FBQyxPQUFPLEVBQ2xCLFVBQVUsQ0FBQyxRQUFRLEVBQUUsSUFBSSxDQUMxQixDQUFDO1FBQ0YsTUFBTSxTQUFTLEdBQUcsVUFBVSxDQUFDLFFBQVEsRUFBRSxJQUFXLENBQUM7UUFDbkQsSUFBSSxVQUFVLENBQUMsUUFBUSxFQUFFLE1BQU0sS0FBSyxHQUFHO1lBQ3JDLE9BQU87Z0JBQ0wsRUFBRSxFQUFFLEtBQUs7Z0JBQ1QsS0FBSyxFQUFFO29CQUNMLElBQUksRUFBRSwyQkFBMkI7b0JBQ2pDLE9BQU8sRUFBRSw0QkFBNEI7aUJBQ3RDO2FBQ0YsQ0FBQztRQUNKLE9BQU87WUFDTCxFQUFFLEVBQUUsS0FBSztZQUNULEtBQUssRUFBRTtnQkFDTCxJQUFJLEVBQUUsU0FBUyxFQUFFLEtBQUssRUFBRSxJQUFJLElBQUksbUJBQW1CO2dCQUNuRCxPQUFPLEVBQ0wsU0FBUyxFQUFFLEtBQUssRUFBRSxPQUFPLElBQUksdUNBQXVDO2FBQ3ZFO1NBQ0YsQ0FBQztJQUNKLENBQUM7QUFDSCxDQUFDO0FBRUQsZ0ZBQWdGO0FBQ2hGLG9GQUFvRjtBQUNwRixvR0FBb0ciLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgYXhpb3MsIHsgQXhpb3NFcnJvciB9IGZyb20gJ2F4aW9zJztcbmltcG9ydCB7XG4gIENvbmZpZGVudGlhbENsaWVudEFwcGxpY2F0aW9uLFxuICBDb25maWd1cmF0aW9uLFxuICBBdXRoZW50aWNhdGlvblJlc3VsdCxcbiAgTG9nTGV2ZWwsXG4gIFB1YmxpY0NsaWVudEFwcGxpY2F0aW9uLFxuICBBdXRob3JpemF0aW9uQ29kZVJlcXVlc3QsXG4gIEFjY291bnRJbmZvLFxuICBTaWxlbnRGbG93UmVxdWVzdCxcbn0gZnJvbSAnQGF6dXJlL21zYWwtbm9kZSc7IC8vIEFkZGVkIFB1YmxpY0NsaWVudEFwcGxpY2F0aW9uIGFuZCByZWxhdGVkIHR5cGVzXG5pbXBvcnQge30gZnJvbSAnQGF6dXJlL21zYWwtbm9kZSc7XG5pbXBvcnQge1xuICAvLyBBVE9NX01TR1JBUEhfQ0xJRU5UX0lELCAvLyBSZXBsYWNlZCBieSBNU0dSQVBIX0RFTEVHQVRFRF9DTElFTlRfSURcbiAgLy8gQVRPTV9NU0dSQVBIX0NMSUVOVF9TRUNSRVQsIC8vIFJlcGxhY2VkIGJ5IE1TR1JBUEhfREVMRUdBVEVEX0NMSUVOVF9TRUNSRVRcbiAgLy8gQVRPTV9NU0dSQVBIX1RFTkFOVF9JRCwgLy8gUmVwbGFjZWQgYnkgTVNHUkFQSF9ERUxFR0FURURfVEVOQU5UX0lEXG4gIC8vIEFUT01fTVNHUkFQSF9BVVRIT1JJVFksIC8vIFJlcGxhY2VkIGJ5IE1TR1JBUEhfREVMRUdBVEVEX0FVVEhPUklUWVxuICAvLyBBVE9NX01TR1JBUEhfU0NPUEVTLCAvLyBSZXBsYWNlZCBieSBNU0dSQVBIX0RFTEVHQVRFRF9TQ09QRVNcbiAgLy8gSW1wb3J0IG5ldyBEZWxlZ2F0ZWQgQXV0aCBDb25zdGFudHMgZnJvbSBhIGNlbnRyYWwgcGxhY2UgaWYgYXZhaWxhYmxlLCBvdGhlcndpc2UgdXNlIHByb2Nlc3MuZW52XG4gIE1TR1JBUEhfREVMRUdBVEVEX0NMSUVOVF9JRCxcbiAgTVNHUkFQSF9ERUxFR0FURURfQ0xJRU5UX1NFQ1JFVCxcbiAgTVNHUkFQSF9ERUxFR0FURURfQVVUSE9SSVRZLFxuICBNU0dSQVBIX0RFTEVHQVRFRF9SRURJUkVDVF9VUkwsXG4gIE1TR1JBUEhfREVMRUdBVEVEX1NDT1BFUyxcbiAgTVNURUFNU19UT0tFTl9FTkNSWVBUSU9OX0tFWSxcbn0gZnJvbSAnLi4vYXRvbS1hZ2VudC9fbGlicy9jb25zdGFudHMnOyAvLyBBZGp1c3RlZCBwYXRoIGFzc3VtaW5nIGNvbnN0YW50cyBhcmUgd2VsbC1kZWZpbmVkXG5pbXBvcnQge1xuICBNU0dyYXBoRXZlbnQsXG4gIEdyYXBoU2tpbGxSZXNwb25zZSxcbiAgTGlzdE1TR3JhcGhFdmVudHNEYXRhLFxuICBTa2lsbEVycm9yLFxufSBmcm9tICcuLi9hdG9tLWFnZW50L3R5cGVzJzsgLy8gQWRqdXN0ZWQgcGF0aFxuaW1wb3J0IHsgbG9nZ2VyIH0gZnJvbSAnLi4vX3V0aWxzL2xvZ2dlcic7XG5pbXBvcnQgeyBjcmVhdGVBZG1pbkdyYXBoUUxDbGllbnQgfSBmcm9tICcuLi9fdXRpbHMvZGJTZXJ2aWNlJztcbi8vIGltcG9ydCB7IGVuY3J5cHQsIGRlY3J5cHQgfSBmcm9tICcuLi9fdXRpbHMvZW5jcnlwdGlvbic7IC8vIFRPRE86IENyZWF0ZSBhbmQgdXNlIGEgc2hhcmVkIGVuY3J5cHRpb24gdXRpbGl0eVxuXG5jb25zdCBNU0dSQVBIX0FQSV9CQVNFX1VSTCA9ICdodHRwczovL2dyYXBoLm1pY3Jvc29mdC5jb20vdjEuMCc7XG5cbi8vIE1TQUwgQ29uZmlkZW50aWFsQ2xpZW50QXBwbGljYXRpb24gaW5zdGFuY2UgZm9yIHRoZSBiYWNrZW5kXG5sZXQgbXNhbENvbmZpZGVudGlhbENsaWVudEFwcDogQ29uZmlkZW50aWFsQ2xpZW50QXBwbGljYXRpb24gfCBudWxsID0gbnVsbDtcblxuLy8gRGF0YWJhc2UgaW50ZXJhY3Rpb24gZnVuY3Rpb25zIChwbGFjZWhvbGRlcnMgLSB0byBiZSBpbXBsZW1lbnRlZCB3aXRoIGFjdHVhbCBEQiBjYWxscylcbi8vIFRoZXNlIHdvdWxkIHR5cGljYWxseSBpbnRlcmFjdCB3aXRoIGEgdGFibGUgbGlrZSAndXNlcl9tc3RlYW1zX3Rva2Vucydcbi8vIGludGVyZmFjZSBTdG9yZWRUb2tlbkRhdGEge1xuLy8gICBlbmNyeXB0ZWRBY2Nlc3NUb2tlbjogc3RyaW5nO1xuLy8gICBlbmNyeXB0ZWRSZWZyZXNoVG9rZW4/OiBzdHJpbmcgfCBudWxsO1xuLy8gICBhY2NvdW50SnNvbjogc3RyaW5nOyAvLyBTdG9yZSBNU0FMIEFjY291bnRJbmZvIGFzIEpTT05cbi8vICAgdG9rZW5FeHBpcnlUaW1lc3RhbXA6IERhdGU7XG4vLyB9XG5cbi8vIFRPRE86IEltcGxlbWVudCB0aGVzZSBmdW5jdGlvbnMgcHJvcGVybHlcbi8vIFRoZXNlIGFyZSBjb25jZXB0dWFsIGFuZCBuZWVkIHRvIGJlIGltcGxlbWVudGVkIGJhc2VkIG9uIHlvdXIgREIgc2NoZW1hIGFuZCBlbmNyeXB0aW9uIHV0aWxpdHlcbmNvbnN0IGdldFN0b3JlZFVzZXJNU1RlYW1zVG9rZW5zID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZ1xuKTogUHJvbWlzZTx7IHJlZnJlc2hUb2tlbjogc3RyaW5nOyBhY2NvdW50OiBBY2NvdW50SW5mbyB9IHwgbnVsbD4gPT4ge1xuICBsb2dnZXIuZGVidWcoXG4gICAgYFtNU1RlYW1zU2VydmljZV0gQXR0ZW1wdGluZyB0byBmZXRjaCBzdG9yZWQgTVMgVGVhbXMgdG9rZW5zIGZvciB1c2VyICR7dXNlcklkfS5gXG4gICk7XG4gIGNvbnN0IGFkbWluQ2xpZW50ID0gY3JlYXRlQWRtaW5HcmFwaFFMQ2xpZW50KCk7XG4gIGNvbnN0IHF1ZXJ5ID0gYFxuICAgIHF1ZXJ5IEdldE1TVGVhbXNUb2tlbigkdXNlcklkOiBTdHJpbmchKSB7XG4gICAgICB1c2VyX3Rva2Vucyh3aGVyZToge3VzZXJfaWQ6IHtfZXE6ICR1c2VySWR9LCBzZXJ2aWNlOiB7X2VxOiBcIm1zdGVhbXNcIn19KSB7XG4gICAgICAgIHJlZnJlc2hfdG9rZW5cbiAgICAgICAgYWNjb3VudF9qc29uXG4gICAgICB9XG4gICAgfVxuICBgO1xuICB0cnkge1xuICAgIGNvbnN0IGRhdGEgPSBhd2FpdCBhZG1pbkNsaWVudC5yZXF1ZXN0KHF1ZXJ5LCB7IHVzZXJJZCB9KTtcbiAgICBpZiAoZGF0YS51c2VyX3Rva2VucyAmJiBkYXRhLnVzZXJfdG9rZW5zLmxlbmd0aCA+IDApIHtcbiAgICAgIGNvbnN0IHRva2VuUmVjb3JkID0gZGF0YS51c2VyX3Rva2Vuc1swXTtcbiAgICAgIGlmICghdG9rZW5SZWNvcmQucmVmcmVzaF90b2tlbiB8fCAhdG9rZW5SZWNvcmQuYWNjb3VudF9qc29uKSByZXR1cm4gbnVsbDtcbiAgICAgIGNvbnN0IHJlZnJlc2hUb2tlbiA9IGRlY3J5cHQoXG4gICAgICAgIHRva2VuUmVjb3JkLnJlZnJlc2hfdG9rZW4sXG4gICAgICAgIE1TVEVBTVNfVE9LRU5fRU5DUllQVElPTl9LRVkhXG4gICAgICApO1xuICAgICAgY29uc3QgYWNjb3VudCA9IEpTT04ucGFyc2UodG9rZW5SZWNvcmQuYWNjb3VudF9qc29uKSBhcyBBY2NvdW50SW5mbztcbiAgICAgIHJldHVybiB7IHJlZnJlc2hUb2tlbiwgYWNjb3VudCB9O1xuICAgIH1cbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICBgW01TVGVhbXNTZXJ2aWNlXSBFcnJvciBmZXRjaGluZyBNUyBUZWFtcyB0b2tlbnMgZm9yIHVzZXIgJHt1c2VySWR9OmAsXG4gICAgICBlcnJvclxuICAgICk7XG4gIH1cbiAgcmV0dXJuIG51bGw7XG59O1xuXG5jb25zdCBzdG9yZVVzZXJNU1RlYW1zVG9rZW5zID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgYXV0aFJlc3VsdDogQXV0aGVudGljYXRpb25SZXN1bHRcbik6IFByb21pc2U8dm9pZD4gPT4ge1xuICBsb2dnZXIuZGVidWcoYFtNU1RlYW1zU2VydmljZV0gU3RvcmluZyBNUyBUZWFtcyB0b2tlbnMgZm9yIHVzZXIgJHt1c2VySWR9LmApO1xuICBpZiAoIWF1dGhSZXN1bHQuYWNjb3VudCkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICdbTVNUZWFtc1NlcnZpY2VdIEFjY291bnQgaW5mbyBtaXNzaW5nIGluIEF1dGhlbnRpY2F0aW9uUmVzdWx0LiBDYW5ub3Qgc3RvcmUgdG9rZW5zLidcbiAgICApO1xuICAgIHRocm93IG5ldyBFcnJvcignQWNjb3VudCBpbmZvIG1pc3NpbmcsIGNhbm5vdCBzdG9yZSB0b2tlbnMuJyk7XG4gIH1cbiAgY29uc3QgYWNjZXNzVG9rZW4gPSBlbmNyeXB0KFxuICAgIGF1dGhSZXN1bHQuYWNjZXNzVG9rZW4sXG4gICAgTVNURUFNU19UT0tFTl9FTkNSWVBUSU9OX0tFWSFcbiAgKTtcbiAgY29uc3QgcmVmcmVzaFRva2VuID0gYXV0aFJlc3VsdC5yZWZyZXNoVG9rZW5cbiAgICA/IGVuY3J5cHQoYXV0aFJlc3VsdC5yZWZyZXNoVG9rZW4sIE1TVEVBTVNfVE9LRU5fRU5DUllQVElPTl9LRVkhKVxuICAgIDogbnVsbDtcbiAgY29uc3QgYWNjb3VudEpzb24gPSBKU09OLnN0cmluZ2lmeShhdXRoUmVzdWx0LmFjY291bnQpO1xuICBjb25zdCBleHBpcnkgPSBhdXRoUmVzdWx0LmV4cGlyZXNPbjtcblxuICBjb25zdCBhZG1pbkNsaWVudCA9IGNyZWF0ZUFkbWluR3JhcGhRTENsaWVudCgpO1xuICBjb25zdCBtdXRhdGlvbiA9IGBcbiAgICBtdXRhdGlvbiBVcHNlcnRNU1RlYW1zVG9rZW4oJHVzZXJJZDogU3RyaW5nISwgJGFjY2Vzc1Rva2VuOiBTdHJpbmchLCAkcmVmcmVzaFRva2VuOiBTdHJpbmcsICRhY2NvdW50SnNvbjoganNvbmIhLCAkZXhwaXJ5OiB0aW1lc3RhbXB0eiEpIHtcbiAgICAgIGluc2VydF91c2VyX3Rva2VucyhvYmplY3RzOiB7dXNlcl9pZDogJHVzZXJJZCwgc2VydmljZTogXCJtc3RlYW1zXCIsIGFjY2Vzc190b2tlbjogJGFjY2Vzc1Rva2VuLCByZWZyZXNoX3Rva2VuOiAkcmVmcmVzaFRva2VuLCBhY2NvdW50X2pzb246ICRhY2NvdW50SnNvbiwgZXhwaXJlc19hdDogJGV4cGlyeX0sIG9uX2NvbmZsaWN0OiB7Y29uc3RyYWludDogdXNlcl90b2tlbnNfdXNlcl9pZF9zZXJ2aWNlX2tleSwgdXBkYXRlX2NvbHVtbnM6IFthY2Nlc3NfdG9rZW4sIHJlZnJlc2hfdG9rZW4sIGFjY291bnRfanNvbiwgZXhwaXJlc19hdF19KSB7XG4gICAgICAgIGFmZmVjdGVkX3Jvd3NcbiAgICAgIH1cbiAgICB9XG4gIGA7XG4gIHRyeSB7XG4gICAgYXdhaXQgYWRtaW5DbGllbnQucmVxdWVzdChtdXRhdGlvbiwge1xuICAgICAgdXNlcklkLFxuICAgICAgYWNjZXNzVG9rZW4sXG4gICAgICByZWZyZXNoVG9rZW4sXG4gICAgICBhY2NvdW50SnNvbixcbiAgICAgIGV4cGlyeSxcbiAgICB9KTtcbiAgICBsb2dnZXIuaW5mbyhcbiAgICAgIGBbTVNUZWFtc1NlcnZpY2VdIFRva2VucyBmb3IgdXNlciAke3VzZXJJZH0gc3RvcmVkL3VwZGF0ZWQgc3VjY2Vzc2Z1bGx5LmBcbiAgICApO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbTVNUZWFtc1NlcnZpY2VdIEVycm9yIHN0b3JpbmcgTVMgVGVhbXMgdG9rZW5zIGZvciB1c2VyICR7dXNlcklkfTpgLFxuICAgICAgZXJyb3JcbiAgICApO1xuICB9XG59O1xuXG5mdW5jdGlvbiBpbml0aWFsaXplQ29uZmlkZW50aWFsQ2xpZW50QXBwKCk6IENvbmZpZGVudGlhbENsaWVudEFwcGxpY2F0aW9uIHwgbnVsbCB7XG4gIGlmIChtc2FsQ29uZmlkZW50aWFsQ2xpZW50QXBwKSB7XG4gICAgcmV0dXJuIG1zYWxDb25maWRlbnRpYWxDbGllbnRBcHA7XG4gIH1cblxuICBpZiAoXG4gICAgIU1TR1JBUEhfREVMRUdBVEVEX0NMSUVOVF9JRCB8fFxuICAgICFNU0dSQVBIX0RFTEVHQVRFRF9BVVRIT1JJVFkgfHxcbiAgICAhTVNHUkFQSF9ERUxFR0FURURfQ0xJRU5UX1NFQ1JFVFxuICApIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAnW01TVGVhbXNTZXJ2aWNlXSBNUyBHcmFwaCBBUEkgZGVsZWdhdGVkIGNsaWVudCBjcmVkZW50aWFscyBub3QgZnVsbHkgY29uZmlndXJlZC4nXG4gICAgKTtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxuICBpZiAoIU1TVEVBTVNfVE9LRU5fRU5DUllQVElPTl9LRVkpIHtcbiAgICAvLyBUaGlzIGNoZWNrIGlzIGNydWNpYWwgYmVjYXVzZSBpZiB0aGUga2V5IGlzIG1pc3NpbmcsIHdlIGNhbid0IGRlY3J5cHQvZW5jcnlwdCB0b2tlbnMgZm9yIHN0b3JhZ2UuXG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgJ1tNU1RlYW1zU2VydmljZV0gTVNURUFNU19UT0tFTl9FTkNSWVBUSU9OX0tFWSBpcyBub3QgY29uZmlndXJlZC4gQ2Fubm90IHByb2NlZWQgd2l0aCB0b2tlbiBvcGVyYXRpb25zLidcbiAgICApO1xuICAgIC8vIERlcGVuZGluZyBvbiBkZXNpcmVkIGJlaGF2aW9yLCB5b3UgbWlnaHQgdGhyb3cgYW4gZXJyb3Igb3IgcmV0dXJuIG51bGwuXG4gICAgLy8gRm9yIHNlcnZpY2UgaW5pdGlhbGl6YXRpb24sIHJldHVybmluZyBudWxsIGlzIHNhZmVyLlxuICAgIHJldHVybiBudWxsO1xuICB9XG5cbiAgY29uc3QgbXNhbENvbmZpZzogQ29uZmlndXJhdGlvbiA9IHtcbiAgICBhdXRoOiB7XG4gICAgICBjbGllbnRJZDogTVNHUkFQSF9ERUxFR0FURURfQ0xJRU5UX0lELFxuICAgICAgYXV0aG9yaXR5OiBNU0dSQVBIX0RFTEVHQVRFRF9BVVRIT1JJVFksXG4gICAgICBjbGllbnRTZWNyZXQ6IE1TR1JBUEhfREVMRUdBVEVEX0NMSUVOVF9TRUNSRVQsXG4gICAgfSxcbiAgICBzeXN0ZW06IHtcbiAgICAgIGxvZ2dlck9wdGlvbnM6IHtcbiAgICAgICAgbG9nZ2VyQ2FsbGJhY2sobG9nbGV2ZWwsIG1lc3NhZ2UsIGNvbnRhaW5zUGlpKSB7XG4gICAgICAgICAgLy8gQXZvaWQgbG9nZ2luZyB0b2tlbnMgb3IgUElJIGluIHByb2R1Y3Rpb25cbiAgICAgICAgICBpZiAoIWNvbnRhaW5zUGlpKVxuICAgICAgICAgICAgbG9nZ2VyLmRlYnVnKGBbTVNBTC0ke0xvZ0xldmVsW2xvZ2xldmVsXX1dICR7bWVzc2FnZX1gKTtcbiAgICAgICAgfSxcbiAgICAgICAgcGlpTG9nZ2luZ0VuYWJsZWQ6IGZhbHNlLCAvLyBTZXQgdG8gdHJ1ZSBPTkxZIGZvciBsb2NhbCBkZWJ1Z2dpbmcgb2YgYXV0aCBmbG93c1xuICAgICAgICBsb2dMZXZlbDogTG9nTGV2ZWwuV2FybmluZywgLy8gQWRqdXN0IGFzIG5lZWRlZDogRXJyb3IsIFdhcm5pbmcsIEluZm8sIFZlcmJvc2VcbiAgICAgIH0sXG4gICAgfSxcbiAgfTtcbiAgbXNhbENvbmZpZGVudGlhbENsaWVudEFwcCA9IG5ldyBDb25maWRlbnRpYWxDbGllbnRBcHBsaWNhdGlvbihtc2FsQ29uZmlnKTtcbiAgbG9nZ2VyLmluZm8oXG4gICAgJ1tNU1RlYW1zU2VydmljZV0gTVNBTCBDb25maWRlbnRpYWxDbGllbnRBcHBsaWNhdGlvbiBpbml0aWFsaXplZCBmb3IgZGVsZWdhdGVkIGZsb3cuJ1xuICApO1xuICByZXR1cm4gbXNhbENvbmZpZGVudGlhbENsaWVudEFwcDtcbn1cblxuZXhwb3J0IGludGVyZmFjZSBNU0dyYXBoVXNlclRva2VuRGV0YWlscyB7XG4gIGFjY2Vzc1Rva2VuOiBzdHJpbmc7XG4gIHVzZXJBYWRPYmplY3RJZDogc3RyaW5nIHwgbnVsbDsgLy8gQUFEIE9iamVjdCBJRFxuICB1c2VyUHJpbmNpcGFsTmFtZTogc3RyaW5nIHwgbnVsbDsgLy8gVVBOXG4gIGFjY291bnRJbmZvPzogQWNjb3VudEluZm87IC8vIFRoZSByYXcgYWNjb3VudCBpbmZvIGZvciBmdXJ0aGVyIHVzZSBpZiBuZWVkZWRcbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldERlbGVnYXRlZE1TR3JhcGhUb2tlbkZvclVzZXIoXG4gIHVzZXJJZDogc3RyaW5nXG4pOiBQcm9taXNlPEdyYXBoU2tpbGxSZXNwb25zZTxNU0dyYXBoVXNlclRva2VuRGV0YWlscz4+IHtcbiAgY29uc3QgY2xpZW50QXBwID0gaW5pdGlhbGl6ZUNvbmZpZGVudGlhbENsaWVudEFwcCgpO1xuICBpZiAoIWNsaWVudEFwcCkge1xuICAgIGNvbnN0IGVycm9yTXNnID0gJ01TQUwgY2xpZW50IGFwcGxpY2F0aW9uIGNvdWxkIG5vdCBiZSBpbml0aWFsaXplZC4nO1xuICAgIGxvZ2dlci5lcnJvcihgW01TVGVhbXNTZXJ2aWNlXSAke2Vycm9yTXNnfWApO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjogeyBjb2RlOiAnTVNHUkFQSF9DT05GSUdfRVJST1InLCBtZXNzYWdlOiBlcnJvck1zZyB9LFxuICAgIH07XG4gIH1cblxuICBpZiAoIU1TVEVBTVNfVE9LRU5fRU5DUllQVElPTl9LRVkpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAnW01TVGVhbXNTZXJ2aWNlXSBNU1RFQU1TX1RPS0VOX0VOQ1JZUFRJT05fS0VZIGlzIG5vdCBjb25maWd1cmVkLiBDYW5ub3QgZ2V0L3JlZnJlc2ggdG9rZW5zLidcbiAgICApO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnTVNHUkFQSF9DT05GSUdfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnVG9rZW4gZW5jcnlwdGlvbiBrZXkgbm90IGNvbmZpZ3VyZWQuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIGNvbnN0IHN0b3JlZFRva2VuSW5mbyA9IGF3YWl0IGdldFN0b3JlZFVzZXJNU1RlYW1zVG9rZW5zKHVzZXJJZCk7XG4gIGlmIChcbiAgICAhc3RvcmVkVG9rZW5JbmZvIHx8XG4gICAgIXN0b3JlZFRva2VuSW5mby5hY2NvdW50IHx8XG4gICAgIXN0b3JlZFRva2VuSW5mby5yZWZyZXNoVG9rZW5cbiAgKSB7XG4gICAgbG9nZ2VyLndhcm4oXG4gICAgICBgW01TVGVhbXNTZXJ2aWNlXSBObyBzdG9yZWQgTVMgVGVhbXMgcmVmcmVzaCB0b2tlbiBvciBhY2NvdW50IGluZm8gZm9yIHVzZXIgJHt1c2VySWR9LiBVc2VyIG5lZWRzIHRvIGF1dGhlbnRpY2F0ZS5gXG4gICAgKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ01TR1JBUEhfQVVUSF9SRVFVSVJFRCcsXG4gICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgJ1VzZXIgYXV0aGVudGljYXRpb24gcmVxdWlyZWQgZm9yIE1TIFRlYW1zIChubyByZWZyZXNoIHRva2VuIG9yIGFjY291bnQgaW5mbykuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIHRyeSB7XG4gICAgLy8gTVNBTCdzIGFjcXVpcmVUb2tlblNpbGVudCB3aWxsIHVzZSBhIGNhY2hlZCBhY2Nlc3MgdG9rZW4gaWYgdmFsaWQsXG4gICAgLy8gb3IgdXNlIHRoZSByZWZyZXNoIHRva2VuIHRvIGdldCBhIG5ldyBhY2Nlc3MgdG9rZW4gaWYgdGhlIGNhY2hlZCBvbmUgaXMgZXhwaXJlZC5cbiAgICBjb25zdCBzaWxlbnRSZXF1ZXN0OiBTaWxlbnRGbG93UmVxdWVzdCA9IHtcbiAgICAgIGFjY291bnQ6IHN0b3JlZFRva2VuSW5mby5hY2NvdW50LCAvLyBBY2NvdW50SW5mbyBvYmplY3QgZnJvbSB3aGVuIHRva2VuIHdhcyBmaXJzdCBhY3F1aXJlZFxuICAgICAgc2NvcGVzOiBNU0dSQVBIX0RFTEVHQVRFRF9TQ09QRVMhLCAvLyBFbnN1cmUgc2NvcGVzIGFyZSBkZWZpbmVkIGFzIGFuIGFycmF5XG4gICAgICBmb3JjZVJlZnJlc2g6IGZhbHNlLCAvLyBTZXQgdG8gdHJ1ZSBvbmx5IGlmIHlvdSBzdXNwZWN0IHRoZSBjYWNoZWQgQVQgaXMgc3RhbGUgYnV0IG5vdCBleHBpcmVkXG4gICAgfTtcblxuICAgIGxldCBhdXRoUmVzdWx0OiBBdXRoZW50aWNhdGlvblJlc3VsdCB8IG51bGwgPSBudWxsO1xuICAgIHRyeSB7XG4gICAgICBsb2dnZXIuZGVidWcoXG4gICAgICAgIGBbTVNUZWFtc1NlcnZpY2VdIEF0dGVtcHRpbmcgdG8gYWNxdWlyZSB0b2tlbiBzaWxlbnRseSBmb3IgdXNlciAke3VzZXJJZH0gd2l0aCBhY2NvdW50ICR7c3RvcmVkVG9rZW5JbmZvLmFjY291bnQuaG9tZUFjY291bnRJZH1gXG4gICAgICApO1xuICAgICAgYXV0aFJlc3VsdCA9IGF3YWl0IGNsaWVudEFwcC5hY3F1aXJlVG9rZW5TaWxlbnQoc2lsZW50UmVxdWVzdCk7XG4gICAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgIGBbTVNUZWFtc1NlcnZpY2VdIFNpbGVudCB0b2tlbiBhY3F1aXNpdGlvbiBmYWlsZWQgZm9yIHVzZXIgJHt1c2VySWR9IChFcnJvcjogJHtlcnJvci5lcnJvckNvZGUgfHwgZXJyb3IubmFtZX0pLiBBdHRlbXB0aW5nIHJlZnJlc2ggdmlhIHN0b3JlZCByZWZyZXNoIHRva2VuIGlmIGFwcGxpY2FibGUuYFxuICAgICAgKTtcbiAgICAgIC8vIENoZWNrIGlmIGVycm9yIGlzIGR1ZSB0byBuZWVkaW5nIGEgcmVmcmVzaCB0b2tlbiBvciBpZiBpdCdzIGFuIEludGVyYWN0aW9uUmVxdWlyZWQgZXJyb3JcbiAgICAgIC8vIFNvbWUgZXJyb3JzIChsaWtlIG5vX3Rva2Vuc19mb3VuZCkgbWlnaHQgbWVhbiB3ZSBzaG91bGQgdHJ5IGFjcXVpcmVUb2tlbkJ5UmVmcmVzaFRva2VuXG4gICAgICBpZiAoXG4gICAgICAgIGVycm9yLm5hbWUgPT09ICdDbGllbnRBdXRoRXJyb3InICYmXG4gICAgICAgIChlcnJvci5lcnJvckNvZGUgPT09ICdub190b2tlbnNfZm91bmQnIHx8XG4gICAgICAgICAgZXJyb3IuZXJyb3JDb2RlID09PSAndG9rZW5fZXhwaXJlZF9lcnJvcicgfHxcbiAgICAgICAgICBlcnJvci5tZXNzYWdlPy5pbmNsdWRlcyhcbiAgICAgICAgICAgICcgUMWZaSBwb2t1c3UgbyB6w61za8OhbsOtIHRva2VudSB6IG1lemlwYW3Em3RpIG5lYnlsIG5hbGV6ZW4gxb7DoWRuw70gcGxhdG7DvSBwxZnDrXN0dXBvdsO9IHRva2VuLidcbiAgICAgICAgICApKVxuICAgICAgKSB7XG4gICAgICAgIC8vIFRoZSBsYXN0IGVycm9yIG1lc3NhZ2UgaXMgYW4gZXhhbXBsZSBvZiBhIGxvY2FsaXplZCBlcnJvciB0aGF0IG1pZ2h0IGluZGljYXRlIG5vIHZhbGlkIEFUIGluIGNhY2hlLlxuICAgICAgICB0cnkge1xuICAgICAgICAgIGxvZ2dlci5pbmZvKFxuICAgICAgICAgICAgYFtNU1RlYW1zU2VydmljZV0gQXR0ZW1wdGluZyBhY3F1aXJlVG9rZW5CeVJlZnJlc2hUb2tlbiBmb3IgdXNlciAke3VzZXJJZH0uYFxuICAgICAgICAgICk7XG4gICAgICAgICAgY29uc3QgcmVmcmVzaFRva2VuUmVxdWVzdCA9IHtcbiAgICAgICAgICAgIHJlZnJlc2hUb2tlbjogc3RvcmVkVG9rZW5JbmZvLnJlZnJlc2hUb2tlbixcbiAgICAgICAgICAgIHNjb3BlczogTVNHUkFQSF9ERUxFR0FURURfU0NPUEVTISxcbiAgICAgICAgICB9O1xuICAgICAgICAgIGF1dGhSZXN1bHQgPVxuICAgICAgICAgICAgYXdhaXQgY2xpZW50QXBwLmFjcXVpcmVUb2tlbkJ5UmVmcmVzaFRva2VuKHJlZnJlc2hUb2tlblJlcXVlc3QpO1xuICAgICAgICB9IGNhdGNoIChyZWZyZXNoRXJyb3I6IGFueSkge1xuICAgICAgICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICAgICAgIGBbTVNUZWFtc1NlcnZpY2VdIEZhaWxlZCB0byBhY3F1aXJlIHRva2VuIGJ5IHJlZnJlc2ggdG9rZW4gZm9yIHVzZXIgJHt1c2VySWR9OmAsXG4gICAgICAgICAgICByZWZyZXNoRXJyb3JcbiAgICAgICAgICApO1xuICAgICAgICAgIC8vIElmIHJlZnJlc2ggdG9rZW4gaXRzZWxmIGlzIGludmFsaWQvZXhwaXJlZCwgdXNlciBtdXN0IHJlLWF1dGhlbnRpY2F0ZS5cbiAgICAgICAgICBpZiAoXG4gICAgICAgICAgICByZWZyZXNoRXJyb3IubmFtZSA9PT0gJ0ludGVyYWN0aW9uUmVxdWlyZWRBdXRoRXJyb3InIHx8XG4gICAgICAgICAgICByZWZyZXNoRXJyb3IuZXJyb3JDb2RlID09PSAnaW52YWxpZF9ncmFudCcgfHxcbiAgICAgICAgICAgIHJlZnJlc2hFcnJvci5tZXNzYWdlPy5pbmNsdWRlcygnQUFEU1RTNzAwMDgnKVxuICAgICAgICAgICkge1xuICAgICAgICAgICAgLy8gaW52YWxpZF9ncmFudCBvciBzaW1pbGFyXG4gICAgICAgICAgICByZXR1cm4ge1xuICAgICAgICAgICAgICBvazogZmFsc2UsXG4gICAgICAgICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgICAgICAgY29kZTogJ01TR1JBUEhfSU5URVJBQ1RJT05fUkVRVUlSRUQnLFxuICAgICAgICAgICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgICAgICAgICAnUmVmcmVzaCB0b2tlbiBpbnZhbGlkIG9yIGV4cGlyZWQuIFVzZXIgbXVzdCByZS1hdXRoZW50aWNhdGUgd2l0aCBNaWNyb3NvZnQgVGVhbXMuJyxcbiAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIH07XG4gICAgICAgICAgfVxuICAgICAgICAgIHJldHVybiB7XG4gICAgICAgICAgICBvazogZmFsc2UsXG4gICAgICAgICAgICBlcnJvcjoge1xuICAgICAgICAgICAgICBjb2RlOiAnTVNHUkFQSF9SRUZSRVNIX0ZBSUxFRCcsXG4gICAgICAgICAgICAgIG1lc3NhZ2U6IGBGYWlsZWQgdG8gcmVmcmVzaCB0b2tlbjogJHtyZWZyZXNoRXJyb3IubWVzc2FnZX1gLFxuICAgICAgICAgICAgICBkZXRhaWxzOiByZWZyZXNoRXJyb3IsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIH07XG4gICAgICAgIH1cbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIHRocm93IGVycm9yOyAvLyBSZS10aHJvdyBvdGhlciBzaWxlbnQgZXJyb3JzIG5vdCBoYW5kbGVkIGJ5IHJlZnJlc2ggdG9rZW4gYXR0ZW1wdFxuICAgICAgfVxuICAgIH1cblxuICAgIGlmIChhdXRoUmVzdWx0ICYmIGF1dGhSZXN1bHQuYWNjZXNzVG9rZW4pIHtcbiAgICAgIC8vIEFjY291bnQgb2JqZWN0IGluIGF1dGhSZXN1bHQgbWlnaHQgYmUgdXBkYXRlZCAoZS5nLiBpZiB0b2tlbnMgd2VyZSByZWZyZXNoZWQgd2l0aCBhIG5ldyBhY2NvdW50IHN0YXRlIGZyb20gSWRQKVxuICAgICAgYXdhaXQgc3RvcmVVc2VyTVNUZWFtc1Rva2Vucyh1c2VySWQsIGF1dGhSZXN1bHQpO1xuICAgICAgbG9nZ2VyLmluZm8oXG4gICAgICAgIGBbTVNUZWFtc1NlcnZpY2VdIFN1Y2Nlc3NmdWxseSBhY3F1aXJlZC9yZWZyZXNoZWQgdG9rZW4gZm9yIHVzZXIgJHt1c2VySWR9LmBcbiAgICAgICk7XG5cbiAgICAgIGxldCB1c2VyQWFkT2JqZWN0SWQ6IHN0cmluZyB8IG51bGwgPSBudWxsO1xuICAgICAgbGV0IHVzZXJQcmluY2lwYWxOYW1lOiBzdHJpbmcgfCBudWxsID0gbnVsbDtcblxuICAgICAgaWYgKGF1dGhSZXN1bHQuYWNjb3VudCkge1xuICAgICAgICAvLyBQcmVmZXIgb2lkIGZyb20gaWRUb2tlbkNsYWltcyBpZiBhdmFpbGFibGVcbiAgICAgICAgaWYgKGF1dGhSZXN1bHQuYWNjb3VudC5pZFRva2VuQ2xhaW1zPy5vaWQpIHtcbiAgICAgICAgICB1c2VyQWFkT2JqZWN0SWQgPSBhdXRoUmVzdWx0LmFjY291bnQuaWRUb2tlbkNsYWltcy5vaWQ7XG4gICAgICAgIH0gZWxzZSBpZiAoYXV0aFJlc3VsdC5hY2NvdW50LmhvbWVBY2NvdW50SWQpIHtcbiAgICAgICAgICAvLyBob21lQWNjb3VudElkIGlzIHVzdWFsbHkgPE9JRD4uPFRJRD5cbiAgICAgICAgICB1c2VyQWFkT2JqZWN0SWQgPSBhdXRoUmVzdWx0LmFjY291bnQuaG9tZUFjY291bnRJZC5zcGxpdCgnLicpWzBdO1xuICAgICAgICB9XG4gICAgICAgIHVzZXJQcmluY2lwYWxOYW1lID0gYXV0aFJlc3VsdC5hY2NvdW50LnVzZXJuYW1lOyAvLyBVc3VhbGx5IFVQTlxuXG4gICAgICAgIGxvZ2dlci5pbmZvKFxuICAgICAgICAgIGBbTVNUZWFtc1NlcnZpY2VdIEV4dHJhY3RlZCBBQUQgT0lEOiAke3VzZXJBYWRPYmplY3RJZH0sIFVQTjogJHt1c2VyUHJpbmNpcGFsTmFtZX0gZnJvbSBNU0FMIEFjY291bnRJbmZvIGZvciB1c2VyICR7dXNlcklkfS5gXG4gICAgICAgICk7XG5cbiAgICAgICAgLy8gT3B0aW9uYWw6IFZlcmlmeS9mZXRjaCB3aXRoIC9tZSBpZiBuZWVkZWQsIG9yIGlmIHNwZWNpZmljIGNsYWltcyBhcmUgbWlzc2luZ1xuICAgICAgICAvLyBGb3IgaW5zdGFuY2UsIGlmIG9ubHkgaG9tZUFjY291bnRJZCB3YXMgYXZhaWxhYmxlIGFuZCBub3QgaWRUb2tlbkNsYWltcy5vaWQsXG4gICAgICAgIC8vIGFuZCB5b3Ugd2FudGVkIHRvIGJlIGNlcnRhaW4gb3IgZ2V0IG90aGVyIGRldGFpbHMgbGlrZSBkaXNwbGF5IG5hbWUuXG4gICAgICAgIC8vIEZvciBub3csIHdlIHJlbHkgb24gdGhlIE1TQUwgYWNjb3VudCBvYmplY3QuXG4gICAgICAgIC8vIGlmICghdXNlckFhZE9iamVjdElkICYmIGF1dGhSZXN1bHQuYWNjZXNzVG9rZW4pIHsgLyogLi4uIGNhbGwgL21lIC4uLiAqLyB9XG4gICAgICB9XG5cbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiB0cnVlLFxuICAgICAgICBkYXRhOiB7XG4gICAgICAgICAgYWNjZXNzVG9rZW46IGF1dGhSZXN1bHQuYWNjZXNzVG9rZW4sXG4gICAgICAgICAgdXNlckFhZE9iamVjdElkOiB1c2VyQWFkT2JqZWN0SWQsXG4gICAgICAgICAgdXNlclByaW5jaXBhbE5hbWU6IHVzZXJQcmluY2lwYWxOYW1lLFxuICAgICAgICAgIGFjY291bnRJbmZvOiBhdXRoUmVzdWx0LmFjY291bnQsIC8vIFBhc3MgdGhlIGZ1bGwgYWNjb3VudEluZm8gaWYgdGhlIGNhbGxlciBtaWdodCBuZWVkIGl0XG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH0gZWxzZSB7XG4gICAgICBsb2dnZXIud2FybihcbiAgICAgICAgYFtNU1RlYW1zU2VydmljZV0gVG9rZW4gYWNxdWlzaXRpb24geWllbGRlZCBudWxsL2VtcHR5IGFjY2Vzc1Rva2VuIGZvciB1c2VyICR7dXNlcklkfSB3aXRob3V0IHRocm93aW5nLiBUaGlzIGlzIHVuZXhwZWN0ZWQuYFxuICAgICAgKTtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICBjb2RlOiAnTVNHUkFQSF9BVVRIX1VORVhQRUNURURfTk9fVE9LRU4nLFxuICAgICAgICAgIG1lc3NhZ2U6ICdUb2tlbiBhY3F1aXNpdGlvbiByZXR1cm5lZCBubyBhY2Nlc3MgdG9rZW4gdW5leHBlY3RlZGx5LicsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH1cbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbTVNUZWFtc1NlcnZpY2VdIEdlbmVyYWwgZXJyb3IgaW4gZ2V0RGVsZWdhdGVkTVNHcmFwaFRva2VuRm9yVXNlciBmb3IgJHt1c2VySWR9OmAsXG4gICAgICBlcnJvclxuICAgICk7XG4gICAgaWYgKFxuICAgICAgZXJyb3IubmFtZSA9PT0gJ0ludGVyYWN0aW9uUmVxdWlyZWRBdXRoRXJyb3InIHx8XG4gICAgICAoZXJyb3IubmFtZSA9PT0gJ0NsaWVudEF1dGhFcnJvcicgJiZcbiAgICAgICAgZXJyb3IuZXJyb3JDb2RlID09PSAnbm9fYWNjb3VudF9pbl9zaWxlbnRfcmVxdWVzdCcpXG4gICAgKSB7XG4gICAgICAvLyBUaGlzIGVycm9yIG1lYW5zIHRoZSB1c2VyIG5lZWRzIHRvIGdvIHRocm91Z2ggdGhlIGludGVyYWN0aXZlIHNpZ24taW4gcHJvY2VzcyBhZ2Fpbi5cbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICBjb2RlOiAnTVNHUkFQSF9JTlRFUkFDVElPTl9SRVFVSVJFRCcsXG4gICAgICAgICAgbWVzc2FnZTpcbiAgICAgICAgICAgICdVc2VyIGludGVyYWN0aW9uIHJlcXVpcmVkLiBQbGVhc2UgcmUtYXV0aGVudGljYXRlIHdpdGggTWljcm9zb2Z0IFRlYW1zLicsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH1cbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ01TR1JBUEhfQVVUSF9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IGBGYWlsZWQgdG8gYWNxdWlyZSBNUyBHcmFwaCB0b2tlbiBmb3IgdXNlciAke3VzZXJJZH06ICR7ZXJyb3IubWVzc2FnZX1gLFxuICAgICAgICBkZXRhaWxzOiBlcnJvcixcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2VuZXJhdGVUZWFtc0F1dGhVcmwoXG4gIHVzZXJJZEZvckNvbnRleHQ6IHN0cmluZyxcbiAgc3RhdGU/OiBzdHJpbmdcbik6IFByb21pc2U8c3RyaW5nIHwgbnVsbD4ge1xuICBjb25zdCBjbGllbnRBcHAgPSBpbml0aWFsaXplQ29uZmlkZW50aWFsQ2xpZW50QXBwKCk7IC8vIENvcnJlY3RseSB1c2UgdGhlIGNvbmZpZGVudGlhbCBjbGllbnQgYXBwXG4gIGlmICghY2xpZW50QXBwKSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgJ1tNU1RlYW1zU2VydmljZV0gTVNBTCBjbGllbnQgbm90IGluaXRpYWxpemVkLCBjYW5ub3QgZ2VuZXJhdGUgYXV0aCBVUkwuJ1xuICAgICk7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cblxuICBpZiAoIU1TR1JBUEhfREVMRUdBVEVEX1NDT1BFUyB8fCBNU0dSQVBIX0RFTEVHQVRFRF9TQ09QRVMubGVuZ3RoID09PSAwKSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgJ1tNU1RlYW1zU2VydmljZV0gTVNHUkFQSF9ERUxFR0FURURfU0NPUEVTIGFyZSBub3QgY29uZmlndXJlZC4nXG4gICAgKTtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxuICBpZiAoIU1TR1JBUEhfREVMRUdBVEVEX1JFRElSRUNUX1VSTCkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICdbTVNUZWFtc1NlcnZpY2VdIE1TR1JBUEhfREVMRUdBVEVEX1JFRElSRUNUX1VSTCBpcyBub3QgY29uZmlndXJlZC4nXG4gICAgKTtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxuXG4gIHRyeSB7XG4gICAgY29uc3QgYXV0aENvZGVVcmxQYXJhbWV0ZXJzID0ge1xuICAgICAgc2NvcGVzOiBNU0dSQVBIX0RFTEVHQVRFRF9TQ09QRVMsXG4gICAgICByZWRpcmVjdFVyaTogTVNHUkFQSF9ERUxFR0FURURfUkVESVJFQ1RfVVJMLFxuICAgICAgc3RhdGU6IHN0YXRlLCAvLyBGb3IgQ1NSRiBwcm90ZWN0aW9uOyBzaG91bGQgYmUgZ2VuZXJhdGVkLCB0ZW1wb3JhcmlseSBzdG9yZWQsIGFuZCB2YWxpZGF0ZWQgYnkgY2FsbGVyIG9uIGNhbGxiYWNrXG4gICAgfTtcbiAgICBjb25zdCBhdXRoVXJsID0gYXdhaXQgY2xpZW50QXBwLmdldEF1dGhDb2RlVXJsKGF1dGhDb2RlVXJsUGFyYW1ldGVycyk7XG4gICAgbG9nZ2VyLmluZm8oXG4gICAgICBgW01TVGVhbXNTZXJ2aWNlXSBHZW5lcmF0ZWQgTVMgVGVhbXMgYXV0aCBVUkwgZm9yIGNvbnRleHQgdXNlcjogJHt1c2VySWRGb3JDb250ZXh0fS5gXG4gICAgKTtcbiAgICByZXR1cm4gYXV0aFVybDtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbTVNUZWFtc1NlcnZpY2VdIEVycm9yIGdlbmVyYXRpbmcgTVMgVGVhbXMgYXV0aCBVUkwgZm9yIGNvbnRleHQgdXNlciAke3VzZXJJZEZvckNvbnRleHR9OmAsXG4gICAgICBlcnJvclxuICAgICk7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZVRlYW1zQXV0aENhbGxiYWNrKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgYXV0aG9yaXphdGlvbkNvZGU6IHN0cmluZ1xuKTogUHJvbWlzZTxHcmFwaFNraWxsUmVzcG9uc2U8Ym9vbGVhbj4+IHtcbiAgY29uc3QgY2xpZW50QXBwID0gaW5pdGlhbGl6ZUNvbmZpZGVudGlhbENsaWVudEFwcCgpOyAvLyBDb3JyZWN0bHkgdXNlIHRoZSBjb25maWRlbnRpYWwgY2xpZW50IGFwcFxuICBpZiAoIWNsaWVudEFwcCkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICdbTVNUZWFtc1NlcnZpY2VdIE1TQUwgY2xpZW50IG5vdCBpbml0aWFsaXplZCwgY2Fubm90IGhhbmRsZSBhdXRoIGNhbGxiYWNrLidcbiAgICApO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnTVNHUkFQSF9DT05GSUdfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnTVNBTCBjbGllbnQgbm90IGluaXRpYWxpemVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cblxuICBpZiAoIU1TVEVBTVNfVE9LRU5fRU5DUllQVElPTl9LRVkpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAnW01TVGVhbXNTZXJ2aWNlXSBNU1RFQU1TX1RPS0VOX0VOQ1JZUFRJT05fS0VZIGlzIG5vdCBjb25maWd1cmVkLiBDYW5ub3Qgc3RvcmUgdG9rZW5zIHBvc3QgY2FsbGJhY2suJ1xuICAgICk7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdNU0dSQVBIX0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdUb2tlbiBlbmNyeXB0aW9uIGtleSBub3QgY29uZmlndXJlZCBmb3IgY2FsbGJhY2suJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBpZiAoIU1TR1JBUEhfREVMRUdBVEVEX1NDT1BFUyB8fCBNU0dSQVBIX0RFTEVHQVRFRF9TQ09QRVMubGVuZ3RoID09PSAwKSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgJ1tNU1RlYW1zU2VydmljZV0gTVNHUkFQSF9ERUxFR0FURURfU0NPUEVTIGFyZSBub3QgY29uZmlndXJlZCBmb3IgY2FsbGJhY2sgdG9rZW4gcmVxdWVzdC4nXG4gICAgKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ01TR1JBUEhfQ09ORklHX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ1Njb3BlcyBub3QgY29uZmlndXJlZCBmb3IgY2FsbGJhY2suJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBpZiAoIU1TR1JBUEhfREVMRUdBVEVEX1JFRElSRUNUX1VSTCkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICdbTVNUZWFtc1NlcnZpY2VdIE1TR1JBUEhfREVMRUdBVEVEX1JFRElSRUNUX1VSTCBpcyBub3QgY29uZmlndXJlZCBmb3IgY2FsbGJhY2sgdG9rZW4gcmVxdWVzdC4nXG4gICAgKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ01TR1JBUEhfQ09ORklHX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ1JlZGlyZWN0IFVSTCBub3QgY29uZmlndXJlZCBmb3IgY2FsbGJhY2suJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIHRyeSB7XG4gICAgY29uc3QgdG9rZW5SZXF1ZXN0OiBBdXRob3JpemF0aW9uQ29kZVJlcXVlc3QgPSB7XG4gICAgICBjb2RlOiBhdXRob3JpemF0aW9uQ29kZSxcbiAgICAgIHNjb3BlczogTVNHUkFQSF9ERUxFR0FURURfU0NPUEVTLFxuICAgICAgcmVkaXJlY3RVcmk6IE1TR1JBUEhfREVMRUdBVEVEX1JFRElSRUNUX1VSTCxcbiAgICB9O1xuICAgIGNvbnN0IGF1dGhSZXN1bHQgPSBhd2FpdCBjbGllbnRBcHAuYWNxdWlyZVRva2VuQnlDb2RlKHRva2VuUmVxdWVzdCk7XG5cbiAgICBpZiAoYXV0aFJlc3VsdCAmJiBhdXRoUmVzdWx0LmFjY2Vzc1Rva2VuICYmIGF1dGhSZXN1bHQuYWNjb3VudCkge1xuICAgICAgYXdhaXQgc3RvcmVVc2VyTVNUZWFtc1Rva2Vucyh1c2VySWQsIGF1dGhSZXN1bHQpOyAvLyBVc2VzIHBsYWNlaG9sZGVyXG4gICAgICBsb2dnZXIuaW5mbyhcbiAgICAgICAgYFtNU1RlYW1zU2VydmljZV0gU3VjY2Vzc2Z1bGx5IGhhbmRsZWQgTVMgVGVhbXMgYXV0aCBjYWxsYmFjayBhbmQgaW5pdGlhdGVkIHRva2VuIHN0b3JhZ2UgZm9yIHVzZXIgJHt1c2VySWR9LmBcbiAgICAgICk7XG4gICAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogdHJ1ZSB9O1xuICAgIH0gZWxzZSB7XG4gICAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAgIGBbTVNUZWFtc1NlcnZpY2VdIEZhaWxlZCB0byBhY3F1aXJlIHRva2VuIGJ5IGNvZGUgZm9yIHVzZXIgJHt1c2VySWR9LiBBdXRoUmVzdWx0IGludmFsaWQgb3IgYWNjb3VudCBtaXNzaW5nLmAsXG4gICAgICAgIGF1dGhSZXN1bHRcbiAgICAgICk7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgY29kZTogJ01TR1JBUEhfQVVUSF9DQUxMQkFDS19GQUlMRUQnLFxuICAgICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgICAnQ291bGQgbm90IHByb2Nlc3MgYXV0aCBjb2RlIG9yIHZpdGFsIHRva2VuL2FjY291bnQgaW5mbyBtaXNzaW5nLicsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH1cbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbTVNUZWFtc1NlcnZpY2VdIEVycm9yIGluIGhhbmRsZVRlYW1zQXV0aENhbGxiYWNrIGZvciB1c2VyICR7dXNlcklkfTpgLFxuICAgICAgZXJyb3JcbiAgICApO1xuICAgIC8vIFByb3ZpZGUgbW9yZSBzcGVjaWZpYyBlcnJvciBpZiBNU0FMIGdpdmVzIG9uZSAoZS5nLiBpbnZhbGlkX2dyYW50IGZvciB1c2VkL2V4cGlyZWQgY29kZSlcbiAgICBjb25zdCBlcnJvckNvZGUgPSBlcnJvci5lcnJvckNvZGUgfHwgJ01TR1JBUEhfQVVUSF9FUlJPUic7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6IGVycm9yQ29kZSxcbiAgICAgICAgbWVzc2FnZTogYENhbGxiYWNrIGhhbmRsaW5nIGVycm9yOiAke2Vycm9yLm1lc3NhZ2V9YCxcbiAgICAgICAgZGV0YWlsczogZXJyb3IsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn1cblxuLy8gRXhpc3RpbmcgbWVldGluZyBmdW5jdGlvbnMgbmVlZCB0byBiZSBhZGFwdGVkIHRvIHVzZSBnZXREZWxlZ2F0ZWRNU0dyYXBoVG9rZW5Gb3JVc2VyXG4vLyBGb3IgZXhhbXBsZTpcbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBsaXN0TWljcm9zb2Z0VGVhbXNNZWV0aW5ncyhcbiAgYXRvbVVzZXJJZDogc3RyaW5nLCAvLyBDaGFuZ2VkIGZyb20gdXNlclByaW5jaXBhbE5hbWVPcklkIHRvIEF0b20ncyBpbnRlcm5hbCB1c2VySWRcbiAgb3B0aW9ucz86IHtcbiAgICBsaW1pdD86IG51bWJlcjtcbiAgICBuZXh0TGluaz86IHN0cmluZztcbiAgICBmaWx0ZXJGb3JUZWFtc01lZXRpbmdzPzogYm9vbGVhbjsgLy8gTW9yZSBkZXNjcmlwdGl2ZSBuYW1lXG4gIH1cbik6IFByb21pc2U8R3JhcGhTa2lsbFJlc3BvbnNlPExpc3RNU0dyYXBoRXZlbnRzRGF0YT4+IHtcbiAgbG9nZ2VyLmRlYnVnKFxuICAgIGBbTVNUZWFtc1NlcnZpY2VdIGxpc3RNaWNyb3NvZnRUZWFtc01lZXRpbmdzIGNhbGxlZCBmb3IgQXRvbSB1c2VyOiAke2F0b21Vc2VySWR9LCBvcHRpb25zOmAsXG4gICAgb3B0aW9uc1xuICApO1xuXG4gIGNvbnN0IHRva2VuUmVzcG9uc2UgPSBhd2FpdCBnZXREZWxlZ2F0ZWRNU0dyYXBoVG9rZW5Gb3JVc2VyKGF0b21Vc2VySWQpO1xuICBpZiAoIXRva2VuUmVzcG9uc2Uub2sgfHwgIXRva2VuUmVzcG9uc2UuZGF0YSkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjogdG9rZW5SZXNwb25zZS5lcnJvciB8fCB7XG4gICAgICAgIGNvZGU6ICdNU0dSQVBIX0FVVEhfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnRmFpbGVkIHRvIG9idGFpbiBNUyBHcmFwaCBhY2Nlc3MgdG9rZW4gZm9yIGxpc3RpbmcgbWVldGluZ3MuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBjb25zdCB0b2tlbiA9IHRva2VuUmVzcG9uc2UuZGF0YTtcblxuICBsZXQgcmVxdWVzdFVybCA9IG9wdGlvbnM/Lm5leHRMaW5rO1xuXG4gIGlmICghcmVxdWVzdFVybCkge1xuICAgIGNvbnN0IHNlbGVjdFBhcmFtcyA9XG4gICAgICAnaWQsc3ViamVjdCxzdGFydCxlbmQsaXNPbmxpbmVNZWV0aW5nLG9ubGluZU1lZXRpbmcsd2ViTGluayxib2R5UHJldmlldyc7XG4gICAgY29uc3Qgb3JkZXJCeVBhcmFtcyA9ICdzdGFydC9kYXRlVGltZSBBU0MnOyAvLyBHcmFwaCBBUEkgdXNlcyBQYXNjYWxDYXNlIGZvciBPRGF0YSBxdWVyeSBwYXJhbXNcbiAgICBjb25zdCB0b3BQYXJhbXMgPSBvcHRpb25zPy5saW1pdCB8fCAxMDtcbiAgICBsZXQgZmlsdGVyUGFyYW1zVmFsdWUgPSAnJztcblxuICAgIC8vIEZpbHRlciBmb3IgYWN0dWFsIFRlYW1zIG1lZXRpbmdzIGlmIHJlcXVlc3RlZCwgb3RoZXJ3aXNlIGZldGNoIGFsbCBjYWxlbmRhciBldmVudHMgZm9yIHRoZSB1c2VyXG4gICAgaWYgKG9wdGlvbnM/LmZpbHRlckZvclRlYW1zTWVldGluZ3MgPT09IHRydWUpIHtcbiAgICAgIGZpbHRlclBhcmFtc1ZhbHVlID0gYGlzT25saW5lTWVldGluZyBlcSB0cnVlIGFuZCBvbmxpbmVNZWV0aW5nL29ubGluZU1lZXRpbmdQcm92aWRlciBlcSAndGVhbXNGb3JCdXNpbmVzcydgO1xuICAgIH1cblxuICAgIGNvbnN0IHF1ZXJ5UGFyYW1zID0gbmV3IFVSTFNlYXJjaFBhcmFtcygpO1xuICAgIHF1ZXJ5UGFyYW1zLmFwcGVuZCgnJHNlbGVjdCcsIHNlbGVjdFBhcmFtcyk7XG4gICAgcXVlcnlQYXJhbXMuYXBwZW5kKCckb3JkZXJCeScsIG9yZGVyQnlQYXJhbXMpOyAvLyBDb3JyZWN0ZWQgZnJvbSAnJG9yZGVyYnknXG4gICAgcXVlcnlQYXJhbXMuYXBwZW5kKCckdG9wJywgdG9wUGFyYW1zLnRvU3RyaW5nKCkpO1xuICAgIGlmIChmaWx0ZXJQYXJhbXNWYWx1ZSkge1xuICAgICAgcXVlcnlQYXJhbXMuYXBwZW5kKCckZmlsdGVyJywgZmlsdGVyUGFyYW1zVmFsdWUpO1xuICAgIH1cbiAgICAvLyBVc2UgJy9tZS9jYWxlbmRhci9ldmVudHMnIGZvciBkZWxlZ2F0ZWQgcGVybWlzc2lvbnMgdG8gZ2V0IGV2ZW50cyBmcm9tIHRoZSBzaWduZWQtaW4gdXNlcidzIHByaW1hcnkgY2FsZW5kYXJcbiAgICByZXF1ZXN0VXJsID0gYCR7TVNHUkFQSF9BUElfQkFTRV9VUkx9L21lL2NhbGVuZGFyL2V2ZW50cz8ke3F1ZXJ5UGFyYW1zLnRvU3RyaW5nKCl9YDtcbiAgfVxuXG4gIHRyeSB7XG4gICAgbG9nZ2VyLmRlYnVnKFxuICAgICAgYFtNU1RlYW1zU2VydmljZV0gUmVxdWVzdGluZyBtZWV0aW5ncyBmcm9tIE1TIEdyYXBoOiAke3JlcXVlc3RVcmx9YFxuICAgICk7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcy5nZXQocmVxdWVzdFVybCwge1xuICAgICAgaGVhZGVyczogeyBBdXRob3JpemF0aW9uOiBgQmVhcmVyICR7dG9rZW59YCB9LFxuICAgIH0pO1xuICAgIHJldHVybiB7XG4gICAgICBvazogdHJ1ZSxcbiAgICAgIGRhdGE6IHtcbiAgICAgICAgZXZlbnRzOiByZXNwb25zZS5kYXRhLnZhbHVlIGFzIE1TR3JhcGhFdmVudFtdLFxuICAgICAgICBuZXh0TGluazogcmVzcG9uc2UuZGF0YVsnQG9kYXRhLm5leHRMaW5rJ10gfHwgdW5kZWZpbmVkLFxuICAgICAgfSxcbiAgICB9O1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgY29uc3QgYXhpb3NFcnJvciA9IGVycm9yIGFzIEF4aW9zRXJyb3I7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFtNU1RlYW1zU2VydmljZV0gRXJyb3IgbGlzdGluZyBNUyBUZWFtcyBtZWV0aW5ncyBmb3IgQXRvbSB1c2VyICR7YXRvbVVzZXJJZH06YCxcbiAgICAgIGF4aW9zRXJyb3IubWVzc2FnZSxcbiAgICAgIGF4aW9zRXJyb3IucmVzcG9uc2U/LmRhdGFcbiAgICApO1xuICAgIGNvbnN0IGVycm9yRGF0YSA9IGF4aW9zRXJyb3IucmVzcG9uc2U/LmRhdGEgYXMgYW55O1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiBlcnJvckRhdGE/LmVycm9yPy5jb2RlIHx8ICdNU0dSQVBIX0FQSV9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgZXJyb3JEYXRhPy5lcnJvcj8ubWVzc2FnZSB8fFxuICAgICAgICAgIGF4aW9zRXJyb3IubWVzc2FnZSB8fFxuICAgICAgICAgICdGYWlsZWQgdG8gbGlzdCBNUyBUZWFtcyBtZWV0aW5ncycsXG4gICAgICAgIGRldGFpbHM6IGVycm9yRGF0YT8uZXJyb3IgfHwgZXJyb3JEYXRhLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRNaWNyb3NvZnRUZWFtc01lZXRpbmdEZXRhaWxzKFxuICBhdG9tVXNlcklkOiBzdHJpbmcsIC8vIENoYW5nZWQgZnJvbSB1c2VyUHJpbmNpcGFsTmFtZU9ySWQgdG8gQXRvbSdzIGludGVybmFsIHVzZXJJZFxuICBldmVudElkOiBzdHJpbmdcbik6IFByb21pc2U8R3JhcGhTa2lsbFJlc3BvbnNlPE1TR3JhcGhFdmVudD4+IHtcbiAgbG9nZ2VyLmRlYnVnKFxuICAgIGBbTVNUZWFtc1NlcnZpY2VdIGdldE1pY3Jvc29mdFRlYW1zTWVldGluZ0RldGFpbHMgY2FsbGVkIGZvciBBdG9tIHVzZXI6ICR7YXRvbVVzZXJJZH0sIGV2ZW50SWQ6ICR7ZXZlbnRJZH1gXG4gICk7XG5cbiAgY29uc3QgdG9rZW5SZXNwb25zZSA9IGF3YWl0IGdldERlbGVnYXRlZE1TR3JhcGhUb2tlbkZvclVzZXIoYXRvbVVzZXJJZCk7XG4gIGlmICghdG9rZW5SZXNwb25zZS5vayB8fCAhdG9rZW5SZXNwb25zZS5kYXRhKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB0b2tlblJlc3BvbnNlLmVycm9yIHx8IHtcbiAgICAgICAgY29kZTogJ01TR1JBUEhfQVVUSF9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdGYWlsZWQgdG8gb2J0YWluIE1TIEdyYXBoIGFjY2VzcyB0b2tlbiBmb3IgbWVldGluZyBkZXRhaWxzLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgY29uc3QgdG9rZW4gPSB0b2tlblJlc3BvbnNlLmRhdGE7XG5cbiAgY29uc3Qgc2VsZWN0UGFyYW1zID1cbiAgICAnaWQsc3ViamVjdCxzdGFydCxlbmQsaXNPbmxpbmVNZWV0aW5nLG9ubGluZU1lZXRpbmcsd2ViTGluayxib2R5UHJldmlldyxib2R5LGF0dGVuZGVlcyxsb2NhdGlvbixsb2NhdGlvbnMsb3JnYW5pemVyJztcbiAgLy8gVXNlICcvbWUvZXZlbnRzL3tpZH0nIGZvciBkZWxlZ2F0ZWQgcGVybWlzc2lvbnMgdG8gZ2V0IGEgc3BlY2lmaWMgZXZlbnQgZnJvbSB0aGUgc2lnbmVkLWluIHVzZXIncyBkZWZhdWx0IGNhbGVuZGFyXG4gIGNvbnN0IHJlcXVlc3RVcmwgPSBgJHtNU0dSQVBIX0FQSV9CQVNFX1VSTH0vbWUvZXZlbnRzLyR7ZXZlbnRJZH0/JHNlbGVjdD0ke3NlbGVjdFBhcmFtc31gO1xuXG4gIHRyeSB7XG4gICAgbG9nZ2VyLmRlYnVnKFxuICAgICAgYFtNU1RlYW1zU2VydmljZV0gUmVxdWVzdGluZyBtZWV0aW5nIGRldGFpbHMgZnJvbSBNUyBHcmFwaDogJHtyZXF1ZXN0VXJsfWBcbiAgICApO1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MuZ2V0PE1TR3JhcGhFdmVudD4ocmVxdWVzdFVybCwge1xuICAgICAgaGVhZGVyczogeyBBdXRob3JpemF0aW9uOiBgQmVhcmVyICR7dG9rZW59YCB9LFxuICAgIH0pO1xuICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiByZXNwb25zZS5kYXRhIH07XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBjb25zdCBheGlvc0Vycm9yID0gZXJyb3IgYXMgQXhpb3NFcnJvcjtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICBgW01TVGVhbXNTZXJ2aWNlXSBFcnJvciBnZXR0aW5nIE1TIFRlYW1zIG1lZXRpbmcgZGV0YWlscyBmb3IgZXZlbnQgJHtldmVudElkfSwgQXRvbSB1c2VyICR7YXRvbVVzZXJJZH06YCxcbiAgICAgIGF4aW9zRXJyb3IubWVzc2FnZSxcbiAgICAgIGF4aW9zRXJyb3IucmVzcG9uc2U/LmRhdGFcbiAgICApO1xuICAgIGNvbnN0IGVycm9yRGF0YSA9IGF4aW9zRXJyb3IucmVzcG9uc2U/LmRhdGEgYXMgYW55O1xuICAgIGlmIChheGlvc0Vycm9yLnJlc3BvbnNlPy5zdGF0dXMgPT09IDQwNCkge1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICBlcnJvcjoge1xuICAgICAgICAgIGNvZGU6ICdFVkVOVF9OT1RfRk9VTkQnLFxuICAgICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgICBgTWVldGluZyBldmVudCBub3QgZm91bmQgKElEOiAke2V2ZW50SWR9KS4gRGV0YWlsczogJHtlcnJvckRhdGE/LmVycm9yPy5tZXNzYWdlIHx8ICcnfWAudHJpbSgpLFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICB9XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6IGVycm9yRGF0YT8uZXJyb3I/LmNvZGUgfHwgJ01TR1JBUEhfQVBJX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTpcbiAgICAgICAgICBlcnJvckRhdGE/LmVycm9yPy5tZXNzYWdlIHx8XG4gICAgICAgICAgYXhpb3NFcnJvci5tZXNzYWdlIHx8XG4gICAgICAgICAgJ0ZhaWxlZCB0byBnZXQgTVMgVGVhbXMgbWVldGluZyBkZXRhaWxzJyxcbiAgICAgICAgZGV0YWlsczogZXJyb3JEYXRhPy5lcnJvciB8fCBlcnJvckRhdGEsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn1cblxuLy8gUGxhY2Vob2xkZXIgZm9yIG1zYWxDbGllbnRBcHAsIHRoaXMgd2FzIHRoZSBvbGQgb25lIGZvciBjbGllbnQgY3JlZGVudGlhbHMsIGNhbiBiZSByZW1vdmVkLlxuLy8gbGV0IG1zYWxDbGllbnRBcHA6IENvbmZpZGVudGlhbENsaWVudEFwcGxpY2F0aW9uIHwgbnVsbCA9IG51bGw7XG5cbi8vIC0tLSBOZXcgZnVuY3Rpb25zIGZvciBjaGF0IG1lc3NhZ2UgaW50ZXJhY3Rpb25zIC0tLVxuXG4vKipcbiAqIERlZmluZXMgdGhlIHN0cnVjdHVyZSBmb3IgYSBUZWFtcyBtZXNzYWdlIG9iamVjdCB3aXRoaW4gdGhlIGFnZW50LlxuICogVGhpcyBzaG91bGQgYWxpZ24gd2l0aCB3aGF0IHRoZSBhZ2VudCBuZWVkcyBhbmQgd2hhdCBHcmFwaCBBUEkgcHJvdmlkZXMuXG4gKi9cbmV4cG9ydCBpbnRlcmZhY2UgQWdlbnRNU1RlYW1zTWVzc2FnZSB7XG4gIGlkOiBzdHJpbmc7XG4gIGNoYXRJZD86IHN0cmluZzsgLy8gRm9yIDE6MSBvciBncm91cCBjaGF0c1xuICBjaGFubmVsSWQ/OiBzdHJpbmc7IC8vIEZvciBjaGFubmVsIG1lc3NhZ2VzICh3aXRoaW4gYSB0ZWFtKVxuICB0ZWFtSWQ/OiBzdHJpbmc7IC8vIEZvciBjaGFubmVsIG1lc3NhZ2VzXG4gIHJlcGx5VG9JZD86IHN0cmluZzsgLy8gSUQgb2YgdGhlIG1lc3NhZ2UgdGhpcyBvbmUgaXMgYSByZXBseSB0b1xuICB1c2VySWQ/OiBzdHJpbmc7IC8vIFNlbmRlcidzIEFBRCBVc2VyIElEXG4gIHVzZXJOYW1lPzogc3RyaW5nOyAvLyBTZW5kZXIncyBkaXNwbGF5IG5hbWVcbiAgY29udGVudDogc3RyaW5nOyAvLyBIVE1MIGNvbnRlbnQgb2YgdGhlIG1lc3NhZ2VcbiAgY29udGVudFR5cGU6ICdodG1sJyB8ICd0ZXh0JztcbiAgY3JlYXRlZERhdGVUaW1lOiBzdHJpbmc7IC8vIElTTyA4NjAxXG4gIGxhc3RNb2RpZmllZERhdGVUaW1lPzogc3RyaW5nOyAvLyBJU08gODYwMVxuICB3ZWJVcmw/OiBzdHJpbmc7IC8vIFBlcm1hbGlua1xuICBhdHRhY2htZW50cz86IHtcbiAgICBpZDogc3RyaW5nO1xuICAgIG5hbWU/OiBzdHJpbmc7XG4gICAgY29udGVudFR5cGU/OiBzdHJpbmc7XG4gICAgY29udGVudFVybD86IHN0cmluZztcbiAgICBzaXplPzogbnVtYmVyO1xuICB9W107XG4gIG1lbnRpb25zPzoge1xuICAgIGlkOiBudW1iZXI7XG4gICAgbWVudGlvblRleHQ/OiBzdHJpbmc7XG4gICAgbWVudGlvbmVkPzoge1xuICAgICAgdXNlcj86IHsgaWQ6IHN0cmluZzsgZGlzcGxheU5hbWU/OiBzdHJpbmc7IHVzZXJJZGVudGl0eVR5cGU/OiBzdHJpbmcgfTtcbiAgICB9O1xuICB9W107XG4gIHJhdz86IGFueTsgLy8gU3RvcmUgdGhlIHJhdyBHcmFwaCBBUEkgbWVzc2FnZSBvYmplY3Rcbn1cblxuLyoqXG4gKiBTZWFyY2hlcyBNaWNyb3NvZnQgVGVhbXMgbWVzc2FnZXMgdXNpbmcgdGhlIEdyYXBoIFNlYXJjaCBBUEkuXG4gKiBAcGFyYW0gYXRvbVVzZXJJZCBBdG9tJ3MgaW50ZXJuYWwgdXNlciBJRC5cbiAqIEBwYXJhbSBzZWFyY2hRdWVyeSBLUUwgcXVlcnkgc3RyaW5nLlxuICogQHBhcmFtIG1heFJlc3VsdHMgTWF4aW11bSBudW1iZXIgb2YgbWVzc2FnZXMgdG8gcmV0dXJuLlxuICogQHJldHVybnMgQSBwcm9taXNlIHJlc29sdmluZyB0byBhbiBhcnJheSBvZiBBZ2VudE1TVGVhbXNNZXNzYWdlIG9iamVjdHMuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBzZWFyY2hUZWFtc01lc3NhZ2VzKFxuICBhdG9tVXNlcklkOiBzdHJpbmcsXG4gIHNlYXJjaFF1ZXJ5OiBzdHJpbmcsIC8vIFRoaXMgd2lsbCBiZSB0aGUgS1FMIHF1ZXJ5IHN0cmluZ1xuICBtYXhSZXN1bHRzOiBudW1iZXIgPSAyMCxcbiAgdXNlckFhZE9iamVjdElkPzogc3RyaW5nIC8vIE9wdGlvbmFsOiBBQUQgT2JqZWN0IElEIG9mIHRoZSB1c2VyIGZvciBtb3JlIHNwZWNpZmljIHF1ZXJpZXNcbik6IFByb21pc2U8R3JhcGhTa2lsbFJlc3BvbnNlPEFnZW50TVNUZWFtc01lc3NhZ2VbXT4+IHtcbiAgbG9nZ2VyLmRlYnVnKFxuICAgIGBbTVNUZWFtc1NlcnZpY2VdIHNlYXJjaFRlYW1zTWVzc2FnZXMgY2FsbGVkIGZvciBBdG9tIHVzZXIgJHthdG9tVXNlcklkfSwgcXVlcnk6IFwiJHtzZWFyY2hRdWVyeX1cIiwgbWF4UmVzdWx0czogJHttYXhSZXN1bHRzfSwgdXNlckFhZE9iamVjdElkOiAke3VzZXJBYWRPYmplY3RJZH1gXG4gICk7XG5cbiAgY29uc3QgdG9rZW5SZXNwb25zZSA9IGF3YWl0IGdldERlbGVnYXRlZE1TR3JhcGhUb2tlbkZvclVzZXIoYXRvbVVzZXJJZCk7XG4gIGlmICghdG9rZW5SZXNwb25zZS5vayB8fCAhdG9rZW5SZXNwb25zZS5kYXRhKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB0b2tlblJlc3BvbnNlLmVycm9yIHx8IHtcbiAgICAgICAgY29kZTogJ01TR1JBUEhfQVVUSF9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdGYWlsZWQgdG8gb2J0YWluIE1TIEdyYXBoIHRva2VuIGZvciBzZWFyY2hpbmcgbWVzc2FnZXMuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBjb25zdCB0b2tlbiA9IHRva2VuUmVzcG9uc2UuZGF0YTtcblxuICAvLyBLUUwgcXVlcnkgY29uc3RydWN0aW9uIHdpbGwgbm93IGhhcHBlbiBpbiB0aGUgY2FsbGluZyBsYXllciAoZS5nLiwgSGFzdXJhIGFjdGlvbiwgb3IgbXNUZWFtc1NraWxscy50cylcbiAgLy8gaWYgdXNlckFhZE9iamVjdElkIGlzIHRvIGJlIGR5bmFtaWNhbGx5IGluc2VydGVkLlxuICAvLyBGb3IgdGhpcyBmdW5jdGlvbiwgc2VhcmNoUXVlcnkgaXMgYXNzdW1lZCB0byBiZSB0aGUgZmluYWwgS1FMLlxuICAvLyBJZiB1c2VyQWFkT2JqZWN0SWQgaXMgcHJvdmlkZWQsIHRoZSBjYWxsZXIgc2hvdWxkIGhhdmUgYWxyZWFkeSBpbmNvcnBvcmF0ZWQgaXQgaW50byBzZWFyY2hRdWVyeS5cbiAgLy8gVGhpcyBmdW5jdGlvbidzIHJlc3BvbnNpYmlsaXR5IGlzIHRvIGV4ZWN1dGUgdGhlIHByb3ZpZGVkIEtRTC5cblxuICAvLyBFeGFtcGxlIG9mIGhvdyBhIGNhbGxlciBtaWdodCBjb25zdHJ1Y3QgS1FMIGlmIGl0IGhhZCB1c2VyQWFkT2JqZWN0SWQ6XG4gIC8vIGxldCBmaW5hbEtxbCA9IHNlYXJjaFF1ZXJ5OyAvLyBzZWFyY2hRdWVyeSB3b3VsZCBiZSBqdXN0IGRhdGUgcmFuZ2UgcGFydHNcbiAgLy8gaWYgKHVzZXJBYWRPYmplY3RJZCkge1xuICAvLyAgIGZpbmFsS3FsID0gYChmcm9tOlwiJHt1c2VyQWFkT2JqZWN0SWR9XCIgT1IgbWVudGlvbnM6XCIke3VzZXJBYWRPYmplY3RJZH1cIikgQU5EICR7c2VhcmNoUXVlcnl9YDtcbiAgLy8gfVxuICAvLyBsb2dnZXIuaW5mbyhgW01TVGVhbXNTZXJ2aWNlXSBFZmZlY3RpdmUgS1FMIGZvciBzZWFyY2g6ICR7ZmluYWxLcWx9YCk7XG5cbiAgY29uc3Qgc2VhcmNoUmVxdWVzdCA9IHtcbiAgICByZXF1ZXN0czogW1xuICAgICAge1xuICAgICAgICBlbnRpdHlUeXBlczogWydjaGF0TWVzc2FnZSddLFxuICAgICAgICBxdWVyeToge1xuICAgICAgICAgIHF1ZXJ5U3RyaW5nOiBzZWFyY2hRdWVyeSwgLy8gVXNlIHRoZSBwYXNzZWQgc2VhcmNoUXVlcnkgZGlyZWN0bHlcbiAgICAgICAgfSxcbiAgICAgICAgZnJvbTogMCxcbiAgICAgICAgc2l6ZTogbWF4UmVzdWx0cyxcbiAgICAgICAgc29ydFByb3BlcnRpZXM6IFt7IG5hbWU6ICdjcmVhdGVkRGF0ZVRpbWUnLCBpc0Rlc2NlbmRpbmc6IHRydWUgfV0sXG4gICAgICB9LFxuICAgIF0sXG4gIH07XG5cbiAgY29uc3QgcmVxdWVzdFVybCA9IGAke01TR1JBUEhfQVBJX0JBU0VfVVJMfS9zZWFyY2gvcXVlcnlgO1xuXG4gIHRyeSB7XG4gICAgLy8gTG9nIHRoZSBhY3R1YWwgS1FMIHF1ZXJ5IGJlaW5nIHNlbnQgdG8gR3JhcGggQVBJXG4gICAgbG9nZ2VyLmluZm8oXG4gICAgICBgW01TVGVhbXNTZXJ2aWNlXSBFeGVjdXRpbmcgR3JhcGggU2VhcmNoIEFQSSB3aXRoIEtRTDogXCIke3NlYXJjaFF1ZXJ5fVwiIGZvciB1c2VyICR7YXRvbVVzZXJJZH1gXG4gICAgKTtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGF4aW9zLnBvc3QocmVxdWVzdFVybCwgc2VhcmNoUmVxdWVzdCwge1xuICAgICAgaGVhZGVyczoge1xuICAgICAgICBBdXRob3JpemF0aW9uOiBgQmVhcmVyICR7dG9rZW59YCxcbiAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgIH0sXG4gICAgfSk7XG5cbiAgICBjb25zdCBtZXNzYWdlczogQWdlbnRNU1RlYW1zTWVzc2FnZVtdID0gW107XG4gICAgaWYgKFxuICAgICAgcmVzcG9uc2UuZGF0YSAmJlxuICAgICAgcmVzcG9uc2UuZGF0YS52YWx1ZSAmJlxuICAgICAgcmVzcG9uc2UuZGF0YS52YWx1ZS5sZW5ndGggPiAwXG4gICAgKSB7XG4gICAgICBjb25zdCBzZWFyY2hIaXRzQ29udGFpbmVycyA9IHJlc3BvbnNlLmRhdGEudmFsdWVbMF0/LmhpdHNDb250YWluZXJzO1xuICAgICAgaWYgKHNlYXJjaEhpdHNDb250YWluZXJzICYmIHNlYXJjaEhpdHNDb250YWluZXJzLmxlbmd0aCA+IDApIHtcbiAgICAgICAgc2VhcmNoSGl0c0NvbnRhaW5lcnMuZm9yRWFjaCgoY29udGFpbmVyOiBhbnkpID0+IHtcbiAgICAgICAgICBpZiAoY29udGFpbmVyLmhpdHMpIHtcbiAgICAgICAgICAgIGNvbnRhaW5lci5oaXRzLmZvckVhY2goKGhpdDogYW55KSA9PiB7XG4gICAgICAgICAgICAgIGNvbnN0IHJlc291cmNlID0gaGl0LnJlc291cmNlO1xuICAgICAgICAgICAgICBpZiAocmVzb3VyY2UpIHtcbiAgICAgICAgICAgICAgICBtZXNzYWdlcy5wdXNoKHtcbiAgICAgICAgICAgICAgICAgIGlkOiByZXNvdXJjZS5pZCxcbiAgICAgICAgICAgICAgICAgIGNoYXRJZDogcmVzb3VyY2UuY2hhdElkLFxuICAgICAgICAgICAgICAgICAgY2hhbm5lbElkOiByZXNvdXJjZS5jaGFubmVsSWRlbnRpdHk/LmNoYW5uZWxJZCxcbiAgICAgICAgICAgICAgICAgIHRlYW1JZDogcmVzb3VyY2UuY2hhbm5lbElkZW50aXR5Py50ZWFtSWQsXG4gICAgICAgICAgICAgICAgICByZXBseVRvSWQ6IHJlc291cmNlLnJlcGx5VG9JZCxcbiAgICAgICAgICAgICAgICAgIHVzZXJJZDogcmVzb3VyY2UuZnJvbT8udXNlcj8uaWQsXG4gICAgICAgICAgICAgICAgICB1c2VyTmFtZTogcmVzb3VyY2UuZnJvbT8udXNlcj8uZGlzcGxheU5hbWUsXG4gICAgICAgICAgICAgICAgICBjb250ZW50OiByZXNvdXJjZS5ib2R5Py5jb250ZW50LFxuICAgICAgICAgICAgICAgICAgY29udGVudFR5cGU6IHJlc291cmNlLmJvZHk/LmNvbnRlbnRUeXBlLFxuICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVUaW1lOiByZXNvdXJjZS5jcmVhdGVkRGF0ZVRpbWUsXG4gICAgICAgICAgICAgICAgICBsYXN0TW9kaWZpZWREYXRlVGltZTogcmVzb3VyY2UubGFzdE1vZGlmaWVkRGF0ZVRpbWUsXG4gICAgICAgICAgICAgICAgICB3ZWJVcmw6IHJlc291cmNlLndlYlVybCxcbiAgICAgICAgICAgICAgICAgIC8vIGF0dGFjaG1lbnRzOiByZXNvdXJjZS5hdHRhY2htZW50cywgLy8gR3JhcGggc2VhcmNoIG1pZ2h0IG5vdCByZXR1cm4gZnVsbCBhdHRhY2htZW50cyBoZXJlXG4gICAgICAgICAgICAgICAgICAvLyBtZW50aW9uczogcmVzb3VyY2UubWVudGlvbnMsXG4gICAgICAgICAgICAgICAgICByYXc6IHJlc291cmNlLFxuICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9KTtcbiAgICAgICAgICB9XG4gICAgICAgIH0pO1xuICAgICAgfVxuICAgIH1cbiAgICBsb2dnZXIuaW5mbyhcbiAgICAgIGBbTVNUZWFtc1NlcnZpY2VdIEZvdW5kICR7bWVzc2FnZXMubGVuZ3RofSBUZWFtcyBtZXNzYWdlcyBmb3IgcXVlcnkgXCIke3NlYXJjaFF1ZXJ5fVwiIGZvciBBdG9tIHVzZXIgJHthdG9tVXNlcklkfS5gXG4gICAgKTtcbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogbWVzc2FnZXMgfTtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGNvbnN0IGF4aW9zRXJyb3IgPSBlcnJvciBhcyBBeGlvc0Vycm9yO1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbTVNUZWFtc1NlcnZpY2VdIEVycm9yIHNlYXJjaGluZyBUZWFtcyBtZXNzYWdlcyBmb3IgQXRvbSB1c2VyICR7YXRvbVVzZXJJZH06YCxcbiAgICAgIGF4aW9zRXJyb3IubWVzc2FnZSxcbiAgICAgIGF4aW9zRXJyb3IucmVzcG9uc2U/LmRhdGFcbiAgICApO1xuICAgIGNvbnN0IGVycm9yRGF0YSA9IGF4aW9zRXJyb3IucmVzcG9uc2U/LmRhdGEgYXMgYW55O1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiBlcnJvckRhdGE/LmVycm9yPy5jb2RlIHx8ICdNU0dSQVBIX1NFQVJDSF9BUElfRVJST1InLFxuICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgIGVycm9yRGF0YT8uZXJyb3I/Lm1lc3NhZ2UgfHxcbiAgICAgICAgICBheGlvc0Vycm9yLm1lc3NhZ2UgfHxcbiAgICAgICAgICAnRmFpbGVkIHRvIHNlYXJjaCBUZWFtcyBtZXNzYWdlcycsXG4gICAgICAgIGRldGFpbHM6IGVycm9yRGF0YT8uZXJyb3IgfHwgZXJyb3JEYXRhLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59XG5cbi8qKlxuICogR2V0cyB0aGUgY29udGVudCBvZiBhIHNwZWNpZmljIGNoYXQgbWVzc2FnZSAoMToxIG9yIGdyb3VwIGNoYXQpLlxuICogQHBhcmFtIGF0b21Vc2VySWQgQXRvbSdzIGludGVybmFsIHVzZXIgSUQuXG4gKiBAcGFyYW0gY2hhdElkIFRoZSBJRCBvZiB0aGUgY2hhdC5cbiAqIEBwYXJhbSBtZXNzYWdlSWQgVGhlIElEIG9mIHRoZSBtZXNzYWdlLlxuICogQHJldHVybnMgQSBwcm9taXNlIHJlc29sdmluZyB0byBhbiBBZ2VudE1TVGVhbXNNZXNzYWdlIG9iamVjdCBvciBudWxsLlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0VGVhbXNDaGF0TWVzc2FnZUNvbnRlbnQoXG4gIGF0b21Vc2VySWQ6IHN0cmluZyxcbiAgY2hhdElkOiBzdHJpbmcsXG4gIG1lc3NhZ2VJZDogc3RyaW5nXG4pOiBQcm9taXNlPEdyYXBoU2tpbGxSZXNwb25zZTxBZ2VudE1TVGVhbXNNZXNzYWdlIHwgbnVsbD4+IHtcbiAgbG9nZ2VyLmRlYnVnKFxuICAgIGBbTVNUZWFtc1NlcnZpY2VdIGdldFRlYW1zQ2hhdE1lc3NhZ2VDb250ZW50IGZvciB1c2VyICR7YXRvbVVzZXJJZH0sIGNoYXRJZDogJHtjaGF0SWR9LCBtZXNzYWdlSWQ6ICR7bWVzc2FnZUlkfWBcbiAgKTtcbiAgY29uc3QgdG9rZW5SZXNwb25zZSA9IGF3YWl0IGdldERlbGVnYXRlZE1TR3JhcGhUb2tlbkZvclVzZXIoYXRvbVVzZXJJZCk7XG4gIGlmICghdG9rZW5SZXNwb25zZS5vayB8fCAhdG9rZW5SZXNwb25zZS5kYXRhKVxuICAgIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHRva2VuUmVzcG9uc2UuZXJyb3IgfTtcbiAgY29uc3QgdG9rZW4gPSB0b2tlblJlc3BvbnNlLmRhdGE7XG5cbiAgLy8gVGhlIGZpZWxkcyBzZWxlY3RlZCBoZXJlIHNob3VsZCBtYXRjaCB0aGUgQWdlbnRNU1RlYW1zTWVzc2FnZSBpbnRlcmZhY2VcbiAgY29uc3Qgc2VsZWN0RmllbGRzID1cbiAgICAnaWQscmVwbHlUb0lkLGZyb20sYm9keSxjcmVhdGVkRGF0ZVRpbWUsbGFzdE1vZGlmaWVkRGF0ZVRpbWUsd2ViVXJsLGF0dGFjaG1lbnRzLG1lbnRpb25zLGNoYXRJZCc7XG4gIGNvbnN0IHJlcXVlc3RVcmwgPSBgJHtNU0dSQVBIX0FQSV9CQVNFX1VSTH0vbWUvY2hhdHMvJHtjaGF0SWR9L21lc3NhZ2VzLyR7bWVzc2FnZUlkfT8kc2VsZWN0PSR7c2VsZWN0RmllbGRzfWA7XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGF4aW9zLmdldChyZXF1ZXN0VXJsLCB7XG4gICAgICBoZWFkZXJzOiB7IEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt0b2tlbn1gIH0sXG4gICAgfSk7XG4gICAgY29uc3QgcmF3TXNnID0gcmVzcG9uc2UuZGF0YTtcbiAgICBjb25zdCBtZXNzYWdlOiBBZ2VudE1TVGVhbXNNZXNzYWdlID0ge1xuICAgICAgaWQ6IHJhd01zZy5pZCxcbiAgICAgIGNoYXRJZDogcmF3TXNnLmNoYXRJZCwgLy8gV2lsbCBiZSBwb3B1bGF0ZWQgYnkgdGhpcyBlbmRwb2ludFxuICAgICAgcmVwbHlUb0lkOiByYXdNc2cucmVwbHlUb0lkLFxuICAgICAgdXNlcklkOiByYXdNc2cuZnJvbT8udXNlcj8uaWQsXG4gICAgICB1c2VyTmFtZTogcmF3TXNnLmZyb20/LnVzZXI/LmRpc3BsYXlOYW1lLFxuICAgICAgY29udGVudDogcmF3TXNnLmJvZHk/LmNvbnRlbnQsXG4gICAgICBjb250ZW50VHlwZTogcmF3TXNnLmJvZHk/LmNvbnRlbnRUeXBlLFxuICAgICAgY3JlYXRlZERhdGVUaW1lOiByYXdNc2cuY3JlYXRlZERhdGVUaW1lLFxuICAgICAgbGFzdE1vZGlmaWVkRGF0ZVRpbWU6IHJhd01zZy5sYXN0TW9kaWZpZWREYXRlVGltZSxcbiAgICAgIHdlYlVybDogcmF3TXNnLndlYlVybCxcbiAgICAgIGF0dGFjaG1lbnRzOiByYXdNc2cuYXR0YWNobWVudHM/Lm1hcCgoYXR0OiBhbnkpID0+ICh7XG4gICAgICAgIGlkOiBhdHQuaWQsXG4gICAgICAgIG5hbWU6IGF0dC5uYW1lLFxuICAgICAgICBjb250ZW50VHlwZTogYXR0LmNvbnRlbnRUeXBlLFxuICAgICAgICBjb250ZW50VXJsOiBhdHQuY29udGVudFVybCxcbiAgICAgICAgc2l6ZTogYXR0LnNpemUsXG4gICAgICB9KSksXG4gICAgICBtZW50aW9uczogcmF3TXNnLm1lbnRpb25zPy5tYXAoKG1lbjogYW55KSA9PiAoe1xuICAgICAgICBpZDogbWVuLmlkLFxuICAgICAgICBtZW50aW9uVGV4dDogbWVuLm1lbnRpb25UZXh0LFxuICAgICAgICBtZW50aW9uZWQ6IG1lbi5tZW50aW9uZWQsXG4gICAgICB9KSksXG4gICAgICByYXc6IHJhd01zZyxcbiAgICB9O1xuICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiBtZXNzYWdlIH07XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBjb25zdCBheGlvc0Vycm9yID0gZXJyb3IgYXMgQXhpb3NFcnJvcjtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICBgW01TVGVhbXNTZXJ2aWNlXSBFcnJvciBnZXR0aW5nIGNoYXQgbWVzc2FnZSBjb250ZW50IChjaGF0ICR7Y2hhdElkfSwgbXNnICR7bWVzc2FnZUlkfSk6YCxcbiAgICAgIGF4aW9zRXJyb3IubWVzc2FnZSxcbiAgICAgIGF4aW9zRXJyb3IucmVzcG9uc2U/LmRhdGFcbiAgICApO1xuICAgIGNvbnN0IGVycm9yRGF0YSA9IGF4aW9zRXJyb3IucmVzcG9uc2U/LmRhdGEgYXMgYW55O1xuICAgIGlmIChheGlvc0Vycm9yLnJlc3BvbnNlPy5zdGF0dXMgPT09IDQwNClcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICBjb2RlOiAnTVNHUkFQSF9NRVNTQUdFX05PVF9GT1VORCcsXG4gICAgICAgICAgbWVzc2FnZTogJ0NoYXQgbWVzc2FnZSBub3QgZm91bmQuJyxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6IGVycm9yRGF0YT8uZXJyb3I/LmNvZGUgfHwgJ01TR1JBUEhfQVBJX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTpcbiAgICAgICAgICBlcnJvckRhdGE/LmVycm9yPy5tZXNzYWdlIHx8ICdGYWlsZWQgdG8gZ2V0IGNoYXQgbWVzc2FnZSBjb250ZW50JyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufVxuXG4vKipcbiAqIEdldHMgdGhlIGNvbnRlbnQgb2YgYSBzcGVjaWZpYyBjaGFubmVsIG1lc3NhZ2UuXG4gKiBAcGFyYW0gYXRvbVVzZXJJZCBBdG9tJ3MgaW50ZXJuYWwgdXNlciBJRC5cbiAqIEBwYXJhbSB0ZWFtSWQgVGhlIElEIG9mIHRoZSB0ZWFtLlxuICogQHBhcmFtIGNoYW5uZWxJZCBUaGUgSUQgb2YgdGhlIGNoYW5uZWwuXG4gKiBAcGFyYW0gbWVzc2FnZUlkIFRoZSBJRCBvZiB0aGUgbWVzc2FnZS5cbiAqIEByZXR1cm5zIEEgcHJvbWlzZSByZXNvbHZpbmcgdG8gYW4gQWdlbnRNU1RlYW1zTWVzc2FnZSBvYmplY3Qgb3IgbnVsbC5cbiAqL1xuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldFRlYW1zQ2hhbm5lbE1lc3NhZ2VDb250ZW50KFxuICBhdG9tVXNlcklkOiBzdHJpbmcsXG4gIHRlYW1JZDogc3RyaW5nLFxuICBjaGFubmVsSWQ6IHN0cmluZyxcbiAgbWVzc2FnZUlkOiBzdHJpbmdcbik6IFByb21pc2U8R3JhcGhTa2lsbFJlc3BvbnNlPEFnZW50TVNUZWFtc01lc3NhZ2UgfCBudWxsPj4ge1xuICBsb2dnZXIuZGVidWcoXG4gICAgYFtNU1RlYW1zU2VydmljZV0gZ2V0VGVhbXNDaGFubmVsTWVzc2FnZUNvbnRlbnQgZm9yIHVzZXIgJHthdG9tVXNlcklkfSwgdGVhbSAke3RlYW1JZH0sIGNoYW5uZWwgJHtjaGFubmVsSWR9LCBtc2cgJHttZXNzYWdlSWR9YFxuICApO1xuICBjb25zdCB0b2tlblJlc3BvbnNlID0gYXdhaXQgZ2V0RGVsZWdhdGVkTVNHcmFwaFRva2VuRm9yVXNlcihhdG9tVXNlcklkKTtcbiAgaWYgKCF0b2tlblJlc3BvbnNlLm9rIHx8ICF0b2tlblJlc3BvbnNlLmRhdGEpXG4gICAgcmV0dXJuIHsgb2s6IGZhbHNlLCBlcnJvcjogdG9rZW5SZXNwb25zZS5lcnJvciB9O1xuICBjb25zdCB0b2tlbiA9IHRva2VuUmVzcG9uc2UuZGF0YTtcblxuICBjb25zdCBzZWxlY3RGaWVsZHMgPVxuICAgICdpZCxyZXBseVRvSWQsZnJvbSxib2R5LGNyZWF0ZWREYXRlVGltZSxsYXN0TW9kaWZpZWREYXRlVGltZSx3ZWJVcmwsYXR0YWNobWVudHMsbWVudGlvbnMsY2hhbm5lbElkZW50aXR5JztcbiAgY29uc3QgcmVxdWVzdFVybCA9IGAke01TR1JBUEhfQVBJX0JBU0VfVVJMfS90ZWFtcy8ke3RlYW1JZH0vY2hhbm5lbHMvJHtjaGFubmVsSWR9L21lc3NhZ2VzLyR7bWVzc2FnZUlkfT8kc2VsZWN0PSR7c2VsZWN0RmllbGRzfWA7XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGF4aW9zLmdldChyZXF1ZXN0VXJsLCB7XG4gICAgICBoZWFkZXJzOiB7IEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt0b2tlbn1gIH0sXG4gICAgfSk7XG4gICAgY29uc3QgcmF3TXNnID0gcmVzcG9uc2UuZGF0YTtcbiAgICBjb25zdCBtZXNzYWdlOiBBZ2VudE1TVGVhbXNNZXNzYWdlID0ge1xuICAgICAgaWQ6IHJhd01zZy5pZCxcbiAgICAgIHRlYW1JZDogcmF3TXNnLmNoYW5uZWxJZGVudGl0eT8udGVhbUlkLFxuICAgICAgY2hhbm5lbElkOiByYXdNc2cuY2hhbm5lbElkZW50aXR5Py5jaGFubmVsSWQsXG4gICAgICByZXBseVRvSWQ6IHJhd01zZy5yZXBseVRvSWQsXG4gICAgICB1c2VySWQ6IHJhd01zZy5mcm9tPy51c2VyPy5pZCxcbiAgICAgIHVzZXJOYW1lOiByYXdNc2cuZnJvbT8udXNlcj8uZGlzcGxheU5hbWUsXG4gICAgICBjb250ZW50OiByYXdNc2cuYm9keT8uY29udGVudCxcbiAgICAgIGNvbnRlbnRUeXBlOiByYXdNc2cuYm9keT8uY29udGVudFR5cGUsXG4gICAgICBjcmVhdGVkRGF0ZVRpbWU6IHJhd01zZy5jcmVhdGVkRGF0ZVRpbWUsXG4gICAgICBsYXN0TW9kaWZpZWREYXRlVGltZTogcmF3TXNnLmxhc3RNb2RpZmllZERhdGVUaW1lLFxuICAgICAgd2ViVXJsOiByYXdNc2cud2ViVXJsLFxuICAgICAgYXR0YWNobWVudHM6IHJhd01zZy5hdHRhY2htZW50cz8ubWFwKChhdHQ6IGFueSkgPT4gKHtcbiAgICAgICAgaWQ6IGF0dC5pZCxcbiAgICAgICAgbmFtZTogYXR0Lm5hbWUsXG4gICAgICAgIGNvbnRlbnRUeXBlOiBhdHQuY29udGVudFR5cGUsXG4gICAgICAgIGNvbnRlbnRVcmw6IGF0dC5jb250ZW50VXJsLFxuICAgICAgICBzaXplOiBhdHQuc2l6ZSxcbiAgICAgIH0pKSxcbiAgICAgIG1lbnRpb25zOiByYXdNc2cubWVudGlvbnM/Lm1hcCgobWVuOiBhbnkpID0+ICh7XG4gICAgICAgIGlkOiBtZW4uaWQsXG4gICAgICAgIG1lbnRpb25UZXh0OiBtZW4ubWVudGlvblRleHQsXG4gICAgICAgIG1lbnRpb25lZDogbWVuLm1lbnRpb25lZCxcbiAgICAgIH0pKSxcbiAgICAgIHJhdzogcmF3TXNnLFxuICAgIH07XG4gICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IG1lc3NhZ2UgfTtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGNvbnN0IGF4aW9zRXJyb3IgPSBlcnJvciBhcyBBeGlvc0Vycm9yO1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbTVNUZWFtc1NlcnZpY2VdIEVycm9yIGdldHRpbmcgY2hhbm5lbCBtZXNzYWdlIGNvbnRlbnQgKHRlYW0gJHt0ZWFtSWR9LCBjaGFubmVsICR7Y2hhbm5lbElkfSwgbXNnICR7bWVzc2FnZUlkfSk6YCxcbiAgICAgIGF4aW9zRXJyb3IubWVzc2FnZSxcbiAgICAgIGF4aW9zRXJyb3IucmVzcG9uc2U/LmRhdGFcbiAgICApO1xuICAgIGNvbnN0IGVycm9yRGF0YSA9IGF4aW9zRXJyb3IucmVzcG9uc2U/LmRhdGEgYXMgYW55O1xuICAgIGlmIChheGlvc0Vycm9yLnJlc3BvbnNlPy5zdGF0dXMgPT09IDQwNClcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICBjb2RlOiAnTVNHUkFQSF9NRVNTQUdFX05PVF9GT1VORCcsXG4gICAgICAgICAgbWVzc2FnZTogJ0NoYW5uZWwgbWVzc2FnZSBub3QgZm91bmQuJyxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6IGVycm9yRGF0YT8uZXJyb3I/LmNvZGUgfHwgJ01TR1JBUEhfQVBJX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTpcbiAgICAgICAgICBlcnJvckRhdGE/LmVycm9yPy5tZXNzYWdlIHx8ICdGYWlsZWQgdG8gZ2V0IGNoYW5uZWwgbWVzc2FnZSBjb250ZW50JyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufVxuXG4vLyBOb3RlOiBnZXRUZWFtc01lc3NhZ2VQZXJtYWxpbmsgaXMgaW1wbGljaXRseSBoYW5kbGVkIGJ5IHRoZSBgd2ViVXJsYCBwcm9wZXJ0eVxuLy8gaW4gdGhlIEFnZW50TVNUZWFtc01lc3NhZ2Ugd2hlbiBtZXNzYWdlcyBhcmUgZmV0Y2hlZC4gTm8gc2VwYXJhdGUgZnVuY3Rpb24gbmVlZGVkXG4vLyB1bmxlc3MgYSBzcGVjaWZpYyBBUEkgY2FsbCBmb3IgcGVybWFsaW5rIGdlbmVyYXRpb24gaXMgcHJlZmVycmVkIG9yIHJlcXVpcmVkIGZvciBzb21lIGVkZ2UgY2FzZXMuXG4iXX0=