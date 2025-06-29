import {
    LLMServiceInterface, // Import the interface
    StructuredLLMPrompt,
    EmailCategorizationData,
    EmailSummarizationData,
    EmailReplySuggestionData,
    EmailActionExtractionData,
    LLMTaskType
} from '../lib/llmUtils';

/**
 * Represents an incoming email message.
 */
export interface EmailObject {
  id: string;
  sender: string;
  recipients: string[];
  subject: string;
  body: string;
  receivedDate: Date;
  headers?: Record<string, string>;
}

/**
 * Defines the possible categories for a triaged email.
 */
export type EmailCategory = 'Urgent' | 'ActionRequired' | 'FYI' | 'Spam' | 'MeetingInvite' | 'Other';

/**
 * Represents the result of triaging an email.
 */
export interface TriageResult {
  emailId: string;
  category: EmailCategory;
  confidence?: number;
  summary?: string;
  suggestedReply?: string;
  priorityScore?: number;
  extractedActionItems?: string[];
}

const IMPORTANT_SENDERS = ["boss@example.com", "ceo@example.com", "directreport@example.com", "importantclient@example.com"];

function _stripHtml(htmlString: string): string {
  let text = htmlString;
  text = text.replace(/<\/(p|div|h[1-6]|li|dt|dd|pre|blockquote|address|header|footer|section|article)>/gi, '\n');
  text = text.replace(/<br\s*\/?>/gi, '\n');
  text = text.replace(/<li[^>]*>/gi, '\n* ');
  text = text.replace(/<dd[^>]*>/gi, '\n  ');
  text = text.replace(/<[^>]+>/g, '');
  text = text.replace(/&nbsp;/g, ' ')
             .replace(/&amp;/g, '&')
             .replace(/&lt;/g, '<')
             .replace(/&gt;/g, '>')
             .replace(/&quot;/g, '"')
             .replace(/&#39;/g, "'");
  text = text.replace(/\n{3,}/g, '\n\n');
  text = text.replace(/ {2,}/g, ' ');
  return text.trim();
}

export class EmailTriageSkill {
  private readonly llmService: LLMServiceInterface;

  constructor(llmService: LLMServiceInterface) {
    this.llmService = llmService;
    console.log("EmailTriageSkill initialized with LLMService.");
  }

  public async execute(email: EmailObject): Promise<TriageResult> {
    console.log(`[EmailTriageSkill] Processing email ID: ${email.id} from: ${email.sender} with subject: "${email.subject}"`);

    if (!email || !email.id || !email.subject || !email.body) {
      throw new Error("Invalid email object provided. Essential fields (id, subject, body) are missing.");
    }
    console.log(`[EmailTriageSkill] Email validated: ${email.id}`);

    let processedBody = email.body;
    const isHtml = /<([a-z][a-z0-9]*)\b[^>]*>/i.test(email.body);
    if (isHtml) {
      processedBody = _stripHtml(email.body);
      console.log("[EmailTriageSkill] HTML detected; stripped to plain text.");
    } else {
      console.log("[EmailTriageSkill] Email body appears to be plain text.");
    }

    // 1. Determine Category (LLM-based)
    let determinedCategory: EmailCategory = 'Other';
    let categoryConfidence = 0.2;
    const categorizationData: EmailCategorizationData = {
        subject: email.subject,
        bodySnippet: processedBody.substring(0, 250)
    };
    const structuredCategorizationPrompt: StructuredLLMPrompt = {
        task: 'categorize_email',
        data: categorizationData
    };
    try {
      const llmResponse = await this.llmService.generate(structuredCategorizationPrompt, 'cheapest');
      if (llmResponse.success && llmResponse.content) {
        const parsedResponse = JSON.parse(llmResponse.content);
        const validCategories: EmailCategory[] = ['Urgent', 'ActionRequired', 'FYI', 'Spam', 'MeetingInvite', 'Other'];
        if (parsedResponse && parsedResponse.category && validCategories.includes(parsedResponse.category) && typeof parsedResponse.confidence === 'number') {
          determinedCategory = parsedResponse.category;
          categoryConfidence = parsedResponse.confidence;
        } else {
          console.warn(`[EmailTriageSkill] LLM category response invalid structure. Defaulting. Resp: ${llmResponse.content}`);
        }
      } else {
         console.error(`[EmailTriageSkill] LLM category call failed. Error: ${llmResponse.error}`);
      }
    } catch (error: any) {
      console.error('[EmailTriageSkill] Error processing LLM category response:', error.message);
    }
    console.log(`[EmailTriageSkill] LLM Category: ${determinedCategory}, Confidence: ${categoryConfidence.toFixed(2)}`);

    // 2. Calculate Priority Score (Rule-based)
    let calculatedPriorityScore = 0;
    switch (determinedCategory) {
      case 'Urgent': calculatedPriorityScore = 9; break;
      case 'ActionRequired': calculatedPriorityScore = 7; break;
      case 'MeetingInvite': calculatedPriorityScore = 6; break;
      case 'FYI': calculatedPriorityScore = 3; break;
      default: calculatedPriorityScore = 2;
    }
    if (determinedCategory === 'Spam') calculatedPriorityScore = 0;

    const senderEmailMatch = email.sender.toLowerCase().match(/<([^>]+)>/);
    const actualSender = senderEmailMatch ? senderEmailMatch[1] : email.sender.toLowerCase();
    if (IMPORTANT_SENDERS.includes(actualSender)) {
      calculatedPriorityScore = Math.min(10, calculatedPriorityScore + 2);
    }
    if (email.headers?.Importance?.toLowerCase() === 'high' || email.headers?.['X-Priority']?.startsWith('1')) {
      calculatedPriorityScore = Math.min(10, calculatedPriorityScore + 1);
    }
    console.log(`[EmailTriageSkill] Priority Score: ${calculatedPriorityScore}`);

    // 3. Generate Summary (LLM-based)
    let generatedSummary = `Subject: "${email.subject}". Body: ${processedBody.substring(0,150)}...`; // Fallback
    const summarizationData: EmailSummarizationData = {
        subject: email.subject,
        bodySnippet: processedBody.substring(0, 500)
    };
    const structuredSummaryPrompt: StructuredLLMPrompt = { task: 'summarize_email', data: summarizationData };
    try {
      const llmResponse = await this.llmService.generate(structuredSummaryPrompt, 'cheapest');
      if (llmResponse.success && llmResponse.content && !llmResponse.content.toLowerCase().startsWith("llm fallback")) {
        generatedSummary = llmResponse.content;
      } else {
         console.warn(`[EmailTriageSkill] LLM summary failed or fallback: ${llmResponse.error || llmResponse.content}. Using basic snippet.`);
      }
    } catch (error: any) {
      console.error('[EmailTriageSkill] Error in LLM summarization:', error.message);
    }
    console.log(`[EmailTriageSkill] Summary: ${generatedSummary}`);

    // 4. Extract Action Items (LLM-based)
    let foundActionItems: string[] = [];
    const actionExtractionData: EmailActionExtractionData = { emailBody: processedBody.substring(0, 1000) };
    const structuredActionItemPrompt: StructuredLLMPrompt = { task: 'extract_actions_email', data: actionExtractionData };
    try {
      const llmResponse = await this.llmService.generate(structuredActionItemPrompt, 'cheapest');
      if (llmResponse.success && llmResponse.content) {
        const parsedResponse = JSON.parse(llmResponse.content);
        if (parsedResponse && Array.isArray(parsedResponse.actionItems)) {
          foundActionItems = parsedResponse.actionItems.filter((item: any): item is string => typeof item === 'string');
        } else if (typeof llmResponse.content === 'string' && !llmResponse.content.toLowerCase().startsWith("llm fallback") && !llmResponse.content.startsWith("{")) {
           foundActionItems = [llmResponse.content];
        } else {
             console.warn(`[EmailTriageSkill] LLM action items response invalid structure: ${llmResponse.content}`);
        }
      } else {
         console.warn(`[EmailTriageSkill] LLM action item extraction failed: ${llmResponse.error || llmResponse.content}`);
      }
    } catch (error: any) {
      console.error('[EmailTriageSkill] Error in LLM action extraction:', error.message);
    }
    if (foundActionItems.length > 0) console.log(`[EmailTriageSkill] Action Items:`, foundActionItems);

    // 5. Suggest Reply (LLM-based)
    let suggestedReplyMessage: string | undefined = undefined;
    const replyData: EmailReplySuggestionData = {
        category: determinedCategory,
        subject: email.subject,
        summary: generatedSummary,
        actionItems: foundActionItems.length > 0 ? foundActionItems : undefined
    };
    const structuredReplyPrompt: StructuredLLMPrompt = { task: 'suggest_reply_email', data: replyData };
    try {
      const llmResponse = await this.llmService.generate(structuredReplyPrompt, 'cheapest');
      if (llmResponse.success && llmResponse.content && llmResponse.content.trim().toLowerCase() !== "no reply needed." && !llmResponse.content.toLowerCase().startsWith("llm fallback")) {
        suggestedReplyMessage = llmResponse.content.trim();
      } else {
         console.log(`[EmailTriageSkill] LLM indicated no reply needed or fallback for reply. Error: ${llmResponse.error || 'No content'}`);
      }
    } catch (error: any) {
      console.error('[EmailTriageSkill] Error in LLM reply suggestion:', error.message);
    }
    if(suggestedReplyMessage) console.log(`[EmailTriageSkill] Suggested Reply: "${suggestedReplyMessage}"`);

    // Construct and return TriageResult
    const result: TriageResult = {
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
