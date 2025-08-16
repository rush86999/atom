import got from 'got';
import dayjs from 'dayjs';
import isoWeek from 'dayjs/plugin/isoWeek';
import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import _ from 'lodash';
import {
  googleClientIdWeb,
  googleClientSecretWeb,
  googleRedirectUrl,
  hasuraAdminSecret,
  hasuraGraphUrl,
  zoomIVForPass,
  zoomPassKey,
  zoomSaltForPass,
  githubClientId,
  githubClientSecret,
  githubRedirectUrl,
  discordClientId,
  discordClientSecret,
  discordRedirectUrl,
  paypalClientId,
  paypalClientSecret,
  jiraClientId,
  jiraClientSecret,
  jiraRedirectUrl,
} from '@lib/constants';
import {
  CalendarIntegrationType,
  ZoomWebhookRequestType,
  ZoomWebhookValidationRequestType,
} from '@lib/types';
import { google } from 'googleapis';
import type { NextApiResponse } from 'next';
import crypto, { BinaryLike } from 'crypto';
import { executeGraphQLMutation } from './graphqlClient';
import { Credentials as OAuth2Token } from 'google-auth-library';
import { AuthorizationCode } from 'simple-oauth2';

const GOOGLE_CALENDAR_SERVICE_NAME = 'google_calendar';
const GITHUB_SERVICE_NAME = 'github';
const DISCORD_SERVICE_NAME = 'discord';
const PAYPAL_SERVICE_NAME = 'paypal';
const JIRA_SERVICE_NAME = 'jira';

dayjs.extend(isoWeek);
dayjs.extend(duration);
dayjs.extend(isBetween);
dayjs.extend(timezone);
dayjs.extend(utc);

const oauth2Client = new google.auth.OAuth2(
  googleClientIdWeb,
  googleClientSecretWeb,
  googleRedirectUrl
);

const githubOAuth2 = new AuthorizationCode({
    client: {
        id: githubClientId,
        secret: githubClientSecret,
    },
    auth: {
        tokenHost: 'https://github.com',
        tokenPath: '/login/oauth/access_token',
        authorizePath: '/login/oauth/authorize',
    },
});

const discordOAuth2 = new AuthorizationCode({
    client: {
        id: discordClientId,
        secret: discordClientSecret,
    },
    auth: {
        tokenHost: 'https://discord.com',
        tokenPath: '/api/oauth2/token',
        authorizePath: '/api/oauth2/authorize',
    },
});

const jiraOAuth2 = new AuthorizationCode({
    client: {
        id: jiraClientId,
        secret: jiraClientSecret,
    },
    auth: {
        tokenHost: 'https://auth.atlassian.com',
        tokenPath: '/oauth/token',
        authorizePath: '/authorize',
    },
});

async function saveUserTokens(
  userId: string,
  serviceName: string,
  tokens: any
): Promise<{ ok: boolean; error?: any }> {
  console.log(
    `Saving tokens for userId: ${userId}, service: ${serviceName}`
  );

  const mutation = `
    mutation UpsertUserToken($objects: [user_tokens_insert_input!]!) {
      insert_user_tokens(
        objects: $objects,
        on_conflict: {
          constraint: user_tokens_user_id_service_key,
          update_columns: [encrypted_access_token, encrypted_refresh_token, token_expiry_timestamp, metadata, updated_at]
        }
      ) {
        affected_rows
      }
    }
  `;

  const tokenDataForDb = {
    user_id: userId,
    service: serviceName,
    encrypted_access_token: tokens.access_token, // Assuming encryption happens elsewhere
    encrypted_refresh_token: tokens.refresh_token,
    token_expiry_timestamp: tokens.expires_at
      ? new Date(tokens.expires_at).toISOString()
      : null,
    metadata: tokens.metadata || {},
    updated_at: new Date().toISOString(),
  };

  const variables = { objects: [tokenDataForDb] };
  const operationName = 'UpsertUserToken';

  try {
    const response = await executeGraphQLMutation<{
      insert_user_tokens: { affected_rows: number };
    }>(mutation, variables, operationName, userId);

    if (
      !response ||
      !response.insert_user_tokens ||
      response.insert_user_tokens.affected_rows === 0
    ) {
      console.warn(
        `Token save operation for user ${userId} reported 0 affected_rows.`,
        response
      );
    } else {
      console.log(
        `Tokens saved successfully to database for user ${userId}. Affected rows: ${response.insert_user_tokens.affected_rows}`
      );
    }
    return { ok: true };
  } catch (error: any) {
    console.error(
      `Exception during saveUserTokens for userId ${userId}:`,
      error
    );
    return {
      ok: false,
      error: {
        message: `Failed to save ${serviceName} tokens.`,
        details: error.message,
      },
    };
  }
}

