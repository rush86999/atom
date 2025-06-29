// Mock LLM function - to be used by multiple skills

export type LLMTaskType =
  | 'categorize_email'
  | 'summarize_email'
  | 'suggest_reply_email'
  | 'extract_actions_email'
  | 'classify_guidance_query'
  | 'answer_from_text'
  | 'extract_steps_from_text'
  | 'summarize_for_explanation'
  | 'generate_followup_suggestions'
  | 'extract_document_snippets'
  | 'summarize_document_snippets'
  | 'summarize_overall_answer';

// --- Data Payloads for specific tasks ---
export interface EmailCategorizationData { subject: string; bodySnippet: string; }
export interface EmailSummarizationData { subject: string; bodySnippet: string; }
export interface EmailReplySuggestionData {
    category: string;
    subject: string;
    summary: string;
    actionItems?: string[];
}
export interface EmailActionExtractionData { emailBody: string; }

export interface GuidanceQueryClassificationData { query: string; }
export interface AnswerFromTextData { query: string; textContent: string; articleTitle?: string; }
export interface StepsFromTextData { query: string; textContent: string; articleTitle?: string; }
export interface ExplanationData { query: string; textContent: string; articleTitle?: string; }
export interface FollowupSuggestionData { query: string; articleTitle?: string; }

export interface DocumentSnippetData { query: string; documentTitle: string; documentText: string; snippetLength?: number; }
export interface DocumentSummaryData { query: string; documentTitle: string; snippets?: string[]; documentText?: string; targetLength?: string; }
export interface OverallSummaryData { query: string; individualSummaries: {title?: string, summary?: string}[] }


export interface StructuredLLMPrompt {
  task: LLMTaskType;
  data: any;
}

/**
 * Simulates a call to a Large Language Model using a structured prompt.
 * Behavior is based on the task in the structured prompt.
 * @param structuredPrompt The structured prompt object.
 * @param model The model identifier (e.g., 'cheapest', 'balanced', 'powerful').
 * @returns A Promise resolving to the LLM's string response.
 */
