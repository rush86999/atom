import { WebClient, SlackAPIError, } from '@slack/web-api';
import { executeGraphQLQuery } from '../_libs/graphqlClient';
import { logger } from '../../_utils/logger';
async function getSlackToken(userId) {
    const query = `
        query GetUserToken($userId: String!, $service: String!) {
            user_tokens(where: {user_id: {_eq: $userId}, service: {_eq: $service}}) {
                access_token
            }
        }
    `;
    const variables = {
        userId,
        service: 'slack',
    };
    const response = await executeGraphQLQuery(query, variables, 'GetUserToken', userId);
    if (response.user_tokens && response.user_tokens.length > 0) {
        return response.user_tokens[0].access_token;
    }
    return null;
}
const getSlackClient = async (userId) => {
    const token = await getSlackToken(userId);
    if (!token) {
        logger.error('[SlackSkills] Slack token not found for user.');
        return null;
    }
    return new WebClient(token);
};
// Helper to determine if a string looks like a Slack ID
function isSlackId(id) {
    if (!id)
        return false;
    return /^[UCGDWF][A-Z0-9]{8,10}$/.test(id);
}
// --- Helper function to enrich Slack messages with user and channel names ---
async function _enrichSlackMessagesWithNames(client, messages, userCache, channelCache) {
    const userIdsToFetch = new Set();
    const channelIdsToFetch = new Set();
    for (const msg of messages) {
        if (msg.userId && !msg.userName && !userCache.has(msg.userId)) {
            userIdsToFetch.add(msg.userId);
        }
        if (msg.botId && !msg.userName && !userCache.has(msg.botId)) {
            // Also try to resolve bot names
            userIdsToFetch.add(msg.botId); // Slack's users.info works for bot IDs too
        }
        if (msg.channelId && !msg.channelName && !channelCache.has(msg.channelId)) {
            channelIdsToFetch.add(msg.channelId);
        }
    }
    if (userIdsToFetch.size > 0) {
        logger.debug(`[SlackSkills_Enrich] Fetching info for ${userIdsToFetch.size} user/bot IDs.`);
        await Promise.allSettled(Array.from(userIdsToFetch).map(async (uid) => {
            if (userCache.has(uid))
                return;
            try {
                const response = await client.users.info({ user: uid });
                if (response.ok && response.user) {
                    userCache.set(uid, response.user.real_name || response.user.name || uid);
                }
                else {
                    // Check for bot_info if users.info fails for a bot_id
                    if (uid.startsWith('B')) {
                        // Heuristic for bot ID
                        try {
                            const botInfo = await client.bots.info({ bot: uid });
                            if (botInfo.ok && botInfo.bot) {
                                userCache.set(uid, botInfo.bot.name || uid); // bot.name
                            }
                            else {
                                logger.warn(`[SlackSkills_Enrich] bots.info call not ok for bot ${uid}: ${botInfo.error}`);
                                userCache.set(uid, uid);
                            }
                        }
                        catch (botError) {
                            logger.warn(`[SlackSkills_Enrich] Failed to fetch info for bot ${uid} via bots.info: ${botError.message}`);
                            userCache.set(uid, uid);
                        }
                    }
                    else {
                        logger.warn(`[SlackSkills_Enrich] users.info call not ok for ${uid}: ${response.error}`);
                        userCache.set(uid, uid);
                    }
                }
            }
            catch (e) {
                logger.warn(`[SlackSkills_Enrich] Failed to fetch info for user/bot ${uid}: ${e.message}`);
                userCache.set(uid, uid);
            }
        }));
    }
    if (channelIdsToFetch.size > 0) {
        logger.debug(`[SlackSkills_Enrich] Fetching info for ${channelIdsToFetch.size} channel IDs.`);
        await Promise.allSettled(Array.from(channelIdsToFetch).map(async (cid) => {
            if (channelCache.has(cid))
                return;
            try {
                const convInfo = await client.conversations.info({ channel: cid });
                if (convInfo.ok && convInfo.channel) {
                    let cName = convInfo.channel.name;
                    if (!cName &&
                        convInfo.channel.is_im &&
                        convInfo.channel.user) {
                        const otherUserId = convInfo.channel.user;
                        if (userCache.has(otherUserId)) {
                            cName = userCache.get(otherUserId) || otherUserId;
                        }
                        else {
                            try {
                                const dmUserInfo = await client.users.info({
                                    user: otherUserId,
                                });
                                if (dmUserInfo.ok && dmUserInfo.user) {
                                    const name = dmUserInfo.user.real_name ||
                                        dmUserInfo.user.name ||
                                        otherUserId;
                                    userCache.set(otherUserId, name);
                                    cName = name;
                                }
                                else {
                                    cName = otherUserId;
                                }
                            }
                            catch (userFetchErr) {
                                logger.warn(`[SlackSkills_Enrich] Failed to fetch user info for DM partner ${otherUserId} in channel ${cid}`);
                                cName = otherUserId;
                            }
                        }
                    }
                    channelCache.set(cid, cName || cid);
                }
                else {
                    logger.warn(`[SlackSkills_Enrich] conversations.info call not ok for ${cid}: ${convInfo.error}`);
                    channelCache.set(cid, cid);
                }
            }
            catch (e) {
                logger.warn(`[SlackSkills_Enrich] Failed to fetch info for channel ${cid}: ${e.message}`);
                channelCache.set(cid, cid);
            }
        }));
    }
    return messages.map((msg) => {
        const enrichedMsg = { ...msg };
        if (msg.userId && userCache.has(msg.userId)) {
            enrichedMsg.userName = userCache.get(msg.userId) || msg.userId;
        }
        else if (msg.botId && userCache.has(msg.botId)) {
            // Check botId against userCache too
            enrichedMsg.userName = userCache.get(msg.botId) || msg.botId; // Bot name
        }
        else if (msg.userId) {
            enrichedMsg.userName = msg.userId;
        }
        else if (msg.botId) {
            enrichedMsg.userName = `Bot (${msg.botId})`;
        }
        if (msg.channelId && channelCache.has(msg.channelId)) {
            enrichedMsg.channelName =
                channelCache.get(msg.channelId) || msg.channelId;
        }
        else if (msg.channelId && !enrichedMsg.channelName) {
            enrichedMsg.channelName = msg.channelId;
        }
        return enrichedMsg;
    });
}
export async function listSlackChannels(userId, limit = 100, cursor) {
    logger.debug(`[SlackSkills] listSlackChannels called by userId: ${userId}, limit: ${limit}, cursor: ${cursor}`);
    const client = await getSlackClient(userId);
    if (!client) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Slack Bot Token not configured.',
            },
        };
    }
    try {
        const result = await client.conversations.list({
            limit: limit,
            cursor: cursor,
            types: 'public_channel,private_channel,mpim,im',
            exclude_archived: true,
        });
        if (!result.ok || !result.channels) {
            const slackError = result.error || 'unknown_slack_api_error';
            logger.error(`[SlackSkills] Slack API error while listing channels (result.ok is false): ${slackError}`);
            return {
                ok: false,
                error: {
                    code: 'SLACK_API_ERROR',
                    message: `Failed to list channels: ${slackError}`,
                    details: result,
                },
            };
        }
        return {
            ok: true,
            data: {
                channels: result.channels || [],
                nextPageCursor: result.response_metadata?.next_cursor,
            },
        };
    }
    catch (error) {
        logger.error(`[SlackSkills] Error listing Slack channels for userId ${userId}:`, error);
        if (error instanceof SlackAPIError) {
            return {
                ok: false,
                error: {
                    code: error.code || 'SLACK_API_ERROR',
                    message: error.data?.error ||
                        error.message ||
                        'Slack API error while listing channels',
                    details: error.data,
                },
            };
        }
        return {
            ok: false,
            error: {
                code: 'INTERNAL_ERROR',
                message: 'Failed to list Slack channels due to an unexpected error.',
                details: error.message,
            },
        };
    }
}
async function getChannelIdByNameOrUser(client, identifier, userIdForContext) {
    logger.debug(`[SlackSkills] getChannelIdByNameOrUser called for identifier: ${identifier}`);
    if (identifier.startsWith('#')) {
        const channelName = identifier.substring(1);
        let cursor = undefined;
        let attempts = 0;
        try {
            while (attempts < 10) {
                const response = await listSlackChannels(userIdForContext, 200, cursor);
                if (!response.ok || !response.data?.channels) {
                    logger.error(`[SlackSkills] Error fetching channels to find ID for "#${channelName}":`, response.error);
                    return {
                        ok: false,
                        error: response.error || {
                            code: 'LOOKUP_FAILED',
                            message: 'Failed to list channels during ID lookup.',
                        },
                    };
                }
                const foundChannel = response.data.channels.find((ch) => ch.name === channelName && (ch.is_channel || ch.is_group));
                if (foundChannel?.id)
                    return { ok: true, data: foundChannel.id };
                cursor = response.data.nextPageCursor;
                if (!cursor)
                    break;
                attempts++;
            }
            logger.warn(`[SlackSkills] Channel "#${channelName}" not found.`);
            return { ok: true, data: null };
        }
        catch (error) {
            logger.error(`[SlackSkills] Exception in getChannelIdByNameOrUser for "#${channelName}":`, error);
            return {
                ok: false,
                error: {
                    code: 'INTERNAL_ERROR',
                    message: `Exception looking up channel ID: ${error.message}`,
                    details: error,
                },
            };
        }
    }
    else if (identifier.startsWith('@')) {
        const userNameOrId = identifier.substring(1);
        try {
            if (isSlackId(userNameOrId)) {
                const dmResponse = await client.conversations.open({
                    users: userNameOrId,
                });
                if (dmResponse.ok && dmResponse.channel?.id) {
                    return { ok: true, data: dmResponse.channel.id };
                }
                else {
                    logger.error(`[SlackSkills] Failed to open DM with user ID "${userNameOrId}": ${dmResponse.error}`);
                    return {
                        ok: false,
                        error: {
                            code: 'DM_OPEN_FAILED',
                            message: `Could not open DM with ${userNameOrId}. Error: ${dmResponse.error}`,
                        },
                    };
                }
            }
            logger.warn(`[SlackSkills] Identifier "${identifier}" for DM is not a user ID. Robust name-to-ID resolution for DMs is not implemented in this helper.`);
            return {
                ok: true,
                data: null,
                error: {
                    code: 'USER_RESOLUTION_NEEDED',
                    message: `Could not resolve DM for user name ${userNameOrId} directly. User ID needed.`,
                },
            };
        }
        catch (error) {
            logger.error(`[SlackSkills] Exception trying to open DM for "${identifier}":`, error);
            return {
                ok: false,
                error: {
                    code: 'INTERNAL_ERROR',
                    message: `Exception opening DM: ${error.message}`,
                    details: error,
                },
            };
        }
    }
    logger.warn(`[SlackSkills] Channel identifier "${identifier}" format not recognized for ID resolution (expected #channel or @user).`);
    return { ok: true, data: null };
}
export async function sendSlackMessage(userId, channelIdentifier, text) {
    logger.debug(`[SlackSkills] sendSlackMessage called by userId: ${userId} to channelIdentifier: ${channelIdentifier}, text: "${text.substring(0, 50)}..."`);
    const client = await getSlackClient(userId);
    if (!client) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Slack Bot Token not configured.',
            },
        };
    }
    if (!channelIdentifier || !text) {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Channel identifier and text are required.',
            },
        };
    }
    let targetChannelId = channelIdentifier;
    if (!isSlackId(channelIdentifier)) {
        logger.debug(`[SlackSkills] Channel identifier "${channelIdentifier}" is not an ID. Attempting to resolve...`);
        const idResponse = await getChannelIdByNameOrUser(client, channelIdentifier, userId);
        if (!idResponse.ok) {
            logger.error(`[SlackSkills] Failed to resolve channel identifier "${channelIdentifier}":`, idResponse.error);
            return {
                ok: false,
                error: idResponse.error || {
                    code: 'CHANNEL_RESOLUTION_FAILED',
                    message: `Could not resolve channel identifier ${channelIdentifier}.`,
                },
            };
        }
        if (!idResponse.data) {
            logger.warn(`[SlackSkills] Channel identifier "${channelIdentifier}" not found or could not be resolved to an ID.`);
            return {
                ok: false,
                error: {
                    code: 'CHANNEL_NOT_FOUND',
                    message: `Channel or user "${channelIdentifier}" not found.`,
                },
            };
        }
        targetChannelId = idResponse.data;
        logger.debug(`[SlackSkills] Resolved identifier "${channelIdentifier}" to ID "${targetChannelId}"`);
    }
    try {
        const result = await client.chat.postMessage({
            channel: targetChannelId,
            text: text,
        });
        if (!result.ok || !result.ts) {
            const slackError = result.error || 'unknown_slack_api_error_on_post';
            logger.error(`[SlackSkills] Slack API error sending message to channel ${targetChannelId}: ${slackError}`);
            return {
                ok: false,
                error: {
                    code: 'SLACK_API_ERROR',
                    message: `Failed to send message: ${slackError}`,
                    details: result,
                },
            };
        }
        logger.info(`[SlackSkills] Message sent successfully to channel ${targetChannelId} by user ${userId}. TS: ${result.ts}`);
        return {
            ok: true,
            data: {
                ts: result.ts,
                channel: result.channel,
                message: result.message,
            },
        };
    }
    catch (error) {
        logger.error(`[SlackSkills] Error sending Slack message for userId ${userId} to channel ${targetChannelId}:`, error);
        if (error instanceof SlackAPIError) {
            return {
                ok: false,
                error: {
                    code: error.code || 'SLACK_API_ERROR',
                    message: error.data?.error ||
                        error.message ||
                        'Slack API error sending message',
                    details: error.data,
                },
            };
        }
        return {
            ok: false,
            error: {
                code: 'INTERNAL_ERROR',
                message: 'Failed to send Slack message due to an unexpected error.',
                details: error.message,
            },
        };
    }
}
/**
 * Searches Slack messages for the user using the Slack Web API.
 * @param atomUserId The Atom internal ID of the user making the request (for logging/context).
 * @param searchQuery The Slack API compatible search query string.
 * @param limit Max number of messages to return.
 * @returns A promise resolving to an array of SlackMessage objects.
 */
export async function searchMySlackMessages(atomUserId, searchQuery, limit = 10) {
    logger.debug(`[SlackSkills] searchMySlackMessages direct API call for Atom user ${atomUserId}, query: "${searchQuery}", limit: ${limit}`);
    const client = await getSlackClient(atomUserId);
    if (!client) {
        logger.error('[SlackSkills] Slack client not available for searchMySlackMessages.');
        return [];
    }
    try {
        const response = await client.search.messages({
            query: searchQuery,
            count: limit,
            sort: 'timestamp',
            sort_dir: 'desc',
        });
        if (!response.ok || !response.messages?.matches) {
            const slackError = response.error || 'unknown_slack_search_error';
            logger.error(`[SlackSkills] Slack API error during search.messages: ${slackError}`, response);
            return [];
        }
        let results = (response.messages.matches || []).map((match) => {
            return {
                id: match.ts,
                threadId: match.thread_ts || undefined,
                userId: match.user,
                userName: match.username || match.user,
                botId: match.bot_id,
                channelId: match.channel?.id,
                channelName: match.channel?.name || match.channel?.id,
                text: match.text,
                blocks: match.blocks,
                files: match.files,
                reactions: match.reactions,
                timestamp: new Date(parseFloat(match.ts) * 1000).toISOString(),
                permalink: match.permalink,
                raw: match,
            };
        });
        if (results.length > 0) {
            const userCache = new Map();
            const channelCache = new Map();
            results = await _enrichSlackMessagesWithNames(client, results, userCache, channelCache);
        }
        logger.info(`[SlackSkills] searchMySlackMessages direct API call found and enriched ${results.length} messages.`);
        return results;
    }
    catch (error) {
        logger.error(`[SlackSkills] Error in searchMySlackMessages direct API call for Atom user ${atomUserId}, query "${searchQuery}":`, error);
        if (error instanceof SlackAPIError) {
            logger.error(`[SlackSkills] SlackAPIError code: ${error.code}, data:`, error.data);
        }
        return [];
    }
}
/**
 * Reads the detailed content of a specific Slack message using Slack Web API.
 * @param atomUserId The Atom internal ID of the user (for logging/context).
 * @param channelId The ID of the channel containing the message.
 * @param messageTs The timestamp (ID) of the message.
 * @returns A promise resolving to a SlackMessage object or null if not found/error.
 */
