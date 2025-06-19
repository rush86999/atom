import OAuthClient from 'intuit-oauth';
import QuickBooks from 'node-quickbooks';
import { URLSearchParams } from 'url'; // For parsing state from callback URL
import {
  ATOM_QB_CLIENT_ID,
  ATOM_QB_CLIENT_SECRET,
  ATOM_QB_ENVIRONMENT,
  ATOM_QB_REDIRECT_URI,
  ATOM_QB_SCOPES,
  HASURA_GRAPHQL_URL,
  HASURA_ADMIN_SECRET,
} from '../_libs/constants';
import { executeGraphQLQuery, executeGraphQLMutation } from '../_libs/graphqlClient';
import {
  QuickBooksAuthTokens,
  QBSkillResponse,
  ListQBInvoicesData,
  SkillError,
  QuickBooksInvoice,
} from '../types';

const QBO_SERVICE_NAME = 'quickbooks_online';
let oauthClientInstance: OAuthClient | null = null;

export function resetOAuthClientInstanceCache() {
    oauthClientInstance = null;
}

function getOAuthClient(): OAuthClient {
  if (!oauthClientInstance) {
    if (!ATOM_QB_CLIENT_ID || !ATOM_QB_CLIENT_SECRET || !ATOM_QB_REDIRECT_URI) {
      throw new Error('QuickBooks OAuth client credentials (ID, Secret, Redirect URI) not configured.');
    }
    oauthClientInstance = new OAuthClient({
      clientId: ATOM_QB_CLIENT_ID,
      clientSecret: ATOM_QB_CLIENT_SECRET,
      environment: ATOM_QB_ENVIRONMENT,
      redirectUri: ATOM_QB_REDIRECT_URI,
    });
  }
  return oauthClientInstance;
}

/**
 * Generates the QuickBooks Online authorization URI.
 * @returns {QBSkillResponse<string>} The authorization URI or an error response.
 */
export function getAuthUri(stateCSRFToken: string): QBSkillResponse<string> {
    if (!ATOM_QB_CLIENT_ID || !ATOM_QB_CLIENT_SECRET || !ATOM_QB_REDIRECT_URI || !ATOM_QB_SCOPES || ATOM_QB_SCOPES.length === 0) {
      const errorMsg = 'QuickBooks OAuth client credentials or scopes for Auth URI generation not configured.';
      console.error(errorMsg);
      return { ok: false, error: { code: 'QBO_CONFIG_ERROR', message: errorMsg } };
    }
    if (!stateCSRFToken || typeof stateCSRFToken !== 'string' || stateCSRFToken.trim().length < 10) {
        // Basic validation for state token
        const errorMsg = 'A valid state CSRF token must be provided for generating the Auth URI.';
        console.error(errorMsg);
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: errorMsg } };
    }
    try {
        const oauthClient = getOAuthClient();
        const authUri = oauthClient.generateAuthUri({
            scope: ATOM_QB_SCOPES,
            state: stateCSRFToken,
        });
        if (!authUri) {
            return { ok: false, error: { code: 'QBO_UNKNOWN_ERROR', message: 'Failed to generate QBO Auth URI (URI was null/empty).' } };
        }
        return { ok: true, data: authUri };
    } catch (error: any) {
        console.error('Error generating QBO Auth URI:', error);
        return { ok: false, error: { code: 'QBO_CONFIG_ERROR', message: `Failed to initialize OAuth client or generate URI: ${error.message}`, details: error } };
    }
}

interface UserQBTokenRecord {
  access_token: string;
  refresh_token: string;
  expiry_date: string;
  other_data: {
    realmId: string;
    refreshTokenExpiresAt: number;
    tokenCreatedAt: number;
  } | null;
}

