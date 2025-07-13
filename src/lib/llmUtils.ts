// Shared LLM utilities, types, and mock implementations

// Re-export EmailCategory if needed by skills directly, though it's better if skills use their own specific types or generic strings for categories passed to LLM.
// For now, we'll assume skills that need EmailCategory will define/import it themselves or that the string type for category in EmailReplySuggestionData is sufficient.
// import { EmailCategory } from '../skills/emailTriageSkill';

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
  | 'summarize_overall_answer'
  | 'parse_search_query'; // Added for the new NLU filter skill

// --- Data Payloads for specific tasks ---
export interface EmailCategorizationData { subject: string; bodySnippet: string; }
export interface SearchQueryParsingData { rawQuery: string; currentDate: string; } // Added for the new NLU filter skill
export interface EmailSummarizationData { subject: string; bodySnippet: string; }
export interface EmailReplySuggestionData {
    category: string; // Could be more specific like EmailCategory, but string is fine for mock
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
export interface OverallSummaryData { query: string; individualSummaries: {title?: string | undefined, summary?: string | undefined}[] }


export interface StructuredLLMPrompt {
  task: LLMTaskType;
  data: any;
}

export interface LLMServiceResponse {
  success: boolean;
  content?: string;
  error?: string;
  usage?: { promptTokens: number; completionTokens: number; totalTokens: number };
}

export interface LLMServiceInterface {
  generate(prompt: StructuredLLMPrompt, model: string, options?: { temperature?: number; maxTokens?: number }): Promise<LLMServiceResponse>;
}

export class MockLLMService implements LLMServiceInterface {
  public async generate(structuredPrompt: StructuredLLMPrompt, model: string, options?: { temperature?: number; maxTokens?: number }): Promise<LLMServiceResponse> {
    console.log(`[MockLLMService] Received task "${structuredPrompt.task}" for model "${model}". Data keys: ${Object.keys(structuredPrompt.data || {}).join(', ')}`);
    await new Promise(resolve => setTimeout(resolve, Math.random() * 100 + 50));

    try {
      let content: string;
      switch (structuredPrompt.task) {
        case 'categorize_email': {
          const data = structuredPrompt.data as EmailCategorizationData;
          const subjectLower = data.subject.toLowerCase();
          const bodySnippetLower = data.bodySnippet.toLowerCase();
          const textForCat = `${subjectLower} ${bodySnippetLower}`;
          let category: string = "Other"; // Allow string for flexibility in mock
          let confidence: number = parseFloat((Math.random() * 0.3 + 0.3).toFixed(2));

          if (subjectLower.includes("win a free") || textForCat.includes("limited time offer") || textForCat.includes("cialis") || textForCat.includes("viagra")) {
            category = "Spam"; confidence = 0.99;
          } else if (subjectLower.includes("meeting invite") || subjectLower.includes("calendar invite") || subjectLower.endsWith(".ics") || bodySnippetLower.includes("begin:vcalendar")) {
            category = "MeetingInvite"; confidence = 0.95;
          } else if (textForCat.includes("urgent") || textForCat.includes("critical") || textForCat.includes("outage") || textForCat.includes("asap")) {
            category = "Urgent"; confidence = parseFloat((Math.random() * 0.15 + 0.8).toFixed(2));
          } else if (textForCat.includes("action required") || textForCat.includes("please review") || textForCat.includes("task for you") || textForCat.includes("deadline")) {
            category = "ActionRequired"; confidence = parseFloat((Math.random() * 0.2 + 0.7).toFixed(2));
          } else if (textForCat.includes("fyi") || textForCat.includes("heads up") || textForCat.includes("update") || subjectLower.includes("newsletter")) {
            category = "FYI"; confidence = parseFloat((Math.random() * 0.2 + 0.6).toFixed(2));
          } else if (data.bodySnippet.length < 50 && !textForCat.match(/(urgent|action|meeting|spam)/i)) {
            category = Math.random() < 0.5 ? "FYI" : "Other";
            confidence = parseFloat((Math.random() * 0.2 + 0.45).toFixed(2));
          } else if (Math.random() < 0.05) { // Chance of plausible miscategorization
             const cats: string[] = ['ActionRequired', 'FYI', 'Other'];
             category = cats[Math.floor(Math.random() * cats.length)];
             confidence = parseFloat((Math.random() * 0.3 + 0.3).toFixed(2));
          }
          content = JSON.stringify({ category, confidence });
          break;
        }
        case 'summarize_email': {
          const data = structuredPrompt.data as EmailSummarizationData;
          const subject = data.subject.trim();
          const bodySnippet = data.bodySnippet.trim();
          if (bodySnippet.length === 0) content = `The email with subject "${subject}" has no body content.`;
          else if (bodySnippet.length < 70 && !bodySnippet.includes('.')) content = `Subject: "${subject}". Content: "${bodySnippet}"`;
          else {
            const firstSentence = bodySnippet.match(/[^.!?]+[.!?]+/g)?.[0]?.trim() || bodySnippet.substring(0,100);
            content = `Regarding "${subject}", the email mentions: "${firstSentence.substring(0,100)}${firstSentence.length > 100 ? "..." : ""}".`;
          }
          if (subject.toLowerCase().startsWith("re:") || subject.toLowerCase().startsWith("fwd:")) content = `This is part of a thread on "${subject}". ${content}`;
          if (Math.random() < 0.3) content += " Further details might be important.";
          break;
        }
        case 'suggest_reply_email': {
          const data = structuredPrompt.data as EmailReplySuggestionData;
          if (data.category === "Spam" || data.category === "FYI" && Math.random() < 0.7) { // More likely no reply for FYI
            content = "No reply needed.";
          } else if (data.category === "Urgent") {
            content = "Acknowledged. Looking into this with high priority and will update shortly.";
          } else if (data.category === "ActionRequired") {
            content = (data.actionItems && data.actionItems.length > 0) ? `Understood. I will start with: "${data.actionItems[0]}".` : "Received. I'll take care of the necessary actions.";
          } else if (data.category === "MeetingInvite") {
            content = "Thanks for the invite! I'll check my availability and respond via calendar.";
          } else {
            content = `Thank you for your email regarding "${data.subject}". I will review it.`;
          }
          break;
        }
        case 'extract_actions_email': {
          const data = structuredPrompt.data as EmailActionExtractionData;
          const bodyLower = data.emailBody.toLowerCase();
          const actions: string[] = [];
          if (bodyLower.includes("please send") || bodyLower.includes("can you attach")) actions.push("Send/attach requested document.");
          if (bodyLower.includes("schedule a meeting") || bodyLower.includes("set up a call")) actions.push("Schedule a meeting.");
          if (bodyLower.includes("confirm availability") || bodyLower.includes("are you free")) actions.push("Confirm availability for something.");
          if (bodyLower.includes("your thoughts on") || bodyLower.includes("feedback on")) actions.push("Provide feedback/thoughts.");
          content = JSON.stringify({ actionItems: actions.slice(0,2) });
          break;
        }
        case 'extract_document_snippets': {
            const data = structuredPrompt.data as DocumentSnippetData;
            content = JSON.stringify({ snippets: [`Mock snippet for "${data.query}" from "${data.documentTitle}".`, `Another detail regarding "${data.query}".`] });
            break;
        }
        case 'summarize_document_snippets': {
            const data = structuredPrompt.data as DocumentSummaryData;
            content = `This is a mock ${data.targetLength || 'medium'} summary about "${data.query}" from "${data.documentTitle}".`;
            break;
        }
        case 'summarize_overall_answer': {
            const data = structuredPrompt.data as OverallSummaryData;
            content = `Overall mock summary for "${data.query}", combining ${data.individualSummaries.length} sources.`;
            break;
        }
        case 'classify_guidance_query': {
            const data = structuredPrompt.data as GuidanceQueryClassificationData;
            const qL = data.query.toLowerCase();
            if (qL.includes("how to")||qL.includes("steps")) content = JSON.stringify({ guidanceType: "find_tutorial" });
            else if (qL.includes("what is")||qL.includes("explain")) content = JSON.stringify({ guidanceType: "general_explanation" });
            else if (qL.includes("guide")||qL.includes("workflow")) content = JSON.stringify({ guidanceType: "guide_workflow" });
            else content = JSON.stringify({ guidanceType: "answer_question" });
            break;
        }
        case 'answer_from_text': {
            const data = structuredPrompt.data as AnswerFromTextData;
            content = `Mock answer for "${data.query}" from "${data.articleTitle || 'the document'}": ${data.textContent.substring(0,70)}...`;
            break;
        }
        case 'extract_steps_from_text': {
            const data = structuredPrompt.data as StepsFromTextData;
            content = JSON.stringify({ steps: [{title: "Mock Step 1 (from LLM)", description: `Do this first for ${data.query}`}, {title: "Mock Step 2", description: "Then do that."}] });
            break;
        }
        case 'summarize_for_explanation': {
            const data = structuredPrompt.data as ExplanationData;
            content = `Mock explanation of "${data.query}" based on "${data.articleTitle}". It covers...`;
            break;
        }
        case 'generate_followup_suggestions': {
            const data = structuredPrompt.data as FollowupSuggestionData;
            content = JSON.stringify({ suggestions: [`Advanced ${data.articleTitle || data.query}`, "Related Topic B"] });
            break;
        }
        default:
          console.warn(`[MockLLMService] Unhandled task type: ${structuredPrompt.task}`);
          return { success: false, error: `Unhandled task type: ${structuredPrompt.task}` };
      }
      return { success: true, content };
    } catch (error: any) {
      console.error(`[MockLLMService] Error during task ${structuredPrompt.task}:`, error);
      return { success: false, error: error.message || "Unknown error in MockLLMService" };
    }
  }
}

// Stub for a real OpenAI/Groq service
export class OpenAIGroqService_Stub implements LLMServiceInterface {
  private apiKey: string;
  private groqModelName: string;
  private baseURL: string = 'https://api.groq.com/openai/v1'; // Standard Groq OpenAI-compatible endpoint

