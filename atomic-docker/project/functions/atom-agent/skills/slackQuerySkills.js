import { logger } from '../../_utils/logger';
import { understandSlackSearchQueryLLM, } from './llm_slack_query_understander';
import { buildSlackSearchQuery } from './nlu_slack_helper';
import { searchMySlackMessages as searchMySlackMessagesBackend, readSlackMessage as readSlackMessageBackend, extractInformationFromSlackMessage, } from './slackSkills'; // The actual backend callers
// --- Skill Implementations ---
export async function handleSearchSlackMessages(userId, rawUserQuery, limit = 20 // Default limit for Slack search results
) {
    logger.info(`[handleSearchSlackMessages] User: ${userId}, Query: "${rawUserQuery}", Limit: ${limit}`);
    try {
        const structuredQuery = await understandSlackSearchQueryLLM(rawUserQuery);
        logger.info(`[handleSearchSlackMessages] LLM structured query for Slack: ${JSON.stringify(structuredQuery)}`);
        // Resolve user/channel names to IDs if LLM provided names.
        // This is a complex step and might require calls to listUsers/listChannels if not already IDs.
        // For V1, we might rely on the Hasura Action/slack-service to handle some name resolution
        // or require users to use IDs/exact names that Slack search understands.
        // The `buildSlackSearchQuery` helper currently assumes names might be passed.
        // TODO: Enhance with ID resolution step here or ensure LLM provides IDs where possible.
        // Example: if (structuredQuery.fromUser && !isSlackUserId(structuredQuery.fromUser)) { structuredQuery.fromUser = await resolveSlackUserNameToId(structuredQuery.fromUser); }
        // Example: if (structuredQuery.inChannel && !isSlackChannelId(structuredQuery.inChannel)) { structuredQuery.inChannel = await resolveSlackChannelNameToId(structuredQuery.inChannel); }
        const slackApiQueryString = buildSlackSearchQuery(structuredQuery, rawUserQuery);
        logger.info(`[handleSearchSlackMessages] Constructed Slack API query string: "${slackApiQueryString}"`);
        if (!slackApiQueryString || slackApiQueryString.trim() === '') {
            return {
                ok: true,
                data: {
                    messages: [],
                    userMessage: "I couldn't determine specific search criteria for Slack from your request. Please try rephrasing.",
                },
            };
        }
        const messages = await searchMySlackMessagesBackend(userId, slackApiQueryString, limit);
        let userMessage = '';
        if (messages.length === 0) {
            userMessage =
                "I couldn't find any Slack messages matching your search criteria.";
        }
        else {
            userMessage = `I found ${messages.length} Slack message(s) matching your criteria:\n`;
            messages.forEach((msg, index) => {
                userMessage += `${index + 1}. ${msg.text ? msg.text.substring(0, 150) + '...' : '[No text content]'} (From: ${msg.userName || msg.userId || 'Unknown'}, In: ${msg.channelName || msg.channelId || 'Unknown'}, Date: ${new Date(msg.timestamp).toLocaleString()})\n   Permalink: ${msg.permalink || 'N/A'}\n`;
            });
        }
        return { ok: true, data: { messages, userMessage } };
    }
    catch (error) {
        logger.error(`[handleSearchSlackMessages] Error: ${error.message}`, error);
        return {
            ok: false,
            error: {
                code: 'SLACK_SEARCH_FAILED',
                message: error.message || 'Failed to search Slack messages.',
            },
            data: {
                messages: [],
                userMessage: `Sorry, I encountered an error while searching Slack: ${error.message}`,
            },
        };
    }
}
export async function handleExtractInfoFromSlackMessage(userId, messageReference, // Can be permalink, or "channelId/messageTs", or natural language reference
informationKeywords, messageTextContext) {
    logger.info(`[handleExtractInfoFromSlack] User: ${userId}, MessageRef: "${messageReference}", Keywords: [${informationKeywords.join(', ')}]`);
    if (!informationKeywords || informationKeywords.length === 0) {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Please specify what information you want to extract.',
            },
        };
    }
    let messageText = messageTextContext || null;
    let resolvedChannelId = null;
    let resolvedMessageTs = null;
    let messageDescription = `the message (Ref: ${messageReference.substring(0, 50)}...)`;
    try {
        if (!messageText) {
            // Attempt to parse permalink: https://[your-team].slack.com/archives/[CHANNEL_ID]/p[MESSAGE_TS_NO_DOT]
            const permalinkMatch = messageReference.match(/slack\.com\/archives\/([CDGUW][A-Z0-9]{8,10})\/p(\d{10})(\d{6})/);
            if (permalinkMatch) {
                resolvedChannelId = permalinkMatch[1];
                resolvedMessageTs = `${permalinkMatch[2]}.${permalinkMatch[3]}`;
                logger.info(`[handleExtractInfoFromSlack] Parsed permalink to Channel ID: ${resolvedChannelId}, Message TS: ${resolvedMessageTs}`);
            }
            else if (messageReference.includes('/')) {
                // Basic check for "channelId/messageTs"
                const parts = messageReference.split('/');
                if (parts.length === 2 && parts[0] && parts[1]) {
                    // rudimentary check
                    resolvedChannelId = parts[0];
                    resolvedMessageTs = parts[1];
                    logger.info(`[handleExtractInfoFromSlack] Interpreted reference as Channel ID: ${resolvedChannelId}, Message TS: ${resolvedMessageTs}`);
                }
            }
            // If not resolved yet, this indicates a natural language reference or an unparseable one.
            // TODO: For NL reference (e.g., "last message from Bob"), call handleSearchSlackMessages.
            // This is complex due to ambiguity. For V1, we might require permalink or ID format.
            if (!resolvedChannelId || !resolvedMessageTs) {
                logger.warn(`[handleExtractInfoFromSlack] Could not resolve message reference "${messageReference}" to channelId/messageTs. Advanced NL reference resolution is a TODO.`);
                throw new Error(`Could not identify the specific Slack message from your reference: "${messageReference}". Please try providing a permalink or more specific details.`);
            }
            const slackMessage = await readSlackMessageBackend(userId, resolvedChannelId, resolvedMessageTs);
            if (slackMessage && slackMessage.text) {
                messageText = slackMessage.text;
                messageDescription = `the message in ${slackMessage.channelName || resolvedChannelId} from ${slackMessage.userName || resolvedMessageTs}`;
            }
            else {
                throw new Error(`Could not find or read the Slack message (Channel: ${resolvedChannelId}, TS: ${resolvedMessageTs}).`);
            }
        }
        if (!messageText || messageText.trim() === '') {
            return {
                ok: false,
                error: {
                    code: 'SLACK_MESSAGE_EMPTY',
                    message: `The Slack message body for "${messageDescription}" is empty.`,
                },
                data: {
                    extractedInfo: {},
                    userMessage: `The Slack message body for "${messageDescription}" is empty, so I couldn't extract information.`,
                },
            };
        }
        const extractedInfo = await extractInformationFromSlackMessage(messageText, informationKeywords);
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
        logger.error(`[handleExtractInfoFromSlack] Error: ${error.message}`, error);
        return {
            ok: false,
            error: {
                code: 'SLACK_EXTRACT_FAILED',
                message: error.message || 'Failed to extract information from Slack message.',
            },
            data: {
                extractedInfo: {},
                userMessage: `Sorry, I encountered an error while extracting information from the Slack message: ${error.message}`,
            },
        };
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic2xhY2tRdWVyeVNraWxscy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInNsYWNrUXVlcnlTa2lsbHMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBS0EsT0FBTyxFQUFFLE1BQU0sRUFBRSxNQUFNLHFCQUFxQixDQUFDO0FBQzdDLE9BQU8sRUFDTCw2QkFBNkIsR0FFOUIsTUFBTSxnQ0FBZ0MsQ0FBQztBQUN4QyxPQUFPLEVBQUUscUJBQXFCLEVBQUUsTUFBTSxvQkFBb0IsQ0FBQztBQUMzRCxPQUFPLEVBQ0wscUJBQXFCLElBQUksNEJBQTRCLEVBQ3JELGdCQUFnQixJQUFJLHVCQUF1QixFQUMzQyxrQ0FBa0MsR0FFbkMsTUFBTSxlQUFlLENBQUMsQ0FBQyw2QkFBNkI7QUFvQnJELGdDQUFnQztBQUVoQyxNQUFNLENBQUMsS0FBSyxVQUFVLHlCQUF5QixDQUM3QyxNQUFjLEVBQ2QsWUFBb0IsRUFDcEIsUUFBZ0IsRUFBRSxDQUFDLHlDQUF5Qzs7SUFFNUQsTUFBTSxDQUFDLElBQUksQ0FDVCxxQ0FBcUMsTUFBTSxhQUFhLFlBQVksYUFBYSxLQUFLLEVBQUUsQ0FDekYsQ0FBQztJQUVGLElBQUksQ0FBQztRQUNILE1BQU0sZUFBZSxHQUNuQixNQUFNLDZCQUE2QixDQUFDLFlBQVksQ0FBQyxDQUFDO1FBQ3BELE1BQU0sQ0FBQyxJQUFJLENBQ1QsK0RBQStELElBQUksQ0FBQyxTQUFTLENBQUMsZUFBZSxDQUFDLEVBQUUsQ0FDakcsQ0FBQztRQUVGLDJEQUEyRDtRQUMzRCwrRkFBK0Y7UUFDL0YsMEZBQTBGO1FBQzFGLHlFQUF5RTtRQUN6RSw4RUFBOEU7UUFDOUUsd0ZBQXdGO1FBQ3hGLDhLQUE4SztRQUM5Syx3TEFBd0w7UUFFeEwsTUFBTSxtQkFBbUIsR0FBRyxxQkFBcUIsQ0FDL0MsZUFBZSxFQUNmLFlBQVksQ0FDYixDQUFDO1FBQ0YsTUFBTSxDQUFDLElBQUksQ0FDVCxvRUFBb0UsbUJBQW1CLEdBQUcsQ0FDM0YsQ0FBQztRQUVGLElBQUksQ0FBQyxtQkFBbUIsSUFBSSxtQkFBbUIsQ0FBQyxJQUFJLEVBQUUsS0FBSyxFQUFFLEVBQUUsQ0FBQztZQUM5RCxPQUFPO2dCQUNMLEVBQUUsRUFBRSxJQUFJO2dCQUNSLElBQUksRUFBRTtvQkFDSixRQUFRLEVBQUUsRUFBRTtvQkFDWixXQUFXLEVBQ1QsbUdBQW1HO2lCQUN0RzthQUNGLENBQUM7UUFDSixDQUFDO1FBRUQsTUFBTSxRQUFRLEdBQW1CLE1BQU0sNEJBQTRCLENBQ2pFLE1BQU0sRUFDTixtQkFBbUIsRUFDbkIsS0FBSyxDQUNOLENBQUM7UUFFRixJQUFJLFdBQVcsR0FBRyxFQUFFLENBQUM7UUFDckIsSUFBSSxRQUFRLENBQUMsTUFBTSxLQUFLLENBQUMsRUFBRSxDQUFDO1lBQzFCLFdBQVc7Z0JBQ1QsbUVBQW1FLENBQUM7UUFDeEUsQ0FBQzthQUFNLENBQUM7WUFDTixXQUFXLEdBQUcsV0FBVyxRQUFRLENBQUMsTUFBTSw2Q0FBNkMsQ0FBQztZQUN0RixRQUFRLENBQUMsT0FBTyxDQUFDLENBQUMsR0FBRyxFQUFFLEtBQUssRUFBRSxFQUFFO2dCQUM5QixXQUFXLElBQUksR0FBRyxLQUFLLEdBQUcsQ0FBQyxLQUFLLEdBQUcsQ0FBQyxJQUFJLENBQUMsQ0FBQyxDQUFDLEdBQUcsQ0FBQyxJQUFJLENBQUMsU0FBUyxDQUFDLENBQUMsRUFBRSxHQUFHLENBQUMsR0FBRyxLQUFLLENBQUMsQ0FBQyxDQUFDLG1CQUFtQixXQUFXLEdBQUcsQ0FBQyxRQUFRLElBQUksR0FBRyxDQUFDLE1BQU0sSUFBSSxTQUFTLFNBQVMsR0FBRyxDQUFDLFdBQVcsSUFBSSxHQUFHLENBQUMsU0FBUyxJQUFJLFNBQVMsV0FBVyxJQUFJLElBQUksQ0FBQyxHQUFHLENBQUMsU0FBUyxDQUFDLENBQUMsY0FBYyxFQUFFLG9CQUFvQixHQUFHLENBQUMsU0FBUyxJQUFJLEtBQUssSUFBSSxDQUFDO1lBQy9TLENBQUMsQ0FBQyxDQUFDO1FBQ0wsQ0FBQztRQUNELE9BQU8sRUFBRSxFQUFFLEVBQUUsSUFBSSxFQUFFLElBQUksRUFBRSxFQUFFLFFBQVEsRUFBRSxXQUFXLEVBQUUsRUFBRSxDQUFDO0lBQ3ZELENBQUM7SUFBQyxPQUFPLEtBQVUsRUFBRSxDQUFDO1FBQ3BCLE1BQU0sQ0FBQyxLQUFLLENBQUMsc0NBQXNDLEtBQUssQ0FBQyxPQUFPLEVBQUUsRUFBRSxLQUFLLENBQUMsQ0FBQztRQUMzRSxPQUFPO1lBQ0wsRUFBRSxFQUFFLEtBQUs7WUFDVCxLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLHFCQUFxQjtnQkFDM0IsT0FBTyxFQUFFLEtBQUssQ0FBQyxPQUFPLElBQUksa0NBQWtDO2FBQzdEO1lBQ0QsSUFBSSxFQUFFO2dCQUNKLFFBQVEsRUFBRSxFQUFFO2dCQUNaLFdBQVcsRUFBRSx3REFBd0QsS0FBSyxDQUFDLE9BQU8sRUFBRTthQUNyRjtTQUNGLENBQUM7SUFDSixDQUFDO0FBQ0gsQ0FBQztBQUVELE1BQU0sQ0FBQyxLQUFLLFVBQVUsaUNBQWlDLENBQ3JELE1BQWMsRUFDZCxnQkFBd0IsRUFBRSw0RUFBNEU7QUFDdEcsbUJBQTZCLEVBQzdCLGtCQUEyQjtJQU8zQixNQUFNLENBQUMsSUFBSSxDQUNULHNDQUFzQyxNQUFNLGtCQUFrQixnQkFBZ0IsaUJBQWlCLG1CQUFtQixDQUFDLElBQUksQ0FBQyxJQUFJLENBQUMsR0FBRyxDQUNqSSxDQUFDO0lBRUYsSUFBSSxDQUFDLG1CQUFtQixJQUFJLG1CQUFtQixDQUFDLE1BQU0sS0FBSyxDQUFDLEVBQUUsQ0FBQztRQUM3RCxPQUFPO1lBQ0wsRUFBRSxFQUFFLEtBQUs7WUFDVCxLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLGtCQUFrQjtnQkFDeEIsT0FBTyxFQUFFLHNEQUFzRDthQUNoRTtTQUNGLENBQUM7SUFDSixDQUFDO0lBRUQsSUFBSSxXQUFXLEdBQWtCLGtCQUFrQixJQUFJLElBQUksQ0FBQztJQUM1RCxJQUFJLGlCQUFpQixHQUFrQixJQUFJLENBQUM7SUFDNUMsSUFBSSxpQkFBaUIsR0FBa0IsSUFBSSxDQUFDO0lBQzVDLElBQUksa0JBQWtCLEdBQUcscUJBQXFCLGdCQUFnQixDQUFDLFNBQVMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLE1BQU0sQ0FBQztJQUV0RixJQUFJLENBQUM7UUFDSCxJQUFJLENBQUMsV0FBVyxFQUFFLENBQUM7WUFDakIsdUdBQXVHO1lBQ3ZHLE1BQU0sY0FBYyxHQUFHLGdCQUFnQixDQUFDLEtBQUssQ0FDM0MsaUVBQWlFLENBQ2xFLENBQUM7WUFDRixJQUFJLGNBQWMsRUFBRSxDQUFDO2dCQUNuQixpQkFBaUIsR0FBRyxjQUFjLENBQUMsQ0FBQyxDQUFDLENBQUM7Z0JBQ3RDLGlCQUFpQixHQUFHLEdBQUcsY0FBYyxDQUFDLENBQUMsQ0FBQyxJQUFJLGNBQWMsQ0FBQyxDQUFDLENBQUMsRUFBRSxDQUFDO2dCQUNoRSxNQUFNLENBQUMsSUFBSSxDQUNULGdFQUFnRSxpQkFBaUIsaUJBQWlCLGlCQUFpQixFQUFFLENBQ3RILENBQUM7WUFDSixDQUFDO2lCQUFNLElBQUksZ0JBQWdCLENBQUMsUUFBUSxDQUFDLEdBQUcsQ0FBQyxFQUFFLENBQUM7Z0JBQzFDLHdDQUF3QztnQkFDeEMsTUFBTSxLQUFLLEdBQUcsZ0JBQWdCLENBQUMsS0FBSyxDQUFDLEdBQUcsQ0FBQyxDQUFDO2dCQUMxQyxJQUFJLEtBQUssQ0FBQyxNQUFNLEtBQUssQ0FBQyxJQUFJLEtBQUssQ0FBQyxDQUFDLENBQUMsSUFBSSxLQUFLLENBQUMsQ0FBQyxDQUFDLEVBQUUsQ0FBQztvQkFDL0Msb0JBQW9CO29CQUNwQixpQkFBaUIsR0FBRyxLQUFLLENBQUMsQ0FBQyxDQUFDLENBQUM7b0JBQzdCLGlCQUFpQixHQUFHLEtBQUssQ0FBQyxDQUFDLENBQUMsQ0FBQztvQkFDN0IsTUFBTSxDQUFDLElBQUksQ0FDVCxxRUFBcUUsaUJBQWlCLGlCQUFpQixpQkFBaUIsRUFBRSxDQUMzSCxDQUFDO2dCQUNKLENBQUM7WUFDSCxDQUFDO1lBRUQsMEZBQTBGO1lBQzFGLDBGQUEwRjtZQUMxRixxRkFBcUY7WUFDckYsSUFBSSxDQUFDLGlCQUFpQixJQUFJLENBQUMsaUJBQWlCLEVBQUUsQ0FBQztnQkFDN0MsTUFBTSxDQUFDLElBQUksQ0FDVCxxRUFBcUUsZ0JBQWdCLHVFQUF1RSxDQUM3SixDQUFDO2dCQUNGLE1BQU0sSUFBSSxLQUFLLENBQ2IsdUVBQXVFLGdCQUFnQiwrREFBK0QsQ0FDdkosQ0FBQztZQUNKLENBQUM7WUFFRCxNQUFNLFlBQVksR0FBRyxNQUFNLHVCQUF1QixDQUNoRCxNQUFNLEVBQ04saUJBQWlCLEVBQ2pCLGlCQUFpQixDQUNsQixDQUFDO1lBQ0YsSUFBSSxZQUFZLElBQUksWUFBWSxDQUFDLElBQUksRUFBRSxDQUFDO2dCQUN0QyxXQUFXLEdBQUcsWUFBWSxDQUFDLElBQUksQ0FBQztnQkFDaEMsa0JBQWtCLEdBQUcsa0JBQWtCLFlBQVksQ0FBQyxXQUFXLElBQUksaUJBQWlCLFNBQVMsWUFBWSxDQUFDLFFBQVEsSUFBSSxpQkFBaUIsRUFBRSxDQUFDO1lBQzVJLENBQUM7aUJBQU0sQ0FBQztnQkFDTixNQUFNLElBQUksS0FBSyxDQUNiLHNEQUFzRCxpQkFBaUIsU0FBUyxpQkFBaUIsSUFBSSxDQUN0RyxDQUFDO1lBQ0osQ0FBQztRQUNILENBQUM7UUFFRCxJQUFJLENBQUMsV0FBVyxJQUFJLFdBQVcsQ0FBQyxJQUFJLEVBQUUsS0FBSyxFQUFFLEVBQUUsQ0FBQztZQUM5QyxPQUFPO2dCQUNMLEVBQUUsRUFBRSxLQUFLO2dCQUNULEtBQUssRUFBRTtvQkFDTCxJQUFJLEVBQUUscUJBQXFCO29CQUMzQixPQUFPLEVBQUUsK0JBQStCLGtCQUFrQixhQUFhO2lCQUN4RTtnQkFDRCxJQUFJLEVBQUU7b0JBQ0osYUFBYSxFQUFFLEVBQUU7b0JBQ2pCLFdBQVcsRUFBRSwrQkFBK0Isa0JBQWtCLGdEQUFnRDtpQkFDL0c7YUFDRixDQUFDO1FBQ0osQ0FBQztRQUVELE1BQU0sYUFBYSxHQUFHLE1BQU0sa0NBQWtDLENBQzVELFdBQVcsRUFDWCxtQkFBbUIsQ0FDcEIsQ0FBQztRQUVGLElBQUksVUFBVSxHQUFHLENBQUMsQ0FBQztRQUNuQixJQUFJLFlBQVksR0FBYSxDQUFDLHFCQUFxQixrQkFBa0IsR0FBRyxDQUFDLENBQUM7UUFDMUUsbUJBQW1CLENBQUMsT0FBTyxDQUFDLENBQUMsT0FBTyxFQUFFLEVBQUU7WUFDdEMsSUFDRSxhQUFhLENBQUMsT0FBTyxDQUFDLEtBQUssSUFBSTtnQkFDL0IsYUFBYSxDQUFDLE9BQU8sQ0FBQyxLQUFLLFNBQVMsRUFDcEMsQ0FBQztnQkFDRCxZQUFZLENBQUMsSUFBSSxDQUFDLFVBQVUsT0FBTyxNQUFNLGFBQWEsQ0FBQyxPQUFPLENBQUMsRUFBRSxDQUFDLENBQUM7Z0JBQ25FLFVBQVUsRUFBRSxDQUFDO1lBQ2YsQ0FBQztpQkFBTSxDQUFDO2dCQUNOLFlBQVksQ0FBQyxJQUFJLENBQUMsd0NBQXdDLE9BQU8sSUFBSSxDQUFDLENBQUM7WUFDekUsQ0FBQztRQUNILENBQUMsQ0FBQyxDQUFDO1FBRUgsTUFBTSxXQUFXLEdBQ2YsVUFBVSxHQUFHLENBQUM7WUFDWixDQUFDLENBQUMsWUFBWSxDQUFDLElBQUksQ0FBQyxJQUFJLENBQUM7WUFDekIsQ0FBQyxDQUFDLGNBQWMsa0JBQWtCLDhEQUE4RCxtQkFBbUIsQ0FBQyxJQUFJLENBQUMsSUFBSSxDQUFDLElBQUksQ0FBQztRQUV2SSxPQUFPLEVBQUUsRUFBRSxFQUFFLElBQUksRUFBRSxJQUFJLEVBQUUsRUFBRSxhQUFhLEVBQUUsV0FBVyxFQUFFLEVBQUUsQ0FBQztJQUM1RCxDQUFDO0lBQUMsT0FBTyxLQUFVLEVBQUUsQ0FBQztRQUNwQixNQUFNLENBQUMsS0FBSyxDQUFDLHVDQUF1QyxLQUFLLENBQUMsT0FBTyxFQUFFLEVBQUUsS0FBSyxDQUFDLENBQUM7UUFDNUUsT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxzQkFBc0I7Z0JBQzVCLE9BQU8sRUFDTCxLQUFLLENBQUMsT0FBTyxJQUFJLG1EQUFtRDthQUN2RTtZQUNELElBQUksRUFBRTtnQkFDSixhQUFhLEVBQUUsRUFBRTtnQkFDakIsV0FBVyxFQUFFLHNGQUFzRixLQUFLLENBQUMsT0FBTyxFQUFFO2FBQ25IO1NBQ0YsQ0FBQztJQUNKLENBQUM7QUFDSCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHtcbiAgU2tpbGxSZXNwb25zZSxcbiAgU2xhY2tNZXNzYWdlLFxuICAvLyBOTFUgZW50aXR5IHR5cGVzIGZvciBTbGFjayAtIHdpbGwgYmUgZGVmaW5lZCBvciBpbXBvcnRlZFxufSBmcm9tICcuLi90eXBlcyc7XG5pbXBvcnQgeyBsb2dnZXIgfSBmcm9tICcuLi8uLi9fdXRpbHMvbG9nZ2VyJztcbmltcG9ydCB7XG4gIHVuZGVyc3RhbmRTbGFja1NlYXJjaFF1ZXJ5TExNLFxuICBTdHJ1Y3R1cmVkU2xhY2tRdWVyeSxcbn0gZnJvbSAnLi9sbG1fc2xhY2tfcXVlcnlfdW5kZXJzdGFuZGVyJztcbmltcG9ydCB7IGJ1aWxkU2xhY2tTZWFyY2hRdWVyeSB9IGZyb20gJy4vbmx1X3NsYWNrX2hlbHBlcic7XG5pbXBvcnQge1xuICBzZWFyY2hNeVNsYWNrTWVzc2FnZXMgYXMgc2VhcmNoTXlTbGFja01lc3NhZ2VzQmFja2VuZCxcbiAgcmVhZFNsYWNrTWVzc2FnZSBhcyByZWFkU2xhY2tNZXNzYWdlQmFja2VuZCxcbiAgZXh0cmFjdEluZm9ybWF0aW9uRnJvbVNsYWNrTWVzc2FnZSxcbiAgZ2V0U2xhY2tNZXNzYWdlUGVybWFsaW5rIGFzIGdldFNsYWNrTWVzc2FnZVBlcm1hbGlua0JhY2tlbmQsXG59IGZyb20gJy4vc2xhY2tTa2lsbHMnOyAvLyBUaGUgYWN0dWFsIGJhY2tlbmQgY2FsbGVyc1xuXG4vLyBOTFUgRW50aXR5IEludGVyZmFjZXMgKENvbmNlcHR1YWwgLSBmb3IgZG9jdW1lbnRhdGlvbiBhbmQgdHlwZSBzYWZldHkgaWYgTkxVIHByb3ZpZGVzIHRoZW0gZGlyZWN0bHkpXG4vLyBUaGVzZSB3b3VsZCBhbGlnbiB3aXRoIHRoZSBpbnB1dHMgZXhwZWN0ZWQgYnkgdGhlIExMTSBwYXJzZXIgb3IgYSBkaXJlY3QgTkxVIHNlcnZpY2UuXG5leHBvcnQgaW50ZXJmYWNlIFNlYXJjaFNsYWNrTWVzc2FnZXNObHVFbnRpdGllcyB7XG4gIHJhd19xdWVyeV90ZXh0OiBzdHJpbmc7IC8vIFRoZSBmdWxsIG5hdHVyYWwgbGFuZ3VhZ2UgcXVlcnkgZnJvbSB0aGUgdXNlclxuICBsaW1pdF9udW1iZXI/OiBudW1iZXI7XG4gIC8vIE90aGVyIHBvdGVudGlhbCBwcmUtcGFyc2VkIGVudGl0aWVzIGxpa2UgY2hhbm5lbF9uYW1lLCBmcm9tX3VzZXIgYnkgTkxVIGlmIGF2YWlsYWJsZVxuICAvLyBIb3dldmVyLCB0aGUgcHJpbWFyeSBwYXRoIGlzIGZvciByYXdfcXVlcnlfdGV4dCB0byBiZSBwYXJzZWQgYnkgdW5kZXJzdGFuZFNsYWNrU2VhcmNoUXVlcnlMTE1cbn1cblxuZXhwb3J0IGludGVyZmFjZSBFeHRyYWN0SW5mb0Zyb21TbGFja01lc3NhZ2VObHVFbnRpdGllcyB7XG4gIG1lc3NhZ2VfcmVmZXJlbmNlX3RleHQ6IHN0cmluZzsgLy8gZS5nLiwgXCJsYXN0IG1lc3NhZ2UgZnJvbSBib2IgaW4gI2dlbmVyYWxcIiwgXCJ0aGUgbWVzc2FnZSBhYm91dCBidWRnZXRcIiwgcGVybWFsaW5rXG4gIC8vIE9SIHNwZWNpZmljIGlkZW50aWZpZXJzIGlmIE5MVSBjYW4gcHJvdmlkZSB0aGVtOlxuICAvLyBjaGFubmVsX2lkPzogc3RyaW5nO1xuICAvLyBtZXNzYWdlX3RzPzogc3RyaW5nO1xuICBpbmZvcm1hdGlvbl9rZXl3b3Jkczogc3RyaW5nW107IC8vIEFycmF5IG9mIHdoYXQgdG8gZXh0cmFjdFxuICBtZXNzYWdlX3RleHRfY29udGV4dD86IHN0cmluZzsgLy8gT3B0aW9uYWw6IGlmIHNraWxsIHJlY2VpdmVzIG1lc3NhZ2UgdGV4dCBkaXJlY3RseVxufVxuXG4vLyAtLS0gU2tpbGwgSW1wbGVtZW50YXRpb25zIC0tLVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlU2VhcmNoU2xhY2tNZXNzYWdlcyhcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHJhd1VzZXJRdWVyeTogc3RyaW5nLFxuICBsaW1pdDogbnVtYmVyID0gMjAgLy8gRGVmYXVsdCBsaW1pdCBmb3IgU2xhY2sgc2VhcmNoIHJlc3VsdHNcbik6IFByb21pc2U8U2tpbGxSZXNwb25zZTx7IG1lc3NhZ2VzOiBTbGFja01lc3NhZ2VbXTsgdXNlck1lc3NhZ2U6IHN0cmluZyB9Pj4ge1xuICBsb2dnZXIuaW5mbyhcbiAgICBgW2hhbmRsZVNlYXJjaFNsYWNrTWVzc2FnZXNdIFVzZXI6ICR7dXNlcklkfSwgUXVlcnk6IFwiJHtyYXdVc2VyUXVlcnl9XCIsIExpbWl0OiAke2xpbWl0fWBcbiAgKTtcblxuICB0cnkge1xuICAgIGNvbnN0IHN0cnVjdHVyZWRRdWVyeTogUGFydGlhbDxTdHJ1Y3R1cmVkU2xhY2tRdWVyeT4gPVxuICAgICAgYXdhaXQgdW5kZXJzdGFuZFNsYWNrU2VhcmNoUXVlcnlMTE0ocmF3VXNlclF1ZXJ5KTtcbiAgICBsb2dnZXIuaW5mbyhcbiAgICAgIGBbaGFuZGxlU2VhcmNoU2xhY2tNZXNzYWdlc10gTExNIHN0cnVjdHVyZWQgcXVlcnkgZm9yIFNsYWNrOiAke0pTT04uc3RyaW5naWZ5KHN0cnVjdHVyZWRRdWVyeSl9YFxuICAgICk7XG5cbiAgICAvLyBSZXNvbHZlIHVzZXIvY2hhbm5lbCBuYW1lcyB0byBJRHMgaWYgTExNIHByb3ZpZGVkIG5hbWVzLlxuICAgIC8vIFRoaXMgaXMgYSBjb21wbGV4IHN0ZXAgYW5kIG1pZ2h0IHJlcXVpcmUgY2FsbHMgdG8gbGlzdFVzZXJzL2xpc3RDaGFubmVscyBpZiBub3QgYWxyZWFkeSBJRHMuXG4gICAgLy8gRm9yIFYxLCB3ZSBtaWdodCByZWx5IG9uIHRoZSBIYXN1cmEgQWN0aW9uL3NsYWNrLXNlcnZpY2UgdG8gaGFuZGxlIHNvbWUgbmFtZSByZXNvbHV0aW9uXG4gICAgLy8gb3IgcmVxdWlyZSB1c2VycyB0byB1c2UgSURzL2V4YWN0IG5hbWVzIHRoYXQgU2xhY2sgc2VhcmNoIHVuZGVyc3RhbmRzLlxuICAgIC8vIFRoZSBgYnVpbGRTbGFja1NlYXJjaFF1ZXJ5YCBoZWxwZXIgY3VycmVudGx5IGFzc3VtZXMgbmFtZXMgbWlnaHQgYmUgcGFzc2VkLlxuICAgIC8vIFRPRE86IEVuaGFuY2Ugd2l0aCBJRCByZXNvbHV0aW9uIHN0ZXAgaGVyZSBvciBlbnN1cmUgTExNIHByb3ZpZGVzIElEcyB3aGVyZSBwb3NzaWJsZS5cbiAgICAvLyBFeGFtcGxlOiBpZiAoc3RydWN0dXJlZFF1ZXJ5LmZyb21Vc2VyICYmICFpc1NsYWNrVXNlcklkKHN0cnVjdHVyZWRRdWVyeS5mcm9tVXNlcikpIHsgc3RydWN0dXJlZFF1ZXJ5LmZyb21Vc2VyID0gYXdhaXQgcmVzb2x2ZVNsYWNrVXNlck5hbWVUb0lkKHN0cnVjdHVyZWRRdWVyeS5mcm9tVXNlcik7IH1cbiAgICAvLyBFeGFtcGxlOiBpZiAoc3RydWN0dXJlZFF1ZXJ5LmluQ2hhbm5lbCAmJiAhaXNTbGFja0NoYW5uZWxJZChzdHJ1Y3R1cmVkUXVlcnkuaW5DaGFubmVsKSkgeyBzdHJ1Y3R1cmVkUXVlcnkuaW5DaGFubmVsID0gYXdhaXQgcmVzb2x2ZVNsYWNrQ2hhbm5lbE5hbWVUb0lkKHN0cnVjdHVyZWRRdWVyeS5pbkNoYW5uZWwpOyB9XG5cbiAgICBjb25zdCBzbGFja0FwaVF1ZXJ5U3RyaW5nID0gYnVpbGRTbGFja1NlYXJjaFF1ZXJ5KFxuICAgICAgc3RydWN0dXJlZFF1ZXJ5LFxuICAgICAgcmF3VXNlclF1ZXJ5XG4gICAgKTtcbiAgICBsb2dnZXIuaW5mbyhcbiAgICAgIGBbaGFuZGxlU2VhcmNoU2xhY2tNZXNzYWdlc10gQ29uc3RydWN0ZWQgU2xhY2sgQVBJIHF1ZXJ5IHN0cmluZzogXCIke3NsYWNrQXBpUXVlcnlTdHJpbmd9XCJgXG4gICAgKTtcblxuICAgIGlmICghc2xhY2tBcGlRdWVyeVN0cmluZyB8fCBzbGFja0FwaVF1ZXJ5U3RyaW5nLnRyaW0oKSA9PT0gJycpIHtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiB0cnVlLFxuICAgICAgICBkYXRhOiB7XG4gICAgICAgICAgbWVzc2FnZXM6IFtdLFxuICAgICAgICAgIHVzZXJNZXNzYWdlOlxuICAgICAgICAgICAgXCJJIGNvdWxkbid0IGRldGVybWluZSBzcGVjaWZpYyBzZWFyY2ggY3JpdGVyaWEgZm9yIFNsYWNrIGZyb20geW91ciByZXF1ZXN0LiBQbGVhc2UgdHJ5IHJlcGhyYXNpbmcuXCIsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH1cblxuICAgIGNvbnN0IG1lc3NhZ2VzOiBTbGFja01lc3NhZ2VbXSA9IGF3YWl0IHNlYXJjaE15U2xhY2tNZXNzYWdlc0JhY2tlbmQoXG4gICAgICB1c2VySWQsXG4gICAgICBzbGFja0FwaVF1ZXJ5U3RyaW5nLFxuICAgICAgbGltaXRcbiAgICApO1xuXG4gICAgbGV0IHVzZXJNZXNzYWdlID0gJyc7XG4gICAgaWYgKG1lc3NhZ2VzLmxlbmd0aCA9PT0gMCkge1xuICAgICAgdXNlck1lc3NhZ2UgPVxuICAgICAgICBcIkkgY291bGRuJ3QgZmluZCBhbnkgU2xhY2sgbWVzc2FnZXMgbWF0Y2hpbmcgeW91ciBzZWFyY2ggY3JpdGVyaWEuXCI7XG4gICAgfSBlbHNlIHtcbiAgICAgIHVzZXJNZXNzYWdlID0gYEkgZm91bmQgJHttZXNzYWdlcy5sZW5ndGh9IFNsYWNrIG1lc3NhZ2UocykgbWF0Y2hpbmcgeW91ciBjcml0ZXJpYTpcXG5gO1xuICAgICAgbWVzc2FnZXMuZm9yRWFjaCgobXNnLCBpbmRleCkgPT4ge1xuICAgICAgICB1c2VyTWVzc2FnZSArPSBgJHtpbmRleCArIDF9LiAke21zZy50ZXh0ID8gbXNnLnRleHQuc3Vic3RyaW5nKDAsIDE1MCkgKyAnLi4uJyA6ICdbTm8gdGV4dCBjb250ZW50XSd9IChGcm9tOiAke21zZy51c2VyTmFtZSB8fCBtc2cudXNlcklkIHx8ICdVbmtub3duJ30sIEluOiAke21zZy5jaGFubmVsTmFtZSB8fCBtc2cuY2hhbm5lbElkIHx8ICdVbmtub3duJ30sIERhdGU6ICR7bmV3IERhdGUobXNnLnRpbWVzdGFtcCkudG9Mb2NhbGVTdHJpbmcoKX0pXFxuICAgUGVybWFsaW5rOiAke21zZy5wZXJtYWxpbmsgfHwgJ04vQSd9XFxuYDtcbiAgICAgIH0pO1xuICAgIH1cbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogeyBtZXNzYWdlcywgdXNlck1lc3NhZ2UgfSB9O1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgbG9nZ2VyLmVycm9yKGBbaGFuZGxlU2VhcmNoU2xhY2tNZXNzYWdlc10gRXJyb3I6ICR7ZXJyb3IubWVzc2FnZX1gLCBlcnJvcik7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdTTEFDS19TRUFSQ0hfRkFJTEVEJyxcbiAgICAgICAgbWVzc2FnZTogZXJyb3IubWVzc2FnZSB8fCAnRmFpbGVkIHRvIHNlYXJjaCBTbGFjayBtZXNzYWdlcy4nLFxuICAgICAgfSxcbiAgICAgIGRhdGE6IHtcbiAgICAgICAgbWVzc2FnZXM6IFtdLFxuICAgICAgICB1c2VyTWVzc2FnZTogYFNvcnJ5LCBJIGVuY291bnRlcmVkIGFuIGVycm9yIHdoaWxlIHNlYXJjaGluZyBTbGFjazogJHtlcnJvci5tZXNzYWdlfWAsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZUV4dHJhY3RJbmZvRnJvbVNsYWNrTWVzc2FnZShcbiAgdXNlcklkOiBzdHJpbmcsXG4gIG1lc3NhZ2VSZWZlcmVuY2U6IHN0cmluZywgLy8gQ2FuIGJlIHBlcm1hbGluaywgb3IgXCJjaGFubmVsSWQvbWVzc2FnZVRzXCIsIG9yIG5hdHVyYWwgbGFuZ3VhZ2UgcmVmZXJlbmNlXG4gIGluZm9ybWF0aW9uS2V5d29yZHM6IHN0cmluZ1tdLFxuICBtZXNzYWdlVGV4dENvbnRleHQ/OiBzdHJpbmdcbik6IFByb21pc2U8XG4gIFNraWxsUmVzcG9uc2U8e1xuICAgIGV4dHJhY3RlZEluZm86IFJlY29yZDxzdHJpbmcsIHN0cmluZyB8IG51bGw+O1xuICAgIHVzZXJNZXNzYWdlOiBzdHJpbmc7XG4gIH0+XG4+IHtcbiAgbG9nZ2VyLmluZm8oXG4gICAgYFtoYW5kbGVFeHRyYWN0SW5mb0Zyb21TbGFja10gVXNlcjogJHt1c2VySWR9LCBNZXNzYWdlUmVmOiBcIiR7bWVzc2FnZVJlZmVyZW5jZX1cIiwgS2V5d29yZHM6IFske2luZm9ybWF0aW9uS2V5d29yZHMuam9pbignLCAnKX1dYFxuICApO1xuXG4gIGlmICghaW5mb3JtYXRpb25LZXl3b3JkcyB8fCBpbmZvcm1hdGlvbktleXdvcmRzLmxlbmd0aCA9PT0gMCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdQbGVhc2Ugc3BlY2lmeSB3aGF0IGluZm9ybWF0aW9uIHlvdSB3YW50IHRvIGV4dHJhY3QuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIGxldCBtZXNzYWdlVGV4dDogc3RyaW5nIHwgbnVsbCA9IG1lc3NhZ2VUZXh0Q29udGV4dCB8fCBudWxsO1xuICBsZXQgcmVzb2x2ZWRDaGFubmVsSWQ6IHN0cmluZyB8IG51bGwgPSBudWxsO1xuICBsZXQgcmVzb2x2ZWRNZXNzYWdlVHM6IHN0cmluZyB8IG51bGwgPSBudWxsO1xuICBsZXQgbWVzc2FnZURlc2NyaXB0aW9uID0gYHRoZSBtZXNzYWdlIChSZWY6ICR7bWVzc2FnZVJlZmVyZW5jZS5zdWJzdHJpbmcoMCwgNTApfS4uLilgO1xuXG4gIHRyeSB7XG4gICAgaWYgKCFtZXNzYWdlVGV4dCkge1xuICAgICAgLy8gQXR0ZW1wdCB0byBwYXJzZSBwZXJtYWxpbms6IGh0dHBzOi8vW3lvdXItdGVhbV0uc2xhY2suY29tL2FyY2hpdmVzL1tDSEFOTkVMX0lEXS9wW01FU1NBR0VfVFNfTk9fRE9UXVxuICAgICAgY29uc3QgcGVybWFsaW5rTWF0Y2ggPSBtZXNzYWdlUmVmZXJlbmNlLm1hdGNoKFxuICAgICAgICAvc2xhY2tcXC5jb21cXC9hcmNoaXZlc1xcLyhbQ0RHVVddW0EtWjAtOV17OCwxMH0pXFwvcChcXGR7MTB9KShcXGR7Nn0pL1xuICAgICAgKTtcbiAgICAgIGlmIChwZXJtYWxpbmtNYXRjaCkge1xuICAgICAgICByZXNvbHZlZENoYW5uZWxJZCA9IHBlcm1hbGlua01hdGNoWzFdO1xuICAgICAgICByZXNvbHZlZE1lc3NhZ2VUcyA9IGAke3Blcm1hbGlua01hdGNoWzJdfS4ke3Blcm1hbGlua01hdGNoWzNdfWA7XG4gICAgICAgIGxvZ2dlci5pbmZvKFxuICAgICAgICAgIGBbaGFuZGxlRXh0cmFjdEluZm9Gcm9tU2xhY2tdIFBhcnNlZCBwZXJtYWxpbmsgdG8gQ2hhbm5lbCBJRDogJHtyZXNvbHZlZENoYW5uZWxJZH0sIE1lc3NhZ2UgVFM6ICR7cmVzb2x2ZWRNZXNzYWdlVHN9YFxuICAgICAgICApO1xuICAgICAgfSBlbHNlIGlmIChtZXNzYWdlUmVmZXJlbmNlLmluY2x1ZGVzKCcvJykpIHtcbiAgICAgICAgLy8gQmFzaWMgY2hlY2sgZm9yIFwiY2hhbm5lbElkL21lc3NhZ2VUc1wiXG4gICAgICAgIGNvbnN0IHBhcnRzID0gbWVzc2FnZVJlZmVyZW5jZS5zcGxpdCgnLycpO1xuICAgICAgICBpZiAocGFydHMubGVuZ3RoID09PSAyICYmIHBhcnRzWzBdICYmIHBhcnRzWzFdKSB7XG4gICAgICAgICAgLy8gcnVkaW1lbnRhcnkgY2hlY2tcbiAgICAgICAgICByZXNvbHZlZENoYW5uZWxJZCA9IHBhcnRzWzBdO1xuICAgICAgICAgIHJlc29sdmVkTWVzc2FnZVRzID0gcGFydHNbMV07XG4gICAgICAgICAgbG9nZ2VyLmluZm8oXG4gICAgICAgICAgICBgW2hhbmRsZUV4dHJhY3RJbmZvRnJvbVNsYWNrXSBJbnRlcnByZXRlZCByZWZlcmVuY2UgYXMgQ2hhbm5lbCBJRDogJHtyZXNvbHZlZENoYW5uZWxJZH0sIE1lc3NhZ2UgVFM6ICR7cmVzb2x2ZWRNZXNzYWdlVHN9YFxuICAgICAgICAgICk7XG4gICAgICAgIH1cbiAgICAgIH1cblxuICAgICAgLy8gSWYgbm90IHJlc29sdmVkIHlldCwgdGhpcyBpbmRpY2F0ZXMgYSBuYXR1cmFsIGxhbmd1YWdlIHJlZmVyZW5jZSBvciBhbiB1bnBhcnNlYWJsZSBvbmUuXG4gICAgICAvLyBUT0RPOiBGb3IgTkwgcmVmZXJlbmNlIChlLmcuLCBcImxhc3QgbWVzc2FnZSBmcm9tIEJvYlwiKSwgY2FsbCBoYW5kbGVTZWFyY2hTbGFja01lc3NhZ2VzLlxuICAgICAgLy8gVGhpcyBpcyBjb21wbGV4IGR1ZSB0byBhbWJpZ3VpdHkuIEZvciBWMSwgd2UgbWlnaHQgcmVxdWlyZSBwZXJtYWxpbmsgb3IgSUQgZm9ybWF0LlxuICAgICAgaWYgKCFyZXNvbHZlZENoYW5uZWxJZCB8fCAhcmVzb2x2ZWRNZXNzYWdlVHMpIHtcbiAgICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgICAgYFtoYW5kbGVFeHRyYWN0SW5mb0Zyb21TbGFja10gQ291bGQgbm90IHJlc29sdmUgbWVzc2FnZSByZWZlcmVuY2UgXCIke21lc3NhZ2VSZWZlcmVuY2V9XCIgdG8gY2hhbm5lbElkL21lc3NhZ2VUcy4gQWR2YW5jZWQgTkwgcmVmZXJlbmNlIHJlc29sdXRpb24gaXMgYSBUT0RPLmBcbiAgICAgICAgKTtcbiAgICAgICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgICAgIGBDb3VsZCBub3QgaWRlbnRpZnkgdGhlIHNwZWNpZmljIFNsYWNrIG1lc3NhZ2UgZnJvbSB5b3VyIHJlZmVyZW5jZTogXCIke21lc3NhZ2VSZWZlcmVuY2V9XCIuIFBsZWFzZSB0cnkgcHJvdmlkaW5nIGEgcGVybWFsaW5rIG9yIG1vcmUgc3BlY2lmaWMgZGV0YWlscy5gXG4gICAgICAgICk7XG4gICAgICB9XG5cbiAgICAgIGNvbnN0IHNsYWNrTWVzc2FnZSA9IGF3YWl0IHJlYWRTbGFja01lc3NhZ2VCYWNrZW5kKFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIHJlc29sdmVkQ2hhbm5lbElkLFxuICAgICAgICByZXNvbHZlZE1lc3NhZ2VUc1xuICAgICAgKTtcbiAgICAgIGlmIChzbGFja01lc3NhZ2UgJiYgc2xhY2tNZXNzYWdlLnRleHQpIHtcbiAgICAgICAgbWVzc2FnZVRleHQgPSBzbGFja01lc3NhZ2UudGV4dDtcbiAgICAgICAgbWVzc2FnZURlc2NyaXB0aW9uID0gYHRoZSBtZXNzYWdlIGluICR7c2xhY2tNZXNzYWdlLmNoYW5uZWxOYW1lIHx8IHJlc29sdmVkQ2hhbm5lbElkfSBmcm9tICR7c2xhY2tNZXNzYWdlLnVzZXJOYW1lIHx8IHJlc29sdmVkTWVzc2FnZVRzfWA7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAgICAgYENvdWxkIG5vdCBmaW5kIG9yIHJlYWQgdGhlIFNsYWNrIG1lc3NhZ2UgKENoYW5uZWw6ICR7cmVzb2x2ZWRDaGFubmVsSWR9LCBUUzogJHtyZXNvbHZlZE1lc3NhZ2VUc30pLmBcbiAgICAgICAgKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBpZiAoIW1lc3NhZ2VUZXh0IHx8IG1lc3NhZ2VUZXh0LnRyaW0oKSA9PT0gJycpIHtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICBjb2RlOiAnU0xBQ0tfTUVTU0FHRV9FTVBUWScsXG4gICAgICAgICAgbWVzc2FnZTogYFRoZSBTbGFjayBtZXNzYWdlIGJvZHkgZm9yIFwiJHttZXNzYWdlRGVzY3JpcHRpb259XCIgaXMgZW1wdHkuYCxcbiAgICAgICAgfSxcbiAgICAgICAgZGF0YToge1xuICAgICAgICAgIGV4dHJhY3RlZEluZm86IHt9LFxuICAgICAgICAgIHVzZXJNZXNzYWdlOiBgVGhlIFNsYWNrIG1lc3NhZ2UgYm9keSBmb3IgXCIke21lc3NhZ2VEZXNjcmlwdGlvbn1cIiBpcyBlbXB0eSwgc28gSSBjb3VsZG4ndCBleHRyYWN0IGluZm9ybWF0aW9uLmAsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH1cblxuICAgIGNvbnN0IGV4dHJhY3RlZEluZm8gPSBhd2FpdCBleHRyYWN0SW5mb3JtYXRpb25Gcm9tU2xhY2tNZXNzYWdlKFxuICAgICAgbWVzc2FnZVRleHQsXG4gICAgICBpbmZvcm1hdGlvbktleXdvcmRzXG4gICAgKTtcblxuICAgIGxldCBmb3VuZENvdW50ID0gMDtcbiAgICBsZXQgbWVzc2FnZVBhcnRzOiBzdHJpbmdbXSA9IFtgRnJvbSBteSByZXZpZXcgb2YgJHttZXNzYWdlRGVzY3JpcHRpb259OmBdO1xuICAgIGluZm9ybWF0aW9uS2V5d29yZHMuZm9yRWFjaCgoa2V5d29yZCkgPT4ge1xuICAgICAgaWYgKFxuICAgICAgICBleHRyYWN0ZWRJbmZvW2tleXdvcmRdICE9PSBudWxsICYmXG4gICAgICAgIGV4dHJhY3RlZEluZm9ba2V5d29yZF0gIT09IHVuZGVmaW5lZFxuICAgICAgKSB7XG4gICAgICAgIG1lc3NhZ2VQYXJ0cy5wdXNoKGAtIEZvciBcIiR7a2V5d29yZH1cIjogJHtleHRyYWN0ZWRJbmZvW2tleXdvcmRdfWApO1xuICAgICAgICBmb3VuZENvdW50Kys7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBtZXNzYWdlUGFydHMucHVzaChgLSBJIGNvdWxkbid0IGZpbmQgaW5mb3JtYXRpb24gYWJvdXQgXCIke2tleXdvcmR9XCIuYCk7XG4gICAgICB9XG4gICAgfSk7XG5cbiAgICBjb25zdCB1c2VyTWVzc2FnZSA9XG4gICAgICBmb3VuZENvdW50ID4gMFxuICAgICAgICA/IG1lc3NhZ2VQYXJ0cy5qb2luKCdcXG4nKVxuICAgICAgICA6IGBJIHJldmlld2VkICR7bWVzc2FnZURlc2NyaXB0aW9ufSBidXQgY291bGRuJ3QgZmluZCB0aGUgc3BlY2lmaWMgaW5mb3JtYXRpb24geW91IGFza2VkIGZvciAoJHtpbmZvcm1hdGlvbktleXdvcmRzLmpvaW4oJywgJyl9KS5gO1xuXG4gICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IHsgZXh0cmFjdGVkSW5mbywgdXNlck1lc3NhZ2UgfSB9O1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgbG9nZ2VyLmVycm9yKGBbaGFuZGxlRXh0cmFjdEluZm9Gcm9tU2xhY2tdIEVycm9yOiAke2Vycm9yLm1lc3NhZ2V9YCwgZXJyb3IpO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnU0xBQ0tfRVhUUkFDVF9GQUlMRUQnLFxuICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgIGVycm9yLm1lc3NhZ2UgfHwgJ0ZhaWxlZCB0byBleHRyYWN0IGluZm9ybWF0aW9uIGZyb20gU2xhY2sgbWVzc2FnZS4nLFxuICAgICAgfSxcbiAgICAgIGRhdGE6IHtcbiAgICAgICAgZXh0cmFjdGVkSW5mbzoge30sXG4gICAgICAgIHVzZXJNZXNzYWdlOiBgU29ycnksIEkgZW5jb3VudGVyZWQgYW4gZXJyb3Igd2hpbGUgZXh0cmFjdGluZyBpbmZvcm1hdGlvbiBmcm9tIHRoZSBTbGFjayBtZXNzYWdlOiAke2Vycm9yLm1lc3NhZ2V9YCxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufVxuIl19