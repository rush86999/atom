import { MSTeamsMessage, GraphSkillResponse, GetMSTeamsMessageDetailInput } from '../types';
/**
 * Searches Microsoft Teams messages for the user by calling the msteams-service directly.
 * @param atomUserId The Atom internal ID of the user making the request.
 * @param kqlQuery The KQL search query string.
 * @param limit Max number of messages to return.
 * @returns A promise resolving to an array of MSTeamsMessage objects.
 */
export declare function searchMyMSTeamsMessages(atomUserId: string, kqlQuery: string, limit?: number): Promise<MSTeamsMessage[]>;
export declare function getRecentChatsAndMentionsForBriefing(atomUserId: string, targetDate: Date, count?: number): Promise<GraphSkillResponse<{
    results: MSTeamsMessage[];
    query_executed?: string;
}>>;
/**
 * Gets a permalink (webUrl) for a specific MS Teams message by calling the msteams-service.
 * @param atomUserId The Atom internal ID of the user.
 * @param identifier An object to identify the message (messageId and chatId or teamId/channelId).
 * @returns A promise resolving to the webUrl string or null.
 */
export declare function getMSTeamsMessageWebUrl(atomUserId: string, identifier: GetMSTeamsMessageDetailInput): Promise<string | null>;
/**
 * Uses an LLM to extract specific pieces of information from an MS Teams message body.
 * @param messageContent The content of the MS Teams message (can be HTML or plain text).
 * @param infoKeywords An array of strings representing the concepts/keywords to search for.
 * @returns A Promise resolving to a record where keys are infoKeywords and values are the extracted strings (or null).
 */
export declare function extractInformationFromMSTeamsMessage(messageContent: string, infoKeywords: string[]): Promise<Record<string, string | null>>;
export interface GetMSTeamsMessageDetailInput {
    messageId: string;
    chatId?: string;
    teamId?: string;
    channelId?: string;
}
/**
 * Reads the detailed content of a specific MS Teams message.
 * @param userId The ID of the user.
 * @param identifier An object to identify the message, containing messageId and context (chatId or teamId/channelId).
 * @returns A promise resolving to an MSTeamsMessage object or null if not found/error.
 */
export declare function readMSTeamsMessage(userId: string, identifier: GetMSTeamsMessageDetailInput): Promise<MSTeamsMessage | null>;
