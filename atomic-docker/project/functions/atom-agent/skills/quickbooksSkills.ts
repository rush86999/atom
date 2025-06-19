import OAuthClient from 'intuit-oauth';
import QuickBooks from 'node-quickbooks';
import fs from 'fs/promises';
import path from 'path';
import {
  ATOM_QB_CLIENT_ID,
  ATOM_QB_CLIENT_SECRET,
  ATOM_QB_ENVIRONMENT,
  ATOM_QB_REDIRECT_URI,
  ATOM_QB_TOKEN_FILE_PATH,
  ATOM_QB_SCOPES,
} from '../_libs/constants';
import {
  QuickBooksAuthTokens,
  QuickBooksInvoice,
  // ListQuickBooksInvoicesResponse, // Superseded by QBSkillResponse<ListQBInvoicesData>
  // GetQuickBooksInvoiceDetailsResponse, // Superseded by QBSkillResponse<QuickBooksInvoice>
  QBSkillResponse, // New generic response type
  ListQBInvoicesData, // New data payload type
  SkillError, // Standardized error type
} from '../types';

let oauthClientInstance: OAuthClient | null = null;
const TOKEN_PATH = path.resolve(ATOM_QB_TOKEN_FILE_PATH);

// Export for testing purposes, to reset the client instance if needed.
export function resetOAuthClientInstanceCache() {
    oauthClientInstance = null;
}

