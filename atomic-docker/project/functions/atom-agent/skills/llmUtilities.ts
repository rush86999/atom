// In atomic-docker/project/functions/atom-agent/skills/llmUtilities.ts
import { ExtractedFollowUpItems } from '../../types';

/**
 * Analyzes a given text block using an LLM to extract potential follow-up items.
 * This is a conceptual function. Actual implementation would involve API calls
 * to an LLM service (e.g., OpenAI, or a self-hosted model via Python backend).
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
  console.log(`[llmUtilities.analyzeTextForFollowUps] Analyzing text for context: ${contextDescription || 'General Text'}`);

  // 1. Construct the Prompt for the LLM
  let prompt = `You are an AI assistant helping to identify follow-up items from text.
Analyze the following document${contextDescription ? ` regarding "${contextDescription}"` : ''}:

"""
${textContent}
"""

Based *only* on the information within the document provided:
1. Identify distinct actionable items or tasks that need to be done. For each action item, if an assignee is mentioned or clearly implied, note the assignee.
2. Identify key decisions that were explicitly made.
3. Identify open questions, unresolved issues, or topics that were marked for future discussion.

Provide your response as a JSON object with the following structure:
{
  "action_items": [
    { "description": "Complete summary of action item 1...", "assignee": "Name or 'unassigned'" },
    { "description": "Summary of action item 2...", "assignee": "Name or 'unassigned'" }
  ],
  "decisions": [
    { "description": "Summary of decision 1..." },
    { "description": "Summary of decision 2..." }
  ],
  "questions": [
    { "description": "Summary of question 1..." },
    { "description": "Summary of question 2..." }
  ]
}

Ensure each description is concise and directly extracted or summarized from the text.
If no items are found for a category, return an empty array for that category.
Do not invent information not present in the text.
`;

  try {
    // 2. Make the LLM API Call (Conceptual - replace with actual implementation)
    console.log("[llmUtilities.analyzeTextForFollowUps] Sending prompt to LLM (conceptual)...");
    // Example: const llmApiResponse = await openai.chat.completions.create({ messages: [{ role: "user", content: prompt }], model: "gpt-3.5-turbo" });
    // const rawResponse = llmApiResponse.choices[0].message.content;

    // --- Start of MOCK LLM RESPONSE (for conceptual development) ---
    let mockJsonResponse: string;
    if (textContent.toLowerCase().includes("action item: review budget") && textContent.toLowerCase().includes("decision: approve new vendor")) {
        mockJsonResponse = JSON.stringify({
            action_items: [{ description: "Review budget proposal by Friday", assignee: "John Doe" }, { description: "Send meeting minutes to team", assignee: "Sarah Smith" }],
            decisions: [{ description: "Approved new vendor for Q3" }, { description: "Postponed website redesign project" }],
            questions: [{ description: "What is the timeline for Phase 2?" }, {description: "Who will follow up with marketing on campaign results?"}]
        });
    } else if (textContent.toLowerCase().includes("project plan for alpha")) { // More specific mock trigger
        mockJsonResponse = JSON.stringify({
            action_items: [{ description: "Develop feature X for Alpha", assignee: "Alice" }, {"description": "Setup testing environment for Alpha", "assignee": "Bob"}],
            decisions: [{ description: "Prioritize feature Y for Alpha's next sprint" }],
            questions: [{"description": "What is the final deadline for Alpha project?"}]
        });
    } else {
         mockJsonResponse = JSON.stringify({
            action_items: [],
            decisions: [],
            questions: []
        });
    }
    console.log("[llmUtilities.analyzeTextForFollowUps] Mock LLM raw response:", mockJsonResponse);
    // --- End of MOCK LLM RESPONSE ---

    // 3. Parse the LLM Response
    const parsedResponse = JSON.parse(mockJsonResponse) as ExtractedFollowUpItems;

    if (!parsedResponse || typeof parsedResponse !== 'object' ||
        !Array.isArray(parsedResponse.action_items) ||
        !Array.isArray(parsedResponse.decisions) ||
        !Array.isArray(parsedResponse.questions)) {
      console.error("[llmUtilities.analyzeTextForFollowUps] LLM response was not in the expected JSON format.");
      return {
        extractedItems: { action_items: [], decisions: [], questions: [] },
        error: "LLM response format error."
      };
    }

    console.log("[llmUtilities.analyzeTextForFollowUps] Successfully parsed LLM response.");
    return { extractedItems: parsedResponse };

  } catch (error: any) {
    console.error("[llmUtilities.analyzeTextForFollowUps] Error calling or parsing LLM response:", error.message, error.stack);
    return {
      extractedItems: { action_items: [], decisions: [], questions: [] },
      error: `LLM interaction failed: ${error.message}`
    };
  }
}
