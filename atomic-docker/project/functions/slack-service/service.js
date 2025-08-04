import { WebClient, ErrorCode as SlackErrorCode, SlackAPIError, } from '@slack/web-api';
import { ATOM_SLACK_BOT_TOKEN } from '../atom-agent/_libs/constants'; // Assuming constants are in atom-agent/_libs
import { logger } from '../_utils/logger'; // Assuming logger is in _utils
let slackWebClientInstance = null;
/**
 * Returns an initialized Slack WebClient.
 * For now, it returns a global client based on ATOM_SLACK_BOT_TOKEN.
 * Sets up a pattern for potential future user-specific Slack configurations.
 * @param userId The ID of the user (currently for logging/context).
 * @returns An initialized WebClient instance or null if configuration is missing.
 */
export function getSlackClientForUser(userId) {
    // userId is logged for now, but could be used for user-specific tokens in the future
    logger.debug(`[SlackService] getSlackClientForUser called for userId: ${userId}`);
    if (slackWebClientInstance) {
        return slackWebClientInstance;
    }
    if (!ATOM_SLACK_BOT_TOKEN) {
        logger.error('[SlackService] Slack Bot Token (ATOM_SLACK_BOT_TOKEN) is not configured.');
        return null;
    }
    try {
        slackWebClientInstance = new WebClient(ATOM_SLACK_BOT_TOKEN);
        logger.info('[SlackService] Slack WebClient initialized successfully.');
        return slackWebClientInstance;
    }
    catch (error) {
        logger.error('[SlackService] Failed to initialize Slack WebClient:', error);
        return null;
    }
}
/**
 * Searches Slack messages using the search.messages API.
 * @param userId The ID of the user (for logging/context).
 *   client.search.messages({ query, count, page })
 * @param query The search query string (compatible with Slack's search syntax).
 * @param maxResults Desired maximum number of results. Pagination will be handled to try to meet this.
 * @returns A promise resolving to an array of AgentSlackMessage objects.
 * @throws Error if the Slack client is not configured or if the API call fails.
 */
export async function searchSlackMessages(userId, query, maxResults = 20) {
    logger.debug(`[SlackService] searchSlackMessages called for userId: ${userId}, query: "${query}", maxResults: ${maxResults}`);
    const client = getSlackClientForUser(userId);
    if (!client) {
        throw new Error('[SlackService] Slack client is not available. Check configuration.');
    }
    const messages = [];
    let currentPage = 1;
    const countPerPage = Math.min(maxResults, 100); // Slack's max count for search.messages is often 100
    try {
        while (messages.length < maxResults) {
            const response = await client.search.messages({
                query: query,
                count: countPerPage,
                page: currentPage,
                sort: 'timestamp', // Sort by relevance (score) or timestamp
                sort_dir: 'desc', // 'desc' for newest first if sorting by timestamp
            });
            if (!response.ok || !response.messages?.matches) {
                const errorMsg = `Slack API error during search: ${response.error || 'Unknown error'}`;
                logger.error(`[SlackService] ${errorMsg}`, response);
                // If it's a critical error, or first page fails, throw. Otherwise, might return what we have.
                if (currentPage === 1)
                    throw new Error(errorMsg);
                else
                    break; // Stop if subsequent pages fail
            }
            const matches = response.messages.matches;
            for (const match of matches) {
                if (messages.length >= maxResults)
                    break;
                // Basic transformation - this will be improved when AgentSlackMessage is finalized
                messages.push({
                    ts: match.ts, // ts is message ID
                    thread_ts: match.thread_ts,
                    channel: { id: match.channel?.id, name: match.channel?.name },
                    user: { id: match.user, name: match.username || match.user }, // Prefer username, fallback to user ID
                    text: match.text,
                    permalink: match.permalink,
                    raw: match, // Store the raw match for now
                });
            }
            // Check for pagination: Slack's search.messages pagination is based on 'page' number.
            // We stop if we have enough messages, if there are no more results, or if we fetched fewer than requested (implies end).
            const totalPages = response.messages.paging?.total_pages || currentPage;
            if (messages.length >= maxResults ||
                currentPage >= totalPages ||
                matches.length < countPerPage) {
                break;
            }
            currentPage++;
        }
        logger.info(`[SlackService] Found ${messages.length} messages for query "${query}" for user ${userId}.`);
        return messages;
    }
    catch (error) {
        logger.error(`[SlackService] Error during searchSlackMessages for userId ${userId}, query "${query}":`, error);
        if (error instanceof SlackAPIError) {
            throw new Error(`[SlackService] Slack API Error (${error.code}): ${error.data?.error || error.message}`);
        }
        throw error; // Re-throw other errors
    }
}
/**
 * Fetches the content of a specific Slack message.
 * Uses conversations.history with latest, oldest, and inclusive flags to pinpoint the message.
 * @param userId The ID of the user (for logging/context).
 * @param channelId The ID of the channel where the message resides.
 * @param messageTs The timestamp (ID) of the message to fetch.
 * @returns A promise resolving to an AgentSlackMessage object or null if not found/error.
 * @throws Error if the Slack client is not configured or if the API call fails critically.
 */
