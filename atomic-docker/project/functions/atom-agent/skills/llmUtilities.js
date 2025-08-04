// In atomic-docker/project/functions/atom-agent/skills/llmUtilities.ts
import OpenAI from 'openai';
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
let openai = null;
if (OPENAI_API_KEY) {
    openai = new OpenAI({ apiKey: OPENAI_API_KEY });
    console.log('[llmUtilities] OpenAI client initialized.');
}
else {
    console.warn('[llmUtilities] OPENAI_API_KEY not found in environment variables. LLM calls will be skipped.');
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
export async function analyzeTextForFollowUps(textContent, contextDescription) {
    console.log(`[llmUtilities.analyzeTextForFollowUps] Analyzing text for context: ${contextDescription || 'General Text'}. Text length: ${textContent.length}`);
    if (!openai) {
        console.warn('[llmUtilities.analyzeTextForFollowUps] OpenAI client not initialized (API key missing). Skipping LLM call.');
        return {
            extractedItems: { action_items: [], decisions: [], questions: [] },
            error: 'OpenAI API key not configured. LLM analysis skipped.',
        };
    }
    if (textContent.trim().length < 50) {
        // Avoid sending very short texts to LLM
        console.log('[llmUtilities.analyzeTextForFollowUps] Text content is too short. Skipping LLM call.');
        return {
            extractedItems: { action_items: [], decisions: [], questions: [] },
            error: 'Text content too short for meaningful analysis.',
        };
    }
    // Construct the System and User Prompts for the LLM
    // This prompt is crucial for the LLM's performance and will likely require
    // iterative testing and refinement with real-world data to achieve optimal results.
    // Key aspects:
    // - Clear definition of the AI's role and goal.
    // - Explicit instruction for JSON output with a defined schema.
    // - Constraints like "based only on the information within the document" and "Do not invent".
    // - Guidance on handling empty categories (return empty arrays).
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
        console.log('[llmUtilities.analyzeTextForFollowUps] Sending prompt to OpenAI API...');
        const completion = await openai.chat.completions.create({
            model: 'gpt-3.5-turbo-1106', // Using a model that supports JSON mode well
            response_format: { type: 'json_object' },
            messages: [
                { role: 'system', content: systemPrompt },
                { role: 'user', content: userPrompt },
            ],
            temperature: 0.2,
            max_tokens: 1500, // Increased max_tokens for potentially larger JSON responses
        });
        const rawResponse = completion.choices[0]?.message?.content;
        if (!rawResponse) {
            console.error('[llmUtilities.analyzeTextForFollowUps] LLM response content is null or empty.');
            return {
                extractedItems: { action_items: [], decisions: [], questions: [] },
                error: 'LLM returned empty or null response content.',
            };
        }
        console.log('[llmUtilities.analyzeTextForFollowUps] LLM raw response received (first 500 chars):', rawResponse.substring(0, 500));
        // Parse the LLM Response
        const parsedResponse = JSON.parse(rawResponse);
        if (!parsedResponse ||
            typeof parsedResponse !== 'object' ||
            !Array.isArray(parsedResponse.action_items) ||
            !Array.isArray(parsedResponse.decisions) ||
            !Array.isArray(parsedResponse.questions)) {
            console.error('[llmUtilities.analyzeTextForFollowUps] LLM response was not in the expected JSON format after parsing.');
            return {
                extractedItems: { action_items: [], decisions: [], questions: [] },
                error: 'LLM response format error after parsing.',
            };
        }
        console.log('[llmUtilities.analyzeTextForFollowUps] Successfully parsed LLM response.');
        return { extractedItems: parsedResponse };
    }
    catch (error) {
        console.error('[llmUtilities.analyzeTextForFollowUps] Error during LLM interaction or parsing:', error.message, error.stack);
        let errorMessage = `LLM interaction failed: ${error.message}`;
        if (error.code) {
            // Specific OpenAI error codes
            errorMessage += ` (Code: ${error.code})`;
        }
        return {
            extractedItems: { action_items: [], decisions: [], questions: [] },
            error: errorMessage,
        };
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGxtVXRpbGl0aWVzLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsibGxtVXRpbGl0aWVzLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLHVFQUF1RTtBQUN2RSxPQUFPLE1BQU0sTUFBTSxRQUFRLENBQUM7QUFHNUIsTUFBTSxjQUFjLEdBQUcsT0FBTyxDQUFDLEdBQUcsQ0FBQyxjQUFjLENBQUM7QUFDbEQsSUFBSSxNQUFNLEdBQWtCLElBQUksQ0FBQztBQUVqQyxJQUFJLGNBQWMsRUFBRSxDQUFDO0lBQ25CLE1BQU0sR0FBRyxJQUFJLE1BQU0sQ0FBQyxFQUFFLE1BQU0sRUFBRSxjQUFjLEVBQUUsQ0FBQyxDQUFDO0lBQ2hELE9BQU8sQ0FBQyxHQUFHLENBQUMsMkNBQTJDLENBQUMsQ0FBQztBQUMzRCxDQUFDO0tBQU0sQ0FBQztJQUNOLE9BQU8sQ0FBQyxJQUFJLENBQ1YsOEZBQThGLENBQy9GLENBQUM7QUFDSixDQUFDO0FBRUQ7Ozs7Ozs7OztHQVNHO0FBQ0gsTUFBTSxDQUFDLEtBQUssVUFBVSx1QkFBdUIsQ0FDM0MsV0FBbUIsRUFDbkIsa0JBQTJCO0lBRTNCLE9BQU8sQ0FBQyxHQUFHLENBQ1Qsc0VBQXNFLGtCQUFrQixJQUFJLGNBQWMsa0JBQWtCLFdBQVcsQ0FBQyxNQUFNLEVBQUUsQ0FDakosQ0FBQztJQUVGLElBQUksQ0FBQyxNQUFNLEVBQUUsQ0FBQztRQUNaLE9BQU8sQ0FBQyxJQUFJLENBQ1YsNEdBQTRHLENBQzdHLENBQUM7UUFDRixPQUFPO1lBQ0wsY0FBYyxFQUFFLEVBQUUsWUFBWSxFQUFFLEVBQUUsRUFBRSxTQUFTLEVBQUUsRUFBRSxFQUFFLFNBQVMsRUFBRSxFQUFFLEVBQUU7WUFDbEUsS0FBSyxFQUFFLHNEQUFzRDtTQUM5RCxDQUFDO0lBQ0osQ0FBQztJQUVELElBQUksV0FBVyxDQUFDLElBQUksRUFBRSxDQUFDLE1BQU0sR0FBRyxFQUFFLEVBQUUsQ0FBQztRQUNuQyx3Q0FBd0M7UUFDeEMsT0FBTyxDQUFD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WCxpRkFBaUYsRUFDakYsS0FBSyxDQUFDLE9BQU8sRUFDYixLQUFLLENBQUMsS0FBSyxDQUNaLENBQUM7UUFDRixJQUFJLFlBQVksR0FBRywyQkFBMkIsS0FBSyxDQUFDLE9BQU8sRUFBRSxDQUFDO1FBQzlELElBQUksS0FBSyxDQUFDLElBQUksRUFBRSxDQUFDO1lBQ2YsOEJBQThCO1lBQzlCLFlBQVksSUFBSSxXQUFXLEtBQUssQ0FBQyxJQUFJLEdBQUcsQ0FBQztRQUMzQyxDQUFDO1FBQ0QsT0FBTztZQUNMLGNBQWMsRUFBRSxFQUFFLFlBQVksRUFBRSxFQUFFLEVBQUUsU0FBUyxFQUFFLEVBQUUsRUFBRSxTQUFTLEVBQUUsRUFBRSxFQUFFO1lBQ2xFLEtBQUssRUFBRSxZQUFZO1NBQ3BCLENBQUM7SUFDSixDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbIi8vIEluIGF0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvYXRvbS1hZ2VudC9za2lsbHMvbGxtVXRpbGl0aWVzLnRzXG5pbXBvcnQgT3BlbkFJIGZyb20gJ29wZW5haSc7XG5pbXBvcnQgeyBFeHRyYWN0ZWRGb2xsb3dVcEl0ZW1zIH0gZnJvbSAnLi4vLi4vdHlwZXMnO1xuXG5jb25zdCBPUEVOQUlfQVBJX0tFWSA9IHByb2Nlc3MuZW52Lk9QRU5BSV9BUElfS0VZO1xubGV0IG9wZW5haTogT3BlbkFJIHwgbnVsbCA9IG51bGw7XG5cbmlmIChPUEVOQUlfQVBJX0tFWSkge1xuICBvcGVuYWkgPSBuZXcgT3BlbkFJKHsgYXBpS2V5OiBPUEVOQUlfQVBJX0tFWSB9KTtcbiAgY29uc29sZS5sb2coJ1tsbG1VdGlsaXRpZXNdIE9wZW5BSSBjbGllbnQgaW5pdGlhbGl6ZWQuJyk7XG59IGVsc2Uge1xuICBjb25zb2xlLndhcm4oXG4gICAgJ1tsbG1VdGlsaXRpZXNdIE9QRU5BSV9BUElfS0VZIG5vdCBmb3VuZCBpbiBlbnZpcm9ubWVudCB2YXJpYWJsZXMuIExMTSBjYWxscyB3aWxsIGJlIHNraXBwZWQuJ1xuICApO1xufVxuXG4vKipcbiAqIEFuYWx5emVzIGEgZ2l2ZW4gdGV4dCBibG9jayB1c2luZyBhbiBMTE0gdG8gZXh0cmFjdCBwb3RlbnRpYWwgZm9sbG93LXVwIGl0ZW1zLlxuICogVGhpcyBmdW5jdGlvbiB3aWxsIGJlIHVwZGF0ZWQgdG8gbWFrZSByZWFsIEFQSSBjYWxscyB0byBPcGVuQUkuXG4gKlxuICogQHBhcmFtIHRleHRDb250ZW50IFRoZSB0ZXh0IHRvIGFuYWx5emUgKGUuZy4sIG1lZXRpbmcgbm90ZXMsIHByb2plY3QgZG9jdW1lbnQpLlxuICogQHBhcmFtIGNvbnRleHREZXNjcmlwdGlvbiBPcHRpb25hbCBkZXNjcmlwdGlvbiBvZiB0aGUgY29udGV4dCAoZS5nLiwgXCJNZWV0aW5nIG5vdGVzIGZvciBQcm9qZWN0IFggcmV2aWV3XCIpXG4gKiAgICAgICAgICAgICAgICAgICAgICAgICAgIHRvIGhlbHAgdGhlIExMTSB1bmRlcnN0YW5kIHRoZSBzb3VyY2UuXG4gKiBAcmV0dXJucyBBIHByb21pc2UgdGhhdCByZXNvbHZlcyB0byBhbiBvYmplY3QgY29udGFpbmluZyBhcnJheXMgb2ZcbiAqICAgICAgICAgIGFjdGlvbiBpdGVtcywgZGVjaXNpb25zLCBhbmQgcXVlc3Rpb25zLlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gYW5hbHl6ZVRleHRGb3JGb2xsb3dVcHMoXG4gIHRleHRDb250ZW50OiBzdHJpbmcsXG4gIGNvbnRleHREZXNjcmlwdGlvbj86IHN0cmluZ1xuKTogUHJvbWlzZTx7IGV4dHJhY3RlZEl0ZW1zOiBFeHRyYWN0ZWRGb2xsb3dVcEl0ZW1zOyBlcnJvcj86IHN0cmluZyB9PiB7XG4gIGNvbnNvbGUubG9nKFxuICAgIGBbbGxtVXRpbGl0aWVzLmFuYWx5emVUZXh0Rm9yRm9sbG93VXBzXSBBbmFseXppbmcgdGV4dCBmb3IgY29udGV4dDogJHtjb250ZXh0RGVzY3JpcHRpb24gfHwgJ0dlbmVyYWwgVGV4dCd9LiBUZXh0IGxlbmd0aDogJHt0ZXh0Q29udGVudC5sZW5ndGh9YFxuICApO1xuXG4gIGlmICghb3BlbmFpKSB7XG4gICAgY29uc29sZS53YXJuKFxuICAgICAgJ1tsbG1VdGlsaXRpZXMuYW5hbHl6ZVRleHRGb3JGb2xsb3dVcHNdIE9wZW5BSSBjbGllbnQgbm90IGluaXRpYWxpemVkIChBUEkga2V5IG1pc3NpbmcpLiBTa2lwcGluZyBMTE0gY2FsbC4nXG4gICAgKTtcbiAgICByZXR1cm4ge1xuICAgICAgZXh0cmFjdGVkSXRlbXM6IHsgYWN0aW9uX2l0ZW1zOiBbXSwgZGVjaXNpb25zOiBbXSwgcXVlc3Rpb25zOiBbXSB9LFxuICAgICAgZXJyb3I6ICdPcGVuQUkgQVBJIGtleSBub3QgY29uZmlndXJlZC4gTExNIGFuYWx5c2lzIHNraXBwZWQuJyxcbiAgICB9O1xuICB9XG5cbiAgaWYgKHRleHRDb250ZW50LnRyaW0oKS5sZW5ndGggPCA1MCkge1xuICAgIC8vIEF2b2lkIHNlbmRpbmcgdmVyeSBzaG9ydCB0ZXh0cyB0byBMTE1cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgICdbbGxtVXRpbGl0aWVzLmFuYWx5emVUZXh0Rm9yRm9sbG93VXBzXSBUZXh0IGNvbnRlbnQgaXMgdG9vIHNob3J0LiBTa2lwcGluZyBMTE0gY2FsbC4nXG4gICAgKTtcbiAgICByZXR1cm4ge1xuICAgICAgZXh0cmFjdGVkSXRlbXM6IHsgYWN0aW9uX2l0ZW1zOiBbXSwgZGVjaXNpb25zOiBbXSwgcXVlc3Rpb25zOiBbXSB9LFxuICAgICAgZXJyb3I6ICdUZXh0IGNvbnRlbnQgdG9vIHNob3J0IGZvciBtZWFuaW5nZnVsIGFuYWx5c2lzLicsXG4gICAgfTtcbiAgfVxuXG4gIC8vIENvbnN0cnVjdCB0aGUgU3lzdGVtIGFuZCBVc2VyIFByb21wdHMgZm9yIHRoZSBMTE1cbiAgLy8gVGhpcyBwcm9tcHQgaXMgY3J1Y2lhbCBmb3IgdGhlIExMTSdzIHBlcmZvcm1hbmNlIGFuZCB3aWxsIGxpa2VseSByZXF1aXJlXG4gIC8vIGl0ZXJhdGl2ZSB0ZXN0aW5nIGFuZCByZWZpbmVtZW50IHdpdGggcmVhbC13b3JsZCBkYXRhIHRvIGFjaGlldmUgb3B0aW1hbCByZXN1bHRzLlxuICAvLyBLZXkgYXNwZWN0czpcbiAgLy8gLSBDbGVhciBkZWZpbml0aW9uIG9mIHRoZSBBSSdzIHJvbGUgYW5kIGdvYWwuXG4gIC8vIC0gRXhwbGljaXQgaW5zdHJ1Y3Rpb24gZm9yIEpTT04gb3V0cHV0IHdpdGggYSBkZWZpbmVkIHNjaGVtYS5cbiAgLy8gLSBDb25zdHJhaW50cyBsaWtlIFwiYmFzZWQgb25seSBvbiB0aGUgaW5mb3JtYXRpb24gd2l0aGluIHRoZSBkb2N1bWVudFwiIGFuZCBcIkRvIG5vdCBpbnZlbnRcIi5cbiAgLy8gLSBHdWlkYW5jZSBvbiBoYW5kbGluZyBlbXB0eSBjYXRlZ29yaWVzIChyZXR1cm4gZW1wdHkgYXJyYXlzKS5cbiAgY29uc3Qgc3lzdGVtUHJvbXB0ID0gYFlvdSBhcmUgYW4gQUkgYXNzaXN0YW50IHNwZWNpYWxpemVkIGluIGlkZW50aWZ5aW5nIGZvbGxvdy11cCBpdGVtcyBmcm9tIHRleHQuXG5Zb3VyIGdvYWwgaXMgdG8gZXh0cmFjdDpcbjEuIERpc3RpbmN0IGFjdGlvbmFibGUgaXRlbXMgb3IgdGFza3MuIElmIGFuIGFzc2lnbmVlIGlzIG1lbnRpb25lZCBvciBjbGVhcmx5IGltcGxpZWQsIG5vdGUgdGhlIGFzc2lnbmVlLlxuMi4gS2V5IGRlY2lzaW9ucyB0aGF0IHdlcmUgZXhwbGljaXRseSBtYWRlLlxuMy4gT3BlbiBxdWVzdGlvbnMsIHVucmVzb2x2ZWQgaXNzdWVzLCBvciB0b3BpY3MgbWFya2VkIGZvciBmdXR1cmUgZGlzY3Vzc2lvbi5cblxuUHJvdmlkZSB5b3VyIHJlc3BvbnNlIHN0cmljdGx5IGFzIGEgSlNPTiBvYmplY3Qgd2l0aCB0aGUgZm9sbG93aW5nIHN0cnVjdHVyZTpcbntcbiAgXCJhY3Rpb25faXRlbXNcIjogW1xuICAgIHsgXCJkZXNjcmlwdGlvblwiOiBcIkNvbXBsZXRlIHN1bW1hcnkgb2YgYWN0aW9uIGl0ZW0gMS4uLlwiLCBcImFzc2lnbmVlXCI6IFwiTmFtZSBvciAndW5hc3NpZ25lZCdcIiB9XG4gIF0sXG4gIFwiZGVjaXNpb25zXCI6IFtcbiAgICB7IFwiZGVzY3JpcHRpb25cIjogXCJTdW1tYXJ5IG9mIGRlY2lzaW9uIDEuLi5cIiB9XG4gIF0sXG4gIFwicXVlc3Rpb25zXCI6IFtcbiAgICB7IFwiZGVzY3JpcHRpb25cIjogXCJTdW1tYXJ5IG9mIHF1ZXN0aW9uIDEuLi5cIiB9XG4gIF1cbn1cbkVuc3VyZSBlYWNoIGRlc2NyaXB0aW9uIGlzIGNvbmNpc2UgYW5kIGRpcmVjdGx5IGV4dHJhY3RlZCBvciBzdW1tYXJpemVkIGZyb20gdGhlIHByb3ZpZGVkIHRleHQuXG5JZiBubyBpdGVtcyBhcmUgZm91bmQgZm9yIGEgY2F0ZWdvcnksIHJldHVybiBhbiBlbXB0eSBhcnJheSBmb3IgdGhhdCBjYXRlZ29yeS5cbkRvIG5vdCBpbnZlbnQgaW5mb3JtYXRpb24gbm90IHByZXNlbnQgaW4gdGhlIHRleHQuIFN0aWNrIHN0cmljdGx5IHRvIHRoZSBkb2N1bWVudCBjb250ZW50LmA7XG5cbiAgY29uc3QgdXNlclByb21wdCA9IGBBbmFseXplIHRoZSBmb2xsb3dpbmcgZG9jdW1lbnQke2NvbnRleHREZXNjcmlwdGlvbiA/IGAgcmVnYXJkaW5nIFwiJHtjb250ZXh0RGVzY3JpcHRpb259XCJgIDogJyd9OlxuXG5cIlwiXCJcbiR7dGV4dENvbnRlbnR9XG5cIlwiXCJcblxuQmFzZWQgKm9ubHkqIG9uIHRoZSBpbmZvcm1hdGlvbiB3aXRoaW4gdGhlIGRvY3VtZW50IHByb3ZpZGVkLCBpZGVudGlmeSBhY3Rpb24gaXRlbXMsIGRlY2lzaW9ucywgYW5kIHF1ZXN0aW9ucyBhY2NvcmRpbmcgdG8gdGhlIEpTT04gc3RydWN0dXJlIEkgc3BlY2lmaWVkIGluIG15IHN5c3RlbSBpbnN0cnVjdGlvbnMuYDtcblxuICB0cnkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgJ1tsbG1VdGlsaXRpZXMuYW5hbHl6ZVRleHRGb3JGb2xsb3dVcHNdIFNlbmRpbmcgcHJvbXB0IHRvIE9wZW5BSSBBUEkuLi4nXG4gICAgKTtcblxuICAgIGNvbnN0IGNvbXBsZXRpb24gPSBhd2FpdCBvcGVuYWkuY2hhdC5jb21wbGV0aW9ucy5jcmVhdGUoe1xuICAgICAgbW9kZWw6ICdncHQtMy41LXR1cmJvLTExMDYnLCAvLyBVc2luZyBhIG1vZGVsIHRoYXQgc3VwcG9ydHMgSlNPTiBtb2RlIHdlbGxcbiAgICAgIHJlc3BvbnNlX2Zvcm1hdDogeyB0eXBlOiAnanNvbl9vYmplY3QnIH0sXG4gICAgICBtZXNzYWdlczogW1xuICAgICAgICB7IHJvbGU6ICdzeXN0ZW0nLCBjb250ZW50OiBzeXN0ZW1Qcm9tcHQgfSxcbiAgICAgICAgeyByb2xlOiAndXNlcicsIGNvbnRlbnQ6IHVzZXJQcm9tcHQgfSxcbiAgICAgIF0sXG4gICAgICB0ZW1wZXJhdHVyZTogMC4yLFxuICAgICAgbWF4X3Rva2VuczogMTUwMCwgLy8gSW5jcmVhc2VkIG1heF90b2tlbnMgZm9yIHBvdGVudGlhbGx5IGxhcmdlciBKU09OIHJlc3BvbnNlc1xuICAgIH0pO1xuXG4gICAgY29uc3QgcmF3UmVzcG9uc2UgPSBjb21wbGV0aW9uLmNob2ljZXNbMF0/Lm1lc3NhZ2U/LmNvbnRlbnQ7XG5cbiAgICBpZiAoIXJhd1Jlc3BvbnNlKSB7XG4gICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICAnW2xsbVV0aWxpdGllcy5hbmFseXplVGV4dEZvckZvbGxvd1Vwc10gTExNIHJlc3BvbnNlIGNvbnRlbnQgaXMgbnVsbCBvciBlbXB0eS4nXG4gICAgICApO1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgZXh0cmFjdGVkSXRlbXM6IHsgYWN0aW9uX2l0ZW1zOiBbXSwgZGVjaXNpb25zOiBbXSwgcXVlc3Rpb25zOiBbXSB9LFxuICAgICAgICBlcnJvcjogJ0xMTSByZXR1cm5lZCBlbXB0eSBvciBudWxsIHJlc3BvbnNlIGNvbnRlbnQuJyxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgY29uc29sZS5sb2coXG4gICAgICAnW2xsbVV0aWxpdGllcy5hbmFseXplVGV4dEZvckZvbGxvd1Vwc10gTExNIHJhdyByZXNwb25zZSByZWNlaXZlZCAoZmlyc3QgNTAwIGNoYXJzKTonLFxuICAgICAgcmF3UmVzcG9uc2Uuc3Vic3RyaW5nKDAsIDUwMClcbiAgICApO1xuXG4gICAgLy8gUGFyc2UgdGhlIExMTSBSZXNwb25zZVxuICAgIGNvbnN0IHBhcnNlZFJlc3BvbnNlID0gSlNPTi5wYXJzZShyYXdSZXNwb25zZSkgYXMgRXh0cmFjdGVkRm9sbG93VXBJdGVtcztcblxuICAgIGlmIChcbiAgICAgICFwYXJzZWRSZXNwb25zZSB8fFxuICAgICAgdHlwZW9mIHBhcnNlZFJlc3BvbnNlICE9PSAnb2JqZWN0JyB8fFxuICAgICAgIUFycmF5LmlzQXJyYXkocGFyc2VkUmVzcG9uc2UuYWN0aW9uX2l0ZW1zKSB8fFxuICAgICAgIUFycmF5LmlzQXJyYXkocGFyc2VkUmVzcG9uc2UuZGVjaXNpb25zKSB8fFxuICAgICAgIUFycmF5LmlzQXJyYXkocGFyc2VkUmVzcG9uc2UucXVlc3Rpb25zKVxuICAgICkge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgJ1tsbG1VdGlsaXRpZXMuYW5hbHl6ZVRleHRGb3JGb2xsb3dVcHNdIExMTSByZXNwb25zZSB3YXMgbm90IGluIHRoZSBleHBlY3RlZCBKU09OIGZvcm1hdCBhZnRlciBwYXJzaW5nLidcbiAgICAgICk7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBleHRyYWN0ZWRJdGVtczogeyBhY3Rpb25faXRlbXM6IFtdLCBkZWNpc2lvbnM6IFtdLCBxdWVzdGlvbnM6IFtdIH0sXG4gICAgICAgIGVycm9yOiAnTExNIHJlc3BvbnNlIGZvcm1hdCBlcnJvciBhZnRlciBwYXJzaW5nLicsXG4gICAgICB9O1xuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgJ1tsbG1VdGlsaXRpZXMuYW5hbHl6ZVRleHRGb3JGb2xsb3dVcHNdIFN1Y2Nlc3NmdWxseSBwYXJzZWQgTExNIHJlc3BvbnNlLidcbiAgICApO1xuICAgIHJldHVybiB7IGV4dHJhY3RlZEl0ZW1zOiBwYXJzZWRSZXNwb25zZSB9O1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcihcbiAgICAgICdbbGxtVXRpbGl0aWVzLmFuYWx5emVUZXh0Rm9yRm9sbG93VXBzXSBFcnJvciBkdXJpbmcgTExNIGludGVyYWN0aW9uIG9yIHBhcnNpbmc6JyxcbiAgICAgIGVycm9yLm1lc3NhZ2UsXG4gICAgICBlcnJvci5zdGFja1xuICAgICk7XG4gICAgbGV0IGVycm9yTWVzc2FnZSA9IGBMTE0gaW50ZXJhY3Rpb24gZmFpbGVkOiAke2Vycm9yLm1lc3NhZ2V9YDtcbiAgICBpZiAoZXJyb3IuY29kZSkge1xuICAgICAgLy8gU3BlY2lmaWMgT3BlbkFJIGVycm9yIGNvZGVzXG4gICAgICBlcnJvck1lc3NhZ2UgKz0gYCAoQ29kZTogJHtlcnJvci5jb2RlfSlgO1xuICAgIH1cbiAgICByZXR1cm4ge1xuICAgICAgZXh0cmFjdGVkSXRlbXM6IHsgYWN0aW9uX2l0ZW1zOiBbXSwgZGVjaXNpb25zOiBbXSwgcXVlc3Rpb25zOiBbXSB9LFxuICAgICAgZXJyb3I6IGVycm9yTWVzc2FnZSxcbiAgICB9O1xuICB9XG59XG4iXX0=