  constructor(apiKey: string = "YOUR_GROQ_API_KEY_PLACEHOLDER", groqModelName: string = "mixtral-8x7b-32768") {
    this.apiKey = apiKey;
    this.groqModelName = groqModelName;
    if (this.apiKey === "YOUR_GROQ_API_KEY_PLACEHOLDER") {
        console.warn("OpenAIGroqService_Stub: API Key is a placeholder! Real calls will fail.");
    }
    console.log(`OpenAIGroqService_Stub initialized for model ${this.groqModelName}. CAUTION: Real API calls are stubbed out.`);
  }

  // Helper to construct appropriate messages for different tasks
  private _constructMessages(structuredPrompt: StructuredLLMPrompt): any[] {
    let systemMessage = `You are an AI assistant. Perform the task: ${structuredPrompt.task}.`;
    let userMessageContent = `Data: ${JSON.stringify(structuredPrompt.data)}`;

    // Customize system/user messages based on task for better real LLM performance
    switch(structuredPrompt.task) {
        case 'categorize_email':
            const catData = structuredPrompt.data as EmailCategorizationData;
            systemMessage = `Categorize the following email into one of: 'Urgent', 'ActionRequired', 'FYI', 'Spam', 'MeetingInvite', 'Other'. Return ONLY valid JSON: {"category": "CATEGORY_NAME", "confidence": 0.X}`;
            userMessageContent = `Subject: "${catData.subject}"\nBody Snippet: "${catData.bodySnippet}"`;
            break;
        case 'summarize_email':
            const sumData = structuredPrompt.data as EmailSummarizationData;
            systemMessage = "Summarize the following email concisely in 1-2 sentences. Return only the summary text.";
            userMessageContent = `Subject: "${sumData.subject}"\nBody Snippet: "${sumData.bodySnippet}"`;
            break;
        case 'suggest_reply_email':
            const repData = structuredPrompt.data as EmailReplySuggestionData;
            systemMessage = `Suggest a brief, polite, professional reply for this email. If no reply is needed (e.g., Spam, some FYI), return "No reply needed.". Category: ${repData.category}.`;
            userMessageContent = `Subject: "${repData.subject}"\nSummary: "${repData.summary}"\n${repData.actionItems && repData.actionItems.length > 0 ? `Identified Action Items: "${repData.actionItems.join('; ')}"` : ""}`;
            break;
        case 'extract_actions_email':
            const actData = structuredPrompt.data as EmailActionExtractionData;
            systemMessage = `Extract distinct action items from this email body. Return JSON: {"actionItems": ["Action 1", ...]}. If none, return {"actionItems": []}.`;
            userMessageContent = `Email Body: "${actData.emailBody}"`;
            break;
        // Add more cases for other LLMTaskTypes to customize prompts
        case 'extract_document_snippets':
             const snipData = structuredPrompt.data as DocumentSnippetData;
             systemMessage = `Extract up to 3 relevant snippets (each ~${snipData.snippetLength || 150} chars) for the query from the document. Return JSON: {"snippets": ["...", ...]}. If none, return {"snippets": []}.`;
             userMessageContent = `Query: "${snipData.query}"\nDocument Title: "${snipData.documentTitle}"\nDocument Text: "${snipData.documentText}"`;
             break;
        case 'summarize_document_snippets':
            const docSumData = structuredPrompt.data as DocumentSummaryData;
            systemMessage = `Summarize the provided snippets based on the query. Target length: ${docSumData.targetLength || 'medium'}. Return only the summary.`;
            userMessageContent = `Query: "${docSumData.query}"\nDocument Title: "${docSumData.documentTitle}"\nSnippets:\n${(docSumData.snippets || []).map(s => `- ${s}`).join('\n')}`;
            break;
        case 'summarize_overall_answer':
            const overallData = structuredPrompt.data as OverallSummaryData;
            systemMessage = `Combine these individual summaries into one concise overall answer to the user's query. Return only the combined summary.`;
            userMessageContent = `User's Query: "${overallData.query}"\nIndividual Summaries:\n${overallData.individualSummaries.map(s => `From "${s.title}": ${s.summary}`).join('\n---\n')}`;
            break;
        case 'classify_guidance_query':
            const gqClassData = structuredPrompt.data as GuidanceQueryClassificationData;
            systemMessage = `Classify the user query into one of: 'answer_question', 'find_tutorial', 'guide_workflow', 'general_explanation'. Return JSON: {"guidanceType": "TYPE"}.`;
            userMessageContent = `User Query: "${gqClassData.query}"`;
            break;
        case 'answer_from_text':
            const ansTextData = structuredPrompt.data as AnswerFromTextData;
            systemMessage = `Using ONLY the provided text, answer the question. Return only the direct answer.`;
            userMessageContent = `Question: '${ansTextData.query}'\nProvided text from "${ansTextData.articleTitle || 'document'}": '${ansTextData.textContent}'`;
            break;
        case 'extract_steps_from_text':
            const stepsTextData = structuredPrompt.data as StepsFromTextData;
            systemMessage = `Extract key steps for the query from the tutorial text. Return JSON: {"steps": [{"title":"Step Title", "description":"Step desc"}, ...]}. If none, return {"steps": []}.`;
            userMessageContent = `Query: '${stepsTextData.query}'\nTutorial Text from "${stepsTextData.articleTitle || 'document'}": '${stepsTextData.textContent}'`;
            break;
        case 'summarize_for_explanation':
            const explData = structuredPrompt.data as ExplanationData;
            systemMessage = `Provide a concise explanation for the query based on the text. Return only the explanation.`;
            userMessageContent = `Query: '${explData.query}'\nText from "${explData.articleTitle || 'document'}": '${explData.textContent}'`;
            break;
        case 'generate_followup_suggestions':
            const sugData = structuredPrompt.data as FollowupSuggestionData;
            systemMessage = `Given the user query and shown guidance, suggest two distinct, related topics or advanced features. Return JSON: {"suggestions": ["Sugg 1", "Sugg 2"]}. If none, return {"suggestions": []}.`;
            userMessageContent = `User Query: '${sugData.query}'\nGuidance Shown (Title): '${sugData.articleTitle || 'N/A'}'`;
            break;
        case 'parse_search_query':
            const parseData = structuredPrompt.data as SearchQueryParsingData;
            systemMessage = `You are an expert NLU (Natural Language Understanding) parser for a search engine. Your task is to analyze a user's raw search query and convert it into a structured JSON object.

You must identify the following entities from the user's query:

1.  \`search_term\`: The core subject of the search. Remove filler words like "find me", "show me", "search for", etc. Keep the essential keywords.

2.  \`filters\`: An object containing structured filter criteria. You must extract the following filter types:

    *   \`doc_types\`: An array of document types mentioned. The valid types are: \`gdrive_pdf\`, \`gdrive_docx\`, \`gdrive_folder\`, \`gdrive_sheet\`, \`gdrive_slide\`, \`email_snippet\`, \`notion_summary\`, \`document_chunk\`. If a user says "g-drive doc", map it to \`gdrive_docx\`. If they say "pdf" without "gdrive", map to \`document_chunk\`.

    *   \`date_after\` & \`date_before\`: A date range. Today's date is ${parseData.currentDate}. If the user says "last month", calculate the first and last day of the previous month. If they say "this week", calculate the past Monday and upcoming Sunday. If the user says "yesterday", calculate the start and end of the previous day. Always return the date as a full \`YYYY-MM-DD\` string.

    *   \`date_field_to_filter\`: The date field to filter on. Valid fields are \`ingested_at\`, \`created_at_source\`, \`last_modified_source\`. Default to \`ingested_at\` if ambiguous.

    *   \`metadata_properties\`: Key-value pairs like "by <author>". Extract the key (e.g., "author") and the value.

You MUST respond with ONLY a valid JSON object. The JSON object must conform to this structure:
\`\`\`json
{
  "search_term": "string",
  "filters": {
    "doc_types": ["string", ...],
    "date_after": "YYYY-MM-DD",
    "date_before": "YYYY-MM-DD",
    "date_field_to_filter": "string",
    "metadata_properties": { "key": "value", ... }
  }
}
\`\`\`
If a filter is not present, omit its key. If no filters are found, \`filters\` should be an empty object.`;
            userMessageContent = `User Query: "${parseData.rawQuery}"`;
            break;
        default:
            systemMessage = `You are an AI assistant performing task: ${structuredPrompt.task}. Respond appropriately based on the data.`;
            userMessageContent = `Data: ${JSON.stringify(structuredPrompt.data)}`;
            break;
    }
    return [ { role: "system", content: systemMessage }, { role: "user", content: userMessageContent } ];
  }