export async function getSlackMessageContent(userId, channelId, messageTs) {
    logger.debug(`[SlackService] getSlackMessageContent called for userId: ${userId}, channelId: ${channelId}, messageTs: ${messageTs}`);
    const client = getSlackClientForUser(userId);
    if (!client) {
        throw new Error('[SlackService] Slack client is not available. Check configuration.');
    }
    if (!channelId || !messageTs) {
        logger.warn('[SlackService] getSlackMessageContent: channelId or messageTs is missing.');
        return null;
    }
    try {
        const response = await client.conversations.history({
            channel: channelId,
            latest: messageTs,
            oldest: messageTs, // Fetch just this one message
            inclusive: true,
            limit: 1,
        });
        if (!response.ok || !response.messages || response.messages.length === 0) {
            const errorMsg = `Slack API error fetching message content: ${response.error || 'Message not found or no content'}`;
            logger.warn(`[SlackService] ${errorMsg} for channel ${channelId}, ts ${messageTs}`, response);
            return null;
        }
        const rawMessage = response.messages[0];
        // TODO: Potentially fetch user info here to populate user.name if not available in message object.
        // const userInfo = await client.users.info({ user: rawMessage.user });
        // const userName = userInfo.ok ? userInfo.user.real_name || userInfo.user.name : rawMessage.user;
        // Basic transformation - to be refined
        const message = {
            ts: rawMessage.ts,
            thread_ts: rawMessage.thread_ts,
            channel: { id: channelId }, // We know channelId, name might need separate lookup or come from elsewhere
            user: { id: rawMessage.user, name: rawMessage.user }, // Placeholder for name, ideally resolve user ID
            text: rawMessage.text,
            blocks: rawMessage.blocks,
            files: rawMessage.files,
            reactions: rawMessage.reactions,
            // permalink: will be fetched by getSlackPermalink if needed
            raw: rawMessage,
        };
        logger.debug(`[SlackService] Successfully fetched message content for ts ${messageTs} in channel ${channelId}`);
        return message;
    }
    catch (error) {
        logger.error(`[SlackService] Error in getSlackMessageContent for channel ${channelId}, ts ${messageTs}:`, error);
        if (error instanceof SlackAPIError) {
            // Specific Slack errors like 'message_not_found', 'channel_not_found' can be handled here
            if (error.code === SlackErrorCode.MessageNotFound ||
                error.code === SlackErrorCode.ChannelNotFound) {
                return null;
            }
            throw new Error(`[SlackService] Slack API Error (${error.code}) fetching message content: ${error.data?.error || error.message}`);
        }
        throw error; // Re-throw other errors
    }
}
/**
 * Fetches a permalink for a specific Slack message.
 * @param userId The ID of the user (for logging/context).
 * @param channelId The ID of the channel where the message resides.
 * @param messageTs The timestamp (ID) of the message.
 * @returns A promise resolving to the permalink string or null if not found/error.
 * @throws Error if the Slack client is not configured or if the API call fails critically.
 */
