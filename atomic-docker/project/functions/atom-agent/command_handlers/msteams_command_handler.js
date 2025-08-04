import { understandMSTeamsSearchQueryLLM } from '../skills/llm_msteams_query_understander';
import { buildMSTeamsSearchQuery } from '../skills/nlu_msteams_helper';
import { searchMyMSTeamsMessages, readMSTeamsMessage, extractInformationFromMSTeamsMessage, getMSTeamsMessageWebUrl, } from '../skills/msTeamsSkills';
import { logger } from '../../_utils/logger';
export async function handleMSTeamsInquiry(request) {
    const { userId, rawMSTeamsSearchQuery, actionRequested, targetMessageId, targetChatId, targetTeamId, targetChannelId, } = request;
    let messageToUser = '';
    logger.debug(`[MSTeamsCommandHandler] Handling MS Teams inquiry for user ${userId}:`, request);
    try {
        let targetMessage = null;
        // Step 1: Obtain the target message
        if (targetMessageId &&
            (targetChatId || (targetTeamId && targetChannelId))) {
            const identifier = {
                messageId: targetMessageId,
            };
            if (targetChatId)
                identifier.chatId = targetChatId;
            if (targetTeamId)
                identifier.teamId = targetTeamId;
            if (targetChannelId)
                identifier.channelId = targetChannelId;
            logger.info(`[MSTeamsCommandHandler] Attempting to read specified MS Teams message:`, identifier);
            targetMessage = await readMSTeamsMessage(userId, identifier);
            if (!targetMessage) {
                messageToUser = `Sorry, I couldn't find or read the specific Teams message you referred to.`;
                logger.warn(`[MSTeamsCommandHandler] Failed to read specific message: ${messageToUser}`);
                return messageToUser;
            }
        }
        else {
            logger.info(`[MSTeamsCommandHandler] Understanding MS Teams search query: "${rawMSTeamsSearchQuery}"`);
            const structuredSearchParams = await understandMSTeamsSearchQueryLLM(rawMSTeamsSearchQuery);
            if (Object.keys(structuredSearchParams).length === 0 &&
                !rawMSTeamsSearchQuery.toLowerCase().includes('latest')) {
                messageToUser =
                    "I couldn't determine specific search criteria for Teams from your request. Could you be more precise?";
                logger.warn(`[MSTeamsCommandHandler] LLM returned empty search params for query: "${rawMSTeamsSearchQuery}"`);
                return messageToUser;
            }
            const kqlQueryString = buildMSTeamsSearchQuery(structuredSearchParams);
            logger.info(`[MSTeamsCommandHandler] Searching MS Teams messages with KQL query: "${kqlQueryString}" (Limit 5)`);
            const messagesFound = await searchMyMSTeamsMessages(userId, kqlQueryString, 5);
            if (!messagesFound || messagesFound.length === 0) {
                messageToUser =
                    "I couldn't find any Teams messages matching your criteria.";
                logger.info(`[MSTeamsCommandHandler] No messages found for KQL query: "${kqlQueryString}"`);
                return messageToUser;
            }
            if (messagesFound.length > 1 &&
                actionRequested.actionType !== 'FIND_INFO_IN_MSTEAMS_MESSAGE') {
                messageToUser =
                    'I found a few Teams messages matching your criteria:\n';
                messagesFound.slice(0, 3).forEach((msg, index) => {
                    const msgTextPreview = msg.content
                        ? msg.content.replace(/<[^>]+>/g, ' ').substring(0, 70) + '...'
                        : 'No text content';
                    const context = msg.channelName
                        ? `in ${msg.channelName}`
                        : msg.chatId
                            ? `in chat ${msg.chatId.substring(0, 10)}...`
                            : '';
                    messageToUser += `${index + 1}. From ${msg.userName || 'Unknown User'} ${context}: "${msgTextPreview}" (ID: ...${msg.id.slice(-6)})\n`;
                });
                if (messagesFound.length > 3)
                    messageToUser += `And ${messagesFound.length - 3} more.\n`;
                messageToUser +=
                    'Which one are you interested in? You can tell me the number or provide more details (like its ID).';
                logger.info(`[MSTeamsCommandHandler] Multiple messages found, clarification needed.`);
                return messageToUser;
            }
            targetMessage = messagesFound[0];
            logger.info(`[MSTeamsCommandHandler] Single message identified for processing. ID: ${targetMessage.id}`);
            // Ensure full content if search result was partial (heuristic: check if content seems too short or lacks detail)
            // This might require a more robust check or always fetching full details if search API returns summaries.
            // For now, assume search returns enough, or readMSTeamsMessage is called if specific ID is known.
            // If targetMessage.content seems like a snippet, fetch full.
            // This check is simplified; Graph search results for messages usually contain the full body.
        }
        if (!targetMessage) {
            messageToUser =
                "I couldn't identify a specific Teams message to process.";
            logger.warn(`[MSTeamsCommandHandler] No target message identified.`);
            return messageToUser;
        }
        // Step 2: Perform the requested action
        const messageDesc = `the Teams message from ${targetMessage.userName || 'Unknown User'}` +
            (targetMessage.channelName
                ? ` in ${targetMessage.channelName}`
                : targetMessage.chatId
                    ? ` in chat`
                    : '');
        switch (actionRequested.actionType) {
            case 'GET_MSTEAMS_MESSAGE_CONTENT':
                const contentPreview = targetMessage.content
                    ? targetMessage.content.replace(/<[^>]+>/g, ' ').substring(0, 200) +
                        '...'
                    : 'it appears to have no readable content.';
                messageToUser = `The content of ${messageDesc} (ID: ...${targetMessage.id.slice(-6)}) starts with: "${contentPreview}".`;
                break;
            case 'FIND_INFO_IN_MSTEAMS_MESSAGE':
                if (!targetMessage.content) {
                    messageToUser = `${messageDesc} (ID: ...${targetMessage.id.slice(-6)}) doesn't seem to have any content for me to analyze.`;
                    break;
                }
                const keywords = actionRequested.infoKeywords || [];
                if (keywords.length === 0) {
                    messageToUser = `You asked me to find specific information in ${messageDesc}, but didn't specify what to look for.`;
                    break;
                }
                logger.info(`[MSTeamsCommandHandler] Extracting info for keywords [${keywords.join(', ')}] from message ID ${targetMessage.id}`);
                const extracted = await extractInformationFromMSTeamsMessage(targetMessage.content, keywords);
                let foundAnyInfo = false;
                let parts = [
                    `Regarding ${messageDesc} (ID: ...${targetMessage.id.slice(-6)}):`,
                ];
                for (const keyword of keywords) {
                    const val = extracted[keyword];
                    if (val) {
                        parts.push(`- For "${keyword}", I found: ${val}.`);
                        foundAnyInfo = true;
                    }
                    else {
                        parts.push(`- I couldn't find specific information about "${keyword}".`);
                    }
                }
                messageToUser = foundAnyInfo
                    ? parts.join('\n')
                    : `I scanned ${messageDesc} for "${keywords.join(', ')}", but couldn't find those details.`;
                break;
            case 'GET_MSTEAMS_MESSAGE_LINK':
                if (targetMessage.webUrl) {
                    messageToUser = `Here's the link to ${messageDesc} (ID: ...${targetMessage.id.slice(-6)}): ${targetMessage.webUrl}`;
                }
                else {
                    // Attempt to fetch it if not directly on the object (though our service populates it)
                    const identifier = {
                        messageId: targetMessage.id,
                    };
                    if (targetMessage.chatId)
                        identifier.chatId = targetMessage.chatId;
                    if (targetMessage.teamId)
                        identifier.teamId = targetMessage.teamId;
                    if (targetMessage.channelId)
                        identifier.channelId = targetMessage.channelId;
                    const link = await getMSTeamsMessageWebUrl(userId, identifier);
                    if (link) {
                        messageToUser = `Here's the link to ${messageDesc} (ID: ...${targetMessage.id.slice(-6)}): ${link}`;
                    }
                    else {
                        messageToUser = `I tried, but I couldn't get a direct link for ${messageDesc} (ID: ...${targetMessage.id.slice(-6)}).`;
                    }
                }
                break;
            case 'SUMMARIZE_MSTEAMS_MESSAGE':
                messageToUser = `I can't summarize Teams messages yet, but I found ${messageDesc} (ID: ...${targetMessage.id.slice(-6)}).`;
                break;
            default:
                // @ts-expect-error actionType might be an unexpected value
                messageToUser = `I found ${messageDesc} (ID: ...${targetMessage.id.slice(-6)}). I'm not sure how to handle your request: ${actionRequested.actionType}.`;
                logger.warn(`[MSTeamsCommandHandler] Unknown actionType: ${actionRequested.actionType}`);
        }
        logger.info(`[MSTeamsCommandHandler] Final response for user ${userId}: "${messageToUser.substring(0, 150)}..."`);
        return messageToUser;
    }
    catch (error) {
        logger.error(`[MSTeamsCommandHandler] Critical error in handleMSTeamsInquiry for user ${userId}:`, error);
        messageToUser = `I encountered an issue while processing your Microsoft Teams request: ${error.message || 'Unknown error'}. Please try again.`;
        return messageToUser;
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibXN0ZWFtc19jb21tYW5kX2hhbmRsZXIuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJtc3RlYW1zX2NvbW1hbmRfaGFuZGxlci50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxPQUFPLEVBQUUsK0JBQStCLEVBQUUsTUFBTSwwQ0FBMEMsQ0FBQztBQUMzRixPQUFPLEVBQUUsdUJBQXVCLEVBQUUsTUFBTSw4QkFBOEIsQ0FBQztBQUN2RSxPQUFPLEVBQ0wsdUJBQXVCLEVBQ3ZCLGtCQUFrQixFQUNsQixvQ0FBb0MsRUFDcEMsdUJBQXVCLEdBRXhCLE1BQU0seUJBQXlCLENBQUM7QUFFakMsT0FBTyxFQUFFLE1BQU0sRUFBRSxNQUFNLHFCQUFxQixDQUFDO0FBeUI3QyxNQUFNLENBQUMsS0FBSyxVQUFVLG9CQUFvQixDQUN4QyxPQUFnQztJQUVoQyxNQUFNLEVBQ0osTUFBTSxFQUNOLHFCQUFxQixFQUNyQixlQUFlLEVBQ2YsZUFBZSxFQUNmLFlBQVksRUFDWixZQUFZLEVBQ1osZUFBZSxHQUNoQixHQUFHLE9BQU8sQ0FBQztJQUNaLElBQUksYUFBYSxHQUFHLEVBQUUsQ0FBQztJQUV2QixNQUFNLENBQUMsS0FBSyxDQUNWLDhEQUE4RCxNQUFNLEdBQUcsRUFDdkUsT0FBTyxDQUNSLENBQUM7SUFFRixJQUFJLENBQUM7UUFDSCxJQUFJLGFBQWEsR0FBMEIsSUFBSSxDQUFDO1FBRWhELG9DQUFvQztRQUNwQyxJQUNFLGVBQWU7WUFDZixDQUFDLFlBQVksSUFBSSxDQUFDLFlBQVksSUFBSSxlQUFlLENBQUMsQ0FBQyxFQUNuRCxDQUFDO1lBQ0QsTUFBTSxVQUFVLEdBQWlDO2dCQUMvQyxTQUFTLEVBQUUsZUFBZTthQUMzQixDQUFDO1lBQ0YsSUFBSSxZQUFZO2dCQUFFLFVBQVUsQ0FBQyxNQUFNLEdBQUcsWUFBWSxDQUFDO1lBQ25ELElBQUksWUFBWTtnQkFBRSxVQUFVLENBQUMsTUFBTSxHQUFHLFlBQVksQ0FBQztZQUNuRCxJQUFJLGVBQWU7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LGFBQWEsQ0FBQztJQUN2QixDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IHVuZGVyc3RhbmRNU1RlYW1zU2VhcmNoUXVlcnlMTE0gfSBmcm9tICcuLi9za2lsbHMvbGxtX21zdGVhbXNfcXVlcnlfdW5kZXJzdGFuZGVyJztcbmltcG9ydCB7IGJ1aWxkTVNUZWFtc1NlYXJjaFF1ZXJ5IH0gZnJvbSAnLi4vc2tpbGxzL25sdV9tc3RlYW1zX2hlbHBlcic7XG5pbXBvcnQge1xuICBzZWFyY2hNeU1TVGVhbXNNZXNzYWdlcyxcbiAgcmVhZE1TVGVhbXNNZXNzYWdlLFxuICBleHRyYWN0SW5mb3JtYXRpb25Gcm9tTVNUZWFtc01lc3NhZ2UsXG4gIGdldE1TVGVhbXNNZXNzYWdlV2ViVXJsLFxuICBHZXRNU1RlYW1zTWVzc2FnZURldGFpbElucHV0LCAvLyBJbnB1dCB0eXBlIGZvciByZWFkTVNUZWFtc01lc3NhZ2Vcbn0gZnJvbSAnLi4vc2tpbGxzL21zVGVhbXNTa2lsbHMnO1xuaW1wb3J0IHsgTVNUZWFtc01lc3NhZ2UgfSBmcm9tICcuLi90eXBlcyc7XG5pbXBvcnQgeyBsb2dnZXIgfSBmcm9tICcuLi8uLi9fdXRpbHMvbG9nZ2VyJztcblxuZXhwb3J0IHR5cGUgTVNUZWFtc0FjdGlvblR5cGUgPVxuICB8ICdHRVRfTVNURUFNU19NRVNTQUdFX0NPTlRFTlQnXG4gIHwgJ0ZJTkRfSU5GT19JTl9NU1RFQU1TX01FU1NBR0UnXG4gIHwgJ0dFVF9NU1RFQU1TX01FU1NBR0VfTElOSydcbiAgfCAnU1VNTUFSSVpFX01TVEVBTVNfTUVTU0FHRSc7IC8vIEZ1dHVyZSBjYXBhYmlsaXR5XG5cbmV4cG9ydCBpbnRlcmZhY2UgTVNUZWFtc0FjdGlvblJlcXVlc3Qge1xuICBhY3Rpb25UeXBlOiBNU1RlYW1zQWN0aW9uVHlwZTtcbiAgaW5mb0tleXdvcmRzPzogc3RyaW5nW107XG4gIG5hdHVyYWxMYW5ndWFnZVF1ZXN0aW9uPzogc3RyaW5nO1xufVxuXG5leHBvcnQgaW50ZXJmYWNlIFBhcnNlZE5sdU1TVGVhbXNSZXF1ZXN0IHtcbiAgdXNlcklkOiBzdHJpbmc7XG4gIHJhd01TVGVhbXNTZWFyY2hRdWVyeTogc3RyaW5nO1xuICBhY3Rpb25SZXF1ZXN0ZWQ6IE1TVGVhbXNBY3Rpb25SZXF1ZXN0O1xuICAvLyBGaWVsZHMgdG8gZGlyZWN0bHkgdGFyZ2V0IGEgbWVzc2FnZSBpZiBOTFUgaWRlbnRpZmllcyB0aGVtXG4gIHRhcmdldE1lc3NhZ2VJZD86IHN0cmluZztcbiAgdGFyZ2V0Q2hhdElkPzogc3RyaW5nO1xuICB0YXJnZXRUZWFtSWQ/OiBzdHJpbmc7XG4gIHRhcmdldENoYW5uZWxJZD86IHN0cmluZztcbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZU1TVGVhbXNJbnF1aXJ5KFxuICByZXF1ZXN0OiBQYXJzZWRObHVNU1RlYW1zUmVxdWVzdFxuKTogUHJvbWlzZTxzdHJpbmc+IHtcbiAgY29uc3Qge1xuICAgIHVzZXJJZCxcbiAgICByYXdNU1RlYW1zU2VhcmNoUXVlcnksXG4gICAgYWN0aW9uUmVxdWVzdGVkLFxuICAgIHRhcmdldE1lc3NhZ2VJZCxcbiAgICB0YXJnZXRDaGF0SWQsXG4gICAgdGFyZ2V0VGVhbUlkLFxuICAgIHRhcmdldENoYW5uZWxJZCxcbiAgfSA9IHJlcXVlc3Q7XG4gIGxldCBtZXNzYWdlVG9Vc2VyID0gJyc7XG5cbiAgbG9nZ2VyLmRlYnVnKFxuICAgIGBbTVNUZWFtc0NvbW1hbmRIYW5kbGVyXSBIYW5kbGluZyBNUyBUZWFtcyBpbnF1aXJ5IGZvciB1c2VyICR7dXNlcklkfTpgLFxuICAgIHJlcXVlc3RcbiAgKTtcblxuICB0cnkge1xuICAgIGxldCB0YXJnZXRNZXNzYWdlOiBNU1RlYW1zTWVzc2FnZSB8IG51bGwgPSBudWxsO1xuXG4gICAgLy8gU3RlcCAxOiBPYnRhaW4gdGhlIHRhcmdldCBtZXNzYWdlXG4gICAgaWYgKFxuICAgICAgdGFyZ2V0TWVzc2FnZUlkICYmXG4gICAgICAodGFyZ2V0Q2hhdElkIHx8ICh0YXJnZXRUZWFtSWQgJiYgdGFyZ2V0Q2hhbm5lbElkKSlcbiAgICApIHtcbiAgICAgIGNvbnN0IGlkZW50aWZpZXI6IEdldE1TVGVhbXNNZXNzYWdlRGV0YWlsSW5wdXQgPSB7XG4gICAgICAgIG1lc3NhZ2VJZDogdGFyZ2V0TWVzc2FnZUlkLFxuICAgICAgfTtcbiAgICAgIGlmICh0YXJnZXRDaGF0SWQpIGlkZW50aWZpZXIuY2hhdElkID0gdGFyZ2V0Q2hhdElkO1xuICAgICAgaWYgKHRhcmdldFRlYW1JZCkgaWRlbnRpZmllci50ZWFtSWQgPSB0YXJnZXRUZWFtSWQ7XG4gICAgICBpZiAodGFyZ2V0Q2hhbm5lbElkKSBpZGVudGlmaWVyLmNoYW5uZWxJZCA9IHRhcmdldENoYW5uZWxJZDtcblxuICAgICAgbG9nZ2VyLmluZm8oXG4gICAgICAgIGBbTVNUZWFtc0NvbW1hbmRIYW5kbGVyXSBBdHRlbXB0aW5nIHRvIHJlYWQgc3BlY2lmaWVkIE1TIFRlYW1zIG1lc3NhZ2U6YCxcbiAgICAgICAgaWRlbnRpZmllclxuICAgICAgKTtcbiAgICAgIHRhcmdldE1lc3NhZ2UgPSBhd2FpdCByZWFkTVNUZWFtc01lc3NhZ2UodXNlcklkLCBpZGVudGlmaWVyKTtcbiAgICAgIGlmICghdGFyZ2V0TWVzc2FnZSkge1xuICAgICAgICBtZXNzYWdlVG9Vc2VyID0gYFNvcnJ5LCBJIGNvdWxkbid0IGZpbmQgb3IgcmVhZCB0aGUgc3BlY2lmaWMgVGVhbXMgbWVzc2FnZSB5b3UgcmVmZXJyZWQgdG8uYDtcbiAgICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgICAgYFtNU1RlYW1zQ29tbWFuZEhhbmRsZXJdIEZhaWxlZCB0byByZWFkIHNwZWNpZmljIG1lc3NhZ2U6ICR7bWVzc2FnZVRvVXNlcn1gXG4gICAgICAgICk7XG4gICAgICAgIHJldHVybiBtZXNzYWdlVG9Vc2VyO1xuICAgICAgfVxuICAgIH0gZWxzZSB7XG4gICAgICBsb2dnZXIuaW5mbyhcbiAgICAgICAgYFtNU1RlYW1zQ29tbWFuZEhhbmRsZXJdIFVuZGVyc3RhbmRpbmcgTVMgVGVhbXMgc2VhcmNoIHF1ZXJ5OiBcIiR7cmF3TVNUZWFtc1NlYXJjaFF1ZXJ5fVwiYFxuICAgICAgKTtcbiAgICAgIGNvbnN0IHN0cnVjdHVyZWRTZWFyY2hQYXJhbXMgPSBhd2FpdCB1bmRlcnN0YW5kTVNUZWFtc1NlYXJjaFF1ZXJ5TExNKFxuICAgICAgICByYXdNU1RlYW1zU2VhcmNoUXVlcnlcbiAgICAgICk7XG5cbiAgICAgIGlmIChcbiAgICAgICAgT2JqZWN0LmtleXMoc3RydWN0dXJlZFNlYXJjaFBhcmFtcykubGVuZ3RoID09PSAwICYmXG4gICAgICAgICFyYXdNU1RlYW1zU2VhcmNoUXVlcnkudG9Mb3dlckNhc2UoKS5pbmNsdWRlcygnbGF0ZXN0JylcbiAgICAgICkge1xuICAgICAgICBtZXNzYWdlVG9Vc2VyID1cbiAgICAgICAgICBcIkkgY291bGRuJ3QgZGV0ZXJtaW5lIHNwZWNpZmljIHNlYXJjaCBjcml0ZXJpYSBmb3IgVGVhbXMgZnJvbSB5b3VyIHJlcXVlc3QuIENvdWxkIHlvdSBiZSBtb3JlIHByZWNpc2U/XCI7XG4gICAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICAgIGBbTVNUZWFtc0NvbW1hbmRIYW5kbGVyXSBMTE0gcmV0dXJuZWQgZW1wdHkgc2VhcmNoIHBhcmFtcyBmb3IgcXVlcnk6IFwiJHtyYXdNU1RlYW1zU2VhcmNoUXVlcnl9XCJgXG4gICAgICAgICk7XG4gICAgICAgIHJldHVybiBtZXNzYWdlVG9Vc2VyO1xuICAgICAgfVxuXG4gICAgICBjb25zdCBrcWxRdWVyeVN0cmluZyA9IGJ1aWxkTVNUZWFtc1NlYXJjaFF1ZXJ5KHN0cnVjdHVyZWRTZWFyY2hQYXJhbXMpO1xuICAgICAgbG9nZ2VyLmluZm8oXG4gICAgICAgIGBbTVNUZWFtc0NvbW1hbmRIYW5kbGVyXSBTZWFyY2hpbmcgTVMgVGVhbXMgbWVzc2FnZXMgd2l0aCBLUUwgcXVlcnk6IFwiJHtrcWxRdWVyeVN0cmluZ31cIiAoTGltaXQgNSlgXG4gICAgICApO1xuICAgICAgY29uc3QgbWVzc2FnZXNGb3VuZCA9IGF3YWl0IHNlYXJjaE15TVNUZWFtc01lc3NhZ2VzKFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIGtxbFF1ZXJ5U3RyaW5nLFxuICAgICAgICA1XG4gICAgICApO1xuXG4gICAgICBpZiAoIW1lc3NhZ2VzRm91bmQgfHwgbWVzc2FnZXNGb3VuZC5sZW5ndGggPT09IDApIHtcbiAgICAgICAgbWVzc2FnZVRvVXNlciA9XG4gICAgICAgICAgXCJJIGNvdWxkbid0IGZpbmQgYW55IFRlYW1zIG1lc3NhZ2VzIG1hdGNoaW5nIHlvdXIgY3JpdGVyaWEuXCI7XG4gICAgICAgIGxvZ2dlci5pbmZvKFxuICAgICAgICAgIGBbTVNUZWFtc0NvbW1hbmRIYW5kbGVyXSBObyBtZXNzYWdlcyBmb3VuZCBmb3IgS1FMIHF1ZXJ5OiBcIiR7a3FsUXVlcnlTdHJpbmd9XCJgXG4gICAgICAgICk7XG4gICAgICAgIHJldHVybiBtZXNzYWdlVG9Vc2VyO1xuICAgICAgfVxuXG4gICAgICBpZiAoXG4gICAgICAgIG1lc3NhZ2VzRm91bmQubGVuZ3RoID4gMSAmJlxuICAgICAgICBhY3Rpb25SZXF1ZXN0ZWQuYWN0aW9uVHlwZSAhPT0gJ0ZJTkRfSU5GT19JTl9NU1RFQU1TX01FU1NBR0UnXG4gICAgICApIHtcbiAgICAgICAgbWVzc2FnZVRvVXNlciA9XG4gICAgICAgICAgJ0kgZm91bmQgYSBmZXcgVGVhbXMgbWVzc2FnZXMgbWF0Y2hpbmcgeW91ciBjcml0ZXJpYTpcXG4nO1xuICAgICAgICBtZXNzYWdlc0ZvdW5kLnNsaWNlKDAsIDMpLmZvckVhY2goKG1zZywgaW5kZXgpID0+IHtcbiAgICAgICAgICBjb25zdCBtc2dUZXh0UHJldmlldyA9IG1zZy5jb250ZW50XG4gICAgICAgICAgICA/IG1zZy5jb250ZW50LnJlcGxhY2UoLzxbXj5dKz4vZywgJyAnKS5zdWJzdHJpbmcoMCwgNzApICsgJy4uLidcbiAgICAgICAgICAgIDogJ05vIHRleHQgY29udGVudCc7XG4gICAgICAgICAgY29uc3QgY29udGV4dCA9IG1zZy5jaGFubmVsTmFtZVxuICAgICAgICAgICAgPyBgaW4gJHttc2cuY2hhbm5lbE5hbWV9YFxuICAgICAgICAgICAgOiBtc2cuY2hhdElkXG4gICAgICAgICAgICAgID8gYGluIGNoYXQgJHttc2cuY2hhdElkLnN1YnN0cmluZygwLCAxMCl9Li4uYFxuICAgICAgICAgICAgICA6ICcnO1xuICAgICAgICAgIG1lc3NhZ2VUb1VzZXIgKz0gYCR7aW5kZXggKyAxfS4gRnJvbSAke21zZy51c2VyTmFtZSB8fCAnVW5rbm93biBVc2VyJ30gJHtjb250ZXh0fTogXCIke21zZ1RleHRQcmV2aWV3fVwiIChJRDogLi4uJHttc2cuaWQuc2xpY2UoLTYpfSlcXG5gO1xuICAgICAgICB9KTtcbiAgICAgICAgaWYgKG1lc3NhZ2VzRm91bmQubGVuZ3RoID4gMylcbiAgICAgICAgICBtZXNzYWdlVG9Vc2VyICs9IGBBbmQgJHttZXNzYWdlc0ZvdW5kLmxlbmd0aCAtIDN9IG1vcmUuXFxuYDtcbiAgICAgICAgbWVzc2FnZVRvVXNlciArPVxuICAgICAgICAgICdXaGljaCBvbmUgYXJlIHlvdSBpbnRlcmVzdGVkIGluPyBZb3UgY2FuIHRlbGwgbWUgdGhlIG51bWJlciBvciBwcm92aWRlIG1vcmUgZGV0YWlscyAobGlrZSBpdHMgSUQpLic7XG4gICAgICAgIGxvZ2dlci5pbmZvKFxuICAgICAgICAgIGBbTVNUZWFtc0NvbW1hbmRIYW5kbGVyXSBNdWx0aXBsZSBtZXNzYWdlcyBmb3VuZCwgY2xhcmlmaWNhdGlvbiBuZWVkZWQuYFxuICAgICAgICApO1xuICAgICAgICByZXR1cm4gbWVzc2FnZVRvVXNlcjtcbiAgICAgIH1cbiAgICAgIHRhcmdldE1lc3NhZ2UgPSBtZXNzYWdlc0ZvdW5kWzBdO1xuICAgICAgbG9nZ2VyLmluZm8oXG4gICAgICAgIGBbTVNUZWFtc0NvbW1hbmRIYW5kbGVyXSBTaW5nbGUgbWVzc2FnZSBpZGVudGlmaWVkIGZvciBwcm9jZXNzaW5nLiBJRDogJHt0YXJnZXRNZXNzYWdlLmlkfWBcbiAgICAgICk7XG5cbiAgICAgIC8vIEVuc3VyZSBmdWxsIGNvbnRlbnQgaWYgc2VhcmNoIHJlc3VsdCB3YXMgcGFydGlhbCAoaGV1cmlzdGljOiBjaGVjayBpZiBjb250ZW50IHNlZW1zIHRvbyBzaG9ydCBvciBsYWNrcyBkZXRhaWwpXG4gICAgICAvLyBUaGlzIG1pZ2h0IHJlcXVpcmUgYSBtb3JlIHJvYnVzdCBjaGVjayBvciBhbHdheXMgZmV0Y2hpbmcgZnVsbCBkZXRhaWxzIGlmIHNlYXJjaCBBUEkgcmV0dXJucyBzdW1tYXJpZXMuXG4gICAgICAvLyBGb3Igbm93LCBhc3N1bWUgc2VhcmNoIHJldHVybnMgZW5vdWdoLCBvciByZWFkTVNUZWFtc01lc3NhZ2UgaXMgY2FsbGVkIGlmIHNwZWNpZmljIElEIGlzIGtub3duLlxuICAgICAgLy8gSWYgdGFyZ2V0TWVzc2FnZS5jb250ZW50IHNlZW1zIGxpa2UgYSBzbmlwcGV0LCBmZXRjaCBmdWxsLlxuICAgICAgLy8gVGhpcyBjaGVjayBpcyBzaW1wbGlmaWVkOyBHcmFwaCBzZWFyY2ggcmVzdWx0cyBmb3IgbWVzc2FnZXMgdXN1YWxseSBjb250YWluIHRoZSBmdWxsIGJvZHkuXG4gICAgfVxuXG4gICAgaWYgKCF0YXJnZXRNZXNzYWdlKSB7XG4gICAgICBtZXNzYWdlVG9Vc2VyID1cbiAgICAgICAgXCJJIGNvdWxkbid0IGlkZW50aWZ5IGEgc3BlY2lmaWMgVGVhbXMgbWVzc2FnZSB0byBwcm9jZXNzLlwiO1xuICAgICAgbG9nZ2VyLndhcm4oYFtNU1RlYW1zQ29tbWFuZEhhbmRsZXJdIE5vIHRhcmdldCBtZXNzYWdlIGlkZW50aWZpZWQuYCk7XG4gICAgICByZXR1cm4gbWVzc2FnZVRvVXNlcjtcbiAgICB9XG5cbiAgICAvLyBTdGVwIDI6IFBlcmZvcm0gdGhlIHJlcXVlc3RlZCBhY3Rpb25cbiAgICBjb25zdCBtZXNzYWdlRGVzYyA9XG4gICAgICBgdGhlIFRlYW1zIG1lc3NhZ2UgZnJvbSAke3RhcmdldE1lc3NhZ2UudXNlck5hbWUgfHwgJ1Vua25vd24gVXNlcid9YCArXG4gICAgICAodGFyZ2V0TWVzc2FnZS5jaGFubmVsTmFtZVxuICAgICAgICA/IGAgaW4gJHt0YXJnZXRNZXNzYWdlLmNoYW5uZWxOYW1lfWBcbiAgICAgICAgOiB0YXJnZXRNZXNzYWdlLmNoYXRJZFxuICAgICAgICAgID8gYCBpbiBjaGF0YFxuICAgICAgICAgIDogJycpO1xuXG4gICAgc3dpdGNoIChhY3Rpb25SZXF1ZXN0ZWQuYWN0aW9uVHlwZSkge1xuICAgICAgY2FzZSAnR0VUX01TVEVBTVNfTUVTU0FHRV9DT05URU5UJzpcbiAgICAgICAgY29uc3QgY29udGVudFByZXZpZXcgPSB0YXJnZXRNZXNzYWdlLmNvbnRlbnRcbiAgICAgICAgICA/IHRhcmdldE1lc3NhZ2UuY29udGVudC5yZXBsYWNlKC88W14+XSs+L2csICcgJykuc3Vic3RyaW5nKDAsIDIwMCkgK1xuICAgICAgICAgICAgJy4uLidcbiAgICAgICAgICA6ICdpdCBhcHBlYXJzIHRvIGhhdmUgbm8gcmVhZGFibGUgY29udGVudC4nO1xuICAgICAgICBtZXNzYWdlVG9Vc2VyID0gYFRoZSBjb250ZW50IG9mICR7bWVzc2FnZURlc2N9IChJRDogLi4uJHt0YXJnZXRNZXNzYWdlLmlkLnNsaWNlKC02KX0pIHN0YXJ0cyB3aXRoOiBcIiR7Y29udGVudFByZXZpZXd9XCIuYDtcbiAgICAgICAgYnJlYWs7XG5cbiAgICAgIGNhc2UgJ0ZJTkRfSU5GT19JTl9NU1RFQU1TX01FU1NBR0UnOlxuICAgICAgICBpZiAoIXRhcmdldE1lc3NhZ2UuY29udGVudCkge1xuICAgICAgICAgIG1lc3NhZ2VUb1VzZXIgPSBgJHttZXNzYWdlRGVzY30gKElEOiAuLi4ke3RhcmdldE1lc3NhZ2UuaWQuc2xpY2UoLTYpfSkgZG9lc24ndCBzZWVtIHRvIGhhdmUgYW55IGNvbnRlbnQgZm9yIG1lIHRvIGFuYWx5emUuYDtcbiAgICAgICAgICBicmVhaztcbiAgICAgICAgfVxuICAgICAgICBjb25zdCBrZXl3b3JkcyA9IGFjdGlvblJlcXVlc3RlZC5pbmZvS2V5d29yZHMgfHwgW107XG4gICAgICAgIGlmIChrZXl3b3Jkcy5sZW5ndGggPT09IDApIHtcbiAgICAgICAgICBtZXNzYWdlVG9Vc2VyID0gYFlvdSBhc2tlZCBtZSB0byBmaW5kIHNwZWNpZmljIGluZm9ybWF0aW9uIGluICR7bWVzc2FnZURlc2N9LCBidXQgZGlkbid0IHNwZWNpZnkgd2hhdCB0byBsb29rIGZvci5gO1xuICAgICAgICAgIGJyZWFrO1xuICAgICAgICB9XG4gICAgICAgIGxvZ2dlci5pbmZvKFxuICAgICAgICAgIGBbTVNUZWFtc0NvbW1hbmRIYW5kbGVyXSBFeHRyYWN0aW5nIGluZm8gZm9yIGtleXdvcmRzIFske2tleXdvcmRzLmpvaW4oJywgJyl9XSBmcm9tIG1lc3NhZ2UgSUQgJHt0YXJnZXRNZXNzYWdlLmlkfWBcbiAgICAgICAgKTtcbiAgICAgICAgY29uc3QgZXh0cmFjdGVkID0gYXdhaXQgZXh0cmFjdEluZm9ybWF0aW9uRnJvbU1TVGVhbXNNZXNzYWdlKFxuICAgICAgICAgIHRhcmdldE1lc3NhZ2UuY29udGVudCxcbiAgICAgICAgICBrZXl3b3Jkc1xuICAgICAgICApO1xuICAgICAgICBsZXQgZm91bmRBbnlJbmZvID0gZmFsc2U7XG4gICAgICAgIGxldCBwYXJ0czogc3RyaW5nW10gPSBbXG4gICAgICAgICAgYFJlZ2FyZGluZyAke21lc3NhZ2VEZXNjfSAoSUQ6IC4uLiR7dGFyZ2V0TWVzc2FnZS5pZC5zbGljZSgtNil9KTpgLFxuICAgICAgICBdO1xuICAgICAgICBmb3IgKGNvbnN0IGtleXdvcmQgb2Yga2V5d29yZHMpIHtcbiAgICAgICAgICBjb25zdCB2YWwgPSBleHRyYWN0ZWRba2V5d29yZF07XG4gICAgICAgICAgaWYgKHZhbCkge1xuICAgICAgICAgICAgcGFydHMucHVzaChgLSBGb3IgXCIke2tleXdvcmR9XCIsIEkgZm91bmQ6ICR7dmFsfS5gKTtcbiAgICAgICAgICAgIGZvdW5kQW55SW5mbyA9IHRydWU7XG4gICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIHBhcnRzLnB1c2goXG4gICAgICAgICAgICAgIGAtIEkgY291bGRuJ3QgZmluZCBzcGVjaWZpYyBpbmZvcm1hdGlvbiBhYm91dCBcIiR7a2V5d29yZH1cIi5gXG4gICAgICAgICAgICApO1xuICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgICAgICBtZXNzYWdlVG9Vc2VyID0gZm91bmRBbnlJbmZvXG4gICAgICAgICAgPyBwYXJ0cy5qb2luKCdcXG4nKVxuICAgICAgICAgIDogYEkgc2Nhbm5lZCAke21lc3NhZ2VEZXNjfSBmb3IgXCIke2tleXdvcmRzLmpvaW4oJywgJyl9XCIsIGJ1dCBjb3VsZG4ndCBmaW5kIHRob3NlIGRldGFpbHMuYDtcbiAgICAgICAgYnJlYWs7XG5cbiAgICAgIGNhc2UgJ0dFVF9NU1RFQU1TX01FU1NBR0VfTElOSyc6XG4gICAgICAgIGlmICh0YXJnZXRNZXNzYWdlLndlYlVybCkge1xuICAgICAgICAgIG1lc3NhZ2VUb1VzZXIgPSBgSGVyZSdzIHRoZSBsaW5rIHRvICR7bWVzc2FnZURlc2N9IChJRDogLi4uJHt0YXJnZXRNZXNzYWdlLmlkLnNsaWNlKC02KX0pOiAke3RhcmdldE1lc3NhZ2Uud2ViVXJsfWA7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgLy8gQXR0ZW1wdCB0byBmZXRjaCBpdCBpZiBub3QgZGlyZWN0bHkgb24gdGhlIG9iamVjdCAodGhvdWdoIG91ciBzZXJ2aWNlIHBvcHVsYXRlcyBpdClcbiAgICAgICAgICBjb25zdCBpZGVudGlmaWVyOiBHZXRNU1RlYW1zTWVzc2FnZURldGFpbElucHV0ID0ge1xuICAgICAgICAgICAgbWVzc2FnZUlkOiB0YXJnZXRNZXNzYWdlLmlkLFxuICAgICAgICAgIH07XG4gICAgICAgICAgaWYgKHRhcmdldE1lc3NhZ2UuY2hhdElkKSBpZGVudGlmaWVyLmNoYXRJZCA9IHRhcmdldE1lc3NhZ2UuY2hhdElkO1xuICAgICAgICAgIGlmICh0YXJnZXRNZXNzYWdlLnRlYW1JZCkgaWRlbnRpZmllci50ZWFtSWQgPSB0YXJnZXRNZXNzYWdlLnRlYW1JZDtcbiAgICAgICAgICBpZiAodGFyZ2V0TWVzc2FnZS5jaGFubmVsSWQpXG4gICAgICAgICAgICBpZGVudGlmaWVyLmNoYW5uZWxJZCA9IHRhcmdldE1lc3NhZ2UuY2hhbm5lbElkO1xuICAgICAgICAgIGNvbnN0IGxpbmsgPSBhd2FpdCBnZXRNU1RlYW1zTWVzc2FnZVdlYlVybCh1c2VySWQsIGlkZW50aWZpZXIpO1xuICAgICAgICAgIGlmIChsaW5rKSB7XG4gICAgICAgICAgICBtZXNzYWdlVG9Vc2VyID0gYEhlcmUncyB0aGUgbGluayB0byAke21lc3NhZ2VEZXNjfSAoSUQ6IC4uLiR7dGFyZ2V0TWVzc2FnZS5pZC5zbGljZSgtNil9KTogJHtsaW5rfWA7XG4gICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIG1lc3NhZ2VUb1VzZXIgPSBgSSB0cmllZCwgYnV0IEkgY291bGRuJ3QgZ2V0IGEgZGlyZWN0IGxpbmsgZm9yICR7bWVzc2FnZURlc2N9IChJRDogLi4uJHt0YXJnZXRNZXNzYWdlLmlkLnNsaWNlKC02KX0pLmA7XG4gICAgICAgICAgfVxuICAgICAgICB9XG4gICAgICAgIGJyZWFrO1xuXG4gICAgICBjYXNlICdTVU1NQVJJWkVfTVNURUFNU19NRVNTQUdFJzpcbiAgICAgICAgbWVzc2FnZVRvVXNlciA9IGBJIGNhbid0IHN1bW1hcml6ZSBUZWFtcyBtZXNzYWdlcyB5ZXQsIGJ1dCBJIGZvdW5kICR7bWVzc2FnZURlc2N9IChJRDogLi4uJHt0YXJnZXRNZXNzYWdlLmlkLnNsaWNlKC02KX0pLmA7XG4gICAgICAgIGJyZWFrO1xuXG4gICAgICBkZWZhdWx0OlxuICAgICAgICAvLyBAdHMtZXhwZWN0LWVycm9yIGFjdGlvblR5cGUgbWlnaHQgYmUgYW4gdW5leHBlY3RlZCB2YWx1ZVxuICAgICAgICBtZXNzYWdlVG9Vc2VyID0gYEkgZm91bmQgJHttZXNzYWdlRGVzY30gKElEOiAuLi4ke3RhcmdldE1lc3NhZ2UuaWQuc2xpY2UoLTYpfSkuIEknbSBub3Qgc3VyZSBob3cgdG8gaGFuZGxlIHlvdXIgcmVxdWVzdDogJHthY3Rpb25SZXF1ZXN0ZWQuYWN0aW9uVHlwZX0uYDtcbiAgICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgICAgYFtNU1RlYW1zQ29tbWFuZEhhbmRsZXJdIFVua25vd24gYWN0aW9uVHlwZTogJHthY3Rpb25SZXF1ZXN0ZWQuYWN0aW9uVHlwZX1gXG4gICAgICAgICk7XG4gICAgfVxuXG4gICAgbG9nZ2VyLmluZm8oXG4gICAgICBgW01TVGVhbXNDb21tYW5kSGFuZGxlcl0gRmluYWwgcmVzcG9uc2UgZm9yIHVzZXIgJHt1c2VySWR9OiBcIiR7bWVzc2FnZVRvVXNlci5zdWJzdHJpbmcoMCwgMTUwKX0uLi5cImBcbiAgICApO1xuICAgIHJldHVybiBtZXNzYWdlVG9Vc2VyO1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFtNU1RlYW1zQ29tbWFuZEhhbmRsZXJdIENyaXRpY2FsIGVycm9yIGluIGhhbmRsZU1TVGVhbXNJbnF1aXJ5IGZvciB1c2VyICR7dXNlcklkfTpgLFxuICAgICAgZXJyb3JcbiAgICApO1xuICAgIG1lc3NhZ2VUb1VzZXIgPSBgSSBlbmNvdW50ZXJlZCBhbiBpc3N1ZSB3aGlsZSBwcm9jZXNzaW5nIHlvdXIgTWljcm9zb2Z0IFRlYW1zIHJlcXVlc3Q6ICR7ZXJyb3IubWVzc2FnZSB8fCAnVW5rbm93biBlcnJvcid9LiBQbGVhc2UgdHJ5IGFnYWluLmA7XG4gICAgcmV0dXJuIG1lc3NhZ2VUb1VzZXI7XG4gIH1cbn1cbiJdfQ==