import { WebClient } from '@slack/web-api';
export interface AgentSlackMessage {
    ts: string;
    thread_ts?: string;
    channel?: {
        id: string;
        name?: string;
    };
    user?: {
        id: string;
        name?: string;
    };
    text?: string;
    blocks?: any[];
    files?: any[];
    reactions?: any[];
    permalink?: string;
    raw?: any;
}
/**
 * Returns an initialized Slack WebClient.
 * For now, it returns a global client based on ATOM_SLACK_BOT_TOKEN.
 * Sets up a pattern for potential future user-specific Slack configurations.
 * @param userId The ID of the user (currently for logging/context).
 * @returns An initialized WebClient instance or null if configuration is missing.
 */
export declare function getSlackClientForUser(userId: string): WebClient | null;
/**
 * Searches Slack messages using the search.messages API.
 * @param userId The ID of the user (for logging/context).
 *   client.search.messages({ query, count, page })
 * @param query The search query string (compatible with Slack's search syntax).
 * @param maxResults Desired maximum number of results. Pagination will be handled to try to meet this.
 * @returns A promise resolving to an array of AgentSlackMessage objects.
 * @throws Error if the Slack client is not configured or if the API call fails.
 */
export declare function searchSlackMessages(userId: string, query: string, maxResults?: number): Promise<AgentSlackMessage[]>;
/**
 * Fetches the content of a specific Slack message.
 * Uses conversations.history with latest, oldest, and inclusive flags to pinpoint the message.
 * @param userId The ID of the user (for logging/context).
 * @param channelId The ID of the channel where the message resides.
 * @param messageTs The timestamp (ID) of the message to fetch.
 * @returns A promise resolving to an AgentSlackMessage object or null if not found/error.
 * @throws Error if the Slack client is not configured or if the API call fails critically.
 */
export declare function getSlackMessageContent(userId: string, channelId: string, messageTs: string): Promise<AgentSlackMessage | null>;
/**
 * Fetches a permalink for a specific Slack message.
 * @param userId The ID of the user (for logging/context).
 * @param channelId The ID of the channel where the message resides.
 * @param messageTs The timestamp (ID) of the message.
 * @returns A promise resolving to the permalink string or null if not found/error.
 * @throws Error if the Slack client is not configured or if the API call fails critically.
 */
export declare function getSlackPermalink(userId: string, channelId: string, messageTs: string): Promise<string | null>;
