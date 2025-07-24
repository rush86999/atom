import * as conversationManager from './conversationState'; // Added for conversation management
import type { InterfaceType } from './conversationState';
// import { listUpcomingEvents, createCalendarEvent } from './skills/calendarSkills'; // Will be re-imported with others
// import { listRecentEmails, readEmail, sendEmail, EmailDetails } from './skills/emailSkills'; // Will be re-imported
// import { searchWeb } from './skills/webResearchSkills'; // Will be re-imported
// import { triggerZap, ZapData } from './skills/zapierSkills'; // Will be re-imported

import {
  CalendarEvent, CreateEventResponse,
  Email, ReadEmailResponse, SendEmailResponse, EmailDetails,
  SearchResult,
  ZapTriggerResponse, ZapData,
  HubSpotContactProperties,
  CreateHubSpotContactResponse,
  HubSpotContact,
  ListCalendlyEventTypesResponse,
  ListCalendlyScheduledEventsResponse,
  ListZoomMeetingsResponse,
  GetZoomMeetingDetailsResponse,
  ZoomMeeting,
  ListGoogleMeetEventsResponse,
  GetGoogleMeetEventDetailsResponse,
  ListMSTeamsMeetingsResponse,
  GetMSTeamsMeetingDetailsResponse,
  MSGraphEvent,
  ListStripePaymentsResponse,
  GetStripePaymentDetailsResponse,
  StripePaymentIntent,
  ListQuickBooksInvoicesResponse,
  GetQuickBooksInvoiceDetailsResponse,
  QuickBooksInvoice,
  ProcessedNLUResponse,
  LtmQueryResult,
  SkillArgs, // Added for SemanticSearchMeetingNotes
  // Semantic Search Result Type - for structured data
  ApiMeetingSearchResult, // Assuming this type can be imported or defined
  // Task Management Types
  CreateNotionTaskParams,
  QueryNotionTasksParams,
  UpdateNotionTaskParams,
  NotionTask,
  NotionTaskStatus,
  NotionTaskPriority,
  TaskQueryResponse, // Response type for queryNotionTasks skill
  SkillResponse, // Generic skill response
  CreateTaskData, // Data type for CreateTask skill response
  UpdateTaskData, // Data type for UpdateTask skill response
  SkillError, // For getUserIdByEmail
  PrepareForMeetingResponse, // Added for Smart Meeting Prep
  PrepareForMeetingEntities, // Added for Smart Meeting Prep
  GenerateWeeklyDigestResponse, // Added for Weekly Digest
  GenerateWeeklyDigestEntities, // Added for Weekly Digest
  SuggestFollowUpsResponse, // Added for Follow-up Suggester
  SuggestFollowUpsEntities, // Added for Follow-up Suggester
  // Types for ComplexTask Orchestration
  ComplexTaskSubTaskNlu,
  ExecutedSubTaskResult,
  OrchestratedComplexTaskReport,
  AgentClientCommand, // Import from central types
  AgentSkillContext,  // Import from central types
} from '../types';

// Import the specific skill response type if available, or define locally
// For SemanticSearchMeetingNotes, the skill returns Promise<string | { displayType: 'semantic_search_results'; summaryText: string; data: ApiMeetingSearchResult[] }>
// We need ApiMeetingSearchResult definition. For now, let's assume it's available via '../types' or we'll define a placeholder.
// If it's not in types, let's define a placeholder for the data part of semantic search
interface PlaceholderApiMeetingSearchResult {
    notion_page_id: string;
    notion_page_title: string;
    notion_page_url: string;
    text_preview: string;
    last_edited: string;
    score: number;
}

interface SemanticSearchStructuredData {
    displayType: 'semantic_search_results';
    summaryText: string;
    data: PlaceholderApiMeetingSearchResult[];
}


import { executeGraphQLQuery } from './_libs/graphqlClient'; // For getUserIdByEmail

// --- Interface Definitions for Agent-Client Communication and Skill Context ---
// Local definitions of AgentClientCommand and AgentSkillContext are removed.
// They are now imported from '../types'.

// Extend existing options for _internalHandleMessage to include the sendCommandToClientFunction.
// This allows the core message handling logic to be equipped with the capability to send commands to the client.
interface InternalHandleMessageOptions {
  requestSource?: string; // Source of the request (e.g., 'WebSocketChat', 'ScheduledJobExecutor', 'HasuraAction')
  intentName?: string;    // Pre-determined intent name, bypassing NLU (e.g., for scheduled tasks)
  entities?: Record<string, any>; // Pre-determined entities
  conversationId?: string; // ID for tracking the conversation session
  sendCommandToClientFunction?: (userId: string, command: AgentClientCommand) => Promise<boolean>; // The actual function to send a command
}
// --- End Interface Definitions ---

