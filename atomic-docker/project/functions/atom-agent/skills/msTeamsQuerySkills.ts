import {
  SkillResponse,
  MSTeamsMessage,
  // NLU entity types for MS Teams - will be defined or imported
} from '../types';
import { logger } from '../../_utils/logger';
import { understandMSTeamsSearchQueryLLM, StructuredMSTeamsQuery } from './llm_msteams_query_understander';
import { buildMSTeamsSearchQuery } from './nlu_msteams_helper';
import {
    searchMyMSTeamsMessages as searchMyMSTeamsMessagesBackend,
    readMSTeamsMessage as readMSTeamsMessageBackend,
    extractInformationFromMSTeamsMessage,
    getMSTeamsMessageWebUrl as getMSTeamsMessageWebUrlBackend,
    GetMSTeamsMessageDetailInput
} from './msTeamsSkills';

// NLU Entity Interfaces
export interface SearchMSTeamsMessagesNluEntities {
  raw_query_text: string;
  limit_number?: number;
  // Other potential pre-parsed entities from NLU
}

export interface ExtractInfoFromMSTeamsMessageNluEntities {
  message_reference_text: string; // e.g., "last message about budget in General channel", permalink, or "messageId:chatId"
  information_keywords: string[];
  message_content_context?: string; // Optional: if skill receives message content directly
  // Specific identifiers if NLU can reliably parse them from message_reference_text or they are contextual:
  message_id?: string;
  chat_id?: string;
  team_id?: string;
  channel_id?: string;
}

// --- Skill Implementations ---

export async function handleSearchMSTeamsMessages(
  userId: string,
  rawUserQuery: string,
  limit: number = 20, // Default limit
): Promise<SkillResponse<{ messages: MSTeamsMessage[], userMessage: string }>> {
  logger.info(`[handleSearchMSTeamsMessages] User: ${userId}, Query: "${rawUserQuery}", Limit: ${limit}`);

  try {
    const structuredQuery: Partial<StructuredMSTeamsQuery> = await understandMSTeamsSearchQueryLLM(rawUserQuery);
    logger.info(`[handleSearchMSTeamsMessages] LLM structured query for MS Teams: ${JSON.stringify(structuredQuery)}`);

    // TODO: Resolve user/channel names to IDs if LLM provided names (e.g., fromUser, inChatOrChannel, mentionsUser).
    // This is a complex step for MS Teams and might require Graph API calls to search users/teams/channels.
    // For V1, the KQL query might rely on Graph Search's ability to interpret names, or these fields might need IDs.
    // The buildMSTeamsKqlQuery helper currently assumes names might be passed.

    const kqlQueryString = buildMSTeamsSearchQuery(structuredQuery, rawUserQuery);
    logger.info(`[handleSearchMSTeamsMessages] Constructed MS Teams KQL query string: "${kqlQueryString}"`);

    if (!kqlQueryString || kqlQueryString.trim() === "") {
        return {
            ok: true,
            data: { messages: [], userMessage: "I couldn't determine specific search criteria for MS Teams from your request. Please try rephrasing." }
        };
    }

    const messages: MSTeamsMessage[] = await searchMyMSTeamsMessagesBackend(userId, kqlQueryString, limit);

    let userMessage = "";
    if (messages.length === 0) {
      userMessage = "I couldn't find any MS Teams messages matching your search criteria.";
    } else {
      userMessage = `I found ${messages.length} MS Teams message(s):\n`;
      messages.forEach((msg, index) => {
        const contentPreview = msg.contentType === 'html'
            ? msg.content.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().substring(0,150)
            : msg.content.substring(0,150);
        userMessage += `${index + 1}. "${contentPreview}..." (From: ${msg.userName || msg.userId || 'Unknown'}, In: ${msg.chatId || msg.channelId || 'Unknown'}, Date: ${new Date(msg.createdDateTime).toLocaleString()})\n   Web Link: ${msg.webUrl || 'N/A'}\n`;
      });
    }
    return { ok: true, data: { messages, userMessage } };

  } catch (error: any) {
    logger.error(`[handleSearchMSTeamsMessages] Error: ${error.message}`, error);
    return {
        ok: false,
        error: { code: 'MSTEAMS_SEARCH_FAILED', message: error.message || "Failed to search MS Teams messages." },
        data: { messages: [], userMessage: `Sorry, I encountered an error while searching your MS Teams messages: ${error.message}` }
    };
  }
}