async function getStoredQBTokens(userId: string): Promise<QBSkillResponse<QuickBooksAuthTokens | null>> {
  console.log(`Retrieving QBO tokens for userId: ${userId}, service: ${QBO_SERVICE_NAME}`);
  if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'GraphQL client is not configured for QBO token retrieval.' } };
  }
  const query = `
    query GetUserQBOToken($userId: String!, $serviceName: String!) {
      user_tokens(
        where: { user_id: { _eq: $userId }, service_name: { _eq: $serviceName } },
        order_by: { created_at: desc },
        limit: 1
      ) { access_token refresh_token expiry_date other_data }
    }
  `;
  const variables = { userId, serviceName: QBO_SERVICE_NAME };
  const operationName = 'GetUserQBOToken';
  try {
    const response = await executeGraphQLQuery<{ user_tokens: UserQBTokenRecord[] }>(query, variables, operationName, userId);
    if (!response || !response.user_tokens || response.user_tokens.length === 0) {
      return { ok: true, data: null };
    }
    const dbToken = response.user_tokens[0];
    if (!dbToken.other_data || !dbToken.other_data.realmId) {
        return { ok: false, error: { code: 'QBO_TOKEN_INVALID_STRUCTURE', message: 'Stored QBO token is invalid (missing realmId).'}};
    }
    const tokens: QuickBooksAuthTokens = {
        accessToken: dbToken.access_token, refreshToken: dbToken.refresh_token, realmId: dbToken.other_data.realmId,
        accessTokenExpiresAt: new Date(dbToken.expiry_date).getTime(),
        refreshTokenExpiresAt: dbToken.other_data.refreshTokenExpiresAt,
        tokenCreatedAt: dbToken.other_data.tokenCreatedAt,
    };
    return { ok: true, data: tokens };
  } catch (error: any) {
    console.error(`Exception during getStoredQBTokens for user ${userId}:`, error);
    const skillError: SkillError = {
      code: 'TOKEN_FETCH_FAILED', message: `Failed to retrieve QuickBooks Online tokens.`, details: error.message,
    };
    if (error.code) { skillError.details = `${error.code}: ${error.message}`; if (error.code === 'CONFIG_ERROR') skillError.code = 'CONFIG_ERROR'; }
    return { ok: false, error: skillError };
  }
}

async function saveQBTokens(userId: string, tokenDataFromOAuth: OAuthClient.TokenResponseData): Promise<QBSkillResponse<void>> {
  console.log(`Saving QBO tokens for userId: ${userId}`);
  if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'GraphQL client is not configured for QBO token saving.' } };
  }
  const tokenObtainedAt = Date.now();
  const accessTokenExpiresAt = tokenObtainedAt + (tokenDataFromOAuth.expires_in! * 1000);
  const refreshTokenExpiresAt = tokenObtainedAt + (tokenDataFromOAuth.x_refresh_token_expires_in! * 1000);
  if (!tokenDataFromOAuth.realmId) {
    return { ok: false, error: { code: 'QBO_TOKEN_INVALID_STRUCTURE', message: 'realmId missing from QBO OAuth response, cannot save tokens.'}};
  }
  const otherData = {
    realmId: tokenDataFromOAuth.realmId, refreshTokenExpiresAt: refreshTokenExpiresAt, tokenCreatedAt: tokenObtainedAt,
  };
  const mutation = `
    mutation UpsertUserQBOToken($objects: [user_tokens_insert_input!]!) {
      insert_user_tokens(objects: $objects, on_conflict: {
          constraint: user_tokens_user_id_service_name_key,
          update_columns: [access_token, refresh_token, expiry_date, other_data, updated_at]
        }) { affected_rows }
    }
  `;
  const tokenInputForDb = {
    user_id: userId, service_name: QBO_SERVICE_NAME, access_token: tokenDataFromOAuth.access_token!,
    refresh_token: tokenDataFromOAuth.refresh_token!, expiry_date: new Date(accessTokenExpiresAt).toISOString(),
    other_data: otherData, updated_at: new Date().toISOString(),
  };
  const variables = { objects: [tokenInputForDb] };
  const operationName = 'UpsertUserQBOToken';
  try {
    await executeGraphQLMutation<{ insert_user_tokens: { affected_rows: number } }>(mutation, variables, operationName, userId);
    console.log(`QBO tokens saved/updated successfully for user ${userId}.`);
    return { ok: true, data: undefined };
  } catch (error: any) {
    console.error(`Exception saving QBO tokens for user ${userId}:`, error);
    const skillError: SkillError = {
      code: 'TOKEN_SAVE_FAILED', message: `Failed to save QuickBooks Online tokens.`, details: error.message,
    };
     if (error.code) { skillError.details = `${error.code}: ${error.message}`; if (error.code === 'CONFIG_ERROR') skillError.code = 'CONFIG_ERROR';}
    return { ok: false, error: skillError };
  }
}

