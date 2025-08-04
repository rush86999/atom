import { EmailDetails } from '../skills/emailSkills';
export type EmailActionType = 'GET_FULL_CONTENT' | 'GET_SENDER' | 'GET_SUBJECT' | 'GET_DATE' | 'FIND_SPECIFIC_INFO' | 'SUMMARIZE_EMAIL' | 'SEND_EMAIL';
export interface EmailActionRequest {
    actionType: EmailActionType;
    infoKeywords?: string[];
    naturalLanguageQuestion?: string;
}
export interface ParsedNluEmailRequest {
    userId: string;
    rawEmailSearchQuery: string;
    actionRequested: EmailActionRequest;
    targetEmailId?: string;
}
export interface ParsedNluSendEmailRequest {
    userId: string;
    emailDetails: EmailDetails;
}
/**
 * Handles a generic email inquiry: understands the search query using an LLM,
 * finds an email, and performs an action on it (e.g., extracts info, gets metadata).
 */
export declare function handleEmailInquiry(request: ParsedNluEmailRequest): Promise<string>;
/**
 * Handles a request to send an email.
 */
export declare function handleSendEmailRequest(request: ParsedNluSendEmailRequest): Promise<string>;
