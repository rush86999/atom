import { LLMServiceInterface } from '../lib/llmUtils';
/**
 * Represents an incoming email message.
 */
export interface EmailObject {
    id: string;
    sender: string;
    recipients: string[];
    subject: string;
    body: string;
    receivedDate: Date;
    headers?: Record<string, string>;
}
/**
 * Defines the possible categories for a triaged email.
 */
export type EmailCategory = 'Urgent' | 'ActionRequired' | 'FYI' | 'Spam' | 'MeetingInvite' | 'Other';
/**
 * Represents the result of triaging an email.
 */
export interface TriageResult {
    emailId: string;
    category: EmailCategory;
    confidence?: number;
    summary?: string;
    suggestedReply?: string;
    priorityScore?: number;
    extractedActionItems?: string[];
}
export declare class EmailTriageSkill {
    private readonly llmService;
    constructor(llmService: LLMServiceInterface);
    execute(email: EmailObject): Promise<TriageResult>;
}
