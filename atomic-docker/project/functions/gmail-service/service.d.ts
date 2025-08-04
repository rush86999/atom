import { gmail_v1 } from 'googleapis';
/**
 * Retrieves a user's stored Gmail tokens, refreshes if necessary,
 * and returns an authenticated OAuth2 client configured for Gmail API.
 * @param userId The ID of the user.
 * @returns An authenticated google.auth.OAuth2 client or null if tokens are not found/valid.
 */
export declare function getGmailClientForUser(userId: string): Promise<google.auth.OAuth2 | null>;
/**
 * Placeholder for searching user's emails.
 * @param userId The ID of the user.
 * @param query The search query (e.g., "from:xyz@example.com subject:contract after:2023/01/01 before:2023/03/31").
 * @param maxResults Maximum number of results to return.
 * @returns A promise that resolves to an array of Gmail messages.
 */
export declare function searchUserEmails(userId: string, query: string, maxResults?: number): Promise<gmail_v1.Schema$Message[]>;
/**
 * Fetches the full content of a specific email.
 * @param userId The ID of the user.
 * @param emailId The ID of the email to fetch.
 * @returns A promise that resolves to the full Gmail message content.
 */
export declare function getUserEmailContent(userId: string, emailId: string): Promise<gmail_v1.Schema$Message | null>;
