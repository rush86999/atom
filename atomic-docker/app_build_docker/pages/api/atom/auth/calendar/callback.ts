import type { NextApiRequest, NextApiResponse } from 'next';
import qs from 'qs';
import Cors from 'cors';
import { exchangeCodeForTokens } from '@lib/api-backend-helper'; // Removed unused Google-specific helpers for now
import { dayjs } from '@lib/date-utils';

import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from 'supertokens-node/recipe/session/framework/express';
import supertokens from 'supertokens-node';
import { backendConfig } from '../../../../../config/backendConfig'; // Adjusted path
import { Credentials as OAuth2Token } from 'google-auth-library';

// Assuming these are needed for GraphQL client used by saveUserTokensInternal
// These constants might be better sourced from a shared constants file within app-service if possible,
// or ensure the path is robust.
import {
  HASURA_GRAPHQL_URL,
  HASURA_ADMIN_SECRET,
} from '../../../../../../project/functions/atom-agent/_libs/constants';
import { executeGraphQLMutation } from '../../../../../../project/functions/atom-agent/_libs/graphqlClient';
import appServiceLogger from '../../../../../lib/logger'; // Import the shared app-service logger

const GOOGLE_CALENDAR_SERVICE_NAME = 'google_calendar';

const cors = Cors({
  methods: ['POST', 'GET', 'HEAD'],
  // Allow all origins for simplicity in dev, or specify your frontend URL
  // origin: process.env.NODE_ENV === 'production' ? ["https://atomiclife.app", /\.atomiclife\.app$/] : "*",
});

supertokens.init(backendConfig());

function runMiddleware(
  req: NextApiRequest,
  res: NextApiResponse,
  fn: Function
) {
  return new Promise((resolve, reject) => {
    fn(req, res, (result: any) => {
      if (result instanceof Error) {
        return reject(result);
      }
      return resolve(result);
    });
  });
}