  public async generate(structuredPrompt: StructuredLLMPrompt, modelNameToUse?: string, options?: {temperature?: number; maxTokens?: number}): Promise<LLMServiceResponse> {
    const targetModel = modelNameToUse || this.groqModelName;
    console.log(`[OpenAIGroqService_Stub] Task: "${structuredPrompt.task}" for model "${targetModel}".`);
    // console.log("[OpenAIGroqService_Stub] Data:", structuredPrompt.data); // Can be verbose
    console.log("[OpenAIGroqService_Stub] THIS IS A STUB. IT WILL NOT MAKE REAL API CALLS YET.");
    console.log("[OpenAIGroqService_Stub] Uncomment and configure the section below with 'openai' package and your API key.");

    const messages = this._constructMessages(structuredPrompt);

    /*
    // ---- BEGIN ACTUAL OPENAI SDK CODE (NEEDS 'openai' PACKAGE INSTALLED & CONFIGURED) ----
    // At the top of this file, you would need:
    // import OpenAI from 'openai';
    // (And ensure 'openai' is in your package.json and installed)

    // const openai = new OpenAI({
    //   apiKey: this.apiKey, // Ensure this.apiKey is set (e.g., from environment variables)
    //   baseURL: this.baseURL, // Crucial for targeting Groq's OpenAI-compatible API
    // });

    // try {
    //   console.log(`[OpenAIGroqService_Stub] Attempting API call to model: ${targetModel} with messages:`, JSON.stringify(messages, null, 2));

    //   // Determine if JSON mode should be requested
    //   const tasksRequiringJson = [
    //       'categorize_email', 'extract_actions_email', 'classify_guidance_query',
    //       'extract_steps_from_text', 'generate_followup_suggestions', 'extract_document_snippets'
    //   ];
    //   const responseFormat = tasksRequiringJson.includes(structuredPrompt.task)
    //       ? { type: "json_object" as const } // Use "as const" for literal type
    //       : undefined;

    //   console.log(`[OpenAIGroqService_Stub] Using response_format: ${JSON.stringify(responseFormat)}`);

    //   const chatCompletion = await openai.chat.completions.create({
    //     messages: messages,
    //     model: targetModel, // e.g., "mixtral-8x7b-32768", "llama2-70b-4096"
    //     temperature: options?.temperature || (responseFormat?.type === "json_object" ? 0.2 : 0.7), // Lower temp for JSON
    //     max_tokens: options?.maxTokens || (responseFormat?.type === "json_object" ? 1024 : 400), // Adjust as needed
    //     // ...(responseFormat ? { response_format: responseFormat } : {}), // Add if supported and needed by Groq for strict JSON
    //   });

    //   const content = chatCompletion.choices[0]?.message?.content;
    //   const usage = chatCompletion.usage
    //       ? {
    //           promptTokens: chatCompletion.usage.prompt_tokens,
    //           completionTokens: chatCompletion.usage.completion_tokens,
    //           totalTokens: chatCompletion.usage.total_tokens
    //         }
    //       : undefined;

    //   if (content) {
    //     console.log("[OpenAIGroqService_Stub] API call successful. Content snippet:", content.substring(0,100));
    //     return { success: true, content: content, usage: usage };
    //   } else {
    //     console.error("[OpenAIGroqService_Stub] API call succeeded but content is null or undefined.");
    //     return { success: false, error: "API call succeeded but content is missing." };
    //   }
    // } catch (error: any) {
    //   console.error("[OpenAIGroqService_Stub] Error during API call:", error);
    //   return { success: false, error: error.message || "Unknown API error" };
    // }
    // ---- END ACTUAL OPENAI SDK CODE ----
    */

    // Fallback to calling MockLLMService to get more dynamic mock content for the stub
    const mockService = new MockLLMService();
    // We pass the original structuredPrompt here, so MockLLMService uses its own detailed mock logic.
    // The 'model' and 'options' are passed along too, though MockLLMService doesn't currently use them.
    const mockResponse = await mockService.generate(structuredPrompt, targetModel, options);
    console.log(`[OpenAIGroqService_Stub] Returning response from MockLLMService for task: ${structuredPrompt.task}`);
    return mockResponse;

    // Or, if you prefer a very simple static stub response:
    // return {
    //     success: true,
    //     content: `[Stubbed OpenAIGroq Response for task: ${structuredPrompt.task} on model ${targetModel}. Input data (first 100 chars): ${JSON.stringify(structuredPrompt.data).substring(0,100)}...]`,
    //     usage: { promptTokens: 50, completionTokens: 50, totalTokens: 100} // Mock usage
    // };
  }
}