export async function readSlackMessage(atomUserId, channelId, messageTs) {
    logger.debug(`[SlackSkills] readSlackMessage direct API call for Atom user ${atomUserId}, channelId: ${channelId}, messageTs: ${messageTs}`);
    const client = await getSlackClient(atomUserId);
    if (!client) {
        logger.error('[SlackSkills] Slack client not available for readSlackMessage.');
        return null;
    }
    try {
        const response = await client.conversations.history({
            channel: channelId,
            latest: messageTs,
            oldest: messageTs,
            inclusive: true,
            limit: 1,
        });
        if (!response.ok || !response.messages || response.messages.length === 0) {
            const slackError = response.error || 'message_not_found_or_access_denied';
            logger.warn(`[SlackSkills] Slack API error or message not found during conversations.history for ts ${messageTs} in channel ${channelId}: ${slackError}`, response);
            return null;
        }
        const msgData = response.messages[0];
        let permalink;
        try {
            const permalinkResponse = await client.chat.getPermalink({
                channel: channelId,
                message_ts: msgData.ts,
            });
            if (permalinkResponse.ok && permalinkResponse.permalink) {
                permalink = permalinkResponse.permalink;
            }
        }
        catch (permalinkError) {
            logger.warn(`[SlackSkills] Could not fetch permalink for message ${msgData.ts} in channel ${channelId}:`, permalinkError);
        }
        let message = {
            id: msgData.ts,
            threadId: msgData.thread_ts || undefined,
            userId: msgData.user,
            userName: msgData.username || msgData.user,
            botId: msgData.bot_id,
            channelId: channelId,
            channelName: channelId, // Placeholder
            text: msgData.text,
            blocks: msgData.blocks,
            files: msgData.files,
            reactions: msgData.reactions,
            timestamp: new Date(parseFloat(msgData.ts) * 1000).toISOString(),
            permalink: permalink,
            raw: msgData,
        };
        const userCache = new Map();
        const channelCache = new Map();
        const enrichedMessages = await _enrichSlackMessagesWithNames(client, [message], userCache, channelCache);
        logger.info(`[SlackSkills] Successfully read and enriched Slack message ${messageTs} from channel ${channelId}.`);
        return enrichedMessages.length > 0 ? enrichedMessages[0] : null;
    }
    catch (error) {
        logger.error(`[SlackSkills] Error in readSlackMessage direct API call for Atom user ${atomUserId}, channel ${channelId}, ts ${messageTs}:`, error);
        if (error instanceof SlackAPIError) {
            logger.error(`[SlackSkills] SlackAPIError code: ${error.code}, data:`, error.data);
        }
        return null;
    }
}
// ... LLM extraction code and getRecentDMsAndMentionsForBriefing follow ...
// getRecentDMsAndMentionsForBriefing will also benefit from enriched messages returned by searchMySlackMessages.
import OpenAI from 'openai';
import { ATOM_OPENAI_API_KEY, ATOM_NLU_MODEL_NAME } from '../_libs/constants';
let openAIClientForSlackExtraction = null;
function getSlackExtractionOpenAIClient() {
    if (openAIClientForSlackExtraction) {
        return openAIClientForSlackExtraction;
    }
    if (!ATOM_OPENAI_API_KEY) {
        logger.error('[SlackSkills] OpenAI API Key not configured for LLM Slack Extractor.');
        throw new Error('OpenAI API Key not configured for LLM Slack Extractor.');
    }
    openAIClientForSlackExtraction = new OpenAI({ apiKey: ATOM_OPENAI_API_KEY });
    logger.info('[SlackSkills] OpenAI client for Slack extraction initialized.');
    return openAIClientForSlackExtraction;
}
// System prompt for extracting info from Slack messages.
// This is very similar to the email one, but could be tailored more for Slack's typical message style (e.g. mentions, threads, emojis).
const SLACK_EXTRACTION_SYSTEM_PROMPT_TEMPLATE = `
You are an expert system designed to extract specific pieces of information from a Slack message body.
The user will provide a message body and a list of information points they are looking for (keywords).
For each keyword, find the corresponding information in the message body.
Respond ONLY with a single, valid JSON object. Do not include any explanatory text before or after the JSON.
The JSON object should have keys corresponding to the user's original keywords.
The value for each key should be the extracted information as a string.
If a specific piece of information for a keyword is not found in the message body, the value for that key should be null.

Example:
User provides keywords: ["task assigned to", "due date", "project name"]
Message body: "Hey @anna can you take on the 'UI design for Project Phoenix'? Needs to be done by next Friday."
Your JSON response:
{
  "task assigned to": "@anna",
  "due date": "next Friday",
  "project name": "Project Phoenix"
}

If information for a keyword is not found, use null for its value.
The keywords you need to extract information for are: {{KEYWORDS_JSON_ARRAY_STRING}}
Extract the information from the Slack message body provided by the user.
`;
/**
 * Uses an LLM to extract specific pieces of information from a Slack message body
 * based on a list of keywords or concepts.
 * @param messageText The plain text content of the Slack message.
 * @param infoKeywords An array of strings representing the concepts/keywords to search for.
 * @returns A Promise resolving to a record where keys are infoKeywords and values are the extracted strings (or null).
 */
export async function extractInformationFromSlackMessage(messageText, infoKeywords) {
    if (!infoKeywords || infoKeywords.length === 0) {
        logger.debug('[SlackSkills] extractInformationFromSlackMessage: No infoKeywords provided.');
        return {};
    }
    if (!messageText || messageText.trim() === '') {
        logger.debug('[SlackSkills] extractInformationFromSlackMessage: Empty messageText provided.');
        const emptyResult = {};
        infoKeywords.forEach((kw) => (emptyResult[kw] = null));
        return emptyResult;
    }
    logger.debug(`[SlackSkills] LLM Extractor: Attempting to extract from Slack message for keywords: [${infoKeywords.join(', ')}]`);
    const client = getSlackExtractionOpenAIClient();
    const keywordsJsonArrayString = JSON.stringify(infoKeywords);
    const systemPrompt = SLACK_EXTRACTION_SYSTEM_PROMPT_TEMPLATE.replace('{{KEYWORDS_JSON_ARRAY_STRING}}', keywordsJsonArrayString);
    const messages = [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: `Slack Message Body:\n---\n${messageText}\n---` },
    ];
    try {
        const completion = await client.chat.completions.create({
            model: ATOM_NLU_MODEL_NAME, // Or a more capable model
            messages: messages,
            temperature: 0.1,
            response_format: { type: 'json_object' },
        });
        const llmResponse = completion.choices[0]?.message?.content;
        if (!llmResponse) {
            logger.error('[SlackSkills] LLM Extractor: Received an empty response from AI for Slack message.');
            throw new Error('LLM Extractor (Slack): Empty response from AI.');
        }
        logger.debug('[SlackSkills] LLM Extractor: Raw LLM JSON response for Slack:', llmResponse);
        const parsedResponse = JSON.parse(llmResponse);
        const result = {};
        for (const keyword of infoKeywords) {
            result[keyword] = parsedResponse.hasOwnProperty(keyword)
                ? parsedResponse[keyword]
                : null;
        }
        logger.debug('[SlackSkills] LLM Extractor: Parsed and reconciled extraction from Slack:', result);
        return result;
    }
    catch (error) {
        logger.error('[SlackSkills] LLM Extractor: Error processing information extraction from Slack message with OpenAI:', error.message);
        if (error instanceof SyntaxError) {
            logger.error('[SlackSkills] LLM Extractor: Failed to parse JSON response from LLM for Slack message.');
            throw new Error('LLM Extractor (Slack): Failed to parse response from AI.');
        }
        // Fallback to return null for all keywords if LLM fails
        const fallbackResult = {};
        infoKeywords.forEach((kw) => (emptyResult[kw] = null));
        return fallbackResult;
    }
}
export async function getRecentDMsAndMentionsForBriefing(atomUserId, // Atom's internal user ID
targetDate, count = 3) {
    logger.debug(`[SlackSkills] getRecentDMsAndMentionsForBriefing for Atom user: ${atomUserId}, TargetDate: ${targetDate.toISOString().split('T')[0]}, Count: ${count}`);
    const client = await getSlackClient(atomUserId);
    if (!client) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Slack Bot Token not configured.',
            },
        };
    }
    try {
        let userSlackId;
        try {
            const authTestResponse = await client.auth.test();
            if (authTestResponse.ok && authTestResponse.user_id) {
                userSlackId = authTestResponse.user_id;
                logger.info(`[SlackSkills] Resolved Slack user ID for search: ${userSlackId}`);
            }
            else {
                logger.warn(`[SlackSkills] Could not resolve Slack user ID via auth.test. Mentions search might be impacted. Error: ${authTestResponse.error}`);
            }
        }
        catch (authError) {
            logger.warn(`[SlackSkills] Exception during client.auth.test: ${authError.message}. Mentions search might be impacted.`);
        }
        const formatDateForSlack = (date) => {
            const year = date.getUTCFullYear();
            const month = (date.getUTCMonth() + 1).toString().padStart(2, '0');
            const day = date.getUTCDate().toString().padStart(2, '0');
            return `${year}-${month}-${day}`;
        };
        const afterDate = new Date(targetDate);
        afterDate.setUTCHours(0, 0, 0, 0);
        const beforeDate = new Date(targetDate);
        beforeDate.setUTCHours(0, 0, 0, 0);
        beforeDate.setUTCDate(targetDate.getUTCDate() + 1);
        let querySegments = [];
        if (userSlackId) {
            querySegments.push(`(@${userSlackId} OR to:${userSlackId} OR in:${userSlackId})`);
        }
        else {
            querySegments.push(`(is:dm)`);
            logger.warn('[SlackSkills] No specific Slack User ID for DMs/Mentions search, results might be less targeted if using a bot token without specific user context for DMs.');
        }
        querySegments.push(`after:${formatDateForSlack(afterDate)}`);
        querySegments.push(`before:${formatDateForSlack(beforeDate)}`);
        const searchQuery = querySegments.join(' ');
        const fullSearchQueryWithSort = `${searchQuery} sort:timestamp dir:desc`;
        logger.info(`[SlackSkills] Constructed Slack search query for briefing: "${fullSearchQueryWithSort}"`);
        const searchResults = await searchMySlackMessages(atomUserId, fullSearchQueryWithSort, count);
        logger.info(`[SlackSkills] Found ${searchResults.length} Slack messages for briefing.`);
        return {
            ok: true,
            data: { results: searchResults, query_executed: fullSearchQueryWithSort },
        };
    }
    catch (error) {
        logger.error(`[SlackSkills] Error in getRecentDMsAndMentionsForBriefing for Atom user ${atomUserId}: ${error.message}`, error);
        return {
            ok: false,
            error: {
                code: 'SLACK_BRIEFING_FETCH_FAILED',
                message: error.message || 'Failed to fetch recent DMs/mentions for briefing.',
            },
        };
    }
}
/**
 * Gets a permalink for a specific Slack message using the Slack Web API.
 * @param atomUserId The Atom internal ID of the user (for logging/context).
 * @param channelId The ID of the channel containing the message.
 * @param messageTs The timestamp (ID) of the message.
 * @returns A promise resolving to the permalink string or null if not found/error.
 */
