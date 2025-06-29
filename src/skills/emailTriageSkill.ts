import {
    invokeLLM,
    StructuredLLMPrompt,
    EmailCategorizationData,
    EmailSummarizationData,
    EmailReplySuggestionData,
    EmailActionExtractionData,
    LLMTaskType // Assuming LLMTaskType is also exported from llmUtils
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

// Define a list of important senders (lowercase for easier matching)
const IMPORTANT_SENDERS = ["boss@example.com", "ceo@example.com", "directreport@example.com", "importantclient@example.com"];

// Helper function to strip basic HTML
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

/**
 * Skill to triage and prioritize incoming emails.
 */
export class EmailTriageSkill {
  constructor() {
    console.log("EmailTriageSkill initialized.");
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
      const llmCategoryResponse = await invokeLLM(structuredCategorizationPrompt, 'cheapest');
      const parsedResponse = JSON.parse(llmCategoryResponse);
      const validCategories: EmailCategory[] = ['Urgent', 'ActionRequired', 'FYI', 'Spam', 'MeetingInvite', 'Other'];
      if (parsedResponse && parsedResponse.category && validCategories.includes(parsedResponse.category) && typeof parsedResponse.confidence === 'number') {
        determinedCategory = parsedResponse.category;
        categoryConfidence = parsedResponse.confidence;
      } else {
        console.warn(`[EmailTriageSkill] LLM category response invalid. Defaulting. Resp: ${llmCategoryResponse}`);
      }
    } catch (error) {
      console.error('[EmailTriageSkill] Error in LLM categorization:', error);
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
      const llmSummaryResponse = await invokeLLM(structuredSummaryPrompt, 'cheapest');
      if (llmSummaryResponse && !llmSummaryResponse.toLowerCase().startsWith("llm fallback")) {
        generatedSummary = llmSummaryResponse;
      } else {
         console.warn(`[EmailTriageSkill] LLM summary failed or fallback. Using basic snippet.`);
      }
    } catch (error) {
      console.error('[EmailTriageSkill] Error in LLM summarization:', error);
    }
    console.log(`[EmailTriageSkill] Summary: ${generatedSummary}`);

    // 4. Extract Action Items (LLM-based)
    let foundActionItems: string[] = [];
    const actionExtractionData: EmailActionExtractionData = { emailBody: processedBody.substring(0, 1000) };
    const structuredActionItemPrompt: StructuredLLMPrompt = { task: 'extract_actions_email', data: actionExtractionData };
    try {
      const llmActionItemsResponse = await invokeLLM(structuredActionItemPrompt, 'cheapest');
      const parsedResponse = JSON.parse(llmActionItemsResponse);
      if (parsedResponse && Array.isArray(parsedResponse.actionItems)) {
        foundActionItems = parsedResponse.actionItems.filter((item: any): item is string => typeof item === 'string');
      } else if (typeof llmActionItemsResponse === 'string' && !llmActionItemsResponse.toLowerCase().startsWith("llm fallback") && !llmActionItemsResponse.startsWith("{")) {
         foundActionItems = [llmActionItemsResponse]; // Single string action item
      }
    } catch (error) {
      console.error('[EmailTriageSkill] Error in LLM action extraction:', error);
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
      const llmReply = await invokeLLM(structuredReplyPrompt, 'cheapest');
      if (llmReply && llmReply.trim().toLowerCase() !== "no reply needed." && !llmReply.toLowerCase().startsWith("llm fallback")) {
        suggestedReplyMessage = llmReply.trim();
      }
    } catch (error) {
      console.error('[EmailTriageSkill] Error in LLM reply suggestion:', error);
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
async function testEmailTriageSkill() {
  const skill = new EmailTriageSkill();
  const testEmails: EmailObject[] = [
    { id: "email1", sender: "urgent@example.com", recipients: ["me@example.com"], subject: "URGENT HELP NEEDED NOW!", body: "The server is down and we need immediate assistance. Please call me ASAP.", receivedDate: new Date(), headers: {Importance: "High"} },
    { id: "email2", sender: "taskmaster@example.com", recipients: ["me@example.com"], subject: "Action Required: Update project status", body: "Please update the project status report by EOD. Also, can you prepare the slides for tomorrow's meeting?", receivedDate: new Date() },
    { id: "email3", sender: "calendar@example.com", recipients: ["me@example.com"], subject: "Meeting Invite: Q4 Planning", body: "You are invited to Q4 Planning. When: Tomorrow 10 AM. Where: Conference Room A. Details: BEGIN:VCALENDAR...", receivedDate: new Date() },
    { id: "email4", sender: "info@example.com", recipients: ["me@example.com"], subject: "FYI: Company picnic next month", body: "Just a heads up, the annual company picnic is scheduled for next month. More details to follow.", receivedDate: new Date() },
    { id: "email5", sender: "spamking@example.com", recipients: ["me@example.com"], subject: "Win a FREE iPhone now!", body: "Click here to claim your prize, limited time offer!", receivedDate: new Date() },
    { id: "email6", sender: "alice@example.com", recipients: ["me@example.com"], subject: "Quick question", body: "Hey, just had a quick question about the report. Nothing urgent. Thanks", receivedDate: new Date() },
  ];

  for (const email of testEmails) {
    try {
      console.log(`\n--- Testing Email ID: ${email.id} ---`);
      const triageResult = await skill.execute(email);
      console.log("Triage Result:", JSON.stringify(triageResult, null, 2));
    } catch (e) {
      console.error("Error testing skill:", e);
    }
  }
}
// testEmailTriageSkill();
*/
