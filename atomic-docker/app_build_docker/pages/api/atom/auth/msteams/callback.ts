import type { NextApiRequest, NextApiResponse } from 'next';
import { ConfidentialClientApplication, Configuration, LogLevel, AuthenticationResult, AuthorizationCodeRequest } from '@azure/msal-node';
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from 'supertokens-node/recipe/session/framework/express'; // For state validation if needed, though state contains userId
import supertokens from 'supertokens-node';
import { backendConfig } from '../../../../../config/backendConfig'; // Adjusted path
import { logger } from '../../../../../../project/functions/_utils/logger';
import { Credentials as OAuth2Token } from 'google-auth-library'; // Re-using this type for structure, though not strictly Google
import { HASURA_GRAPHQL_URL, HASURA_ADMIN_SECRET } from '../../../../../../project/functions/atom-agent/_libs/constants';
import { executeGraphQLMutation } from '../../../../../../project/functions/atom-agent/_libs/graphqlClient';

// TODO: Move these to a central constants file and manage via environment variables
const MSTEAMS_CLIENT_ID = process.env.MSTEAMS_CLIENT_ID || "YOUR_MSTEAMS_APP_CLIENT_ID";
const MSTEAMS_CLIENT_SECRET = process.env.MSTEAMS_CLIENT_SECRET || "YOUR_MSTEAMS_APP_CLIENT_SECRET";
const MSTEAMS_REDIRECT_URI = process.env.MSTEAMS_REDIRECT_URI || "http://localhost:3000/api/atom/auth/msteams/callback";
const MSTEAMS_AUTHORITY = process.env.MSTEAMS_AUTHORITY || "https://login.microsoftonline.com/common";
const MSTEAMS_SCOPES = ["Chat.Read", "ChannelMessage.Read.All", "User.Read", "offline_access"]; // Ensure offline_access for refresh token

const MSTEAMS_TOKEN_SERVICE_NAME = 'msteams_graph'; // Or 'microsoft_graph'

supertokens.init(backendConfig());

const msalConfig: Configuration = {
    auth: {
        clientId: MSTEAMS_CLIENT_ID,
        authority: MSTEAMS_AUTHORITY,
        clientSecret: MSTEAMS_CLIENT_SECRET,
    },
    system: { /* ... logger config ... */ }
};

// Adapted from Google OAuth callback
async function saveMSTeamsUserTokens(userId: string, tokens: AuthenticationResult): Promise<{ ok: boolean; error?: any }> {
  logger.info(`[MSTeamsAuthCallback] Saving MS Teams tokens for userId: ${userId}`);

  if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
    logger.error("[MSTeamsAuthCallback] GraphQL client not configured for saveMSTeamsUserTokens.");
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'GraphQL client is not configured.' } };
  }
  if (!tokens.accessToken || !tokens.account) {
    logger.error("[MSTeamsAuthCallback] Critical token information missing from MSAL response.");
    return { ok: false, error: { code: 'TOKEN_ERROR', message: 'Essential token information missing from MSAL response.'}};
  }

  const mutation = `
    mutation UpsertUserToken($objects: [user_tokens_insert_input!]!) {
      insert_user_tokens(
        objects: $objects,
        on_conflict: {
          constraint: user_tokens_user_id_service_name_key,
          update_columns: [access_token, refresh_token, expiry_date, scope, token_type, id_token, other_data, updated_at]
        }
      ) {
        affected_rows
      }
    }
  `;

  // MSAL's AuthenticationResult has account.idTokenClaims.exp (seconds since epoch) for id_token expiry
  // tokens.expiresOn is a Date object for access_token expiry
  const tokenDataForDb = {
    user_id: userId,
    service_name: MSTEAMS_TOKEN_SERVICE_NAME,
    access_token: tokens.accessToken,
    refresh_token: tokens.refreshToken, // This should be present if offline_access scope was granted
    expiry_date: tokens.expiresOn ? tokens.expiresOn.toISOString() : null,
    scope: tokens.scopes.join(' '),
    token_type: "Bearer", // Typically Bearer for MS Graph
    id_token: tokens.idToken, // Store ID token if needed
    other_data: {
        accountHomeAccountId: tokens.account.homeAccountId, // Useful for MSAL cache lookups later if needed
        accountEnvironment: tokens.account.environment,
        accountTenantId: tokens.account.tenantId,
    },
    updated_at: new Date().toISOString(),
  };

  const variables = { objects: [tokenDataForDb] };
  try {
    const response = await executeGraphQLMutation<{ insert_user_tokens: { affected_rows: number } }>(
        mutation, variables, "UpsertMSTeamsUserToken", userId
    );
    if (response && response.insert_user_tokens && response.insert_user_tokens.affected_rows > 0) {
      logger.info(`[MSTeamsAuthCallback] MS Teams tokens saved successfully for user ${userId}.`);
      return { ok: true };
    } else {
      logger.warn(`[MSTeamsAuthCallback] MS Teams token save reported 0 affected_rows for user ${userId}.`, response);
      return { ok: false, error: {code: 'DB_NO_ROWS_AFFECTED', message: 'Token save did not affect any rows.'}};
    }
  } catch (error: any) {
    logger.error(`[MSTeamsAuthCallback] Exception saving MS Teams tokens for user ${userId}:`, error);
    return { ok: false, error: { code: 'TOKEN_SAVE_FAILED', message: error.message } };
  }
}


