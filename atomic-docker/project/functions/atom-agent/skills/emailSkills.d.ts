import { Email, SendEmailResponse, ReadEmailResponse } from '../types';
export declare function searchMyEmails(userId: string, searchQuery: string, limit?: number): Promise<Email[]>;
export declare function readEmail(userId: string, emailId: string): Promise<ReadEmailResponse>;
/**
 * Uses an LLM to extract specific pieces of information from an email body
 * based on a list of keywords or concepts.
 * @param emailBody The plain text body of the email.
 * @param infoKeywords An array of strings representing the concepts/keywords to search for.
 *                     (e.g., ["contract end date", "invoice number", "meeting link"])
 * @returns A Promise resolving to a record where keys are infoKeywords and values are the extracted strings (or null).
 */
export declare function extractInformationFromEmailBody(emailBody: string, infoKeywords: string[]): Promise<Record<string, string | null>>;
export interface EmailDetails {
    to: string;
    subject: string;
    body: string;
    cc?: string[];
    bcc?: string[];
    htmlBody?: string;
}
export declare function sendEmail(emailDetails: EmailDetails): Promise<SendEmailResponse>;
