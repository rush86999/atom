import OAuthClient from 'intuit-oauth';
import QuickBooks from 'node-quickbooks';
import { URLSearchParams } from 'url'; // For parsing state from callback URL
import { ATOM_QB_CLIENT_ID, ATOM_QB_CLIENT_SECRET, ATOM_QB_ENVIRONMENT, ATOM_QB_REDIRECT_URI, ATOM_QB_SCOPES, HASURA_GRAPHQL_URL, HASURA_ADMIN_SECRET, } from '../_libs/constants';
import { executeGraphQLQuery, executeGraphQLMutation, } from '../_libs/graphqlClient';
const QBO_SERVICE_NAME = 'quickbooks_online';
let oauthClientInstance = null;
export function resetOAuthClientInstanceCache() {
    oauthClientInstance = null;
}
function getOAuthClient() {
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
export function getAuthUri(stateCSRFToken) {
    if (!ATOM_QB_CLIENT_ID ||
        !ATOM_QB_CLIENT_SECRET ||
        !ATOM_QB_REDIRECT_URI ||
        !ATOM_QB_SCOPES ||
        ATOM_QB_SCOPES.length === 0) {
        const errorMsg = 'QuickBooks OAuth client credentials or scopes for Auth URI generation not configured.';
        console.error(errorMsg);
        return {
            ok: false,
            error: { code: 'QBO_CONFIG_ERROR', message: errorMsg },
        };
    }
    if (!stateCSRFToken ||
        typeof stateCSRFToken !== 'string' ||
        stateCSRFToken.trim().length < 10) {
        // Basic validation for state token
        const errorMsg = 'A valid state CSRF token must be provided for generating the Auth URI.';
        console.error(errorMsg);
        return {
            ok: false,
            error: { code: 'VALIDATION_ERROR', message: errorMsg },
        };
    }
    try {
        const oauthClient = getOAuthClient();
        const authUri = oauthClient.generateAuthUri({
            scope: ATOM_QB_SCOPES,
            state: stateCSRFToken,
        });
        if (!authUri) {
            return {
                ok: false,
                error: {
                    code: 'QBO_UNKNOWN_ERROR',
                    message: 'Failed to generate QBO Auth URI (URI was null/empty).',
                },
            };
        }
        return { ok: true, data: authUri };
    }
    catch (error) {
        console.error('Error generating QBO Auth URI:', error);
        return {
            ok: false,
            error: {
                code: 'QBO_CONFIG_ERROR',
                message: `Failed to initialize OAuth client or generate URI: ${error.message}`,
                details: error,
            },
        };
    }
}
async function getStoredQBTokens(userId) {
    console.log(`Retrieving QBO tokens for userId: ${userId}, service: ${QBO_SERVICE_NAME}`);
    if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'GraphQL client is not configured for QBO token retrieval.',
            },
        };
    }
    const query = `
    query GetUserQBOToken($userId: String!, $serviceName: String!) {
      user_tokens(
        where: { user_id: { _eq: $userId }, service: { _eq: $serviceName } },
        order_by: { created_at: desc },
        limit: 1
      ) { access_token, refresh_token, expires_at, meta }
    }
  `;
    const variables = { userId, serviceName: QBO_SERVICE_NAME };
    const operationName = 'GetUserQBOToken';
    try {
        const response = await executeGraphQLQuery(query, variables, operationName, userId);
        if (!response ||
            !response.user_tokens ||
            response.user_tokens.length === 0) {
            return { ok: true, data: null };
        }
        const dbToken = response.user_tokens[0];
        if (!dbToken.meta || !dbToken.meta.realmId) {
            return {
                ok: false,
                error: {
                    code: 'QBO_TOKEN_INVALID_STRUCTURE',
                    message: 'Stored QBO token is invalid (missing realmId).',
                },
            };
        }
        const tokens = {
            accessToken: dbToken.access_token,
            refreshToken: dbToken.refresh_token,
            realmId: dbToken.meta.realmId,
            accessTokenExpiresAt: new Date(dbToken.expires_at).getTime(),
            refreshTokenExpiresAt: dbToken.meta.refreshTokenExpiresAt,
            tokenCreatedAt: dbToken.meta.tokenCreatedAt,
        };
        return { ok: true, data: tokens };
    }
    catch (error) {
        console.error(`Exception during getStoredQBTokens for userId ${userId}:`, error);
        const skillError = {
            code: 'TOKEN_FETCH_FAILED',
            message: `Failed to retrieve QuickBooks Online tokens.`,
            details: error.message,
        };
        if (error.code) {
            skillError.details = `${error.code}: ${error.message}`;
            if (error.code === 'CONFIG_ERROR')
                skillError.code = 'CONFIG_ERROR';
        }
        return { ok: false, error: skillError };
    }
}
async function saveQBTokens(userId, tokenDataFromOAuth) {
    console.log(`Saving QBO tokens for userId: ${userId}`);
    if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'GraphQL client is not configured for QBO token saving.',
            },
        };
    }
    const tokenObtainedAt = Date.now();
    const accessTokenExpiresAt = tokenObtainedAt + tokenDataFromOAuth.expires_in * 1000;
    const refreshTokenExpiresAt = tokenObtainedAt + tokenDataFromOAuth.x_refresh_token_expires_in * 1000;
    if (!tokenDataFromOAuth.realmId) {
        return {
            ok: false,
            error: {
                code: 'QBO_TOKEN_INVALID_STRUCTURE',
                message: 'realmId missing from QBO OAuth response, cannot save tokens.',
            },
        };
    }
    const meta = {
        realmId: tokenDataFromOAuth.realmId,
        refreshTokenExpiresAt: refreshTokenExpiresAt,
        tokenCreatedAt: tokenObtainedAt,
    };
    const mutation = `
    mutation UpsertUserQBOToken($objects: [user_tokens_insert_input!]!) {
      insert_user_tokens(objects: $objects, on_conflict: {
          constraint: user_tokens_user_id_service_key,
          update_columns: [access_token, refresh_token, expires_at, meta, updated_at]
        }) { affected_rows }
    }
  `;
    const tokenInputForDb = {
        user_id: userId,
        service: QBO_SERVICE_NAME,
        access_token: tokenDataFromOAuth.access_token,
        refresh_token: tokenDataFromOAuth.refresh_token,
        expires_at: new Date(accessTokenExpiresAt).toISOString(),
        meta: meta,
        updated_at: new Date().toISOString(),
    };
    const variables = { objects: [tokenInputForDb] };
    const operationName = 'UpsertUserQBOToken';
    try {
        await executeGraphQLMutation(mutation, variables, operationName, userId);
        console.log(`QBO tokens saved/updated successfully for user ${userId}.`);
        return { ok: true, data: undefined };
    }
    catch (error) {
        console.error(`Exception saving QBO tokens for user ${userId}:`, error);
        const skillError = {
            code: 'TOKEN_SAVE_FAILED',
            message: `Failed to save QuickBooks Online tokens.`,
            details: error.message,
        };
        if (error.code) {
            skillError.details = `${error.code}: ${error.message}`;
            if (error.code === 'CONFIG_ERROR')
                skillError.code = 'CONFIG_ERROR';
        }
        return { ok: false, error: skillError };
    }
}
async function getValidTokens(userId) {
    const loadResponse = await getStoredQBTokens(userId);
    if (!loadResponse.ok)
        return { ok: false, error: loadResponse.error };
    let currentTokens = loadResponse.data;
    if (!currentTokens) {
        return {
            ok: false,
            error: {
                code: 'QBO_AUTH_REQUIRED',
                message: 'No QuickBooks tokens found. Please authorize.',
            },
        };
    }
    const now = Date.now();
    if (now >= currentTokens.accessTokenExpiresAt - 5 * 60 * 1000) {
        console.log(`QBO access token for user ${userId} expired/nearing expiry. Refreshing...`);
        if (!currentTokens.refreshToken ||
            now >= currentTokens.refreshTokenExpiresAt) {
            return {
                ok: false,
                error: {
                    code: 'QBO_REFRESH_TOKEN_EXPIRED',
                    message: 'Refresh token missing or expired. Please re-authorize.',
                },
            };
        }
        try {
            const authClient = getOAuthClient();
            const refreshedTokenResponse = await authClient.refreshUsingToken(currentTokens.refreshToken);
            if (!refreshedTokenResponse ||
                !refreshedTokenResponse.getJson()?.access_token) {
                return {
                    ok: false,
                    error: {
                        code: 'QBO_REFRESH_FAILED',
                        message: 'Invalid response from OAuth server during refresh.',
                        details: refreshedTokenResponse?.getJson(),
                    },
                };
            }
            const newTokensFromOAuth = refreshedTokenResponse.getJson();
            const saveOp = await saveQBTokens(userId, newTokensFromOAuth);
            if (!saveOp.ok)
                return { ok: false, error: saveOp.error };
            console.log(`QBO tokens refreshed and saved for user ${userId}.`);
            const reloadedTokensResponse = await getStoredQBTokens(userId);
            if (!reloadedTokensResponse.ok || !reloadedTokensResponse.data) {
                return {
                    ok: false,
                    error: reloadedTokensResponse.error || {
                        code: 'QBO_TOKEN_RELOAD_FAILED',
                        message: 'Failed to reload tokens after refresh.',
                    },
                };
            }
            currentTokens = reloadedTokensResponse.data;
        }
        catch (e) {
            const errorDetails = e.originalError?.error_description ||
                e.message ||
                'Unknown refresh error';
            return {
                ok: false,
                error: {
                    code: 'QBO_REFRESH_FAILED',
                    message: `Token refresh API call failed: ${errorDetails}`,
                    details: e,
                },
            };
        }
    }
    return { ok: true, data: currentTokens };
}
async function getQboClient(userId) {
    const tokenResponse = await getValidTokens(userId);
    if (!tokenResponse.ok || !tokenResponse.data)
        return { ok: false, error: tokenResponse.error };
    const tokens = tokenResponse.data;
    if (!ATOM_QB_CLIENT_ID || !ATOM_QB_CLIENT_SECRET) {
        return {
            ok: false,
            error: {
                code: 'QBO_CONFIG_ERROR',
                message: 'Client ID or Secret not configured.',
            },
        };
    }
    try {
        return {
            ok: true,
            data: new QuickBooks(ATOM_QB_CLIENT_ID, ATOM_QB_CLIENT_SECRET, tokens.accessToken, false, tokens.realmId, ATOM_QB_ENVIRONMENT === 'sandbox', false, null, '2.0', tokens.refreshToken),
        };
    }
    catch (initError) {
        return {
            ok: false,
            error: {
                code: 'QBO_CLIENT_INIT_FAILED',
                message: `Error initializing QuickBooks SDK: ${initError.message}`,
                details: initError,
            },
        };
    }
}
function mapQBInvoiceToInternal(qbInvoice) {
    /* ... as before ... */
    return {
        Id: qbInvoice.Id,
        DocNumber: qbInvoice.DocNumber,
        TxnDate: qbInvoice.TxnDate,
        DueDate: qbInvoice.DueDate,
        CustomerRef: qbInvoice.CustomerRef
            ? { value: qbInvoice.CustomerRef.value, name: qbInvoice.CustomerRef.name }
            : undefined,
        BillEmail: qbInvoice.BillEmail
            ? { Address: qbInvoice.BillEmail.Address }
            : undefined,
        TotalAmt: qbInvoice.TotalAmt,
        Balance: qbInvoice.Balance,
        CurrencyRef: qbInvoice.CurrencyRef
            ? { value: qbInvoice.CurrencyRef.value, name: qbInvoice.CurrencyRef.name }
            : undefined,
        Line: qbInvoice.Line,
        PrivateNote: qbInvoice.PrivateNote,
        CustomerMemo: qbInvoice.CustomerMemo,
        EmailStatus: qbInvoice.EmailStatus,
    };
}
export async function listQuickBooksInvoices(userId, options) {
    const qboClientResponse = await getQboClient(userId);
    if (!qboClientResponse.ok || !qboClientResponse.data) {
        return {
            ok: false,
            error: qboClientResponse.error || {
                code: 'QBO_INIT_FAILED',
                message: 'QBO client init failed for listing invoices.',
            },
        };
    }
    const qbo = qboClientResponse.data;
    const limit = options?.limit || 10;
    const offset = options?.offset || 1;
    let query = 'SELECT * FROM Invoice';
    const conditions = [];
    if (options?.customerId)
        conditions.push(`CustomerRef = '${options.customerId}'`);
    if (options?.status) {
        switch (options.status) {
            case 'Paid':
                conditions.push('Balance = 0 AND TotalAmt > 0');
                break;
            case 'Open':
                conditions.push('Balance > 0');
                break;
            case 'Void':
                conditions.push("EmailStatus = 'Void'");
                break;
            case 'Overdue':
                conditions.push(`DueDate < '${new Date().toISOString().split('T')[0]}' AND Balance > 0`);
                break;
            case 'Pending':
                conditions.push("EmailStatus = 'Pending'");
                break;
            case 'Draft':
                conditions.push("EmailStatus = 'Draft'");
                break;
            default:
                console.warn(`Unsupported status filter '${options.status}' ignored.`);
                break;
        }
    }
    if (conditions.length > 0)
        query += ' WHERE ' + conditions.join(' AND ');
    query += ` ORDERBY MetaData.LastUpdatedTime DESC STARTPOSITION ${offset} MAXRESULTS ${limit}`;
    console.log(`QBO Query (User ${userId}): ${query}`);
    return new Promise((resolve) => {
        qbo.queryInvoices({ query }, (err, queryResponse) => {
            if (err) {
                const fault = err.Fault || err.fault;
                const errorDetailsArray = fault?.Error || [
                    { Message: 'Unknown QBO API error', code: 'UNKNOWN' },
                ];
                const firstError = errorDetailsArray[0];
                const errorCode = firstError.code || 'QBO_QUERY_ERROR';
                resolve({
                    ok: false,
                    error: {
                        code: `QBO_API_ERROR_${errorCode}`,
                        message: firstError.Message || 'Failed to list QBO invoices.',
                        details: fault || err,
                    },
                });
            }
            else {
                resolve({
                    ok: true,
                    data: {
                        invoices: queryResponse?.Invoice?.map(mapQBInvoiceToInternal) || [],
                        queryResponse: queryResponse,
                    },
                });
            }
        });
    });
}
export async function getQuickBooksInvoiceDetails(userId, invoiceId) {
    const qboClientResponse = await getQboClient(userId);
    if (!qboClientResponse.ok || !qboClientResponse.data) {
        return {
            ok: false,
            error: qboClientResponse.error || {
                code: 'QBO_INIT_FAILED',
                message: 'QBO client init failed for invoice details.',
            },
        };
    }
    const qbo = qboClientResponse.data;
    if (!invoiceId || invoiceId.trim() === '') {
        return {
            ok: false,
            error: { code: 'VALIDATION_ERROR', message: 'Invoice ID is required.' },
        };
    }
    return new Promise((resolve) => {
        qbo.getInvoice(invoiceId, (err, invoice) => {
            if (err) {
                const fault = err.Fault || err.fault;
                const errorDetailsArray = fault?.Error || [
                    { Message: 'Unknown QBO API error', code: 'UNKNOWN' },
                ];
                const firstError = errorDetailsArray[0];
                if (firstError.code === '6240' ||
                    firstError.Message?.toLowerCase().includes('object not found')) {
                    resolve({ ok: true, data: null });
                }
                else {
                    const errorCode = firstError.code || 'QBO_GET_ERROR';
                    resolve({
                        ok: false,
                        error: {
                            code: `QBO_API_ERROR_${errorCode}`,
                            message: firstError.Message || 'Failed to get QBO invoice.',
                            details: fault || err,
                        },
                    });
                }
            }
            else {
                resolve({
                    ok: true,
                    data: invoice ? mapQBInvoiceToInternal(invoice) : null,
                });
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
export async function handleQuickBooksCallback(userId, urlWithCode, originalState) {
    // 1. Perform GraphQL configuration checks (for saveQBTokens)
    if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'GraphQL client is not configured for QBO token saving during callback.',
            },
        };
    }
    // 2. Initialize OAuthClient
    let oauthClient;
    try {
        oauthClient = getOAuthClient();
    }
    catch (configError) {
        // This error (e.g., missing client ID/secret) is critical and from app config.
        return {
            ok: false,
            error: {
                code: 'QBO_CONFIG_ERROR',
                message: `OAuth client initialization failed: ${configError.message}`,
            },
        };
    }
    // 3. CSRF Protection
    try {
        const callbackParams = new URLSearchParams(urlWithCode.substring(urlWithCode.indexOf('?')));
        const receivedState = callbackParams.get('state');
        if (originalState) {
            if (!receivedState || receivedState !== originalState) {
                console.error(`QBO OAuth callback state mismatch for user ${userId}. Expected: '${originalState}', Received: '${receivedState}'`);
                return {
                    ok: false,
                    error: {
                        code: 'INVALID_OAUTH_STATE',
                        message: 'OAuth state mismatch. Possible CSRF attack.',
                    },
                };
            }
        }
        else {
            console.warn(`QBO OAuth callback for user ${userId}: originalState not provided. CSRF protection is weakened. Received state: '${receivedState}'`);
            // Depending on security policy, you might choose to fail here if originalState is mandatory.
        }
    }
    catch (e) {
        console.error(`Error parsing state from QBO callback URL for user ${userId}: ${urlWithCode}`, e);
        return {
            ok: false,
            error: {
                code: 'URL_PARSING_ERROR',
                message: 'Failed to parse callback URL parameters.',
                details: e.message,
            },
        };
    }
    // 4. Token Exchange
    let tokenDataFromOAuth;
    try {
        const authResponse = await oauthClient.createToken(urlWithCode);
        if (!authResponse || !authResponse.getJson()?.access_token) {
            console.error('QBO OAuth createToken response was invalid or missing access_token for user:', userId, authResponse?.getJson());
            return {
                ok: false,
                error: {
                    code: 'OAUTH_TOKEN_EXCHANGE_FAILED',
                    message: 'Failed to exchange authorization code for token: Invalid response from server.',
                    details: authResponse?.getJson(),
                },
            };
        }
        tokenDataFromOAuth = authResponse.getJson();
    }
    catch (e) {
        const errorDetails = e.originalError?.error_description ||
            e.message ||
            e.intuit_tid ||
            'Unknown token exchange error';
        console.error(`QBO OAuth token exchange failed for user ${userId}:`, e);
        return {
            ok: false,
            error: {
                code: 'OAUTH_TOKEN_EXCHANGE_FAILED',
                message: `Token exchange failed: ${errorDetails}`,
                details: e,
            },
        };
    }
    // 6. Validate Token Response (especially realmId, as access_token was checked above)
    if (!tokenDataFromOAuth.realmId) {
        console.error(`QBO OAuth callback for user ${userId} did not return realmId.`, tokenDataFromOAuth);
        return {
            ok: false,
            error: {
                code: 'QBO_AUTH_INVALID_RESPONSE',
                message: 'OAuth response is missing realmId.',
                details: tokenDataFromOAuth,
            },
        };
    }
    // 7. Persist Tokens
    const saveOp = await saveQBTokens(userId, tokenDataFromOAuth);
    if (!saveOp.ok) {
        // Propagate the detailed error from saveQBTokens (e.g., TOKEN_SAVE_FAILED, CONFIG_ERROR)
        return { ok: false, error: saveOp.error };
    }
    // 8. Success
    console.log(`QuickBooks authorization successful and tokens saved for user ${userId}, realmId ${tokenDataFromOAuth.realmId}.`);
    return {
        ok: true,
        data: {
            message: 'QuickBooks authorization successful. Tokens saved.',
            realmId: tokenDataFromOAuth.realmId,
        },
    };
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicXVpY2tib29rc1NraWxscy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInF1aWNrYm9va3NTa2lsbHMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxXQUFXLE1BQU0sY0FBYyxDQUFDO0FBQ3ZDLE9BQU8sVUFBVSxNQUFNLGlCQUFpQixDQUFDO0FBQ3pDLE9BQU8sRUFBRSxlQUFlLEVBQUUsTUFBTSxLQUFLLENBQUMsQ0FBQyxzQ0FBc0M7QUFDN0UsT0FBTyxFQUNMLGlCQUFpQixFQUNqQixxQkFBcUIsRUFDckIsbUJBQW1CLEVBQ25CLG9CQUFvQixFQUNwQixjQUFjLEVBQ2Qsa0JBQWtCLEVBQ2xCLG1CQUFtQixHQUNwQixNQUFNLG9CQUFvQixDQUFDO0FBQzVCLE9BQU8sRUFDTCxtQkFBbUIsRUFDbkIsc0JBQXNCLEdBQ3ZCLE1BQU0sd0JBQXdCLENBQUM7QUFTaEMsTUFBTSxnQkFBZ0IsR0FBRyxtQkFBbUIsQ0FBQztBQUM3QyxJQUFJLG1CQUFtQixHQUF1QixJQUFJLENBQUM7QUFFbkQsTUFBTSxVQUFVLDZCQUE2QjtJQUMzQyxtQkFBbUIsR0FBRyxJQUFJLENBQUM7QUFDN0IsQ0FBQztBQUVELFNBQVMsY0FBYztJQUNyQixJQUFJLENBQUMsbUJBQW1CLEVBQUUsQ0FBQztRQUN6QixJQUFJLENBQUMsaUJBQWlCLElBQUksQ0FBQyxxQkFBcUIsSUFBSSxDQUFDLG9CQUFvQixFQUFFLENBQUM7WUFDMUUsTUFBTSxJQUFJLEtBQUssQ0FDYixnRkFBZ0YsQ0FDakYsQ0FBQztRQUNKLENBQUM7UUFDRCxtQkFBbUIsR0FBRyxJQUFJLFdBQVcsQ0FBQztZQUNwQyxRQUFRLEVBQUUsaUJBQWlCO1lBQzNCLFlBQVksRUFBRSxxQkFBcUI7WUFDbkMsV0FBVyxFQUFFLG1CQUFtQjtZQUNoQyxXQUFXLEVBQUUsb0JBQW9CO1NBQ2xDLENBQUMsQ0FBQztJQUNMLENBQUM7SUFDRCxPQUFPLG1CQUFtQixDQUFDO0FBQzdCLENBQUM7QUFFRDs7O0dBR0c7QUFDSCxNQUFNLFVBQVUsVUFBVSxDQUFDLGNBQXNCO0lBQy9DLElBQ0UsQ0FBQyxpQkFBaUI7UUFDbEIsQ0FBQyxxQkFBcUI7UUFDdEIsQ0FBQyxvQkFBb0I7UUFDckIsQ0FBQyxjQUFjO1FBQ2YsY0FBYyxDQUFDLE1BQU0sS0FBSyxDQUFDLEVBQzNCLENBQUM7UUFDRCxNQUFNLFFBQVEsR0FDWix1RkFBdUYsQ0FBQztRQUMxRixPQUFPLENBQUMsS0FBSyxDQUFDLFFBQVEsQ0FBQyxDQUFDO1FBQ3hCLE9BQU87WUFDTCxFQUFFLEVBQUUsS0FBSztZQUNULEtBQUssRUFBRSxFQUFFLElBQUksRUFBRSxrQkFBa0IsRUFBRSxPQUFPLEVBQUUsUUFBUSxFQUFFO1NBQ3ZELENBQUM7SUFDSixDQUFDO0lBQ0QsSUFDRSxDQUFDLGNBQWM7UUFDZixPQUFPLGNBQWMsS0FBSyxRQUFRO1FBQ2xDLGNBQWMsQ0FBQyxJQUFJLEVBQUUsQ0FBQyxNQUFNLEdBQUcsRUFBRSxFQUNqQyxDQUFDO1FBQ0QsbUNBQW1DO1FBQ25DLE1BQU0sUUFBUSxHQUNaLHdFQUF3RSxDQUFDO1FBQzNFLE9BQU8sQ0FBQyxLQUFLLENBQUMsUUFBUSxDQUFDLENBQUM7UUFDeEIsT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFLEVBQUUsSUFBSSxFQUFFLGtCQUFrQixFQUFFLE9BQU8sRUFBRSxRQUFRLEVBQUU7U0FDdkQsQ0FBQztJQUNKLENBQUM7SUFDRCxJQUFJLENBQUM7UUFDSCxNQUFNLFdBQVcsR0FBRyxjQUFjLEVBQUUsQ0FBQztRQUNyQyxNQUFNLE9BQU8sR0FBRyxXQUFXLENBQUMsZUFBZSxDQUFDO1lBQzFDLEtBQUssRUFBRSxjQUFjO1lBQ3JCLEtBQUssRUFBRSxjQUFjO1NBQ3RCLENBQUMsQ0FBQztRQUNILElBQUksQ0FBQyxPQUFPLEVBQUUsQ0FBQztZQUNiLE9BQU87Z0JBQ0wsRUFBRSxFQUFFLEtBQUs7Z0JBQ1QsS0FBSyxFQUFFO29CQUNMLElBQUksRUFBRSxtQkFBbUI7b0JBQ3pCLE9BQU8sRUFBRSx1REFBdUQ7aUJBQ2pFO2FBQ0YsQ0FBQztRQUNKLENBQUM7UUFDRCxPQUFPLEVBQUUsRUFBRSxFQUFFLElBQUksRUFBRSxJQUFJLEVBQUUsT0FBTyxFQUFFLENBQUM7SUFDckMsQ0FBQztJQUFDLE9BQU8sS0FBVSxFQUFFLENBQUM7UUFDcEIsT0FBTyxDQUFDLEtBQUssQ0FBQyxnQ0FBZ0MsRUFBRSxLQUFLLENBQUMsQ0FBQztRQUN2RCxPQUFPO1lBQ0wsRUFBRSxFQUFFLEtBQUs7WUFDVCxLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLGtCQUFrQjtnQkFDeEIsT0FBTyxFQUFFLHNEQUFzRCxLQUFLLENBQUMsT0FBTyxFQUFFO2dCQUM5RSxPQUFPLEVBQUUsS0FBSzthQUNmO1NBQ0YsQ0FBQztJQUNKLENBQUM7QUFDSCxDQUFDO0FBYUQsS0FBSyxVQUFVLGlCQUFpQixDQUM5QixNQUFjO0lBRWQsT0FBTyxDQUFDLEdBQUcsQ0FDVCxxQ0FBcUMsTUFBTSxjQUFjLGdCQUFnQixFQUFFLENBQzVFLENBQUM7SUFDRixJQUFJLENBQUMsa0JBQWtCLElBQUksQ0FBQyxtQkFBbUIsRUFBRSxDQUFDO1FBQ2hELE9BQU87WUFDTCxFQUFFLEVBQUUsS0FBSztZQUNULEtBQUssRUFBRTtnQkFDTCxJQUFJLEVBQUUsY0FBYztnQkFDcEIsT0FBTyxFQUFFLDJEQUEyRDthQUNyRTtTQUNGLENBQUM7SUFDSixDQUFDO0lBQ0QsTUFBTSxLQUFLLEdBQUc7Ozs7Ozs7O0dBUWIsQ0FBQztJQUNGLE1BQU0sU0FBUyxHQUFHLEVBQUUsTUFBTSxFQUFFLFdBQVcsRUFBRSxnQkFBZ0IsRUFBRSxDQUFDO0lBQzVELE1BQU0sYUFBYSxHQUFHLGlCQUFpQixDQUFDO0lBQ3hDLElBQUksQ0FBQztRQUNILE1BQU0sUUFBUSxHQUFHLE1BQU0sbUJBQW1CLENBT3ZDLEtBQUssRUFBRSxTQUFTLEVBQUUsYUFBYSxFQUFFLE1BQU0sQ0FBQyxDQUFDO1FBQzVDLElBQ0UsQ0FBQyxRQUFRO1lBQ1QsQ0FBQyxRQUFRLENBQUMsV0FBVztZQUNyQixRQUFRLENBQUMsV0FBVyxDQUFDLE1BQU0sS0FBSyxDQUFDLEVBQ2pDLENBQUM7WUFDRCxPQUFPLEVBQUUsRUFBRSxFQUFFLElBQUksRUFBRSxJQUFJLEVBQUUsSUFBSSxFQUFFLENBQUM7UUFDbEMsQ0FBQztRQUNELE1BQU0sT0FBTyxHQUFHLFFBQVEsQ0FBQyxXQUFXLENBQUMsQ0FBQyxDQUFDLENBQUM7UUFDeEMsSUFBSSxDQUFDLE9BQU8sQ0FBQyxJQUFJLElBQUksQ0FBQyxPQUFPLENBQUMsSUFBSSxDQUFDLE9BQU8sRUFBRSxDQUFDO1lBQzNDLE9BQU87Z0JBQ0wsRUFBRSxFQUFFLEtBQUs7Z0JBQ1QsS0FBSyxFQUFFO29CQUNMLElBQUksRUFBRSw2QkFBNkI7b0JBQ25DLE9BQU8sRUFBRSxnREFBZ0Q7aUJBQzFEO2FBQ0YsQ0FBQztRQUNKLENBQUM7UUFDRCxNQUFNLE1BQU0sR0FBeUI7WUFDbkMsV0FBVyxFQUFFLE9BQU8sQ0FBQyxZQUFZO1lBQ2pDLFlBQVksRUFBRSxPQUFPLENBQUMsYUFBYTtZQUNuQyxPQUFPLEVBQUUsT0FBTyxDQUFDLElBQUksQ0FBQyxPQUFPO1lBQzdCLG9CQUFvQixFQUFFLElBQUksSUFBSSxDQUFDLE9BQU8sQ0FBQyxVQUFVLENBQUMsQ0FBQyxPQUFPLEVBQUU7WUFDNUQscUJBQXFCLEVBQUUsT0FBTyxDQUFDLElBQUksQ0FBQyxxQkFBcUI7WUFDekQsY0FBYyxFQUFFLE9BQU8sQ0FBQyxJQUFJLENBQUMsY0FBYztTQUM1QyxDQUFDO1FBQ0YsT0FBTyxFQUFFLEVBQUUsRUFBRSxJQUFJLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRSxDQUFDO0lBQ3BDLENBQUM7SUFBQyxPQUFPLEtBQVUsRUFBRSxDQUFDO1FBQ3BCLE9BQU8sQ0FBQyxLQUFLLENBQ1gsaURBQWlELE1BQU0sR0FBRyxFQUMxRCxLQUFLLENBQ04sQ0FBQztRQUNGLE1BQU0sVUFBVSxHQUFlO1lBQzdCLElBQUksRUFBRSxvQkFBb0I7WUFDMUIsT0FBTyxFQUFFLDhDQUE4QztZQUN2RCxPQUFPLEVBQUUsS0FBSyxDQUFDLE9BQU87U0FDdkIsQ0FBQztRQUNGLElBQUksS0FBSyxDQUFDLElBQUksRUFBRSxDQUFDO1lBQ2YsVUFBVSxDQUFDLE9BQU8sR0FBRyxHQUFHLEtBQUssQ0FBQyxJQUFJLEtBQUssS0FBSyxDQUFDLE9BQU8sRUFBRSxDQUFDO1lBQ3ZELElBQUksS0FBSyxDQUFDLElBQUksS0FBSyxjQUFjO2dCQUFFLFVBQVUsQ0FBQyxJQUFJLEdBQUcsY0FBYyxDQUFDO1FBQ3RFLENBQUM7UUFDRCxPQUFPLEVBQUUsRUFBRSxFQUFFLEtBQUssRUFBRSxLQUFLLEVBQUUsVUFBVSxFQUFFLENBQUM7SUFDMUMsQ0FBQztBQUNILENBQUM7QUFFRCxLQUFLLFVBQVUsWUFBWSxDQUN6QixNQUFjLEVBQ2Qsa0JBQWlEO0lBRWpELE9BQU8sQ0FBQyxHQUFHLENBQUMsaUNBQWlDLE1BQU0sRUFBRSxDQUFDLENBQUM7SUFDdkQsSUFBSSxDQUFDLGtCQUFrQixJQUFJLENBQUMsbUJBQW1CLEVBQUUsQ0FBQztRQUNoRCxPQUFPO1lBQ0wsRUFBRSxFQUFFLEtBQUs7WUFDVCxLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLGNBQWM7Z0JBQ3BCLE9BQU8sRUFBRSx3REFBd0Q7YUFDbEU7U0FDRixDQUFDO0lBQ0osQ0FBQztJQUNELE1BQU0sZUFBZSxHQUFHLElBQUksQ0FBQyxHQUFHLEVBQUUsQ0FBQztJQUNuQyxNQUFNLG9CQUFvQixHQUN4QixlQUFlLEdBQUcsa0JBQWtCLENBQUMsVUFBVyxHQUFHLElBQUksQ0FBQztJQUMxRCxNQUFNLHFCQUFxQixHQUN6QixlQUFlLEdBQUcsa0JBQWtCLENBQUMsMEJBQTJCLEdBQUcsSUFBSSxDQUFDO0lBQzFFLElBQUksQ0FBQyxrQkFBa0IsQ0FBQyxPQUFPLEVBQUUsQ0FBQztRQUNoQyxPQUFPO1lBQ0wsRUFBRSxFQUFFLEtBQUs7WUFDVCxLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLDZCQUE2QjtnQkFDbkMsT0FBTyxFQUFFLDhEQUE4RDthQUN4RTtTQUNGLENBQUM7SUFDSixDQUFDO0lBQ0QsTUFBTSxJQUFJLEdBQUc7UUFDWCxPQUFPLEVBQUUsa0JBQWtCLENBQUMsT0FBTztRQUNuQyxxQkFBcUIsRUFBRSxxQkFBcUI7UUFDNUMsY0FBYyxFQUFFLGVBQWU7S0FDaEMsQ0FBQztJQUNGLE1BQU0sUUFBUSxHQUFHOzs7Ozs7O0dBT2hCLENBQUM7SUFDRixNQUFNLGVBQWUsR0FBRztRQUN0QixPQUFPLEVBQUUsTUFBTTtRQUNmLE9BQU8sRUFBRSxnQkFBZ0I7UUFDekIsWUFBWSxFQUFFLGtCQUFrQixDQUFDLFlBQWE7UUFDOUMsYUFBYSxFQUFFLGtCQUFrQixDQUFDLGFBQWM7UUFDaEQsVUFBVSxFQUFFLElBQUksSUFBSSxDQUFDLG9CQUFvQixDQUFDLENBQUMsV0FBVyxFQUFFO1FBQ3hELElBQUksRUFBRSxJQUFJO1FBQ1YsVUFBVSxFQUFFLElBQUksSUFBSSxFQUFFLENBQUMsV0FBVyxFQUFFO0tBQ3JDLENBQUM7SUFDRixNQUFNLFNBQVMsR0FBRyxFQUFFLE9BQU8sRUFBRSxDQUFDLGVBQWUsQ0FBQyxFQUFFLENBQUM7SUFDakQsTUFBTSxhQUFhLEdBQUcsb0JBQW9CLENBQUM7SUFDM0MsSUFBSSxDQUFDO1FBQ0gsTUFBTSxzQkFBc0IsQ0FFekIsUUFBUSxFQUFFLFNBQVMsRUFBRSxhQUFhLEVBQUUsTUFBTSxDQUFDLENBQUM7UUFDL0MsT0FBTyxDQUFDLEdBQUcsQ0FBQyxrREFBa0QsTUFBTSxHQUFHLENBQUMsQ0FBQztRQUN6RSxPQUFPLEVBQUUsRUFBRSxFQUFFLElBQUksRUFBRSxJQUFJLEVBQUUsU0FBUyxFQUFFLENBQUM7SUFDdkMsQ0FBQztJQUFDLE9BQU8sS0FBVSxFQUFFLENBQUM7UUFDcEIsT0FBTyxDQUFDLEtBQUssQ0FBQyx3Q0FBd0MsTUFBTSxHQUFHLEVBQUUsS0FBSyxDQUFDLENBQUM7UUFDeEUsTUFBTSxVQUFVLEdBQWU7WUFDN0IsSUFBSSxFQUFFLG1CQUFtQjtZQUN6QixPQUFPLEVBQUUsMENBQTBDO1lBQ25ELE9BQU8sRUFBRSxLQUFLLENBQUMsT0FBTztTQUN2QixDQUFDO1FBQ0YsSUFBSSxLQUFLLENBQUMsSUFBSSxFQUFFLENBQUM7WUFDZixVQUFVLENBQUMsT0FBTyxHQUFHLEdBQUcsS0FBSyxDQUFDLElBQUksS0FBSyxLQUFLLENBQUMsT0FBTyxFQUFFLENBQUM7WUFDdkQsSUFBSSxLQUFLLENBQUMsSUFBSSxLQUFLLGNBQWM7Z0JBQUUsVUFBVSxDQUFDLElBQUksR0FBRyxjQUFjLENBQUM7UUFDdEUsQ0FBQztRQUNELE9BQU8sRUFBRSxFQUFFLEVBQUUsS0FBSyxFQUFFLEtBQUssRUFBRSxVQUFVLEVBQUUsQ0FBQztJQUMxQyxDQUFDO0FBQ0gsQ0FBQztBQUVELEtBQUssVUFBVSxjQUFjLENBQzNCLE1BQWM7SUFFZCxNQUFNLFlBQVksR0FBRyxNQUFNLGlCQUFpQixDQUFDLE1BQU0sQ0FBQyxDQUFDO0lBQ3JELElBQUksQ0FBQyxZQUFZLENBQUMsRUFBRTtRQUFFLE9BQU8sRUFBRSxFQUFFLEVBQUUsS0FBSyxFQUFFLEtBQUssRUFBRSxZQUFZLENBQUMsS0FBTSxFQUFFLENBQUM7SUFDdkUsSUFBSSxhQUFhLEdBQUcsWUFBWSxDQUFDLElBQUksQ0FBQztJQUN0QyxJQUFJLENBQUMsYUFBYSxFQUFFLENBQUM7UUFDbkIsT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxtQkFBbUI7Z0JBQ3pCLE9BQU8sRUFBRSwrQ0FBK0M7YUFDekQ7U0FDRixDQUFDO0lBQ0osQ0FBQztJQUNELE1BQU0sR0FBRyxHQUFHLElBQUksQ0FBQyxHQUFHLEVBQUUsQ0FBQztJQUN2QixJQUFJLEdBQUcsSUFBSSxhQUFhLENBQUMsb0JBQW9CLEdBQUcsQ0FBQyxHQUFHLEVBQUUsR0FBRyxJQUFJLEVBQUUsQ0FBQztRQUM5RCxPQUFPLENBQUMsR0FBRyxDQUNULDZCQUE2QixNQUFNLHdDQUF3QyxDQUM1RSxDQUFDO1FBQ0YsSUFDRSxDQUFDLGFBQWEsQ0FBQyxZQUFZO1lBQzNCLEdBQUcsSUFBSSxhQUFhLENBQUMscUJBQXFCLEVBQzFDLENBQUM7WUFDRCxPQUFPO2dCQUNMLEVBQUUsRUFBRSxLQUFLO2dCQUNULEtBQUssRUFBRTtvQkFDTCxJQUFJLEVBQUUsMkJBQTJCO29CQUNqQyxPQUFPLEVBQUUsd0RBQXdEO2lCQUNsRTthQUNGLENBQUM7UUFDSixDQUFDO1FBQ0QsSUFBSSxDQUFDO1lBQ0gsTUFBTSxVQUFVLEdBQUcsY0FBYyxFQUFFLENBQUM7WUFDcEMsTUFBTSxzQkFBc0IsR0FBRyxNQUFNLFVBQVUsQ0FBQyxpQkFBaUIsQ0FDL0QsYUFBYSxDQUFDLFlBQVksQ0FDM0IsQ0FBQztZQUNGLElBQ0UsQ0FBQyxzQkFBc0I7Z0JBQ3ZCLENBQUMsc0JBQXNCLENBQUMsT0FBTyxFQUFFLEVBQUUsWUFBWSxFQUMvQyxDQUFDO2dCQUNELE9BQU87b0JBQ0wsRUFBRSxFQUFFLEtBQUs7b0JBQ1QsS0FBSyxFQUFFO3dCQUNMLElBQUksRUFBRSxvQkFBb0I7d0JBQzFCLE9BQU8sRUFBRSxvREFBb0Q7d0JBQzdELE9BQU8sRUFBRSxzQkFBc0IsRUFBRSxPQUFPLEVBQUU7cUJBQzNDO2lCQUNGLENBQUM7WUFDSixDQUFDO1lBQ0QsTUFBTSxrQkFBa0IsR0FBRyxzQkFBc0IsQ0FBQyxPQUFPLEVBQUUsQ0FBQztZQUM1RCxNQUFNLE1BQU0sR0FBRyxNQUFNLFlBQVksQ0FBQyxNQUFNLEVBQUUsa0JBQWtCLENBQUMsQ0FBQztZQUM5RCxJQUFJLENBQUMsTUFBTSxDQUFDLEVBQUU7Z0JBQUUsT0FBTyxFQUFFLEVBQUUsRUFBRSxLQUFLLEVBQUUsS0FBSyxFQUFFLE1BQU0sQ0FBQyxLQUFNLEVBQUUsQ0FBQztZQUMzRCxPQUFPLENBQUMsR0FBRyxDQUFDLDJDQUEyQyxNQUFNLEdBQUcsQ0FBQyxDQUFDO1lBQ2xFLE1BQU0sc0JBQXNCLEdBQUcsTUFBTSxpQkFBaUIsQ0FBQyxNQUFNLENBQUMsQ0FBQztZQUMvRCxJQUFJLENBQUMsc0JBQXNCLENBQUMsRUFBRSxJQUFJLENBQUMsc0JBQXNCLENBQUMsSUFBSSxFQUFFLENBQUM7Z0JBQy9ELE9BQU87b0JBQ0wsRUFBRSxFQUFFLEtBQUs7b0JBQ1QsS0FBSyxFQUFFLHNCQUFzQixDQUFDLEtBQUssSUFBSTt3QkFDckMsSUFBSSxFQUFFLHlCQUF5Qjt3QkFDL0IsT0FBTyxFQUFFLHdDQUF3QztxQkFDbEQ7aUJBQ0YsQ0FBQztZQUNKLENBQUM7WUFDRCxhQUFhLEdBQUcsc0JBQXNCLENBQUMsSUFBSSxDQUFDO1FBQzlDLENBQUM7UUFBQyxPQUFPLENBQU0sRUFBRSxDQUFDO1lBQ2hCLE1BQU0sWUFBWSxHQUNoQixDQUFDLENBQUMsYUFBYSxFQUFFLGlCQUFpQjtnQkFDbEMsQ0FBQyxDQUFDLE9BQU87Z0JBQ1QsdUJBQXVCLENBQUM7WUFDMUIsT0FBTztnQkFDTCxFQUFFLEVBQUUsS0FBSztnQkFDVCxLQUFLLEVBQUU7b0JBQ0wsSUFBSSxFQUFFLG9CQUFvQjtvQkFDMUIsT0FBTyxFQUFFLGtDQUFrQyxZQUFZLEVBQUU7b0JBQ3pELE9BQU8sRUFBRSxDQUFDO2lCQUNYO2FBQ0YsQ0FBQztRQUNKLENBQUM7SUFDSCxDQUFDO0lBQ0QsT0FBTyxFQUFFLEVBQUUsRUFBRSxJQUFJLEVBQUUsSUFBSSxFQUFFLGFBQWEsRUFBRSxDQUFDO0FBQzNDLENBQUM7QUFFRCxLQUFLLFVBQVUsWUFBWSxDQUN6QixNQUFjO0lBRWQsTUFBTSxhQUFhLEdBQUcsTUFBTSxjQUFjLENBQUMsTUFBTSxDQUFDLENBQUM7SUFDbkQsSUFBSSxDQUFDLGFBQWEsQ0FBQyxFQUFFLElBQUksQ0FBQyxhQUFhLENBQUMsSUFBSTtRQUMxQyxPQUFPLEVBQUUsRUFBRSxFQUFFLEtBQUssRUFBRSxLQUFLLEVBQUUsYUFBYSxDQUFDLEtBQU0sRUFBRSxDQUFDO0lBQ3BELE1BQU0sTUFBTSxHQUFHLGFBQWEsQ0FBQyxJQUFJLENBQUM7SUFDbEMsSUFBSSxDQUFDLGlCQUFpQixJQUFJLENBQUMscUJBQXFCLEVBQUUsQ0FBQztRQUNqRCxPQUFPO1lBQ0wsRUFBRSxFQUFFLEtBQUs7WUFDVCxLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLGtCQUFrQjtnQkFDeEIsT0FBTyxFQUFFLHFDQUFxQzthQUMvQztTQUNGLENBQUM7SUFDSixDQUFDO0lBQ0QsSUFBSSxDQUFDO1FBQ0gsT0FBTztZQUNMLEVBQUUsRUFBRSxJQUFJO1lBQ1IsSUFBSSxFQUFFLElBQUksVUFBVSxDQUNsQixpQkFBaUIsRUFDakIscUJBQXFCLEVBQ3JCLE1BQU0sQ0FBQyxXQUFXLEVBQ2xCLEtBQUssRUFDTCxNQUFNLENBQUMsT0FBTyxFQUNkLG1CQUFtQixLQUFLLFNBQVMsRUFDakMsS0FBSyxFQUNMLElBQUksRUFDSixLQUFLLEVBQ0wsTUFBTSxDQUFDLFlBQVksQ0FDcEI7U0FDRixDQUFDO0lBQ0osQ0FBQztJQUFDLE9BQU8sU0FBYyxFQUFFLENBQUM7UUFDeEIsT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSx3QkFBd0I7Z0JBQzlCLE9BQU8sRUFBRSxzQ0FBc0MsU0FBUyxDQUFDLE9BQU8sRUFBRTtnQkFDbEUsT0FBTyxFQUFFLFNBQVM7YUFDbkI7U0FDRixDQUFDO0lBQ0osQ0FBQztBQUNILENBQUM7QUFFRCxTQUFTLHNCQUFzQixDQUFDLFNBQWM7SUFDNUMsdUJBQXVCO0lBQ3ZCLE9BQU87UUFDTCxFQUFFLEVBQUUsU0FBUyxDQUFDLEVBQUU7UUFDaEIsU0FBUyxFQUFFLFNBQVMsQ0FBQyxTQUFTO1FBQzlCLE9BQU8sRUFBRSxTQUFTLENBQUMsT0FBTztRQUMxQixPQUFPLEVBQUUsU0FBUyxDQUFDLE9BQU87UUFDMUIsV0FBVyxFQUFFLFNBQVMsQ0FBQyxXQUFXO1lBQ2hDLENBQUMsQ0FBQyxFQUFFLEtBQUssRUFBRSxTQUFTLENBQUMsV0FBVyxDQUFDLEtBQUssRUFBRSxJQUFJLEVBQUUsU0FBUyxDQUFDLFdBQVcsQ0FBQyxJQUFJLEVBQUU7WUFDMUUsQ0FBQyxDQUFDLFNBQVM7UUFDYixTQUFTLEVBQUUsU0FBUyxDQUFDLFNBQVM7WUFDNUIsQ0FBQyxDQUFDLEVBQUUsT0FBTyxFQUFFLFNBQVMsQ0FBQyxTQUFTLENBQUMsT0FBTyxFQUFFO1lBQzFDLENBQUMsQ0FBQyxTQUFTO1FBQ2IsUUFBUSxFQUFFLFNBQVMsQ0FBQyxRQUFRO1FBQzVCLE9BQU8sRUFBRSxTQUFTLENBQUMsT0FBTztRQUMxQixXQUFXLEVBQUUsU0FBUyxDQUFDLFdBQVc7WUFDaEMsQ0FBQyxDQUFDLEVBQUUsS0FBSyxFQUFFLFNBQVMsQ0FBQyxXQUFXLENBQUMsS0FBSyxFQUFFLElBQUksRUFBRSxTQUFTLENBQUMsV0FBVyxDQUFDLElBQUksRUFBRTtZQUMxRSxDQUFDLENBQUMsU0FBUztRQUNiLElBQUksRUFBRSxTQUFTLENBQUMsSUFBSTtRQUNwQixXQUFXLEVBQUUsU0FBUyxDQUFDLFdBQVc7UUFDbEMsWUFBWSxFQUFFLFNBQVMsQ0FBQyxZQUFZO1FBQ3BDLFdBQVcsRUFBRSxTQUFTLENBQUMsV0FBVztLQUNuQyxDQUFDO0FBQ0osQ0FBQztBQUVELE1BQU0sQ0FBQyxLQUFLLFVBQVUsc0JBQXNCLENBQzFDLE1BQWMsRUFDZCxPQUtDO0lBRUQsTUFBTSxpQkFBaUIsR0FBRyxNQUFNLFlBQVksQ0FBQyxNQUFNLENBQUMsQ0FBQztJQUNyRCxJQUFJLENBQUMsaUJBQWlCLENBQUMsRUFBRSxJQUFJLENBQUMsaUJBQWlCLENBQUMsSUFBSSxFQUFFLENBQUM7UUFDckQsT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFLGlCQUFpQixDQUFDLEtBQUssSUFBSTtnQkFDaEMsSUFBSSxFQUFFLGlCQUFpQjtnQkFDdkIsT0FBTyxFQUFFLDhDQUE4QzthQUN4RDtTQUNGLENBQUM7SUFDSixDQUFDO0lBQ0QsTUFBTSxHQUFHLEdBQUcsaUJBQWlCLENBQUMsSUFBSSxDQUFDO0lBQ25DLE1BQU0sS0FBSyxHQUFHLE9BQU8sRUFBRSxLQUFLLElBQUksRUFBRSxDQUFDO0lBQ25DLE1BQU0sTUFBTSxHQUFHLE9BQU8sRUFBRSxNQUFNLElBQUksQ0FBQyxDQUFDO0lBQ3BDLElBQUksS0FBSyxHQUFHLHVCQUF1QixDQUFDO0lBQ3BDLE1BQU0sVUFBVSxHQUFhLEVBQUUsQ0FBQztJQUNoQyxJQUFJLE9BQU8sRUFBRSxVQUFVO1FBQ3JCLFVBQVUsQ0FBQyxJQUFJLENBQUMsa0JBQWtCLE9BQU8sQ0FBQyxVQUFVLEdBQUcsQ0FBQyxDQUFDO0lBQzNELElBQUksT0FBTyxFQUFFLE1BQU0sRUFBRSxDQUFDO1FBQ3BCLFFBQVEsT0FBTyxDQUFDLE1BQU0sRUFBRSxDQUFDO1lBQ3ZCLEtBQUssTUFBTTtnQkFDVCxVQUFVLENBQUMsSUFBSSxDQUFDLDhCQUE4QixDQUFDLENBQUM7Z0JBQ2hELE1BQU07WUFDUixLQUFLLE1BQU07Z0JBQ1QsVUFBVSxDQUFDLElBQUksQ0FBQyxhQUFhLENBQUMsQ0FBQztnQkFDL0IsTUFBTTtZQUNSLEtBQUssTUFBTTtnQkFDVCxVQUFVLENBQUMsSUFBSSxDQUFDLHNCQUFzQixDQUFDLENBQUM7Z0JBQ3hDLE1BQU07WUFDUixLQUFLLFNBQVM7Z0JBQ1osVUFBVSxDQUFDLElBQUksQ0FDYixjQUFjLElBQUksSUFBSSxFQUFFLENBQUMsV0FBVyxFQUFFLENBQUMsS0FBSyxDQUFDLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FBQyxtQkFBbUIsQ0FDeEUsQ0FBQztnQkFDRixNQUFNO1lBQ1IsS0FBSyxTQUFTO2dCQUNaLFVBQVUsQ0FBQyxJQUFJLENBQUMseUJBQXlCLENBQUMsQ0FBQztnQkFDM0MsTUFBTTtZQUNSLEtBQUssT0FBTztnQkFDVixVQUFVLENBQUMsSUFBSSxDQUFDLHVCQUF1QixDQUFDLENBQUM7Z0JBQ3pDLE1BQU07WUFDUjtnQkFDRSxPQUFPLENBQUMsSUFBSSxDQUFDLDhCQUE4QixPQUFPLENBQUMsTUFBTSxZQUFZLENBQUMsQ0FBQztnQkFDdkUsTUFBTTtRQUNWLENBQUM7SUFDSCxDQUFDO0lBQ0QsSUFBSSxVQUFVLENBQUMsTUFBTSxHQUFHLENBQUM7UUFBRSxLQUFLLElBQUksU0FBUyxHQUFHLFVBQVUsQ0FBQyxJQUFJLENBQUMsT0FBTyxDQUFDLENBQUM7SUFDekUsS0FBSyxJQUFJLHdEQUF3RCxNQUFNLGVBQWUsS0FBSyxFQUFFLENBQUM7SUFDOUYsT0FBTyxDQUFDLEdBQUcsQ0FBQyxtQkFBbUIsTUFBTSxNQUFNLEtBQUssRUFBRSxDQUFDLENBQUM7SUFDcEQsT0FBTyxJQUFJLE9BQU8sQ0FBQyxDQUFDLE9BQU8sRUFBRSxFQUFFO1FBQzdCLEdBQUcsQ0FBQyxhQUFhLENBQUMsRUFBRSxLQUFLLEVBQUUsRUFBRSxDQUFDLEdBQVEsRUFBRSxhQUFrQixFQUFFLEVBQUU7WUFDNUQsSUFBSSxHQUFHLEVBQUUsQ0FBQztnQkFDUixNQUFNLEtBQUssR0FBRyxHQUFHLENBQUMsS0FBSyxJQUFJLEdBQUcsQ0FBQyxLQUFLLENBQUM7Z0JBQ3JDLE1BQU0saUJBQWlCLEdBQUcsS0FBSyxFQUFFLEtBQUssSUFBSTtvQkFDeEMsRUFBRSxPQUFPLEVBQUUsdUJBQXVCLEVBQUUsSUFBSSxFQUFFLFNBQVMsRUFBRTtpQkFDdEQsQ0FBQztnQkFDRixNQUFNLFVBQVUsR0FBRyxpQkFBaUIsQ0FBQyxDQUFDLENBQUMsQ0FBQztnQkFDeEMsTUFBTSxTQUFTLEdBQUcsVUFBVSxDQUFDLElBQUksSUFBSSxpQkFBaUIsQ0FBQztnQkFDdkQsT0FBTyxDQUFDO29CQUNOLEVBQUUsRUFBRSxLQUFLO29CQUNULEtBQUssRUFBRTt3QkFDTCxJQUFJLEVBQUUsaUJBQWlCLFNBQVMsRUFBRTt3QkFDbEMsT0FBTyxFQUFFLFVBQVUsQ0FBQyxPQUFPLElBQUksOEJBQThCO3dCQUM3RCxPQUFPLEVBQUUsS0FBSyxJQUFJLEdBQUc7cUJBQ3RCO2lCQUNGLENBQUMsQ0FBQztZQUNMLENBQUM7aUJBQU0sQ0FBQztnQkFDTixPQUFPLENBQUM7b0JBQ04sRUFBRSxFQUFFLElBQUk7b0JBQ1IsSUFBSSxFQUFFO3dCQUNKLFFBQVEsRUFBRSxhQUFhLEVBQUUsT0FBTyxFQUFFLEdBQUcsQ0FBQyxzQkFBc0IsQ0FBQyxJQUFJLEVBQUU7d0JBQ25FLGFBQWEsRUFBRSxhQUFhO3FCQUM3QjtpQkFDRixDQUFDLENBQUM7WUFDTCxDQUFDO1FBQ0gsQ0FBQyxDQUFDLENBQUM7SUFDTCxDQUFDLENBQUMsQ0FBQztBQUNMLENBQUM7QUFFRCxNQUFNLENBQUMsS0FBSyxVQUFVLDJCQUEyQixDQUMvQyxNQUFjLEVBQ2QsU0FBaUI7SUFFakIsTUFBTSxpQkFBaUIsR0FBRyxNQUFNLFlBQVksQ0FBQyxNQUFNLENBQUMsQ0FBQztJQUNyRCxJQUFJLENBQUMsaUJBQWlCLENBQUMsRUFBRSxJQUFJLENBQUMsaUJBQWlCLENBQUMsSUFBSSxFQUFFLENBQUM7UUFDckQsT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFLGlCQUFpQixDQUFDLEtBQUssSUFBSTtnQkFDaEMsSUFBSSxFQUFFLGlCQUFpQjtnQkFDdkIsT0FBTyxFQUFFLDZDQUE2QzthQUN2RDtTQUNGLENBQUM7SUFDSixDQUFDO0lBQ0QsTUFBTSxHQUFHLEdBQUcsaUJBQWlCLENBQUMsSUFBSSxDQUFDO0lBQ25DLElBQUksQ0FBQyxTQUFTLElBQUksU0FBUyxDQUFDLElBQUksRUFBRSxLQUFLLEVBQUUsRUFBRSxDQUFDO1FBQzFDLE9BQU87WUFDTCxFQUFFLEVBQUUsS0FBSztZQUNULEtBQUssRUFBRSxFQUFFLElBQUksRUFBRSxrQkFBa0IsRUFBRSxPQUFPLEVBQUUseUJBQXlCLEVBQUU7U0FDeEUsQ0FBQztJQUNKLENBQUM7SUFDRCxPQUFPLElBQUksT0FBTyxDQUFDLENBQUMsT0FBTyxFQUFFLEVBQUU7UUFDN0IsR0FBRyxDQUFDLFVBQVUsQ0FBQyxTQUFTLEVBQUUsQ0FBQyxHQUFRLEVBQUUsT0FBWSxFQUFFLEVBQUU7WUFDbkQsSUFBSSxHQUFHLEVBQUUsQ0FBQztnQkFDUixNQUFNLEtBQUssR0FBRyxHQUFHLENBQUMsS0FBSyxJQUFJLEdBQUcsQ0FBQyxLQUFLLENBQUM7Z0JBQ3JDLE1BQU0saUJBQWlCLEdBQUcsS0FBSyxFQUFFLEtBQUssSUFBSTtvQkFDeEMsRUFBRSxPQUFPLEVBQUUsdUJBQXVCLEVBQUUsSUFBSSxFQUFFLFNBQVMsRUFBRTtpQkFDdEQsQ0FBQztnQkFDRixNQUFNLFVBQVUsR0FBRyxpQkFBaUIsQ0FBQyxDQUFDLENBQUMsQ0FBQztnQkFDeEMsSUFDRSxVQUFVLENBQUMsSUFBSSxLQUFLLE1BQU07b0JBQzFCLFVBQVUsQ0FBQyxPQUFPLEVBQUUsV0FBVyxFQUFFLENBQUMsUUFBUSxDQUFDLGtCQUFrQixDQUFDLEVBQzlELENBQUM7b0JBQ0QsT0FBTyxDQUFDLEVBQUUsRUFBRSxFQUFFLElBQUksRUFBRSxJQUFJLEVBQUUsSUFBSSxFQUFFLENBQUMsQ0FBQztnQkFDcEMsQ0FBQztxQkFBTSxDQUFDO29CQUNOLE1BQU0sU0FBUyxHQUFHLFVBQVUsQ0FBQyxJQUFJLElBQUksZUFBZSxDQUFDO29CQUNyRCxPQUFPLENBQUM7d0JBQ04sRUFBRSxFQUFFLEtBQUs7d0JBQ1QsS0FBSyxFQUFFOzRCQUNMLElBQUksRUFBRSxpQkFBaUIsU0FBUyxFQUFFOzRCQUNsQyxPQUFPLEVBQUUsVUFBVSxDQUFDLE9BQU8sSUFBSSw0QkFBNEI7NEJBQzNELE9BQU8sRUFBRSxLQUFLLElBQUksR0FBRzt5QkFDdEI7cUJBQ0YsQ0FBQyxDQUFDO2dCQUNMLENBQUM7WUFDSCxDQUFDO2lCQUFNLENBQUM7Z0JBQ04sT0FBTyxDQUFDO29CQUNOLEVBQUUsRUFBRSxJQUFJO29CQUNSLElBQUksRUFBRSxPQUFPLENBQUMsQ0FBQyxDQUFDLHNCQUFzQixDQUFDLE9BQU8sQ0FBQyxDQUFDLENBQUMsQ0FBQyxJQUFJO2lCQUN2RCxDQUFDLENBQUM7WUFDTCxDQUFDO1FBQ0gsQ0FBQyxDQUFDLENBQUM7SUFDTCxDQUFDLENBQUMsQ0FBQztBQUNMLENBQUM7QUFFRDs7Ozs7Ozs7Ozs7R0FXRztBQUNILE1BQU0sQ0FBQyxLQUFLLFVBQVUsd0JBQXdCLENBQzVDLE1BQWMsRUFDZCxXQUFtQixFQUNuQixhQUFzQjtJQUV0Qiw2REFBNkQ7SUFDN0QsSUFBSSxDQUFDLGtCQUFrQixJQUFJLENBQUMsbUJBQW1CLEVBQUUsQ0FBQztRQUNoRCxPQUFPO1lBQ0wsRUFBRSxFQUFFLEtBQUs7WUFDVCxLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLGNBQWM7Z0JBQ3BCLE9BQU8sRUFDTCx3RUFBd0U7YUFDM0U7U0FDRixDQUFDO0lBQ0osQ0FBQztJQUVELDRCQUE0QjtJQUM1QixJQUFJLFdBQXdCLENBQUM7SUFDN0IsSUFBSSxDQUFDO1FBQ0gsV0FBVyxHQUFHLGNBQWMsRUFBRSxDQUFDO0lBQ2pDLENBQUM7SUFBQyxPQUFPLFdBQWdCLEVBQUUsQ0FBQztRQUMxQiwrRUFBK0U7UUFDL0UsT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxrQkFBa0I7Z0JBQ3hCLE9BQU8sRUFBRSx1Q0FBdUMsV0FBVyxDQUFDLE9BQU8sRUFBRTthQUN0RTtTQUNGLENBQUM7SUFDSixDQUFDO0lBRUQscUJBQXFCO0lBQ3JCLElBQUksQ0FBQztRQUNILE1BQU0sY0FBYyxHQUFHLElBQUksZUFBZSxDQUN4QyxXQUFXLENBQUMsU0FBUyxDQUFDLFdBQVcsQ0FBQyxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsQ0FDaEQsQ0FBQztRQUNGLE1BQU0sYUFBYSxHQUFHLGNBQWMsQ0FBQyxHQUFHLENBQUMsT0FBTyxDQUFDLENBQUM7UUFFbEQsSUFBSSxhQUFhLEVBQUUsQ0FBQztZQUNsQixJQUFJLENBQUMsYUFBYSxJQUFJLGFBQWEsS0FBSyxhQUFhLEVBQUUsQ0FBQztnQkFDdEQsT0FBTyxDQUFDLEtBQUssQ0FDWCw4Q0FBOEMsTUFBTSxnQkFBZ0IsYUFBYSxpQkFBaUIsYUFBYSxHQUFHLENBQ25ILENBQUM7Z0JBQ0YsT0FBTztvQkFDTCxFQUFFLEVBQUUsS0FBSztvQkFDVCxLQUFLLEVBQUU7d0JBQ0wsSUFBSSxFQUFFLHFCQUFxQjt3QkFDM0IsT0FBTyxFQUFFLDZDQUE2QztxQkFDdkQ7aUJBQ0YsQ0FBQztZQUNKLENBQUM7UUFDSCxDQUFDO2FBQU0sQ0FBQztZQUNOLE9BQU8sQ0FBQyxJQUFJLENBQ1YsK0JBQStCLE1BQU0sK0VBQStFLGFBQWEsR0FBRyxDQUNySSxDQUFDO1lBQ0YsNkZBQTZGO1FBQy9GLENBQUM7SUFDSCxDQUFDO0lBQUMsT0FBTyxDQUFNLEVBQUUsQ0FBQztRQUNoQixPQUFPLENBQUMsS0FBSyxDQUNYLHNEQUFzRCxNQUFNLEtBQUssV0FBVyxFQUFFLEVBQzlFLENBQUMsQ0FDRixDQUFDO1FBQ0YsT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxtQkFBbUI7Z0JBQ3pCLE9BQU8sRUFBRSwwQ0FBMEM7Z0JBQ25ELE9BQU8sRUFBRSxDQUFDLENBQUMsT0FBTzthQUNuQjtTQUNGLENBQUM7SUFDSixDQUFDO0lBRUQsb0JBQW9CO0lBQ3BCLElBQUksa0JBQWlELENBQUM7SUFDdEQsSUFBSSxDQUFDO1FBQ0gsTUFBTSxZQUFZLEdBQUcsTUFBTSxXQUFXLENBQUMsV0FBVyxDQUFDLFdBQVcsQ0FBQyxDQUFDO1FBQ2hFLElBQUksQ0FBQyxZQUFZLElBQUksQ0FBQyxZQUFZLENBQUMsT0FBTyxFQUFFLEVBQUUsWUFBWSxFQUFFLENBQUM7WUFDM0QsT0FBTyxDQUFDLEtBQUssQ0FDWCw4RUFBOEUsRUFDOUUsTUFBTSxFQUNOLFlBQVksRUFBRSxPQUFPLEVBQUUsQ0FDeEIsQ0FBQztZQUNGLE9BQU87Z0JBQ0wsRUFBRSxFQUFFLEtBQUs7Z0JBQ1QsS0FBSyxFQUFFO29CQUNMLElBQUksRUFBRSw2QkFBNkI7b0JBQ25DLE9BQU8sRUFDTCxnRkFBZ0Y7b0JBQ2xGLE9BQU8sRUFBRSxZQUFZLEVBQUUsT0FBTyxFQUFFO2lCQUNqQzthQUNGLENBQUM7UUFDSixDQUFDO1FBQ0Qsa0JBQWtCLEdBQUcsWUFBWSxDQUFDLE9BQU8sRUFBRSxDQUFDO0lBQzlDLENBQUM7SUFBQyxPQUFPLENBQU0sRUFBRSxDQUFDO1FBQ2hCLE1BQU0sWUFBWSxHQUNoQixDQUFDLENBQUMsYUFBYSxFQUFFLGlCQUFpQjtZQUNsQyxDQUFDLENBQUMsT0FBTztZQUNULENBQUMsQ0FBQyxVQUFVO1lBQ1osOEJBQThCLENBQUM7UUFDakMsT0FBTyxDQUFDLEtBQUssQ0FBQyw0Q0FBNEMsTUFBTSxHQUFHLEVBQUUsQ0FBQyxDQUFDLENBQUM7UUFDeEUsT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSw2QkFBNkI7Z0JBQ25DLE9BQU8sRUFBRSwwQkFBMEIsWUFBWSxFQUFFO2dCQUNqRCxPQUFPLEVBQUUsQ0FBQzthQUNYO1NBQ0YsQ0FBQztJQUNKLENBQUM7SUFFRCxxRkFBcUY7SUFDckYsSUFBSSxDQUFDLGtCQUFrQixDQUFDLE9BQU8sRUFBRSxDQUFDO1FBQ2hDLE9BQU8sQ0FBQyxLQUFLLENBQ1gsK0JBQStCLE1BQU0sMEJBQTBCLEVBQy9ELGtCQUFrQixDQUNuQixDQUFDO1FBQ0YsT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSwyQkFBMkI7Z0JBQ2pDLE9BQU8sRUFBRSxvQ0FBb0M7Z0JBQzdDLE9BQU8sRUFBRSxrQkFBa0I7YUFDNUI7U0FDRixDQUFDO0lBQ0osQ0FBQztJQUVELG9CQUFvQjtJQUNwQixNQUFNLE1BQU0sR0FBRyxNQUFNLFlBQVksQ0FBQyxNQUFNLEVBQUUsa0JBQWtCLENBQUMsQ0FBQztJQUM5RCxJQUFJLENBQUMsTUFBTSxDQUFDLEVBQUUsRUFBRSxDQUFDO1FBQ2YseUZBQXlGO1FBQ3pGLE9BQU8sRUFBRSxFQUFFLEVBQUUsS0FBSyxFQUFFLEtBQUssRUFBRSxNQUFNLENBQUMsS0FBTSxFQUFFLENBQUM7SUFDN0MsQ0FBQztJQUVELGFBQWE7SUFDYixPQUFPLENBQUMsR0FBRyxDQUNULGlFQUFpRSxNQUFNLGFBQWEsa0JBQWtCLENBQUMsT0FBTyxHQUFHLENBQ2xILENBQUM7SUFDRixPQUFPO1FBQ0wsRUFBRSxFQUFFLElBQUk7UUFDUixJQUFJLEVBQUU7WUFDSixPQUFPLEVBQUUsb0RBQW9EO1lBQzdELE9BQU8sRUFBRSxrQkFBa0IsQ0FBQyxPQUFPO1NBQ3BDO0tBQ0YsQ0FBQztBQUNKLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgT0F1dGhDbGllbnQgZnJvbSAnaW50dWl0LW9hdXRoJztcbmltcG9ydCBRdWlja0Jvb2tzIGZyb20gJ25vZGUtcXVpY2tib29rcyc7XG5pbXBvcnQgeyBVUkxTZWFyY2hQYXJhbXMgfSBmcm9tICd1cmwnOyAvLyBGb3IgcGFyc2luZyBzdGF0ZSBmcm9tIGNhbGxiYWNrIFVSTFxuaW1wb3J0IHtcbiAgQVRPTV9RQl9DTElFTlRfSUQsXG4gIEFUT01fUUJfQ0xJRU5UX1NFQ1JFVCxcbiAgQVRPTV9RQl9FTlZJUk9OTUVOVCxcbiAgQVRPTV9RQl9SRURJUkVDVF9VUkksXG4gIEFUT01fUUJfU0NPUEVTLFxuICBIQVNVUkFfR1JBUEhRTF9VUkwsXG4gIEhBU1VSQV9BRE1JTl9TRUNSRVQsXG59IGZyb20gJy4uL19saWJzL2NvbnN0YW50cyc7XG5pbXBvcnQge1xuICBleGVjdXRlR3JhcGhRTFF1ZXJ5LFxuICBleGVjdXRlR3JhcGhRTE11dGF0aW9uLFxufSBmcm9tICcuLi9fbGlicy9ncmFwaHFsQ2xpZW50JztcbmltcG9ydCB7XG4gIFF1aWNrQm9va3NBdXRoVG9rZW5zLFxuICBRQlNraWxsUmVzcG9uc2UsXG4gIExpc3RRQkludm9pY2VzRGF0YSxcbiAgU2tpbGxFcnJvcixcbiAgUXVpY2tCb29rc0ludm9pY2UsXG59IGZyb20gJy4uL3R5cGVzJztcblxuY29uc3QgUUJPX1NFUlZJQ0VfTkFNRSA9ICdxdWlja2Jvb2tzX29ubGluZSc7XG5sZXQgb2F1dGhDbGllbnRJbnN0YW5jZTogT0F1dGhDbGllbnQgfCBudWxsID0gbnVsbDtcblxuZXhwb3J0IGZ1bmN0aW9uIHJlc2V0T0F1dGhDbGllbnRJbnN0YW5jZUNhY2hlKCkge1xuICBvYXV0aENsaWVudEluc3RhbmNlID0gbnVsbDtcbn1cblxuZnVuY3Rpb24gZ2V0T0F1dGhDbGllbnQoKTogT0F1dGhDbGllbnQge1xuICBpZiAoIW9hdXRoQ2xpZW50SW5zdGFuY2UpIHtcbiAgICBpZiAoIUFUT01fUUJfQ0xJRU5UX0lEIHx8ICFBVE9NX1FCX0NMSUVOVF9TRUNSRVQgfHwgIUFUT01fUUJfUkVESVJFQ1RfVVJJKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAgICdRdWlja0Jvb2tzIE9BdXRoIGNsaWVudCBjcmVkZW50aWFscyAoSUQsIFNlY3JldCwgUmVkaXJlY3QgVVJJKSBub3QgY29uZmlndXJlZC4nXG4gICAgICApO1xuICAgIH1cbiAgICBvYXV0aENsaWVudEluc3RhbmNlID0gbmV3IE9BdXRoQ2xpZW50KHtcbiAgICAgIGNsaWVudElkOiBBVE9NX1FCX0NMSUVOVF9JRCxcbiAgICAgIGNsaWVudFNlY3JldDogQVRPTV9RQl9DTElFTlRfU0VDUkVULFxuICAgICAgZW52aXJvbm1lbnQ6IEFUT01fUUJfRU5WSVJPTk1FTlQsXG4gICAgICByZWRpcmVjdFVyaTogQVRPTV9RQl9SRURJUkVDVF9VUkksXG4gICAgfSk7XG4gIH1cbiAgcmV0dXJuIG9hdXRoQ2xpZW50SW5zdGFuY2U7XG59XG5cbi8qKlxuICogR2VuZXJhdGVzIHRoZSBRdWlja0Jvb2tzIE9ubGluZSBhdXRob3JpemF0aW9uIFVSSS5cbiAqIEByZXR1cm5zIHtRQlNraWxsUmVzcG9uc2U8c3RyaW5nPn0gVGhlIGF1dGhvcml6YXRpb24gVVJJIG9yIGFuIGVycm9yIHJlc3BvbnNlLlxuICovXG5leHBvcnQgZnVuY3Rpb24gZ2V0QXV0aFVyaShzdGF0ZUNTUkZUb2tlbjogc3RyaW5nKTogUUJTa2lsbFJlc3BvbnNlPHN0cmluZz4ge1xuICBpZiAoXG4gICAgIUFUT01fUUJfQ0xJRU5UX0lEIHx8XG4gICAgIUFUT01fUUJfQ0xJRU5UX1NFQ1JFVCB8fFxuICAgICFBVE9NX1FCX1JFRElSRUNUX1VSSSB8fFxuICAgICFBVE9NX1FCX1NDT1BFUyB8fFxuICAgIEFUT01fUUJfU0NPUEVTLmxlbmd0aCA9PT0gMFxuICApIHtcbiAgICBjb25zdCBlcnJvck1zZyA9XG4gICAgICAnUXVpY2tCb29rcyBPQXV0aCBjbGllbnQgY3JlZGVudGlhbHMgb3Igc2NvcGVzIGZvciBBdXRoIFVSSSBnZW5lcmF0aW9uIG5vdCBjb25maWd1cmVkLic7XG4gICAgY29uc29sZS5lcnJvcihlcnJvck1zZyk7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7IGNvZGU6ICdRQk9fQ09ORklHX0VSUk9SJywgbWVzc2FnZTogZXJyb3JNc2cgfSxcbiAgICB9O1xuICB9XG4gIGlmIChcbiAgICAhc3RhdGVDU1JGVG9rZW4gfHxcbiAgICB0eXBlb2Ygc3RhdGVDU1JGVG9rZW4gIT09ICdzdHJpbmcnIHx8XG4gICAgc3RhdGVDU1JGVG9rZW4udHJpbSgpLmxlbmd0aCA8IDEwXG4gICkge1xuICAgIC8vIEJhc2ljIHZhbGlkYXRpb24gZm9yIHN0YXRlIHRva2VuXG4gICAgY29uc3QgZXJyb3JNc2cgPVxuICAgICAgJ0EgdmFsaWQgc3RhdGUgQ1NSRiB0b2tlbiBtdXN0IGJlIHByb3ZpZGVkIGZvciBnZW5lcmF0aW5nIHRoZSBBdXRoIFVSSS4nO1xuICAgIGNvbnNvbGUuZXJyb3IoZXJyb3JNc2cpO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjogeyBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsIG1lc3NhZ2U6IGVycm9yTXNnIH0sXG4gICAgfTtcbiAgfVxuICB0cnkge1xuICAgIGNvbnN0IG9hdXRoQ2xpZW50ID0gZ2V0T0F1dGhDbGllbnQoKTtcbiAgICBjb25zdCBhdXRoVXJpID0gb2F1dGhDbGllbnQuZ2VuZXJhdGVBdXRoVXJpKHtcbiAgICAgIHNjb3BlOiBBVE9NX1FCX1NDT1BFUyxcbiAgICAgIHN0YXRlOiBzdGF0ZUNTUkZUb2tlbixcbiAgICB9KTtcbiAgICBpZiAoIWF1dGhVcmkpIHtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICBjb2RlOiAnUUJPX1VOS05PV05fRVJST1InLFxuICAgICAgICAgIG1lc3NhZ2U6ICdGYWlsZWQgdG8gZ2VuZXJhdGUgUUJPIEF1dGggVVJJIChVUkkgd2FzIG51bGwvZW1wdHkpLicsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH1cbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogYXV0aFVyaSB9O1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcignRXJyb3IgZ2VuZXJhdGluZyBRQk8gQXV0aCBVUkk6JywgZXJyb3IpO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnUUJPX0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IGBGYWlsZWQgdG8gaW5pdGlhbGl6ZSBPQXV0aCBjbGllbnQgb3IgZ2VuZXJhdGUgVVJJOiAke2Vycm9yLm1lc3NhZ2V9YCxcbiAgICAgICAgZGV0YWlsczogZXJyb3IsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn1cblxuaW50ZXJmYWNlIFVzZXJRQlRva2VuUmVjb3JkIHtcbiAgYWNjZXNzX3Rva2VuOiBzdHJpbmc7XG4gIHJlZnJlc2hfdG9rZW46IHN0cmluZztcbiAgZXhwaXJ5X2RhdGU6IHN0cmluZztcbiAgb3RoZXJfZGF0YToge1xuICAgIHJlYWxtSWQ6IHN0cmluZztcbiAgICByZWZyZXNoVG9rZW5FeHBpcmVzQXQ6IG51bWJlcjtcbiAgICB0b2tlbkNyZWF0ZWRBdDogbnVtYmVyO1xuICB9IHwgbnVsbDtcbn1cblxuYXN5bmMgZnVuY3Rpb24gZ2V0U3RvcmVkUUJUb2tlbnMoXG4gIHVzZXJJZDogc3RyaW5nXG4pOiBQcm9taXNlPFFCU2tpbGxSZXNwb25zZTxRdWlja0Jvb2tzQXV0aFRva2VucyB8IG51bGw+PiB7XG4gIGNvbnNvbGUubG9nKFxuICAgIGBSZXRyaWV2aW5nIFFCTyB0b2tlbnMgZm9yIHVzZXJJZDogJHt1c2VySWR9LCBzZXJ2aWNlOiAke1FCT19TRVJWSUNFX05BTUV9YFxuICApO1xuICBpZiAoIUhBU1VSQV9HUkFQSFFMX1VSTCB8fCAhSEFTVVJBX0FETUlOX1NFQ1JFVCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnQ09ORklHX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ0dyYXBoUUwgY2xpZW50IGlzIG5vdCBjb25maWd1cmVkIGZvciBRQk8gdG9rZW4gcmV0cmlldmFsLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgY29uc3QgcXVlcnkgPSBgXG4gICAgcXVlcnkgR2V0VXNlclFCT1Rva2VuKCR1c2VySWQ6IFN0cmluZyEsICRzZXJ2aWNlTmFtZTogU3RyaW5nISkge1xuICAgICAgdXNlcl90b2tlbnMoXG4gICAgICAgIHdoZXJlOiB7IHVzZXJfaWQ6IHsgX2VxOiAkdXNlcklkIH0sIHNlcnZpY2U6IHsgX2VxOiAkc2VydmljZU5hbWUgfSB9LFxuICAgICAgICBvcmRlcl9ieTogeyBjcmVhdGVkX2F0OiBkZXNjIH0sXG4gICAgICAgIGxpbWl0OiAxXG4gICAgICApIHsgYWNjZXNzX3Rva2VuLCByZWZyZXNoX3Rva2VuLCBleHBpcmVzX2F0LCBtZXRhIH1cbiAgICB9XG4gIGA7XG4gIGNvbnN0IHZhcmlhYmxlcyA9IHsgdXNlcklkLCBzZXJ2aWNlTmFtZTogUUJPX1NFUlZJQ0VfTkFNRSB9O1xuICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0dldFVzZXJRQk9Ub2tlbic7XG4gIHRyeSB7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBleGVjdXRlR3JhcGhRTFF1ZXJ5PHtcbiAgICAgIHVzZXJfdG9rZW5zOiB7XG4gICAgICAgIGFjY2Vzc190b2tlbjogc3RyaW5nO1xuICAgICAgICByZWZyZXNoX3Rva2VuOiBzdHJpbmc7XG4gICAgICAgIGV4cGlyZXNfYXQ6IHN0cmluZztcbiAgICAgICAgbWV0YTogYW55O1xuICAgICAgfVtdO1xuICAgIH0+KHF1ZXJ5LCB2YXJpYWJsZXMsIG9wZXJhdGlvbk5hbWUsIHVzZXJJZCk7XG4gICAgaWYgKFxuICAgICAgIXJlc3BvbnNlIHx8XG4gICAgICAhcmVzcG9uc2UudXNlcl90b2tlbnMgfHxcbiAgICAgIHJlc3BvbnNlLnVzZXJfdG9rZW5zLmxlbmd0aCA9PT0gMFxuICAgICkge1xuICAgICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IG51bGwgfTtcbiAgICB9XG4gICAgY29uc3QgZGJUb2tlbiA9IHJlc3BvbnNlLnVzZXJfdG9rZW5zWzBdO1xuICAgIGlmICghZGJUb2tlbi5tZXRhIHx8ICFkYlRva2VuLm1ldGEucmVhbG1JZCkge1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICBlcnJvcjoge1xuICAgICAgICAgIGNvZGU6ICdRQk9fVE9LRU5fSU5WQUxJRF9TVFJVQ1RVUkUnLFxuICAgICAgICAgIG1lc3NhZ2U6ICdTdG9yZWQgUUJPIHRva2VuIGlzIGludmFsaWQgKG1pc3NpbmcgcmVhbG1JZCkuJyxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgfVxuICAgIGNvbnN0IHRva2VuczogUXVpY2tCb29rc0F1dGhUb2tlbnMgPSB7XG4gICAgICBhY2Nlc3NUb2tlbjogZGJUb2tlbi5hY2Nlc3NfdG9rZW4sXG4gICAgICByZWZyZXNoVG9rZW46IGRiVG9rZW4ucmVmcmVzaF90b2tlbixcbiAgICAgIHJlYWxtSWQ6IGRiVG9rZW4ubWV0YS5yZWFsbUlkLFxuICAgICAgYWNjZXNzVG9rZW5FeHBpcmVzQXQ6IG5ldyBEYXRlKGRiVG9rZW4uZXhwaXJlc19hdCkuZ2V0VGltZSgpLFxuICAgICAgcmVmcmVzaFRva2VuRXhwaXJlc0F0OiBkYlRva2VuLm1ldGEucmVmcmVzaFRva2VuRXhwaXJlc0F0LFxuICAgICAgdG9rZW5DcmVhdGVkQXQ6IGRiVG9rZW4ubWV0YS50b2tlbkNyZWF0ZWRBdCxcbiAgICB9O1xuICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiB0b2tlbnMgfTtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICBgRXhjZXB0aW9uIGR1cmluZyBnZXRTdG9yZWRRQlRva2VucyBmb3IgdXNlcklkICR7dXNlcklkfTpgLFxuICAgICAgZXJyb3JcbiAgICApO1xuICAgIGNvbnN0IHNraWxsRXJyb3I6IFNraWxsRXJyb3IgPSB7XG4gICAgICBjb2RlOiAnVE9LRU5fRkVUQ0hfRkFJTEVEJyxcbiAgICAgIG1lc3NhZ2U6IGBGYWlsZWQgdG8gcmV0cmlldmUgUXVpY2tCb29rcyBPbmxpbmUgdG9rZW5zLmAsXG4gICAgICBkZXRhaWxzOiBlcnJvci5tZXNzYWdlLFxuICAgIH07XG4gICAgaWYgKGVycm9yLmNvZGUpIHtcbiAgICAgIHNraWxsRXJyb3IuZGV0YWlscyA9IGAke2Vycm9yLmNvZGV9OiAke2Vycm9yLm1lc3NhZ2V9YDtcbiAgICAgIGlmIChlcnJvci5jb2RlID09PSAnQ09ORklHX0VSUk9SJykgc2tpbGxFcnJvci5jb2RlID0gJ0NPTkZJR19FUlJPUic7XG4gICAgfVxuICAgIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHNraWxsRXJyb3IgfTtcbiAgfVxufVxuXG5hc3luYyBmdW5jdGlvbiBzYXZlUUJUb2tlbnMoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0b2tlbkRhdGFGcm9tT0F1dGg6IE9BdXRoQ2xpZW50LlRva2VuUmVzcG9uc2VEYXRhXG4pOiBQcm9taXNlPFFCU2tpbGxSZXNwb25zZTx2b2lkPj4ge1xuICBjb25zb2xlLmxvZyhgU2F2aW5nIFFCTyB0b2tlbnMgZm9yIHVzZXJJZDogJHt1c2VySWR9YCk7XG4gIGlmICghSEFTVVJBX0dSQVBIUUxfVVJMIHx8ICFIQVNVUkFfQURNSU5fU0VDUkVUKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdDT05GSUdfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnR3JhcGhRTCBjbGllbnQgaXMgbm90IGNvbmZpZ3VyZWQgZm9yIFFCTyB0b2tlbiBzYXZpbmcuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBjb25zdCB0b2tlbk9idGFpbmVkQXQgPSBEYXRlLm5vdygpO1xuICBjb25zdCBhY2Nlc3NUb2tlbkV4cGlyZXNBdCA9XG4gICAgdG9rZW5PYnRhaW5lZEF0ICsgdG9rZW5EYXRhRnJvbU9BdXRoLmV4cGlyZXNfaW4hICogMTAwMDtcbiAgY29uc3QgcmVmcmVzaFRva2VuRXhwaXJlc0F0ID1cbiAgICB0b2tlbk9idGFpbmVkQXQgKyB0b2tlbkRhdGFGcm9tT0F1dGgueF9yZWZyZXNoX3Rva2VuX2V4cGlyZXNfaW4hICogMTAwMDtcbiAgaWYgKCF0b2tlbkRhdGFGcm9tT0F1dGgucmVhbG1JZCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnUUJPX1RPS0VOX0lOVkFMSURfU1RSVUNUVVJFJyxcbiAgICAgICAgbWVzc2FnZTogJ3JlYWxtSWQgbWlzc2luZyBmcm9tIFFCTyBPQXV0aCByZXNwb25zZSwgY2Fubm90IHNhdmUgdG9rZW5zLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgY29uc3QgbWV0YSA9IHtcbiAgICByZWFsbUlkOiB0b2tlbkRhdGFGcm9tT0F1dGgucmVhbG1JZCxcbiAgICByZWZyZXNoVG9rZW5FeHBpcmVzQXQ6IHJlZnJlc2hUb2tlbkV4cGlyZXNBdCxcbiAgICB0b2tlbkNyZWF0ZWRBdDogdG9rZW5PYnRhaW5lZEF0LFxuICB9O1xuICBjb25zdCBtdXRhdGlvbiA9IGBcbiAgICBtdXRhdGlvbiBVcHNlcnRVc2VyUUJPVG9rZW4oJG9iamVjdHM6IFt1c2VyX3Rva2Vuc19pbnNlcnRfaW5wdXQhXSEpIHtcbiAgICAgIGluc2VydF91c2VyX3Rva2VucyhvYmplY3RzOiAkb2JqZWN0cywgb25fY29uZmxpY3Q6IHtcbiAgICAgICAgICBjb25zdHJhaW50OiB1c2VyX3Rva2Vuc191c2VyX2lkX3NlcnZpY2Vfa2V5LFxuICAgICAgICAgIHVwZGF0ZV9jb2x1bW5zOiBbYWNjZXNzX3Rva2VuLCByZWZyZXNoX3Rva2VuLCBleHBpcmVzX2F0LCBtZXRhLCB1cGRhdGVkX2F0XVxuICAgICAgICB9KSB7IGFmZmVjdGVkX3Jvd3MgfVxuICAgIH1cbiAgYDtcbiAgY29uc3QgdG9rZW5JbnB1dEZvckRiID0ge1xuICAgIHVzZXJfaWQ6IHVzZXJJZCxcbiAgICBzZXJ2aWNlOiBRQk9fU0VSVklDRV9OQU1FLFxuICAgIGFjY2Vzc190b2tlbjogdG9rZW5EYXRhRnJvbU9BdXRoLmFjY2Vzc190b2tlbiEsXG4gICAgcmVmcmVzaF90b2tlbjogdG9rZW5EYXRhRnJvbU9BdXRoLnJlZnJlc2hfdG9rZW4hLFxuICAgIGV4cGlyZXNfYXQ6IG5ldyBEYXRlKGFjY2Vzc1Rva2VuRXhwaXJlc0F0KS50b0lTT1N0cmluZygpLFxuICAgIG1ldGE6IG1ldGEsXG4gICAgdXBkYXRlZF9hdDogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxuICB9O1xuICBjb25zdCB2YXJpYWJsZXMgPSB7IG9iamVjdHM6IFt0b2tlbklucHV0Rm9yRGJdIH07XG4gIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnVXBzZXJ0VXNlclFCT1Rva2VuJztcbiAgdHJ5IHtcbiAgICBhd2FpdCBleGVjdXRlR3JhcGhRTE11dGF0aW9uPHtcbiAgICAgIGluc2VydF91c2VyX3Rva2VuczogeyBhZmZlY3RlZF9yb3dzOiBudW1iZXIgfTtcbiAgICB9PihtdXRhdGlvbiwgdmFyaWFibGVzLCBvcGVyYXRpb25OYW1lLCB1c2VySWQpO1xuICAgIGNvbnNvbGUubG9nKGBRQk8gdG9rZW5zIHNhdmVkL3VwZGF0ZWQgc3VjY2Vzc2Z1bGx5IGZvciB1c2VyICR7dXNlcklkfS5gKTtcbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogdW5kZWZpbmVkIH07XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKGBFeGNlcHRpb24gc2F2aW5nIFFCTyB0b2tlbnMgZm9yIHVzZXIgJHt1c2VySWR9OmAsIGVycm9yKTtcbiAgICBjb25zdCBza2lsbEVycm9yOiBTa2lsbEVycm9yID0ge1xuICAgICAgY29kZTogJ1RPS0VOX1NBVkVfRkFJTEVEJyxcbiAgICAgIG1lc3NhZ2U6IGBGYWlsZWQgdG8gc2F2ZSBRdWlja0Jvb2tzIE9ubGluZSB0b2tlbnMuYCxcbiAgICAgIGRldGFpbHM6IGVycm9yLm1lc3NhZ2UsXG4gICAgfTtcbiAgICBpZiAoZXJyb3IuY29kZSkge1xuICAgICAgc2tpbGxFcnJvci5kZXRhaWxzID0gYCR7ZXJyb3IuY29kZX06ICR7ZXJyb3IubWVzc2FnZX1gO1xuICAgICAgaWYgKGVycm9yLmNvZGUgPT09ICdDT05GSUdfRVJST1InKSBza2lsbEVycm9yLmNvZGUgPSAnQ09ORklHX0VSUk9SJztcbiAgICB9XG4gICAgcmV0dXJuIHsgb2s6IGZhbHNlLCBlcnJvcjogc2tpbGxFcnJvciB9O1xuICB9XG59XG5cbmFzeW5jIGZ1bmN0aW9uIGdldFZhbGlkVG9rZW5zKFxuICB1c2VySWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxRQlNraWxsUmVzcG9uc2U8UXVpY2tCb29rc0F1dGhUb2tlbnM+PiB7XG4gIGNvbnN0IGxvYWRSZXNwb25zZSA9IGF3YWl0IGdldFN0b3JlZFFCVG9rZW5zKHVzZXJJZCk7XG4gIGlmICghbG9hZFJlc3BvbnNlLm9rKSByZXR1cm4geyBvazogZmFsc2UsIGVycm9yOiBsb2FkUmVzcG9uc2UuZXJyb3IhIH07XG4gIGxldCBjdXJyZW50VG9rZW5zID0gbG9hZFJlc3BvbnNlLmRhdGE7XG4gIGlmICghY3VycmVudFRva2Vucykge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnUUJPX0FVVEhfUkVRVUlSRUQnLFxuICAgICAgICBtZXNzYWdlOiAnTm8gUXVpY2tCb29rcyB0b2tlbnMgZm91bmQuIFBsZWFzZSBhdXRob3JpemUuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBjb25zdCBub3cgPSBEYXRlLm5vdygpO1xuICBpZiAobm93ID49IGN1cnJlbnRUb2tlbnMuYWNjZXNzVG9rZW5FeHBpcmVzQXQgLSA1ICogNjAgKiAxMDAwKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBgUUJPIGFjY2VzcyB0b2tlbiBmb3IgdXNlciAke3VzZXJJZH0gZXhwaXJlZC9uZWFyaW5nIGV4cGlyeS4gUmVmcmVzaGluZy4uLmBcbiAgICApO1xuICAgIGlmIChcbiAgICAgICFjdXJyZW50VG9rZW5zLnJlZnJlc2hUb2tlbiB8fFxuICAgICAgbm93ID49IGN1cnJlbnRUb2tlbnMucmVmcmVzaFRva2VuRXhwaXJlc0F0XG4gICAgKSB7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgY29kZTogJ1FCT19SRUZSRVNIX1RPS0VOX0VYUElSRUQnLFxuICAgICAgICAgIG1lc3NhZ2U6ICdSZWZyZXNoIHRva2VuIG1pc3Npbmcgb3IgZXhwaXJlZC4gUGxlYXNlIHJlLWF1dGhvcml6ZS4nLFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICB9XG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IGF1dGhDbGllbnQgPSBnZXRPQXV0aENsaWVudCgpO1xuICAgICAgY29uc3QgcmVmcmVzaGVkVG9rZW5SZXNwb25zZSA9IGF3YWl0IGF1dGhDbGllbnQucmVmcmVzaFVzaW5nVG9rZW4oXG4gICAgICAgIGN1cnJlbnRUb2tlbnMucmVmcmVzaFRva2VuXG4gICAgICApO1xuICAgICAgaWYgKFxuICAgICAgICAhcmVmcmVzaGVkVG9rZW5SZXNwb25zZSB8fFxuICAgICAgICAhcmVmcmVzaGVkVG9rZW5SZXNwb25zZS5nZXRKc29uKCk/LmFjY2Vzc190b2tlblxuICAgICAgKSB7XG4gICAgICAgIHJldHVybiB7XG4gICAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgICBjb2RlOiAnUUJPX1JFRlJFU0hfRkFJTEVEJyxcbiAgICAgICAgICAgIG1lc3NhZ2U6ICdJbnZhbGlkIHJlc3BvbnNlIGZyb20gT0F1dGggc2VydmVyIGR1cmluZyByZWZyZXNoLicsXG4gICAgICAgICAgICBkZXRhaWxzOiByZWZyZXNoZWRUb2tlblJlc3BvbnNlPy5nZXRKc29uKCksXG4gICAgICAgICAgfSxcbiAgICAgICAgfTtcbiAgICAgIH1cbiAgICAgIGNvbnN0IG5ld1Rva2Vuc0Zyb21PQXV0aCA9IHJlZnJlc2hlZFRva2VuUmVzcG9uc2UuZ2V0SnNvbigpO1xuICAgICAgY29uc3Qgc2F2ZU9wID0gYXdhaXQgc2F2ZVFCVG9rZW5zKHVzZXJJZCwgbmV3VG9rZW5zRnJvbU9BdXRoKTtcbiAgICAgIGlmICghc2F2ZU9wLm9rKSByZXR1cm4geyBvazogZmFsc2UsIGVycm9yOiBzYXZlT3AuZXJyb3IhIH07XG4gICAgICBjb25zb2xlLmxvZyhgUUJPIHRva2VucyByZWZyZXNoZWQgYW5kIHNhdmVkIGZvciB1c2VyICR7dXNlcklkfS5gKTtcbiAgICAgIGNvbnN0IHJlbG9hZGVkVG9rZW5zUmVzcG9uc2UgPSBhd2FpdCBnZXRTdG9yZWRRQlRva2Vucyh1c2VySWQpO1xuICAgICAgaWYgKCFyZWxvYWRlZFRva2Vuc1Jlc3BvbnNlLm9rIHx8ICFyZWxvYWRlZFRva2Vuc1Jlc3BvbnNlLmRhdGEpIHtcbiAgICAgICAgcmV0dXJuIHtcbiAgICAgICAgICBvazogZmFsc2UsXG4gICAgICAgICAgZXJyb3I6IHJlbG9hZGVkVG9rZW5zUmVzcG9uc2UuZXJyb3IgfHwge1xuICAgICAgICAgICAgY29kZTogJ1FCT19UT0tFTl9SRUxPQURfRkFJTEVEJyxcbiAgICAgICAgICAgIG1lc3NhZ2U6ICdGYWlsZWQgdG8gcmVsb2FkIHRva2VucyBhZnRlciByZWZyZXNoLicsXG4gICAgICAgICAgfSxcbiAgICAgICAgfTtcbiAgICAgIH1cbiAgICAgIGN1cnJlbnRUb2tlbnMgPSByZWxvYWRlZFRva2Vuc1Jlc3BvbnNlLmRhdGE7XG4gICAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgICBjb25zdCBlcnJvckRldGFpbHMgPVxuICAgICAgICBlLm9yaWdpbmFsRXJyb3I/LmVycm9yX2Rlc2NyaXB0aW9uIHx8XG4gICAgICAgIGUubWVzc2FnZSB8fFxuICAgICAgICAnVW5rbm93biByZWZyZXNoIGVycm9yJztcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICBjb2RlOiAnUUJPX1JFRlJFU0hfRkFJTEVEJyxcbiAgICAgICAgICBtZXNzYWdlOiBgVG9rZW4gcmVmcmVzaCBBUEkgY2FsbCBmYWlsZWQ6ICR7ZXJyb3JEZXRhaWxzfWAsXG4gICAgICAgICAgZGV0YWlsczogZSxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgfVxuICB9XG4gIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiBjdXJyZW50VG9rZW5zIH07XG59XG5cbmFzeW5jIGZ1bmN0aW9uIGdldFFib0NsaWVudChcbiAgdXNlcklkOiBzdHJpbmdcbik6IFByb21pc2U8UUJTa2lsbFJlc3BvbnNlPFF1aWNrQm9va3M+PiB7XG4gIGNvbnN0IHRva2VuUmVzcG9uc2UgPSBhd2FpdCBnZXRWYWxpZFRva2Vucyh1c2VySWQpO1xuICBpZiAoIXRva2VuUmVzcG9uc2Uub2sgfHwgIXRva2VuUmVzcG9uc2UuZGF0YSlcbiAgICByZXR1cm4geyBvazogZmFsc2UsIGVycm9yOiB0b2tlblJlc3BvbnNlLmVycm9yISB9O1xuICBjb25zdCB0b2tlbnMgPSB0b2tlblJlc3BvbnNlLmRhdGE7XG4gIGlmICghQVRPTV9RQl9DTElFTlRfSUQgfHwgIUFUT01fUUJfQ0xJRU5UX1NFQ1JFVCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnUUJPX0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdDbGllbnQgSUQgb3IgU2VjcmV0IG5vdCBjb25maWd1cmVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgdHJ5IHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IHRydWUsXG4gICAgICBkYXRhOiBuZXcgUXVpY2tCb29rcyhcbiAgICAgICAgQVRPTV9RQl9DTElFTlRfSUQsXG4gICAgICAgIEFUT01fUUJfQ0xJRU5UX1NFQ1JFVCxcbiAgICAgICAgdG9rZW5zLmFjY2Vzc1Rva2VuLFxuICAgICAgICBmYWxzZSxcbiAgICAgICAgdG9rZW5zLnJlYWxtSWQsXG4gICAgICAgIEFUT01fUUJfRU5WSVJPTk1FTlQgPT09ICdzYW5kYm94JyxcbiAgICAgICAgZmFsc2UsXG4gICAgICAgIG51bGwsXG4gICAgICAgICcyLjAnLFxuICAgICAgICB0b2tlbnMucmVmcmVzaFRva2VuXG4gICAgICApLFxuICAgIH07XG4gIH0gY2F0Y2ggKGluaXRFcnJvcjogYW55KSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdRQk9fQ0xJRU5UX0lOSVRfRkFJTEVEJyxcbiAgICAgICAgbWVzc2FnZTogYEVycm9yIGluaXRpYWxpemluZyBRdWlja0Jvb2tzIFNESzogJHtpbml0RXJyb3IubWVzc2FnZX1gLFxuICAgICAgICBkZXRhaWxzOiBpbml0RXJyb3IsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn1cblxuZnVuY3Rpb24gbWFwUUJJbnZvaWNlVG9JbnRlcm5hbChxYkludm9pY2U6IGFueSk6IFF1aWNrQm9va3NJbnZvaWNlIHtcbiAgLyogLi4uIGFzIGJlZm9yZSAuLi4gKi9cbiAgcmV0dXJuIHtcbiAgICBJZDogcWJJbnZvaWNlLklkLFxuICAgIERvY051bWJlcjogcWJJbnZvaWNlLkRvY051bWJlcixcbiAgICBUeG5EYXRlOiBxYkludm9pY2UuVHhuRGF0ZSxcbiAgICBEdWVEYXRlOiBxYkludm9pY2UuRHVlRGF0ZSxcbiAgICBDdXN0b21lclJlZjogcWJJbnZvaWNlLkN1c3RvbWVyUmVmXG4gICAgICA/IHsgdmFsdWU6IHFiSW52b2ljZS5DdXN0b21lclJlZi52YWx1ZSwgbmFtZTogcWJJbnZvaWNlLkN1c3RvbWVyUmVmLm5hbWUgfVxuICAgICAgOiB1bmRlZmluZWQsXG4gICAgQmlsbEVtYWlsOiBxYkludm9pY2UuQmlsbEVtYWlsXG4gICAgICA/IHsgQWRkcmVzczogcWJJbnZvaWNlLkJpbGxFbWFpbC5BZGRyZXNzIH1cbiAgICAgIDogdW5kZWZpbmVkLFxuICAgIFRvdGFsQW10OiBxYkludm9pY2UuVG90YWxBbXQsXG4gICAgQmFsYW5jZTogcWJJbnZvaWNlLkJhbGFuY2UsXG4gICAgQ3VycmVuY3lSZWY6IHFiSW52b2ljZS5DdXJyZW5jeVJlZlxuICAgICAgPyB7IHZhbHVlOiBxYkludm9pY2UuQ3VycmVuY3lSZWYudmFsdWUsIG5hbWU6IHFiSW52b2ljZS5DdXJyZW5jeVJlZi5uYW1lIH1cbiAgICAgIDogdW5kZWZpbmVkLFxuICAgIExpbmU6IHFiSW52b2ljZS5MaW5lLFxuICAgIFByaXZhdGVOb3RlOiBxYkludm9pY2UuUHJpdmF0ZU5vdGUsXG4gICAgQ3VzdG9tZXJNZW1vOiBxYkludm9pY2UuQ3VzdG9tZXJNZW1vLFxuICAgIEVtYWlsU3RhdHVzOiBxYkludm9pY2UuRW1haWxTdGF0dXMsXG4gIH07XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBsaXN0UXVpY2tCb29rc0ludm9pY2VzKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgb3B0aW9ucz86IHtcbiAgICBsaW1pdD86IG51bWJlcjtcbiAgICBvZmZzZXQ/OiBudW1iZXI7XG4gICAgY3VzdG9tZXJJZD86IHN0cmluZztcbiAgICBzdGF0dXM/OiBzdHJpbmc7XG4gIH1cbik6IFByb21pc2U8UUJTa2lsbFJlc3BvbnNlPExpc3RRQkludm9pY2VzRGF0YT4+IHtcbiAgY29uc3QgcWJvQ2xpZW50UmVzcG9uc2UgPSBhd2FpdCBnZXRRYm9DbGllbnQodXNlcklkKTtcbiAgaWYgKCFxYm9DbGllbnRSZXNwb25zZS5vayB8fCAhcWJvQ2xpZW50UmVzcG9uc2UuZGF0YSkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjogcWJvQ2xpZW50UmVzcG9uc2UuZXJyb3IgfHwge1xuICAgICAgICBjb2RlOiAnUUJPX0lOSVRfRkFJTEVEJyxcbiAgICAgICAgbWVzc2FnZTogJ1FCTyBjbGllbnQgaW5pdCBmYWlsZWQgZm9yIGxpc3RpbmcgaW52b2ljZXMuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBjb25zdCBxYm8gPSBxYm9DbGllbnRSZXNwb25zZS5kYXRhO1xuICBjb25zdCBsaW1pdCA9IG9wdGlvbnM/LmxpbWl0IHx8IDEwO1xuICBjb25zdCBvZmZzZXQgPSBvcHRpb25zPy5vZmZzZXQgfHwgMTtcbiAgbGV0IHF1ZXJ5ID0gJ1NFTEVDVCAqIEZST00gSW52b2ljZSc7XG4gIGNvbnN0IGNvbmRpdGlvbnM6IHN0cmluZ1tdID0gW107XG4gIGlmIChvcHRpb25zPy5jdXN0b21lcklkKVxuICAgIGNvbmRpdGlvbnMucHVzaChgQ3VzdG9tZXJSZWYgPSAnJHtvcHRpb25zLmN1c3RvbWVySWR9J2ApO1xuICBpZiAob3B0aW9ucz8uc3RhdHVzKSB7XG4gICAgc3dpdGNoIChvcHRpb25zLnN0YXR1cykge1xuICAgICAgY2FzZSAnUGFpZCc6XG4gICAgICAgIGNvbmRpdGlvbnMucHVzaCgnQmFsYW5jZSA9IDAgQU5EIFRvdGFsQW10ID4gMCcpO1xuICAgICAgICBicmVhaztcbiAgICAgIGNhc2UgJ09wZW4nOlxuICAgICAgICBjb25kaXRpb25zLnB1c2goJ0JhbGFuY2UgPiAwJyk7XG4gICAgICAgIGJyZWFrO1xuICAgICAgY2FzZSAnVm9pZCc6XG4gICAgICAgIGNvbmRpdGlvbnMucHVzaChcIkVtYWlsU3RhdHVzID0gJ1ZvaWQnXCIpO1xuICAgICAgICBicmVhaztcbiAgICAgIGNhc2UgJ092ZXJkdWUnOlxuICAgICAgICBjb25kaXRpb25zLnB1c2goXG4gICAgICAgICAgYER1ZURhdGUgPCAnJHtuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCkuc3BsaXQoJ1QnKVswXX0nIEFORCBCYWxhbmNlID4gMGBcbiAgICAgICAgKTtcbiAgICAgICAgYnJlYWs7XG4gICAgICBjYXNlICdQZW5kaW5nJzpcbiAgICAgICAgY29uZGl0aW9ucy5wdXNoKFwiRW1haWxTdGF0dXMgPSAnUGVuZGluZydcIik7XG4gICAgICAgIGJyZWFrO1xuICAgICAgY2FzZSAnRHJhZnQnOlxuICAgICAgICBjb25kaXRpb25zLnB1c2goXCJFbWFpbFN0YXR1cyA9ICdEcmFmdCdcIik7XG4gICAgICAgIGJyZWFrO1xuICAgICAgZGVmYXVsdDpcbiAgICAgICAgY29uc29sZS53YXJuKGBVbnN1cHBvcnRlZCBzdGF0dXMgZmlsdGVyICcke29wdGlvbnMuc3RhdHVzfScgaWdub3JlZC5gKTtcbiAgICAgICAgYnJlYWs7XG4gICAgfVxuICB9XG4gIGlmIChjb25kaXRpb25zLmxlbmd0aCA+IDApIHF1ZXJ5ICs9ICcgV0hFUkUgJyArIGNvbmRpdGlvbnMuam9pbignIEFORCAnKTtcbiAgcXVlcnkgKz0gYCBPUkRFUkJZIE1ldGFEYXRhLkxhc3RVcGRhdGVkVGltZSBERVNDIFNUQVJUUE9TSVRJT04gJHtvZmZzZXR9IE1BWFJFU1VMVFMgJHtsaW1pdH1gO1xuICBjb25zb2xlLmxvZyhgUUJPIFF1ZXJ5IChVc2VyICR7dXNlcklkfSk6ICR7cXVlcnl9YCk7XG4gIHJldHVybiBuZXcgUHJvbWlzZSgocmVzb2x2ZSkgPT4ge1xuICAgIHFiby5xdWVyeUludm9pY2VzKHsgcXVlcnkgfSwgKGVycjogYW55LCBxdWVyeVJlc3BvbnNlOiBhbnkpID0+IHtcbiAgICAgIGlmIChlcnIpIHtcbiAgICAgICAgY29uc3QgZmF1bHQgPSBlcnIuRmF1bHQgfHwgZXJyLmZhdWx0O1xuICAgICAgICBjb25zdCBlcnJvckRldGFpbHNBcnJheSA9IGZhdWx0Py5FcnJvciB8fCBbXG4gICAgICAgICAgeyBNZXNzYWdlOiAnVW5rbm93biBRQk8gQVBJIGVycm9yJywgY29kZTogJ1VOS05PV04nIH0sXG4gICAgICAgIF07XG4gICAgICAgIGNvbnN0IGZpcnN0RXJyb3IgPSBlcnJvckRldGFpbHNBcnJheVswXTtcbiAgICAgICAgY29uc3QgZXJyb3JDb2RlID0gZmlyc3RFcnJvci5jb2RlIHx8ICdRQk9fUVVFUllfRVJST1InO1xuICAgICAgICByZXNvbHZlKHtcbiAgICAgICAgICBvazogZmFsc2UsXG4gICAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICAgIGNvZGU6IGBRQk9fQVBJX0VSUk9SXyR7ZXJyb3JDb2RlfWAsXG4gICAgICAgICAgICBtZXNzYWdlOiBmaXJzdEVycm9yLk1lc3NhZ2UgfHwgJ0ZhaWxlZCB0byBsaXN0IFFCTyBpbnZvaWNlcy4nLFxuICAgICAgICAgICAgZGV0YWlsczogZmF1bHQgfHwgZXJyLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0pO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgcmVzb2x2ZSh7XG4gICAgICAgICAgb2s6IHRydWUsXG4gICAgICAgICAgZGF0YToge1xuICAgICAgICAgICAgaW52b2ljZXM6IHF1ZXJ5UmVzcG9uc2U/Lkludm9pY2U/Lm1hcChtYXBRQkludm9pY2VUb0ludGVybmFsKSB8fCBbXSxcbiAgICAgICAgICAgIHF1ZXJ5UmVzcG9uc2U6IHF1ZXJ5UmVzcG9uc2UsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSk7XG4gICAgICB9XG4gICAgfSk7XG4gIH0pO1xufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0UXVpY2tCb29rc0ludm9pY2VEZXRhaWxzKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgaW52b2ljZUlkOiBzdHJpbmdcbik6IFByb21pc2U8UUJTa2lsbFJlc3BvbnNlPFF1aWNrQm9va3NJbnZvaWNlIHwgbnVsbD4+IHtcbiAgY29uc3QgcWJvQ2xpZW50UmVzcG9uc2UgPSBhd2FpdCBnZXRRYm9DbGllbnQodXNlcklkKTtcbiAgaWYgKCFxYm9DbGllbnRSZXNwb25zZS5vayB8fCAhcWJvQ2xpZW50UmVzcG9uc2UuZGF0YSkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjogcWJvQ2xpZW50UmVzcG9uc2UuZXJyb3IgfHwge1xuICAgICAgICBjb2RlOiAnUUJPX0lOSVRfRkFJTEVEJyxcbiAgICAgICAgbWVzc2FnZTogJ1FCTyBjbGllbnQgaW5pdCBmYWlsZWQgZm9yIGludm9pY2UgZGV0YWlscy4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG4gIGNvbnN0IHFibyA9IHFib0NsaWVudFJlc3BvbnNlLmRhdGE7XG4gIGlmICghaW52b2ljZUlkIHx8IGludm9pY2VJZC50cmltKCkgPT09ICcnKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7IGNvZGU6ICdWQUxJREFUSU9OX0VSUk9SJywgbWVzc2FnZTogJ0ludm9pY2UgSUQgaXMgcmVxdWlyZWQuJyB9LFxuICAgIH07XG4gIH1cbiAgcmV0dXJuIG5ldyBQcm9taXNlKChyZXNvbHZlKSA9PiB7XG4gICAgcWJvLmdldEludm9pY2UoaW52b2ljZUlkLCAoZXJyOiBhbnksIGludm9pY2U6IGFueSkgPT4ge1xuICAgICAgaWYgKGVycikge1xuICAgICAgICBjb25zdCBmYXVsdCA9IGVyci5GYXVsdCB8fCBlcnIuZmF1bHQ7XG4gICAgICAgIGNvbnN0IGVycm9yRGV0YWlsc0FycmF5ID0gZmF1bHQ/LkVycm9yIHx8IFtcbiAgICAgICAgICB7IE1lc3NhZ2U6ICdVbmtub3duIFFCTyBBUEkgZXJyb3InLCBjb2RlOiAnVU5LTk9XTicgfSxcbiAgICAgICAgXTtcbiAgICAgICAgY29uc3QgZmlyc3RFcnJvciA9IGVycm9yRGV0YWlsc0FycmF5WzBdO1xuICAgICAgICBpZiAoXG4gICAgICAgICAgZmlyc3RFcnJvci5jb2RlID09PSAnNjI0MCcgfHxcbiAgICAgICAgICBmaXJzdEVycm9yLk1lc3NhZ2U/LnRvTG93ZXJDYXNlKCkuaW5jbHVkZXMoJ29iamVjdCBub3QgZm91bmQnKVxuICAgICAgICApIHtcbiAgICAgICAgICByZXNvbHZlKHsgb2s6IHRydWUsIGRhdGE6IG51bGwgfSk7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgY29uc3QgZXJyb3JDb2RlID0gZmlyc3RFcnJvci5jb2RlIHx8ICdRQk9fR0VUX0VSUk9SJztcbiAgICAgICAgICByZXNvbHZlKHtcbiAgICAgICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgICAgIGNvZGU6IGBRQk9fQVBJX0VSUk9SXyR7ZXJyb3JDb2RlfWAsXG4gICAgICAgICAgICAgIG1lc3NhZ2U6IGZpcnN0RXJyb3IuTWVzc2FnZSB8fCAnRmFpbGVkIHRvIGdldCBRQk8gaW52b2ljZS4nLFxuICAgICAgICAgICAgICBkZXRhaWxzOiBmYXVsdCB8fCBlcnIsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIH0pO1xuICAgICAgICB9XG4gICAgICB9IGVsc2Uge1xuICAgICAgICByZXNvbHZlKHtcbiAgICAgICAgICBvazogdHJ1ZSxcbiAgICAgICAgICBkYXRhOiBpbnZvaWNlID8gbWFwUUJJbnZvaWNlVG9JbnRlcm5hbChpbnZvaWNlKSA6IG51bGwsXG4gICAgICAgIH0pO1xuICAgICAgfVxuICAgIH0pO1xuICB9KTtcbn1cblxuLyoqXG4gKiBIYW5kbGVzIHRoZSBPQXV0aCBjYWxsYmFjayBmcm9tIFF1aWNrQm9va3MgT25saW5lLlxuICogRXhjaGFuZ2VzIHRoZSBhdXRob3JpemF0aW9uIGNvZGUgZm9yIHRva2VucywgdmFsaWRhdGVzIHN0YXRlIGZvciBDU1JGIHByb3RlY3Rpb24sIGFuZCBzYXZlcyB0aGUgdG9rZW5zLlxuICpcbiAqIEBwYXJhbSB1c2VySWQgVGhlIElEIG9mIHRoZSB1c2VyIGZvciB3aG9tIHRoZSB0b2tlbnMgYXJlIGJlaW5nIGF1dGhvcml6ZWQuXG4gKiBAcGFyYW0gdXJsV2l0aENvZGUgVGhlIGZ1bGwgY2FsbGJhY2sgVVJMIHN0cmluZyBmcm9tIFF1aWNrQm9va3MgKGUuZy4sIHJlcS5vcmlnaW5hbFVybCBvciByZXEudXJsKS5cbiAqIEBwYXJhbSBvcmlnaW5hbFN0YXRlIE9wdGlvbmFsLiBUaGUgJ3N0YXRlJyB2YWx1ZSB0aGF0IHdhcyBpbml0aWFsbHkgc2VudCB0byBRQk8ncyBhdXRoIFVSSS5cbiAqICAgICAgICAgICAgICAgICAgICAgIEl0IHNob3VsZCBiZSByZXRyaWV2ZWQgZnJvbSB0aGUgdXNlcidzIHNlc3Npb24gb3IgYSBzZWN1cmUgdGVtcG9yYXJ5IHN0b3JlLlxuICogICAgICAgICAgICAgICAgICAgICAgSWYgbm90IHByb3ZpZGVkLCBDU1JGIHByb3RlY3Rpb24gaXMgd2Vha2VuZWQgKGEgd2FybmluZyB3aWxsIGJlIGxvZ2dlZCkuXG4gKiBAcmV0dXJucyBBIHByb21pc2UgdGhhdCByZXNvbHZlcyB0byBhIFFCU2tpbGxSZXNwb25zZSBpbmRpY2F0aW5nIHN1Y2Nlc3Mgb3IgZmFpbHVyZS5cbiAqICAgICAgICAgIE9uIHN1Y2Nlc3MsIGRhdGEgY29udGFpbnMgYSBtZXNzYWdlIGFuZCB0aGUgcmVhbG1JZC5cbiAqL1xuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZVF1aWNrQm9va3NDYWxsYmFjayhcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHVybFdpdGhDb2RlOiBzdHJpbmcsXG4gIG9yaWdpbmFsU3RhdGU/OiBzdHJpbmdcbik6IFByb21pc2U8UUJTa2lsbFJlc3BvbnNlPHsgbWVzc2FnZTogc3RyaW5nOyByZWFsbUlkOiBzdHJpbmcgfT4+IHtcbiAgLy8gMS4gUGVyZm9ybSBHcmFwaFFMIGNvbmZpZ3VyYXRpb24gY2hlY2tzIChmb3Igc2F2ZVFCVG9rZW5zKVxuICBpZiAoIUhBU1VSQV9HUkFQSFFMX1VSTCB8fCAhSEFTVVJBX0FETUlOX1NFQ1JFVCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnQ09ORklHX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTpcbiAgICAgICAgICAnR3JhcGhRTCBjbGllbnQgaXMgbm90IGNvbmZpZ3VyZWQgZm9yIFFCTyB0b2tlbiBzYXZpbmcgZHVyaW5nIGNhbGxiYWNrLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cblxuICAvLyAyLiBJbml0aWFsaXplIE9BdXRoQ2xpZW50XG4gIGxldCBvYXV0aENsaWVudDogT0F1dGhDbGllbnQ7XG4gIHRyeSB7XG4gICAgb2F1dGhDbGllbnQgPSBnZXRPQXV0aENsaWVudCgpO1xuICB9IGNhdGNoIChjb25maWdFcnJvcjogYW55KSB7XG4gICAgLy8gVGhpcyBlcnJvciAoZS5nLiwgbWlzc2luZyBjbGllbnQgSUQvc2VjcmV0KSBpcyBjcml0aWNhbCBhbmQgZnJvbSBhcHAgY29uZmlnLlxuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnUUJPX0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IGBPQXV0aCBjbGllbnQgaW5pdGlhbGl6YXRpb24gZmFpbGVkOiAke2NvbmZpZ0Vycm9yLm1lc3NhZ2V9YCxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIC8vIDMuIENTUkYgUHJvdGVjdGlvblxuICB0cnkge1xuICAgIGNvbnN0IGNhbGxiYWNrUGFyYW1zID0gbmV3IFVSTFNlYXJjaFBhcmFtcyhcbiAgICAgIHVybFdpdGhDb2RlLnN1YnN0cmluZyh1cmxXaXRoQ29kZS5pbmRleE9mKCc/JykpXG4gICAgKTtcbiAgICBjb25zdCByZWNlaXZlZFN0YXRlID0gY2FsbGJhY2tQYXJhbXMuZ2V0KCdzdGF0ZScpO1xuXG4gICAgaWYgKG9yaWdpbmFsU3RhdGUpIHtcbiAgICAgIGlmICghcmVjZWl2ZWRTdGF0ZSB8fCByZWNlaXZlZFN0YXRlICE9PSBvcmlnaW5hbFN0YXRlKSB7XG4gICAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgICAgYFFCTyBPQXV0aCBjYWxsYmFjayBzdGF0ZSBtaXNtYXRjaCBmb3IgdXNlciAke3VzZXJJZH0uIEV4cGVjdGVkOiAnJHtvcmlnaW5hbFN0YXRlfScsIFJlY2VpdmVkOiAnJHtyZWNlaXZlZFN0YXRlfSdgXG4gICAgICAgICk7XG4gICAgICAgIHJldHVybiB7XG4gICAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgICBjb2RlOiAnSU5WQUxJRF9PQVVUSF9TVEFURScsXG4gICAgICAgICAgICBtZXNzYWdlOiAnT0F1dGggc3RhdGUgbWlzbWF0Y2guIFBvc3NpYmxlIENTUkYgYXR0YWNrLicsXG4gICAgICAgICAgfSxcbiAgICAgICAgfTtcbiAgICAgIH1cbiAgICB9IGVsc2Uge1xuICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICBgUUJPIE9BdXRoIGNhbGxiYWNrIGZvciB1c2VyICR7dXNlcklkfTogb3JpZ2luYWxTdGF0ZSBub3QgcHJvdmlkZWQuIENTUkYgcHJvdGVjdGlvbiBpcyB3ZWFrZW5lZC4gUmVjZWl2ZWQgc3RhdGU6ICcke3JlY2VpdmVkU3RhdGV9J2BcbiAgICAgICk7XG4gICAgICAvLyBEZXBlbmRpbmcgb24gc2VjdXJpdHkgcG9saWN5LCB5b3UgbWlnaHQgY2hvb3NlIHRvIGZhaWwgaGVyZSBpZiBvcmlnaW5hbFN0YXRlIGlzIG1hbmRhdG9yeS5cbiAgICB9XG4gIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICBgRXJyb3IgcGFyc2luZyBzdGF0ZSBmcm9tIFFCTyBjYWxsYmFjayBVUkwgZm9yIHVzZXIgJHt1c2VySWR9OiAke3VybFdpdGhDb2RlfWAsXG4gICAgICBlXG4gICAgKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ1VSTF9QQVJTSU5HX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ0ZhaWxlZCB0byBwYXJzZSBjYWxsYmFjayBVUkwgcGFyYW1ldGVycy4nLFxuICAgICAgICBkZXRhaWxzOiBlLm1lc3NhZ2UsXG4gICAgICB9LFxuICAgIH07XG4gIH1cblxuICAvLyA0LiBUb2tlbiBFeGNoYW5nZVxuICBsZXQgdG9rZW5EYXRhRnJvbU9BdXRoOiBPQXV0aENsaWVudC5Ub2tlblJlc3BvbnNlRGF0YTtcbiAgdHJ5IHtcbiAgICBjb25zdCBhdXRoUmVzcG9uc2UgPSBhd2FpdCBvYXV0aENsaWVudC5jcmVhdGVUb2tlbih1cmxXaXRoQ29kZSk7XG4gICAgaWYgKCFhdXRoUmVzcG9uc2UgfHwgIWF1dGhSZXNwb25zZS5nZXRKc29uKCk/LmFjY2Vzc190b2tlbikge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgJ1FCTyBPQXV0aCBjcmVhdGVUb2tlbiByZXNwb25zZSB3YXMgaW52YWxpZCBvciBtaXNzaW5nIGFjY2Vzc190b2tlbiBmb3IgdXNlcjonLFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIGF1dGhSZXNwb25zZT8uZ2V0SnNvbigpXG4gICAgICApO1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICBlcnJvcjoge1xuICAgICAgICAgIGNvZGU6ICdPQVVUSF9UT0tFTl9FWENIQU5HRV9GQUlMRUQnLFxuICAgICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgICAnRmFpbGVkIHRvIGV4Y2hhbmdlIGF1dGhvcml6YXRpb24gY29kZSBmb3IgdG9rZW46IEludmFsaWQgcmVzcG9uc2UgZnJvbSBzZXJ2ZXIuJyxcbiAgICAgICAgICBkZXRhaWxzOiBhdXRoUmVzcG9uc2U/LmdldEpzb24oKSxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgfVxuICAgIHRva2VuRGF0YUZyb21PQXV0aCA9IGF1dGhSZXNwb25zZS5nZXRKc29uKCk7XG4gIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgIGNvbnN0IGVycm9yRGV0YWlscyA9XG4gICAgICBlLm9yaWdpbmFsRXJyb3I/LmVycm9yX2Rlc2NyaXB0aW9uIHx8XG4gICAgICBlLm1lc3NhZ2UgfHxcbiAgICAgIGUuaW50dWl0X3RpZCB8fFxuICAgICAgJ1Vua25vd24gdG9rZW4gZXhjaGFuZ2UgZXJyb3InO1xuICAgIGNvbnNvbGUuZXJyb3IoYFFCTyBPQXV0aCB0b2tlbiBleGNoYW5nZSBmYWlsZWQgZm9yIHVzZXIgJHt1c2VySWR9OmAsIGUpO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnT0FVVEhfVE9LRU5fRVhDSEFOR0VfRkFJTEVEJyxcbiAgICAgICAgbWVzc2FnZTogYFRva2VuIGV4Y2hhbmdlIGZhaWxlZDogJHtlcnJvckRldGFpbHN9YCxcbiAgICAgICAgZGV0YWlsczogZSxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIC8vIDYuIFZhbGlkYXRlIFRva2VuIFJlc3BvbnNlIChlc3BlY2lhbGx5IHJlYWxtSWQsIGFzIGFjY2Vzc190b2tlbiB3YXMgY2hlY2tlZCBhYm92ZSlcbiAgaWYgKCF0b2tlbkRhdGFGcm9tT0F1dGgucmVhbG1JZCkge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICBgUUJPIE9BdXRoIGNhbGxiYWNrIGZvciB1c2VyICR7dXNlcklkfSBkaWQgbm90IHJldHVybiByZWFsbUlkLmAsXG4gICAgICB0b2tlbkRhdGFGcm9tT0F1dGhcbiAgICApO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnUUJPX0FVVEhfSU5WQUxJRF9SRVNQT05TRScsXG4gICAgICAgIG1lc3NhZ2U6ICdPQXV0aCByZXNwb25zZSBpcyBtaXNzaW5nIHJlYWxtSWQuJyxcbiAgICAgICAgZGV0YWlsczogdG9rZW5EYXRhRnJvbU9BdXRoLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgLy8gNy4gUGVyc2lzdCBUb2tlbnNcbiAgY29uc3Qgc2F2ZU9wID0gYXdhaXQgc2F2ZVFCVG9rZW5zKHVzZXJJZCwgdG9rZW5EYXRhRnJvbU9BdXRoKTtcbiAgaWYgKCFzYXZlT3Aub2spIHtcbiAgICAvLyBQcm9wYWdhdGUgdGhlIGRldGFpbGVkIGVycm9yIGZyb20gc2F2ZVFCVG9rZW5zIChlLmcuLCBUT0tFTl9TQVZFX0ZBSUxFRCwgQ09ORklHX0VSUk9SKVxuICAgIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHNhdmVPcC5lcnJvciEgfTtcbiAgfVxuXG4gIC8vIDguIFN1Y2Nlc3NcbiAgY29uc29sZS5sb2coXG4gICAgYFF1aWNrQm9va3MgYXV0aG9yaXphdGlvbiBzdWNjZXNzZnVsIGFuZCB0b2tlbnMgc2F2ZWQgZm9yIHVzZXIgJHt1c2VySWR9LCByZWFsbUlkICR7dG9rZW5EYXRhRnJvbU9BdXRoLnJlYWxtSWR9LmBcbiAgKTtcbiAgcmV0dXJuIHtcbiAgICBvazogdHJ1ZSxcbiAgICBkYXRhOiB7XG4gICAgICBtZXNzYWdlOiAnUXVpY2tCb29rcyBhdXRob3JpemF0aW9uIHN1Y2Nlc3NmdWwuIFRva2VucyBzYXZlZC4nLFxuICAgICAgcmVhbG1JZDogdG9rZW5EYXRhRnJvbU9BdXRoLnJlYWxtSWQsXG4gICAgfSxcbiAgfTtcbn1cbiJdfQ==