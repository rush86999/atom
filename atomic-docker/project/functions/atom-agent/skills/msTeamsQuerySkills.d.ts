import { SkillResponse, MSTeamsMessage } from '../types';
export interface SearchMSTeamsMessagesNluEntities {
    raw_query_text: string;
    limit_number?: number;
}
export interface ExtractInfoFromMSTeamsMessageNluEntities {
    message_reference_text: string;
    information_keywords: string[];
    message_content_context?: string;
    message_id?: string;
    chat_id?: string;
    team_id?: string;
    channel_id?: string;
}
export declare function handleSearchMSTeamsMessages(userId: string, rawUserQuery: string, limit?: number): Promise<SkillResponse<{
    messages: MSTeamsMessage[];
    userMessage: string;
}>>;
export declare function handleExtractInfoFromMSTeamsMessage(userId: string, messageReferenceText: string, informationKeywords: string[], messageContentContext?: string): Promise<SkillResponse<{
    extractedInfo: Record<string, string | null>;
    userMessage: string;
}>>;