// import * as conversationManager from './conversationState'; // Already imported at the top
// No longer importing individual functions directly, will use conversationManager.
// import {
// getConversationStateSnapshot,
// updateLTMContext,
// updateUserGoal,
// updateIntentAndEntities
// } from './conversationState';
import { handleSemanticSearchMeetingNotesSkill } from './skills/semanticSearchSkills';
import {
    createNotionTask,
    queryNotionTasks,
    // createNotionTask, // Now handled by createNotionTaskCommandHandler
    // queryNotionTasks, // Now handled by queryNotionTasksCommandHandler
    // updateNotionTask // Now handled by updateNotionTaskCommandHandler
} from './skills/notionAndResearchSkills';
import { initializeDB as initializeLanceDB } from '../lanceDBManager';
import * as lancedb from '@lancedb/lancedb';
// Import new command handlers for Notion tasks
import { handleCreateTaskRequest } from './command_handlers/createNotionTaskCommandHandler';
import { handleQueryTasksRequest } from './command_handlers/queryNotionTasksCommandHandler';
import { handleUpdateTaskRequest } from './command_handlers/updateNotionTaskCommandHandler';
// Import new Gmail skills
import { handleSearchGmail, handleExtractInfoFromGmail, SearchGmailNluEntities, ExtractInfoFromGmailNluEntities } from './skills/gmailSkills';
// Import new Slack Query skills
import { handleSearchSlackMessages, handleExtractInfoFromSlackMessage, SearchSlackMessagesNluEntities, ExtractInfoFromSlackMessageNluEntities } from './skills/slackQuerySkills';
// Import new MS Teams Query skills
import { handleSearchMSTeamsMessages, handleExtractInfoFromMSTeamsMessage, SearchMSTeamsMessagesNluEntities, ExtractInfoFromMSTeamsMessageNluEntities } from './skills/msTeamsQuerySkills';
import {
    retrieveRelevantLTM,
    loadLTMToSTM,
    processSTMToLTM,
    ConversationStateActions
} from './memoryManager';

