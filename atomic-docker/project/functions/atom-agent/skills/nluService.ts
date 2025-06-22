import OpenAI from 'openai';
import { ChatCompletionMessageParam } from 'openai/resources/chat/completions';
import {
  ATOM_OPENAI_API_KEY,
  ATOM_NLU_MODEL_NAME,
} from '../_libs/constants';
import {
  NLUResponseData,
  ProcessedNLUResponse,
  LtmQueryResult, // Import LtmQueryResult
} from '../../types'; // Adjusted path assuming types.ts is in functions/types.ts

let openAIClient: OpenAI | null = null;

export function resetOpenAIClientCache() {
  openAIClient = null;
}

function getOpenAIClient(): OpenAI | null {
  if (openAIClient) {
    return openAIClient;
  }

  if (!ATOM_OPENAI_API_KEY) {
    console.error('OpenAI API Key not configured for NLU service.');
    return null;
  }

  openAIClient = new OpenAI({
    apiKey: ATOM_OPENAI_API_KEY,
  });

  return openAIClient;
}

const SYSTEM_PROMPT = `
You are an NLU (Natural Language Understanding) system for the Atomic Agent.
Your task is to identify the user's intent and extract relevant entities from their message.
Respond ONLY with a single, valid JSON object. Do not include any explanatory text before or after the JSON.
The JSON object must have two top-level keys: "intent" (string or null) and "entities" (an object).

Available Intents and their Entities:

(Existing intents 1-27 are assumed to be listed here)
1.  Intent: "GetCalendarEvents"
    - Entities: {"date_range": "e.g., tomorrow, next week, specific date", "limit": "number of events", "event_type_filter": "e.g., Google Meet events", "time_query": "e.g., 2:30 PM, evening", "query_type": "e.g., check_availability, list_events"}
    - Example: User asks "What's on my calendar for tomorrow?" -> {"intent": "GetCalendarEvents", "entities": {"date_range": "tomorrow"}}
    - Example: User asks "Am I free on Friday at 2:30 PM?" -> {"intent": "GetCalendarEvents", "entities": {"date_range": "Friday", "time_query": "2:30 PM", "query_type": "check_availability"}}
2.  Intent: "CreateCalendarEvent"
    - Entities: {"summary": "event title", "start_time": "ISO string or natural language", "end_time": "ISO string or natural language", "duration": "e.g., 30 minutes, 1 hour", "description": "event details", "location": "event location", "attendees": "array of email addresses"}
    - Example: User says "Schedule 'Team Sync' for next Monday at 10 AM for 45 minutes with alice@example.com" -> {"intent": "CreateCalendarEvent", "entities": {"summary": "Team Sync", "start_time": "next Monday 10:00 AM", "duration": "45 minutes", "attendees": ["alice@example.com"]}}
... (Assume other existing intents like ListEmails, SendEmail, SearchWeb, CreateHubSpotContact, etc., are here)
27. Intent: "ScheduleTeamMeeting"
    - Entities: {"attendees": "array of email addresses or names", "purpose": "meeting subject", "duration_preference": "e.g., 30 minutes, 1 hour", "time_preference_details": "e.g., next Monday morning, this week afternoon"}

New Autopilot Intents:
28. Intent: "EnableAutopilot"
    - Entities: {"raw_query": "The full or relevant part of the user query detailing the autopilot configuration.", "autopilot_config_details": "Specific configuration details if discernable, otherwise use raw_query.", "schedule_description": "e.g., daily, for project X"}
    - Example: User says "Enable autopilot for daily feature deployment" -> {"intent": "EnableAutopilot", "entities": {"raw_query": "Enable autopilot for daily feature deployment", "autopilot_config_details": "daily feature deployment", "schedule_description": "daily"}}
    - Example: User says "Turn on autopilot with query {...}" -> {"intent": "EnableAutopilot", "entities": {"raw_query": "Turn on autopilot with query {...}", "autopilot_config_details": "{...}"}}

29. Intent: "DisableAutopilot"
    - Entities: {"raw_query": "The full user query.", "autopilot_id": "The ID of the autopilot instance or event to disable, if specified.", "event_id": "Alternative key for the ID."}
    - Example: User says "Disable autopilot event 12345" -> {"intent": "DisableAutopilot", "entities": {"raw_query": "Disable autopilot event 12345", "autopilot_id": "12345", "event_id": "12345"}}
    - Example: User says "Turn off autopilot job abc-def" -> {"intent": "DisableAutopilot", "entities": {"raw_query": "Turn off autopilot job abc-def", "autopilot_id": "abc-def"}}

30. Intent: "GetAutopilotStatus"
    - Entities: {"raw_query": "The full user query.", "autopilot_id": "The ID of the autopilot instance to check, if specified."}
    - Example: User says "What's the status of autopilot task 67890?" -> {"intent": "GetAutopilotStatus", "entities": {"raw_query": "What's the status of autopilot task 67890?", "autopilot_id": "67890"}}
    - Example: User says "Show me my autopilot status" -> {"intent": "GetAutopilotStatus", "entities": {"raw_query": "Show me my autopilot status"}}

New Email Querying and Action Intent:
31. Intent: "QueryEmails"
    - Purpose: To find specific emails based on various criteria and potentially perform an action on them (like extracting information or summarizing).
    - Entities:
        - "from_sender": (string, optional) Email address or name of the sender. Example: "Jane Doe", "alerts@example.com"
        - "to_recipient": (string, optional) Email address or name of the recipient. Example: "me", "support team"
        - "subject_keywords": (string, optional) Keywords to search in the email subject. Example: "contract renewal", "important update"
        - "body_keywords": (string, optional) Keywords or phrases to search within the email body. Example: "action items", "summary attached"
        - "label": (string, optional) Gmail label to filter by. Example: "work", "starred", "important"
        - "date_query": (string, optional) Natural language description of the date or date range. Example: "last week", "yesterday", "in July", "since Monday", "between March 1st and April 15th 2023"
        - "has_attachment": (boolean, optional) True if emails must have attachments.
        - "is_unread": (boolean, optional) True if emails must be unread.
        - "exact_phrase_search": (string, optional) An exact phrase to search for in the email.
        - "action_on_email": (string, optional, defaults to just finding/listing if not specified) The action to perform on the found email(s). Values:
            - "FIND_SPECIFIC_INFO": Extract specific details. Requires "information_to_extract_keywords".
            - "GET_SENDER": Get the sender.
            - "GET_SUBJECT": Get the subject.
            - "GET_DATE": Get the date of the email.
            - "GET_FULL_CONTENT": Get the full body content.
            - "SUMMARIZE_EMAIL": Summarize the email content (future capability).
        - "information_to_extract_keywords": (array of strings, optional) Required if "action_on_email" is "FIND_SPECIFIC_INFO". Example: ["contract end date", "invoice amount"]
        - "target_email_id": (string, optional) If the user is referring to a specific email by its ID.
    - Examples:
        - User: "Find emails from XYZ about the contract sent a few months ago and tell me when the contract ends."
          Response: {"intent": "QueryEmails", "entities": {"from_sender": "XYZ", "subject_keywords": "contract", "body_keywords": "contract", "date_query": "a few months ago", "action_on_email": "FIND_SPECIFIC_INFO", "information_to_extract_keywords": ["contract end date"]}}
        - User: "Did I get any emails from support@company.com yesterday?"
          Response: {"intent": "QueryEmails", "entities": {"from_sender": "support@company.com", "date_query": "yesterday"}}
        - User: "Show me unread emails with attachments from 'Project Alpha'."
          Response: {"intent": "QueryEmails", "entities": {"is_unread": true, "has_attachment": true, "body_keywords": "Project Alpha"}}
        - User: "What was the subject of email ID 123abc456?"
          Response: {"intent": "QueryEmails", "entities": {"target_email_id": "123abc456", "action_on_email": "GET_SUBJECT"}}

New Task Management Intents:
32. Intent: "CreateTask"
    - Entities: {"task_description": "string, required - The full description of the task.", "due_date_time": "string, optional - e.g., tomorrow, next Friday 5pm, specific date/time", "priority": "string, optional - e.g., high, medium, low", "list_name": "string, optional - e.g., work, personal, shopping list"}
    - Example: User says "Atom, remind me to submit the TPS report by end of day Friday" -> {"intent": "CreateTask", "entities": {"task_description": "submit the TPS report", "due_date_time": "Friday end of day"}}
    - Example: User says "add a task to call the plumber" -> {"intent": "CreateTask", "entities": {"task_description": "call the plumber"}}
    - Example: User says "new task for my shopping list: buy milk and eggs" -> {"intent": "CreateTask", "entities": {"list_name": "shopping list", "task_description": "buy milk and eggs"}}
    - Example: User says "remind me to pick up laundry tomorrow morning with high priority" -> {"intent": "CreateTask", "entities": {"task_description": "pick up laundry", "due_date_time": "tomorrow morning", "priority": "high"}}

32. Intent: "QueryTasks"
    - Entities: {"date_range": "string, optional - e.g., today, tomorrow, this week, next month", "list_name": "string, optional - e.g., work, personal", "status": "string, optional - e.g., pending, completed, overdue"}
    - Example: User says "what are my tasks for today" -> {"intent": "QueryTasks", "entities": {"date_range": "today"}}
    - Example: User says "show me my work tasks" -> {"intent": "QueryTasks", "entities": {"list_name": "work"}}
    - Example: User says "list all completed tasks for this week" -> {"intent": "QueryTasks", "entities": {"status": "completed", "date_range": "this week"}}
    - Example: User says "do I have any overdue tasks on my personal list" -> {"intent": "QueryTasks", "entities": {"status": "overdue", "list_name": "personal"}}

33. Intent: "UpdateTask"
    - Entities: {"task_identifier": "string, required - Description or part of description of the task to update.", "update_action": "string, required - e.g., complete, set_due_date, change_description, set_priority", "new_due_date_time": "string, optional - New due date/time", "new_description": "string, optional - New task description", "new_priority": "string, optional - New priority level"}
    - Example: User says "mark task 'buy milk' as done" -> {"intent": "UpdateTask", "entities": {"task_identifier": "buy milk", "update_action": "complete"}}
    - Example: User says "change due date for 'review proposal' to tomorrow afternoon" -> {"intent": "UpdateTask", "entities": {"task_identifier": "review proposal", "update_action": "set_due_date", "new_due_date_time": "tomorrow afternoon"}}
    - Example: User says "update task 'call client' to 'call client about new quote'" -> {"intent": "UpdateTask", "entities": {"task_identifier": "call client", "update_action": "change_description", "new_description": "call client about new quote"}}
    - Example: User says "set priority for 'finish report' to high" -> {"intent": "UpdateTask", "entities": {"task_identifier": "finish report", "update_action": "set_priority", "new_priority": "high"}}

If the user's intent is unclear or does not match any of the above single intents, set "intent" to null and "entities" to an empty object.

If the user's intent is ambiguous or critical information is missing for a recognized single intent, set "intent" to "NeedsClarification",
set "entities" to include what was understood (e.g., {"partially_understood_intent": "CreateCalendarEvent", "summary": "Meeting"}),
and formulate a "clarification_question" to ask the user.
Example for NeedsClarification: {"intent": "NeedsClarification", "entities": {"partially_understood_intent": "CreateCalendarEvent", "summary": "Team Meeting with Marketing"}, "clarification_question": "What date and time would you like to schedule the meeting for, and who should be invited?"}

If a user's request involves multiple distinct actions or a sequence of steps that correspond to known simple intents, identify it as a "ComplexTask".
The "entities" for a "ComplexTask" should include an "original_query" key with the user's full request, and a "sub_tasks" key, which is an array of objects.
Each object in the "sub_tasks" array should itself be a standard NLU output structure for a simple intent: {"intent": "SubIntentName", "entities": {...}, "summary_for_sub_task": "User-friendly description of this step"}.
Example for ComplexTask: User says "Book a flight to London for next Tuesday and find me a hotel near Hyde Park for 3 nights."
Response (assuming BookFlight and FindHotel are defined simple intents):
{
  "intent": "ComplexTask",
  "entities": {
    "original_query": "Book a flight to London for next Tuesday and find me a hotel near Hyde Park for 3 nights.",
    "sub_tasks": [
      {
        "intent": "CreateCalendarEvent", "entities": {"summary": "Flight to London", "description": "Book flight for next Tuesday to London"},
        "summary_for_sub_task": "Book a flight to London for next Tuesday."
      },
      {
        "intent": "SearchWeb", "entities": {"query": "hotel near Hyde Park London 3 nights"},
        "summary_for_sub_task": "Find a hotel near Hyde Park in London for 3 nights."
      }
    ]
  }
}
If you identify a "ComplexTask", do not also try to process its parts as one of the simpler, single intents in the main response. Focus on the decomposition.
Ensure sub_task intents are chosen from the list of available simple intents.

Example for no matching intent: {"intent": null, "entities": {}}
Example for GetCalendarEvents: {"intent": "GetCalendarEvents", "entities": {"date_range": "tomorrow", "limit": 3, "event_type_filter": "Google Meet events"}}`;

