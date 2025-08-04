import { logger } from '../../_utils/logger';
// Direct import from msteams-service.ts
import * as msTeamsService from '../../msteams-service/service';
/**
 * Searches Microsoft Teams messages for the user by calling the msteams-service directly.
 * @param atomUserId The Atom internal ID of the user making the request.
 * @param kqlQuery The KQL search query string.
 * @param limit Max number of messages to return.
 * @returns A promise resolving to an array of MSTeamsMessage objects.
 */
export async function searchMyMSTeamsMessages(atomUserId, kqlQuery, limit = 10) {
    logger.debug(`[MSTeamsSkills] searchMyMSTeamsMessages direct call for Atom user ${atomUserId}, KQL: "${kqlQuery}", limit: ${limit}`);
    try {
        // Call the service function directly.
        // The service function `searchTeamsMessages` returns GraphSkillResponse<AgentMSTeamsMessage[]>
        // We need to adapt this to Promise<MSTeamsMessage[]> or handle the GraphSkillResponse structure.
        // For now, let's assume we adapt to MSTeamsMessage[] if successful.
        const response = await msTeamsService.searchTeamsMessages(atomUserId, kqlQuery, limit);
        if (!response.ok || !response.data) {
            logger.error(`[MSTeamsSkills] msteams-service.searchTeamsMessages failed for user ${atomUserId}: ${response.error?.message}`);
            return [];
        }
        // Assuming AgentMSTeamsMessage is compatible with MSTeamsMessage for the fields we need.
        // If not, a mapping function would be required here.
        // MSTeamsMessage from types.ts is more detailed than AgentMSTeamsMessage in service.ts.
        // Let's ensure proper mapping.
        return response.data.map((item) => ({
            id: item.id,
            chatId: item.chatId,
            teamId: item.teamId,
            channelId: item.channelId,
            replyToId: item.replyToId,
            userId: item.userId,
            userName: item.userName,
            content: item.content,
            contentType: item.contentType, // service might return string
            createdDateTime: item.createdDateTime,
            lastModifiedDateTime: item.lastModifiedDateTime,
            webUrl: item.webUrl,
            attachments: item.attachments, // Assuming structure matches
            mentions: item.mentions, // Assuming structure matches
            raw: item.raw,
        }));
    }
    catch (error) {
        logger.error(`[MSTeamsSkills] Error in searchMyMSTeamsMessages direct call for Atom user ${atomUserId}, KQL "${kqlQuery}":`, error);
        return [];
    }
}
// Removed _getUserGraphObjectId as AAD ID fetching is now part of msteams-service.getDelegatedMSGraphTokenForUser
export async function getRecentChatsAndMentionsForBriefing(atomUserId, targetDate, count = 3) {
    logger.debug(`[MSTeamsSkills] getRecentChatsAndMentionsForBriefing for Atom user: ${atomUserId}, TargetDate: ${targetDate.toISOString().split('T')[0]}, Count: ${count}`);
    try {
        // 1. Get token and user AAD identifiers from msteams-service
        const tokenDetailsResponse = await msTeamsService.getDelegatedMSGraphTokenForUser(atomUserId);
        if (!tokenDetailsResponse.ok ||
            !tokenDetailsResponse.data?.accessToken ||
            !tokenDetailsResponse.data?.userAadObjectId) {
            logger.error(`[MSTeamsSkills] Could not get valid token or user AAD Object ID for user ${atomUserId}. Error: ${tokenDetailsResponse.error?.message}`);
            return {
                ok: false,
                error: tokenDetailsResponse.error || {
                    code: 'MSTEAMS_AUTH_FAILED',
                    message: 'Authentication or user ID retrieval failed for MS Teams.',
                },
            };
        }
        const { userAadObjectId, userPrincipalName } = tokenDetailsResponse.data;
        // Note: accessToken is managed within msteams-service calls, not directly used here anymore.
        if (!userAadObjectId && !userPrincipalName) {
            logger.warn(`[MSTeamsSkills] User AAD Object ID and UPN are both null for user ${atomUserId}. KQL query will be very broad.`);
            // Fallback to a very generic query or return error, for now, proceed with broad query.
        }
        const startOfDay = new Date(targetDate);
        startOfDay.setUTCHours(0, 0, 0, 0);
        const endOfDay = new Date(targetDate);
        endOfDay.setUTCHours(23, 59, 59, 999);
        const startOfDayISO = startOfDay.toISOString();
        const endOfDayISO = endOfDay.toISOString();
        // 2. Construct KQL query using AAD Object ID or UPN
        const dateFilterKQL = `createdDateTime>=${startOfDayISO} AND createdDateTime<=${endOfDayISO}`;
        let userSpecificKQL = '';
        if (userAadObjectId) {
            // Using AAD Object ID is generally more robust for mentions and identifying users.
            // This query targets messages mentioning the user OR messages sent by the user.
            // It helps find @mentions in channels/group chats and user's own messages in DMs/group chats.
            // It doesn't specifically isolate DMs *to* the user if they haven't replied and weren't mentioned.
            userSpecificKQL = `(mentions:"${userAadObjectId}" OR from:"${userAadObjectId}")`;
        }
        else if (userPrincipalName) {
            // Fallback to UPN if AAD Object ID is not available.
            // UPN might work for `from` but can be less reliable for `mentions` if display names are used more often.
            userSpecificKQL = `(mentions:"${userPrincipalName}" OR from:"${userPrincipalName}")`;
            logger.warn(`[MSTeamsSkills] Using UPN for KQL construction as AAD Object ID was not available for user ${atomUserId}. This might be less precise for mentions.`);
        }
        else {
            logger.warn(`[MSTeamsSkills] No user AAD ID or UPN available for user ${atomUserId}. KQL will only use date filters and be very broad. Results might not be relevant DMs/mentions.`);
            // If no user identifier, the query will just be the date filter, relying on the user's token context.
            // This will fetch all messages accessible to the user in that time range.
        }
        const kqlQuery = userSpecificKQL
            ? `${userSpecificKQL} AND ${dateFilterKQL}`
            : dateFilterKQL;
        logger.info(`[MSTeamsSkills] Constructed KQL query for briefing: "${kqlQuery}"`);
        // 3. Call the refactored searchMyMSTeamsMessages
        // The `searchMyMSTeamsMessages` will pass this KQL to the msteams-service,
        // which executes it against the Graph Search API.
        const searchResponse = await searchMyMSTeamsMessages(atomUserId, kqlQuery, count);
        // searchMyMSTeamsMessages now returns MSTeamsMessage[] directly, not a GraphSkillResponse.
        // The error handling and transformation to GraphSkillResponse should happen here.
        // However, looking at the current searchMyMSTeamsMessages, it already returns MSTeamsMessage[] and logs errors.
        // For consistency, getRecentChatsAndMentionsForBriefing should also return GraphSkillResponse.
        logger.info(`[MSTeamsSkills] Found ${searchResponse.length} MS Teams messages for briefing using KQL.`);
        return {
            ok: true,
            data: { results: searchResponse, query_executed: kqlQuery },
        };
    }
    catch (error) {
        logger.error(`[MSTeamsSkills] Error in getRecentChatsAndMentionsForBriefing for Atom user ${atomUserId}: ${error.message}`, error);
        const skillError = {
            code: 'MSTEAMS_BRIEFING_FETCH_FAILED',
            message: error.message ||
                'Failed to fetch recent MS Teams messages for briefing.',
            details: error,
        };
        return { ok: false, error: skillError };
    }
}
// Removed GQL_GET_MS_TEAMS_MESSAGE_WEB_URL constant
// Input type for the Hasura action, mirrors GetMSTeamsMessageDetailInput for identifying the message
// This interface is defined in types.ts, so no need to redefine here if imported.
// export interface GetMSTeamsMessageWebUrlInput extends GetMSTeamsMessageDetailInput {}
/**
 * Gets a permalink (webUrl) for a specific MS Teams message by calling the msteams-service.
 * @param atomUserId The Atom internal ID of the user.
 * @param identifier An object to identify the message (messageId and chatId or teamId/channelId).
 * @returns A promise resolving to the webUrl string or null.
 */
export async function getMSTeamsMessageWebUrl(atomUserId, identifier // Use the one from types.ts
) {
    logger.debug(`[MSTeamsSkills] getMSTeamsMessageWebUrl direct call for Atom user ${atomUserId}, identifier:`, identifier);
    if (!identifier.messageId ||
        (!identifier.chatId && (!identifier.teamId || !identifier.channelId))) {
        logger.error('[MSTeamsSkills] Invalid identifier for getMSTeamsMessageWebUrl.');
        return null;
    }
    try {
        // To get webUrl, we might need to fetch the message details first if not available otherwise
        // The msteams-service layer doesn't have a dedicated "get permalink" function.
        // We can call readMSTeamsMessage and extract webUrl.
        const message = await readMSTeamsMessage(atomUserId, identifier);
        if (message && message.webUrl) {
            return message.webUrl;
        }
        else if (message) {
            logger.warn(`[MSTeamsSkills] Message found but webUrl is missing for message ID ${identifier.messageId}.`);
            return null;
        }
        else {
            logger.warn(`[MSTeamsSkills] Could not read message to get webUrl for ID ${identifier.messageId}.`);
            return null;
        }
    }
    catch (error) {
        logger.error(`[MSTeamsSkills] Error in getMSTeamsMessageWebUrl for Atom user ${atomUserId}, identifier:`, identifier, error);
        return null;
    }
}
// --- LLM Information Extraction from MS Teams Message ---
import OpenAI from 'openai'; // Assuming OpenAI is standard for LLM tasks
import { ATOM_OPENAI_API_KEY, ATOM_NLU_MODEL_NAME } from '../_libs/constants';
let openAIClientForMSTeamsExtraction = null;
function getMSTeamsExtractionOpenAIClient() {
    if (openAIClientForMSTeamsExtraction) {
        return openAIClientForMSTeamsExtraction;
    }
    if (!ATOM_OPENAI_API_KEY) {
        logger.error('[MSTeamsSkills] OpenAI API Key not configured for LLM MS Teams Extractor.');
        throw new Error('OpenAI API Key not configured for LLM MS Teams Extractor.');
    }
    openAIClientForMSTeamsExtraction = new OpenAI({
        apiKey: ATOM_OPENAI_API_KEY,
    });
    logger.info('[MSTeamsSkills] OpenAI client for MS Teams extraction initialized.');
    return openAIClientForMSTeamsExtraction;
}
// System prompt for extracting info from MS Teams messages.
// Similar to Slack/Email, but can be tailored for Teams message nuances.
const MSTEAMS_EXTRACTION_SYSTEM_PROMPT_TEMPLATE = `
You are an expert system designed to extract specific pieces of information from a Microsoft Teams message.
The user will provide the message content (which might be HTML or plain text) and a list of information points (keywords).
For each keyword, find the corresponding information in the message.
Respond ONLY with a single, valid JSON object. Do not include any explanatory text before or after the JSON.
The JSON object should have keys corresponding to the user's original keywords.
The value for each key should be the extracted information as a string.
If information for a keyword is not found, the value for that key should be null.

Example:
User provides keywords: ["task details", "assigned to", "deadline"]
Message content: "<div><p>Hey @Alex, please look into the <b>spec review for feature X</b>. It needs to be completed by エンドオブデー Friday.</p></div>"
Your JSON response (assuming EOD Friday is understood as a deadline):
{
  "task details": "spec review for feature X",
  "assigned to": "@Alex",
  "deadline": "EOD Friday"
}

The keywords you need to extract information for are: {{KEYWORDS_JSON_ARRAY_STRING}}
Extract the information from the Teams message content provided by the user. If the content is HTML, focus on the textual information.
`;
/**
 * Uses an LLM to extract specific pieces of information from an MS Teams message body.
 * @param messageContent The content of the MS Teams message (can be HTML or plain text).
 * @param infoKeywords An array of strings representing the concepts/keywords to search for.
 * @returns A Promise resolving to a record where keys are infoKeywords and values are the extracted strings (or null).
 */
