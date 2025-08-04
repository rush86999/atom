import { EventRecord, CategoryType, AIProcessedEvent, AIQueryEnhancementResult } from './types';
/**
 * Calls the OpenAI LLM with a given prompt.
 * @param prompt The complete prompt string (including system and user messages).
 * @param apiKey OpenAI API key.
 * @param model The OpenAI model to use.
 * @returns A promise that resolves to the AI's content string.
 */
export declare function callLLM(prompt: string, // In this setup, prompt is the user message, system message is separate
systemPrompt: string, apiKey: string, model?: string): Promise<string | null>;
/**
 * Processes events using an AI model to assign categories and relevance scores.
 * @param events Array of event records from LanceDB.
 * @param userQuery The original user search query.
 * @param userCategories List of available user categories.
 * @param openAIApiKey OpenAI API key.
 * @param userMessageHistory Optional array of previous user messages for context.
 * @returns A promise that resolves to an array of AIProcessedEvent objects.
 */
export declare function callAIEventProcessor(events: EventRecord[], userQuery: string, userCategories: CategoryType[], openAIApiKey: string, userMessageHistory?: any[]): Promise<AIProcessedEvent[]>;
/**
 * Enhances a user's search query using an AI model.
 * @param userQuery The original user search query.
 * @param userCategories List of available user categories.
 * @param openAIApiKey OpenAI API key.
 * @param userMessageHistory Optional array of previous user messages for context.
 * @returns A promise that resolves to an AIQueryEnhancementResult object.
 */
export declare function callAIQueryEnhancer(userQuery: string, userCategories: CategoryType[], openAIApiKey: string, userMessageHistory?: any[]): Promise<AIQueryEnhancementResult>;