function getOAuthClient(): OAuthClient {
  if (!oauthClientInstance) {
    if (!ATOM_QB_CLIENT_ID || !ATOM_QB_CLIENT_SECRET || !ATOM_QB_REDIRECT_URI) {
      // This case should ideally not happen if constants are checked before calling.
      // Throwing an error or ensuring it's handled by callers.
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
        const oauthClient = getOAuthClient(); // This can throw if not configured above this point.
        const authUri = oauthClient.generateAuthUri({
            scope: ATOM_QB_SCOPES,
            state: 'atom_qbo_init_oauth',
        });
        if (!authUri) { // Should not happen if client is properly initialized
            return { ok: false, error: { code: 'QBO_UNKNOWN_ERROR', message: 'Failed to generate QBO Auth URI.' } };
        }
        return { ok: true, data: authUri };
    } catch (error: any) {
        console.error('Error generating QBO Auth URI:', error);
        return { ok: false, error: { code: 'QBO_CONFIG_ERROR', message: `Failed to initialize OAuth client or generate URI: ${error.message}`, details: error } };
    }
}

async function loadTokens(): Promise<QBSkillResponse<QuickBooksAuthTokens | null>> {
  try {
    const data = await fs.readFile(TOKEN_PATH, 'utf-8');
    return { ok: true, data: JSON.parse(data) as QuickBooksAuthTokens };
  } catch (error: any) {
    if (error.code === 'ENOENT') {
        console.log('Token file not found. Need to authorize.');
        return { ok: true, data: null }; // No tokens is not an error itself for loadTokens
    }
    console.warn('Error reading QuickBooks tokens file:', error.message);
    return { ok: false, error: { code: 'QBO_TOKEN_READ_ERROR', message: 'Failed to read token file.', details: error.message } };
  }
}

async function saveTokens(tokenData: OAuthClient.TokenResponseData): Promise<void> {
  const now = Date.now();
  // intuit-oauth TokenResponseData gives expires_in and x_refresh_token_expires_in in seconds
  const tokensToSave: QuickBooksAuthTokens = {
    accessToken: tokenData.access_token!,
    refreshToken: tokenData.refresh_token!,
    realmId: tokenData.realmId!, // realmId should be present in the token response after auth
    accessTokenExpiresAt: now + (tokenData.expires_in! * 1000),
    refreshTokenExpiresAt: now + (tokenData.x_refresh_token_expires_in! * 1000),
    createdAt: now,
  };
  try {
    await fs.writeFile(TOKEN_PATH, JSON.stringify(tokensToSave, null, 2), 'utf-8');
    console.log('QuickBooks tokens saved successfully.');
  } catch (e: any) {
    console.error('Error saving QuickBooks tokens:', e.message);
  }
}

async function getValidTokens(): Promise<QBSkillResponse<QuickBooksAuthTokens>> {
  const loadResponse = await loadTokens();
  if (!loadResponse.ok) return { ok: false, error: loadResponse.error }; // Propagate read error

  let tokens = loadResponse.data;
  if (!tokens) {
    const msg = 'No QuickBooks tokens found. Please authorize the application.';
    console.log(msg);
    return { ok: false, error: { code: 'QBO_AUTH_REQUIRED', message: msg } };
  }

  if (Date.now() >= tokens.accessTokenExpiresAt) {
    console.log('QuickBooks access token expired. Attempting to refresh...');
    if (!tokens.refreshToken || Date.now() >= tokens.refreshTokenExpiresAt) {
        const msg = 'QuickBooks refresh token is missing or expired. Please re-authorize.';
        console.error(msg);
        try { await fs.unlink(TOKEN_PATH); } catch (e) { /* ignore */ }
        return { ok: false, error: { code: 'QBO_REFRESH_TOKEN_EXPIRED', message: msg } };
    }
    try {
      const authClient = getOAuthClient();
      const newTokensResponse = await authClient.refreshUsingToken(tokens.refreshToken);
      const newJsonTokens = newTokensResponse.getJson();
      if (newJsonTokens && newJsonTokens.access_token) {
        await saveTokens(newJsonTokens);
        console.log('QuickBooks tokens refreshed and saved.');
        const reloadedTokensResponse = await loadTokens(); // Reload to get newly calculated expiry
        if (!reloadedTokensResponse.ok || !reloadedTokensResponse.data) {
            const msg = "Failed to reload tokens after refresh.";
            console.error(msg, reloadedTokensResponse.error);
            return { ok: false, error: reloadedTokensResponse.error || {code: 'QBO_TOKEN_READ_ERROR', message: msg }};
        }
        tokens = reloadedTokensResponse.data;
      } else {
        const msg = "Refresh token response was invalid or missing access_token.";
        console.error(msg, newTokensResponse);
        return { ok: false, error: { code: 'QBO_REFRESH_FAILED', message: msg, details: newTokensResponse } };
      }
    } catch (e: any) {
      const msg = `QuickBooks token refresh failed: ${e.message || e}`;
      console.error(msg, e);
      try { await fs.unlink(TOKEN_PATH); } catch (delErr) { console.error("Error deleting invalid token file:", delErr); }
      return { ok: false, error: { code: 'QBO_REFRESH_FAILED', message: msg, details: e } };
    }
  }
  return { ok: true, data: tokens };
}

async function getQboClient(): Promise<QBSkillResponse<QuickBooks>> {
  const tokenResponse = await getValidTokens();
  if (!tokenResponse.ok || !tokenResponse.data) {
    return { ok: false, error: tokenResponse.error }; // Propagate error
  }
  const tokens = tokenResponse.data;

  if (!ATOM_QB_CLIENT_ID || !ATOM_QB_CLIENT_SECRET) {
    const msg = 'QuickBooks Client ID or Secret not configured for QBO client initialization.';
    console.error(msg);
    return { ok: false, error: { code: 'QBO_CONFIG_ERROR', message: msg } };
  }

  // Ensure QuickBooks constructor is called with all required fields as per node-quickbooks documentation
  return new QuickBooks(
    ATOM_QB_CLIENT_ID,
    ATOM_QB_CLIENT_SECRET,
    tokens.accessToken,
    false, // noUserProfile
    tokens.realmId,
    ATOM_QB_ENVIRONMENT === 'sandbox', // useSandbox
    true, // newApp
    null, // debug
    '2.0', // oauthversion
    tokens.refreshToken
  );
  return { ok: true, data: qboInstance }; // Corrected: qboInstance was not defined here before
}

// Basic mapping, can be expanded based on what fields are needed from QuickBooksInvoice
function mapQBInvoiceToInternal(qbInvoice: any): QuickBooksInvoice {
    return {
        Id: qbInvoice.Id,
        DocNumber: qbInvoice.DocNumber,
        TxnDate: qbInvoice.TxnDate,
        DueDate: qbInvoice.DueDate,
        CustomerRef: qbInvoice.CustomerRef ? {
            value: qbInvoice.CustomerRef.value,
            name: qbInvoice.CustomerRef.name,
        } : undefined,
        BillEmail: qbInvoice.BillEmail ? { Address: qbInvoice.BillEmail.Address } : undefined,
        TotalAmt: qbInvoice.TotalAmt,
        Balance: qbInvoice.Balance,
        CurrencyRef: qbInvoice.CurrencyRef ? {
            value: qbInvoice.CurrencyRef.value,
            name: qbInvoice.CurrencyRef.name,
        } : undefined,
        Line: qbInvoice.Line, // Keep as any for now, or map to a defined Line type
        PrivateNote: qbInvoice.PrivateNote,
        CustomerMemo: qbInvoice.CustomerMemo,
        EmailStatus: qbInvoice.EmailStatus,
        // Add any other fields that are directly mappable or needed
    };
}


export async function listQuickBooksInvoices(
  options?: {
    limit?: number;
    offset?: number;
    customerId?: string;
    status?: 'Draft' | 'Open' | 'Paid' | 'Void' | 'Pending' | 'Overdue';
  }
): Promise<QBSkillResponse<ListQBInvoicesData>> {
  const qboClientResponse = await getQboClient();
  if (!qboClientResponse.ok || !qboClientResponse.data) {
    return { ok: false, error: qboClientResponse.error || { code: 'QBO_INIT_FAILED', message: 'QuickBooks client could not be initialized.'} };
  }
  const qbo = qboClientResponse.data;

  const limit = options?.limit || 10;
  const offset = options?.offset || 1;

  let query = 'SELECT * FROM Invoice';
  const conditions: string[] = [];

  if (options?.customerId) {
    conditions.push(`CustomerRef = '${options.customerId}'`);
  }
  if (options?.status) {
    // QBO Invoice statuses are typically queried via fields like 'Balance' or specific status fields.
    // 'Paid': Balance = 0
    // 'Open': Balance > 0 (this includes Overdue)
    // 'Overdue': DueDate < CurrentDate AND Balance > 0
    // 'Void': Voided status field if available (e.g., Status = 'Voided')
    // 'Draft': Usually a specific status or a boolean flag.
    // 'Pending': May not be a standard queryable status directly, might depend on workflow.
    // For this implementation, we'll handle 'Paid' and 'Open'. 'Void' is common.
    // 'Overdue' requires date comparison.
    switch (options.status) {
        case 'Paid':
            conditions.push("Balance = 0");
            break;
        case 'Open': // Includes Overdue, essentially means not fully paid
            conditions.push("Balance > 0");
            break;
        case 'Void':
            conditions.push("DocNumber like '%VOID%'"); // QBO often appends VOID to DocNumber, or specific Voided status.
                                                    // A more robust way is to check the actual `status` field if the SDK exposes it easily
                                                    // or if a specific 'VoidStatus' field exists.
                                                    // For now, this is a common workaround.
            break;
        case 'Overdue':
            // QBO SQL does not support functions like GETDATE() or TODAY directly in WHERE clauses for dates.
            // This would typically be handled by constructing the date string in the application.
            // For simplicity in this example, we'll note this requires external date logic.
            // conditions.push(`DueDate < '${new Date().toISOString().split('T')[0]}' AND Balance > 0`);
            console.warn("Filtering by 'Overdue' status requires date comparison logic not fully implemented in this generic example.");
            // If you need this, you'd construct the date string for 'today' and pass it into the query.
            break;
        default:
            console.warn(`Unsupported status filter '${options.status}' passed to listQuickBooksInvoices.`);
            break;
    }
  }

  if (conditions.length > 0) {
    query += ' WHERE ' + conditions.join(' AND ');
  }

  query += ` ORDERBY MetaData.LastUpdatedTime DESC STARTPOSITION ${offset} MAXRESULTS ${limit}`;

  console.log(`Executing QBO Query: ${query}`);

  return new Promise((resolve) => {
    qbo.query(query, (err: any, queryResponse: any) => {
      if (err) {
        const errorDetails = err.Fault ? err.Fault.Error[0] : err;
        console.error('Error listing QuickBooks Invoices:', JSON.stringify(errorDetails));
        resolve({
            ok: false,
            error: {
                code: `QBO_API_${errorDetails.code || 'QUERY_ERROR'}`,
                message: errorDetails.Message || 'Failed to list QuickBooks invoices.',
                details: errorDetails
            }
        });
      } else {
        const invoices = queryResponse?.QueryResponse?.Invoice?.map(mapQBInvoiceToInternal) || [];
        resolve({
            ok: true,
            data: {
                invoices: invoices,
                queryResponse: queryResponse?.QueryResponse // Contains MaxResults, startPosition, totalCount etc.
            }
        });
      }
    });
  });
}

export async function getQuickBooksInvoiceDetails(invoiceId: string): Promise<QBSkillResponse<QuickBooksInvoice | null>> {
  const qboClientResponse = await getQboClient();
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
        console.error(`Error getting QuickBooks Invoice ${invoiceId}:`, JSON.stringify(errorDetails));
        if (errorDetails.code === '6240' || errorDetails.Message?.includes('object not found')) {
          // For "not found", we return ok:true and data:null, as the API call itself didn't fail.
          resolve({ ok: true, data: null });
        } else {
          resolve({
              ok: false,
              error: {
                  code: `QBO_API_${errorDetails.code || 'GET_ERROR'}`,
                  message: errorDetails.Message || `Failed to get QuickBooks invoice ${invoiceId}.`,
                  details: errorDetails
              }
          });
        }
      } else {
        if (!invoice) {
             resolve({ ok: true, data: null });
        } else {
            resolve({ ok: true, data: mapQBInvoiceToInternal(invoice) });
        }
      }
    });
  });
}

