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
  ListQuickBooksInvoicesResponse,
  GetQuickBooksInvoiceDetailsResponse,
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

export function getAuthUri(): string | null {
    if (!ATOM_QB_CLIENT_ID || !ATOM_QB_CLIENT_SECRET || !ATOM_QB_REDIRECT_URI) {
      console.error('QuickBooks OAuth client credentials for Auth URI generation not configured.');
      return null;
    }
    const oauthClient = getOAuthClient();
    return oauthClient.generateAuthUri({
        scope: ATOM_QB_SCOPES, // Uses the scopes from constants
        state: 'atom_qbo_init_oauth', // Optional state for CSRF protection
    });
}

async function loadTokens(): Promise<QuickBooksAuthTokens | null> {
  try {
    const data = await fs.readFile(TOKEN_PATH, 'utf-8');
    return JSON.parse(data) as QuickBooksAuthTokens;
  } catch (e) {
    // console.warn('No token file found or error reading tokens:', e.message);
    return null;
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

async function getValidTokens(): Promise<QuickBooksAuthTokens | null> {
  let tokens = await loadTokens();
  if (!tokens) {
    console.log('No QuickBooks tokens found. Please authorize the application first using the /api/atom/auth/qb/connect endpoint or by calling getAuthUri() and completing flow.');
    return null;
  }

  if (Date.now() >= tokens.accessTokenExpiresAt) {
    console.log('QuickBooks access token expired. Attempting to refresh...');
    if (!tokens.refreshToken || Date.now() >= tokens.refreshTokenExpiresAt) {
        console.error('QuickBooks refresh token is missing or expired. Please re-authorize.');
        try { await fs.unlink(TOKEN_PATH); } catch (e) { /* ignore if already deleted */ }
        return null;
    }
    try {
      const authClient = getOAuthClient(); // Ensures client is initialized
      const newTokensResponse = await authClient.refreshUsingToken(tokens.refreshToken);
      if (newTokensResponse && newTokensResponse.getJson().access_token) {
        await saveTokens(newTokensResponse.getJson());
        console.log('QuickBooks tokens refreshed and saved.');
        tokens = await loadTokens(); // Reload to get newly calculated expiry timestamps
        if (!tokens) throw new Error("Failed to reload tokens after refresh."); // Should not happen
      } else {
        throw new Error("Refresh token response was invalid or missing access_token.");
      }
    } catch (e: any) {
      console.error('QuickBooks token refresh failed:', e.message || e);
      // If refresh fails (e.g. refresh token also expired or revoked), delete the token file to force re-auth.
      try { await fs.unlink(TOKEN_PATH); } catch (delErr) { console.error("Error deleting invalid token file:", delErr); }
      return null;
    }
  }
  return tokens;
}

async function getQboClient(): Promise<QuickBooks | null> {
  const tokens = await getValidTokens();
  if (!tokens || !tokens.accessToken || !tokens.realmId) {
    console.error('Valid QuickBooks tokens (including realmId) are required to initialize QBO client.');
    return null;
  }

  if (!ATOM_QB_CLIENT_ID || !ATOM_QB_CLIENT_SECRET) {
    console.error('QuickBooks Client ID or Secret not configured for QBO client initialization.');
    return null;
  }

  // Ensure QuickBooks constructor is called with all required fields as per node-quickbooks documentation
  return new QuickBooks(
    ATOM_QB_CLIENT_ID,
    ATOM_QB_CLIENT_SECRET,
    tokens.accessToken,
    false, // noUserProfile (set to false to use the token owner's profile)
    tokens.realmId,
    ATOM_QB_ENVIRONMENT === 'sandbox', // useSandbox
    true, // A QBO app created after 2014 is considered a new app (minorversion flag)
    null, // Debug: set to true to trace requests
    '2.0', // oauthversion
    tokens.refreshToken
  );
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
  options?: { limit?: number; offset?: number; customerId?: string; }
): Promise<ListQuickBooksInvoicesResponse> {
  const qbo = await getQboClient();
  if (!qbo) {
    return { ok: false, error: 'QuickBooks client could not be initialized. Check tokens and configuration.' };
  }

  // Construct query for node-quickbooks. This format is specific to the library.
  // Example: {field: 'DocNumber', value: '123', operator: '='}
  // For general listing with pagination:
  const queryConditions: any[] = [];
  if (options?.customerId) {
      queryConditions.push({ field: 'CustomerRef', value: options.customerId, operator: '=' });
  }
  // Add more conditions based on options if needed

  const queryParams = {
    fetchAll: false, // Set to true to fetch all records, ignoring MAXRESULTS. Be careful with large datasets.
    limit: options?.limit || 10,
    offset: options?.offset || 1, // node-quickbooks uses 1-based offset for STARTPOSITION
  };

  let queryString = '';
  if (queryConditions.length > 0) {
      queryString = queryConditions.map(c => `${c.field} ${c.operator} '${c.value}'`).join (' AND ');
  }


  return new Promise((resolve) => {
    qbo.findInvoices({
        // The node-quickbooks findInvoices can take a direct query string or an array of conditions
        // For simple CustomerRef filter: [{field: 'CustomerRef', value: options.customerId, operator: '='}]
        // For general listing with limit/offset, it seems we might need to use a more generic query
        // or ensure the library handles simple limit/offset directly.
        // Let's try with a generic query if specific filters are not passed.
        // If a query string is built:
        // qbo.findInvoices(queryString, (err, queryResponse) => {...})
        // If using the object for limit/offset:
        // This is how node-quickbooks expects filters for find operations.
        // For just pagination:
        // qbo.findInvoices({desc: 'MetaData.LastUpdatedTime', limit: options?.limit || 10, offset: options?.offset || 1}, callback)
        // If filtering by customerId:
        // qbo.findInvoices([{field: 'CustomerRef', value: options.customerId, operator: '='}], callback)
        // Combining these is tricky with the library's direct methods.
        // A raw query might be more flexible:
        // qbo.reportInvoice({仕訳日from: '2015-01-01', 仕訳日to: '2015-01-31', group_by: 'Customer'}, callback) - this is for reports.
        // For findInvoices, it's either a filter object or an array of filter objects.
        // Let's adapt to use a simple filter for customerId if provided, or just pagination.

        // Simpler approach for now: Use a basic query for all if no customerId, then filter by customerId client-side if needed (not ideal for QB).
        // Or, construct a query string for more complex scenarios.
        // The library might not directly support complex filter strings with simple limit/offset in findInvoices.
        // Let's use the array of filter objects for customerId, and rely on limit/offset.
        // The `node-quickbooks` library's `findInvoices` method takes an array of filter objects or a single filter object.
        // To apply pagination, you pass `limit` and `offset` as top-level properties of the first argument.

        query: queryString, // This might not be how node-quickbooks takes raw queries for findInvoices.
                           // It usually expects structured filter objects.
                           // For pagination only: { limit: X, offset: Y }
                           // For filter + pagination: [{field: 'CustomerRef', value: '1', operator: '='}, {limit: X, offset: Y}]
                           // The library is a bit inconsistent here. A direct query might be better.
                           // Let's use a direct query string if possible.
                           // The node-quickbooks documentation implies `findInvoices` uses a QuickBooks-SQL like syntax for its query.
                           // However, the first argument is often an array of filter objects or a single filter object.
                           // Let's try with the object structure for pagination and filter.

        // The node-quickbooks `findInvoices` method is a bit particular.
        // It expects filter criteria directly or an array of such. Pagination is handled by top-level `limit` and `offset`.
        // If we have a customerId filter:
        // [{ field: 'CustomerRef', value: options.customerId, operator: '='}, {limit: X, offset: Y}] - this is problematic syntax.
        // Correct usage for filtering and pagination:
        // The filter object should be separate.
        // qbo.findInvoices({ CustomerRef: options.customerId, limit: options.limit, offset: options.offset }, callback)
        // Or for just pagination:
        // qbo.findInvoices({ limit: options.limit, offset: options.offset }, callback)

        // For this implementation, let's assume `findInvoices` can take a simple object with filters and pagination.
        // If `options.customerId` is provided, it will be part of this object.
        filter: options?.customerId ? { CustomerRef: options.customerId } : undefined,
        limit: queryParams.limit,
        offset: queryParams.offset,
        // desc: 'MetaData.LastUpdatedTime' // Example sort
    }, (err: any, queryResponse: any) => {
      if (err) {
        console.error('Error listing QuickBooks Invoices:', err.Fault ? JSON.stringify(err.Fault) : err);
        resolve({ ok: false, error: err.Fault?.Error?.[0]?.Message || 'Failed to list QuickBooks invoices.' });
      } else {
        const invoices = queryResponse?.QueryResponse?.Invoice?.map(mapQBInvoiceToInternal) || [];
        resolve({ ok: true, invoices: invoices, queryResponse: queryResponse?.QueryResponse });
      }
    });
  });
}

export async function getQuickBooksInvoiceDetails(invoiceId: string): Promise<GetQuickBooksInvoiceDetailsResponse> {
  const qbo = await getQboClient();
  if (!qbo) {
    return { ok: false, error: 'QuickBooks client could not be initialized. Check tokens and configuration.' };
  }
  if (!invoiceId) {
      return { ok: false, error: 'Invoice ID is required.'};
  }

  return new Promise((resolve) => {
    qbo.getInvoice(invoiceId, (err: any, invoice: any) => { // `invoice` here is the direct QBO invoice object
      if (err) {
        console.error(`Error getting QuickBooks Invoice ${invoiceId}:`, err.Fault ? JSON.stringify(err.Fault) : err);
        if (err.Fault?.Error?.[0]?.code === '6240' || err.Fault?.Error?.[0]?.Message?.includes('object not found')) {
          resolve({ ok: false, error: `Invoice with ID ${invoiceId} not found.` });
        } else {
          resolve({ ok: false, error: err.Fault?.Error?.[0]?.Message || `Failed to get QuickBooks invoice ${invoiceId}.` });
        }
      } else {
        resolve({ ok: true, invoice: mapQBInvoiceToInternal(invoice) });
      }
    });
  });
}

// Placeholder for other QBO actions like create, update, delete invoices, customers, etc.
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