async function getValidTokens(userId: string): Promise<QBSkillResponse<QuickBooksAuthTokens>> {
  const loadResponse = await getStoredQBTokens(userId);
  if (!loadResponse.ok) return { ok: false, error: loadResponse.error! };
  let currentTokens = loadResponse.data;
  if (!currentTokens) {
    return { ok: false, error: { code: 'QBO_AUTH_REQUIRED', message: 'No QuickBooks tokens found. Please authorize.' } };
  }
  const now = Date.now();
  if (now >= (currentTokens.accessTokenExpiresAt - (5 * 60 * 1000))) {
    console.log(`QBO access token for user ${userId} expired/nearing expiry. Refreshing...`);
    if (!currentTokens.refreshToken || now >= currentTokens.refreshTokenExpiresAt) {
        return { ok: false, error: { code: 'QBO_REFRESH_TOKEN_EXPIRED', message: 'Refresh token missing or expired. Please re-authorize.' } };
    }
    try {
      const authClient = getOAuthClient();
      const refreshedTokenResponse = await authClient.refreshUsingToken(currentTokens.refreshToken);
      if (!refreshedTokenResponse || !refreshedTokenResponse.getJson()?.access_token) {
        return { ok: false, error: { code: 'QBO_REFRESH_FAILED', message: 'Invalid response from OAuth server during refresh.', details: refreshedTokenResponse?.getJson() } };
      }
      const newTokensFromOAuth = refreshedTokenResponse.getJson();
      const saveOp = await saveQBTokens(userId, newTokensFromOAuth);
      if (!saveOp.ok) return {ok: false, error: saveOp.error! };
      console.log(`QBO tokens refreshed and saved for user ${userId}.`);
      const reloadedTokensResponse = await getStoredQBTokens(userId);
      if (!reloadedTokensResponse.ok || !reloadedTokensResponse.data) {
          return { ok: false, error: reloadedTokensResponse.error || {code: 'QBO_TOKEN_RELOAD_FAILED', message: 'Failed to reload tokens after refresh.' }};
      }
      currentTokens = reloadedTokensResponse.data;
    } catch (e: any) {
      const errorDetails = e.originalError?.error_description || e.message || 'Unknown refresh error';
      return { ok: false, error: { code: 'QBO_REFRESH_FAILED', message: `Token refresh API call failed: ${errorDetails}`, details: e } };
    }
  }
  return { ok: true, data: currentTokens };
}

async function getQboClient(userId: string): Promise<QBSkillResponse<QuickBooks>> {
  const tokenResponse = await getValidTokens(userId);
  if (!tokenResponse.ok || !tokenResponse.data) return { ok: false, error: tokenResponse.error! };
  const tokens = tokenResponse.data;
  if (!ATOM_QB_CLIENT_ID || !ATOM_QB_CLIENT_SECRET) {
    return { ok: false, error: { code: 'QBO_CONFIG_ERROR', message: 'Client ID or Secret not configured.' } };
  }
  try {
    return { ok: true, data: new QuickBooks(
      ATOM_QB_CLIENT_ID, ATOM_QB_CLIENT_SECRET, tokens.accessToken, false, tokens.realmId,
      ATOM_QB_ENVIRONMENT === 'sandbox', false, null, '2.0', tokens.refreshToken
    )};
  } catch(initError: any) {
    return { ok: false, error: { code: 'QBO_CLIENT_INIT_FAILED', message: `Error initializing QuickBooks SDK: ${initError.message}`, details: initError }};
  }
}

function mapQBInvoiceToInternal(qbInvoice: any): QuickBooksInvoice { /* ... as before ... */
    return {
        Id: qbInvoice.Id, DocNumber: qbInvoice.DocNumber, TxnDate: qbInvoice.TxnDate, DueDate: qbInvoice.DueDate,
        CustomerRef: qbInvoice.CustomerRef ? { value: qbInvoice.CustomerRef.value, name: qbInvoice.CustomerRef.name } : undefined,
        BillEmail: qbInvoice.BillEmail ? { Address: qbInvoice.BillEmail.Address } : undefined,
        TotalAmt: qbInvoice.TotalAmt, Balance: qbInvoice.Balance,
        CurrencyRef: qbInvoice.CurrencyRef ? { value: qbInvoice.CurrencyRef.value, name: qbInvoice.CurrencyRef.name } : undefined,
        Line: qbInvoice.Line, PrivateNote: qbInvoice.PrivateNote, CustomerMemo: qbInvoice.CustomerMemo, EmailStatus: qbInvoice.EmailStatus,
    };
}

