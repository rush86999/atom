import { logger } from '../../_utils/logger';
import { understandMSTeamsSearchQueryLLM, } from './llm_msteams_query_understander';
import { buildMSTeamsSearchQuery } from './nlu_msteams_helper';
import { searchMyMSTeamsMessages as searchMyMSTeamsMessagesBackend, readMSTeamsMessage as readMSTeamsMessageBackend, extractInformationFromMSTeamsMessage, } from './msTeamsSkills';
// --- Skill Implementations ---
export async function handleSearchMSTeamsMessages(userId, rawUserQuery, limit = 20 // Default limit
) {
    logger.info(`[handleSearchMSTeamsMessages] User: ${userId}, Query: "${rawUserQuery}", Limit: ${limit}`);
    try {
        const structuredQuery = await understandMSTeamsSearchQueryLLM(rawUserQuery);
        logger.info(`[handleSearchMSTeamsMessages] LLM structured query for MS Teams: ${JSON.stringify(structuredQuery)}`);
        // TODO: Resolve user/channel names to IDs if LLM provided names (e.g., fromUser, inChatOrChannel, mentionsUser).
        // This is a complex step for MS Teams and might require Graph API calls to search users/teams/channels.
        // For V1, the KQL query might rely on Graph Search's ability to interpret names, or these fields might need IDs.
        // The buildMSTeamsKqlQuery helper currently assumes names might be passed.
        const kqlQueryString = buildMSTeamsSearchQuery(structuredQuery, rawUserQuery);
        logger.info(`[handleSearchMSTeamsMessages] Constructed MS Teams KQL query string: "${kqlQueryString}"`);
        if (!kqlQueryString || kqlQueryString.trim() === '') {
            return {
                ok: true,
                data: {
                    messages: [],
                    userMessage: "I couldn't determine specific search criteria for MS Teams from your request. Please try rephrasing.",
                },
            };
        }
        const messages = await searchMyMSTeamsMessagesBackend(userId, kqlQueryString, limit);
        let userMessage = '';
        if (messages.length === 0) {
            userMessage =
                "I couldn't find any MS Teams messages matching your search criteria.";
        }
        else {
            userMessage = `I found ${messages.length} MS Teams message(s):\n`;
            messages.forEach((msg, index) => {
                const contentPreview = msg.contentType === 'html'
                    ? msg.content
                        .replace(/<[^>]+>/g, ' ')
                        .replace(/\s+/g, ' ')
                        .trim()
                        .substring(0, 150)
                    : msg.content.substring(0, 150);
                userMessage += `${index + 1}. "${contentPreview}..." (From: ${msg.userName || msg.userId || 'Unknown'}, In: ${msg.chatId || msg.channelId || 'Unknown'}, Date: ${new Date(msg.createdDateTime).toLocaleString()})\n   Web Link: ${msg.webUrl || 'N/A'}\n`;
            });
        }
        return { ok: true, data: { messages, userMessage } };
    }
    catch (error) {
        logger.error(`[handleSearchMSTeamsMessages] Error: ${error.message}`, error);
        return {
            ok: false,
            error: {
                code: 'MSTEAMS_SEARCH_FAILED',
                message: error.message || 'Failed to search MS Teams messages.',
            },
            data: {
                messages: [],
                userMessage: `Sorry, I encountered an error while searching your MS Teams messages: ${error.message}`,
            },
        };
    }
}
async function resolveMessageReferenceToIdentifiers(userId, reference) {
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
        if (channelOrChatId.includes('@thread.tacv2') ||
            channelOrChatId.includes('@thread.skype')) {
            // Common patterns for channel/chat IDs
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
            if (channelOrChatId.startsWith('19:') &&
                channelOrChatId.includes('@thread.tacv2')) {
                // Likely a channel
                logger.warn(`[resolveMessageReferenceToIdentifiers] Permalink gives channel-like ID (${channelOrChatId}) but teamId is missing for full context.`);
                // We can't form a full GetMSTeamsMessageDetailInput for a channel message without teamId.
                // This implies the backend `getMSTeamsMessageDetail` needs to be able to find a message by its ID globally or within user's scope,
                // or the NLU needs to provide more context.
                // For now, we can try with chatId if it's a 1:1 or group chat ID format.
                return { messageId: messageId, chatId: channelOrChatId }; // Hopeful guess that channelOrChatId could be a chatId
            }
            else if (channelOrChatId.startsWith('19:') &&
                channelOrChatId.includes('会議')) {
                // Japanese variant for meeting chats
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
        if (reference.length > 50) {
            // Heuristic for Graph API Message ID length
            logger.warn(`[resolveMessageReferenceToIdentifiers] Assuming reference "${reference}" is a direct messageID. Context (chat/channel) might be missing for precise lookup.`);
            return { messageId: reference };
        }
    }
    // TODO: Implement NL query to find the message if reference is textual e.g. "last message from Bob"
    // This would call handleSearchMSTeamsMessages and might need disambiguation.
    logger.warn(`[resolveMessageReferenceToIdentifiers] Natural language reference resolution for "${reference}" is not yet implemented. Please use a permalink or message ID with context.`);
    return null;
}
export async function handleExtractInfoFromMSTeamsMessage(userId, messageReferenceText, informationKeywords, messageContentContext // Optional: if skill receives message content directly
) {
    logger.info(`[handleExtractInfoFromMSTeams] User: ${userId}, MessageRef: "${messageReferenceText}", Keywords: [${informationKeywords.join(', ')}]`);
    if (!informationKeywords || informationKeywords.length === 0) {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Please specify what information you want to extract.',
            },
        };
    }
    let messageContent = messageContentContext || null;
    let messageDescription = `the Teams message (Ref: ${messageReferenceText.substring(0, 50)}...)`;
    try {
        if (!messageContent) {
            const identifiers = await resolveMessageReferenceToIdentifiers(userId, messageReferenceText);
            if (!identifiers || !identifiers.messageId) {
                throw new Error(`Could not identify the specific MS Teams message from your reference: "${messageReferenceText}". Please use a permalink or provide more specific identifiers.`);
            }
            // Construct the GetMSTeamsMessageDetailInput based on what resolveMessageReferenceToIdentifiers could parse
            const detailInput = {
                messageId: identifiers.messageId,
            };
            if (identifiers.chatId)
                detailInput.chatId = identifiers.chatId;
            // If it was a channel, teamId and channelId would be needed. The resolver is limited here.
            // This highlights a dependency on either good permalink parsing or structured IDs from NLU.
            const teamsMessage = await readMSTeamsMessageBackend(userId, detailInput);
            if (teamsMessage && teamsMessage.content) {
                messageContent = teamsMessage.content; // Could be HTML or text
                messageDescription = `the Teams message from ${teamsMessage.userName || 'Unknown'} in ${teamsMessage.chatId || teamsMessage.channelId || 'Unknown chat/channel'}`;
                if (teamsMessage.contentType === 'html') {
                    // Basic stripping, extractInformationFromMSTeamsMessage also does this
                    messageContent = messageContent
                        .replace(/<[^>]+>/g, ' ')
                        .replace(/\s+/g, ' ')
                        .trim();
                }
            }
            else {
                throw new Error(`Could not find or read the content of the MS Teams message (ID: ${identifiers.messageId}).`);
            }
        }
        if (!messageContent || messageContent.trim() === '') {
            return {
                ok: false,
                error: {
                    code: 'MSTEAMS_MESSAGE_EMPTY',
                    message: `The MS Teams message body for "${messageDescription}" is empty.`,
                },
                data: {
                    extractedInfo: {},
                    userMessage: `The MS Teams message body for "${messageDescription}" is empty, so I couldn't extract information.`,
                },
            };
        }
        const extractedInfo = await extractInformationFromMSTeamsMessage(messageContent, informationKeywords);
        let foundCount = 0;
        let messageParts = [`From my review of ${messageDescription}:`];
        informationKeywords.forEach((keyword) => {
            if (extractedInfo[keyword] !== null &&
                extractedInfo[keyword] !== undefined) {
                messageParts.push(`- For "${keyword}": ${extractedInfo[keyword]}`);
                foundCount++;
            }
            else {
                messageParts.push(`- I couldn't find information about "${keyword}".`);
            }
        });
        const userMessage = foundCount > 0
            ? messageParts.join('\n')
            : `I reviewed ${messageDescription} but couldn't find the specific information you asked for (${informationKeywords.join(', ')}).`;
        return { ok: true, data: { extractedInfo, userMessage } };
    }
    catch (error) {
        logger.error(`[handleExtractInfoFromMSTeams] Error: ${error.message}`, error);
        return {
            ok: false,
            error: {
                code: 'MSTEAMS_EXTRACT_FAILED',
                message: error.message ||
                    'Failed to extract information from MS Teams message.',
            },
            data: {
                extractedInfo: {},
                userMessage: `Sorry, I encountered an error while extracting information from the MS Teams message: ${error.message}`,
            },
        };
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibXNUZWFtc1F1ZXJ5U2tpbGxzLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsibXNUZWFtc1F1ZXJ5U2tpbGxzLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUtBLE9BQU8sRUFBRSxNQUFNLEVBQUUsTUFBTSxxQkFBcUIsQ0FBQztBQUM3QyxPQUFPLEVBQ0wsK0JBQStCLEdBRWhDLE1BQU0sa0NBQWtDLENBQUM7QUFDMUMsT0FBTyxFQUFFLHVCQUF1QixFQUFFLE1BQU0sc0JBQXNCLENBQUM7QUFDL0QsT0FBTyxFQUNMLHVCQUF1QixJQUFJLDhCQUE4QixFQUN6RCxrQkFBa0IsSUFBSSx5QkFBeUIsRUFDL0Msb0NBQW9DLEdBR3JDLE1BQU0saUJBQWlCLENBQUM7QUFvQnpCLGdDQUFnQztBQUVoQyxNQUFNLENBQUMsS0FBSyxVQUFVLDJCQUEyQixDQUMvQyxNQUFjLEVBQ2QsWUFBb0IsRUFDcEIsUUFBZ0IsRUFBRSxDQUFDLGdCQUFnQjs7SUFFbkMsTUFBTSxDQUFDLElBQUksQ0FDVCx1Q0FBdUMsTUFBTSxhQUFhLFlBQVksYUFBYSxLQUFLLEVBQUUsQ0FDM0YsQ0FBQztJQUVGLElBQUksQ0FBQztRQUNILE1BQU0sZUFBZSxHQUNuQixNQUFNLCtCQUErQixDQUFDLFlBQVksQ0FBQyxDQUFDO1FBQ3RELE1BQU0sQ0FBQyxJQUFJLENBQ1Qsb0VBQW9FLElBQUksQ0FBQyxTQUFTLENBQUMsZUFBZSxDQUFDLEVBQUUsQ0FDdEcsQ0FBQztRQUVGLGlIQUFpSDtRQUNqSCx3R0FBd0c7UUFDeEcsaUhBQWlIO1FBQ2pILDJFQUEyRTtRQUUzRSxNQUFNLGNBQWMsR0FBRyx1QkFBdUIsQ0FDNUMsZUFBZSxFQUNmLFlBQVksQ0FDYixDQUFDO1FBQ0YsTUFBTSxDQUFDLElBQUksQ0FDVCx5RUFBeUUsY0FBYyxHQUFHLENBQzNGLENBQUM7UUFFRixJQUFJLENBQUMsY0FBYyxJQUFJLGNBQWMsQ0FBQyxJQUFJLEVBQUUsS0FBSyxFQUFFLEVBQUUsQ0FBQztZQUNw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aUJBQU0sQ0FBQztnQkFDTixZQUFZLENBQUMsSUFBSSxDQUFDLHdDQUF3QyxPQUFPLElBQUksQ0FBQyxDQUFDO1lBQ3pFLENBQUM7UUFDSCxDQUFDLENBQUMsQ0FBQztRQUVILE1BQU0sV0FBVyxHQUNmLFVBQVUsR0FBRyxDQUFDO1lBQ1osQ0FBQyxDQUFDLFlBQVksQ0FBQyxJQUFJLENBQUMsSUFBSSxDQUFDO1lBQ3pCLENBQUMsQ0FBQyxjQUFjLGtCQUFrQiw4REFBOEQsbUJBQW1CLENBQUMsSUFBSSxDQUFDLElBQUksQ0FBQyxJQUFJLENBQUM7UUFFdkksT0FBTyxFQUFFLEVBQUUsRUFBRSxJQUFJLEVBQUUsSUFBSSxFQUFFLEVBQUUsYUFBYSxFQUFFLFdBQVcsRUFBRSxFQUFFLENBQUM7SUFDNUQsQ0FBQztJQUFDLE9BQU8sS0FBVSxFQUFFLENBQUM7UUFDcEIsTUFBTSxDQUFDLEtBQUssQ0FDVix5Q0FBeUMsS0FBSyxDQUFDLE9BQU8sRUFBRSxFQUN4RCxLQUFLLENBQ04sQ0FBQztRQUNGLE9BQU87WUFDTCxFQUFFLEVBQUUsS0FBSztZQUNULEtBQUssRUFBRTtnQkFDTCxJQUFJLEVBQUUsd0JBQXdCO2dCQUM5QixPQUFPLEVBQ0wsS0FBSyxDQUFDLE9BQU87b0JBQ2Isc0RBQXNEO2FBQ3pEO1lBQ0QsSUFBSSxFQUFFO2dCQUNKLGFBQWEsRUFBRSxFQUFFO2dCQUNqQixXQUFXLEVBQUUseUZBQXlGLEtBQUssQ0FBQyxPQUFPLEVBQUU7YUFDdEg7U0FDRixDQUFDO0lBQ0osQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQge1xuICBTa2lsbFJlc3BvbnNlLFxuICBNU1RlYW1zTWVzc2FnZSxcbiAgLy8gTkxVIGVudGl0eSB0eXBlcyBmb3IgTVMgVGVhbXMgLSB3aWxsIGJlIGRlZmluZWQgb3IgaW1wb3J0ZWRcbn0gZnJvbSAnLi4vdHlwZXMnO1xuaW1wb3J0IHsgbG9nZ2VyIH0gZnJvbSAnLi4vLi4vX3V0aWxzL2xvZ2dlcic7XG5pbXBvcnQge1xuICB1bmRlcnN0YW5kTVNUZWFtc1NlYXJjaFF1ZXJ5TExNLFxuICBTdHJ1Y3R1cmVkTVNUZWFtc1F1ZXJ5LFxufSBmcm9tICcuL2xsbV9tc3RlYW1zX3F1ZXJ5X3VuZGVyc3RhbmRlcic7XG5pbXBvcnQgeyBidWlsZE1TVGVhbXNTZWFyY2hRdWVyeSB9IGZyb20gJy4vbmx1X21zdGVhbXNfaGVscGVyJztcbmltcG9ydCB7XG4gIHNlYXJjaE15TVNUZWFtc01lc3NhZ2VzIGFzIHNlYXJjaE15TVNUZWFtc01lc3NhZ2VzQmFja2VuZCxcbiAgcmVhZE1TVGVhbXNNZXNzYWdlIGFzIHJlYWRNU1RlYW1zTWVzc2FnZUJhY2tlbmQsXG4gIGV4dHJhY3RJbmZvcm1hdGlvbkZyb21NU1RlYW1zTWVzc2FnZSxcbiAgZ2V0TVNUZWFtc01lc3NhZ2VXZWJVcmwgYXMgZ2V0TVNUZWFtc01lc3NhZ2VXZWJVcmxCYWNrZW5kLFxuICBHZXRNU1RlYW1zTWVzc2FnZURldGFpbElucHV0LFxufSBmcm9tICcuL21zVGVhbXNTa2lsbHMnO1xuXG4vLyBOTFUgRW50aXR5IEludGVyZmFjZXNcbmV4cG9ydCBpbnRlcmZhY2UgU2VhcmNoTVNUZWFtc01lc3NhZ2VzTmx1RW50aXRpZXMge1xuICByYXdfcXVlcnlfdGV4dDogc3RyaW5nO1xuICBsaW1pdF9udW1iZXI/OiBudW1iZXI7XG4gIC8vIE90aGVyIHBvdGVudGlhbCBwcmUtcGFyc2VkIGVudGl0aWVzIGZyb20gTkxVXG59XG5cbmV4cG9ydCBpbnRlcmZhY2UgRXh0cmFjdEluZm9Gcm9tTVNUZWFtc01lc3NhZ2VObHVFbnRpdGllcyB7XG4gIG1lc3NhZ2VfcmVmZXJlbmNlX3RleHQ6IHN0cmluZzsgLy8gZS5nLiwgXCJsYXN0IG1lc3NhZ2UgYWJvdXQgYnVkZ2V0IGluIEdlbmVyYWwgY2hhbm5lbFwiLCBwZXJtYWxpbmssIG9yIFwibWVzc2FnZUlkOmNoYXRJZFwiXG4gIGluZm9ybWF0aW9uX2tleXdvcmRzOiBzdHJpbmdbXTtcbiAgbWVzc2FnZV9jb250ZW50X2NvbnRleHQ/OiBzdHJpbmc7IC8vIE9wdGlvbmFsOiBpZiBza2lsbCByZWNlaXZlcyBtZXNzYWdlIGNvbnRlbnQgZGlyZWN0bHlcbiAgLy8gU3BlY2lmaWMgaWRlbnRpZmllcnMgaWYgTkxVIGNhbiByZWxpYWJseSBwYXJzZSB0aGVtIGZyb20gbWVzc2FnZV9yZWZlcmVuY2VfdGV4dCBvciB0aGV5IGFyZSBjb250ZXh0dWFsOlxuICBtZXNzYWdlX2lkPzogc3RyaW5nO1xuICBjaGF0X2lkPzogc3RyaW5nO1xuICB0ZWFtX2lkPzogc3RyaW5nO1xuICBjaGFubmVsX2lkPzogc3RyaW5nO1xufVxuXG4vLyAtLS0gU2tpbGwgSW1wbGVtZW50YXRpb25zIC0tLVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlU2VhcmNoTVNUZWFtc01lc3NhZ2VzKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgcmF3VXNlclF1ZXJ5OiBzdHJpbmcsXG4gIGxpbWl0OiBudW1iZXIgPSAyMCAvLyBEZWZhdWx0IGxpbWl0XG4pOiBQcm9taXNlPFNraWxsUmVzcG9uc2U8eyBtZXNzYWdlczogTVNUZWFtc01lc3NhZ2VbXTsgdXNlck1lc3NhZ2U6IHN0cmluZyB9Pj4ge1xuICBsb2dnZXIuaW5mbyhcbiAgICBgW2hhbmRsZVNlYXJjaE1TVGVhbXNNZXNzYWdlc10gVXNlcjogJHt1c2VySWR9LCBRdWVyeTogXCIke3Jhd1VzZXJRdWVyeX1cIiwgTGltaXQ6ICR7bGltaXR9YFxuICApO1xuXG4gIHRyeSB7XG4gICAgY29uc3Qgc3RydWN0dXJlZFF1ZXJ5OiBQYXJ0aWFsPFN0cnVjdHVyZWRNU1RlYW1zUXVlcnk+ID1cbiAgICAgIGF3YWl0IHVuZGVyc3RhbmRNU1RlYW1zU2VhcmNoUXVlcnlMTE0ocmF3VXNlclF1ZXJ5KTtcbiAgICBsb2dnZXIuaW5mbyhcbiAgICAgIGBbaGFuZGxlU2VhcmNoTVNUZWFtc01lc3NhZ2VzXSBMTE0gc3RydWN0dXJlZCBxdWVyeSBmb3IgTVMgVGVhbXM6ICR7SlNPTi5zdHJpbmdpZnkoc3RydWN0dXJlZFF1ZXJ5KX1gXG4gICAgKTtcblxuICAgIC8vIFRPRE86IFJlc29sdmUgdXNlci9jaGFubmVsIG5hbWVzIHRvIElEcyBpZiBMTE0gcHJvdmlkZWQgbmFtZXMgKGUuZy4sIGZyb21Vc2VyLCBpbkNoYXRPckNoYW5uZWwsIG1lbnRpb25zVXNlcikuXG4gICAgLy8gVGhpcyBpcyBhIGNvbXBsZXggc3RlcCBmb3IgTVMgVGVhbXMgYW5kIG1pZ2h0IHJlcXVpcmUgR3JhcGggQVBJIGNhbGxzIHRvIHNlYXJjaCB1c2Vycy90ZWFtcy9jaGFubmVscy5cbiAgICAvLyBGb3IgVjEsIHRoZSBLUUwgcXVlcnkgbWlnaHQgcmVseSBvbiBHcmFwaCBTZWFyY2gncyBhYmlsaXR5IHRvIGludGVycHJldCBuYW1lcywgb3IgdGhlc2UgZmllbGRzIG1pZ2h0IG5lZWQgSURzLlxuICAgIC8vIFRoZSBidWlsZE1TVGVhbXNLcWxRdWVyeSBoZWxwZXIgY3VycmVudGx5IGFzc3VtZXMgbmFtZXMgbWlnaHQgYmUgcGFzc2VkLlxuXG4gICAgY29uc3Qga3FsUXVlcnlTdHJpbmcgPSBidWlsZE1TVGVhbXNTZWFyY2hRdWVyeShcbiAgICAgIHN0cnVjdHVyZWRRdWVyeSxcbiAgICAgIHJhd1VzZXJRdWVyeVxuICAgICk7XG4gICAgbG9nZ2VyLmluZm8oXG4gICAgICBgW2hhbmRsZVNlYXJjaE1TVGVhbXNNZXNzYWdlc10gQ29uc3RydWN0ZWQgTVMgVGVhbXMgS1FMIHF1ZXJ5IHN0cmluZzogXCIke2txbFF1ZXJ5U3RyaW5nfVwiYFxuICAgICk7XG5cbiAgICBpZiAoIWtxbFF1ZXJ5U3RyaW5nIHx8IGtxbFF1ZXJ5U3RyaW5nLnRyaW0oKSA9PT0gJycpIHtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiB0cnVlLFxuICAgICAgICBkYXRhOiB7XG4gICAgICAgICAgbWVzc2FnZXM6IFtdLFxuICAgICAgICAgIHVzZXJNZXNzYWdlOlxuICAgICAgICAgICAgXCJJIGNvdWxkbid0IGRldGVybWluZSBzcGVjaWZpYyBzZWFyY2ggY3JpdGVyaWEgZm9yIE1TIFRlYW1zIGZyb20geW91ciByZXF1ZXN0LiBQbGVhc2UgdHJ5IHJlcGhyYXNpbmcuXCIsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH1cblxuICAgIGNvbnN0IG1lc3NhZ2VzOiBNU1RlYW1zTWVzc2FnZVtdID0gYXdhaXQgc2VhcmNoTXlNU1RlYW1zTWVzc2FnZXNCYWNrZW5kKFxuICAgICAgdXNlcklkLFxuICAgICAga3FsUXVlcnlTdHJpbmcsXG4gICAgICBsaW1pdFxuICAgICk7XG5cbiAgICBsZXQgdXNlck1lc3NhZ2UgPSAnJztcbiAgICBpZiAobWVzc2FnZXMubGVuZ3RoID09PSAwKSB7XG4gICAgICB1c2VyTWVzc2FnZSA9XG4gICAgICAgIFwiSSBjb3VsZG4ndCBmaW5kIGFueSBNUyBUZWFtcyBtZXNzYWdlcyBtYXRjaGluZyB5b3VyIHNlYXJjaCBjcml0ZXJpYS5cIjtcbiAgICB9IGVsc2Uge1xuICAgICAgdXNlck1lc3NhZ2UgPSBgSSBmb3VuZCAke21lc3NhZ2VzLmxlbmd0aH0gTVMgVGVhbXMgbWVzc2FnZShzKTpcXG5gO1xuICAgICAgbWVzc2FnZXMuZm9yRWFjaCgobXNnLCBpbmRleCkgPT4ge1xuICAgICAgICBjb25zdCBjb250ZW50UHJldmlldyA9XG4gICAgICAgICAgbXNnLmNvbnRlbnRUeXBlID09PSAnaHRtbCdcbiAgICAgICAgICAgID8gbXNnLmNvbnRlbnRcbiAgICAgICAgICAgICAgICAucmVwbGFjZSgvPFtePl0rPi9nLCAnICcpXG4gICAgICAgICAgICAgICAgLnJlcGxhY2UoL1xccysvZywgJyAnKVxuICAgICAgICAgICAgICAgIC50cmltKClcbiAgICAgICAgICAgICAgICAuc3Vic3RyaW5nKDAsIDE1MClcbiAgICAgICAgICAgIDogbXNnLmNvbnRlbnQuc3Vic3RyaW5nKDAsIDE1MCk7XG4gICAgICAgIHVzZXJNZXNzYWdlICs9IGAke2luZGV4ICsgMX0uIFwiJHtjb250ZW50UHJldmlld30uLi5cIiAoRnJvbTogJHttc2cudXNlck5hbWUgfHwgbXNnLnVzZXJJZCB8fCAnVW5rbm93bid9LCBJbjogJHttc2cuY2hhdElkIHx8IG1zZy5jaGFubmVsSWQgfHwgJ1Vua25vd24nfSwgRGF0ZTogJHtuZXcgRGF0ZShtc2cuY3JlYXRlZERhdGVUaW1lKS50b0xvY2FsZVN0cmluZygpfSlcXG4gICBXZWIgTGluazogJHttc2cud2ViVXJsIHx8ICdOL0EnfVxcbmA7XG4gICAgICB9KTtcbiAgICB9XG4gICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IHsgbWVzc2FnZXMsIHVzZXJNZXNzYWdlIH0gfTtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbaGFuZGxlU2VhcmNoTVNUZWFtc01lc3NhZ2VzXSBFcnJvcjogJHtlcnJvci5tZXNzYWdlfWAsXG4gICAgICBlcnJvclxuICAgICk7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdNU1RFQU1TX1NFQVJDSF9GQUlMRUQnLFxuICAgICAgICBtZXNzYWdlOiBlcnJvci5tZXNzYWdlIHx8ICdGYWlsZWQgdG8gc2VhcmNoIE1TIFRlYW1zIG1lc3NhZ2VzLicsXG4gICAgICB9LFxuICAgICAgZGF0YToge1xuICAgICAgICBtZXNzYWdlczogW10sXG4gICAgICAgIHVzZXJNZXNzYWdlOiBgU29ycnksIEkgZW5jb3VudGVyZWQgYW4gZXJyb3Igd2hpbGUgc2VhcmNoaW5nIHlvdXIgTVMgVGVhbXMgbWVzc2FnZXM6ICR7ZXJyb3IubWVzc2FnZX1gLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59XG5cbmFzeW5jIGZ1bmN0aW9uIHJlc29sdmVNZXNzYWdlUmVmZXJlbmNlVG9JZGVudGlmaWVycyhcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHJlZmVyZW5jZTogc3RyaW5nXG4pOiBQcm9taXNlPEdldE1TVGVhbXNNZXNzYWdlRGV0YWlsSW5wdXQgfCBudWxsPiB7XG4gIC8vIEJhc2ljIGNoZWNrIGZvciBtZXNzYWdlSWQgZm9ybWF0IChHcmFwaCBBUEkgSURzIGFyZSBsb25nIGFuZCBVUkwtc2FmZSBiYXNlNjQpXG4gIC8vIEEgdHlwaWNhbCBtZXNzYWdlIElEOiBBQU1rQUdWbU1ERXpNVE00TFRabVlXVXRORGRrTkMxaE0yUXhMVE15TURZeE5HWTFNMkUwT1FCR0FBQUFBQURiV0ZBQ3EwNWRUSzB0cTNua2QyTlVCd0JmN3MwNTFZZkZTcTB0MFJ6SEw3UmZBQUFBQUFFTUFBQmY3czA1MVlmRlNxMHQwUnpITDdSZkFBRmo3b0UxQUFBPVxuICAvLyBDaGF0IElEIGZvcm1hdDogMTk6dXNlcjFfdXBuLXVzZXIyX3VwbkB0aHJlYWQudjIgb3IgMTk6Z3VpZEB0aHJlYWQudGFjdjJcbiAgLy8gQ2hhbm5lbCBtZXNzYWdlIElEIG1pZ2h0IGJlIGp1c3QgdGhlIElELCBjb250ZXh0IGZyb20gY2hhbm5lbC5cbiAgLy8gUGVybWFsaW5rOiBodHRwczovL3RlYW1zLm1pY3Jvc29mdC5jb20vbC9tZXNzYWdlLzE5JTNBW2NoYW5uZWxfaWRdJTQwdGhyZWFkLnRhY3YyL1ttZXNzYWdlX2lkXT90ZW5hbnRJZD0uLi4mZ3JvdXBJZD0uLi4mcGFyZW50TWVzc2FnZUlkPS4uLiZ0ZWFtTmFtZT0uLi4mY2hhbm5lbE5hbWU9Li4uJmNyZWF0ZWRUaW1lPS4uLlxuXG4gIGxvZ2dlci5kZWJ1ZyhcbiAgICBgW3Jlc29sdmVNZXNzYWdlUmVmZXJlbmNlVG9JZGVudGlmaWVyc10gQXR0ZW1wdGluZyB0byByZXNvbHZlIHJlZmVyZW5jZTogXCIke3JlZmVyZW5jZX1cImBcbiAgKTtcblxuICBjb25zdCB0ZWFtc1Blcm1hbGlua1JlZ2V4ID1cbiAgICAvdGVhbXNcXC5taWNyb3NvZnRcXC5jb21cXC9sXFwvbWVzc2FnZVxcLyhbXi9dKylcXC8oW14vP10rKS87XG4gIGNvbnN0IHBlcm1hbGlua01hdGNoID0gcmVmZXJlbmNlLm1hdGNoKHRlYW1zUGVybWFsaW5rUmVnZXgpO1xuXG4gIGlmIChwZXJtYWxpbmtNYXRjaCkge1xuICAgIGNvbnN0IGNoYW5uZWxPckNoYXRJZCA9IGRlY29kZVVSSUNvbXBvbmVudChwZXJtYWxpbmtNYXRjaFsxXSk7IC8vIFRoaXMgaXMgb2Z0ZW4gdGhlIGNoYW5uZWwvY2hhdCBJRC5cbiAgICBjb25zdCBtZXNzYWdlSWQgPSBwZXJtYWxpbmtNYXRjaFsyXTtcbiAgICBsb2dnZXIuaW5mbyhcbiAgICAgIGBbcmVzb2x2ZU1lc3NhZ2VSZWZlcmVuY2VUb0lkZW50aWZpZXJzXSBQYXJzZWQgZnJvbSBwZXJtYWxpbms6IENoYW5uZWwvQ2hhdCBJRDogJHtjaGFubmVsT3JDaGF0SWR9LCBNZXNzYWdlIElEOiAke21lc3NhZ2VJZH1gXG4gICAgKTtcbiAgICAvLyBOZWVkIHRvIGRldGVybWluZSBpZiBjaGFubmVsT3JDaGF0SWQgaXMgYSBjaGFubmVsIElEICh3aXRoaW4gYSB0ZWFtKSBvciBhIGNoYXQgSUQuXG4gICAgLy8gVGhpcyBtaWdodCByZXF1aXJlIGFkZGl0aW9uYWwgY29udGV4dCBvciBhbiBBUEkgY2FsbCBpZiBub3Qgb2J2aW91cy5cbiAgICAvLyBGb3Igbm93LCBpZiBpdCBsb29rcyBsaWtlIGEgY2hhbm5lbCAoZS5nLiwgY29udGFpbnMgJ0B0aHJlYWQudGFjdjInKSwgYXNzdW1lIGNoYW5uZWwgY29udGV4dC5cbiAgICAvLyBUaGlzIGlzIGEgaGV1cmlzdGljLiBBIHJvYnVzdCBzb2x1dGlvbiBtaWdodCBuZWVkIHRvIHRyeSBmZXRjaGluZyBhcyBjaGF0IHRoZW4gYXMgY2hhbm5lbCBtZXNzYWdlLlxuICAgIGlmIChcbiAgICAgIGNoYW5uZWxPckNoYXRJZC5pbmNsdWRlcygnQHRocmVhZC50YWN2MicpIHx8XG4gICAgICBjaGFubmVsT3JDaGF0SWQuaW5jbHVkZXMoJ0B0aHJlYWQuc2t5cGUnKVxuICAgICkge1xuICAgICAgLy8gQ29tbW9uIHBhdHRlcm5zIGZvciBjaGFubmVsL2NoYXQgSURzXG4gICAgICAvLyBJdCdzIGhhcmQgdG8gZGlzdGluZ3Vpc2ggY2hhdElkIHZzIGNoYW5uZWxJZCBmcm9tIHRoZSBwZXJtYWxpbmsgcGFydCBhbG9uZSB3aXRob3V0IHRlYW1JZC5cbiAgICAgIC8vIFRoZSBHcmFwaCBBUEkgZm9yIGdldHRpbmcgYSBtZXNzYWdlIG9mdGVuIHJlcXVpcmVzIC9jaGF0cy97Y2hhdElkfS9tZXNzYWdlcy97bWVzc2FnZUlkfSBPUiAvdGVhbXMve3RlYW1JZH0vY2hhbm5lbHMve2NoYW5uZWxJZH0vbWVzc2FnZXMve21lc3NhZ2VJZH1cbiAgICAgIC8vIFRoaXMgc2ltcGxlIHJlc29sdmVyIG1pZ2h0IG5vdCBiZSBlbm91Z2guIFRoZSBza2lsbCBtaWdodCBuZWVkIHRvIHRyeSBib3RoIG9yIGhhdmUgbW9yZSBjb250ZXh0LlxuICAgICAgLy8gRm9yIG5vdywgbGV0J3MgYXNzdW1lIGlmIGl0J3MgYSBjaGFubmVsIGZvcm1hdCwgd2UgbWlnaHQgbmVlZCB0ZWFtSWQgdG9vLlxuICAgICAgLy8gVGhpcyBwYXJ0IGlzIHRyaWNreSB3aXRob3V0IGtub3dpbmcgaWYgaXQncyBhIGNoYXQgb3IgY2hhbm5lbCBtZXNzYWdlIGZyb20gdGhlIHBlcm1hbGluayBhbG9uZS5cbiAgICAgIC8vIExldCdzIGFzc3VtZSBmb3Igbm93IHRoZSBIYXN1cmEgYWN0aW9uIG9yIG1zdGVhbXMtc2VydmljZSBjYW4gaGFuZGxlIGp1c3QgbWVzc2FnZUlkIGlmIGl0J3MgZ2xvYmFsbHkgdW5pcXVlIGVub3VnaCxcbiAgICAgIC8vIG9yIHRoaXMgcmVzb2x2ZXIgbmVlZHMgdG8gYmUgbXVjaCBzbWFydGVyLCBwb3RlbnRpYWxseSBxdWVyeWluZyBHcmFwaCBBUEkuXG4gICAgICAvLyBBd2FpdGluZyBtb3JlIGNsYXJpdHkgb24gaG93IG1lc3NhZ2VfaWQgaXMgZ2xvYmFsbHkgdW5pcXVlIG9yIGNvbnRleHR1YWxpemVkIGJ5IGJhY2tlbmQuXG4gICAgICAvLyBGb3Igbm93LCBpZiBjaGFubmVsSWQtbGlrZSwgd2UgbWlnaHQgbm90IGhhdmUgdGVhbUlkLlxuICAgICAgLy8gTGV0J3Mgc2ltcGxpZnk6IGFzc3VtZSB0aGUgYmFja2VuZCBjYW4gZmluZCBpdCB3aXRoIG1lc3NhZ2VJZCBpZiBjaGFubmVsL2NoYXQgY29udGV4dCBpcyBhbWJpZ3VvdXMgZnJvbSBwZXJtYWxpbmsgYWxvbmUuXG4gICAgICAvLyBPciwgdGhlIEhhc3VyYSBhY3Rpb24gYGdldE1TVGVhbXNNZXNzYWdlRGV0YWlsYCBuZWVkcyB0byBiZSBjbGV2ZXIuXG4gICAgICAvLyBUaGUgYEdldE1TVGVhbXNNZXNzYWdlRGV0YWlsSW5wdXRgIHJlcXVpcmVzIEVJVEhFUiBjaGF0SWQgT1IgKHRlYW1JZCBBTkQgY2hhbm5lbElkKS5cbiAgICAgIC8vIFRoaXMgZnVuY3Rpb24gY2Fubm90IHJlbGlhYmx5IHByb3ZpZGUgdGhhdCBmcm9tIG9ubHkgYSBwZXJtYWxpbmsgZnJhZ21lbnQuXG4gICAgICAvLyBUaGlzIGluZGljYXRlcyBhIHBvdGVudGlhbCBpc3N1ZSB3aXRoIHJlc29sdmluZyBzb2xlbHkgZnJvbSBwZXJtYWxpbmsgd2l0aG91dCBtb3JlIGNvbnRleHQuXG4gICAgICAvLyBGb3Igbm93LCB3ZSdsbCBwYXNzIHdoYXQgd2UgaGF2ZS5cbiAgICAgIGlmIChcbiAgICAgICAgY2hhbm5lbE9yQ2hhdElkLnN0YXJ0c1dpdGgoJzE5OicpICYmXG4gICAgICAgIGNoYW5uZWxPckNoYXRJZC5pbmNsdWRlcygnQHRocmVhZC50YWN2MicpXG4gICAgICApIHtcbiAgICAgICAgLy8gTGlrZWx5IGEgY2hhbm5lbFxuICAgICAgICBsb2dnZXIud2FybihcbiAgICAgICAgICBgW3Jlc29sdmVNZXNzYWdlUmVmZXJlbmNlVG9JZGVudGlmaWVyc10gUGVybWFsaW5rIGdpdmVzIGNoYW5uZWwtbGlrZSBJRCAoJHtjaGFubmVsT3JDaGF0SWR9KSBidXQgdGVhbUlkIGlzIG1pc3NpbmcgZm9yIGZ1bGwgY29udGV4dC5gXG4gICAgICAgICk7XG4gICAgICAgIC8vIFdlIGNhbid0IGZvcm0gYSBmdWxsIEdldE1TVGVhbXNNZXNzYWdlRGV0YWlsSW5wdXQgZm9yIGEgY2hhbm5lbCBtZXNzYWdlIHdpdGhvdXQgdGVhbUlkLlxuICAgICAgICAvLyBUaGlzIGltcGxpZXMgdGhlIGJhY2tlbmQgYGdldE1TVGVhbXNNZXNzYWdlRGV0YWlsYCBuZWVkcyB0byBiZSBhYmxlIHRvIGZpbmQgYSBtZXNzYWdlIGJ5IGl0cyBJRCBnbG9iYWxseSBvciB3aXRoaW4gdXNlcidzIHNjb3BlLFxuICAgICAgICAvLyBvciB0aGUgTkxVIG5lZWRzIHRvIHByb3ZpZGUgbW9yZSBjb250ZXh0LlxuICAgICAgICAvLyBGb3Igbm93LCB3ZSBjYW4gdHJ5IHdpdGggY2hhdElkIGlmIGl0J3MgYSAxOjEgb3IgZ3JvdXAgY2hhdCBJRCBmb3JtYXQuXG4gICAgICAgIHJldHVybiB7IG1lc3NhZ2VJZDogbWVzc2FnZUlkLCBjaGF0SWQ6IGNoYW5uZWxPckNoYXRJZCB9OyAvLyBIb3BlZnVsIGd1ZXNzIHRoYXQgY2hhbm5lbE9yQ2hhdElkIGNvdWxkIGJlIGEgY2hhdElkXG4gICAgICB9IGVsc2UgaWYgKFxuICAgICAgICBjaGFubmVsT3JDaGF0SWQuc3RhcnRzV2l0aCgnMTk6JykgJiZcbiAgICAgICAgY2hhbm5lbE9yQ2hhdElkLmluY2x1ZGVzKCfkvJrorbAnKVxuICAgICAgKSB7XG4gICAgICAgIC8vIEphcGFuZXNlIHZhcmlhbnQgZm9yIG1lZXRpbmcgY2hhdHNcbiAgICAgICAgcmV0dXJuIHsgbWVzc2FnZUlkOiBtZXNzYWdlSWQsIGNoYXRJZDogY2hhbm5lbE9yQ2hhdElkIH07XG4gICAgICB9XG4gICAgICAvLyBJZiBpdCdzIG5vdCBjbGVhcmx5IGEgY2hhdCBJRCwgd2UgbWlnaHQgYmUgc3R1Y2sgd2l0aG91dCB0ZWFtSWQgZm9yIGNoYW5uZWwgbWVzc2FnZXMuXG4gICAgICBsb2dnZXIud2FybihcbiAgICAgICAgYFtyZXNvbHZlTWVzc2FnZVJlZmVyZW5jZVRvSWRlbnRpZmllcnNdIENvdWxkIG5vdCByZWxpYWJseSBkZXRlcm1pbmUgZnVsbCBjb250ZXh0IChjaGF0SWQgdnMgdGVhbUlkL2NoYW5uZWxJZCkgZnJvbSBwZXJtYWxpbmsgZnJhZ21lbnQuYFxuICAgICAgKTtcbiAgICAgIC8vIEZhbGxiYWNrOiBqdXN0IHJldHVybiBtZXNzYWdlSWQsIGhvcGUgYmFja2VuZCBjYW4gdXNlIGl0LlxuICAgICAgcmV0dXJuIHsgbWVzc2FnZUlkOiBtZXNzYWdlSWQgfTtcbiAgICB9XG4gIH1cblxuICAvLyBCYXNpYyBjaGVjayBmb3IgXCJtZXNzYWdlSWQ6Y2hhdElkXCIgb3IgXCJtZXNzYWdlSWQ6dGVhbUlkL2NoYW5uZWxJZFwiIChjdXN0b20gZm9ybWF0KVxuICBpZiAocmVmZXJlbmNlLmluY2x1ZGVzKCc6JykgfHwgcmVmZXJlbmNlLmluY2x1ZGVzKCcvJykpIHtcbiAgICAvLyBUaGlzIGlzIHRvbyBhbWJpZ3VvdXMuIFRoZSBOTFUgc2hvdWxkIHByb3ZpZGUgc3RydWN0dXJlZCBJRHMuXG4gICAgLy8gRm9yIG5vdywgaWYgaXQncyBub3QgYSBwZXJtYWxpbmssIHdlJ2xsIGFzc3VtZSB0aGUgcmVmZXJlbmNlIElTIHRoZSBtZXNzYWdlSWQgaWYgaXQncyBsb25nLlxuICAgIC8vIFRoaXMgaXMgYSB3ZWFrIGFzc3VtcHRpb24uXG4gICAgaWYgKHJlZmVyZW5jZS5sZW5ndGggPiA1MCkge1xuICAgICAgLy8gSGV1cmlzdGljIGZvciBHcmFwaCBBUEkgTWVzc2FnZSBJRCBsZW5ndGhcbiAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICBgW3Jlc29sdmVNZXNzYWdlUmVmZXJlbmNlVG9JZGVudGlmaWVyc10gQXNzdW1pbmcgcmVmZXJlbmNlIFwiJHtyZWZlcmVuY2V9XCIgaXMgYSBkaXJlY3QgbWVzc2FnZUlELiBDb250ZXh0IChjaGF0L2NoYW5uZWwpIG1pZ2h0IGJlIG1pc3NpbmcgZm9yIHByZWNpc2UgbG9va3VwLmBcbiAgICAgICk7XG4gICAgICByZXR1cm4geyBtZXNzYWdlSWQ6IHJlZmVyZW5jZSB9O1xuICAgIH1cbiAgfVxuXG4gIC8vIFRPRE86IEltcGxlbWVudCBOTCBxdWVyeSB0byBmaW5kIHRoZSBtZXNzYWdlIGlmIHJlZmVyZW5jZSBpcyB0ZXh0dWFsIGUuZy4gXCJsYXN0IG1lc3NhZ2UgZnJvbSBCb2JcIlxuICAvLyBUaGlzIHdvdWxkIGNhbGwgaGFuZGxlU2VhcmNoTVNUZWFtc01lc3NhZ2VzIGFuZCBtaWdodCBuZWVkIGRpc2FtYmlndWF0aW9uLlxuICBsb2dnZXIud2FybihcbiAgICBgW3Jlc29sdmVNZXNzYWdlUmVmZXJlbmNlVG9JZGVudGlmaWVyc10gTmF0dXJhbCBsYW5ndWFnZSByZWZlcmVuY2UgcmVzb2x1dGlvbiBmb3IgXCIke3JlZmVyZW5jZX1cIiBpcyBub3QgeWV0IGltcGxlbWVudGVkLiBQbGVhc2UgdXNlIGEgcGVybWFsaW5rIG9yIG1lc3NhZ2UgSUQgd2l0aCBjb250ZXh0LmBcbiAgKTtcbiAgcmV0dXJuIG51bGw7XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBoYW5kbGVFeHRyYWN0SW5mb0Zyb21NU1RlYW1zTWVzc2FnZShcbiAgdXNlcklkOiBzdHJpbmcsXG4gIG1lc3NhZ2VSZWZlcmVuY2VUZXh0OiBzdHJpbmcsXG4gIGluZm9ybWF0aW9uS2V5d29yZHM6IHN0cmluZ1tdLFxuICBtZXNzYWdlQ29udGVudENvbnRleHQ/OiBzdHJpbmcgLy8gT3B0aW9uYWw6IGlmIHNraWxsIHJlY2VpdmVzIG1lc3NhZ2UgY29udGVudCBkaXJlY3RseVxuKTogUHJvbWlzZTxcbiAgU2tpbGxSZXNwb25zZTx7XG4gICAgZXh0cmFjdGVkSW5mbzogUmVjb3JkPHN0cmluZywgc3RyaW5nIHwgbnVsbD47XG4gICAgdXNlck1lc3NhZ2U6IHN0cmluZztcbiAgfT5cbj4ge1xuICBsb2dnZXIuaW5mbyhcbiAgICBgW2hhbmRsZUV4dHJhY3RJbmZvRnJvbU1TVGVhbXNdIFVzZXI6ICR7dXNlcklkfSwgTWVzc2FnZVJlZjogXCIke21lc3NhZ2VSZWZlcmVuY2VUZXh0fVwiLCBLZXl3b3JkczogWyR7aW5mb3JtYXRpb25LZXl3b3Jkcy5qb2luKCcsICcpfV1gXG4gICk7XG5cbiAgaWYgKCFpbmZvcm1hdGlvbktleXdvcmRzIHx8IGluZm9ybWF0aW9uS2V5d29yZHMubGVuZ3RoID09PSAwKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdWQUxJREFUSU9OX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ1BsZWFzZSBzcGVjaWZ5IHdoYXQgaW5mb3JtYXRpb24geW91IHdhbnQgdG8gZXh0cmFjdC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgbGV0IG1lc3NhZ2VDb250ZW50OiBzdHJpbmcgfCBudWxsID0gbWVzc2FnZUNvbnRlbnRDb250ZXh0IHx8IG51bGw7XG4gIGxldCBtZXNzYWdlRGVzY3JpcHRpb24gPSBgdGhlIFRlYW1zIG1lc3NhZ2UgKFJlZjogJHttZXNzYWdlUmVmZXJlbmNlVGV4dC5zdWJzdHJpbmcoMCwgNTApfS4uLilgO1xuXG4gIHRyeSB7XG4gICAgaWYgKCFtZXNzYWdlQ29udGVudCkge1xuICAgICAgY29uc3QgaWRlbnRpZmllcnMgPSBhd2FpdCByZXNvbHZlTWVzc2FnZVJlZmVyZW5jZVRvSWRlbnRpZmllcnMoXG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgbWVzc2FnZVJlZmVyZW5jZVRleHRcbiAgICAgICk7XG4gICAgICBpZiAoIWlkZW50aWZpZXJzIHx8ICFpZGVudGlmaWVycy5tZXNzYWdlSWQpIHtcbiAgICAgICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgICAgIGBDb3VsZCBub3QgaWRlbnRpZnkgdGhlIHNwZWNpZmljIE1TIFRlYW1zIG1lc3NhZ2UgZnJvbSB5b3VyIHJlZmVyZW5jZTogXCIke21lc3NhZ2VSZWZlcmVuY2VUZXh0fVwiLiBQbGVhc2UgdXNlIGEgcGVybWFsaW5rIG9yIHByb3ZpZGUgbW9yZSBzcGVjaWZpYyBpZGVudGlmaWVycy5gXG4gICAgICAgICk7XG4gICAgICB9XG5cbiAgICAgIC8vIENvbnN0cnVjdCB0aGUgR2V0TVNUZWFtc01lc3NhZ2VEZXRhaWxJbnB1dCBiYXNlZCBvbiB3aGF0IHJlc29sdmVNZXNzYWdlUmVmZXJlbmNlVG9JZGVudGlmaWVycyBjb3VsZCBwYXJzZVxuICAgICAgY29uc3QgZGV0YWlsSW5wdXQ6IEdldE1TVGVhbXNNZXNzYWdlRGV0YWlsSW5wdXQgPSB7XG4gICAgICAgIG1lc3NhZ2VJZDogaWRlbnRpZmllcnMubWVzc2FnZUlkLFxuICAgICAgfTtcbiAgICAgIGlmIChpZGVudGlmaWVycy5jaGF0SWQpIGRldGFpbElucHV0LmNoYXRJZCA9IGlkZW50aWZpZXJzLmNoYXRJZDtcbiAgICAgIC8vIElmIGl0IHdhcyBhIGNoYW5uZWwsIHRlYW1JZCBhbmQgY2hhbm5lbElkIHdvdWxkIGJlIG5lZWRlZC4gVGhlIHJlc29sdmVyIGlzIGxpbWl0ZWQgaGVyZS5cbiAgICAgIC8vIFRoaXMgaGlnaGxpZ2h0cyBhIGRlcGVuZGVuY3kgb24gZWl0aGVyIGdvb2QgcGVybWFsaW5rIHBhcnNpbmcgb3Igc3RydWN0dXJlZCBJRHMgZnJvbSBOTFUuXG5cbiAgICAgIGNvbnN0IHRlYW1zTWVzc2FnZSA9IGF3YWl0IHJlYWRNU1RlYW1zTWVzc2FnZUJhY2tlbmQodXNlcklkLCBkZXRhaWxJbnB1dCk7XG4gICAgICBpZiAodGVhbXNNZXNzYWdlICYmIHRlYW1zTWVzc2FnZS5jb250ZW50KSB7XG4gICAgICAgIG1lc3NhZ2VDb250ZW50ID0gdGVhbXNNZXNzYWdlLmNvbnRlbnQ7IC8vIENvdWxkIGJlIEhUTUwgb3IgdGV4dFxuICAgICAgICBtZXNzYWdlRGVzY3JpcHRpb24gPSBgdGhlIFRlYW1zIG1lc3NhZ2UgZnJvbSAke3RlYW1zTWVzc2FnZS51c2VyTmFtZSB8fCAnVW5rbm93bid9IGluICR7dGVhbXNNZXNzYWdlLmNoYXRJZCB8fCB0ZWFtc01lc3NhZ2UuY2hhbm5lbElkIHx8ICdVbmtub3duIGNoYXQvY2hhbm5lbCd9YDtcbiAgICAgICAgaWYgKHRlYW1zTWVzc2FnZS5jb250ZW50VHlwZSA9PT0gJ2h0bWwnKSB7XG4gICAgICAgICAgLy8gQmFzaWMgc3RyaXBwaW5nLCBleHRyYWN0SW5mb3JtYXRpb25Gcm9tTVNUZWFtc01lc3NhZ2UgYWxzbyBkb2VzIHRoaXNcbiAgICAgICAgICBtZXNzYWdlQ29udGVudCA9IG1lc3NhZ2VDb250ZW50XG4gICAgICAgICAgICAucmVwbGFjZSgvPFtePl0rPi9nLCAnICcpXG4gICAgICAgICAgICAucmVwbGFjZSgvXFxzKy9nLCAnICcpXG4gICAgICAgICAgICAudHJpbSgpO1xuICAgICAgICB9XG4gICAgICB9IGVsc2Uge1xuICAgICAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAgICAgYENvdWxkIG5vdCBmaW5kIG9yIHJlYWQgdGhlIGNvbnRlbnQgb2YgdGhlIE1TIFRlYW1zIG1lc3NhZ2UgKElEOiAke2lkZW50aWZpZXJzLm1lc3NhZ2VJZH0pLmBcbiAgICAgICAgKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBpZiAoIW1lc3NhZ2VDb250ZW50IHx8IG1lc3NhZ2VDb250ZW50LnRyaW0oKSA9PT0gJycpIHtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICBjb2RlOiAnTVNURUFNU19NRVNTQUdFX0VNUFRZJyxcbiAgICAgICAgICBtZXNzYWdlOiBgVGhlIE1TIFRlYW1zIG1lc3NhZ2UgYm9keSBmb3IgXCIke21lc3NhZ2VEZXNjcmlwdGlvbn1cIiBpcyBlbXB0eS5gLFxuICAgICAgICB9LFxuICAgICAgICBkYXRhOiB7XG4gICAgICAgICAgZXh0cmFjdGVkSW5mbzoge30sXG4gICAgICAgICAgdXNlck1lc3NhZ2U6IGBUaGUgTVMgVGVhbXMgbWVzc2FnZSBib2R5IGZvciBcIiR7bWVzc2FnZURlc2NyaXB0aW9ufVwiIGlzIGVtcHR5LCBzbyBJIGNvdWxkbid0IGV4dHJhY3QgaW5mb3JtYXRpb24uYCxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgY29uc3QgZXh0cmFjdGVkSW5mbyA9IGF3YWl0IGV4dHJhY3RJbmZvcm1hdGlvbkZyb21NU1RlYW1zTWVzc2FnZShcbiAgICAgIG1lc3NhZ2VDb250ZW50LFxuICAgICAgaW5mb3JtYXRpb25LZXl3b3Jkc1xuICAgICk7XG5cbiAgICBsZXQgZm91bmRDb3VudCA9IDA7XG4gICAgbGV0IG1lc3NhZ2VQYXJ0czogc3RyaW5nW10gPSBbYEZyb20gbXkgcmV2aWV3IG9mICR7bWVzc2FnZURlc2NyaXB0aW9ufTpgXTtcbiAgICBpbmZvcm1hdGlvbktleXdvcmRzLmZvckVhY2goKGtleXdvcmQpID0+IHtcbiAgICAgIGlmIChcbiAgICAgICAgZXh0cmFjdGVkSW5mb1trZXl3b3JkXSAhPT0gbnVsbCAmJlxuICAgICAgICBleHRyYWN0ZWRJbmZvW2tleXdvcmRdICE9PSB1bmRlZmluZWRcbiAgICAgICkge1xuICAgICAgICBtZXNzYWdlUGFydHMucHVzaChgLSBGb3IgXCIke2tleXdvcmR9XCI6ICR7ZXh0cmFjdGVkSW5mb1trZXl3b3JkXX1gKTtcbiAgICAgICAgZm91bmRDb3VudCsrO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgbWVzc2FnZVBhcnRzLnB1c2goYC0gSSBjb3VsZG4ndCBmaW5kIGluZm9ybWF0aW9uIGFib3V0IFwiJHtrZXl3b3JkfVwiLmApO1xuICAgICAgfVxuICAgIH0pO1xuXG4gICAgY29uc3QgdXNlck1lc3NhZ2UgPVxuICAgICAgZm91bmRDb3VudCA+IDBcbiAgICAgICAgPyBtZXNzYWdlUGFydHMuam9pbignXFxuJylcbiAgICAgICAgOiBgSSByZXZpZXdlZCAke21lc3NhZ2VEZXNjcmlwdGlvbn0gYnV0IGNvdWxkbid0IGZpbmQgdGhlIHNwZWNpZmljIGluZm9ybWF0aW9uIHlvdSBhc2tlZCBmb3IgKCR7aW5mb3JtYXRpb25LZXl3b3Jkcy5qb2luKCcsICcpfSkuYDtcblxuICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiB7IGV4dHJhY3RlZEluZm8sIHVzZXJNZXNzYWdlIH0gfTtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbaGFuZGxlRXh0cmFjdEluZm9Gcm9tTVNUZWFtc10gRXJyb3I6ICR7ZXJyb3IubWVzc2FnZX1gLFxuICAgICAgZXJyb3JcbiAgICApO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnTVNURUFNU19FWFRSQUNUX0ZBSUxFRCcsXG4gICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgZXJyb3IubWVzc2FnZSB8fFxuICAgICAgICAgICdGYWlsZWQgdG8gZXh0cmFjdCBpbmZvcm1hdGlvbiBmcm9tIE1TIFRlYW1zIG1lc3NhZ2UuJyxcbiAgICAgIH0sXG4gICAgICBkYXRhOiB7XG4gICAgICAgIGV4dHJhY3RlZEluZm86IHt9LFxuICAgICAgICB1c2VyTWVzc2FnZTogYFNvcnJ5LCBJIGVuY291bnRlcmVkIGFuIGVycm9yIHdoaWxlIGV4dHJhY3RpbmcgaW5mb3JtYXRpb24gZnJvbSB0aGUgTVMgVGVhbXMgbWVzc2FnZTogJHtlcnJvci5tZXNzYWdlfWAsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn1cbiJdfQ==