export async function extractInformationFromMSTeamsMessage(messageContent, infoKeywords) {
    if (!infoKeywords || infoKeywords.length === 0) {
        logger.debug('[MSTeamsSkills] extractInformationFromMSTeamsMessage: No infoKeywords provided.');
        return {};
    }
    if (!messageContent || messageContent.trim() === '') {
        logger.debug('[MSTeamsSkills] extractInformationFromMSTeamsMessage: Empty messageContent provided.');
        const emptyResult = {};
        infoKeywords.forEach((kw) => (emptyResult[kw] = null));
        return emptyResult;
    }
    logger.debug(`[MSTeamsSkills] LLM Extractor: Attempting to extract from MS Teams message for keywords: [${infoKeywords.join(', ')}]`);
    const client = getMSTeamsExtractionOpenAIClient();
    const keywordsJsonArrayString = JSON.stringify(infoKeywords);
    const systemPrompt = MSTEAMS_EXTRACTION_SYSTEM_PROMPT_TEMPLATE.replace('{{KEYWORDS_JSON_ARRAY_STRING}}', keywordsJsonArrayString);
    // Simple HTML to text conversion if content type is HTML, for cleaner input to LLM
    // More sophisticated stripping might be needed for complex HTML.
    let processedContent = messageContent;
    // Basic stripping of HTML tags for LLM processing if it's likely HTML
    if (messageContent.includes('<') && messageContent.includes('>')) {
        processedContent = messageContent
            .replace(/<[^>]+>/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
        logger.debug('[MSTeamsSkills] LLM Extractor: Stripped HTML from message content.');
    }
    const messages = [
        { role: 'system', content: systemPrompt },
        {
            role: 'user',
            content: `MS Teams Message Content:\n---\n${processedContent}\n---`,
        },
    ];
    try {
        const completion = await client.chat.completions.create({
            model: ATOM_NLU_MODEL_NAME,
            messages: messages,
            temperature: 0.1,
            response_format: { type: 'json_object' },
        });
        const llmResponse = completion.choices[0]?.message?.content;
        if (!llmResponse) {
            logger.error('[MSTeamsSkills] LLM Extractor: Received an empty response from AI for MS Teams message.');
            throw new Error('LLM Extractor (MS Teams): Empty response from AI.');
        }
        logger.debug('[MSTeamsSkills] LLM Extractor: Raw LLM JSON response for MS Teams:', llmResponse);
        const parsedResponse = JSON.parse(llmResponse);
        const result = {};
        for (const keyword of infoKeywords) {
            result[keyword] = parsedResponse.hasOwnProperty(keyword)
                ? parsedResponse[keyword]
                : null;
        }
        logger.debug('[MSTeamsSkills] LLM Extractor: Parsed and reconciled extraction from MS Teams:', result);
        return result;
    }
    catch (error) {
        logger.error('[MSTeamsSkills] LLM Extractor: Error processing information extraction from MS Teams message with OpenAI:', error.message);
        if (error instanceof SyntaxError) {
            logger.error('[MSTeamsSkills] LLM Extractor: Failed to parse JSON response from LLM for MS Teams message.');
            throw new Error('LLM Extractor (MS Teams): Failed to parse response from AI.');
        }
        const fallbackResult = {};
        infoKeywords.forEach((kw) => (fallbackResult[kw] = null));
        return fallbackResult;
    }
}
// Placeholder for callHasuraActionGraphQL utility if it's not in a shared location yet.
// Ensure this is implemented or imported correctly. For now, using a simplified version.
// import fetch from 'node-fetch';
// const HASURA_GRAPHQL_ENDPOINT = process.env.HASURA_GRAPHQL_ENDPOINT || 'http://hasura:8080/v1/graphql';
// async function callHasuraActionGraphQL(userId: string, operationName: string, query: string, variables: Record<string, any>): Promise<any> {
//   logger.debug(`[MSTeamsSkills] Calling Hasura Action GQL: ${operationName} for user ${userId}`);
//   try {
//       const response = await fetch(HASURA_GRAPHQL_ENDPOINT, {
//           method: 'POST',
//           headers: {
//               'Content-Type': 'application/json',
//               'X-Hasura-Role': 'user',
//               'X-Hasura-User-Id': userId,
//               ...(process.env.HASURA_ADMIN_SECRET && !userId ? { 'x-hasura-admin-secret': process.env.HASURA_ADMIN_SECRET } : {})
//           },
//           body: JSON.stringify({ query, variables }),
//       });
//       if (!response.ok) { /* ... error handling ... */ throw new Error(`Hasura GQL call to ${operationName} failed: ${response.statusText}`); }
//       const jsonResponse = await response.json();
//       if (jsonResponse.errors) { /* ... error handling ... */ throw new Error(`Hasura GQL call to ${operationName} returned errors: ${jsonResponse.errors.map((e: any) => e.message).join(', ')}`);}
//       return jsonResponse.data;
//   } catch (error) { /* ... error handling ... */ throw error; }
// }
const GQL_GET_MS_TEAMS_MESSAGE_DETAIL = `
  mutation GetMSTeamsMessageDetail($input: GetMSTeamsMessageDetailInput!) {
    getMSTeamsMessageDetail(input: $input) {
      success
      message
      msTeamsMessage { # This structure should match MSTeamsMessageObject
        id
        chatId
        teamId
        channelId
        replyToId
        userId
        userName
        content
        contentType
        createdDateTime
        lastModifiedDateTime
        webUrl
        attachments { id name contentType contentUrl size }
        mentions {
          id
          mentionText
          mentioned {
            user { id displayName userIdentityType }
          }
        }
        # raw
      }
    }
  }
`;
/**
 * Reads the detailed content of a specific MS Teams message.
 * @param userId The ID of the user.
 * @param identifier An object to identify the message, containing messageId and context (chatId or teamId/channelId).
 * @returns A promise resolving to an MSTeamsMessage object or null if not found/error.
 */
export async function readMSTeamsMessage(userId, identifier) {
    logger.debug(`[MSTeamsSkills] readMSTeamsMessage called for user ${userId}, identifier:`, identifier);
    if (!identifier.messageId ||
        (!identifier.chatId && (!identifier.teamId || !identifier.channelId))) {
        logger.error('[MSTeamsSkills] Invalid identifier for readMSTeamsMessage. Need messageId and (chatId or teamId+channelId).');
        return null;
    }
    try {
        const responseData = await callHasuraActionGraphQL(userId, 'GetMSTeamsMessageDetail', GQL_GET_MS_TEAMS_MESSAGE_DETAIL, {
            input: identifier,
        });
        const getResult = responseData.getMSTeamsMessageDetail;
        if (!getResult.success || !getResult.msTeamsMessage) {
            logger.warn(`[MSTeamsSkills] getMSTeamsMessageDetail action failed or message not found for user ${userId}: ${getResult.message}`, identifier);
            return null;
        }
        // Direct cast if GraphQL output matches agent's MSTeamsMessage type.
        // Ensure nested structures like attachments and mentions are also correctly typed/mapped if needed.
        const message = {
            ...getResult.msTeamsMessage,
            contentType: getResult.msTeamsMessage.contentType, // Ensure enum type if not guaranteed by GQL
            attachments: getResult.msTeamsMessage.attachments?.map((att) => ({
                id: att.id,
                name: att.name,
                contentType: att.contentType,
                contentUrl: att.contentUrl,
                size: att.size,
            })) || [],
            mentions: getResult.msTeamsMessage.mentions?.map((men) => ({
                id: men.id,
                mentionText: men.mentionText,
                mentioned: men.mentioned
                    ? {
                        user: men.mentioned.user
                            ? {
                                id: men.mentioned.user.id,
                                displayName: men.mentioned.user.displayName,
                                userIdentityType: men.mentioned.user.userIdentityType,
                            }
                            : undefined,
                    }
                    : undefined,
            })) || [],
        };
        return message;
    }
    catch (error) {
        logger.error(`[MSTeamsSkills] Error in readMSTeamsMessage for user ${userId}, identifier:`, identifier, error);
        return null;
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibXNUZWFtc1NraWxscy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIm1zVGVhbXNTa2lsbHMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUFFLE1BQU0sRUFBRSxNQUFNLHFCQUFxQixDQUFDO0FBUTdDLHdDQUF3QztBQUN4QyxPQUFPLEtBQUssY0FBYyxNQUFNLCtCQUErQixDQUFDO0FBRWhFOzs7Ozs7R0FNRztBQUNILE1BQU0sQ0FBQyxLQUFLLFVBQVUsdUJBQXVCLENBQzNDLFVBQWtCLEVBQ2xCLFFBQWdCLEVBQ2hCLFFBQWdCLEVBQUU7SUFFbEIsTUFBTSxDQUFDLEtBQUssQ0FDVixxRUFBcUUsVUFBVSxXQUFXLFFBQVEsYUFBYSxLQUFLLEVBQUUsQ0FDdkgsQ0FBQztJQUVGLElBQUksQ0FBQztRQUNILHNDQUFzQztRQUN0QywrRkFBK0Y7UUFDL0YsaUdBQWlHO1FBQ2pHLG9FQUFvRTtRQUNwRSxNQUFNLFFBQVEsR0FBRyxNQUFNLGNBQWMsQ0FBQyxtQkFBbUIsQ0FDdkQsVUFBVSxFQUNWLFFBQVEsRUFDUixLQUFLLENBQ04sQ0FBQztRQUVGLElBQUksQ0FBQyxRQUFRLENBQUMsRUFBRSxJQUFJLENBQUMsUUFBUSxDQUFDLElBQUksRUFBRSxDQUFDO1lBQ25DLE1BQU0sQ0FBQyxLQUFLLENBQ1YsdUVBQXVFLFVBQVUsS0FBSyxRQUFRLENBQUMsS0FBSyxFQUFFLE9BQU8sRUFBRSxDQUNoSCxDQUFDO1lBQ0YsT0FBTyxFQUFFLENBQUM7UUFDWixDQUFDO1FBQ0QseUZBQXlGO1FBQ3pGLHFEQUFxRDtRQUNyRCx3RkFBd0Y7UUFDeEYsK0JBQStCO1FBQy9CLE9BQU8sUUFBUSxDQUFDLElBQUksQ0FBQyxHQUFHLENBQ3RCLENBQUMsSUFBd0MsRUFBa0IsRUFBRSxDQUFDLENBQUM7WUFDN0QsRUFBRSxFQUFFLElBQUksQ0FBQyxFQUFFO1lBQ1gsTUFBTSxFQUFFLElBQUksQ0FBQyxNQUFNO1lBQ25CLE1BQU0sRUFBRSxJQUFJ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QU8sT0FBTyxDQUFDO0lBQ2pCLENBQUM7SUFBQyxPQUFPLEtBQUssRUFBRSxDQUFDO1FBQ2YsTUFBTSxDQUFDLEtBQUssQ0FDVix3REFBd0QsTUFBTSxlQUFlLEVBQzdFLFVBQVUsRUFDVixLQUFLLENBQ04sQ0FBQztRQUNGLE9BQU8sSUFBSSxDQUFDO0lBQ2QsQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBsb2dnZXIgfSBmcm9tICcuLi8uLi9fdXRpbHMvbG9nZ2VyJztcbi8vIFJlbW92ZWQgY2FsbEhhc3VyYUFjdGlvbkdyYXBoUUwgYW5kIEdRTCBjb25zdGFudHNcbmltcG9ydCB7XG4gIE1TVGVhbXNNZXNzYWdlLFxuICBHcmFwaFNraWxsUmVzcG9uc2UsXG4gIFNraWxsRXJyb3IsXG4gIEdldE1TVGVhbXNNZXNzYWdlRGV0YWlsSW5wdXQsXG59IGZyb20gJy4uL3R5cGVzJztcbi8vIERpcmVjdCBpbXBvcnQgZnJvbSBtc3RlYW1zLXNlcnZpY2UudHNcbmltcG9ydCAqIGFzIG1zVGVhbXNTZXJ2aWNlIGZyb20gJy4uLy4uL21zdGVhbXMtc2VydmljZS9zZXJ2aWNlJztcblxuLyoqXG4gKiBTZWFyY2hlcyBNaWNyb3NvZnQgVGVhbXMgbWVzc2FnZXMgZm9yIHRoZSB1c2VyIGJ5IGNhbGxpbmcgdGhlIG1zdGVhbXMtc2VydmljZSBkaXJlY3RseS5cbiAqIEBwYXJhbSBhdG9tVXNlcklkIFRoZSBBdG9tIGludGVybmFsIElEIG9mIHRoZSB1c2VyIG1ha2luZyB0aGUgcmVxdWVzdC5cbiAqIEBwYXJhbSBrcWxRdWVyeSBUaGUgS1FMIHNlYXJjaCBxdWVyeSBzdHJpbmcuXG4gKiBAcGFyYW0gbGltaXQgTWF4IG51bWJlciBvZiBtZXNzYWdlcyB0byByZXR1cm4uXG4gKiBAcmV0dXJucyBBIHByb21pc2UgcmVzb2x2aW5nIHRvIGFuIGFycmF5IG9mIE1TVGVhbXNNZXNzYWdlIG9iamVjdHMuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBzZWFyY2hNeU1TVGVhbXNNZXNzYWdlcyhcbiAgYXRvbVVzZXJJZDogc3RyaW5nLFxuICBrcWxRdWVyeTogc3RyaW5nLFxuICBsaW1pdDogbnVtYmVyID0gMTBcbik6IFByb21pc2U8TVNUZWFtc01lc3NhZ2VbXT4ge1xuICBsb2dnZXIuZGVidWcoXG4gICAgYFtNU1RlYW1zU2tpbGxzXSBzZWFyY2hNeU1TVGVhbXNNZXNzYWdlcyBkaXJlY3QgY2FsbCBmb3IgQXRvbSB1c2VyICR7YXRvbVVzZXJJZH0sIEtRTDogXCIke2txbFF1ZXJ5fVwiLCBsaW1pdDogJHtsaW1pdH1gXG4gICk7XG5cbiAgdHJ5IHtcbiAgICAvLyBDYWxsIHRoZSBzZXJ2aWNlIGZ1bmN0aW9uIGRpcmVjdGx5LlxuICAgIC8vIFRoZSBzZXJ2aWNlIGZ1bmN0aW9uIGBzZWFyY2hUZWFtc01lc3NhZ2VzYCByZXR1cm5zIEdyYXBoU2tpbGxSZXNwb25zZTxBZ2VudE1TVGVhbXNNZXNzYWdlW10+XG4gICAgLy8gV2UgbmVlZCB0byBhZGFwdCB0aGlzIHRvIFByb21pc2U8TVNUZWFtc01lc3NhZ2VbXT4gb3IgaGFuZGxlIHRoZSBHcmFwaFNraWxsUmVzcG9uc2Ugc3RydWN0dXJlLlxuICAgIC8vIEZvciBub3csIGxldCdzIGFzc3VtZSB3ZSBhZGFwdCB0byBNU1RlYW1zTWVzc2FnZVtdIGlmIHN1Y2Nlc3NmdWwuXG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBtc1RlYW1zU2VydmljZS5zZWFyY2hUZWFtc01lc3NhZ2VzKFxuICAgICAgYXRvbVVzZXJJZCxcbiAgICAgIGtxbFF1ZXJ5LFxuICAgICAgbGltaXRcbiAgICApO1xuXG4gICAgaWYgKCFyZXNwb25zZS5vayB8fCAhcmVzcG9uc2UuZGF0YSkge1xuICAgICAgbG9nZ2VyLmVycm9yKFxuICAgICAgICBgW01TVGVhbXNTa2lsbHNdIG1zdGVhbXMtc2VydmljZS5zZWFyY2hUZWFtc01lc3NhZ2VzIGZhaWxlZCBmb3IgdXNlciAke2F0b21Vc2VySWR9OiAke3Jlc3BvbnNlLmVycm9yPy5tZXNzYWdlfWBcbiAgICAgICk7XG4gICAgICByZXR1cm4gW107XG4gICAgfVxuICAgIC8vIEFzc3VtaW5nIEFnZW50TVNUZWFtc01lc3NhZ2UgaXMgY29tcGF0aWJsZSB3aXRoIE1TVGVhbXNNZXNzYWdlIGZvciB0aGUgZmllbGRzIHdlIG5lZWQuXG4gICAgLy8gSWYgbm90LCBhIG1hcHBpbmcgZnVuY3Rpb24gd291bGQgYmUgcmVxdWlyZWQgaGVyZS5cbiAgICAvLyBNU1RlYW1zTWVzc2FnZSBmcm9tIHR5cGVzLnRzIGlzIG1vcmUgZGV0YWlsZWQgdGhhbiBBZ2VudE1TVGVhbXNNZXNzYWdlIGluIHNlcnZpY2UudHMuXG4gICAgLy8gTGV0J3MgZW5zdXJlIHByb3BlciBtYXBwaW5nLlxuICAgIHJldHVybiByZXNwb25zZS5kYXRhLm1hcChcbiAgICAgIChpdGVtOiBtc1RlYW1zU2VydmljZS5BZ2VudE1TVGVhbXNNZXNzYWdlKTogTVNUZWFtc01lc3NhZ2UgPT4gKHtcbiAgICAgICAgaWQ6IGl0ZW0uaWQsXG4gICAgICAgIGNoYXRJZDogaXRlbS5jaGF0SWQsXG4gICAgICAgIHRlYW1JZDogaXRlbS50ZWFtSWQsXG4gICAgICAgIGNoYW5uZWxJZDogaXRlbS5jaGFubmVsSWQsXG4gICAgICAgIHJlcGx5VG9JZDogaXRlbS5yZXBseVRvSWQsXG4gICAgICAgIHVzZXJJZDogaXRlbS51c2VySWQsXG4gICAgICAgIHVzZXJOYW1lOiBpdGVtLnVzZXJOYW1lLFxuICAgICAgICBjb250ZW50OiBpdGVtLmNvbnRlbnQsXG4gICAgICAgIGNvbnRlbnRUeXBlOiBpdGVtLmNvbnRlbnRUeXBlIGFzICdodG1sJyB8ICd0ZXh0JywgLy8gc2VydmljZSBtaWdodCByZXR1cm4gc3RyaW5nXG4gICAgICAgIGNyZWF0ZWREYXRlVGltZTogaXRlbS5jcmVhdGVkRGF0ZVRpbWUsXG4gICAgICAgIGxhc3RNb2RpZmllZERhdGVUaW1lOiBpdGVtLmxhc3RNb2RpZmllZERhdGVUaW1lLFxuICAgICAgICB3ZWJVcmw6IGl0ZW0ud2ViVXJsLFxuICAgICAgICBhdHRhY2htZW50czogaXRlbS5hdHRhY2htZW50cywgLy8gQXNzdW1pbmcgc3RydWN0dXJlIG1hdGNoZXNcbiAgICAgICAgbWVudGlvbnM6IGl0ZW0ubWVudGlvbnMsIC8vIEFzc3VtaW5nIHN0cnVjdHVyZSBtYXRjaGVzXG4gICAgICAgIHJhdzogaXRlbS5yYXcsXG4gICAgICB9KVxuICAgICk7XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICBgW01TVGVhbXNTa2lsbHNdIEVycm9yIGluIHNlYXJjaE15TVNUZWFtc01lc3NhZ2VzIGRpcmVjdCBjYWxsIGZvciBBdG9tIHVzZXIgJHthdG9tVXNlcklkfSwgS1FMIFwiJHtrcWxRdWVyeX1cIjpgLFxuICAgICAgZXJyb3JcbiAgICApO1xuICAgIHJldHVybiBbXTtcbiAgfVxufVxuXG4vLyBSZW1vdmVkIF9nZXRVc2VyR3JhcGhPYmplY3RJZCBhcyBBQUQgSUQgZmV0Y2hpbmcgaXMgbm93IHBhcnQgb2YgbXN0ZWFtcy1zZXJ2aWNlLmdldERlbGVnYXRlZE1TR3JhcGhUb2tlbkZvclVzZXJcblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldFJlY2VudENoYXRzQW5kTWVudGlvbnNGb3JCcmllZmluZyhcbiAgYXRvbVVzZXJJZDogc3RyaW5nLFxuICB0YXJnZXREYXRlOiBEYXRlLFxuICBjb3VudDogbnVtYmVyID0gM1xuKTogUHJvbWlzZTxcbiAgR3JhcGhTa2lsbFJlc3BvbnNlPHsgcmVzdWx0czogTVNUZWFtc01lc3NhZ2VbXTsgcXVlcnlfZXhlY3V0ZWQ/OiBzdHJpbmcgfT5cbj4ge1xuICBsb2dnZXIuZGVidWcoXG4gICAgYFtNU1RlYW1zU2tpbGxzXSBnZXRSZWNlbnRDaGF0c0FuZE1lbnRpb25zRm9yQnJpZWZpbmcgZm9yIEF0b20gdXNlcjogJHthdG9tVXNlcklkfSwgVGFyZ2V0RGF0ZTogJHt0YXJnZXREYXRlLnRvSVNPU3RyaW5nKCkuc3BsaXQoJ1QnKVswXX0sIENvdW50OiAke2NvdW50fWBcbiAgKTtcblxuICB0cnkge1xuICAgIC8vIDEuIEdldCB0b2tlbiBhbmQgdXNlciBBQUQgaWRlbnRpZmllcnMgZnJvbSBtc3RlYW1zLXNlcnZpY2VcbiAgICBjb25zdCB0b2tlbkRldGFpbHNSZXNwb25zZSA9XG4gICAgICBhd2FpdCBtc1RlYW1zU2VydmljZS5nZXREZWxlZ2F0ZWRNU0dyYXBoVG9rZW5Gb3JVc2VyKGF0b21Vc2VySWQpO1xuICAgIGlmIChcbiAgICAgICF0b2tlbkRldGFpbHNSZXNwb25zZS5vayB8fFxuICAgICAgIXRva2VuRGV0YWlsc1Jlc3BvbnNlLmRhdGE/LmFjY2Vzc1Rva2VuIHx8XG4gICAgICAhdG9rZW5EZXRhaWxzUmVzcG9uc2UuZGF0YT8udXNlckFhZE9iamVjdElkXG4gICAgKSB7XG4gICAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAgIGBbTVNUZWFtc1NraWxsc10gQ291bGQgbm90IGdldCB2YWxpZCB0b2tlbiBvciB1c2VyIEFBRCBPYmplY3QgSUQgZm9yIHVzZXIgJHthdG9tVXNlcklkfS4gRXJyb3I6ICR7dG9rZW5EZXRhaWxzUmVzcG9uc2UuZXJyb3I/Lm1lc3NhZ2V9YFxuICAgICAgKTtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHRva2VuRGV0YWlsc1Jlc3BvbnNlLmVycm9yIHx8IHtcbiAgICAgICAgICBjb2RlOiAnTVNURUFNU19BVVRIX0ZBSUxFRCcsXG4gICAgICAgICAgbWVzc2FnZTogJ0F1dGhlbnRpY2F0aW9uIG9yIHVzZXIgSUQgcmV0cmlldmFsIGZhaWxlZCBmb3IgTVMgVGVhbXMuJyxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgfVxuICAgIGNvbnN0IHsgdXNlckFhZE9iamVjdElkLCB1c2VyUHJpbmNpcGFsTmFtZSB9ID0gdG9rZW5EZXRhaWxzUmVzcG9uc2UuZGF0YTtcbiAgICAvLyBOb3RlOiBhY2Nlc3NUb2tlbiBpcyBtYW5hZ2VkIHdpdGhpbiBtc3RlYW1zLXNlcnZpY2UgY2FsbHMsIG5vdCBkaXJlY3RseSB1c2VkIGhlcmUgYW55bW9yZS5cblxuICAgIGlmICghdXNlckFhZE9iamVjdElkICYmICF1c2VyUHJpbmNpcGFsTmFtZSkge1xuICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgIGBbTVNUZWFtc1NraWxsc10gVXNlciBBQUQgT2JqZWN0IElEIGFuZCBVUE4gYXJlIGJvdGggbnVsbCBmb3IgdXNlciAke2F0b21Vc2VySWR9LiBLUUwgcXVlcnkgd2lsbCBiZSB2ZXJ5IGJyb2FkLmBcbiAgICAgICk7XG4gICAgICAvLyBGYWxsYmFjayB0byBhIHZlcnkgZ2VuZXJpYyBxdWVyeSBvciByZXR1cm4gZXJyb3IsIGZvciBub3csIHByb2NlZWQgd2l0aCBicm9hZCBxdWVyeS5cbiAgICB9XG5cbiAgICBjb25zdCBzdGFydE9mRGF5ID0gbmV3IERhdGUodGFyZ2V0RGF0ZSk7XG4gICAgc3RhcnRPZkRheS5zZXRVVENIb3VycygwLCAwLCAwLCAwKTtcbiAgICBjb25zdCBlbmRPZkRheSA9IG5ldyBEYXRlKHRhcmdldERhdGUpO1xuICAgIGVuZE9mRGF5LnNldFVUQ0hvdXJzKDIzLCA1OSwgNTksIDk5OSk7XG4gICAgY29uc3Qgc3RhcnRPZkRheUlTTyA9IHN0YXJ0T2ZEYXkudG9JU09TdHJpbmcoKTtcbiAgICBjb25zdCBlbmRPZkRheUlTTyA9IGVuZE9mRGF5LnRvSVNPU3RyaW5nKCk7XG5cbiAgICAvLyAyLiBDb25zdHJ1Y3QgS1FMIHF1ZXJ5IHVzaW5nIEFBRCBPYmplY3QgSUQgb3IgVVBOXG4gICAgY29uc3QgZGF0ZUZpbHRlcktRTCA9IGBjcmVhdGVkRGF0ZVRpbWU+PSR7c3RhcnRPZkRheUlTT30gQU5EIGNyZWF0ZWREYXRlVGltZTw9JHtlbmRPZkRheUlTT31gO1xuICAgIGxldCB1c2VyU3BlY2lmaWNLUUwgPSAnJztcblxuICAgIGlmICh1c2VyQWFkT2JqZWN0SWQpIHtcbiAgICAgIC8vIFVzaW5nIEFBRCBPYmplY3QgSUQgaXMgZ2VuZXJhbGx5IG1vcmUgcm9idXN0IGZvciBtZW50aW9ucyBhbmQgaWRlbnRpZnlpbmcgdXNlcnMuXG4gICAgICAvLyBUaGlzIHF1ZXJ5IHRhcmdldHMgbWVzc2FnZXMgbWVudGlvbmluZyB0aGUgdXNlciBPUiBtZXNzYWdlcyBzZW50IGJ5IHRoZSB1c2VyLlxuICAgICAgLy8gSXQgaGVscHMgZmluZCBAbWVudGlvbnMgaW4gY2hhbm5lbHMvZ3JvdXAgY2hhdHMgYW5kIHVzZXIncyBvd24gbWVzc2FnZXMgaW4gRE1zL2dyb3VwIGNoYXRzLlxuICAgICAgLy8gSXQgZG9lc24ndCBzcGVjaWZpY2FsbHkgaXNvbGF0ZSBETXMgKnRvKiB0aGUgdXNlciBpZiB0aGV5IGhhdmVuJ3QgcmVwbGllZCBhbmQgd2VyZW4ndCBtZW50aW9uZWQuXG4gICAgICB1c2VyU3BlY2lmaWNLUUwgPSBgKG1lbnRpb25zOlwiJHt1c2VyQWFkT2JqZWN0SWR9XCIgT1IgZnJvbTpcIiR7dXNlckFhZE9iamVjdElkfVwiKWA7XG4gICAgfSBlbHNlIGlmICh1c2VyUHJpbmNpcGFsTmFtZSkge1xuICAgICAgLy8gRmFsbGJhY2sgdG8gVVBOIGlmIEFBRCBPYmplY3QgSUQgaXMgbm90IGF2YWlsYWJsZS5cbiAgICAgIC8vIFVQTiBtaWdodCB3b3JrIGZvciBgZnJvbWAgYnV0IGNhbiBiZSBsZXNzIHJlbGlhYmxlIGZvciBgbWVudGlvbnNgIGlmIGRpc3BsYXkgbmFtZXMgYXJlIHVzZWQgbW9yZSBvZnRlbi5cbiAgICAgIHVzZXJTcGVjaWZpY0tRTCA9IGAobWVudGlvbnM6XCIke3VzZXJQcmluY2lwYWxOYW1lfVwiIE9SIGZyb206XCIke3VzZXJQcmluY2lwYWxOYW1lfVwiKWA7XG4gICAgICBsb2dnZXIud2FybihcbiAgICAgICAgYFtNU1RlYW1zU2tpbGxzXSBVc2luZyBVUE4gZm9yIEtRTCBjb25zdHJ1Y3Rpb24gYXMgQUFEIE9iamVjdCBJRCB3YXMgbm90IGF2YWlsYWJsZSBmb3IgdXNlciAke2F0b21Vc2VySWR9LiBUaGlzIG1pZ2h0IGJlIGxlc3MgcHJlY2lzZSBmb3IgbWVudGlvbnMuYFxuICAgICAgKTtcbiAgICB9IGVsc2Uge1xuICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgIGBbTVNUZWFtc1NraWxsc10gTm8gdXNlciBBQUQgSUQgb3IgVVBOIGF2YWlsYWJsZSBmb3IgdXNlciAke2F0b21Vc2VySWR9LiBLUUwgd2lsbCBvbmx5IHVzZSBkYXRlIGZpbHRlcnMgYW5kIGJlIHZlcnkgYnJvYWQuIFJlc3VsdHMgbWlnaHQgbm90IGJlIHJlbGV2YW50IERNcy9tZW50aW9ucy5gXG4gICAgICApO1xuICAgICAgLy8gSWYgbm8gdXNlciBpZGVudGlmaWVyLCB0aGUgcXVlcnkgd2lsbCBqdXN0IGJlIHRoZSBkYXRlIGZpbHRlciwgcmVseWluZyBvbiB0aGUgdXNlcidzIHRva2VuIGNvbnRleHQuXG4gICAgICAvLyBUaGlzIHdpbGwgZmV0Y2ggYWxsIG1lc3NhZ2VzIGFjY2Vzc2libGUgdG8gdGhlIHVzZXIgaW4gdGhhdCB0aW1lIHJhbmdlLlxuICAgIH1cblxuICAgIGNvbnN0IGtxbFF1ZXJ5ID0gdXNlclNwZWNpZmljS1FMXG4gICAgICA/IGAke3VzZXJTcGVjaWZpY0tRTH0gQU5EICR7ZGF0ZUZpbHRlcktRTH1gXG4gICAgICA6IGRhdGVGaWx0ZXJLUUw7XG5cbiAgICBsb2dnZXIuaW5mbyhcbiAgICAgIGBbTVNUZWFtc1NraWxsc10gQ29uc3RydWN0ZWQgS1FMIHF1ZXJ5IGZvciBicmllZmluZzogXCIke2txbFF1ZXJ5fVwiYFxuICAgICk7XG5cbiAgICAvLyAzLiBDYWxsIHRoZSByZWZhY3RvcmVkIHNlYXJjaE15TVNUZWFtc01lc3NhZ2VzXG4gICAgLy8gVGhlIGBzZWFyY2hNeU1TVGVhbXNNZXNzYWdlc2Agd2lsbCBwYXNzIHRoaXMgS1FMIHRvIHRoZSBtc3RlYW1zLXNlcnZpY2UsXG4gICAgLy8gd2hpY2ggZXhlY3V0ZXMgaXQgYWdhaW5zdCB0aGUgR3JhcGggU2VhcmNoIEFQSS5cbiAgICBjb25zdCBzZWFyY2hSZXNwb25zZSA9IGF3YWl0IHNlYXJjaE15TVNUZWFtc01lc3NhZ2VzKFxuICAgICAgYXRvbVVzZXJJZCxcbiAgICAgIGtxbFF1ZXJ5LFxuICAgICAgY291bnRcbiAgICApO1xuXG4gICAgLy8gc2VhcmNoTXlNU1RlYW1zTWVzc2FnZXMgbm93IHJldHVybnMgTVNUZWFtc01lc3NhZ2VbXSBkaXJlY3RseSwgbm90IGEgR3JhcGhTa2lsbFJlc3BvbnNlLlxuICAgIC8vIFRoZSBlcnJvciBoYW5kbGluZyBhbmQgdHJhbnNmb3JtYXRpb24gdG8gR3JhcGhTa2lsbFJlc3BvbnNlIHNob3VsZCBoYXBwZW4gaGVyZS5cbiAgICAvLyBIb3dldmVyLCBsb29raW5nIGF0IHRoZSBjdXJyZW50IHNlYXJjaE15TVNUZWFtc01lc3NhZ2VzLCBpdCBhbHJlYWR5IHJldHVybnMgTVNUZWFtc01lc3NhZ2VbXSBhbmQgbG9ncyBlcnJvcnMuXG4gICAgLy8gRm9yIGNvbnNpc3RlbmN5LCBnZXRSZWNlbnRDaGF0c0FuZE1lbnRpb25zRm9yQnJpZWZpbmcgc2hvdWxkIGFsc28gcmV0dXJuIEdyYXBoU2tpbGxSZXNwb25zZS5cblxuICAgIGxvZ2dlci5pbmZvKFxuICAgICAgYFtNU1RlYW1zU2tpbGxzXSBGb3VuZCAke3NlYXJjaFJlc3BvbnNlLmxlbmd0aH0gTVMgVGVhbXMgbWVzc2FnZXMgZm9yIGJyaWVmaW5nIHVzaW5nIEtRTC5gXG4gICAgKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IHRydWUsXG4gICAgICBkYXRhOiB7IHJlc3VsdHM6IHNlYXJjaFJlc3BvbnNlLCBxdWVyeV9leGVjdXRlZDoga3FsUXVlcnkgfSxcbiAgICB9O1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFtNU1RlYW1zU2tpbGxzXSBFcnJvciBpbiBnZXRSZWNlbnRDaGF0c0FuZE1lbnRpb25zRm9yQnJpZWZpbmcgZm9yIEF0b20gdXNlciAke2F0b21Vc2VySWR9OiAke2Vycm9yLm1lc3NhZ2V9YCxcbiAgICAgIGVycm9yXG4gICAgKTtcbiAgICBjb25zdCBza2lsbEVycm9yOiBTa2lsbEVycm9yID0ge1xuICAgICAgY29kZTogJ01TVEVBTVNfQlJJRUZJTkdfRkVUQ0hfRkFJTEVEJyxcbiAgICAgIG1lc3NhZ2U6XG4gICAgICAgIGVycm9yLm1lc3NhZ2UgfHxcbiAgICAgICAgJ0ZhaWxlZCB0byBmZXRjaCByZWNlbnQgTVMgVGVhbXMgbWVzc2FnZXMgZm9yIGJyaWVmaW5nLicsXG4gICAgICBkZXRhaWxzOiBlcnJvcixcbiAgICB9O1xuICAgIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHNraWxsRXJyb3IgfTtcbiAgfVxufVxuXG4vLyBSZW1vdmVkIEdRTF9HRVRfTVNfVEVBTVNfTUVTU0FHRV9XRUJfVVJMIGNvbnN0YW50XG5cbi8vIElucHV0IHR5cGUgZm9yIHRoZSBIYXN1cmEgYWN0aW9uLCBtaXJyb3JzIEdldE1TVGVhbXNNZXNzYWdlRGV0YWlsSW5wdXQgZm9yIGlkZW50aWZ5aW5nIHRoZSBtZXNzYWdlXG4vLyBUaGlzIGludGVyZmFjZSBpcyBkZWZpbmVkIGluIHR5cGVzLnRzLCBzbyBubyBuZWVkIHRvIHJlZGVmaW5lIGhlcmUgaWYgaW1wb3J0ZWQuXG4vLyBleHBvcnQgaW50ZXJmYWNlIEdldE1TVGVhbXNNZXNzYWdlV2ViVXJsSW5wdXQgZXh0ZW5kcyBHZXRNU1RlYW1zTWVzc2FnZURldGFpbElucHV0IHt9XG5cbi8qKlxuICogR2V0cyBhIHBlcm1hbGluayAod2ViVXJsKSBmb3IgYSBzcGVjaWZpYyBNUyBUZWFtcyBtZXNzYWdlIGJ5IGNhbGxpbmcgdGhlIG1zdGVhbXMtc2VydmljZS5cbiAqIEBwYXJhbSBhdG9tVXNlcklkIFRoZSBBdG9tIGludGVybmFsIElEIG9mIHRoZSB1c2VyLlxuICogQHBhcmFtIGlkZW50aWZpZXIgQW4gb2JqZWN0IHRvIGlkZW50aWZ5IHRoZSBtZXNzYWdlIChtZXNzYWdlSWQgYW5kIGNoYXRJZCBvciB0ZWFtSWQvY2hhbm5lbElkKS5cbiAqIEByZXR1cm5zIEEgcHJvbWlzZSByZXNvbHZpbmcgdG8gdGhlIHdlYlVybCBzdHJpbmcgb3IgbnVsbC5cbiAqL1xuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldE1TVGVhbXNNZXNzYWdlV2ViVXJsKFxuICBhdG9tVXNlcklkOiBzdHJpbmcsXG4gIGlkZW50aWZpZXI6IEdldE1TVGVhbXNNZXNzYWdlRGV0YWlsSW5wdXQgLy8gVXNlIHRoZSBvbmUgZnJvbSB0eXBlcy50c1xuKTogUHJvbWlzZTxzdHJpbmcgfCBudWxsPiB7XG4gIGxvZ2dlci5kZWJ1ZyhcbiAgICBgW01TVGVhbXNTa2lsbHNdIGdldE1TVGVhbXNNZXNzYWdlV2ViVXJsIGRpcmVjdCBjYWxsIGZvciBBdG9tIHVzZXIgJHthdG9tVXNlcklkfSwgaWRlbnRpZmllcjpgLFxuICAgIGlkZW50aWZpZXJcbiAgKTtcblxuICBpZiAoXG4gICAgIWlkZW50aWZpZXIubWVzc2FnZUlkIHx8XG4gICAgKCFpZGVudGlmaWVyLmNoYXRJZCAmJiAoIWlkZW50aWZpZXIudGVhbUlkIHx8ICFpZGVudGlmaWVyLmNoYW5uZWxJZCkpXG4gICkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICdbTVNUZWFtc1NraWxsc10gSW52YWxpZCBpZGVudGlmaWVyIGZvciBnZXRNU1RlYW1zTWVzc2FnZVdlYlVybC4nXG4gICAgKTtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxuXG4gIHRyeSB7XG4gICAgLy8gVG8gZ2V0IHdlYlVybCwgd2UgbWlnaHQgbmVlZCB0byBmZXRjaCB0aGUgbWVzc2FnZSBkZXRhaWxzIGZpcnN0IGlmIG5vdCBhdmFpbGFibGUgb3RoZXJ3aXNlXG4gICAgLy8gVGhlIG1zdGVhbXMtc2VydmljZSBsYXllciBkb2Vzbid0IGhhdmUgYSBkZWRpY2F0ZWQgXCJnZXQgcGVybWFsaW5rXCIgZnVuY3Rpb24uXG4gICAgLy8gV2UgY2FuIGNhbGwgcmVhZE1TVGVhbXNNZXNzYWdlIGFuZCBleHRyYWN0IHdlYlVybC5cbiAgICBjb25zdCBtZXNzYWdlID0gYXdhaXQgcmVhZE1TVGVhbXNNZXNzYWdlKGF0b21Vc2VySWQsIGlkZW50aWZpZXIpO1xuICAgIGlmIChtZXNzYWdlICYmIG1lc3NhZ2Uud2ViVXJsKSB7XG4gICAgICByZXR1cm4gbWVzc2FnZS53ZWJVcmw7XG4gICAgfSBlbHNlIGlmIChtZXNzYWdlKSB7XG4gICAgICBsb2dnZXIud2FybihcbiAgICAgICAgYFtNU1RlYW1zU2tpbGxzXSBNZXNzYWdlIGZvdW5kIGJ1dCB3ZWJVcmwgaXMgbWlzc2luZyBmb3IgbWVzc2FnZSBJRCAke2lkZW50aWZpZXIubWVzc2FnZUlkfS5gXG4gICAgICApO1xuICAgICAgcmV0dXJuIG51bGw7XG4gICAgfSBlbHNlIHtcbiAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICBgW01TVGVhbXNTa2lsbHNdIENvdWxkIG5vdCByZWFkIG1lc3NhZ2UgdG8gZ2V0IHdlYlVybCBmb3IgSUQgJHtpZGVudGlmaWVyLm1lc3NhZ2VJZH0uYFxuICAgICAgKTtcbiAgICAgIHJldHVybiBudWxsO1xuICAgIH1cbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICBgW01TVGVhbXNTa2lsbHNdIEVycm9yIGluIGdldE1TVGVhbXNNZXNzYWdlV2ViVXJsIGZvciBBdG9tIHVzZXIgJHthdG9tVXNlcklkfSwgaWRlbnRpZmllcjpgLFxuICAgICAgaWRlbnRpZmllcixcbiAgICAgIGVycm9yXG4gICAgKTtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxufVxuXG4vLyAtLS0gTExNIEluZm9ybWF0aW9uIEV4dHJhY3Rpb24gZnJvbSBNUyBUZWFtcyBNZXNzYWdlIC0tLVxuaW1wb3J0IE9wZW5BSSBmcm9tICdvcGVuYWknOyAvLyBBc3N1bWluZyBPcGVuQUkgaXMgc3RhbmRhcmQgZm9yIExMTSB0YXNrc1xuaW1wb3J0IHsgQ2hhdENvbXBsZXRpb25NZXNzYWdlUGFyYW0gfSBmcm9tICdvcGVuYWkvcmVzb3VyY2VzL2NoYXQvY29tcGxldGlvbnMnO1xuaW1wb3J0IHsgQVRPTV9PUEVOQUlfQVBJX0tFWSwgQVRPTV9OTFVfTU9ERUxfTkFNRSB9IGZyb20gJy4uL19saWJzL2NvbnN0YW50cyc7XG5cbmxldCBvcGVuQUlDbGllbnRGb3JNU1RlYW1zRXh0cmFjdGlvbjogT3BlbkFJIHwgbnVsbCA9IG51bGw7XG5cbmZ1bmN0aW9uIGdldE1TVGVhbXNFeHRyYWN0aW9uT3BlbkFJQ2xpZW50KCk6IE9wZW5BSSB7XG4gIGlmIChvcGVuQUlDbGllbnRGb3JNU1RlYW1zRXh0cmFjdGlvbikge1xuICAgIHJldHVybiBvcGVuQUlDbGllbnRGb3JNU1RlYW1zRXh0cmFjdGlvbjtcbiAgfVxuICBpZiAoIUFUT01fT1BFTkFJX0FQSV9LRVkpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAnW01TVGVhbXNTa2lsbHNdIE9wZW5BSSBBUEkgS2V5IG5vdCBjb25maWd1cmVkIGZvciBMTE0gTVMgVGVhbXMgRXh0cmFjdG9yLidcbiAgICApO1xuICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICdPcGVuQUkgQVBJIEtleSBub3QgY29uZmlndXJlZCBmb3IgTExNIE1TIFRlYW1zIEV4dHJhY3Rvci4nXG4gICAgKTtcbiAgfVxuICBvcGVuQUlDbGllbnRGb3JNU1RlYW1zRXh0cmFjdGlvbiA9IG5ldyBPcGVuQUkoe1xuICAgIGFwaUtleTogQVRPTV9PUEVOQUlfQVBJX0tFWSxcbiAgfSk7XG4gIGxvZ2dlci5pbmZvKFxuICAgICdbTVNUZWFtc1NraWxsc10gT3BlbkFJIGNsaWVudCBmb3IgTVMgVGVhbXMgZXh0cmFjdGlvbiBpbml0aWFsaXplZC4nXG4gICk7XG4gIHJldHVybiBvcGVuQUlDbGllbnRGb3JNU1RlYW1zRXh0cmFjdGlvbjtcbn1cblxuLy8gU3lzdGVtIHByb21wdCBmb3IgZXh0cmFjdGluZyBpbmZvIGZyb20gTVMgVGVhbXMgbWVzc2FnZXMuXG4vLyBTaW1pbGFyIHRvIFNsYWNrL0VtYWlsLCBidXQgY2FuIGJlIHRhaWxvcmVkIGZvciBUZWFtcyBtZXNzYWdlIG51YW5jZXMuXG5jb25zdCBNU1RFQU1TX0VYVFJBQ1RJT05fU1lTVEVNX1BST01QVF9URU1QTEFURSA9IGBcbllvdSBhcmUgYW4gZXhwZXJ0IHN5c3RlbSBkZXNpZ25lZCB0byBleHRyYWN0IHNwZWNpZmljIHBpZWNlcyBvZiBpbmZvcm1hdGlvbiBmcm9tIGEgTWljcm9zb2Z0IFRlYW1zIG1lc3NhZ2UuXG5UaGUgdXNlciB3aWxsIHByb3ZpZGUgdGhlIG1lc3NhZ2UgY29udGVudCAod2hpY2ggbWlnaHQgYmUgSFRNTCBvciBwbGFpbiB0ZXh0KSBhbmQgYSBsaXN0IG9mIGluZm9ybWF0aW9uIHBvaW50cyAoa2V5d29yZHMpLlxuRm9yIGVhY2gga2V5d29yZCwgZmluZCB0aGUgY29ycmVzcG9uZGluZyBpbmZvcm1hdGlvbiBpbiB0aGUgbWVzc2FnZS5cblJlc3BvbmQgT05MWSB3aXRoIGEgc2luZ2xlLCB2YWxpZCBKU09OIG9iamVjdC4gRG8gbm90IGluY2x1ZGUgYW55IGV4cGxhbmF0b3J5IHRleHQgYmVmb3JlIG9yIGFmdGVyIHRoZSBKU09OLlxuVGhlIEpTT04gb2JqZWN0IHNob3VsZCBoYXZlIGtleXMgY29ycmVzcG9uZGluZyB0byB0aGUgdXNlcidzIG9yaWdpbmFsIGtleXdvcmRzLlxuVGhlIHZhbHVlIGZvciBlYWNoIGtleSBzaG91bGQgYmUgdGhlIGV4dHJhY3RlZCBpbmZvcm1hdGlvbiBhcyBhIHN0cmluZy5cbklmIGluZm9ybWF0aW9uIGZvciBhIGtleXdvcmQgaXMgbm90IGZvdW5kLCB0aGUgdmFsdWUgZm9yIHRoYXQga2V5IHNob3VsZCBiZSBudWxsLlxuXG5FeGFtcGxlOlxuVXNlciBwcm92aWRlcyBrZXl3b3JkczogW1widGFzayBkZXRhaWxzXCIsIFwiYXNzaWduZWQgdG9cIiwgXCJkZWFkbGluZVwiXVxuTWVzc2FnZSBjb250ZW50OiBcIjxkaXY+PHA+SGV5IEBBbGV4LCBwbGVhc2UgbG9vayBpbnRvIHRoZSA8Yj5zcGVjIHJldmlldyBmb3IgZmVhdHVyZSBYPC9iPi4gSXQgbmVlZHMgdG8gYmUgY29tcGxldGVkIGJ5IOOCqOODs+ODieOCquODluODh+ODvCBGcmlkYXkuPC9wPjwvZGl2PlwiXG5Zb3VyIEpTT04gcmVzcG9uc2UgKGFzc3VtaW5nIEVPRCBGcmlkYXkgaXMgdW5kZXJzdG9vZCBhcyBhIGRlYWRsaW5lKTpcbntcbiAgXCJ0YXNrIGRldGFpbHNcIjogXCJzcGVjIHJldmlldyBmb3IgZmVhdHVyZSBYXCIsXG4gIFwiYXNzaWduZWQgdG9cIjogXCJAQWxleFwiLFxuICBcImRlYWRsaW5lXCI6IFwiRU9EIEZyaWRheVwiXG59XG5cblRoZSBrZXl3b3JkcyB5b3UgbmVlZCB0byBleHRyYWN0IGluZm9ybWF0aW9uIGZvciBhcmU6IHt7S0VZV09SRFNfSlNPTl9BUlJBWV9TVFJJTkd9fVxuRXh0cmFjdCB0aGUgaW5mb3JtYXRpb24gZnJvbSB0aGUgVGVhbXMgbWVzc2FnZSBjb250ZW50IHByb3ZpZGVkIGJ5IHRoZSB1c2VyLiBJZiB0aGUgY29udGVudCBpcyBIVE1MLCBmb2N1cyBvbiB0aGUgdGV4dHVhbCBpbmZvcm1hdGlvbi5cbmA7XG5cbi8qKlxuICogVXNlcyBhbiBMTE0gdG8gZXh0cmFjdCBzcGVjaWZpYyBwaWVjZXMgb2YgaW5mb3JtYXRpb24gZnJvbSBhbiBNUyBUZWFtcyBtZXNzYWdlIGJvZHkuXG4gKiBAcGFyYW0gbWVzc2FnZUNvbnRlbnQgVGhlIGNvbnRlbnQgb2YgdGhlIE1TIFRlYW1zIG1lc3NhZ2UgKGNhbiBiZSBIVE1MIG9yIHBsYWluIHRleHQpLlxuICogQHBhcmFtIGluZm9LZXl3b3JkcyBBbiBhcnJheSBvZiBzdHJpbmdzIHJlcHJlc2VudGluZyB0aGUgY29uY2VwdHMva2V5d29yZHMgdG8gc2VhcmNoIGZvci5cbiAqIEByZXR1cm5zIEEgUHJvbWlzZSByZXNvbHZpbmcgdG8gYSByZWNvcmQgd2hlcmUga2V5cyBhcmUgaW5mb0tleXdvcmRzIGFuZCB2YWx1ZXMgYXJlIHRoZSBleHRyYWN0ZWQgc3RyaW5ncyAob3IgbnVsbCkuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBleHRyYWN0SW5mb3JtYXRpb25Gcm9tTVNUZWFtc01lc3NhZ2UoXG4gIG1lc3NhZ2VDb250ZW50OiBzdHJpbmcsXG4gIGluZm9LZXl3b3Jkczogc3RyaW5nW11cbik6IFByb21pc2U8UmVjb3JkPHN0cmluZywgc3RyaW5nIHwgbnVsbD4+IHtcbiAgaWYgKCFpbmZvS2V5d29yZHMgfHwgaW5mb0tleXdvcmRzLmxlbmd0aCA9PT0gMCkge1xuICAgIGxvZ2dlci5kZWJ1ZyhcbiAgICAgICdbTVNUZWFtc1NraWxsc10gZXh0cmFjdEluZm9ybWF0aW9uRnJvbU1TVGVhbXNNZXNzYWdlOiBObyBpbmZvS2V5d29yZHMgcHJvdmlkZWQuJ1xuICAgICk7XG4gICAgcmV0dXJuIHt9O1xuICB9XG4gIGlmICghbWVzc2FnZUNvbnRlbnQgfHwgbWVzc2FnZUNvbnRlbnQudHJpbSgpID09PSAnJykge1xuICAgIGxvZ2dlci5kZWJ1ZyhcbiAgICAgICdbTVNUZWFtc1NraWxsc10gZXh0cmFjdEluZm9ybWF0aW9uRnJvbU1TVGVhbXNNZXNzYWdlOiBFbXB0eSBtZXNzYWdlQ29udGVudCBwcm92aWRlZC4nXG4gICAgKTtcbiAgICBjb25zdCBlbXB0eVJlc3VsdDogUmVjb3JkPHN0cmluZywgc3RyaW5nIHwgbnVsbD4gPSB7fTtcbiAgICBpbmZvS2V5d29yZHMuZm9yRWFjaCgoa3cpID0+IChlbXB0eVJlc3VsdFtrd10gPSBudWxsKSk7XG4gICAgcmV0dXJuIGVtcHR5UmVzdWx0O1xuICB9XG5cbiAgbG9nZ2VyLmRlYnVnKFxuICAgIGBbTVNUZWFtc1NraWxsc10gTExNIEV4dHJhY3RvcjogQXR0ZW1wdGluZyB0byBleHRyYWN0IGZyb20gTVMgVGVhbXMgbWVzc2FnZSBmb3Iga2V5d29yZHM6IFske2luZm9LZXl3b3Jkcy5qb2luKCcsICcpfV1gXG4gICk7XG4gIGNvbnN0IGNsaWVudCA9IGdldE1TVGVhbXNFeHRyYWN0aW9uT3BlbkFJQ2xpZW50KCk7XG5cbiAgY29uc3Qga2V5d29yZHNKc29uQXJyYXlTdHJpbmcgPSBKU09OLnN0cmluZ2lmeShpbmZvS2V5d29yZHMpO1xuICBjb25zdCBzeXN0ZW1Qcm9tcHQgPSBNU1RFQU1TX0VYVFJBQ1RJT05fU1lTVEVNX1BST01QVF9URU1QTEFURS5yZXBsYWNlKFxuICAgICd7e0tFWVdPUkRTX0pTT05fQVJSQVlfU1RSSU5HfX0nLFxuICAgIGtleXdvcmRzSnNvbkFycmF5U3RyaW5nXG4gICk7XG5cbiAgLy8gU2ltcGxlIEhUTUwgdG8gdGV4dCBjb252ZXJzaW9uIGlmIGNvbnRlbnQgdHlwZSBpcyBIVE1MLCBmb3IgY2xlYW5lciBpbnB1dCB0byBMTE1cbiAgLy8gTW9yZSBzb3BoaXN0aWNhdGVkIHN0cmlwcGluZyBtaWdodCBiZSBuZWVkZWQgZm9yIGNvbXBsZXggSFRNTC5cbiAgbGV0IHByb2Nlc3NlZENvbnRlbnQgPSBtZXNzYWdlQ29udGVudDtcbiAgLy8gQmFzaWMgc3RyaXBwaW5nIG9mIEhUTUwgdGFncyBmb3IgTExNIHByb2Nlc3NpbmcgaWYgaXQncyBsaWtlbHkgSFRNTFxuICBpZiAobWVzc2FnZUNvbnRlbnQuaW5jbHVkZXMoJzwnKSAmJiBtZXNzYWdlQ29udGVudC5pbmNsdWRlcygnPicpKSB7XG4gICAgcHJvY2Vzc2VkQ29udGVudCA9IG1lc3NhZ2VDb250ZW50XG4gICAgICAucmVwbGFjZSgvPFtePl0rPi9nLCAnICcpXG4gICAgICAucmVwbGFjZSgvXFxzKy9nLCAnICcpXG4gICAgICAudHJpbSgpO1xuICAgIGxvZ2dlci5kZWJ1ZyhcbiAgICAgICdbTVNUZWFtc1NraWxsc10gTExNIEV4dHJhY3RvcjogU3RyaXBwZWQgSFRNTCBmcm9tIG1lc3NhZ2UgY29udGVudC4nXG4gICAgKTtcbiAgfVxuXG4gIGNvbnN0IG1lc3NhZ2VzOiBDaGF0Q29tcGxldGlvbk1lc3NhZ2VQYXJhbVtdID0gW1xuICAgIHsgcm9sZTogJ3N5c3RlbScsIGNvbnRlbnQ6IHN5c3RlbVByb21wdCB9LFxuICAgIHtcbiAgICAgIHJvbGU6ICd1c2VyJyxcbiAgICAgIGNvbnRlbnQ6IGBNUyBUZWFtcyBNZXNzYWdlIENvbnRlbnQ6XFxuLS0tXFxuJHtwcm9jZXNzZWRDb250ZW50fVxcbi0tLWAsXG4gICAgfSxcbiAgXTtcblxuICB0cnkge1xuICAgIGNvbnN0IGNvbXBsZXRpb24gPSBhd2FpdCBjbGllbnQuY2hhdC5jb21wbGV0aW9ucy5jcmVhdGUoe1xuICAgICAgbW9kZWw6IEFUT01fTkxVX01PREVMX05BTUUsXG4gICAgICBtZXNzYWdlczogbWVzc2FnZXMsXG4gICAgICB0ZW1wZXJhdHVyZTogMC4xLFxuICAgICAgcmVzcG9uc2VfZm9ybWF0OiB7IHR5cGU6ICdqc29uX29iamVjdCcgfSxcbiAgICB9KTtcblxuICAgIGNvbnN0IGxsbVJlc3BvbnNlID0gY29tcGxldGlvbi5jaG9pY2VzWzBdPy5tZXNzYWdlPy5jb250ZW50O1xuICAgIGlmICghbGxtUmVzcG9uc2UpIHtcbiAgICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICAgJ1tNU1RlYW1zU2tpbGxzXSBMTE0gRXh0cmFjdG9yOiBSZWNlaXZlZCBhbiBlbXB0eSByZXNwb25zZSBmcm9tIEFJIGZvciBNUyBUZWFtcyBtZXNzYWdlLidcbiAgICAgICk7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ0xMTSBFeHRyYWN0b3IgKE1TIFRlYW1zKTogRW1wdHkgcmVzcG9uc2UgZnJvbSBBSS4nKTtcbiAgICB9XG5cbiAgICBsb2dnZXIuZGVidWcoXG4gICAgICAnW01TVGVhbXNTa2lsbHNdIExMTSBFeHRyYWN0b3I6IFJhdyBMTE0gSlNPTiByZXNwb25zZSBmb3IgTVMgVGVhbXM6JyxcbiAgICAgIGxsbVJlc3BvbnNlXG4gICAgKTtcbiAgICBjb25zdCBwYXJzZWRSZXNwb25zZSA9IEpTT04ucGFyc2UobGxtUmVzcG9uc2UpO1xuXG4gICAgY29uc3QgcmVzdWx0OiBSZWNvcmQ8c3RyaW5nLCBzdHJpbmcgfCBudWxsPiA9IHt9O1xuICAgIGZvciAoY29uc3Qga2V5d29yZCBvZiBpbmZvS2V5d29yZHMpIHtcbiAgICAgIHJlc3VsdFtrZXl3b3JkXSA9IHBhcnNlZFJlc3BvbnNlLmhhc093blByb3BlcnR5KGtleXdvcmQpXG4gICAgICAgID8gcGFyc2VkUmVzcG9uc2Vba2V5d29yZF1cbiAgICAgICAgOiBudWxsO1xuICAgIH1cblxuICAgIGxvZ2dlci5kZWJ1ZyhcbiAgICAgICdbTVNUZWFtc1NraWxsc10gTExNIEV4dHJhY3RvcjogUGFyc2VkIGFuZCByZWNvbmNpbGVkIGV4dHJhY3Rpb24gZnJvbSBNUyBUZWFtczonLFxuICAgICAgcmVzdWx0XG4gICAgKTtcbiAgICByZXR1cm4gcmVzdWx0O1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgJ1tNU1RlYW1zU2tpbGxzXSBMTE0gRXh0cmFjdG9yOiBFcnJvciBwcm9jZXNzaW5nIGluZm9ybWF0aW9uIGV4dHJhY3Rpb24gZnJvbSBNUyBUZWFtcyBtZXNzYWdlIHdpdGggT3BlbkFJOicsXG4gICAgICBlcnJvci5tZXNzYWdlXG4gICAgKTtcbiAgICBpZiAoZXJyb3IgaW5zdGFuY2VvZiBTeW50YXhFcnJvcikge1xuICAgICAgbG9nZ2VyLmVycm9yKFxuICAgICAgICAnW01TVGVhbXNTa2lsbHNdIExMTSBFeHRyYWN0b3I6IEZhaWxlZCB0byBwYXJzZSBKU09OIHJlc3BvbnNlIGZyb20gTExNIGZvciBNUyBUZWFtcyBtZXNzYWdlLidcbiAgICAgICk7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAgICdMTE0gRXh0cmFjdG9yIChNUyBUZWFtcyk6IEZhaWxlZCB0byBwYXJzZSByZXNwb25zZSBmcm9tIEFJLidcbiAgICAgICk7XG4gICAgfVxuICAgIGNvbnN0IGZhbGxiYWNrUmVzdWx0OiBSZWNvcmQ8c3RyaW5nLCBzdHJpbmcgfCBudWxsPiA9IHt9O1xuICAgIGluZm9LZXl3b3Jkcy5mb3JFYWNoKChrdykgPT4gKGZhbGxiYWNrUmVzdWx0W2t3XSA9IG51bGwpKTtcbiAgICByZXR1cm4gZmFsbGJhY2tSZXN1bHQ7XG4gIH1cbn1cblxuLy8gUGxhY2Vob2xkZXIgZm9yIGNhbGxIYXN1cmFBY3Rpb25HcmFwaFFMIHV0aWxpdHkgaWYgaXQncyBub3QgaW4gYSBzaGFyZWQgbG9jYXRpb24geWV0LlxuLy8gRW5zdXJlIHRoaXMgaXMgaW1wbGVtZW50ZWQgb3IgaW1wb3J0ZWQgY29ycmVjdGx5LiBGb3Igbm93LCB1c2luZyBhIHNpbXBsaWZpZWQgdmVyc2lvbi5cbi8vIGltcG9ydCBmZXRjaCBmcm9tICdub2RlLWZldGNoJztcbi8vIGNvbnN0IEhBU1VSQV9HUkFQSFFMX0VORFBPSU5UID0gcHJvY2Vzcy5lbnYuSEFTVVJBX0dSQVBIUUxfRU5EUE9JTlQgfHwgJ2h0dHA6Ly9oYXN1cmE6ODA4MC92MS9ncmFwaHFsJztcblxuLy8gYXN5bmMgZnVuY3Rpb24gY2FsbEhhc3VyYUFjdGlvbkdyYXBoUUwodXNlcklkOiBzdHJpbmcsIG9wZXJhdGlvbk5hbWU6IHN0cmluZywgcXVlcnk6IHN0cmluZywgdmFyaWFibGVzOiBSZWNvcmQ8c3RyaW5nLCBhbnk+KTogUHJvbWlzZTxhbnk+IHtcbi8vICAgbG9nZ2VyLmRlYnVnKGBbTVNUZWFtc1NraWxsc10gQ2FsbGluZyBIYXN1cmEgQWN0aW9uIEdRTDogJHtvcGVyYXRpb25OYW1lfSBmb3IgdXNlciAke3VzZXJJZH1gKTtcbi8vICAgdHJ5IHtcbi8vICAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZmV0Y2goSEFTVVJBX0dSQVBIUUxfRU5EUE9JTlQsIHtcbi8vICAgICAgICAgICBtZXRob2Q6ICdQT1NUJyxcbi8vICAgICAgICAgICBoZWFkZXJzOiB7XG4vLyAgICAgICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4vLyAgICAgICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ3VzZXInLFxuLy8gICAgICAgICAgICAgICAnWC1IYXN1cmEtVXNlci1JZCc6IHVzZXJJZCxcbi8vICAgICAgICAgICAgICAgLi4uKHByb2Nlc3MuZW52LkhBU1VSQV9BRE1JTl9TRUNSRVQgJiYgIXVzZXJJZCA/IHsgJ3gtaGFzdXJhLWFkbWluLXNlY3JldCc6IHByb2Nlc3MuZW52LkhBU1VSQV9BRE1JTl9TRUNSRVQgfSA6IHt9KVxuLy8gICAgICAgICAgIH0sXG4vLyAgICAgICAgICAgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBxdWVyeSwgdmFyaWFibGVzIH0pLFxuLy8gICAgICAgfSk7XG4vLyAgICAgICBpZiAoIXJlc3BvbnNlLm9rKSB7IC8qIC4uLiBlcnJvciBoYW5kbGluZyAuLi4gKi8gdGhyb3cgbmV3IEVycm9yKGBIYXN1cmEgR1FMIGNhbGwgdG8gJHtvcGVyYXRpb25OYW1lfSBmYWlsZWQ6ICR7cmVzcG9uc2Uuc3RhdHVzVGV4dH1gKTsgfVxuLy8gICAgICAgY29uc3QganNvblJlc3BvbnNlID0gYXdhaXQgcmVzcG9uc2UuanNvbigpO1xuLy8gICAgICAgaWYgKGpzb25SZXNwb25zZS5lcnJvcnMpIHsgLyogLi4uIGVycm9yIGhhbmRsaW5nIC4uLiAqLyB0aHJvdyBuZXcgRXJyb3IoYEhhc3VyYSBHUUwgY2FsbCB0byAke29wZXJhdGlvbk5hbWV9IHJldHVybmVkIGVycm9yczogJHtqc29uUmVzcG9uc2UuZXJyb3JzLm1hcCgoZTogYW55KSA9PiBlLm1lc3NhZ2UpLmpvaW4oJywgJyl9YCk7fVxuLy8gICAgICAgcmV0dXJuIGpzb25SZXNwb25zZS5kYXRhO1xuLy8gICB9IGNhdGNoIChlcnJvcikgeyAvKiAuLi4gZXJyb3IgaGFuZGxpbmcgLi4uICovIHRocm93IGVycm9yOyB9XG4vLyB9XG5cbmNvbnN0IEdRTF9HRVRfTVNfVEVBTVNfTUVTU0FHRV9ERVRBSUwgPSBgXG4gIG11dGF0aW9uIEdldE1TVGVhbXNNZXNzYWdlRGV0YWlsKCRpbnB1dDogR2V0TVNUZWFtc01lc3NhZ2VEZXRhaWxJbnB1dCEpIHtcbiAgICBnZXRNU1RlYW1zTWVzc2FnZURldGFpbChpbnB1dDogJGlucHV0KSB7XG4gICAgICBzdWNjZXNzXG4gICAgICBtZXNzYWdlXG4gICAgICBtc1RlYW1zTWVzc2FnZSB7ICMgVGhpcyBzdHJ1Y3R1cmUgc2hvdWxkIG1hdGNoIE1TVGVhbXNNZXNzYWdlT2JqZWN0XG4gICAgICAgIGlkXG4gICAgICAgIGNoYXRJZFxuICAgICAgICB0ZWFtSWRcbiAgICAgICAgY2hhbm5lbElkXG4gICAgICAgIHJlcGx5VG9JZFxuICAgICAgICB1c2VySWRcbiAgICAgICAgdXNlck5hbWVcbiAgICAgICAgY29udGVudFxuICAgICAgICBjb250ZW50VHlwZVxuICAgICAgICBjcmVhdGVkRGF0ZVRpbWVcbiAgICAgICAgbGFzdE1vZGlmaWVkRGF0ZVRpbWVcbiAgICAgICAgd2ViVXJsXG4gICAgICAgIGF0dGFjaG1lbnRzIHsgaWQgbmFtZSBjb250ZW50VHlwZSBjb250ZW50VXJsIHNpemUgfVxuICAgICAgICBtZW50aW9ucyB7XG4gICAgICAgICAgaWRcbiAgICAgICAgICBtZW50aW9uVGV4dFxuICAgICAgICAgIG1lbnRpb25lZCB7XG4gICAgICAgICAgICB1c2VyIHsgaWQgZGlzcGxheU5hbWUgdXNlcklkZW50aXR5VHlwZSB9XG4gICAgICAgICAgfVxuICAgICAgICB9XG4gICAgICAgICMgcmF3XG4gICAgICB9XG4gICAgfVxuICB9XG5gO1xuXG5leHBvcnQgaW50ZXJmYWNlIEdldE1TVGVhbXNNZXNzYWdlRGV0YWlsSW5wdXQge1xuICBtZXNzYWdlSWQ6IHN0cmluZztcbiAgY2hhdElkPzogc3RyaW5nOyAvLyBQcm92aWRlIGlmIGl0J3MgYSBjaGF0IG1lc3NhZ2VcbiAgdGVhbUlkPzogc3RyaW5nOyAvLyBQcm92aWRlIHdpdGggY2hhbm5lbElkIGlmIGl0J3MgYSBjaGFubmVsIG1lc3NhZ2VcbiAgY2hhbm5lbElkPzogc3RyaW5nOyAvLyBQcm92aWRlIHdpdGggdGVhbUlkIGlmIGl0J3MgYSBjaGFubmVsIG1lc3NhZ2Vcbn1cblxuLyoqXG4gKiBSZWFkcyB0aGUgZGV0YWlsZWQgY29udGVudCBvZiBhIHNwZWNpZmljIE1TIFRlYW1zIG1lc3NhZ2UuXG4gKiBAcGFyYW0gdXNlcklkIFRoZSBJRCBvZiB0aGUgdXNlci5cbiAqIEBwYXJhbSBpZGVudGlmaWVyIEFuIG9iamVjdCB0byBpZGVudGlmeSB0aGUgbWVzc2FnZSwgY29udGFpbmluZyBtZXNzYWdlSWQgYW5kIGNvbnRleHQgKGNoYXRJZCBvciB0ZWFtSWQvY2hhbm5lbElkKS5cbiAqIEByZXR1cm5zIEEgcHJvbWlzZSByZXNvbHZpbmcgdG8gYW4gTVNUZWFtc01lc3NhZ2Ugb2JqZWN0IG9yIG51bGwgaWYgbm90IGZvdW5kL2Vycm9yLlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gcmVhZE1TVGVhbXNNZXNzYWdlKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgaWRlbnRpZmllcjogR2V0TVNUZWFtc01lc3NhZ2VEZXRhaWxJbnB1dFxuKTogUHJvbWlzZTxNU1RlYW1zTWVzc2FnZSB8IG51bGw+IHtcbiAgbG9nZ2VyLmRlYnVnKFxuICAgIGBbTVNUZWFtc1NraWxsc10gcmVhZE1TVGVhbXNNZXNzYWdlIGNhbGxlZCBmb3IgdXNlciAke3VzZXJJZH0sIGlkZW50aWZpZXI6YCxcbiAgICBpZGVudGlmaWVyXG4gICk7XG5cbiAgaWYgKFxuICAgICFpZGVudGlmaWVyLm1lc3NhZ2VJZCB8fFxuICAgICghaWRlbnRpZmllci5jaGF0SWQgJiYgKCFpZGVudGlmaWVyLnRlYW1JZCB8fCAhaWRlbnRpZmllci5jaGFubmVsSWQpKVxuICApIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAnW01TVGVhbXNTa2lsbHNdIEludmFsaWQgaWRlbnRpZmllciBmb3IgcmVhZE1TVGVhbXNNZXNzYWdlLiBOZWVkIG1lc3NhZ2VJZCBhbmQgKGNoYXRJZCBvciB0ZWFtSWQrY2hhbm5lbElkKS4nXG4gICAgKTtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxuXG4gIHRyeSB7XG4gICAgY29uc3QgcmVzcG9uc2VEYXRhID0gYXdhaXQgY2FsbEhhc3VyYUFjdGlvbkdyYXBoUUwoXG4gICAgICB1c2VySWQsXG4gICAgICAnR2V0TVNUZWFtc01lc3NhZ2VEZXRhaWwnLFxuICAgICAgR1FMX0dFVF9NU19URUFNU19NRVNTQUdFX0RFVEFJTCxcbiAgICAgIHtcbiAgICAgICAgaW5wdXQ6IGlkZW50aWZpZXIsXG4gICAgICB9XG4gICAgKTtcblxuICAgIGNvbnN0IGdldFJlc3VsdCA9IHJlc3BvbnNlRGF0YS5nZXRNU1RlYW1zTWVzc2FnZURldGFpbDtcblxuICAgIGlmICghZ2V0UmVzdWx0LnN1Y2Nlc3MgfHwgIWdldFJlc3VsdC5tc1RlYW1zTWVzc2FnZSkge1xuICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgIGBbTVNUZWFtc1NraWxsc10gZ2V0TVNUZWFtc01lc3NhZ2VEZXRhaWwgYWN0aW9uIGZhaWxlZCBvciBtZXNzYWdlIG5vdCBmb3VuZCBmb3IgdXNlciAke3VzZXJJZH06ICR7Z2V0UmVzdWx0Lm1lc3NhZ2V9YCxcbiAgICAgICAgaWRlbnRpZmllclxuICAgICAgKTtcbiAgICAgIHJldHVybiBudWxsO1xuICAgIH1cblxuICAgIC8vIERpcmVjdCBjYXN0IGlmIEdyYXBoUUwgb3V0cHV0IG1hdGNoZXMgYWdlbnQncyBNU1RlYW1zTWVzc2FnZSB0eXBlLlxuICAgIC8vIEVuc3VyZSBuZXN0ZWQgc3RydWN0dXJlcyBsaWtlIGF0dGFjaG1lbnRzIGFuZCBtZW50aW9ucyBhcmUgYWxzbyBjb3JyZWN0bHkgdHlwZWQvbWFwcGVkIGlmIG5lZWRlZC5cbiAgICBjb25zdCBtZXNzYWdlOiBNU1RlYW1zTWVzc2FnZSA9IHtcbiAgICAgIC4uLmdldFJlc3VsdC5tc1RlYW1zTWVzc2FnZSxcbiAgICAgIGNvbnRlbnRUeXBlOiBnZXRSZXN1bHQubXNUZWFtc01lc3NhZ2UuY29udGVudFR5cGUgYXMgJ2h0bWwnIHwgJ3RleHQnLCAvLyBFbnN1cmUgZW51bSB0eXBlIGlmIG5vdCBndWFyYW50ZWVkIGJ5IEdRTFxuICAgICAgYXR0YWNobWVudHM6XG4gICAgICAgIGdldFJlc3VsdC5tc1RlYW1zTWVzc2FnZS5hdHRhY2htZW50cz8ubWFwKChhdHQ6IGFueSkgPT4gKHtcbiAgICAgICAgICBpZDogYXR0LmlkLFxuICAgICAgICAgIG5hbWU6IGF0dC5uYW1lLFxuICAgICAgICAgIGNvbnRlbnRUeXBlOiBhdHQuY29udGVudFR5cGUsXG4gICAgICAgICAgY29udGVudFVybDogYXR0LmNvbnRlbnRVcmwsXG4gICAgICAgICAgc2l6ZTogYXR0LnNpemUsXG4gICAgICAgIH0pKSB8fCBbXSxcbiAgICAgIG1lbnRpb25zOlxuICAgICAgICBnZXRSZXN1bHQubXNUZWFtc01lc3NhZ2UubWVudGlvbnM/Lm1hcCgobWVuOiBhbnkpID0+ICh7XG4gICAgICAgICAgaWQ6IG1lbi5pZCxcbiAgICAgICAgICBtZW50aW9uVGV4dDogbWVuLm1lbnRpb25UZXh0LFxuICAgICAgICAgIG1lbnRpb25lZDogbWVuLm1lbnRpb25lZFxuICAgICAgICAgICAgPyB7XG4gICAgICAgICAgICAgICAgdXNlcjogbWVuLm1lbnRpb25lZC51c2VyXG4gICAgICAgICAgICAgICAgICA/IHtcbiAgICAgICAgICAgICAgICAgICAgICBpZDogbWVuLm1lbnRpb25lZC51c2VyLmlkLFxuICAgICAgICAgICAgICAgICAgICAgIGRpc3BsYXlOYW1lOiBtZW4ubWVudGlvbmVkLnVzZXIuZGlzcGxheU5hbWUsXG4gICAgICAgICAgICAgICAgICAgICAgdXNlcklkZW50aXR5VHlwZTogbWVuLm1lbnRpb25lZC51c2VyLnVzZXJJZGVudGl0eVR5cGUsXG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgIDogdW5kZWZpbmVkLFxuICAgICAgICAgICAgICB9XG4gICAgICAgICAgICA6IHVuZGVmaW5lZCxcbiAgICAgICAgfSkpIHx8IFtdLFxuICAgIH07XG4gICAgcmV0dXJuIG1lc3NhZ2U7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFtNU1RlYW1zU2tpbGxzXSBFcnJvciBpbiByZWFkTVNUZWFtc01lc3NhZ2UgZm9yIHVzZXIgJHt1c2VySWR9LCBpZGVudGlmaWVyOmAsXG4gICAgICBpZGVudGlmaWVyLFxuICAgICAgZXJyb3JcbiAgICApO1xuICAgIHJldHVybiBudWxsO1xuICB9XG59XG4iXX0=