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
    scheduleTask // Added for scheduleTask
} from './skills/schedulingSkills';
import { understandMessage } from './skills/nluService';
import {
    ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID,
    ATOM_HUBSPOT_PORTAL_ID,
    ATOM_QB_TOKEN_FILE_PATH,
    ATOM_NOTION_TASKS_DATABASE_ID, // Added for Notion Tasks
    LANCEDB_LTM_AGENT_TABLE_NAME, // Added for LTM table name
    PYTHON_API_SERVICE_BASE_URL
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
  // Options now uses the extended interface
  options?: InternalHandleMessageOptions
): Promise<{text: string, nluResponse?: ProcessedNLUResponse, structuredData?: any}> {
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

    nluResponse = await understandMessage(message, undefined, conversationLtmContext);
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

    switch (nluResponse.intent) {
      case "GetCalendarEvents":
        textResponse = await handleGetCalendarEvents(userId, entities);
        break;

      case "CreateTaskFromChatMessage": // New Case for Task from Chat Message
        try {
          const taskFromChatEntities = nluResponse.entities as import('../types').CreateTaskFromChatMessageNluEntities;
          if (!taskFromChatEntities.chat_message_reference || !taskFromChatEntities.source_platform) {
            textResponse = "To create a task from a message, please specify the message reference and its platform (e.g., Slack, Teams).";
            console.warn(`[Handler][${interfaceType}] CreateTaskFromChatMessage: Missing chat_message_reference or source_platform.`);
          } else {
            console.info(`[Handler][${interfaceType}] Calling handleCreateTaskFromChatMessageRequest for message: "${taskFromChatEntities.chat_message_reference}"`);
            textResponse = await handleCreateTaskFromChatMessageRequest(userId, taskFromChatEntities);
          }
        } catch (error: any) {
          console.error(`[Handler][${interfaceType}] Error in NLU Intent "CreateTaskFromChatMessage":`, error.message, error.stack);
          textResponse = "Sorry, an unexpected error occurred while creating a task from the chat message.";
        }
        break;

      case "GetDailyPriorityBriefing": // New Case for Daily Briefing
        try {
          const briefingEntities = nluResponse.entities as import('../types').GetDailyPriorityBriefingNluEntities;
          // Basic validation, though the skill/handler might do more
          if (!briefingEntities) {
            textResponse = "I need a bit more information to get your daily briefing. For example, what day are you interested in?";
             console.warn(`[Handler][${interfaceType}] GetDailyPriorityBriefing: Entities object is missing or undefined.`);
          } else {
            console.info(`[Handler][${interfaceType}] Calling handleGetDailyBriefingRequest for date: "${briefingEntities.date_context || 'today'}"`);
            textResponse = await handleGetDailyBriefingRequest(userId, briefingEntities);
          }
        } catch (error: any) {
          console.error(`[Handler][${interfaceType}] Error in NLU Intent "GetDailyPriorityBriefing":`, error.message, error.stack);
          textResponse = "Sorry, an unexpected error occurred while generating your daily briefing.";
        }
        break;

      case "ProcessMeetingOutcomes": // New Case for Post-Meeting Workflow
        try {
          const outcomeEntities = nluResponse.entities as import('../types').ProcessMeetingOutcomesNluEntities;
          if (!outcomeEntities.meeting_reference || !outcomeEntities.requested_actions || outcomeEntities.requested_actions.length === 0) {
            textResponse = "To process meeting outcomes, please specify the meeting and the actions you'd like me to take (e.g., summarize, extract action items).";
            console.warn(`[Handler][${interfaceType}] ProcessMeetingOutcomes: Missing meeting_reference or requested_actions.`);
          } else {
            console.info(`[Handler][${interfaceType}] Calling handleProcessMeetingOutcomesRequest for meeting: "${outcomeEntities.meeting_reference}"`);
            textResponse = await handleProcessMeetingOutcomesRequest(userId, outcomeEntities);
          }
        } catch (error: any) {
          console.error(`[Handler][${interfaceType}] Error in NLU Intent "ProcessMeetingOutcomes":`, error.message, error.stack);
          textResponse = "Sorry, an unexpected error occurred while processing the meeting outcomes.";
        }
        break;

      case "RequestMeetingPreparation": // New Case for Meeting Prep
        textResponse = await handleMeetingPrep(userId, entities);
        break;

      case "SuggestFollowUps":
        try {
            const entities = nluResponse.entities as SuggestFollowUpsEntities;
            console.log(`[Handler][${interfaceType}] Intent: SuggestFollowUps, Entities:`, JSON.stringify(entities));

            if (!entities.context_identifier) {
                textResponse = "Please specify a meeting or project to get follow-up suggestions for.";
                break;
            }

            const response: SuggestFollowUpsResponse = await handleSuggestFollowUps(
                userId,
                entities.context_identifier,
                entities.context_type
            );

            if (response.ok && response.data) {
                const followUpInfo = response.data;
                let summaryText = `Here are some potential follow-ups and key points for "${followUpInfo.contextName}":\n`;
                if (followUpInfo.sourceDocumentSummary) {
                    summaryText += `(Based on: ${followUpInfo.sourceDocumentSummary})\n`;
                }

                if (followUpInfo.suggestions.length > 0) {
                    const actions = followUpInfo.suggestions.filter(s => s.type === 'action_item');
                    const decisions = followUpInfo.suggestions.filter(s => s.type === 'decision');
                    const questions = followUpInfo.suggestions.filter(s => s.type === 'question');

                    if (actions.length > 0) {
                        summaryText += "\n🎯 Action Items:\n";
                        actions.forEach(s => {
                            summaryText += `  - ${s.description}`;
                            if (s.suggestedAssignee) summaryText += ` (Assignee: ${s.suggestedAssignee})`;
                            if (s.existingTaskFound) summaryText += ` (Possibly related to existing task: ${s.existingTaskId || 'ID N/A'}${s.existingTaskUrl ? ` - ${s.existingTaskUrl}` : ''})`;
                            else summaryText += ` - [Consider creating a task]`;
                            summaryText += "\n";
                        });
                    }
                    if (decisions.length > 0) {
                        summaryText += "\n⚖️ Key Decisions:\n";
                        decisions.forEach(s => {
                            summaryText += `  - ${s.description}\n`;
                        });
                    }
                    if (questions.length > 0) {
                        summaryText += "\n❓ Open Questions/Unresolved:\n";
                        questions.forEach(s => {
                            summaryText += `  - ${s.description}\n`;
                        });
                    }
                } else {
                    summaryText += "\nNo specific action items, decisions, or questions were identified for follow-up from the provided context.\n";
                }

                if (followUpInfo.errorMessage) {
                    summaryText += `\n⚠️ Issues encountered: ${followUpInfo.errorMessage}\n`;
                }
                textResponse = summaryText;

            } else {
                textResponse = `Sorry, I couldn't generate follow-up suggestions. ${response.error?.message || 'Unknown error'}`;
            }

        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "SuggestFollowUps":`, error.message, error.stack);
            textResponse = "Sorry, an unexpected error occurred while generating follow-up suggestions.";
        }
        break;

      case "GenerateWeeklyDigest":
        try {
            const entities = nluResponse.entities as GenerateWeeklyDigestEntities;
            console.log(`[Handler][${interfaceType}] Intent: GenerateWeeklyDigest, Entities:`, JSON.stringify(entities));

            const response: GenerateWeeklyDigestResponse = await handleGenerateWeeklyDigest(
                userId,
                entities.time_period
            );

            if (response.ok && response.data) {
                const digestInfo = response.data.digest;
                let summaryText = `📅 Weekly Digest for ${new Date(digestInfo.periodStart).toLocaleDateString()} - ${new Date(digestInfo.periodEnd).toLocaleDateString()} 📅\n\n`;

                if (digestInfo.completedTasks.length > 0) {
                    summaryText += "🎉 Accomplishments This Period:\n";
                    digestInfo.completedTasks.forEach(task => {
                        summaryText += `  - ✅ ${task.description} (Completed)\n`;
                    });
                } else {
                    summaryText += "🎉 No specific tasks marked completed this period.\n";
                }

                if (digestInfo.attendedMeetings.length > 0) {
                    summaryText += "\n🗓️ Key Meetings Attended:\n";
                    digestInfo.attendedMeetings.forEach(meeting => {
                        summaryText += `  - 🗣️ ${meeting.summary} (On: ${new Date(meeting.startTime).toLocaleDateString()})\n`;
                    });
                } else {
                    summaryText += "\n🗓️ No significant meetings logged this period.\n";
                }

                summaryText += "\n🚀 Focus for Next Period:\n";
                if (digestInfo.upcomingCriticalTasks.length > 0) {
                    summaryText += "  Critical Tasks:\n";
                    digestInfo.upcomingCriticalTasks.forEach(task => {
                        summaryText += `    - ❗ ${task.description} (Due: ${task.dueDate || 'N/A'}, Prio: ${task.priority || 'N/A'})\n`;
                    });
                } else {
                    summaryText += "  No high-priority tasks specifically logged for next period yet.\n";
                }

                if (digestInfo.upcomingCriticalMeetings.length > 0) {
                    summaryText += "  Important Meetings:\n";
                    digestInfo.upcomingCriticalMeetings.forEach(meeting => {
                        summaryText += `    - 🎤 ${meeting.summary} (On: ${new Date(meeting.startTime).toLocaleDateString()})\n`;
                    });
                } else {
                    summaryText += "  No major meetings specifically logged for next period yet.\n";
                }

                if (digestInfo.errorMessage) {
                    summaryText += `\n⚠️ Issues encountered during digest generation: ${digestInfo.errorMessage}\n`;
                }
                textResponse = summaryText;
            } else {
                textResponse = `Sorry, I couldn't generate the weekly digest. ${response.error?.message || 'Unknown error'}`;
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "GenerateWeeklyDigest":`, error.message, error.stack);
            textResponse = "Sorry, an unexpected error occurred while generating your weekly digest.";
        }
        break;

      case "PrepareForMeeting":
        try {
          const entities = nluResponse.entities as PrepareForMeetingEntities;
          console.log(`[Handler][${interfaceType}] Intent: PrepareForMeeting, Entities:`, JSON.stringify(entities));

          const response: PrepareForMeetingResponse = await handlePrepareForMeeting(
            userId,
            entities.meeting_identifier,
            entities.meeting_date_time
          );

          if (response.ok && response.data) {
            const prepData = response.data;
            let summaryText = `Okay, here's some information for your meeting: "${prepData.targetMeeting.summary}" on ${new Date(prepData.targetMeeting.startTime).toLocaleString()}:\n`;

            if (prepData.relatedNotionPages && prepData.relatedNotionPages.length > 0) {
              summaryText += "\n📚 Relevant Notion Documents:\n";
              prepData.relatedNotionPages.forEach(p => {
                summaryText += `  - ${p.title} ${p.url ? `(Link: ${p.url})` : ''}\n    Snippet: ${p.briefSnippet || 'N/A'}\n`;
              });
            } else {
              summaryText += "\n📚 No specific Notion documents found this time.\n";
            }

            if (prepData.relatedEmails && prepData.relatedEmails.length > 0) {
              summaryText += "\n📧 Recent Relevant Emails:\n";
              prepData.relatedEmails.forEach(e => {
                summaryText += `  - Subject: "${e.subject}" (From: ${e.sender || 'N/A'})\n    Snippet: ${e.briefSnippet || 'N/A'}\n`;
              });
            } else {
              summaryText += "\n📧 No specific recent emails found this time.\n";
            }

            if (prepData.relatedTasks && prepData.relatedTasks.length > 0) {
              summaryText += "\n✅ Open Related Tasks:\n";
              prepData.relatedTasks.forEach(t => {
                summaryText += `  - ${t.description} (Due: ${t.dueDate || 'N/A'}, Status: ${t.status || 'N/A'})\n`;
              });
            } else {
              summaryText += "\n✅ No specific open tasks found related to this meeting.\n";
            }

            if (prepData.keyPointsFromLastMeeting) {
                summaryText += `\n📌 Key Points from Last Similar Meeting:\n  - ${prepData.keyPointsFromLastMeeting}\n`;
            }

            if (prepData.errorMessage) {
                summaryText += `\n⚠️ Issues encountered during preparation: ${prepData.errorMessage}\n`;
            }
            textResponse = summaryText;

          } else {
            textResponse = `Sorry, I couldn't prepare for the meeting. ${response.error?.message || 'Unknown error'}`;
          }
        } catch (error: any) {
          console.error(`[Handler][${interfaceType}] Error in NLU Intent "PrepareForMeeting":`, error.message, error.stack);
          textResponse = "Sorry, an unexpected error occurred while preparing for your meeting.";
        }
        break;

      case "CreateCalendarEvent":
        textResponse = await handleCreateCalendarEvent(userId, entities);
        break;

      // --- Notion Task Management Intents ---
      case "CreateTask": // Assuming NLU intent name matches this
        try {
            // The NLU entities should align with CreateTaskHandlerNluEntities
            const taskEntities = entities as import('./command_handlers/createNotionTaskCommandHandler').CreateTaskHandlerNluEntities;
            if (!taskEntities.task_description) { // Basic validation
                 textResponse = "Please provide a description for the task.";
            } else {
                textResponse = await handleCreateTaskRequest(userId, taskEntities);
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "CreateTask":`, error.message, error.stack);
            textResponse = "Sorry, an error occurred while creating your task.";
        }
        break;

      case "QueryTasks": // Assuming NLU intent name matches this
        try {
            // The NLU entities should align with QueryTasksHandlerNluEntities
            const queryEntities = entities as import('./command_handlers/queryNotionTasksCommandHandler').QueryTasksHandlerNluEntities;
            textResponse = await handleQueryTasksRequest(userId, queryEntities);
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "QueryTasks":`, error.message, error.stack);
            textResponse = "Sorry, an error occurred while querying your tasks.";
        }
        break;

      case "UpdateTask": // Assuming NLU intent name matches this
        try {
            // The NLU entities should align with UpdateTaskHandlerNluEntities
            const updateEntities = entities as import('./command_handlers/updateNotionTaskCommandHandler').UpdateTaskHandlerNluEntities;
             if (!updateEntities.task_identifier_text) { // Basic validation
                 textResponse = "Please specify which task you want to update by its name or part of its description.";
            } else {
                textResponse = await handleUpdateTaskRequest(userId, updateEntities);
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "UpdateTask":`, error.message, error.stack);
            textResponse = "Sorry, an error occurred while updating your task.";
        }
        break;
      // --- End Notion Task Management Intents ---

      // --- Gmail AI Powered Querying Intents ---
      case "SearchGmail": // New Intent for AI Powered Search
        try {
            // NLU entities should align with SearchGmailNluEntities defined in gmailSkills.ts
            const searchGmailEntities = entities as SearchGmailNluEntities;
            if (!searchGmailEntities.raw_query_text || searchGmailEntities.raw_query_text.trim() === "") {
                textResponse = "Please tell me what you'd like to search for in your Gmail.";
            } else {
                const limit = typeof searchGmailEntities.limit_number === 'number' ? searchGmailEntities.limit_number : 10; // Default limit
                const skillResponse = await handleSearchGmail(userId, searchGmailEntities.raw_query_text, limit);
                if (skillResponse.ok && skillResponse.data) {
                    textResponse = skillResponse.data.userMessage;
                } else {
                    textResponse = skillResponse.data?.userMessage || skillResponse.error?.message || "Sorry, I couldn't complete the Gmail search.";
                }
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "SearchGmail":`, error.message, error.stack);
            textResponse = "Sorry, an unexpected error occurred while searching your Gmail.";
        }
        break;

      case "ExtractInfoFromEmail": // New Intent
        try {
            // NLU entities should align with ExtractInfoFromGmailNluEntities from gmailSkills.ts
            const extractEntities = entities as ExtractInfoFromGmailNluEntities;
            if (!extractEntities.information_keywords || extractEntities.information_keywords.length === 0) {
                textResponse = "Please specify what information you want me to extract from the email.";
            } else if (!extractEntities.email_id && !extractEntities.email_reference_context) {
                textResponse = "Please specify which email you're referring to (e.g., by its ID or a reference like 'last email from support').";
            }
            else {
                const emailIdOrRef = extractEntities.email_id || extractEntities.email_reference_context!; // One must be present due to above check
                const skillResponse = await handleExtractInfoFromGmail(userId, emailIdOrRef, extractEntities.information_keywords, extractEntities.email_body_context);
                 if (skillResponse.ok && skillResponse.data) {
                    textResponse = skillResponse.data.userMessage;
                } else {
                    textResponse = skillResponse.data?.userMessage || skillResponse.error?.message || "Sorry, I couldn't extract information from the email.";
                }
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "ExtractInfoFromEmail":`, error.message, error.stack);
            textResponse = "Sorry, an unexpected error occurred while extracting information from the email.";
        }
        break;
      // --- End Gmail AI Powered Querying Intents ---

      // --- Slack AI Powered Querying Intents ---
      case "SearchSlackMessages": // New Intent
        try {
            const searchSlackEntities = entities as SearchSlackMessagesNluEntities;
            if (!searchSlackEntities.raw_query_text || searchSlackEntities.raw_query_text.trim() === "") {
                textResponse = "Please tell me what you'd like to search for in Slack.";
            } else {
                const limit = typeof searchSlackEntities.limit_number === 'number' ? searchSlackEntities.limit_number : 20;
                const skillResponse = await handleSearchSlackMessages(userId, searchSlackEntities.raw_query_text, limit);
                if (skillResponse.ok && skillResponse.data) {
                    textResponse = skillResponse.data.userMessage;
                } else {
                    textResponse = skillResponse.data?.userMessage || skillResponse.error?.message || "Sorry, I couldn't complete the Slack search.";
                }
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "SearchSlackMessages":`, error.message, error.stack);
            textResponse = "Sorry, an unexpected error occurred while searching Slack.";
        }
        break;

      case "ExtractInfoFromSlackMessage": // New Intent
        try {
            const extractSlackEntities = entities as ExtractInfoFromSlackMessageNluEntities;
            if (!extractSlackEntities.information_keywords || extractSlackEntities.information_keywords.length === 0) {
                textResponse = "Please specify what information you want me to extract from the Slack message.";
            } else if (!extractSlackEntities.message_reference_text) {
                textResponse = "Please specify which Slack message you're referring to (e.g., by its permalink or a description like 'last message from bob').";
            } else {
                const skillResponse = await handleExtractInfoFromSlackMessage(userId, extractSlackEntities.message_reference_text, extractSlackEntities.information_keywords, extractSlackEntities.message_text_context);
                if (skillResponse.ok && skillResponse.data) {
                    textResponse = skillResponse.data.userMessage;
                } else {
                    textResponse = skillResponse.data?.userMessage || skillResponse.error?.message || "Sorry, I couldn't extract information from the Slack message.";
                }
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "ExtractInfoFromSlackMessage":`, error.message, error.stack);
            textResponse = "Sorry, an unexpected error occurred while extracting information from the Slack message.";
        }
        break;
      // --- End Slack AI Powered Querying Intents ---

      // --- MS Teams AI Powered Querying Intents ---
      case "SearchMSTeamsMessages": // New Intent
        try {
            const searchTeamsEntities = entities as SearchMSTeamsMessagesNluEntities; // From msTeamsQuerySkills.ts
            if (!searchTeamsEntities.raw_query_text || searchTeamsEntities.raw_query_text.trim() === "") {
                textResponse = "Please tell me what you'd like to search for in Microsoft Teams.";
            } else {
                const limit = typeof searchTeamsEntities.limit_number === 'number' ? searchTeamsEntities.limit_number : 20;
                const skillResponse = await handleSearchMSTeamsMessages(userId, searchTeamsEntities.raw_query_text, limit);
                if (skillResponse.ok && skillResponse.data) {
                    textResponse = skillResponse.data.userMessage;
                } else {
                    textResponse = skillResponse.data?.userMessage || skillResponse.error?.message || "Sorry, I couldn't complete the Teams message search.";
                }
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "SearchMSTeamsMessages":`, error.message, error.stack);
            textResponse = "Sorry, an unexpected error occurred while searching your Teams messages.";
        }
        break;

      case "ExtractInfoFromMSTeamsMessage": // New Intent
        try {
            const extractTeamsEntities = entities as ExtractInfoFromMSTeamsMessageNluEntities; // From msTeamsQuerySkills.ts
            if (!extractTeamsEntities.information_keywords || extractTeamsEntities.information_keywords.length === 0) {
                textResponse = "Please specify what information you want me to extract from the Teams message.";
            } else if (!extractTeamsEntities.message_reference_text && !extractTeamsEntities.message_id) { // Check if either reference or direct ID is present
                textResponse = "Please specify which Teams message you're referring to (e.g., by its permalink, a description, or message ID).";
            } else {
                // Pass the whole entity object to the skill, it will figure out how to identify the message
                const skillResponse = await handleExtractInfoFromMSTeamsMessage(userId, extractTeamsEntities);
                if (skillResponse.ok && skillResponse.data) {
                    textResponse = skillResponse.data.userMessage;
                } else {
                    textResponse = skillResponse.data?.userMessage || skillResponse.error?.message || "Sorry, I couldn't extract information from the Teams message.";
                }
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "ExtractInfoFromMSTeamsMessage":`, error.message, error.stack);
            textResponse = "Sorry, an unexpected error occurred while extracting information from the Teams message.";
        }
        break;
      // --- End MS Teams AI Powered Querying Intents ---

      // Existing Email Intents (might be deprecated or refactored if SearchGmail covers their functionality)
      case "ListEmails": // This might be replaced by SearchGmail with an empty/generic query
        textResponse = await handleListEmails(nluResponse.entities);
        break;

      case "ReadEmail":
        textResponse = await handleReadEmail(nluResponse.entities);
        break;

      case "SendEmail":
        textResponse = await handleSendEmail(nluResponse.entities);
        break;

      case "SearchWeb":
        textResponse = await handleSearchWeb(nluResponse.entities);
        break;

      case "TriggerZap":
        textResponse = await handleTriggerZap(nluResponse.entities);
        break;

      case "GetHubSpotContactByEmail":
        textResponse = await handleGetHubSpotContactByEmail(userId, nluResponse.entities);
        break;

      case "SlackMyAgenda":
        textResponse = await handleSlackMyAgenda(userId, nluResponse.entities);
        break;
      case "ListCalendlyEventTypes":
        textResponse = await handleListCalendlyEventTypes(userId, nluResponse.entities);
        break;

      case "ListCalendlyScheduledEvents":
        textResponse = await handleListCalendlyScheduledEvents(userId, nluResponse.entities);
        break;

      case "ListZoomMeetings":
        textResponse = await handleListZoomMeetings(userId, nluResponse.entities);
        break;

      case "GetZoomMeetingDetails":
        textResponse = await handleGetZoomMeetingDetails(userId, nluResponse.entities);
        break;

      case "ListGoogleMeetEvents":
        textResponse = await handleListGoogleMeetEvents(userId, nluResponse.entities);
        break;

      case "GetGoogleMeetEventDetails":
        textResponse = await handleGetGoogleMeetEventDetails(userId, nluResponse.entities);
        break;

      case "ListMicrosoftTeamsMeetings":
        textResponse = await handleListMicrosoftTeamsMeetings(userId, nluResponse.entities);
        break;

      case "GetMicrosoftTeamsMeetingDetails":
        textResponse = await handleGetMicrosoftTeamsMeetingDetails(userId, nluResponse.entities);
        break;

      case "ListStripePayments":
        textResponse = await handleListStripePayments(userId, nluResponse.entities);
        break;

      case "GetStripePaymentDetails":
        textResponse = await handleGetStripePaymentDetails(userId, nluResponse.entities);
        break;

      case "GetQuickBooksAuthUrl":
        textResponse = await handleGetQuickBooksAuthUrl(userId, nluResponse.entities);
        break;

      case "ListQuickBooksInvoices":
        textResponse = await handleListQuickBooksInvoices(userId, nluResponse.entities);
        break;

      case "GetQuickBooksInvoiceDetails":
        textResponse = await handleGetQuickBooksInvoiceDetails(userId, nluResponse.entities);
        break;

      case "CreateTimePreferenceRule":
        try {
            const ruleDetails: NLUCreateTimePreferenceRuleEntities = {
                activity_description: nluResponse.entities?.activity_description as string,
                time_ranges: nluResponse.entities?.time_ranges as Array<{ start_time: string; end_time: string }>,
                days_of_week: nluResponse.entities?.days_of_week as string[],
                priority: nluResponse.entities?.priority,
                category_tags: nluResponse.entities?.category_tags as string[] | undefined,
            };
            if (!ruleDetails.activity_description || !ruleDetails.time_ranges || !Array.isArray(ruleDetails.time_ranges) || ruleDetails.time_ranges.length === 0 || !ruleDetails.days_of_week || !Array.isArray(ruleDetails.days_of_week) || ruleDetails.days_of_week.length === 0) {
                textResponse = "Missing required details (activity description, time ranges, or days of week) to create a time preference rule.";
            } else {
                const response: SchedulingResponse = await createSchedulingRule(userId, ruleDetails);
                textResponse = response.message;
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "CreateTimePreferenceRule":`, error.message, error.stack);
            textResponse = "Sorry, there was an issue processing your time preference rule request.";
        }
        break;

      case "BlockTimeSlot":
        try {
            const blockDetails: NLUBlockTimeSlotEntities = {
                task_name: nluResponse.entities?.task_name as string,
                start_time: nluResponse.entities?.start_time as string | undefined,
                end_time: nluResponse.entities?.end_time as string | undefined,
                duration: nluResponse.entities?.duration as string | undefined,
                date: nluResponse.entities?.date as string | undefined,
                purpose: nluResponse.entities?.purpose as string | undefined,
            };
            if (!blockDetails.task_name) {
                textResponse = "Missing task name to block time.";
            } else {
                const response: SchedulingResponse = await blockCalendarTime(userId, blockDetails);
                textResponse = response.message;
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "BlockTimeSlot":`, error.message, error.stack);
            textResponse = "Sorry, there was an issue processing your time blocking request.";
        }
        break;

      case "ScheduleTeamMeeting":
        try {
            const meetingDetails: NLUScheduleTeamMeetingEntities = {
                attendees: nluResponse.entities?.attendees as string[],
                purpose: nluResponse.entities?.purpose as string | undefined,
                duration_preference: nluResponse.entities?.duration_preference as string | undefined,
                time_preference_details: nluResponse.entities?.time_preference_details as string | undefined,
                meeting_title: nluResponse.entities?.meeting_title as string | undefined,
            };
            if (!meetingDetails.attendees || !Array.isArray(meetingDetails.attendees) || meetingDetails.attendees.length === 0) {
                textResponse = "Missing attendees (must be an array of strings) to schedule a team meeting.";
            } else {
                const response: SchedulingResponse = await initiateTeamMeetingScheduling(userId, meetingDetails);
                textResponse = response.message;
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "ScheduleTeamMeeting":`, error.message, error.stack);
            textResponse = "Sorry, there was an issue processing your team meeting request.";
        }
        break;

      case "CreateHubSpotContact":
        textResponse = await handleCreateHubSpotContact(userId, nluResponse.entities);
        break;

      case "SendSlackMessage":
        textResponse = await handleSendSlackMessage(userId, nluResponse.entities);
        break;

      // --- Autopilot Intents ---
      case "EnableAutopilot":
        try {
            console.log(`[Handler][${interfaceType}] Intent: EnableAutopilot, Entities:`, nluResponse.entities);
            // The query for enableAutopilot might need a structured JSON string.
            // For now, we'll try to use raw_query or stringify all entities.
            // This part will need refinement based on NLU capabilities for Autopilot.
            let autopilotQuery = "";
            if (nluResponse.entities?.raw_query && typeof nluResponse.entities.raw_query === 'string') {
                autopilotQuery = nluResponse.entities.raw_query;
            } else if (nluResponse.entities) {
                // Fallback: stringify all entities if raw_query isn't specific enough or available
                // This assumes `parseQuery` in autopilotSkills can handle it or it's a simple ID.
                autopilotQuery = JSON.stringify(nluResponse.entities);
            }

            const autopilotEnableResponse = await enableAutopilot(userId, autopilotQuery);
            if (autopilotEnableResponse.ok && autopilotEnableResponse.data) {
                textResponse = `Autopilot enabled successfully. Details: ${JSON.stringify(autopilotEnableResponse.data)}`;
            } else {
                textResponse = `Failed to enable Autopilot. Error: ${autopilotEnableResponse.error?.message || 'Unknown error'}`;
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "EnableAutopilot":`, error.message, error.stack);
            textResponse = "Sorry, there was an unexpected issue enabling Autopilot.";
        }
        break;

      case "DisableAutopilot":
        try {
            console.log(`[Handler][${interfaceType}] Intent: DisableAutopilot, Entities:`, nluResponse.entities);
            // Query for disable should ideally be the autopilotId/eventId
            let autopilotQuery = "";
            if (nluResponse.entities?.raw_query && typeof nluResponse.entities.raw_query === 'string') {
                autopilotQuery = nluResponse.entities.raw_query;
            } else if (nluResponse.entities?.autopilot_id && typeof nluResponse.entities.autopilot_id === 'string') {
                autopilotQuery = nluResponse.entities.autopilot_id;
            } else if (nluResponse.entities?.event_id && typeof nluResponse.entities.event_id === 'string') {
                autopilotQuery = nluResponse.entities.event_id; // Assuming event_id can be used as query
            } else if (nluResponse.entities) {
                 autopilotQuery = JSON.stringify(nluResponse.entities); // Fallback
            }

            if (!autopilotQuery) {
                textResponse = "Could not disable Autopilot: Missing ID in your request. Please specify the Autopilot ID or event ID.";
            } else {
                const autopilotDisableResponse = await disableAutopilot(userId, autopilotQuery);
                if (autopilotDisableResponse.ok && autopilotDisableResponse.data?.success) {
                    textResponse = "Autopilot disabled successfully.";
                } else {
                    textResponse = `Failed to disable Autopilot. Error: ${autopilotDisableResponse.error?.message || 'Unknown error or already disabled'}`;
                }
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "DisableAutopilot":`, error.message, error.stack);
            textResponse = "Sorry, there was an unexpected issue disabling Autopilot.";
        }
        break;

      case "GetAutopilotStatus":
        try {
            console.log(`[Handler][${interfaceType}] Intent: GetAutopilotStatus, Entities:`, nluResponse.entities);
            // Query for status can be empty (all for user) or specific autopilotId/eventId
            let autopilotQuery = "";
            if (nluResponse.entities?.raw_query && typeof nluResponse.entities.raw_query === 'string') {
                autopilotQuery = nluResponse.entities.raw_query;
            } else if (nluResponse.entities?.autopilot_id && typeof nluResponse.entities.autopilot_id === 'string') {
                autopilotQuery = nluResponse.entities.autopilot_id;
            } else if (nluResponse.entities?.event_id && typeof nluResponse.entities.event_id === 'string') {
                autopilotQuery = nluResponse.entities.event_id; // Assuming event_id can be used as query
            }
            // If autopilotQuery is empty, getAutopilotStatus skill should handle it by listing all for the user.

            const autopilotStatusResponse = await getAutopilotStatus(userId, autopilotQuery);
            if (autopilotStatusResponse.ok && autopilotStatusResponse.data) {
                // Data could be AutopilotType or AutopilotType[]
                const statusData = autopilotStatusResponse.data;
                if (Array.isArray(statusData)) {
                    if (statusData.length === 0) {
                        textResponse = "No Autopilot configurations found for you.";
                    } else {
                        textResponse = `Found ${statusData.length} Autopilot configurations:\n`;
                        statusData.forEach(ap => {
                            textResponse += `- ID: ${ap.id}, Scheduled at: ${ap.scheduleAt}, Timezone: ${ap.timezone}\n`;
                        });
                    }
                } else { // Single AutopilotType object
                     textResponse = `Autopilot Status (ID: ${statusData.id}): Scheduled at ${statusData.scheduleAt} in ${statusData.timezone}. Payload: ${JSON.stringify(statusData.payload, null, 2)}`;
                }
            } else if (autopilotStatusResponse.ok && !autopilotStatusResponse.data) {
                 textResponse = "No specific Autopilot configuration found for the given query, or no configurations exist.";
            }
            else {
                textResponse = `Failed to get Autopilot status. Error: ${autopilotStatusResponse.error?.message || 'Unknown error'}`;
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "GetAutopilotStatus":`, error.message, error.stack);
            textResponse = "Sorry, there was an unexpected issue fetching Autopilot status.";
        }
        break;
      // --- End Autopilot Intents ---

      case "SCHEDULE_TASK": // Updated case for Agenda-based scheduling
        try {
          // NLU should provide entities like:
          // entities.when_value (e.g., "2024-08-15T10:00:00Z", "tomorrow at 10am", "every Monday at 9am")
          // entities.task_intent (e.g., "SEND_EMAIL")
          // entities.task_entities (e.g., { to: "user@example.com", subject: "Meeting Reminder" })
          // entities.task_description (e.g., "Send a reminder email to Bob about the project deadline")
          // entities.is_recurring (boolean, e.g., true if "every Monday")
          // entities.repeat_interval (e.g., "1 week", "every day", "0 0 * * 1" - cron for every Monday at midnight)
          // entities.repeat_timezone (e.g., "America/New_York")

          const whenParam = entities.when_value as string | Date | undefined;
          const originalIntentParam = entities.task_intent as string | undefined;
          const taskEntitiesParam = (entities.task_entities || {}) as Record<string, any>;
          const taskDescriptionParam = entities.task_description as string | undefined;
          const isRecurringParam = entities.is_recurring as boolean | undefined ?? false;
          const repeatIntervalParam = entities.repeat_interval as string | undefined;
          const repeatTimezoneParam = entities.repeat_timezone as string | undefined;

          // Attempt to get conversationId from conversationManager if available and needed
          // const currentConversationState = conversationManager.getConversationStateSnapshot(interfaceType);
          // const conversationIdParam = currentConversationState?.conversationId; // Assuming it exists on state

          if (!whenParam && (!isRecurringParam || !repeatIntervalParam)) {
            textResponse = "Please specify when the task should run or provide a valid recurrence rule.";
            break;
          }
          if (!originalIntentParam) {
            textResponse = "Please specify what task you want to schedule (e.g., the intent of the task).";
            break;
          }

          const scheduleParams: ScheduleTaskParams = {
            when: whenParam as string | Date, // NLU must ensure this is a type Agenda accepts
            originalUserIntent: originalIntentParam,
            entities: taskEntitiesParam,
            userId: userId, // userId is from _internalHandleMessage scope
                            // conversationId: conversationIdParam, // Pass if available and used by jobs
            taskDescription: taskDescriptionParam || `Scheduled: ${originalIntentParam}`,
            isRecurring: isRecurringParam,
            repeatInterval: repeatIntervalParam,
            repeatTimezone: repeatTimezoneParam,
          };

          console.log(`[Handler][${interfaceType}] SCHEDULE_TASK: Processing with Agenda direct scheduling. Params:`, JSON.stringify(scheduleParams, null, 2));

          try {
            let job;
            const jobName = 'EXECUTE_AGENT_ACTION'; // Must match the name defined in agendaService.ts
            const jobData: ScheduledAgentTaskData = {
              originalUserIntent: scheduleParams.originalUserIntent,
              entities: scheduleParams.entities,
              userId: scheduleParams.userId,
              conversationId: scheduleParams.conversationId,
            };

            if (scheduleParams.isRecurring && scheduleParams.repeatInterval) {
              // For recurring tasks, use agenda.every()
              // The 'when' parameter for `every` is the interval.
              // An optional options object can specify timezone, startDate, endDate, skipImmediate.
              const options: { timezone?: string; startDate?: Date; endDate?: Date, skipImmediate?: boolean } = {};
              if (scheduleParams.repeatTimezone) {
                options.timezone = scheduleParams.repeatTimezone;
              }
              // If 'when' was a specific start date for the recurrence, agenda.every might need careful handling
              // or a combination of a first `schedule` and then `every`.
              // For simplicity, assuming `repeatInterval` is like "1 day", "2 hours", or a cron string.
              // And `when` (if a date) is the first time it should run if not skipping immediate.
              // If `scheduleParams.when` is a Date, it could be used as `startDate`.
              if (scheduleParams.when instanceof Date) {
                  options.startDate = scheduleParams.when;
                  // Potentially set skipImmediate to true if the startDate is also the first run,
                  // and the interval itself would trigger it too soon.
                  // However, agenda.every's `interval, name, data, options` signature.
                  // `when` (the first arg to `every`) is the interval.
                  // The start time is handled by the job's `nextRunAt` which Agenda calculates.
                  // If a specific start time is needed for the *first* occurrence of a recurring job,
                  // and `every` doesn't directly support it as a simple "start now then repeat",
                  // one might schedule the first job with `agenda.schedule` and then the recurring one
                  // or adjust `nextRunAt` manually after defining with `every`.

                  // Let's assume `repeatInterval` is the primary driver for recurrence timing.
                  // `scheduleParams.when` (if a date) might inform the *first* run,
                  // but `agenda.every` focuses on the interval.
              }


              job = await agenda.every(scheduleParams.repeatInterval, jobName, jobData, options);
              textResponse = `Recurring task "${scheduleParams.taskDescription || scheduleParams.originalUserIntent}" scheduled to run ${scheduleParams.repeatInterval}.`;
              if (options.startDate) {
                textResponse += ` Starting from ${options.startDate.toLocaleString()}.`;
              }
            } else if (scheduleParams.when) {
              // For one-time tasks, use agenda.schedule()
              job = await agenda.schedule(scheduleParams.when, jobName, jobData);
              textResponse = `Task "${scheduleParams.taskDescription || scheduleParams.originalUserIntent}" scheduled for ${new Date(scheduleParams.when instanceof Date ? scheduleParams.when : scheduleParams.when).toLocaleString()}.`;
            } else {
              textResponse = "Cannot schedule task: 'when' must be provided for one-time tasks, or 'repeatInterval' for recurring tasks.";
              break;
            }
            console.log(`[Handler][${interfaceType}] Task scheduled with Agenda. Job Name: ${jobName}, Job ID: ${job?.attrs._id}`);
            // The `scheduleTask` function from `schedulingSkills.ts` might have contained more complex logic
            // (e.g., interacting with another scheduling system before Agenda).
            // If so, that logic needs to be merged here or `scheduleTask` adapted to use `agenda` directly.
            // For this integration, we are replacing its direct scheduling capability with Agenda.
            // textResponse = await scheduleTask(scheduleParams); // This line is now replaced by direct agenda calls.
          } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error scheduling task with Agenda:`, error.message, error.stack);
            textResponse = `Sorry, an error occurred while scheduling your task with Agenda: ${error.message}`;
          }

        } catch (error: any) {
          console.error(`[Handler][${interfaceType}] Error in NLU Intent "SCHEDULE_TASK" (Agenda):`, error.message, error.stack);
          textResponse = `Sorry, an error occurred while processing your schedule request: ${error.message}`;
        }
        break;

      case "SemanticSearchMeetingNotes": // This intent needs to be defined and recognized by your NLU service
        try {
          const skillArgs: SkillArgs = {
            command: "search_meeting_notes",
            params: nluResponse.entities || {},
            user_id: userId,
            raw_message: message
          };

          if (!skillArgs.params.query || typeof skillArgs.params.query !== 'string' || skillArgs.params.query.trim() === '') {
              textResponse = "Please specify what you'd like to search for in your meeting notes.";
          } else {
              console.log(`[Handler][${interfaceType}] Calling handleSemanticSearchMeetingNotesSkill with query: "${skillArgs.params.query}" for user ${userId}`);
              const skillOutput = await handleSemanticSearchMeetingNotesSkill(skillArgs);

              if (typeof skillOutput === 'string') {
                  textResponse = skillOutput;
                  structuredDataResponse = undefined;
              } else if (typeof skillOutput === 'object' && skillOutput.displayType === 'semantic_search_results') {
                  // This is the structured response
                  textResponse = skillOutput.summaryText; // Use the summary text for verbal/main text response
                  structuredDataResponse = skillOutput; // Pass the full structured data
                  console.log(`[Handler][${interfaceType}] SemanticSearchMeetingNotes returned structured data.`);
              } else {
                  // Fallback if the response is not a string and not the expected object structure
                  textResponse = "Received an unexpected data format from the search skill.";
                  structuredDataResponse = undefined;
                  console.warn(`[Handler][${interfaceType}] SemanticSearchMeetingNotes returned an unexpected data type:`, skillOutput);
              }
          }

          // Console log for textResponse, as structuredDataResponse might be large
          console.log(`[Handler][${interfaceType}] SemanticSearchMeetingNotes textResponse: ${textResponse.substring(0, 200)}...`);
        } catch (error: any) {
          console.error(`[Handler][${interfaceType}] Error in NLU Intent "SemanticSearchMeetingNotes":`, error.message, error.stack);
          textResponse = "Sorry, an error occurred while searching your meeting notes.";
          structuredDataResponse = undefined;
        }
        break;

      case "ScheduleMeetingFromEmail":
        try {
            const {
                attendees: attendeeStrings, // string[] from NLU
                duration: durationString, // e.g., "30 minutes"
                timing_preferences: timingPreferences, // e.g., "next week Wednesday afternoon"
                meeting_summary: meetingSummary,
                original_email_body: originalEmailBody,
                original_email_subject: originalEmailSubject
            } = entities;

            if (!attendeeStrings || !Array.isArray(attendeeStrings) || attendeeStrings.length === 0) {
                textResponse = "Please specify who to invite to the meeting.";
                break;
            }
            if (!meetingSummary || typeof meetingSummary !== 'string') {
                textResponse = "Please provide a summary or title for the meeting.";
                break;
            }

            console.log(`[Handler][${interfaceType}][ScheduleMeetingFromEmail] Received request. Attendees: ${attendeeStrings.join(', ')}, Summary: ${meetingSummary}`);

            // 1. Resolve Attendees
            const resolvedAttendeesResponse = await resolveAttendees(attendeeStrings as string[], userId);
            if (!resolvedAttendeesResponse.ok || !resolvedAttendeesResponse.data) {
                textResponse = `I had trouble finding contact details for some attendees: ${resolvedAttendeesResponse.error?.message || 'Unknown error'}`;
                break;
            }
            const resolvedAttendeesList = resolvedAttendeesResponse.data;
            const internalAttendeeUserIds = resolvedAttendeesList.filter(a => a.userId && a.source === 'atom_user').map(a => a.userId!);

            console.log(`[Handler][${interfaceType}][ScheduleMeetingFromEmail] Resolved attendees:`, resolvedAttendeesList);
            console.log(`[Handler][${interfaceType}][ScheduleMeetingFromEmail] Internal Atom user IDs for availability check:`, internalAttendeeUserIds);

            // 2. Get Availability for internal users
            const now = new Date();
            const windowStart = now.toISOString();
            const windowEnd = new Date(new Date(now).setDate(now.getDate() + 14)).toISOString(); // Default to 2 weeks window

            let usersAvailabilityData = [];
            if (internalAttendeeUserIds.length > 0) {
                // const availabilityResponse = await getUsersAvailability(internalAttendeeUserIds, windowStart, windowEnd); // Assuming getUsersAvailability exists
                // if (!availabilityResponse.ok || !availabilityResponse.data) {
                //     textResponse = `Could not fetch availability for some users: ${availabilityResponse.error?.message || 'Unknown error'}`;
                //     console.warn(`[Handler][${interfaceType}][ScheduleMeetingFromEmail] Failed to get availability for some users.`);
                // } else {
                //     usersAvailabilityData = availabilityResponse.data;
                // }
                console.log(`[Handler][${interfaceType}][ScheduleMeetingFromEmail] TODO: Call actual getUsersAvailability. Placeholder for availability data.`);
            }
            console.log(`[Handler][${interfaceType}][ScheduleMeetingFromEmail] Availability data for internal users (placeholder):`, usersAvailabilityData);

            textResponse = `Okay, I've received the request to schedule a meeting: "${meetingSummary}" with ${attendeeStrings.join(', ')}. I will work on finding a time and will notify you. (Full scheduling logic including OptaPlanner is a TODO).`;
            console.log(`[Handler][${interfaceType}][ScheduleMeetingFromEmail] TODO: Implement full scheduling logic with OptaPlanner.`);

        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "ScheduleMeetingFromEmail":`, error.message, error.stack);
            textResponse = "Sorry, I encountered an error while trying to schedule the meeting from the email.";
        }
        break;

    // START_IN_PERSON_AUDIO_NOTE and related intents will be handled here
      case "START_IN_PERSON_AUDIO_NOTE":
      case "STOP_IN_PERSON_AUDIO_NOTE":
      case "CANCEL_IN_PERSON_AUDIO_NOTE":
        try {
            // Dynamically import the skill to avoid making it a hard dependency if not used often
            // Ensure the path is correct based on your project structure and build output.
            // This assumes inPersonAudioNoteSkills.ts is compiled to JS and accessible.
            const { InPersonAudioNoteDirectSkillManifest } = await import('./skills/inPersonAudioNoteSkills');
            const skillHandler = InPersonAudioNoteDirectSkillManifest.intentHandlers[nluResponse.intent as keyof typeof InPersonAudioNoteDirectSkillManifest.intentHandlers];

            if (skillHandler) {
                // Pass the constructed agentSkillContext to the skill handler
                const skillResponse = await skillHandler(nluResponse, agentSkillContext);
                textResponse = skillResponse.message;
                // If skillResponse contains other fields like a sessionTrackingId for the command,
                // it could be logged or used here if the agent framework supports it.
                // e.g., if (skillResponse.sessionTrackingId) {
                //   console.log(`[Handler][${interfaceType}] Audio note skill initiated client command with ID: ${skillResponse.sessionTrackingId}`);
                // }
            } else {
                textResponse = `I understood you want to ${nluResponse.intent}, but I'm not configured to handle that audio note action right now.`;
                console.warn(`[Handler][${interfaceType}] No skill handler found for intent: ${nluResponse.intent} in InPersonAudioNoteDirectSkillManifest.`);
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in In-Person Audio Note Intent "${nluResponse.intent}":`, error.message, error.stack);
            textResponse = "Sorry, there was an issue managing your in-person audio note request.";
        }
        break;


      default:
        if (nluResponse.error) {
             console.log(`[InternalHandleMessage][${interfaceType}] NLU processed with intent '${nluResponse.intent}' but also had an error: ${nluResponse.error}`);
        }
        textResponse = `I understood your intent as '${nluResponse.intent}' with entities ${JSON.stringify(nluResponse.entities)}, but I'm not fully set up to handle that specific request conversationally yet. You can try specific commands or 'help'.`;
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
export async function handleMessage(message: string): Promise<HandleMessageResponse> {
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
