"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.EmailTriageSkill = void 0;
const IMPORTANT_SENDERS = [
    'boss@example.com',
    'ceo@example.com',
    'directreport@example.com',
    'importantclient@example.com',
];
function _stripHtml(htmlString) {
    let text = htmlString;
    text = text.replace(/<\/(p|div|h[1-6]|li|dt|dd|pre|blockquote|address|header|footer|section|article)>/gi, '\n');
    text = text.replace(/<br\s*\/?>/gi, '\n');
    text = text.replace(/<li[^>]*>/gi, '\n* ');
    text = text.replace(/<dd[^>]*>/gi, '\n  ');
    text = text.replace(/<[^>]+>/g, '');
    text = text
        .replace(/&nbsp;/g, ' ')
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'");
    text = text.replace(/\n{3,}/g, '\n\n');
    text = text.replace(/ {2,}/g, ' ');
    return text.trim();
}
class EmailTriageSkill {
    llmService;
    constructor(llmService) {
        this.llmService = llmService;
        console.log('EmailTriageSkill initialized with LLMService.');
    }
    async execute(email) {
        console.log(`[EmailTriageSkill] Processing email ID: ${email.id} from: ${email.sender} with subject: "${email.subject}"`);
        if (!email || !email.id || !email.subject || !email.body) {
            throw new Error('Invalid email object provided. Essential fields (id, subject, body) are missing.');
        }
        console.log(`[EmailTriageSkill] Email validated: ${email.id}`);
        let processedBody = email.body;
        const isHtml = /<([a-z][a-z0-9]*)\b[^>]*>/i.test(email.body);
        if (isHtml) {
            processedBody = _stripHtml(email.body);
            console.log('[EmailTriageSkill] HTML detected; stripped to plain text.');
        }
        else {
            console.log('[EmailTriageSkill] Email body appears to be plain text.');
        }
        // 1. Determine Category (LLM-based)
        let determinedCategory = 'Other';
        let categoryConfidence = 0.2;
        const categorizationData = {
            subject: email.subject,
            bodySnippet: processedBody.substring(0, 250),
        };
        const structuredCategorizationPrompt = {
            task: 'categorize_email',
            data: categorizationData,
        };
        try {
            const llmResponse = await this.llmService.generate(structuredCategorizationPrompt, 'cheapest');
            if (llmResponse.success && llmResponse.content) {
                const parsedResponse = JSON.parse(llmResponse.content);
                const validCategories = [
                    'Urgent',
                    'ActionRequired',
                    'FYI',
                    'Spam',
                    'MeetingInvite',
                    'Other',
                ];
                if (parsedResponse &&
                    parsedResponse.category &&
                    validCategories.includes(parsedResponse.category) &&
                    typeof parsedResponse.confidence === 'number') {
                    determinedCategory = parsedResponse.category;
                    categoryConfidence = parsedResponse.confidence;
                }
                else {
                    console.warn(`[EmailTriageSkill] LLM category response invalid structure. Defaulting. Resp: ${llmResponse.content}`);
                }
            }
            else {
                console.error(`[EmailTriageSkill] LLM category call failed. Error: ${llmResponse.error}`);
            }
        }
        catch (error) {
            console.error('[EmailTriageSkill] Error processing LLM category response:', error.message);
        }
        console.log(`[EmailTriageSkill] LLM Category: ${determinedCategory}, Confidence: ${categoryConfidence.toFixed(2)}`);
        // 2. Calculate Priority Score (Rule-based)
        let calculatedPriorityScore = 0;
        switch (determinedCategory) {
            case 'Urgent':
                calculatedPriorityScore = 9;
                break;
            case 'ActionRequired':
                calculatedPriorityScore = 7;
                break;
            case 'MeetingInvite':
                calculatedPriorityScore = 6;
                break;
            case 'FYI':
                calculatedPriorityScore = 3;
                break;
            default:
                calculatedPriorityScore = 2;
        }
        if (determinedCategory === 'Spam')
            calculatedPriorityScore = 0;
        const senderEmailMatch = email.sender.toLowerCase().match(/<([^>]+)>/);
        const actualSender = senderEmailMatch
            ? senderEmailMatch[1]
            : email.sender.toLowerCase();
        if (IMPORTANT_SENDERS.includes(actualSender)) {
            calculatedPriorityScore = Math.min(10, calculatedPriorityScore + 2);
        }
        if (email.headers?.Importance?.toLowerCase() === 'high' ||
            email.headers?.['X-Priority']?.startsWith('1')) {
            calculatedPriorityScore = Math.min(10, calculatedPriorityScore + 1);
        }
        console.log(`[EmailTriageSkill] Priority Score: ${calculatedPriorityScore}`);
        // 3. Generate Summary (LLM-based)
        let generatedSummary = `Subject: "${email.subject}". Body: ${processedBody.substring(0, 150)}...`; // Fallback
        const summarizationData = {
            subject: email.subject,
            bodySnippet: processedBody.substring(0, 500),
        };
        const structuredSummaryPrompt = {
            task: 'summarize_email',
            data: summarizationData,
        };
        try {
            const llmResponse = await this.llmService.generate(structuredSummaryPrompt, 'cheapest');
            if (llmResponse.success &&
                llmResponse.content &&
                !llmResponse.content.toLowerCase().startsWith('llm fallback')) {
                generatedSummary = llmResponse.content;
            }
            else {
                console.warn(`[EmailTriageSkill] LLM summary failed or fallback: ${llmResponse.error || llmResponse.content}. Using basic snippet.`);
            }
        }
        catch (error) {
            console.error('[EmailTriageSkill] Error in LLM summarization:', error.message);
        }
        console.log(`[EmailTriageSkill] Summary: ${generatedSummary}`);
        // 4. Extract Action Items (LLM-based)
        let foundActionItems = [];
        const actionExtractionData = {
            emailBody: processedBody.substring(0, 1000),
        };
        const structuredActionItemPrompt = {
            task: 'extract_actions_email',
            data: actionExtractionData,
        };
        try {
            const llmResponse = await this.llmService.generate(structuredActionItemPrompt, 'cheapest');
            if (llmResponse.success && llmResponse.content) {
                const parsedResponse = JSON.parse(llmResponse.content);
                if (parsedResponse && Array.isArray(parsedResponse.actionItems)) {
                    foundActionItems = parsedResponse.actionItems.filter((item) => typeof item === 'string');
                }
                else if (typeof llmResponse.content === 'string' &&
                    !llmResponse.content.toLowerCase().startsWith('llm fallback') &&
                    !llmResponse.content.startsWith('{')) {
                    foundActionItems = [llmResponse.content];
                }
                else {
                    console.warn(`[EmailTriageSkill] LLM action items response invalid structure: ${llmResponse.content}`);
                }
            }
            else {
                console.warn(`[EmailTriageSkill] LLM action item extraction failed: ${llmResponse.error || llmResponse.content}`);
            }
        }
        catch (error) {
            console.error('[EmailTriageSkill] Error in LLM action extraction:', error.message);
        }
        if (foundActionItems.length > 0)
            console.log(`[EmailTriageSkill] Action Items:`, foundActionItems);
        // 5. Suggest Reply (LLM-based)
        let suggestedReplyMessage = undefined;
        const replyData = {
            category: determinedCategory,
            subject: email.subject,
            summary: generatedSummary,
            actionItems: foundActionItems.length > 0 ? foundActionItems : undefined,
        };
        const structuredReplyPrompt = {
            task: 'suggest_reply_email',
            data: replyData,
        };
        try {
            const llmResponse = await this.llmService.generate(structuredReplyPrompt, 'cheapest');
            if (llmResponse.success &&
                llmResponse.content &&
                llmResponse.content.trim().toLowerCase() !== 'no reply needed.' &&
                !llmResponse.content.toLowerCase().startsWith('llm fallback')) {
                suggestedReplyMessage = llmResponse.content.trim();
            }
            else {
                console.log(`[EmailTriageSkill] LLM indicated no reply needed or fallback for reply. Error: ${llmResponse.error || 'No content'}`);
            }
        }
        catch (error) {
            console.error('[EmailTriageSkill] Error in LLM reply suggestion:', error.message);
        }
        if (suggestedReplyMessage)
            console.log(`[EmailTriageSkill] Suggested Reply: "${suggestedReplyMessage}"`);
        // Construct and return TriageResult
        const result = {
            emailId: email.id,
            category: determinedCategory,
            confidence: parseFloat(categoryConfidence.toFixed(2)),
            priorityScore: calculatedPriorityScore,
            summary: generatedSummary,
            suggestedReply: suggestedReplyMessage,
            extractedActionItems: foundActionItems.length > 0 ? foundActionItems : undefined,
        };
        console.log(`[EmailTriageSkill] Triage complete. Result:`, result);
        return result;
    }
}
exports.EmailTriageSkill = EmailTriageSkill;
// Example Usage
/*
import { MockLLMService, OpenAIGroqService_Stub } from '../lib/llmUtils'; // Adjust path as needed

async function testEmailTriageSkill() {
  // Option 1: Use the MockLLMService for predictable mock behavior
  const mockLlmService = new MockLLMService();
  const skillWithMock = new EmailTriageSkill(mockLlmService);

  console.log("\\n--- Testing EmailTriageSkill with MockLLMService ---");

  const testEmail1: EmailObject = {
    id: "test-email-001",
    sender: "Alice <alice@example.com>",
    recipients: ["bob@example.com", "currentUser@example.com"],
    subject: "Quick question about the Phoenix project",
    body: "Hi team, I had a quick question regarding the latest update on the Phoenix project. Can someone point me to the documentation for the new auth module? Thanks! Please send the report too.",
    receivedDate: new Date(),
    headers: { "X-Priority": "3" }
  };
  try {
    const result1 = await skillWithMock.execute(testEmail1);
    console.log("Result for testEmail1:", JSON.stringify(result1, null, 2));
  } catch (error) {
    console.error("Error during skillWithMock execution (testEmail1):", error);
  }

  const urgentEmail: EmailObject = {
    id: "urgent-email-002",
    sender: "boss@example.com", // This sender is in IMPORTANT_SENDERS
    recipients: ["currentUser@example.com"],
    subject: "URGENT: Action Required - System Outage",
    body: "Team, we have a critical system outage affecting all customers. All hands on deck. Please join the emergency bridge now: conf-link. This requires your immediate action.",
    receivedDate: new Date(),
    headers: { "Importance": "High" }
  };
  try {
    const resultUrgent = await skillWithMock.execute(urgentEmail);
    console.log("Result for urgentEmail:", JSON.stringify(resultUrgent, null, 2));
  } catch (error) {
    console.error("Error during skillWithMock execution (urgentEmail):", error);
  }

  // Option 2: Use the OpenAIGroqService_Stub (which internally might call MockLLMService or have its own simple stubs)
  // Replace with your actual API key and desired Groq model when ready for real calls.
  // const groqApiKey = process.env.GROQ_API_KEY || "YOUR_GROQ_API_KEY_PLACEHOLDER";
  // const groqModel = "mixtral-8x7b-32768"; // Example Groq model
  // const openAIGroqStubService = new OpenAIGroqService_Stub(groqApiKey, groqModel);
  // const skillWithGroqStub = new EmailTriageSkill(openAIGroqStubService);

  // console.log("\\n--- Testing EmailTriageSkill with OpenAIGroqService_Stub ---");
  // try {
  //   const resultStub = await skillWithGroqStub.execute(testEmail1);
  //   console.log("Result for testEmail1 (Groq Stub):", JSON.stringify(resultStub, null, 2));
  // } catch (error) {
  //   console.error("Error during skillWithGroqStub execution (testEmail1):", error);
  // }
}

// To run the test:
// 1. Ensure `MockLLMService` and `OpenAIGroqService_Stub` are exported from `llmUtils.ts`.
// 2. Uncomment the imports at the top of this example function.
// 3. If testing `OpenAIGroqService_Stub` for real, provide API key and uncomment relevant lines.
// 4. Call testEmailTriageSkill();
// testEmailTriageSkill();
*/
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZW1haWxUcmlhZ2VTa2lsbC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImVtYWlsVHJpYWdlU2tpbGwudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7O0FBK0NBLE1BQU0saUJBQWlCLEdBQUc7SUFDeEIsa0JBQWtCO0lBQ2xCLGlCQUFpQjtJQUNqQiwwQkFBMEI7SUFDMUIsNkJBQTZCO0NBQzlCLENBQUM7QUFFRixTQUFTLFVBQVUsQ0FBQyxVQUFrQjtJQUNwQyxJQUFJLElBQUksR0FBRyxVQUFVLENBQUM7SUFDdEIsSUFBSSxHQUFHLElBQUksQ0FBQyxPQUFPLENBQ2pCLG9GQUFvRixFQUNwRixJQUFJLENBQ0wsQ0FBQztJQUNGLElBQUksR0FBRyxJQUFJLENBQUMsT0FBTyxDQUFDLGNBQWMsRUFBRSxJQUFJLENBQUMsQ0FBQztJQUMxQyxJQUFJLEdBQUcsSUFBSSxDQUFDLE9BQU8sQ0FBQyxhQUFhLEVBQUUsTUFBTSxDQUFDLENBQUM7SUFDM0MsSUFBSSxHQUFHLElBQUksQ0FBQyxPQUFPLENBQUMsYUFBYSxFQUFFLE1BQU0sQ0FBQyxDQUFDO0lBQzNDLElBQUksR0FBRyxJQUFJLENBQUMsT0FBTyxDQUFDLFVBQVUsRUFBRSxFQUFFLENBQUMsQ0FBQztJQUNwQyxJQUFJLEdBQUcsSUFBSTtTQUNSLE9BQU8sQ0FBQyxTQUFTLEVBQUUsR0FBRyxDQUFDO1NBQ3ZCLE9BQU8sQ0FBQyxRQUFRLEVBQUUsR0FBRyxDQUFDO1NBQ3RCLE9BQU8sQ0FBQyxPQUFPLEVBQUUsR0FBRyxDQUFDO1NBQ3JCLE9BQU8sQ0FBQyxPQUFPLEVBQUUsR0FBRyxDQUFDO1NBQ3JCLE9BQU8sQ0FBQyxTQUFTLEVBQUUsR0FBRyxDQUFDO1NBQ3ZCLE9BQU8sQ0FBQyxRQUFRLEVBQUUsR0FBRyxDQUFDLENBQUM7SUFDMUIsSUFBSSxHQUFHLElBQUksQ0FBQyxPQUFPLENBQUMsU0FBUyxFQUFFLE1BQU0sQ0FBQyxDQUFDO0lBQ3ZDLElBQUksR0FBRyxJQUFJLENBQUMsT0FB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QUMsT0FBTyxDQUFDLENBQUMsQ0FBQyxDQUFDO1lBQ3JELGFBQWEsRUFBRSx1QkFBdUI7WUFDdEMsT0FBTyxFQUFFLGdCQUFnQjtZQUN6QixjQUFjLEVBQUUscUJBQXFCO1lBQ3JDLG9CQUFvQixFQUNsQixnQkFBZ0IsQ0FBQyxNQUFNLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDLENBQUMsU0FBUztTQUM3RCxDQUFDO1FBRUYsT0FBTyxDQUFDLEdBQUcsQ0FBQyw2Q0FBNkMsRUFBRSxNQUFNLENBQUMsQ0FBQztRQUNuRSxPQUFPLE1BQU0sQ0FBQztJQUNoQixDQUFDO0NBQ0Y7QUE5UEQsNENBOFBDO0FBRUQsZ0JBQWdCO0FBQ2hCOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0VBZ0VFIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHtcbiAgTExNU2VydmljZUludGVyZmFjZSwgLy8gSW1wb3J0IHRoZSBpbnRlcmZhY2VcbiAgU3RydWN0dXJlZExMTVByb21wdCxcbiAgRW1haWxDYXRlZ29yaXphdGlvbkRhdGEsXG4gIEVtYWlsU3VtbWFyaXphdGlvbkRhdGEsXG4gIEVtYWlsUmVwbHlTdWdnZXN0aW9uRGF0YSxcbiAgRW1haWxBY3Rpb25FeHRyYWN0aW9uRGF0YSxcbiAgTExNVGFza1R5cGUsXG59IGZyb20gJy4uL2xpYi9sbG1VdGlscyc7XG5cbi8qKlxuICogUmVwcmVzZW50cyBhbiBpbmNvbWluZyBlbWFpbCBtZXNzYWdlLlxuICovXG5leHBvcnQgaW50ZXJmYWNlIEVtYWlsT2JqZWN0IHtcbiAgaWQ6IHN0cmluZztcbiAgc2VuZGVyOiBzdHJpbmc7XG4gIHJlY2lwaWVudHM6IHN0cmluZ1tdO1xuICBzdWJqZWN0OiBzdHJpbmc7XG4gIGJvZHk6IHN0cmluZztcbiAgcmVjZWl2ZWREYXRlOiBEYXRlO1xuICBoZWFkZXJzPzogUmVjb3JkPHN0cmluZywgc3RyaW5nPjtcbn1cblxuLyoqXG4gKiBEZWZpbmVzIHRoZSBwb3NzaWJsZSBjYXRlZ29yaWVzIGZvciBhIHRyaWFnZWQgZW1haWwuXG4gKi9cbmV4cG9ydCB0eXBlIEVtYWlsQ2F0ZWdvcnkgPVxuICB8ICdVcmdlbnQnXG4gIHwgJ0FjdGlvblJlcXVpcmVkJ1xuICB8ICdGWUknXG4gIHwgJ1NwYW0nXG4gIHwgJ01lZXRpbmdJbnZpdGUnXG4gIHwgJ090aGVyJztcblxuLyoqXG4gKiBSZXByZXNlbnRzIHRoZSByZXN1bHQgb2YgdHJpYWdpbmcgYW4gZW1haWwuXG4gKi9cbmV4cG9ydCBpbnRlcmZhY2UgVHJpYWdlUmVzdWx0IHtcbiAgZW1haWxJZDogc3RyaW5nO1xuICBjYXRlZ29yeTogRW1haWxDYXRlZ29yeTtcbiAgY29uZmlkZW5jZT86IG51bWJlcjtcbiAgc3VtbWFyeT86IHN0cmluZztcbiAgc3VnZ2VzdGVkUmVwbHk/OiBzdHJpbmc7XG4gIHByaW9yaXR5U2NvcmU/OiBudW1iZXI7XG4gIGV4dHJhY3RlZEFjdGlvbkl0ZW1zPzogc3RyaW5nW107XG59XG5cbmNvbnN0IElNUE9SVEFOVF9TRU5ERVJTID0gW1xuICAnYm9zc0BleGFtcGxlLmNvbScsXG4gICdjZW9AZXhhbXBsZS5jb20nLFxuICAnZGlyZWN0cmVwb3J0QGV4YW1wbGUuY29tJyxcbiAgJ2ltcG9ydGFudGNsaWVudEBleGFtcGxlLmNvbScsXG5dO1xuXG5mdW5jdGlvbiBfc3RyaXBIdG1sKGh0bWxTdHJpbmc6IHN0cmluZyk6IHN0cmluZyB7XG4gIGxldCB0ZXh0ID0gaHRtbFN0cmluZztcbiAgdGV4dCA9IHRleHQucmVwbGFjZShcbiAgICAvPFxcLyhwfGRpdnxoWzEtNl18bGl8ZHR8ZGR8cHJlfGJsb2NrcXVvdGV8YWRkcmVzc3xoZWFkZXJ8Zm9vdGVyfHNlY3Rpb258YXJ0aWNsZSk+L2dpLFxuICAgICdcXG4nXG4gICk7XG4gIHRleHQgPSB0ZXh0LnJlcGxhY2UoLzxiclxccypcXC8/Pi9naSwgJ1xcbicpO1xuICB0ZXh0ID0gdGV4dC5yZXBsYWNlKC88bGlbXj5dKj4vZ2ksICdcXG4qICcpO1xuICB0ZXh0ID0gdGV4dC5yZXBsYWNlKC88ZGRbXj5dKj4vZ2ksICdcXG4gICcpO1xuICB0ZXh0ID0gdGV4dC5yZXBsYWNlKC88W14+XSs+L2csICcnKTtcbiAgdGV4dCA9IHRleHRcbiAgICAucmVwbGFjZSgvJm5ic3A7L2csICcgJylcbiAgICAucmVwbGFjZSgvJmFtcDsvZywgJyYnKVxuICAgIC5yZXBsYWNlKC8mbHQ7L2csICc8JylcbiAgICAucmVwbGFjZSgvJmd0Oy9nLCAnPicpXG4gICAgLnJlcGxhY2UoLyZxdW90Oy9nLCAnXCInKVxuICAgIC5yZXBsYWNlKC8mIzM5Oy9nLCBcIidcIik7XG4gIHRleHQgPSB0ZXh0LnJlcGxhY2UoL1xcbnszLH0vZywgJ1xcblxcbicpO1xuICB0ZXh0ID0gdGV4dC5yZXBsYWNlKC8gezIsfS9nLCAnICcpO1xuICByZXR1cm4gdGV4dC50cmltKCk7XG59XG5cbmV4cG9ydCBjbGFzcyBFbWFpbFRyaWFnZVNraWxsIHtcbiAgcHJpdmF0ZSByZWFkb25seSBsbG1TZXJ2aWNlOiBMTE1TZXJ2aWNlSW50ZXJmYWNlO1xuXG4gIGNvbnN0cnVjdG9yKGxsbVNlcnZpY2U6IExMTVNlcnZpY2VJbnRlcmZhY2UpIHtcbiAgICB0aGlzLmxsbVNlcnZpY2UgPSBsbG1TZXJ2aWNlO1xuICAgIGNvbnNvbGUubG9nKCdFbWFpbFRyaWFnZVNraWxsIGluaXRpYWxpemVkIHdpdGggTExNU2VydmljZS4nKTtcbiAgfVxuXG4gIHB1YmxpYyBhc3luYyBleGVjdXRlKGVtYWlsOiBFbWFpbE9iamVjdCk6IFByb21pc2U8VHJpYWdlUmVzdWx0PiB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBgW0VtYWlsVHJpYWdlU2tpbGxdIFByb2Nlc3NpbmcgZW1haWwgSUQ6ICR7ZW1haWwuaWR9IGZyb206ICR7ZW1haWwuc2VuZGVyfSB3aXRoIHN1YmplY3Q6IFwiJHtlbWFpbC5zdWJqZWN0fVwiYFxuICAgICk7XG5cbiAgICBpZiAoIWVtYWlsIHx8ICFlbWFpbC5pZCB8fCAhZW1haWwuc3ViamVjdCB8fCAhZW1haWwuYm9keSkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgICAnSW52YWxpZCBlbWFpbCBvYmplY3QgcHJvdmlkZWQuIEVzc2VudGlhbCBmaWVsZHMgKGlkLCBzdWJqZWN0LCBib2R5KSBhcmUgbWlzc2luZy4nXG4gICAgICApO1xuICAgIH1cbiAgICBjb25zb2xlLmxvZyhgW0VtYWlsVHJpYWdlU2tpbGxdIEVtYWlsIHZhbGlkYXRlZDogJHtlbWFpbC5pZH1gKTtcblxuICAgIGxldCBwcm9jZXNzZWRCb2R5ID0gZW1haWwuYm9keTtcbiAgICBjb25zdCBpc0h0bWwgPSAvPChbYS16XVthLXowLTldKilcXGJbXj5dKj4vaS50ZXN0KGVtYWlsLmJvZHkpO1xuICAgIGlmIChpc0h0bWwpIHtcbiAgICAgIHByb2Nlc3NlZEJvZHkgPSBfc3RyaXBIdG1sKGVtYWlsLmJvZHkpO1xuICAgICAgY29uc29sZS5sb2coJ1tFbWFpbFRyaWFnZVNraWxsXSBIVE1MIGRldGVjdGVkOyBzdHJpcHBlZCB0byBwbGFpbiB0ZXh0LicpO1xuICAgIH0gZWxzZSB7XG4gICAgICBjb25zb2xlLmxvZygnW0VtYWlsVHJpYWdlU2tpbGxdIEVtYWlsIGJvZHkgYXBwZWFycyB0byBiZSBwbGFpbiB0ZXh0LicpO1xuICAgIH1cblxuICAgIC8vIDEuIERldGVybWluZSBDYXRlZ29yeSAoTExNLWJhc2VkKVxuICAgIGxldCBkZXRlcm1pbmVkQ2F0ZWdvcnk6IEVtYWlsQ2F0ZWdvcnkgPSAnT3RoZXInO1xuICAgIGxldCBjYXRlZ29yeUNvbmZpZGVuY2UgPSAwLjI7XG4gICAgY29uc3QgY2F0ZWdvcml6YXRpb25EYXRhOiBFbWFpbENhdGVnb3JpemF0aW9uRGF0YSA9IHtcbiAgICAgIHN1YmplY3Q6IGVtYWlsLnN1YmplY3QsXG4gICAgICBib2R5U25pcHBldDogcHJvY2Vzc2VkQm9keS5zdWJzdHJpbmcoMCwgMjUwKSxcbiAgICB9O1xuICAgIGNvbnN0IHN0cnVjdHVyZWRDYXRlZ29yaXphdGlvblByb21wdDogU3RydWN0dXJlZExMTVByb21wdCA9IHtcbiAgICAgIHRhc2s6ICdjYXRlZ29yaXplX2VtYWlsJyxcbiAgICAgIGRhdGE6IGNhdGVnb3JpemF0aW9uRGF0YSxcbiAgICB9O1xuICAgIHRyeSB7XG4gICAgICBjb25zdCBsbG1SZXNwb25zZSA9IGF3YWl0IHRoaXMubGxtU2VydmljZS5nZW5lcmF0ZShcbiAgICAgICAgc3RydWN0dXJlZENhdGVnb3JpemF0aW9uUHJvbXB0LFxuICAgICAgICAnY2hlYXBlc3QnXG4gICAgICApO1xuICAgICAgaWYgKGxsbVJlc3BvbnNlLnN1Y2Nlc3MgJiYgbGxtUmVzcG9uc2UuY29udGVudCkge1xuICAgICAgICBjb25zdCBwYXJzZWRSZXNwb25zZSA9IEpTT04ucGFyc2UobGxtUmVzcG9uc2UuY29udGVudCk7XG4gICAgICAgIGNvbnN0IHZhbGlkQ2F0ZWdvcmllczogRW1haWxDYXRlZ29yeVtdID0gW1xuICAgICAgICAgICdVcmdlbnQnLFxuICAgICAgICAgICdBY3Rpb25SZXF1aXJlZCcsXG4gICAgICAgICAgJ0ZZSScsXG4gICAgICAgICAgJ1NwYW0nLFxuICAgICAgICAgICdNZWV0aW5nSW52aXRlJyxcbiAgICAgICAgICAnT3RoZXInLFxuICAgICAgICBdO1xuICAgICAgICBpZiAoXG4gICAgICAgICAgcGFyc2VkUmVzcG9uc2UgJiZcbiAgICAgICAgICBwYXJzZWRSZXNwb25zZS5jYXRlZ29yeSAmJlxuICAgICAgICAgIHZhbGlkQ2F0ZWdvcmllcy5pbmNsdWRlcyhwYXJzZWRSZXNwb25zZS5jYXRlZ29yeSkgJiZcbiAgICAgICAgICB0eXBlb2YgcGFyc2VkUmVzcG9uc2UuY29uZmlkZW5jZSA9PT0gJ251bWJlcidcbiAgICAgICAgKSB7XG4gICAgICAgICAgZGV0ZXJtaW5lZENhdGVnb3J5ID0gcGFyc2VkUmVzcG9uc2UuY2F0ZWdvcnk7XG4gICAgICAgICAgY2F0ZWdvcnlDb25maWRlbmNlID0gcGFyc2VkUmVzcG9uc2UuY29uZmlkZW5jZTtcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICAgICBgW0VtYWlsVHJpYWdlU2tpbGxdIExMTSBjYXRlZ29yeSByZXNwb25zZSBpbnZhbGlkIHN0cnVjdHVyZS4gRGVmYXVsdGluZy4gUmVzcDogJHtsbG1SZXNwb25zZS5jb250ZW50fWBcbiAgICAgICAgICApO1xuICAgICAgICB9XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICAgIGBbRW1haWxUcmlhZ2VTa2lsbF0gTExNIGNhdGVnb3J5IGNhbGwgZmFpbGVkLiBFcnJvcjogJHtsbG1SZXNwb25zZS5lcnJvcn1gXG4gICAgICAgICk7XG4gICAgICB9XG4gICAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgJ1tFbWFpbFRyaWFnZVNraWxsXSBFcnJvciBwcm9jZXNzaW5nIExMTSBjYXRlZ29yeSByZXNwb25zZTonLFxuICAgICAgICBlcnJvci5tZXNzYWdlXG4gICAgICApO1xuICAgIH1cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGBbRW1haWxUcmlhZ2VTa2lsbF0gTExNIENhdGVnb3J5OiAke2RldGVybWluZWRDYXRlZ29yeX0sIENvbmZpZGVuY2U6ICR7Y2F0ZWdvcnlDb25maWRlbmNlLnRvRml4ZWQoMil9YFxuICAgICk7XG5cbiAgICAvLyAyLiBDYWxjdWxhdGUgUHJpb3JpdHkgU2NvcmUgKFJ1bGUtYmFzZWQpXG4gICAgbGV0IGNhbGN1bGF0ZWRQcmlvcml0eVNjb3JlID0gMDtcbiAgICBzd2l0Y2ggKGRldGVybWluZWRDYXRlZ29yeSkge1xuICAgICAgY2FzZSAnVXJnZW50JzpcbiAgICAgICAgY2FsY3VsYXRlZFByaW9yaXR5U2NvcmUgPSA5O1xuICAgICAgICBicmVhaztcbiAgICAgIGNhc2UgJ0FjdGlvblJlcXVpcmVkJzpcbiAgICAgICAgY2FsY3VsYXRlZFByaW9yaXR5U2NvcmUgPSA3O1xuICAgICAgICBicmVhaztcbiAgICAgIGNhc2UgJ01lZXRpbmdJbnZpdGUnOlxuICAgICAgICBjYWxjdWxhdGVkUHJpb3JpdHlTY29yZSA9IDY7XG4gICAgICAgIGJyZWFrO1xuICAgICAgY2FzZSAnRllJJzpcbiAgICAgICAgY2FsY3VsYXRlZFByaW9yaXR5U2NvcmUgPSAzO1xuICAgICAgICBicmVhaztcbiAgICAgIGRlZmF1bHQ6XG4gICAgICAgIGNhbGN1bGF0ZWRQcmlvcml0eVNjb3JlID0gMjtcbiAgICB9XG4gICAgaWYgKGRldGVybWluZWRDYXRlZ29yeSA9PT0gJ1NwYW0nKSBjYWxjdWxhdGVkUHJpb3JpdHlTY29yZSA9IDA7XG5cbiAgICBjb25zdCBzZW5kZXJFbWFpbE1hdGNoID0gZW1haWwuc2VuZGVyLnRvTG93ZXJDYXNlKCkubWF0Y2goLzwoW14+XSspPi8pO1xuICAgIGNvbnN0IGFjdHVhbFNlbmRlciA9IHNlbmRlckVtYWlsTWF0Y2hcbiAgICAgID8gc2VuZGVyRW1haWxNYXRjaFsxXVxuICAgICAgOiBlbWFpbC5zZW5kZXIudG9Mb3dlckNhc2UoKTtcbiAgICBpZiAoSU1QT1JUQU5UX1NFTkRFUlMuaW5jbHVkZXMoYWN0dWFsU2VuZGVyKSkge1xuICAgICAgY2FsY3VsYXRlZFByaW9yaXR5U2NvcmUgPSBNYXRoLm1pbigxMCwgY2FsY3VsYXRlZFByaW9yaXR5U2NvcmUgKyAyKTtcbiAgICB9XG4gICAgaWYgKFxuICAgICAgZW1haWwuaGVhZGVycz8uSW1wb3J0YW5jZT8udG9Mb3dlckNhc2UoKSA9PT0gJ2hpZ2gnIHx8XG4gICAgICBlbWFpbC5oZWFkZXJzPy5bJ1gtUHJpb3JpdHknXT8uc3RhcnRzV2l0aCgnMScpXG4gICAgKSB7XG4gICAgICBjYWxjdWxhdGVkUHJpb3JpdHlTY29yZSA9IE1hdGgubWluKDEwLCBjYWxjdWxhdGVkUHJpb3JpdHlTY29yZSArIDEpO1xuICAgIH1cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGBbRW1haWxUcmlhZ2VTa2lsbF0gUHJpb3JpdHkgU2NvcmU6ICR7Y2FsY3VsYXRlZFByaW9yaXR5U2NvcmV9YFxuICAgICk7XG5cbiAgICAvLyAzLiBHZW5lcmF0ZSBTdW1tYXJ5IChMTE0tYmFzZWQpXG4gICAgbGV0IGdlbmVyYXRlZFN1bW1hcnkgPSBgU3ViamVjdDogXCIke2VtYWlsLnN1YmplY3R9XCIuIEJvZHk6ICR7cHJvY2Vzc2VkQm9keS5zdWJzdHJpbmcoMCwgMTUwKX0uLi5gOyAvLyBGYWxsYmFja1xuICAgIGNvbnN0IHN1bW1hcml6YXRpb25EYXRhOiBFbWFpbFN1bW1hcml6YXRpb25EYXRhID0ge1xuICAgICAgc3ViamVjdDogZW1haWwuc3ViamVjdCxcbiAgICAgIGJvZHlTbmlwcGV0OiBwcm9jZXNzZWRCb2R5LnN1YnN0cmluZygwLCA1MDApLFxuICAgIH07XG4gICAgY29uc3Qgc3RydWN0dXJlZFN1bW1hcnlQcm9tcHQ6IFN0cnVjdHVyZWRMTE1Qcm9tcHQgPSB7XG4gICAgICB0YXNrOiAnc3VtbWFyaXplX2VtYWlsJyxcbiAgICAgIGRhdGE6IHN1bW1hcml6YXRpb25EYXRhLFxuICAgIH07XG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IGxsbVJlc3BvbnNlID0gYXdhaXQgdGhpcy5sbG1TZXJ2aWNlLmdlbmVyYXRlKFxuICAgICAgICBzdHJ1Y3R1cmVkU3VtbWFyeVByb21wdCxcbiAgICAgICAgJ2NoZWFwZXN0J1xuICAgICAgKTtcbiAgICAgIGlmIChcbiAgICAgICAgbGxtUmVzcG9uc2Uuc3VjY2VzcyAmJlxuICAgICAgICBsbG1SZXNwb25zZS5jb250ZW50ICYmXG4gICAgICAgICFsbG1SZXNwb25zZS5jb250ZW50LnRvTG93ZXJDYXNlKCkuc3RhcnRzV2l0aCgnbGxtIGZhbGxiYWNrJylcbiAgICAgICkge1xuICAgICAgICBnZW5lcmF0ZWRTdW1tYXJ5ID0gbGxtUmVzcG9uc2UuY29udGVudDtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgICBgW0VtYWlsVHJpYWdlU2tpbGxdIExMTSBzdW1tYXJ5IGZhaWxlZCBvciBmYWxsYmFjazogJHtsbG1SZXNwb25zZS5lcnJvciB8fCBsbG1SZXNwb25zZS5jb250ZW50fS4gVXNpbmcgYmFzaWMgc25pcHBldC5gXG4gICAgICAgICk7XG4gICAgICB9XG4gICAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgJ1tFbWFpbFRyaWFnZVNraWxsXSBFcnJvciBpbiBMTE0gc3VtbWFyaXphdGlvbjonLFxuICAgICAgICBlcnJvci5tZXNzYWdlXG4gICAgICApO1xuICAgIH1cbiAgICBjb25zb2xlLmxvZyhgW0VtYWlsVHJpYWdlU2tpbGxdIFN1bW1hcnk6ICR7Z2VuZXJhdGVkU3VtbWFyeX1gKTtcblxuICAgIC8vIDQuIEV4dHJhY3QgQWN0aW9uIEl0ZW1zIChMTE0tYmFzZWQpXG4gICAgbGV0IGZvdW5kQWN0aW9uSXRlbXM6IHN0cmluZ1tdID0gW107XG4gICAgY29uc3QgYWN0aW9uRXh0cmFjdGlvbkRhdGE6IEVtYWlsQWN0aW9uRXh0cmFjdGlvbkRhdGEgPSB7XG4gICAgICBlbWFpbEJvZHk6IHByb2Nlc3NlZEJvZHkuc3Vic3RyaW5nKDAsIDEwMDApLFxuICAgIH07XG4gICAgY29uc3Qgc3RydWN0dXJlZEFjdGlvbkl0ZW1Qcm9tcHQ6IFN0cnVjdHVyZWRMTE1Qcm9tcHQgPSB7XG4gICAgICB0YXNrOiAnZXh0cmFjdF9hY3Rpb25zX2VtYWlsJyxcbiAgICAgIGRhdGE6IGFjdGlvbkV4dHJhY3Rpb25EYXRhLFxuICAgIH07XG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IGxsbVJlc3BvbnNlID0gYXdhaXQgdGhpcy5sbG1TZXJ2aWNlLmdlbmVyYXRlKFxuICAgICAgICBzdHJ1Y3R1cmVkQWN0aW9uSXRlbVByb21wdCxcbiAgICAgICAgJ2NoZWFwZXN0J1xuICAgICAgKTtcbiAgICAgIGlmIChsbG1SZXNwb25zZS5zdWNjZXNzICYmIGxsbVJlc3BvbnNlLmNvbnRlbnQpIHtcbiAgICAgICAgY29uc3QgcGFyc2VkUmVzcG9uc2UgPSBKU09OLnBhcnNlKGxsbVJlc3BvbnNlLmNvbnRlbnQpO1xuICAgICAgICBpZiAocGFyc2VkUmVzcG9uc2UgJiYgQXJyYXkuaXNBcnJheShwYXJzZWRSZXNwb25zZS5hY3Rpb25JdGVtcykpIHtcbiAgICAgICAgICBmb3VuZEFjdGlvbkl0ZW1zID0gcGFyc2VkUmVzcG9uc2UuYWN0aW9uSXRlbXMuZmlsdGVyKFxuICAgICAgICAgICAgKGl0ZW06IGFueSk6IGl0ZW0gaXMgc3RyaW5nID0+IHR5cGVvZiBpdGVtID09PSAnc3RyaW5nJ1xuICAgICAgICAgICk7XG4gICAgICAgIH0gZWxzZSBpZiAoXG4gICAgICAgICAgdHlwZW9mIGxsbVJlc3BvbnNlLmNvbnRlbnQgPT09ICdzdHJpbmcnICYmXG4gICAgICAgICAgIWxsbVJlc3BvbnNlLmNvbnRlbnQudG9Mb3dlckNhc2UoKS5zdGFydHNXaXRoKCdsbG0gZmFsbGJhY2snKSAmJlxuICAgICAgICAgICFsbG1SZXNwb25zZS5jb250ZW50LnN0YXJ0c1dpdGgoJ3snKVxuICAgICAgICApIHtcbiAgICAgICAgICBmb3VuZEFjdGlvbkl0ZW1zID0gW2xsbVJlc3BvbnNlLmNvbnRlbnRdO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgICAgIGBbRW1haWxUcmlhZ2VTa2lsbF0gTExNIGFjdGlvbiBpdGVtcyByZXNwb25zZSBpbnZhbGlkIHN0cnVjdHVyZTogJHtsbG1SZXNwb25zZS5jb250ZW50fWBcbiAgICAgICAgICApO1xuICAgICAgICB9XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICAgYFtFbWFpbFRyaWFnZVNraWxsXSBMTE0gYWN0aW9uIGl0ZW0gZXh0cmFjdGlvbiBmYWlsZWQ6ICR7bGxtUmVzcG9uc2UuZXJyb3IgfHwgbGxtUmVzcG9uc2UuY29udGVudH1gXG4gICAgICAgICk7XG4gICAgICB9XG4gICAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgJ1tFbWFpbFRyaWFnZVNraWxsXSBFcnJvciBpbiBMTE0gYWN0aW9uIGV4dHJhY3Rpb246JyxcbiAgICAgICAgZXJyb3IubWVzc2FnZVxuICAgICAgKTtcbiAgICB9XG4gICAgaWYgKGZvdW5kQWN0aW9uSXRlbXMubGVuZ3RoID4gMClcbiAgICAgIGNvbnNvbGUubG9nKGBbRW1haWxUcmlhZ2VTa2lsbF0gQWN0aW9uIEl0ZW1zOmAsIGZvdW5kQWN0aW9uSXRlbXMpO1xuXG4gICAgLy8gNS4gU3VnZ2VzdCBSZXBseSAoTExNLWJhc2VkKVxuICAgIGxldCBzdWdnZXN0ZWRSZXBseU1lc3NhZ2U6IHN0cmluZyB8IHVuZGVmaW5lZCA9IHVuZGVmaW5lZDtcbiAgICBjb25zdCByZXBseURhdGE6IEVtYWlsUmVwbHlTdWdnZXN0aW9uRGF0YSA9IHtcbiAgICAgIGNhdGVnb3J5OiBkZXRlcm1pbmVkQ2F0ZWdvcnksXG4gICAgICBzdWJqZWN0OiBlbWFpbC5zdWJqZWN0LFxuICAgICAgc3VtbWFyeTogZ2VuZXJhdGVkU3VtbWFyeSxcbiAgICAgIGFjdGlvbkl0ZW1zOiBmb3VuZEFjdGlvbkl0ZW1zLmxlbmd0aCA+IDAgPyBmb3VuZEFjdGlvbkl0ZW1zIDogdW5kZWZpbmVkLFxuICAgIH07XG4gICAgY29uc3Qgc3RydWN0dXJlZFJlcGx5UHJvbXB0OiBTdHJ1Y3R1cmVkTExNUHJvbXB0ID0ge1xuICAgICAgdGFzazogJ3N1Z2dlc3RfcmVwbHlfZW1haWwnLFxuICAgICAgZGF0YTogcmVwbHlEYXRhLFxuICAgIH07XG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IGxsbVJlc3BvbnNlID0gYXdhaXQgdGhpcy5sbG1TZXJ2aWNlLmdlbmVyYXRlKFxuICAgICAgICBzdHJ1Y3R1cmVkUmVwbHlQcm9tcHQsXG4gICAgICAgICdjaGVhcGVzdCdcbiAgICAgICk7XG4gICAgICBpZiAoXG4gICAgICAgIGxsbVJlc3BvbnNlLnN1Y2Nlc3MgJiZcbiAgICAgICAgbGxtUmVzcG9uc2UuY29udGVudCAmJlxuICAgICAgICBsbG1SZXNwb25zZS5jb250ZW50LnRyaW0oKS50b0xvd2VyQ2FzZSgpICE9PSAnbm8gcmVwbHkgbmVlZGVkLicgJiZcbiAgICAgICAgIWxsbVJlc3BvbnNlLmNvbnRlbnQudG9Mb3dlckNhc2UoKS5zdGFydHNXaXRoKCdsbG0gZmFsbGJhY2snKVxuICAgICAgKSB7XG4gICAgICAgIHN1Z2dlc3RlZFJlcGx5TWVzc2FnZSA9IGxsbVJlc3BvbnNlLmNvbnRlbnQudHJpbSgpO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgYFtFbWFpbFRyaWFnZVNraWxsXSBMTE0gaW5kaWNhdGVkIG5vIHJlcGx5IG5lZWRlZCBvciBmYWxsYmFjayBmb3IgcmVwbHkuIEVycm9yOiAke2xsbVJlc3BvbnNlLmVycm9yIHx8ICdObyBjb250ZW50J31gXG4gICAgICAgICk7XG4gICAgICB9XG4gICAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgJ1tFbWFpbFRyaWFnZVNraWxsXSBFcnJvciBpbiBMTE0gcmVwbHkgc3VnZ2VzdGlvbjonLFxuICAgICAgICBlcnJvci5tZXNzYWdlXG4gICAgICApO1xuICAgIH1cbiAgICBpZiAoc3VnZ2VzdGVkUmVwbHlNZXNzYWdlKVxuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGBbRW1haWxUcmlhZ2VTa2lsbF0gU3VnZ2VzdGVkIFJlcGx5OiBcIiR7c3VnZ2VzdGVkUmVwbHlNZXNzYWdlfVwiYFxuICAgICAgKTtcblxuICAgIC8vIENvbnN0cnVjdCBhbmQgcmV0dXJuIFRyaWFnZVJlc3VsdFxuICAgIGNvbnN0IHJlc3VsdDogVHJpYWdlUmVzdWx0ID0ge1xuICAgICAgZW1haWxJZDogZW1haWwuaWQsXG4gICAgICBjYXRlZ29yeTogZGV0ZXJtaW5lZENhdGVnb3J5LFxuICAgICAgY29uZmlkZW5jZTogcGFyc2VGbG9hdChjYXRlZ29yeUNvbmZpZGVuY2UudG9GaXhlZCgyKSksXG4gICAgICBwcmlvcml0eVNjb3JlOiBjYWxjdWxhdGVkUHJpb3JpdHlTY29yZSxcbiAgICAgIHN1bW1hcnk6IGdlbmVyYXRlZFN1bW1hcnksXG4gICAgICBzdWdnZXN0ZWRSZXBseTogc3VnZ2VzdGVkUmVwbHlNZXNzYWdlLFxuICAgICAgZXh0cmFjdGVkQWN0aW9uSXRlbXM6XG4gICAgICAgIGZvdW5kQWN0aW9uSXRlbXMubGVuZ3RoID4gMCA/IGZvdW5kQWN0aW9uSXRlbXMgOiB1bmRlZmluZWQsXG4gICAgfTtcblxuICAgIGNvbnNvbGUubG9nKGBbRW1haWxUcmlhZ2VTa2lsbF0gVHJpYWdlIGNvbXBsZXRlLiBSZXN1bHQ6YCwgcmVzdWx0KTtcbiAgICByZXR1cm4gcmVzdWx0O1xuICB9XG59XG5cbi8vIEV4YW1wbGUgVXNhZ2Vcbi8qXG5pbXBvcnQgeyBNb2NrTExNU2VydmljZSwgT3BlbkFJR3JvcVNlcnZpY2VfU3R1YiB9IGZyb20gJy4uL2xpYi9sbG1VdGlscyc7IC8vIEFkanVzdCBwYXRoIGFzIG5lZWRlZFxuXG5hc3luYyBmdW5jdGlvbiB0ZXN0RW1haWxUcmlhZ2VTa2lsbCgpIHtcbiAgLy8gT3B0aW9uIDE6IFVzZSB0aGUgTW9ja0xMTVNlcnZpY2UgZm9yIHByZWRpY3RhYmxlIG1vY2sgYmVoYXZpb3JcbiAgY29uc3QgbW9ja0xsbVNlcnZpY2UgPSBuZXcgTW9ja0xMTVNlcnZpY2UoKTtcbiAgY29uc3Qgc2tpbGxXaXRoTW9jayA9IG5ldyBFbWFpbFRyaWFnZVNraWxsKG1vY2tMbG1TZXJ2aWNlKTtcblxuICBjb25zb2xlLmxvZyhcIlxcXFxuLS0tIFRlc3RpbmcgRW1haWxUcmlhZ2VTa2lsbCB3aXRoIE1vY2tMTE1TZXJ2aWNlIC0tLVwiKTtcblxuICBjb25zdCB0ZXN0RW1haWwxOiBFbWFpbE9iamVjdCA9IHtcbiAgICBpZDogXCJ0ZXN0LWVtYWlsLTAwMVwiLFxuICAgIHNlbmRlcjogXCJBbGljZSA8YWxpY2VAZXhhbXBsZS5jb20+XCIsXG4gICAgcmVjaXBpZW50czogW1wiYm9iQGV4YW1wbGUuY29tXCIsIFwiY3VycmVudFVzZXJAZXhhbXBsZS5jb21cIl0sXG4gICAgc3ViamVjdDogXCJRdWljayBxdWVzdGlvbiBhYm91dCB0aGUgUGhvZW5peCBwcm9qZWN0XCIsXG4gICAgYm9keTogXCJIaSB0ZWFtLCBJIGhhZCBhIHF1aWNrIHF1ZXN0aW9uIHJlZ2FyZGluZyB0aGUgbGF0ZXN0IHVwZGF0ZSBvbiB0aGUgUGhvZW5peCBwcm9qZWN0LiBDYW4gc29tZW9uZSBwb2ludCBtZSB0byB0aGUgZG9jdW1lbnRhdGlvbiBmb3IgdGhlIG5ldyBhdXRoIG1vZHVsZT8gVGhhbmtzISBQbGVhc2Ugc2VuZCB0aGUgcmVwb3J0IHRvby5cIixcbiAgICByZWNlaXZlZERhdGU6IG5ldyBEYXRlKCksXG4gICAgaGVhZGVyczogeyBcIlgtUHJpb3JpdHlcIjogXCIzXCIgfVxuICB9O1xuICB0cnkge1xuICAgIGNvbnN0IHJlc3VsdDEgPSBhd2FpdCBza2lsbFdpdGhNb2NrLmV4ZWN1dGUodGVzdEVtYWlsMSk7XG4gICAgY29uc29sZS5sb2coXCJSZXN1bHQgZm9yIHRlc3RFbWFpbDE6XCIsIEpTT04uc3RyaW5naWZ5KHJlc3VsdDEsIG51bGwsIDIpKTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICBjb25zb2xlLmVycm9yKFwiRXJyb3IgZHVyaW5nIHNraWxsV2l0aE1vY2sgZXhlY3V0aW9uICh0ZXN0RW1haWwxKTpcIiwgZXJyb3IpO1xuICB9XG5cbiAgY29uc3QgdXJnZW50RW1haWw6IEVtYWlsT2JqZWN0ID0ge1xuICAgIGlkOiBcInVyZ2VudC1lbWFpbC0wMDJcIixcbiAgICBzZW5kZXI6IFwiYm9zc0BleGFtcGxlLmNvbVwiLCAvLyBUaGlzIHNlbmRlciBpcyBpbiBJTVBPUlRBTlRfU0VOREVSU1xuICAgIHJlY2lwaWVudHM6IFtcImN1cnJlbnRVc2VyQGV4YW1wbGUuY29tXCJdLFxuICAgIHN1YmplY3Q6IFwiVVJHRU5UOiBBY3Rpb24gUmVxdWlyZWQgLSBTeXN0ZW0gT3V0YWdlXCIsXG4gICAgYm9keTogXCJUZWFtLCB3ZSBoYXZlIGEgY3JpdGljYWwgc3lzdGVtIG91dGFnZSBhZmZlY3RpbmcgYWxsIGN1c3RvbWVycy4gQWxsIGhhbmRzIG9uIGRlY2suIFBsZWFzZSBqb2luIHRoZSBlbWVyZ2VuY3kgYnJpZGdlIG5vdzogY29uZi1saW5rLiBUaGlzIHJlcXVpcmVzIHlvdXIgaW1tZWRpYXRlIGFjdGlvbi5cIixcbiAgICByZWNlaXZlZERhdGU6IG5ldyBEYXRlKCksXG4gICAgaGVhZGVyczogeyBcIkltcG9ydGFuY2VcIjogXCJIaWdoXCIgfVxuICB9O1xuICB0cnkge1xuICAgIGNvbnN0IHJlc3VsdFVyZ2VudCA9IGF3YWl0IHNraWxsV2l0aE1vY2suZXhlY3V0ZSh1cmdlbnRFbWFpbCk7XG4gICAgY29uc29sZS5sb2coXCJSZXN1bHQgZm9yIHVyZ2VudEVtYWlsOlwiLCBKU09OLnN0cmluZ2lmeShyZXN1bHRVcmdlbnQsIG51bGwsIDIpKTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICBjb25zb2xlLmVycm9yKFwiRXJyb3IgZHVyaW5nIHNraWxsV2l0aE1vY2sgZXhlY3V0aW9uICh1cmdlbnRFbWFpbCk6XCIsIGVycm9yKTtcbiAgfVxuXG4gIC8vIE9wdGlvbiAyOiBVc2UgdGhlIE9wZW5BSUdyb3FTZXJ2aWNlX1N0dWIgKHdoaWNoIGludGVybmFsbHkgbWlnaHQgY2FsbCBNb2NrTExNU2VydmljZSBvciBoYXZlIGl0cyBvd24gc2ltcGxlIHN0dWJzKVxuICAvLyBSZXBsYWNlIHdpdGggeW91ciBhY3R1YWwgQVBJIGtleSBhbmQgZGVzaXJlZCBHcm9xIG1vZGVsIHdoZW4gcmVhZHkgZm9yIHJlYWwgY2FsbHMuXG4gIC8vIGNvbnN0IGdyb3FBcGlLZXkgPSBwcm9jZXNzLmVudi5HUk9RX0FQSV9LRVkgfHwgXCJZT1VSX0dST1FfQVBJX0tFWV9QTEFDRUhPTERFUlwiO1xuICAvLyBjb25zdCBncm9xTW9kZWwgPSBcIm1peHRyYWwtOHg3Yi0zMjc2OFwiOyAvLyBFeGFtcGxlIEdyb3EgbW9kZWxcbiAgLy8gY29uc3Qgb3BlbkFJR3JvcVN0dWJTZXJ2aWNlID0gbmV3IE9wZW5BSUdyb3FTZXJ2aWNlX1N0dWIoZ3JvcUFwaUtleSwgZ3JvcU1vZGVsKTtcbiAgLy8gY29uc3Qgc2tpbGxXaXRoR3JvcVN0dWIgPSBuZXcgRW1haWxUcmlhZ2VTa2lsbChvcGVuQUlHcm9xU3R1YlNlcnZpY2UpO1xuXG4gIC8vIGNvbnNvbGUubG9nKFwiXFxcXG4tLS0gVGVzdGluZyBFbWFpbFRyaWFnZVNraWxsIHdpdGggT3BlbkFJR3JvcVNlcnZpY2VfU3R1YiAtLS1cIik7XG4gIC8vIHRyeSB7XG4gIC8vICAgY29uc3QgcmVzdWx0U3R1YiA9IGF3YWl0IHNraWxsV2l0aEdyb3FTdHViLmV4ZWN1dGUodGVzdEVtYWlsMSk7XG4gIC8vICAgY29uc29sZS5sb2coXCJSZXN1bHQgZm9yIHRlc3RFbWFpbDEgKEdyb3EgU3R1Yik6XCIsIEpTT04uc3RyaW5naWZ5KHJlc3VsdFN0dWIsIG51bGwsIDIpKTtcbiAgLy8gfSBjYXRjaCAoZXJyb3IpIHtcbiAgLy8gICBjb25zb2xlLmVycm9yKFwiRXJyb3IgZHVyaW5nIHNraWxsV2l0aEdyb3FTdHViIGV4ZWN1dGlvbiAodGVzdEVtYWlsMSk6XCIsIGVycm9yKTtcbiAgLy8gfVxufVxuXG4vLyBUbyBydW4gdGhlIHRlc3Q6XG4vLyAxLiBFbnN1cmUgYE1vY2tMTE1TZXJ2aWNlYCBhbmQgYE9wZW5BSUdyb3FTZXJ2aWNlX1N0dWJgIGFyZSBleHBvcnRlZCBmcm9tIGBsbG1VdGlscy50c2AuXG4vLyAyLiBVbmNvbW1lbnQgdGhlIGltcG9ydHMgYXQgdGhlIHRvcCBvZiB0aGlzIGV4YW1wbGUgZnVuY3Rpb24uXG4vLyAzLiBJZiB0ZXN0aW5nIGBPcGVuQUlHcm9xU2VydmljZV9TdHViYCBmb3IgcmVhbCwgcHJvdmlkZSBBUEkga2V5IGFuZCB1bmNvbW1lbnQgcmVsZXZhbnQgbGluZXMuXG4vLyA0LiBDYWxsIHRlc3RFbWFpbFRyaWFnZVNraWxsKCk7XG4vLyB0ZXN0RW1haWxUcmlhZ2VTa2lsbCgpO1xuKi9cbiJdfQ==