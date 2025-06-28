import { invokeLLM } from '../lib/llmUtils';

/**
 * Represents an incoming email message.
 */
export interface EmailObject {
  id: string;
  sender: string; // e.g., "John Doe <john.doe@example.com>" or "internal-alerts@example.com"
  recipients: string[]; // List of recipient addresses/names
  subject: string;
  body: string; // Can be plain text or HTML content
  receivedDate: Date;
  headers?: Record<string, string>; // Optional: For specific mail headers like 'Importance', 'X-Priority'
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
  confidence?: number; // Confidence score (0.0 to 1.0) for the assigned category
  summary?: string; // A brief summary of the email content
  suggestedReply?: string; // A short suggested reply, if applicable
  priorityScore?: number; // A numerical priority (e.g., 1-10, higher is more important)
  extractedActionItems?: string[]; // Any specific action items identified in the email
  // Could also include entities like mentioned people, dates, organizations etc.
}

// Define keyword sets for categorization (No longer primarily used for categorization, but might be useful for other heuristics or priority)
const URGENT_KEYWORDS = ["urgent", "critical", "immediate", "action now", "down", "outage"];
const ACTION_KEYWORDS = ["action required", "please review", "task for you", "can you look into", "needs your attention", "respond by", "deadline"];
const MEETING_KEYWORDS = ["meeting invite", "calendar invite", "invitation:", "scheduled:", "zoom link", "teams meeting", ".ics"];
const FYI_KEYWORDS = ["fyi", "heads up", "update", "information only", "newsletter", "announcement"];
const SPAM_KEYWORDS = ["win a free", "limited time offer", "cialis", "viagra", "unsubscribe here", "claim your prize", "$$$"];

// Define a list of important senders (lowercase for easier matching)
const IMPORTANT_SENDERS = ["boss@example.com", "ceo@example.com", "directreport@example.com", "importantclient@example.com"];

// Define phrases for action item extraction (Commented out as LLM now handles this)
// const ACTION_PHRASES = ['please', 'can you', 'could you', 'action:', 'task:', 'needed:', 'required:', 'to do:', 'ensure that', 'confirm if'];
// const QUESTION_ACTION_VERBS = ['send', 'provide', 'do', 'create', 'organize', 'schedule', 'confirm', 'clarify', 'find', 'update', 'check', 'get'];

