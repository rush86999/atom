import type { NextApiRequest, NextApiResponse } from 'next'
import qs from 'qs'
import Cors from 'cors'
import { exchangeCodeForTokens } from '@lib/api-backend-helper' // Removed unused Google-specific helpers for now
import { dayjs } from '@lib/date-utils'

import { superTokensNextWrapper } from 'supertokens-node/nextjs'
import { verifySession } from 'supertokens-node/recipe/session/framework/express'
import supertokens from 'supertokens-node'
import { backendConfig } from '../../../../../config/backendConfig' // Adjusted path
import { Credentials as OAuth2Token } from 'google-auth-library';

// Assuming these are needed for GraphQL client used by saveUserTokensInternal
import { HASURA_GRAPHQL_URL, HASURA_ADMIN_SECRET } from '../../../../../../project/functions/atom-agent/_libs/constants';
import { executeGraphQLMutation } from '../../../../../../project/functions/atom-agent/_libs/graphqlClient';

const GOOGLE_CALENDAR_SERVICE_NAME = 'google_calendar';


const cors = Cors({
    methods: ['POST', 'GET', 'HEAD'],
    // Allow all origins for simplicity in dev, or specify your frontend URL
    // origin: process.env.NODE_ENV === 'production' ? ["https://atomiclife.app", /\.atomiclife\.app$/] : "*",
})

supertokens.init(backendConfig())

function runMiddleware(
    req: NextApiRequest,
    res: NextApiResponse,
    fn: Function
) {
    return new Promise((resolve, reject) => {
        fn(req, res, (result: any) => {
            if (result instanceof Error) {
                return reject(result)
            }
            return resolve(result)
        })
    })
}

// This function is an adaptation of saveUserTokens from calendarSkills.ts
// to be used directly within this API route.
async function saveUserTokensInternal(userId: string, tokens: OAuth2Token): Promise<{ ok: boolean; error?: any }> {
  console.log(`AUTH_CALLBACK: Saving tokens for userId: ${userId}, service: ${GOOGLE_CALENDAR_SERVICE_NAME}`);

  if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
    console.error("AUTH_CALLBACK: GraphQL client is not configured for saveUserTokensInternal.");
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'GraphQL client is not configured.' } };
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
    expiry_date: tokens.expiry_date ? new Date(tokens.expiry_date).toISOString() : null,
    scope: tokens.scope,
    token_type: tokens.token_type,
    updated_at: new Date().toISOString(),
  };

  const variables = { objects: [tokenDataForDb] };
  const operationName = 'UpsertUserToken';

  try {
    const response = await executeGraphQLMutation<{ insert_user_tokens: { affected_rows: number } }>(
        mutation,
        variables,
        operationName,
        userId // Assuming executeGraphQLMutation can take userId for context/logging
    );

    if (response && response.insert_user_tokens && response.insert_user_tokens.affected_rows > 0) {
      console.log(`AUTH_CALLBACK: Tokens saved successfully to user_tokens table for user ${userId}.`);
      return { ok: true };
    } else {
      console.warn(`AUTH_CALLBACK: Token save operation for user ${userId} (user_tokens table) reported 0 affected_rows or no response.`, response);
      // Potentially an issue if tokens were expected to be new or different
      return { ok: false, error: {code: 'DB_NO_ROWS_AFFECTED', message: 'Token save did not affect any rows.'}};
    }
  } catch (error: any) {
    console.error(`AUTH_CALLBACK: Exception during saveUserTokensInternal for userId ${userId}:`, error);
    return {
        ok: false,
        error: {
            code: 'TOKEN_SAVE_FAILED_INTERNAL',
            message: `Failed to save Google Calendar tokens to user_tokens for user ${userId}.`,
            details: error.message
        }
    };
  }
}


export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    try {
        await runMiddleware(req, res, cors)

        await superTokensNextWrapper(
            async (next) => {
              return await verifySession()(req as any, res as any, next)
            },
            req,
            res
        )

        const session = req.session;
        const userId = session?.getUserId();

        if (!userId) {
            console.error("AUTH_CALLBACK: User not authenticated in callback.");
            // Redirect to login or an error page if not authenticated
            return res.redirect('/User/Login/UserLogin?error=session_expired_oauth_callback');
        }

        const thisUrl = new URL(req.url as string, `https://${req.headers.host}`)
        const queryParams = qs.parse(thisUrl.search.substring(1)); // Use qs to parse query

        if (queryParams.error) {
            const error = queryParams.error as string;
            console.warn(`AUTH_CALLBACK: Error from Google OAuth provider: ${error}`);
            // Redirect to settings page with an error message
            // The settings page should be prepared to display this error to the user.
            return res.redirect(`/Settings/UserViewSettings?calendar_auth_error=${encodeURIComponent(error)}&atom_agent=true`);
        }

        const code = queryParams.code as string;
        const state = queryParams.state as string; // This should be the userId

        if (state !== userId) {
            console.error(`AUTH_CALLBACK: Invalid OAuth state. Expected: ${userId}, Received: ${state}`);
            return res.redirect(`/Settings/UserViewSettings?calendar_auth_error=invalid_state&atom_agent=true`);
        }

        if (!code) {
            console.error("AUTH_CALLBACK: No authorization code received from Google.");
            return res.redirect(`/Settings/UserViewSettings?calendar_auth_error=no_code_received&atom_agent=true`);
        }

        const tokens = await exchangeCodeForTokens(code);

        if (!tokens || !tokens.access_token) {
            console.error("AUTH_CALLBACK: Failed to exchange code for tokens or access_token missing.", tokens);
            return res.redirect(`/Settings/UserViewSettings?calendar_auth_error=token_exchange_failed&atom_agent=true`);
        }

        console.log('AUTH_CALLBACK: Tokens received from Google:', {
            accessToken: tokens.access_token ? 'PRESENT' : 'MISSING',
            refreshToken: tokens.refresh_token ? 'PRESENT' : 'MISSING',
            expiresIn: tokens.expiry_date, // This is actually expiry_date (timestamp) from googleapis
            scope: tokens.scope,
        });

        // Save tokens to the user_tokens table using the internal helper
        const saveResult = await saveUserTokensInternal(userId, tokens);

        if (!saveResult.ok) {
            console.error("AUTH_CALLBACK: Failed to save tokens to user_tokens table.", saveResult.error);
            const errorMessage = saveResult.error?.message || 'failed_to_save_tokens';
            return res.redirect(`/Settings/UserViewSettings?calendar_auth_error=${encodeURIComponent(errorMessage)}&atom_agent=true`);
        }

        console.log(`AUTH_CALLBACK: Google Calendar connected successfully for user ${userId}.`);
        // Redirect to settings page with success message
        return res.redirect('/Settings/UserViewSettings?calendar_auth_success=true&atom_agent=true');

    } catch (e: unknown) {
        console.error('AUTH_CALLBACK: General error in Google OAuth callback handler:', e);
        const errorMessage = e instanceof Error ? e.message : 'Internal server error in OAuth callback.';
        // It's crucial to avoid exposing sensitive error details.
        // Log the detailed error server-side and redirect with a generic error message.
        return res.redirect(`/Settings/UserViewSettings?calendar_auth_error=${encodeURIComponent('callback_processing_failed')}&atom_agent=true`);
    }
}
