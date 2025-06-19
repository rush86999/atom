import OAuthClient from 'intuit-oauth';
import QuickBooks from 'node-quickbooks';
// File system operations for tokens are removed.
// import fs from 'fs/promises';
// import path from 'path';

import {
  ATOM_QB_CLIENT_ID,
  ATOM_QB_CLIENT_SECRET,
  ATOM_QB_ENVIRONMENT,
  ATOM_QB_REDIRECT_URI,
  // ATOM_QB_TOKEN_FILE_PATH, // Removed
  ATOM_QB_SCOPES,
} from '../_libs/constants';
import { executeGraphQLQuery, executeGraphQLMutation } from '../_libs/graphqlClient'; // Import GraphQL helpers
import {
  QuickBooksAuthTokens,
  QBSkillResponse,
  ListQBInvoicesData,
  SkillError,
  QuickBooksInvoice, // Ensure this is imported if not already
} from '../types';

const QBO_SERVICE_NAME = 'quickbooks_online';
let oauthClientInstance: OAuthClient | null = null;
// const TOKEN_PATH = path.resolve(ATOM_QB_TOKEN_FILE_PATH); // Removed

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

export function getAuthUri(): QBSkillResponse<string> {
    if (!ATOM_QB_CLIENT_ID || !ATOM_QB_CLIENT_SECRET || !ATOM_QB_REDIRECT_URI || !ATOM_QB_SCOPES || ATOM_QB_SCOPES.length === 0) {
      const errorMsg = 'QuickBooks OAuth client credentials or scopes for Auth URI generation not configured.';
      console.error(errorMsg);
      return { ok: false, error: { code: 'QBO_CONFIG_ERROR', message: errorMsg } };
    }
    try {
        const oauthClient = getOAuthClient();
        const authUri = oauthClient.generateAuthUri({
            scope: ATOM_QB_SCOPES,
            state: 'atom_qbo_init_oauth',
        });
        if (!authUri) {
            return { ok: false, error: { code: 'QBO_UNKNOWN_ERROR', message: 'Failed to generate QBO Auth URI.' } };
        }
        return { ok: true, data: authUri };
    } catch (error: any) {
        console.error('Error generating QBO Auth URI:', error);
        return { ok: false, error: { code: 'QBO_CONFIG_ERROR', message: `Failed to initialize OAuth client or generate URI: ${error.message}`, details: error } };
    }
}

async function getStoredQBTokens(userId: string): Promise<QBSkillResponse<QuickBooksAuthTokens | null>> {
  console.log(`Retrieving QBO tokens for userId: ${userId}, service: ${QBO_SERVICE_NAME}`);
  const query = `
    query GetUserQBOTokens($userId: String!, $serviceName: String!) {
      user_tokens(where: {user_id: {_eq: $userId}, service_name: {_eq: $serviceName}}, order_by: {created_at: desc}, limit: 1) {
        access_token
        refresh_token
        expiry_date
        other_data # JSONB field storing { realmId, refreshTokenExpiresAt, createdAt }
      }
    }
  `;
  const variables = { userId, serviceName: QBO_SERVICE_NAME };

  try {
    const response = await executeGraphQLQuery<{ user_tokens: any[] }>(query, variables);
    if (response.errors || !response.data || response.data.user_tokens.length === 0) {
      console.log('No QBO tokens found in database for user:', userId, response.errors);
      return { ok: true, data: null };
    }
    const dbToken = response.data.user_tokens[0];
    const otherData = typeof dbToken.other_data === 'string' ? JSON.parse(dbToken.other_data) : dbToken.other_data;

    const tokens: QuickBooksAuthTokens = {
        accessToken: dbToken.access_token,
        refreshToken: dbToken.refresh_token,
        realmId: otherData?.realmId,
        accessTokenExpiresAt: dbToken.expiry_date ? new Date(dbToken.expiry_date).getTime() : 0,
        refreshTokenExpiresAt: otherData?.refreshTokenExpiresAt ? new Date(otherData.refreshTokenExpiresAt).getTime() : 0,
        createdAt: otherData?.createdAt ? new Date(otherData.createdAt).getTime() : 0,
    };
    if (!tokens.realmId) {
        return { ok: false, error: { code: 'QBO_TOKEN_INVALID', message: 'Stored QBO token is missing realmId.'}};
    }
    return { ok: true, data: tokens };
  } catch (error: any) {
    console.error('Exception during getStoredQBTokens for user:', userId, error);
    return { ok: false, error: { code: 'INTERNAL_ERROR', message: 'Failed to retrieve QBO tokens.', details: error.message } };
  }
}

