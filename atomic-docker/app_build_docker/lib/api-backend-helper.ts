import got from "got"
import { dayjs } from '@lib/date-utils'
import _ from "lodash"
import { googleClientIdAtomicWeb, googleClientSecretAtomicWeb, googleOAuthAtomicWebRedirectUrl, googleTokenUrl, postgraphileAdminSecret, postgraphileGraphUrl, zoomIVForPass, zoomPassKey, zoomSaltForPass } from "@lib/constants"
import { ZoomWebhookRequestType, ZoomWebhookValidationRequestType } from "@lib/types"
import { google } from 'googleapis';
import type { NextApiRequest, NextApiResponse } from 'next';
import crypto, { BinaryLike } from 'crypto';
import { CalendarIntegrationType, colorType } from "./dataTypes/Calendar_IntegrationType";
import { googleColorUrl } from "./calendarLib/constants";
import appServiceLogger from './logger'; // Import the shared logger
import { colorResponseType } from "./calendarLib/types"
import { type Credentials } from 'google-auth-library/build/src/auth/credentials'
import { googlePeopleSyncUrl } from "./contactLib/constants"
import { ScheduleMeetingRequestType } from "./dataTypes/ScheduleMeetingRequestType"
import { SCHEDULER_API_URL } from "./constants"