// This function is an adaptation of saveUserTokens from calendarSkills.ts
// to be used directly within this API route.
async function saveUserTokensInternal(
  userId: string,
  tokens: OAuth2Token
): Promise<{ ok: boolean; error?: any }> {
  const operationName = 'saveUserTokensInternal_GoogleCalendarAuthCallback';
  appServiceLogger.info(`[${operationName}] Attempting to save tokens.`, {
    userId,
    service: GOOGLE_CALENDAR_SERVICE_NAME,
  });

  if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
    appServiceLogger.error(
      `[${operationName}] GraphQL client configuration missing (Hasura URL/Secret).`,
      { userId }
    );
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'GraphQL client is not configured.',
      },
    };
  }

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
    const response = await executeGraphQLMutation<{
      insert_user_tokens: { affected_rows: number };
    }>(
      mutation,
      variables,
      operationName, // This is 'UpsertUserToken' from the GQL mutation name
      userId
    );

    if (
      response &&
      response.insert_user_tokens &&
      response.insert_user_tokens.affected_rows > 0
    ) {
      appServiceLogger.info(
        `[${operationName}] Tokens saved successfully to user_tokens table.`,
        { userId }
      );
      return { ok: true };
    } else {
      appServiceLogger.warn(
        `[${operationName}] Token save operation (user_tokens table) reported 0 affected_rows or no/unexpected response.`,
        { userId, response }
      );
      return {
        ok: false,
        error: {
          code: 'DB_NO_ROWS_AFFECTED',
          message: 'Token save did not affect any rows.',
        },
      };
    }
  } catch (error: any) {
    appServiceLogger.error(`[${operationName}] Exception during token save.`, {
      userId,
      error: error.message,
      stack: error.stack,
      details: error,
    });
    return {
      ok: false,
      error: {
        code: 'TOKEN_SAVE_FAILED_INTERNAL',
        message: `Failed to save Google Calendar tokens to user_tokens for user ${userId}.`,
        details: error.message,
      },
    };
  }
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  try {
    await runMiddleware(req, res, cors);

    await superTokensNextWrapper(
      async (next) => {
        return await verifySession()(req as any, res as any, next);
      },
      req,
      res
    );

    const session = req.session;
    const userId = session?.getUserId();
    const operationName = 'GoogleCalendarAuthCallback'; // For logging context

    if (!userId) {
      appServiceLogger.error(
        `[${operationName}] User not authenticated in callback. Session may be missing or invalid.`,
        { headers: req.headers }
      );
      return res.redirect(
        '/User/Login/UserLogin?error=session_expired_oauth_callback'
      );
    }
    appServiceLogger.info(`[${operationName}] Processing callback for user.`, {
      userId,
    });

    const thisUrl = new URL(req.url as string, `https://${req.headers.host}`);
    const queryParams = qs.parse(thisUrl.search.substring(1));

    if (queryParams.error) {
      const error = queryParams.error as string;
      appServiceLogger.warn(
        `[${operationName}] Error from Google OAuth provider.`,
        { userId, error, queryParams }
      );
      return res.redirect(
        `/Settings/UserViewSettings?calendar_auth_error=${encodeURIComponent(error)}&atom_agent=true`
      );
    }

    const code = queryParams.code as string;
    const state = queryParams.state as string;

    if (state !== userId) {
      appServiceLogger.error(
        `[${operationName}] Invalid OAuth state. CSRF attempt?`,
        { expectedState: userId, receivedState: state }
      );
      return res.redirect(
        `/Settings/UserViewSettings?calendar_auth_error=invalid_state&atom_agent=true`
      );
    }

    if (!code) {
      appServiceLogger.error(
        `[${operationName}] No authorization code received from Google.`,
        { userId }
      );
      return res.redirect(
        `/Settings/UserViewSettings?calendar_auth_error=no_code_received&atom_agent=true`
      );
    }
    appServiceLogger.debug(`[${operationName}] Authorization code received.`, {
      userId,
      codePrefix: code?.substring(0, 10),
    });

    const tokens = await exchangeCodeForTokens(code);

    if (!tokens || !tokens.access_token) {
      appServiceLogger.error(
        `[${operationName}] Failed to exchange code for tokens or access_token missing.`,
        {
          userId,
          tokensReceived: !!tokens,
          accessTokenPresent: !!tokens?.access_token,
        }
      );
      return res.redirect(
        `/Settings/UserViewSettings?calendar_auth_error=token_exchange_failed&atom_agent=true`
      );
    }

    appServiceLogger.info(
      `[${operationName}] Tokens received from Google successfully.`,
      {
        userId,
        accessTokenPresent: !!tokens.access_token,
        refreshTokenPresent: !!tokens.refresh_token,
        expiresAt: tokens.expiry_date,
        scope: tokens.scope,
      }
    );

    const saveResult = await saveUserTokensInternal(userId, tokens);

    if (!saveResult.ok) {
      appServiceLogger.error(
        `[${operationName}] Failed to save tokens to user_tokens table.`,
        { userId, errorDetails: saveResult.error }
      );
      const errorMessage = saveResult.error?.message || 'failed_to_save_tokens';
      return res.redirect(
        `/Settings/UserViewSettings?calendar_auth_error=${encodeURIComponent(errorMessage)}&atom_agent=true`
      );
    }

    appServiceLogger.info(
      `[${operationName}] Google Calendar connected and tokens saved successfully.`,
      { userId }
    );
    return res.redirect(
      '/Settings/UserViewSettings?calendar_auth_success=true&atom_agent=true'
    );
  } catch (e: any) {
    // Catching 'any' to access potential properties like 'message'
    const operationName = 'GoogleCalendarAuthCallback_OuterCatch'; // Specific for this catch
    appServiceLogger.error(
      `[${operationName}] General error in Google OAuth callback handler.`,
      { error: e.message, stack: e.stack, details: e }
    );
    // Avoid exposing sensitive error details in redirect.
    return res.redirect(
      `/Settings/UserViewSettings?calendar_auth_error=${encodeURIComponent('callback_processing_failed')}&atom_agent=true`
    );
  }
}