export async function listQuickBooksInvoices( /* ... as before ... */ ): Promise<QBSkillResponse<ListQBInvoicesData>> {
  const qboClientResponse = await getQboClient(userId);
  if (!qboClientResponse.ok || !qboClientResponse.data) {
    return { ok: false, error: qboClientResponse.error || { code: 'QBO_INIT_FAILED', message: 'QBO client init failed for listing invoices.'} };
  }
  const qbo = qboClientResponse.data;
  const limit = options?.limit || 10; const offset = options?.offset || 1;
  let query = 'SELECT * FROM Invoice'; const conditions: string[] = [];
  if (options?.customerId) conditions.push(`CustomerRef = '${options.customerId}'`);
  if (options?.status) {
    switch (options.status) {
        case 'Paid': conditions.push("Balance = 0 AND TotalAmt > 0"); break;
        case 'Open': conditions.push("Balance > 0"); break;
        case 'Void': conditions.push("EmailStatus = 'Void'"); break;
        case 'Overdue': conditions.push(`DueDate < '${new Date().toISOString().split('T')[0]}' AND Balance > 0`); break;
        case 'Pending': conditions.push("EmailStatus = 'Pending'"); break;
        case 'Draft': conditions.push("EmailStatus = 'Draft'"); break;
        default: console.warn(`Unsupported status filter '${options.status}' ignored.`); break;
    }
  }
  if (conditions.length > 0) query += ' WHERE ' + conditions.join(' AND ');
  query += ` ORDERBY MetaData.LastUpdatedTime DESC STARTPOSITION ${offset} MAXRESULTS ${limit}`;
  console.log(`QBO Query (User ${userId}): ${query}`);
  return new Promise((resolve) => {
    qbo.queryInvoices({ query }, (err: any, queryResponse: any) => {
      if (err) {
        const fault = err.Fault || err.fault; const errorDetailsArray = fault?.Error || [{ Message: 'Unknown QBO API error', code: 'UNKNOWN' }];
        const firstError = errorDetailsArray[0]; const errorCode = firstError.code || 'QBO_QUERY_ERROR';
        resolve({ ok: false, error: { code: `QBO_API_ERROR_${errorCode}`, message: firstError.Message || 'Failed to list QBO invoices.', details: fault || err }});
      } else {
        resolve({ ok: true, data: { invoices: queryResponse?.Invoice?.map(mapQBInvoiceToInternal) || [], queryResponse: queryResponse } });
      }
    });
  });
}

export async function getQuickBooksInvoiceDetails( /* ... as before ... */ ): Promise<QBSkillResponse<QuickBooksInvoice | null>> {
  const qboClientResponse = await getQboClient(userId);
  if (!qboClientResponse.ok || !qboClientResponse.data) {
    return { ok: false, error: qboClientResponse.error || { code: 'QBO_INIT_FAILED', message: 'QBO client init failed for invoice details.'} };
  }
  const qbo = qboClientResponse.data;
  if (!invoiceId || invoiceId.trim() === '') {
      return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Invoice ID is required.'}};
  }
  return new Promise((resolve) => {
    qbo.getInvoice(invoiceId, (err: any, invoice: any) => {
      if (err) {
        const fault = err.Fault || err.fault; const errorDetailsArray = fault?.Error || [{ Message: 'Unknown QBO API error', code: 'UNKNOWN' }];
        const firstError = errorDetailsArray[0];
        if (firstError.code === '6240' || firstError.Message?.toLowerCase().includes('object not found')) {
          resolve({ ok: true, data: null });
        } else {
          const errorCode = firstError.code || 'QBO_GET_ERROR';
          resolve({ ok: false, error: { code: `QBO_API_ERROR_${errorCode}`, message: firstError.Message || 'Failed to get QBO invoice.', details: fault || err }});
        }
      } else {
        resolve({ ok: true, data: invoice ? mapQBInvoiceToInternal(invoice) : null });
      }
    });
  });
}