// Helper function to strip basic HTML
function _stripHtml(htmlString: string): string {
  let text = htmlString;
  // Replace block-level tags that usually imply newlines
  text = text.replace(/<\/(p|div|h[1-6]|li|dt|dd|pre|blockquote|address|header|footer|section|article)>/gi, '\n');
  text = text.replace(/<br\s*\/?>/gi, '\n');
  // Replace li and dd with a bullet point for better readability
  text = text.replace(/<li[^>]*>/gi, '\n* ');
  text = text.replace(/<dd[^>]*>/gi, '\n  '); // Indent definition descriptions

  // Remove all other HTML tags
  text = text.replace(/<[^>]+>/g, '');

  // Decode common HTML entities
  text = text.replace(/&nbsp;/g, ' ')
             .replace(/&amp;/g, '&')
             .replace(/&lt;/g, '<')
             .replace(/&gt;/g, '>')
             .replace(/&quot;/g, '"')
             .replace(/&#39;/g, "'");
             // Add more entities as needed: &apos; &cent; &pound; &yen; &euro; &copy; &reg;

  // Normalize multiple newlines and spaces
  text = text.replace(/\n{3,}/g, '\n\n'); // Max two consecutive newlines
  text = text.replace(/ {2,}/g, ' ');    // Max one space

  return text.trim();
}


/**
 * Skill to triage and prioritize incoming emails.
 */
export class EmailTriageSkill {
  constructor() {
    // Initialization for the skill, e.g., loading models, configuration, etc.
    console.log("EmailTriageSkill initialized.");
  }

  /**
   * Executes the email triage process.
   * @param email The EmailObject to process.
   * @returns A Promise resolving to the TriageResult.
   */
  public async execute(email: EmailObject): Promise<TriageResult> {
    console.log(`[EmailTriageSkill] Processing email ID: ${email.id} from: ${email.sender} with subject: "${email.subject}"`);

    // 1. Validate email input (Basic check for now)
    if (!email || !email.id || !email.subject || !email.body) {
      throw new Error("Invalid email object provided. Essential fields (id, subject, body) are missing.");
    }
    console.log(`[EmailTriageSkill] Email validated: ${email.id}`);

    // Pre-process body: Strip HTML if necessary
    let processedBody = email.body;
    const isHtml = /<([a-z][a-z0-9]*)\b[^>]*>/i.test(email.body);
    if (isHtml) {
      processedBody = _stripHtml(email.body);
      console.log("[EmailTriageSkill] HTML detected in email body; stripped to plain text for processing.");
    } else {
      console.log("[EmailTriageSkill] Email body appears to be plain text.");
    }

    // 2. Determine Category (LLM-based)
    let determinedCategory: EmailCategory = 'Other';
    let categoryConfidence = 0.2;

    const bodySnippetForCategorization = processedBody.substring(0, 250);
    const categorizationPrompt = `
      Given the following email details:
      Subject: "${email.subject}"
      Body (first ${bodySnippetForCategorization.length} chars): "${bodySnippetForCategorization}..."

      Categorize this email into one of the following categories:
      'Urgent', 'ActionRequired', 'FYI', 'Spam', 'MeetingInvite', 'Other'.
      Return ONLY the category and a confidence score (0.0-1.0) in a valid JSON format, like:
      {"category": "CATEGORY_NAME", "confidence": 0.X}
    `;

    try {
      const llmCategoryResponse = await invokeLLM(categorizationPrompt, 'cheapest');
      console.log(`[EmailTriageSkill] LLM category response string: ${llmCategoryResponse}`);
      const parsedResponse = JSON.parse(llmCategoryResponse);

      if (parsedResponse && parsedResponse.category && typeof parsedResponse.confidence === 'number') {
        const potentialCategory = parsedResponse.category as EmailCategory;
        const validCategories: EmailCategory[] = ['Urgent', 'ActionRequired', 'FYI', 'Spam', 'MeetingInvite', 'Other'];
        if (validCategories.includes(potentialCategory)) {
          determinedCategory = potentialCategory;
          categoryConfidence = parsedResponse.confidence;
        } else {
          console.warn(`[EmailTriageSkill] LLM returned an invalid category: ${parsedResponse.category}. Defaulting to 'Other'.`);
          determinedCategory = 'Other';
          categoryConfidence = 0.25;
        }
      } else {
        console.error('[EmailTriageSkill] LLM category response parsing error or invalid structure. Response:', llmCategoryResponse);
      }
    } catch (error) {
      console.error('[EmailTriageSkill] Error calling or parsing LLM category response:', error);
    }
    console.log(`[EmailTriageSkill] LLM-determined category: ${determinedCategory} with confidence ${categoryConfidence.toFixed(2)}`);

    // 3. Calculate Priority Score (Rule-based, using LLM category)
    let calculatedPriorityScore = 0;
    switch (determinedCategory) {
      case 'Urgent': calculatedPriorityScore = 9; break;
      case 'ActionRequired': calculatedPriorityScore = 7; break;
      case 'MeetingInvite': calculatedPriorityScore = 6; break;
      case 'FYI': calculatedPriorityScore = 3; break;
      case 'Other': calculatedPriorityScore = 2; break;
      case 'Spam': calculatedPriorityScore = 0; break;
      default: calculatedPriorityScore = 1;
    }

    const senderLower = email.sender.toLowerCase();
    const emailMatch = senderLower.match(/<([^>]+)>/);
    const actualSenderEmail = emailMatch ? emailMatch[1] : senderLower;

    if (IMPORTANT_SENDERS.includes(actualSenderEmail)) {
      calculatedPriorityScore = Math.min(10, calculatedPriorityScore + 2);
      console.log(`[EmailTriageSkill] Priority boosted due to important sender: ${email.sender}`);
    }
    if (email.headers?.Importance?.toLowerCase() === 'high' || email.headers?.['X-Priority']?.startsWith('1')) {
      calculatedPriorityScore = Math.min(10, calculatedPriorityScore + 1);
      console.log(`[EmailTriageSkill] Priority boosted due to high importance header.`);
    }
    console.log(`[EmailTriageSkill] Calculated priority score: ${calculatedPriorityScore}`);

    // 4. Generate Summary (LLM-based)
    let generatedSummary = "";
    const bodySnippetForSummary = processedBody.substring(0, 500);
    const summaryPrompt = `Summarize this email in 1-2 sentences: Subject: "${email.subject}" Body: "${bodySnippetForSummary}..." Return only the summary text.`;
    try {
        const llmSummaryResponse = await invokeLLM(summaryPrompt, 'cheapest');
        console.log(`[EmailTriageSkill] LLM summary response: ${llmSummaryResponse}`);
        if (llmSummaryResponse && !llmSummaryResponse.toLowerCase().startsWith("llm fallback response")) {
            generatedSummary = llmSummaryResponse;
        } else {
            console.warn("[EmailTriageSkill] LLM summary failed or returned fallback, using basic snippet.");
            const normalizedBodyForFallback = processedBody.replace(/\s+/g, " ").trim();
            generatedSummary = `Subject: "${email.subject}". Body excerpt: "${normalizedBodyForFallback.substring(0, 150)}..."`;
        }
    } catch (error) {
        console.error('[EmailTriageSkill] Error calling LLM for summary:', error);
        const normalizedBodyForFallback = processedBody.replace(/\s+/g, " ").trim();
        generatedSummary = `Subject: "${email.subject}". Body excerpt: "${normalizedBodyForFallback.substring(0, 150)}..."`;
    }
    console.log(`[EmailTriageSkill] Final generated summary: ${generatedSummary}`);

    // 6. Extract Action Items (LLM-based) - Done *before* reply suggestion to inform it
    let foundActionItems: string[] = [];
    const bodyForActionExtraction = processedBody.substring(0, 1000);
    const actionItemPrompt = `
      Review the following email body and extract any distinct action items or tasks requested of the recipient.
      Return these as a JSON array of strings, like: {"actionItems": ["Action 1", "Action 2"]}.
      If no specific action items are found, return {"actionItems": []}.

      Email Body:
      "${bodyForActionExtraction}..."
    `;
    try {
      const llmActionItemsResponse = await invokeLLM(actionItemPrompt, 'cheapest');
      console.log(`[EmailTriageSkill] LLM action items response: ${llmActionItemsResponse}`);
      const parsedResponse = JSON.parse(llmActionItemsResponse);
      if (parsedResponse && Array.isArray(parsedResponse.actionItems)) {
        foundActionItems = parsedResponse.actionItems.filter((item: any): item is string => typeof item === 'string');
         if (foundActionItems.length > 0) {
            console.log(`[EmailTriageSkill] LLM extracted action items:`, foundActionItems);
        } else {
            console.log(`[EmailTriageSkill] LLM found no specific action items.`);
        }
      } else {
        if (typeof llmActionItemsResponse === 'string' && llmActionItemsResponse.length > 0 && !llmActionItemsResponse.toLowerCase().startsWith("llm fallback") && !llmActionItemsResponse.startsWith("{")) {
            console.warn('[EmailTriageSkill] LLM action items response was not JSON array, treating as single string action item.');
            foundActionItems = [llmActionItemsResponse];
            console.log(`[EmailTriageSkill] LLM extracted single action item (from string):`, foundActionItems);
        } else {
            console.warn('[EmailTriageSkill] LLM action items response parsing error or invalid structure. Response:', llmActionItemsResponse);
        }
      }
    } catch (error) {
      console.error('[EmailTriageSkill] Error calling or parsing LLM for action items:', error);
    }

    // 5. Suggest Reply (LLM-based, now informed by extracted action items)
    let suggestedReplyMessage: string | undefined = undefined;
    const actionItemsText = foundActionItems.length > 0 ? `Identified Action Items: "${foundActionItems.join('; ')}"` : "";
    const replyPrompt = `
      Given an email with the following details:
      Category: "${determinedCategory}"
      Subject: "${email.subject}"
      Summary: "${generatedSummary}"
      ${actionItemsText}

      Suggest a brief, polite, and professional reply for this email.
      If no reply is typically needed for this category or content (e.g., for Spam or some FYI), return the exact phrase "No reply needed.".
      Otherwise, provide only the suggested reply text.
    `;
    try {
      const llmReply = await invokeLLM(replyPrompt, 'cheapest');
      console.log(`[EmailTriageSkill] LLM raw reply: "${llmReply}"`);
      if (llmReply && llmReply.trim().toLowerCase() !== "no reply needed." && !llmReply.toLowerCase().startsWith("llm fallback response")) {
        suggestedReplyMessage = llmReply.trim();
        console.log(`[EmailTriageSkill] LLM suggested reply: "${suggestedReplyMessage}"`);
      } else {
        console.log(`[EmailTriageSkill] LLM indicated no reply needed or fallback response for reply generation.`);
        suggestedReplyMessage = undefined;
      }
    } catch (error) {
      console.error('[EmailTriageSkill] Error calling LLM for suggested reply:', error);
      suggestedReplyMessage = undefined;
    }

    // 7. Construct and return TriageResult
    const result: TriageResult = {
      emailId: email.id,
      category: determinedCategory,
      confidence: parseFloat(categoryConfidence.toFixed(2)),
      priorityScore: calculatedPriorityScore,
      summary: generatedSummary,
      suggestedReply: suggestedReplyMessage,
      extractedActionItems: foundActionItems.length > 0 ? foundActionItems : undefined,
    };

    console.log(`[EmailTriageSkill] Triage complete for email ID: ${email.id}. Category: ${result.category}, Priority: ${result.priorityScore}, Confidence: ${result.confidence}, Actions: ${foundActionItems.length}`);
    return result;
  }
}

// Example Usage (for testing or demonstration, typically called by an orchestrator)
/*
async function testEmailTriageSkill() {
  const skill = new EmailTriageSkill();
  const testEmail: EmailObject = {
    id: "test-email-001",
    sender: "Alice <alice@example.com>",
    recipients: ["bob@example.com", "currentUser@example.com"],
    subject: "Quick question about the Phoenix project",
    body: "Hi team, I had a quick question regarding the latest update on the Phoenix project. Can someone point me to the documentation for the new auth module? Thanks!",
    receivedDate: new Date(),
    headers: { "X-Priority": "3" }
  };

  try {
    const result = await skill.execute(testEmail);
    console.log("\\n--- Email Triage Result ---");
    console.log(JSON.stringify(result, null, 2));
  } catch (error) {
    console.error("Error during EmailTriageSkill execution:", error);
  }

  const urgentEmail: EmailObject = {
    id: "urgent-email-002",
    sender: "boss@example.com",
    recipients: ["currentUser@example.com"],
    subject: "URGENT: Action Required - System Outage",
    body: "Team, we have a critical system outage affecting all customers. All hands on deck. Please join the emergency bridge now: conf-link. This requires your immediate action.",
    receivedDate: new Date(),
    headers: { "Importance": "High" }
  };

  try {
    const resultUrgent = await skill.execute(urgentEmail);
    console.log("\\n--- Urgent Email Triage Result ---");
    console.log(JSON.stringify(resultUrgent, null, 2));
  } catch (error) {
    console.error("Error during Urgent EmailTriageSkill execution:", error);
  }
}

// testEmailTriageSkill();
*/