async function saveQBTokens(userId: string, tokenDataFromOAuth: OAuthClient.TokenResponseData): Promise<QBSkillResponse<void>> {
  console.log(`Saving QBO tokens for userId: ${userId}`);
  const now = Date.now();
  const accessTokenExpiresAt = now + (tokenDataFromOAuth.expires_in! * 1000);
  const refreshTokenExpiresAt = now + (tokenDataFromOAuth.x_refresh_token_expires_in! * 1000);

  const otherData = {
    realmId: tokenDataFromOAuth.realmId!,
    refreshTokenExpiresAt: refreshTokenExpiresAt,
    createdAt: now,
  };

  const mutation = `
    mutation UpsertUserToken($tokenInput: user_tokens_insert_input!) {
      insert_user_tokens_one(object: $tokenInput, on_conflict: { constraint: user_tokens_user_id_service_name_key, update_columns: [access_token, refresh_token, expiry_date, other_data, updated_at]}) {
        id
      }
    }
  `;
  const tokenInput = {
    user_id: userId,
    service_name: QBO_SERVICE_NAME,
    access_token: tokenDataFromOAuth.access_token!,
    refresh_token: tokenDataFromOAuth.refresh_token!,
    expiry_date: new Date(accessTokenExpiresAt).toISOString(),
    other_data: JSON.stringify(otherData), // Store realmId and refresh token expiry here
    updated_at: new Date().toISOString(),
  };

  try {
    const response = await executeGraphQLMutation(mutation, { tokenInput });
    if (response.errors) {
      return { ok: false, error: { code: 'QBO_TOKEN_SAVE_ERROR', message: 'Failed to save QBO tokens to database.', details: response.errors } };
    }
    console.log('QBO tokens saved successfully to database for user:', userId);
    return { ok: true, data: undefined };
  } catch (error: any) {
    return { ok: false, error: { code: 'INTERNAL_ERROR', message: 'Exception saving QBO tokens.', details: error.message } };
  }
}

async function getValidTokens(userId: string): Promise<QBSkillResponse<QuickBooksAuthTokens>> {
  const loadResponse = await getStoredQBTokens(userId);
  if (!loadResponse.ok) return { ok: false, error: loadResponse.error! };

  let tokens = loadResponse.data;
  if (!tokens) {
    return { ok: false, error: { code: 'QBO_AUTH_REQUIRED', message: 'No QuickBooks tokens found. Please authorize.' } };
  }

  if (Date.now() >= tokens.accessTokenExpiresAt) {
    console.log('QuickBooks access token expired for user:', userId, '. Attempting to refresh...');
    if (!tokens.refreshToken || Date.now() >= tokens.refreshTokenExpiresAt) {
        const msg = 'QuickBooks refresh token is missing or expired. Please re-authorize.';
        console.error(msg);
        // Conceptually, one might delete the invalid/expired token from the DB here.
        return { ok: false, error: { code: 'QBO_REFRESH_TOKEN_EXPIRED', message: msg } };
    }
    try {
      const authClient = getOAuthClient();
      const newTokensResponseFromOAuth = await authClient.refreshUsingToken(tokens.refreshToken);
      const newJsonTokens = newTokensResponseFromOAuth.getJson();

      if (newJsonTokens && newJsonTokens.access_token) {
        const saveOp = await saveQBTokens(userId, newJsonTokens);
        if (!saveOp.ok) {
            console.error("CRITICAL: Failed to save refreshed QBO tokens for user:", userId, saveOp.error);
            return {ok: false, error: saveOp.error! };
        }
        console.log('QuickBooks tokens refreshed and saved for user:', userId);

        const reloadedTokensResponse = await getStoredQBTokens(userId);
        if (!reloadedTokensResponse.ok || !reloadedTokensResponse.data) {
            const msg = "Failed to reload QBO tokens after refresh for user:" + userId;
            return { ok: false, error: reloadedTokensResponse.error || {code: 'QBO_TOKEN_READ_ERROR', message: msg }};
        }
        tokens = reloadedTokensResponse.data;
      } else {
        const msg = "Refresh token response was invalid for user:" + userId;
        // Also delete invalid tokens from DB
        return { ok: false, error: { code: 'QBO_REFRESH_FAILED', message: msg, details: newTokensResponseFromOAuth } };
      }
    } catch (e: any) {
      const msg = `QuickBooks token refresh failed for user ${userId}: ${e.message || e}`;
      // Also delete invalid tokens from DB
      return { ok: false, error: { code: 'QBO_REFRESH_FAILED', message: msg, details: e } };
    }
  }
  return { ok: true, data: tokens };
}