export const validateZoomWebook = (
  request: ZoomWebhookValidationRequestType,
  response: NextApiResponse
) => {
  const hashForValidate = crypto
    .createHmac('sha256', process.env.ZOOM_WEBHOOK_SECRET_TOKEN as BinaryLike)
    .update(request.body.payload.plainToken)
    .digest('hex');
  return response.status(200).json({
    plainToken: request.body.payload.plainToken,
    encryptedToken: hashForValidate,
  });
};

export const verifyZoomWebhook = (request: ZoomWebhookRequestType) => {
  const message = `v0:${request.headers['x-zm-request-timestamp']}:${JSON.stringify(request.body)}`;

  const hashForVerify = crypto
    .createHmac('sha256', process.env.ZOOM_WEBHOOK_SECRET_TOKEN as BinaryLike)
    .update(message)
    .digest('hex');

  const signature = `v0=${hashForVerify}`;

  if (request.headers['x-zm-signature'] === signature) {
    return true;
  }

  throw new Error(
    'Failed zoom webhook verification using secret token & sha256'
  );
};

export const exchangeCodeForTokens = async (code: string, userId: string) => {
  try {
    let { tokens } = await oauth2Client.getToken(code);
    oauth2Client.setCredentials(tokens);
    if (tokens) {
      await saveUserTokens(userId, GOOGLE_CALENDAR_SERVICE_NAME, tokens);
    }
    return tokens;
  } catch (e) {
    console.log(e, ' unable to exchange code for tokens');
  }
};

export const exchangeCodeForGithubTokens = async (code: string, userId: string) => {
    try {
        const result = await githubOAuth2.getToken({
            code,
            redirect_uri: githubRedirectUrl,
            scope: 'repo,user',
        });
        const { token } = result;
        await saveUserTokens(userId, GITHUB_SERVICE_NAME, token);
        return token;
    } catch (error) {
        console.error('Access Token Error', error.message);
        throw error;
    }
};

export const exchangeCodeForDiscordTokens = async (code: string, userId: string) => {
    try {
        const result = await discordOAuth2.getToken({
            code,
            redirect_uri: discordRedirectUrl,
            scope: 'identify guilds messages.read',
        });
        const { token } = result;
        await saveUserTokens(userId, DISCORD_SERVICE_NAME, token);
        return token;
    } catch (error) {
        console.error('Access Token Error', error.message);
        throw error;
    }
};

export const exchangeCodeForJiraTokens = async (code: string, userId: string) => {
    try {
        const result = await jiraOAuth2.getToken({
            code,
            redirect_uri: jiraRedirectUrl,
            scope: 'read:jira-work manage:jira-project',
        });
        const { token } = result;
        await saveUserTokens(userId, JIRA_SERVICE_NAME, token);
        return token;
    } catch (error) {
        console.error('Access Token Error', error.message);
        throw error;
    }
};

export const getPaypalAccessToken = async (userId: string) => {
    try {
        const response = await got.post('https://api-m.sandbox.paypal.com/v1/oauth2/token', {
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': 'Basic ' + Buffer.from(paypalClientId + ':' + paypalClientSecret).toString('base64'),
            },
            form: {
                grant_type: 'client_credentials',
            },
        }).json();
        const token = response.access_token;
        await saveUserTokens(userId, PAYPAL_SERVICE_NAME, { access_token: token, expires_in: response.expires_in });
        return token;
    } catch (error) {
        console.error('Access Token Error', error.message);
        throw error;
    }
};

export const generateGoogleAuthUrl = (state: string) => {
  const scopes = [
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/contacts.readonly',
  ];

  const authorizationUrl = oauth2Client.generateAuthUrl({
    access_type: 'online',
    scope: scopes,
    include_granted_scopes: true,
    state,
  });

  return authorizationUrl;
};

export const generateGithubAuthUrl = (state: string) => {
    const authorizationUri = githubOAuth2.authorizeURL({
        redirect_uri: githubRedirectUrl,
        scope: 'repo,user',
        state,
    });
    return authorizationUri;
};

export const generateDiscordAuthUrl = (state: string) => {
    const authorizationUri = discordOAuth2.authorizeURL({
        redirect_uri: discordRedirectUrl,
        scope: 'identify guilds messages.read',
        state,
    });
    return authorizationUri;
};

export const generateJiraAuthUrl = (state: string) => {
    const authorizationUri = jiraOAuth2.authorizeURL({
        redirect_uri: jiraRedirectUrl,
        scope: 'read:jira-work manage:jira-project',
        state,
        audience: 'api.atlassian.com',
        prompt: 'consent',
    });
    return authorizationUri;
};

