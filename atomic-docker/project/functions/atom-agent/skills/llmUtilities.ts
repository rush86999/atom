// In atomic-docker/project/functions/atom-agent/skills/llmUtilities.ts
import OpenAI from 'openai';
import { ExtractedFollowUpItems } from '../../types';

const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
let openai: OpenAI | null = null;

if (OPENAI_API_KEY) {
  openai = new OpenAI({ apiKey: OPENAI_API_KEY });
  console.log("[llmUtilities] OpenAI client initialized.");
} else {
  console.warn("[llmUtilities] OPENAI_API_KEY not found in environment variables. LLM calls will be skipped.");
}

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
export async function analyzeTextForFollowUps(
  textContent: string,
  contextDescription?: string
): Promise<{ extractedItems: ExtractedFollowUpItems; error?: string }> {
  console.log(`[llmUtilities.analyzeTextForFollowUps] Analyzing text for context: ${contextDescription || 'General Text'}. Text length: ${textContent.length}`);

  if (!openai) {
    console.warn("[llmUtilities.analyzeTextForFollowUps] OpenAI client not initialized (API key missing). Skipping LLM call.");
    return {
      extractedItems: { action_items: [], decisions: [], questions: [] },
      error: "OpenAI API key not configured. LLM analysis skipped."
    };
  }

  if (textContent.trim().length < 50) { // Avoid sending very short texts to LLM
    console.log("[llmUtilities.analyzeTextForFollowUps] Text content is too short. Skipping LLM call.");
    return {
        extractedItems: { action_items: [], decisions: [], questions: [] },
        error: "Text content too short for meaningful analysis."
      };
  }

  // Construct the System and User Prompts for the LLM
  const systemPrompt = `You are an AI assistant specialized in identifying follow-up items from text.
Your goal is to extract:
1. Distinct actionable items or tasks. If an assignee is mentioned or clearly implied, note the assignee.
2. Key decisions that were explicitly made.
3. Open questions, unresolved issues, or topics marked for future discussion.

Provide your response strictly as a JSON object with the following structure:
{
  "action_items": [
    { "description": "Complete summary of action item 1...", "assignee": "Name or 'unassigned'" }
  ],
  "decisions": [
    { "description": "Summary of decision 1..." }
  ],
  "questions": [
    { "description": "Summary of question 1..." }
  ]
}
Ensure each description is concise and directly extracted or summarized from the provided text.
If no items are found for a category, return an empty array for that category.
Do not invent information not present in the text. Stick strictly to the document content.`;

  const userPrompt = `Analyze the following document${contextDescription ? ` regarding "${contextDescription}"` : ''}:

"""
${textContent}
"""

Based *only* on the information within the document provided, identify action items, decisions, and questions according to the JSON structure I specified in my system instructions.`;

  try {
    console.log("[llmUtilities.analyzeTextForFollowUps] Sending prompt to OpenAI API...");

    const completion = await openai.chat.completions.create({
      model: "gpt-3.5-turbo-1106", // Using a model that supports JSON mode well
      response_format: { type: "json_object" },
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: userPrompt }
      ],
      temperature: 0.2,
      max_tokens: 1500, // Increased max_tokens for potentially larger JSON responses
    });

    const rawResponse = completion.choices[0]?.message?.content;

    if (!rawResponse) {
      console.error("[llmUtilities.analyzeTextForFollowUps] LLM response content is null or empty.");
      return {
        extractedItems: { action_items: [], decisions: [], questions: [] },
        error: "LLM returned empty or null response content."
      };
    }

    console.log("[llmUtilities.analyzeTextForFollowUps] LLM raw response received (first 500 chars):", rawResponse.substring(0, 500));

    // Parse the LLM Response
    const parsedResponse = JSON.parse(rawResponse) as ExtractedFollowUpItems;

    if (!parsedResponse || typeof parsedResponse !== 'object' ||
        !Array.isArray(parsedResponse.action_items) ||
        !Array.isArray(parsedResponse.decisions) ||
        !Array.isArray(parsedResponse.questions)) {
      console.error("[llmUtilities.analyzeTextForFollowUps] LLM response was not in the expected JSON format after parsing.");
      return {
        extractedItems: { action_items: [], decisions: [], questions: [] },
        error: "LLM response format error after parsing."
      };
    }

    console.log("[llmUtilities.analyzeTextForFollowUps] Successfully parsed LLM response.");
    return { extractedItems: parsedResponse };

  } catch (error: any) {
    console.error("[llmUtilities.analyzeTextForFollowUps] Error during LLM interaction or parsing:", error.message, error.stack);
    let errorMessage = `LLM interaction failed: ${error.message}`;
    if (error.code) { // Specific OpenAI error codes
        errorMessage += ` (Code: ${error.code})`;
    }
    return {
      extractedItems: { action_items: [], decisions: [], questions: [] },
      error: errorMessage
    };
  }
}