export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    // It's important to verify the session of the user who initiated the flow,
    // usually by checking the 'state' parameter returned by Microsoft.
    // The 'state' should match what was sent in the initiate step (e.g., SuperTokens userId).
    const receivedState = req.query.state as string;
    // TODO: Securely validate the state parameter against a stored value from the initiate step if not using userId directly.
    // For now, we assume state IS the userId for simplicity as set in initiate.ts

    // Verify SuperTokens session for the user ID passed in state
    // This ensures the callback is for a valid, currently logged-in user session.
    let session;
    try {
        session = await superTokensNextWrapper(
            async (next) => verifySession({ sessionRequired: true })(req as any, res as any, next),
            req,
            res
        );
    } catch (error) { // verifySession throws if no session
        logger.error("[MSTeamsAuthCallback] SuperTokens session verification failed in callback:", error);
        return res.status(401).redirect('/Auth/UserLogin?error=session_expired_oauth');
    }

    const sessionUserId = session?.getUserId();

    if (!sessionUserId || sessionUserId !== receivedState) {
        logger.error(`[MSTeamsAuthCallback] Invalid state or session mismatch. Session UserID: ${sessionUserId}, State: ${receivedState}`);
        return res.status(400).redirect('/Settings/UserViewSettings?msteams_auth_error=invalid_state');
    }

    const userId = sessionUserId; // Confirmed user

    if (req.query.error) {
        logger.error(`[MSTeamsAuthCallback] Error from MS Identity platform for user ${userId}: ${req.query.error_description || req.query.error}`);
        return res.redirect(`/Settings/UserViewSettings?msteams_auth_error=${encodeURIComponent(req.query.error as string)}`);
    }

    if (!req.query.code || typeof req.query.code !== 'string') {
        logger.error(`[MSTeamsAuthCallback] No authorization code received for user ${userId}.`);
        return res.redirect('/Settings/UserViewSettings?msteams_auth_error=no_code');
    }

    if (!MSTEAMS_CLIENT_ID || MSTEAMS_CLIENT_ID === "YOUR_MSTEAMS_APP_CLIENT_ID" || !MSTEAMS_CLIENT_SECRET || MSTEAMS_CLIENT_SECRET === "YOUR_MSTEAMS_APP_CLIENT_SECRET") {
        logger.error("[MSTeamsAuthCallback] MS Teams Client ID or Secret not configured.");
        return res.status(500).json({ message: "MS Teams OAuth configuration error on server (callback)." });
    }

    const cca = new ConfidentialClientApplication(msalConfig);
    const tokenRequest: AuthorizationCodeRequest = {
        code: req.query.code,
        scopes: MSTEAMS_SCOPES,
        redirectUri: MSTEAMS_REDIRECT_URI,
    };

    try {
        const msalResponse = await cca.acquireTokenByCode(tokenRequest);
        if (!msalResponse || !msalResponse.accessToken) {
            logger.error(`[MSTeamsAuthCallback] Failed to acquire MS Teams token for user ${userId}. MSAL response empty or missing accessToken.`, msalResponse);
            throw new Error("Failed to acquire MS Teams token.");
        }

        logger.info(`[MSTeamsAuthCallback] MS Teams token acquired successfully for user ${userId}. Account: ${msalResponse.account?.username}`);

        const saveResult = await saveMSTeamsUserTokens(userId, msalResponse);
        if (!saveResult.ok) {
            logger.error(`[MSTeamsAuthCallback] Failed to save MS Teams tokens for user ${userId}:`, saveResult.error);
            const errMsg = saveResult.error?.message || 'token_save_failed';
            return res.redirect(`/Settings/UserViewSettings?msteams_auth_error=${encodeURIComponent(errMsg)}`);
        }

        logger.info(`[MSTeamsAuthCallback] MS Teams successfully connected and tokens stored for user ${userId}.`);
        // Redirect to a success page or settings page
        return res.redirect('/Settings/UserViewSettings?msteams_auth_success=true');

    } catch (error: any) {
        logger.error(`[MSTeamsAuthCallback] Error acquiring/saving MS Teams token for user ${userId}:`, error);
        const errMsg = error.message || error.errorCode || 'msteams_token_acquisition_failed';
        return res.redirect(`/Settings/UserViewSettings?msteams_auth_error=${encodeURIComponent(errMsg)}`);
    }
}