export const getMinimalCalendarIntegration = async (
  userId: string,
  resource: string
) => {
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

    const res: { data: { Calendar_Integration: CalendarIntegrationType[] } } =
      await got
        .post(hasuraGraphUrl, {
          json: {
            operationName,
            query,
            variables,
          },
          headers: {
            'X-Hasura-Admin-Secret': hasuraAdminSecret,
            'Content-Type': 'application/json',
            'X-Hasura-Role': 'admin',
          },
        })
        .json();

    if (res?.data?.Calendar_Integration?.length > 0) {
      return res?.data?.Calendar_Integration?.[0];
    }
  } catch (e) {
    console.log(e, ' unable to get calendar integration');
  }
};

export const deAuthZoomGivenUserId = async (appId: string) => {
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

    const res: {
      data: {
        update_Calendar_Integration: {
          affected_rows: number;
          returning: CalendarIntegrationType[];
        };
      };
    } = await got
      .post(hasuraGraphUrl, {
        json: {
          operationName,
          query,
          variables,
        },
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
      })
      .json();

    console.log(
      res?.data?.update_Calendar_Integration?.affected_rows,
      ' successfully deAuth zoom'
    );
  } catch (e) {
    console.log(e, ' unable to deAuth Zoom');
  }
};

export const updateAccessTokenCalendarIntegration = async (
  id: string,
  token: string | null,
  expiresIn: number | null,
  enabled?: boolean,
  refreshToken?: string | null
) => {
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
    let variables: any = {
      id,
      token,
      expiresAt: expiresIn
        ? dayjs().add(expiresIn, 'seconds').toISOString()
        : null,
    };

    if (enabled !== undefined) {
      variables.enabled = enabled;
    }

    if (refreshToken !== undefined) {
      variables.refreshToken = refreshToken;
    }

    const res: {
      data: { update_Calendar_Integration_by_pk: CalendarIntegrationType };
    } = await got
      .post(hasuraGraphUrl, {
        json: {
          operationName,
          query,
          variables,
        },
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
      })
      .json();

  } catch (e) {
    console.log(e, ' unable to update calendar integration');
  }
};

export const decryptZoomTokens = (
  encryptedToken: string,
  encryptedRefreshToken?: string
) => {
  const ivBuffer = Buffer.from(zoomIVForPass, 'base64');
  const saltBuffer = Buffer.from(zoomSaltForPass, 'base64');

  const key = crypto.pbkdf2Sync(
    zoomPassKey as string,
    saltBuffer,
    10000,
    32,
    'sha256'
  );

  const decipherToken = crypto.createDecipheriv('aes-256-cbc', key, ivBuffer);
  let decryptedToken = decipherToken.update(encryptedToken, 'base64', 'utf8');
  decryptedToken += decipherToken.final('utf8');

  if (encryptedRefreshToken) {
    const decipherRefreshToken = crypto.createDecipheriv(
      'aes-256-cbc',
      key,
      ivBuffer
    );
    let decryptedRefreshToken = decipherRefreshToken.update(
      encryptedRefreshToken,
      'base64',
      'utf8'
    );
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

export const encryptZoomTokens = (token: string, refreshToken?: string) => {
  const ivBuffer = Buffer.from(zoomIVForPass, 'base64');
  const saltBuffer = Buffer.from(zoomSaltForPass, 'base64');

  const key = crypto.pbkdf2Sync(
    zoomPassKey as string,
    saltBuffer,
    10000,
    32,
    'sha256'
  );
  const cipherToken = crypto.createCipheriv('aes-256-cbc', key, ivBuffer);
  let encryptedToken = cipherToken.update(token, 'utf8', 'base64');
  encryptedToken += cipherToken.final('base64');

  let encryptedRefreshToken = '';

  if (refreshToken) {
    const cipherRefreshToken = crypto.createCipheriv(
      'aes-256-cbc',
      key,
      ivBuffer
    );
    encryptedRefreshToken = cipherRefreshToken.update(
      refreshToken,
      'utf8',
      'base64'
    );
    encryptedRefreshToken += cipherRefreshToken.final('base64');
  }

  if (encryptedRefreshToken) {
    return {
      encryptedToken,
      encryptedRefreshToken,
    };
  } else {
    return { encryptedToken };
  }
};

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
  phoneCountry?: string,
  phoneNumber?: string,
  enabled?: boolean
) => {
  try {
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
      encryptedValues = encryptZoomTokens(token, refreshToken);
    }

    const variables = {
      id,
      appAccountId,
      appEmail,
      appId,
      token: encryptedValues?.encryptedToken,
      expiresAt: expiresIn
        ? dayjs().add(expiresIn, 'seconds').toISOString()
        : null,
      refreshToken:
        refreshToken === undefined
          ? undefined
          : encryptedValues?.encryptedRefreshToken,
      contactFirstName,
      contactLastName,
      phoneCountry,
      phoneNumber,
      enabled,
    };

    const res = await got
      .post(hasuraGraphUrl, {
        json: {
          operationName,
          query,
          variables,
        },
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
      })
      .json();

  } catch (e) {
    console.log(e, ' unable to update zoom integration');
  }
};
