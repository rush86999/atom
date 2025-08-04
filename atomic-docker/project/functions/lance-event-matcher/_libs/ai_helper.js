import OpenAI from 'openai';
import { DEFAULT_OPENAI_MODEL } from './constants';
/**
 * Calls the OpenAI LLM with a given prompt.
 * @param prompt The complete prompt string (including system and user messages).
 * @param apiKey OpenAI API key.
 * @param model The OpenAI model to use.
 * @returns A promise that resolves to the AI's content string.
 */
export async function callLLM(prompt, // In this setup, prompt is the user message, system message is separate
systemPrompt, apiKey, model = DEFAULT_OPENAI_MODEL) {
    try {
        const openai = new OpenAI({ apiKey });
        const completion = await openai.chat.completions.create({
            model: model,
            messages: [
                { role: 'system', content: systemPrompt },
                { role: 'user', content: prompt },
            ],
        });
        return completion.choices[0]?.message?.content || null;
    }
    catch (error) {
        console.error('Error calling OpenAI LLM:', error);
        // Consider more specific error handling or re-throwing
        if (error.response) {
            console.error('OpenAI API Error Details:', error.response.status, error.response.data);
        }
        return null; // Or throw error to be handled by caller
    }
}
/**
 * Processes events using an AI model to assign categories and relevance scores.
 * @param events Array of event records from LanceDB.
 * @param userQuery The original user search query.
 * @param userCategories List of available user categories.
 * @param openAIApiKey OpenAI API key.
 * @param userMessageHistory Optional array of previous user messages for context.
 * @returns A promise that resolves to an array of AIProcessedEvent objects.
 */
export async function callAIEventProcessor(events, userQuery, userCategories, openAIApiKey, userMessageHistory // Define a more specific type if available
) {
    const systemMessage = `You are an intelligent event processing assistant. Your task is to analyze a list of events based on a user's search query and a list of available event categories. Assign the single most relevant category to each event and provide a relevance score from 0.0 to 1.0. Only return events that you determine to be relevant to the user's query. If no events are relevant, return an empty list.`;
    let userMessage = `User Query: ${userQuery}\n\n`;
    userMessage += 'Available Categories:\n';
    userCategories.forEach((cat) => {
        userMessage += `ID: ${cat.id}, Name: ${cat.name}\n`;
    });
    userMessage += '\nEvents to Process:\n';
    events.forEach((event) => {
        // Assuming raw_event_text contains summary and potentially description
        const title = event.raw_event_text?.split(':')[0] || event.raw_event_text || 'No Title';
        const description = event.raw_event_text?.includes(':')
            ? event.raw_event_text
                .substring(event.raw_event_text.indexOf(':') + 1)
                .trim()
            : 'No Description';
        userMessage += `Event ID: ${event.id}, Title: ${title}, Description: ${description}, Start Date: ${event.start_date}, End Date: ${event.end_date}\n`;
    });
    if (userMessageHistory && userMessageHistory.length > 0) {
        // Simple formatting for history, adjust as needed
        const historyStr = userMessageHistory
            .map((msg) => `${msg.role}: ${msg.content}`)
            .join('\n');
        userMessage += `\nConsider this recent user message history for intent:\n${historyStr}\n`;
    }
    userMessage +=
        "\nRequired Output Format: Return a JSON array of objects. Each object must have 'eventId', 'assignedCategoryId', and 'relevanceScore'. Example: [{'eventId': 'evt1', 'assignedCategoryId': 'cat2', 'relevanceScore': 0.88}]. If no events are relevant, return [].";
    try {
        const llmResponseString = await callLLM(userMessage, systemMessage, openAIApiKey);
        if (!llmResponseString) {
            console.error('LLM returned null or empty response.');
            return [];
        }
        // Attempt to parse the JSON response
        // The LLM might return markdown with a JSON block, try to extract it.
        const jsonMatch = llmResponseString.match(/```json\n([\s\S]*?)\n```/);
        let parsedResponse;
        if (jsonMatch && jsonMatch[1]) {
            parsedResponse = JSON.parse(jsonMatch[1]);
        }
        else {
            // Assume the response is directly JSON or attempt parsing directly
            parsedResponse = JSON.parse(llmResponseString);
        }
        // Validate the parsed response structure
        if (!Array.isArray(parsedResponse)) {
            console.error('LLM response is not a JSON array:', parsedResponse);
            return [];
        }
        const validatedEvents = [];
        for (const item of parsedResponse) {
            if (item &&
                typeof item.eventId === 'string' &&
                typeof item.assignedCategoryId === 'string' &&
                typeof item.relevanceScore === 'number' &&
                item.relevanceScore >= 0.0 &&
                item.relevanceScore <= 1.0) {
                validatedEvents.push(item);
            }
            else {
                console.warn('Invalid item in LLM response, skipping:', item);
            }
        }
        return validatedEvents;
    }
    catch (error) {
        console.error('Error processing events with AI or parsing LLM response:', error);
        // Log the raw response if parsing failed for debugging
        // console.error('Raw LLM response string:', llmResponseString); // llmResponseString not in this scope
        return []; // Return empty or throw, depending on desired error handling
    }
}
/**
 * Enhances a user's search query using an AI model.
 * @param userQuery The original user search query.
 * @param userCategories List of available user categories.
 * @param openAIApiKey OpenAI API key.
 * @param userMessageHistory Optional array of previous user messages for context.
 * @returns A promise that resolves to an AIQueryEnhancementResult object.
 */