async function getQboClient(userId: string): Promise<QBSkillResponse<QuickBooks>> {
  const tokenResponse = await getValidTokens(userId);
  if (!tokenResponse.ok || !tokenResponse.data) {
    return { ok: false, error: tokenResponse.error! };
  }
  const tokens = tokenResponse.data;

  if (!ATOM_QB_CLIENT_ID || !ATOM_QB_CLIENT_SECRET) {
    const msg = 'QuickBooks Client ID or Secret not configured.';
    return { ok: false, error: { code: 'QBO_CONFIG_ERROR', message: msg } };
  }

  const qboInstance = new QuickBooks(
    ATOM_QB_CLIENT_ID, ATOM_QB_CLIENT_SECRET, tokens.accessToken,
    false, tokens.realmId, ATOM_QB_ENVIRONMENT === 'sandbox',
    true, null, '2.0', tokens.refreshToken
  );
  return { ok: true, data: qboInstance };
}

function mapQBInvoiceToInternal(qbInvoice: any): QuickBooksInvoice {
    return { /* ... mapping as before ... */
        Id: qbInvoice.Id, DocNumber: qbInvoice.DocNumber, TxnDate: qbInvoice.TxnDate, DueDate: qbInvoice.DueDate,
        CustomerRef: qbInvoice.CustomerRef ? { value: qbInvoice.CustomerRef.value, name: qbInvoice.CustomerRef.name } : undefined,
        BillEmail: qbInvoice.BillEmail ? { Address: qbInvoice.BillEmail.Address } : undefined,
        TotalAmt: qbInvoice.TotalAmt, Balance: qbInvoice.Balance,
        CurrencyRef: qbInvoice.CurrencyRef ? { value: qbInvoice.CurrencyRef.value, name: qbInvoice.CurrencyRef.name } : undefined,
        Line: qbInvoice.Line, PrivateNote: qbInvoice.PrivateNote, CustomerMemo: qbInvoice.CustomerMemo, EmailStatus: qbInvoice.EmailStatus,
    };
}