export async function getSlackPermalink(userId, channelId, messageTs) {
    logger.debug(`[SlackService] getSlackPermalink called for userId: ${userId}, channelId: ${channelId}, messageTs: ${messageTs}`);
    const client = getSlackClientForUser(userId);
    if (!client) {
        throw new Error('[SlackService] Slack client is not available. Check configuration.');
    }
    if (!channelId || !messageTs) {
        logger.warn('[SlackService] getSlackPermalink: channelId or messageTs is missing.');
        return null;
    }
    try {
        const response = await client.chat.getPermalink({
            channel: channelId,
            message_ts: messageTs,
        });
        if (!response.ok || !response.permalink) {
            const errorMsg = `Slack API error fetching permalink: ${response.error || 'Permalink not found'}`;
            logger.warn(`[SlackService] ${errorMsg} for channel ${channelId}, ts ${messageTs}`, response);
            return null;
        }
        logger.debug(`[SlackService] Successfully fetched permalink for ts ${messageTs} in channel ${channelId}`);
        return response.permalink;
    }
    catch (error) {
        logger.error(`[SlackService] Error in getSlackPermalink for channel ${channelId}, ts ${messageTs}:`, error);
        if (error instanceof SlackAPIError) {
            if (error.code === SlackErrorCode.MessageNotFound ||
                error.code === SlackErrorCode.ChannelNotFound) {
                return null;
            }
            throw new Error(`[SlackService] Slack API Error (${error.code}) fetching permalink: ${error.data?.error || error.message}`);
        }
        throw error; // Re-throw other errors
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic2VydmljZS5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInNlcnZpY2UudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUNMLFNBQVMsRUFDVCxTQUFTLElBQUksY0FBYyxFQUMzQixhQUFhLEdBQ2QsTUFBTSxnQkFBZ0IsQ0FBQztBQUN4QixPQUFPLEVBQUUsb0JBQW9CLEVBQUUsTUFBTSwrQkFBK0IsQ0FBQyxDQUFDLDZDQUE2QztBQUNuSCxPQUFPLEVBQUUsTUFBTSxFQUFFLE1BQU0sa0JBQWtCLENBQUMsQ0FBQywrQkFBK0I7QUFnQjFFLElBQUksc0JBQXNCLEdBQXFCLElBQUksQ0FBQztBQUVwRDs7Ozs7O0dBTUc7QUFDSCxNQUFNLFVBQVUscUJBQXFCLENBQUMsTUFBYztJQUNsRCxxRkFBcUY7SUFDckYsTUFBTSxDQUFDLEtBQUssQ0FDViwyREFBMkQsTUFBTSxFQUFFLENBQ3BFLENBQUM7SUFFRixJQUFJLHNCQUFzQixFQUFFLENBQUM7UUFDM0IsT0FBTyxzQkFBc0IsQ0FBQztJQUNoQyxDQUFDO0lBRUQsSUFBSSxDQUFDLG9CQUFvQixFQUFFLENBQUM7UUFDMUIsTUFBTSxDQUFDLEtBQUssQ0FDViwwRUFBMEUsQ0FDM0UsQ0FBQztRQUNGLE9BQU8sSUFBSSxDQUFDO0lBQ2QsQ0FBQztJQUVELElBQUksQ0FBQztRQUNILHNCQUFzQixHQUFHLElBQUksU0FBUyxDQUFDLG9CQUFvQixDQUFDLENBQUM7UUFDN0QsTUFBTSxDQUFDLElBQUksQ0FBQywwREFBMEQsQ0FBQyxDQUFDO1FBQ3hFLE9BQU8sc0JBQXNCLENBQUM7SUFDaEMsQ0FBQztJQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7UUFDZixNQUFNLENBQUMsS0FBSyxDQUFDLHNEQUFzRCxFQUFFLEtBQUssQ0FBQyxDQUFDO1FBQzVFLE9BQU8sSUFBSSxDQUFDO0lBQ2QsQ0FBQztBQUNILENBQUM7QUFFRDs7Ozs7Ozs7R0FRRztBQUNILE1BQU0sQ0FBQyxLQUFLLFVBQVUs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QUkseUJBQXlCLEtBQUssQ0FBQyxJQUFJLEVBQUUsS0FBSyxJQUFJLEtBQUssQ0FBQyxPQUFPLEVBQUUsQ0FDM0csQ0FBQztRQUNKLENBQUM7UUFDRCxNQUFNLEtBQUssQ0FBQyxDQUFDLHdCQUF3QjtJQUN2QyxDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7XG4gIFdlYkNsaWVudCxcbiAgRXJyb3JDb2RlIGFzIFNsYWNrRXJyb3JDb2RlLFxuICBTbGFja0FQSUVycm9yLFxufSBmcm9tICdAc2xhY2svd2ViLWFwaSc7XG5pbXBvcnQgeyBBVE9NX1NMQUNLX0JPVF9UT0tFTiB9IGZyb20gJy4uL2F0b20tYWdlbnQvX2xpYnMvY29uc3RhbnRzJzsgLy8gQXNzdW1pbmcgY29uc3RhbnRzIGFyZSBpbiBhdG9tLWFnZW50L19saWJzXG5pbXBvcnQgeyBsb2dnZXIgfSBmcm9tICcuLi9fdXRpbHMvbG9nZ2VyJzsgLy8gQXNzdW1pbmcgbG9nZ2VyIGlzIGluIF91dGlsc1xuXG4vLyBCYXNpYyBTbGFja01lc3NhZ2UgaW50ZXJmYWNlIC0gVGhpcyB3aWxsIGJlIHJlZmluZWQgbGF0ZXIgaW4gc2xhY2tTa2lsbHMudHMgb3IgdHlwZXMudHNcbmV4cG9ydCBpbnRlcmZhY2UgQWdlbnRTbGFja01lc3NhZ2Uge1xuICB0czogc3RyaW5nOyAvLyBTbGFjayBtZXNzYWdlIHRpbWVzdGFtcCAoc2VydmVzIGFzIElEKVxuICB0aHJlYWRfdHM/OiBzdHJpbmc7IC8vIFRpbWVzdGFtcCBvZiB0aGUgcGFyZW50IG1lc3NhZ2UsIGlmIGluIGEgdGhyZWFkXG4gIGNoYW5uZWw/OiB7IGlkOiBzdHJpbmc7IG5hbWU/OiBzdHJpbmcgfTsgLy8gQ2hhbm5lbCBJRCBhbmQgb3B0aW9uYWxseSBuYW1lXG4gIHVzZXI/OiB7IGlkOiBzdHJpbmc7IG5hbWU/OiBzdHJpbmcgfTsgLy8gVXNlciBJRCBhbmQgb3B0aW9uYWxseSBuYW1lXG4gIHRleHQ/OiBzdHJpbmc7XG4gIGJsb2Nrcz86IGFueVtdOyAvLyBTbGFjayBibG9ja3NcbiAgZmlsZXM/OiBhbnlbXTsgLy8gU2xhY2sgZmlsZXNcbiAgcmVhY3Rpb25zPzogYW55W107IC8vIFNsYWNrIHJlYWN0aW9uc1xuICBwZXJtYWxpbms/OiBzdHJpbmc7XG4gIHJhdz86IGFueTsgLy8gU3RvcmUgdGhlIHJhdyBTbGFjayBtZXNzYWdlIG9iamVjdCBpZiBuZWVkZWRcbn1cblxubGV0IHNsYWNrV2ViQ2xpZW50SW5zdGFuY2U6IFdlYkNsaWVudCB8IG51bGwgPSBudWxsO1xuXG4vKipcbiAqIFJldHVybnMgYW4gaW5pdGlhbGl6ZWQgU2xhY2sgV2ViQ2xpZW50LlxuICogRm9yIG5vdywgaXQgcmV0dXJucyBhIGdsb2JhbCBjbGllbnQgYmFzZWQgb24gQVRPTV9TTEFDS19CT1RfVE9LRU4uXG4gKiBTZXRzIHVwIGEgcGF0dGVybiBmb3IgcG90ZW50aWFsIGZ1dHVyZSB1c2VyLXNwZWNpZmljIFNsYWNrIGNvbmZpZ3VyYXRpb25zLlxuICogQHBhcmFtIHVzZXJJZCBUaGUgSUQgb2YgdGhlIHVzZXIgKGN1cnJlbnRseSBmb3IgbG9nZ2luZy9jb250ZXh0KS5cbiAqIEByZXR1cm5zIEFuIGluaXRpYWxpemVkIFdlYkNsaWVudCBpbnN0YW5jZSBvciBudWxsIGlmIGNvbmZpZ3VyYXRpb24gaXMgbWlzc2luZy5cbiAqL1xuZXhwb3J0IGZ1bmN0aW9uIGdldFNsYWNrQ2xpZW50Rm9yVXNlcih1c2VySWQ6IHN0cmluZyk6IFdlYkNsaWVudCB8IG51bGwge1xuICAvLyB1c2VySWQgaXMgbG9nZ2VkIGZvciBub3csIGJ1dCBjb3VsZCBiZSB1c2VkIGZvciB1c2VyLXNwZWNpZmljIHRva2VucyBpbiB0aGUgZnV0dXJlXG4gIGxvZ2dlci5kZWJ1ZyhcbiAgICBgW1NsYWNrU2VydmljZV0gZ2V0U2xhY2tDbGllbnRGb3JVc2VyIGNhbGxlZCBmb3IgdXNlcklkOiAke3VzZXJJZH1gXG4gICk7XG5cbiAgaWYgKHNsYWNrV2ViQ2xpZW50SW5zdGFuY2UpIHtcbiAgICByZXR1cm4gc2xhY2tXZWJDbGllbnRJbnN0YW5jZTtcbiAgfVxuXG4gIGlmICghQVRPTV9TTEFDS19CT1RfVE9LRU4pIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAnW1NsYWNrU2VydmljZV0gU2xhY2sgQm90IFRva2VuIChBVE9NX1NMQUNLX0JPVF9UT0tFTikgaXMgbm90IGNvbmZpZ3VyZWQuJ1xuICAgICk7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cblxuICB0cnkge1xuICAgIHNsYWNrV2ViQ2xpZW50SW5zdGFuY2UgPSBuZXcgV2ViQ2xpZW50KEFUT01fU0xBQ0tfQk9UX1RPS0VOKTtcbiAgICBsb2dnZXIuaW5mbygnW1NsYWNrU2VydmljZV0gU2xhY2sgV2ViQ2xpZW50IGluaXRpYWxpemVkIHN1Y2Nlc3NmdWxseS4nKTtcbiAgICByZXR1cm4gc2xhY2tXZWJDbGllbnRJbnN0YW5jZTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICBsb2dnZXIuZXJyb3IoJ1tTbGFja1NlcnZpY2VdIEZhaWxlZCB0byBpbml0aWFsaXplIFNsYWNrIFdlYkNsaWVudDonLCBlcnJvcik7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cbn1cblxuLyoqXG4gKiBTZWFyY2hlcyBTbGFjayBtZXNzYWdlcyB1c2luZyB0aGUgc2VhcmNoLm1lc3NhZ2VzIEFQSS5cbiAqIEBwYXJhbSB1c2VySWQgVGhlIElEIG9mIHRoZSB1c2VyIChmb3IgbG9nZ2luZy9jb250ZXh0KS5cbiAqICAgY2xpZW50LnNlYXJjaC5tZXNzYWdlcyh7IHF1ZXJ5LCBjb3VudCwgcGFnZSB9KVxuICogQHBhcmFtIHF1ZXJ5IFRoZSBzZWFyY2ggcXVlcnkgc3RyaW5nIChjb21wYXRpYmxlIHdpdGggU2xhY2sncyBzZWFyY2ggc3ludGF4KS5cbiAqIEBwYXJhbSBtYXhSZXN1bHRzIERlc2lyZWQgbWF4aW11bSBudW1iZXIgb2YgcmVzdWx0cy4gUGFnaW5hdGlvbiB3aWxsIGJlIGhhbmRsZWQgdG8gdHJ5IHRvIG1lZXQgdGhpcy5cbiAqIEByZXR1cm5zIEEgcHJvbWlzZSByZXNvbHZpbmcgdG8gYW4gYXJyYXkgb2YgQWdlbnRTbGFja01lc3NhZ2Ugb2JqZWN0cy5cbiAqIEB0aHJvd3MgRXJyb3IgaWYgdGhlIFNsYWNrIGNsaWVudCBpcyBub3QgY29uZmlndXJlZCBvciBpZiB0aGUgQVBJIGNhbGwgZmFpbHMuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBzZWFyY2hTbGFja01lc3NhZ2VzKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgcXVlcnk6IHN0cmluZyxcbiAgbWF4UmVzdWx0czogbnVtYmVyID0gMjBcbik6IFByb21pc2U8QWdlbnRTbGFja01lc3NhZ2VbXT4ge1xuICBsb2dnZXIuZGVidWcoXG4gICAgYFtTbGFja1NlcnZpY2VdIHNlYXJjaFNsYWNrTWVzc2FnZXMgY2FsbGVkIGZvciB1c2VySWQ6ICR7dXNlcklkfSwgcXVlcnk6IFwiJHtxdWVyeX1cIiwgbWF4UmVzdWx0czogJHttYXhSZXN1bHRzfWBcbiAgKTtcbiAgY29uc3QgY2xpZW50ID0gZ2V0U2xhY2tDbGllbnRGb3JVc2VyKHVzZXJJZCk7XG4gIGlmICghY2xpZW50KSB7XG4gICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgJ1tTbGFja1NlcnZpY2VdIFNsYWNrIGNsaWVudCBpcyBub3QgYXZhaWxhYmxlLiBDaGVjayBjb25maWd1cmF0aW9uLidcbiAgICApO1xuICB9XG5cbiAgY29uc3QgbWVzc2FnZXM6IEFnZW50U2xhY2tNZXNzYWdlW10gPSBbXTtcbiAgbGV0IGN1cnJlbnRQYWdlID0gMTtcbiAgY29uc3QgY291bnRQZXJQYWdlID0gTWF0aC5taW4obWF4UmVzdWx0cywgMTAwKTsgLy8gU2xhY2sncyBtYXggY291bnQgZm9yIHNlYXJjaC5tZXNzYWdlcyBpcyBvZnRlbiAxMDBcblxuICB0cnkge1xuICAgIHdoaWxlIChtZXNzYWdlcy5sZW5ndGggPCBtYXhSZXN1bHRzKSB7XG4gICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGNsaWVudC5zZWFyY2gubWVzc2FnZXMoe1xuICAgICAgICBxdWVyeTogcXVlcnksXG4gICAgICAgIGNvdW50OiBjb3VudFBlclBhZ2UsXG4gICAgICAgIHBhZ2U6IGN1cnJlbnRQYWdlLFxuICAgICAgICBzb3J0OiAndGltZXN0YW1wJywgLy8gU29ydCBieSByZWxldmFuY2UgKHNjb3JlKSBvciB0aW1lc3RhbXBcbiAgICAgICAgc29ydF9kaXI6ICdkZXNjJywgLy8gJ2Rlc2MnIGZvciBuZXdlc3QgZmlyc3QgaWYgc29ydGluZyBieSB0aW1lc3RhbXBcbiAgICAgIH0pO1xuXG4gICAgICBpZiAoIXJlc3BvbnNlLm9rIHx8ICFyZXNwb25zZS5tZXNzYWdlcz8ubWF0Y2hlcykge1xuICAgICAgICBjb25zdCBlcnJvck1zZyA9IGBTbGFjayBBUEkgZXJyb3IgZHVyaW5nIHNlYXJjaDogJHtyZXNwb25zZS5lcnJvciB8fCAnVW5rbm93biBlcnJvcid9YDtcbiAgICAgICAgbG9nZ2VyLmVycm9yKGBbU2xhY2tTZXJ2aWNlXSAke2Vycm9yTXNnfWAsIHJlc3BvbnNlKTtcbiAgICAgICAgLy8gSWYgaXQncyBhIGNyaXRpY2FsIGVycm9yLCBvciBmaXJzdCBwYWdlIGZhaWxzLCB0aHJvdy4gT3RoZXJ3aXNlLCBtaWdodCByZXR1cm4gd2hhdCB3ZSBoYXZlLlxuICAgICAgICBpZiAoY3VycmVudFBhZ2UgPT09IDEpIHRocm93IG5ldyBFcnJvcihlcnJvck1zZyk7XG4gICAgICAgIGVsc2UgYnJlYWs7IC8vIFN0b3AgaWYgc3Vic2VxdWVudCBwYWdlcyBmYWlsXG4gICAgICB9XG5cbiAgICAgIGNvbnN0IG1hdGNoZXMgPSByZXNwb25zZS5tZXNzYWdlcy5tYXRjaGVzO1xuICAgICAgZm9yIChjb25zdCBtYXRjaCBvZiBtYXRjaGVzKSB7XG4gICAgICAgIGlmIChtZXNzYWdlcy5sZW5ndGggPj0gbWF4UmVzdWx0cykgYnJlYWs7XG5cbiAgICAgICAgLy8gQmFzaWMgdHJhbnNmb3JtYXRpb24gLSB0aGlzIHdpbGwgYmUgaW1wcm92ZWQgd2hlbiBBZ2VudFNsYWNrTWVzc2FnZSBpcyBmaW5hbGl6ZWRcbiAgICAgICAgbWVzc2FnZXMucHVzaCh7XG4gICAgICAgICAgdHM6IG1hdGNoLnRzISwgLy8gdHMgaXMgbWVzc2FnZSBJRFxuICAgICAgICAgIHRocmVhZF90czogbWF0Y2gudGhyZWFkX3RzLFxuICAgICAgICAgIGNoYW5uZWw6IHsgaWQ6IG1hdGNoLmNoYW5uZWw/LmlkISwgbmFtZTogbWF0Y2guY2hhbm5lbD8ubmFtZSB9LFxuICAgICAgICAgIHVzZXI6IHsgaWQ6IG1hdGNoLnVzZXIhLCBuYW1lOiBtYXRjaC51c2VybmFtZSB8fCBtYXRjaC51c2VyIH0sIC8vIFByZWZlciB1c2VybmFtZSwgZmFsbGJhY2sgdG8gdXNlciBJRFxuICAgICAgICAgIHRleHQ6IG1hdGNoLnRleHQsXG4gICAgICAgICAgcGVybWFsaW5rOiBtYXRjaC5wZXJtYWxpbmssXG4gICAgICAgICAgcmF3OiBtYXRjaCwgLy8gU3RvcmUgdGhlIHJhdyBtYXRjaCBmb3Igbm93XG4gICAgICAgIH0pO1xuICAgICAgfVxuXG4gICAgICAvLyBDaGVjayBmb3IgcGFnaW5hdGlvbjogU2xhY2sncyBzZWFyY2gubWVzc2FnZXMgcGFnaW5hdGlvbiBpcyBiYXNlZCBvbiAncGFnZScgbnVtYmVyLlxuICAgICAgLy8gV2Ugc3RvcCBpZiB3ZSBoYXZlIGVub3VnaCBtZXNzYWdlcywgaWYgdGhlcmUgYXJlIG5vIG1vcmUgcmVzdWx0cywgb3IgaWYgd2UgZmV0Y2hlZCBmZXdlciB0aGFuIHJlcXVlc3RlZCAoaW1wbGllcyBlbmQpLlxuICAgICAgY29uc3QgdG90YWxQYWdlcyA9IHJlc3BvbnNlLm1lc3NhZ2VzLnBhZ2luZz8udG90YWxfcGFnZXMgfHwgY3VycmVudFBhZ2U7XG4gICAgICBpZiAoXG4gICAgICAgIG1lc3NhZ2VzLmxlbmd0aCA+PSBtYXhSZXN1bHRzIHx8XG4gICAgICAgIGN1cnJlbnRQYWdlID49IHRvdGFsUGFnZXMgfHxcbiAgICAgICAgbWF0Y2hlcy5sZW5ndGggPCBjb3VudFBlclBhZ2VcbiAgICAgICkge1xuICAgICAgICBicmVhaztcbiAgICAgIH1cbiAgICAgIGN1cnJlbnRQYWdlKys7XG4gICAgfVxuICAgIGxvZ2dlci5pbmZvKFxuICAgICAgYFtTbGFja1NlcnZpY2VdIEZvdW5kICR7bWVzc2FnZXMubGVuZ3RofSBtZXNzYWdlcyBmb3IgcXVlcnkgXCIke3F1ZXJ5fVwiIGZvciB1c2VyICR7dXNlcklkfS5gXG4gICAgKTtcbiAgICByZXR1cm4gbWVzc2FnZXM7XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICBgW1NsYWNrU2VydmljZV0gRXJyb3IgZHVyaW5nIHNlYXJjaFNsYWNrTWVzc2FnZXMgZm9yIHVzZXJJZCAke3VzZXJJZH0sIHF1ZXJ5IFwiJHtxdWVyeX1cIjpgLFxuICAgICAgZXJyb3JcbiAgICApO1xuICAgIGlmIChlcnJvciBpbnN0YW5jZW9mIFNsYWNrQVBJRXJyb3IpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICAgYFtTbGFja1NlcnZpY2VdIFNsYWNrIEFQSSBFcnJvciAoJHtlcnJvci5jb2RlfSk6ICR7ZXJyb3IuZGF0YT8uZXJyb3IgfHwgZXJyb3IubWVzc2FnZX1gXG4gICAgICApO1xuICAgIH1cbiAgICB0aHJvdyBlcnJvcjsgLy8gUmUtdGhyb3cgb3RoZXIgZXJyb3JzXG4gIH1cbn1cblxuLyoqXG4gKiBGZXRjaGVzIHRoZSBjb250ZW50IG9mIGEgc3BlY2lmaWMgU2xhY2sgbWVzc2FnZS5cbiAqIFVzZXMgY29udmVyc2F0aW9ucy5oaXN0b3J5IHdpdGggbGF0ZXN0LCBvbGRlc3QsIGFuZCBpbmNsdXNpdmUgZmxhZ3MgdG8gcGlucG9pbnQgdGhlIG1lc3NhZ2UuXG4gKiBAcGFyYW0gdXNlcklkIFRoZSBJRCBvZiB0aGUgdXNlciAoZm9yIGxvZ2dpbmcvY29udGV4dCkuXG4gKiBAcGFyYW0gY2hhbm5lbElkIFRoZSBJRCBvZiB0aGUgY2hhbm5lbCB3aGVyZSB0aGUgbWVzc2FnZSByZXNpZGVzLlxuICogQHBhcmFtIG1lc3NhZ2VUcyBUaGUgdGltZXN0YW1wIChJRCkgb2YgdGhlIG1lc3NhZ2UgdG8gZmV0Y2guXG4gKiBAcmV0dXJucyBBIHByb21pc2UgcmVzb2x2aW5nIHRvIGFuIEFnZW50U2xhY2tNZXNzYWdlIG9iamVjdCBvciBudWxsIGlmIG5vdCBmb3VuZC9lcnJvci5cbiAqIEB0aHJvd3MgRXJyb3IgaWYgdGhlIFNsYWNrIGNsaWVudCBpcyBub3QgY29uZmlndXJlZCBvciBpZiB0aGUgQVBJIGNhbGwgZmFpbHMgY3JpdGljYWxseS5cbiAqL1xuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldFNsYWNrTWVzc2FnZUNvbnRlbnQoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBjaGFubmVsSWQ6IHN0cmluZyxcbiAgbWVzc2FnZVRzOiBzdHJpbmdcbik6IFByb21pc2U8QWdlbnRTbGFja01lc3NhZ2UgfCBudWxsPiB7XG4gIGxvZ2dlci5kZWJ1ZyhcbiAgICBgW1NsYWNrU2VydmljZV0gZ2V0U2xhY2tNZXNzYWdlQ29udGVudCBjYWxsZWQgZm9yIHVzZXJJZDogJHt1c2VySWR9LCBjaGFubmVsSWQ6ICR7Y2hhbm5lbElkfSwgbWVzc2FnZVRzOiAke21lc3NhZ2VUc31gXG4gICk7XG4gIGNvbnN0IGNsaWVudCA9IGdldFNsYWNrQ2xpZW50Rm9yVXNlcih1c2VySWQpO1xuICBpZiAoIWNsaWVudCkge1xuICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICdbU2xhY2tTZXJ2aWNlXSBTbGFjayBjbGllbnQgaXMgbm90IGF2YWlsYWJsZS4gQ2hlY2sgY29uZmlndXJhdGlvbi4nXG4gICAgKTtcbiAgfVxuXG4gIGlmICghY2hhbm5lbElkIHx8ICFtZXNzYWdlVHMpIHtcbiAgICBsb2dnZXIud2FybihcbiAgICAgICdbU2xhY2tTZXJ2aWNlXSBnZXRTbGFja01lc3NhZ2VDb250ZW50OiBjaGFubmVsSWQgb3IgbWVzc2FnZVRzIGlzIG1pc3NpbmcuJ1xuICAgICk7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgY2xpZW50LmNvbnZlcnNhdGlvbnMuaGlzdG9yeSh7XG4gICAgICBjaGFubmVsOiBjaGFubmVsSWQsXG4gICAgICBsYXRlc3Q6IG1lc3NhZ2VUcyxcbiAgICAgIG9sZGVzdDogbWVzc2FnZVRzLCAvLyBGZXRjaCBqdXN0IHRoaXMgb25lIG1lc3NhZ2VcbiAgICAgIGluY2x1c2l2ZTogdHJ1ZSxcbiAgICAgIGxpbWl0OiAxLFxuICAgIH0pO1xuXG4gICAgaWYgKCFyZXNwb25zZS5vayB8fCAhcmVzcG9uc2UubWVzc2FnZXMgfHwgcmVzcG9uc2UubWVzc2FnZXMubGVuZ3RoID09PSAwKSB7XG4gICAgICBjb25zdCBlcnJvck1zZyA9IGBTbGFjayBBUEkgZXJyb3IgZmV0Y2hpbmcgbWVzc2FnZSBjb250ZW50OiAke3Jlc3BvbnNlLmVycm9yIHx8ICdNZXNzYWdlIG5vdCBmb3VuZCBvciBubyBjb250ZW50J31gO1xuICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgIGBbU2xhY2tTZXJ2aWNlXSAke2Vycm9yTXNnfSBmb3IgY2hhbm5lbCAke2NoYW5uZWxJZH0sIHRzICR7bWVzc2FnZVRzfWAsXG4gICAgICAgIHJlc3BvbnNlXG4gICAgICApO1xuICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuXG4gICAgY29uc3QgcmF3TWVzc2FnZSA9IHJlc3BvbnNlLm1lc3NhZ2VzWzBdO1xuXG4gICAgLy8gVE9ETzogUG90ZW50aWFsbHkgZmV0Y2ggdXNlciBpbmZvIGhlcmUgdG8gcG9wdWxhdGUgdXNlci5uYW1lIGlmIG5vdCBhdmFpbGFibGUgaW4gbWVzc2FnZSBvYmplY3QuXG4gICAgLy8gY29uc3QgdXNlckluZm8gPSBhd2FpdCBjbGllbnQudXNlcnMuaW5mbyh7IHVzZXI6IHJhd01lc3NhZ2UudXNlciB9KTtcbiAgICAvLyBjb25zdCB1c2VyTmFtZSA9IHVzZXJJbmZvLm9rID8gdXNlckluZm8udXNlci5yZWFsX25hbWUgfHwgdXNlckluZm8udXNlci5uYW1lIDogcmF3TWVzc2FnZS51c2VyO1xuXG4gICAgLy8gQmFzaWMgdHJhbnNmb3JtYXRpb24gLSB0byBiZSByZWZpbmVkXG4gICAgY29uc3QgbWVzc2FnZTogQWdlbnRTbGFja01lc3NhZ2UgPSB7XG4gICAgICB0czogcmF3TWVzc2FnZS50cyEsXG4gICAgICB0aHJlYWRfdHM6IHJhd01lc3NhZ2UudGhyZWFkX3RzLFxuICAgICAgY2hhbm5lbDogeyBpZDogY2hhbm5lbElkIH0sIC8vIFdlIGtub3cgY2hhbm5lbElkLCBuYW1lIG1pZ2h0IG5lZWQgc2VwYXJhdGUgbG9va3VwIG9yIGNvbWUgZnJvbSBlbHNld2hlcmVcbiAgICAgIHVzZXI6IHsgaWQ6IHJhd01lc3NhZ2UudXNlciEsIG5hbWU6IHJhd01lc3NhZ2UudXNlciB9LCAvLyBQbGFjZWhvbGRlciBmb3IgbmFtZSwgaWRlYWxseSByZXNvbHZlIHVzZXIgSURcbiAgICAgIHRleHQ6IHJhd01lc3NhZ2UudGV4dCxcbiAgICAgIGJsb2NrczogcmF3TWVzc2FnZS5ibG9ja3MsXG4gICAgICBmaWxlczogcmF3TWVzc2FnZS5maWxlcyxcbiAgICAgIHJlYWN0aW9uczogcmF3TWVzc2FnZS5yZWFjdGlvbnMsXG4gICAgICAvLyBwZXJtYWxpbms6IHdpbGwgYmUgZmV0Y2hlZCBieSBnZXRTbGFja1Blcm1hbGluayBpZiBuZWVkZWRcbiAgICAgIHJhdzogcmF3TWVzc2FnZSxcbiAgICB9O1xuICAgIGxvZ2dlci5kZWJ1ZyhcbiAgICAgIGBbU2xhY2tTZXJ2aWNlXSBTdWNjZXNzZnVsbHkgZmV0Y2hlZCBtZXNzYWdlIGNvbnRlbnQgZm9yIHRzICR7bWVzc2FnZVRzfSBpbiBjaGFubmVsICR7Y2hhbm5lbElkfWBcbiAgICApO1xuICAgIHJldHVybiBtZXNzYWdlO1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFtTbGFja1NlcnZpY2VdIEVycm9yIGluIGdldFNsYWNrTWVzc2FnZUNvbnRlbnQgZm9yIGNoYW5uZWwgJHtjaGFubmVsSWR9LCB0cyAke21lc3NhZ2VUc306YCxcbiAgICAgIGVycm9yXG4gICAgKTtcbiAgICBpZiAoZXJyb3IgaW5zdGFuY2VvZiBTbGFja0FQSUVycm9yKSB7XG4gICAgICAvLyBTcGVjaWZpYyBTbGFjayBlcnJvcnMgbGlrZSAnbWVzc2FnZV9ub3RfZm91bmQnLCAnY2hhbm5lbF9ub3RfZm91bmQnIGNhbiBiZSBoYW5kbGVkIGhlcmVcbiAgICAgIGlmIChcbiAgICAgICAgZXJyb3IuY29kZSA9PT0gU2xhY2tFcnJvckNvZGUuTWVzc2FnZU5vdEZvdW5kIHx8XG4gICAgICAgIGVycm9yLmNvZGUgPT09IFNsYWNrRXJyb3JDb2RlLkNoYW5uZWxOb3RGb3VuZFxuICAgICAgKSB7XG4gICAgICAgIHJldHVybiBudWxsO1xuICAgICAgfVxuICAgICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgICBgW1NsYWNrU2VydmljZV0gU2xhY2sgQVBJIEVycm9yICgke2Vycm9yLmNvZGV9KSBmZXRjaGluZyBtZXNzYWdlIGNvbnRlbnQ6ICR7ZXJyb3IuZGF0YT8uZXJyb3IgfHwgZXJyb3IubWVzc2FnZX1gXG4gICAgICApO1xuICAgIH1cbiAgICB0aHJvdyBlcnJvcjsgLy8gUmUtdGhyb3cgb3RoZXIgZXJyb3JzXG4gIH1cbn1cblxuLyoqXG4gKiBGZXRjaGVzIGEgcGVybWFsaW5rIGZvciBhIHNwZWNpZmljIFNsYWNrIG1lc3NhZ2UuXG4gKiBAcGFyYW0gdXNlcklkIFRoZSBJRCBvZiB0aGUgdXNlciAoZm9yIGxvZ2dpbmcvY29udGV4dCkuXG4gKiBAcGFyYW0gY2hhbm5lbElkIFRoZSBJRCBvZiB0aGUgY2hhbm5lbCB3aGVyZSB0aGUgbWVzc2FnZSByZXNpZGVzLlxuICogQHBhcmFtIG1lc3NhZ2VUcyBUaGUgdGltZXN0YW1wIChJRCkgb2YgdGhlIG1lc3NhZ2UuXG4gKiBAcmV0dXJucyBBIHByb21pc2UgcmVzb2x2aW5nIHRvIHRoZSBwZXJtYWxpbmsgc3RyaW5nIG9yIG51bGwgaWYgbm90IGZvdW5kL2Vycm9yLlxuICogQHRocm93cyBFcnJvciBpZiB0aGUgU2xhY2sgY2xpZW50IGlzIG5vdCBjb25maWd1cmVkIG9yIGlmIHRoZSBBUEkgY2FsbCBmYWlscyBjcml0aWNhbGx5LlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0U2xhY2tQZXJtYWxpbmsoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBjaGFubmVsSWQ6IHN0cmluZyxcbiAgbWVzc2FnZVRzOiBzdHJpbmdcbik6IFByb21pc2U8c3RyaW5nIHwgbnVsbD4ge1xuICBsb2dnZXIuZGVidWcoXG4gICAgYFtTbGFja1NlcnZpY2VdIGdldFNsYWNrUGVybWFsaW5rIGNhbGxlZCBmb3IgdXNlcklkOiAke3VzZXJJZH0sIGNoYW5uZWxJZDogJHtjaGFubmVsSWR9LCBtZXNzYWdlVHM6ICR7bWVzc2FnZVRzfWBcbiAgKTtcbiAgY29uc3QgY2xpZW50ID0gZ2V0U2xhY2tDbGllbnRGb3JVc2VyKHVzZXJJZCk7XG4gIGlmICghY2xpZW50KSB7XG4gICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgJ1tTbGFja1NlcnZpY2VdIFNsYWNrIGNsaWVudCBpcyBub3QgYXZhaWxhYmxlLiBDaGVjayBjb25maWd1cmF0aW9uLidcbiAgICApO1xuICB9XG5cbiAgaWYgKCFjaGFubmVsSWQgfHwgIW1lc3NhZ2VUcykge1xuICAgIGxvZ2dlci53YXJuKFxuICAgICAgJ1tTbGFja1NlcnZpY2VdIGdldFNsYWNrUGVybWFsaW5rOiBjaGFubmVsSWQgb3IgbWVzc2FnZVRzIGlzIG1pc3NpbmcuJ1xuICAgICk7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgY2xpZW50LmNoYXQuZ2V0UGVybWFsaW5rKHtcbiAgICAgIGNoYW5uZWw6IGNoYW5uZWxJZCxcbiAgICAgIG1lc3NhZ2VfdHM6IG1lc3NhZ2VUcyxcbiAgICB9KTtcblxuICAgIGlmICghcmVzcG9uc2Uub2sgfHwgIXJlc3BvbnNlLnBlcm1hbGluaykge1xuICAgICAgY29uc3QgZXJyb3JNc2cgPSBgU2xhY2sgQVBJIGVycm9yIGZldGNoaW5nIHBlcm1hbGluazogJHtyZXNwb25zZS5lcnJvciB8fCAnUGVybWFsaW5rIG5vdCBmb3VuZCd9YDtcbiAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICBgW1NsYWNrU2VydmljZV0gJHtlcnJvck1zZ30gZm9yIGNoYW5uZWwgJHtjaGFubmVsSWR9LCB0cyAke21lc3NhZ2VUc31gLFxuICAgICAgICByZXNwb25zZVxuICAgICAgKTtcbiAgICAgIHJldHVybiBudWxsO1xuICAgIH1cblxuICAgIGxvZ2dlci5kZWJ1ZyhcbiAgICAgIGBbU2xhY2tTZXJ2aWNlXSBTdWNjZXNzZnVsbHkgZmV0Y2hlZCBwZXJtYWxpbmsgZm9yIHRzICR7bWVzc2FnZVRzfSBpbiBjaGFubmVsICR7Y2hhbm5lbElkfWBcbiAgICApO1xuICAgIHJldHVybiByZXNwb25zZS5wZXJtYWxpbmsgYXMgc3RyaW5nO1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFtTbGFja1NlcnZpY2VdIEVycm9yIGluIGdldFNsYWNrUGVybWFsaW5rIGZvciBjaGFubmVsICR7Y2hhbm5lbElkfSwgdHMgJHttZXNzYWdlVHN9OmAsXG4gICAgICBlcnJvclxuICAgICk7XG4gICAgaWYgKGVycm9yIGluc3RhbmNlb2YgU2xhY2tBUElFcnJvcikge1xuICAgICAgaWYgKFxuICAgICAgICBlcnJvci5jb2RlID09PSBTbGFja0Vycm9yQ29kZS5NZXNzYWdlTm90Rm91bmQgfHxcbiAgICAgICAgZXJyb3IuY29kZSA9PT0gU2xhY2tFcnJvckNvZGUuQ2hhbm5lbE5vdEZvdW5kXG4gICAgICApIHtcbiAgICAgICAgcmV0dXJuIG51bGw7XG4gICAgICB9XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAgIGBbU2xhY2tTZXJ2aWNlXSBTbGFjayBBUEkgRXJyb3IgKCR7ZXJyb3IuY29kZX0pIGZldGNoaW5nIHBlcm1hbGluazogJHtlcnJvci5kYXRhPy5lcnJvciB8fCBlcnJvci5tZXNzYWdlfWBcbiAgICAgICk7XG4gICAgfVxuICAgIHRocm93IGVycm9yOyAvLyBSZS10aHJvdyBvdGhlciBlcnJvcnNcbiAgfVxufVxuIl19