export async function getSlackMessagePermalink(atomUserId, // Atom user ID for context
channelId, messageTs) {
    logger.debug(`[SlackSkills] getSlackMessagePermalink direct API call for Atom user ${atomUserId}, channelId: ${channelId}, messageTs: ${messageTs}`);
    const client = getSlackClient();
    if (!client) {
        logger.error('[SlackSkills] Slack client not available for getSlackMessagePermalink.');
        return null;
    }
    try {
        const response = await client.chat.getPermalink({
            channel: channelId,
            message_ts: messageTs,
        });
        if (!response.ok || !response.permalink) {
            const slackError = response.error || 'permalink_not_found';
            logger.warn(`[SlackSkills] Slack API error or permalink not found for ts ${messageTs} in channel ${channelId}: ${slackError}`, response);
            return null;
        }
        logger.info(`[SlackSkills] Successfully fetched permalink for message ${messageTs}.`);
        return response.permalink;
    }
    catch (error) {
        logger.error(`[SlackSkills] Error in getSlackMessagePermalink direct API call for Atom user ${atomUserId}, channel ${channelId}, ts ${messageTs}:`, error);
        if (error instanceof SlackAPIError) {
            logger.error(`[SlackSkills] SlackAPIError code: ${error.code}, data:`, error.data);
        }
        return null;
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic2xhY2tTa2lsbHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJzbGFja1NraWxscy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxPQUFPLEVBQ0wsU0FBUyxFQUVULGFBQWEsR0FHZCxNQUFNLGdCQUFnQixDQUFDO0FBQ3hCLE9BQU8sRUFBRSxtQkFBbUIsRUFBRSxNQUFNLHdCQUF3QixDQUFDO0FBUzdELE9BQU8sRUFBRSxNQUFNLEVBQUUsTUFBTSxxQkFBcUIsQ0FBQztBQUU3QyxLQUFLLFVBQVUsYUFBYSxDQUFDLE1BQWM7SUFDekMsTUFBTSxLQUFLLEdBQUc7Ozs7OztLQU1YLENBQUM7SUFDSixNQUFNLFNBQVMsR0FBRztRQUNoQixNQUFNO1FBQ04sT0FBTyxFQUFFLE9BQU87S0FDakIsQ0FBQztJQUNGLE1BQU0sUUFBUSxHQUFHLE1BQU0sbUJBQW1CLENBRXZDLEtBQUssRUFBRSxTQUFTLEVBQUUsY0FBYyxFQUFFLE1BQU0sQ0FBQyxDQUFDO0lBQzdDLElBQUksUUFBUSxDQUFDLFdBQVcsSUFBSSxRQUFRLENBQUMsV0FBVyxDQUFDLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztRQUM1RCxPQUFPLFFBQVEsQ0FBQyxXQUFXLENBQUMsQ0FBQyxDQUFDLENBQUMsWUFBWSxDQUFDO0lBQzlDLENBQUM7SUFDRCxPQUFPLElBQUksQ0FBQztBQUNkLENBQUM7QUFFRCxNQUFNLGNBQWMsR0FBRyxLQUFLLEVBQUUsTUFBYyxFQUE2QixFQUFFO0lBQ3pFLE1BQU0sS0FBSyxHQUFHLE1BQU0sYUFBYSxDQUFDLE1BQU0sQ0FBQyxDQUFDO0lBQzFDLElBQUksQ0FBQyxLQUFLLEVBQUUsQ0FBQztRQUNYLE1BQU0sQ0FBQyxLQUFLLENBQUMsK0NBQStDLENBQUMsQ0FBQztRQUM5RCxPQUFPLElBQUksQ0FBQztJQUNkLENBQUM7SUFDRCxPQUFPLElBQUksU0FBUyxDQUFDLEtBQUssQ0FBQyxDQUFDO0FBQzlCLENBQUMsQ0FBQztBQUVGLHdEQUF3RDtB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TUFBTSxDQUFDLElBQUksQ0FDVCw0REFBNEQsU0FBUyxHQUFHLENBQ3pFLENBQUM7UUFDRixPQUFPLFFBQVEsQ0FBQyxTQUFtQixDQUFDO0lBQ3RDLENBQUM7SUFBQyxPQUFPLEtBQVUsRUFBRSxDQUFDO1FBQ3BCLE1BQU0sQ0FBQyxLQUFLLENBQ1YsaUZBQWlGLFVBQVUsYUFBYSxTQUFTLFFBQVEsU0FBUyxHQUFHLEVBQ3JJLEtBQUssQ0FDTixDQUFDO1FBQ0YsSUFBSSxLQUFLLFlBQVksYUFBYSxFQUFFLENBQUM7WUFDbkMsTUFBTSxDQUFDLEtBQUssQ0FDVixxQ0FBcUMsS0FBSyxDQUFDLElBQUksU0FBUyxFQUN4RCxLQUFLLENBQUMsSUFBSSxDQUNYLENBQUM7UUFDSixDQUFDO1FBQ0QsT0FBTyxJQUFJLENBQUM7SUFDZCxDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7XG4gIFdlYkNsaWVudCxcbiAgRXJyb3JDb2RlIGFzIFNsYWNrRXJyb3JDb2RlLFxuICBTbGFja0FQSUVycm9yLFxuICBDb252ZXJzYXRpb25zTGlzdFJlc3BvbnNlLFxuICBDaGF0UG9zdE1lc3NhZ2VSZXNwb25zZSxcbn0gZnJvbSAnQHNsYWNrL3dlYi1hcGknO1xuaW1wb3J0IHsgZXhlY3V0ZUdyYXBoUUxRdWVyeSB9IGZyb20gJy4uL19saWJzL2dyYXBocWxDbGllbnQnO1xuaW1wb3J0IHtcbiAgU2xhY2tTa2lsbFJlc3BvbnNlLFxuICBTbGFja0NoYW5uZWwsXG4gIFNsYWNrTWVzc2FnZURhdGEsXG4gIExpc3RTbGFja0NoYW5uZWxzRGF0YSxcbiAgU2tpbGxFcnJvcixcbiAgU2xhY2tNZXNzYWdlLFxufSBmcm9tICcuLi90eXBlcyc7XG5pbXBvcnQgeyBsb2dnZXIgfSBmcm9tICcuLi8uLi9fdXRpbHMvbG9nZ2VyJztcblxuYXN5bmMgZnVuY3Rpb24gZ2V0U2xhY2tUb2tlbih1c2VySWQ6IHN0cmluZyk6IFByb21pc2U8c3RyaW5nIHwgbnVsbD4ge1xuICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgcXVlcnkgR2V0VXNlclRva2VuKCR1c2VySWQ6IFN0cmluZyEsICRzZXJ2aWNlOiBTdHJpbmchKSB7XG4gICAgICAgICAgICB1c2VyX3Rva2Vucyh3aGVyZToge3VzZXJfaWQ6IHtfZXE6ICR1c2VySWR9LCBzZXJ2aWNlOiB7X2VxOiAkc2VydmljZX19KSB7XG4gICAgICAgICAgICAgICAgYWNjZXNzX3Rva2VuXG4gICAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICBgO1xuICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgdXNlcklkLFxuICAgIHNlcnZpY2U6ICdzbGFjaycsXG4gIH07XG4gIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZXhlY3V0ZUdyYXBoUUxRdWVyeTx7XG4gICAgdXNlcl90b2tlbnM6IHsgYWNjZXNzX3Rva2VuOiBzdHJpbmcgfVtdO1xuICB9PihxdWVyeSwgdmFyaWFibGVzLCAnR2V0VXNlclRva2VuJywgdXNlcklkKTtcbiAgaWYgKHJlc3BvbnNlLnVzZXJfdG9rZW5zICYmIHJlc3BvbnNlLnVzZXJfdG9rZW5zLmxlbmd0aCA+IDApIHtcbiAgICByZXR1cm4gcmVzcG9uc2UudXNlcl90b2tlbnNbMF0uYWNjZXNzX3Rva2VuO1xuICB9XG4gIHJldHVybiBudWxsO1xufVxuXG5jb25zdCBnZXRTbGFja0NsaWVudCA9IGFzeW5jICh1c2VySWQ6IHN0cmluZyk6IFByb21pc2U8V2ViQ2xpZW50IHwgbnVsbD4gPT4ge1xuICBjb25zdCB0b2tlbiA9IGF3YWl0IGdldFNsYWNrVG9rZW4odXNlcklkKTtcbiAgaWYgKCF0b2tlbikge1xuICAgIGxvZ2dlci5lcnJvcignW1NsYWNrU2tpbGxzXSBTbGFjayB0b2tlbiBub3QgZm91bmQgZm9yIHVzZXIuJyk7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cbiAgcmV0dXJuIG5ldyBXZWJDbGllbnQodG9rZW4pO1xufTtcblxuLy8gSGVscGVyIHRvIGRldGVybWluZSBpZiBhIHN0cmluZyBsb29rcyBsaWtlIGEgU2xhY2sgSURcbmZ1bmN0aW9uIGlzU2xhY2tJZChpZDogc3RyaW5nKTogYm9vbGVhbiB7XG4gIGlmICghaWQpIHJldHVybiBmYWxzZTtcbiAgcmV0dXJuIC9eW1VDR0RXRl1bQS1aMC05XXs4LDEwfSQvLnRlc3QoaWQpO1xufVxuXG4vLyAtLS0gSGVscGVyIGZ1bmN0aW9uIHRvIGVucmljaCBTbGFjayBtZXNzYWdlcyB3aXRoIHVzZXIgYW5kIGNoYW5uZWwgbmFtZXMgLS0tXG5hc3luYyBmdW5jdGlvbiBfZW5yaWNoU2xhY2tNZXNzYWdlc1dpdGhOYW1lcyhcbiAgY2xpZW50OiBXZWJDbGllbnQsXG4gIG1lc3NhZ2VzOiBTbGFja01lc3NhZ2VbXSxcbiAgdXNlckNhY2hlOiBNYXA8c3RyaW5nLCBzdHJpbmcgfCBudWxsPixcbiAgY2hhbm5lbENhY2hlOiBNYXA8c3RyaW5nLCBzdHJpbmcgfCBudWxsPlxuKTogUHJvbWlzZTxTbGFja01lc3NhZ2VbXT4ge1xuICBjb25zdCB1c2VySWRzVG9GZXRjaCA9IG5ldyBTZXQ8c3RyaW5nPigpO1xuICBjb25zdCBjaGFubmVsSWRzVG9GZXRjaCA9IG5ldyBTZXQ8c3RyaW5nPigpO1xuXG4gIGZvciAoY29uc3QgbXNnIG9mIG1lc3NhZ2VzKSB7XG4gICAgaWYgKG1zZy51c2VySWQgJiYgIW1zZy51c2VyTmFtZSAmJiAhdXNlckNhY2hlLmhhcyhtc2cudXNlcklkKSkge1xuICAgICAgdXNlcklkc1RvRmV0Y2guYWRkKG1zZy51c2VySWQpO1xuICAgIH1cbiAgICBpZiAobXNnLmJvdElkICYmICFtc2cudXNlck5hbWUgJiYgIXVzZXJDYWNoZS5oYXMobXNnLmJvdElkKSkge1xuICAgICAgLy8gQWxzbyB0cnkgdG8gcmVzb2x2ZSBib3QgbmFtZXNcbiAgICAgIHVzZXJJZHNUb0ZldGNoLmFkZChtc2cuYm90SWQpOyAvLyBTbGFjaydzIHVzZXJzLmluZm8gd29ya3MgZm9yIGJvdCBJRHMgdG9vXG4gICAgfVxuICAgIGlmIChtc2cuY2hhbm5lbElkICYmICFtc2cuY2hhbm5lbE5hbWUgJiYgIWNoYW5uZWxDYWNoZS5oYXMobXNnLmNoYW5uZWxJZCkpIHtcbiAgICAgIGNoYW5uZWxJZHNUb0ZldGNoLmFkZChtc2cuY2hhbm5lbElkKTtcbiAgICB9XG4gIH1cblxuICBpZiAodXNlcklkc1RvRmV0Y2guc2l6ZSA+IDApIHtcbiAgICBsb2dnZXIuZGVidWcoXG4gICAgICBgW1NsYWNrU2tpbGxzX0VucmljaF0gRmV0Y2hpbmcgaW5mbyBmb3IgJHt1c2VySWRzVG9GZXRjaC5zaXplfSB1c2VyL2JvdCBJRHMuYFxuICAgICk7XG4gICAgYXdhaXQgUHJvbWlzZS5hbGxTZXR0bGVkKFxuICAgICAgQXJyYXkuZnJvbSh1c2VySWRzVG9GZXRjaCkubWFwKGFzeW5jICh1aWQpID0+IHtcbiAgICAgICAgaWYgKHVzZXJDYWNoZS5oYXModWlkKSkgcmV0dXJuO1xuICAgICAgICB0cnkge1xuICAgICAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgY2xpZW50LnVzZXJzLmluZm8oeyB1c2VyOiB1aWQgfSk7XG4gICAgICAgICAgaWYgKHJlc3BvbnNlLm9rICYmIHJlc3BvbnNlLnVzZXIpIHtcbiAgICAgICAgICAgIHVzZXJDYWNoZS5zZXQoXG4gICAgICAgICAgICAgIHVpZCxcbiAgICAgICAgICAgICAgcmVzcG9uc2UudXNlci5yZWFsX25hbWUgfHwgcmVzcG9uc2UudXNlci5uYW1lIHx8IHVpZFxuICAgICAgICAgICAgKTtcbiAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgLy8gQ2hlY2sgZm9yIGJvdF9pbmZvIGlmIHVzZXJzLmluZm8gZmFpbHMgZm9yIGEgYm90X2lkXG4gICAgICAgICAgICBpZiAodWlkLnN0YXJ0c1dpdGgoJ0InKSkge1xuICAgICAgICAgICAgICAvLyBIZXVyaXN0aWMgZm9yIGJvdCBJRFxuICAgICAgICAgICAgICB0cnkge1xuICAgICAgICAgICAgICAgIGNvbnN0IGJvdEluZm8gPSBhd2FpdCBjbGllbnQuYm90cy5pbmZvKHsgYm90OiB1aWQgfSk7XG4gICAgICAgICAgICAgICAgaWYgKGJvdEluZm8ub2sgJiYgYm90SW5mby5ib3QpIHtcbiAgICAgICAgICAgICAgICAgIHVzZXJDYWNoZS5zZXQodWlkLCAoYm90SW5mby5ib3QgYXMgYW55KS5uYW1lIHx8IHVpZCk7IC8vIGJvdC5uYW1lXG4gICAgICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICAgICAgICAgICAgICBgW1NsYWNrU2tpbGxzX0VucmljaF0gYm90cy5pbmZvIGNhbGwgbm90IG9rIGZvciBib3QgJHt1aWR9OiAke2JvdEluZm8uZXJyb3J9YFxuICAgICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgICAgICAgIHVzZXJDYWNoZS5zZXQodWlkLCB1aWQpO1xuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgfSBjYXRjaCAoYm90RXJyb3I6IGFueSkge1xuICAgICAgICAgICAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICAgICAgICAgICAgYFtTbGFja1NraWxsc19FbnJpY2hdIEZhaWxlZCB0byBmZXRjaCBpbmZvIGZvciBib3QgJHt1aWR9IHZpYSBib3RzLmluZm86ICR7Ym90RXJyb3IubWVzc2FnZX1gXG4gICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgICAgICB1c2VyQ2FjaGUuc2V0KHVpZCwgdWlkKTtcbiAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgICAgICAgICAgYFtTbGFja1NraWxsc19FbnJpY2hdIHVzZXJzLmluZm8gY2FsbCBub3Qgb2sgZm9yICR7dWlkfTogJHtyZXNwb25zZS5lcnJvcn1gXG4gICAgICAgICAgICAgICk7XG4gICAgICAgICAgICAgIHVzZXJDYWNoZS5zZXQodWlkLCB1aWQpO1xuICAgICAgICAgICAgfVxuICAgICAgICAgIH1cbiAgICAgICAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgICAgICBgW1NsYWNrU2tpbGxzX0VucmljaF0gRmFpbGVkIHRvIGZldGNoIGluZm8gZm9yIHVzZXIvYm90ICR7dWlkfTogJHtlLm1lc3NhZ2V9YFxuICAgICAgICAgICk7XG4gICAgICAgICAgdXNlckNhY2hlLnNldCh1aWQsIHVpZCk7XG4gICAgICAgIH1cbiAgICAgIH0pXG4gICAgKTtcbiAgfVxuXG4gIGlmIChjaGFubmVsSWRzVG9GZXRjaC5zaXplID4gMCkge1xuICAgIGxvZ2dlci5kZWJ1ZyhcbiAgICAgIGBbU2xhY2tTa2lsbHNfRW5yaWNoXSBGZXRjaGluZyBpbmZvIGZvciAke2NoYW5uZWxJZHNUb0ZldGNoLnNpemV9IGNoYW5uZWwgSURzLmBcbiAgICApO1xuICAgIGF3YWl0IFByb21pc2UuYWxsU2V0dGxlZChcbiAgICAgIEFycmF5LmZyb20oY2hhbm5lbElkc1RvRmV0Y2gpLm1hcChhc3luYyAoY2lkKSA9PiB7XG4gICAgICAgIGlmIChjaGFubmVsQ2FjaGUuaGFzKGNpZCkpIHJldHVybjtcbiAgICAgICAgdHJ5IHtcbiAgICAgICAgICBjb25zdCBjb252SW5mbyA9IGF3YWl0IGNsaWVudC5jb252ZXJzYXRpb25zLmluZm8oeyBjaGFubmVsOiBjaWQgfSk7XG4gICAgICAgICAgaWYgKGNvbnZJbmZvLm9rICYmIGNvbnZJbmZvLmNoYW5uZWwpIHtcbiAgICAgICAgICAgIGxldCBjTmFtZSA9IChjb252SW5mby5jaGFubmVsIGFzIGFueSkubmFtZTtcbiAgICAgICAgICAgIGlmIChcbiAgICAgICAgICAgICAgIWNOYW1lICYmXG4gICAgICAgICAgICAgIChjb252SW5mby5jaGFubmVsIGFzIGFueSkuaXNfaW0gJiZcbiAgICAgICAgICAgICAgKGNvbnZJbmZvLmNoYW5uZWwgYXMgYW55KS51c2VyXG4gICAgICAgICAgICApIHtcbiAgICAgICAgICAgICAgY29uc3Qgb3RoZXJVc2VySWQgPSAoY29udkluZm8uY2hhbm5lbCBhcyBhbnkpLnVzZXI7XG4gICAgICAgICAgICAgIGlmICh1c2VyQ2FjaGUuaGFzKG90aGVyVXNlcklkKSkge1xuICAgICAgICAgICAgICAgIGNOYW1lID0gdXNlckNhY2hlLmdldChvdGhlclVzZXJJZCkgfHwgb3RoZXJVc2VySWQ7XG4gICAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgICAgICAgIGNvbnN0IGRtVXNlckluZm8gPSBhd2FpdCBjbGllbnQudXNlcnMuaW5mbyh7XG4gICAgICAgICAgICAgICAgICAgIHVzZXI6IG90aGVyVXNlcklkLFxuICAgICAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICAgICAgICBpZiAoZG1Vc2VySW5mby5vayAmJiBkbVVzZXJJbmZvLnVzZXIpIHtcbiAgICAgICAgICAgICAgICAgICAgY29uc3QgbmFtZSA9XG4gICAgICAgICAgICAgICAgICAgICAgZG1Vc2VySW5mby51c2VyLnJlYWxfbmFtZSB8fFxuICAgICAgICAgICAgICAgICAgICAgIGRtVXNlckluZm8udXNlci5uYW1lIHx8XG4gICAgICAgICAgICAgICAgICAgICAgb3RoZXJVc2VySWQ7XG4gICAgICAgICAgICAgICAgICAgIHVzZXJDYWNoZS5zZXQob3RoZXJVc2VySWQsIG5hbWUpO1xuICAgICAgICAgICAgICAgICAgICBjTmFtZSA9IG5hbWU7XG4gICAgICAgICAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgICAgICAgICBjTmFtZSA9IG90aGVyVXNlcklkO1xuICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH0gY2F0Y2ggKHVzZXJGZXRjaEVycikge1xuICAgICAgICAgICAgICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgICAgICAgICAgICAgIGBbU2xhY2tTa2lsbHNfRW5yaWNoXSBGYWlsZWQgdG8gZmV0Y2ggdXNlciBpbmZvIGZvciBETSBwYXJ0bmVyICR7b3RoZXJVc2VySWR9IGluIGNoYW5uZWwgJHtjaWR9YFxuICAgICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgICAgICAgIGNOYW1lID0gb3RoZXJVc2VySWQ7XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgICAgICBjaGFubmVsQ2FjaGUuc2V0KGNpZCwgY05hbWUgfHwgY2lkKTtcbiAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgICAgICAgIGBbU2xhY2tTa2lsbHNfRW5yaWNoXSBjb252ZXJzYXRpb25zLmluZm8gY2FsbCBub3Qgb2sgZm9yICR7Y2lkfTogJHtjb252SW5mby5lcnJvcn1gXG4gICAgICAgICAgICApO1xuICAgICAgICAgICAgY2hhbm5lbENhY2hlLnNldChjaWQsIGNpZCk7XG4gICAgICAgICAgfVxuICAgICAgICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICAgICAgICBsb2dnZXIud2FybihcbiAgICAgICAgICAgIGBbU2xhY2tTa2lsbHNfRW5yaWNoXSBGYWlsZWQgdG8gZmV0Y2ggaW5mbyBmb3IgY2hhbm5lbCAke2NpZH06ICR7ZS5tZXNzYWdlfWBcbiAgICAgICAgICApO1xuICAgICAgICAgIGNoYW5uZWxDYWNoZS5zZXQoY2lkLCBjaWQpO1xuICAgICAgICB9XG4gICAgICB9KVxuICAgICk7XG4gIH1cblxuICByZXR1cm4gbWVzc2FnZXMubWFwKChtc2cpID0+IHtcbiAgICBjb25zdCBlbnJpY2hlZE1zZyA9IHsgLi4ubXNnIH07XG4gICAgaWYgKG1zZy51c2VySWQgJiYgdXNlckNhY2hlLmhhcyhtc2cudXNlcklkKSkge1xuICAgICAgZW5yaWNoZWRNc2cudXNlck5hbWUgPSB1c2VyQ2FjaGUuZ2V0KG1zZy51c2VySWQpIHx8IG1zZy51c2VySWQ7XG4gICAgfSBlbHNlIGlmIChtc2cuYm90SWQgJiYgdXNlckNhY2hlLmhhcyhtc2cuYm90SWQpKSB7XG4gICAgICAvLyBDaGVjayBib3RJZCBhZ2FpbnN0IHVzZXJDYWNoZSB0b29cbiAgICAgIGVucmljaGVkTXNnLnVzZXJOYW1lID0gdXNlckNhY2hlLmdldChtc2cuYm90SWQpIHx8IG1zZy5ib3RJZDsgLy8gQm90IG5hbWVcbiAgICB9IGVsc2UgaWYgKG1zZy51c2VySWQpIHtcbiAgICAgIGVucmljaGVkTXNnLnVzZXJOYW1lID0gbXNnLnVzZXJJZDtcbiAgICB9IGVsc2UgaWYgKG1zZy5ib3RJZCkge1xuICAgICAgZW5yaWNoZWRNc2cudXNlck5hbWUgPSBgQm90ICgke21zZy5ib3RJZH0pYDtcbiAgICB9XG5cbiAgICBpZiAobXNnLmNoYW5uZWxJZCAmJiBjaGFubmVsQ2FjaGUuaGFzKG1zZy5jaGFubmVsSWQpKSB7XG4gICAgICBlbnJpY2hlZE1zZy5jaGFubmVsTmFtZSA9XG4gICAgICAgIGNoYW5uZWxDYWNoZS5nZXQobXNnLmNoYW5uZWxJZCkgfHwgbXNnLmNoYW5uZWxJZDtcbiAgICB9IGVsc2UgaWYgKG1zZy5jaGFubmVsSWQgJiYgIWVucmljaGVkTXNnLmNoYW5uZWxOYW1lKSB7XG4gICAgICBlbnJpY2hlZE1zZy5jaGFubmVsTmFtZSA9IG1zZy5jaGFubmVsSWQ7XG4gICAgfVxuICAgIHJldHVybiBlbnJpY2hlZE1zZztcbiAgfSk7XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBsaXN0U2xhY2tDaGFubmVscyhcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGxpbWl0OiBudW1iZXIgPSAxMDAsXG4gIGN1cnNvcj86IHN0cmluZ1xuKTogUHJvbWlzZTxTbGFja1NraWxsUmVzcG9uc2U8TGlzdFNsYWNrQ2hhbm5lbHNEYXRhPj4ge1xuICBsb2dnZXIuZGVidWcoXG4gICAgYFtTbGFja1NraWxsc10gbGlzdFNsYWNrQ2hhbm5lbHMgY2FsbGVkIGJ5IHVzZXJJZDogJHt1c2VySWR9LCBsaW1pdDogJHtsaW1pdH0sIGN1cnNvcjogJHtjdXJzb3J9YFxuICApO1xuICBjb25zdCBjbGllbnQgPSBhd2FpdCBnZXRTbGFja0NsaWVudCh1c2VySWQpO1xuICBpZiAoIWNsaWVudCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnQ09ORklHX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ1NsYWNrIEJvdCBUb2tlbiBub3QgY29uZmlndXJlZC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByZXN1bHQ6IENvbnZlcnNhdGlvbnNMaXN0UmVzcG9uc2UgPSBhd2FpdCBjbGllbnQuY29udmVyc2F0aW9ucy5saXN0KHtcbiAgICAgIGxpbWl0OiBsaW1pdCxcbiAgICAgIGN1cnNvcjogY3Vyc29yLFxuICAgICAgdHlwZXM6ICdwdWJsaWNfY2hhbm5lbCxwcml2YXRlX2NoYW5uZWwsbXBpbSxpbScsXG4gICAgICBleGNsdWRlX2FyY2hpdmVkOiB0cnVlLFxuICAgIH0pO1xuXG4gICAgaWYgKCFyZXN1bHQub2sgfHwgIXJlc3VsdC5jaGFubmVscykge1xuICAgICAgY29uc3Qgc2xhY2tFcnJvciA9IHJlc3VsdC5lcnJvciB8fCAndW5rbm93bl9zbGFja19hcGlfZXJyb3InO1xuICAgICAgbG9nZ2VyLmVycm9yKFxuICAgICAgICBgW1NsYWNrU2tpbGxzXSBTbGFjayBBUEkgZXJyb3Igd2hpbGUgbGlzdGluZyBjaGFubmVscyAocmVzdWx0Lm9rIGlzIGZhbHNlKTogJHtzbGFja0Vycm9yfWBcbiAgICAgICk7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgY29kZTogJ1NMQUNLX0FQSV9FUlJPUicsXG4gICAgICAgICAgbWVzc2FnZTogYEZhaWxlZCB0byBsaXN0IGNoYW5uZWxzOiAke3NsYWNrRXJyb3J9YCxcbiAgICAgICAgICBkZXRhaWxzOiByZXN1bHQsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH1cblxuICAgIHJldHVybiB7XG4gICAgICBvazogdHJ1ZSxcbiAgICAgIGRhdGE6IHtcbiAgICAgICAgY2hhbm5lbHM6IChyZXN1bHQuY2hhbm5lbHMgYXMgU2xhY2tDaGFubmVsW10pIHx8IFtdLFxuICAgICAgICBuZXh0UGFnZUN1cnNvcjogcmVzdWx0LnJlc3BvbnNlX21ldGFkYXRhPy5uZXh0X2N1cnNvcixcbiAgICAgIH0sXG4gICAgfTtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbU2xhY2tTa2lsbHNdIEVycm9yIGxpc3RpbmcgU2xhY2sgY2hhbm5lbHMgZm9yIHVzZXJJZCAke3VzZXJJZH06YCxcbiAgICAgIGVycm9yXG4gICAgKTtcbiAgICBpZiAoZXJyb3IgaW5zdGFuY2VvZiBTbGFja0FQSUVycm9yKSB7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgY29kZTogZXJyb3IuY29kZSB8fCAnU0xBQ0tfQVBJX0VSUk9SJyxcbiAgICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgICAgZXJyb3IuZGF0YT8uZXJyb3IgfHxcbiAgICAgICAgICAgIGVycm9yLm1lc3NhZ2UgfHxcbiAgICAgICAgICAgICdTbGFjayBBUEkgZXJyb3Igd2hpbGUgbGlzdGluZyBjaGFubmVscycsXG4gICAgICAgICAgZGV0YWlsczogZXJyb3IuZGF0YSxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgfVxuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnSU5URVJOQUxfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnRmFpbGVkIHRvIGxpc3QgU2xhY2sgY2hhbm5lbHMgZHVlIHRvIGFuIHVuZXhwZWN0ZWQgZXJyb3IuJyxcbiAgICAgICAgZGV0YWlsczogKGVycm9yIGFzIEVycm9yKS5tZXNzYWdlLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59XG5cbmFzeW5jIGZ1bmN0aW9uIGdldENoYW5uZWxJZEJ5TmFtZU9yVXNlcihcbiAgY2xpZW50OiBXZWJDbGllbnQsXG4gIGlkZW50aWZpZXI6IHN0cmluZyxcbiAgdXNlcklkRm9yQ29udGV4dDogc3RyaW5nXG4pOiBQcm9taXNlPFNsYWNrU2tpbGxSZXNwb25zZTxzdHJpbmcgfCBudWxsPj4ge1xuICBsb2dnZXIuZGVidWcoXG4gICAgYFtTbGFja1NraWxsc10gZ2V0Q2hhbm5lbElkQnlOYW1lT3JVc2VyIGNhbGxlZCBmb3IgaWRlbnRpZmllcjogJHtpZGVudGlmaWVyfWBcbiAgKTtcblxuICBpZiAoaWRlbnRpZmllci5zdGFydHNXaXRoKCcjJykpIHtcbiAgICBjb25zdCBjaGFubmVsTmFtZSA9IGlkZW50aWZpZXIuc3Vic3RyaW5nKDEpO1xuICAgIGxldCBjdXJzb3I6IHN0cmluZyB8IHVuZGVmaW5lZCA9IHVuZGVmaW5lZDtcbiAgICBsZXQgYXR0ZW1wdHMgPSAwO1xuICAgIHRyeSB7XG4gICAgICB3aGlsZSAoYXR0ZW1wdHMgPCAxMCkge1xuICAgICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGxpc3RTbGFja0NoYW5uZWxzKHVzZXJJZEZvckNvbnRleHQsIDIwMCwgY3Vyc29yKTtcbiAgICAgICAgaWYgKCFyZXNwb25zZS5vayB8fCAhcmVzcG9uc2UuZGF0YT8uY2hhbm5lbHMpIHtcbiAgICAgICAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAgICAgICBgW1NsYWNrU2tpbGxzXSBFcnJvciBmZXRjaGluZyBjaGFubmVscyB0byBmaW5kIElEIGZvciBcIiMke2NoYW5uZWxOYW1lfVwiOmAsXG4gICAgICAgICAgICByZXNwb25zZS5lcnJvclxuICAgICAgICAgICk7XG4gICAgICAgICAgcmV0dXJuIHtcbiAgICAgICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgICAgIGVycm9yOiByZXNwb25zZS5lcnJvciB8fCB7XG4gICAgICAgICAgICAgIGNvZGU6ICdMT09LVVBfRkFJTEVEJyxcbiAgICAgICAgICAgICAgbWVzc2FnZTogJ0ZhaWxlZCB0byBsaXN0IGNoYW5uZWxzIGR1cmluZyBJRCBsb29rdXAuJyxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgfTtcbiAgICAgICAgfVxuICAgICAgICBjb25zdCBmb3VuZENoYW5uZWwgPSByZXNwb25zZS5kYXRhLmNoYW5uZWxzLmZpbmQoXG4gICAgICAgICAgKGNoKSA9PiBjaC5uYW1lID09PSBjaGFubmVsTmFtZSAmJiAoY2guaXNfY2hhbm5lbCB8fCBjaC5pc19ncm91cClcbiAgICAgICAgKTtcbiAgICAgICAgaWYgKGZvdW5kQ2hhbm5lbD8uaWQpIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiBmb3VuZENoYW5uZWwuaWQgfTtcbiAgICAgICAgY3Vyc29yID0gcmVzcG9uc2UuZGF0YS5uZXh0UGFnZUN1cnNvcjtcbiAgICAgICAgaWYgKCFjdXJzb3IpIGJyZWFrO1xuICAgICAgICBhdHRlbXB0cysrO1xuICAgICAgfVxuICAgICAgbG9nZ2VyLndhcm4oYFtTbGFja1NraWxsc10gQ2hhbm5lbCBcIiMke2NoYW5uZWxOYW1lfVwiIG5vdCBmb3VuZC5gKTtcbiAgICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiBudWxsIH07XG4gICAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgICAgbG9nZ2VyLmVycm9yKFxuICAgICAgICBgW1NsYWNrU2tpbGxzXSBFeGNlcHRpb24gaW4gZ2V0Q2hhbm5lbElkQnlOYW1lT3JVc2VyIGZvciBcIiMke2NoYW5uZWxOYW1lfVwiOmAsXG4gICAgICAgIGVycm9yXG4gICAgICApO1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICBlcnJvcjoge1xuICAgICAgICAgIGNvZGU6ICdJTlRFUk5BTF9FUlJPUicsXG4gICAgICAgICAgbWVzc2FnZTogYEV4Y2VwdGlvbiBsb29raW5nIHVwIGNoYW5uZWwgSUQ6ICR7ZXJyb3IubWVzc2FnZX1gLFxuICAgICAgICAgIGRldGFpbHM6IGVycm9yLFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICB9XG4gIH0gZWxzZSBpZiAoaWRlbnRpZmllci5zdGFydHNXaXRoKCdAJykpIHtcbiAgICBjb25zdCB1c2VyTmFtZU9ySWQgPSBpZGVudGlmaWVyLnN1YnN0cmluZygxKTtcbiAgICB0cnkge1xuICAgICAgaWYgKGlzU2xhY2tJZCh1c2VyTmFtZU9ySWQpKSB7XG4gICAgICAgIGNvbnN0IGRtUmVzcG9uc2UgPSBhd2FpdCBjbGllbnQuY29udmVyc2F0aW9ucy5vcGVuKHtcbiAgICAgICAgICB1c2VyczogdXNlck5hbWVPcklkLFxuICAgICAgICB9KTtcbiAgICAgICAgaWYgKGRtUmVzcG9uc2Uub2sgJiYgZG1SZXNwb25zZS5jaGFubmVsPy5pZCkge1xuICAgICAgICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiBkbVJlc3BvbnNlLmNoYW5uZWwuaWQgfTtcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAgICAgICBgW1NsYWNrU2tpbGxzXSBGYWlsZWQgdG8gb3BlbiBETSB3aXRoIHVzZXIgSUQgXCIke3VzZXJOYW1lT3JJZH1cIjogJHtkbVJlc3BvbnNlLmVycm9yfWBcbiAgICAgICAgICApO1xuICAgICAgICAgIHJldHVybiB7XG4gICAgICAgICAgICBvazogZmFsc2UsXG4gICAgICAgICAgICBlcnJvcjoge1xuICAgICAgICAgICAgICBjb2RlOiAnRE1fT1BFTl9GQUlMRUQnLFxuICAgICAgICAgICAgICBtZXNzYWdlOiBgQ291bGQgbm90IG9wZW4gRE0gd2l0aCAke3VzZXJOYW1lT3JJZH0uIEVycm9yOiAke2RtUmVzcG9uc2UuZXJyb3J9YCxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgfTtcbiAgICAgICAgfVxuICAgICAgfVxuICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgIGBbU2xhY2tTa2lsbHNdIElkZW50aWZpZXIgXCIke2lkZW50aWZpZXJ9XCIgZm9yIERNIGlzIG5vdCBhIHVzZXIgSUQuIFJvYnVzdCBuYW1lLXRvLUlEIHJlc29sdXRpb24gZm9yIERNcyBpcyBub3QgaW1wbGVtZW50ZWQgaW4gdGhpcyBoZWxwZXIuYFxuICAgICAgKTtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiB0cnVlLFxuICAgICAgICBkYXRhOiBudWxsLFxuICAgICAgICBlcnJvcjoge1xuICAgICAgICAgIGNvZGU6ICdVU0VSX1JFU09MVVRJT05fTkVFREVEJyxcbiAgICAgICAgICBtZXNzYWdlOiBgQ291bGQgbm90IHJlc29sdmUgRE0gZm9yIHVzZXIgbmFtZSAke3VzZXJOYW1lT3JJZH0gZGlyZWN0bHkuIFVzZXIgSUQgbmVlZGVkLmAsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICAgYFtTbGFja1NraWxsc10gRXhjZXB0aW9uIHRyeWluZyB0byBvcGVuIERNIGZvciBcIiR7aWRlbnRpZmllcn1cIjpgLFxuICAgICAgICBlcnJvclxuICAgICAgKTtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICBjb2RlOiAnSU5URVJOQUxfRVJST1InLFxuICAgICAgICAgIG1lc3NhZ2U6IGBFeGNlcHRpb24gb3BlbmluZyBETTogJHtlcnJvci5tZXNzYWdlfWAsXG4gICAgICAgICAgZGV0YWlsczogZXJyb3IsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH1cbiAgfVxuICBsb2dnZXIud2FybihcbiAgICBgW1NsYWNrU2tpbGxzXSBDaGFubmVsIGlkZW50aWZpZXIgXCIke2lkZW50aWZpZXJ9XCIgZm9ybWF0IG5vdCByZWNvZ25pemVkIGZvciBJRCByZXNvbHV0aW9uIChleHBlY3RlZCAjY2hhbm5lbCBvciBAdXNlcikuYFxuICApO1xuICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogbnVsbCB9O1xufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gc2VuZFNsYWNrTWVzc2FnZShcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGNoYW5uZWxJZGVudGlmaWVyOiBzdHJpbmcsXG4gIHRleHQ6IHN0cmluZ1xuKTogUHJvbWlzZTxTbGFja1NraWxsUmVzcG9uc2U8U2xhY2tNZXNzYWdlRGF0YT4+IHtcbiAgbG9nZ2VyLmRlYnVnKFxuICAgIGBbU2xhY2tTa2lsbHNdIHNlbmRTbGFja01lc3NhZ2UgY2FsbGVkIGJ5IHVzZXJJZDogJHt1c2VySWR9IHRvIGNoYW5uZWxJZGVudGlmaWVyOiAke2NoYW5uZWxJZGVudGlmaWVyfSwgdGV4dDogXCIke3RleHQuc3Vic3RyaW5nKDAsIDUwKX0uLi5cImBcbiAgKTtcbiAgY29uc3QgY2xpZW50ID0gYXdhaXQgZ2V0U2xhY2tDbGllbnQodXNlcklkKTtcbiAgaWYgKCFjbGllbnQpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdTbGFjayBCb3QgVG9rZW4gbm90IGNvbmZpZ3VyZWQuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIGlmICghY2hhbm5lbElkZW50aWZpZXIgfHwgIXRleHQpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnQ2hhbm5lbCBpZGVudGlmaWVyIGFuZCB0ZXh0IGFyZSByZXF1aXJlZC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgbGV0IHRhcmdldENoYW5uZWxJZCA9IGNoYW5uZWxJZGVudGlmaWVyO1xuXG4gIGlmICghaXNTbGFja0lkKGNoYW5uZWxJZGVudGlmaWVyKSkge1xuICAgIGxvZ2dlci5kZWJ1ZyhcbiAgICAgIGBbU2xhY2tTa2lsbHNdIENoYW5uZWwgaWRlbnRpZmllciBcIiR7Y2hhbm5lbElkZW50aWZpZXJ9XCIgaXMgbm90IGFuIElELiBBdHRlbXB0aW5nIHRvIHJlc29sdmUuLi5gXG4gICAgKTtcbiAgICBjb25zdCBpZFJlc3BvbnNlID0gYXdhaXQgZ2V0Q2hhbm5lbElkQnlOYW1lT3JVc2VyKFxuICAgICAgY2xpZW50LFxuICAgICAgY2hhbm5lbElkZW50aWZpZXIsXG4gICAgICB1c2VySWRcbiAgICApO1xuICAgIGlmICghaWRSZXNwb25zZS5vaykge1xuICAgICAgbG9nZ2VyLmVycm9yKFxuICAgICAgICBgW1NsYWNrU2tpbGxzXSBGYWlsZWQgdG8gcmVzb2x2ZSBjaGFubmVsIGlkZW50aWZpZXIgXCIke2NoYW5uZWxJZGVudGlmaWVyfVwiOmAsXG4gICAgICAgIGlkUmVzcG9uc2UuZXJyb3JcbiAgICAgICk7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiBpZFJlc3BvbnNlLmVycm9yIHx8IHtcbiAgICAgICAgICBjb2RlOiAnQ0hBTk5FTF9SRVNPTFVUSU9OX0ZBSUxFRCcsXG4gICAgICAgICAgbWVzc2FnZTogYENvdWxkIG5vdCByZXNvbHZlIGNoYW5uZWwgaWRlbnRpZmllciAke2NoYW5uZWxJZGVudGlmaWVyfS5gLFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICB9XG4gICAgaWYgKCFpZFJlc3BvbnNlLmRhdGEpIHtcbiAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICBgW1NsYWNrU2tpbGxzXSBDaGFubmVsIGlkZW50aWZpZXIgXCIke2NoYW5uZWxJZGVudGlmaWVyfVwiIG5vdCBmb3VuZCBvciBjb3VsZCBub3QgYmUgcmVzb2x2ZWQgdG8gYW4gSUQuYFxuICAgICAgKTtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICBjb2RlOiAnQ0hBTk5FTF9OT1RfRk9VTkQnLFxuICAgICAgICAgIG1lc3NhZ2U6IGBDaGFubmVsIG9yIHVzZXIgXCIke2NoYW5uZWxJZGVudGlmaWVyfVwiIG5vdCBmb3VuZC5gLFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICB9XG4gICAgdGFyZ2V0Q2hhbm5lbElkID0gaWRSZXNwb25zZS5kYXRhO1xuICAgIGxvZ2dlci5kZWJ1ZyhcbiAgICAgIGBbU2xhY2tTa2lsbHNdIFJlc29sdmVkIGlkZW50aWZpZXIgXCIke2NoYW5uZWxJZGVudGlmaWVyfVwiIHRvIElEIFwiJHt0YXJnZXRDaGFubmVsSWR9XCJgXG4gICAgKTtcbiAgfVxuXG4gIHRyeSB7XG4gICAgY29uc3QgcmVzdWx0OiBDaGF0UG9zdE1lc3NhZ2VSZXNwb25zZSA9IGF3YWl0IGNsaWVudC5jaGF0LnBvc3RNZXNzYWdlKHtcbiAgICAgIGNoYW5uZWw6IHRhcmdldENoYW5uZWxJZCxcbiAgICAgIHRleHQ6IHRleHQsXG4gICAgfSk7XG5cbiAgICBpZiAoIXJlc3VsdC5vayB8fCAhcmVzdWx0LnRzKSB7XG4gICAgICBjb25zdCBzbGFja0Vycm9yID0gcmVzdWx0LmVycm9yIHx8ICd1bmtub3duX3NsYWNrX2FwaV9lcnJvcl9vbl9wb3N0JztcbiAgICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICAgYFtTbGFja1NraWxsc10gU2xhY2sgQVBJIGVycm9yIHNlbmRpbmcgbWVzc2FnZSB0byBjaGFubmVsICR7dGFyZ2V0Q2hhbm5lbElkfTogJHtzbGFja0Vycm9yfWBcbiAgICAgICk7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgY29kZTogJ1NMQUNLX0FQSV9FUlJPUicsXG4gICAgICAgICAgbWVzc2FnZTogYEZhaWxlZCB0byBzZW5kIG1lc3NhZ2U6ICR7c2xhY2tFcnJvcn1gLFxuICAgICAgICAgIGRldGFpbHM6IHJlc3VsdCxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgfVxuICAgIGxvZ2dlci5pbmZvKFxuICAgICAgYFtTbGFja1NraWxsc10gTWVzc2FnZSBzZW50IHN1Y2Nlc3NmdWxseSB0byBjaGFubmVsICR7dGFyZ2V0Q2hhbm5lbElkfSBieSB1c2VyICR7dXNlcklkfS4gVFM6ICR7cmVzdWx0LnRzfWBcbiAgICApO1xuICAgIHJldHVybiB7XG4gICAgICBvazogdHJ1ZSxcbiAgICAgIGRhdGE6IHtcbiAgICAgICAgdHM6IHJlc3VsdC50cyxcbiAgICAgICAgY2hhbm5lbDogcmVzdWx0LmNoYW5uZWwsXG4gICAgICAgIG1lc3NhZ2U6IHJlc3VsdC5tZXNzYWdlIGFzIFNsYWNrTWVzc2FnZURhdGFbJ21lc3NhZ2UnXSxcbiAgICAgIH0sXG4gICAgfTtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbU2xhY2tTa2lsbHNdIEVycm9yIHNlbmRpbmcgU2xhY2sgbWVzc2FnZSBmb3IgdXNlcklkICR7dXNlcklkfSB0byBjaGFubmVsICR7dGFyZ2V0Q2hhbm5lbElkfTpgLFxuICAgICAgZXJyb3JcbiAgICApO1xuICAgIGlmIChlcnJvciBpbnN0YW5jZW9mIFNsYWNrQVBJRXJyb3IpIHtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICBjb2RlOiBlcnJvci5jb2RlIHx8ICdTTEFDS19BUElfRVJST1InLFxuICAgICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgICBlcnJvci5kYXRhPy5lcnJvciB8fFxuICAgICAgICAgICAgZXJyb3IubWVzc2FnZSB8fFxuICAgICAgICAgICAgJ1NsYWNrIEFQSSBlcnJvciBzZW5kaW5nIG1lc3NhZ2UnLFxuICAgICAgICAgIGRldGFpbHM6IGVycm9yLmRhdGEsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH1cbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0lOVEVSTkFMX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ0ZhaWxlZCB0byBzZW5kIFNsYWNrIG1lc3NhZ2UgZHVlIHRvIGFuIHVuZXhwZWN0ZWQgZXJyb3IuJyxcbiAgICAgICAgZGV0YWlsczogKGVycm9yIGFzIEVycm9yKS5tZXNzYWdlLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59XG5cbi8qKlxuICogU2VhcmNoZXMgU2xhY2sgbWVzc2FnZXMgZm9yIHRoZSB1c2VyIHVzaW5nIHRoZSBTbGFjayBXZWIgQVBJLlxuICogQHBhcmFtIGF0b21Vc2VySWQgVGhlIEF0b20gaW50ZXJuYWwgSUQgb2YgdGhlIHVzZXIgbWFraW5nIHRoZSByZXF1ZXN0IChmb3IgbG9nZ2luZy9jb250ZXh0KS5cbiAqIEBwYXJhbSBzZWFyY2hRdWVyeSBUaGUgU2xhY2sgQVBJIGNvbXBhdGlibGUgc2VhcmNoIHF1ZXJ5IHN0cmluZy5cbiAqIEBwYXJhbSBsaW1pdCBNYXggbnVtYmVyIG9mIG1lc3NhZ2VzIHRvIHJldHVybi5cbiAqIEByZXR1cm5zIEEgcHJvbWlzZSByZXNvbHZpbmcgdG8gYW4gYXJyYXkgb2YgU2xhY2tNZXNzYWdlIG9iamVjdHMuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBzZWFyY2hNeVNsYWNrTWVzc2FnZXMoXG4gIGF0b21Vc2VySWQ6IHN0cmluZyxcbiAgc2VhcmNoUXVlcnk6IHN0cmluZyxcbiAgbGltaXQ6IG51bWJlciA9IDEwXG4pOiBQcm9taXNlPFNsYWNrTWVzc2FnZVtdPiB7XG4gIGxvZ2dlci5kZWJ1ZyhcbiAgICBgW1NsYWNrU2tpbGxzXSBzZWFyY2hNeVNsYWNrTWVzc2FnZXMgZGlyZWN0IEFQSSBjYWxsIGZvciBBdG9tIHVzZXIgJHthdG9tVXNlcklkfSwgcXVlcnk6IFwiJHtzZWFyY2hRdWVyeX1cIiwgbGltaXQ6ICR7bGltaXR9YFxuICApO1xuXG4gIGNvbnN0IGNsaWVudCA9IGF3YWl0IGdldFNsYWNrQ2xpZW50KGF0b21Vc2VySWQpO1xuICBpZiAoIWNsaWVudCkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICdbU2xhY2tTa2lsbHNdIFNsYWNrIGNsaWVudCBub3QgYXZhaWxhYmxlIGZvciBzZWFyY2hNeVNsYWNrTWVzc2FnZXMuJ1xuICAgICk7XG4gICAgcmV0dXJuIFtdO1xuICB9XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGNsaWVudC5zZWFyY2gubWVzc2FnZXMoe1xuICAgICAgcXVlcnk6IHNlYXJjaFF1ZXJ5LFxuICAgICAgY291bnQ6IGxpbWl0LFxuICAgICAgc29ydDogJ3RpbWVzdGFtcCcsXG4gICAgICBzb3J0X2RpcjogJ2Rlc2MnLFxuICAgIH0pO1xuXG4gICAgaWYgKCFyZXNwb25zZS5vayB8fCAhcmVzcG9uc2UubWVzc2FnZXM/Lm1hdGNoZXMpIHtcbiAgICAgIGNvbnN0IHNsYWNrRXJyb3IgPVxuICAgICAgICAocmVzcG9uc2UgYXMgYW55KS5lcnJvciB8fCAndW5rbm93bl9zbGFja19zZWFyY2hfZXJyb3InO1xuICAgICAgbG9nZ2VyLmVycm9yKFxuICAgICAgICBgW1NsYWNrU2tpbGxzXSBTbGFjayBBUEkgZXJyb3IgZHVyaW5nIHNlYXJjaC5tZXNzYWdlczogJHtzbGFja0Vycm9yfWAsXG4gICAgICAgIHJlc3BvbnNlXG4gICAgICApO1xuICAgICAgcmV0dXJuIFtdO1xuICAgIH1cblxuICAgIGxldCByZXN1bHRzOiBTbGFja01lc3NhZ2VbXSA9IChyZXNwb25zZS5tZXNzYWdlcy5tYXRjaGVzIHx8IFtdKS5tYXAoXG4gICAgICAobWF0Y2g6IGFueSk6IFNsYWNrTWVzc2FnZSA9PiB7XG4gICAgICAgIHJldHVybiB7XG4gICAgICAgICAgaWQ6IG1hdGNoLnRzLFxuICAgICAgICAgIHRocmVhZElkOiBtYXRjaC50aHJlYWRfdHMgfHwgdW5kZWZpbmVkLFxuICAgICAgICAgIHVzZXJJZDogbWF0Y2gudXNlcixcbiAgICAgICAgICB1c2VyTmFtZTogbWF0Y2gudXNlcm5hbWUgfHwgbWF0Y2gudXNlcixcbiAgICAgICAgICBib3RJZDogbWF0Y2guYm90X2lkLFxuICAgICAgICAgIGNoYW5uZWxJZDogbWF0Y2guY2hhbm5lbD8uaWQsXG4gICAgICAgICAgY2hhbm5lbE5hbWU6IG1hdGNoLmNoYW5uZWw/Lm5hbWUgfHwgbWF0Y2guY2hhbm5lbD8uaWQsXG4gICAgICAgICAgdGV4dDogbWF0Y2gudGV4dCxcbiAgICAgICAgICBibG9ja3M6IG1hdGNoLmJsb2NrcyxcbiAgICAgICAgICBmaWxlczogbWF0Y2guZmlsZXMsXG4gICAgICAgICAgcmVhY3Rpb25zOiBtYXRjaC5yZWFjdGlvbnMsXG4gICAgICAgICAgdGltZXN0YW1wOiBuZXcgRGF0ZShwYXJzZUZsb2F0KG1hdGNoLnRzKSAqIDEwMDApLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgcGVybWFsaW5rOiBtYXRjaC5wZXJtYWxpbmssXG4gICAgICAgICAgcmF3OiBtYXRjaCxcbiAgICAgICAgfTtcbiAgICAgIH1cbiAgICApO1xuXG4gICAgaWYgKHJlc3VsdHMubGVuZ3RoID4gMCkge1xuICAgICAgY29uc3QgdXNlckNhY2hlID0gbmV3IE1hcDxzdHJpbmcsIHN0cmluZyB8IG51bGw+KCk7XG4gICAgICBjb25zdCBjaGFubmVsQ2FjaGUgPSBuZXcgTWFwPHN0cmluZywgc3RyaW5nIHwgbnVsbD4oKTtcbiAgICAgIHJlc3VsdHMgPSBhd2FpdCBfZW5yaWNoU2xhY2tNZXNzYWdlc1dpdGhOYW1lcyhcbiAgICAgICAgY2xpZW50LFxuICAgICAgICByZXN1bHRzLFxuICAgICAgICB1c2VyQ2FjaGUsXG4gICAgICAgIGNoYW5uZWxDYWNoZVxuICAgICAgKTtcbiAgICB9XG5cbiAgICBsb2dnZXIuaW5mbyhcbiAgICAgIGBbU2xhY2tTa2lsbHNdIHNlYXJjaE15U2xhY2tNZXNzYWdlcyBkaXJlY3QgQVBJIGNhbGwgZm91bmQgYW5kIGVucmljaGVkICR7cmVzdWx0cy5sZW5ndGh9IG1lc3NhZ2VzLmBcbiAgICApO1xuICAgIHJldHVybiByZXN1bHRzO1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFtTbGFja1NraWxsc10gRXJyb3IgaW4gc2VhcmNoTXlTbGFja01lc3NhZ2VzIGRpcmVjdCBBUEkgY2FsbCBmb3IgQXRvbSB1c2VyICR7YXRvbVVzZXJJZH0sIHF1ZXJ5IFwiJHtzZWFyY2hRdWVyeX1cIjpgLFxuICAgICAgZXJyb3JcbiAgICApO1xuICAgIGlmIChlcnJvciBpbnN0YW5jZW9mIFNsYWNrQVBJRXJyb3IpIHtcbiAgICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICAgYFtTbGFja1NraWxsc10gU2xhY2tBUElFcnJvciBjb2RlOiAke2Vycm9yLmNvZGV9LCBkYXRhOmAsXG4gICAgICAgIGVycm9yLmRhdGFcbiAgICAgICk7XG4gICAgfVxuICAgIHJldHVybiBbXTtcbiAgfVxufVxuXG4vKipcbiAqIFJlYWRzIHRoZSBkZXRhaWxlZCBjb250ZW50IG9mIGEgc3BlY2lmaWMgU2xhY2sgbWVzc2FnZSB1c2luZyBTbGFjayBXZWIgQVBJLlxuICogQHBhcmFtIGF0b21Vc2VySWQgVGhlIEF0b20gaW50ZXJuYWwgSUQgb2YgdGhlIHVzZXIgKGZvciBsb2dnaW5nL2NvbnRleHQpLlxuICogQHBhcmFtIGNoYW5uZWxJZCBUaGUgSUQgb2YgdGhlIGNoYW5uZWwgY29udGFpbmluZyB0aGUgbWVzc2FnZS5cbiAqIEBwYXJhbSBtZXNzYWdlVHMgVGhlIHRpbWVzdGFtcCAoSUQpIG9mIHRoZSBtZXNzYWdlLlxuICogQHJldHVybnMgQSBwcm9taXNlIHJlc29sdmluZyB0byBhIFNsYWNrTWVzc2FnZSBvYmplY3Qgb3IgbnVsbCBpZiBub3QgZm91bmQvZXJyb3IuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiByZWFkU2xhY2tNZXNzYWdlKFxuICBhdG9tVXNlcklkOiBzdHJpbmcsXG4gIGNoYW5uZWxJZDogc3RyaW5nLFxuICBtZXNzYWdlVHM6IHN0cmluZ1xuKTogUHJvbWlzZTxTbGFja01lc3NhZ2UgfCBudWxsPiB7XG4gIGxvZ2dlci5kZWJ1ZyhcbiAgICBgW1NsYWNrU2tpbGxzXSByZWFkU2xhY2tNZXNzYWdlIGRpcmVjdCBBUEkgY2FsbCBmb3IgQXRvbSB1c2VyICR7YXRvbVVzZXJJZH0sIGNoYW5uZWxJZDogJHtjaGFubmVsSWR9LCBtZXNzYWdlVHM6ICR7bWVzc2FnZVRzfWBcbiAgKTtcblxuICBjb25zdCBjbGllbnQgPSBhd2FpdCBnZXRTbGFja0NsaWVudChhdG9tVXNlcklkKTtcbiAgaWYgKCFjbGllbnQpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAnW1NsYWNrU2tpbGxzXSBTbGFjayBjbGllbnQgbm90IGF2YWlsYWJsZSBmb3IgcmVhZFNsYWNrTWVzc2FnZS4nXG4gICAgKTtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxuXG4gIHRyeSB7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBjbGllbnQuY29udmVyc2F0aW9ucy5oaXN0b3J5KHtcbiAgICAgIGNoYW5uZWw6IGNoYW5uZWxJZCxcbiAgICAgIGxhdGVzdDogbWVzc2FnZVRzLFxuICAgICAgb2xkZXN0OiBtZXNzYWdlVHMsXG4gICAgICBpbmNsdXNpdmU6IHRydWUsXG4gICAgICBsaW1pdDogMSxcbiAgICB9KTtcblxuICAgIGlmICghcmVzcG9uc2Uub2sgfHwgIXJlc3BvbnNlLm1lc3NhZ2VzIHx8IHJlc3BvbnNlLm1lc3NhZ2VzLmxlbmd0aCA9PT0gMCkge1xuICAgICAgY29uc3Qgc2xhY2tFcnJvciA9XG4gICAgICAgIChyZXNwb25zZSBhcyBhbnkpLmVycm9yIHx8ICdtZXNzYWdlX25vdF9mb3VuZF9vcl9hY2Nlc3NfZGVuaWVkJztcbiAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICBgW1NsYWNrU2tpbGxzXSBTbGFjayBBUEkgZXJyb3Igb3IgbWVzc2FnZSBub3QgZm91bmQgZHVyaW5nIGNvbnZlcnNhdGlvbnMuaGlzdG9yeSBmb3IgdHMgJHttZXNzYWdlVHN9IGluIGNoYW5uZWwgJHtjaGFubmVsSWR9OiAke3NsYWNrRXJyb3J9YCxcbiAgICAgICAgcmVzcG9uc2VcbiAgICAgICk7XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9XG5cbiAgICBjb25zdCBtc2dEYXRhID0gcmVzcG9uc2UubWVzc2FnZXNbMF0gYXMgYW55O1xuXG4gICAgbGV0IHBlcm1hbGluaztcbiAgICB0cnkge1xuICAgICAgY29uc3QgcGVybWFsaW5rUmVzcG9uc2UgPSBhd2FpdCBjbGllbnQuY2hhdC5nZXRQZXJtYWxpbmsoe1xuICAgICAgICBjaGFubmVsOiBjaGFubmVsSWQsXG4gICAgICAgIG1lc3NhZ2VfdHM6IG1zZ0RhdGEudHMhLFxuICAgICAgfSk7XG4gICAgICBpZiAocGVybWFsaW5rUmVzcG9uc2Uub2sgJiYgcGVybWFsaW5rUmVzcG9uc2UucGVybWFsaW5rKSB7XG4gICAgICAgIHBlcm1hbGluayA9IHBlcm1hbGlua1Jlc3BvbnNlLnBlcm1hbGluayBhcyBzdHJpbmc7XG4gICAgICB9XG4gICAgfSBjYXRjaCAocGVybWFsaW5rRXJyb3IpIHtcbiAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICBgW1NsYWNrU2tpbGxzXSBDb3VsZCBub3QgZmV0Y2ggcGVybWFsaW5rIGZvciBtZXNzYWdlICR7bXNnRGF0YS50c30gaW4gY2hhbm5lbCAke2NoYW5uZWxJZH06YCxcbiAgICAgICAgcGVybWFsaW5rRXJyb3JcbiAgICAgICk7XG4gICAgfVxuXG4gICAgbGV0IG1lc3NhZ2U6IFNsYWNrTWVzc2FnZSA9IHtcbiAgICAgIGlkOiBtc2dEYXRhLnRzISxcbiAgICAgIHRocmVhZElkOiBtc2dEYXRhLnRocmVhZF90cyB8fCB1bmRlZmluZWQsXG4gICAgICB1c2VySWQ6IG1zZ0RhdGEudXNlcixcbiAgICAgIHVzZXJOYW1lOiBtc2dEYXRhLnVzZXJuYW1lIHx8IG1zZ0RhdGEudXNlcixcbiAgICAgIGJvdElkOiBtc2dEYXRhLmJvdF9pZCxcbiAgICAgIGNoYW5uZWxJZDogY2hhbm5lbElkLFxuICAgICAgY2hhbm5lbE5hbWU6IGNoYW5uZWxJZCwgLy8gUGxhY2Vob2xkZXJcbiAgICAgIHRleHQ6IG1zZ0RhdGEudGV4dCxcbiAgICAgIGJsb2NrczogbXNnRGF0YS5ibG9ja3MsXG4gICAgICBmaWxlczogbXNnRGF0YS5maWxlcyxcbiAgICAgIHJlYWN0aW9uczogbXNnRGF0YS5yZWFjdGlvbnMsXG4gICAgICB0aW1lc3RhbXA6IG5ldyBEYXRlKHBhcnNlRmxvYXQobXNnRGF0YS50cyEpICogMTAwMCkudG9JU09TdHJpbmcoKSxcbiAgICAgIHBlcm1hbGluazogcGVybWFsaW5rLFxuICAgICAgcmF3OiBtc2dEYXRhLFxuICAgIH07XG5cbiAgICBjb25zdCB1c2VyQ2FjaGUgPSBuZXcgTWFwPHN0cmluZywgc3RyaW5nIHwgbnVsbD4oKTtcbiAgICBjb25zdCBjaGFubmVsQ2FjaGUgPSBuZXcgTWFwPHN0cmluZywgc3RyaW5nIHwgbnVsbD4oKTtcbiAgICBjb25zdCBlbnJpY2hlZE1lc3NhZ2VzID0gYXdhaXQgX2VucmljaFNsYWNrTWVzc2FnZXNXaXRoTmFtZXMoXG4gICAgICBjbGllbnQsXG4gICAgICBbbWVzc2FnZV0sXG4gICAgICB1c2VyQ2FjaGUsXG4gICAgICBjaGFubmVsQ2FjaGVcbiAgICApO1xuXG4gICAgbG9nZ2VyLmluZm8oXG4gICAgICBgW1NsYWNrU2tpbGxzXSBTdWNjZXNzZnVsbHkgcmVhZCBhbmQgZW5yaWNoZWQgU2xhY2sgbWVzc2FnZSAke21lc3NhZ2VUc30gZnJvbSBjaGFubmVsICR7Y2hhbm5lbElkfS5gXG4gICAgKTtcbiAgICByZXR1cm4gZW5yaWNoZWRNZXNzYWdlcy5sZW5ndGggPiAwID8gZW5yaWNoZWRNZXNzYWdlc1swXSA6IG51bGw7XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICBgW1NsYWNrU2tpbGxzXSBFcnJvciBpbiByZWFkU2xhY2tNZXNzYWdlIGRpcmVjdCBBUEkgY2FsbCBmb3IgQXRvbSB1c2VyICR7YXRvbVVzZXJJZH0sIGNoYW5uZWwgJHtjaGFubmVsSWR9LCB0cyAke21lc3NhZ2VUc306YCxcbiAgICAgIGVycm9yXG4gICAgKTtcbiAgICBpZiAoZXJyb3IgaW5zdGFuY2VvZiBTbGFja0FQSUVycm9yKSB7XG4gICAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAgIGBbU2xhY2tTa2lsbHNdIFNsYWNrQVBJRXJyb3IgY29kZTogJHtlcnJvci5jb2RlfSwgZGF0YTpgLFxuICAgICAgICBlcnJvci5kYXRhXG4gICAgICApO1xuICAgIH1cbiAgICByZXR1cm4gbnVsbDtcbiAgfVxufVxuXG4vLyAuLi4gTExNIGV4dHJhY3Rpb24gY29kZSBhbmQgZ2V0UmVjZW50RE1zQW5kTWVudGlvbnNGb3JCcmllZmluZyBmb2xsb3cgLi4uXG4vLyBnZXRSZWNlbnRETXNBbmRNZW50aW9uc0ZvckJyaWVmaW5nIHdpbGwgYWxzbyBiZW5lZml0IGZyb20gZW5yaWNoZWQgbWVzc2FnZXMgcmV0dXJuZWQgYnkgc2VhcmNoTXlTbGFja01lc3NhZ2VzLlxuXG5pbXBvcnQgT3BlbkFJIGZyb20gJ29wZW5haSc7XG5pbXBvcnQgeyBDaGF0Q29tcGxldGlvbk1lc3NhZ2VQYXJhbSB9IGZyb20gJ29wZW5haS9yZXNvdXJjZXMvY2hhdC9jb21wbGV0aW9ucyc7XG5pbXBvcnQgeyBBVE9NX09QRU5BSV9BUElfS0VZLCBBVE9NX05MVV9NT0RFTF9OQU1FIH0gZnJvbSAnLi4vX2xpYnMvY29uc3RhbnRzJztcblxubGV0IG9wZW5BSUNsaWVudEZvclNsYWNrRXh0cmFjdGlvbjogT3BlbkFJIHwgbnVsbCA9IG51bGw7XG5cbmZ1bmN0aW9uIGdldFNsYWNrRXh0cmFjdGlvbk9wZW5BSUNsaWVudCgpOiBPcGVuQUkge1xuICBpZiAob3BlbkFJQ2xpZW50Rm9yU2xhY2tFeHRyYWN0aW9uKSB7XG4gICAgcmV0dXJuIG9wZW5BSUNsaWVudEZvclNsYWNrRXh0cmFjdGlvbjtcbiAgfVxuICBpZiAoIUFUT01fT1BFTkFJX0FQSV9LRVkpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAnW1NsYWNrU2tpbGxzXSBPcGVuQUkgQVBJIEtleSBub3QgY29uZmlndXJlZCBmb3IgTExNIFNsYWNrIEV4dHJhY3Rvci4nXG4gICAgKTtcbiAgICB0aHJvdyBuZXcgRXJyb3IoJ09wZW5BSSBBUEkgS2V5IG5vdCBjb25maWd1cmVkIGZvciBMTE0gU2xhY2sgRXh0cmFjdG9yLicpO1xuICB9XG4gIG9wZW5BSUNsaWVudEZvclNsYWNrRXh0cmFjdGlvbiA9IG5ldyBPcGVuQUkoeyBhcGlLZXk6IEFUT01fT1BFTkFJX0FQSV9LRVkgfSk7XG4gIGxvZ2dlci5pbmZvKCdbU2xhY2tTa2lsbHNdIE9wZW5BSSBjbGllbnQgZm9yIFNsYWNrIGV4dHJhY3Rpb24gaW5pdGlhbGl6ZWQuJyk7XG4gIHJldHVybiBvcGVuQUlDbGllbnRGb3JTbGFja0V4dHJhY3Rpb247XG59XG5cbi8vIFN5c3RlbSBwcm9tcHQgZm9yIGV4dHJhY3RpbmcgaW5mbyBmcm9tIFNsYWNrIG1lc3NhZ2VzLlxuLy8gVGhpcyBpcyB2ZXJ5IHNpbWlsYXIgdG8gdGhlIGVtYWlsIG9uZSwgYnV0IGNvdWxkIGJlIHRhaWxvcmVkIG1vcmUgZm9yIFNsYWNrJ3MgdHlwaWNhbCBtZXNzYWdlIHN0eWxlIChlLmcuIG1lbnRpb25zLCB0aHJlYWRzLCBlbW9qaXMpLlxuY29uc3QgU0xBQ0tfRVhUUkFDVElPTl9TWVNURU1fUFJPTVBUX1RFTVBMQVRFID0gYFxuWW91IGFyZSBhbiBleHBlcnQgc3lzdGVtIGRlc2lnbmVkIHRvIGV4dHJhY3Qgc3BlY2lmaWMgcGllY2VzIG9mIGluZm9ybWF0aW9uIGZyb20gYSBTbGFjayBtZXNzYWdlIGJvZHkuXG5UaGUgdXNlciB3aWxsIHByb3ZpZGUgYSBtZXNzYWdlIGJvZHkgYW5kIGEgbGlzdCBvZiBpbmZvcm1hdGlvbiBwb2ludHMgdGhleSBhcmUgbG9va2luZyBmb3IgKGtleXdvcmRzKS5cbkZvciBlYWNoIGtleXdvcmQsIGZpbmQgdGhlIGNvcnJlc3BvbmRpbmcgaW5mb3JtYXRpb24gaW4gdGhlIG1lc3NhZ2UgYm9keS5cblJlc3BvbmQgT05MWSB3aXRoIGEgc2luZ2xlLCB2YWxpZCBKU09OIG9iamVjdC4gRG8gbm90IGluY2x1ZGUgYW55IGV4cGxhbmF0b3J5IHRleHQgYmVmb3JlIG9yIGFmdGVyIHRoZSBKU09OLlxuVGhlIEpTT04gb2JqZWN0IHNob3VsZCBoYXZlIGtleXMgY29ycmVzcG9uZGluZyB0byB0aGUgdXNlcidzIG9yaWdpbmFsIGtleXdvcmRzLlxuVGhlIHZhbHVlIGZvciBlYWNoIGtleSBzaG91bGQgYmUgdGhlIGV4dHJhY3RlZCBpbmZvcm1hdGlvbiBhcyBhIHN0cmluZy5cbklmIGEgc3BlY2lmaWMgcGllY2Ugb2YgaW5mb3JtYXRpb24gZm9yIGEga2V5d29yZCBpcyBub3QgZm91bmQgaW4gdGhlIG1lc3NhZ2UgYm9keSwgdGhlIHZhbHVlIGZvciB0aGF0IGtleSBzaG91bGQgYmUgbnVsbC5cblxuRXhhbXBsZTpcblVzZXIgcHJvdmlkZXMga2V5d29yZHM6IFtcInRhc2sgYXNzaWduZWQgdG9cIiwgXCJkdWUgZGF0ZVwiLCBcInByb2plY3QgbmFtZVwiXVxuTWVzc2FnZSBib2R5OiBcIkhleSBAYW5uYSBjYW4geW91IHRha2Ugb24gdGhlICdVSSBkZXNpZ24gZm9yIFByb2plY3QgUGhvZW5peCc/IE5lZWRzIHRvIGJlIGRvbmUgYnkgbmV4dCBGcmlkYXkuXCJcbllvdXIgSlNPTiByZXNwb25zZTpcbntcbiAgXCJ0YXNrIGFzc2lnbmVkIHRvXCI6IFwiQGFubmFcIixcbiAgXCJkdWUgZGF0ZVwiOiBcIm5leHQgRnJpZGF5XCIsXG4gIFwicHJvamVjdCBuYW1lXCI6IFwiUHJvamVjdCBQaG9lbml4XCJcbn1cblxuSWYgaW5mb3JtYXRpb24gZm9yIGEga2V5d29yZCBpcyBub3QgZm91bmQsIHVzZSBudWxsIGZvciBpdHMgdmFsdWUuXG5UaGUga2V5d29yZHMgeW91IG5lZWQgdG8gZXh0cmFjdCBpbmZvcm1hdGlvbiBmb3IgYXJlOiB7e0tFWVdPUkRTX0pTT05fQVJSQVlfU1RSSU5HfX1cbkV4dHJhY3QgdGhlIGluZm9ybWF0aW9uIGZyb20gdGhlIFNsYWNrIG1lc3NhZ2UgYm9keSBwcm92aWRlZCBieSB0aGUgdXNlci5cbmA7XG5cbi8qKlxuICogVXNlcyBhbiBMTE0gdG8gZXh0cmFjdCBzcGVjaWZpYyBwaWVjZXMgb2YgaW5mb3JtYXRpb24gZnJvbSBhIFNsYWNrIG1lc3NhZ2UgYm9keVxuICogYmFzZWQgb24gYSBsaXN0IG9mIGtleXdvcmRzIG9yIGNvbmNlcHRzLlxuICogQHBhcmFtIG1lc3NhZ2VUZXh0IFRoZSBwbGFpbiB0ZXh0IGNvbnRlbnQgb2YgdGhlIFNsYWNrIG1lc3NhZ2UuXG4gKiBAcGFyYW0gaW5mb0tleXdvcmRzIEFuIGFycmF5IG9mIHN0cmluZ3MgcmVwcmVzZW50aW5nIHRoZSBjb25jZXB0cy9rZXl3b3JkcyB0byBzZWFyY2ggZm9yLlxuICogQHJldHVybnMgQSBQcm9taXNlIHJlc29sdmluZyB0byBhIHJlY29yZCB3aGVyZSBrZXlzIGFyZSBpbmZvS2V5d29yZHMgYW5kIHZhbHVlcyBhcmUgdGhlIGV4dHJhY3RlZCBzdHJpbmdzIChvciBudWxsKS5cbiAqL1xuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGV4dHJhY3RJbmZvcm1hdGlvbkZyb21TbGFja01lc3NhZ2UoXG4gIG1lc3NhZ2VUZXh0OiBzdHJpbmcsXG4gIGluZm9LZXl3b3Jkczogc3RyaW5nW11cbik6IFByb21pc2U8UmVjb3JkPHN0cmluZywgc3RyaW5nIHwgbnVsbD4+IHtcbiAgaWYgKCFpbmZvS2V5d29yZHMgfHwgaW5mb0tleXdvcmRzLmxlbmd0aCA9PT0gMCkge1xuICAgIGxvZ2dlci5kZWJ1ZyhcbiAgICAgICdbU2xhY2tTa2lsbHNdIGV4dHJhY3RJbmZvcm1hdGlvbkZyb21TbGFja01lc3NhZ2U6IE5vIGluZm9LZXl3b3JkcyBwcm92aWRlZC4nXG4gICAgKTtcbiAgICByZXR1cm4ge307XG4gIH1cbiAgaWYgKCFtZXNzYWdlVGV4dCB8fCBtZXNzYWdlVGV4dC50cmltKCkgPT09ICcnKSB7XG4gICAgbG9nZ2VyLmRlYnVnKFxuICAgICAgJ1tTbGFja1NraWxsc10gZXh0cmFjdEluZm9ybWF0aW9uRnJvbVNsYWNrTWVzc2FnZTogRW1wdHkgbWVzc2FnZVRleHQgcHJvdmlkZWQuJ1xuICAgICk7XG4gICAgY29uc3QgZW1wdHlSZXN1bHQ6IFJlY29yZDxzdHJpbmcsIHN0cmluZyB8IG51bGw+ID0ge307XG4gICAgaW5mb0tleXdvcmRzLmZvckVhY2goKGt3KSA9PiAoZW1wdHlSZXN1bHRba3ddID0gbnVsbCkpO1xuICAgIHJldHVybiBlbXB0eVJlc3VsdDtcbiAgfVxuXG4gIGxvZ2dlci5kZWJ1ZyhcbiAgICBgW1NsYWNrU2tpbGxzXSBMTE0gRXh0cmFjdG9yOiBBdHRlbXB0aW5nIHRvIGV4dHJhY3QgZnJvbSBTbGFjayBtZXNzYWdlIGZvciBrZXl3b3JkczogWyR7aW5mb0tleXdvcmRzLmpvaW4oJywgJyl9XWBcbiAgKTtcbiAgY29uc3QgY2xpZW50ID0gZ2V0U2xhY2tFeHRyYWN0aW9uT3BlbkFJQ2xpZW50KCk7XG5cbiAgY29uc3Qga2V5d29yZHNKc29uQXJyYXlTdHJpbmcgPSBKU09OLnN0cmluZ2lmeShpbmZvS2V5d29yZHMpO1xuICBjb25zdCBzeXN0ZW1Qcm9tcHQgPSBTTEFDS19FWFRSQUNUSU9OX1NZU1RFTV9QUk9NUFRfVEVNUExBVEUucmVwbGFjZShcbiAgICAne3tLRVlXT1JEU19KU09OX0FSUkFZX1NUUklOR319JyxcbiAgICBrZXl3b3Jkc0pzb25BcnJheVN0cmluZ1xuICApO1xuXG4gIGNvbnN0IG1lc3NhZ2VzOiBDaGF0Q29tcGxldGlvbk1lc3NhZ2VQYXJhbVtdID0gW1xuICAgIHsgcm9sZTogJ3N5c3RlbScsIGNvbnRlbnQ6IHN5c3RlbVByb21wdCB9LFxuICAgIHsgcm9sZTogJ3VzZXInLCBjb250ZW50OiBgU2xhY2sgTWVzc2FnZSBCb2R5Olxcbi0tLVxcbiR7bWVzc2FnZVRleHR9XFxuLS0tYCB9LFxuICBdO1xuXG4gIHRyeSB7XG4gICAgY29uc3QgY29tcGxldGlvbiA9IGF3YWl0IGNsaWVudC5jaGF0LmNvbXBsZXRpb25zLmNyZWF0ZSh7XG4gICAgICBtb2RlbDogQVRPTV9OTFVfTU9ERUxfTkFNRSwgLy8gT3IgYSBtb3JlIGNhcGFibGUgbW9kZWxcbiAgICAgIG1lc3NhZ2VzOiBtZXNzYWdlcyxcbiAgICAgIHRlbXBlcmF0dXJlOiAwLjEsXG4gICAgICByZXNwb25zZV9mb3JtYXQ6IHsgdHlwZTogJ2pzb25fb2JqZWN0JyB9LFxuICAgIH0pO1xuXG4gICAgY29uc3QgbGxtUmVzcG9uc2UgPSBjb21wbGV0aW9uLmNob2ljZXNbMF0/Lm1lc3NhZ2U/LmNvbnRlbnQ7XG4gICAgaWYgKCFsbG1SZXNwb25zZSkge1xuICAgICAgbG9nZ2VyLmVycm9yKFxuICAgICAgICAnW1NsYWNrU2tpbGxzXSBMTE0gRXh0cmFjdG9yOiBSZWNlaXZlZCBhbiBlbXB0eSByZXNwb25zZSBmcm9tIEFJIGZvciBTbGFjayBtZXNzYWdlLidcbiAgICAgICk7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ0xMTSBFeHRyYWN0b3IgKFNsYWNrKTogRW1wdHkgcmVzcG9uc2UgZnJvbSBBSS4nKTtcbiAgICB9XG5cbiAgICBsb2dnZXIuZGVidWcoXG4gICAgICAnW1NsYWNrU2tpbGxzXSBMTE0gRXh0cmFjdG9yOiBSYXcgTExNIEpTT04gcmVzcG9uc2UgZm9yIFNsYWNrOicsXG4gICAgICBsbG1SZXNwb25zZVxuICAgICk7XG4gICAgY29uc3QgcGFyc2VkUmVzcG9uc2UgPSBKU09OLnBhcnNlKGxsbVJlc3BvbnNlKTtcblxuICAgIGNvbnN0IHJlc3VsdDogUmVjb3JkPHN0cmluZywgc3RyaW5nIHwgbnVsbD4gPSB7fTtcbiAgICBmb3IgKGNvbnN0IGtleXdvcmQgb2YgaW5mb0tleXdvcmRzKSB7XG4gICAgICByZXN1bHRba2V5d29yZF0gPSBwYXJzZWRSZXNwb25zZS5oYXNPd25Qcm9wZXJ0eShrZXl3b3JkKVxuICAgICAgICA/IHBhcnNlZFJlc3BvbnNlW2tleXdvcmRdXG4gICAgICAgIDogbnVsbDtcbiAgICB9XG5cbiAgICBsb2dnZXIuZGVidWcoXG4gICAgICAnW1NsYWNrU2tpbGxzXSBMTE0gRXh0cmFjdG9yOiBQYXJzZWQgYW5kIHJlY29uY2lsZWQgZXh0cmFjdGlvbiBmcm9tIFNsYWNrOicsXG4gICAgICByZXN1bHRcbiAgICApO1xuICAgIHJldHVybiByZXN1bHQ7XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAnW1NsYWNrU2tpbGxzXSBMTE0gRXh0cmFjdG9yOiBFcnJvciBwcm9jZXNzaW5nIGluZm9ybWF0aW9uIGV4dHJhY3Rpb24gZnJvbSBTbGFjayBtZXNzYWdlIHdpdGggT3BlbkFJOicsXG4gICAgICBlcnJvci5tZXNzYWdlXG4gICAgKTtcbiAgICBpZiAoZXJyb3IgaW5zdGFuY2VvZiBTeW50YXhFcnJvcikge1xuICAgICAgbG9nZ2VyLmVycm9yKFxuICAgICAgICAnW1NsYWNrU2tpbGxzXSBMTE0gRXh0cmFjdG9yOiBGYWlsZWQgdG8gcGFyc2UgSlNPTiByZXNwb25zZSBmcm9tIExMTSBmb3IgU2xhY2sgbWVzc2FnZS4nXG4gICAgICApO1xuICAgICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgICAnTExNIEV4dHJhY3RvciAoU2xhY2spOiBGYWlsZWQgdG8gcGFyc2UgcmVzcG9uc2UgZnJvbSBBSS4nXG4gICAgICApO1xuICAgIH1cbiAgICAvLyBGYWxsYmFjayB0byByZXR1cm4gbnVsbCBmb3IgYWxsIGtleXdvcmRzIGlmIExMTSBmYWlsc1xuICAgIGNvbnN0IGZhbGxiYWNrUmVzdWx0OiBSZWNvcmQ8c3RyaW5nLCBzdHJpbmcgfCBudWxsPiA9IHt9O1xuICAgIGluZm9LZXl3b3Jkcy5mb3JFYWNoKChrdykgPT4gKGVtcHR5UmVzdWx0W2t3XSA9IG51bGwpKTtcbiAgICByZXR1cm4gZmFsbGJhY2tSZXN1bHQ7XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldFJlY2VudERNc0FuZE1lbnRpb25zRm9yQnJpZWZpbmcoXG4gIGF0b21Vc2VySWQ6IHN0cmluZywgLy8gQXRvbSdzIGludGVybmFsIHVzZXIgSURcbiAgdGFyZ2V0RGF0ZTogRGF0ZSxcbiAgY291bnQ6IG51bWJlciA9IDNcbik6IFByb21pc2U8XG4gIFNsYWNrU2tpbGxSZXNwb25zZTx7IHJlc3VsdHM6IFNsYWNrTWVzc2FnZVtdOyBxdWVyeV9leGVjdXRlZD86IHN0cmluZyB9PlxuPiB7XG4gIGxvZ2dlci5kZWJ1ZyhcbiAgICBgW1NsYWNrU2tpbGxzXSBnZXRSZWNlbnRETXNBbmRNZW50aW9uc0ZvckJyaWVmaW5nIGZvciBBdG9tIHVzZXI6ICR7YXRvbVVzZXJJZH0sIFRhcmdldERhdGU6ICR7dGFyZ2V0RGF0ZS50b0lTT1N0cmluZygpLnNwbGl0KCdUJylbMF19LCBDb3VudDogJHtjb3VudH1gXG4gICk7XG5cbiAgY29uc3QgY2xpZW50ID0gYXdhaXQgZ2V0U2xhY2tDbGllbnQoYXRvbVVzZXJJZCk7XG4gIGlmICghY2xpZW50KSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdDT05GSUdfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnU2xhY2sgQm90IFRva2VuIG5vdCBjb25maWd1cmVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cblxuICB0cnkge1xuICAgIGxldCB1c2VyU2xhY2tJZDogc3RyaW5nIHwgdW5kZWZpbmVkO1xuICAgIHRyeSB7XG4gICAgICBjb25zdCBhdXRoVGVzdFJlc3BvbnNlID0gYXdhaXQgY2xpZW50LmF1dGgudGVzdCgpO1xuICAgICAgaWYgKGF1dGhUZXN0UmVzcG9uc2Uub2sgJiYgYXV0aFRlc3RSZXNwb25zZS51c2VyX2lkKSB7XG4gICAgICAgIHVzZXJTbGFja0lkID0gYXV0aFRlc3RSZXNwb25zZS51c2VyX2lkO1xuICAgICAgICBsb2dnZXIuaW5mbyhcbiAgICAgICAgICBgW1NsYWNrU2tpbGxzXSBSZXNvbHZlZCBTbGFjayB1c2VyIElEIGZvciBzZWFyY2g6ICR7dXNlclNsYWNrSWR9YFxuICAgICAgICApO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgICAgYFtTbGFja1NraWxsc10gQ291bGQgbm90IHJlc29sdmUgU2xhY2sgdXNlciBJRCB2aWEgYXV0aC50ZXN0LiBNZW50aW9ucyBzZWFyY2ggbWlnaHQgYmUgaW1wYWN0ZWQuIEVycm9yOiAke2F1dGhUZXN0UmVzcG9uc2UuZXJyb3J9YFxuICAgICAgICApO1xuICAgICAgfVxuICAgIH0gY2F0Y2ggKGF1dGhFcnJvcjogYW55KSB7XG4gICAgICBsb2dnZXIud2FybihcbiAgICAgICAgYFtTbGFja1NraWxsc10gRXhjZXB0aW9uIGR1cmluZyBjbGllbnQuYXV0aC50ZXN0OiAke2F1dGhFcnJvci5tZXNzYWdlfS4gTWVudGlvbnMgc2VhcmNoIG1pZ2h0IGJlIGltcGFjdGVkLmBcbiAgICAgICk7XG4gICAgfVxuXG4gICAgY29uc3QgZm9ybWF0RGF0ZUZvclNsYWNrID0gKGRhdGU6IERhdGUpOiBzdHJpbmcgPT4ge1xuICAgICAgY29uc3QgeWVhciA9IGRhdGUuZ2V0VVRDRnVsbFllYXIoKTtcbiAgICAgIGNvbnN0IG1vbnRoID0gKGRhdGUuZ2V0VVRDTW9udGgoKSArIDEpLnRvU3RyaW5nKCkucGFkU3RhcnQoMiwgJzAnKTtcbiAgICAgIGNvbnN0IGRheSA9IGRhdGUuZ2V0VVRDRGF0ZSgpLnRvU3RyaW5nKCkucGFkU3RhcnQoMiwgJzAnKTtcbiAgICAgIHJldHVybiBgJHt5ZWFyfS0ke21vbnRofS0ke2RheX1gO1xuICAgIH07XG5cbiAgICBjb25zdCBhZnRlckRhdGUgPSBuZXcgRGF0ZSh0YXJnZXREYXRlKTtcbiAgICBhZnRlckRhdGUuc2V0VVRDSG91cnMoMCwgMCwgMCwgMCk7XG4gICAgY29uc3QgYmVmb3JlRGF0ZSA9IG5ldyBEYXRlKHRhcmdldERhdGUpO1xuICAgIGJlZm9yZURhdGUuc2V0VVRDSG91cnMoMCwgMCwgMCwgMCk7XG4gICAgYmVmb3JlRGF0ZS5zZXRVVENEYXRlKHRhcmdldERhdGUuZ2V0VVRDRGF0ZSgpICsgMSk7XG5cbiAgICBsZXQgcXVlcnlTZWdtZW50czogc3RyaW5nW10gPSBbXTtcbiAgICBpZiAodXNlclNsYWNrSWQpIHtcbiAgICAgIHF1ZXJ5U2VnbWVudHMucHVzaChcbiAgICAgICAgYChAJHt1c2VyU2xhY2tJZH0gT1IgdG86JHt1c2VyU2xhY2tJZH0gT1IgaW46JHt1c2VyU2xhY2tJZH0pYFxuICAgICAgKTtcbiAgICB9IGVsc2Uge1xuICAgICAgcXVlcnlTZWdtZW50cy5wdXNoKGAoaXM6ZG0pYCk7XG4gICAgICBsb2dnZXIud2FybihcbiAgICAgICAgJ1tTbGFja1NraWxsc10gTm8gc3BlY2lmaWMgU2xhY2sgVXNlciBJRCBmb3IgRE1zL01lbnRpb25zIHNlYXJjaCwgcmVzdWx0cyBtaWdodCBiZSBsZXNzIHRhcmdldGVkIGlmIHVzaW5nIGEgYm90IHRva2VuIHdpdGhvdXQgc3BlY2lmaWMgdXNlciBjb250ZXh0IGZvciBETXMuJ1xuICAgICAgKTtcbiAgICB9XG5cbiAgICBxdWVyeVNlZ21lbnRzLnB1c2goYGFmdGVyOiR7Zm9ybWF0RGF0ZUZvclNsYWNrKGFmdGVyRGF0ZSl9YCk7XG4gICAgcXVlcnlTZWdtZW50cy5wdXNoKGBiZWZvcmU6JHtmb3JtYXREYXRlRm9yU2xhY2soYmVmb3JlRGF0ZSl9YCk7XG5cbiAgICBjb25zdCBzZWFyY2hRdWVyeSA9IHF1ZXJ5U2VnbWVudHMuam9pbignICcpO1xuICAgIGNvbnN0IGZ1bGxTZWFyY2hRdWVyeVdpdGhTb3J0ID0gYCR7c2VhcmNoUXVlcnl9IHNvcnQ6dGltZXN0YW1wIGRpcjpkZXNjYDtcblxuICAgIGxvZ2dlci5pbmZvKFxuICAgICAgYFtTbGFja1NraWxsc10gQ29uc3RydWN0ZWQgU2xhY2sgc2VhcmNoIHF1ZXJ5IGZvciBicmllZmluZzogXCIke2Z1bGxTZWFyY2hRdWVyeVdpdGhTb3J0fVwiYFxuICAgICk7XG5cbiAgICBjb25zdCBzZWFyY2hSZXN1bHRzOiBTbGFja01lc3NhZ2VbXSA9IGF3YWl0IHNlYXJjaE15U2xhY2tNZXNzYWdlcyhcbiAgICAgIGF0b21Vc2VySWQsXG4gICAgICBmdWxsU2VhcmNoUXVlcnlXaXRoU29ydCxcbiAgICAgIGNvdW50XG4gICAgKTtcblxuICAgIGxvZ2dlci5pbmZvKFxuICAgICAgYFtTbGFja1NraWxsc10gRm91bmQgJHtzZWFyY2hSZXN1bHRzLmxlbmd0aH0gU2xhY2sgbWVzc2FnZXMgZm9yIGJyaWVmaW5nLmBcbiAgICApO1xuICAgIHJldHVybiB7XG4gICAgICBvazogdHJ1ZSxcbiAgICAgIGRhdGE6IHsgcmVzdWx0czogc2VhcmNoUmVzdWx0cywgcXVlcnlfZXhlY3V0ZWQ6IGZ1bGxTZWFyY2hRdWVyeVdpdGhTb3J0IH0sXG4gICAgfTtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbU2xhY2tTa2lsbHNdIEVycm9yIGluIGdldFJlY2VudERNc0FuZE1lbnRpb25zRm9yQnJpZWZpbmcgZm9yIEF0b20gdXNlciAke2F0b21Vc2VySWR9OiAke2Vycm9yLm1lc3NhZ2V9YCxcbiAgICAgIGVycm9yXG4gICAgKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ1NMQUNLX0JSSUVGSU5HX0ZFVENIX0ZBSUxFRCcsXG4gICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgZXJyb3IubWVzc2FnZSB8fCAnRmFpbGVkIHRvIGZldGNoIHJlY2VudCBETXMvbWVudGlvbnMgZm9yIGJyaWVmaW5nLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn1cblxuLyoqXG4gKiBHZXRzIGEgcGVybWFsaW5rIGZvciBhIHNwZWNpZmljIFNsYWNrIG1lc3NhZ2UgdXNpbmcgdGhlIFNsYWNrIFdlYiBBUEkuXG4gKiBAcGFyYW0gYXRvbVVzZXJJZCBUaGUgQXRvbSBpbnRlcm5hbCBJRCBvZiB0aGUgdXNlciAoZm9yIGxvZ2dpbmcvY29udGV4dCkuXG4gKiBAcGFyYW0gY2hhbm5lbElkIFRoZSBJRCBvZiB0aGUgY2hhbm5lbCBjb250YWluaW5nIHRoZSBtZXNzYWdlLlxuICogQHBhcmFtIG1lc3NhZ2VUcyBUaGUgdGltZXN0YW1wIChJRCkgb2YgdGhlIG1lc3NhZ2UuXG4gKiBAcmV0dXJucyBBIHByb21pc2UgcmVzb2x2aW5nIHRvIHRoZSBwZXJtYWxpbmsgc3RyaW5nIG9yIG51bGwgaWYgbm90IGZvdW5kL2Vycm9yLlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0U2xhY2tNZXNzYWdlUGVybWFsaW5rKFxuICBhdG9tVXNlcklkOiBzdHJpbmcsIC8vIEF0b20gdXNlciBJRCBmb3IgY29udGV4dFxuICBjaGFubmVsSWQ6IHN0cmluZyxcbiAgbWVzc2FnZVRzOiBzdHJpbmdcbik6IFByb21pc2U8c3RyaW5nIHwgbnVsbD4ge1xuICBsb2dnZXIuZGVidWcoXG4gICAgYFtTbGFja1NraWxsc10gZ2V0U2xhY2tNZXNzYWdlUGVybWFsaW5rIGRpcmVjdCBBUEkgY2FsbCBmb3IgQXRvbSB1c2VyICR7YXRvbVVzZXJJZH0sIGNoYW5uZWxJZDogJHtjaGFubmVsSWR9LCBtZXNzYWdlVHM6ICR7bWVzc2FnZVRzfWBcbiAgKTtcblxuICBjb25zdCBjbGllbnQgPSBnZXRTbGFja0NsaWVudCgpO1xuICBpZiAoIWNsaWVudCkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICdbU2xhY2tTa2lsbHNdIFNsYWNrIGNsaWVudCBub3QgYXZhaWxhYmxlIGZvciBnZXRTbGFja01lc3NhZ2VQZXJtYWxpbmsuJ1xuICAgICk7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgY2xpZW50LmNoYXQuZ2V0UGVybWFsaW5rKHtcbiAgICAgIGNoYW5uZWw6IGNoYW5uZWxJZCxcbiAgICAgIG1lc3NhZ2VfdHM6IG1lc3NhZ2VUcyxcbiAgICB9KTtcblxuICAgIGlmICghcmVzcG9uc2Uub2sgfHwgIXJlc3BvbnNlLnBlcm1hbGluaykge1xuICAgICAgY29uc3Qgc2xhY2tFcnJvciA9IChyZXNwb25zZSBhcyBhbnkpLmVycm9yIHx8ICdwZXJtYWxpbmtfbm90X2ZvdW5kJztcbiAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICBgW1NsYWNrU2tpbGxzXSBTbGFjayBBUEkgZXJyb3Igb3IgcGVybWFsaW5rIG5vdCBmb3VuZCBmb3IgdHMgJHttZXNzYWdlVHN9IGluIGNoYW5uZWwgJHtjaGFubmVsSWR9OiAke3NsYWNrRXJyb3J9YCxcbiAgICAgICAgcmVzcG9uc2VcbiAgICAgICk7XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9XG4gICAgbG9nZ2VyLmluZm8oXG4gICAgICBgW1NsYWNrU2tpbGxzXSBTdWNjZXNzZnVsbHkgZmV0Y2hlZCBwZXJtYWxpbmsgZm9yIG1lc3NhZ2UgJHttZXNzYWdlVHN9LmBcbiAgICApO1xuICAgIHJldHVybiByZXNwb25zZS5wZXJtYWxpbmsgYXMgc3RyaW5nO1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFtTbGFja1NraWxsc10gRXJyb3IgaW4gZ2V0U2xhY2tNZXNzYWdlUGVybWFsaW5rIGRpcmVjdCBBUEkgY2FsbCBmb3IgQXRvbSB1c2VyICR7YXRvbVVzZXJJZH0sIGNoYW5uZWwgJHtjaGFubmVsSWR9LCB0cyAke21lc3NhZ2VUc306YCxcbiAgICAgIGVycm9yXG4gICAgKTtcbiAgICBpZiAoZXJyb3IgaW5zdGFuY2VvZiBTbGFja0FQSUVycm9yKSB7XG4gICAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAgIGBbU2xhY2tTa2lsbHNdIFNsYWNrQVBJRXJyb3IgY29kZTogJHtlcnJvci5jb2RlfSwgZGF0YTpgLFxuICAgICAgICBlcnJvci5kYXRhXG4gICAgICApO1xuICAgIH1cbiAgICByZXR1cm4gbnVsbDtcbiAgfVxufVxuIl19