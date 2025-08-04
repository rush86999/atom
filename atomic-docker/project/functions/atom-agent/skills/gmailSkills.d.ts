import { SkillResponse, Email } from '../types';
export interface SearchGmailNluEntities {
    raw_query_text: string;
    from_sender?: string;
    subject_keywords?: string;
    date_filter?: string;
    limit_number?: number;
}
export interface ExtractInfoFromGmailNluEntities {
    email_id?: string;
    email_reference_context?: string;
    information_keywords: string[];
}
export declare function handleSearchGmail(userId: string, rawUserQuery: string, limit?: number): Promise<SkillResponse<{
    emails: Email[];
    userMessage: string;
}>>;
export declare function getRecentUnreadEmailsForBriefing(userId: string, targetDate: Date, // The specific date for which to get emails
count?: number): Promise<SkillResponse<{
    results: GmailMessageSnippet[];
    query_executed?: string;
}>>;
import { GmailSearchParameters, CalendarEventSummary, GmailMessageSnippet } from '../types';
export declare function searchEmailsForPrep(userId: string, params: GmailSearchParameters, meetingContext?: CalendarEventSummary | null, // Optional meeting context
limit?: number): Promise<SkillResponse<{
    results: GmailMessageSnippet[];
    query_executed?: string;
}>>;
export declare function handleExtractInfoFromGmail(userId: string, emailIdOrReference: string, // Could be an email ID or a reference like "last email from ..."
informationKeywords: string[], emailBodyContext?: string): Promise<SkillResponse<{
    extractedInfo: Record<string, string | null>;
    userMessage: string;
}>>;