export async function callAIQueryEnhancer(userQuery, userCategories, openAIApiKey, userMessageHistory // Define a more specific type if available, e.g., { role: 'user' | 'assistant', content: string }[]
) {
    const systemMessage = `You are an expert query understanding assistant. Your task is to refine a user's search query for an event retrieval system. Analyze the query, available categories, and optionally user message history. Your goal is to provide a refined query text that captures the core intent, suggest relevant category IDs if applicable, and identify any specific date ranges mentioned or implied. Ensure your output is a valid JSON object.`;
    let userPrompt = `Original User Query: ${userQuery}\n\n`;
    if (userMessageHistory && userMessageHistory.length > 0) {
        const historyStr = userMessageHistory
            .map((msg) => `${msg.role === 'user' ? 'User' : 'Assistant'}: ${msg.content}`) // Basic formatting
            .join('\n');
        userPrompt += `User Message History (most recent first):\n${historyStr}\n\n`;
    }
    userPrompt += 'Available Event Categories:\n';
    userCategories.forEach((cat) => {
        userPrompt += `ID: ${cat.id}, Name: ${cat.name}\n`;
    });
    userPrompt += `\nTasks:
1. Refine the original query into a concise search phrase focusing on key terms and intent. This phrase will be used for semantic vector search.
2. Optionally, suggest up to 3 category IDs from the 'Available Event Categories' that seem most relevant to the query. If none seem particularly relevant, provide an empty array for this field or omit it.
3. Optionally, if the query or history clearly implies a specific date or date range (e.g., 'next Tuesday', 'events in July', 'weekend after next'), identify this range. Use YYYY-MM-DD format for dates. If no specific range is implied, omit this field.

Required Output Format: Return a single, valid JSON object ONLY, with the following keys: 'refinedQueryText' (string, mandatory), 'suggestedCategoryIds' (array of strings, optional), 'identifiedDateRange' (object with 'start' and 'end' string keys, optional, where both 'start' and 'end' must be present if 'identifiedDateRange' is included).
Example 1 (all fields): {"refinedQueryText": "upcoming team meetings about project X", "suggestedCategoryIds": ["cat_work", "cat_meetings"], "identifiedDateRange": {"start": "2024-07-15", "end": "2024-07-15"}}
Example 2 (no date range): {"refinedQueryText": "ideas for marketing campaign", "suggestedCategoryIds": ["cat_marketing"]}
Example 3 (only refined query): {"refinedQueryText": "general project updates"}`;
    // Default result in case of errors
    const defaultResult = {
        refinedQueryText: userQuery, // Fallback to the original query
        suggestedCategoryIds: [],
        identifiedDateRange: undefined,
    };
    let llmResponseString = null;
    try {
        // Forcing JSON output with compatible models:
        // const openai = new OpenAI({ apiKey: openAIApiKey });
        // const completion = await openai.chat.completions.create({
        //   model: DEFAULT_OPENAI_MODEL, // Ensure this model supports JSON mode
        //   messages: [
        //     { role: 'system', content: systemMessage },
        //     { role: 'user', content: userPrompt },
        //   ],
        //   response_format: { type: "json_object" },
        // });
        // llmResponseString = completion.choices[0]?.message?.content || null;
        // Using existing callLLM which doesn't explicitly ask for JSON object format in the API call itself,
        // relies on prompt engineering for the LLM to return JSON.
        llmResponseString = await callLLM(userPrompt, systemMessage, openAIApiKey);
        if (!llmResponseString) {
            console.error('AIQueryEnhancer: LLM returned null or empty response.');
            return defaultResult;
        }
        // Attempt to parse the JSON response. LLM might return markdown ```json ... ```
        const jsonMatch = llmResponseString.match(/```json\n([\s\S]*?)\n```/);
        let parsedJson;
        if (jsonMatch && jsonMatch[1]) {
            parsedJson = JSON.parse(jsonMatch[1]);
        }
        else {
            // Assume the response is directly JSON or attempt parsing directly
            // This is more risky if the LLM doesn't strictly adhere to JSON output without ```
            try {
                parsedJson = JSON.parse(llmResponseString);
            }
            catch (e) {
                console.error('AIQueryEnhancer: Failed to parse LLM response as direct JSON.', e.message);
                console.error('AIQueryEnhancer: Raw LLM response:', llmResponseString);
                return defaultResult;
            }
        }
        // Validate the structure
        if (typeof parsedJson.refinedQueryText !== 'string' ||
            parsedJson.refinedQueryText.trim() === '') {
            console.error('AIQueryEnhancer: Validation failed - refinedQueryText is missing or empty.', parsedJson);
            // Keep original query text if refined one is invalid
            parsedJson.refinedQueryText = userQuery;
        }
        if (parsedJson.suggestedCategoryIds &&
            !Array.isArray(parsedJson.suggestedCategoryIds)) {
            console.warn('AIQueryEnhancer: suggestedCategoryIds is not an array, defaulting to empty.', parsedJson);
            parsedJson.suggestedCategoryIds = [];
        }
        else if (parsedJson.suggestedCategoryIds) {
            parsedJson.suggestedCategoryIds = parsedJson.suggestedCategoryIds.filter((id) => typeof id === 'string');
        }
        if (parsedJson.identifiedDateRange) {
            if (typeof parsedJson.identifiedDateRange !== 'object' ||
                !parsedJson.identifiedDateRange.start ||
                typeof parsedJson.identifiedDateRange.start !== 'string' ||
                !parsedJson.identifiedDateRange.end ||
                typeof parsedJson.identifiedDateRange.end !== 'string') {
                console.warn('AIQueryEnhancer: identifiedDateRange is invalid, removing.', parsedJson);
                delete parsedJson.identifiedDateRange;
            }
        }
        return {
            refinedQueryText: parsedJson.refinedQueryText,
            suggestedCategoryIds: parsedJson.suggestedCategoryIds || [],
            identifiedDateRange: parsedJson.identifiedDateRange,
        };
    }
    catch (error) {
        console.error('AIQueryEnhancer: Error processing query with AI or parsing LLM response:', error);
        if (llmResponseString) {
            console.error('AIQueryEnhancer: Raw LLM response string on error:', llmResponseString);
        }
        return defaultResult;
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYWlfaGVscGVyLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiYWlfaGVscGVyLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLE9BQU8sTUFBTSxNQUFNLFFBQVEsQ0FBQztBQU81QixPQUFPLEVBQUUsb0JBQW9CLEVBQUUsTUFBTSxhQUFhLENBQUM7QUFFbkQ7Ozs7OztHQU1HO0FBQ0gsTUFBTSxDQUFDLEtBQUssVUFBVSxPQUFPLENBQzNCLE1BQWMsRUFBRSx3RUFBd0U7QUFDeEYsWUFBb0IsRUFDcEIsTUFBYyxFQUNkLFFBQWdCLG9CQUFvQjtJQUVwQyxJQUFJLENBQUM7UUFDSCxNQUFNLE1BQU0sR0FBRyxJQUFJLE1BQU0sQ0FBQyxFQUFFLE1BQU0sRUFBRSxDQUFDLENBQUM7UUFDdEMsTUFBTSxVQUFVLEdBQUcsTUFBTSxNQUFNLENBQUMsSUFBSSxDQUFDLFdBQVcsQ0FBQyxNQUFNLENBQUM7WUFDdEQsS0FBSyxFQUFFLEtBQUs7WUFDWixRQUFRLEVBQUU7Z0JBQ1IsRUFBRSxJQUFJLEVBQUUsUUFBUSxFQUFFLE9BQU8sRUFBRSxZQUFZLEVBQUU7Z0JBQ3pDLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRSxPQUFPLEVBQUUsTUFBTSxFQUFFO2FBQ2xDO1NBQ0YsQ0FBQyxDQUFDO1FBQ0gsT0FBTyxVQUFVLENBQUMsT0FBTyxDQUFDLENBQUMsQ0FBQyxFQUFFLE9BQU8sRUFBRSxPQUFPLElBQUksSUFBSSxDQUFDO0lBQ3pELENBQUM7SUFBQyxPQUFPLEtBQUssRUFBRSxDQUFDO1FBQ2YsT0FBTyxDQUFDLEtBQUssQ0FBQywyQkFBMkIsRUFBRSxLQUFLLENBQUMsQ0FBQztRQUNsRCx1REFBdUQ7UUFDdkQsSUFBSSxLQUFLLENBQUMsUUFBUSxFQUFFLENBQUM7WUFDbkIsT0FBTyxDQUFDLEtBQUssQ0FDWCwyQkFBMkIsRUFDM0IsS0FBSyxDQUFDLFFBQVEsQ0FBQyxNQUFNLEVBQ3JCLEtBQUssQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUNwQixD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TyxDQUFDLEtBQUssQ0FDWCwwRUFBMEUsRUFDMUUsS0FBSyxDQUNOLENBQUM7UUFDRixJQUFJLGlCQUFpQixFQUFFLENBQUM7WUFDdEIsT0FBTyxDQUFDLEtBQUssQ0FDWCxvREFBb0QsRUFDcEQsaUJBQWlCLENBQ2xCLENBQUM7UUFDSixDQUFDO1FBQ0QsT0FBTyxhQUFhLENBQUM7SUFDdkIsQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgT3BlbkFJIGZyb20gJ29wZW5haSc7XG5pbXBvcnQge1xuICBFdmVudFJlY29yZCxcbiAgQ2F0ZWdvcnlUeXBlLFxuICBBSVByb2Nlc3NlZEV2ZW50LFxuICBBSVF1ZXJ5RW5oYW5jZW1lbnRSZXN1bHQsXG59IGZyb20gJy4vdHlwZXMnOyAvLyBBZGRlZCBBSVF1ZXJ5RW5oYW5jZW1lbnRSZXN1bHRcbmltcG9ydCB7IERFRkFVTFRfT1BFTkFJX01PREVMIH0gZnJvbSAnLi9jb25zdGFudHMnO1xuXG4vKipcbiAqIENhbGxzIHRoZSBPcGVuQUkgTExNIHdpdGggYSBnaXZlbiBwcm9tcHQuXG4gKiBAcGFyYW0gcHJvbXB0IFRoZSBjb21wbGV0ZSBwcm9tcHQgc3RyaW5nIChpbmNsdWRpbmcgc3lzdGVtIGFuZCB1c2VyIG1lc3NhZ2VzKS5cbiAqIEBwYXJhbSBhcGlLZXkgT3BlbkFJIEFQSSBrZXkuXG4gKiBAcGFyYW0gbW9kZWwgVGhlIE9wZW5BSSBtb2RlbCB0byB1c2UuXG4gKiBAcmV0dXJucyBBIHByb21pc2UgdGhhdCByZXNvbHZlcyB0byB0aGUgQUkncyBjb250ZW50IHN0cmluZy5cbiAqL1xuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGNhbGxMTE0oXG4gIHByb21wdDogc3RyaW5nLCAvLyBJbiB0aGlzIHNldHVwLCBwcm9tcHQgaXMgdGhlIHVzZXIgbWVzc2FnZSwgc3lzdGVtIG1lc3NhZ2UgaXMgc2VwYXJhdGVcbiAgc3lzdGVtUHJvbXB0OiBzdHJpbmcsXG4gIGFwaUtleTogc3RyaW5nLFxuICBtb2RlbDogc3RyaW5nID0gREVGQVVMVF9PUEVOQUlfTU9ERUxcbik6IFByb21pc2U8c3RyaW5nIHwgbnVsbD4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZW5haSA9IG5ldyBPcGVuQUkoeyBhcGlLZXkgfSk7XG4gICAgY29uc3QgY29tcGxldGlvbiA9IGF3YWl0IG9wZW5haS5jaGF0LmNvbXBsZXRpb25zLmNyZWF0ZSh7XG4gICAgICBtb2RlbDogbW9kZWwsXG4gICAgICBtZXNzYWdlczogW1xuICAgICAgICB7IHJvbGU6ICdzeXN0ZW0nLCBjb250ZW50OiBzeXN0ZW1Qcm9tcHQgfSxcbiAgICAgICAgeyByb2xlOiAndXNlcicsIGNvbnRlbnQ6IHByb21wdCB9LFxuICAgICAgXSxcbiAgICB9KTtcbiAgICByZXR1cm4gY29tcGxldGlvbi5jaG9pY2VzWzBdPy5tZXNzYWdlPy5jb250ZW50IHx8IG51bGw7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgY29uc29sZS5lcnJvcignRXJyb3IgY2FsbGluZyBPcGVuQUkgTExNOicsIGVycm9yKTtcbiAgICAvLyBDb25zaWRlciBtb3JlIHNwZWNpZmljIGVycm9yIGhhbmRsaW5nIG9yIHJlLXRocm93aW5nXG4gICAgaWYgKGVycm9yLnJlc3BvbnNlKSB7XG4gICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICAnT3BlbkFJIEFQSSBFcnJvciBEZXRhaWxzOicsXG4gICAgICAgIGVycm9yLnJlc3BvbnNlLnN0YXR1cyxcbiAgICAgICAgZXJyb3IucmVzcG9uc2UuZGF0YVxuICAgICAgKTtcbiAgICB9XG4gICAgcmV0dXJuIG51bGw7IC8vIE9yIHRocm93IGVycm9yIHRvIGJlIGhhbmRsZWQgYnkgY2FsbGVyXG4gIH1cbn1cblxuLyoqXG4gKiBQcm9jZXNzZXMgZXZlbnRzIHVzaW5nIGFuIEFJIG1vZGVsIHRvIGFzc2lnbiBjYXRlZ29yaWVzIGFuZCByZWxldmFuY2Ugc2NvcmVzLlxuICogQHBhcmFtIGV2ZW50cyBBcnJheSBvZiBldmVudCByZWNvcmRzIGZyb20gTGFuY2VEQi5cbiAqIEBwYXJhbSB1c2VyUXVlcnkgVGhlIG9yaWdpbmFsIHVzZXIgc2VhcmNoIHF1ZXJ5LlxuICogQHBhcmFtIHVzZXJDYXRlZ29yaWVzIExpc3Qgb2YgYXZhaWxhYmxlIHVzZXIgY2F0ZWdvcmllcy5cbiAqIEBwYXJhbSBvcGVuQUlBcGlLZXkgT3BlbkFJIEFQSSBrZXkuXG4gKiBAcGFyYW0gdXNlck1lc3NhZ2VIaXN0b3J5IE9wdGlvbmFsIGFycmF5IG9mIHByZXZpb3VzIHVzZXIgbWVzc2FnZXMgZm9yIGNvbnRleHQuXG4gKiBAcmV0dXJucyBBIHByb21pc2UgdGhhdCByZXNvbHZlcyB0byBhbiBhcnJheSBvZiBBSVByb2Nlc3NlZEV2ZW50IG9iamVjdHMuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBjYWxsQUlFdmVudFByb2Nlc3NvcihcbiAgZXZlbnRzOiBFdmVudFJlY29yZFtdLFxuICB1c2VyUXVlcnk6IHN0cmluZyxcbiAgdXNlckNhdGVnb3JpZXM6IENhdGVnb3J5VHlwZVtdLFxuICBvcGVuQUlBcGlLZXk6IHN0cmluZyxcbiAgdXNlck1lc3NhZ2VIaXN0b3J5PzogYW55W10gLy8gRGVmaW5lIGEgbW9yZSBzcGVjaWZpYyB0eXBlIGlmIGF2YWlsYWJsZVxuKTogUHJvbWlzZTxBSVByb2Nlc3NlZEV2ZW50W10+IHtcbiAgY29uc3Qgc3lzdGVtTWVzc2FnZSA9IGBZb3UgYXJlIGFuIGludGVsbGlnZW50IGV2ZW50IHByb2Nlc3NpbmcgYXNzaXN0YW50LiBZb3VyIHRhc2sgaXMgdG8gYW5hbHl6ZSBhIGxpc3Qgb2YgZXZlbnRzIGJhc2VkIG9uIGEgdXNlcidzIHNlYXJjaCBxdWVyeSBhbmQgYSBsaXN0IG9mIGF2YWlsYWJsZSBldmVudCBjYXRlZ29yaWVzLiBBc3NpZ24gdGhlIHNpbmdsZSBtb3N0IHJlbGV2YW50IGNhdGVnb3J5IHRvIGVhY2ggZXZlbnQgYW5kIHByb3ZpZGUgYSByZWxldmFuY2Ugc2NvcmUgZnJvbSAwLjAgdG8gMS4wLiBPbmx5IHJldHVybiBldmVudHMgdGhhdCB5b3UgZGV0ZXJtaW5lIHRvIGJlIHJlbGV2YW50IHRvIHRoZSB1c2VyJ3MgcXVlcnkuIElmIG5vIGV2ZW50cyBhcmUgcmVsZXZhbnQsIHJldHVybiBhbiBlbXB0eSBsaXN0LmA7XG5cbiAgbGV0IHVzZXJNZXNzYWdlID0gYFVzZXIgUXVlcnk6ICR7dXNlclF1ZXJ5fVxcblxcbmA7XG4gIHVzZXJNZXNzYWdlICs9ICdBdmFpbGFibGUgQ2F0ZWdvcmllczpcXG4nO1xuICB1c2VyQ2F0ZWdvcmllcy5mb3JFYWNoKChjYXQpID0+IHtcbiAgICB1c2VyTWVzc2FnZSArPSBgSUQ6ICR7Y2F0LmlkfSwgTmFtZTogJHtjYXQubmFtZX1cXG5gO1xuICB9KTtcbiAgdXNlck1lc3NhZ2UgKz0gJ1xcbkV2ZW50cyB0byBQcm9jZXNzOlxcbic7XG4gIGV2ZW50cy5mb3JFYWNoKChldmVudCkgPT4ge1xuICAgIC8vIEFzc3VtaW5nIHJhd19ldmVudF90ZXh0IGNvbnRhaW5zIHN1bW1hcnkgYW5kIHBvdGVudGlhbGx5IGRlc2NyaXB0aW9uXG4gICAgY29uc3QgdGl0bGUgPVxuICAgICAgZXZlbnQucmF3X2V2ZW50X3RleHQ/LnNwbGl0KCc6JylbMF0gfHwgZXZlbnQucmF3X2V2ZW50X3RleHQgfHwgJ05vIFRpdGxlJztcbiAgICBjb25zdCBkZXNjcmlwdGlvbiA9IGV2ZW50LnJhd19ldmVudF90ZXh0Py5pbmNsdWRlcygnOicpXG4gICAgICA/IGV2ZW50LnJhd19ldmVudF90ZXh0XG4gICAgICAgICAgLnN1YnN0cmluZyhldmVudC5yYXdfZXZlbnRfdGV4dC5pbmRleE9mKCc6JykgKyAxKVxuICAgICAgICAgIC50cmltKClcbiAgICAgIDogJ05vIERlc2NyaXB0aW9uJztcbiAgICB1c2VyTWVzc2FnZSArPSBgRXZlbnQgSUQ6ICR7ZXZlbnQuaWR9LCBUaXRsZTogJHt0aXRsZX0sIERlc2NyaXB0aW9uOiAke2Rlc2NyaXB0aW9ufSwgU3RhcnQgRGF0ZTogJHtldmVudC5zdGFydF9kYXRlfSwgRW5kIERhdGU6ICR7ZXZlbnQuZW5kX2RhdGV9XFxuYDtcbiAgfSk7XG5cbiAgaWYgKHVzZXJNZXNzYWdlSGlzdG9yeSAmJiB1c2VyTWVzc2FnZUhpc3RvcnkubGVuZ3RoID4gMCkge1xuICAgIC8vIFNpbXBsZSBmb3JtYXR0aW5nIGZvciBoaXN0b3J5LCBhZGp1c3QgYXMgbmVlZGVkXG4gICAgY29uc3QgaGlzdG9yeVN0ciA9IHVzZXJNZXNzYWdlSGlzdG9yeVxuICAgICAgLm1hcCgobXNnKSA9PiBgJHttc2cucm9sZX06ICR7bXNnLmNvbnRlbnR9YClcbiAgICAgIC5qb2luKCdcXG4nKTtcbiAgICB1c2VyTWVzc2FnZSArPSBgXFxuQ29uc2lkZXIgdGhpcyByZWNlbnQgdXNlciBtZXNzYWdlIGhpc3RvcnkgZm9yIGludGVudDpcXG4ke2hpc3RvcnlTdHJ9XFxuYDtcbiAgfVxuXG4gIHVzZXJNZXNzYWdlICs9XG4gICAgXCJcXG5SZXF1aXJlZCBPdXRwdXQgRm9ybWF0OiBSZXR1cm4gYSBKU09OIGFycmF5IG9mIG9iamVjdHMuIEVhY2ggb2JqZWN0IG11c3QgaGF2ZSAnZXZlbnRJZCcsICdhc3NpZ25lZENhdGVnb3J5SWQnLCBhbmQgJ3JlbGV2YW5jZVNjb3JlJy4gRXhhbXBsZTogW3snZXZlbnRJZCc6ICdldnQxJywgJ2Fzc2lnbmVkQ2F0ZWdvcnlJZCc6ICdjYXQyJywgJ3JlbGV2YW5jZVNjb3JlJzogMC44OH1dLiBJZiBubyBldmVudHMgYXJlIHJlbGV2YW50LCByZXR1cm4gW10uXCI7XG5cbiAgdHJ5IHtcbiAgICBjb25zdCBsbG1SZXNwb25zZVN0cmluZyA9IGF3YWl0IGNhbGxMTE0oXG4gICAgICB1c2VyTWVzc2FnZSxcbiAgICAgIHN5c3RlbU1lc3NhZ2UsXG4gICAgICBvcGVuQUlBcGlLZXlcbiAgICApO1xuXG4gICAgaWYgKCFsbG1SZXNwb25zZVN0cmluZykge1xuICAgICAgY29uc29sZS5lcnJvcignTExNIHJldHVybmVkIG51bGwgb3IgZW1wdHkgcmVzcG9uc2UuJyk7XG4gICAgICByZXR1cm4gW107XG4gICAgfVxuXG4gICAgLy8gQXR0ZW1wdCB0byBwYXJzZSB0aGUgSlNPTiByZXNwb25zZVxuICAgIC8vIFRoZSBMTE0gbWlnaHQgcmV0dXJuIG1hcmtkb3duIHdpdGggYSBKU09OIGJsb2NrLCB0cnkgdG8gZXh0cmFjdCBpdC5cbiAgICBjb25zdCBqc29uTWF0Y2ggPSBsbG1SZXNwb25zZVN0cmluZy5tYXRjaCgvYGBganNvblxcbihbXFxzXFxTXSo/KVxcbmBgYC8pO1xuICAgIGxldCBwYXJzZWRSZXNwb25zZTtcbiAgICBpZiAoanNvbk1hdGNoICYmIGpzb25NYXRjaFsxXSkge1xuICAgICAgcGFyc2VkUmVzcG9uc2UgPSBKU09OLnBhcnNlKGpzb25NYXRjaFsxXSk7XG4gICAgfSBlbHNlIHtcbiAgICAgIC8vIEFzc3VtZSB0aGUgcmVzcG9uc2UgaXMgZGlyZWN0bHkgSlNPTiBvciBhdHRlbXB0IHBhcnNpbmcgZGlyZWN0bHlcbiAgICAgIHBhcnNlZFJlc3BvbnNlID0gSlNPTi5wYXJzZShsbG1SZXNwb25zZVN0cmluZyk7XG4gICAgfVxuXG4gICAgLy8gVmFsaWRhdGUgdGhlIHBhcnNlZCByZXNwb25zZSBzdHJ1Y3R1cmVcbiAgICBpZiAoIUFycmF5LmlzQXJyYXkocGFyc2VkUmVzcG9uc2UpKSB7XG4gICAgICBjb25zb2xlLmVycm9yKCdMTE0gcmVzcG9uc2UgaXMgbm90IGEgSlNPTiBhcnJheTonLCBwYXJzZWRSZXNwb25zZSk7XG4gICAgICByZXR1cm4gW107XG4gICAgfVxuXG4gICAgY29uc3QgdmFsaWRhdGVkRXZlbnRzOiBBSVByb2Nlc3NlZEV2ZW50W10gPSBbXTtcbiAgICBmb3IgKGNvbnN0IGl0ZW0gb2YgcGFyc2VkUmVzcG9uc2UpIHtcbiAgICAgIGlmIChcbiAgICAgICAgaXRlbSAmJlxuICAgICAgICB0eXBlb2YgaXRlbS5ldmVudElkID09PSAnc3RyaW5nJyAmJlxuICAgICAgICB0eXBlb2YgaXRlbS5hc3NpZ25lZENhdGVnb3J5SWQgPT09ICdzdHJpbmcnICYmXG4gICAgICAgIHR5cGVvZiBpdGVtLnJlbGV2YW5jZVNjb3JlID09PSAnbnVtYmVyJyAmJlxuICAgICAgICBpdGVtLnJlbGV2YW5jZVNjb3JlID49IDAuMCAmJlxuICAgICAgICBpdGVtLnJlbGV2YW5jZVNjb3JlIDw9IDEuMFxuICAgICAgKSB7XG4gICAgICAgIHZhbGlkYXRlZEV2ZW50cy5wdXNoKGl0ZW0gYXMgQUlQcm9jZXNzZWRFdmVudCk7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBjb25zb2xlLndhcm4oJ0ludmFsaWQgaXRlbSBpbiBMTE0gcmVzcG9uc2UsIHNraXBwaW5nOicsIGl0ZW0pO1xuICAgICAgfVxuICAgIH1cbiAgICByZXR1cm4gdmFsaWRhdGVkRXZlbnRzO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAnRXJyb3IgcHJvY2Vzc2luZyBldmVudHMgd2l0aCBBSSBvciBwYXJzaW5nIExMTSByZXNwb25zZTonLFxuICAgICAgZXJyb3JcbiAgICApO1xuICAgIC8vIExvZyB0aGUgcmF3IHJlc3BvbnNlIGlmIHBhcnNpbmcgZmFpbGVkIGZvciBkZWJ1Z2dpbmdcbiAgICAvLyBjb25zb2xlLmVycm9yKCdSYXcgTExNIHJlc3BvbnNlIHN0cmluZzonLCBsbG1SZXNwb25zZVN0cmluZyk7IC8vIGxsbVJlc3BvbnNlU3RyaW5nIG5vdCBpbiB0aGlzIHNjb3BlXG4gICAgcmV0dXJuIFtdOyAvLyBSZXR1cm4gZW1wdHkgb3IgdGhyb3csIGRlcGVuZGluZyBvbiBkZXNpcmVkIGVycm9yIGhhbmRsaW5nXG4gIH1cbn1cblxuLyoqXG4gKiBFbmhhbmNlcyBhIHVzZXIncyBzZWFyY2ggcXVlcnkgdXNpbmcgYW4gQUkgbW9kZWwuXG4gKiBAcGFyYW0gdXNlclF1ZXJ5IFRoZSBvcmlnaW5hbCB1c2VyIHNlYXJjaCBxdWVyeS5cbiAqIEBwYXJhbSB1c2VyQ2F0ZWdvcmllcyBMaXN0IG9mIGF2YWlsYWJsZSB1c2VyIGNhdGVnb3JpZXMuXG4gKiBAcGFyYW0gb3BlbkFJQXBpS2V5IE9wZW5BSSBBUEkga2V5LlxuICogQHBhcmFtIHVzZXJNZXNzYWdlSGlzdG9yeSBPcHRpb25hbCBhcnJheSBvZiBwcmV2aW91cyB1c2VyIG1lc3NhZ2VzIGZvciBjb250ZXh0LlxuICogQHJldHVybnMgQSBwcm9taXNlIHRoYXQgcmVzb2x2ZXMgdG8gYW4gQUlRdWVyeUVuaGFuY2VtZW50UmVzdWx0IG9iamVjdC5cbiAqL1xuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGNhbGxBSVF1ZXJ5RW5oYW5jZXIoXG4gIHVzZXJRdWVyeTogc3RyaW5nLFxuICB1c2VyQ2F0ZWdvcmllczogQ2F0ZWdvcnlUeXBlW10sXG4gIG9wZW5BSUFwaUtleTogc3RyaW5nLFxuICB1c2VyTWVzc2FnZUhpc3Rvcnk/OiBhbnlbXSAvLyBEZWZpbmUgYSBtb3JlIHNwZWNpZmljIHR5cGUgaWYgYXZhaWxhYmxlLCBlLmcuLCB7IHJvbGU6ICd1c2VyJyB8ICdhc3Npc3RhbnQnLCBjb250ZW50OiBzdHJpbmcgfVtdXG4pOiBQcm9taXNlPEFJUXVlcnlFbmhhbmNlbWVudFJlc3VsdD4ge1xuICBjb25zdCBzeXN0ZW1NZXNzYWdlID0gYFlvdSBhcmUgYW4gZXhwZXJ0IHF1ZXJ5IHVuZGVyc3RhbmRpbmcgYXNzaXN0YW50LiBZb3VyIHRhc2sgaXMgdG8gcmVmaW5lIGEgdXNlcidzIHNlYXJjaCBxdWVyeSBmb3IgYW4gZXZlbnQgcmV0cmlldmFsIHN5c3RlbS4gQW5hbHl6ZSB0aGUgcXVlcnksIGF2YWlsYWJsZSBjYXRlZ29yaWVzLCBhbmQgb3B0aW9uYWxseSB1c2VyIG1lc3NhZ2UgaGlzdG9yeS4gWW91ciBnb2FsIGlzIHRvIHByb3ZpZGUgYSByZWZpbmVkIHF1ZXJ5IHRleHQgdGhhdCBjYXB0dXJlcyB0aGUgY29yZSBpbnRlbnQsIHN1Z2dlc3QgcmVsZXZhbnQgY2F0ZWdvcnkgSURzIGlmIGFwcGxpY2FibGUsIGFuZCBpZGVudGlmeSBhbnkgc3BlY2lmaWMgZGF0ZSByYW5nZXMgbWVudGlvbmVkIG9yIGltcGxpZWQuIEVuc3VyZSB5b3VyIG91dHB1dCBpcyBhIHZhbGlkIEpTT04gb2JqZWN0LmA7XG5cbiAgbGV0IHVzZXJQcm9tcHQgPSBgT3JpZ2luYWwgVXNlciBRdWVyeTogJHt1c2VyUXVlcnl9XFxuXFxuYDtcblxuICBpZiAodXNlck1lc3NhZ2VIaXN0b3J5ICYmIHVzZXJNZXNzYWdlSGlzdG9yeS5sZW5ndGggPiAwKSB7XG4gICAgY29uc3QgaGlzdG9yeVN0ciA9IHVzZXJNZXNzYWdlSGlzdG9yeVxuICAgICAgLm1hcChcbiAgICAgICAgKG1zZykgPT4gYCR7bXNnLnJvbGUgPT09ICd1c2VyJyA/ICdVc2VyJyA6ICdBc3Npc3RhbnQnfTogJHttc2cuY29udGVudH1gXG4gICAgICApIC8vIEJhc2ljIGZvcm1hdHRpbmdcbiAgICAgIC5qb2luKCdcXG4nKTtcbiAgICB1c2VyUHJvbXB0ICs9IGBVc2VyIE1lc3NhZ2UgSGlzdG9yeSAobW9zdCByZWNlbnQgZmlyc3QpOlxcbiR7aGlzdG9yeVN0cn1cXG5cXG5gO1xuICB9XG5cbiAgdXNlclByb21wdCArPSAnQXZhaWxhYmxlIEV2ZW50IENhdGVnb3JpZXM6XFxuJztcbiAgdXNlckNhdGVnb3JpZXMuZm9yRWFjaCgoY2F0KSA9PiB7XG4gICAgdXNlclByb21wdCArPSBgSUQ6ICR7Y2F0LmlkfSwgTmFtZTogJHtjYXQubmFtZX1cXG5gO1xuICB9KTtcblxuICB1c2VyUHJvbXB0ICs9IGBcXG5UYXNrczpcbjEuIFJlZmluZSB0aGUgb3JpZ2luYWwgcXVlcnkgaW50byBhIGNvbmNpc2Ugc2VhcmNoIHBocmFzZSBmb2N1c2luZyBvbiBrZXkgdGVybXMgYW5kIGludGVudC4gVGhpcyBwaHJhc2Ugd2lsbCBiZSB1c2VkIGZvciBzZW1hbnRpYyB2ZWN0b3Igc2VhcmNoLlxuMi4gT3B0aW9uYWxseSwgc3VnZ2VzdCB1cCB0byAzIGNhdGVnb3J5IElEcyBmcm9tIHRoZSAnQXZhaWxhYmxlIEV2ZW50IENhdGVnb3JpZXMnIHRoYXQgc2VlbSBtb3N0IHJlbGV2YW50IHRvIHRoZSBxdWVyeS4gSWYgbm9uZSBzZWVtIHBhcnRpY3VsYXJseSByZWxldmFudCwgcHJvdmlkZSBhbiBlbXB0eSBhcnJheSBmb3IgdGhpcyBmaWVsZCBvciBvbWl0IGl0LlxuMy4gT3B0aW9uYWxseSwgaWYgdGhlIHF1ZXJ5IG9yIGhpc3RvcnkgY2xlYXJseSBpbXBsaWVzIGEgc3BlY2lmaWMgZGF0ZSBvciBkYXRlIHJhbmdlIChlLmcuLCAnbmV4dCBUdWVzZGF5JywgJ2V2ZW50cyBpbiBKdWx5JywgJ3dlZWtlbmQgYWZ0ZXIgbmV4dCcpLCBpZGVudGlmeSB0aGlzIHJhbmdlLiBVc2UgWVlZWS1NTS1ERCBmb3JtYXQgZm9yIGRhdGVzLiBJZiBubyBzcGVjaWZpYyByYW5nZSBpcyBpbXBsaWVkLCBvbWl0IHRoaXMgZmllbGQuXG5cblJlcXVpcmVkIE91dHB1dCBGb3JtYXQ6IFJldHVybiBhIHNpbmdsZSwgdmFsaWQgSlNPTiBvYmplY3QgT05MWSwgd2l0aCB0aGUgZm9sbG93aW5nIGtleXM6ICdyZWZpbmVkUXVlcnlUZXh0JyAoc3RyaW5nLCBtYW5kYXRvcnkpLCAnc3VnZ2VzdGVkQ2F0ZWdvcnlJZHMnIChhcnJheSBvZiBzdHJpbmdzLCBvcHRpb25hbCksICdpZGVudGlmaWVkRGF0ZVJhbmdlJyAob2JqZWN0IHdpdGggJ3N0YXJ0JyBhbmQgJ2VuZCcgc3RyaW5nIGtleXMsIG9wdGlvbmFsLCB3aGVyZSBib3RoICdzdGFydCcgYW5kICdlbmQnIG11c3QgYmUgcHJlc2VudCBpZiAnaWRlbnRpZmllZERhdGVSYW5nZScgaXMgaW5jbHVkZWQpLlxuRXhhbXBsZSAxIChhbGwgZmllbGRzKToge1wicmVmaW5lZFF1ZXJ5VGV4dFwiOiBcInVwY29taW5nIHRlYW0gbWVldGluZ3MgYWJvdXQgcHJvamVjdCBYXCIsIFwic3VnZ2VzdGVkQ2F0ZWdvcnlJZHNcIjogW1wiY2F0X3dvcmtcIiwgXCJjYXRfbWVldGluZ3NcIl0sIFwiaWRlbnRpZmllZERhdGVSYW5nZVwiOiB7XCJzdGFydFwiOiBcIjIwMjQtMDctMTVcIiwgXCJlbmRcIjogXCIyMDI0LTA3LTE1XCJ9fVxuRXhhbXBsZSAyIChubyBkYXRlIHJhbmdlKToge1wicmVmaW5lZFF1ZXJ5VGV4dFwiOiBcImlkZWFzIGZvciBtYXJrZXRpbmcgY2FtcGFpZ25cIiwgXCJzdWdnZXN0ZWRDYXRlZ29yeUlkc1wiOiBbXCJjYXRfbWFya2V0aW5nXCJdfVxuRXhhbXBsZSAzIChvbmx5IHJlZmluZWQgcXVlcnkpOiB7XCJyZWZpbmVkUXVlcnlUZXh0XCI6IFwiZ2VuZXJhbCBwcm9qZWN0IHVwZGF0ZXNcIn1gO1xuXG4gIC8vIERlZmF1bHQgcmVzdWx0IGluIGNhc2Ugb2YgZXJyb3JzXG4gIGNvbnN0IGRlZmF1bHRSZXN1bHQ6IEFJUXVlcnlFbmhhbmNlbWVudFJlc3VsdCA9IHtcbiAgICByZWZpbmVkUXVlcnlUZXh0OiB1c2VyUXVlcnksIC8vIEZhbGxiYWNrIHRvIHRoZSBvcmlnaW5hbCBxdWVyeVxuICAgIHN1Z2dlc3RlZENhdGVnb3J5SWRzOiBbXSxcbiAgICBpZGVudGlmaWVkRGF0ZVJhbmdlOiB1bmRlZmluZWQsXG4gIH07XG5cbiAgbGV0IGxsbVJlc3BvbnNlU3RyaW5nOiBzdHJpbmcgfCBudWxsID0gbnVsbDtcbiAgdHJ5IHtcbiAgICAvLyBGb3JjaW5nIEpTT04gb3V0cHV0IHdpdGggY29tcGF0aWJsZSBtb2RlbHM6XG4gICAgLy8gY29uc3Qgb3BlbmFpID0gbmV3IE9wZW5BSSh7IGFwaUtleTogb3BlbkFJQXBpS2V5IH0pO1xuICAgIC8vIGNvbnN0IGNvbXBsZXRpb24gPSBhd2FpdCBvcGVuYWkuY2hhdC5jb21wbGV0aW9ucy5jcmVhdGUoe1xuICAgIC8vICAgbW9kZWw6IERFRkFVTFRfT1BFTkFJX01PREVMLCAvLyBFbnN1cmUgdGhpcyBtb2RlbCBzdXBwb3J0cyBKU09OIG1vZGVcbiAgICAvLyAgIG1lc3NhZ2VzOiBbXG4gICAgLy8gICAgIHsgcm9sZTogJ3N5c3RlbScsIGNvbnRlbnQ6IHN5c3RlbU1lc3NhZ2UgfSxcbiAgICAvLyAgICAgeyByb2xlOiAndXNlcicsIGNvbnRlbnQ6IHVzZXJQcm9tcHQgfSxcbiAgICAvLyAgIF0sXG4gICAgLy8gICByZXNwb25zZV9mb3JtYXQ6IHsgdHlwZTogXCJqc29uX29iamVjdFwiIH0sXG4gICAgLy8gfSk7XG4gICAgLy8gbGxtUmVzcG9uc2VTdHJpbmcgPSBjb21wbGV0aW9uLmNob2ljZXNbMF0/Lm1lc3NhZ2U/LmNvbnRlbnQgfHwgbnVsbDtcbiAgICAvLyBVc2luZyBleGlzdGluZyBjYWxsTExNIHdoaWNoIGRvZXNuJ3QgZXhwbGljaXRseSBhc2sgZm9yIEpTT04gb2JqZWN0IGZvcm1hdCBpbiB0aGUgQVBJIGNhbGwgaXRzZWxmLFxuICAgIC8vIHJlbGllcyBvbiBwcm9tcHQgZW5naW5lZXJpbmcgZm9yIHRoZSBMTE0gdG8gcmV0dXJuIEpTT04uXG4gICAgbGxtUmVzcG9uc2VTdHJpbmcgPSBhd2FpdCBjYWxsTExNKHVzZXJQcm9tcHQsIHN5c3RlbU1lc3NhZ2UsIG9wZW5BSUFwaUtleSk7XG5cbiAgICBpZiAoIWxsbVJlc3BvbnNlU3RyaW5nKSB7XG4gICAgICBjb25zb2xlLmVycm9yKCdBSVF1ZXJ5RW5oYW5jZXI6IExMTSByZXR1cm5lZCBudWxsIG9yIGVtcHR5IHJlc3BvbnNlLicpO1xuICAgICAgcmV0dXJuIGRlZmF1bHRSZXN1bHQ7XG4gICAgfVxuXG4gICAgLy8gQXR0ZW1wdCB0byBwYXJzZSB0aGUgSlNPTiByZXNwb25zZS4gTExNIG1pZ2h0IHJldHVybiBtYXJrZG93biBgYGBqc29uIC4uLiBgYGBcbiAgICBjb25zdCBqc29uTWF0Y2ggPSBsbG1SZXNwb25zZVN0cmluZy5tYXRjaCgvYGBganNvblxcbihbXFxzXFxTXSo/KVxcbmBgYC8pO1xuICAgIGxldCBwYXJzZWRKc29uO1xuICAgIGlmIChqc29uTWF0Y2ggJiYganNvbk1hdGNoWzFdKSB7XG4gICAgICBwYXJzZWRKc29uID0gSlNPTi5wYXJzZShqc29uTWF0Y2hbMV0pO1xuICAgIH0gZWxzZSB7XG4gICAgICAvLyBBc3N1bWUgdGhlIHJlc3BvbnNlIGlzIGRpcmVjdGx5IEpTT04gb3IgYXR0ZW1wdCBwYXJzaW5nIGRpcmVjdGx5XG4gICAgICAvLyBUaGlzIGlzIG1vcmUgcmlza3kgaWYgdGhlIExMTSBkb2Vzbid0IHN0cmljdGx5IGFkaGVyZSB0byBKU09OIG91dHB1dCB3aXRob3V0IGBgYFxuICAgICAgdHJ5IHtcbiAgICAgICAgcGFyc2VkSnNvbiA9IEpTT04ucGFyc2UobGxtUmVzcG9uc2VTdHJpbmcpO1xuICAgICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICAgICdBSVF1ZXJ5RW5oYW5jZXI6IEZhaWxlZCB0byBwYXJzZSBMTE0gcmVzcG9uc2UgYXMgZGlyZWN0IEpTT04uJyxcbiAgICAgICAgICBlLm1lc3NhZ2VcbiAgICAgICAgKTtcbiAgICAgICAgY29uc29sZS5lcnJvcignQUlRdWVyeUVuaGFuY2VyOiBSYXcgTExNIHJlc3BvbnNlOicsIGxsbVJlc3BvbnNlU3RyaW5nKTtcbiAgICAgICAgcmV0dXJuIGRlZmF1bHRSZXN1bHQ7XG4gICAgICB9XG4gICAgfVxuXG4gICAgLy8gVmFsaWRhdGUgdGhlIHN0cnVjdHVyZVxuICAgIGlmIChcbiAgICAgIHR5cGVvZiBwYXJzZWRKc29uLnJlZmluZWRRdWVyeVRleHQgIT09ICdzdHJpbmcnIHx8XG4gICAgICBwYXJzZWRKc29uLnJlZmluZWRRdWVyeVRleHQudHJpbSgpID09PSAnJ1xuICAgICkge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgJ0FJUXVlcnlFbmhhbmNlcjogVmFsaWRhdGlvbiBmYWlsZWQgLSByZWZpbmVkUXVlcnlUZXh0IGlzIG1pc3Npbmcgb3IgZW1wdHkuJyxcbiAgICAgICAgcGFyc2VkSnNvblxuICAgICAgKTtcbiAgICAgIC8vIEtlZXAgb3JpZ2luYWwgcXVlcnkgdGV4dCBpZiByZWZpbmVkIG9uZSBpcyBpbnZhbGlkXG4gICAgICBwYXJzZWRKc29uLnJlZmluZWRRdWVyeVRleHQgPSB1c2VyUXVlcnk7XG4gICAgfVxuXG4gICAgaWYgKFxuICAgICAgcGFyc2VkSnNvbi5zdWdnZXN0ZWRDYXRlZ29yeUlkcyAmJlxuICAgICAgIUFycmF5LmlzQXJyYXkocGFyc2VkSnNvbi5zdWdnZXN0ZWRDYXRlZ29yeUlkcylcbiAgICApIHtcbiAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgJ0FJUXVlcnlFbmhhbmNlcjogc3VnZ2VzdGVkQ2F0ZWdvcnlJZHMgaXMgbm90IGFuIGFycmF5LCBkZWZhdWx0aW5nIHRvIGVtcHR5LicsXG4gICAgICAgIHBhcnNlZEpzb25cbiAgICAgICk7XG4gICAgICBwYXJzZWRKc29uLnN1Z2dlc3RlZENhdGVnb3J5SWRzID0gW107XG4gICAgfSBlbHNlIGlmIChwYXJzZWRKc29uLnN1Z2dlc3RlZENhdGVnb3J5SWRzKSB7XG4gICAgICBwYXJzZWRKc29uLnN1Z2dlc3RlZENhdGVnb3J5SWRzID0gcGFyc2VkSnNvbi5zdWdnZXN0ZWRDYXRlZ29yeUlkcy5maWx0ZXIoXG4gICAgICAgIChpZCkgPT4gdHlwZW9mIGlkID09PSAnc3RyaW5nJ1xuICAgICAgKTtcbiAgICB9XG5cbiAgICBpZiAocGFyc2VkSnNvbi5pZGVudGlmaWVkRGF0ZVJhbmdlKSB7XG4gICAgICBpZiAoXG4gICAgICAgIHR5cGVvZiBwYXJzZWRKc29uLmlkZW50aWZpZWREYXRlUmFuZ2UgIT09ICdvYmplY3QnIHx8XG4gICAgICAgICFwYXJzZWRKc29uLmlkZW50aWZpZWREYXRlUmFuZ2Uuc3RhcnQgfHxcbiAgICAgICAgdHlwZW9mIHBhcnNlZEpzb24uaWRlbnRpZmllZERhdGVSYW5nZS5zdGFydCAhPT0gJ3N0cmluZycgfHxcbiAgICAgICAgIXBhcnNlZEpzb24uaWRlbnRpZmllZERhdGVSYW5nZS5lbmQgfHxcbiAgICAgICAgdHlwZW9mIHBhcnNlZEpzb24uaWRlbnRpZmllZERhdGVSYW5nZS5lbmQgIT09ICdzdHJpbmcnXG4gICAgICApIHtcbiAgICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAgICdBSVF1ZXJ5RW5oYW5jZXI6IGlkZW50aWZpZWREYXRlUmFuZ2UgaXMgaW52YWxpZCwgcmVtb3ZpbmcuJyxcbiAgICAgICAgICBwYXJzZWRKc29uXG4gICAgICAgICk7XG4gICAgICAgIGRlbGV0ZSBwYXJzZWRKc29uLmlkZW50aWZpZWREYXRlUmFuZ2U7XG4gICAgICB9XG4gICAgfVxuXG4gICAgcmV0dXJuIHtcbiAgICAgIHJlZmluZWRRdWVyeVRleHQ6IHBhcnNlZEpzb24ucmVmaW5lZFF1ZXJ5VGV4dCxcbiAgICAgIHN1Z2dlc3RlZENhdGVnb3J5SWRzOiBwYXJzZWRKc29uLnN1Z2dlc3RlZENhdGVnb3J5SWRzIHx8IFtdLFxuICAgICAgaWRlbnRpZmllZERhdGVSYW5nZTogcGFyc2VkSnNvbi5pZGVudGlmaWVkRGF0ZVJhbmdlLFxuICAgIH07XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgY29uc29sZS5lcnJvcihcbiAgICAgICdBSVF1ZXJ5RW5oYW5jZXI6IEVycm9yIHByb2Nlc3NpbmcgcXVlcnkgd2l0aCBBSSBvciBwYXJzaW5nIExMTSByZXNwb25zZTonLFxuICAgICAgZXJyb3JcbiAgICApO1xuICAgIGlmIChsbG1SZXNwb25zZVN0cmluZykge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgJ0FJUXVlcnlFbmhhbmNlcjogUmF3IExMTSByZXNwb25zZSBzdHJpbmcgb24gZXJyb3I6JyxcbiAgICAgICAgbGxtUmVzcG9uc2VTdHJpbmdcbiAgICAgICk7XG4gICAgfVxuICAgIHJldHVybiBkZWZhdWx0UmVzdWx0O1xuICB9XG59XG4iXX0=