import { createHubSpotContact, getHubSpotContactByEmail } from './skills/hubspotSkills';
import { sendSlackMessage } from './skills/slackSkills';
import { listCalendlyEventTypes, listCalendlyScheduledEvents } from './skills/calendlySkills';
import { listZoomMeetings, getZoomMeetingDetails } from './skills/zoomSkills';
import {
    listUpcomingEvents, // Already imported but ensure it's covered
    createCalendarEvent, // Already imported
    listUpcomingGoogleMeetEvents,
    getGoogleMeetEventDetails
} from './skills/calendarSkills';
import { listMicrosoftTeamsMeetings, getMicrosoftTeamsMeetingDetails } from './skills/msTeamsSkills';
import { listStripePayments, getStripePaymentDetails } from './skills/stripeSkills';
import {
    listQuickBooksInvoices,
    getQuickBooksInvoiceDetails,
    getAuthUri as getQuickBooksAuthUri
} from './skills/quickbooksSkills';
import {
    enableAutopilot,
    disableAutopilot,
    getAutopilotStatus
} from './skills/autopilotSkills';
import {
    createSchedulingRule,
    blockCalendarTime,
    initiateTeamMeetingScheduling,
    NLUCreateTimePreferenceRuleEntities,
    NLUBlockTimeSlotEntities,
    NLUScheduleTeamMeetingEntities,
    SchedulingResponse,
    ScheduleTaskParams, // Added for scheduleTask
    scheduleTask, // Added for scheduleTask
    handleScheduleSkillActivation
} from './skills/schedulingSkills';
import { understandMessage } from './skills/nluService';
import {
    ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID,
    ATOM_HUBSPOT_PORTAL_ID,
    ATOM_QB_TOKEN_FILE_PATH,
    ATOM_NOTION_TASKS_DATABASE_ID, // Added for Notion Tasks
    LANCEDB_LTM_AGENT_TABLE_NAME, // Added for LTM table name
    PYTHON_API_SERVICE_BASE_URL,
    ASANA_ACCESS_TOKEN,
    JIRA_SERVER,
    JIRA_USERNAME,
    JIRA_PASSWORD,
    TRELLO_API_KEY,
    TRELLO_API_SECRET,
    TRELLO_TOKEN
} from '../_libs/constants';
import { agenda, ScheduledAgentTaskData } from '../agendaService'; // Added for Agenda
import { searchWeb } from './skills/webResearchSkills'; // Added missing import
import { listRecentEmails, readEmail, sendEmail } from './skills/emailSkills'; // Added missing import
import { triggerZap } from './skills/zapierSkills'; // Added missing import
import { resolveAttendees } from './skills/contactSkills'; // For ScheduleMeetingFromEmail
// import { invokeOptaPlannerScheduling } from './skills/schedulingSkills'; // Will be added to schedulingSkills
import { handlePrepareForMeeting, handleGenerateWeeklyDigest, handleSuggestFollowUps } from './skills/productivitySkills'; // Added for Smart Meeting Prep, Weekly Digest & Follow-up Suggester
import { handleMeetingPreparationRequest } from './command_handlers/meetingPrepCommandHandler'; // Added for Meeting Prep
import { handleProcessMeetingOutcomesRequest } from './command_handlers/postMeetingWorkflowCommandHandler'; // Added for Post-Meeting Workflow
import { handleGetDailyBriefingRequest } from './command_handlers/dailyBriefingCommandHandler'; // Added for Daily Briefing
import { handleCreateTaskFromChatMessageRequest } from './command_handlers/taskFromChatCommandHandler'; // Added for Task from Chat
import { handleGetCalendarEvents, handleCreateCalendarEvent } from './skills/calendar';
import { handleListEmails, handleReadEmail, handleSendEmail } from './skills/email';
import { handleSearchWeb } from './skills/web';
import { handleTriggerZap } from './skills/zapier';
import { handleGetHubSpotContactByEmail, handleCreateHubSpotContact } from './skills/hubspot';
import { handleSendSlackMessage, handleSlackMyAgenda } from './skills/slack';
import { handleListCalendlyEventTypes, handleListCalendlyScheduledEvents } from './skills/calendly';
import { handleListZoomMeetings, handleGetZoomMeetingDetails } from './skills/zoom';
import { handleListGoogleMeetEvents, handleGetGoogleMeetEventDetails } from './skills/googleMeet';
import { handleListMicrosoftTeamsMeetings, handleGetMicrosoftTeamsMeetingDetails } from './skills/msteams';
import { handleListStripePayments, handleGetStripePaymentDetails } from './skills/stripe';
import { handleGetQuickBooksAuthUrl, handleListQuickBooksInvoices, handleGetQuickBooksInvoiceDetails } from './skills/quickbooks';
import { handleMeetingPrep } from './skills/meetingPrep';
import { handleCreateAsanaTask, handleQueryAsanaTasks, handleUpdateAsanaTask } from './skills/asana';
import { handleCreateJiraIssue, handleQueryJiraIssues, handleUpdateJiraIssue } from './skills/jira';
import { handleCreateTrelloCard, handleQueryTrelloCards, handleUpdateTrelloCard } from './skills/trello';
import { handleBrowser } from './skills/browserSkills';
import { ReminderSkills } from './skills/reminderSkills';


// Define the TTS service URL
const AUDIO_PROCESSOR_TTS_URL = process.env.AUDIO_PROCESSOR_BASE_URL
    ? `${process.env.AUDIO_PROCESSOR_BASE_URL}/tts`
    : 'http://localhost:8080/tts';

// --- LanceDB Initialization ---
let ltmDbConnection: lancedb.Connection | null = null;

async function initializeLtmDatabase(): Promise<void> {
  try {
    ltmDbConnection = await initializeLanceDB("ltm_agent_data");
    if (ltmDbConnection) {
      console.log('[Handler] LanceDB LTM connection initialized successfully.');
    } else {
      console.error('[Handler] LanceDB LTM connection failed to initialize (returned null).');
    }
  } catch (error) {
    console.error('[Handler] Error initializing LanceDB LTM connection:', error);
    ltmDbConnection = null;
  }
}

initializeLtmDatabase();

export interface HandleMessageResponse {
  text: string;
  audioUrl?: string;
  error?: string;
  structuredData?: any; // Added field for structured skill responses
}

