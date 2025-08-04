import { ExtractedFollowUpItems } from '../../types';
/**
 * Analyzes a given text block using an LLM to extract potential follow-up items.
 * This function will be updated to make real API calls to OpenAI.
 *
 * @param textContent The text to analyze (e.g., meeting notes, project document).
 * @param contextDescription Optional description of the context (e.g., "Meeting notes for Project X review")
 *                           to help the LLM understand the source.
 * @returns A promise that resolves to an object containing arrays of
 *          action items, decisions, and questions.
 */
export declare function analyzeTextForFollowUps(textContent: string, contextDescription?: string): Promise<{
    extractedItems: ExtractedFollowUpItems;
    error?: string;
}>;
