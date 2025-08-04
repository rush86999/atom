import { QBSkillResponse, ListQBInvoicesData, QuickBooksInvoice } from '../types';
export declare function resetOAuthClientInstanceCache(): void;
/**
 * Generates the QuickBooks Online authorization URI.
 * @returns {QBSkillResponse<string>} The authorization URI or an error response.
 */
export declare function getAuthUri(stateCSRFToken: string): QBSkillResponse<string>;
export declare function listQuickBooksInvoices(userId: string, options?: {
    limit?: number;
    offset?: number;
    customerId?: string;
    status?: string;
}): Promise<QBSkillResponse<ListQBInvoicesData>>;
export declare function getQuickBooksInvoiceDetails(userId: string, invoiceId: string): Promise<QBSkillResponse<QuickBooksInvoice | null>>;
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
export declare function handleQuickBooksCallback(userId: string, urlWithCode: string, originalState?: string): Promise<QBSkillResponse<{
    message: string;
    realmId: string;
}>>;