// Extend existing options for _internalHandleMessage to include the sendCommandToClientFunction.
// This allows the core message handling logic to be equipped with the capability to send commands to the client.
interface InternalHandleMessageOptions {
  requestSource?: string; // Source of the request (e.g., 'WebSocketChat', 'ScheduledJobExecutor', 'HasuraAction')
  intentName?: string;    // Pre-determined intent name, bypassing NLU (e.g., for scheduled tasks)
  entities?: Record<string, any>; // Pre-determined entities
  conversationId?: string; // ID for tracking the conversation session
  sendCommandToClientFunction?: (userId: string, command: AgentClientCommand) => Promise<boolean>; // The actual function to send a command
}
// --- End Interface Definitions ---

async function _internalHandleMessage(
  interfaceType: InterfaceType,
  message: string,
  userId: string,
  llm: { service: string; apiKey: string },
  // Options now uses the extended interface
  options?: InternalHandleMessageOptions
): Promise<{text: string, nluResponse?: ProcessedNLUResponse, structuredData?: any}> {
  const reminderSkills = new ReminderSkills();
  await reminderSkills.processDueReminders();

  let textResponse: string;
  let structuredDataResponse: any = undefined; // Variable to hold structured data
  let conversationLtmContext: LtmQueryResult[] | null = null;
  let nluResponse: ProcessedNLUResponse;

  const requestSource = options?.requestSource;
  const directIntentName = options?.intentName;
  const directEntities = options?.entities;
  const conversationId = options?.conversationId; // Available if needed

  // Construct the AgentSkillContext to be passed to skill handlers
  // This context now includes the sendCommandToClient function if it was provided by the caller.
  const agentSkillContext: AgentSkillContext = {
    userId: userId,
    sendCommandToClient: options?.sendCommandToClientFunction || (async (uid_unused, cmd_unused) => {
      // This default function is a fallback and logs a warning if no actual send function is provided.
      // It ensures that skills can always try to call context.sendCommandToClient without crashing,
      // but it won't actually send anything if the infrastructure isn't wired up from the caller.
      console.warn(
        `[AgentSkillContext] sendCommandToClient was called for user ${userId} ` +
        `but no implementation was provided to _internalHandleMessage. Command was: ${JSON.stringify(cmd_unused)}`
      );
      return false; // Indicate failure to send
    }),
    // Potentially add other context items here if needed by various skills
  };

  if (requestSource === 'ScheduledJobExecutor' && directIntentName) {
    console.log(`[InternalHandleMessage][${interfaceType}] Received direct execution request from ScheduledJobExecutor. ConversationID: ${conversationId}`);
    nluResponse = {
      intent: directIntentName,
      entities: directEntities || {},
      // Ensure other necessary fields for ProcessedNLUResponse are present
      user_id: userId,
      original_query: `Scheduled task: ${directIntentName}`, // Construct a descriptive query
      // confidence: 1.0, // Assuming 100% confidence for direct execution
      // error: undefined
    };
    console.log(`[InternalHandleMessage][${interfaceType}] Bypassing NLU for scheduled task. Intent: ${nluResponse.intent}, Entities: ${JSON.stringify(nluResponse.entities)}`);
  } else {
    if (ltmDbConnection) {
      try {
        const relevantLtm = await retrieveRelevantLTM(message, userId, ltmDbConnection, { table: LANCEDB_LTM_AGENT_TABLE_NAME });
        if (relevantLtm && relevantLtm.length > 0) {
          console.log(`[Handler][${interfaceType}] Retrieved ${relevantLtm.length} items from LTM for query: ${message}. Storing in conversation state.`);
          conversationManager.updateLTMContext(interfaceType, relevantLtm);
          conversationLtmContext = relevantLtm;
          const conversationStateActions: ConversationStateActions = {
              updateUserGoal: (goal) => conversationManager.updateUserGoal(interfaceType, goal),
              updateIntentAndEntities: (intent, entities) => conversationManager.updateIntentAndEntities(interfaceType, intent, entities),
              updateLtmRepoContext: (context) => conversationManager.updateLTMContext(interfaceType, context)
          };
          await loadLTMToSTM(relevantLtm, conversationStateActions);
        } else {
          conversationManager.updateLTMContext(interfaceType, null);
          conversationLtmContext = null;
        }
      } catch (error) {
        console.error(`[Handler][${interfaceType}] Error retrieving or loading LTM:`, error);
        conversationManager.updateLTMContext(interfaceType, null);
        conversationLtmContext = null;
      }
    } else {
      console.warn(`[Handler][${interfaceType}] LTM DB connection not available, skipping LTM retrieval.`);
      conversationManager.updateLTMContext(interfaceType, null);
      conversationLtmContext = null;
    }

    nluResponse = await understandMessage(message, undefined, conversationLtmContext, llm);
    console.log(`[InternalHandleMessage][${interfaceType}] NLU Response (with LTM context consideration):`, JSON.stringify(nluResponse, null, 2));
  }

  if (nluResponse.error && !nluResponse.intent) {
    // This condition might need adjustment if scheduled tasks (bypassing NLU) could still have an "error"
    // in the constructed nluResponse, though ideally they wouldn't if intent is present.
    console.error(`[InternalHandleMessage][${interfaceType}] NLU service critical error or no intent from scheduled task:`, nluResponse.error);
    textResponse = "Sorry, I'm having trouble understanding requests right now or processing the scheduled task. Please try again later.";
    const currentConvStateOnError = conversationManager.getConversationStateSnapshot(interfaceType);
    const ltmContextForErrorResponse = currentConvStateOnError.ltmContext;
    if (ltmContextForErrorResponse && ltmContextForErrorResponse.length > 0) {
        const firstLtmItem = ltmContextForErrorResponse[0] as LtmQueryResult; // Type assertion still needed
        if (firstLtmItem && firstLtmItem.text) { // Check if text property exists
            let ltmPreamble = `I recall from our records that: "${firstLtmItem.text.substring(0, 150)}${firstLtmItem.text.length > 150 ? '...' : ''}". `;
            textResponse = ltmPreamble + textResponse;
            console.log(`[Handler][${interfaceType}] Augmented error response with LTM context: ${ltmPreamble}`);
        }
    }
    return { text: textResponse, nluResponse, structuredData: structuredDataResponse };
  }

  // Process NLU response and execute skills
  // All console logs within this block should also be prefixed with [interfaceType]
  if (nluResponse.intent) {
    const entities = nluResponse.entities || {};
    // Log intent and entities with interfaceType
    console.log(`[Handler][${interfaceType}] Intent: ${nluResponse.intent}, Entities: ${JSON.stringify(entities)}`);

    try {
    switch (nluResponse.intent) {
      case "GetCalendarEvents":
        textResponse = await handleGetCalendarEvents(userId, entities, agentSkillContext.settings.integrations);
        break;
      // ... (other cases)
      default:
        textResponse = `I understood your intent as '${nluResponse.intent}', but I'm not set up to handle that yet.`;
    }
} catch (error: any) {
    console.error(`[Handler][${interfaceType}] Error executing intent "${nluResponse.intent}":`, error.message, error.stack);
    textResponse = `Sorry, I encountered an error while trying to handle your request for "${nluResponse.intent}". Please try again.`;
}
  } else if (message.toLowerCase() === 'help' || message.toLowerCase() === '?') { // Check lowerCaseMessage for 'help'
     textResponse = `I can understand natural language for tasks like listing calendar events, creating HubSpot contacts, or sending Slack messages. Try "show me my next 3 meetings" or "create hubspot contact for jane@example.com name Jane Doe".
You can also use specific commands:
- "create hubspot contact and dm me details {JSON_DETAILS}"
- "create hubspot contact {JSON_DETAILS}" (for channel notifications)
// ... (help message content as before)
- And other general commands like "list emails", "read email <id>", "send email {JSON}", "search web <query>", "trigger zap <name> [with data {JSON}]".`;
  } else {
    if (nluResponse.error) {
        textResponse = `I had some trouble fully understanding that due to: ${nluResponse.error}. You can try rephrasing or use 'help'.`;
    } else {
        textResponse = "Sorry, I didn't quite understand your request. Please try rephrasing, or type 'help' to see what I can do.";
    }
  }

  // 4. Augment response with LTM context (New)
  console.log(`[Handler][${interfaceType}] Future enhancement: Implement relevance check for LTM items before augmenting response.`);
  const currentConvState = conversationManager.getConversationStateSnapshot(interfaceType);
  const ltmContextForResponse = currentConvState.ltmContext;

  if (ltmContextForResponse && ltmContextForResponse.length > 0) {
      const firstLtmItem = ltmContextForResponse[0] as LtmQueryResult; // Type assertion still needed
      if (firstLtmItem && firstLtmItem.text) { // Check if text property exists
          let ltmPreamble = `I recall from our records that: "${firstLtmItem.text.substring(0, 150)}${firstLtmItem.text.length > 150 ? '...' : ''}". `;
          textResponse = ltmPreamble + textResponse;
          console.log(`[Handler][${interfaceType}] Augmented response with LTM context: ${ltmPreamble}`);
      }
  }

  return { text: textResponse, nluResponse, structuredData: structuredDataResponse };
}