export async function invokeLLM(structuredPrompt: StructuredLLMPrompt, model: string): Promise<string> {
  console.log(`[Mock LLM Utility] Received task "${structuredPrompt.task}" for model "${model}". Data (keys): ${Object.keys(structuredPrompt.data || {}).join(', ')}`);

  switch (structuredPrompt.task) {
    case 'categorize_email': {
      const data = structuredPrompt.data as EmailCategorizationData;
      const textForCat = `${data.subject} ${data.bodySnippet}`.toLowerCase();
      if (textForCat.includes("urgent") || textForCat.includes("critical system outage")) {
        return JSON.stringify({ category: "Urgent", confidence: Math.random() * 0.2 + 0.8 });
      } else if (textForCat.includes("action required") || textForCat.includes("please review") || textForCat.includes("task for you")) {
        return JSON.stringify({ category: "ActionRequired", confidence: Math.random() * 0.2 + 0.75 });
      } else if (textForCat.includes("meeting invite") || textForCat.includes("calendar invite") || data.subject.toLowerCase().endsWith(".ics")) {
        return JSON.stringify({ category: "MeetingInvite", confidence: 0.95 });
      } else if (textForCat.includes("fyi") || textForCat.includes("update on") || textForCat.includes("heads up")) {
        return JSON.stringify({ category: "FYI", confidence: 0.78 });
      } else if (textForCat.includes("win a free") || textForCat.includes("limited time offer")) { // Basic spam check
          return JSON.stringify({ category: "Spam", confidence: 0.99 });
      }
      return JSON.stringify({ category: "Other", confidence: Math.random() * 0.3 + 0.3 });
    }
    case 'summarize_email': {
      const data = structuredPrompt.data as EmailSummarizationData;
      return `LLM Summary: Key information from "${data.subject}" suggests it's about [topic derived from body: ${data.bodySnippet.substring(0,30)}...] and requires [action/attention].`;
    }
    case 'suggest_reply_email': {
      const data = structuredPrompt.data as EmailReplySuggestionData;
      if (data.category === "Urgent") {
        return "Acknowledged. We are looking into this with high priority and will update you shortly.";
      } else if (data.category === "ActionRequired") {
        if (data.actionItems && data.actionItems.length > 0) {
          return `Understood. I will address the action items, starting with: "${data.actionItems[0]}".`;
        }
        return "Received. I'll take care of the necessary actions.";
      } else if (data.category === "MeetingInvite") {
        return "Thanks for the invite! I'll check my availability and respond through the calendar system.";
      } else if (data.category === "FYI" || data.category === "Spam") {
        return "No reply needed.";
      }
      return `Thank you for your email regarding "${data.subject}". I will review it.`;
    }
    case 'extract_actions_email': {
      const data = structuredPrompt.data as EmailActionExtractionData;
      const bodyLower = data.emailBody.toLowerCase();
      const extractedActions: string[] = [];
      if (bodyLower.includes("please send the report") || bodyLower.includes("can you prepare the document")) {
        extractedActions.push("Send the report", "Prepare the document");
      }
      if (bodyLower.includes("schedule a meeting") && bodyLower.includes("discuss the proposal")) {
        extractedActions.push("Schedule a meeting to discuss the proposal");
      }
      if (bodyLower.includes("confirm your availability")) {
        extractedActions.push("Confirm availability");
      }
      if (bodyLower.includes("let me know what you think")) {
        extractedActions.push("Provide feedback or thoughts.");
      }
      return JSON.stringify({ actionItems: extractedActions.slice(0,2) });
    }
    case 'extract_document_snippets': {
        const data = structuredPrompt.data as DocumentSnippetData;
        const queryWords = data.query.toLowerCase().split(" ").filter(w => w.length > 2);
        if (queryWords.some(qw => data.documentText.toLowerCase().includes(qw))) {
             return JSON.stringify({ snippets: [`Mock snippet about "${data.query}" from "${data.documentTitle}".`, `Further details on "${data.query}" from the document.`] });
        }
        return JSON.stringify({ snippets: [] });
    }
    case 'summarize_document_snippets': {
        const data = structuredPrompt.data as DocumentSummaryData;
        return `This is a mock ${data.targetLength || 'medium'} summary regarding "${data.query}" from "${data.documentTitle}", based on provided snippets.`;
    }
    case 'summarize_overall_answer': {
        const data = structuredPrompt.data as OverallSummaryData;
        return `This is an overall synthesized mock summary for the query "${data.query}", based on ${data.individualSummaries.length} pieces of information.`;
    }
    case 'classify_guidance_query': {
        const data = structuredPrompt.data as GuidanceQueryClassificationData;
        const queryLower = data.query.toLowerCase();
        if (queryLower.includes("how to") || queryLower.includes("steps for") || queryLower.includes("tutorial for")) {
          return JSON.stringify({ guidanceType: "find_tutorial" });
        } else if (queryLower.includes("what is") || queryLower.includes("explain") || queryLower.includes("tell me about")) {
          return JSON.stringify({ guidanceType: "general_explanation" });
        } else if (queryLower.includes("guide me through") || queryLower.includes("workflow for")) {
          return JSON.stringify({ guidanceType: "guide_workflow" });
        }
        return JSON.stringify({ guidanceType: "answer_question" });
    }
    case 'answer_from_text': {
        const data = structuredPrompt.data as AnswerFromTextData;
        const queryWords = data.query.toLowerCase().split(/\s+/).filter(w => w.length > 2);
        if (queryWords.some(qw => data.textContent.toLowerCase().includes(qw))) {
          return `Based on "${data.articleTitle || 'the text'}", the answer to '${data.query}' is [mocked detail: ${data.textContent.substring(0, 70)}...].`;
        }
        return `The provided text from "${data.articleTitle || 'the document'}" does not appear to contain a direct answer to your question about '${data.query}'.`;
    }
    case 'extract_steps_from_text': {
        const data = structuredPrompt.data as StepsFromTextData;
        const contentLower = data.textContent.toLowerCase();
        if (contentLower.includes("step 1") || contentLower.includes("firstly") || contentLower.includes("1.")) {
          return JSON.stringify({ steps: [{title: "Mock Step 1: Initialize", description: `Based on "${data.articleTitle}", first initialize the system.`}, {title: "Mock Step 2: Configure", description: `Then, configure relevant parameters for "${data.query}".`}] });
        }
        return JSON.stringify({ steps: [] });
    }
    case 'summarize_for_explanation': {
        const data = structuredPrompt.data as ExplanationData;
        return `This is a mock explanation regarding '${data.query}'. The article "${data.articleTitle}" mentions '${data.textContent.substring(0,50)}...' and covers key aspects.`;
    }
    case 'generate_followup_suggestions': {
        const data = structuredPrompt.data as FollowupSuggestionData;
        return JSON.stringify({ suggestions: [`Explore advanced features for "${data.articleTitle || data.query}"`, `Find related tutorials on similar topics.`] });
    }
    default:
      console.warn(`[Mock LLM Utility] Unhandled task type: ${structuredPrompt.task}`);
      return "LLM fallback response: Unable to process this specific type of request.";
  }
}