// Generic resilient 'got' wrapper for app-service backend helpers
const resilientGot = async (
    method: 'get' | 'post' | 'patch' | 'put' | 'delete',
    url: string,
    options?: import('got').OptionsOfJSONResponseBody | import('got').OptionsOfTextResponseBody, // Adjust as needed for form/json etc.
    operationName: string = 'externalApiCall', // Default operation name for logging
) => {
    const MAX_RETRIES = 3;
    // Standardize timeout, e.g. 15s, can be overridden in options if needed by specific calls
    const DEFAULT_TIMEOUT_MS = options?.timeout?.request || 15000;
    let attempt = 0;
    let lastError: any = null;

    const gotOptions = {
        ...options,
        timeout: { request: DEFAULT_TIMEOUT_MS }, // Ensure timeout is set
        retry: { limit: 0 }, // Disable got's native retry, we're handling it manually
        throwHttpErrors: true, // Ensure got throws on HTTP errors > 399
        responseType: options?.responseType || 'json', // Default to JSON, can be overridden
    } as import('got').Options; // Cast to base Options for got call

    while (attempt < MAX_RETRIES) {
        try {
            appServiceLogger.info(`[${operationName}] Attempt ${attempt + 1}/${MAX_RETRIES} - ${method.toUpperCase()} ${url}`, { url, method, options: _.omit(gotOptions, ['headers.Authorization']) }); // Omit sensitive headers

            let response: import('got').GotResponse<any>;
            switch (method.toLowerCase()) {
                case 'get':
                    response = await got.get(url, gotOptions);
                    break;
                case 'post':
                    response = await got.post(url, gotOptions);
                    break;
                case 'patch':
                    response = await got.patch(url, gotOptions);
                    break;
                case 'put':
                    response = await got.put(url, gotOptions);
                    break;
                case 'delete':
                    response = await got.delete(url, gotOptions);
                    break;
                default:
                    throw new Error(`Unsupported HTTP method: ${method}`);
            }

            appServiceLogger.info(`[${operationName}] Attempt ${attempt + 1} successful.`, { url, method, statusCode: response.statusCode });
            return response.body; // got already parses if responseType is 'json'
        } catch (error: any) {
            lastError = error;
            const statusCode = error.response?.statusCode;
            const errorCode = error.code;

            appServiceLogger.warn(`[${operationName}] Attempt ${attempt + 1}/${MAX_RETRIES} failed.`, {
                url, method, attempt: attempt + 1,
                error: error.message,
                statusCode,
                errorCode,
                // responseBody: error.response?.body, // Be cautious logging full response bodies
            });

            // Decide if we should retry
            const isRetryableHttpError = statusCode && (statusCode >= 500 || statusCode === 408 || statusCode === 429);
            const isRetryableNetworkError = errorCode && ['ETIMEDOUT', 'ECONNRESET', 'EADDRINUSE', 'ECONNREFUSED', 'EPIPE', 'ENETUNREACH', 'EAI_AGAIN'].includes(errorCode);

            if (!isRetryableHttpError && !isRetryableNetworkError) {
                 appServiceLogger.error(`[${operationName}] Non-retryable error encountered. Aborting retries.`, { url, method, statusCode, errorCode });
                break; // Break for non-retryable errors
            }
        }
        attempt++;
        if (attempt < MAX_RETRIES) {
            const delay = Math.pow(2, attempt -1) * 1000; // e.g., 1s, 2s
            appServiceLogger.info(`[${operationName}] Waiting ${delay}ms before retry ${attempt + 1}/${MAX_RETRIES}.`, { url, method });
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }
    appServiceLogger.error(`[${operationName}] Failed after ${attempt} attempts.`, { url, method, lastError: lastError?.message, lastStatusCode: lastError?.response?.statusCode });
    throw lastError || new Error(`[${operationName}] Failed after all retries for ${method.toUpperCase()} ${url}.`);
};


const oauth2Client = new google.auth.OAuth2(
    googleClientIdAtomicWeb,
    googleClientSecretAtomicWeb,
    googleOAuthAtomicWebRedirectUrl,
)


export const exchangeCodeForTokens = async (code: string): Promise<Credentials> => {
    try {
        let { tokens } = await oauth2Client.getToken(code);
        oauth2Client.setCredentials(tokens)
        appServiceLogger.info('[exchangeCodeForTokens] Successfully exchanged code for tokens.', { codePrefix: code?.substring(0, 10), tokenExpiry: tokens.expiry_date });
        return tokens
    } catch (e: any) {
        appServiceLogger.error('[exchangeCodeForTokens] Unable to exchange code for tokens.', { codePrefix: code?.substring(0, 10), error: e.message, stack: e.stack, details: e });
        throw e; // Rethrow the error
    }
}

export const generateGoogleAuthUrl = (state?: string) => {


    // Access scopes
    const scopes = [
        'https://www.googleapis.com/auth/calendar.readonly',
        'https://www.googleapis.com/auth/calendar.events',
        'https://www.googleapis.com/auth/contacts.readonly',
        'https://www.googleapis.com/auth/gmail.readonly' // Added Gmail readonly scope
    ]

    const config: any = {
        // 'online' (default) or 'offline' (gets refresh_token)
        access_type: 'offline',
        /** Pass in the scopes array defined above.
          * Alternatively, if only one scope is needed, you can pass a scope URL as a string */
        scope: scopes,
        // Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes: true,
    }

    if (state) {
        config.state = state
    }
    // Generate a url that asks permissions for the Calendar activity scope
    const authorizationUrl = oauth2Client.generateAuthUrl(config)

    // console.log(authorizationUrl, ' authorizationUrl')

    return authorizationUrl
}

export const getMinimalCalendarIntegrationByResource = async (
    userId: string,
    resource: string,
) => {
    try {
        const operationName = 'getCalendarIntegration'
        const query = `
      query getCalendarIntegration($userId: uuid!, $resource: String!) {
        Calendar_Integration(where: {userId: {_eq: $userId}, resource: {_eq: $resource}}) {
            appAccountId
            appEmail
            appId
            clientType
            colors
            contactEmail
            contactFirstName
            contactLastName
            contactName
            createdDate
            deleted
            enabled
            expiresAt
            id
            name
            pageToken
            password
            phoneCountry
            phoneNumber
            refreshToken
            resource
            syncEnabled
            syncToken
            token
            updatedAt
            userId
            username
        }
      }
    `
        const variables = {
            userId,
            resource,
        }

        const options = {
            json: { operationName, query, variables },
            headers: {
                'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin' // Assuming admin role as per original direct call
            },
        };

        const responseData = await resilientGot('post', postgraphileGraphUrl, options, operationName) as { data?: { Calendar_Integration: CalendarIntegrationType[] } };

        if (responseData?.data?.Calendar_Integration?.length > 0) {
            appServiceLogger.debug(`[${operationName}] Found integration for userId: ${userId}, resource: ${resource}.`, { integrationId: responseData.data.Calendar_Integration[0].id });
            return responseData.data.Calendar_Integration[0];
        } else {
            appServiceLogger.info(`[${operationName}] No integration found for userId: ${userId}, resource: ${resource}.`);
            return undefined;
        }
    } catch (e: any) {
        appServiceLogger.error(`[${operationName}] Unable to get calendar integration.`, { userId, resource, error: e.message, stack: e.stack, details: e });
        // resilientGot will throw, this catch is for any additional handling or if it's not caught by resilientGot (unlikely for HTTP errors)
        throw e; // Rethrow to ensure failure is propagated if not already by resilientGot
    }
}

export const updateAccessTokenCalendarIntegration = async (
    id: string,
    token: string | null,
    expiresIn: number | null,
    enabled?: boolean,
    refreshToken?: string | null,
) => {
    const operationName = 'updateAccessTokenCalendarIntegration'; // Renamed from 'updateCalendarIntegration' for clarity
    try {
        // const operationName = 'updateCalendarIntegration' // Original name
        const query = `
      mutation updateAccessTokenCalendarIntegration($id: uuid!,${token !== undefined ? ' $token: String,' : ''}${refreshToken !== undefined ? ' $refreshToken: String,' : ''}${expiresIn !== undefined ? ' $expiresAt: timestamptz,' : ''}${enabled !== undefined ? ' $enabled: Boolean,' : ''}) {
        update_Calendar_Integration_by_pk(pk_columns: {id: $id}, _set: {${token !== undefined ? 'token: $token,' : ''}${refreshToken !== undefined ? ' refreshToken: $refreshToken,' : ''}${expiresIn !== undefined ? ' expiresAt: $expiresAt,' : ''}${enabled !== undefined ? ' enabled: $enabled,' : ''}}) {
          id
          name
          refreshToken
          token
          clientType
          userId
          updatedAt
        }
      }
    `
        let variables: any = {
            id,
            token,
            expiresAt: expiresIn ? dayjs().add(expiresIn, 'seconds').toISOString() : null,

        }

        if (enabled !== undefined) {
            variables.enabled = enabled
        }

        if (refreshToken !== undefined) {
            variables.refreshToken = refreshToken
        }

        const gotOptions = {
            json: { operationName, query, variables },
            headers: {
                'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin'
            },
        };

        // Using resilientGot now
        await resilientGot('post', postgraphileGraphUrl, gotOptions, operationName);

        appServiceLogger.info(`[${operationName}] Successfully updated calendar integration.`, { id, enabled, hasToken: !!token, hasRefreshToken: !!refreshToken });
        // Original function implicitly returns undefined, and resilientGot for POST might not return meaningful data unless specified.
    } catch (e: any) {
        appServiceLogger.error(`[${operationName}] Unable to update calendar integration.`, { id, error: e.message, stack: e.stack, details: e });
        // resilientGot will throw, this catch is for any additional handling
        throw e;
    }
}

export const refreshGoogleToken = async (
    refreshToken: string,
    clientType: 'ios' | 'android' | 'web' | 'atomic-web'
): Promise<{
    access_token: string,
    expires_in: number, // add seconds to now
    scope: string,
    token_type: string
} | undefined> => {
    const operationName = 'getMinimalCalendarIntegrationByName'; // Corrected operation name
    try {
        // const operationName = 'getCalendarIntegration' // Original name in this func
        const query = `
      query getMinimalCalendarIntegrationByName($userId: uuid!, $name: String!) {
        Calendar_Integration(where: {userId: {_eq: $userId}, name: {_eq: $name}}) {
            appAccountId
            appEmail
            appId
            clientType
            colors
            contactEmail
            contactFirstName
            contactLastName
            contactName
            createdDate
            deleted
            enabled
            expiresAt
            id
            name
            pageToken
            password
            phoneCountry
            phoneNumber
            refreshToken
            resource
            syncEnabled
            syncToken
            token
            updatedAt
            userId
            username
        }
      }
    `
        const variables = {
            userId,
            name,
        }

        const options = {
            json: { operationName, query, variables },
            headers: {
                'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin'
            },
        };

        const responseData = await resilientGot('post', postgraphileGraphUrl, options, operationName) as { data?: { Calendar_Integration: CalendarIntegrationType[] } };

        if (responseData?.data?.Calendar_Integration?.length > 0) {
            appServiceLogger.debug(`[${operationName}] Found integration for userId: ${userId}, name: ${name}.`, { integrationId: responseData.data.Calendar_Integration[0].id });
            return responseData.data.Calendar_Integration[0];
        } else {
            appServiceLogger.info(`[${operationName}] No integration found for userId: ${userId}, name: ${name}.`);
            return undefined;
        }
    } catch (e: any) {
        appServiceLogger.error(`[${operationName}] Unable to get calendar integration by name.`, { userId, name, error: e.message, stack: e.stack, details: e });
        throw e;
    }
}

/**
 * query getCalendarIntegration($userId: uuid!, $resource: String!, $clientType: String!) {
  Calendar_Integration(where: {userId: {_eq: $userId}, resource: {_eq: $resource}, clientType: {_eq: $clientType}}) {
    appAccountId
    appEmail
    appId
    clientType
    colors
    contactEmail
    contactFirstName
    contactLastName
    contactName
    createdDate
    deleted
    enabled
    expiresAt
    id
    name
    pageToken
    password
    phoneCountry
    phoneNumber
    refreshToken
    resource
    syncEnabled
    syncToken
    token
    updatedAt
    userId
    username
  }
}

 */

export const getAllCalendarIntegratonsByResourceAndClientType = async (
    userId: string,
    resource: string,
    clientType: 'ios' | 'android' | 'web' | 'atomic-web'
) => {
    const operationName = 'getAllCalendarIntegratonsByResourceAndClientType'; // Corrected name
    try {
        // const operationName = 'getCalendarIntegrationByResourceAndClientType' // Original name
        const query = `
            query getAllCalendarIntegratonsByResourceAndClientType($userId: uuid!, $resource: String!, $clientType: String!) {
                Calendar_Integration(where: {userId: {_eq: $userId}, resource: {_eq: $resource}, clientType: {_eq: $clientType}}) {
                appAccountId
                appEmail
                appId
                clientType
                colors
                contactEmail
                contactFirstName
                contactLastName
                contactName
                createdDate
                deleted
                enabled
                expiresAt
                id
                name
                pageToken
                password
                phoneCountry
                phoneNumber
                refreshToken
                resource
                syncEnabled
                syncToken
                token
                updatedAt
                userId
                username
                }
            }
        `

        const variables = {
            userId,
            resource,
            clientType,
        }

        const options = {
            json: { operationName, query, variables },
            headers: {
                'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin'
            },
        };

        const responseData = await resilientGot('post', postgraphileGraphUrl, options, operationName) as { data?: { Calendar_Integration: CalendarIntegrationType[] } };

        if (responseData?.data?.Calendar_Integration?.length > 0) {
            appServiceLogger.debug(`[${operationName}] Found ${responseData.data.Calendar_Integration.length} integrations.`, { userId, resource, clientType });
            return responseData.data.Calendar_Integration;
        } else {
            appServiceLogger.info(`[${operationName}] No integrations found.`, { userId, resource, clientType });
            return undefined; // Or an empty array [] depending on desired contract
        }
    } catch (e: any) {
        appServiceLogger.error(`[${operationName}] Unable to get calendar integrations.`, { userId, resource, clientType, error: e.message, stack: e.stack, details: e });
        throw e;
    }
}

export const getAllCalendarIntegrationsByResource = async (
    userId: string,
    resource: string,
) => {
    const operationName = 'getAllCalendarIntegrationsByResource'; // Corrected name
    try {
        // const operationName = 'getCalendarIntegrationByResource' // Original name
        const query = `
      query getAllCalendarIntegrationsByResource($userId: uuid!, $resource: String!) {
        Calendar_Integration(where: {userId: {_eq: $userId}, resource: {_eq: $resource}}) {
            appAccountId
            appEmail
            appId
            clientType
            colors
            contactEmail
            contactFirstName
            contactLastName
            contactName
            createdDate
            deleted
            enabled
            expiresAt
            id
            name
            pageToken
            password
            phoneCountry
            phoneNumber
            refreshToken
            resource
            syncEnabled
            syncToken
            token
            updatedAt
            userId
            username
        }
      }
    `
        const variables = {
            userId,
            resource,
        }

        const options = {
            json: { operationName, query, variables },
            headers: {
                'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin'
            },
        };

        const responseData = await resilientGot('post', postgraphileGraphUrl, options, operationName) as { data?: { Calendar_Integration: CalendarIntegrationType[] } };

        if (responseData?.data?.Calendar_Integration?.length > 0) {
            appServiceLogger.debug(`[${operationName}] Found ${responseData.data.Calendar_Integration.length} integrations.`, { userId, resource });
            return responseData.data.Calendar_Integration;
        } else {
            appServiceLogger.info(`[${operationName}] No integrations found.`, { userId, resource });
            return undefined; // Or an empty array []
        }
    } catch (e: any) {
        appServiceLogger.error(`[${operationName}] Unable to get all calendar integrations by resource.`, { userId, resource, error: e.message, stack: e.stack, details: e });
        throw e;
    }
}

export const getGoogleColors = async (
    token: string,
) => {
    const operationName = 'getGoogleColors';
    try {
        const url = googleColorUrl
        const config = {
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            responseType: 'json' as 'json', // For resilientGot
        };

        const data = await resilientGot('get', url, config, operationName) as colorResponseType;
        appServiceLogger.debug(`[${operationName}] Successfully fetched Google colors.`, { calendarColorsCount: Object.keys(data.calendar || {}).length, eventColorsCount: Object.keys(data.event || {}).length });
        return data;
    } catch (e: any) {
        appServiceLogger.error(`[${operationName}] Unable to get Google colors.`, { error: e.message, stack: e.stack, details: e });
        throw e;
    }
}

export const triggerGooglePeopleSync = async (
    calendarIntegrationId: string,
    userId: string,
    req: NextApiRequest,
) => {
    const operationName = 'triggerGooglePeopleSync';
    try {
        appServiceLogger.info(`[${operationName}] Called.`, { calendarIntegrationId, userId });
        if (!calendarIntegrationId) {
            appServiceLogger.warn(`[${operationName}] No calendarIntegrationId provided.`);
            return;
        }

        if (!userId) {
            appServiceLogger.warn(`[${operationName}] No userId provided.`);
            return;
        }
        const tokenPayload = req.session?.getAccessTokenPayload(); // Safely access session and payload
        const sessionToken = tokenPayload; // Assuming the whole payload might be the token, or adjust if it's a property like tokenPayload.jwt

        if (!sessionToken) {
            appServiceLogger.warn(`[${operationName}] No access token found in session.`);
            return;
        }

        const data = {
            calendarIntegrationId,
            userId,
            isInitialSync: true,
        }

        const url = googlePeopleSyncUrl

        const options = {
            json: data,
            headers: {
                Authorization: `Bearer ${sessionToken}`, // Use the session token
                'Content-Type': 'application/json',
            },
            responseType: 'json' as 'json',
        };

        const results = await resilientGot('post', url, options, operationName);

        appServiceLogger.info(`[${operationName}] Successfully triggered Google people sync.`, { calendarIntegrationId, userId, results });
    } catch (e: any) {
        appServiceLogger.error(`[${operationName}] Unable to trigger Google people sync.`, {
            calendarIntegrationId,
            userId,
            error: e.message,
            code: e.code,
            responseBody: e?.response?.body,
            stack: e.stack,
        });
        throw e;
    }
}
export const updateGoogleIntegration = async (
    id: string,
    enabled?: boolean,
    token?: string,
    refreshToken?: string,
    expiresAt?: string,
    syncEnabled?: boolean,
    colors?: colorType[],
    pageToken?: string,
    syncToken?: string,
    clientType?: 'ios' | 'android' | 'web' | 'atomic-web',
) => {
    const operationName = 'updateGoogleIntegration'; // Corrected name
    try {
        // const operationName = 'UpdateCalendarIntegrationById' // Original name
        const query = `
            mutation updateGoogleIntegration($id: uuid!,
                ${enabled !== undefined ? '$enabled: Boolean,' : ''}
                ${expiresAt !== undefined ? '$expiresAt: timestamptz,' : ''}
                ${refreshToken !== undefined ? '$refreshToken: String,' : ''}
                ${token !== undefined ? '$token: String,' : ''}
                ${syncEnabled !== undefined ? '$syncEnabled: Boolean,' : ''}
                ${colors !== undefined ? '$colors: jsonb,' : ''}
                ${pageToken !== undefined ? '$pageToken: String,' : ''}
                ${syncToken !== undefined ? '$syncToken: String,' : ''}
                ${clientType !== undefined ? '$clientType: String,' : ''}
                $updatedAt: timestamptz) {
                update_Calendar_Integration_by_pk(_set: {
                    ${enabled !== undefined ? 'enabled: $enabled,' : ''}
                    ${expiresAt !== undefined ? 'expiresAt: $expiresAt,' : ''}
                    ${refreshToken !== undefined ? 'refreshToken: $refreshToken,' : ''}
                    ${token !== undefined ? 'token: $token,' : ''}
                    ${syncEnabled !== undefined ? 'syncEnabled: $syncEnabled,' : ''}
                    ${colors !== undefined ? 'colors: $colors,' : ''}
                    ${pageToken !== undefined ? 'pageToken: $pageToken,' : ''}
                    ${syncToken !== undefined ? 'syncToken: $syncToken,' : ''}
                    ${clientType !== undefined ? 'clientType: $clientType,' : ''}
                    updatedAt: $updatedAt}, pk_columns: {id: $id}) {
                    appAccountId
                    appEmail
                    appId
                    colors
                    contactEmail
                    contactName
                    createdDate
                    deleted
                    enabled
                    expiresAt
                    id
                    name
                    pageToken
                    password
                    refreshToken
                    syncEnabled
                    resource
                    token
                    syncToken
                    updatedAt
                    userId
                    username
                }
            }
        `

        let variables: any = {
            id,
            updatedAt: dayjs().format(),
        }

        if (enabled !== undefined) { variables.enabled = enabled; }
        if (expiresAt !== undefined) { variables.expiresAt = expiresAt === null ? null : dayjs(expiresAt).format(); }
        if (refreshToken !== undefined) { variables.refreshToken = refreshToken; }
        if (token !== undefined) { variables.token = token; }
        if (syncEnabled !== undefined) { variables.syncEnabled = syncEnabled; }
        if (colors !== undefined) { variables.colors = colors; }
        if (pageToken !== undefined) { variables.pageToken = pageToken; }
        if (syncToken !== undefined) { variables.syncToken = syncToken; }
        if (clientType !== undefined) { variables.clientType = clientType; }

        const options = {
            json: { operationName, query, variables },
            headers: {
                'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin'
            },
        };

        const responseData = await resilientGot('post', postgraphileGraphUrl, options, operationName) as { data?: { update_Calendar_Integration_by_pk: CalendarIntegrationType } };

        appServiceLogger.info(`[${operationName}] Successfully updated Google Calendar integration.`, { integrationId: responseData?.data?.update_Calendar_Integration_by_pk?.id, enabled });
        return responseData?.data?.update_Calendar_Integration_by_pk;
    } catch (e: any) {
        appServiceLogger.error(`[${operationName}] Unable to update Google Calendar integration.`, { id, error: e.message, stack: e.stack, details: e });
        throw e;
    }
}

export const scheduleMeeting = async (
    payload: ScheduleMeetingRequestType,
    clientType: 'ios' | 'android' | 'web' | 'atomic-web',
) => {
    let integrationId = ''
    const operationName = 'getGoogleAPIToken';
    try {
        appServiceLogger.info(`[${operationName}] Attempting to get Google API token.`, { userId, resource, clientType });
        const integration = await getMinimalCalendarIntegrationByResource(userId, resource);

        if (!integration) {
            appServiceLogger.warn(`[${operationName}] No calendar integration found.`, { userId, resource });
            throw new Error('No calendar integration available.');
        }
        integrationId = integration.id; // Assign integrationId here once 'integration' is confirmed to exist

        if (!integration.refreshToken) {
            appServiceLogger.warn(`[${operationName}] No refresh token found for integration.`, { userId, resource, integrationId });
            throw new Error('No refresh token provided from calendar integration.');
        }

        appServiceLogger.debug(`[${operationName}] Integration found. Checking token validity.`, { userId, resource, integrationId, expiresAt: integration.expiresAt, tokenExists: !!integration.token });

        if (dayjs().isAfter(dayjs(integration.expiresAt)) || !integration.token) {
            appServiceLogger.info(`[${operationName}] Token expired or missing. Attempting refresh.`, { userId, resource, integrationId });
            const refreshResponse = await refreshGoogleToken(integration.refreshToken, clientType);

            if (refreshResponse && refreshResponse.access_token) {
                appServiceLogger.info(`[${operationName}] Token refresh successful. Updating integration.`, { userId, resource, integrationId });
                await updateAccessTokenCalendarIntegration(integrationId, refreshResponse.access_token, refreshResponse.expires_in);
                return refreshResponse.access_token;
            } else {
                appServiceLogger.warn(`[${operationName}] Token refresh failed or returned no access_token.`, { userId, resource, integrationId });
                // Potentially throw an error here if token refresh is critical and failed
                throw new Error('Token refresh failed to return an access token.');
            }
        }
        appServiceLogger.info(`[${operationName}] Existing token is valid.`, { userId, resource, integrationId });
        return integration.token;
    } catch (e: any) {
        appServiceLogger.error(`[${operationName}] Error getting Google API token.`, { userId, resource, clientType, integrationIdOnError: integrationId, error: e.message, stack: e.stack, details: e });
        if (integrationId) { // Attempt to disable only if integrationId was set
            try {
                appServiceLogger.info(`[${operationName}] Attempting to disable integration due to error.`, { integrationId });
                await updateAccessTokenCalendarIntegration(integrationId, null, null, false);
            } catch (disableError: any) {
                appServiceLogger.error(`[${operationName}] Failed to disable integration after error.`, { integrationId, disableError: disableError.message, stack: disableError.stack });
            }
        }
        throw e; // Re-throw the original error or a new one
    }
}


export const decryptZoomTokens = (
    encryptedToken: string,
    encryptedRefreshToken?: string,
) => {
    const ivBuffer = Buffer.from(zoomIVForPass, 'base64')
    const saltBuffer = Buffer.from(zoomSaltForPass, 'base64')

    const key = crypto.pbkdf2Sync(zoomPassKey as string, saltBuffer, 10000, 32, 'sha256')

    const decipherToken = crypto.createDecipheriv('aes-256-cbc', key, ivBuffer)
    let decryptedToken = decipherToken.update(encryptedToken, 'base64', 'utf8')
    decryptedToken += decipherToken.final('utf8')

    if (encryptedRefreshToken) {
        const decipherRefreshToken = crypto.createDecipheriv('aes-256-cbc', key, ivBuffer)
        let decryptedRefreshToken = decipherRefreshToken.update(encryptedRefreshToken, 'base64', 'utf8')
        decryptedRefreshToken += decipherRefreshToken.final('utf8')

        return {
            token: decryptedToken,
            refreshToken: decryptedRefreshToken,
        }
    }

    return {
        token: decryptedToken,
    }

}


export const encryptZoomTokens = (
    token: string,
    refreshToken?: string,
) => {
    const ivBuffer = Buffer.from(zoomIVForPass, 'base64')
    const saltBuffer = Buffer.from(zoomSaltForPass, 'base64')

    const key = crypto.pbkdf2Sync(zoomPassKey as string, saltBuffer, 10000, 32, 'sha256')
    const cipherToken = crypto.createCipheriv('aes-256-cbc', key, ivBuffer)
    let encryptedToken = cipherToken.update(token, 'utf8', 'base64');
    encryptedToken += cipherToken.final('base64')

    let encryptedRefreshToken = ''

    if (refreshToken) {
        const cipherRefreshToken = crypto.createCipheriv('aes-256-cbc', key, ivBuffer)
        encryptedRefreshToken = cipherRefreshToken.update(refreshToken, 'utf8', 'base64');
        encryptedRefreshToken += cipherRefreshToken.final('base64')
    }

    if (encryptedRefreshToken) {
        return {
            encryptedToken,
            encryptedRefreshToken
        }
    } else {
        return { encryptedToken }
    }
}

// This function was previously just for Zoom but seems generic enough for any Calendar_Integration by ID.
// However, it encrypts tokens specifically for Zoom.
// The original `updateCalendarIntegration` in `api-helper.ts` is for generic Apollo client updates.
// This `updateZoomIntegration` in `api-backend-helper.ts` is server-side and uses `got`.
// It might be better named if it's truly Zoom specific due to encryption.
// For now, just replacing console.log. Resilience for the `got` call will be added later.
export const updateZoomIntegration = async (
    id: string,
    appAccountId: string,
    appEmail: string,
    appId: string,
    token: string | null,
    expiresIn: number | null,
    refreshToken?: string,
    contactFirstName?: string,
    contactLastName?: string,
    phoneCountry?: string, // 'US'
    phoneNumber?: string, // '+1 1234567891'
    enabled?: boolean,
) => {
    try {
        //${token !== undefined ? ' $token: String,' : ''}
        // 
        const operationName = 'updateCalendarIntegrationById'
        const query = `
            mutation updateCalendarIntegrationById(
                    $id: uuid!,
                    $appAccountId: String!,
                    $appEmail: String!,
                    $appId: String!,
                    ${token !== undefined ? ' $token: String,' : ''}
                    ${refreshToken !== undefined ? ' $refreshToken: String,' : ''}
                    ${expiresIn !== undefined ? ' $expiresAt: timestamptz,' : ''}
                    ${enabled !== undefined ? ' $enabled: Boolean,' : ''}
                    ${contactFirstName !== undefined ? ' $contactFirstName: String,' : ''}
                    ${contactLastName !== undefined ? ' $contactLastName: String,' : ''}
                    ${phoneCountry !== undefined ? ' $phoneCountry: String,' : ''}
                    ${phoneNumber !== undefined ? ' $phoneNumber: String,' : ''}
                ) {
                update_Calendar_Integration_by_pk(pk_columns: {id: $id}, _set: {
                    appAccountId: $appAccountId,
                    appEmail: $appEmail,
                    appId: $appId,
                    ${token !== undefined ? 'token: $token,' : ''}
                    ${expiresIn !== undefined ? ' expiresAt: $expiresAt,' : ''}
                    ${refreshToken !== undefined ? 'refreshToken: $refreshToken,' : ''}
                    ${contactFirstName !== undefined ? 'contactFirstName: $contactFirstName,' : ''}
                    ${contactLastName !== undefined ? 'contactLastName: $contactLastName,' : ''}
                    ${phoneCountry !== undefined ? 'phoneCountry: $phoneCountry,' : ''}
                    ${phoneNumber !== undefined ? 'phoneNumber: $phoneNumber,' : ''}
                    ${enabled !== undefined ? ' enabled: $enabled,' : ''}
                }) {
                    appAccountId
                    appEmail
                    appId
                    clientType
                    colors
                    contactEmail
                    contactFirstName
                    contactLastName
                    contactName
                    createdDate
                    deleted
                    enabled
                    expiresAt
                    id
                    name
                    pageToken
                    password
                    phoneCountry
                    phoneNumber
                    refreshToken
                    resource
                    syncEnabled
                    syncToken
                    token
                    updatedAt
                    userId
                    username
                }
            }
        `

        let encryptedValues = null

        if (token) {
            encryptedValues = encryptZoomTokens(token, refreshToken)
        }

        const variables = {
            id,
            appAccountId,
            appEmail,
            appId,
            token: encryptedValues?.encryptedToken,
            expiresAt: expiresIn ? dayjs().add(expiresIn, 'seconds').toISOString() : null,
            refreshToken: refreshToken === undefined ? undefined : encryptedValues?.encryptedRefreshToken,
            contactFirstName,
            contactLastName,
            phoneCountry,
            phoneNumber,
            enabled,
        };

        const options = {
            json: { operationName, query, variables },
            headers: {
                'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin'
            },
        };

        await resilientGot('post', postgraphileGraphUrl, options, operationName);

        appServiceLogger.info(`[${operationName}] Successfully updated Zoom integration.`, { id, appAccountId, appEmail, enabled });
    } catch (e: any) {
        appServiceLogger.error(`[${operationName}] Unable to update Zoom integration.`, { id, appAccountId, appEmail, error: e.message, stack: e.stack, details: e });
        throw e; // Rethrow to ensure failure is propagated
    }
}

export const getMinimalCalendarIntegrationByName = async (
    userId: string,
    name: string,
) => {
    try {
        const operationName = 'getCalendarIntegration'
        const query = `
      query getCalendarIntegration($userId: uuid!, $name: String!) {
        Calendar_Integration(where: {userId: {_eq: $userId}, name: {_eq: $name}}) {
            appAccountId
            appEmail
            appId
            clientType
            colors
            contactEmail
            contactFirstName
            contactLastName
            contactName
            createdDate
            deleted
            enabled
            expiresAt
            id
            name
            pageToken
            password
            phoneCountry
            phoneNumber
            refreshToken
            resource
            syncEnabled
            syncToken
            token
            updatedAt
            userId
            username
        }
      }
    `
        const variables = {
            userId,
            name,
        }

        const res: { data: { Calendar_Integration: CalendarIntegrationType[] } } = await got.post(
            postgraphileGraphUrl,
            {
                json: {
                    operationName,
                    query,
                    variables,
                },
                headers: {
                    'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                    'Content-Type': 'application/json',
                    'X-Postgraphile-Role': 'admin'
                },
            },
        ).json()

        // console.log(res, ' res inside getCalendarIntegration')
        if (res?.data?.Calendar_Integration?.length > 0) {
            appServiceLogger.debug(`[getMinimalCalendarIntegrationByName] Found integration for userId: ${userId}, name: ${name}.`, { integrationId: res.data.Calendar_Integration[0].id });
            return res?.data?.Calendar_Integration?.[0];
        } else {
            appServiceLogger.info(`[getMinimalCalendarIntegrationByName] No integration found for userId: ${userId}, name: ${name}.`);
            return undefined;
        }
    } catch (e: any) {
        appServiceLogger.error('[getMinimalCalendarIntegrationByName] Unable to get calendar integration by name.', { userId, name, error: e.message, stack: e.stack, details: e });
        // Original function implicitly returns undefined.
    }
}

/**
 * query getCalendarIntegration($userId: uuid!, $resource: String!, $clientType: String!) {
  Calendar_Integration(where: {userId: {_eq: $userId}, resource: {_eq: $resource}, clientType: {_eq: $clientType}}) {
    appAccountId
    appEmail
    appId
    clientType
    colors
    contactEmail
    contactFirstName
    contactLastName
    contactName
    createdDate
    deleted
    enabled
    expiresAt
    id
    name
    pageToken
    password
    phoneCountry
    phoneNumber
    refreshToken
    resource
    syncEnabled
    syncToken
    token
    updatedAt
    userId
    username
  }
}

 */

export const getAllCalendarIntegratonsByResourceAndClientType = async (
    userId: string,
    resource: string,
    clientType: 'ios' | 'android' | 'web' | 'atomic-web'
) => {
    try {
        const operationName = 'getCalendarIntegrationByResourceAndClientType'

        const query = `
            query getCalendarIntegrationByResourceAndClientType($userId: uuid!, $resource: String!, $clientType: String!) {
                Calendar_Integration(where: {userId: {_eq: $userId}, resource: {_eq: $resource}, clientType: {_eq: $clientType}}) {
                appAccountId
                appEmail
                appId
                clientType
                colors
                contactEmail
                contactFirstName
                contactLastName
                contactName
                createdDate
                deleted
                enabled
                expiresAt
                id
                name
                pageToken
                password
                phoneCountry
                phoneNumber
                refreshToken
                resource
                syncEnabled
                syncToken
                token
                updatedAt
                userId
                username
                }
            }
        `

        const variables = {
            userId,
            resource,
            clientType,
        }

        const res: { data: { Calendar_Integration: CalendarIntegrationType[] } } = await got.post(
            postgraphileGraphUrl,
            {
                json: {
                    operationName,
                    query,
                    variables,
                },
                headers: {
                    'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                    'Content-Type': 'application/json',
                    'X-Postgraphile-Role': 'admin'
                },
            },
        ).json()

        // console.log(res, ' res inside getCalendarIntegration')
        if (res?.data?.Calendar_Integration?.length > 0) {
            appServiceLogger.debug(`[getAllCalendarIntegratonsByResourceAndClientType] Found ${res.data.Calendar_Integration.length} integrations.`, { userId, resource, clientType });
            return res?.data?.Calendar_Integration;
        } else {
            appServiceLogger.info(`[getAllCalendarIntegratonsByResourceAndClientType] No integrations found.`, { userId, resource, clientType });
            return undefined; // Or an empty array [] depending on desired contract
        }
    } catch (e: any) {
        appServiceLogger.error('[getAllCalendarIntegratonsByResourceAndClientType] Unable to get calendar integrations.', { userId, resource, clientType, error: e.message, stack: e.stack, details: e });
    }
}

export const getAllCalendarIntegrationsByResource = async (
    userId: string,
    resource: string,
) => {
    try {
        const operationName = 'getCalendarIntegrationByResource'
        const query = `
      query getCalendarIntegrationByResource($userId: uuid!, $resource: String!) {
        Calendar_Integration(where: {userId: {_eq: $userId}, resource: {_eq: $resource}}) {
            appAccountId
            appEmail
            appId
            clientType
            colors
            contactEmail
            contactFirstName
            contactLastName
            contactName
            createdDate
            deleted
            enabled
            expiresAt
            id
            name
            pageToken
            password
            phoneCountry
            phoneNumber
            refreshToken
            resource
            syncEnabled
            syncToken
            token
            updatedAt
            userId
            username
        }
      }
    `
        const variables = {
            userId,
            resource,
        }

        const res: { data: { Calendar_Integration: CalendarIntegrationType[] } } = await got.post(
            postgraphileGraphUrl,
            {
                json: {
                    operationName,
                    query,
                    variables,
                },
                headers: {
                    'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                    'Content-Type': 'application/json',
                    'X-Postgraphile-Role': 'admin'
                },
            },
        ).json()

        // console.log(res, ' res inside getCalendarIntegration')
        if (res?.data?.Calendar_Integration?.length > 0) {
            appServiceLogger.debug(`[getAllCalendarIntegrationsByResource] Found ${res.data.Calendar_Integration.length} integrations.`, { userId, resource });
            return res?.data?.Calendar_Integration;
        } else {
            appServiceLogger.info(`[getAllCalendarIntegrationsByResource] No integrations found.`, { userId, resource });
            return undefined; // Or an empty array []
        }
    } catch (e: any) {
        appServiceLogger.error('[getAllCalendarIntegrationsByResource] Unable to get all calendar integrations by resource.', { userId, resource, error: e.message, stack: e.stack, details: e });
    }
}

export const getGoogleColors = async (
    token: string,
) => {
    try {
        const url = googleColorUrl
        const config = {
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
        }

        const data: colorResponseType = await got.get(url, config).json()
        appServiceLogger.debug('[getGoogleColors] Successfully fetched Google colors.', { calendarColorsCount: Object.keys(data.calendar || {}).length, eventColorsCount: Object.keys(data.event || {}).length });
        return data
    } catch (e: any) {
        appServiceLogger.error('[getGoogleColors] Unable to get Google colors.', { error: e.message, stack: e.stack, details: e });
        // Original function implicitly returns undefined.
    }
}

export const triggerGooglePeopleSync = async (
    calendarIntegrationId: string,
    userId: string,
    req: NextApiRequest,
) => {
    const operationName = 'triggerGooglePeopleSync';
    try {
        appServiceLogger.info(`[${operationName}] Called.`, { calendarIntegrationId, userId });
        if (!calendarIntegrationId) {
            appServiceLogger.warn(`[${operationName}] No calendarIntegrationId provided.`);
            return;
        }

        if (!userId) {
            appServiceLogger.warn(`[${operationName}] No userId provided.`);
            return;
        }
        const tokenPayload = req.session?.getAccessTokenPayload(); // Safely access session and payload
        const token = tokenPayload; // Assuming the whole payload might be the token, or adjust if it's a property like tokenPayload.jwt

        if (!token) {
            appServiceLogger.warn(`[${operationName}] No access token found in session.`);
            // Depending on requirements, might throw an error or return a specific response
            return; // Or handle error appropriately
        }

        const data = {
            calendarIntegrationId,
            userId,
            isInitialSync: true,
        }

        const url = googlePeopleSyncUrl

        const results = await got.post(url, {
            json: data,
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
        }).json()

        appServiceLogger.info(`[${operationName}] Successfully triggered Google people sync.`, { calendarIntegrationId, userId, results });
    } catch (e: any) {
        appServiceLogger.error(`[${operationName}] Unable to trigger Google people sync.`, {
            calendarIntegrationId,
            userId,
            error: e.message,
            code: e.code,
            responseBody: e?.response?.body, // Log the actual response body if available
            stack: e.stack,
        });
        // Original function implicitly returns undefined on error.
    }
}
export const updateGoogleIntegration = async (
    id: string,
    enabled?: boolean,
    token?: string,
    refreshToken?: string,
    expiresAt?: string,
    syncEnabled?: boolean,
    colors?: colorType[],
    pageToken?: string,
    syncToken?: string,
    clientType?: 'ios' | 'android' | 'web' | 'atomic-web',
) => {
    try {
        const operationName = 'UpdateCalendarIntegrationById'
        const query = `
            mutation UpdateCalendarIntegrationById($id: uuid!, 
                ${enabled !== undefined ? '$enabled: Boolean,' : ''} 
                ${expiresAt !== undefined ? '$expiresAt: timestamptz,' : ''} 
                ${refreshToken !== undefined ? '$refreshToken: String,' : ''} 
                ${token !== undefined ? '$token: String,' : ''}
                ${syncEnabled !== undefined ? '$syncEnabled: Boolean,' : ''}
                ${colors !== undefined ? '$colors: jsonb,' : ''}
                ${pageToken !== undefined ? '$pageToken: String,' : ''}
                ${syncToken !== undefined ? '$syncToken: String,' : ''}
                ${clientType !== undefined ? '$clientType: String,' : ''}
                $updatedAt: timestamptz) {
                update_Calendar_Integration_by_pk(_set: {
                    ${enabled !== undefined ? 'enabled: $enabled,' : ''} 
                    ${expiresAt !== undefined ? 'expiresAt: $expiresAt,' : ''} 
                    ${refreshToken !== undefined ? 'refreshToken: $refreshToken,' : ''} 
                    ${token !== undefined ? 'token: $token,' : ''}
                    ${syncEnabled !== undefined ? 'syncEnabled: $syncEnabled,' : ''}
                    ${colors !== undefined ? 'colors: $colors,' : ''}
                    ${pageToken !== undefined ? 'pageToken: $pageToken,' : ''}
                    ${syncToken !== undefined ? 'syncToken: $syncToken,' : ''}
                    ${clientType !== undefined ? 'clientType: $clientType,' : ''}
                    updatedAt: $updatedAt}, pk_columns: {id: $id}) {
                    appAccountId
                    appEmail
                    appId
                    colors
                    contactEmail
                    contactName
                    createdDate
                    deleted
                    enabled
                    expiresAt
                    id
                    name
                    pageToken
                    password
                    refreshToken
                    syncEnabled
                    resource
                    token
                    syncToken
                    updatedAt
                    userId
                    username
                }
            }
        `

        let variables: any = {
            id,
            updatedAt: dayjs().format(),
        }

        if (enabled !== undefined) {
            variables.enabled = enabled
        }

        if (expiresAt !== undefined) {
            if (expiresAt === null) {
                variables.expiresAt = null
            } else {
                variables.expiresAt = dayjs(expiresAt).format()
            }
        }

        if (refreshToken !== undefined) {
            variables.refreshToken = refreshToken
        }

        if (token !== undefined) {
            variables.token = token
        }

        if (syncEnabled !== undefined) {
            variables.syncEnabled = syncEnabled
        }

        if (colors !== undefined) {
            variables.colors = colors
        }

        if (pageToken !== undefined) {
            variables.pageToken = pageToken
        }

        if (syncToken !== undefined) {
            variables.syncToken = syncToken
        }

        if (clientType !== undefined) {
            variables.clientType = clientType
        }

        const res: { data: { update_Calendar_Integration_by_pk: CalendarIntegrationType } } = await got.post(
            postgraphileGraphUrl,
            {
                json: {
                    operationName,
                    query,
                    variables,
                },
                headers: {
                    'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                    'Content-Type': 'application/json',
                    'X-Postgraphile-Role': 'admin'
                },
            },
        ).json()

        appServiceLogger.info('[updateGoogleIntegration] Successfully updated Google Calendar integration.', { integrationId: res?.data?.update_Calendar_Integration_by_pk?.id, enabled });
        return res?.data?.update_Calendar_Integration_by_pk;
    } catch (e: any) {
        appServiceLogger.error('[updateGoogleIntegration] Unable to update Google Calendar integration.', { id, error: e.message, stack: e.stack, details: e });
        // Original function implicitly returns undefined.
    }
}

export const scheduleMeeting = async (
    payload: ScheduleMeetingRequestType,
    // TODO: Add userId and token once auth is figured out for this endpoint
): Promise<any> => { // eslint-disable-line @typescript-eslint/no-explicit-any
    const operationName = 'scheduleMeeting';
    const url = `${SCHEDULER_API_URL}/timeTable/user/scheduleMeeting`;
    appServiceLogger.info(`[${operationName}] Called.`, { url, requestPayload: payload });

    try {
        // This got.post call will be wrapped with resilience later.
        const response = await got.post(url, {
            json: payload,
            headers: {
                'Content-Type': 'application/json',
                // 'Authorization': `Bearer ${token}`, // TODO: Add when auth is available
            },
            // timeout: { request: 15000 }, // Example: Adding a timeout
        }).json();

        appServiceLogger.info(`[${operationName}] Successfully scheduled meeting.`, { url, response });
        return response;
    } catch (e: any) {
        const errorContext = {
            operationName,
            url,
            requestPayload: payload,
            error: e.message,
            code: e.code,
            statusCode: e.response?.statusCode,
            responseBody: e.response?.body,
            stack: e.stack,
        };
        appServiceLogger.error(`[${operationName}] Error calling scheduleMeeting API.`, errorContext);

        // Rethrow a more structured error or the original error
        // The original code rethrew a new error based on parsing the response body.
        if (e?.response?.body) {
            try {
                // Attempt to parse as JSON, but handle non-JSON responses gracefully
                const errorBodyStr = typeof e.response.body === 'string' ? e.response.body : JSON.stringify(e.response.body);
                let parsedErrorBody;
                try {
                    parsedErrorBody = JSON.parse(errorBodyStr);
                } catch (jsonParseError) {
                    // If body is not JSON, use the raw string
                    parsedErrorBody = { message: errorBodyStr };
                }
                throw new Error(`API Error from ${operationName}: ${parsedErrorBody.message || errorBodyStr}`);
            } catch (parseError: any) {
                throw new Error(`API Error from ${operationName} (unparseable body): ${e.response.body || e.message}`);
            }
        }
        throw new Error(e.message || `Failed to ${operationName} due to an unknown error`);
    }
};