// --- New Exported Functions for Conversation Management ---

/**
 * Placeholder for user ID retrieval. In a real scenario, this would come from session, token, etc.
 */
function getCurrentUserId(): string {
  // For now, using a mock user ID. This should be replaced with actual user management.
  return "mock_user_id_from_handler";
}

/**
 * Activates the conversation mode.
 * Assumed to be mapped to an HTTP endpoint like POST /atom-agent/activate
 */
export async function activateConversationWrapper(): Promise<{ status: string; active: boolean; message?: string }> {
  console.log(`[Handler][voice] Received request to activate conversation (assumed for voice).`);
  // activateConversation itself now sets isAgentResponding to false.
  const result = conversationManager.activateConversation('voice');
  return { ...result, message: result.status };
}

/**
 * Deactivates the conversation mode.
 * Assumed to be mapped to an HTTP endpoint like POST /atom-agent/deactivate
 */
export async function deactivateConversationWrapper(reason: string = "manual_deactivation"): Promise<{ status: string; active: boolean; message?: string }> {
  console.log(`[Handler][voice] Received request to deactivate conversation. Reason: ${reason}`);
  // deactivateConversation itself now sets isAgentResponding to false.
  // Deactivates 'voice' by default. If text needs separate deactivation, it needs its own endpoint/logic.
  conversationManager.deactivateConversation('voice', reason);
  return { status: `Conversation deactivated due to ${reason}.`, active: false, message: `Conversation deactivated due to ${reason}.` };
}