async function resolveMessageReferenceToIdentifiers(
    userId: string,
    reference: string
): Promise<GetMSTeamsMessageDetailInput | null> {
    // Basic check for messageId format (Graph API IDs are long and URL-safe base64)
    // A typical message ID: AAMkAGVmMDEzMTM4LTZmYWUtNDdkNC1hM2QxLTMyMDYxNGY1M2E0OQBGAAAAAADbWFACq05dTK0tq3nkd2NUBwBf7s051YfFSq0t0RzHL7RfAAAAAAEMAABf7s051YfFSq0t0RzHL7RfAAFj7oE1AAA=
    // Chat ID format: 19:user1_upn-user2_upn@thread.v2 or 19:guid@thread.tacv2
    // Channel message ID might be just the ID, context from channel.
    // Permalink: https://teams.microsoft.com/l/message/19%3A[channel_id]%40thread.tacv2/[message_id]?tenantId=...&groupId=...&parentMessageId=...&teamName=...&channelName=...&createdTime=...

    logger.debug(`[resolveMessageReferenceToIdentifiers] Attempting to resolve reference: "${reference}"`);

    const teamsPermalinkRegex = /teams\.microsoft\.com\/l\/message\/([^/]+)\/([^/?]+)/;
    const permalinkMatch = reference.match(teamsPermalinkRegex);

    if (permalinkMatch) {
        const channelOrChatId = decodeURIComponent(permalinkMatch[1]); // This is often the channel/chat ID.
        const messageId = permalinkMatch[2];
        logger.info(`[resolveMessageReferenceToIdentifiers] Parsed from permalink: Channel/Chat ID: ${channelOrChatId}, Message ID: ${messageId}`);
        // Need to determine if channelOrChatId is a channel ID (within a team) or a chat ID.
        // This might require additional context or an API call if not obvious.
        // For now, if it looks like a channel (e.g., contains '@thread.tacv2'), assume channel context.
        // This is a heuristic. A robust solution might need to try fetching as chat then as channel message.
        if (channelOrChatId.includes('@thread.tacv2') || channelOrChatId.includes('@thread.skype')) { // Common patterns for channel/chat IDs
            // It's hard to distinguish chatId vs channelId from the permalink part alone without teamId.
            // The Graph API for getting a message often requires /chats/{chatId}/messages/{messageId} OR /teams/{teamId}/channels/{channelId}/messages/{messageId}
            // This simple resolver might not be enough. The skill might need to try both or have more context.
            // For now, let's assume if it's a channel format, we might need teamId too.
            // This part is tricky without knowing if it's a chat or channel message from the permalink alone.
            // Let's assume for now the Hasura action or msteams-service can handle just messageId if it's globally unique enough,
            // or this resolver needs to be much smarter, potentially querying Graph API.
            // Awaiting more clarity on how message_id is globally unique or contextualized by backend.
            // For now, if channelId-like, we might not have teamId.
            // Let's simplify: assume the backend can find it with messageId if channel/chat context is ambiguous from permalink alone.
            // Or, the Hasura action `getMSTeamsMessageDetail` needs to be clever.
            // The `GetMSTeamsMessageDetailInput` requires EITHER chatId OR (teamId AND channelId).
            // This function cannot reliably provide that from only a permalink fragment.
            // This indicates a potential issue with resolving solely from permalink without more context.
            // For now, we'll pass what we have.
            if (channelOrChatId.startsWith("19:") && channelOrChatId.includes("@thread.tacv2")) { // Likely a channel
                 logger.warn(`[resolveMessageReferenceToIdentifiers] Permalink gives channel-like ID (${channelOrChatId}) but teamId is missing for full context.`);
                 // We can't form a full GetMSTeamsMessageDetailInput for a channel message without teamId.
                 // This implies the backend `getMSTeamsMessageDetail` needs to be able to find a message by its ID globally or within user's scope,
                 // or the NLU needs to provide more context.
                 // For now, we can try with chatId if it's a 1:1 or group chat ID format.
                 return { messageId: messageId, chatId: channelOrChatId }; // Hopeful guess that channelOrChatId could be a chatId
            } else if (channelOrChatId.startsWith("19:") && channelOrChatId.includes("会議")) { // Japanese variant for meeting chats
                 return { messageId: messageId, chatId: channelOrChatId };
            }
             // If it's not clearly a chat ID, we might be stuck without teamId for channel messages.
             logger.warn(`[resolveMessageReferenceToIdentifiers] Could not reliably determine full context (chatId vs teamId/channelId) from permalink fragment.`);
             // Fallback: just return messageId, hope backend can use it.
             return { messageId: messageId };


        }
    }

    // Basic check for "messageId:chatId" or "messageId:teamId/channelId" (custom format)
    if (reference.includes(':') || reference.includes('/')) {
        // This is too ambiguous. The NLU should provide structured IDs.
        // For now, if it's not a permalink, we'll assume the reference IS the messageId if it's long.
        // This is a weak assumption.
        if (reference.length > 50) { // Heuristic for Graph API Message ID length
            logger.warn(`[resolveMessageReferenceToIdentifiers] Assuming reference "${reference}" is a direct messageID. Context (chat/channel) might be missing for precise lookup.`);
            return { messageId: reference };
        }
    }

    // TODO: Implement NL query to find the message if reference is textual e.g. "last message from Bob"
    // This would call handleSearchMSTeamsMessages and might need disambiguation.
    logger.warn(`[resolveMessageReferenceToIdentifiers] Natural language reference resolution for "${reference}" is not yet implemented. Please use a permalink or message ID with context.`);
    return null;
}


