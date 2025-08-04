import { SlackSkillResponse, SlackMessageData, ListSlackChannelsData, SlackMessage } from '../types';
export declare function listSlackChannels(userId: string, limit?: number, cursor?: string): Promise<SlackSkillResponse<ListSlackChannelsData>>;
export declare function sendSlackMessage(userId: string, channelIdentifier: string, text: string): Promise<SlackSkillResponse<SlackMessageData>>;
/**
 * Searches Slack messages for the user using the Slack Web API.
 * @param atomUserId The Atom internal ID of the user making the request (for logging/context).
 * @param searchQuery The Slack API compatible search query string.
 * @param limit Max number of messages to return.
 * @returns A promise resolving to an array of SlackMessage objects.
 */
export declare function searchMySlackMessages(atomUserId: string, searchQuery: string, limit?: number): Promise<SlackMessage[]>;
/**
 * Reads the detailed content of a specific Slack message using Slack Web API.
 * @param atomUserId The Atom internal ID of the user (for logging/context).
 * @param channelId The ID of the channel containing the message.
 * @param messageTs The timestamp (ID) of the message.
 * @returns A promise resolving to a SlackMessage object or null if not found/error.
 */
export declare function readSlackMessage(atomUserId: string, channelId: string, messageTs: string): Promise<SlackMessage | null>;
/**
 * Uses an LLM to extract specific pieces of information from a Slack message body
 * based on a list of keywords or concepts.
 * @param messageText The plain text content of the Slack message.
 * @param infoKeywords An array of strings representing the concepts/keywords to search for.
 * @returns A Promise resolving to a record where keys are infoKeywords and values are the extracted strings (or null).
 */
export declare function extractInformationFromSlackMessage(messageText: string, infoKeywords: string[]): Promise<Record<string, string | null>>;
export declare function getRecentDMsAndMentionsForBriefing(atomUserId: string, // Atom's internal user ID
targetDate: Date, count?: number): Promise<SlackSkillResponse<{
    results: SlackMessage[];
    query_executed?: string;
}>>;
/**
 * Gets a permalink for a specific Slack message using the Slack Web API.
 * @param atomUserId The Atom internal ID of the user (for logging/context).
 * @param channelId The ID of the channel containing the message.
 * @param messageTs The timestamp (ID) of the message.
 * @returns A promise resolving to the permalink string or null if not found/error.
 */
export declare function getSlackMessagePermalink(atomUserId: string, // Atom user ID for context
channelId: string, messageTs: string): Promise<string | null>;