/**
 * Handles an interrupt signal.
 * Assumed to be mapped to an HTTP endpoint like POST /atom-agent/interrupt
 */
export async function handleInterruptWrapper(): Promise<{ status: string; message: string }> {
  console.log("[Handler][voice] Received interrupt signal.");
  // Key action: Signal that the agent should stop its current response processing/output.
  // Primarily for voice interface, as text doesn't usually have an agent "speaking" state to interrupt.
  conversationManager.setAgentResponding('voice', false);

  // Optional: Could also deactivate conversation entirely or just reset timer to allow immediate next command.
  // For now, just stopping agent response and keeping conversation active.
  // conversationManager.activateConversation('voice'); // This would reset the timer and keep it active.
  // Or, if an interrupt means "stop everything":
  // conversationManager.deactivateConversation('voice', "interrupt_signal");

  // For now, the primary effect is setting isAgentResponding = false for 'voice'.
  // The wake_word_detector will follow up with an activate & new conversation input for 'voice'.
  // This ensures the agent is receptive.
  // If there were long-running tasks tied to the previous response, they should ideally check
  // conversationManager.checkIfAgentIsResponding('voice') and halt. This is not implemented in skills yet.

  return { status: "success", message: "Interrupt signal processed for voice interface. Agent responding state set to false." };
}


/**
 * Handles transcribed text input for an ongoing conversation.
 * Assumed to be mapped to an HTTP endpoint like POST /atom-agent/conversation
 * Expects payload: { "text": "user's transcribed speech" }
 */
