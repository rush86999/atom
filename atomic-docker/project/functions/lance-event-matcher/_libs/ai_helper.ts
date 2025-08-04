import OpenAI from 'openai';
import {
  EventRecord,
  CategoryType,
  AIProcessedEvent,
  AIQueryEnhancementResult,
} from './types'; // Added AIQueryEnhancementResult
import { DEFAULT_OPENAI_MODEL } from './constants';

/**
 * Calls the OpenAI LLM with a given prompt.
 * @param prompt The complete prompt string (including system and user messages).
 * @param apiKey OpenAI API key.
 * @param model The OpenAI model to use.
 * @returns A promise that resolves to the AI's content string.
 */
export async function callLLM(
  prompt: string, // In this setup, prompt is the user message, system message is separate
  systemPrompt: string,
  apiKey: string,
  model: string = DEFAULT_OPENAI_MODEL
): Promise<string | null> {
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
  } catch (error) {
    console.error('Error calling OpenAI LLM:', error);
    // Consider more specific error handling or re-throwing
    if (error.response) {
      console.error(
        'OpenAI API Error Details:',
        error.response.status,
        error.response.data
      );
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
export async function callAIEventProcessor(
  events: EventRecord[],
  userQuery: string,
  userCategories: CategoryType[],
  openAIApiKey: string,
  userMessageHistory?: any[] // Define a more specific type if available
): Promise<AIProcessedEvent[]> {
  const systemMessage = `You are an intelligent event processing assistant. Your task is to analyze a list of events based on a user's search query and a list of available event categories. Assign the single most relevant category to each event and provide a relevance score from 0.0 to 1.0. Only return events that you determine to be relevant to the user's query. If no events are relevant, return an empty list.`;

  let userMessage = `User Query: ${userQuery}\n\n`;
  userMessage += 'Available Categories:\n';
  userCategories.forEach((cat) => {
    userMessage += `ID: ${cat.id}, Name: ${cat.name}\n`;
  });
  userMessage += '\nEvents to Process:\n';
  events.forEach((event) => {
    // Assuming raw_event_text contains summary and potentially description
    const title =
      event.raw_event_text?.split(':')[0] || event.raw_event_text || 'No Title';
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
    const llmResponseString = await callLLM(
      userMessage,
      systemMessage,
      openAIApiKey
    );

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
    } else {
      // Assume the response is directly JSON or attempt parsing directly
      parsedResponse = JSON.parse(llmResponseString);
    }

    // Validate the parsed response structure
    if (!Array.isArray(parsedResponse)) {
      console.error('LLM response is not a JSON array:', parsedResponse);
      return [];
    }

    const validatedEvents: AIProcessedEvent[] = [];
    for (const item of parsedResponse) {
      if (
        item &&
        typeof item.eventId === 'string' &&
        typeof item.assignedCategoryId === 'string' &&
        typeof item.relevanceScore === 'number' &&
        item.relevanceScore >= 0.0 &&
        item.relevanceScore <= 1.0
      ) {
        validatedEvents.push(item as AIProcessedEvent);
      } else {
        console.warn('Invalid item in LLM response, skipping:', item);
      }
    }
    return validatedEvents;
  } catch (error) {
    console.error(
      'Error processing events with AI or parsing LLM response:',
      error
    );
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
export async function callAIQueryEnhancer(
  userQuery: string,
  userCategories: CategoryType[],
  openAIApiKey: string,
  userMessageHistory?: any[] // Define a more specific type if available, e.g., { role: 'user' | 'assistant', content: string }[]
): Promise<AIQueryEnhancementResult> {
  const systemMessage = `You are an expert query understanding assistant. Your task is to refine a user's search query for an event retrieval system. Analyze the query, available categories, and optionally user message history. Your goal is to provide a refined query text that captures the core intent, suggest relevant category IDs if applicable, and identify any specific date ranges mentioned or implied. Ensure your output is a valid JSON object.`;

  let userPrompt = `Original User Query: ${userQuery}\n\n`;

  if (userMessageHistory && userMessageHistory.length > 0) {
    const historyStr = userMessageHistory
      .map(
        (msg) => `${msg.role === 'user' ? 'User' : 'Assistant'}: ${msg.content}`
      ) // Basic formatting
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
  const defaultResult: AIQueryEnhancementResult = {
    refinedQueryText: userQuery, // Fallback to the original query
    suggestedCategoryIds: [],
    identifiedDateRange: undefined,
  };

  let llmResponseString: string | null = null;
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
    } else {
      // Assume the response is directly JSON or attempt parsing directly
      // This is more risky if the LLM doesn't strictly adhere to JSON output without ```
      try {
        parsedJson = JSON.parse(llmResponseString);
      } catch (e) {
        console.error(
          'AIQueryEnhancer: Failed to parse LLM response as direct JSON.',
          e.message
        );
        console.error('AIQueryEnhancer: Raw LLM response:', llmResponseString);
        return defaultResult;
      }
    }

    // Validate the structure
    if (
      typeof parsedJson.refinedQueryText !== 'string' ||
      parsedJson.refinedQueryText.trim() === ''
    ) {
      console.error(
        'AIQueryEnhancer: Validation failed - refinedQueryText is missing or empty.',
        parsedJson
      );
      // Keep original query text if refined one is invalid
      parsedJson.refinedQueryText = userQuery;
    }

    if (
      parsedJson.suggestedCategoryIds &&
      !Array.isArray(parsedJson.suggestedCategoryIds)
    ) {
      console.warn(
        'AIQueryEnhancer: suggestedCategoryIds is not an array, defaulting to empty.',
        parsedJson
      );
      parsedJson.suggestedCategoryIds = [];
    } else if (parsedJson.suggestedCategoryIds) {
      parsedJson.suggestedCategoryIds = parsedJson.suggestedCategoryIds.filter(
        (id) => typeof id === 'string'
      );
    }

    if (parsedJson.identifiedDateRange) {
      if (
        typeof parsedJson.identifiedDateRange !== 'object' ||
        !parsedJson.identifiedDateRange.start ||
        typeof parsedJson.identifiedDateRange.start !== 'string' ||
        !parsedJson.identifiedDateRange.end ||
        typeof parsedJson.identifiedDateRange.end !== 'string'
      ) {
        console.warn(
          'AIQueryEnhancer: identifiedDateRange is invalid, removing.',
          parsedJson
        );
        delete parsedJson.identifiedDateRange;
      }
    }

    return {
      refinedQueryText: parsedJson.refinedQueryText,
      suggestedCategoryIds: parsedJson.suggestedCategoryIds || [],
      identifiedDateRange: parsedJson.identifiedDateRange,
    };
  } catch (error) {
    console.error(
      'AIQueryEnhancer: Error processing query with AI or parsing LLM response:',
      error
    );
    if (llmResponseString) {
      console.error(
        'AIQueryEnhancer: Raw LLM response string on error:',
        llmResponseString
      );
    }
    return defaultResult;
  }
}
