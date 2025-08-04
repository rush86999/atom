"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.updateZoomIntegration = exports.encryptZoomTokens = exports.decryptZoomTokens = exports.updateAccessTokenCalendarIntegration = exports.deAuthZoomGivenUserId = exports.getMinimalCalendarIntegration = exports.generateGoogleAuthUrl = exports.exchangeCodeForTokens = exports.verifyZoomWebhook = exports.validateZoomWebook = void 0;
const got_1 = __importDefault(require("got"));
const dayjs_1 = __importDefault(require("dayjs"));
const isoWeek_1 = __importDefault(require("dayjs/plugin/isoWeek"));
const duration_1 = __importDefault(require("dayjs/plugin/duration"));
const isBetween_1 = __importDefault(require("dayjs/plugin/isBetween"));
const timezone_1 = __importDefault(require("dayjs/plugin/timezone"));
const utc_1 = __importDefault(require("dayjs/plugin/utc"));
const constants_1 = require("@lib/constants");
const googleapis_1 = require("googleapis");
const crypto_1 = __importDefault(require("crypto"));
const graphqlClient_1 = require("./graphqlClient");
const GOOGLE_CALENDAR_SERVICE_NAME = 'google_calendar';
dayjs_1.default.extend(isoWeek_1.default);
dayjs_1.default.extend(duration_1.default);
dayjs_1.default.extend(isBetween_1.default);
dayjs_1.default.extend(timezone_1.default);
dayjs_1.default.extend(utc_1.default);
const oauth2Client = new googleapis_1.google.auth.OAuth2(constants_1.googleClientIdWeb, constants_1.googleClientSecretWeb, constants_1.googleRedirectUrl);
// Re-implementing saveUserTokens here
async function saveUserTokens(userId, tokens) {
    console.log(`Saving tokens for userId: ${userId}, service: ${GOOGLE_CALENDAR_SERVICE_NAME}`);
    const mutation = `
    mutation UpsertUserToken($objects: [user_tokens_insert_input!]!) {
      insert_user_tokens(
        objects: $objects,
        on_conflict: {
          constraint: user_tokens_user_id_service_name_key,
          update_columns: [access_token, refresh_token, expiry_date, scope, token_type, updated_at]
        }
      ) {
        affected_rows
      }
    }
  `;
    const tokenDataForDb = {
        user_id: userId,
        service_name: GOOGLE_CALENDAR_SERVICE_NAME,
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        expiry_date: tokens.expiry_date
            ? new Date(tokens.expiry_date).toISOString()
            : null,
        scope: tokens.scope,
        token_type: tokens.token_type,
        updated_at: new Date().toISOString(),
    };
    const variables = { objects: [tokenDataForDb] };
    const operationName = 'UpsertUserToken';
    try {
        const response = await (0, graphqlClient_1.executeGraphQLMutation)(mutation, variables, operationName, userId);
        if (!response ||
            !response.insert_user_tokens ||
            response.insert_user_tokens.affected_rows === 0) {
            console.warn(`Token save operation for user ${userId} reported 0 affected_rows.`, response);
        }
        else {
            console.log(`Tokens saved successfully to database for user ${userId}. Affected rows: ${response.insert_user_tokens.affected_rows}`);
        }
        return { ok: true };
    }
    catch (error) {
        console.error(`Exception during saveUserTokens for userId ${userId}:`, error);
        return {
            ok: false,
            error: {
                message: 'Failed to save Google Calendar tokens.',
                details: error.message,
            },
        };
    }
}
const validateZoomWebook = (request, response) => {
    const hashForValidate = crypto_1.default
        .createHmac('sha256', process.env.ZOOM_WEBHOOK_SECRET_TOKEN)
        .update(request.body.payload.plainToken)
        .digest('hex');
    // console.log(hashForValidate, ' hashForValidate')
    return response.status(200).json({
        plainToken: request.body.payload.plainToken,
        encryptedToken: hashForValidate,
    });
};
exports.validateZoomWebook = validateZoomWebook;
const verifyZoomWebhook = (request) => {
    const message = `v0:${request.headers['x-zm-request-timestamp']}:${JSON.stringify(request.body)}`;
    const hashForVerify = crypto_1.default
        .createHmac('sha256', process.env.ZOOM_WEBHOOK_SECRET_TOKEN)
        .update(message)
        .digest('hex');
    const signature = `v0=${hashForVerify}`;
    if (request.headers['x-zm-signature'] === signature) {
        // Webhook request came from Zoom
        return true;
    }
    throw new Error('Failed zoom webhook verification using secret token & sha256');
};
exports.verifyZoomWebhook = verifyZoomWebhook;
const exchangeCodeForTokens = async (code, userId) => {
    try {
        let { tokens } = await oauth2Client.getToken(code);
        oauth2Client.setCredentials(tokens);
        if (tokens) {
            await saveUserTokens(userId, tokens);
        }
        return tokens;
    }
    catch (e) {
        console.log(e, ' unable to exchange code for tokens');
    }
};
exports.exchangeCodeForTokens = exchangeCodeForTokens;
const generateGoogleAuthUrl = (state) => {
    // Access scopes for read-only Drive activity.
    const scopes = [
        'https://www.googleapis.com/auth/calendar.readonly',
        'https://www.googleapis.com/auth/calendar.events',
        'https://www.googleapis.com/auth/contacts.readonly',
    ];
    // Generate a url that asks permissions for the Calendar activity scope
    const authorizationUrl = oauth2Client.generateAuthUrl({
        // 'online' (default) or 'offline' (gets refresh_token)
        access_type: 'online',
        /** Pass in the scopes array defined above.
         * Alternatively, if only one scope is needed, you can pass a scope URL as a string */
        scope: scopes,
        // Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes: true,
        state,
    });
    // console.log(authorizationUrl, ' authorizationUrl')
    return authorizationUrl;
};
exports.generateGoogleAuthUrl = generateGoogleAuthUrl;
const getMinimalCalendarIntegration = async (userId, resource) => {
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
        const res = await got_1.default
            .post(constants_1.hasuraGraphUrl, {
            json: {
                operationName,
                query,
                variables,
            },
            headers: {
                'X-Hasura-Admin-Secret': constants_1.hasuraAdminSecret,
                'Content-Type': 'application/json',
                'X-Hasura-Role': 'admin',
            },
        })
            .json();
        // console.log(res, ' res inside getCalendarIntegration')
        if (res?.data?.Calendar_Integration?.length > 0) {
            return res?.data?.Calendar_Integration?.[0];
        }
    }
    catch (e) {
        console.log(e, ' unable to get calendar integration');
    }
};
exports.getMinimalCalendarIntegration = getMinimalCalendarIntegration;
const deAuthZoomGivenUserId = async (appId) => {
    try {
        const operationName = 'DeAuthZoomByAppId';
        const query = `
            mutation DeAuthZoomByAppId($appId: String!) {
                update_Calendar_Integration(where: {appId: {_eq: $appId}}, _set: {expiresAt: null, refreshToken: null, token: null, enabled: false, syncEnabled: false}) {
                    affected_rows
                    returning {
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
            }
        `;
        const variables = {
            appId,
        };
        const res = await got_1.default
            .post(constants_1.hasuraGraphUrl, {
            json: {
                operationName,
                query,
                variables,
            },
            headers: {
                'X-Hasura-Admin-Secret': constants_1.hasuraAdminSecret,
                'Content-Type': 'application/json',
                'X-Hasura-Role': 'admin',
            },
        })
            .json();
        console.log(res?.data?.update_Calendar_Integration?.affected_rows, ' successfully deAuth zoom');
    }
    catch (e) {
        console.log(e, ' unable to deAuth Zoom');
    }
};
exports.deAuthZoomGivenUserId = deAuthZoomGivenUserId;
const updateAccessTokenCalendarIntegration = async (id, token, expiresIn, enabled, refreshToken) => {
    try {
        const operationName = 'updateCalendarIntegration';
        const query = `
      mutation updateCalendarIntegration($id: uuid!,${token !== undefined ? ' $token: String,' : ''}${refreshToken !== undefined ? ' $refreshToken: String,' : ''}${expiresIn !== undefined ? ' $expiresAt: timestamptz,' : ''}${enabled !== undefined ? ' $enabled: Boolean,' : ''}) {
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
                ? (0, dayjs_1.default)().add(expiresIn, 'seconds').toISOString()
                : null,
        };
        if (enabled !== undefined) {
            variables.enabled = enabled;
        }
        if (refreshToken !== undefined) {
            variables.refreshToken = refreshToken;
        }
        const res = await got_1.default
            .post(constants_1.hasuraGraphUrl, {
            json: {
                operationName,
                query,
                variables,
            },
            headers: {
                'X-Hasura-Admin-Secret': constants_1.hasuraAdminSecret,
                'Content-Type': 'application/json',
                'X-Hasura-Role': 'admin',
            },
        })
            .json();
        // console.log(res, ' res inside updateCalendarIntegration')
    }
    catch (e) {
        console.log(e, ' unable to update calendar integration');
    }
};
exports.updateAccessTokenCalendarIntegration = updateAccessTokenCalendarIntegration;
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
                ? (0, dayjs_1.default)().add(expiresIn, 'seconds').toISOString()
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
        const res = await got_1.default
            .post(constants_1.hasuraGraphUrl, {
            json: {
                operationName,
                query,
                variables,
            },
            headers: {
                'X-Hasura-Admin-Secret': constants_1.hasuraAdminSecret,
                'Content-Type': 'application/json',
                'X-Hasura-Role': 'admin',
            },
        })
            .json();
        // console.log(res, ' res inside updateCalendarIntegration')
    }
    catch (e) {
        console.log(e, ' unable to update zoom integration');
    }
};
exports.updateZoomIntegration = updateZoomIntegration;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7O0FBQUEsOENBQXNCO0FBQ3RCLGtEQUEwQjtBQUMxQixtRUFBMkM7QUFDM0MscUVBQTZDO0FBQzdDLHVFQUErQztBQUMvQyxxRUFBNkM7QUFDN0MsMkRBQW1DO0FBRW5DLDhDQVN3QjtBQU14QiwyQ0FBb0M7QUFFcEMsb0RBQTRDO0FBQzVDLG1EQUF5RDtBQUd6RCxNQUFNLDRCQUE0QixHQUFHLGlCQUFpQixDQUFDO0FBRXZELGVBQUssQ0FBQyxNQUFNLENBQUMsaUJBQU8sQ0FBQyxDQUFDO0FBQ3RCLGVBQUssQ0FBQyxNQUFNLENBQUMsa0JBQVEsQ0FBQyxDQUFDO0FBQ3ZCLGVBQUssQ0FBQyxNQUFNLENBQUMsbUJBQVMsQ0FBQyxDQUFDO0FBQ3hCLGVBQUssQ0FBQyxNQUFNLENBQUMsa0JBQVEsQ0FBQyxDQUFDO0FBQ3ZCLGVBQUssQ0FBQyxNQUFNLENBQUMsYUFBRyxDQUFDLENBQUM7QUFFbEIsTUFBTSxZQUFZLEdBQUcsSUFBSSxtQkFBTSxDQUFDLElBQUksQ0FBQyxNQUFNLENBQ3pDLDZCQUFpQixFQUNqQixpQ0FBcUIsRUFDckIsNkJBQWlCLENBQ2xCLENBQUM7QUFFRixzQ0FBc0M7QUFDdEMsS0FBSyxVQUFVLGNBQWMsQ0FDM0IsTUFBYyxFQUNkLE1BQW1CO0lBRW5CLE9BQU8sQ0FBQyxHQUFHLENBQ1QsNkJBQTZCLE1BQU0sY0FBYyw0QkFBNEIsRUFBRSxDQUNoRixDQUFDO0lBRUYsTUFBTSxRQUFRLEdBQUc7Ozs7Ozs7Ozs7OztHQVloQixDQUFDO0lBRUYsTUFBTSxjQUFjLEdBQUc7UUFDckIsT0FBTyxFQUFFLE1BQU07UUFDZixZQUFZLEVBQUUsNEJBQTRCO1FBQzFDLFlBQVksRUFBRSxNQUFNLENBQUMsWUFBWTtRQUNqQyxhQUFhLEVBQUUsTUFBTSxDQUFDLGFBQWE7UUFDbkMsV0FBVyxFQUFF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QUFTO2dCQUNsQixDQUFDLENBQUMsSUFBQSxlQUFLLEdBQUUsQ0FBQyxHQUFHLENBQUMsU0FBUyxFQUFFLFNBQVMsQ0FBQyxDQUFDLFdBQVcsRUFBRTtnQkFDakQsQ0FBQyxDQUFDLElBQUk7WUFDUixZQUFZLEVBQ1YsWUFBWSxLQUFLLFNBQVM7Z0JBQ3hCLENBQUMsQ0FBQyxTQUFTO2dCQUNYLENBQUMsQ0FBQyxlQUFlLEVBQUUscUJBQXFCO1lBQzVDLGdCQUFnQjtZQUNoQixlQUFlO1lBQ2YsWUFBWTtZQUNaLFdBQVc7WUFDWCxPQUFPO1NBQ1IsQ0FBQztRQUVGLE1BQU0sR0FBRyxHQUFHLE1BQU0sYUFBRzthQUNsQixJQUFJLENBQUMsMEJBQWMsRUFBRTtZQUNwQixJQUFJLEVBQUU7Z0JBQ0osYUFBYTtnQkFDYixLQUFLO2dCQUNMLFNBQVM7YUFDVjtZQUNELE9BQU8sRUFBRTtnQkFDUCx1QkFBdUIsRUFBRSw2QkFBaUI7Z0JBQzFDLGNBQWMsRUFBRSxrQkFBa0I7Z0JBQ2xDLGVBQWUsRUFBRSxPQUFPO2FBQ3pCO1NBQ0YsQ0FBQzthQUNELElBQUksRUFBRSxDQUFDO1FBRVYsNERBQTREO0lBQzlELENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsb0NBQW9DLENBQUMsQ0FBQztJQUN2RCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBMUhXLFFBQUEscUJBQXFCLHlCQTBIaEMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgZ290IGZyb20gJ2dvdCc7XG5pbXBvcnQgZGF5anMgZnJvbSAnZGF5anMnO1xuaW1wb3J0IGlzb1dlZWsgZnJvbSAnZGF5anMvcGx1Z2luL2lzb1dlZWsnO1xuaW1wb3J0IGR1cmF0aW9uIGZyb20gJ2RheWpzL3BsdWdpbi9kdXJhdGlvbic7XG5pbXBvcnQgaXNCZXR3ZWVuIGZyb20gJ2RheWpzL3BsdWdpbi9pc0JldHdlZW4nO1xuaW1wb3J0IHRpbWV6b25lIGZyb20gJ2RheWpzL3BsdWdpbi90aW1lem9uZSc7XG5pbXBvcnQgdXRjIGZyb20gJ2RheWpzL3BsdWdpbi91dGMnO1xuaW1wb3J0IF8gZnJvbSAnbG9kYXNoJztcbmltcG9ydCB7XG4gIGdvb2dsZUNsaWVudElkV2ViLFxuICBnb29nbGVDbGllbnRTZWNyZXRXZWIsXG4gIGdvb2dsZVJlZGlyZWN0VXJsLFxuICBoYXN1cmFBZG1pblNlY3JldCxcbiAgaGFzdXJhR3JhcGhVcmwsXG4gIHpvb21JVkZvclBhc3MsXG4gIHpvb21QYXNzS2V5LFxuICB6b29tU2FsdEZvclBhc3MsXG59IGZyb20gJ0BsaWIvY29uc3RhbnRzJztcbmltcG9ydCB7XG4gIENhbGVuZGFySW50ZWdyYXRpb25UeXBlLFxuICBab29tV2ViaG9va1JlcXVlc3RUeXBlLFxuICBab29tV2ViaG9va1ZhbGlkYXRpb25SZXF1ZXN0VHlwZSxcbn0gZnJvbSAnQGxpYi90eXBlcyc7XG5pbXBvcnQgeyBnb29nbGUgfSBmcm9tICdnb29nbGVhcGlzJztcbmltcG9ydCB0eXBlIHsgTmV4dEFwaVJlc3BvbnNlIH0gZnJvbSAnbmV4dCc7XG5pbXBvcnQgY3J5cHRvLCB7IEJpbmFyeUxpa2UgfSBmcm9tICdjcnlwdG8nO1xuaW1wb3J0IHsgZXhlY3V0ZUdyYXBoUUxNdXRhdGlvbiB9IGZyb20gJy4vZ3JhcGhxbENsaWVudCc7XG5pbXBvcnQgeyBDcmVkZW50aWFscyBhcyBPQXV0aDJUb2tlbiB9IGZyb20gJ2dvb2dsZS1hdXRoLWxpYnJhcnknO1xuXG5jb25zdCBHT09HTEVfQ0FMRU5EQVJfU0VSVklDRV9OQU1FID0gJ2dvb2dsZV9jYWxlbmRhcic7XG5cbmRheWpzLmV4dGVuZChpc29XZWVrKTtcbmRheWpzLmV4dGVuZChkdXJhdGlvbik7XG5kYXlqcy5leHRlbmQoaXNCZXR3ZWVuKTtcbmRheWpzLmV4dGVuZCh0aW1lem9uZSk7XG5kYXlqcy5leHRlbmQodXRjKTtcblxuY29uc3Qgb2F1dGgyQ2xpZW50ID0gbmV3IGdvb2dsZS5hdXRoLk9BdXRoMihcbiAgZ29vZ2xlQ2xpZW50SWRXZWIsXG4gIGdvb2dsZUNsaWVudFNlY3JldFdlYixcbiAgZ29vZ2xlUmVkaXJlY3RVcmxcbik7XG5cbi8vIFJlLWltcGxlbWVudGluZyBzYXZlVXNlclRva2VucyBoZXJlXG5hc3luYyBmdW5jdGlvbiBzYXZlVXNlclRva2VucyhcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHRva2VuczogT0F1dGgyVG9rZW5cbik6IFByb21pc2U8eyBvazogYm9vbGVhbjsgZXJyb3I/OiBhbnkgfT4ge1xuICBjb25zb2xlLmxvZyhcbiAgICBgU2F2aW5nIHRva2VucyBmb3IgdXNlcklkOiAke3VzZXJJZH0sIHNlcnZpY2U6ICR7R09PR0xFX0NBTEVOREFSX1NFUlZJQ0VfTkFNRX1gXG4gICk7XG5cbiAgY29uc3QgbXV0YXRpb24gPSBgXG4gICAgbXV0YXRpb24gVXBzZXJ0VXNlclRva2VuKCRvYmplY3RzOiBbdXNlcl90b2tlbnNfaW5zZXJ0X2lucHV0IV0hKSB7XG4gICAgICBpbnNlcnRfdXNlcl90b2tlbnMoXG4gICAgICAgIG9iamVjdHM6ICRvYmplY3RzLFxuICAgICAgICBvbl9jb25mbGljdDoge1xuICAgICAgICAgIGNvbnN0cmFpbnQ6IHVzZXJfdG9rZW5zX3VzZXJfaWRfc2VydmljZV9uYW1lX2tleSxcbiAgICAgICAgICB1cGRhdGVfY29sdW1uczogW2FjY2Vzc190b2tlbiwgcmVmcmVzaF90b2tlbiwgZXhwaXJ5X2RhdGUsIHNjb3BlLCB0b2tlbl90eXBlLCB1cGRhdGVkX2F0XVxuICAgICAgICB9XG4gICAgICApIHtcbiAgICAgICAgYWZmZWN0ZWRfcm93c1xuICAgICAgfVxuICAgIH1cbiAgYDtcblxuICBjb25zdCB0b2tlbkRhdGFGb3JEYiA9IHtcbiAgICB1c2VyX2lkOiB1c2VySWQsXG4gICAgc2VydmljZV9uYW1lOiBHT09HTEVfQ0FMRU5EQVJfU0VSVklDRV9OQU1FLFxuICAgIGFjY2Vzc190b2tlbjogdG9rZW5zLmFjY2Vzc190b2tlbixcbiAgICByZWZyZXNoX3Rva2VuOiB0b2tlbnMucmVmcmVzaF90b2tlbixcbiAgICBleHBpcnlfZGF0ZTogdG9rZW5zLmV4cGlyeV9kYXRlXG4gICAgICA/IG5ldyBEYXRlKHRva2Vucy5leHBpcnlfZGF0ZSkudG9JU09TdHJpbmcoKVxuICAgICAgOiBudWxsLFxuICAgIHNjb3BlOiB0b2tlbnMuc2NvcGUsXG4gICAgdG9rZW5fdHlwZTogdG9rZW5zLnRva2VuX3R5cGUsXG4gICAgdXBkYXRlZF9hdDogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxuICB9O1xuXG4gIGNvbnN0IHZhcmlhYmxlcyA9IHsgb2JqZWN0czogW3Rva2VuRGF0YUZvckRiXSB9O1xuICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ1Vwc2VydFVzZXJUb2tlbic7XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGV4ZWN1dGVHcmFwaFFMTXV0YXRpb248e1xuICAgICAgaW5zZXJ0X3VzZXJfdG9rZW5zOiB7IGFmZmVjdGVkX3Jvd3M6IG51bWJlciB9O1xuICAgIH0+KG11dGF0aW9uLCB2YXJpYWJsZXMsIG9wZXJhdGlvbk5hbWUsIHVzZXJJZCk7XG5cbiAgICBpZiAoXG4gICAgICAhcmVzcG9uc2UgfHxcbiAgICAgICFyZXNwb25zZS5pbnNlcnRfdXNlcl90b2tlbnMgfHxcbiAgICAgIHJlc3BvbnNlLmluc2VydF91c2VyX3Rva2Vucy5hZmZlY3RlZF9yb3dzID09PSAwXG4gICAgKSB7XG4gICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgIGBUb2tlbiBzYXZlIG9wZXJhdGlvbiBmb3IgdXNlciAke3VzZXJJZH0gcmVwb3J0ZWQgMCBhZmZlY3RlZF9yb3dzLmAsXG4gICAgICAgIHJlc3BvbnNlXG4gICAgICApO1xuICAgIH0gZWxzZSB7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgYFRva2VucyBzYXZlZCBzdWNjZXNzZnVsbHkgdG8gZGF0YWJhc2UgZm9yIHVzZXIgJHt1c2VySWR9LiBBZmZlY3RlZCByb3dzOiAke3Jlc3BvbnNlLmluc2VydF91c2VyX3Rva2Vucy5hZmZlY3RlZF9yb3dzfWBcbiAgICAgICk7XG4gICAgfVxuICAgIHJldHVybiB7IG9rOiB0cnVlIH07XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgYEV4Y2VwdGlvbiBkdXJpbmcgc2F2ZVVzZXJUb2tlbnMgZm9yIHVzZXJJZCAke3VzZXJJZH06YCxcbiAgICAgIGVycm9yXG4gICAgKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgbWVzc2FnZTogJ0ZhaWxlZCB0byBzYXZlIEdvb2dsZSBDYWxlbmRhciB0b2tlbnMuJyxcbiAgICAgICAgZGV0YWlsczogZXJyb3IubWVzc2FnZSxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufVxuXG5leHBvcnQgY29uc3QgdmFsaWRhdGVab29tV2Vib29rID0gKFxuICByZXF1ZXN0OiBab29tV2ViaG9va1ZhbGlkYXRpb25SZXF1ZXN0VHlwZSxcbiAgcmVzcG9uc2U6IE5leHRBcGlSZXNwb25zZVxuKSA9PiB7XG4gIGNvbnN0IGhhc2hGb3JWYWxpZGF0ZSA9IGNyeXB0b1xuICAgIC5jcmVhdGVIbWFjKCdzaGEyNTYnLCBwcm9jZXNzLmVudi5aT09NX1dFQkhPT0tfU0VDUkVUX1RPS0VOIGFzIEJpbmFyeUxpa2UpXG4gICAgLnVwZGF0ZShyZXF1ZXN0LmJvZHkucGF5bG9hZC5wbGFpblRva2VuKVxuICAgIC5kaWdlc3QoJ2hleCcpO1xuICAvLyBjb25zb2xlLmxvZyhoYXNoRm9yVmFsaWRhdGUsICcgaGFzaEZvclZhbGlkYXRlJylcbiAgcmV0dXJuIHJlc3BvbnNlLnN0YXR1cygyMDApLmpzb24oe1xuICAgIHBsYWluVG9rZW46IHJlcXVlc3QuYm9keS5wYXlsb2FkLnBsYWluVG9rZW4sXG4gICAgZW5jcnlwdGVkVG9rZW46IGhhc2hGb3JWYWxpZGF0ZSxcbiAgfSk7XG59O1xuXG5leHBvcnQgY29uc3QgdmVyaWZ5Wm9vbVdlYmhvb2sgPSAocmVxdWVzdDogWm9vbVdlYmhvb2tSZXF1ZXN0VHlwZSkgPT4ge1xuICBjb25zdCBtZXNzYWdlID0gYHYwOiR7cmVxdWVzdC5oZWFkZXJzWyd4LXptLXJlcXVlc3QtdGltZXN0YW1wJ119OiR7SlNPTi5zdHJpbmdpZnkocmVxdWVzdC5ib2R5KX1gO1xuXG4gIGNvbnN0IGhhc2hGb3JWZXJpZnkgPSBjcnlwdG9cbiAgICAuY3JlYXRlSG1hYygnc2hhMjU2JywgcHJvY2Vzcy5lbnYuWk9PTV9XRUJIT09LX1NFQ1JFVF9UT0tFTiBhcyBCaW5hcnlMaWtlKVxuICAgIC51cGRhdGUobWVzc2FnZSlcbiAgICAuZGlnZXN0KCdoZXgnKTtcblxuICBjb25zdCBzaWduYXR1cmUgPSBgdjA9JHtoYXNoRm9yVmVyaWZ5fWA7XG5cbiAgaWYgKHJlcXVlc3QuaGVhZGVyc1sneC16bS1zaWduYXR1cmUnXSA9PT0gc2lnbmF0dXJlKSB7XG4gICAgLy8gV2ViaG9vayByZXF1ZXN0IGNhbWUgZnJvbSBab29tXG4gICAgcmV0dXJuIHRydWU7XG4gIH1cblxuICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgJ0ZhaWxlZCB6b29tIHdlYmhvb2sgdmVyaWZpY2F0aW9uIHVzaW5nIHNlY3JldCB0b2tlbiAmIHNoYTI1NidcbiAgKTtcbn07XG5cbmV4cG9ydCBjb25zdCBleGNoYW5nZUNvZGVGb3JUb2tlbnMgPSBhc3luYyAoY29kZTogc3RyaW5nLCB1c2VySWQ6IHN0cmluZykgPT4ge1xuICB0cnkge1xuICAgIGxldCB7IHRva2VucyB9ID0gYXdhaXQgb2F1dGgyQ2xpZW50LmdldFRva2VuKGNvZGUpO1xuICAgIG9hdXRoMkNsaWVudC5zZXRDcmVkZW50aWFscyh0b2tlbnMpO1xuICAgIGlmICh0b2tlbnMpIHtcbiAgICAgIGF3YWl0IHNhdmVVc2VyVG9rZW5zKHVzZXJJZCwgdG9rZW5zKTtcbiAgICB9XG4gICAgcmV0dXJuIHRva2VucztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGV4Y2hhbmdlIGNvZGUgZm9yIHRva2VucycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVHb29nbGVBdXRoVXJsID0gKHN0YXRlOiBzdHJpbmcpID0+IHtcbiAgLy8gQWNjZXNzIHNjb3BlcyBmb3IgcmVhZC1vbmx5IERyaXZlIGFjdGl2aXR5LlxuICBjb25zdCBzY29wZXMgPSBbXG4gICAgJ2h0dHBzOi8vd3d3Lmdvb2dsZWFwaXMuY29tL2F1dGgvY2FsZW5kYXIucmVhZG9ubHknLFxuICAgICdodHRwczovL3d3dy5nb29nbGVhcGlzLmNvbS9hdXRoL2NhbGVuZGFyLmV2ZW50cycsXG4gICAgJ2h0dHBzOi8vd3d3Lmdvb2dsZWFwaXMuY29tL2F1dGgvY29udGFjdHMucmVhZG9ubHknLFxuICBdO1xuXG4gIC8vIEdlbmVyYXRlIGEgdXJsIHRoYXQgYXNrcyBwZXJtaXNzaW9ucyBmb3IgdGhlIENhbGVuZGFyIGFjdGl2aXR5IHNjb3BlXG4gIGNvbnN0IGF1dGhvcml6YXRpb25VcmwgPSBvYXV0aDJDbGllbnQuZ2VuZXJhdGVBdXRoVXJsKHtcbiAgICAvLyAnb25saW5lJyAoZGVmYXVsdCkgb3IgJ29mZmxpbmUnIChnZXRzIHJlZnJlc2hfdG9rZW4pXG4gICAgYWNjZXNzX3R5cGU6ICdvbmxpbmUnLFxuICAgIC8qKiBQYXNzIGluIHRoZSBzY29wZXMgYXJyYXkgZGVmaW5lZCBhYm92ZS5cbiAgICAgKiBBbHRlcm5hdGl2ZWx5LCBpZiBvbmx5IG9uZSBzY29wZSBpcyBuZWVkZWQsIHlvdSBjYW4gcGFzcyBhIHNjb3BlIFVSTCBhcyBhIHN0cmluZyAqL1xuICAgIHNjb3BlOiBzY29wZXMsXG4gICAgLy8gRW5hYmxlIGluY3JlbWVudGFsIGF1dGhvcml6YXRpb24uIFJlY29tbWVuZGVkIGFzIGEgYmVzdCBwcmFjdGljZS5cbiAgICBpbmNsdWRlX2dyYW50ZWRfc2NvcGVzOiB0cnVlLFxuICAgIHN0YXRlLFxuICB9KTtcblxuICAvLyBjb25zb2xlLmxvZyhhdXRob3JpemF0aW9uVXJsLCAnIGF1dGhvcml6YXRpb25VcmwnKVxuXG4gIHJldHVybiBhdXRob3JpemF0aW9uVXJsO1xufTtcblxuZXhwb3J0IGNvbnN0IGdldE1pbmltYWxDYWxlbmRhckludGVncmF0aW9uID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgcmVzb3VyY2U6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdnZXRDYWxlbmRhckludGVncmF0aW9uJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgIHF1ZXJ5IGdldENhbGVuZGFySW50ZWdyYXRpb24oJHVzZXJJZDogdXVpZCEsICRyZXNvdXJjZTogU3RyaW5nISkge1xuICAgICAgICBDYWxlbmRhcl9JbnRlZ3JhdGlvbih3aGVyZToge3VzZXJJZDoge19lcTogJHVzZXJJZH0sIHJlc291cmNlOiB7X2VxOiAkcmVzb3VyY2V9fSkge1xuICAgICAgICAgICAgYXBwQWNjb3VudElkXG4gICAgICAgICAgICBhcHBFbWFpbFxuICAgICAgICAgICAgYXBwSWRcbiAgICAgICAgICAgIGNsaWVudFR5cGVcbiAgICAgICAgICAgIGNvbG9yc1xuICAgICAgICAgICAgY29udGFjdEVtYWlsXG4gICAgICAgICAgICBjb250YWN0Rmlyc3ROYW1lXG4gICAgICAgICAgICBjb250YWN0TGFzdE5hbWVcbiAgICAgICAgICAgIGNvbnRhY3ROYW1lXG4gICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgICAgZW5hYmxlZFxuICAgICAgICAgICAgZXhwaXJlc0F0XG4gICAgICAgICAgICBpZFxuICAgICAgICAgICAgbmFtZVxuICAgICAgICAgICAgcGFnZVRva2VuXG4gICAgICAgICAgICBwYXNzd29yZFxuICAgICAgICAgICAgcGhvbmVDb3VudHJ5XG4gICAgICAgICAgICBwaG9uZU51bWJlclxuICAgICAgICAgICAgcmVmcmVzaFRva2VuXG4gICAgICAgICAgICByZXNvdXJjZVxuICAgICAgICAgICAgc3luY0VuYWJsZWRcbiAgICAgICAgICAgIHN5bmNUb2tlblxuICAgICAgICAgICAgdG9rZW5cbiAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICB1c2VybmFtZVxuICAgICAgICB9XG4gICAgICB9XG4gICAgYDtcbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICB1c2VySWQsXG4gICAgICByZXNvdXJjZSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgQ2FsZW5kYXJfSW50ZWdyYXRpb246IENhbGVuZGFySW50ZWdyYXRpb25UeXBlW10gfSB9ID1cbiAgICAgIGF3YWl0IGdvdFxuICAgICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICAgIGpzb246IHtcbiAgICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSlcbiAgICAgICAgLmpzb24oKTtcblxuICAgIC8vIGNvbnNvbGUubG9nKHJlcywgJyByZXMgaW5zaWRlIGdldENhbGVuZGFySW50ZWdyYXRpb24nKVxuICAgIGlmIChyZXM/LmRhdGE/LkNhbGVuZGFyX0ludGVncmF0aW9uPy5sZW5ndGggPiAwKSB7XG4gICAgICByZXR1cm4gcmVzPy5kYXRhPy5DYWxlbmRhcl9JbnRlZ3JhdGlvbj8uWzBdO1xuICAgIH1cbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdldCBjYWxlbmRhciBpbnRlZ3JhdGlvbicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZGVBdXRoWm9vbUdpdmVuVXNlcklkID0gYXN5bmMgKGFwcElkOiBzdHJpbmcpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0RlQXV0aFpvb21CeUFwcElkJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIG11dGF0aW9uIERlQXV0aFpvb21CeUFwcElkKCRhcHBJZDogU3RyaW5nISkge1xuICAgICAgICAgICAgICAgIHVwZGF0ZV9DYWxlbmRhcl9JbnRlZ3JhdGlvbih3aGVyZToge2FwcElkOiB7X2VxOiAkYXBwSWR9fSwgX3NldDoge2V4cGlyZXNBdDogbnVsbCwgcmVmcmVzaFRva2VuOiBudWxsLCB0b2tlbjogbnVsbCwgZW5hYmxlZDogZmFsc2UsIHN5bmNFbmFibGVkOiBmYWxzZX0pIHtcbiAgICAgICAgICAgICAgICAgICAgYWZmZWN0ZWRfcm93c1xuICAgICAgICAgICAgICAgICAgICByZXR1cm5pbmcge1xuICAgICAgICAgICAgICAgICAgICAgICAgYXBwQWNjb3VudElkXG4gICAgICAgICAgICAgICAgICAgICAgICBhcHBFbWFpbFxuICAgICAgICAgICAgICAgICAgICAgICAgYXBwSWRcbiAgICAgICAgICAgICAgICAgICAgICAgIGNsaWVudFR5cGVcbiAgICAgICAgICAgICAgICAgICAgICAgIGNvbG9yc1xuICAgICAgICAgICAgICAgICAgICAgICAgY29udGFjdEVtYWlsXG4gICAgICAgICAgICAgICAgICAgICAgICBjb250YWN0Rmlyc3ROYW1lXG4gICAgICAgICAgICAgICAgICAgICAgICBjb250YWN0TGFzdE5hbWVcbiAgICAgICAgICAgICAgICAgICAgICAgIGNvbnRhY3ROYW1lXG4gICAgICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgICAgICAgICAgICAgICAgZW5hYmxlZFxuICAgICAgICAgICAgICAgICAgICAgICAgZXhwaXJlc0F0XG4gICAgICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICAgICAgbmFtZVxuICAgICAgICAgICAgICAgICAgICAgICAgcGFnZVRva2VuXG4gICAgICAgICAgICAgICAgICAgICAgICBwYXNzd29yZFxuICAgICAgICAgICAgICAgICAgICAgICAgcGhvbmVDb3VudHJ5XG4gICAgICAgICAgICAgICAgICAgICAgICBwaG9uZU51bWJlclxuICAgICAgICAgICAgICAgICAgICAgICAgcmVmcmVzaFRva2VuXG4gICAgICAgICAgICAgICAgICAgICAgICByZXNvdXJjZVxuICAgICAgICAgICAgICAgICAgICAgICAgc3luY0VuYWJsZWRcbiAgICAgICAgICAgICAgICAgICAgICAgIHN5bmNUb2tlblxuICAgICAgICAgICAgICAgICAgICAgICAgdG9rZW5cbiAgICAgICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgICAgICB1c2VybmFtZVxuICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuXG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgYXBwSWQsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlczoge1xuICAgICAgZGF0YToge1xuICAgICAgICB1cGRhdGVfQ2FsZW5kYXJfSW50ZWdyYXRpb246IHtcbiAgICAgICAgICBhZmZlY3RlZF9yb3dzOiBudW1iZXI7XG4gICAgICAgICAgcmV0dXJuaW5nOiBDYWxlbmRhckludGVncmF0aW9uVHlwZVtdO1xuICAgICAgICB9O1xuICAgICAgfTtcbiAgICB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgcmVzPy5kYXRhPy51cGRhdGVfQ2FsZW5kYXJfSW50ZWdyYXRpb24/LmFmZmVjdGVkX3Jvd3MsXG4gICAgICAnIHN1Y2Nlc3NmdWxseSBkZUF1dGggem9vbSdcbiAgICApO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZGVBdXRoIFpvb20nKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHVwZGF0ZUFjY2Vzc1Rva2VuQ2FsZW5kYXJJbnRlZ3JhdGlvbiA9IGFzeW5jIChcbiAgaWQ6IHN0cmluZyxcbiAgdG9rZW46IHN0cmluZyB8IG51bGwsXG4gIGV4cGlyZXNJbjogbnVtYmVyIHwgbnVsbCxcbiAgZW5hYmxlZD86IGJvb2xlYW4sXG4gIHJlZnJlc2hUb2tlbj86IHN0cmluZyB8IG51bGxcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAndXBkYXRlQ2FsZW5kYXJJbnRlZ3JhdGlvbic7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICBtdXRhdGlvbiB1cGRhdGVDYWxlbmRhckludGVncmF0aW9uKCRpZDogdXVpZCEsJHt0b2tlbiAhPT0gdW5kZWZpbmVkID8gJyAkdG9rZW46IFN0cmluZywnIDogJyd9JHtyZWZyZXNoVG9rZW4gIT09IHVuZGVmaW5lZCA/ICcgJHJlZnJlc2hUb2tlbjogU3RyaW5nLCcgOiAnJ30ke2V4cGlyZXNJbiAhPT0gdW5kZWZpbmVkID8gJyAkZXhwaXJlc0F0OiB0aW1lc3RhbXB0eiwnIDogJyd9JHtlbmFibGVkICE9PSB1bmRlZmluZWQgPyAnICRlbmFibGVkOiBCb29sZWFuLCcgOiAnJ30pIHtcbiAgICAgICAgdXBkYXRlX0NhbGVuZGFyX0ludGVncmF0aW9uX2J5X3BrKHBrX2NvbHVtbnM6IHtpZDogJGlkfSwgX3NldDogeyR7dG9rZW4gIT09IHVuZGVmaW5lZCA/ICd0b2tlbjogJHRva2VuLCcgOiAnJ30ke3JlZnJlc2hUb2tlbiAhPT0gdW5kZWZpbmVkID8gJyByZWZyZXNoVG9rZW46ICRyZWZyZXNoVG9rZW4sJyA6ICcnfSR7ZXhwaXJlc0luICE9PSB1bmRlZmluZWQgPyAnIGV4cGlyZXNBdDogJGV4cGlyZXNBdCwnIDogJyd9JHtlbmFibGVkICE9PSB1bmRlZmluZWQgPyAnIGVuYWJsZWQ6ICRlbmFibGVkLCcgOiAnJ319KSB7XG4gICAgICAgICAgaWRcbiAgICAgICAgICBuYW1lXG4gICAgICAgICAgcmVmcmVzaFRva2VuXG4gICAgICAgICAgdG9rZW5cbiAgICAgICAgICBjbGllbnRUeXBlXG4gICAgICAgICAgdXNlcklkXG4gICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICBgO1xuICAgIGxldCB2YXJpYWJsZXM6IGFueSA9IHtcbiAgICAgIGlkLFxuICAgICAgdG9rZW4sXG4gICAgICBleHBpcmVzQXQ6IGV4cGlyZXNJblxuICAgICAgICA/IGRheWpzKCkuYWRkKGV4cGlyZXNJbiwgJ3NlY29uZHMnKS50b0lTT1N0cmluZygpXG4gICAgICAgIDogbnVsbCxcbiAgICB9O1xuXG4gICAgaWYgKGVuYWJsZWQgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLmVuYWJsZWQgPSBlbmFibGVkO1xuICAgIH1cblxuICAgIGlmIChyZWZyZXNoVG9rZW4gIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLnJlZnJlc2hUb2tlbiA9IHJlZnJlc2hUb2tlbjtcbiAgICB9XG5cbiAgICBjb25zdCByZXM6IHtcbiAgICAgIGRhdGE6IHsgdXBkYXRlX0NhbGVuZGFyX0ludGVncmF0aW9uX2J5X3BrOiBDYWxlbmRhckludGVncmF0aW9uVHlwZSB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgLy8gY29uc29sZS5sb2cocmVzLCAnIHJlcyBpbnNpZGUgdXBkYXRlQ2FsZW5kYXJJbnRlZ3JhdGlvbicpXG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB1cGRhdGUgY2FsZW5kYXIgaW50ZWdyYXRpb24nKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGRlY3J5cHRab29tVG9rZW5zID0gKFxuICBlbmNyeXB0ZWRUb2tlbjogc3RyaW5nLFxuICBlbmNyeXB0ZWRSZWZyZXNoVG9rZW4/OiBzdHJpbmdcbikgPT4ge1xuICBjb25zdCBpdkJ1ZmZlciA9IEJ1ZmZlci5mcm9tKHpvb21JVkZvclBhc3MsICdiYXNlNjQnKTtcbiAgY29uc3Qgc2FsdEJ1ZmZlciA9IEJ1ZmZlci5mcm9tKHpvb21TYWx0Rm9yUGFzcywgJ2Jhc2U2NCcpO1xuXG4gIGNvbnN0IGtleSA9IGNyeXB0by5wYmtkZjJTeW5jKFxuICAgIHpvb21QYXNzS2V5IGFzIHN0cmluZyxcbiAgICBzYWx0QnVmZmVyLFxuICAgIDEwMDAwLFxuICAgIDMyLFxuICAgICdzaGEyNTYnXG4gICk7XG5cbiAgY29uc3QgZGVjaXBoZXJUb2tlbiA9IGNyeXB0by5jcmVhdGVEZWNpcGhlcml2KCdhZXMtMjU2LWNiYycsIGtleSwgaXZCdWZmZXIpO1xuICBsZXQgZGVjcnlwdGVkVG9rZW4gPSBkZWNpcGhlclRva2VuLnVwZGF0ZShlbmNyeXB0ZWRUb2tlbiwgJ2Jhc2U2NCcsICd1dGY4Jyk7XG4gIGRlY3J5cHRlZFRva2VuICs9IGRlY2lwaGVyVG9rZW4uZmluYWwoJ3V0ZjgnKTtcblxuICBpZiAoZW5jcnlwdGVkUmVmcmVzaFRva2VuKSB7XG4gICAgY29uc3QgZGVjaXBoZXJSZWZyZXNoVG9rZW4gPSBjcnlwdG8uY3JlYXRlRGVjaXBoZXJpdihcbiAgICAgICdhZXMtMjU2LWNiYycsXG4gICAgICBrZXksXG4gICAgICBpdkJ1ZmZlclxuICAgICk7XG4gICAgbGV0IGRlY3J5cHRlZFJlZnJlc2hUb2tlbiA9IGRlY2lwaGVyUmVmcmVzaFRva2VuLnVwZGF0ZShcbiAgICAgIGVuY3J5cHRlZFJlZnJlc2hUb2tlbixcbiAgICAgICdiYXNlNjQnLFxuICAgICAgJ3V0ZjgnXG4gICAgKTtcbiAgICBkZWNyeXB0ZWRSZWZyZXNoVG9rZW4gKz0gZGVjaXBoZXJSZWZyZXNoVG9rZW4uZmluYWwoJ3V0ZjgnKTtcblxuICAgIHJldHVybiB7XG4gICAgICB0b2tlbjogZGVjcnlwdGVkVG9rZW4sXG4gICAgICByZWZyZXNoVG9rZW46IGRlY3J5cHRlZFJlZnJlc2hUb2tlbixcbiAgICB9O1xuICB9XG5cbiAgcmV0dXJuIHtcbiAgICB0b2tlbjogZGVjcnlwdGVkVG9rZW4sXG4gIH07XG59O1xuXG5leHBvcnQgY29uc3QgZW5jcnlwdFpvb21Ub2tlbnMgPSAodG9rZW46IHN0cmluZywgcmVmcmVzaFRva2VuPzogc3RyaW5nKSA9PiB7XG4gIGNvbnN0IGl2QnVmZmVyID0gQnVmZmVyLmZyb20oem9vbUlWRm9yUGFzcywgJ2Jhc2U2NCcpO1xuICBjb25zdCBzYWx0QnVmZmVyID0gQnVmZmVyLmZyb20oem9vbVNhbHRGb3JQYXNzLCAnYmFzZTY0Jyk7XG5cbiAgY29uc3Qga2V5ID0gY3J5cHRvLnBia2RmMlN5bmMoXG4gICAgem9vbVBhc3NLZXkgYXMgc3RyaW5nLFxuICAgIHNhbHRCdWZmZXIsXG4gICAgMTAwMDAsXG4gICAgMzIsXG4gICAgJ3NoYTI1NidcbiAgKTtcbiAgY29uc3QgY2lwaGVyVG9rZW4gPSBjcnlwdG8uY3JlYXRlQ2lwaGVyaXYoJ2Flcy0yNTYtY2JjJywga2V5LCBpdkJ1ZmZlcik7XG4gIGxldCBlbmNyeXB0ZWRUb2tlbiA9IGNpcGhlclRva2VuLnVwZGF0ZSh0b2tlbiwgJ3V0ZjgnLCAnYmFzZTY0Jyk7XG4gIGVuY3J5cHRlZFRva2VuICs9IGNpcGhlclRva2VuLmZpbmFsKCdiYXNlNjQnKTtcblxuICBsZXQgZW5jcnlwdGVkUmVmcmVzaFRva2VuID0gJyc7XG5cbiAgaWYgKHJlZnJlc2hUb2tlbikge1xuICAgIGNvbnN0IGNpcGhlclJlZnJlc2hUb2tlbiA9IGNyeXB0by5jcmVhdGVDaXBoZXJpdihcbiAgICAgICdhZXMtMjU2LWNiYycsXG4gICAgICBrZXksXG4gICAgICBpdkJ1ZmZlclxuICAgICk7XG4gICAgZW5jcnlwdGVkUmVmcmVzaFRva2VuID0gY2lwaGVyUmVmcmVzaFRva2VuLnVwZGF0ZShcbiAgICAgIHJlZnJlc2hUb2tlbixcbiAgICAgICd1dGY4JyxcbiAgICAgICdiYXNlNjQnXG4gICAgKTtcbiAgICBlbmNyeXB0ZWRSZWZyZXNoVG9rZW4gKz0gY2lwaGVyUmVmcmVzaFRva2VuLmZpbmFsKCdiYXNlNjQnKTtcbiAgfVxuXG4gIGlmIChlbmNyeXB0ZWRSZWZyZXNoVG9rZW4pIHtcbiAgICByZXR1cm4ge1xuICAgICAgZW5jcnlwdGVkVG9rZW4sXG4gICAgICBlbmNyeXB0ZWRSZWZyZXNoVG9rZW4sXG4gICAgfTtcbiAgfSBlbHNlIHtcbiAgICByZXR1cm4geyBlbmNyeXB0ZWRUb2tlbiB9O1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdXBkYXRlWm9vbUludGVncmF0aW9uID0gYXN5bmMgKFxuICBpZDogc3RyaW5nLFxuICBhcHBBY2NvdW50SWQ6IHN0cmluZyxcbiAgYXBwRW1haWw6IHN0cmluZyxcbiAgYXBwSWQ6IHN0cmluZyxcbiAgdG9rZW46IHN0cmluZyB8IG51bGwsXG4gIGV4cGlyZXNJbjogbnVtYmVyIHwgbnVsbCxcbiAgcmVmcmVzaFRva2VuPzogc3RyaW5nLFxuICBjb250YWN0Rmlyc3ROYW1lPzogc3RyaW5nLFxuICBjb250YWN0TGFzdE5hbWU/OiBzdHJpbmcsXG4gIHBob25lQ291bnRyeT86IHN0cmluZywgLy8gJ1VTJ1xuICBwaG9uZU51bWJlcj86IHN0cmluZywgLy8gJysxIDEyMzQ1Njc4OTEnXG4gIGVuYWJsZWQ/OiBib29sZWFuXG4pID0+IHtcbiAgdHJ5IHtcbiAgICAvLyR7dG9rZW4gIT09IHVuZGVmaW5lZCA/ICcgJHRva2VuOiBTdHJpbmcsJyA6ICcnfVxuICAgIC8vXG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICd1cGRhdGVDYWxlbmRhckludGVncmF0aW9uQnlJZCc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBtdXRhdGlvbiB1cGRhdGVDYWxlbmRhckludGVncmF0aW9uQnlJZChcbiAgICAgICAgICAgICAgICAgICAgJGlkOiB1dWlkISxcbiAgICAgICAgICAgICAgICAgICAgJGFwcEFjY291bnRJZDogU3RyaW5nISxcbiAgICAgICAgICAgICAgICAgICAgJGFwcEVtYWlsOiBTdHJpbmchLFxuICAgICAgICAgICAgICAgICAgICAkYXBwSWQ6IFN0cmluZyEsXG4gICAgICAgICAgICAgICAgICAgICR7dG9rZW4gIT09IHVuZGVmaW5lZCA/ICcgJHRva2VuOiBTdHJpbmcsJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICAke3JlZnJlc2hUb2tlbiAhPT0gdW5kZWZpbmVkID8gJyAkcmVmcmVzaFRva2VuOiBTdHJpbmcsJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICAke2V4cGlyZXNJbiAhPT0gdW5kZWZpbmVkID8gJyAkZXhwaXJlc0F0OiB0aW1lc3RhbXB0eiwnIDogJyd9XG4gICAgICAgICAgICAgICAgICAgICR7ZW5hYmxlZCAhPT0gdW5kZWZpbmVkID8gJyAkZW5hYmxlZDogQm9vbGVhbiwnIDogJyd9XG4gICAgICAgICAgICAgICAgICAgICR7Y29udGFjdEZpcnN0TmFtZSAhPT0gdW5kZWZpbmVkID8gJyAkY29udGFjdEZpcnN0TmFtZTogU3RyaW5nLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICAgJHtjb250YWN0TGFzdE5hbWUgIT09IHVuZGVmaW5lZCA/ICcgJGNvbnRhY3RMYXN0TmFtZTogU3RyaW5nLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICAgJHtwaG9uZUNvdW50cnkgIT09IHVuZGVmaW5lZCA/ICcgJHBob25lQ291bnRyeTogU3RyaW5nLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICAgJHtwaG9uZU51bWJlciAhPT0gdW5kZWZpbmVkID8gJyAkcGhvbmVOdW1iZXI6IFN0cmluZywnIDogJyd9XG4gICAgICAgICAgICAgICAgKSB7XG4gICAgICAgICAgICAgICAgdXBkYXRlX0NhbGVuZGFyX0ludGVncmF0aW9uX2J5X3BrKHBrX2NvbHVtbnM6IHtpZDogJGlkfSwgX3NldDoge1xuICAgICAgICAgICAgICAgICAgICBhcHBBY2NvdW50SWQ6ICRhcHBBY2NvdW50SWQsXG4gICAgICAgICAgICAgICAgICAgIGFwcEVtYWlsOiAkYXBwRW1haWwsXG4gICAgICAgICAgICAgICAgICAgIGFwcElkOiAkYXBwSWQsXG4gICAgICAgICAgICAgICAgICAgICR7dG9rZW4gIT09IHVuZGVmaW5lZCA/ICd0b2tlbjogJHRva2VuLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICAgJHtleHBpcmVzSW4gIT09IHVuZGVmaW5lZCA/ICcgZXhwaXJlc0F0OiAkZXhwaXJlc0F0LCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICAgJHtyZWZyZXNoVG9rZW4gIT09IHVuZGVmaW5lZCA/ICdyZWZyZXNoVG9rZW46ICRyZWZyZXNoVG9rZW4sJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICAke2NvbnRhY3RGaXJzdE5hbWUgIT09IHVuZGVmaW5lZCA/ICdjb250YWN0Rmlyc3ROYW1lOiAkY29udGFjdEZpcnN0TmFtZSwnIDogJyd9XG4gICAgICAgICAgICAgICAgICAgICR7Y29udGFjdExhc3ROYW1lICE9PSB1bmRlZmluZWQgPyAnY29udGFjdExhc3ROYW1lOiAkY29udGFjdExhc3ROYW1lLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICAgJHtwaG9uZUNvdW50cnkgIT09IHVuZGVmaW5lZCA/ICdwaG9uZUNvdW50cnk6ICRwaG9uZUNvdW50cnksJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICAke3Bob25lTnVtYmVyICE9PSB1bmRlZmluZWQgPyAncGhvbmVOdW1iZXI6ICRwaG9uZU51bWJlciwnIDogJyd9XG4gICAgICAgICAgICAgICAgICAgICR7ZW5hYmxlZCAhPT0gdW5kZWZpbmVkID8gJyBlbmFibGVkOiAkZW5hYmxlZCwnIDogJyd9XG4gICAgICAgICAgICAgICAgfSkge1xuICAgICAgICAgICAgICAgICAgICBhcHBBY2NvdW50SWRcbiAgICAgICAgICAgICAgICAgICAgYXBwRW1haWxcbiAgICAgICAgICAgICAgICAgICAgYXBwSWRcbiAgICAgICAgICAgICAgICAgICAgY2xpZW50VHlwZVxuICAgICAgICAgICAgICAgICAgICBjb2xvcnNcbiAgICAgICAgICAgICAgICAgICAgY29udGFjdEVtYWlsXG4gICAgICAgICAgICAgICAgICAgIGNvbnRhY3RGaXJzdE5hbWVcbiAgICAgICAgICAgICAgICAgICAgY29udGFjdExhc3ROYW1lXG4gICAgICAgICAgICAgICAgICAgIGNvbnRhY3ROYW1lXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICAgICAgICAgICAgZW5hYmxlZFxuICAgICAgICAgICAgICAgICAgICBleHBpcmVzQXRcbiAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgbmFtZVxuICAgICAgICAgICAgICAgICAgICBwYWdlVG9rZW5cbiAgICAgICAgICAgICAgICAgICAgcGFzc3dvcmRcbiAgICAgICAgICAgICAgICAgICAgcGhvbmVDb3VudHJ5XG4gICAgICAgICAgICAgICAgICAgIHBob25lTnVtYmVyXG4gICAgICAgICAgICAgICAgICAgIHJlZnJlc2hUb2tlblxuICAgICAgICAgICAgICAgICAgICByZXNvdXJjZVxuICAgICAgICAgICAgICAgICAgICBzeW5jRW5hYmxlZFxuICAgICAgICAgICAgICAgICAgICBzeW5jVG9rZW5cbiAgICAgICAgICAgICAgICAgICAgdG9rZW5cbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgICAgICAgICB1c2VybmFtZVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGxldCBlbmNyeXB0ZWRWYWx1ZXMgPSBudWxsO1xuXG4gICAgaWYgKHRva2VuKSB7XG4gICAgICBlbmNyeXB0ZWRWYWx1ZXMgPSBlbmNyeXB0Wm9vbVRva2Vucyh0b2tlbiwgcmVmcmVzaFRva2VuKTtcbiAgICB9XG5cbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBpZCxcbiAgICAgIGFwcEFjY291bnRJZCxcbiAgICAgIGFwcEVtYWlsLFxuICAgICAgYXBwSWQsXG4gICAgICB0b2tlbjogZW5jcnlwdGVkVmFsdWVzPy5lbmNyeXB0ZWRUb2tlbixcbiAgICAgIGV4cGlyZXNBdDogZXhwaXJlc0luXG4gICAgICAgID8gZGF5anMoKS5hZGQoZXhwaXJlc0luLCAnc2Vjb25kcycpLnRvSVNPU3RyaW5nKClcbiAgICAgICAgOiBudWxsLFxuICAgICAgcmVmcmVzaFRva2VuOlxuICAgICAgICByZWZyZXNoVG9rZW4gPT09IHVuZGVmaW5lZFxuICAgICAgICAgID8gdW5kZWZpbmVkXG4gICAgICAgICAgOiBlbmNyeXB0ZWRWYWx1ZXM/LmVuY3J5cHRlZFJlZnJlc2hUb2tlbixcbiAgICAgIGNvbnRhY3RGaXJzdE5hbWUsXG4gICAgICBjb250YWN0TGFzdE5hbWUsXG4gICAgICBwaG9uZUNvdW50cnksXG4gICAgICBwaG9uZU51bWJlcixcbiAgICAgIGVuYWJsZWQsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICAvLyBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGluc2lkZSB1cGRhdGVDYWxlbmRhckludGVncmF0aW9uJylcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHVwZGF0ZSB6b29tIGludGVncmF0aW9uJyk7XG4gIH1cbn07XG4iXX0=