export async function handleConversationInputWrapper(
  payload: { text: string },
  optionsFromCaller?: TempOptionsForCaller // Added optionsFromCaller for passing sendCommandToClient
): Promise<HandleMessageResponse | { error: string; active: boolean; message?: string }> {
  const interfaceType: InterfaceType = 'voice'; // This wrapper is for voice interactions
  const { text } = payload;
  console.log(`[Handler][${interfaceType}] Received conversation input: "${text}"`);

  const userId = getCurrentUserId();

  conversationManager.recordUserInteraction(interfaceType, text);

  if (!conversationManager.isConversationActive(interfaceType)) {
    console.log(`[Handler][${interfaceType}] Conversation is not active. Ignoring input.`);
    conversationManager.setAgentResponding(interfaceType, false);
    return {
      error: "Conversation not active. Please activate with wake word or activation command.",
      active: conversationManager.isConversationActive(interfaceType),
      message: "Conversation is not active. Wake word or activation needed.",
    };
  }

  if (conversationManager.checkIfAgentIsResponding(interfaceType)) {
    console.warn(`[Handler][${interfaceType}] New input received while agent was still marked as responding.`);
    // This implies an interruption, so agent should stop current response.
    conversationManager.setAgentResponding(interfaceType, false);
  }

  conversationManager.setAgentResponding(interfaceType, true);

  console.log(`[Handler][${interfaceType}] Conversation active. Processing message...`);
  // Destructure structuredData as well from _internalHandleMessage
  const { text: coreResponseText, nluResponse, structuredData: structuredDataFromInternal } = await _internalHandleMessage(
    interfaceType,
    text,
    userId,
    // Pass the sendCommandToClient function in options for voice interactions
    // This needs to be correctly implemented in the server layer (e.g. server.ts for WebSockets)
    { sendCommandToClientFunction: optionsFromCaller?.sendCommandToClientFunction } // Assuming optionsFromCaller is passed to handleConversationInputWrapper
  );

  // Record agent's core text response (before TTS) into conversation history
  // NLU results (intent, entities) from this turn can also be added to turnHistory here.
  const currentTurnIntent = nluResponse?.intent || undefined;
  const currentTurnEntities = nluResponse?.entities || undefined;
  conversationManager.recordAgentResponse(interfaceType, text, { text: coreResponseText }, currentTurnIntent, currentTurnEntities);


  // STM to LTM Processing (Fire-and-forget for now)
  if (ltmDbConnection) {
    try {
      const currentConversationState = conversationManager.getConversationStateSnapshot(interfaceType);
      processSTMToLTM(userId, currentConversationState, ltmDbConnection)
        .then(() => console.log(`[Handler][${interfaceType}] STM to LTM processing initiated.`))
        .catch(err => console.error(`[Handler][${interfaceType}] Error in STM to LTM processing:`, err));
    } catch (error) {
      console.error(`[Handler][${interfaceType}] Error initiating STM to LTM processing:`, error);
    }
  } else {
      console.warn('[Handler] LTM DB connection not available, skipping STM to LTM processing.');
  }

  // TTS Synthesis (as before)
  try {
    const ttsPayload = { text: coreResponseText };
    const ttsResponse = await fetch(AUDIO_PROCESSOR_TTS_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ttsPayload)
    });

    if (ttsResponse.ok) {
      const ttsResult = await ttsResponse.json();
      if (ttsResult.audio_url) {
        console.log(`[Handler][${interfaceType}] TTS synthesis successful. Audio URL generated.`);
        conversationManager.setAgentResponding(interfaceType, false); // Agent finished processing and responding
        // Include structuredData in the response if present
        return { text: coreResponseText, audioUrl: ttsResult.audio_url, structuredData: structuredDataFromInternal };
      } else {
        console.error(`[Handler][${interfaceType}] TTS response OK, but no audio_url:`, ttsResult);
        conversationManager.setAgentResponding(interfaceType, false); // Agent finished processing (with error)
        return { text: coreResponseText, error: "TTS synthesis succeeded but no audio URL was returned.", structuredData: structuredDataFromInternal };
      }
    } else {
      const errorBody = await ttsResponse.text();
      console.error(`[Handler][${interfaceType}] TTS request failed:`, ttsResponse.status, errorBody);
      conversationManager.setAgentResponding(interfaceType, false); // Agent finished processing (with error)
      return { text: coreResponseText, error: `Failed to synthesize audio. Status: ${ttsResponse.status}`, structuredData: structuredDataFromInternal };
    }
  } catch (error: any) {
    console.error(`[Handler][${interfaceType}] Error calling TTS service:`, error.message, error.stack);
    conversationManager.setAgentResponding(interfaceType, false); // Agent finished processing (with error)
    return { text: coreResponseText, error: "Error occurred during audio synthesis.", structuredData: structuredDataFromInternal };
  }
}

// Temporary: Define optionsFromCaller type if not passed to handleConversationInputWrapper
// This is just for type-checking within this file, actual implementation is in the calling server.
interface TempOptionsForCaller {
    sendCommandToClientFunction?: (userId: string, command: AgentClientCommand) => Promise<boolean>;
}
// Make sure handleConversationInputWrapper receives options: TempOptionsForCaller
// export async function handleConversationInputWrapper(
//   payload: { text: string },
//   optionsFromCaller?: TempOptionsForCaller // Added for passing sendCommandToClient
// ): Promise<HandleMessageResponse | { error: string; active: boolean; message?: string }> { ... }