export async function understandMessage(
  message: string,
  conversationHistory?: ChatCompletionMessageParam[],
  ltmContext?: LtmQueryResult[] | null // Added ltmContext parameter
): Promise<ProcessedNLUResponse> {
  const client = getOpenAIClient();
  if (!client) {
    return { originalMessage: message, intent: null, entities: {}, error: 'NLU service not configured: OpenAI API Key is missing.' };
  }
  if (!message || message.trim() === '') {
    return { originalMessage: message, intent: null, entities: {}, error: 'Input message is empty.' };
  }

  if (ltmContext && ltmContext.length > 0) {
    console.log(`[NLU Service] Received LTM context with ${ltmContext.length} items. First item (summary): ${JSON.stringify(ltmContext[0].text?.substring(0,100))}... Potential use: Augment prompts to NLU provider.`);
    // console.log('[NLU Service] Full LTM Context:', JSON.stringify(ltmContext, null, 2)); // Optional: for more detail
  }
  // TODO: Future enhancement - incorporate ltmContext into the prompt for the NLU model.
  // This might involve creating a summarized version of ltmContext to fit token limits
  // or selecting the most relevant pieces of context.

  const messages: ChatCompletionMessageParam[] = [
    { role: 'system', content: SYSTEM_PROMPT },
    ...(conversationHistory || []).map(h => ({ role: h.role as 'user' | 'assistant', content: h.content || '' })),
    { role: 'user', content: message },
  ];

  try {
    const completion = await client.chat.completions.create({
      model: ATOM_NLU_MODEL_NAME,
      messages: messages,
      temperature: 0.1,
      response_format: { type: 'json_object' },
    });

    const llmResponse = completion.choices[0]?.message?.content;
    if (!llmResponse) {
      return { originalMessage: message, intent: null, entities: {}, error: 'NLU service received an empty response from AI.' };
    }

    try {
      const parsedResponse = JSON.parse(llmResponse) as NLUResponseData;
      if (typeof parsedResponse.intent === 'undefined' || typeof parsedResponse.entities !== 'object') {
        return { originalMessage: message, intent: null, entities: {}, error: `NLU service received malformed JSON from AI: ${llmResponse}` };
      }

      const processed: ProcessedNLUResponse = {
        originalMessage: message,
        intent: parsedResponse.intent,
        entities: parsedResponse.entities || {},
        confidence: parsedResponse.confidence,
        recognized_phrase: parsedResponse.recognized_phrase,
      };

      if (parsedResponse.intent === "NeedsClarification" && parsedResponse.clarification_question) {
        processed.requires_clarification = true;
        processed.clarification_question = parsedResponse.clarification_question;
        if (parsedResponse.partially_understood_intent) {
          processed.entities.partially_understood_intent = parsedResponse.partially_understood_intent;
        }
      } else if (parsedResponse.intent === "ComplexTask" && parsedResponse.entities && parsedResponse.entities.sub_tasks) {
        processed.sub_tasks = parsedResponse.entities.sub_tasks.map(st => ({
          intent: st.intent || null,
          entities: st.entities || {},
          summary_for_sub_task: st.summary_for_sub_task || ''
        }));
        // Keep original_query if present in entities
        if (parsedResponse.entities.original_query) {
          processed.entities.original_query = parsedResponse.entities.original_query;
        }
      }

      // Conceptual Post-Processing for QueryEmails intent:
      // If processed.intent === "QueryEmails", this is where you would transform
      // the raw entities from the LLM into the more structured
      // ParsedNluEmailRequest object expected by email_command_handler.ts.
      // This involves:
      // 1. Date Resolution:
      //    - const dateQuery = processed.entities.date_query;
      //    - if (dateQuery) {
      //    -   // Use a date parsing library (e.g., Chronic, date-fns, custom logic)
      //    -   // to convert dateQuery into { after: "YYYY/MM/DD", before: "YYYY/MM/DD" }
      //    -   // and add these to a searchParameters object.
      //    -   // Example: processed.entities.search_after_date = resolvedAfterDate;
      //    -   //          processed.entities.search_before_date = resolvedBeforeDate;
      //    -   console.log("NLU TODO: Resolve date_query '"+dateQuery+"' into after/before dates.");
      //    - }
      // 2. Entity Mapping to StructuredEmailQuery:
      //    - const searchParams = {
      //    -   from: processed.entities.from_sender,
      //    -   subject: processed.entities.subject_keywords,
      //    -   bodyKeywords: processed.entities.body_keywords,
      //    -   // ... and so on for other fields of StructuredEmailQuery
      //    -   after: processed.entities.search_after_date, // from date resolution
      //    -   before: processed.entities.search_before_date, // from date resolution
      //    -   label: processed.entities.label,
      //    -   hasAttachment: processed.entities.has_attachment,
      //    -   exactPhrase: processed.entities.exact_phrase_search,
      //    -   excludeChats: processed.entities.is_unread === false, // Example logic
      //    - };
      //    - processed.entities.structured_search_params = searchParams; // Store for handler
      // 3. Action Mapping to EmailActionRequest:
      //    - const actionRequest = {
      //    -    actionType: processed.entities.action_on_email || "GET_FULL_CONTENT", // Default action
      //    -    infoKeywords: processed.entities.information_to_extract_keywords
      //    - };
      //    - processed.entities.structured_action_request = actionRequest; // Store for handler
      //
      // The email_command_handler.ts would then expect these structured entities.
      // For now, the handler might need to do some of this mapping itself if NLU only provides raw LLM entities.

      // --- BEGIN Date Resolution and Entity Structuring for QueryEmails ---
      if (processed.intent === "QueryEmails" && processed.entities) {
        const { date_query, ...otherEntities } = processed.entities;
        const resolvedDates: { after?: string; before?: string } = {};

        if (date_query && typeof date_query === 'string') {
          console.log(`[NLU Service] Raw date_query from LLM: "${date_query}"`);
          // TODO: Replace this with a robust date parsing library (e.g., date-fns, dayjs, chrono-node)
          // This is a very basic placeholder for date resolution.
          const now = new Date();
          const todayStr = `${now.getFullYear()}/${(now.getMonth() + 1).toString().padStart(2, '0')}/${now.getDate().toString().padStart(2, '0')}`;

          // Helper to format date as YYYY/MM/DD
          const formatDate = (d: Date) => `${d.getFullYear()}/${(d.getMonth() + 1).toString().padStart(2, '0')}/${d.getDate().toString().padStart(2, '0')}`;

          const lcDateQuery = date_query.toLowerCase();

          if (lcDateQuery === "today") {
            resolvedDates.after = formatDate(new Date(now.setHours(0, 0, 0, 0)));
            resolvedDates.before = formatDate(new Date(now.setHours(23, 59, 59, 999)));
          } else if (lcDateQuery === "yesterday") {
            const yesterday = new Date(now);
            yesterday.setDate(now.getDate() - 1);
            resolvedDates.after = formatDate(new Date(yesterday.setHours(0, 0, 0, 0)));
            resolvedDates.before = formatDate(new Date(yesterday.setHours(23, 59, 59, 999)));
          } else if (lcDateQuery.includes("last week")) {
            const dayOfWeek = now.getDay(); // 0 (Sun) - 6 (Sat)
            const lastMonday = new Date(now);
            lastMonday.setDate(now.getDate() - dayOfWeek - 6); // Go to previous Monday (start of last week)
            lastMonday.setHours(0,0,0,0);
            const lastSunday = new Date(lastMonday);
            lastSunday.setDate(lastMonday.getDate() + 6);
            lastSunday.setHours(23,59,59,999);
            resolvedDates.after = formatDate(lastMonday);
            resolvedDates.before = formatDate(lastSunday);
          } else if (lcDateQuery.includes("this week")) {
            const dayOfWeek = now.getDay();
            const currentMonday = new Date(now);
            currentMonday.setDate(now.getDate() - dayOfWeek + (dayOfWeek === 0 ? -6 : 1) ); // Adjust for Sunday being 0
            currentMonday.setHours(0,0,0,0);
            const currentSunday = new Date(currentMonday);
            currentSunday.setDate(currentMonday.getDate() + 6);
            currentSunday.setHours(23,59,59,999);
            resolvedDates.after = formatDate(currentMonday);
            resolvedDates.before = formatDate(currentSunday);
          } else if (lcDateQuery.includes("last month")) {
            const firstDayLastMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1);
            const lastDayLastMonth = new Date(now.getFullYear(), now.getMonth(), 0); // Day 0 of current month is last day of previous
            resolvedDates.after = formatDate(firstDayLastMonth);
            resolvedDates.before = formatDate(lastDayLastMonth);
          } else if (lcDateQuery.includes("this month")) {
            const firstDayThisMonth = new Date(now.getFullYear(), now.getMonth(), 1);
            const lastDayThisMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0);
            resolvedDates.after = formatDate(firstDayThisMonth);
            resolvedDates.before = formatDate(lastDayThisMonth);
          }
          // Add more specific parsing for "in July", "a few months ago", "since Monday" etc.
          // This requires a more sophisticated date parsing logic or library.
          // For "a few months ago" (e.g. 3 months), LLM might provide this directly, or NLU needs to interpret.
          // Example: if LLM says "3 months ago" -> calculate after/before for that month.

          if (resolvedDates.after || resolvedDates.before) {
            processed.entities.resolved_date_range = resolvedDates;
            console.log(`[NLU Service] Resolved date_query "${date_query}" to:`, resolvedDates);
          } else {
            console.log(`[NLU Service] Could not resolve date_query "${date_query}" with basic logic. Passing raw.`);
            // Keep raw date_query if not resolved, llm_email_query_understander might handle it.
          }
        }
        // The email_command_handler.ts will now receive entities including resolved_date_range (if successful)
        // and the raw entities from the LLM. It will then call llm_email_query_understander.ts
        // which should ideally use these pre-resolved dates if available.

        // Further prepare entities for email_command_handler.ts
        // The handler expects: rawEmailSearchQuery and actionRequested
        if (processed.intent === "QueryEmails" && processed.entities) {
            // The raw_email_search_query is already expected from the LLM for this intent.
            // Ensure it's passed through or explicitly set.
            if (!processed.entities.raw_email_search_query && message) {
                // Fallback if LLM didn't isolate it, use the original user message.
                // This might happen if the prompt for QueryEmails isn't perfectly followed by the LLM.
                // Ideally, the LLM for QueryEmails intent should always return raw_email_search_query.
                processed.entities.raw_email_search_query = message;
                console.warn("[NLU Service] LLM did not explicitly return 'raw_email_search_query' for QueryEmails intent. Using original message as fallback.");
            }

            // Construct the actionRequested object for email_command_handler
            const actionTypeFromLLM = processed.entities.action_on_email as (EmailActionType | undefined);
            processed.entities.structured_action_request = {
                actionType: actionTypeFromLLM || "GET_FULL_CONTENT", // Default if not specified
                infoKeywords: processed.entities.information_to_extract_keywords || undefined,
                naturalLanguageQuestion: processed.entities.natural_language_question_about_email || undefined,
            };
            // Remove raw action fields from top-level entities if they are now in structured_action_request
            // to avoid redundancy, or keep them if useful for logging/debugging.
            // delete processed.entities.action_on_email;
            // delete processed.entities.information_to_extract_keywords;
            // delete processed.entities.natural_language_question_about_email;
        }
      }
      // --- END Date Resolution and Entity Structuring ---

      return processed;
    } catch (jsonError: any) {
      console.error(`Error parsing NLU response from AI. Raw response: ${llmResponse}. Error: ${jsonError.message}`);
      return { originalMessage: message, intent: null, entities: {}, error: `Error parsing NLU response from AI. Raw response: ${llmResponse}. Error: ${jsonError.message}` };
    }
  } catch (error: any) {
    console.error('Error calling OpenAI for NLU service:', error.message);
    let errorMessage = 'Failed to understand message due to an NLU service error.';
    if (error.response?.data?.error?.message) { // More robust error checking
        errorMessage += ` API Error: ${error.response.data.error.message}`;\
    } else if (error.message) {
        errorMessage += ` Details: ${error.message}`;\
    }
    return { originalMessage: message, intent: null, entities: {}, error: errorMessage };
  }
}