/**
 * Handles the OAuth callback from QuickBooks Online.
 * Exchanges the authorization code for tokens, validates state for CSRF protection, and saves the tokens.
 *
 * @param userId The ID of the user for whom the tokens are being authorized.
 * @param urlWithCode The full callback URL string from QuickBooks (e.g., req.originalUrl or req.url).
 * @param originalState Optional. The 'state' value that was initially sent to QBO's auth URI.
 *                      It should be retrieved from the user's session or a secure temporary store.
 *                      If not provided, CSRF protection is weakened (a warning will be logged).
 * @returns A promise that resolves to a QBSkillResponse indicating success or failure.
 *          On success, data contains a message and the realmId.
 */
export async function handleQuickBooksCallback(
  userId: string,
  urlWithCode: string,
  originalState?: string
): Promise<QBSkillResponse<{ message: string; realmId: string }>> {
  // 1. Perform GraphQL configuration checks (for saveQBTokens)
  if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'GraphQL client is not configured for QBO token saving during callback.' } };
  }

  // 2. Initialize OAuthClient
  let oauthClient: OAuthClient;
  try {
    oauthClient = getOAuthClient();
  } catch (configError: any) {
    // This error (e.g., missing client ID/secret) is critical and from app config.
    return { ok: false, error: { code: 'QBO_CONFIG_ERROR', message: `OAuth client initialization failed: ${configError.message}` } };
  }

  // 3. CSRF Protection
  try {
    const callbackParams = new URLSearchParams(urlWithCode.substring(urlWithCode.indexOf('?')));
    const receivedState = callbackParams.get('state');

    if (originalState) {
      if (!receivedState || receivedState !== originalState) {
        console.error(`QBO OAuth callback state mismatch for user ${userId}. Expected: '${originalState}', Received: '${receivedState}'`);
        return { ok: false, error: { code: 'INVALID_OAUTH_STATE', message: 'OAuth state mismatch. Possible CSRF attack.' } };
      }
    } else {
      console.warn(`QBO OAuth callback for user ${userId}: originalState not provided. CSRF protection is weakened. Received state: '${receivedState}'`);
      // Depending on security policy, you might choose to fail here if originalState is mandatory.
    }
  } catch (e: any) {
    console.error(`Error parsing state from QBO callback URL for user ${userId}: ${urlWithCode}`, e);
    return { ok: false, error: { code: 'URL_PARSING_ERROR', message: 'Failed to parse callback URL parameters.', details: e.message }};
  }

  // 4. Token Exchange
  let tokenDataFromOAuth: OAuthClient.TokenResponseData;
  try {
    const authResponse = await oauthClient.createToken(urlWithCode);
    if (!authResponse || !authResponse.getJson()?.access_token) {
        console.error('QBO OAuth createToken response was invalid or missing access_token for user:', userId, authResponse?.getJson());
        return { ok: false, error: { code: 'OAUTH_TOKEN_EXCHANGE_FAILED', message: 'Failed to exchange authorization code for token: Invalid response from server.', details: authResponse?.getJson() }};
    }
    tokenDataFromOAuth = authResponse.getJson();
  } catch (e: any) {
    const errorDetails = e.originalError?.error_description || e.message || e.intuit_tid || 'Unknown token exchange error';
    console.error(`QBO OAuth token exchange failed for user ${userId}:`, e);
    return { ok: false, error: { code: 'OAUTH_TOKEN_EXCHANGE_FAILED', message: `Token exchange failed: ${errorDetails}`, details: e } };
  }

  // 6. Validate Token Response (especially realmId, as access_token was checked above)
  if (!tokenDataFromOAuth.realmId) {
    console.error(`QBO OAuth callback for user ${userId} did not return realmId.`, tokenDataFromOAuth);
    return { ok: false, error: { code: 'QBO_AUTH_INVALID_RESPONSE', message: 'OAuth response is missing realmId.', details: tokenDataFromOAuth } };
  }

  // 7. Persist Tokens
  const saveOp = await saveQBTokens(userId, tokenDataFromOAuth);
  if (!saveOp.ok) {
    // Propagate the detailed error from saveQBTokens (e.g., TOKEN_SAVE_FAILED, CONFIG_ERROR)
    return { ok: false, error: saveOp.error! };
  }

  // 8. Success
  console.log(`QuickBooks authorization successful and tokens saved for user ${userId}, realmId ${tokenDataFromOAuth.realmId}.`);
  return {
    ok: true,
    data: {
      message: 'QuickBooks authorization successful. Tokens saved.',
      realmId: tokenDataFromOAuth.realmId
    }
  };
}

[end of atomic-docker/project/functions/atom-agent/skills/quickbooksSkills.ts]