// TODO: Implement handleQuickBooksCallback to exchange auth code for tokens and save them.
// This function would be called by your application's OAuth redirect URI handler.
/*
export async function handleQuickBooksCallback(urlWithCode: string): Promise<QBSkillResponse<{ message: string }>> {
  const oauthClient = getOAuthClient(); // Ensure client is initialized
  if (!oauthClient) {
      return { ok: false, error: { code: 'QBO_CONFIG_ERROR', message: 'OAuth client not initialized due to missing config.'}};
  }
  try {
    const authResponse = await oauthClient.createToken(urlWithCode);
    const tokenJson = authResponse.getJson();

    if (!tokenJson.access_token || !tokenJson.realmId) {
      console.error('Failed to obtain access token or realmId from callback:', tokenJson);
      return {
        ok: false,
        error: {
          code: 'QBO_AUTH_FAILED',
          message: 'Callback failed to return access token or realmId.',
          details: tokenJson
        }
      };
    }
    await saveTokens(tokenJson);
    return { ok: true, data: { message: 'QuickBooks authorization successful. Tokens saved.' } };
  } catch (e: any) {
    console.error('Error processing QuickBooks OAuth callback:', e);
    const errorDetails = e.error_description || e.message || e;
    return {
      ok: false,
      error: {
        code: 'QBO_CALLBACK_ERROR',
        message: `Callback processing failed: ${errorDetails}`,
        details: e
      }
    };
  }
}
*/

// Note: The current implementation relies on a local file for token storage (ATOM_QB_TOKEN_FILE_PATH).
// e.g., export async function createQuickBooksCustomer(...)
// e.g., export async function createQuickBooksInvoice(...)

// Note: The current implementation relies on a local file for token storage (ATOM_QB_TOKEN_FILE_PATH).
// This is suitable for single-instance environments or testing.
// For scalable or serverless deployments, token storage should use a database (e.g., Firestore, DynamoDB)
// or a secure parameter store, associated with the user or tenant.
// The OAuth callback mechanism (redirect URI) would also need to be implemented in the application's
// HTTP server component to receive the authorization code and exchange it for tokens using oauthClient.createToken().
// That initial token acquisition is outside the scope of these direct skill functions but is essential for them to work.
// The getAuthUri() function is provided to help initiate that flow.
// The `saveTokens` and `loadTokens` would be adapted for the chosen storage mechanism.
// Refresh token logic within `getValidTokens` would remain conceptually similar.