export async function handleExtractInfoFromMSTeamsMessage(
  userId: string,
  messageReferenceText: string,
  informationKeywords: string[],
  messageContentContext?: string // Optional: if skill receives message content directly
): Promise<SkillResponse<{ extractedInfo: Record<string, string | null>, userMessage: string }>> {
  logger.info(`[handleExtractInfoFromMSTeams] User: ${userId}, MessageRef: "${messageReferenceText}", Keywords: [${informationKeywords.join(', ')}]`);

  if (!informationKeywords || informationKeywords.length === 0) {
    return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Please specify what information you want to extract.'} };
  }

  let messageContent: string | null = messageContentContext || null;
  let messageDescription = `the Teams message (Ref: ${messageReferenceText.substring(0,50)}...)`;

  try {
    if (!messageContent) {
      const identifiers = await resolveMessageReferenceToIdentifiers(userId, messageReferenceText);
      if (!identifiers || !identifiers.messageId) {
        throw new Error(`Could not identify the specific MS Teams message from your reference: "${messageReferenceText}". Please use a permalink or provide more specific identifiers.`);
      }

      // Construct the GetMSTeamsMessageDetailInput based on what resolveMessageReferenceToIdentifiers could parse
      const detailInput: GetMSTeamsMessageDetailInput = { messageId: identifiers.messageId };
      if (identifiers.chatId) detailInput.chatId = identifiers.chatId;
      // If it was a channel, teamId and channelId would be needed. The resolver is limited here.
      // This highlights a dependency on either good permalink parsing or structured IDs from NLU.

      const teamsMessage = await readMSTeamsMessageBackend(userId, detailInput);
      if (teamsMessage && teamsMessage.content) {
        messageContent = teamsMessage.content; // Could be HTML or text
        messageDescription = `the Teams message from ${teamsMessage.userName || 'Unknown'} in ${teamsMessage.chatId || teamsMessage.channelId || 'Unknown chat/channel'}`;
        if (teamsMessage.contentType === 'html') {
            // Basic stripping, extractInformationFromMSTeamsMessage also does this
            messageContent = messageContent.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
        }
      } else {
        throw new Error(`Could not find or read the content of the MS Teams message (ID: ${identifiers.messageId}).`);
      }
    }

    if (!messageContent || messageContent.trim() === "") {
        return {
            ok: false,
            error: { code: 'MSTEAMS_MESSAGE_EMPTY', message: `The MS Teams message body for "${messageDescription}" is empty.`},
            data: { extractedInfo: {}, userMessage: `The MS Teams message body for "${messageDescription}" is empty, so I couldn't extract information.`}
        };
    }

    const extractedInfo = await extractInformationFromMSTeamsMessage(messageContent, informationKeywords);

    let foundCount = 0;
    let messageParts: string[] = [`From my review of ${messageDescription}:`];
    informationKeywords.forEach(keyword => {
      if (extractedInfo[keyword] !== null && extractedInfo[keyword] !== undefined) {
        messageParts.push(`- For "${keyword}": ${extractedInfo[keyword]}`);
        foundCount++;
      } else {
        messageParts.push(`- I couldn't find information about "${keyword}".`);
      }
    });

    const userMessage = foundCount > 0 ? messageParts.join('\n') : `I reviewed ${messageDescription} but couldn't find the specific information you asked for (${informationKeywords.join(', ')}).`;

    return { ok: true, data: { extractedInfo, userMessage } };

  } catch (error: any) {
    logger.error(`[handleExtractInfoFromMSTeams] Error: ${error.message}`, error);
     return {
        ok: false,
        error: { code: 'MSTEAMS_EXTRACT_FAILED', message: error.message || "Failed to extract information from MS Teams message." },
        data: { extractedInfo: {}, userMessage: `Sorry, I encountered an error while extracting information from the MS Teams message: ${error.message}` }
    };
  }
}