export async function listQuickBooksInvoices(
  userId: string,
  options?: { limit?: number; offset?: number; customerId?: string; status?: 'Draft' | 'Open' | 'Paid' | 'Void' | 'Pending' | 'Overdue'; }
): Promise<QBSkillResponse<ListQBInvoicesData>> {
  const qboClientResponse = await getQboClient(userId);
  if (!qboClientResponse.ok || !qboClientResponse.data) {
    return { ok: false, error: qboClientResponse.error || { code: 'QBO_INIT_FAILED', message: 'QuickBooks client could not be initialized.'} };
  }
  const qbo = qboClientResponse.data;

  const limit = options?.limit || 10;
  const offset = options?.offset || 1;

  let query = 'SELECT * FROM Invoice';
  const conditions: string[] = [];

  if (options?.customerId) conditions.push(`CustomerRef = '${options.customerId}'`);
  if (options?.status) {
    switch (options.status) {
        case 'Paid': conditions.push("Balance = 0"); break;
        case 'Open': conditions.push("Balance > 0"); break;
        case 'Void': conditions.push("DocNumber like '%VOID%'"); break; // Simplified
        case 'Overdue': conditions.push(`DueDate < '${new Date().toISOString().split('T')[0]}' AND Balance > 0`); break; // Requires date to be in QBO format
        default: console.warn(`Unsupported status filter '${options.status}'.`); break;
    }
  }
  if (conditions.length > 0) query += ' WHERE ' + conditions.join(' AND ');
  query += ` ORDERBY MetaData.LastUpdatedTime DESC STARTPOSITION ${offset} MAXRESULTS ${limit}`;
  console.log(`Executing QBO Query: ${query}`);

  return new Promise((resolve) => {
    qbo.query(query, (err: any, queryResponse: any) => {
      if (err) {
        const errorDetails = err.Fault ? err.Fault.Error[0] : err;
        resolve({ ok: false, error: { code: `QBO_API_${errorDetails.code || 'QUERY_ERROR'}`, message: errorDetails.Message || 'Failed to list invoices.', details: errorDetails }});
      } else {
        const invoices = queryResponse?.QueryResponse?.Invoice?.map(mapQBInvoiceToInternal) || [];
        resolve({ ok: true, data: { invoices: invoices, queryResponse: queryResponse?.QueryResponse } });
      }
    });
  });
}

export async function getQuickBooksInvoiceDetails(userId: string, invoiceId: string): Promise<QBSkillResponse<QuickBooksInvoice | null>> {
  const qboClientResponse = await getQboClient(userId);
  if (!qboClientResponse.ok || !qboClientResponse.data) {
    return { ok: false, error: qboClientResponse.error || { code: 'QBO_INIT_FAILED', message: 'QuickBooks client could not be initialized.'} };
  }
  const qbo = qboClientResponse.data;

  if (!invoiceId || invoiceId.trim() === '') {
      return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Invoice ID is required.'}};
  }

  return new Promise((resolve) => {
    qbo.getInvoice(invoiceId, (err: any, invoice: any) => {
      if (err) {
        const errorDetails = err.Fault ? err.Fault.Error[0] : err;
        if (errorDetails.code === '6240' || errorDetails.Message?.includes('object not found')) {
          resolve({ ok: true, data: null }); // Not found is not an "error" state for get by ID
        } else {
          resolve({ ok: false, error: { code: `QBO_API_${errorDetails.code || 'GET_ERROR'}`, message: errorDetails.Message || 'Failed to get invoice.', details: errorDetails }});
        }
      } else {
        resolve({ ok: true, data: invoice ? mapQBInvoiceToInternal(invoice) : null });
      }
    });
  });
}

// TODO: Implement handleQuickBooksCallback to exchange auth code for tokens and save them using saveQBTokens.
// This function would be called by your application's OAuth redirect URI handler.
/*
export async function handleQuickBooksCallback(userId: string, urlWithCode: string): Promise<QBSkillResponse<{ message: string }>> {
  const oauthClient = getOAuthClient();
  if (!oauthClient) {
      return { ok: false, error: { code: 'QBO_CONFIG_ERROR', message: 'OAuth client not initialized.'}};
  }
  try {
    const authResponse = await oauthClient.createToken(urlWithCode);
    const tokenJson = authResponse.getJson();

    if (!tokenJson.access_token || !tokenJson.realmId) {
      return { ok: false, error: { code: 'QBO_AUTH_FAILED', message: 'Callback failed to return access token or realmId.', details: tokenJson }};
    }
    const saveOp = await saveQBTokens(userId, tokenJson); // Use new save function
    if (!saveOp.ok) {
        return { ok: false, error: saveOp.error! };
    }
    return { ok: true, data: { message: 'QuickBooks authorization successful. Tokens saved.' } };
  } catch (e: any) {
    const errorDetails = e.error_description || e.message || e;
    return { ok: false, error: { code: 'QBO_CALLBACK_ERROR', message: `Callback processing failed: ${errorDetails}`, details: e }};
  }
}
*/
// Note: Conceptual GraphQL-based token storage replaces the local file system method.
// This makes the skill more suitable for scalable or serverless deployments, assuming the
// GraphQL client (`graphqlClient.ts`) is implemented to connect to a real database.
// The `userId` parameter is now essential for token operations.