/**
 * This is the original handleMessage function, primarily for Hasura Action.
 * It remains largely stateless and does not interact with isAgentResponding by default.
 * If Hasura actions need to be part of conversational flow, this would require more thought.
 */
export async function handleMessage(message: string, settings: any): Promise<HandleMessageResponse> {
  const interfaceType: InterfaceType = 'text'; // This handler is for text-based interactions (e.g., Hasura)
  console.log(`[Handler][${interfaceType}] Received message: "${message}"`);
  const userId = getCurrentUserId();

  // Hasura actions are typically independent and don't use the conversation state's isAgentResponding flag.
  // If they were to, it would need careful consideration of how they fit into the conversation flow.
  // conversationManager.setAgentResponding(interfaceType, true);

  // Activate conversation for this interaction if not already active (for LTM context, etc.)
  // This is a simplified model; a more robust system might have explicit session management for text.
  if (!conversationManager.isConversationActive(interfaceType)) {
    conversationManager.activateConversation(interfaceType);
  }
  conversationManager.recordUserInteraction(interfaceType, message);

  // Destructure structuredData as well
  const { text: coreResponseText, nluResponse, structuredData: structuredDataFromInternal } = await _internalHandleMessage(
    interfaceType,
    message,
    userId,
    settings.llm,
    // For Hasura/text, sendCommandToClient is typically not available or needed unless specifically designed.
    // So, we might not pass sendCommandToClientFunction here, or pass a stub.
    // For now, assuming the default stub in _internalHandleMessage is sufficient if not provided.
    {} // Empty options, relying on default sendCommandToClient stub if skill attempts to use it.
  );

  // Record agent's response
  const currentTurnIntent = nluResponse?.intent || undefined;
  const currentTurnEntities = nluResponse?.entities || undefined;
  conversationManager.recordAgentResponse(interfaceType, message, { text: coreResponseText }, currentTurnIntent, currentTurnEntities);

  // STM to LTM Processing for text interface as well
  if (ltmDbConnection) {
    try {
      const currentConversationState = conversationManager.getConversationStateSnapshot(interfaceType);
      processSTMToLTM(userId, currentConversationState, ltmDbConnection)
        .then(() => console.log(`[Handler][${interfaceType}] STM to LTM processing initiated.`))
        .catch(err => console.error(`[Handler][${interfaceType}] Error in STM to LTM processing:`, err));
    } catch (error: any) {
      console.error(`[Handler][${interfaceType}] Error initiating STM to LTM processing:`, error);
    }
  }

  // For 'text' interface, we do NOT call TTS.
  // conversationManager.setAgentResponding(interfaceType, false); // Agent has finished.

  // Deactivate after single text interaction, unless a longer session is desired.
  // For now, let's assume single interaction for Hasura.
  conversationManager.deactivateConversation(interfaceType, "completed_text_interaction");

  // Include structuredData in the response
  return { text: coreResponseText, structuredData: structuredDataFromInternal };
}

// Example for testing the conversation state (manual activation)
// This would be mapped to an endpoint like /atom-agent/test-activate
export async function testActivateConversation() {
  // Test with 'voice' interface by default for this test wrapper
    conversationManager._test_setConversationActive('voice', true); // This itself calls activateConversation now
    return {
      status: "Conversation manually activated for testing (voice interface) via _test_setConversationActive.",
      active: conversationManager.isConversationActive('voice'),
      agentResponding: conversationManager.checkIfAgentIsResponding('voice')
    };
}

export async function testDeactivateConversation() {
    // Test with 'voice' interface by default
    conversationManager._test_setConversationActive('voice', false); // This itself calls deactivateConversation now
    return {
      status: "Conversation manually deactivated for testing (voice interface) via _test_setConversationActive.",
      active: conversationManager.isConversationActive('voice'),
      agentResponding: conversationManager.checkIfAgentIsResponding('voice')
    };
}

export async function getConversationStatus() {
    // Provide status for both interfaces
    return {
        voice_active: conversationManager.isConversationActive('voice'),
        voice_agentResponding: conversationManager.checkIfAgentIsResponding('voice'),
        text_active: conversationManager.isConversationActive('text'),
        text_agentResponding: conversationManager.checkIfAgentIsResponding('text'),
        voice_state: conversationManager.getConversationStateSnapshot('voice'),
        text_state: conversationManager.getConversationStateSnapshot('text')
    };
}
