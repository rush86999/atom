"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getMinimalCalendarIntegrationByName = exports.updateZoomIntegration = exports.encryptZoomTokens = exports.decryptZoomTokens = exports.scheduleMeeting = exports.updateGoogleIntegration = exports.triggerGooglePeopleSync = exports.getGoogleColors = exports.getAllCalendarIntegrationsByResource = exports.getAllCalendarIntegratonsByResourceAndClientType = exports.refreshGoogleToken = exports.updateAccessTokenCalendarIntegration = exports.getMinimalCalendarIntegrationByResource = exports.generateGoogleAuthUrl = exports.exchangeCodeForTokens = void 0;
const got_1 = __importDefault(require("got"));
const date_utils_1 = require("@lib/date-utils");
const lodash_1 = __importDefault(require("lodash"));
const constants_1 = require("@lib/constants");
const googleapis_1 = require("googleapis");
const crypto_1 = __importDefault(require("crypto"));
const constants_2 = require("./calendarLib/constants");
const logger_1 = __importDefault(require("./logger")); // Import the shared logger
const constants_3 = require("./contactLib/constants");
const constants_4 = require("./constants");
// Generic resilient 'got' wrapper for app-service backend helpers
const resilientGot = async (method, url, options, // Adjust as needed for form/json etc.
operationName = 'externalApiCall' // Default operation name for logging
) => {
    const MAX_RETRIES = 3;
    // Standardize timeout, e.g. 15s, can be overridden in options if needed by specific calls
    const DEFAULT_TIMEOUT_MS = options?.timeout?.request || 15000;
    let attempt = 0;
    let lastError = null;
    const gotOptions = {
        ...options,
        timeout: { request: DEFAULT_TIMEOUT_MS }, // Ensure timeout is set
        retry: { limit: 0 }, // Disable got's native retry, we're handling it manually
        throwHttpErrors: true, // Ensure got throws on HTTP errors > 399
        responseType: options?.responseType || 'json', // Default to JSON, can be overridden
    }; // Cast to base Options for got call
    while (attempt < MAX_RETRIES) {
        try {
            logger_1.default.info(`[${operationName}] Attempt ${attempt + 1}/${MAX_RETRIES} - ${method.toUpperCase()} ${url}`, { url, method, options: lodash_1.default.omit(gotOptions, ['headers.Authorization']) }); // Omit sensitive headers
            let response;
            switch (method.toLowerCase()) {
                case 'get':
                    response = await got_1.default.get(url, gotOptions);
                    break;
                case 'post':
                    response = await got_1.default.post(url, gotOptions);
                    break;
                case 'patch':
                    response = await got_1.default.patch(url, gotOptions);
                    break;
                case 'put':
                    response = await got_1.default.put(url, gotOptions);
                    break;
                case 'delete':
                    response = await got_1.default.delete(url, gotOptions);
                    break;
                default:
                    throw new Error(`Unsupported HTTP method: ${method}`);
            }
            logger_1.default.info(`[${operationName}] Attempt ${attempt + 1} successful.`, { url, method, statusCode: response.statusCode });
            return response.body; // got already parses if responseType is 'json'
        }
        catch (error) {
            lastError = error;
            const statusCode = error.response?.statusCode;
            const errorCode = error.code;
            logger_1.default.warn(`[${operationName}] Attempt ${attempt + 1}/${MAX_RETRIES} failed.`, {
                url,
                method,
                attempt: attempt + 1,
                error: error.message,
                statusCode,
                errorCode,
                // responseBody: error.response?.body, // Be cautious logging full response bodies
            });
            // Decide if we should retry
            const isRetryableHttpError = statusCode &&
                (statusCode >= 500 || statusCode === 408 || statusCode === 429);
            const isRetryableNetworkError = errorCode &&
                [
                    'ETIMEDOUT',
                    'ECONNRESET',
                    'EADDRINUSE',
                    'ECONNREFUSED',
                    'EPIPE',
                    'ENETUNREACH',
                    'EAI_AGAIN',
                ].includes(errorCode);
            if (!isRetryableHttpError && !isRetryableNetworkError) {
                logger_1.default.error(`[${operationName}] Non-retryable error encountered. Aborting retries.`, { url, method, statusCode, errorCode });
                break; // Break for non-retryable errors
            }
        }
        attempt++;
        if (attempt < MAX_RETRIES) {
            const delay = Math.pow(2, attempt - 1) * 1000; // e.g., 1s, 2s
            logger_1.default.info(`[${operationName}] Waiting ${delay}ms before retry ${attempt + 1}/${MAX_RETRIES}.`, { url, method });
            await new Promise((resolve) => setTimeout(resolve, delay));
        }
    }
    logger_1.default.error(`[${operationName}] Failed after ${attempt} attempts.`, {
        url,
        method,
        lastError: lastError?.message,
        lastStatusCode: lastError?.response?.statusCode,
    });
    throw (lastError ||
        new Error(`[${operationName}] Failed after all retries for ${method.toUpperCase()} ${url}.`));
};
const oauth2Client = new googleapis_1.google.auth.OAuth2(constants_1.googleClientIdAtomicWeb, constants_1.googleClientSecretAtomicWeb, constants_1.googleOAuthAtomicWebRedirectUrl);
const exchangeCodeForTokens = async (code) => {
    try {
        let { tokens } = await oauth2Client.getToken(code);
        oauth2Client.setCredentials(tokens);
        logger_1.default.info('[exchangeCodeForTokens] Successfully exchanged code for tokens.', { codePrefix: code?.substring(0, 10), tokenExpiry: tokens.expiry_date });
        return tokens;
    }
    catch (e) {
        logger_1.default.error('[exchangeCodeForTokens] Unable to exchange code for tokens.', {
            codePrefix: code?.substring(0, 10),
            error: e.message,
            stack: e.stack,
            details: e,
        });
        throw e; // Rethrow the error
    }
};
exports.exchangeCodeForTokens = exchangeCodeForTokens;
const generateGoogleAuthUrl = (state) => {
    // Access scopes
    const scopes = [
        'https://www.googleapis.com/auth/calendar.readonly',
        'https://www.googleapis.com/auth/calendar.events',
        'https://www.googleapis.com/auth/contacts.readonly',
        'https://www.googleapis.com/auth/gmail.readonly', // Added Gmail readonly scope
    ];
    const config = {
        // 'online' (default) or 'offline' (gets refresh_token)
        access_type: 'offline',
        /** Pass in the scopes array defined above.
         * Alternatively, if only one scope is needed, you can pass a scope URL as a string */
        scope: scopes,
        // Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes: true,
    };
    if (state) {
        config.state = state;
    }
    // Generate a url that asks permissions for the Calendar activity scope
    const authorizationUrl = oauth2Client.generateAuthUrl(config);
    // console.log(authorizationUrl, ' authorizationUrl')
    return authorizationUrl;
};
exports.generateGoogleAuthUrl = generateGoogleAuthUrl;
const getMinimalCalendarIntegrationByResource = async (userId, resource) => {
    try {
        const operationName = 'getCalendarIntegration';
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
    `;
        const variables = {
            userId,
            resource,
        };
        const options = {
            json: { operationName, query, variables },
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin', // Assuming admin role as per original direct call
            },
        };
        const responseData = (await resilientGot('post', constants_1.postgraphileGraphUrl, options, operationName));
        if (responseData?.data?.Calendar_Integration?.length > 0) {
            logger_1.default.debug(`[${operationName}] Found integration for userId: ${userId}, resource: ${resource}.`, { integrationId: responseData.data.Calendar_Integration[0].id });
            return responseData.data.Calendar_Integration[0];
        }
        else {
            logger_1.default.info(`[${operationName}] No integration found for userId: ${userId}, resource: ${resource}.`);
            return undefined;
        }
    }
    catch (e) {
        logger_1.default.error(`[${operationName}] Unable to get calendar integration.`, { userId, resource, error: e.message, stack: e.stack, details: e });
        // resilientGot will throw, this catch is for any additional handling or if it's not caught by resilientGot (unlikely for HTTP errors)
        throw e; // Rethrow to ensure failure is propagated if not already by resilientGot
    }
};
exports.getMinimalCalendarIntegrationByResource = getMinimalCalendarIntegrationByResource;
const updateAccessTokenCalendarIntegration = async (id, token, expiresIn, enabled, refreshToken) => {
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
    `;
        let variables = {
            id,
            token,
            expiresAt: expiresIn
                ? (0, date_utils_1.dayjs)().add(expiresIn, 'seconds').toISOString()
                : null,
        };
        if (enabled !== undefined) {
            variables.enabled = enabled;
        }
        if (refreshToken !== undefined) {
            variables.refreshToken = refreshToken;
        }
        const gotOptions = {
            json: { operationName, query, variables },
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
        };
        // Using resilientGot now
        await resilientGot('post', constants_1.postgraphileGraphUrl, gotOptions, operationName);
        logger_1.default.info(`[${operationName}] Successfully updated calendar integration.`, { id, enabled, hasToken: !!token, hasRefreshToken: !!refreshToken });
        // Original function implicitly returns undefined, and resilientGot for POST might not return meaningful data unless specified.
    }
    catch (e) {
        logger_1.default.error(`[${operationName}] Unable to update calendar integration.`, { id, error: e.message, stack: e.stack, details: e });
        // resilientGot will throw, this catch is for any additional handling
        throw e;
    }
};
exports.updateAccessTokenCalendarIntegration = updateAccessTokenCalendarIntegration;
const refreshGoogleToken = async (refreshToken, clientType) => {
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
    `;
        const variables = {
            userId,
            name,
        };
        const options = {
            json: { operationName, query, variables },
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
        };
        const responseData = (await resilientGot('post', constants_1.postgraphileGraphUrl, options, operationName));
        if (responseData?.data?.Calendar_Integration?.length > 0) {
            logger_1.default.debug(`[${operationName}] Found integration for userId: ${userId}, name: ${name}.`, { integrationId: responseData.data.Calendar_Integration[0].id });
            return responseData.data.Calendar_Integration[0];
        }
        else {
            logger_1.default.info(`[${operationName}] No integration found for userId: ${userId}, name: ${name}.`);
            return undefined;
        }
    }
    catch (e) {
        logger_1.default.error(`[${operationName}] Unable to get calendar integration by name.`, { userId, name, error: e.message, stack: e.stack, details: e });
        throw e;
    }
};
exports.refreshGoogleToken = refreshGoogleToken;
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
const getAllCalendarIntegratonsByResourceAndClientType = async (userId, resource, clientType) => {
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
        `;
        const variables = {
            userId,
            resource,
            clientType,
        };
        const options = {
            json: { operationName, query, variables },
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
        };
        const responseData = (await resilientGot('post', constants_1.postgraphileGraphUrl, options, operationName));
        if (responseData?.data?.Calendar_Integration?.length > 0) {
            logger_1.default.debug(`[${operationName}] Found ${responseData.data.Calendar_Integration.length} integrations.`, { userId, resource, clientType });
            return responseData.data.Calendar_Integration;
        }
        else {
            logger_1.default.info(`[${operationName}] No integrations found.`, {
                userId,
                resource,
                clientType,
            });
            return undefined; // Or an empty array [] depending on desired contract
        }
    }
    catch (e) {
        logger_1.default.error(`[${operationName}] Unable to get calendar integrations.`, {
            userId,
            resource,
            clientType,
            error: e.message,
            stack: e.stack,
            details: e,
        });
        throw e;
    }
};
exports.getAllCalendarIntegratonsByResourceAndClientType = getAllCalendarIntegratonsByResourceAndClientType;
const getAllCalendarIntegrationsByResource = async (userId, resource) => {
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
    `;
        const variables = {
            userId,
            resource,
        };
        const options = {
            json: { operationName, query, variables },
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
        };
        const responseData = (await resilientGot('post', constants_1.postgraphileGraphUrl, options, operationName));
        if (responseData?.data?.Calendar_Integration?.length > 0) {
            logger_1.default.debug(`[${operationName}] Found ${responseData.data.Calendar_Integration.length} integrations.`, { userId, resource });
            return responseData.data.Calendar_Integration;
        }
        else {
            logger_1.default.info(`[${operationName}] No integrations found.`, {
                userId,
                resource,
            });
            return undefined; // Or an empty array []
        }
    }
    catch (e) {
        logger_1.default.error(`[${operationName}] Unable to get all calendar integrations by resource.`, { userId, resource, error: e.message, stack: e.stack, details: e });
        throw e;
    }
};
exports.getAllCalendarIntegrationsByResource = getAllCalendarIntegrationsByResource;
const getGoogleColors = async (token) => {
    const operationName = 'getGoogleColors';
    try {
        const url = constants_2.googleColorUrl;
        const config = {
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
            responseType: 'json', // For resilientGot
        };
        const data = (await resilientGot('get', url, config, operationName));
        logger_1.default.debug(`[${operationName}] Successfully fetched Google colors.`, {
            calendarColorsCount: Object.keys(data.calendar || {}).length,
            eventColorsCount: Object.keys(data.event || {}).length,
        });
        return data;
    }
    catch (e) {
        logger_1.default.error(`[${operationName}] Unable to get Google colors.`, {
            error: e.message,
            stack: e.stack,
            details: e,
        });
        throw e;
    }
};
exports.getGoogleColors = getGoogleColors;
const triggerGooglePeopleSync = async (calendarIntegrationId, userId, req) => {
    const operationName = 'triggerGooglePeopleSync';
    try {
        logger_1.default.info(`[${operationName}] Called.`, {
            calendarIntegrationId,
            userId,
        });
        if (!calendarIntegrationId) {
            logger_1.default.warn(`[${operationName}] No calendarIntegrationId provided.`);
            return;
        }
        if (!userId) {
            logger_1.default.warn(`[${operationName}] No userId provided.`);
            return;
        }
        const tokenPayload = req.session?.getAccessTokenPayload(); // Safely access session and payload
        const sessionToken = tokenPayload; // Assuming the whole payload might be the token, or adjust if it's a property like tokenPayload.jwt
        if (!sessionToken) {
            logger_1.default.warn(`[${operationName}] No access token found in session.`);
            return;
        }
        const data = {
            calendarIntegrationId,
            userId,
            isInitialSync: true,
        };
        const url = constants_3.googlePeopleSyncUrl;
        const options = {
            json: data,
            headers: {
                Authorization: `Bearer ${sessionToken}`, // Use the session token
                'Content-Type': 'application/json',
            },
            responseType: 'json',
        };
        const results = await resilientGot('post', url, options, operationName);
        logger_1.default.info(`[${operationName}] Successfully triggered Google people sync.`, { calendarIntegrationId, userId, results });
    }
    catch (e) {
        logger_1.default.error(`[${operationName}] Unable to trigger Google people sync.`, {
            calendarIntegrationId,
            userId,
            error: e.message,
            code: e.code,
            responseBody: e?.response?.body,
            stack: e.stack,
        });
        throw e;
    }
};
exports.triggerGooglePeopleSync = triggerGooglePeopleSync;
const updateGoogleIntegration = async (id, enabled, token, refreshToken, expiresAt, syncEnabled, colors, pageToken, syncToken, clientType) => {
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
        `;
        let variables = {
            id,
            updatedAt: (0, date_utils_1.dayjs)().format(),
        };
        if (enabled !== undefined) {
            variables.enabled = enabled;
        }
        if (expiresAt !== undefined) {
            variables.expiresAt =
                expiresAt === null ? null : (0, date_utils_1.dayjs)(expiresAt).format();
        }
        if (refreshToken !== undefined) {
            variables.refreshToken = refreshToken;
        }
        if (token !== undefined) {
            variables.token = token;
        }
        if (syncEnabled !== undefined) {
            variables.syncEnabled = syncEnabled;
        }
        if (colors !== undefined) {
            variables.colors = colors;
        }
        if (pageToken !== undefined) {
            variables.pageToken = pageToken;
        }
        if (syncToken !== undefined) {
            variables.syncToken = syncToken;
        }
        if (clientType !== undefined) {
            variables.clientType = clientType;
        }
        const options = {
            json: { operationName, query, variables },
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
        };
        const responseData = (await resilientGot('post', constants_1.postgraphileGraphUrl, options, operationName));
        logger_1.default.info(`[${operationName}] Successfully updated Google Calendar integration.`, {
            integrationId: responseData?.data?.update_Calendar_Integration_by_pk?.id,
            enabled,
        });
        return responseData?.data?.update_Calendar_Integration_by_pk;
    }
    catch (e) {
        logger_1.default.error(`[${operationName}] Unable to update Google Calendar integration.`, { id, error: e.message, stack: e.stack, details: e });
        throw e;
    }
};
exports.updateGoogleIntegration = updateGoogleIntegration;
const scheduleMeeting = async (payload, clientType) => {
    let integrationId = '';
    const operationName = 'getGoogleAPIToken';
    try {
        logger_1.default.info(`[${operationName}] Attempting to get Google API token.`, { userId, resource, clientType });
        const integration = await (0, exports.getMinimalCalendarIntegrationByResource)(userId, resource);
        if (!integration) {
            logger_1.default.warn(`[${operationName}] No calendar integration found.`, { userId, resource });
            throw new Error('No calendar integration available.');
        }
        integrationId = integration.id; // Assign integrationId here once 'integration' is confirmed to exist
        if (!integration.refreshToken) {
            logger_1.default.warn(`[${operationName}] No refresh token found for integration.`, { userId, resource, integrationId });
            throw new Error('No refresh token provided from calendar integration.');
        }
        logger_1.default.debug(`[${operationName}] Integration found. Checking token validity.`, {
            userId,
            resource,
            integrationId,
            expiresAt: integration.expiresAt,
            tokenExists: !!integration.token,
        });
        if ((0, date_utils_1.dayjs)().isAfter((0, date_utils_1.dayjs)(integration.expiresAt)) || !integration.token) {
            logger_1.default.info(`[${operationName}] Token expired or missing. Attempting refresh.`, { userId, resource, integrationId });
            const refreshResponse = await (0, exports.refreshGoogleToken)(integration.refreshToken, clientType);
            if (refreshResponse && refreshResponse.access_token) {
                logger_1.default.info(`[${operationName}] Token refresh successful. Updating integration.`, { userId, resource, integrationId });
                await (0, exports.updateAccessTokenCalendarIntegration)(integrationId, refreshResponse.access_token, refreshResponse.expires_in);
                return refreshResponse.access_token;
            }
            else {
                logger_1.default.warn(`[${operationName}] Token refresh failed or returned no access_token.`, { userId, resource, integrationId });
                // Potentially throw an error here if token refresh is critical and failed
                throw new Error('Token refresh failed to return an access token.');
            }
        }
        logger_1.default.info(`[${operationName}] Existing token is valid.`, {
            userId,
            resource,
            integrationId,
        });
        return integration.token;
    }
    catch (e) {
        logger_1.default.error(`[${operationName}] Error getting Google API token.`, {
            userId,
            resource,
            clientType,
            integrationIdOnError: integrationId,
            error: e.message,
            stack: e.stack,
            details: e,
        });
        if (integrationId) {
            // Attempt to disable only if integrationId was set
            try {
                logger_1.default.info(`[${operationName}] Attempting to disable integration due to error.`, { integrationId });
                await (0, exports.updateAccessTokenCalendarIntegration)(integrationId, null, null, false);
            }
            catch (disableError) {
                logger_1.default.error(`[${operationName}] Failed to disable integration after error.`, {
                    integrationId,
                    disableError: disableError.message,
                    stack: disableError.stack,
                });
            }
        }
        throw e; // Re-throw the original error or a new one
    }
};
exports.scheduleMeeting = scheduleMeeting;
const decryptZoomTokens = (encryptedToken, encryptedRefreshToken) => {
    const ivBuffer = Buffer.from(constants_1.zoomIVForPass, 'base64');
    const saltBuffer = Buffer.from(constants_1.zoomSaltForPass, 'base64');
    const key = crypto_1.default.pbkdf2Sync(constants_1.zoomPassKey, saltBuffer, 10000, 32, 'sha256');
    const decipherToken = crypto_1.default.createDecipheriv('aes-256-cbc', key, ivBuffer);
    let decryptedToken = decipherToken.update(encryptedToken, 'base64', 'utf8');
    decryptedToken += decipherToken.final('utf8');
    if (encryptedRefreshToken) {
        const decipherRefreshToken = crypto_1.default.createDecipheriv('aes-256-cbc', key, ivBuffer);
        let decryptedRefreshToken = decipherRefreshToken.update(encryptedRefreshToken, 'base64', 'utf8');
        decryptedRefreshToken += decipherRefreshToken.final('utf8');
        return {
            token: decryptedToken,
            refreshToken: decryptedRefreshToken,
        };
    }
    return {
        token: decryptedToken,
    };
};
exports.decryptZoomTokens = decryptZoomTokens;
const encryptZoomTokens = (token, refreshToken) => {
    const ivBuffer = Buffer.from(constants_1.zoomIVForPass, 'base64');
    const saltBuffer = Buffer.from(constants_1.zoomSaltForPass, 'base64');
    const key = crypto_1.default.pbkdf2Sync(constants_1.zoomPassKey, saltBuffer, 10000, 32, 'sha256');
    const cipherToken = crypto_1.default.createCipheriv('aes-256-cbc', key, ivBuffer);
    let encryptedToken = cipherToken.update(token, 'utf8', 'base64');
    encryptedToken += cipherToken.final('base64');
    let encryptedRefreshToken = '';
    if (refreshToken) {
        const cipherRefreshToken = crypto_1.default.createCipheriv('aes-256-cbc', key, ivBuffer);
        encryptedRefreshToken = cipherRefreshToken.update(refreshToken, 'utf8', 'base64');
        encryptedRefreshToken += cipherRefreshToken.final('base64');
    }
    if (encryptedRefreshToken) {
        return {
            encryptedToken,
            encryptedRefreshToken,
        };
    }
    else {
        return { encryptedToken };
    }
};
exports.encryptZoomTokens = encryptZoomTokens;
// This function was previously just for Zoom but seems generic enough for any Calendar_Integration by ID.
// However, it encrypts tokens specifically for Zoom.
// The original `updateCalendarIntegration` in `api-helper.ts` is for generic Apollo client updates.
// This `updateZoomIntegration` in `api-backend-helper.ts` is server-side and uses `got`.
// It might be better named if it's truly Zoom specific due to encryption.
// For now, just replacing console.log. Resilience for the `got` call will be added later.
const updateZoomIntegration = async (id, appAccountId, appEmail, appId, token, expiresIn, refreshToken, contactFirstName, contactLastName, phoneCountry, // 'US'
phoneNumber, // '+1 1234567891'
enabled) => {
    try {
        //${token !== undefined ? ' $token: String,' : ''}
        //
        const operationName = 'updateCalendarIntegrationById';
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
        `;
        let encryptedValues = null;
        if (token) {
            encryptedValues = (0, exports.encryptZoomTokens)(token, refreshToken);
        }
        const variables = {
            id,
            appAccountId,
            appEmail,
            appId,
            token: encryptedValues?.encryptedToken,
            expiresAt: expiresIn
                ? (0, date_utils_1.dayjs)().add(expiresIn, 'seconds').toISOString()
                : null,
            refreshToken: refreshToken === undefined
                ? undefined
                : encryptedValues?.encryptedRefreshToken,
            contactFirstName,
            contactLastName,
            phoneCountry,
            phoneNumber,
            enabled,
        };
        const options = {
            json: { operationName, query, variables },
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
        };
        await resilientGot('post', constants_1.postgraphileGraphUrl, options, operationName);
        logger_1.default.info(`[${operationName}] Successfully updated Zoom integration.`, { id, appAccountId, appEmail, enabled });
    }
    catch (e) {
        logger_1.default.error(`[${operationName}] Unable to update Zoom integration.`, {
            id,
            appAccountId,
            appEmail,
            error: e.message,
            stack: e.stack,
            details: e,
        });
        throw e; // Rethrow to ensure failure is propagated
    }
};
exports.updateZoomIntegration = updateZoomIntegration;
const getMinimalCalendarIntegrationByName = async (userId, name) => {
    try {
        const operationName = 'getCalendarIntegration';
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
    `;
        const variables = {
            userId,
            name,
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            json: {
                operationName,
                query,
                variables,
            },
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
        })
            .json();
        // console.log(res, ' res inside getCalendarIntegration')
        if (res?.data?.Calendar_Integration?.length > 0) {
            logger_1.default.debug(`[getMinimalCalendarIntegrationByName] Found integration for userId: ${userId}, name: ${name}.`, { integrationId: res.data.Calendar_Integration[0].id });
            return res?.data?.Calendar_Integration?.[0];
        }
        else {
            logger_1.default.info(`[getMinimalCalendarIntegrationByName] No integration found for userId: ${userId}, name: ${name}.`);
            return undefined;
        }
    }
    catch (e) {
        logger_1.default.error('[getMinimalCalendarIntegrationByName] Unable to get calendar integration by name.', { userId, name, error: e.message, stack: e.stack, details: e });
        // Original function implicitly returns undefined.
    }
};
exports.getMinimalCalendarIntegrationByName = getMinimalCalendarIntegrationByName;
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
const getAllCalendarIntegratonsByResourceAndClientType = async (userId, resource, clientType) => {
    try {
        const operationName = 'getCalendarIntegrationByResourceAndClientType';
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
        `;
        const variables = {
            userId,
            resource,
            clientType,
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            json: {
                operationName,
                query,
                variables,
            },
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
        })
            .json();
        // console.log(res, ' res inside getCalendarIntegration')
        if (res?.data?.Calendar_Integration?.length > 0) {
            logger_1.default.debug(`[getAllCalendarIntegratonsByResourceAndClientType] Found ${res.data.Calendar_Integration.length} integrations.`, { userId, resource, clientType });
            return res?.data?.Calendar_Integration;
        }
        else {
            logger_1.default.info(`[getAllCalendarIntegratonsByResourceAndClientType] No integrations found.`, { userId, resource, clientType });
            return undefined; // Or an empty array [] depending on desired contract
        }
    }
    catch (e) {
        logger_1.default.error('[getAllCalendarIntegratonsByResourceAndClientType] Unable to get calendar integrations.', {
            userId,
            resource,
            clientType,
            error: e.message,
            stack: e.stack,
            details: e,
        });
    }
};
exports.getAllCalendarIntegratonsByResourceAndClientType = getAllCalendarIntegratonsByResourceAndClientType;
const getAllCalendarIntegrationsByResource = async (userId, resource) => {
    try {
        const operationName = 'getCalendarIntegrationByResource';
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
    `;
        const variables = {
            userId,
            resource,
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            json: {
                operationName,
                query,
                variables,
            },
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
        })
            .json();
        // console.log(res, ' res inside getCalendarIntegration')
        if (res?.data?.Calendar_Integration?.length > 0) {
            logger_1.default.debug(`[getAllCalendarIntegrationsByResource] Found ${res.data.Calendar_Integration.length} integrations.`, { userId, resource });
            return res?.data?.Calendar_Integration;
        }
        else {
            logger_1.default.info(`[getAllCalendarIntegrationsByResource] No integrations found.`, { userId, resource });
            return undefined; // Or an empty array []
        }
    }
    catch (e) {
        logger_1.default.error('[getAllCalendarIntegrationsByResource] Unable to get all calendar integrations by resource.', { userId, resource, error: e.message, stack: e.stack, details: e });
    }
};
exports.getAllCalendarIntegrationsByResource = getAllCalendarIntegrationsByResource;
const getGoogleColors = async (token) => {
    try {
        const url = constants_2.googleColorUrl;
        const config = {
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
        };
        const data = await got_1.default.get(url, config).json();
        logger_1.default.debug('[getGoogleColors] Successfully fetched Google colors.', {
            calendarColorsCount: Object.keys(data.calendar || {}).length,
            eventColorsCount: Object.keys(data.event || {}).length,
        });
        return data;
    }
    catch (e) {
        logger_1.default.error('[getGoogleColors] Unable to get Google colors.', {
            error: e.message,
            stack: e.stack,
            details: e,
        });
        // Original function implicitly returns undefined.
    }
};
exports.getGoogleColors = getGoogleColors;
const triggerGooglePeopleSync = async (calendarIntegrationId, userId, req) => {
    const operationName = 'triggerGooglePeopleSync';
    try {
        logger_1.default.info(`[${operationName}] Called.`, {
            calendarIntegrationId,
            userId,
        });
        if (!calendarIntegrationId) {
            logger_1.default.warn(`[${operationName}] No calendarIntegrationId provided.`);
            return;
        }
        if (!userId) {
            logger_1.default.warn(`[${operationName}] No userId provided.`);
            return;
        }
        const tokenPayload = req.session?.getAccessTokenPayload(); // Safely access session and payload
        const token = tokenPayload; // Assuming the whole payload might be the token, or adjust if it's a property like tokenPayload.jwt
        if (!token) {
            logger_1.default.warn(`[${operationName}] No access token found in session.`);
            // Depending on requirements, might throw an error or return a specific response
            return; // Or handle error appropriately
        }
        const data = {
            calendarIntegrationId,
            userId,
            isInitialSync: true,
        };
        const url = constants_3.googlePeopleSyncUrl;
        const results = await got_1.default
            .post(url, {
            json: data,
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
        })
            .json();
        logger_1.default.info(`[${operationName}] Successfully triggered Google people sync.`, { calendarIntegrationId, userId, results });
    }
    catch (e) {
        logger_1.default.error(`[${operationName}] Unable to trigger Google people sync.`, {
            calendarIntegrationId,
            userId,
            error: e.message,
            code: e.code,
            responseBody: e?.response?.body, // Log the actual response body if available
            stack: e.stack,
        });
        // Original function implicitly returns undefined on error.
    }
};
exports.triggerGooglePeopleSync = triggerGooglePeopleSync;
const updateGoogleIntegration = async (id, enabled, token, refreshToken, expiresAt, syncEnabled, colors, pageToken, syncToken, clientType) => {
    try {
        const operationName = 'UpdateCalendarIntegrationById';
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
        `;
        let variables = {
            id,
            updatedAt: (0, date_utils_1.dayjs)().format(),
        };
        if (enabled !== undefined) {
            variables.enabled = enabled;
        }
        if (expiresAt !== undefined) {
            if (expiresAt === null) {
                variables.expiresAt = null;
            }
            else {
                variables.expiresAt = (0, date_utils_1.dayjs)(expiresAt).format();
            }
        }
        if (refreshToken !== undefined) {
            variables.refreshToken = refreshToken;
        }
        if (token !== undefined) {
            variables.token = token;
        }
        if (syncEnabled !== undefined) {
            variables.syncEnabled = syncEnabled;
        }
        if (colors !== undefined) {
            variables.colors = colors;
        }
        if (pageToken !== undefined) {
            variables.pageToken = pageToken;
        }
        if (syncToken !== undefined) {
            variables.syncToken = syncToken;
        }
        if (clientType !== undefined) {
            variables.clientType = clientType;
        }
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            json: {
                operationName,
                query,
                variables,
            },
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
        })
            .json();
        logger_1.default.info('[updateGoogleIntegration] Successfully updated Google Calendar integration.', {
            integrationId: res?.data?.update_Calendar_Integration_by_pk?.id,
            enabled,
        });
        return res?.data?.update_Calendar_Integration_by_pk;
    }
    catch (e) {
        logger_1.default.error('[updateGoogleIntegration] Unable to update Google Calendar integration.', { id, error: e.message, stack: e.stack, details: e });
        // Original function implicitly returns undefined.
    }
};
exports.updateGoogleIntegration = updateGoogleIntegration;
const scheduleMeeting = async (payload
// TODO: Add userId and token once auth is figured out for this endpoint
) => {
    // eslint-disable-line @typescript-eslint/no-explicit-any
    const operationName = 'scheduleMeeting';
    const url = `${constants_4.SCHEDULER_API_URL}/timeTable/user/scheduleMeeting`;
    logger_1.default.info(`[${operationName}] Called.`, {
        url,
        requestPayload: payload,
    });
    try {
        // This got.post call will be wrapped with resilience later.
        const response = await got_1.default
            .post(url, {
            json: payload,
            headers: {
                'Content-Type': 'application/json',
                // 'Authorization': `Bearer ${token}`, // TODO: Add when auth is available
            },
            // timeout: { request: 15000 }, // Example: Adding a timeout
        })
            .json();
        logger_1.default.info(`[${operationName}] Successfully scheduled meeting.`, { url, response });
        return response;
    }
    catch (e) {
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
        logger_1.default.error(`[${operationName}] Error calling scheduleMeeting API.`, errorContext);
        // Rethrow a more structured error or the original error
        // The original code rethrew a new error based on parsing the response body.
        if (e?.response?.body) {
            try {
                // Attempt to parse as JSON, but handle non-JSON responses gracefully
                const errorBodyStr = typeof e.response.body === 'string'
                    ? e.response.body
                    : JSON.stringify(e.response.body);
                let parsedErrorBody;
                try {
                    parsedErrorBody = JSON.parse(errorBodyStr);
                }
                catch (jsonParseError) {
                    // If body is not JSON, use the raw string
                    parsedErrorBody = { message: errorBodyStr };
                }
                throw new Error(`API Error from ${operationName}: ${parsedErrorBody.message || errorBodyStr}`);
            }
            catch (parseError) {
                throw new Error(`API Error from ${operationName} (unparseable body): ${e.response.body || e.message}`);
            }
        }
        throw new Error(e.message || `Failed to ${operationName} due to an unknown error`);
    }
};
exports.scheduleMeeting = scheduleMeeting;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWJhY2tlbmQtaGVscGVyLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiYXBpLWJhY2tlbmQtaGVscGVyLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7OztBQUFBLDhDQUFzQjtBQUN0QixnREFBd0M7QUFDeEMsb0RBQXVCO0FBQ3ZCLDhDQVV3QjtBQUt4QiwyQ0FBb0M7QUFFcEMsb0RBQTRDO0FBSzVDLHVEQUF5RDtBQUN6RCxzREFBd0MsQ0FBQywyQkFBMkI7QUFHcEUsc0RBQTZEO0FBRTdELDJDQUFnRDtBQUVoRCxrRUFBa0U7QUFDbEUsTUFBTSxZQUFZLEdBQUcsS0FBSyxFQUN4QixNQUFtRCxFQUNuRCxHQUFXLEVBQ1gsT0FFMkMsRUFBRSxzQ0FBc0M7QUFDbkYsZ0JBQXdCLGlCQUFpQixDQUFDLHFDQUFxQztFQUMvRSxFQUFFO0lBQ0YsTUFBTSxXQUFXLEdBQUcsQ0FBQyxDQUFDO0lBQ3RCLDBGQUEwRjtJQUMxRixNQUFNLGtCQUFrQixHQUFHLE9BQU8sRUFBRSxPQUFPLEVBQUUsT0FBTyxJQUFJLEtBQUssQ0FBQztJQUM5RCxJQUFJLE9BQU8sR0FBRyxDQUFDLENBQUM7SUFDaEIsSUFBSSxTQUFTLEdBQVEsSUFBSSxDQUFDO0lBRTFCLE1BQU0sVUFBVSxHQUFHO1FBQ2pCLEdBQUcsT0FBTztRQUNWLE9BQU8sRUFBRSxFQUFFLE9BQU8sRUFBRSxrQkFBa0IsRUFBRSxFQUFFLHdCQUF3QjtRQUNsRSxLQUFLLEVBQUUsRUFBRSxLQUFLLEVBQUUsQ0FBQyxFQUFFLEVBQUUseURBQXlEO1FBQzlFLGVBQWUsRUFBRSxJQUFJLEVBQUUseUNBQXlDO1FBQ2hFLFlBQVksRUFBRSxPQUFPLEVBQUUsWUFBWSxJQUFJLE1BQU0sRUFBRSxxQ0FBcUM7S0FDNUQsQ0FBQyxDQUFDLG9DQUFvQztJQUVoRSxPQUFPLE9BQU8sR0FBRyxXQUFXLEVBQUUsQ0FBQztRQUM3QixJQUFJLENBQUM7WUFDSCxnQkFBZ0IsQ0FBQyxJQUFJLENBQ25CLElBQUksYUFBYSxhQUFhLE9BQU8sR0FBRyxDQUFDLElBQUksV0FBVyxNQUFNLE1BQU0sQ0FBQyxXQUFXLEVBQUUsSUFBSSxHQUFHLEVBQUUsRUFDM0YsRUFBRSxHQUFHLEVBQUUsTUFBTSxFQUFFLE9BQU8sRUFBRSxnQkFBQyxDQUFDLElBQUksQ0FBQyxVQUFVLEVBQUUsQ0FBQyx1QkFBdUIsQ0FBQyxDQUFDLEVBQUUsQ0FDeEUsQ0FBQyxDQUFDLHlCQUF5QjtZQUU1QixJQUFJLFFBQXdDLENBQUM7WUFDN0MsUUFBUSxNQUFNLENBQUMsV0FBVyxFQUFFLEVBQUUsQ0FBQztnQkFDN0IsS0FBSyxLQUFLO29CQUNSLFFBQVEsR0FBRyxNQUFNLGFBQUcsQ0FBQyxHQUFHLENBQUMsR0FBRyxFQUFFLFVBQVUsQ0FBQyxDQUFDO29CQUMxQyxNQUFNO2dCQUNSLEtBQUssTUFBTTtvQkFDVCxRQUFRLEdBQUcsTUFBTSxhQUFHLENBQUMsSUFBSSxDQUFDLEdBQUcsRUFBRSxVQUFVLENBQUMsQ0FBQztvQkFDM0MsTUFBTTtnQkFDUixLQUFLLE9BQU87b0JBQ1YsUUFBUSxHQUFHLE1BQU0sYUFBRyxDQUFDLEtBQUssQ0FBQyxHQUFHLEVBQUUsVUFBVSxDQUFDLENBQUM7b0JBQzVDLE1BQU07Z0JBQ1IsS0FBSyxLQUFLO29CQUNSLFFBQVEsR0FBRyxNQUFNLGFBQUcsQ0FBQyxHQUFHLENBQUMsR0FBRyxFQUFFLFVBQVUsQ0FBQyxDQUFDO29CQUMxQyxNQUFNO2dCQUNSLEtBQUssUUFBUTtvQkFDWCxRQUFRLEdBQUcsTUFBTSxhQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsRUFBRSxVQUFVLENBQUMsQ0FBQztvQkFDN0MsTUFBTTtnQkFDUjtvQkFDRSxNQUFNLElBQUksS0FBSyxDQUFDLDRCQUE0QixNQUFNLEVBQUUsQ0FBQyxDQUFDO1lBQzFELENBQUM7WUFFRCxnQkFBZ0IsQ0FBQyxJQUFJLENBQ25CLElBQUksYUFBYSxhQUFhLE9BQU8sR0FBRyxDQUFDLGNBQWMsRUFDdkQsRUFBRSxHQUFHLEVBQUUsTUFBTSxFQUFFLFVBQVUsRUFBRSxRQUFRLENBQUMsVUFBVSxFQUFFLENBQ2pELENBQUM7WUFDRixPQUFPLFFBQVEsQ0FBQyxJQUFJLENBQUMsQ0FBQywrQ0FBK0M7UUFDdkUsQ0FBQztRQUFDLE9BQU8sS0FBVSxFQUFFLENBQUM7WUFDcEIsU0FBUyxHQUFHLEtBQUssQ0FBQztZQUNsQixNQUFNLFVBQVUsR0FBRyxLQUFLLENBQUMsUUFBUSxFQUFFLFVBQVUsQ0FBQztZQUM5QyxNQUFNLFNBQVMsR0FBRyxLQUFLLENBQUMsSUFBSSxDQUFDO1lBRTdCLGdCQUFnQixDQUFDLElBQUksQ0FDbkIsSUFBSSxhQUFhLGFBQWEsT0FBTyxHQUFHLENBQUMsSUFBSSxXQUFXLFVBQVUsRUFDbEU7Z0JBQ0UsR0FBRztnQkFDSCxNQUFNO2dCQUNOLE9BQU8sRUFBRSxPQUFPLEdBQUcsQ0FBQztnQkFDcEIsS0FBSyxFQUFFLEtBQUssQ0FBQyxPQUFPO2dCQUNwQixVQUFVO2dCQUNWLFNBQVM7Z0JBQ1Qsa0ZBQWtGO2FBQ25GLENBQ0YsQ0FBQztZQUVGLDRCQUE0QjtZQUM1QixNQUFNLG9CQUFvQixHQUN4QixVQUFVO2dCQUNWLENBQUMsVUFBVSxJQUFJLEdBQUcsSUFBSSxVQUFVLEtBQUssR0FBRyxJQUFJLFVBQVUsS0FBSyxHQUFHLENBQUMsQ0FBQztZQUNsRSxNQUFNLHVCQUF1QixHQUMzQixTQUFTO2dCQUNUO29CQUNFLFdBQVc7b0JBQ1gsWUFBWTtvQkFDWixZQUFZO29CQUNaLGNBQWM7b0JBQ2QsT0FBTztvQkFDUCxhQUFhO29CQUNiLFdBQVc7aUJBQ1osQ0FBQyxRQUFRLENBQUMsU0FBUyxDQUFDLENBQUM7WUFFeEIsSUFBSSxDQUFDLG9CQUFvQixJQUFJLENBQUMsdUJBQXVCLEVBQUUsQ0FBQztnQkFDdEQsZ0JBQWdCLENBQUMsS0FBSyxDQUNwQixJQUFJLGFBQWEsc0RBQXNELEVBQ3ZFLEVBQUUsR0FBRyxFQUFFLE1BQU0sRUFBRSxVQUFVLEVBQUUsU0FBUyxFQUFFLENBQ3ZDLENBQUM7Z0JBQ0YsTUFBTSxDQUFDLGlDQUFpQztZQUMxQyxDQUFDO1FBQ0gsQ0FBQztRQUNELE9BQU8sRUFBRSxDQUFDO1FBQ1YsSUFBSSxPQUFPLEdBQUcsV0FBVyxFQUFFLENBQUM7WUFDMUIsTUFBTSxLQUFLLEdBQUcsSUFBSSxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsT0FBTyxHQUFHLENBQUMsQ0FBQyxHQUFHLElBQUksQ0FBQyxDQUFDLGVBQWU7WUFDOUQsZ0JBQWdCLENBQUMsSUFBSSxDQUNuQixJQUFJLGFBQWEsYUFBYSxLQUFLLG1CQUFtQixPQUFPLEdBQUcsQ0FBQyxJQUFJLFdBQVcsR0FBRyxFQUNuRixFQUFFLEdBQUcsRUFBRSxNQUFNLEVBQUUsQ0FDaEIsQ0FBQztZQUNGLE1BQU0sSUFBSSxPQUFPLENBQUMsQ0FBQyxPQUFPLEVBQUUsRUFBRSxDQUFDLFVBQVUsQ0FBQyxPQUFPLEVBQUUsS0FBSyxDQUFDLENBQUMsQ0FBQztRQUM3RCxDQUFDO0lBQ0gsQ0FBQztJQUNELGdCQUFnQixDQUFDLEtBQUssQ0FDcEIsSUFBSSxhQUFhLGtCQUFrQixPQUFPLFlBQVksRUFDdEQ7UUFDRSxHQUFHO1FBQ0gsTUFBTTtRQUNOLFNBQVMsRUFBRSxTQUFTLEVBQUUsT0FBTztRQUM3QixjQUFjLEVBQUUsU0FBUyxFQUFFLFFBQVEsRUFBRSxVQUFVO0tBQ2hELENBQ0YsQ0FBQztJQUNGLE1BQU0sQ0FDSixTQUFTO1FBQ1QsSUFBSSxLQUFLLENBQ1AsSUFBSSxhQUFhLGtDQUFrQyxNQUFNLENBQUMsV0FBVyxFQUFFLElBQUksR0FBRyxHQUFHLENBQ2xGLENBQ0YsQ0FBQztBQUNKLENBQUMsQ0FBQztBQUVGLE1BQU0sWUFBWSxHQUFHLElBQUksbUJBQU0sQ0FBQyxJQUFJLENBQUMsTUFBTSxDQUN6QyxtQ0FBdUIsRUFDdkIsdUNBQTJCLEVBQzNCLDJDQUErQixDQUNoQyxDQUFDO0FBRUssTUFBTSxxQkFBcUIsR0FBRyxLQUFLLEVBQ3hDLElBQVksRUFDVSxFQUFFO0lBQ3hCLElBQUksQ0FBQztRQUNILElBQUksRUFBRSxNQUFNLEVBQUUsR0FBRyxNQUFNLFlBQVksQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUFDLENBQUM7UUFDbkQsWUFBWSxDQUFDLGNBQWMsQ0FBQyxNQUFNLENBQUMsQ0FBQztRQUNwQyxnQkFBZ0IsQ0FBQyxJQUFJLENBQ25CLGlFQUFpRSxFQUNqRSxFQUFFLFVBQVUsRUFBRSxJQUFJLEVBQUUsU0FBUyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsRUFBRSxXQUFXLEVBQUUsTUFBTSxDQUFDLFdBQVcsRUFBRSxDQUN4RSxDQUFDO1FBQ0YsT0FBTyxNQUFNLENBQUM7SUFDaEIsQ0FBQztJQUFDLE9BQU8sQ0FBTSxFQUFFLENBQUM7UUFDaEIsZ0JBQWdCLENBQUMsS0FBSyxDQUNwQiw2REFBNkQsRUFDN0Q7WUFDRSxVQUFVLEVBQUUsSUFBSSxFQUFFLFNBQVMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDO1lBQ2xDLEtBQUssRUFBRSxDQUFDLENBQUMsT0FBTztZQUNoQixLQUFLLEVBQUUsQ0FBQyxDQUFDLEtBQUs7WUFDZCxPQUFPLEVBQUUsQ0FBQztTQUNYLENBQ0YsQ0FBQztRQUNGLE1BQU0sQ0FBQyxDQUFDLENBQUMsb0JBQW9CO0lBQy9CLENBQUM7QUFDSCxDQUFDLENBQUM7QUF2QlcsUUFBQSxxQkFBcUIseUJBdUJoQztBQUVLLE1BQU0scUJBQXFCLEdBQUcsQ0FBQyxLQUFjLEVBQUUsRUFBRTtJQUN0RCxnQkFBZ0I7SUFDaEIsTUFBTSxNQUFNLEdBQUc7UUFDYixtREFBbUQ7UUFDbkQsaURBQWlEO1FBQ2pELG1EQUFtRDtRQUNuRCxnREFBZ0QsRUFBRSw2QkFBNkI7S0FDaEYsQ0FBQztJQUVGLE1BQU0sTUFBTSxHQUFRO1FBQ2xCLHVEQUF1RDtRQUN2RCxXQUFXLEVBQUUsU0FBUztRQUN0Qjs4RkFDc0Y7UUFDdEYsS0FBSyxFQUFFLE1BQU07UUFDYixvRUFBb0U7UUFDcEUsc0JBQXNCLEVBQUUsSUFBSTtLQUM3QixDQUFDO0lBRUYsSUFBSSxLQUFLLEVBQUUsQ0FBQztRQUNWLE1BQU0sQ0FBQyxLQUFLLEdBQUcsS0FBSyxDQUFDO0lBQ3ZCLENBQUM7SUFDRCx1RUFBdUU7SUFDdkUsTUFBTSxnQkFBZ0IsR0FBRyxZQUFZLENBQUMsZUFBZSxDQUFDLE1BQU0sQ0FBQyxDQUFDO0lBRTlELHFEQUFxRDtJQUVyRCxPQUFPLGdCQUFnQixDQUFDO0FBQzFCLENBQUMsQ0FBQztBQTVCVyxRQUFBLHFCQUFxQix5QkE0QmhDO0FBRUssTUFBTSx1Q0FBdUMsR0FBRyxLQUFLLEVBQzFELE1BQWMsRUFDZCxRQUFnQixFQUNoQixFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsTUFBTSxhQUFhLEdBQUcsd0JBQXdCLENBQUM7UUFDL0MsTUFBTSxLQUFLLEdBQUc7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0tBZ0NiLENBQUM7UUFDRixNQUFNLFNBQVMsR0FBRztZQUNoQixNQUFNO1lBQ04sUUFBUTtTQUNULENBQUM7UUFFRixNQUFNLE9BQU8sR0FBRztZQUNkLElBQUksRUFBRSxFQUFFLGFBQWEsRUFBRSxLQUFLLEVBQUUsU0FBUyxFQUFFO1lBQ3pDLE9BQU8sRUFBRTtnQkFDUCw2QkFBNkIsRUFBRSxtQ0FBdUI7Z0JBQ3RELGNBQWMsRUFBRSxrQkFBa0I7Z0JBQ2xDLHFCQUFxQixFQUFFLE9BQU8sRUFBRSxrREFBa0Q7YUFDbkY7U0FDRixDQUFDO1FBRUYsTUFBTSxZQUFZLEdBQUcsQ0FBQyxNQUFNLFlBQVksQ0FDdEMsTUFBTSxFQUNOLGdDQUFvQixFQUNwQixPQUFPLEVBQ1AsYUFBYSxDQUNkLENBQW1FLENBQUM7UUFFckUsSUFBSSxZQUFZLEVBQUUsSUFBSSxFQUFFLG9CQUFvQixFQUFFLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztZQUN6RCxnQkFBZ0IsQ0FBQyxLQUFLLENBQ3BCLElBQUksYUFBYSxtQ0FBbUMsTUFBTSxlQUFlLFFBQVEsR0FBRyxFQUNwRixFQUFFLGFBQWEsRUFBRSxZQUFZLENBQUMsSUFBSSxDQUFDLG9CQUFvQixDQUFDLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUNoRSxDQUFDO1lBQ0YsT0FBTyxZQUFZLENBQUMsSUFBSSxDQUFDLG9CQUFvQixDQUFDLENBQUMsQ0FBQyxDQUFDO1FBQ25ELENBQUM7YUFBTSxDQUFDO1lBQ04sZ0JBQWdCLENBQUMsSUFBSSxDQUNuQixJQUFJLGFBQWEsc0NBQXNDLE1BQU0sZUFBZSxRQUFRLEdBQUcsQ0FDeEYsQ0FBQztZQUNGLE9BQU8sU0FBUyxDQUFDO1FBQ25CLENBQUM7SUFDSCxDQUFDO0lBQUMsT0FBTyxDQUFNLEVBQUUsQ0FBQztRQUNoQixnQkFBZ0IsQ0FBQyxLQUFLLENBQ3BCLElBQUksYUFBYSx1Q0FBdUMsRUFDeEQsRUFBRSxNQUFNLEVBQUUsUUFBUSxFQUFFLEtBQUssRUFBRSxDQUFDLENBQUMsT0FBTyxFQUFFLEtBQUssRUFBRSxDQUFDLENBQUMsS0FBSyxFQUFFLE9BQU8sRUFBRSxDQUFDLEVBQUUsQ0FDbkUsQ0FBQztRQUNGLHNJQUFzSTtRQUN0SSxNQUFNLENBQUMsQ0FBQyxDQUFDLHlFQUF5RTtJQUNwRixDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBaEZXLFFBQUEsdUNBQXVDLDJDQWdGbEQ7QUFFSyxNQUFNLG9DQUFvQyxHQUFHLEtBQUssRUFDdkQsRUFBVSxFQUNWLEtBQW9CLEVBQ3BCLFNBQXdCLEVBQ3hCLE9BQWlCLEVBQ2pCLFlBQTRCLEVBQzVCLEVBQUU7SUFDRixNQUFNLGFBQWEsR0FBRyxzQ0FBc0MsQ0FBQyxDQUFDLHVEQUF1RDtJQUNySCxJQUFJLENBQUM7UUFDSCxxRUFBcUU7UUFDckUsTUFBTSxLQUFLLEdBQUc7aUVBQytDLEtBQUssS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLGtCQUFrQixDQUFDLENBQUMsQ0FBQyxFQUFFLEdBQUcsWUFBWSxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMseUJBQXlCLENBQUMsQ0FBQyxDQUFDLEVBQUUsR0FBRyxTQUFTLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQywyQkFBMkIsQ0FBQyxDQUFDLENBQUMsRUFBRSxHQUFHLE9BQU8sS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLHFCQUFxQixDQUFDLENBQUMsQ0FBQyxFQUFFOzBFQUNwTixLQUFLLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDLENBQUMsRUFBRSxHQUFHLFlBQVksS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLCtCQUErQixDQUFDLENBQUMsQ0FBQyxFQUFFLEdBQUcsU0FBUyxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMseUJBQXlCLENBQUMsQ0FBQyxDQUFDLEVBQUUsR0FBRyxPQUFPLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyxxQkFBcUIsQ0FBQyxDQUFDLENBQUMsRUFBRTs7Ozs7Ozs7OztLQVVwUyxDQUFDO1FBQ0YsSUFBSSxTQUFTLEdBQVE7WUFDbkIsRUFBRTtZQUNGLEtBQUs7WUFDTCxTQUFTLEVBQUUsU0FBUztnQkFDbEIsQ0FBQyxDQUFDLElBQUEsa0JBQUssR0FBRSxDQUFDLEdBQUcsQ0FBQyxTQUFTLEVBQUUsU0FBUyxDQUFDLENBQUMsV0FBVyxFQUFFO2dCQUNqRCxDQUFDLENBQUMsSUFBSTtTQUNULENBQUM7UUFFRixJQUFJLE9BQU8sS0FBSyxTQUFTLEVBQUUsQ0FBQztZQUMxQixTQUFTLENBQUMsT0FBTyxHQUFHLE9BQU8sQ0FBQztRQUM5QixDQUFDO1FBRUQsSUFBSSxZQUFZLEtBQUssU0FBUyxFQUFFLENBQUM7WUFDL0IsU0FBUyxDQUFDLFlBQVksR0FBRyxZQUFZLENBQUM7UUFDeEMsQ0FBQztRQUVELE1BQU0sVUFBVSxHQUFHO1lBQ2pCLElBQUksRUFBRSxFQUFFLGFBQWEsRUFBRSxLQUFLLEVBQUUsU0FBUyxFQUFFO1lBQ3pDLE9BQU8sRUFBRTtnQkFDUCw2QkFBNkIsRUFBRSxtQ0FBdUI7Z0JBQ3RELGNBQWMsRUFBRSxrQkFBa0I7Z0JBQ2xDLHFCQUFxQixFQUFFLE9BQU87YUFDL0I7U0FDRixDQUFDO1FBRUYseUJBQXlCO1FBQ3pCLE1BQU0sWUFBWSxDQUFDLE1BQU0sRUFBRSxnQ0FBb0IsRUFBRSxVQUFVLEVBQUUsYUFBYSxDQUFDLENBQUM7UUFFNUUsZ0JBQWdCLENBQUMsSUFBSSxDQUNuQixJQUFJLGFBQWEsOENBQThDLEVBQy9ELEVBQUUsRUFBRSxFQUFFLE9BQU8sRUFBRSxRQUFRLEVBQUUsQ0FBQyxDQUFDLEtBQUssRUFBRSxlQUFlLEVBQUUsQ0FBQyxDQUFDLFlBQVksRUFBRSxDQUNwRSxDQUFDO1FBQ0YsK0hBQStIO0lBQ2pJLENBQUM7SUFBQyxPQUFPLENBQU0sRUFBRSxDQUFDO1FBQ2hCLGdCQUFnQixDQUFDLEtBQUssQ0FDcEIsSUFBSSxhQUFhLDBDQUEwQyxFQUMzRCxFQUFFLEVBQUUsRUFBRSxLQUFLLEVBQUUsQ0FBQyxDQUFDLE9BQU8sRUFBRSxLQUFLLEVBQUUsQ0FBQyxDQUFDLEtBQUssRUFBRSxPQUFPLEVBQUUsQ0FBQyxFQUFFLENBQ3JELENBQUM7UUFDRixxRUFBcUU7UUFDckUsTUFBTSxDQUFDLENBQUM7SUFDVixDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBaEVXLFFBQUEsb0NBQW9DLHdDQWdFL0M7QUFFSyxNQUFNLGtCQUFrQixHQUFHLEtBQUssRUFDckMsWUFBb0IsRUFDcEIsVUFBb0QsRUFTcEQsRUFBRTtJQUNGLE1BQU0sYUFBYSxHQUFHLHFDQUFxQyxDQUFDLENBQUMsMkJBQTJCO0lBQ3hGLElBQUksQ0FBQztRQUNILCtFQUErRTtRQUMvRSxNQUFNLEtBQUssR0FBRzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7S0FnQ2IsQ0FBQztRQUNGLE1BQU0sU0FBUyxHQUFHO1lBQ2hCLE1BQU07WUFDTixJQUFJO1NBQ0wsQ0FBQztRQUVGLE1BQU0sT0FBTyxHQUFHO1lBQ2QsSUFBSSxFQUFFLEVBQUUsYUFBYSxFQUFFLEtBQUssRUFBRSxTQUFTLEVBQUU7WUFDekMsT0FBTyxFQUFFO2dCQUNQLDZCQUE2QixFQUFFLG1DQUF1QjtnQkFDdEQsY0FBYyxFQUFFLGtCQUFrQjtnQkFDbEMscUJBQXFCLEVBQUUsT0FBTzthQUMvQjtTQUNGLENBQUM7UUFFRixNQUFNLFlBQVksR0FBRyxDQUFDLE1BQU0sWUFBWSxDQUN0QyxNQUFNLEVBQ04sZ0NBQW9CLEVBQ3BCLE9BQU8sRUFDUCxhQUFhLENBQ2QsQ0FBbUUsQ0FBQztRQUVyRSxJQUFJLFlBQVksRUFBRSxJQUFJLEVBQUUsb0JBQW9CLEVBQUUsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDO1lBQ3pELGdCQUFnQixDQUFDLEtBQUssQ0FDcEIsSUFBSSxhQUFhLG1DQUFtQyxNQUFNLFdBQVcsSUFBSSxHQUFHLEVBQzVFLEVBQUUsYUFBYSxFQUFFLFlBQVksQ0FBQyxJQUFJLENBQUMsb0JBQW9CLENBQUMsQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQ2hFLENBQUM7WUFDRixPQUFPLFlBQVksQ0FBQyxJQUFJLENBQUMsb0JBQW9CLENBQUMsQ0FBQyxDQUFDLENBQUM7UUFDbkQsQ0FBQzthQUFNLENBQUM7WUFDTixnQkFBZ0IsQ0FBQyxJQUFJLENBQ25CLElBQUksYUFBYSxzQ0FBc0MsTUFBTSxXQUFXLElBQUksR0FBRyxDQUNoRixDQUFDO1lBQ0YsT0FBTyxTQUFTLENBQUM7UUFDbkIsQ0FBQztJQUNILENBQUM7SUFBQyxPQUFPLENBQU0sRUFBRSxDQUFDO1FBQ2hCLGdCQUFnQixDQUFDLEtBQUssQ0FDcEIsSUFBSSxhQUFhLCtDQUErQyxFQUNoRSxFQUFFLE1BQU0sRUFBRSxJQUFJLEVBQUUsS0FBSyxFQUFFLENBQUMsQ0FBQyxPQUFPLEVBQUUsS0FBSyxFQUFFLENBQUMsQ0FBQyxLQUFLLEVBQUUsT0FBTyxFQUFFLENBQUMsRUFBRSxDQUMvRCxDQUFDO1FBQ0YsTUFBTSxDQUFDLENBQUM7SUFDVixDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBeEZXLFFBQUEsa0JBQWtCLHNCQXdGN0I7QUFFRjs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0dBaUNHO0FBRUksTUFBTSxnREFBZ0QsR0FBRyxLQUFLLEVBQ25FLE1BQWMsRUFDZCxRQUFnQixFQUNoQixVQUFvRCxFQUNwRCxFQUFFO0lBQ0YsTUFBTSxhQUFhLEdBQUcsa0RBQWtELENBQUMsQ0FBQyxpQkFBaUI7SUFDM0YsSUFBSSxDQUFDO1FBQ0gseUZBQXlGO1FBQ3pGLE1BQU0sS0FBSyxHQUFHOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztTQWdDVCxDQUFDO1FBRU4sTUFBTSxTQUFTLEdBQUc7WUFDaEIsTUFBTTtZQUNOLFFBQVE7WUFDUixVQUFVO1NBQ1gsQ0FBQztRQUVGLE1BQU0sT0FBTyxHQUFHO1lBQ2QsSUFBSSxFQUFFLEVBQUUsYUFBYSxFQUFFLEtBQUssRUFBRSxTQUFTLEVBQUU7WUFDekMsT0FBTyxFQUFFO2dCQUNQLDZCQUE2QixFQUFFLG1DQUF1QjtnQkFDdEQsY0FBYyxFQUFFLGtCQUFrQjtnQkFDbEMscUJBQXFCLEVBQUUsT0FBTzthQUMvQjtTQUNGLENBQUM7UUFFRixNQUFNLFlBQVksR0FBRyxDQUFDLE1BQU0sWUFBWSxDQUN0QyxNQUFNLEVBQ04sZ0NBQW9CLEVBQ3BCLE9BQU8sRUFDUCxhQUFhLENBQ2QsQ0FBbUUsQ0FBQztRQUVyRSxJQUFJLFlBQVksRUFBRSxJQUFJLEVBQUUsb0JBQW9CLEVBQUUsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDO1lBQ3pELGdCQUFnQixDQUFDLEtBQUssQ0FDcEIsSUFBSSxhQUFhLFdBQVcsWUFBWSxDQUFDLElBQUksQ0FBQyxvQkFBb0IsQ0FBQyxNQUFNLGdCQUFnQixFQUN6RixFQUFFLE1BQU0sRUFBRSxRQUFRLEVBQUUsVUFBVSxFQUFFLENBQ2pDLENBQUM7WUFDRixPQUFPLFlBQVksQ0FBQyxJQUFJLENBQUMsb0JBQW9CLENBQUM7UUFDaEQsQ0FBQzthQUFNLENBQUM7WUFDTixnQkFBZ0IsQ0FBQyxJQUFJLENBQUMsSUFBSSxhQUFhLDBCQUEwQixFQUFFO2dCQUNqRSxNQUFNO2dCQUNOLFFBQVE7Z0JBQ1IsVUFBVTthQUNYLENBQUMsQ0FBQztZQUNILE9BQU8sU0FBUyxDQUFDLENBQUMscURBQXFEO1FBQ3pFLENBQUM7SUFDSCxDQUFDO0lBQUMsT0FBTyxDQUFNLEVBQUUsQ0FBQztRQUNoQixnQkFBZ0IsQ0FBQyxLQUFLLENBQ3BCLElBQUksYUFBYSx3Q0FBd0MsRUFDekQ7WUFDRSxNQUFNO1lBQ04sUUFBUTtZQUNSLFVBQVU7WUFDVixLQUFLLEVBQUUsQ0FBQyxDQUFDLE9BQU87WUFDaEIsS0FBSyxFQUFFLENBQUMsQ0FBQyxLQUFLO1lBQ2QsT0FBTyxFQUFFLENBQUM7U0FDWCxDQUNGLENBQUM7UUFDRixNQUFNLENBQUMsQ0FBQztJQUNWLENBQUM7QUFDSCxDQUFDLENBQUM7QUE1RlcsUUFBQSxnREFBZ0Qsb0RBNEYzRDtBQUVLLE1BQU0sb0NBQW9DLEdBQUcsS0FBSyxFQUN2RCxNQUFjLEVBQ2QsUUFBZ0IsRUFDaEIsRUFBRTtJQUNGLE1BQU0sYUFBYSxHQUFHLHNDQUFzQyxDQUFDLENBQUMsaUJBQWlCO0lBQy9FLElBQUksQ0FBQztRQUNILDRFQUE0RTtRQUM1RSxNQUFNLEtBQUssR0FBRzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7S0FnQ2IsQ0FBQztRQUNGLE1BQU0sU0FBUyxHQUFHO1lBQ2hCLE1BQU07WUFDTixRQUFRO1NBQ1QsQ0FBQztRQUVGLE1BQU0sT0FBTyxHQUFHO1lBQ2QsSUFBSSxFQUFFLEVBQUUsYUFBYSxFQUFFLEtBQUssRUFBRSxTQUFTLEVBQUU7WUFDekMsT0FBTyxFQUFFO2dCQUNQLDZCQUE2QixFQUFFLG1DQUF1QjtnQkFDdEQsY0FBYyxFQUFFLGtCQUFrQjtnQkFDbEMscUJBQXFCLEVBQUUsT0FBTzthQUMvQjtTQUNGLENBQUM7UUFFRixNQUFNLFlBQVksR0FBRyxDQUFDLE1BQU0sWUFBWSxDQUN0QyxNQUFNLEVBQ04sZ0NBQW9CLEVBQ3BCLE9BQU8sRUFDUCxhQUFhLENBQ2QsQ0FBbUUsQ0FBQztRQUVyRSxJQUFJLFlBQVksRUFBRSxJQUFJLEVBQUUsb0JBQW9CLEVBQUUsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDO1lBQ3pELGdCQUFnQixDQUFDLEtBQUssQ0FDcEIsSUFBSSxhQUFhLFdBQVcsWUFBWSxDQUFDLElBQUksQ0FBQyxvQkFBb0IsQ0FBQyxNQUFNLGdCQUFnQixFQUN6RixFQUFFLE1BQU0sRUFBRSxRQUFRLEVBQUUsQ0FDckIsQ0FBQztZQUNGLE9BQU8sWUFBWSxDQUFDLElBQUksQ0FBQyxvQkFBb0IsQ0FBQztRQUNoRCxDQUFDO2FBQU0sQ0FBQztZQUNOLGdCQUFnQixDQUFDLElBQUksQ0FBQyxJQUFJLGFBQWEsMEJBQTBCLEVBQUU7Z0JBQ2pFLE1BQU07Z0JBQ04sUUFBUTthQUNULENBQUMsQ0FBQztZQUNILE9BQU8sU0FBUyxDQUFDLENBQUMsdUJBQXVCO1FBQzNDLENBQUM7SUFDSCxDQUFDO0lBQUMsT0FBTyxDQUFNLEVBQUUsQ0FBQztRQUNoQixnQkFBZ0IsQ0FBQyxLQUFLLENBQ3BCLElBQUksYUFBYSx3REFBd0QsRUFDekUsRUFBRSxNQUFNLEVBQUUsUUFBUSxFQUFFLEtBQUssRUFBRSxDQUFDLENBQUMsT0FBTyxFQUFFLEtBQUssRUFBRSxDQUFDLENBQUMsS0FBSyxFQUFFLE9BQU8sRUFBRSxDQUFDLEVBQUUsQ0FDbkUsQ0FBQztRQUNGLE1BQU0sQ0FBQyxDQUFDO0lBQ1YsQ0FBQztBQUNILENBQUMsQ0FBQztBQWpGVyxRQUFBLG9DQUFvQyx3Q0FpRi9DO0FBRUssTUFBTSxlQUFlLEdBQUcsS0FBSyxFQUFFLEtBQWEsRUFBRSxFQUFFO0lBQ3JELE1BQU0sYUFBYSxHQUFHLGlCQUFpQixDQUFDO0lBQ3hDLElBQUksQ0FBQztRQUNILE1BQU0sR0FBRyxHQUFHLDBCQUFjLENBQUM7UUFDM0IsTUFBTSxNQUFNLEdBQUc7WUFDYixPQUFPLEVBQUU7Z0JBQ1AsYUFBYSxFQUFFLFVBQVUsS0FBSyxFQUFFO2dCQUNoQyxjQUFjLEVBQUUsa0JBQWtCO2dCQUNsQyxNQUFNLEVBQUUsa0JBQWtCO2FBQzNCO1lBQ0QsWUFBWSxFQUFFLE1BQWdCLEVBQUUsbUJBQW1CO1NBQ3BELENBQUM7UUFFRixNQUFNLElBQUksR0FBRyxDQUFDLE1BQU0sWUFBWSxDQUM5QixLQUFLLEVBQ0wsR0FBRyxFQUNILE1BQU0sRUFDTixhQUFhLENBQ2QsQ0FBc0IsQ0FBQztRQUN4QixnQkFBZ0IsQ0FBQyxLQUFLLENBQ3BCLElBQUksYUFBYSx1Q0FBdUMsRUFDeEQ7WUFDRSxtQkFBbUIsRUFBRSxNQUFNLENBQUMsSUFBSSxDQUFDLElBQUksQ0FBQyxRQUFRLElBQUksRUFBRSxDQUFDLENBQUMsTUFBTTtZQUM1RCxnQkFBZ0IsRUFBRSxNQUFNLENBQUMsSUFBSSxDQUFDLElBQUksQ0FBQyxLQUFLLElBQUksRUFBRSxDQUFDLENBQUMsTUFBTTtTQUN2RCxDQUNGLENBQUM7UUFDRixPQUFPLElBQUksQ0FBQztJQUNkLENBQUM7SUFBQyxPQUFPLENBQU0sRUFBRSxDQUFDO1FBQ2hCLGdCQUFnQixDQUFDLEtBQUssQ0FBQyxJQUFJLGFBQWEsZ0NBQWdDLEVBQUU7WUFDeEUsS0FBSyxFQUFFLENBQUMsQ0FBQyxPQUFPO1lBQ2hCLEtBQUssRUFBRSxDQUFDLENBQUMsS0FBSztZQUNkLE9BQU8sRUFBRSxDQUFDO1NBQ1gsQ0FBQyxDQUFDO1FBQ0gsTUFBTSxDQUFDLENBQUM7SUFDVixDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBbkNXLFFBQUEsZUFBZSxtQkFtQzFCO0FBRUssTUFBTSx1QkFBdUIsR0FBRyxLQUFLLEVBQzFDLHFCQUE2QixFQUM3QixNQUFjLEVBQ2QsR0FBbUIsRUFDbkIsRUFBRTtJQUNGLE1BQU0sYUFBYSxHQUFHLHlCQUF5QixDQUFDO0lBQ2hELElBQUksQ0FBQztRQUNILGdCQUFnQixDQUFDLElBQUksQ0FBQyxJQUFJLGFBQWEsV0FBVyxFQUFFO1lBQ2xELHFCQUFxQjtZQUNyQixNQUFNO1NBQ1AsQ0FBQyxDQUFDO1FBQ0gsSUFBSSxDQUFDLHFCQUFxQixFQUFFLENBQUM7WUFDM0IsZ0JBQWdCLENBQUMsSUFBSSxDQUNuQixJQUFJLGFBQWEsc0NBQXNDLENBQ3hELENBQUM7WUFDRixPQUFPO1FBQ1QsQ0FBQztRQUVELElBQUksQ0FBQyxNQUFNLEVBQUUsQ0FBQztZQUNaLGdCQUFnQixDQUFDLElBQUksQ0FBQyxJQUFJLGFBQWEsdUJBQXVCLENBQUMsQ0FBQztZQUNoRSxPQUFPO1FBQ1QsQ0FBQztRQUNELE1BQU0sWUFBWSxHQUFHLEdBQUcsQ0FBQyxPQUFPLEVBQUUscUJBQXFCLEVBQUUsQ0FBQyxDQUFDLG9DQUFvQztRQUMvRixNQUFNLFlBQVksR0FBRyxZQUFZLENBQUMsQ0FBQyxvR0FBb0c7UUFFdkksSUFBSSxDQUFDLFlBQVksRUFBRSxDQUFDO1lBQ2xCLGdCQUFnQixDQUFDLElBQUksQ0FDbkIsSUFBSSxhQUFhLHFDQUFxQyxDQUN2RCxDQUFDO1lBQ0YsT0FBTztRQUNULENBQUM7UUFFRCxNQUFNLElBQUksR0FBRztZQUNYLHFCQUFxQjtZQUNyQixNQUFNO1lBQ04sYUFBYSxFQUFFLElBQUk7U0FDcEIsQ0FBQztRQUVGLE1BQU0sR0FBRyxHQUFHLCtCQUFtQixDQUFDO1FBRWhDLE1BQU0sT0FBTyxHQUFHO1lBQ2QsSUFBSSxFQUFFLElBQUk7WUFDVixPQUFPLEVBQUU7Z0JBQ1AsYUFBYSxFQUFFLFVBQVUsWUFBWSxFQUFFLEVBQUUsd0JBQXdCO2dCQUNqRSxjQUFjLEVBQUUsa0JBQWtCO2FBQ25DO1lBQ0QsWUFBWSxFQUFFLE1BQWdCO1NBQy9CLENBQUM7UUFFRixNQUFNLE9BQU8sR0FBRyxNQUFNLFlBQVksQ0FBQyxNQUFNLEVBQUUsR0FBRyxFQUFFLE9BQU8sRUFBRSxhQUFhLENBQUMsQ0FBQztRQUV4RSxnQkFBZ0IsQ0FBQyxJQUFJLENBQ25CLElBQUksYUFBYSw4Q0FBOEMsRUFDL0QsRUFBRSxxQkFBcUIsRUFBRSxNQUFNLEVBQUUsT0FBTyxFQUFFLENBQzNDLENBQUM7SUFDSixDQUFDO0lBQUMsT0FBTyxDQUFNLEVBQUUsQ0FBQztRQUNoQixnQkFBZ0IsQ0FBQyxLQUFLLENBQ3BCLElBQUksYUFBYSx5Q0FBeUMsRUFDMUQ7WUFDRSxxQkFBcUI7WUFDckIsTUFBTTtZQUNOLEtBQUssRUFBRSxDQUFDLENBQUMsT0FBTztZQUNoQixJQUFJLEVBQUUsQ0FBQyxDQUFDLElBQUk7WUFDWixZQUFZLEVBQUUsQ0FBQyxFQUFFLFFBQVEsRUFBRSxJQUFJO1lBQy9CLEtBQUssRUFBRSxDQUFDLENBQUMsS0FBSztTQUNmLENBQ0YsQ0FBQztRQUNGLE1BQU0sQ0FBQyxDQUFDO0lBQ1YsQ0FBQztBQUNILENBQUMsQ0FBQztBQXJFVyxRQUFBLHVCQUF1QiwyQkFxRWxDO0FBQ0ssTUFBTSx1QkFBdUIsR0FBRyxLQUFLLEVBQzFDLEVBQVUsRUFDVixPQUFpQixFQUNqQixLQUFjLEVBQ2QsWUFBcUIsRUFDckIsU0FBa0IsRUFDbEIsV0FBcUIsRUFDckIsTUFBb0IsRUFDcEIsU0FBa0IsRUFDbEIsU0FBa0IsRUFDbEIsVUFBcUQsRUFDckQsRUFBRTtJQUNGLE1BQU0sYUFBYSxHQUFHLHlCQUF5QixDQUFDLENBQUMsaUJBQWlCO0lBQ2xFLElBQUksQ0FBQztRQUNILHlFQUF5RTtRQUN6RSxNQUFNLEtBQUssR0FBRzs7a0JBRUEsT0FBTyxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsb0JBQW9CLENBQUMsQ0FBQyxDQUFDLEVBQUU7a0JBQ2pELFNBQVMsS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLDBCQUEwQixDQUFDLENBQUMsQ0FBQyxFQUFFO2tCQUN6RCxZQUFZLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyx3QkFBd0IsQ0FBQyxDQUFDLENBQUMsRUFBRTtrQkFDMUQsS0FBSyxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsaUJBQWlCLENBQUMsQ0FBQyxDQUFDLEVBQUU7a0JBQzVDLFdBQVcsS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLHdCQUF3QixDQUFDLENBQUMsQ0FBQyxFQUFFO2tCQUN6RCxNQUFNLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyxpQkFBaUIsQ0FBQyxDQUFDLENBQUMsRUFBRTtrQkFDN0MsU0FBUyxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMscUJBQXFCLENBQUMsQ0FBQyxDQUFDLEVBQUU7a0JBQ3BELFNBQVMsS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLHFCQUFxQixDQUFDLENBQUMsQ0FBQyxFQUFFO2tCQUNwRCxVQUFVLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyxzQkFBc0IsQ0FBQyxDQUFDLENBQUMsRUFBRTs7O3NCQUdsRCxPQUFPLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyxvQkFBb0IsQ0FBQyxDQUFDLENBQUMsRUFBRTtzQkFDakQsU0FBUyxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsd0JBQXdCLENBQUMsQ0FBQyxDQUFDLEVBQUU7c0JBQ3ZELFlBQVksS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLDhCQUE4QixDQUFDLENBQUMsQ0FBQyxFQUFFO3NCQUNoRSxLQUFLLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDLENBQUMsRUFBRTtzQkFDM0MsV0FBVyxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsNEJBQTRCLENBQUMsQ0FBQyxDQUFDLEVBQUU7c0JBQzdELE1BQU0sS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLGtCQUFrQixDQUFDLENBQUMsQ0FBQyxFQUFFO3NCQUM5QyxTQUFTLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyx3QkFBd0IsQ0FBQyxDQUFDLENBQUMsRUFBRTtzQkFDdkQsU0FBUyxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsd0JBQXdCLENBQUMsQ0FBQyxDQUFDLEVBQUU7c0JBQ3ZELFVBQVUsS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLDBCQUEwQixDQUFDLENBQUMsQ0FBQyxFQUFFOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztTQTBCdkUsQ0FBQztRQUVOLElBQUksU0FBUyxHQUFRO1lBQ25CLEVBQUU7WUFDRixTQUFTLEVBQUUsSUFBQSxrQkFBSyxHQUFFLENBQUMsTUFBTSxFQUFFO1NBQzVCLENBQUM7UUFFRixJQUFJLE9BQU8sS0FBSyxTQUFTLEVBQUUsQ0FBQztZQUMxQixTQUFTLENBQUMsT0FBTyxHQUFHLE9BQU8sQ0FBQztRQUM5QixDQUFDO1FBQ0QsSUFBSSxTQUFTLEtBQUssU0FBUyxFQUFFLENBQUM7WUFDNUIsU0FBUyxDQUFDLFNBQVM7Z0JBQ2pCLFNBQVMsS0FBSyxJQUFJLENBQUMsQ0FBQyxDQUFDLElBQUksQ0FBQyxDQUFDLENBQUMsSUFBQSxrQkFBSyxFQUFDLFNBQVMsQ0FBQyxDQUFDLE1BQU0sRUFBRSxDQUFDO1FBQzFELENBQUM7UUFDRCxJQUFJLFlBQVksS0FBSyxTQUFTLEVBQUUsQ0FBQztZQUMvQixTQUFTLENBQUMsWUFBWSxHQUFHLFlBQVksQ0FBQztRQUN4QyxDQUFDO1FBQ0QsSUFBSSxLQUFLLEtBQUssU0FBUyxFQUFFLENBQUM7WUFDeEIsU0FBUyxDQUFDLEtBQUssR0FBRyxLQUFLLENBQUM7UUFDMUIsQ0FBQztRQUNELElBQUksV0FBVyxLQUFLLFNBQVMsRUFBRSxDQUFDO1lBQzlCLFNBQVMsQ0FBQyxXQUFXLEdBQUcsV0FBVyxDQUFDO1FBQ3RDLENBQUM7UUFDRCxJQUFJLE1BQU0sS0FBSyxTQUFTLEVBQUUsQ0FBQztZQUN6QixTQUFTLENBQUMsTUFBTSxHQUFHLE1BQU0sQ0FBQztRQUM1QixDQUFDO1FBQ0QsSUFBSSxTQUFTLEtBQUssU0FBUyxFQUFFLENBQUM7WUFDNUIsU0FBUyxDQUFDLFNBQVMsR0FBRyxTQUFTLENBQUM7UUFDbEMsQ0FBQztRQUNELElBQUksU0FBUyxLQUFLLFNBQVMsRUFBRSxDQUFDO1lBQzVCLFNBQVMsQ0FBQyxTQUFTLEdBQUcsU0FBUyxDQUFDO1FBQ2xDLENBQUM7UUFDRCxJQUFJLFVBQVUsS0FBSyxTQUFTLEVBQUUsQ0FBQztZQUM3QixTQUFTLENBQUMsVUFBVSxHQUFHLFVBQVUsQ0FBQztRQUNwQyxDQUFDO1FBRUQsTUFBTSxPQUFPLEdBQUc7WUFDZCxJQUFJLEVBQUUsRUFBRSxhQUFhLEVBQUUsS0FBSyxFQUFFLFNBQVMsRUFBRTtZQUN6QyxPQUFPLEVBQUU7Z0JBQ1AsNkJBQTZCLEVBQUUsbUNBQXVCO2dCQUN0RCxjQUFjLEVBQUUsa0JBQWtCO2dCQUNsQyxxQkFBcUIsRUFBRSxPQUFPO2FBQy9CO1NBQ0YsQ0FBQztRQUVGLE1BQU0sWUFBWSxHQUFHLENBQUMsTUFBTSxZQUFZLENBQ3RDLE1BQU0sRUFDTixnQ0FBb0IsRUFDcEIsT0FBTyxFQUNQLGFBQWEsQ0FDZCxDQUVBLENBQUM7UUFFRixnQkFBZ0IsQ0FBQyxJQUFJLENBQ25CLElBQUksYUFBYSxxREFBcUQsRUFDdEU7WUFDRSxhQUFhLEVBQ1gsWUFBWSxFQUFFLElBQUksRUFBRSxpQ0FBaUMsRUFBRSxFQUFFO1lBQzNELE9BQU87U0FDUixDQUNGLENBQUM7UUFDRixPQUFPLFlBQVksRUFBRSxJQUFJLEVBQUUsaUNBQWlDLENBQUM7SUFDL0QsQ0FBQztJQUFDLE9BQU8sQ0FBTSxFQUFFLENBQUM7UUFDaEIsZ0JBQWdCLENBQUMsS0FBSyxDQUNwQixJQUFJLGFBQWEsaURBQWlELEVBQ2xFLEVBQUUsRUFBRSxFQUFFLEtBQUssRUFBRSxDQUFDLENBQUMsT0FBTyxFQUFFLEtBQUssRUFBRSxDQUFDLENBQUMsS0FBSyxFQUFFLE9BQU8sRUFBRSxDQUFDLEVBQUUsQ0FDckQsQ0FBQztRQUNGLE1BQU0sQ0FBQyxDQUFDO0lBQ1YsQ0FBQztBQUNILENBQUMsQ0FBQztBQXBJVyxRQUFBLHVCQUF1QiwyQkFvSWxDO0FBRUssTUFBTSxlQUFlLEdBQUcsS0FBSyxFQUNsQyxPQUFtQyxFQUNuQyxVQUFvRCxFQUNwRCxFQUFFO0lBQ0YsSUFBSSxhQUFhLEdBQUcsRUFBRSxDQUFDO0lBQ3ZCLE1BQU0sYUFBYSxHQUFHLG1CQUFtQixDQUFDO0lBQzFDLElBQUksQ0FBQztRQUNILGdCQUFnQixDQUFDLElBQUksQ0FDbkIsSUFBSSxhQUFhLHVDQUF1QyxFQUN4RCxFQUFFLE1BQU0sRUFBRSxRQUFRLEVBQUUsVUFBVSxFQUFFLENBQ2pDLENBQUM7UUFDRixNQUFNLFdBQVcsR0FBRyxNQUFNLElBQUEsK0NBQXVDLEVBQy9ELE1BQU0sRUFDTixRQUFRLENBQ1QsQ0FBQztRQUVGLElBQUksQ0FBQyxXQUFXLEVBQUUsQ0FBQztZQUNqQixnQkFBZ0IsQ0FBQyxJQUFJLENBQ25CLElBQUksYUFBYSxrQ0FBa0MsRUFDbkQsRUFBRSxNQUFNLEVBQUUsUUFBUSxFQUFFLENBQ3JCLENBQUM7WUFDRixNQUFNLElBQUksS0FBSyxDQUFDLG9DQUFvQyxDQUFDLENBQUM7UUFDeEQsQ0FBQztRQUNELGFBQWEsR0FBRyxXQUFXLENBQUMsRUFBRSxDQUFDLENBQUMscUVBQXFFO1FBRXJHLElBQUksQ0FBQyxXQUFXLENBQUMsWUFBWSxFQUFFLENBQUM7WUFDOUIsZ0JBQWdCLENBQUMsSUFBSSxDQUNuQixJQUFJLGFBQWEsMkNBQTJDLEVBQzVELEVBQUUsTUFBTSxFQUFFLFFBQVEsRUFBRSxhQUFhLEVBQUUsQ0FDcEMsQ0FBQztZQUNGLE1BQU0sSUFBSSxLQUFLLENBQUMsc0RBQXNELENBQUMsQ0FBQztRQUMxRSxDQUFDO1FBRUQsZ0JBQWdCLENBQUMsS0FBSyxDQUNwQixJQUFJLGFBQWEsK0NBQStDLEVBQ2hFO1lBQ0UsTUFBTTtZQUNOLFFBQVE7WUFDUixhQUFhO1lBQ2IsU0FBUyxFQUFFLFdBQVcsQ0FBQyxTQUFTO1lBQ2hDLFdBQVcsRUFBRSxDQUFDLENBQUMsV0FBVyxDQUFDLEtBQUs7U0FDakMsQ0FDRixDQUFDO1FBRUYsSUFBSSxJQUFBLGtCQUFLLEdBQUUsQ0FBQyxPQUFPLENBQUMsSUFBQSxrQkFBSyxFQUFDLFdBQVcsQ0FBQyxTQUFTLENBQUMsQ0FBQyxJQUFJLENBQUMsV0FBVyxDQUFDLEtBQUssRUFBRSxDQUFDO1lBQ3hFLGdCQUFnQixDQUFDLElBQUksQ0FDbkIsSUFBSSxhQUFhLGlEQUFpRCxFQUNsRSxFQUFFLE1BQU0sRUFBRSxRQUFRLEVBQUUsYUFBYSxFQUFFLENBQ3BDLENBQUM7WUFDRixNQUFNLGVBQWUsR0FBRyxNQUFNLElBQUEsMEJBQWtCLEVBQzlDLFdBQVcsQ0FBQyxZQUFZLEVBQ3hCLFVBQVUsQ0FDWCxDQUFDO1lBRUYsSUFBSSxlQUFlLElBQUksZUFBZSxDQUFDLFlBQVksRUFBRSxDQUFDO2dCQUNwRCxnQkFBZ0IsQ0FBQyxJQUFJLENBQ25CLElBQUksYUFBYSxtREFBbUQsRUFDcEUsRUFBRSxNQUFNLEVBQUUsUUFBUSxFQUFFLGFBQWEsRUFBRSxDQUNwQyxDQUFDO2dCQUNGLE1BQU0sSUFBQSw0Q0FBb0MsRUFDeEMsYUFBYSxFQUNiLGVBQWUsQ0FBQyxZQUFZLEVBQzVCLGVBQWUsQ0FBQyxVQUFVLENBQzNCLENBQUM7Z0JBQ0YsT0FBTyxlQUFlLENBQUMsWUFBWSxDQUFDO1lBQ3RDLENBQUM7aUJBQU0sQ0FBQztnQkFDTixnQkFBZ0IsQ0FBQyxJQUFJLENBQ25CLElBQUksYUFBYSxxREFBcUQsRUFDdEUsRUFBRSxNQUFNLEVBQUUsUUFBUSxFQUFFLGFBQWEsRUFBRSxDQUNwQyxDQUFDO2dCQUNGLDBFQUEwRTtnQkFDMUUsTUFBTSxJQUFJLEtBQUssQ0FBQyxpREFBaUQsQ0FBQyxDQUFDO1lBQ3JFLENBQUM7UUFDSCxDQUFDO1FBQ0QsZ0JBQWdCLENBQUMsSUFBSSxDQUFDLElBQUksYUFBYSw0QkFBNEIsRUFBRTtZQUNuRSxNQUFNO1lBQ04sUUFBUTtZQUNSLGFBQWE7U0FDZCxDQUFDLENBQUM7UUFDSCxPQUFPLFdBQVcsQ0FBQyxLQUFLLENBQUM7SUFDM0IsQ0FBQztJQUFDLE9BQU8sQ0FBTSxFQUFFLENBQUM7UUFDaEIsZ0JBQWdCLENBQUMsS0FBSyxDQUNwQixJQUFJLGFBQWEsbUNBQW1DLEVBQ3BEO1lBQ0UsTUFBTTtZQUNOLFFBQVE7WUFDUixVQUFVO1lBQ1Ysb0JBQW9CLEVBQUUsYUFBYTtZQUNuQyxLQUFLLEVBQUUsQ0FBQyxDQUFDLE9BQU87WUFDaEIsS0FBSyxFQUFFLENBQUMsQ0FBQyxLQUFLO1lBQ2QsT0FBTyxFQUFFLENBQUM7U0FDWCxDQUNGLENBQUM7UUFDRixJQUFJLGFBQWEsRUFBRSxDQUFDO1lBQ2xCLG1EQUFtRDtZQUNuRCxJQUFJLENBQUM7Z0JBQ0gsZ0JBQWdCLENBQUMsSUFBSSxDQUNuQixJQUFJLGFBQWEsbURBQW1ELEVBQ3BFLEVBQUUsYUFBYSxFQUFFLENBQ2xCLENBQUM7Z0JBQ0YsTUFBTSxJQUFBLDRDQUFvQyxFQUN4QyxhQUFhLEVBQ2IsSUFBSSxFQUNKLElBQUksRUFDSixLQUFLLENBQ04sQ0FBQztZQUNKLENBQUM7WUFBQyxPQUFPLFlBQWlCLEVBQUUsQ0FBQztnQkFDM0IsZ0JBQWdCLENBQUMsS0FBSyxDQUNwQixJQUFJLGFBQWEsOENBQThDLEVBQy9EO29CQUNFLGFBQWE7b0JBQ2IsWUFBWSxFQUFFLFlBQVksQ0FBQyxPQUFPO29CQUNsQyxLQUFLLEVBQUUsWUFBWSxDQUFDLEtBQUs7aUJBQzFCLENBQ0YsQ0FBQztZQUNKLENBQUM7UUFDSCxDQUFDO1FBQ0QsTUFBTSxDQUFDLENBQUMsQ0FBQywyQ0FBMkM7SUFDdEQsQ0FBQztBQUNILENBQUMsQ0FBQztBQXZIVyxRQUFBLGVBQWUsbUJBdUgxQjtBQUVLLE1BQU0saUJBQWlCLEdBQUcsQ0FDL0IsY0FBc0IsRUFDdEIscUJBQThCLEVBQzlCLEVBQUU7SUFDRixNQUFNLFFBQVEsR0FBRyxNQUFNLENBQUMsSUFBSSxDQUFDLHlCQUFhLEVBQUUsUUFBUSxDQUFDLENBQUM7SUFDdEQsTUFBTSxVQUFVLEdBQUcsTUFBTSxDQUFDLElBQUksQ0FBQywyQkFBZSxFQUFFLFFBQVEsQ0FBQyxDQUFDO0lBRTFELE1BQU0sR0FBRyxHQUFHLGdCQUFNLENBQUMsVUFBVSxDQUMzQix1QkFBcUIsRUFDckIsVUFBVSxFQUNWLEtBQUssRUFDTCxFQUFFLEVBQ0YsUUFBUSxDQUNULENBQUM7SUFFRixNQUFNLGFBQWEsR0FBRyxnQkFBTSxDQUFDLGdCQUFnQixDQUFDLGFBQWEsRUFBRSxHQUFHLEVBQUUsUUFBUSxDQUFDLENBQUM7SUFDNUUsSUFBSSxjQUFjLEdBQUcsYUFBYSxDQUFDLE1BQU0sQ0FBQyxjQUFjLEVBQUUsUUFBUSxFQUFFLE1BQU0sQ0FBQyxDQUFDO0lBQzVFLGNBQWMsSUFBSSxhQUFhLENBQUMsS0FBSyxDQUFDLE1BQU0sQ0FBQyxDQUFDO0lBRTlDLElBQUkscUJBQXFCLEVBQUUsQ0FBQztRQUMxQixNQUFNLG9CQUFvQixHQUFHLGdCQUFNLENBQUMsZ0JBQWdCLENBQ2xELGFBQWEsRUFDYixHQUFHLEVBQ0gsUUFBUSxDQUNULENBQUM7UUFDRixJQUFJLHFCQUFxQixHQUFHLG9CQUFvQixDQUFDLE1BQU0sQ0FDckQscUJBQXFCLEVBQ3JCLFFBQVEsRUFDUixNQUFNLENBQ1AsQ0FBQztRQUNGLHFCQUFxQixJQUFJLG9CQUFvQixDQUFDLEtBQUssQ0FBQyxNQUFNLENBQUMsQ0FBQztRQUU1RCxPQUFPO1lBQ0wsS0FBSyxFQUFFLGNBQWM7WUFDckIsWUFBWSxFQUFFLHFCQUFxQjtTQUNwQyxDQUFDO0lBQ0osQ0FBQztJQUVELE9BQU87UUFDTCxLQUFLLEVBQUUsY0FBYztLQUN0QixDQUFDO0FBQ0osQ0FBQyxDQUFDO0FBekNXLFFBQUEsaUJBQWlCLHFCQXlDNUI7QUFFSyxNQUFNLGlCQUFpQixHQUFHLENBQUMsS0FBYSxFQUFFLFlBQXFCLEVBQUUsRUFBRTtJQUN4RSxNQUFNLFFBQVEsR0FBRyxNQUFNLENBQUMsSUFBSSxDQUFDLHlCQUFhLEVBQUUsUUFBUSxDQUFDLENBQUM7SUFDdEQsTUFBTSxVQUFVLEdBQUcsTUFBTSxDQUFDLElBQUksQ0FBQywyQkFBZSxFQUFFLFFBQVEsQ0FBQyxDQUFDO0lBRTFELE1BQU0sR0FBRyxHQUFHLGdCQUFNLENBQUMsVUFBVSxDQUMzQix1QkFBcUIsRUFDckIsVUFBVSxFQUNWLEtBQUssRUFDTCxFQUFFLEVBQ0YsUUFBUSxDQUNULENBQUM7SUFDRixNQUFNLFdBQVcsR0FBRyxnQkFBTSxDQUFDLGNBQWMsQ0FBQyxhQUFhLEVBQUUsR0FBRyxFQUFFLFFBQVEsQ0FBQyxDQUFDO0lBQ3hFLElBQUksY0FBYyxHQUFHLFdBQVcsQ0FBQyxNQUFNLENBQUMsS0FBSyxFQUFFLE1BQU0sRUFBRSxRQUFRLENBQUMsQ0FBQztJQUNqRSxjQUFjLElBQUksV0FBVyxDQUFDLEtBQUssQ0FBQyxRQUFRLENBQUMsQ0FBQztJQUU5QyxJQUFJLHFCQUFxQixHQUFHLEVBQUUsQ0FBQztJQUUvQixJQUFJLFlBQVksRUFBRSxDQUFDO1FBQ2pCLE1BQU0sa0JBQWtCLEdBQUcsZ0JBQU0sQ0FBQyxjQUFjLENBQzlDLGFBQWEsRUFDYixHQUFHLEVBQ0gsUUFBUSxDQUNULENBQUM7UUFDRixxQkFBcUIsR0FBRyxrQkFBa0IsQ0FBQyxNQUFNLENBQy9DLFlBQVksRUFDWixNQUFNLEVBQ04sUUFBUSxDQUNULENBQUM7UUFDRixxQkFBcUIsSUFBSSxrQkFBa0IsQ0FBQyxLQUFLLENBQUMsUUFBUSxDQUFDLENBQUM7SUFDOUQsQ0FBQztJQUVELElBQUkscUJBQXFCLEVBQUUsQ0FBQztRQUMxQixPQUFPO1lBQ0wsY0FBYztZQUNkLHFCQUFxQjtTQUN0QixDQUFDO0lBQ0osQ0FBQztTQUFNLENBQUM7UUFDTixPQUFPLEVBQUUsY0FBYyxFQUFFLENBQUM7SUFDNUIsQ0FBQztBQUNILENBQUMsQ0FBQztBQXZDVyxRQUFBLGlCQUFpQixxQkF1QzVCO0FBRUYsMEdBQTBHO0FBQzFHLHFEQUFxRDtBQUNyRCxvR0FBb0c7QUFDcEcseUZBQXlGO0FBQ3pGLDBFQUEwRTtBQUMxRSwwRkFBMEY7QUFDbkYsTUFBTSxxQkFBcUIsR0FBRyxLQUFLLEVBQ3hDLEVBQVUsRUFDVixZQUFvQixFQUNwQixRQUFnQixFQUNoQixLQUFhLEVBQ2IsS0FBb0IsRUFDcEIsU0FBd0IsRUFDeEIsWUFBcUIsRUFDckIsZ0JBQXlCLEVBQ3pCLGVBQXdCLEVBQ3hCLFlBQXFCLEVBQUUsT0FBTztBQUM5QixXQUFvQixFQUFFLGtCQUFrQjtBQUN4QyxPQUFpQixFQUNqQixFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsa0RBQWtEO1FBQ2xELEVBQUU7UUFDRixNQUFNLGFBQWEsR0FBRywrQkFBK0IsQ0FBQztRQUN0RCxNQUFNLEtBQUssR0FBRzs7Ozs7O3NCQU1JLEtBQUssS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLGtCQUFrQixDQUFDLENBQUMsQ0FBQyxFQUFFO3NCQUM3QyxZQUFZLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyx5QkFBeUIsQ0FBQyxDQUFDLENBQUMsRUFBRTtzQkFDM0QsU0FBUyxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsMkJBQTJCLENBQUMsQ0FBQyxDQUFDLEVBQUU7c0JBQzFELE9BQU8sS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLHFCQUFxQixDQUFDLENBQUMsQ0FBQyxFQUFFO3NCQUNsRCxnQkFBZ0IsS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLDZCQUE2QixDQUFDLENBQUMsQ0FBQyxFQUFFO3NCQUNuRSxlQUFlLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyw0QkFBNEIsQ0FBQyxDQUFDLENBQUMsRUFBRTtzQkFDakUsWUFBWSxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMseUJBQXlCLENBQUMsQ0FBQyxDQUFDLEVBQUU7c0JBQzNELFdBQVcsS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLHdCQUF3QixDQUFDLENBQUMsQ0FBQyxFQUFFOzs7Ozs7c0JBTXpELEtBQUssS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLGdCQUFnQixDQUFDLENBQUMsQ0FBQyxFQUFFO3NCQUMzQyxTQUFTLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyx5QkFBeUIsQ0FBQyxDQUFDLENBQUMsRUFBRTtzQkFDeEQsWUFBWSxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsOEJBQThCLENBQUMsQ0FBQyxDQUFDLEVBQUU7c0JBQ2hFLGdCQUFnQixLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsc0NBQXNDLENBQUMsQ0FBQyxDQUFDLEVBQUU7c0JBQzVFLGVBQWUsS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLG9DQUFvQyxDQUFDLENBQUMsQ0FBQyxFQUFFO3NCQUN6RSxZQUFZLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyw4QkFBOEIsQ0FBQyxDQUFDLENBQUMsRUFBRTtzQkFDaEUsV0FBVyxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsNEJBQTRCLENBQUMsQ0FBQyxDQUFDLEVBQUU7c0JBQzdELE9BQU8sS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLHFCQUFxQixDQUFDLENBQUMsQ0FBQyxFQUFFOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O1NBK0IvRCxDQUFDO1FBRU4sSUFBSSxlQUFlLEdBQUcsSUFBSSxDQUFDO1FBRTNCLElBQUksS0FBSyxFQUFFLENBQUM7WUFDVixlQUFlLEdBQUcsSUFBQSx5QkFBaUIsRUFBQyxLQUFLLEVBQUUsWUFBWSxDQUFDLENBQUM7UUFDM0QsQ0FBQztRQUVELE1BQU0sU0FBUyxHQUFHO1lBQ2hCLEVBQUU7WUFDRixZQUFZO1lBQ1osUUFBUTtZQUNSLEtBQUs7WUFDTCxLQUFLLEVBQUUsZUFBZSxFQUFFLGNBQWM7WUFDdEMsU0FBUyxFQUFFLFNBQVM7Z0JBQ2xCLENBQUMsQ0FBQyxJQUFBLGtCQUFLLEdBQUUsQ0FBQyxHQUFHLENBQUMsU0FBUyxFQUFFLFNBQVMsQ0FBQyxDQUFDLFdBQVcsRUFBRTtnQkFDakQsQ0FBQyxDQUFDLElBQUk7WUFDUixZQUFZLEVBQ1YsWUFBWSxLQUFLLFNBQVM7Z0JBQ3hCLENBQUMsQ0FBQyxTQUFTO2dCQUNYLENBQUMsQ0FBQyxlQUFlLEVBQUUscUJBQXFCO1lBQzVDLGdCQUFnQjtZQUNoQixlQUFlO1lBQ2YsWUFBWTtZQUNaLFdBQVc7WUFDWCxPQUFPO1NBQ1IsQ0FBQztRQUVGLE1BQU0sT0FBTyxHQUFHO1lBQ2QsSUFBSSxFQUFFLEVBQUUsYUFBYSxFQUFFLEtBQUssRUFBRSxTQUFTLEVBQUU7WUFDekMsT0FBTyxFQUFFO2dCQUNQLDZCQUE2QixFQUFFLG1DQUF1QjtnQkFDdEQsY0FBYyxFQUFFLGtCQUFrQjtnQkFDbEMscUJBQXFCLEVBQUUsT0FBTzthQUMvQjtTQUNGLENBQUM7UUFFRixNQUFNLFlBQVksQ0FBQyxNQUFNLEVBQUUsZ0NBQW9CLEVBQUUsT0FBTyxFQUFFLGFBQWEsQ0FBQyxDQUFDO1FBRXpFLGdCQUFnQixDQUFDLElBQUksQ0FDbkIsSUFBSSxhQUFhLDBDQUEwQyxFQUMzRCxFQUFFLEVBQUUsRUFBRSxZQUFZLEVBQUUsUUFBUSxFQUFFLE9BQU8sRUFBRSxDQUN4QyxDQUFDO0lBQ0osQ0FBQztJQUFDLE9BQU8sQ0FBTSxFQUFFLENBQUM7UUFDaEIsZ0JBQWdCLENBQUMsS0FBSyxDQUNwQixJQUFJLGFBQWEsc0NBQXNDLEVBQ3ZEO1lBQ0UsRUFBRTtZQUNGLFlBQVk7WUFDWixRQUFRO1lBQ1IsS0FBSyxFQUFFLENBQUMsQ0FBQyxPQUFPO1lBQ2hCLEtBQUssRUFBRSxDQUFDLENBQUMsS0FBSztZQUNkLE9BQU8sRUFBRSxDQUFDO1NBQ1gsQ0FDRixDQUFDO1FBQ0YsTUFBTSxDQUFDLENBQUMsQ0FBQywwQ0FBMEM7SUFDckQsQ0FBQztBQUNILENBQUMsQ0FBQztBQXBJVyxRQUFBLHFCQUFxQix5QkFvSWhDO0FBRUssTUFBTSxtQ0FBbUMsR0FBRyxLQUFLLEVBQ3RELE1BQWMsRUFDZCxJQUFZLEVBQ1osRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILE1BQU0sYUFBYSxHQUFHLHdCQUF3QixDQUFDO1FBQy9DLE1BQU0sS0FBSyxHQUFHOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztLQWdDYixDQUFDO1FBQ0YsTUFBTSxTQUFTLEdBQUc7WUFDaEIsTUFBTTtZQUNOLElBQUk7U0FDTCxDQUFDO1FBRUYsTUFBTSxHQUFHLEdBQ1AsTUFBTSxhQUFHO2FBQ04sSUFBSSxDQUFDLGdDQUFvQixFQUFFO1lBQzFCLElBQUksRUFBRTtnQkFDSixhQUFhO2dCQUNiLEtBQUs7Z0JBQ0wsU0FBUzthQUNWO1lBQ0QsT0FBTyxFQUFFO2dCQUNQLDZCQUE2QixFQUFFLG1DQUF1QjtnQkFDdEQsY0FBYyxFQUFFLGtCQUFrQjtnQkFDbEMscUJBQXFCLEVBQUUsT0FBTzthQUMvQjtTQUNGLENBQUM7YUFDRCxJQUFJLEVBQUUsQ0FBQztRQUVaLHlEQUF5RDtRQUN6RCxJQUFJLEdBQUcsRUFBRSxJQUFJLEVBQUUsb0JBQW9CLEVBQUUsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDO1lBQ2hELGdCQUFnQixDQUFDLEtBQUssQ0FDcEIsdUVBQXVFLE1BQU0sV0FBVyxJQUFJLEdBQUcsRUFDL0YsRUFBRSxhQUFhLEVBQUUsR0FBRyxDQUFDLElBQUksQ0FBQyxvQkFBb0IsQ0FBQyxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FDdkQsQ0FBQztZQUNGLE9BQU8sR0FBRyxFQUFFLElBQUksRUFBRSxvQkFBb0IsRUFBRSxDQUFDLENBQUMsQ0FBQyxDQUFDO1FBQzlDLENBQUM7YUFBTSxDQUFDO1lBQ04sZ0JBQWdCLENBQUMsSUFBSSxDQUNuQiwwRUFBMEUsTUFBTSxXQUFXLElBQUksR0FBRyxDQUNuRyxDQUFDO1lBQ0YsT0FBTyxTQUFTLENBQUM7UUFDbkIsQ0FBQztJQUNILENBQUM7SUFBQyxPQUFPLENBQU0sRUFBRSxDQUFDO1FBQ2hCLGdCQUFnQixDQUFDLEtBQUssQ0FDcEIsbUZBQW1GLEVBQ25GLEVBQUUsTUFBTSxFQUFFLElBQUksRUFBRSxLQUFLLEVBQUUsQ0FBQyxDQUFDLE9BQU8sRUFBRSxLQUFLLEVBQUUsQ0FBQyxDQUFDLEtBQUssRUFBRSxPQUFPLEVBQUUsQ0FBQyxFQUFFLENBQy9ELENBQUM7UUFDRixrREFBa0Q7SUFDcEQsQ0FBQztBQUNILENBQUMsQ0FBQztBQWhGVyxRQUFBLG1DQUFtQyx1Q0FnRjlDO0FBRUY7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztHQWlDRztBQUVJLE1BQU0sZ0RBQWdELEdBQUcsS0FBSyxFQUNuRSxNQUFjLEVBQ2QsUUFBZ0IsRUFDaEIsVUFBb0QsRUFDcEQsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILE1BQU0sYUFBYSxHQUFHLCtDQUErQyxDQUFDO1FBRXRFLE1BQU0sS0FBSyxHQUFHOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztTQWdDVCxDQUFDO1FBRU4sTUFBTSxTQUFTLEdBQUc7WUFDaEIsTUFBTTtZQUNOLFFBQVE7WUFDUixVQUFVO1NBQ1gsQ0FBQztRQUVGLE1BQU0sR0FBRyxHQUNQLE1BQU0sYUFBRzthQUNOLElBQUksQ0FBQyxnQ0FBb0IsRUFBRTtZQUMxQixJQUFJLEVBQUU7Z0JBQ0osYUFBYTtnQkFDYixLQUFLO2dCQUNMLFNBQVM7YUFDVjtZQUNELE9BQU8sRUFBRTtnQkFDUCw2QkFBNkIsRUFBRSxtQ0FBdUI7Z0JBQ3RELGNBQWMsRUFBRSxrQkFBa0I7Z0JBQ2xDLHFCQUFxQixFQUFFLE9BQU87YUFDL0I7U0FDRixDQUFDO2FBQ0QsSUFBSSxFQUFFLENBQUM7UUFFWix5REFBeUQ7UUFDekQsSUFBSSxHQUFHLEVBQUUsSUFBSSxFQUFFLG9CQUFvQixFQUFFLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztZQUNoRCxnQkFBZ0IsQ0FBQyxLQUFLLENBQ3BCLDREQUE0RCxHQUFHLENBQUMsSUFBSSxDQUFDLG9CQUFvQixDQUFDLE1BQU0sZ0JBQWdCLEVBQ2hILEVBQUUsTUFBTSxFQUFFLFFBQVEsRUFBRSxVQUFVLEVBQUUsQ0FDakMsQ0FBQztZQUNGLE9BQU8sR0FBRyxFQUFFLElBQUksRUFBRSxvQkFBb0IsQ0FBQztRQUN6QyxDQUFDO2FBQU0sQ0FBQztZQUNOLGdCQUFnQixDQUFDLElBQUksQ0FDbkIsMkVBQTJFLEVBQzNFLEVBQUUsTUFBTSxFQUFFLFFBQVEsRUFBRSxVQUFVLEVBQUUsQ0FDakMsQ0FBQztZQUNGLE9BQU8sU0FBUyxDQUFDLENBQUMscURBQXFEO1FBQ3pFLENBQUM7SUFDSCxDQUFDO0lBQUMsT0FBTyxDQUFNLEVBQUUsQ0FBQztRQUNoQixnQkFBZ0IsQ0FBQyxLQUFLLENBQ3BCLHlGQUF5RixFQUN6RjtZQUNFLE1BQU07WUFDTixRQUFRO1lBQ1IsVUFBVTtZQUNWLEtBQUssRUFBRSxDQUFDLENBQUMsT0FBTztZQUNoQixLQUFLLEVBQUUsQ0FBQyxDQUFDLEtBQUs7WUFDZCxPQUFPLEVBQUUsQ0FBQztTQUNYLENBQ0YsQ0FBQztJQUNKLENBQUM7QUFDSCxDQUFDLENBQUM7QUEzRlcsUUFBQSxnREFBZ0Qsb0RBMkYzRDtBQUVLLE1BQU0sb0NBQW9DLEdBQUcsS0FBSyxFQUN2RCxNQUFjLEVBQ2QsUUFBZ0IsRUFDaEIsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILE1BQU0sYUFBYSxHQUFHLGtDQUFrQyxDQUFDO1FBQ3pELE1BQU0sS0FBSyxHQUFHOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztLQWdDYixDQUFDO1FBQ0YsTUFBTSxTQUFTLEdBQUc7WUFDaEIsTUFBTTtZQUNOLFFBQVE7U0FDVCxDQUFDO1FBRUYsTUFBTSxHQUFHLEdBQ1AsTUFBTSxhQUFHO2FBQ04sSUFBSSxDQUFDLGdDQUFvQixFQUFFO1lBQzFCLElBQUksRUFBRTtnQkFDSixhQUFhO2dCQUNiLEtBQUs7Z0JBQ0wsU0FBUzthQUNWO1lBQ0QsT0FBTyxFQUFFO2dCQUNQLDZCQUE2QixFQUFFLG1DQUF1QjtnQkFDdEQsY0FBYyxFQUFFLGtCQUFrQjtnQkFDbEMscUJBQXFCLEVBQUUsT0FBTzthQUMvQjtTQUNGLENBQUM7YUFDRCxJQUFJLEVBQUUsQ0FBQztRQUVaLHlEQUF5RDtRQUN6RCxJQUFJLEdBQUcsRUFBRSxJQUFJLEVBQUUsb0JBQW9CLEVBQUUsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDO1lBQ2hELGdCQUFnQixDQUFDLEtBQUssQ0FDcEIsZ0RBQWdELEdBQUcsQ0FBQyxJQUFJLENBQUMsb0JBQW9CLENBQUMsTUFBTSxnQkFBZ0IsRUFDcEcsRUFBRSxNQUFNLEVBQUUsUUFBUSxFQUFFLENBQ3JCLENBQUM7WUFDRixPQUFPLEdBQUcsRUFBRSxJQUFJLEVBQUUsb0JBQW9CLENBQUM7UUFDekMsQ0FBQzthQUFNLENBQUM7WUFDTixnQkFBZ0IsQ0FBQyxJQUFJLENBQ25CLCtEQUErRCxFQUMvRCxFQUFFLE1BQU0sRUFBRSxRQUFRLEVBQUUsQ0FDckIsQ0FBQztZQUNGLE9BQU8sU0FBUyxDQUFDLENBQUMsdUJBQXVCO1FBQzNDLENBQUM7SUFDSCxDQUFDO0lBQUMsT0FBTyxDQUFNLEVBQUUsQ0FBQztRQUNoQixnQkFBZ0IsQ0FBQyxLQUFLLENBQ3BCLDZGQUE2RixFQUM3RixFQUFFLE1BQU0sRUFBRSxRQUFRLEVBQUUsS0FBSyxFQUFFLENBQUMsQ0FBQyxPQUFPLEVBQUUsS0FBSyxFQUFFLENBQUMsQ0FBQyxLQUFLLEVBQUUsT0FBTyxFQUFFLENBQUMsRUFBRSxDQUNuRSxDQUFDO0lBQ0osQ0FBQztBQUNILENBQUMsQ0FBQztBQWhGVyxRQUFBLG9DQUFvQyx3Q0FnRi9DO0FBRUssTUFBTSxlQUFlLEdBQUcsS0FBSyxFQUFFLEtBQWEsRUFBRSxFQUFFO0lBQ3JELElBQUksQ0FBQztRQUNILE1BQU0sR0FBRyxHQUFHLDBCQUFjLENBQUM7UUFDM0IsTUFBTSxNQUFNLEdBQUc7WUFDYixPQUFPLEVBQUU7Z0JBQ1AsYUFBYSxFQUFFLFVBQVUsS0FBSyxFQUFFO2dCQUNoQyxjQUFjLEVBQUUsa0JBQWtCO2dCQUNsQyxNQUFNLEVBQUUsa0JBQWtCO2FBQzNCO1NBQ0YsQ0FBQztRQUVGLE1BQU0sSUFBSSxHQUFzQixNQUFNLGFBQUcsQ0FBQyxHQUFHLENBQUMsR0FBRyxFQUFFLE1BQU0sQ0FBQyxDQUFDLElBQUksRUFBRSxDQUFDO1FBQ2xFLGdCQUFnQixDQUFDLEtBQUssQ0FDcEIsdURBQXVELEVBQ3ZEO1lBQ0UsbUJBQW1CLEVBQUUsTUFBTSxDQUFDLElBQUksQ0FBQyxJQUFJLENBQUMsUUFBUSxJQUFJLEVBQUUsQ0FBQyxDQUFDLE1BQU07WUFDNUQsZ0JBQWdCLEVBQUUsTUFBTSxDQUFDLElBQUksQ0FBQyxJQUFJLENBQUMsS0FBSyxJQUFJLEVBQUUsQ0FBQyxDQUFDLE1BQU07U0FDdkQsQ0FDRixDQUFDO1FBQ0YsT0FBTyxJQUFJLENBQUM7SUFDZCxDQUFDO0lBQUMsT0FBTyxDQUFNLEVBQUUsQ0FBQztRQUNoQixnQkFBZ0IsQ0FBQyxLQUFLLENBQUMsZ0RBQWdELEVBQUU7WUFDdkUsS0FBSyxFQUFFLENBQUMsQ0FBQyxPQUFPO1lBQ2hCLEtBQUssRUFBRSxDQUFDLENBQUMsS0FBSztZQUNkLE9BQU8sRUFBRSxDQUFDO1NBQ1gsQ0FBQyxDQUFDO1FBQ0gsa0RBQWtEO0lBQ3BELENBQUM7QUFDSCxDQUFDLENBQUM7QUE1QlcsUUFBQSxlQUFlLG1CQTRCMUI7QUFFSyxNQUFNLHVCQUF1QixHQUFHLEtBQUssRUFDMUMscUJBQTZCLEVBQzdCLE1BQWMsRUFDZCxHQUFtQixFQUNuQixFQUFFO0lBQ0YsTUFBTSxhQUFhLEdBQUcseUJBQXlCLENBQUM7SUFDaEQsSUFBSSxDQUFDO1FBQ0gsZ0JBQWdCLENBQUMsSUFBSSxDQUFDLElBQUksYUFBYSxXQUFXLEVBQUU7WUFDbEQscUJBQXFCO1lBQ3JCLE1BQU07U0FDUCxDQUFDLENBQUM7UUFDSCxJQUFJLENBQUMscUJBQXFCLEVBQUUsQ0FBQztZQUMzQixnQkFBZ0IsQ0FBQyxJQUFJLENBQ25CLElBQUksYUFBYSxzQ0FBc0MsQ0FDeEQsQ0FBQztZQUNGLE9BQU87UUFDVCxDQUFDO1FBRUQsSUFBSSxDQUFDLE1BQU0sRUFBRSxDQUFDO1lBQ1osZ0JBQWdCLENBQUMsSUFBSSxDQUFDLElBQUksYUFBYSx1QkFBdUIsQ0FBQyxDQUFDO1lBQ2hFLE9BQU87UUFDVCxDQUFDO1FBQ0QsTUFBTSxZQUFZLEdBQUcsR0FBRyxDQUFDLE9BQU8sRUFBRSxxQkFBcUIsRUFBRSxDQUFDLENBQUMsb0NBQW9DO1FBQy9GLE1BQU0sS0FBSyxHQUFHLFlBQVksQ0FBQyxDQUFDLG9HQUFvRztRQUVoSSxJQUFJLENBQUMsS0FBSyxFQUFFLENBQUM7WUFDWCxnQkFBZ0IsQ0FBQyxJQUFJLENBQ25CLElBQUksYUFBYSxxQ0FBcUMsQ0FDdkQsQ0FBQztZQUNGLGdGQUFnRjtZQUNoRixPQUFPLENBQUMsZ0NBQWdDO1FBQzFDLENBQUM7UUFFRCxNQUFNLElBQUksR0FBRztZQUNYLHFCQUFxQjtZQUNyQixNQUFNO1lBQ04sYUFBYSxFQUFFLElBQUk7U0FDcEIsQ0FBQztRQUVGLE1BQU0sR0FBRyxHQUFHLCtCQUFtQixDQUFDO1FBRWhDLE1BQU0sT0FBTyxHQUFHLE1BQU0sYUFBRzthQUN0QixJQUFJLENBQUMsR0FBRyxFQUFFO1lBQ1QsSUFBSSxFQUFFLElBQUk7WUFDVixPQUFPLEVBQUU7Z0JBQ1AsYUFBYSxFQUFFLFVBQVUsS0FBSyxFQUFFO2dCQUNoQyxjQUFjLEVBQUUsa0JBQWtCO2FBQ25DO1NBQ0YsQ0FBQzthQUNELElBQUksRUFBRSxDQUFDO1FBRVYsZ0JBQWdCLENBQUMsSUFBSSxDQUNuQixJQUFJLGFBQWEsOENBQThDLEVBQy9ELEVBQUUscUJBQXFCLEVBQUUsTUFBTSxFQUFFLE9BQU8sRUFBRSxDQUMzQyxDQUFDO0lBQ0osQ0FBQztJQUFDLE9BQU8sQ0FBTSxFQUFFLENBQUM7UUFDaEIsZ0JBQWdCLENBQUMsS0FBSyxDQUNwQixJQUFJLGFBQWEseUNBQXlDLEVBQzFEO1lBQ0UscUJBQXFCO1lBQ3JCLE1BQU07WUFDTixLQUFLLEVBQUUsQ0FBQyxDQUFDLE9BQU87WUFDaEIsSUFBSSxFQUFFLENBQUMsQ0FBQyxJQUFJO1lBQ1osWUFBWSxFQUFFLENBQUMsRUFBRSxRQUFRLEVBQUUsSUFBSSxFQUFFLDRDQUE0QztZQUM3RSxLQUFLLEVBQUUsQ0FBQyxDQUFDLEtBQUs7U0FDZixDQUNGLENBQUM7UUFDRiwyREFBMkQ7SUFDN0QsQ0FBQztBQUNILENBQUMsQ0FBQztBQXJFVyxRQUFBLHVCQUF1QiwyQkFxRWxDO0FBQ0ssTUFBTSx1QkFBdUIsR0FBRyxLQUFLLEVBQzFDLEVBQVUsRUFDVixPQUFpQixFQUNqQixLQUFjLEVBQ2QsWUFBcUIsRUFDckIsU0FBa0IsRUFDbEIsV0FBcUIsRUFDckIsTUFBb0IsRUFDcEIsU0FBa0IsRUFDbEIsU0FBa0IsRUFDbEIsVUFBcUQsRUFDckQsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILE1BQU0sYUFBYSxHQUFHLCtCQUErQixDQUFDO1FBQ3RELE1BQU0sS0FBSyxHQUFHOztrQkFFQSxPQUFPLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyxvQkFBb0IsQ0FBQyxDQUFDLENBQUMsRUFBRTtrQkFDakQsU0FBUyxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsMEJBQTBCLENBQUMsQ0FBQyxDQUFDLEVBQUU7a0JBQ3pELFlBQVksS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLHdCQUF3QixDQUFDLENBQUMsQ0FBQyxFQUFFO2tCQUMxRCxLQUFLLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyxpQkFBaUIsQ0FBQyxDQUFDLENBQUMsRUFBRTtrQkFDNUMsV0FBVyxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsd0JBQXdCLENBQUMsQ0FBQyxDQUFDLEVBQUU7a0JBQ3pELE1BQU0sS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLGlCQUFpQixDQUFDLENBQUMsQ0FBQyxFQUFFO2tCQUM3QyxTQUFTLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyxxQkFBcUIsQ0FBQyxDQUFDLENBQUMsRUFBRTtrQkFDcEQsU0FBUyxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMscUJBQXFCLENBQUMsQ0FBQyxDQUFDLEVBQUU7a0JBQ3BELFVBQVUsS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLHNCQUFzQixDQUFDLENBQUMsQ0FBQyxFQUFFOzs7c0JBR2xELE9BQU8sS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLG9CQUFvQixDQUFDLENBQUMsQ0FBQyxFQUFFO3NCQUNqRCxTQUFTLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyx3QkFBd0IsQ0FBQyxDQUFDLENBQUMsRUFBRTtzQkFDdkQsWUFBWSxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsOEJBQThCLENBQUMsQ0FBQyxDQUFDLEVBQUU7c0JBQ2hFLEtBQUssS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLGdCQUFnQixDQUFDLENBQUMsQ0FBQyxFQUFFO3NCQUMzQyxXQUFXLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyw0QkFBNEIsQ0FBQyxDQUFDLENBQUMsRUFBRTtzQkFDN0QsTUFBTSxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsa0JBQWtCLENBQUMsQ0FBQyxDQUFDLEVBQUU7c0JBQzlDLFNBQVMsS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLHdCQUF3QixDQUFDLENBQUMsQ0FBQyxFQUFFO3NCQUN2RCxTQUFTLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyx3QkFBd0IsQ0FBQyxDQUFDLENBQUMsRUFBRTtzQkFDdkQsVUFBVSxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsMEJBQTBCLENBQUMsQ0FBQyxDQUFDLEVBQUU7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O1NBMEJ2RSxDQUFDO1FBRU4sSUFBSSxTQUFTLEdBQVE7WUFDbkIsRUFBRTtZQUNGLFNBQVMsRUFBRSxJQUFBLGtCQUFLLEdBQUUsQ0FBQyxNQUFNLEVBQUU7U0FDNUIsQ0FBQztRQUVGLElBQUksT0FBTyxLQUFLLFNBQVMsRUFBRSxDQUFDO1lBQzFCLFNBQVMsQ0FBQyxPQUFPLEdBQUcsT0FBTyxDQUFDO1FBQzlCLENBQUM7UUFFRCxJQUFJLFNBQVMsS0FBSyxTQUFTLEVBQUUsQ0FBQztZQUM1QixJQUFJLFNBQVMsS0FBSyxJQUFJLEVBQUUsQ0FBQztnQkFDdkIsU0FBUyxDQUFDLFNBQVMsR0FBRyxJQUFJLENBQUM7WUFDN0IsQ0FBQztpQkFBTSxDQUFDO2dCQUNOLFNBQVMsQ0FBQyxTQUFTLEdBQUcsSUFBQSxrQkFBSyxFQUFDLFNBQVMsQ0FBQyxDQUFDLE1BQU0sRUFBRSxDQUFDO1lBQ2xELENBQUM7UUFDSCxDQUFDO1FBRUQsSUFBSSxZQUFZLEtBQUssU0FBUyxFQUFFLENBQUM7WUFDL0IsU0FBUyxDQUFDLFlBQVksR0FBRyxZQUFZLENBQUM7UUFDeEMsQ0FBQztRQUVELElBQUksS0FBSyxLQUFLLFNBQVMsRUFBRSxDQUFDO1lBQ3hCLFNBQVMsQ0FBQyxLQUFLLEdBQUcsS0FBSyxDQUFDO1FBQzFCLENBQUM7UUFFRCxJQUFJLFdBQVcsS0FBSyxTQUFTLEVBQUUsQ0FBQztZQUM5QixTQUFTLENBQUMsV0FBVyxHQUFHLFdBQVcsQ0FBQztRQUN0QyxDQUFDO1FBRUQsSUFBSSxNQUFNLEtBQUssU0FBUyxFQUFFLENBQUM7WUFDekIsU0FBUyxDQUFDLE1BQU0sR0FBRyxNQUFNLENBQUM7UUFDNUIsQ0FBQztRQUVELElBQUksU0FBUyxLQUFLLFNBQVMsRUFBRSxDQUFDO1lBQzVCLFNBQVMsQ0FBQyxTQUFTLEdBQUcsU0FBUyxDQUFDO1FBQ2xDLENBQUM7UUFFRCxJQUFJLFNBQVMsS0FBSyxTQUFTLEVBQUUsQ0FBQztZQUM1QixTQUFTLENBQUMsU0FBUyxHQUFHLFNBQVMsQ0FBQztRQUNsQyxDQUFDO1FBRUQsSUFBSSxVQUFVLEtBQUssU0FBUyxFQUFFLENBQUM7WUFDN0IsU0FBUyxDQUFDLFVBQVUsR0FBRyxVQUFVLENBQUM7UUFDcEMsQ0FBQztRQUVELE1BQU0sR0FBRyxHQUVMLE1BQU0sYUFBRzthQUNWLElBQUksQ0FBQyxnQ0FBb0IsRUFBRTtZQUMxQixJQUFJLEVBQUU7Z0JBQ0osYUFBYTtnQkFDYixLQUFLO2dCQUNMLFNBQVM7YUFDVjtZQUNELE9BQU8sRUFBRTtnQkFDUCw2QkFBNkIsRUFBRSxtQ0FBdUI7Z0JBQ3RELGNBQWMsRUFBRSxrQkFBa0I7Z0JBQ2xDLHFCQUFxQixFQUFFLE9BQU87YUFDL0I7U0FDRixDQUFDO2FBQ0QsSUFBSSxFQUFFLENBQUM7UUFFVixnQkFBZ0IsQ0FBQyxJQUFJLENBQ25CLDZFQUE2RSxFQUM3RTtZQUNFLGFBQWEsRUFBRSxHQUFHLEVBQUUsSUFBSSxFQUFFLGlDQUFpQyxFQUFFLEVBQUU7WUFDL0QsT0FBTztTQUNSLENBQ0YsQ0FBQztRQUNGLE9BQU8sR0FBRyxFQUFFLElBQUksRUFBRSxpQ0FBaUMsQ0FBQztJQUN0RCxDQUFDO0lBQUMsT0FBTyxDQUFNLEVBQUUsQ0FBQztRQUNoQixnQkFBZ0IsQ0FBQyxLQUFLLENBQ3BCLHlFQUF5RSxFQUN6RSxFQUFFLEVBQUUsRUFBRSxLQUFLLEVBQUUsQ0FBQyxDQUFDLE9BQU8sRUFBRSxLQUFLLEVBQUUsQ0FBQyxDQUFDLEtBQUssRUFBRSxPQUFPLEVBQUUsQ0FBQyxFQUFFLENBQ3JELENBQUM7UUFDRixrREFBa0Q7SUFDcEQsQ0FBQztBQUNILENBQUMsQ0FBQztBQTVJVyxRQUFBLHVCQUF1QiwyQkE0SWxDO0FBRUssTUFBTSxlQUFlLEdBQUcsS0FBSyxFQUNsQyxPQUFtQztBQUNuQyx3RUFBd0U7RUFDMUQsRUFBRTtJQUNoQix5REFBeUQ7SUFDekQsTUFBTSxhQUFhLEdBQUcsaUJBQWlCLENBQUM7SUFDeEMsTUFBTSxHQUFHLEdBQUcsR0FBRyw2QkFBaUIsaUNBQWlDLENBQUM7SUFDbEUsZ0JBQWdCLENBQUMsSUFBSSxDQUFDLElBQUksYUFBYSxXQUFXLEVBQUU7UUFDbEQsR0FBRztRQUNILGNBQWMsRUFBRSxPQUFPO0tBQ3hCLENBQUMsQ0FBQztJQUVILElBQUksQ0FBQztRQUNILDREQUE0RDtRQUM1RCxNQUFNLFFBQVEsR0FBRyxNQUFNLGFBQUc7YUFDdkIsSUFBSSxDQUFDLEdBQUcsRUFBRTtZQUNULElBQUksRUFBRSxPQUFPO1lBQ2IsT0FBTyxFQUFFO2dCQUNQLGNBQWMsRUFBRSxrQkFBa0I7Z0JBQ2xDLDBFQUEwRTthQUMzRTtZQUNELDREQUE0RDtTQUM3RCxDQUFDO2FBQ0QsSUFBSSxFQUFFLENBQUM7UUFFVixnQkFBZ0IsQ0FBQyxJQUFJLENBQ25CLElBQUksYUFBYSxtQ0FBbUMsRUFDcEQsRUFBRSxHQUFHLEVBQUUsUUFBUSxFQUFFLENBQ2xCLENBQUM7UUFDRixPQUFPLFFBQVEsQ0FBQztJQUNsQixDQUFDO0lBQUMsT0FBTyxDQUFNLEVBQUUsQ0FBQztRQUNoQixNQUFNLFlBQVksR0FBRztZQUNuQixhQUFhO1lBQ2IsR0FBRztZQUNILGNBQWMsRUFBRSxPQUFPO1lBQ3ZCLEtBQUssRUFBRSxDQUFDLENBQUMsT0FBTztZQUNoQixJQUFJLEVBQUUsQ0FBQyxDQUFDLElBQUk7WUFDWixVQUFVLEVBQUUsQ0FBQyxDQUFDLFFBQVEsRUFBRSxVQUFVO1lBQ2xDLFlBQVksRUFBRSxDQUFDLENBQUMsUUFBUSxFQUFFLElBQUk7WUFDOUIsS0FBSyxFQUFFLENBQUMsQ0FBQyxLQUFLO1NBQ2YsQ0FBQztRQUNGLGdCQUFnQixDQUFDLEtBQUssQ0FDcEIsSUFBSSxhQUFhLHNDQUFzQyxFQUN2RCxZQUFZLENBQ2IsQ0FBQztRQUVGLHdEQUF3RDtRQUN4RCw0RUFBNEU7UUFDNUUsSUFBSSxDQUFDLEVBQUUsUUFBUSxFQUFFLElBQUksRUFBRSxDQUFDO1lBQ3RCLElBQUksQ0FBQztnQkFDSCxxRUFBcUU7Z0JBQ3JFLE1BQU0sWUFBWSxHQUNoQixPQUFPLENBQUMsQ0FBQyxRQUFRLENBQUMsSUFBSSxLQUFLLFFBQVE7b0JBQ2pDLENBQUMsQ0FBQyxDQUFDLENBQUMsUUFBUSxDQUFDLElBQUk7b0JBQ2pCLENBQUMsQ0FBQyxJQUFJLENBQUMsU0FBUyxDQUFDLENBQUMsQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUFDLENBQUM7Z0JBQ3RDLElBQUksZUFBZSxDQUFDO2dCQUNwQixJQUFJLENBQUM7b0JBQ0gsZUFBZSxHQUFHLElBQUksQ0FBQyxLQUFLLENBQUMsWUFBWSxDQUFDLENBQUM7Z0JBQzdDLENBQUM7Z0JBQUMsT0FBTyxjQUFjLEVBQUUsQ0FBQztvQkFDeEIsMENBQTBDO29CQUMxQyxlQUFlLEdBQUcsRUFBRSxPQUFPLEVBQUUsWUFBWSxFQUFFLENBQUM7Z0JBQzlDLENBQUM7Z0JBQ0QsTUFBTSxJQUFJLEtBQUssQ0FDYixrQkFBa0IsYUFBYSxLQUFLLGVBQWUsQ0FBQyxPQUFPLElBQUksWUFBWSxFQUFFLENBQzlFLENBQUM7WUFDSixDQUFDO1lBQUMsT0FBTyxVQUFlLEVBQUUsQ0FBQztnQkFDekIsTUFBTSxJQUFJLEtBQUssQ0FDYixrQkFBa0IsYUFBYSx3QkFBd0IsQ0FBQyxDQUFDLFFBQVEsQ0FBQyxJQUFJLElBQUksQ0FBQyxDQUFDLE9BQU8sRUFBRSxDQUN0RixDQUFDO1lBQ0osQ0FBQztRQUNILENBQUM7UUFDRCxNQUFNLElBQUksS0FBSyxDQUNiLENBQUMsQ0FBQyxPQUFPLElBQUksYUFBYSxhQUFhLDBCQUEwQixDQUNsRSxDQUFDO0lBQ0osQ0FBQztBQUNILENBQUMsQ0FBQztBQTNFVyxRQUFBLGVBQWUsbUJBMkUxQiIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBnb3QgZnJvbSAnZ290JztcbmltcG9ydCB7IGRheWpzIH0gZnJvbSAnQGxpYi9kYXRlLXV0aWxzJztcbmltcG9ydCBfIGZyb20gJ2xvZGFzaCc7XG5pbXBvcnQge1xuICBnb29nbGVDbGllbnRJZEF0b21pY1dlYixcbiAgZ29vZ2xlQ2xpZW50U2VjcmV0QXRvbWljV2ViLFxuICBnb29nbGVPQXV0aEF0b21pY1dlYlJlZGlyZWN0VXJsLFxuICBnb29nbGVUb2tlblVybCxcbiAgcG9zdGdyYXBoaWxlQWRtaW5TZWNyZXQsXG4gIHBvc3RncmFwaGlsZUdyYXBoVXJsLFxuICB6b29tSVZGb3JQYXNzLFxuICB6b29tUGFzc0tleSxcbiAgem9vbVNhbHRGb3JQYXNzLFxufSBmcm9tICdAbGliL2NvbnN0YW50cyc7XG5pbXBvcnQge1xuICBab29tV2ViaG9va1JlcXVlc3RUeXBlLFxuICBab29tV2ViaG9va1ZhbGlkYXRpb25SZXF1ZXN0VHlwZSxcbn0gZnJvbSAnQGxpYi90eXBlcyc7XG5pbXBvcnQgeyBnb29nbGUgfSBmcm9tICdnb29nbGVhcGlzJztcbmltcG9ydCB0eXBlIHsgTmV4dEFwaVJlcXVlc3QsIE5leHRBcGlSZXNwb25zZSB9IGZyb20gJ25leHQnO1xuaW1wb3J0IGNyeXB0bywgeyBCaW5hcnlMaWtlIH0gZnJvbSAnY3J5cHRvJztcbmltcG9ydCB7XG4gIENhbGVuZGFySW50ZWdyYXRpb25UeXBlLFxuICBjb2xvclR5cGUsXG59IGZyb20gJy4vZGF0YVR5cGVzL0NhbGVuZGFyX0ludGVncmF0aW9uVHlwZSc7XG5pbXBvcnQgeyBnb29nbGVDb2xvclVybCB9IGZyb20gJy4vY2FsZW5kYXJMaWIvY29uc3RhbnRzJztcbmltcG9ydCBhcHBTZXJ2aWNlTG9nZ2VyIGZyb20gJy4vbG9nZ2VyJzsgLy8gSW1wb3J0IHRoZSBzaGFyZWQgbG9nZ2VyXG5pbXBvcnQgeyBjb2xvclJlc3BvbnNlVHlwZSB9IGZyb20gJy4vY2FsZW5kYXJMaWIvdHlwZXMnO1xuaW1wb3J0IHsgdHlwZSBDcmVkZW50aWFscyB9IGZyb20gJ2dvb2dsZS1hdXRoLWxpYnJhcnkvYnVpbGQvc3JjL2F1dGgvY3JlZGVudGlhbHMnO1xuaW1wb3J0IHsgZ29vZ2xlUGVvcGxlU3luY1VybCB9IGZyb20gJy4vY29udGFjdExpYi9jb25zdGFudHMnO1xuaW1wb3J0IHsgU2NoZWR1bGVNZWV0aW5nUmVxdWVzdFR5cGUgfSBmcm9tICcuL2RhdGFUeXBlcy9TY2hlZHVsZU1lZXRpbmdSZXF1ZXN0VHlwZSc7XG5pbXBvcnQgeyBTQ0hFRFVMRVJfQVBJX1VSTCB9IGZyb20gJy4vY29uc3RhbnRzJztcblxuLy8gR2VuZXJpYyByZXNpbGllbnQgJ2dvdCcgd3JhcHBlciBmb3IgYXBwLXNlcnZpY2UgYmFja2VuZCBoZWxwZXJzXG5jb25zdCByZXNpbGllbnRHb3QgPSBhc3luYyAoXG4gIG1ldGhvZDogJ2dldCcgfCAncG9zdCcgfCAncGF0Y2gnIHwgJ3B1dCcgfCAnZGVsZXRlJyxcbiAgdXJsOiBzdHJpbmcsXG4gIG9wdGlvbnM/OlxuICAgIHwgaW1wb3J0KCdnb3QnKS5PcHRpb25zT2ZKU09OUmVzcG9uc2VCb2R5XG4gICAgfCBpbXBvcnQoJ2dvdCcpLk9wdGlvbnNPZlRleHRSZXNwb25zZUJvZHksIC8vIEFkanVzdCBhcyBuZWVkZWQgZm9yIGZvcm0vanNvbiBldGMuXG4gIG9wZXJhdGlvbk5hbWU6IHN0cmluZyA9ICdleHRlcm5hbEFwaUNhbGwnIC8vIERlZmF1bHQgb3BlcmF0aW9uIG5hbWUgZm9yIGxvZ2dpbmdcbikgPT4ge1xuICBjb25zdCBNQVhfUkVUUklFUyA9IDM7XG4gIC8vIFN0YW5kYXJkaXplIHRpbWVvdXQsIGUuZy4gMTVzLCBjYW4gYmUgb3ZlcnJpZGRlbiBpbiBvcHRpb25zIGlmIG5lZWRlZCBieSBzcGVjaWZpYyBjYWxsc1xuICBjb25zdCBERUZBVUxUX1RJTUVPVVRfTVMgPSBvcHRpb25zPy50aW1lb3V0Py5yZXF1ZXN0IHx8IDE1MDAwO1xuICBsZXQgYXR0ZW1wdCA9IDA7XG4gIGxldCBsYXN0RXJyb3I6IGFueSA9IG51bGw7XG5cbiAgY29uc3QgZ290T3B0aW9ucyA9IHtcbiAgICAuLi5vcHRpb25zLFxuICAgIHRpbWVvdXQ6IHsgcmVxdWVzdDogREVGQVVMVF9USU1FT1VUX01TIH0sIC8vIEVuc3VyZSB0aW1lb3V0IGlzIHNldFxuICAgIHJldHJ5OiB7IGxpbWl0OiAwIH0sIC8vIERpc2FibGUgZ290J3MgbmF0aXZlIHJldHJ5LCB3ZSdyZSBoYW5kbGluZyBpdCBtYW51YWxseVxuICAgIHRocm93SHR0cEVycm9yczogdHJ1ZSwgLy8gRW5zdXJlIGdvdCB0aHJvd3Mgb24gSFRUUCBlcnJvcnMgPiAzOTlcbiAgICByZXNwb25zZVR5cGU6IG9wdGlvbnM/LnJlc3BvbnNlVHlwZSB8fCAnanNvbicsIC8vIERlZmF1bHQgdG8gSlNPTiwgY2FuIGJlIG92ZXJyaWRkZW5cbiAgfSBhcyBpbXBvcnQoJ2dvdCcpLk9wdGlvbnM7IC8vIENhc3QgdG8gYmFzZSBPcHRpb25zIGZvciBnb3QgY2FsbFxuXG4gIHdoaWxlIChhdHRlbXB0IDwgTUFYX1JFVFJJRVMpIHtcbiAgICB0cnkge1xuICAgICAgYXBwU2VydmljZUxvZ2dlci5pbmZvKFxuICAgICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIEF0dGVtcHQgJHthdHRlbXB0ICsgMX0vJHtNQVhfUkVUUklFU30gLSAke21ldGhvZC50b1VwcGVyQ2FzZSgpfSAke3VybH1gLFxuICAgICAgICB7IHVybCwgbWV0aG9kLCBvcHRpb25zOiBfLm9taXQoZ290T3B0aW9ucywgWydoZWFkZXJzLkF1dGhvcml6YXRpb24nXSkgfVxuICAgICAgKTsgLy8gT21pdCBzZW5zaXRpdmUgaGVhZGVyc1xuXG4gICAgICBsZXQgcmVzcG9uc2U6IGltcG9ydCgnZ290JykuR290UmVzcG9uc2U8YW55PjtcbiAgICAgIHN3aXRjaCAobWV0aG9kLnRvTG93ZXJDYXNlKCkpIHtcbiAgICAgICAgY2FzZSAnZ2V0JzpcbiAgICAgICAgICByZXNwb25zZSA9IGF3YWl0IGdvdC5nZXQodXJsLCBnb3RPcHRpb25zKTtcbiAgICAgICAgICBicmVhaztcbiAgICAgICAgY2FzZSAncG9zdCc6XG4gICAgICAgICAgcmVzcG9uc2UgPSBhd2FpdCBnb3QucG9zdCh1cmwsIGdvdE9wdGlvbnMpO1xuICAgICAgICAgIGJyZWFrO1xuICAgICAgICBjYXNlICdwYXRjaCc6XG4gICAgICAgICAgcmVzcG9uc2UgPSBhd2FpdCBnb3QucGF0Y2godXJsLCBnb3RPcHRpb25zKTtcbiAgICAgICAgICBicmVhaztcbiAgICAgICAgY2FzZSAncHV0JzpcbiAgICAgICAgICByZXNwb25zZSA9IGF3YWl0IGdvdC5wdXQodXJsLCBnb3RPcHRpb25zKTtcbiAgICAgICAgICBicmVhaztcbiAgICAgICAgY2FzZSAnZGVsZXRlJzpcbiAgICAgICAgICByZXNwb25zZSA9IGF3YWl0IGdvdC5kZWxldGUodXJsLCBnb3RPcHRpb25zKTtcbiAgICAgICAgICBicmVhaztcbiAgICAgICAgZGVmYXVsdDpcbiAgICAgICAgICB0aHJvdyBuZXcgRXJyb3IoYFVuc3VwcG9ydGVkIEhUVFAgbWV0aG9kOiAke21ldGhvZH1gKTtcbiAgICAgIH1cblxuICAgICAgYXBwU2VydmljZUxvZ2dlci5pbmZvKFxuICAgICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIEF0dGVtcHQgJHthdHRlbXB0ICsgMX0gc3VjY2Vzc2Z1bC5gLFxuICAgICAgICB7IHVybCwgbWV0aG9kLCBzdGF0dXNDb2RlOiByZXNwb25zZS5zdGF0dXNDb2RlIH1cbiAgICAgICk7XG4gICAgICByZXR1cm4gcmVzcG9uc2UuYm9keTsgLy8gZ290IGFscmVhZHkgcGFyc2VzIGlmIHJlc3BvbnNlVHlwZSBpcyAnanNvbidcbiAgICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgICBsYXN0RXJyb3IgPSBlcnJvcjtcbiAgICAgIGNvbnN0IHN0YXR1c0NvZGUgPSBlcnJvci5yZXNwb25zZT8uc3RhdHVzQ29kZTtcbiAgICAgIGNvbnN0IGVycm9yQ29kZSA9IGVycm9yLmNvZGU7XG5cbiAgICAgIGFwcFNlcnZpY2VMb2dnZXIud2FybihcbiAgICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBBdHRlbXB0ICR7YXR0ZW1wdCArIDF9LyR7TUFYX1JFVFJJRVN9IGZhaWxlZC5gLFxuICAgICAgICB7XG4gICAgICAgICAgdXJsLFxuICAgICAgICAgIG1ldGhvZCxcbiAgICAgICAgICBhdHRlbXB0OiBhdHRlbXB0ICsgMSxcbiAgICAgICAgICBlcnJvcjogZXJyb3IubWVzc2FnZSxcbiAgICAgICAgICBzdGF0dXNDb2RlLFxuICAgICAgICAgIGVycm9yQ29kZSxcbiAgICAgICAgICAvLyByZXNwb25zZUJvZHk6IGVycm9yLnJlc3BvbnNlPy5ib2R5LCAvLyBCZSBjYXV0aW91cyBsb2dnaW5nIGZ1bGwgcmVzcG9uc2UgYm9kaWVzXG4gICAgICAgIH1cbiAgICAgICk7XG5cbiAgICAgIC8vIERlY2lkZSBpZiB3ZSBzaG91bGQgcmV0cnlcbiAgICAgIGNvbnN0IGlzUmV0cnlhYmxlSHR0cEVycm9yID1cbiAgICAgICAgc3RhdHVzQ29kZSAmJlxuICAgICAgICAoc3RhdHVzQ29kZSA+PSA1MDAgfHwgc3RhdHVzQ29kZSA9PT0gNDA4IHx8IHN0YXR1c0NvZGUgPT09IDQyOSk7XG4gICAgICBjb25zdCBpc1JldHJ5YWJsZU5ldHdvcmtFcnJvciA9XG4gICAgICAgIGVycm9yQ29kZSAmJlxuICAgICAgICBbXG4gICAgICAgICAgJ0VUSU1FRE9VVCcsXG4gICAgICAgICAgJ0VDT05OUkVTRVQnLFxuICAgICAgICAgICdFQUREUklOVVNFJyxcbiAgICAgICAgICAnRUNPTk5SRUZVU0VEJyxcbiAgICAgICAgICAnRVBJUEUnLFxuICAgICAgICAgICdFTkVUVU5SRUFDSCcsXG4gICAgICAgICAgJ0VBSV9BR0FJTicsXG4gICAgICAgIF0uaW5jbHVkZXMoZXJyb3JDb2RlKTtcblxuICAgICAgaWYgKCFpc1JldHJ5YWJsZUh0dHBFcnJvciAmJiAhaXNSZXRyeWFibGVOZXR3b3JrRXJyb3IpIHtcbiAgICAgICAgYXBwU2VydmljZUxvZ2dlci5lcnJvcihcbiAgICAgICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIE5vbi1yZXRyeWFibGUgZXJyb3IgZW5jb3VudGVyZWQuIEFib3J0aW5nIHJldHJpZXMuYCxcbiAgICAgICAgICB7IHVybCwgbWV0aG9kLCBzdGF0dXNDb2RlLCBlcnJvckNvZGUgfVxuICAgICAgICApO1xuICAgICAgICBicmVhazsgLy8gQnJlYWsgZm9yIG5vbi1yZXRyeWFibGUgZXJyb3JzXG4gICAgICB9XG4gICAgfVxuICAgIGF0dGVtcHQrKztcbiAgICBpZiAoYXR0ZW1wdCA8IE1BWF9SRVRSSUVTKSB7XG4gICAgICBjb25zdCBkZWxheSA9IE1hdGgucG93KDIsIGF0dGVtcHQgLSAxKSAqIDEwMDA7IC8vIGUuZy4sIDFzLCAyc1xuICAgICAgYXBwU2VydmljZUxvZ2dlci5pbmZvKFxuICAgICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIFdhaXRpbmcgJHtkZWxheX1tcyBiZWZvcmUgcmV0cnkgJHthdHRlbXB0ICsgMX0vJHtNQVhfUkVUUklFU30uYCxcbiAgICAgICAgeyB1cmwsIG1ldGhvZCB9XG4gICAgICApO1xuICAgICAgYXdhaXQgbmV3IFByb21pc2UoKHJlc29sdmUpID0+IHNldFRpbWVvdXQocmVzb2x2ZSwgZGVsYXkpKTtcbiAgICB9XG4gIH1cbiAgYXBwU2VydmljZUxvZ2dlci5lcnJvcihcbiAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIEZhaWxlZCBhZnRlciAke2F0dGVtcHR9IGF0dGVtcHRzLmAsXG4gICAge1xuICAgICAgdXJsLFxuICAgICAgbWV0aG9kLFxuICAgICAgbGFzdEVycm9yOiBsYXN0RXJyb3I/Lm1lc3NhZ2UsXG4gICAgICBsYXN0U3RhdHVzQ29kZTogbGFzdEVycm9yPy5yZXNwb25zZT8uc3RhdHVzQ29kZSxcbiAgICB9XG4gICk7XG4gIHRocm93IChcbiAgICBsYXN0RXJyb3IgfHxcbiAgICBuZXcgRXJyb3IoXG4gICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIEZhaWxlZCBhZnRlciBhbGwgcmV0cmllcyBmb3IgJHttZXRob2QudG9VcHBlckNhc2UoKX0gJHt1cmx9LmBcbiAgICApXG4gICk7XG59O1xuXG5jb25zdCBvYXV0aDJDbGllbnQgPSBuZXcgZ29vZ2xlLmF1dGguT0F1dGgyKFxuICBnb29nbGVDbGllbnRJZEF0b21pY1dlYixcbiAgZ29vZ2xlQ2xpZW50U2VjcmV0QXRvbWljV2ViLFxuICBnb29nbGVPQXV0aEF0b21pY1dlYlJlZGlyZWN0VXJsXG4pO1xuXG5leHBvcnQgY29uc3QgZXhjaGFuZ2VDb2RlRm9yVG9rZW5zID0gYXN5bmMgKFxuICBjb2RlOiBzdHJpbmdcbik6IFByb21pc2U8Q3JlZGVudGlhbHM+ID0+IHtcbiAgdHJ5IHtcbiAgICBsZXQgeyB0b2tlbnMgfSA9IGF3YWl0IG9hdXRoMkNsaWVudC5nZXRUb2tlbihjb2RlKTtcbiAgICBvYXV0aDJDbGllbnQuc2V0Q3JlZGVudGlhbHModG9rZW5zKTtcbiAgICBhcHBTZXJ2aWNlTG9nZ2VyLmluZm8oXG4gICAgICAnW2V4Y2hhbmdlQ29kZUZvclRva2Vuc10gU3VjY2Vzc2Z1bGx5IGV4Y2hhbmdlZCBjb2RlIGZvciB0b2tlbnMuJyxcbiAgICAgIHsgY29kZVByZWZpeDogY29kZT8uc3Vic3RyaW5nKDAsIDEwKSwgdG9rZW5FeHBpcnk6IHRva2Vucy5leHBpcnlfZGF0ZSB9XG4gICAgKTtcbiAgICByZXR1cm4gdG9rZW5zO1xuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBhcHBTZXJ2aWNlTG9nZ2VyLmVycm9yKFxuICAgICAgJ1tleGNoYW5nZUNvZGVGb3JUb2tlbnNdIFVuYWJsZSB0byBleGNoYW5nZSBjb2RlIGZvciB0b2tlbnMuJyxcbiAgICAgIHtcbiAgICAgICAgY29kZVByZWZpeDogY29kZT8uc3Vic3RyaW5nKDAsIDEwKSxcbiAgICAgICAgZXJyb3I6IGUubWVzc2FnZSxcbiAgICAgICAgc3RhY2s6IGUuc3RhY2ssXG4gICAgICAgIGRldGFpbHM6IGUsXG4gICAgICB9XG4gICAgKTtcbiAgICB0aHJvdyBlOyAvLyBSZXRocm93IHRoZSBlcnJvclxuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVHb29nbGVBdXRoVXJsID0gKHN0YXRlPzogc3RyaW5nKSA9PiB7XG4gIC8vIEFjY2VzcyBzY29wZXNcbiAgY29uc3Qgc2NvcGVzID0gW1xuICAgICdodHRwczovL3d3dy5nb29nbGVhcGlzLmNvbS9hdXRoL2NhbGVuZGFyLnJlYWRvbmx5JyxcbiAgICAnaHR0cHM6Ly93d3cuZ29vZ2xlYXBpcy5jb20vYXV0aC9jYWxlbmRhci5ldmVudHMnLFxuICAgICdodHRwczovL3d3dy5nb29nbGVhcGlzLmNvbS9hdXRoL2NvbnRhY3RzLnJlYWRvbmx5JyxcbiAgICAnaHR0cHM6Ly93d3cuZ29vZ2xlYXBpcy5jb20vYXV0aC9nbWFpbC5yZWFkb25seScsIC8vIEFkZGVkIEdtYWlsIHJlYWRvbmx5IHNjb3BlXG4gIF07XG5cbiAgY29uc3QgY29uZmlnOiBhbnkgPSB7XG4gICAgLy8gJ29ubGluZScgKGRlZmF1bHQpIG9yICdvZmZsaW5lJyAoZ2V0cyByZWZyZXNoX3Rva2VuKVxuICAgIGFjY2Vzc190eXBlOiAnb2ZmbGluZScsXG4gICAgLyoqIFBhc3MgaW4gdGhlIHNjb3BlcyBhcnJheSBkZWZpbmVkIGFib3ZlLlxuICAgICAqIEFsdGVybmF0aXZlbHksIGlmIG9ubHkgb25lIHNjb3BlIGlzIG5lZWRlZCwgeW91IGNhbiBwYXNzIGEgc2NvcGUgVVJMIGFzIGEgc3RyaW5nICovXG4gICAgc2NvcGU6IHNjb3BlcyxcbiAgICAvLyBFbmFibGUgaW5jcmVtZW50YWwgYXV0aG9yaXphdGlvbi4gUmVjb21tZW5kZWQgYXMgYSBiZXN0IHByYWN0aWNlLlxuICAgIGluY2x1ZGVfZ3JhbnRlZF9zY29wZXM6IHRydWUsXG4gIH07XG5cbiAgaWYgKHN0YXRlKSB7XG4gICAgY29uZmlnLnN0YXRlID0gc3RhdGU7XG4gIH1cbiAgLy8gR2VuZXJhdGUgYSB1cmwgdGhhdCBhc2tzIHBlcm1pc3Npb25zIGZvciB0aGUgQ2FsZW5kYXIgYWN0aXZpdHkgc2NvcGVcbiAgY29uc3QgYXV0aG9yaXphdGlvblVybCA9IG9hdXRoMkNsaWVudC5nZW5lcmF0ZUF1dGhVcmwoY29uZmlnKTtcblxuICAvLyBjb25zb2xlLmxvZyhhdXRob3JpemF0aW9uVXJsLCAnIGF1dGhvcml6YXRpb25VcmwnKVxuXG4gIHJldHVybiBhdXRob3JpemF0aW9uVXJsO1xufTtcblxuZXhwb3J0IGNvbnN0IGdldE1pbmltYWxDYWxlbmRhckludGVncmF0aW9uQnlSZXNvdXJjZSA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHJlc291cmNlOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbic7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICBxdWVyeSBnZXRDYWxlbmRhckludGVncmF0aW9uKCR1c2VySWQ6IHV1aWQhLCAkcmVzb3VyY2U6IFN0cmluZyEpIHtcbiAgICAgICAgQ2FsZW5kYXJfSW50ZWdyYXRpb24od2hlcmU6IHt1c2VySWQ6IHtfZXE6ICR1c2VySWR9LCByZXNvdXJjZToge19lcTogJHJlc291cmNlfX0pIHtcbiAgICAgICAgICAgIGFwcEFjY291bnRJZFxuICAgICAgICAgICAgYXBwRW1haWxcbiAgICAgICAgICAgIGFwcElkXG4gICAgICAgICAgICBjbGllbnRUeXBlXG4gICAgICAgICAgICBjb2xvcnNcbiAgICAgICAgICAgIGNvbnRhY3RFbWFpbFxuICAgICAgICAgICAgY29udGFjdEZpcnN0TmFtZVxuICAgICAgICAgICAgY29udGFjdExhc3ROYW1lXG4gICAgICAgICAgICBjb250YWN0TmFtZVxuICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICAgIGVuYWJsZWRcbiAgICAgICAgICAgIGV4cGlyZXNBdFxuICAgICAgICAgICAgaWRcbiAgICAgICAgICAgIG5hbWVcbiAgICAgICAgICAgIHBhZ2VUb2tlblxuICAgICAgICAgICAgcGFzc3dvcmRcbiAgICAgICAgICAgIHBob25lQ291bnRyeVxuICAgICAgICAgICAgcGhvbmVOdW1iZXJcbiAgICAgICAgICAgIHJlZnJlc2hUb2tlblxuICAgICAgICAgICAgcmVzb3VyY2VcbiAgICAgICAgICAgIHN5bmNFbmFibGVkXG4gICAgICAgICAgICBzeW5jVG9rZW5cbiAgICAgICAgICAgIHRva2VuXG4gICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgdXNlcm5hbWVcbiAgICAgICAgfVxuICAgICAgfVxuICAgIGA7XG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgdXNlcklkLFxuICAgICAgcmVzb3VyY2UsXG4gICAgfTtcblxuICAgIGNvbnN0IG9wdGlvbnMgPSB7XG4gICAgICBqc29uOiB7IG9wZXJhdGlvbk5hbWUsIHF1ZXJ5LCB2YXJpYWJsZXMgfSxcbiAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLUFkbWluLVNlY3JldCc6IHBvc3RncmFwaGlsZUFkbWluU2VjcmV0LFxuICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtUm9sZSc6ICdhZG1pbicsIC8vIEFzc3VtaW5nIGFkbWluIHJvbGUgYXMgcGVyIG9yaWdpbmFsIGRpcmVjdCBjYWxsXG4gICAgICB9LFxuICAgIH07XG5cbiAgICBjb25zdCByZXNwb25zZURhdGEgPSAoYXdhaXQgcmVzaWxpZW50R290KFxuICAgICAgJ3Bvc3QnLFxuICAgICAgcG9zdGdyYXBoaWxlR3JhcGhVcmwsXG4gICAgICBvcHRpb25zLFxuICAgICAgb3BlcmF0aW9uTmFtZVxuICAgICkpIGFzIHsgZGF0YT86IHsgQ2FsZW5kYXJfSW50ZWdyYXRpb246IENhbGVuZGFySW50ZWdyYXRpb25UeXBlW10gfSB9O1xuXG4gICAgaWYgKHJlc3BvbnNlRGF0YT8uZGF0YT8uQ2FsZW5kYXJfSW50ZWdyYXRpb24/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGFwcFNlcnZpY2VMb2dnZXIuZGVidWcoXG4gICAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gRm91bmQgaW50ZWdyYXRpb24gZm9yIHVzZXJJZDogJHt1c2VySWR9LCByZXNvdXJjZTogJHtyZXNvdXJjZX0uYCxcbiAgICAgICAgeyBpbnRlZ3JhdGlvbklkOiByZXNwb25zZURhdGEuZGF0YS5DYWxlbmRhcl9JbnRlZ3JhdGlvblswXS5pZCB9XG4gICAgICApO1xuICAgICAgcmV0dXJuIHJlc3BvbnNlRGF0YS5kYXRhLkNhbGVuZGFyX0ludGVncmF0aW9uWzBdO1xuICAgIH0gZWxzZSB7XG4gICAgICBhcHBTZXJ2aWNlTG9nZ2VyLmluZm8oXG4gICAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gTm8gaW50ZWdyYXRpb24gZm91bmQgZm9yIHVzZXJJZDogJHt1c2VySWR9LCByZXNvdXJjZTogJHtyZXNvdXJjZX0uYFxuICAgICAgKTtcbiAgICAgIHJldHVybiB1bmRlZmluZWQ7XG4gICAgfVxuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBhcHBTZXJ2aWNlTG9nZ2VyLmVycm9yKFxuICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBVbmFibGUgdG8gZ2V0IGNhbGVuZGFyIGludGVncmF0aW9uLmAsXG4gICAgICB7IHVzZXJJZCwgcmVzb3VyY2UsIGVycm9yOiBlLm1lc3NhZ2UsIHN0YWNrOiBlLnN0YWNrLCBkZXRhaWxzOiBlIH1cbiAgICApO1xuICAgIC8vIHJlc2lsaWVudEdvdCB3aWxsIHRocm93LCB0aGlzIGNhdGNoIGlzIGZvciBhbnkgYWRkaXRpb25hbCBoYW5kbGluZyBvciBpZiBpdCdzIG5vdCBjYXVnaHQgYnkgcmVzaWxpZW50R290ICh1bmxpa2VseSBmb3IgSFRUUCBlcnJvcnMpXG4gICAgdGhyb3cgZTsgLy8gUmV0aHJvdyB0byBlbnN1cmUgZmFpbHVyZSBpcyBwcm9wYWdhdGVkIGlmIG5vdCBhbHJlYWR5IGJ5IHJlc2lsaWVudEdvdFxuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdXBkYXRlQWNjZXNzVG9rZW5DYWxlbmRhckludGVncmF0aW9uID0gYXN5bmMgKFxuICBpZDogc3RyaW5nLFxuICB0b2tlbjogc3RyaW5nIHwgbnVsbCxcbiAgZXhwaXJlc0luOiBudW1iZXIgfCBudWxsLFxuICBlbmFibGVkPzogYm9vbGVhbixcbiAgcmVmcmVzaFRva2VuPzogc3RyaW5nIHwgbnVsbFxuKSA9PiB7XG4gIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAndXBkYXRlQWNjZXNzVG9rZW5DYWxlbmRhckludGVncmF0aW9uJzsgLy8gUmVuYW1lZCBmcm9tICd1cGRhdGVDYWxlbmRhckludGVncmF0aW9uJyBmb3IgY2xhcml0eVxuICB0cnkge1xuICAgIC8vIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAndXBkYXRlQ2FsZW5kYXJJbnRlZ3JhdGlvbicgLy8gT3JpZ2luYWwgbmFtZVxuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgbXV0YXRpb24gdXBkYXRlQWNjZXNzVG9rZW5DYWxlbmRhckludGVncmF0aW9uKCRpZDogdXVpZCEsJHt0b2tlbiAhPT0gdW5kZWZpbmVkID8gJyAkdG9rZW46IFN0cmluZywnIDogJyd9JHtyZWZyZXNoVG9rZW4gIT09IHVuZGVmaW5lZCA/ICcgJHJlZnJlc2hUb2tlbjogU3RyaW5nLCcgOiAnJ30ke2V4cGlyZXNJbiAhPT0gdW5kZWZpbmVkID8gJyAkZXhwaXJlc0F0OiB0aW1lc3RhbXB0eiwnIDogJyd9JHtlbmFibGVkICE9PSB1bmRlZmluZWQgPyAnICRlbmFibGVkOiBCb29sZWFuLCcgOiAnJ30pIHtcbiAgICAgICAgdXBkYXRlX0NhbGVuZGFyX0ludGVncmF0aW9uX2J5X3BrKHBrX2NvbHVtbnM6IHtpZDogJGlkfSwgX3NldDogeyR7dG9rZW4gIT09IHVuZGVmaW5lZCA/ICd0b2tlbjogJHRva2VuLCcgOiAnJ30ke3JlZnJlc2hUb2tlbiAhPT0gdW5kZWZpbmVkID8gJyByZWZyZXNoVG9rZW46ICRyZWZyZXNoVG9rZW4sJyA6ICcnfSR7ZXhwaXJlc0luICE9PSB1bmRlZmluZWQgPyAnIGV4cGlyZXNBdDogJGV4cGlyZXNBdCwnIDogJyd9JHtlbmFibGVkICE9PSB1bmRlZmluZWQgPyAnIGVuYWJsZWQ6ICRlbmFibGVkLCcgOiAnJ319KSB7XG4gICAgICAgICAgaWRcbiAgICAgICAgICBuYW1lXG4gICAgICAgICAgcmVmcmVzaFRva2VuXG4gICAgICAgICAgdG9rZW5cbiAgICAgICAgICBjbGllbnRUeXBlXG4gICAgICAgICAgdXNlcklkXG4gICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICBgO1xuICAgIGxldCB2YXJpYWJsZXM6IGFueSA9IHtcbiAgICAgIGlkLFxuICAgICAgdG9rZW4sXG4gICAgICBleHBpcmVzQXQ6IGV4cGlyZXNJblxuICAgICAgICA/IGRheWpzKCkuYWRkKGV4cGlyZXNJbiwgJ3NlY29uZHMnKS50b0lTT1N0cmluZygpXG4gICAgICAgIDogbnVsbCxcbiAgICB9O1xuXG4gICAgaWYgKGVuYWJsZWQgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLmVuYWJsZWQgPSBlbmFibGVkO1xuICAgIH1cblxuICAgIGlmIChyZWZyZXNoVG9rZW4gIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLnJlZnJlc2hUb2tlbiA9IHJlZnJlc2hUb2tlbjtcbiAgICB9XG5cbiAgICBjb25zdCBnb3RPcHRpb25zID0ge1xuICAgICAganNvbjogeyBvcGVyYXRpb25OYW1lLCBxdWVyeSwgdmFyaWFibGVzIH0sXG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgICdYLVBvc3RncmFwaGlsZS1BZG1pbi1TZWNyZXQnOiBwb3N0Z3JhcGhpbGVBZG1pblNlY3JldCxcbiAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgfSxcbiAgICB9O1xuXG4gICAgLy8gVXNpbmcgcmVzaWxpZW50R290IG5vd1xuICAgIGF3YWl0IHJlc2lsaWVudEdvdCgncG9zdCcsIHBvc3RncmFwaGlsZUdyYXBoVXJsLCBnb3RPcHRpb25zLCBvcGVyYXRpb25OYW1lKTtcblxuICAgIGFwcFNlcnZpY2VMb2dnZXIuaW5mbyhcbiAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gU3VjY2Vzc2Z1bGx5IHVwZGF0ZWQgY2FsZW5kYXIgaW50ZWdyYXRpb24uYCxcbiAgICAgIHsgaWQsIGVuYWJsZWQsIGhhc1Rva2VuOiAhIXRva2VuLCBoYXNSZWZyZXNoVG9rZW46ICEhcmVmcmVzaFRva2VuIH1cbiAgICApO1xuICAgIC8vIE9yaWdpbmFsIGZ1bmN0aW9uIGltcGxpY2l0bHkgcmV0dXJucyB1bmRlZmluZWQsIGFuZCByZXNpbGllbnRHb3QgZm9yIFBPU1QgbWlnaHQgbm90IHJldHVybiBtZWFuaW5nZnVsIGRhdGEgdW5sZXNzIHNwZWNpZmllZC5cbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgYXBwU2VydmljZUxvZ2dlci5lcnJvcihcbiAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gVW5hYmxlIHRvIHVwZGF0ZSBjYWxlbmRhciBpbnRlZ3JhdGlvbi5gLFxuICAgICAgeyBpZCwgZXJyb3I6IGUubWVzc2FnZSwgc3RhY2s6IGUuc3RhY2ssIGRldGFpbHM6IGUgfVxuICAgICk7XG4gICAgLy8gcmVzaWxpZW50R290IHdpbGwgdGhyb3csIHRoaXMgY2F0Y2ggaXMgZm9yIGFueSBhZGRpdGlvbmFsIGhhbmRsaW5nXG4gICAgdGhyb3cgZTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHJlZnJlc2hHb29nbGVUb2tlbiA9IGFzeW5jIChcbiAgcmVmcmVzaFRva2VuOiBzdHJpbmcsXG4gIGNsaWVudFR5cGU6ICdpb3MnIHwgJ2FuZHJvaWQnIHwgJ3dlYicgfCAnYXRvbWljLXdlYidcbik6IFByb21pc2U8XG4gIHwge1xuICAgICAgYWNjZXNzX3Rva2VuOiBzdHJpbmc7XG4gICAgICBleHBpcmVzX2luOiBudW1iZXI7IC8vIGFkZCBzZWNvbmRzIHRvIG5vd1xuICAgICAgc2NvcGU6IHN0cmluZztcbiAgICAgIHRva2VuX3R5cGU6IHN0cmluZztcbiAgICB9XG4gIHwgdW5kZWZpbmVkXG4+ID0+IHtcbiAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdnZXRNaW5pbWFsQ2FsZW5kYXJJbnRlZ3JhdGlvbkJ5TmFtZSc7IC8vIENvcnJlY3RlZCBvcGVyYXRpb24gbmFtZVxuICB0cnkge1xuICAgIC8vIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbicgLy8gT3JpZ2luYWwgbmFtZSBpbiB0aGlzIGZ1bmNcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgIHF1ZXJ5IGdldE1pbmltYWxDYWxlbmRhckludGVncmF0aW9uQnlOYW1lKCR1c2VySWQ6IHV1aWQhLCAkbmFtZTogU3RyaW5nISkge1xuICAgICAgICBDYWxlbmRhcl9JbnRlZ3JhdGlvbih3aGVyZToge3VzZXJJZDoge19lcTogJHVzZXJJZH0sIG5hbWU6IHtfZXE6ICRuYW1lfX0pIHtcbiAgICAgICAgICAgIGFwcEFjY291bnRJZFxuICAgICAgICAgICAgYXBwRW1haWxcbiAgICAgICAgICAgIGFwcElkXG4gICAgICAgICAgICBjbGllbnRUeXBlXG4gICAgICAgICAgICBjb2xvcnNcbiAgICAgICAgICAgIGNvbnRhY3RFbWFpbFxuICAgICAgICAgICAgY29udGFjdEZpcnN0TmFtZVxuICAgICAgICAgICAgY29udGFjdExhc3ROYW1lXG4gICAgICAgICAgICBjb250YWN0TmFtZVxuICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICAgIGVuYWJsZWRcbiAgICAgICAgICAgIGV4cGlyZXNBdFxuICAgICAgICAgICAgaWRcbiAgICAgICAgICAgIG5hbWVcbiAgICAgICAgICAgIHBhZ2VUb2tlblxuICAgICAgICAgICAgcGFzc3dvcmRcbiAgICAgICAgICAgIHBob25lQ291bnRyeVxuICAgICAgICAgICAgcGhvbmVOdW1iZXJcbiAgICAgICAgICAgIHJlZnJlc2hUb2tlblxuICAgICAgICAgICAgcmVzb3VyY2VcbiAgICAgICAgICAgIHN5bmNFbmFibGVkXG4gICAgICAgICAgICBzeW5jVG9rZW5cbiAgICAgICAgICAgIHRva2VuXG4gICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgdXNlcm5hbWVcbiAgICAgICAgfVxuICAgICAgfVxuICAgIGA7XG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgdXNlcklkLFxuICAgICAgbmFtZSxcbiAgICB9O1xuXG4gICAgY29uc3Qgb3B0aW9ucyA9IHtcbiAgICAgIGpzb246IHsgb3BlcmF0aW9uTmFtZSwgcXVlcnksIHZhcmlhYmxlcyB9LFxuICAgICAgaGVhZGVyczoge1xuICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtQWRtaW4tU2VjcmV0JzogcG9zdGdyYXBoaWxlQWRtaW5TZWNyZXQsXG4gICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgIH0sXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlRGF0YSA9IChhd2FpdCByZXNpbGllbnRHb3QoXG4gICAgICAncG9zdCcsXG4gICAgICBwb3N0Z3JhcGhpbGVHcmFwaFVybCxcbiAgICAgIG9wdGlvbnMsXG4gICAgICBvcGVyYXRpb25OYW1lXG4gICAgKSkgYXMgeyBkYXRhPzogeyBDYWxlbmRhcl9JbnRlZ3JhdGlvbjogQ2FsZW5kYXJJbnRlZ3JhdGlvblR5cGVbXSB9IH07XG5cbiAgICBpZiAocmVzcG9uc2VEYXRhPy5kYXRhPy5DYWxlbmRhcl9JbnRlZ3JhdGlvbj8ubGVuZ3RoID4gMCkge1xuICAgICAgYXBwU2VydmljZUxvZ2dlci5kZWJ1ZyhcbiAgICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBGb3VuZCBpbnRlZ3JhdGlvbiBmb3IgdXNlcklkOiAke3VzZXJJZH0sIG5hbWU6ICR7bmFtZX0uYCxcbiAgICAgICAgeyBpbnRlZ3JhdGlvbklkOiByZXNwb25zZURhdGEuZGF0YS5DYWxlbmRhcl9JbnRlZ3JhdGlvblswXS5pZCB9XG4gICAgICApO1xuICAgICAgcmV0dXJuIHJlc3BvbnNlRGF0YS5kYXRhLkNhbGVuZGFyX0ludGVncmF0aW9uWzBdO1xuICAgIH0gZWxzZSB7XG4gICAgICBhcHBTZXJ2aWNlTG9nZ2VyLmluZm8oXG4gICAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gTm8gaW50ZWdyYXRpb24gZm91bmQgZm9yIHVzZXJJZDogJHt1c2VySWR9LCBuYW1lOiAke25hbWV9LmBcbiAgICAgICk7XG4gICAgICByZXR1cm4gdW5kZWZpbmVkO1xuICAgIH1cbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgYXBwU2VydmljZUxvZ2dlci5lcnJvcihcbiAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gVW5hYmxlIHRvIGdldCBjYWxlbmRhciBpbnRlZ3JhdGlvbiBieSBuYW1lLmAsXG4gICAgICB7IHVzZXJJZCwgbmFtZSwgZXJyb3I6IGUubWVzc2FnZSwgc3RhY2s6IGUuc3RhY2ssIGRldGFpbHM6IGUgfVxuICAgICk7XG4gICAgdGhyb3cgZTtcbiAgfVxufTtcblxuLyoqXG4gKiBxdWVyeSBnZXRDYWxlbmRhckludGVncmF0aW9uKCR1c2VySWQ6IHV1aWQhLCAkcmVzb3VyY2U6IFN0cmluZyEsICRjbGllbnRUeXBlOiBTdHJpbmchKSB7XG4gIENhbGVuZGFyX0ludGVncmF0aW9uKHdoZXJlOiB7dXNlcklkOiB7X2VxOiAkdXNlcklkfSwgcmVzb3VyY2U6IHtfZXE6ICRyZXNvdXJjZX0sIGNsaWVudFR5cGU6IHtfZXE6ICRjbGllbnRUeXBlfX0pIHtcbiAgICBhcHBBY2NvdW50SWRcbiAgICBhcHBFbWFpbFxuICAgIGFwcElkXG4gICAgY2xpZW50VHlwZVxuICAgIGNvbG9yc1xuICAgIGNvbnRhY3RFbWFpbFxuICAgIGNvbnRhY3RGaXJzdE5hbWVcbiAgICBjb250YWN0TGFzdE5hbWVcbiAgICBjb250YWN0TmFtZVxuICAgIGNyZWF0ZWREYXRlXG4gICAgZGVsZXRlZFxuICAgIGVuYWJsZWRcbiAgICBleHBpcmVzQXRcbiAgICBpZFxuICAgIG5hbWVcbiAgICBwYWdlVG9rZW5cbiAgICBwYXNzd29yZFxuICAgIHBob25lQ291bnRyeVxuICAgIHBob25lTnVtYmVyXG4gICAgcmVmcmVzaFRva2VuXG4gICAgcmVzb3VyY2VcbiAgICBzeW5jRW5hYmxlZFxuICAgIHN5bmNUb2tlblxuICAgIHRva2VuXG4gICAgdXBkYXRlZEF0XG4gICAgdXNlcklkXG4gICAgdXNlcm5hbWVcbiAgfVxufVxuXG4gKi9cblxuZXhwb3J0IGNvbnN0IGdldEFsbENhbGVuZGFySW50ZWdyYXRvbnNCeVJlc291cmNlQW5kQ2xpZW50VHlwZSA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHJlc291cmNlOiBzdHJpbmcsXG4gIGNsaWVudFR5cGU6ICdpb3MnIHwgJ2FuZHJvaWQnIHwgJ3dlYicgfCAnYXRvbWljLXdlYidcbikgPT4ge1xuICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2dldEFsbENhbGVuZGFySW50ZWdyYXRvbnNCeVJlc291cmNlQW5kQ2xpZW50VHlwZSc7IC8vIENvcnJlY3RlZCBuYW1lXG4gIHRyeSB7XG4gICAgLy8gY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdnZXRDYWxlbmRhckludGVncmF0aW9uQnlSZXNvdXJjZUFuZENsaWVudFR5cGUnIC8vIE9yaWdpbmFsIG5hbWVcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIHF1ZXJ5IGdldEFsbENhbGVuZGFySW50ZWdyYXRvbnNCeVJlc291cmNlQW5kQ2xpZW50VHlwZSgkdXNlcklkOiB1dWlkISwgJHJlc291cmNlOiBTdHJpbmchLCAkY2xpZW50VHlwZTogU3RyaW5nISkge1xuICAgICAgICAgICAgICAgIENhbGVuZGFyX0ludGVncmF0aW9uKHdoZXJlOiB7dXNlcklkOiB7X2VxOiAkdXNlcklkfSwgcmVzb3VyY2U6IHtfZXE6ICRyZXNvdXJjZX0sIGNsaWVudFR5cGU6IHtfZXE6ICRjbGllbnRUeXBlfX0pIHtcbiAgICAgICAgICAgICAgICBhcHBBY2NvdW50SWRcbiAgICAgICAgICAgICAgICBhcHBFbWFpbFxuICAgICAgICAgICAgICAgIGFwcElkXG4gICAgICAgICAgICAgICAgY2xpZW50VHlwZVxuICAgICAgICAgICAgICAgIGNvbG9yc1xuICAgICAgICAgICAgICAgIGNvbnRhY3RFbWFpbFxuICAgICAgICAgICAgICAgIGNvbnRhY3RGaXJzdE5hbWVcbiAgICAgICAgICAgICAgICBjb250YWN0TGFzdE5hbWVcbiAgICAgICAgICAgICAgICBjb250YWN0TmFtZVxuICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgICAgICAgIGVuYWJsZWRcbiAgICAgICAgICAgICAgICBleHBpcmVzQXRcbiAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgIG5hbWVcbiAgICAgICAgICAgICAgICBwYWdlVG9rZW5cbiAgICAgICAgICAgICAgICBwYXNzd29yZFxuICAgICAgICAgICAgICAgIHBob25lQ291bnRyeVxuICAgICAgICAgICAgICAgIHBob25lTnVtYmVyXG4gICAgICAgICAgICAgICAgcmVmcmVzaFRva2VuXG4gICAgICAgICAgICAgICAgcmVzb3VyY2VcbiAgICAgICAgICAgICAgICBzeW5jRW5hYmxlZFxuICAgICAgICAgICAgICAgIHN5bmNUb2tlblxuICAgICAgICAgICAgICAgIHRva2VuXG4gICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgdXNlcm5hbWVcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgIGA7XG5cbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICB1c2VySWQsXG4gICAgICByZXNvdXJjZSxcbiAgICAgIGNsaWVudFR5cGUsXG4gICAgfTtcblxuICAgIGNvbnN0IG9wdGlvbnMgPSB7XG4gICAgICBqc29uOiB7IG9wZXJhdGlvbk5hbWUsIHF1ZXJ5LCB2YXJpYWJsZXMgfSxcbiAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLUFkbWluLVNlY3JldCc6IHBvc3RncmFwaGlsZUFkbWluU2VjcmV0LFxuICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtUm9sZSc6ICdhZG1pbicsXG4gICAgICB9LFxuICAgIH07XG5cbiAgICBjb25zdCByZXNwb25zZURhdGEgPSAoYXdhaXQgcmVzaWxpZW50R290KFxuICAgICAgJ3Bvc3QnLFxuICAgICAgcG9zdGdyYXBoaWxlR3JhcGhVcmwsXG4gICAgICBvcHRpb25zLFxuICAgICAgb3BlcmF0aW9uTmFtZVxuICAgICkpIGFzIHsgZGF0YT86IHsgQ2FsZW5kYXJfSW50ZWdyYXRpb246IENhbGVuZGFySW50ZWdyYXRpb25UeXBlW10gfSB9O1xuXG4gICAgaWYgKHJlc3BvbnNlRGF0YT8uZGF0YT8uQ2FsZW5kYXJfSW50ZWdyYXRpb24/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGFwcFNlcnZpY2VMb2dnZXIuZGVidWcoXG4gICAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gRm91bmQgJHtyZXNwb25zZURhdGEuZGF0YS5DYWxlbmRhcl9JbnRlZ3JhdGlvbi5sZW5ndGh9IGludGVncmF0aW9ucy5gLFxuICAgICAgICB7IHVzZXJJZCwgcmVzb3VyY2UsIGNsaWVudFR5cGUgfVxuICAgICAgKTtcbiAgICAgIHJldHVybiByZXNwb25zZURhdGEuZGF0YS5DYWxlbmRhcl9JbnRlZ3JhdGlvbjtcbiAgICB9IGVsc2Uge1xuICAgICAgYXBwU2VydmljZUxvZ2dlci5pbmZvKGBbJHtvcGVyYXRpb25OYW1lfV0gTm8gaW50ZWdyYXRpb25zIGZvdW5kLmAsIHtcbiAgICAgICAgdXNlcklkLFxuICAgICAgICByZXNvdXJjZSxcbiAgICAgICAgY2xpZW50VHlwZSxcbiAgICAgIH0pO1xuICAgICAgcmV0dXJuIHVuZGVmaW5lZDsgLy8gT3IgYW4gZW1wdHkgYXJyYXkgW10gZGVwZW5kaW5nIG9uIGRlc2lyZWQgY29udHJhY3RcbiAgICB9XG4gIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgIGFwcFNlcnZpY2VMb2dnZXIuZXJyb3IoXG4gICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIFVuYWJsZSB0byBnZXQgY2FsZW5kYXIgaW50ZWdyYXRpb25zLmAsXG4gICAgICB7XG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgcmVzb3VyY2UsXG4gICAgICAgIGNsaWVudFR5cGUsXG4gICAgICAgIGVycm9yOiBlLm1lc3NhZ2UsXG4gICAgICAgIHN0YWNrOiBlLnN0YWNrLFxuICAgICAgICBkZXRhaWxzOiBlLFxuICAgICAgfVxuICAgICk7XG4gICAgdGhyb3cgZTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldEFsbENhbGVuZGFySW50ZWdyYXRpb25zQnlSZXNvdXJjZSA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHJlc291cmNlOiBzdHJpbmdcbikgPT4ge1xuICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2dldEFsbENhbGVuZGFySW50ZWdyYXRpb25zQnlSZXNvdXJjZSc7IC8vIENvcnJlY3RlZCBuYW1lXG4gIHRyeSB7XG4gICAgLy8gY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdnZXRDYWxlbmRhckludGVncmF0aW9uQnlSZXNvdXJjZScgLy8gT3JpZ2luYWwgbmFtZVxuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgcXVlcnkgZ2V0QWxsQ2FsZW5kYXJJbnRlZ3JhdGlvbnNCeVJlc291cmNlKCR1c2VySWQ6IHV1aWQhLCAkcmVzb3VyY2U6IFN0cmluZyEpIHtcbiAgICAgICAgQ2FsZW5kYXJfSW50ZWdyYXRpb24od2hlcmU6IHt1c2VySWQ6IHtfZXE6ICR1c2VySWR9LCByZXNvdXJjZToge19lcTogJHJlc291cmNlfX0pIHtcbiAgICAgICAgICAgIGFwcEFjY291bnRJZFxuICAgICAgICAgICAgYXBwRW1haWxcbiAgICAgICAgICAgIGFwcElkXG4gICAgICAgICAgICBjbGllbnRUeXBlXG4gICAgICAgICAgICBjb2xvcnNcbiAgICAgICAgICAgIGNvbnRhY3RFbWFpbFxuICAgICAgICAgICAgY29udGFjdEZpcnN0TmFtZVxuICAgICAgICAgICAgY29udGFjdExhc3ROYW1lXG4gICAgICAgICAgICBjb250YWN0TmFtZVxuICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICAgIGVuYWJsZWRcbiAgICAgICAgICAgIGV4cGlyZXNBdFxuICAgICAgICAgICAgaWRcbiAgICAgICAgICAgIG5hbWVcbiAgICAgICAgICAgIHBhZ2VUb2tlblxuICAgICAgICAgICAgcGFzc3dvcmRcbiAgICAgICAgICAgIHBob25lQ291bnRyeVxuICAgICAgICAgICAgcGhvbmVOdW1iZXJcbiAgICAgICAgICAgIHJlZnJlc2hUb2tlblxuICAgICAgICAgICAgcmVzb3VyY2VcbiAgICAgICAgICAgIHN5bmNFbmFibGVkXG4gICAgICAgICAgICBzeW5jVG9rZW5cbiAgICAgICAgICAgIHRva2VuXG4gICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgdXNlcm5hbWVcbiAgICAgICAgfVxuICAgICAgfVxuICAgIGA7XG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgdXNlcklkLFxuICAgICAgcmVzb3VyY2UsXG4gICAgfTtcblxuICAgIGNvbnN0IG9wdGlvbnMgPSB7XG4gICAgICBqc29uOiB7IG9wZXJhdGlvbk5hbWUsIHF1ZXJ5LCB2YXJpYWJsZXMgfSxcbiAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLUFkbWluLVNlY3JldCc6IHBvc3RncmFwaGlsZUFkbWluU2VjcmV0LFxuICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtUm9sZSc6ICdhZG1pbicsXG4gICAgICB9LFxuICAgIH07XG5cbiAgICBjb25zdCByZXNwb25zZURhdGEgPSAoYXdhaXQgcmVzaWxpZW50R290KFxuICAgICAgJ3Bvc3QnLFxuICAgICAgcG9zdGdyYXBoaWxlR3JhcGhVcmwsXG4gICAgICBvcHRpb25zLFxuICAgICAgb3BlcmF0aW9uTmFtZVxuICAgICkpIGFzIHsgZGF0YT86IHsgQ2FsZW5kYXJfSW50ZWdyYXRpb246IENhbGVuZGFySW50ZWdyYXRpb25UeXBlW10gfSB9O1xuXG4gICAgaWYgKHJlc3BvbnNlRGF0YT8uZGF0YT8uQ2FsZW5kYXJfSW50ZWdyYXRpb24/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGFwcFNlcnZpY2VMb2dnZXIuZGVidWcoXG4gICAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gRm91bmQgJHtyZXNwb25zZURhdGEuZGF0YS5DYWxlbmRhcl9JbnRlZ3JhdGlvbi5sZW5ndGh9IGludGVncmF0aW9ucy5gLFxuICAgICAgICB7IHVzZXJJZCwgcmVzb3VyY2UgfVxuICAgICAgKTtcbiAgICAgIHJldHVybiByZXNwb25zZURhdGEuZGF0YS5DYWxlbmRhcl9JbnRlZ3JhdGlvbjtcbiAgICB9IGVsc2Uge1xuICAgICAgYXBwU2VydmljZUxvZ2dlci5pbmZvKGBbJHtvcGVyYXRpb25OYW1lfV0gTm8gaW50ZWdyYXRpb25zIGZvdW5kLmAsIHtcbiAgICAgICAgdXNlcklkLFxuICAgICAgICByZXNvdXJjZSxcbiAgICAgIH0pO1xuICAgICAgcmV0dXJuIHVuZGVmaW5lZDsgLy8gT3IgYW4gZW1wdHkgYXJyYXkgW11cbiAgICB9XG4gIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgIGFwcFNlcnZpY2VMb2dnZXIuZXJyb3IoXG4gICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIFVuYWJsZSB0byBnZXQgYWxsIGNhbGVuZGFyIGludGVncmF0aW9ucyBieSByZXNvdXJjZS5gLFxuICAgICAgeyB1c2VySWQsIHJlc291cmNlLCBlcnJvcjogZS5tZXNzYWdlLCBzdGFjazogZS5zdGFjaywgZGV0YWlsczogZSB9XG4gICAgKTtcbiAgICB0aHJvdyBlO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0R29vZ2xlQ29sb3JzID0gYXN5bmMgKHRva2VuOiBzdHJpbmcpID0+IHtcbiAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdnZXRHb29nbGVDb2xvcnMnO1xuICB0cnkge1xuICAgIGNvbnN0IHVybCA9IGdvb2dsZUNvbG9yVXJsO1xuICAgIGNvbnN0IGNvbmZpZyA9IHtcbiAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke3Rva2VufWAsXG4gICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgIEFjY2VwdDogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgfSxcbiAgICAgIHJlc3BvbnNlVHlwZTogJ2pzb24nIGFzICdqc29uJywgLy8gRm9yIHJlc2lsaWVudEdvdFxuICAgIH07XG5cbiAgICBjb25zdCBkYXRhID0gKGF3YWl0IHJlc2lsaWVudEdvdChcbiAgICAgICdnZXQnLFxuICAgICAgdXJsLFxuICAgICAgY29uZmlnLFxuICAgICAgb3BlcmF0aW9uTmFtZVxuICAgICkpIGFzIGNvbG9yUmVzcG9uc2VUeXBlO1xuICAgIGFwcFNlcnZpY2VMb2dnZXIuZGVidWcoXG4gICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIFN1Y2Nlc3NmdWxseSBmZXRjaGVkIEdvb2dsZSBjb2xvcnMuYCxcbiAgICAgIHtcbiAgICAgICAgY2FsZW5kYXJDb2xvcnNDb3VudDogT2JqZWN0LmtleXMoZGF0YS5jYWxlbmRhciB8fCB7fSkubGVuZ3RoLFxuICAgICAgICBldmVudENvbG9yc0NvdW50OiBPYmplY3Qua2V5cyhkYXRhLmV2ZW50IHx8IHt9KS5sZW5ndGgsXG4gICAgICB9XG4gICAgKTtcbiAgICByZXR1cm4gZGF0YTtcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgYXBwU2VydmljZUxvZ2dlci5lcnJvcihgWyR7b3BlcmF0aW9uTmFtZX1dIFVuYWJsZSB0byBnZXQgR29vZ2xlIGNvbG9ycy5gLCB7XG4gICAgICBlcnJvcjogZS5tZXNzYWdlLFxuICAgICAgc3RhY2s6IGUuc3RhY2ssXG4gICAgICBkZXRhaWxzOiBlLFxuICAgIH0pO1xuICAgIHRocm93IGU7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCB0cmlnZ2VyR29vZ2xlUGVvcGxlU3luYyA9IGFzeW5jIChcbiAgY2FsZW5kYXJJbnRlZ3JhdGlvbklkOiBzdHJpbmcsXG4gIHVzZXJJZDogc3RyaW5nLFxuICByZXE6IE5leHRBcGlSZXF1ZXN0XG4pID0+IHtcbiAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICd0cmlnZ2VyR29vZ2xlUGVvcGxlU3luYyc7XG4gIHRyeSB7XG4gICAgYXBwU2VydmljZUxvZ2dlci5pbmZvKGBbJHtvcGVyYXRpb25OYW1lfV0gQ2FsbGVkLmAsIHtcbiAgICAgIGNhbGVuZGFySW50ZWdyYXRpb25JZCxcbiAgICAgIHVzZXJJZCxcbiAgICB9KTtcbiAgICBpZiAoIWNhbGVuZGFySW50ZWdyYXRpb25JZCkge1xuICAgICAgYXBwU2VydmljZUxvZ2dlci53YXJuKFxuICAgICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIE5vIGNhbGVuZGFySW50ZWdyYXRpb25JZCBwcm92aWRlZC5gXG4gICAgICApO1xuICAgICAgcmV0dXJuO1xuICAgIH1cblxuICAgIGlmICghdXNlcklkKSB7XG4gICAgICBhcHBTZXJ2aWNlTG9nZ2VyLndhcm4oYFske29wZXJhdGlvbk5hbWV9XSBObyB1c2VySWQgcHJvdmlkZWQuYCk7XG4gICAgICByZXR1cm47XG4gICAgfVxuICAgIGNvbnN0IHRva2VuUGF5bG9hZCA9IHJlcS5zZXNzaW9uPy5nZXRBY2Nlc3NUb2tlblBheWxvYWQoKTsgLy8gU2FmZWx5IGFjY2VzcyBzZXNzaW9uIGFuZCBwYXlsb2FkXG4gICAgY29uc3Qgc2Vzc2lvblRva2VuID0gdG9rZW5QYXlsb2FkOyAvLyBBc3N1bWluZyB0aGUgd2hvbGUgcGF5bG9hZCBtaWdodCBiZSB0aGUgdG9rZW4sIG9yIGFkanVzdCBpZiBpdCdzIGEgcHJvcGVydHkgbGlrZSB0b2tlblBheWxvYWQuand0XG5cbiAgICBpZiAoIXNlc3Npb25Ub2tlbikge1xuICAgICAgYXBwU2VydmljZUxvZ2dlci53YXJuKFxuICAgICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIE5vIGFjY2VzcyB0b2tlbiBmb3VuZCBpbiBzZXNzaW9uLmBcbiAgICAgICk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgY29uc3QgZGF0YSA9IHtcbiAgICAgIGNhbGVuZGFySW50ZWdyYXRpb25JZCxcbiAgICAgIHVzZXJJZCxcbiAgICAgIGlzSW5pdGlhbFN5bmM6IHRydWUsXG4gICAgfTtcblxuICAgIGNvbnN0IHVybCA9IGdvb2dsZVBlb3BsZVN5bmNVcmw7XG5cbiAgICBjb25zdCBvcHRpb25zID0ge1xuICAgICAganNvbjogZGF0YSxcbiAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke3Nlc3Npb25Ub2tlbn1gLCAvLyBVc2UgdGhlIHNlc3Npb24gdG9rZW5cbiAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgIH0sXG4gICAgICByZXNwb25zZVR5cGU6ICdqc29uJyBhcyAnanNvbicsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3VsdHMgPSBhd2FpdCByZXNpbGllbnRHb3QoJ3Bvc3QnLCB1cmwsIG9wdGlvbnMsIG9wZXJhdGlvbk5hbWUpO1xuXG4gICAgYXBwU2VydmljZUxvZ2dlci5pbmZvKFxuICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBTdWNjZXNzZnVsbHkgdHJpZ2dlcmVkIEdvb2dsZSBwZW9wbGUgc3luYy5gLFxuICAgICAgeyBjYWxlbmRhckludGVncmF0aW9uSWQsIHVzZXJJZCwgcmVzdWx0cyB9XG4gICAgKTtcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgYXBwU2VydmljZUxvZ2dlci5lcnJvcihcbiAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gVW5hYmxlIHRvIHRyaWdnZXIgR29vZ2xlIHBlb3BsZSBzeW5jLmAsXG4gICAgICB7XG4gICAgICAgIGNhbGVuZGFySW50ZWdyYXRpb25JZCxcbiAgICAgICAgdXNlcklkLFxuICAgICAgICBlcnJvcjogZS5tZXNzYWdlLFxuICAgICAgICBjb2RlOiBlLmNvZGUsXG4gICAgICAgIHJlc3BvbnNlQm9keTogZT8ucmVzcG9uc2U/LmJvZHksXG4gICAgICAgIHN0YWNrOiBlLnN0YWNrLFxuICAgICAgfVxuICAgICk7XG4gICAgdGhyb3cgZTtcbiAgfVxufTtcbmV4cG9ydCBjb25zdCB1cGRhdGVHb29nbGVJbnRlZ3JhdGlvbiA9IGFzeW5jIChcbiAgaWQ6IHN0cmluZyxcbiAgZW5hYmxlZD86IGJvb2xlYW4sXG4gIHRva2VuPzogc3RyaW5nLFxuICByZWZyZXNoVG9rZW4/OiBzdHJpbmcsXG4gIGV4cGlyZXNBdD86IHN0cmluZyxcbiAgc3luY0VuYWJsZWQ/OiBib29sZWFuLFxuICBjb2xvcnM/OiBjb2xvclR5cGVbXSxcbiAgcGFnZVRva2VuPzogc3RyaW5nLFxuICBzeW5jVG9rZW4/OiBzdHJpbmcsXG4gIGNsaWVudFR5cGU/OiAnaW9zJyB8ICdhbmRyb2lkJyB8ICd3ZWInIHwgJ2F0b21pYy13ZWInXG4pID0+IHtcbiAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICd1cGRhdGVHb29nbGVJbnRlZ3JhdGlvbic7IC8vIENvcnJlY3RlZCBuYW1lXG4gIHRyeSB7XG4gICAgLy8gY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdVcGRhdGVDYWxlbmRhckludGVncmF0aW9uQnlJZCcgLy8gT3JpZ2luYWwgbmFtZVxuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgbXV0YXRpb24gdXBkYXRlR29vZ2xlSW50ZWdyYXRpb24oJGlkOiB1dWlkISxcbiAgICAgICAgICAgICAgICAke2VuYWJsZWQgIT09IHVuZGVmaW5lZCA/ICckZW5hYmxlZDogQm9vbGVhbiwnIDogJyd9XG4gICAgICAgICAgICAgICAgJHtleHBpcmVzQXQgIT09IHVuZGVmaW5lZCA/ICckZXhwaXJlc0F0OiB0aW1lc3RhbXB0eiwnIDogJyd9XG4gICAgICAgICAgICAgICAgJHtyZWZyZXNoVG9rZW4gIT09IHVuZGVmaW5lZCA/ICckcmVmcmVzaFRva2VuOiBTdHJpbmcsJyA6ICcnfVxuICAgICAgICAgICAgICAgICR7dG9rZW4gIT09IHVuZGVmaW5lZCA/ICckdG9rZW46IFN0cmluZywnIDogJyd9XG4gICAgICAgICAgICAgICAgJHtzeW5jRW5hYmxlZCAhPT0gdW5kZWZpbmVkID8gJyRzeW5jRW5hYmxlZDogQm9vbGVhbiwnIDogJyd9XG4gICAgICAgICAgICAgICAgJHtjb2xvcnMgIT09IHVuZGVmaW5lZCA/ICckY29sb3JzOiBqc29uYiwnIDogJyd9XG4gICAgICAgICAgICAgICAgJHtwYWdlVG9rZW4gIT09IHVuZGVmaW5lZCA/ICckcGFnZVRva2VuOiBTdHJpbmcsJyA6ICcnfVxuICAgICAgICAgICAgICAgICR7c3luY1Rva2VuICE9PSB1bmRlZmluZWQgPyAnJHN5bmNUb2tlbjogU3RyaW5nLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAke2NsaWVudFR5cGUgIT09IHVuZGVmaW5lZCA/ICckY2xpZW50VHlwZTogU3RyaW5nLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAkdXBkYXRlZEF0OiB0aW1lc3RhbXB0eikge1xuICAgICAgICAgICAgICAgIHVwZGF0ZV9DYWxlbmRhcl9JbnRlZ3JhdGlvbl9ieV9wayhfc2V0OiB7XG4gICAgICAgICAgICAgICAgICAgICR7ZW5hYmxlZCAhPT0gdW5kZWZpbmVkID8gJ2VuYWJsZWQ6ICRlbmFibGVkLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICAgJHtleHBpcmVzQXQgIT09IHVuZGVmaW5lZCA/ICdleHBpcmVzQXQ6ICRleHBpcmVzQXQsJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICAke3JlZnJlc2hUb2tlbiAhPT0gdW5kZWZpbmVkID8gJ3JlZnJlc2hUb2tlbjogJHJlZnJlc2hUb2tlbiwnIDogJyd9XG4gICAgICAgICAgICAgICAgICAgICR7dG9rZW4gIT09IHVuZGVmaW5lZCA/ICd0b2tlbjogJHRva2VuLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICAgJHtzeW5jRW5hYmxlZCAhPT0gdW5kZWZpbmVkID8gJ3N5bmNFbmFibGVkOiAkc3luY0VuYWJsZWQsJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICAke2NvbG9ycyAhPT0gdW5kZWZpbmVkID8gJ2NvbG9yczogJGNvbG9ycywnIDogJyd9XG4gICAgICAgICAgICAgICAgICAgICR7cGFnZVRva2VuICE9PSB1bmRlZmluZWQgPyAncGFnZVRva2VuOiAkcGFnZVRva2VuLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICAgJHtzeW5jVG9rZW4gIT09IHVuZGVmaW5lZCA/ICdzeW5jVG9rZW46ICRzeW5jVG9rZW4sJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICAke2NsaWVudFR5cGUgIT09IHVuZGVmaW5lZCA/ICdjbGllbnRUeXBlOiAkY2xpZW50VHlwZSwnIDogJyd9XG4gICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdDogJHVwZGF0ZWRBdH0sIHBrX2NvbHVtbnM6IHtpZDogJGlkfSkge1xuICAgICAgICAgICAgICAgICAgICBhcHBBY2NvdW50SWRcbiAgICAgICAgICAgICAgICAgICAgYXBwRW1haWxcbiAgICAgICAgICAgICAgICAgICAgYXBwSWRcbiAgICAgICAgICAgICAgICAgICAgY29sb3JzXG4gICAgICAgICAgICAgICAgICAgIGNvbnRhY3RFbWFpbFxuICAgICAgICAgICAgICAgICAgICBjb250YWN0TmFtZVxuICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICBkZWxldGVkXG4gICAgICAgICAgICAgICAgICAgIGVuYWJsZWRcbiAgICAgICAgICAgICAgICAgICAgZXhwaXJlc0F0XG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIG5hbWVcbiAgICAgICAgICAgICAgICAgICAgcGFnZVRva2VuXG4gICAgICAgICAgICAgICAgICAgIHBhc3N3b3JkXG4gICAgICAgICAgICAgICAgICAgIHJlZnJlc2hUb2tlblxuICAgICAgICAgICAgICAgICAgICBzeW5jRW5hYmxlZFxuICAgICAgICAgICAgICAgICAgICByZXNvdXJjZVxuICAgICAgICAgICAgICAgICAgICB0b2tlblxuICAgICAgICAgICAgICAgICAgICBzeW5jVG9rZW5cbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgICAgICAgICB1c2VybmFtZVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGxldCB2YXJpYWJsZXM6IGFueSA9IHtcbiAgICAgIGlkLFxuICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIH07XG5cbiAgICBpZiAoZW5hYmxlZCAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMuZW5hYmxlZCA9IGVuYWJsZWQ7XG4gICAgfVxuICAgIGlmIChleHBpcmVzQXQgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLmV4cGlyZXNBdCA9XG4gICAgICAgIGV4cGlyZXNBdCA9PT0gbnVsbCA/IG51bGwgOiBkYXlqcyhleHBpcmVzQXQpLmZvcm1hdCgpO1xuICAgIH1cbiAgICBpZiAocmVmcmVzaFRva2VuICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5yZWZyZXNoVG9rZW4gPSByZWZyZXNoVG9rZW47XG4gICAgfVxuICAgIGlmICh0b2tlbiAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMudG9rZW4gPSB0b2tlbjtcbiAgICB9XG4gICAgaWYgKHN5bmNFbmFibGVkICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5zeW5jRW5hYmxlZCA9IHN5bmNFbmFibGVkO1xuICAgIH1cbiAgICBpZiAoY29sb3JzICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5jb2xvcnMgPSBjb2xvcnM7XG4gICAgfVxuICAgIGlmIChwYWdlVG9rZW4gIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLnBhZ2VUb2tlbiA9IHBhZ2VUb2tlbjtcbiAgICB9XG4gICAgaWYgKHN5bmNUb2tlbiAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMuc3luY1Rva2VuID0gc3luY1Rva2VuO1xuICAgIH1cbiAgICBpZiAoY2xpZW50VHlwZSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMuY2xpZW50VHlwZSA9IGNsaWVudFR5cGU7XG4gICAgfVxuXG4gICAgY29uc3Qgb3B0aW9ucyA9IHtcbiAgICAgIGpzb246IHsgb3BlcmF0aW9uTmFtZSwgcXVlcnksIHZhcmlhYmxlcyB9LFxuICAgICAgaGVhZGVyczoge1xuICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtQWRtaW4tU2VjcmV0JzogcG9zdGdyYXBoaWxlQWRtaW5TZWNyZXQsXG4gICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgIH0sXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlRGF0YSA9IChhd2FpdCByZXNpbGllbnRHb3QoXG4gICAgICAncG9zdCcsXG4gICAgICBwb3N0Z3JhcGhpbGVHcmFwaFVybCxcbiAgICAgIG9wdGlvbnMsXG4gICAgICBvcGVyYXRpb25OYW1lXG4gICAgKSkgYXMge1xuICAgICAgZGF0YT86IHsgdXBkYXRlX0NhbGVuZGFyX0ludGVncmF0aW9uX2J5X3BrOiBDYWxlbmRhckludGVncmF0aW9uVHlwZSB9O1xuICAgIH07XG5cbiAgICBhcHBTZXJ2aWNlTG9nZ2VyLmluZm8oXG4gICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIFN1Y2Nlc3NmdWxseSB1cGRhdGVkIEdvb2dsZSBDYWxlbmRhciBpbnRlZ3JhdGlvbi5gLFxuICAgICAge1xuICAgICAgICBpbnRlZ3JhdGlvbklkOlxuICAgICAgICAgIHJlc3BvbnNlRGF0YT8uZGF0YT8udXBkYXRlX0NhbGVuZGFyX0ludGVncmF0aW9uX2J5X3BrPy5pZCxcbiAgICAgICAgZW5hYmxlZCxcbiAgICAgIH1cbiAgICApO1xuICAgIHJldHVybiByZXNwb25zZURhdGE/LmRhdGE/LnVwZGF0ZV9DYWxlbmRhcl9JbnRlZ3JhdGlvbl9ieV9waztcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgYXBwU2VydmljZUxvZ2dlci5lcnJvcihcbiAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gVW5hYmxlIHRvIHVwZGF0ZSBHb29nbGUgQ2FsZW5kYXIgaW50ZWdyYXRpb24uYCxcbiAgICAgIHsgaWQsIGVycm9yOiBlLm1lc3NhZ2UsIHN0YWNrOiBlLnN0YWNrLCBkZXRhaWxzOiBlIH1cbiAgICApO1xuICAgIHRocm93IGU7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBzY2hlZHVsZU1lZXRpbmcgPSBhc3luYyAoXG4gIHBheWxvYWQ6IFNjaGVkdWxlTWVldGluZ1JlcXVlc3RUeXBlLFxuICBjbGllbnRUeXBlOiAnaW9zJyB8ICdhbmRyb2lkJyB8ICd3ZWInIHwgJ2F0b21pYy13ZWInXG4pID0+IHtcbiAgbGV0IGludGVncmF0aW9uSWQgPSAnJztcbiAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdnZXRHb29nbGVBUElUb2tlbic7XG4gIHRyeSB7XG4gICAgYXBwU2VydmljZUxvZ2dlci5pbmZvKFxuICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBBdHRlbXB0aW5nIHRvIGdldCBHb29nbGUgQVBJIHRva2VuLmAsXG4gICAgICB7IHVzZXJJZCwgcmVzb3VyY2UsIGNsaWVudFR5cGUgfVxuICAgICk7XG4gICAgY29uc3QgaW50ZWdyYXRpb24gPSBhd2FpdCBnZXRNaW5pbWFsQ2FsZW5kYXJJbnRlZ3JhdGlvbkJ5UmVzb3VyY2UoXG4gICAgICB1c2VySWQsXG4gICAgICByZXNvdXJjZVxuICAgICk7XG5cbiAgICBpZiAoIWludGVncmF0aW9uKSB7XG4gICAgICBhcHBTZXJ2aWNlTG9nZ2VyLndhcm4oXG4gICAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gTm8gY2FsZW5kYXIgaW50ZWdyYXRpb24gZm91bmQuYCxcbiAgICAgICAgeyB1c2VySWQsIHJlc291cmNlIH1cbiAgICAgICk7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ05vIGNhbGVuZGFyIGludGVncmF0aW9uIGF2YWlsYWJsZS4nKTtcbiAgICB9XG4gICAgaW50ZWdyYXRpb25JZCA9IGludGVncmF0aW9uLmlkOyAvLyBBc3NpZ24gaW50ZWdyYXRpb25JZCBoZXJlIG9uY2UgJ2ludGVncmF0aW9uJyBpcyBjb25maXJtZWQgdG8gZXhpc3RcblxuICAgIGlmICghaW50ZWdyYXRpb24ucmVmcmVzaFRva2VuKSB7XG4gICAgICBhcHBTZXJ2aWNlTG9nZ2VyLndhcm4oXG4gICAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gTm8gcmVmcmVzaCB0b2tlbiBmb3VuZCBmb3IgaW50ZWdyYXRpb24uYCxcbiAgICAgICAgeyB1c2VySWQsIHJlc291cmNlLCBpbnRlZ3JhdGlvbklkIH1cbiAgICAgICk7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ05vIHJlZnJlc2ggdG9rZW4gcHJvdmlkZWQgZnJvbSBjYWxlbmRhciBpbnRlZ3JhdGlvbi4nKTtcbiAgICB9XG5cbiAgICBhcHBTZXJ2aWNlTG9nZ2VyLmRlYnVnKFxuICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBJbnRlZ3JhdGlvbiBmb3VuZC4gQ2hlY2tpbmcgdG9rZW4gdmFsaWRpdHkuYCxcbiAgICAgIHtcbiAgICAgICAgdXNlcklkLFxuICAgICAgICByZXNvdXJjZSxcbiAgICAgICAgaW50ZWdyYXRpb25JZCxcbiAgICAgICAgZXhwaXJlc0F0OiBpbnRlZ3JhdGlvbi5leHBpcmVzQXQsXG4gICAgICAgIHRva2VuRXhpc3RzOiAhIWludGVncmF0aW9uLnRva2VuLFxuICAgICAgfVxuICAgICk7XG5cbiAgICBpZiAoZGF5anMoKS5pc0FmdGVyKGRheWpzKGludGVncmF0aW9uLmV4cGlyZXNBdCkpIHx8ICFpbnRlZ3JhdGlvbi50b2tlbikge1xuICAgICAgYXBwU2VydmljZUxvZ2dlci5pbmZvKFxuICAgICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIFRva2VuIGV4cGlyZWQgb3IgbWlzc2luZy4gQXR0ZW1wdGluZyByZWZyZXNoLmAsXG4gICAgICAgIHsgdXNlcklkLCByZXNvdXJjZSwgaW50ZWdyYXRpb25JZCB9XG4gICAgICApO1xuICAgICAgY29uc3QgcmVmcmVzaFJlc3BvbnNlID0gYXdhaXQgcmVmcmVzaEdvb2dsZVRva2VuKFxuICAgICAgICBpbnRlZ3JhdGlvbi5yZWZyZXNoVG9rZW4sXG4gICAgICAgIGNsaWVudFR5cGVcbiAgICAgICk7XG5cbiAgICAgIGlmIChyZWZyZXNoUmVzcG9uc2UgJiYgcmVmcmVzaFJlc3BvbnNlLmFjY2Vzc190b2tlbikge1xuICAgICAgICBhcHBTZXJ2aWNlTG9nZ2VyLmluZm8oXG4gICAgICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBUb2tlbiByZWZyZXNoIHN1Y2Nlc3NmdWwuIFVwZGF0aW5nIGludGVncmF0aW9uLmAsXG4gICAgICAgICAgeyB1c2VySWQsIHJlc291cmNlLCBpbnRlZ3JhdGlvbklkIH1cbiAgICAgICAgKTtcbiAgICAgICAgYXdhaXQgdXBkYXRlQWNjZXNzVG9rZW5DYWxlbmRhckludGVncmF0aW9uKFxuICAgICAgICAgIGludGVncmF0aW9uSWQsXG4gICAgICAgICAgcmVmcmVzaFJlc3BvbnNlLmFjY2Vzc190b2tlbixcbiAgICAgICAgICByZWZyZXNoUmVzcG9uc2UuZXhwaXJlc19pblxuICAgICAgICApO1xuICAgICAgICByZXR1cm4gcmVmcmVzaFJlc3BvbnNlLmFjY2Vzc190b2tlbjtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIGFwcFNlcnZpY2VMb2dnZXIud2FybihcbiAgICAgICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIFRva2VuIHJlZnJlc2ggZmFpbGVkIG9yIHJldHVybmVkIG5vIGFjY2Vzc190b2tlbi5gLFxuICAgICAgICAgIHsgdXNlcklkLCByZXNvdXJjZSwgaW50ZWdyYXRpb25JZCB9XG4gICAgICAgICk7XG4gICAgICAgIC8vIFBvdGVudGlhbGx5IHRocm93IGFuIGVycm9yIGhlcmUgaWYgdG9rZW4gcmVmcmVzaCBpcyBjcml0aWNhbCBhbmQgZmFpbGVkXG4gICAgICAgIHRocm93IG5ldyBFcnJvcignVG9rZW4gcmVmcmVzaCBmYWlsZWQgdG8gcmV0dXJuIGFuIGFjY2VzcyB0b2tlbi4nKTtcbiAgICAgIH1cbiAgICB9XG4gICAgYXBwU2VydmljZUxvZ2dlci5pbmZvKGBbJHtvcGVyYXRpb25OYW1lfV0gRXhpc3RpbmcgdG9rZW4gaXMgdmFsaWQuYCwge1xuICAgICAgdXNlcklkLFxuICAgICAgcmVzb3VyY2UsXG4gICAgICBpbnRlZ3JhdGlvbklkLFxuICAgIH0pO1xuICAgIHJldHVybiBpbnRlZ3JhdGlvbi50b2tlbjtcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgYXBwU2VydmljZUxvZ2dlci5lcnJvcihcbiAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gRXJyb3IgZ2V0dGluZyBHb29nbGUgQVBJIHRva2VuLmAsXG4gICAgICB7XG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgcmVzb3VyY2UsXG4gICAgICAgIGNsaWVudFR5cGUsXG4gICAgICAgIGludGVncmF0aW9uSWRPbkVycm9yOiBpbnRlZ3JhdGlvbklkLFxuICAgICAgICBlcnJvcjogZS5tZXNzYWdlLFxuICAgICAgICBzdGFjazogZS5zdGFjayxcbiAgICAgICAgZGV0YWlsczogZSxcbiAgICAgIH1cbiAgICApO1xuICAgIGlmIChpbnRlZ3JhdGlvbklkKSB7XG4gICAgICAvLyBBdHRlbXB0IHRvIGRpc2FibGUgb25seSBpZiBpbnRlZ3JhdGlvbklkIHdhcyBzZXRcbiAgICAgIHRyeSB7XG4gICAgICAgIGFwcFNlcnZpY2VMb2dnZXIuaW5mbyhcbiAgICAgICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIEF0dGVtcHRpbmcgdG8gZGlzYWJsZSBpbnRlZ3JhdGlvbiBkdWUgdG8gZXJyb3IuYCxcbiAgICAgICAgICB7IGludGVncmF0aW9uSWQgfVxuICAgICAgICApO1xuICAgICAgICBhd2FpdCB1cGRhdGVBY2Nlc3NUb2tlbkNhbGVuZGFySW50ZWdyYXRpb24oXG4gICAgICAgICAgaW50ZWdyYXRpb25JZCxcbiAgICAgICAgICBudWxsLFxuICAgICAgICAgIG51bGwsXG4gICAgICAgICAgZmFsc2VcbiAgICAgICAgKTtcbiAgICAgIH0gY2F0Y2ggKGRpc2FibGVFcnJvcjogYW55KSB7XG4gICAgICAgIGFwcFNlcnZpY2VMb2dnZXIuZXJyb3IoXG4gICAgICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBGYWlsZWQgdG8gZGlzYWJsZSBpbnRlZ3JhdGlvbiBhZnRlciBlcnJvci5gLFxuICAgICAgICAgIHtcbiAgICAgICAgICAgIGludGVncmF0aW9uSWQsXG4gICAgICAgICAgICBkaXNhYmxlRXJyb3I6IGRpc2FibGVFcnJvci5tZXNzYWdlLFxuICAgICAgICAgICAgc3RhY2s6IGRpc2FibGVFcnJvci5zdGFjayxcbiAgICAgICAgICB9XG4gICAgICAgICk7XG4gICAgICB9XG4gICAgfVxuICAgIHRocm93IGU7IC8vIFJlLXRocm93IHRoZSBvcmlnaW5hbCBlcnJvciBvciBhIG5ldyBvbmVcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGRlY3J5cHRab29tVG9rZW5zID0gKFxuICBlbmNyeXB0ZWRUb2tlbjogc3RyaW5nLFxuICBlbmNyeXB0ZWRSZWZyZXNoVG9rZW4/OiBzdHJpbmdcbikgPT4ge1xuICBjb25zdCBpdkJ1ZmZlciA9IEJ1ZmZlci5mcm9tKHpvb21JVkZvclBhc3MsICdiYXNlNjQnKTtcbiAgY29uc3Qgc2FsdEJ1ZmZlciA9IEJ1ZmZlci5mcm9tKHpvb21TYWx0Rm9yUGFzcywgJ2Jhc2U2NCcpO1xuXG4gIGNvbnN0IGtleSA9IGNyeXB0by5wYmtkZjJTeW5jKFxuICAgIHpvb21QYXNzS2V5IGFzIHN0cmluZyxcbiAgICBzYWx0QnVmZmVyLFxuICAgIDEwMDAwLFxuICAgIDMyLFxuICAgICdzaGEyNTYnXG4gICk7XG5cbiAgY29uc3QgZGVjaXBoZXJUb2tlbiA9IGNyeXB0by5jcmVhdGVEZWNpcGhlcml2KCdhZXMtMjU2LWNiYycsIGtleSwgaXZCdWZmZXIpO1xuICBsZXQgZGVjcnlwdGVkVG9rZW4gPSBkZWNpcGhlclRva2VuLnVwZGF0ZShlbmNyeXB0ZWRUb2tlbiwgJ2Jhc2U2NCcsICd1dGY4Jyk7XG4gIGRlY3J5cHRlZFRva2VuICs9IGRlY2lwaGVyVG9rZW4uZmluYWwoJ3V0ZjgnKTtcblxuICBpZiAoZW5jcnlwdGVkUmVmcmVzaFRva2VuKSB7XG4gICAgY29uc3QgZGVjaXBoZXJSZWZyZXNoVG9rZW4gPSBjcnlwdG8uY3JlYXRlRGVjaXBoZXJpdihcbiAgICAgICdhZXMtMjU2LWNiYycsXG4gICAgICBrZXksXG4gICAgICBpdkJ1ZmZlclxuICAgICk7XG4gICAgbGV0IGRlY3J5cHRlZFJlZnJlc2hUb2tlbiA9IGRlY2lwaGVyUmVmcmVzaFRva2VuLnVwZGF0ZShcbiAgICAgIGVuY3J5cHRlZFJlZnJlc2hUb2tlbixcbiAgICAgICdiYXNlNjQnLFxuICAgICAgJ3V0ZjgnXG4gICAgKTtcbiAgICBkZWNyeXB0ZWRSZWZyZXNoVG9rZW4gKz0gZGVjaXBoZXJSZWZyZXNoVG9rZW4uZmluYWwoJ3V0ZjgnKTtcblxuICAgIHJldHVybiB7XG4gICAgICB0b2tlbjogZGVjcnlwdGVkVG9rZW4sXG4gICAgICByZWZyZXNoVG9rZW46IGRlY3J5cHRlZFJlZnJlc2hUb2tlbixcbiAgICB9O1xuICB9XG5cbiAgcmV0dXJuIHtcbiAgICB0b2tlbjogZGVjcnlwdGVkVG9rZW4sXG4gIH07XG59O1xuXG5leHBvcnQgY29uc3QgZW5jcnlwdFpvb21Ub2tlbnMgPSAodG9rZW46IHN0cmluZywgcmVmcmVzaFRva2VuPzogc3RyaW5nKSA9PiB7XG4gIGNvbnN0IGl2QnVmZmVyID0gQnVmZmVyLmZyb20oem9vbUlWRm9yUGFzcywgJ2Jhc2U2NCcpO1xuICBjb25zdCBzYWx0QnVmZmVyID0gQnVmZmVyLmZyb20oem9vbVNhbHRGb3JQYXNzLCAnYmFzZTY0Jyk7XG5cbiAgY29uc3Qga2V5ID0gY3J5cHRvLnBia2RmMlN5bmMoXG4gICAgem9vbVBhc3NLZXkgYXMgc3RyaW5nLFxuICAgIHNhbHRCdWZmZXIsXG4gICAgMTAwMDAsXG4gICAgMzIsXG4gICAgJ3NoYTI1NidcbiAgKTtcbiAgY29uc3QgY2lwaGVyVG9rZW4gPSBjcnlwdG8uY3JlYXRlQ2lwaGVyaXYoJ2Flcy0yNTYtY2JjJywga2V5LCBpdkJ1ZmZlcik7XG4gIGxldCBlbmNyeXB0ZWRUb2tlbiA9IGNpcGhlclRva2VuLnVwZGF0ZSh0b2tlbiwgJ3V0ZjgnLCAnYmFzZTY0Jyk7XG4gIGVuY3J5cHRlZFRva2VuICs9IGNpcGhlclRva2VuLmZpbmFsKCdiYXNlNjQnKTtcblxuICBsZXQgZW5jcnlwdGVkUmVmcmVzaFRva2VuID0gJyc7XG5cbiAgaWYgKHJlZnJlc2hUb2tlbikge1xuICAgIGNvbnN0IGNpcGhlclJlZnJlc2hUb2tlbiA9IGNyeXB0by5jcmVhdGVDaXBoZXJpdihcbiAgICAgICdhZXMtMjU2LWNiYycsXG4gICAgICBrZXksXG4gICAgICBpdkJ1ZmZlclxuICAgICk7XG4gICAgZW5jcnlwdGVkUmVmcmVzaFRva2VuID0gY2lwaGVyUmVmcmVzaFRva2VuLnVwZGF0ZShcbiAgICAgIHJlZnJlc2hUb2tlbixcbiAgICAgICd1dGY4JyxcbiAgICAgICdiYXNlNjQnXG4gICAgKTtcbiAgICBlbmNyeXB0ZWRSZWZyZXNoVG9rZW4gKz0gY2lwaGVyUmVmcmVzaFRva2VuLmZpbmFsKCdiYXNlNjQnKTtcbiAgfVxuXG4gIGlmIChlbmNyeXB0ZWRSZWZyZXNoVG9rZW4pIHtcbiAgICByZXR1cm4ge1xuICAgICAgZW5jcnlwdGVkVG9rZW4sXG4gICAgICBlbmNyeXB0ZWRSZWZyZXNoVG9rZW4sXG4gICAgfTtcbiAgfSBlbHNlIHtcbiAgICByZXR1cm4geyBlbmNyeXB0ZWRUb2tlbiB9O1xuICB9XG59O1xuXG4vLyBUaGlzIGZ1bmN0aW9uIHdhcyBwcmV2aW91c2x5IGp1c3QgZm9yIFpvb20gYnV0IHNlZW1zIGdlbmVyaWMgZW5vdWdoIGZvciBhbnkgQ2FsZW5kYXJfSW50ZWdyYXRpb24gYnkgSUQuXG4vLyBIb3dldmVyLCBpdCBlbmNyeXB0cyB0b2tlbnMgc3BlY2lmaWNhbGx5IGZvciBab29tLlxuLy8gVGhlIG9yaWdpbmFsIGB1cGRhdGVDYWxlbmRhckludGVncmF0aW9uYCBpbiBgYXBpLWhlbHBlci50c2AgaXMgZm9yIGdlbmVyaWMgQXBvbGxvIGNsaWVudCB1cGRhdGVzLlxuLy8gVGhpcyBgdXBkYXRlWm9vbUludGVncmF0aW9uYCBpbiBgYXBpLWJhY2tlbmQtaGVscGVyLnRzYCBpcyBzZXJ2ZXItc2lkZSBhbmQgdXNlcyBgZ290YC5cbi8vIEl0IG1pZ2h0IGJlIGJldHRlciBuYW1lZCBpZiBpdCdzIHRydWx5IFpvb20gc3BlY2lmaWMgZHVlIHRvIGVuY3J5cHRpb24uXG4vLyBGb3Igbm93LCBqdXN0IHJlcGxhY2luZyBjb25zb2xlLmxvZy4gUmVzaWxpZW5jZSBmb3IgdGhlIGBnb3RgIGNhbGwgd2lsbCBiZSBhZGRlZCBsYXRlci5cbmV4cG9ydCBjb25zdCB1cGRhdGVab29tSW50ZWdyYXRpb24gPSBhc3luYyAoXG4gIGlkOiBzdHJpbmcsXG4gIGFwcEFjY291bnRJZDogc3RyaW5nLFxuICBhcHBFbWFpbDogc3RyaW5nLFxuICBhcHBJZDogc3RyaW5nLFxuICB0b2tlbjogc3RyaW5nIHwgbnVsbCxcbiAgZXhwaXJlc0luOiBudW1iZXIgfCBudWxsLFxuICByZWZyZXNoVG9rZW4/OiBzdHJpbmcsXG4gIGNvbnRhY3RGaXJzdE5hbWU/OiBzdHJpbmcsXG4gIGNvbnRhY3RMYXN0TmFtZT86IHN0cmluZyxcbiAgcGhvbmVDb3VudHJ5Pzogc3RyaW5nLCAvLyAnVVMnXG4gIHBob25lTnVtYmVyPzogc3RyaW5nLCAvLyAnKzEgMTIzNDU2Nzg5MSdcbiAgZW5hYmxlZD86IGJvb2xlYW5cbikgPT4ge1xuICB0cnkge1xuICAgIC8vJHt0b2tlbiAhPT0gdW5kZWZpbmVkID8gJyAkdG9rZW46IFN0cmluZywnIDogJyd9XG4gICAgLy9cbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ3VwZGF0ZUNhbGVuZGFySW50ZWdyYXRpb25CeUlkJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIG11dGF0aW9uIHVwZGF0ZUNhbGVuZGFySW50ZWdyYXRpb25CeUlkKFxuICAgICAgICAgICAgICAgICAgICAkaWQ6IHV1aWQhLFxuICAgICAgICAgICAgICAgICAgICAkYXBwQWNjb3VudElkOiBTdHJpbmchLFxuICAgICAgICAgICAgICAgICAgICAkYXBwRW1haWw6IFN0cmluZyEsXG4gICAgICAgICAgICAgICAgICAgICRhcHBJZDogU3RyaW5nISxcbiAgICAgICAgICAgICAgICAgICAgJHt0b2tlbiAhPT0gdW5kZWZpbmVkID8gJyAkdG9rZW46IFN0cmluZywnIDogJyd9XG4gICAgICAgICAgICAgICAgICAgICR7cmVmcmVzaFRva2VuICE9PSB1bmRlZmluZWQgPyAnICRyZWZyZXNoVG9rZW46IFN0cmluZywnIDogJyd9XG4gICAgICAgICAgICAgICAgICAgICR7ZXhwaXJlc0luICE9PSB1bmRlZmluZWQgPyAnICRleHBpcmVzQXQ6IHRpbWVzdGFtcHR6LCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICAgJHtlbmFibGVkICE9PSB1bmRlZmluZWQgPyAnICRlbmFibGVkOiBCb29sZWFuLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICAgJHtjb250YWN0Rmlyc3ROYW1lICE9PSB1bmRlZmluZWQgPyAnICRjb250YWN0Rmlyc3ROYW1lOiBTdHJpbmcsJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICAke2NvbnRhY3RMYXN0TmFtZSAhPT0gdW5kZWZpbmVkID8gJyAkY29udGFjdExhc3ROYW1lOiBTdHJpbmcsJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICAke3Bob25lQ291bnRyeSAhPT0gdW5kZWZpbmVkID8gJyAkcGhvbmVDb3VudHJ5OiBTdHJpbmcsJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICAke3Bob25lTnVtYmVyICE9PSB1bmRlZmluZWQgPyAnICRwaG9uZU51bWJlcjogU3RyaW5nLCcgOiAnJ31cbiAgICAgICAgICAgICAgICApIHtcbiAgICAgICAgICAgICAgICB1cGRhdGVfQ2FsZW5kYXJfSW50ZWdyYXRpb25fYnlfcGsocGtfY29sdW1uczoge2lkOiAkaWR9LCBfc2V0OiB7XG4gICAgICAgICAgICAgICAgICAgIGFwcEFjY291bnRJZDogJGFwcEFjY291bnRJZCxcbiAgICAgICAgICAgICAgICAgICAgYXBwRW1haWw6ICRhcHBFbWFpbCxcbiAgICAgICAgICAgICAgICAgICAgYXBwSWQ6ICRhcHBJZCxcbiAgICAgICAgICAgICAgICAgICAgJHt0b2tlbiAhPT0gdW5kZWZpbmVkID8gJ3Rva2VuOiAkdG9rZW4sJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICAke2V4cGlyZXNJbiAhPT0gdW5kZWZpbmVkID8gJyBleHBpcmVzQXQ6ICRleHBpcmVzQXQsJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICAke3JlZnJlc2hUb2tlbiAhPT0gdW5kZWZpbmVkID8gJ3JlZnJlc2hUb2tlbjogJHJlZnJlc2hUb2tlbiwnIDogJyd9XG4gICAgICAgICAgICAgICAgICAgICR7Y29udGFjdEZpcnN0TmFtZSAhPT0gdW5kZWZpbmVkID8gJ2NvbnRhY3RGaXJzdE5hbWU6ICRjb250YWN0Rmlyc3ROYW1lLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICAgJHtjb250YWN0TGFzdE5hbWUgIT09IHVuZGVmaW5lZCA/ICdjb250YWN0TGFzdE5hbWU6ICRjb250YWN0TGFzdE5hbWUsJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICAke3Bob25lQ291bnRyeSAhPT0gdW5kZWZpbmVkID8gJ3Bob25lQ291bnRyeTogJHBob25lQ291bnRyeSwnIDogJyd9XG4gICAgICAgICAgICAgICAgICAgICR7cGhvbmVOdW1iZXIgIT09IHVuZGVmaW5lZCA/ICdwaG9uZU51bWJlcjogJHBob25lTnVtYmVyLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICAgJHtlbmFibGVkICE9PSB1bmRlZmluZWQgPyAnIGVuYWJsZWQ6ICRlbmFibGVkLCcgOiAnJ31cbiAgICAgICAgICAgICAgICB9KSB7XG4gICAgICAgICAgICAgICAgICAgIGFwcEFjY291bnRJZFxuICAgICAgICAgICAgICAgICAgICBhcHBFbWFpbFxuICAgICAgICAgICAgICAgICAgICBhcHBJZFxuICAgICAgICAgICAgICAgICAgICBjbGllbnRUeXBlXG4gICAgICAgICAgICAgICAgICAgIGNvbG9yc1xuICAgICAgICAgICAgICAgICAgICBjb250YWN0RW1haWxcbiAgICAgICAgICAgICAgICAgICAgY29udGFjdEZpcnN0TmFtZVxuICAgICAgICAgICAgICAgICAgICBjb250YWN0TGFzdE5hbWVcbiAgICAgICAgICAgICAgICAgICAgY29udGFjdE5hbWVcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgICAgICAgICAgICBlbmFibGVkXG4gICAgICAgICAgICAgICAgICAgIGV4cGlyZXNBdFxuICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICBuYW1lXG4gICAgICAgICAgICAgICAgICAgIHBhZ2VUb2tlblxuICAgICAgICAgICAgICAgICAgICBwYXNzd29yZFxuICAgICAgICAgICAgICAgICAgICBwaG9uZUNvdW50cnlcbiAgICAgICAgICAgICAgICAgICAgcGhvbmVOdW1iZXJcbiAgICAgICAgICAgICAgICAgICAgcmVmcmVzaFRva2VuXG4gICAgICAgICAgICAgICAgICAgIHJlc291cmNlXG4gICAgICAgICAgICAgICAgICAgIHN5bmNFbmFibGVkXG4gICAgICAgICAgICAgICAgICAgIHN5bmNUb2tlblxuICAgICAgICAgICAgICAgICAgICB0b2tlblxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgIHVzZXJuYW1lXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuXG4gICAgbGV0IGVuY3J5cHRlZFZhbHVlcyA9IG51bGw7XG5cbiAgICBpZiAodG9rZW4pIHtcbiAgICAgIGVuY3J5cHRlZFZhbHVlcyA9IGVuY3J5cHRab29tVG9rZW5zKHRva2VuLCByZWZyZXNoVG9rZW4pO1xuICAgIH1cblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGlkLFxuICAgICAgYXBwQWNjb3VudElkLFxuICAgICAgYXBwRW1haWwsXG4gICAgICBhcHBJZCxcbiAgICAgIHRva2VuOiBlbmNyeXB0ZWRWYWx1ZXM/LmVuY3J5cHRlZFRva2VuLFxuICAgICAgZXhwaXJlc0F0OiBleHBpcmVzSW5cbiAgICAgICAgPyBkYXlqcygpLmFkZChleHBpcmVzSW4sICdzZWNvbmRzJykudG9JU09TdHJpbmcoKVxuICAgICAgICA6IG51bGwsXG4gICAgICByZWZyZXNoVG9rZW46XG4gICAgICAgIHJlZnJlc2hUb2tlbiA9PT0gdW5kZWZpbmVkXG4gICAgICAgICAgPyB1bmRlZmluZWRcbiAgICAgICAgICA6IGVuY3J5cHRlZFZhbHVlcz8uZW5jcnlwdGVkUmVmcmVzaFRva2VuLFxuICAgICAgY29udGFjdEZpcnN0TmFtZSxcbiAgICAgIGNvbnRhY3RMYXN0TmFtZSxcbiAgICAgIHBob25lQ291bnRyeSxcbiAgICAgIHBob25lTnVtYmVyLFxuICAgICAgZW5hYmxlZCxcbiAgICB9O1xuXG4gICAgY29uc3Qgb3B0aW9ucyA9IHtcbiAgICAgIGpzb246IHsgb3BlcmF0aW9uTmFtZSwgcXVlcnksIHZhcmlhYmxlcyB9LFxuICAgICAgaGVhZGVyczoge1xuICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtQWRtaW4tU2VjcmV0JzogcG9zdGdyYXBoaWxlQWRtaW5TZWNyZXQsXG4gICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgIH0sXG4gICAgfTtcblxuICAgIGF3YWl0IHJlc2lsaWVudEdvdCgncG9zdCcsIHBvc3RncmFwaGlsZUdyYXBoVXJsLCBvcHRpb25zLCBvcGVyYXRpb25OYW1lKTtcblxuICAgIGFwcFNlcnZpY2VMb2dnZXIuaW5mbyhcbiAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gU3VjY2Vzc2Z1bGx5IHVwZGF0ZWQgWm9vbSBpbnRlZ3JhdGlvbi5gLFxuICAgICAgeyBpZCwgYXBwQWNjb3VudElkLCBhcHBFbWFpbCwgZW5hYmxlZCB9XG4gICAgKTtcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgYXBwU2VydmljZUxvZ2dlci5lcnJvcihcbiAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gVW5hYmxlIHRvIHVwZGF0ZSBab29tIGludGVncmF0aW9uLmAsXG4gICAgICB7XG4gICAgICAgIGlkLFxuICAgICAgICBhcHBBY2NvdW50SWQsXG4gICAgICAgIGFwcEVtYWlsLFxuICAgICAgICBlcnJvcjogZS5tZXNzYWdlLFxuICAgICAgICBzdGFjazogZS5zdGFjayxcbiAgICAgICAgZGV0YWlsczogZSxcbiAgICAgIH1cbiAgICApO1xuICAgIHRocm93IGU7IC8vIFJldGhyb3cgdG8gZW5zdXJlIGZhaWx1cmUgaXMgcHJvcGFnYXRlZFxuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0TWluaW1hbENhbGVuZGFySW50ZWdyYXRpb25CeU5hbWUgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBuYW1lOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbic7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICBxdWVyeSBnZXRDYWxlbmRhckludGVncmF0aW9uKCR1c2VySWQ6IHV1aWQhLCAkbmFtZTogU3RyaW5nISkge1xuICAgICAgICBDYWxlbmRhcl9JbnRlZ3JhdGlvbih3aGVyZToge3VzZXJJZDoge19lcTogJHVzZXJJZH0sIG5hbWU6IHtfZXE6ICRuYW1lfX0pIHtcbiAgICAgICAgICAgIGFwcEFjY291bnRJZFxuICAgICAgICAgICAgYXBwRW1haWxcbiAgICAgICAgICAgIGFwcElkXG4gICAgICAgICAgICBjbGllbnRUeXBlXG4gICAgICAgICAgICBjb2xvcnNcbiAgICAgICAgICAgIGNvbnRhY3RFbWFpbFxuICAgICAgICAgICAgY29udGFjdEZpcnN0TmFtZVxuICAgICAgICAgICAgY29udGFjdExhc3ROYW1lXG4gICAgICAgICAgICBjb250YWN0TmFtZVxuICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICAgIGVuYWJsZWRcbiAgICAgICAgICAgIGV4cGlyZXNBdFxuICAgICAgICAgICAgaWRcbiAgICAgICAgICAgIG5hbWVcbiAgICAgICAgICAgIHBhZ2VUb2tlblxuICAgICAgICAgICAgcGFzc3dvcmRcbiAgICAgICAgICAgIHBob25lQ291bnRyeVxuICAgICAgICAgICAgcGhvbmVOdW1iZXJcbiAgICAgICAgICAgIHJlZnJlc2hUb2tlblxuICAgICAgICAgICAgcmVzb3VyY2VcbiAgICAgICAgICAgIHN5bmNFbmFibGVkXG4gICAgICAgICAgICBzeW5jVG9rZW5cbiAgICAgICAgICAgIHRva2VuXG4gICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgdXNlcm5hbWVcbiAgICAgICAgfVxuICAgICAgfVxuICAgIGA7XG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgdXNlcklkLFxuICAgICAgbmFtZSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgQ2FsZW5kYXJfSW50ZWdyYXRpb246IENhbGVuZGFySW50ZWdyYXRpb25UeXBlW10gfSB9ID1cbiAgICAgIGF3YWl0IGdvdFxuICAgICAgICAucG9zdChwb3N0Z3JhcGhpbGVHcmFwaFVybCwge1xuICAgICAgICAgIGpzb246IHtcbiAgICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1BZG1pbi1TZWNyZXQnOiBwb3N0Z3JhcGhpbGVBZG1pblNlY3JldCxcbiAgICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSlcbiAgICAgICAgLmpzb24oKTtcblxuICAgIC8vIGNvbnNvbGUubG9nKHJlcywgJyByZXMgaW5zaWRlIGdldENhbGVuZGFySW50ZWdyYXRpb24nKVxuICAgIGlmIChyZXM/LmRhdGE/LkNhbGVuZGFyX0ludGVncmF0aW9uPy5sZW5ndGggPiAwKSB7XG4gICAgICBhcHBTZXJ2aWNlTG9nZ2VyLmRlYnVnKFxuICAgICAgICBgW2dldE1pbmltYWxDYWxlbmRhckludGVncmF0aW9uQnlOYW1lXSBGb3VuZCBpbnRlZ3JhdGlvbiBmb3IgdXNlcklkOiAke3VzZXJJZH0sIG5hbWU6ICR7bmFtZX0uYCxcbiAgICAgICAgeyBpbnRlZ3JhdGlvbklkOiByZXMuZGF0YS5DYWxlbmRhcl9JbnRlZ3JhdGlvblswXS5pZCB9XG4gICAgICApO1xuICAgICAgcmV0dXJuIHJlcz8uZGF0YT8uQ2FsZW5kYXJfSW50ZWdyYXRpb24/LlswXTtcbiAgICB9IGVsc2Uge1xuICAgICAgYXBwU2VydmljZUxvZ2dlci5pbmZvKFxuICAgICAgICBgW2dldE1pbmltYWxDYWxlbmRhckludGVncmF0aW9uQnlOYW1lXSBObyBpbnRlZ3JhdGlvbiBmb3VuZCBmb3IgdXNlcklkOiAke3VzZXJJZH0sIG5hbWU6ICR7bmFtZX0uYFxuICAgICAgKTtcbiAgICAgIHJldHVybiB1bmRlZmluZWQ7XG4gICAgfVxuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBhcHBTZXJ2aWNlTG9nZ2VyLmVycm9yKFxuICAgICAgJ1tnZXRNaW5pbWFsQ2FsZW5kYXJJbnRlZ3JhdGlvbkJ5TmFtZV0gVW5hYmxlIHRvIGdldCBjYWxlbmRhciBpbnRlZ3JhdGlvbiBieSBuYW1lLicsXG4gICAgICB7IHVzZXJJZCwgbmFtZSwgZXJyb3I6IGUubWVzc2FnZSwgc3RhY2s6IGUuc3RhY2ssIGRldGFpbHM6IGUgfVxuICAgICk7XG4gICAgLy8gT3JpZ2luYWwgZnVuY3Rpb24gaW1wbGljaXRseSByZXR1cm5zIHVuZGVmaW5lZC5cbiAgfVxufTtcblxuLyoqXG4gKiBxdWVyeSBnZXRDYWxlbmRhckludGVncmF0aW9uKCR1c2VySWQ6IHV1aWQhLCAkcmVzb3VyY2U6IFN0cmluZyEsICRjbGllbnRUeXBlOiBTdHJpbmchKSB7XG4gIENhbGVuZGFyX0ludGVncmF0aW9uKHdoZXJlOiB7dXNlcklkOiB7X2VxOiAkdXNlcklkfSwgcmVzb3VyY2U6IHtfZXE6ICRyZXNvdXJjZX0sIGNsaWVudFR5cGU6IHtfZXE6ICRjbGllbnRUeXBlfX0pIHtcbiAgICBhcHBBY2NvdW50SWRcbiAgICBhcHBFbWFpbFxuICAgIGFwcElkXG4gICAgY2xpZW50VHlwZVxuICAgIGNvbG9yc1xuICAgIGNvbnRhY3RFbWFpbFxuICAgIGNvbnRhY3RGaXJzdE5hbWVcbiAgICBjb250YWN0TGFzdE5hbWVcbiAgICBjb250YWN0TmFtZVxuICAgIGNyZWF0ZWREYXRlXG4gICAgZGVsZXRlZFxuICAgIGVuYWJsZWRcbiAgICBleHBpcmVzQXRcbiAgICBpZFxuICAgIG5hbWVcbiAgICBwYWdlVG9rZW5cbiAgICBwYXNzd29yZFxuICAgIHBob25lQ291bnRyeVxuICAgIHBob25lTnVtYmVyXG4gICAgcmVmcmVzaFRva2VuXG4gICAgcmVzb3VyY2VcbiAgICBzeW5jRW5hYmxlZFxuICAgIHN5bmNUb2tlblxuICAgIHRva2VuXG4gICAgdXBkYXRlZEF0XG4gICAgdXNlcklkXG4gICAgdXNlcm5hbWVcbiAgfVxufVxuXG4gKi9cblxuZXhwb3J0IGNvbnN0IGdldEFsbENhbGVuZGFySW50ZWdyYXRvbnNCeVJlc291cmNlQW5kQ2xpZW50VHlwZSA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHJlc291cmNlOiBzdHJpbmcsXG4gIGNsaWVudFR5cGU6ICdpb3MnIHwgJ2FuZHJvaWQnIHwgJ3dlYicgfCAnYXRvbWljLXdlYidcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5UmVzb3VyY2VBbmRDbGllbnRUeXBlJztcblxuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgcXVlcnkgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5UmVzb3VyY2VBbmRDbGllbnRUeXBlKCR1c2VySWQ6IHV1aWQhLCAkcmVzb3VyY2U6IFN0cmluZyEsICRjbGllbnRUeXBlOiBTdHJpbmchKSB7XG4gICAgICAgICAgICAgICAgQ2FsZW5kYXJfSW50ZWdyYXRpb24od2hlcmU6IHt1c2VySWQ6IHtfZXE6ICR1c2VySWR9LCByZXNvdXJjZToge19lcTogJHJlc291cmNlfSwgY2xpZW50VHlwZToge19lcTogJGNsaWVudFR5cGV9fSkge1xuICAgICAgICAgICAgICAgIGFwcEFjY291bnRJZFxuICAgICAgICAgICAgICAgIGFwcEVtYWlsXG4gICAgICAgICAgICAgICAgYXBwSWRcbiAgICAgICAgICAgICAgICBjbGllbnRUeXBlXG4gICAgICAgICAgICAgICAgY29sb3JzXG4gICAgICAgICAgICAgICAgY29udGFjdEVtYWlsXG4gICAgICAgICAgICAgICAgY29udGFjdEZpcnN0TmFtZVxuICAgICAgICAgICAgICAgIGNvbnRhY3RMYXN0TmFtZVxuICAgICAgICAgICAgICAgIGNvbnRhY3ROYW1lXG4gICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICBkZWxldGVkXG4gICAgICAgICAgICAgICAgZW5hYmxlZFxuICAgICAgICAgICAgICAgIGV4cGlyZXNBdFxuICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgbmFtZVxuICAgICAgICAgICAgICAgIHBhZ2VUb2tlblxuICAgICAgICAgICAgICAgIHBhc3N3b3JkXG4gICAgICAgICAgICAgICAgcGhvbmVDb3VudHJ5XG4gICAgICAgICAgICAgICAgcGhvbmVOdW1iZXJcbiAgICAgICAgICAgICAgICByZWZyZXNoVG9rZW5cbiAgICAgICAgICAgICAgICByZXNvdXJjZVxuICAgICAgICAgICAgICAgIHN5bmNFbmFibGVkXG4gICAgICAgICAgICAgICAgc3luY1Rva2VuXG4gICAgICAgICAgICAgICAgdG9rZW5cbiAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgICB1c2VybmFtZVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIHJlc291cmNlLFxuICAgICAgY2xpZW50VHlwZSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgQ2FsZW5kYXJfSW50ZWdyYXRpb246IENhbGVuZGFySW50ZWdyYXRpb25UeXBlW10gfSB9ID1cbiAgICAgIGF3YWl0IGdvdFxuICAgICAgICAucG9zdChwb3N0Z3JhcGhpbGVHcmFwaFVybCwge1xuICAgICAgICAgIGpzb246IHtcbiAgICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1BZG1pbi1TZWNyZXQnOiBwb3N0Z3JhcGhpbGVBZG1pblNlY3JldCxcbiAgICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSlcbiAgICAgICAgLmpzb24oKTtcblxuICAgIC8vIGNvbnNvbGUubG9nKHJlcywgJyByZXMgaW5zaWRlIGdldENhbGVuZGFySW50ZWdyYXRpb24nKVxuICAgIGlmIChyZXM/LmRhdGE/LkNhbGVuZGFyX0ludGVncmF0aW9uPy5sZW5ndGggPiAwKSB7XG4gICAgICBhcHBTZXJ2aWNlTG9nZ2VyLmRlYnVnKFxuICAgICAgICBgW2dldEFsbENhbGVuZGFySW50ZWdyYXRvbnNCeVJlc291cmNlQW5kQ2xpZW50VHlwZV0gRm91bmQgJHtyZXMuZGF0YS5DYWxlbmRhcl9JbnRlZ3JhdGlvbi5sZW5ndGh9IGludGVncmF0aW9ucy5gLFxuICAgICAgICB7IHVzZXJJZCwgcmVzb3VyY2UsIGNsaWVudFR5cGUgfVxuICAgICAgKTtcbiAgICAgIHJldHVybiByZXM/LmRhdGE/LkNhbGVuZGFyX0ludGVncmF0aW9uO1xuICAgIH0gZWxzZSB7XG4gICAgICBhcHBTZXJ2aWNlTG9nZ2VyLmluZm8oXG4gICAgICAgIGBbZ2V0QWxsQ2FsZW5kYXJJbnRlZ3JhdG9uc0J5UmVzb3VyY2VBbmRDbGllbnRUeXBlXSBObyBpbnRlZ3JhdGlvbnMgZm91bmQuYCxcbiAgICAgICAgeyB1c2VySWQsIHJlc291cmNlLCBjbGllbnRUeXBlIH1cbiAgICAgICk7XG4gICAgICByZXR1cm4gdW5kZWZpbmVkOyAvLyBPciBhbiBlbXB0eSBhcnJheSBbXSBkZXBlbmRpbmcgb24gZGVzaXJlZCBjb250cmFjdFxuICAgIH1cbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgYXBwU2VydmljZUxvZ2dlci5lcnJvcihcbiAgICAgICdbZ2V0QWxsQ2FsZW5kYXJJbnRlZ3JhdG9uc0J5UmVzb3VyY2VBbmRDbGllbnRUeXBlXSBVbmFibGUgdG8gZ2V0IGNhbGVuZGFyIGludGVncmF0aW9ucy4nLFxuICAgICAge1xuICAgICAgICB1c2VySWQsXG4gICAgICAgIHJlc291cmNlLFxuICAgICAgICBjbGllbnRUeXBlLFxuICAgICAgICBlcnJvcjogZS5tZXNzYWdlLFxuICAgICAgICBzdGFjazogZS5zdGFjayxcbiAgICAgICAgZGV0YWlsczogZSxcbiAgICAgIH1cbiAgICApO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0QWxsQ2FsZW5kYXJJbnRlZ3JhdGlvbnNCeVJlc291cmNlID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgcmVzb3VyY2U6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdnZXRDYWxlbmRhckludGVncmF0aW9uQnlSZXNvdXJjZSc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICBxdWVyeSBnZXRDYWxlbmRhckludGVncmF0aW9uQnlSZXNvdXJjZSgkdXNlcklkOiB1dWlkISwgJHJlc291cmNlOiBTdHJpbmchKSB7XG4gICAgICAgIENhbGVuZGFyX0ludGVncmF0aW9uKHdoZXJlOiB7dXNlcklkOiB7X2VxOiAkdXNlcklkfSwgcmVzb3VyY2U6IHtfZXE6ICRyZXNvdXJjZX19KSB7XG4gICAgICAgICAgICBhcHBBY2NvdW50SWRcbiAgICAgICAgICAgIGFwcEVtYWlsXG4gICAgICAgICAgICBhcHBJZFxuICAgICAgICAgICAgY2xpZW50VHlwZVxuICAgICAgICAgICAgY29sb3JzXG4gICAgICAgICAgICBjb250YWN0RW1haWxcbiAgICAgICAgICAgIGNvbnRhY3RGaXJzdE5hbWVcbiAgICAgICAgICAgIGNvbnRhY3RMYXN0TmFtZVxuICAgICAgICAgICAgY29udGFjdE5hbWVcbiAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICBkZWxldGVkXG4gICAgICAgICAgICBlbmFibGVkXG4gICAgICAgICAgICBleHBpcmVzQXRcbiAgICAgICAgICAgIGlkXG4gICAgICAgICAgICBuYW1lXG4gICAgICAgICAgICBwYWdlVG9rZW5cbiAgICAgICAgICAgIHBhc3N3b3JkXG4gICAgICAgICAgICBwaG9uZUNvdW50cnlcbiAgICAgICAgICAgIHBob25lTnVtYmVyXG4gICAgICAgICAgICByZWZyZXNoVG9rZW5cbiAgICAgICAgICAgIHJlc291cmNlXG4gICAgICAgICAgICBzeW5jRW5hYmxlZFxuICAgICAgICAgICAgc3luY1Rva2VuXG4gICAgICAgICAgICB0b2tlblxuICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgIHVzZXJuYW1lXG4gICAgICAgIH1cbiAgICAgIH1cbiAgICBgO1xuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIHJlc291cmNlLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBDYWxlbmRhcl9JbnRlZ3JhdGlvbjogQ2FsZW5kYXJJbnRlZ3JhdGlvblR5cGVbXSB9IH0gPVxuICAgICAgYXdhaXQgZ290XG4gICAgICAgIC5wb3N0KHBvc3RncmFwaGlsZUdyYXBoVXJsLCB7XG4gICAgICAgICAganNvbjoge1xuICAgICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICAgIH0sXG4gICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLUFkbWluLVNlY3JldCc6IHBvc3RncmFwaGlsZUFkbWluU2VjcmV0LFxuICAgICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgICB9LFxuICAgICAgICB9KVxuICAgICAgICAuanNvbigpO1xuXG4gICAgLy8gY29uc29sZS5sb2cocmVzLCAnIHJlcyBpbnNpZGUgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbicpXG4gICAgaWYgKHJlcz8uZGF0YT8uQ2FsZW5kYXJfSW50ZWdyYXRpb24/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGFwcFNlcnZpY2VMb2dnZXIuZGVidWcoXG4gICAgICAgIGBbZ2V0QWxsQ2FsZW5kYXJJbnRlZ3JhdGlvbnNCeVJlc291cmNlXSBGb3VuZCAke3Jlcy5kYXRhLkNhbGVuZGFyX0ludGVncmF0aW9uLmxlbmd0aH0gaW50ZWdyYXRpb25zLmAsXG4gICAgICAgIHsgdXNlcklkLCByZXNvdXJjZSB9XG4gICAgICApO1xuICAgICAgcmV0dXJuIHJlcz8uZGF0YT8uQ2FsZW5kYXJfSW50ZWdyYXRpb247XG4gICAgfSBlbHNlIHtcbiAgICAgIGFwcFNlcnZpY2VMb2dnZXIuaW5mbyhcbiAgICAgICAgYFtnZXRBbGxDYWxlbmRhckludGVncmF0aW9uc0J5UmVzb3VyY2VdIE5vIGludGVncmF0aW9ucyBmb3VuZC5gLFxuICAgICAgICB7IHVzZXJJZCwgcmVzb3VyY2UgfVxuICAgICAgKTtcbiAgICAgIHJldHVybiB1bmRlZmluZWQ7IC8vIE9yIGFuIGVtcHR5IGFycmF5IFtdXG4gICAgfVxuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBhcHBTZXJ2aWNlTG9nZ2VyLmVycm9yKFxuICAgICAgJ1tnZXRBbGxDYWxlbmRhckludGVncmF0aW9uc0J5UmVzb3VyY2VdIFVuYWJsZSB0byBnZXQgYWxsIGNhbGVuZGFyIGludGVncmF0aW9ucyBieSByZXNvdXJjZS4nLFxuICAgICAgeyB1c2VySWQsIHJlc291cmNlLCBlcnJvcjogZS5tZXNzYWdlLCBzdGFjazogZS5zdGFjaywgZGV0YWlsczogZSB9XG4gICAgKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldEdvb2dsZUNvbG9ycyA9IGFzeW5jICh0b2tlbjogc3RyaW5nKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgdXJsID0gZ29vZ2xlQ29sb3JVcmw7XG4gICAgY29uc3QgY29uZmlnID0ge1xuICAgICAgaGVhZGVyczoge1xuICAgICAgICBBdXRob3JpemF0aW9uOiBgQmVhcmVyICR7dG9rZW59YCxcbiAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgQWNjZXB0OiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICB9LFxuICAgIH07XG5cbiAgICBjb25zdCBkYXRhOiBjb2xvclJlc3BvbnNlVHlwZSA9IGF3YWl0IGdvdC5nZXQodXJsLCBjb25maWcpLmpzb24oKTtcbiAgICBhcHBTZXJ2aWNlTG9nZ2VyLmRlYnVnKFxuICAgICAgJ1tnZXRHb29nbGVDb2xvcnNdIFN1Y2Nlc3NmdWxseSBmZXRjaGVkIEdvb2dsZSBjb2xvcnMuJyxcbiAgICAgIHtcbiAgICAgICAgY2FsZW5kYXJDb2xvcnNDb3VudDogT2JqZWN0LmtleXMoZGF0YS5jYWxlbmRhciB8fCB7fSkubGVuZ3RoLFxuICAgICAgICBldmVudENvbG9yc0NvdW50OiBPYmplY3Qua2V5cyhkYXRhLmV2ZW50IHx8IHt9KS5sZW5ndGgsXG4gICAgICB9XG4gICAgKTtcbiAgICByZXR1cm4gZGF0YTtcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgYXBwU2VydmljZUxvZ2dlci5lcnJvcignW2dldEdvb2dsZUNvbG9yc10gVW5hYmxlIHRvIGdldCBHb29nbGUgY29sb3JzLicsIHtcbiAgICAgIGVycm9yOiBlLm1lc3NhZ2UsXG4gICAgICBzdGFjazogZS5zdGFjayxcbiAgICAgIGRldGFpbHM6IGUsXG4gICAgfSk7XG4gICAgLy8gT3JpZ2luYWwgZnVuY3Rpb24gaW1wbGljaXRseSByZXR1cm5zIHVuZGVmaW5lZC5cbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHRyaWdnZXJHb29nbGVQZW9wbGVTeW5jID0gYXN5bmMgKFxuICBjYWxlbmRhckludGVncmF0aW9uSWQ6IHN0cmluZyxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHJlcTogTmV4dEFwaVJlcXVlc3RcbikgPT4ge1xuICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ3RyaWdnZXJHb29nbGVQZW9wbGVTeW5jJztcbiAgdHJ5IHtcbiAgICBhcHBTZXJ2aWNlTG9nZ2VyLmluZm8oYFske29wZXJhdGlvbk5hbWV9XSBDYWxsZWQuYCwge1xuICAgICAgY2FsZW5kYXJJbnRlZ3JhdGlvbklkLFxuICAgICAgdXNlcklkLFxuICAgIH0pO1xuICAgIGlmICghY2FsZW5kYXJJbnRlZ3JhdGlvbklkKSB7XG4gICAgICBhcHBTZXJ2aWNlTG9nZ2VyLndhcm4oXG4gICAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gTm8gY2FsZW5kYXJJbnRlZ3JhdGlvbklkIHByb3ZpZGVkLmBcbiAgICAgICk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgaWYgKCF1c2VySWQpIHtcbiAgICAgIGFwcFNlcnZpY2VMb2dnZXIud2FybihgWyR7b3BlcmF0aW9uTmFtZX1dIE5vIHVzZXJJZCBwcm92aWRlZC5gKTtcbiAgICAgIHJldHVybjtcbiAgICB9XG4gICAgY29uc3QgdG9rZW5QYXlsb2FkID0gcmVxLnNlc3Npb24/LmdldEFjY2Vzc1Rva2VuUGF5bG9hZCgpOyAvLyBTYWZlbHkgYWNjZXNzIHNlc3Npb24gYW5kIHBheWxvYWRcbiAgICBjb25zdCB0b2tlbiA9IHRva2VuUGF5bG9hZDsgLy8gQXNzdW1pbmcgdGhlIHdob2xlIHBheWxvYWQgbWlnaHQgYmUgdGhlIHRva2VuLCBvciBhZGp1c3QgaWYgaXQncyBhIHByb3BlcnR5IGxpa2UgdG9rZW5QYXlsb2FkLmp3dFxuXG4gICAgaWYgKCF0b2tlbikge1xuICAgICAgYXBwU2VydmljZUxvZ2dlci53YXJuKFxuICAgICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIE5vIGFjY2VzcyB0b2tlbiBmb3VuZCBpbiBzZXNzaW9uLmBcbiAgICAgICk7XG4gICAgICAvLyBEZXBlbmRpbmcgb24gcmVxdWlyZW1lbnRzLCBtaWdodCB0aHJvdyBhbiBlcnJvciBvciByZXR1cm4gYSBzcGVjaWZpYyByZXNwb25zZVxuICAgICAgcmV0dXJuOyAvLyBPciBoYW5kbGUgZXJyb3IgYXBwcm9wcmlhdGVseVxuICAgIH1cblxuICAgIGNvbnN0IGRhdGEgPSB7XG4gICAgICBjYWxlbmRhckludGVncmF0aW9uSWQsXG4gICAgICB1c2VySWQsXG4gICAgICBpc0luaXRpYWxTeW5jOiB0cnVlLFxuICAgIH07XG5cbiAgICBjb25zdCB1cmwgPSBnb29nbGVQZW9wbGVTeW5jVXJsO1xuXG4gICAgY29uc3QgcmVzdWx0cyA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QodXJsLCB7XG4gICAgICAgIGpzb246IGRhdGEsXG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICBBdXRob3JpemF0aW9uOiBgQmVhcmVyICR7dG9rZW59YCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBhcHBTZXJ2aWNlTG9nZ2VyLmluZm8oXG4gICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIFN1Y2Nlc3NmdWxseSB0cmlnZ2VyZWQgR29vZ2xlIHBlb3BsZSBzeW5jLmAsXG4gICAgICB7IGNhbGVuZGFySW50ZWdyYXRpb25JZCwgdXNlcklkLCByZXN1bHRzIH1cbiAgICApO1xuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBhcHBTZXJ2aWNlTG9nZ2VyLmVycm9yKFxuICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBVbmFibGUgdG8gdHJpZ2dlciBHb29nbGUgcGVvcGxlIHN5bmMuYCxcbiAgICAgIHtcbiAgICAgICAgY2FsZW5kYXJJbnRlZ3JhdGlvbklkLFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIGVycm9yOiBlLm1lc3NhZ2UsXG4gICAgICAgIGNvZGU6IGUuY29kZSxcbiAgICAgICAgcmVzcG9uc2VCb2R5OiBlPy5yZXNwb25zZT8uYm9keSwgLy8gTG9nIHRoZSBhY3R1YWwgcmVzcG9uc2UgYm9keSBpZiBhdmFpbGFibGVcbiAgICAgICAgc3RhY2s6IGUuc3RhY2ssXG4gICAgICB9XG4gICAgKTtcbiAgICAvLyBPcmlnaW5hbCBmdW5jdGlvbiBpbXBsaWNpdGx5IHJldHVybnMgdW5kZWZpbmVkIG9uIGVycm9yLlxuICB9XG59O1xuZXhwb3J0IGNvbnN0IHVwZGF0ZUdvb2dsZUludGVncmF0aW9uID0gYXN5bmMgKFxuICBpZDogc3RyaW5nLFxuICBlbmFibGVkPzogYm9vbGVhbixcbiAgdG9rZW4/OiBzdHJpbmcsXG4gIHJlZnJlc2hUb2tlbj86IHN0cmluZyxcbiAgZXhwaXJlc0F0Pzogc3RyaW5nLFxuICBzeW5jRW5hYmxlZD86IGJvb2xlYW4sXG4gIGNvbG9ycz86IGNvbG9yVHlwZVtdLFxuICBwYWdlVG9rZW4/OiBzdHJpbmcsXG4gIHN5bmNUb2tlbj86IHN0cmluZyxcbiAgY2xpZW50VHlwZT86ICdpb3MnIHwgJ2FuZHJvaWQnIHwgJ3dlYicgfCAnYXRvbWljLXdlYidcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnVXBkYXRlQ2FsZW5kYXJJbnRlZ3JhdGlvbkJ5SWQnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgbXV0YXRpb24gVXBkYXRlQ2FsZW5kYXJJbnRlZ3JhdGlvbkJ5SWQoJGlkOiB1dWlkISwgXG4gICAgICAgICAgICAgICAgJHtlbmFibGVkICE9PSB1bmRlZmluZWQgPyAnJGVuYWJsZWQ6IEJvb2xlYW4sJyA6ICcnfSBcbiAgICAgICAgICAgICAgICAke2V4cGlyZXNBdCAhPT0gdW5kZWZpbmVkID8gJyRleHBpcmVzQXQ6IHRpbWVzdGFtcHR6LCcgOiAnJ30gXG4gICAgICAgICAgICAgICAgJHtyZWZyZXNoVG9rZW4gIT09IHVuZGVmaW5lZCA/ICckcmVmcmVzaFRva2VuOiBTdHJpbmcsJyA6ICcnfSBcbiAgICAgICAgICAgICAgICAke3Rva2VuICE9PSB1bmRlZmluZWQgPyAnJHRva2VuOiBTdHJpbmcsJyA6ICcnfVxuICAgICAgICAgICAgICAgICR7c3luY0VuYWJsZWQgIT09IHVuZGVmaW5lZCA/ICckc3luY0VuYWJsZWQ6IEJvb2xlYW4sJyA6ICcnfVxuICAgICAgICAgICAgICAgICR7Y29sb3JzICE9PSB1bmRlZmluZWQgPyAnJGNvbG9yczoganNvbmIsJyA6ICcnfVxuICAgICAgICAgICAgICAgICR7cGFnZVRva2VuICE9PSB1bmRlZmluZWQgPyAnJHBhZ2VUb2tlbjogU3RyaW5nLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAke3N5bmNUb2tlbiAhPT0gdW5kZWZpbmVkID8gJyRzeW5jVG9rZW46IFN0cmluZywnIDogJyd9XG4gICAgICAgICAgICAgICAgJHtjbGllbnRUeXBlICE9PSB1bmRlZmluZWQgPyAnJGNsaWVudFR5cGU6IFN0cmluZywnIDogJyd9XG4gICAgICAgICAgICAgICAgJHVwZGF0ZWRBdDogdGltZXN0YW1wdHopIHtcbiAgICAgICAgICAgICAgICB1cGRhdGVfQ2FsZW5kYXJfSW50ZWdyYXRpb25fYnlfcGsoX3NldDoge1xuICAgICAgICAgICAgICAgICAgICAke2VuYWJsZWQgIT09IHVuZGVmaW5lZCA/ICdlbmFibGVkOiAkZW5hYmxlZCwnIDogJyd9IFxuICAgICAgICAgICAgICAgICAgICAke2V4cGlyZXNBdCAhPT0gdW5kZWZpbmVkID8gJ2V4cGlyZXNBdDogJGV4cGlyZXNBdCwnIDogJyd9IFxuICAgICAgICAgICAgICAgICAgICAke3JlZnJlc2hUb2tlbiAhPT0gdW5kZWZpbmVkID8gJ3JlZnJlc2hUb2tlbjogJHJlZnJlc2hUb2tlbiwnIDogJyd9IFxuICAgICAgICAgICAgICAgICAgICAke3Rva2VuICE9PSB1bmRlZmluZWQgPyAndG9rZW46ICR0b2tlbiwnIDogJyd9XG4gICAgICAgICAgICAgICAgICAgICR7c3luY0VuYWJsZWQgIT09IHVuZGVmaW5lZCA/ICdzeW5jRW5hYmxlZDogJHN5bmNFbmFibGVkLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICAgJHtjb2xvcnMgIT09IHVuZGVmaW5lZCA/ICdjb2xvcnM6ICRjb2xvcnMsJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICAke3BhZ2VUb2tlbiAhPT0gdW5kZWZpbmVkID8gJ3BhZ2VUb2tlbjogJHBhZ2VUb2tlbiwnIDogJyd9XG4gICAgICAgICAgICAgICAgICAgICR7c3luY1Rva2VuICE9PSB1bmRlZmluZWQgPyAnc3luY1Rva2VuOiAkc3luY1Rva2VuLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICAgJHtjbGllbnRUeXBlICE9PSB1bmRlZmluZWQgPyAnY2xpZW50VHlwZTogJGNsaWVudFR5cGUsJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXQ6ICR1cGRhdGVkQXR9LCBwa19jb2x1bW5zOiB7aWQ6ICRpZH0pIHtcbiAgICAgICAgICAgICAgICAgICAgYXBwQWNjb3VudElkXG4gICAgICAgICAgICAgICAgICAgIGFwcEVtYWlsXG4gICAgICAgICAgICAgICAgICAgIGFwcElkXG4gICAgICAgICAgICAgICAgICAgIGNvbG9yc1xuICAgICAgICAgICAgICAgICAgICBjb250YWN0RW1haWxcbiAgICAgICAgICAgICAgICAgICAgY29udGFjdE5hbWVcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgICAgICAgICAgICBlbmFibGVkXG4gICAgICAgICAgICAgICAgICAgIGV4cGlyZXNBdFxuICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICBuYW1lXG4gICAgICAgICAgICAgICAgICAgIHBhZ2VUb2tlblxuICAgICAgICAgICAgICAgICAgICBwYXNzd29yZFxuICAgICAgICAgICAgICAgICAgICByZWZyZXNoVG9rZW5cbiAgICAgICAgICAgICAgICAgICAgc3luY0VuYWJsZWRcbiAgICAgICAgICAgICAgICAgICAgcmVzb3VyY2VcbiAgICAgICAgICAgICAgICAgICAgdG9rZW5cbiAgICAgICAgICAgICAgICAgICAgc3luY1Rva2VuXG4gICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgICAgICAgdXNlcm5hbWVcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgIGA7XG5cbiAgICBsZXQgdmFyaWFibGVzOiBhbnkgPSB7XG4gICAgICBpZCxcbiAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICB9O1xuXG4gICAgaWYgKGVuYWJsZWQgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLmVuYWJsZWQgPSBlbmFibGVkO1xuICAgIH1cblxuICAgIGlmIChleHBpcmVzQXQgIT09IHVuZGVmaW5lZCkge1xuICAgICAgaWYgKGV4cGlyZXNBdCA9PT0gbnVsbCkge1xuICAgICAgICB2YXJpYWJsZXMuZXhwaXJlc0F0ID0gbnVsbDtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIHZhcmlhYmxlcy5leHBpcmVzQXQgPSBkYXlqcyhleHBpcmVzQXQpLmZvcm1hdCgpO1xuICAgICAgfVxuICAgIH1cblxuICAgIGlmIChyZWZyZXNoVG9rZW4gIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLnJlZnJlc2hUb2tlbiA9IHJlZnJlc2hUb2tlbjtcbiAgICB9XG5cbiAgICBpZiAodG9rZW4gIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLnRva2VuID0gdG9rZW47XG4gICAgfVxuXG4gICAgaWYgKHN5bmNFbmFibGVkICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5zeW5jRW5hYmxlZCA9IHN5bmNFbmFibGVkO1xuICAgIH1cblxuICAgIGlmIChjb2xvcnMgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLmNvbG9ycyA9IGNvbG9ycztcbiAgICB9XG5cbiAgICBpZiAocGFnZVRva2VuICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5wYWdlVG9rZW4gPSBwYWdlVG9rZW47XG4gICAgfVxuXG4gICAgaWYgKHN5bmNUb2tlbiAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMuc3luY1Rva2VuID0gc3luY1Rva2VuO1xuICAgIH1cblxuICAgIGlmIChjbGllbnRUeXBlICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5jbGllbnRUeXBlID0gY2xpZW50VHlwZTtcbiAgICB9XG5cbiAgICBjb25zdCByZXM6IHtcbiAgICAgIGRhdGE6IHsgdXBkYXRlX0NhbGVuZGFyX0ludGVncmF0aW9uX2J5X3BrOiBDYWxlbmRhckludGVncmF0aW9uVHlwZSB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KHBvc3RncmFwaGlsZUdyYXBoVXJsLCB7XG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1BZG1pbi1TZWNyZXQnOiBwb3N0Z3JhcGhpbGVBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgYXBwU2VydmljZUxvZ2dlci5pbmZvKFxuICAgICAgJ1t1cGRhdGVHb29nbGVJbnRlZ3JhdGlvbl0gU3VjY2Vzc2Z1bGx5IHVwZGF0ZWQgR29vZ2xlIENhbGVuZGFyIGludGVncmF0aW9uLicsXG4gICAgICB7XG4gICAgICAgIGludGVncmF0aW9uSWQ6IHJlcz8uZGF0YT8udXBkYXRlX0NhbGVuZGFyX0ludGVncmF0aW9uX2J5X3BrPy5pZCxcbiAgICAgICAgZW5hYmxlZCxcbiAgICAgIH1cbiAgICApO1xuICAgIHJldHVybiByZXM/LmRhdGE/LnVwZGF0ZV9DYWxlbmRhcl9JbnRlZ3JhdGlvbl9ieV9waztcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgYXBwU2VydmljZUxvZ2dlci5lcnJvcihcbiAgICAgICdbdXBkYXRlR29vZ2xlSW50ZWdyYXRpb25dIFVuYWJsZSB0byB1cGRhdGUgR29vZ2xlIENhbGVuZGFyIGludGVncmF0aW9uLicsXG4gICAgICB7IGlkLCBlcnJvcjogZS5tZXNzYWdlLCBzdGFjazogZS5zdGFjaywgZGV0YWlsczogZSB9XG4gICAgKTtcbiAgICAvLyBPcmlnaW5hbCBmdW5jdGlvbiBpbXBsaWNpdGx5IHJldHVybnMgdW5kZWZpbmVkLlxuICB9XG59O1xuXG5leHBvcnQgY29uc3Qgc2NoZWR1bGVNZWV0aW5nID0gYXN5bmMgKFxuICBwYXlsb2FkOiBTY2hlZHVsZU1lZXRpbmdSZXF1ZXN0VHlwZVxuICAvLyBUT0RPOiBBZGQgdXNlcklkIGFuZCB0b2tlbiBvbmNlIGF1dGggaXMgZmlndXJlZCBvdXQgZm9yIHRoaXMgZW5kcG9pbnRcbik6IFByb21pc2U8YW55PiA9PiB7XG4gIC8vIGVzbGludC1kaXNhYmxlLWxpbmUgQHR5cGVzY3JpcHQtZXNsaW50L25vLWV4cGxpY2l0LWFueVxuICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ3NjaGVkdWxlTWVldGluZyc7XG4gIGNvbnN0IHVybCA9IGAke1NDSEVEVUxFUl9BUElfVVJMfS90aW1lVGFibGUvdXNlci9zY2hlZHVsZU1lZXRpbmdgO1xuICBhcHBTZXJ2aWNlTG9nZ2VyLmluZm8oYFske29wZXJhdGlvbk5hbWV9XSBDYWxsZWQuYCwge1xuICAgIHVybCxcbiAgICByZXF1ZXN0UGF5bG9hZDogcGF5bG9hZCxcbiAgfSk7XG5cbiAgdHJ5IHtcbiAgICAvLyBUaGlzIGdvdC5wb3N0IGNhbGwgd2lsbCBiZSB3cmFwcGVkIHdpdGggcmVzaWxpZW5jZSBsYXRlci5cbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QodXJsLCB7XG4gICAgICAgIGpzb246IHBheWxvYWQsXG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgIC8vICdBdXRob3JpemF0aW9uJzogYEJlYXJlciAke3Rva2VufWAsIC8vIFRPRE86IEFkZCB3aGVuIGF1dGggaXMgYXZhaWxhYmxlXG4gICAgICAgIH0sXG4gICAgICAgIC8vIHRpbWVvdXQ6IHsgcmVxdWVzdDogMTUwMDAgfSwgLy8gRXhhbXBsZTogQWRkaW5nIGEgdGltZW91dFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBhcHBTZXJ2aWNlTG9nZ2VyLmluZm8oXG4gICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIFN1Y2Nlc3NmdWxseSBzY2hlZHVsZWQgbWVldGluZy5gLFxuICAgICAgeyB1cmwsIHJlc3BvbnNlIH1cbiAgICApO1xuICAgIHJldHVybiByZXNwb25zZTtcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgY29uc3QgZXJyb3JDb250ZXh0ID0ge1xuICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgIHVybCxcbiAgICAgIHJlcXVlc3RQYXlsb2FkOiBwYXlsb2FkLFxuICAgICAgZXJyb3I6IGUubWVzc2FnZSxcbiAgICAgIGNvZGU6IGUuY29kZSxcbiAgICAgIHN0YXR1c0NvZGU6IGUucmVzcG9uc2U/LnN0YXR1c0NvZGUsXG4gICAgICByZXNwb25zZUJvZHk6IGUucmVzcG9uc2U/LmJvZHksXG4gICAgICBzdGFjazogZS5zdGFjayxcbiAgICB9O1xuICAgIGFwcFNlcnZpY2VMb2dnZXIuZXJyb3IoXG4gICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIEVycm9yIGNhbGxpbmcgc2NoZWR1bGVNZWV0aW5nIEFQSS5gLFxuICAgICAgZXJyb3JDb250ZXh0XG4gICAgKTtcblxuICAgIC8vIFJldGhyb3cgYSBtb3JlIHN0cnVjdHVyZWQgZXJyb3Igb3IgdGhlIG9yaWdpbmFsIGVycm9yXG4gICAgLy8gVGhlIG9yaWdpbmFsIGNvZGUgcmV0aHJldyBhIG5ldyBlcnJvciBiYXNlZCBvbiBwYXJzaW5nIHRoZSByZXNwb25zZSBib2R5LlxuICAgIGlmIChlPy5yZXNwb25zZT8uYm9keSkge1xuICAgICAgdHJ5IHtcbiAgICAgICAgLy8gQXR0ZW1wdCB0byBwYXJzZSBhcyBKU09OLCBidXQgaGFuZGxlIG5vbi1KU09OIHJlc3BvbnNlcyBncmFjZWZ1bGx5XG4gICAgICAgIGNvbnN0IGVycm9yQm9keVN0ciA9XG4gICAgICAgICAgdHlwZW9mIGUucmVzcG9uc2UuYm9keSA9PT0gJ3N0cmluZydcbiAgICAgICAgICAgID8gZS5yZXNwb25zZS5ib2R5XG4gICAgICAgICAgICA6IEpTT04uc3RyaW5naWZ5KGUucmVzcG9uc2UuYm9keSk7XG4gICAgICAgIGxldCBwYXJzZWRFcnJvckJvZHk7XG4gICAgICAgIHRyeSB7XG4gICAgICAgICAgcGFyc2VkRXJyb3JCb2R5ID0gSlNPTi5wYXJzZShlcnJvckJvZHlTdHIpO1xuICAgICAgICB9IGNhdGNoIChqc29uUGFyc2VFcnJvcikge1xuICAgICAgICAgIC8vIElmIGJvZHkgaXMgbm90IEpTT04sIHVzZSB0aGUgcmF3IHN0cmluZ1xuICAgICAgICAgIHBhcnNlZEVycm9yQm9keSA9IHsgbWVzc2FnZTogZXJyb3JCb2R5U3RyIH07XG4gICAgICAgIH1cbiAgICAgICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgICAgIGBBUEkgRXJyb3IgZnJvbSAke29wZXJhdGlvbk5hbWV9OiAke3BhcnNlZEVycm9yQm9keS5tZXNzYWdlIHx8IGVycm9yQm9keVN0cn1gXG4gICAgICAgICk7XG4gICAgICB9IGNhdGNoIChwYXJzZUVycm9yOiBhbnkpIHtcbiAgICAgICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgICAgIGBBUEkgRXJyb3IgZnJvbSAke29wZXJhdGlvbk5hbWV9ICh1bnBhcnNlYWJsZSBib2R5KTogJHtlLnJlc3BvbnNlLmJvZHkgfHwgZS5tZXNzYWdlfWBcbiAgICAgICAgKTtcbiAgICAgIH1cbiAgICB9XG4gICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgZS5tZXNzYWdlIHx8IGBGYWlsZWQgdG8gJHtvcGVyYXRpb25OYW1lfSBkdWUgdG8gYW4gdW5rbm93biBlcnJvcmBcbiAgICApO1xuICB9XG59O1xuIl19