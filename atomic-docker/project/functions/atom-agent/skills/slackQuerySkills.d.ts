import { SkillResponse, SlackMessage } from '../types';
export interface SearchSlackMessagesNluEntities {
    raw_query_text: string;
    limit_number?: number;
}
export interface ExtractInfoFromSlackMessageNluEntities {
    message_reference_text: string;
    information_keywords: string[];
    message_text_context?: string;
}
export declare function handleSearchSlackMessages(userId: string, rawUserQuery: string, limit?: number): Promise<SkillResponse<{
    messages: SlackMessage[];
    userMessage: string;
}>>;
export declare function handleExtractInfoFromSlackMessage(userId: string, messageReference: string, // Can be permalink, or "channelId/messageTs", or natural language reference
informationKeywords: string[], messageTextContext?: string): Promise<SkillResponse<{
    extractedInfo: Record<string, string | null>;
    userMessage: string;
}>>;
