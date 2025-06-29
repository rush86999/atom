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
} from '../types';

import { executeGraphQLQuery } from './_libs/graphqlClient'; // For getUserIdByEmail

// --- Interface Definitions for Agent-Client Communication and Skill Context ---

// Defines the structure of commands sent from the agent to the client (e.g., via WebSocket)
// This should align with the command structure expected by the frontend client.
interface AgentClientCommand {
  command_id: string; // Unique ID for tracking the command
  action: 'START_RECORDING_SESSION' | 'STOP_RECORDING_SESSION' | 'CANCEL_RECORDING_SESSION'; // Specific actions client can perform
  payload?: {
    suggestedTitle?: string;
    linkedEventId?: string;
    // Other relevant parameters for the client action
  };
}

// Defines the context object that will be passed to agent skills.
// It includes common utilities or functions that skills might need.
interface AgentSkillContext {
  userId: string;
  // Function to send a command to the connected client.
  // The actual implementation of this function is expected to be injected by the calling environment (e.g., WebSocket handler in server.ts).
  sendCommandToClient: (userId: string, command: AgentClientCommand) => Promise<boolean>;
  // Potentially add other context items:
  // - Access to LTM/STM (though memoryManager functions are currently imported directly)
  // - User preferences relevant to skills
  // - API clients if they are not globally available or need user-specific configuration
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
    LANCEDB_LTM_AGENT_TABLE_NAME // Added for LTM table name
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
): Promise<{text: string, nluResponse?: ProcessedNLUResponse}> {
  let textResponse: string;
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
    return { text: textResponse, nluResponse };
  }

  // Process NLU response and execute skills
  // All console logs within this block should also be prefixed with [interfaceType]
  if (nluResponse.intent) {
    const entities = nluResponse.entities || {};
    // Log intent and entities with interfaceType
    console.log(`[Handler][${interfaceType}] Intent: ${nluResponse.intent}, Entities: ${JSON.stringify(entities)}`);

    switch (nluResponse.intent) {
      case "GetCalendarEvents":
        try {
            let limit = 7;
            if (entities.limit) {
                if (typeof entities.limit === 'number') {
                    limit = entities.limit;
                } else if (typeof entities.limit === 'string') {
                    const parsedLimit = parseInt(entities.limit, 10);
                    if (!isNaN(parsedLimit)) limit = parsedLimit;
                }
            }
            const date_range = entities.date_range as string | undefined;
            const event_type_filter = entities.event_type_filter as string | undefined;
            const time_query = entities.time_query as string | undefined;
            const query_type = entities.query_type as string | undefined;

            if (time_query) console.log(`[Handler][${interfaceType}] GetCalendarEvents: time_query found - ${time_query}`);
            if (query_type) console.log(`[Handler][${interfaceType}] GetCalendarEvents: query_type found - ${query_type}`);
            if (date_range) console.log(`[Handler][${interfaceType}] GetCalendarEvents: date_range found - ${date_range}.`);
            if (event_type_filter) console.log(`[Handler][${interfaceType}] GetCalendarEvents: event_type_filter found - ${event_type_filter}.`);

            const events: CalendarEvent[] = await listUpcomingEvents(userId, limit);
            if (!events || events.length === 0) {
                textResponse = "No upcoming calendar events found matching your criteria, or I couldn't access them.";
            } else {
                const eventList = events.map(event =>
                    `- ${event.summary} (from ${new Date(event.startTime).toLocaleString()} to ${new Date(event.endTime).toLocaleString()})${event.location ? ` - Loc: ${event.location}` : ''}${event.htmlLink ? ` [Link: ${event.htmlLink}]` : ''}`
                ).join('\n');
                textResponse = `Upcoming calendar events:\n${eventList}`;
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "GetCalendarEvents":`, error.message);
            textResponse = "Sorry, I couldn't fetch your calendar events due to an error.";
        }
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
        try {
          // Ensure entities is cast to the correct type, MeetingPrepNluEntities should be available from '../types'
          const prepEntities = nluResponse.entities as import('../types').MeetingPrepNluEntities;
          if (!prepEntities.meeting_reference || !prepEntities.information_requests) {
            textResponse = "To prepare for a meeting, please tell me which meeting and what information you're looking for.";
            console.warn(`[Handler][${interfaceType}] RequestMeetingPreparation: Missing meeting_reference or information_requests.`);
          } else {
            console.info(`[Handler][${interfaceType}] Calling handleMeetingPreparationRequest for meeting: "${prepEntities.meeting_reference}"`);
            textResponse = await handleMeetingPreparationRequest(userId, prepEntities);
          }
        } catch (error: any) {
          console.error(`[Handler][${interfaceType}] Error in NLU Intent "RequestMeetingPreparation":`, error.message, error.stack);
          textResponse = "Sorry, an unexpected error occurred while preparing for your meeting.";
        }
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
        try {
            const { summary, start_time, end_time, description, location, attendees } = entities;
            const duration = entities.duration as string | undefined;

            if (!summary || typeof summary !== 'string') {
                textResponse = "Event summary is required to create an event via NLU.";
            } else if (!start_time || typeof start_time !== 'string') {
                textResponse = "Event start time is required to create an event via NLU.";
            } else if (!end_time && !duration) {
                textResponse = "Event end time or duration is required to create an event via NLU.";
            } else {
                const eventDetails: Partial<CalendarEvent & { duration?: string }> = {
                    summary: summary as string,
                    startTime: start_time as string,
                    endTime: end_time as string | undefined,
                    description: typeof description === 'string' ? description : undefined,
                    location: typeof location === 'string' ? location : undefined,
                    attendees: Array.isArray(attendees) ? attendees.filter(att => typeof att === 'string') : undefined,
                };
                if (duration) {
                    eventDetails.duration = duration;
                    console.log(`[Handler][${interfaceType}] CreateCalendarEvent: duration found - ${duration}`);
                }
                const response: CreateEventResponse = await createCalendarEvent(userId, eventDetails);
                if (response.success) {
                    textResponse = `Event created: ${response.message || 'Successfully created event.'} (ID: ${response.eventId || 'N/A'})${response.htmlLink ? ` Link: ${response.htmlLink}` : ''}`;
                } else {
                    textResponse = `Failed to create calendar event via NLU. ${response.message || 'Please check your connection or try again.'}`;
                }
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "CreateCalendarEvent":`, error.message);
            textResponse = "Sorry, I couldn't create the calendar event due to an error.";
        }
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

        case "ListEmails":
        try {
            let limit = 10; // Default limit
            if (nluResponse.entities?.limit) {
                if (typeof nluResponse.entities.limit === 'number') limit = nluResponse.entities.limit;
                else if (typeof nluResponse.entities.limit === 'string') {
                    const parsedLimit = parseInt(nluResponse.entities.limit, 10);
                    if (!isNaN(parsedLimit)) limit = parsedLimit;
                }
            }
            const emails: Email[] = await listRecentEmails(limit);
            if (emails.length === 0) {
                textResponse = "No recent emails found (via NLU).";
            } else {
                const emailList = emails.map(email =>
                    `- (${email.read ? 'read' : 'unread'}) From: ${email.sender}, Subject: ${email.subject} (ID: ${email.id})`
                ).join('\n');
                textResponse = `Recent emails (via NLU):\n${emailList}`;
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "ListEmails":`, error.message);
            textResponse = "Sorry, I couldn't fetch recent emails due to an error (NLU path).";
        }
        break;

      case "ReadEmail":
        try {
            const { email_id } = nluResponse.entities;
            if (!email_id || typeof email_id !== 'string') {
                textResponse = "Email ID is required to read an email via NLU.";
            } else {
                const response: ReadEmailResponse = await readEmail(email_id);
                if (response.success && response.email) {
                    const email = response.email;
                    textResponse = `Email (ID: ${email.id}):\nFrom: ${email.sender}\nTo: ${email.recipient}\nSubject: ${email.subject}\nDate: ${email.timestamp}\n\n${email.body}`;
                } else {
                    textResponse = response.message || "Could not read email via NLU.";
                }
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "ReadEmail":`, error.message);
            textResponse = "Sorry, I couldn't read the specified email due to an error (NLU path).";
        }
        break;

      case "SendEmail":
        try {
            const { to, subject, body } = nluResponse.entities;
            if (!to || typeof to !== 'string') {
                textResponse = "Recipient 'to' address is required to send an email via NLU.";
            } else if (!subject || typeof subject !== 'string') {
                textResponse = "Subject is required to send an email via NLU.";
            } else if (!body || typeof body !== 'string') {
                textResponse = "Body is required to send an email via NLU.";
            } else {
                const emailDetails: EmailDetails = { to, subject, body };
                const response: SendEmailResponse = await sendEmail(emailDetails);
                if (response.success) {
                    textResponse = `Email sent via NLU: ${response.message} (ID: ${response.emailId})`;
                } else {
                    textResponse = `Failed to send email via NLU: ${response.message}`;
                }
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "SendEmail":`, error.message);
            textResponse = "Sorry, I couldn't send the email due to an error (NLU path).";
        }
        break;

      case "SearchWeb":
        try {
            const { query } = nluResponse.entities;
            if (!query || typeof query !== 'string') {
                textResponse = "A search query is required to search the web via NLU.";
            } else {
                const results: SearchResult[] = await searchWeb(query);
                if (results.length === 0) {
                    textResponse = `No web results found for "${query}" (via NLU).`;
                } else {
                    const resultList = results.map(result =>
                        `- ${result.title}\n  Link: ${result.link}\n  Snippet: ${result.snippet}`
                    ).join('\n\n');
                    textResponse = `Web search results for "${query}" (via NLU):\n\n${resultList}`;
                }
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "SearchWeb":`, error.message);
            textResponse = "Sorry, I couldn't perform the web search due to an error (NLU path).";
        }
        break;

      case "TriggerZap":
        try {
            const { zap_name, data } = nluResponse.entities;
            if (!zap_name || typeof zap_name !== 'string') {
                textResponse = "Zap name is required to trigger a Zap via NLU.";
            } else {
                const zapData: ZapData = (typeof data === 'object' && data !== null) ? data : {};
                const response: ZapTriggerResponse = await triggerZap(zap_name, zapData);
                if (response.success) {
                    textResponse = `Zap triggered via NLU: ${response.message} (Run ID: ${response.runId})`;
                } else {
                    textResponse = `Failed to trigger Zap via NLU: ${response.message}`;
                }
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "TriggerZap":`, error.message);
            textResponse = "Sorry, I couldn't trigger the Zap due to an error (NLU path).";
        }
        break;

      case "GetHubSpotContactByEmail":
        try {
            const emailEntity = nluResponse.entities?.email;
            if (!emailEntity || typeof emailEntity !== 'string' || emailEntity.trim() === '') {
              textResponse = "Email is required and must be a non-empty string to get a HubSpot contact by email.";
            } else {
              const contact: HubSpotContact | null = await getHubSpotContactByEmail(userId, emailEntity);
              if (contact) {
                const name = `${contact.properties.firstname || ''} ${contact.properties.lastname || ''}`.trim();
                let responseString = `HubSpot Contact Found:\nID: ${contact.id}\nName: ${name || 'N/A'}\nEmail: ${contact.properties.email || 'N/A'}\nCompany: ${contact.properties.company || 'N/A'}`;
                if (contact.properties.createdate) responseString += `\nCreated: ${new Date(contact.properties.createdate).toLocaleString()}`;
                if (contact.properties.lastmodifieddate) responseString += `\nLast Modified: ${new Date(contact.properties.lastmodifieddate).toLocaleString()}`;
                if (ATOM_HUBSPOT_PORTAL_ID && contact.id) responseString += `\nView in HubSpot: https://app.hubspot.com/contacts/${ATOM_HUBSPOT_PORTAL_ID}/contact/${contact.id}`;
                textResponse = responseString;
              } else {
                textResponse = `No HubSpot contact found with email: ${emailEntity}.`;
              }
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "GetHubSpotContactByEmail":`, error.message, error.stack);
            textResponse = "Sorry, an error occurred while trying to retrieve the HubSpot contact.";
        }
        break;

      case "SlackMyAgenda":
        try {
            const limit = nluResponse.entities?.limit && typeof nluResponse.entities.limit === 'number' ? nluResponse.entities.limit : 5;
            const events: CalendarEvent[] = await listUpcomingEvents(userId, limit);
            if (!events || events.length === 0) {
                const noEventsMessage = "You have no upcoming events on your calendar for the near future, or I couldn't access them (NLU path).";
                try {
                    await sendSlackMessage(userId, userId, noEventsMessage);
                    textResponse = "I've checked your calendar; no upcoming events. Sent a note to your Slack DM (NLU path).";
                } catch (dmError:any) {
                    textResponse = "No upcoming events found. Tried to DM you on Slack, but failed (NLU path).";
                }
            } else {
                let formattedAgenda = `🗓️ Your Upcoming Events (via NLU):\n`;
                for (const event of events) {
                    const startTime = new Date(event.startTime).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
                    const endTime = new Date(event.endTime).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
                    formattedAgenda += `- ${event.summary} (from ${startTime} to ${endTime})`;
                    if (event.location) formattedAgenda += ` - Location: ${event.location}`;
                    if (event.htmlLink) formattedAgenda += ` [View: ${event.htmlLink}]`;
                    formattedAgenda += "\n";
                }
                const slackResponse = await sendSlackMessage(userId, userId, formattedAgenda);
                if (slackResponse.ok) {
                    textResponse = "I've sent your agenda to your Slack DM (NLU path)!";
                } else {
                    textResponse = `Sorry, I couldn't send your agenda to Slack (NLU path). Error: ${slackResponse.error}`;
                }
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "SlackMyAgenda":`, error.message);
            textResponse = "Sorry, an error occurred while processing your agenda for Slack (NLU path).";
        }
        break;
      case "ListCalendlyEventTypes":
        try {
            const calendlyUserId = nluResponse.entities?.user_id && typeof nluResponse.entities.user_id === 'string' ? nluResponse.entities.user_id : userId;
            const response: ListCalendlyEventTypesResponse = await listCalendlyEventTypes(calendlyUserId);
            if (response.ok && response.collection && response.collection.length > 0) {
                let output = "Your Calendly Event Types (via NLU):\n";
                for (const et of response.collection) {
                    output += `- ${et.name} (${et.duration} mins) - Active: ${et.active} - URL: ${et.scheduling_url}\n`;
                }
                if (response.pagination?.next_page_token) {
                    output += `More event types available. Use next page token: ${response.pagination.next_page_token}\n`;
                }
                textResponse = output;
            } else if (response.ok) {
                textResponse = "No active Calendly event types found (via NLU).";
            } else {
                textResponse = `Error fetching Calendly event types (via NLU): ${response.error || 'Unknown error'}`;
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "ListCalendlyEventTypes":`, error.message);
            textResponse = "Sorry, an unexpected error occurred while fetching your Calendly event types (NLU path).";
        }
        break;

      case "ListCalendlyScheduledEvents":
        try {
            const calendlyUserId = nluResponse.entities?.user_id && typeof nluResponse.entities.user_id === 'string' ? nluResponse.entities.user_id : userId;
            const count = nluResponse.entities?.count && typeof nluResponse.entities.count === 'number' ? nluResponse.entities.count : 10;
            const status = nluResponse.entities?.status && typeof nluResponse.entities.status === 'string' ? nluResponse.entities.status as ('active' | 'canceled') : 'active';
            const sort = nluResponse.entities?.sort && typeof nluResponse.entities.sort === 'string' ? nluResponse.entities.sort : 'start_time:asc';
            const options = { count, status, sort, user: calendlyUserId };
            const response: ListCalendlyScheduledEventsResponse = await listCalendlyScheduledEvents(calendlyUserId, options);
            if (response.ok && response.collection && response.collection.length > 0) {
                let output = `Your Calendly Bookings (${status}, via NLU):\n`;
                for (const se of response.collection) {
                    output += `- ${se.name} (Starts: ${new Date(se.start_time).toLocaleString()}, Ends: ${new Date(se.end_time).toLocaleString()}) - Status: ${se.status}\n`;
                }
                if (response.pagination?.next_page_token) {
                    output += `More bookings available. Use next page token: ${response.pagination.next_page_token}\n`;
                }
                textResponse = output;
            } else if (response.ok) {
                textResponse = `No ${status} scheduled Calendly bookings found (via NLU).`;
            } else {
                textResponse = `Error fetching Calendly bookings (via NLU): ${response.error || 'Unknown error'}`;
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "ListCalendlyScheduledEvents":`, error.message);
            textResponse = "Sorry, an unexpected error occurred while fetching your Calendly bookings (NLU path).";
        }
        break;

      case "ListZoomMeetings":
        try {
            const userIdForZoom = "me";
            const type = (nluResponse.entities?.type && typeof nluResponse.entities.type === 'string' ? nluResponse.entities.type : 'upcoming') as 'live' | 'upcoming' | 'scheduled' | 'upcoming_meetings' | 'previous_meetings';
            const page_size = nluResponse.entities?.page_size && typeof nluResponse.entities.page_size === 'number' ? nluResponse.entities.page_size : 30;
            const next_page_token = nluResponse.entities?.next_page_token && typeof nluResponse.entities.next_page_token === 'string' ? nluResponse.entities.next_page_token : undefined;
            const options = { type, page_size, next_page_token };
            const response: ListZoomMeetingsResponse = await listZoomMeetings(userIdForZoom, options);
            if (response.ok && response.meetings && response.meetings.length > 0) {
                let output = `Your Zoom Meetings (${type}, via NLU):\n`;
                for (const meeting of response.meetings) {
                    output += `- ${meeting.topic} (ID: ${meeting.id}) - Start: ${meeting.start_time ? new Date(meeting.start_time).toLocaleString() : 'N/A'} - Join: ${meeting.join_url || 'N/A'}\n`;
                }
                if (response.next_page_token) {
                    output += `More meetings available. For next page, use token: ${response.next_page_token}\n`;
                }
                textResponse = output;
            } else if (response.ok) {
                textResponse = "No Zoom meetings found matching your criteria (via NLU).";
            } else {
                textResponse = `Error fetching Zoom meetings (via NLU): ${response.error || 'Unknown error'}`;
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "ListZoomMeetings":`, error.message);
            textResponse = "Sorry, an unexpected error occurred while fetching your Zoom meetings (NLU path).";
        }
        break;

      case "GetZoomMeetingDetails":
        try {
            const { meeting_id } = nluResponse.entities;
            if (!meeting_id || typeof meeting_id !== 'string') {
                textResponse = "Zoom Meeting ID is required to get details via NLU.";
            } else {
                const response: GetZoomMeetingDetailsResponse = await getZoomMeetingDetails(meeting_id);
                if (response.ok && response.meeting) {
                    const m = response.meeting;
                    textResponse = `Zoom Meeting Details (via NLU):\nTopic: ${m.topic}\nID: ${m.id}\nStart Time: ${m.start_time ? new Date(m.start_time).toLocaleString() : 'N/A'}\nDuration: ${m.duration || 'N/A'} mins\nJoin URL: ${m.join_url || 'N/A'}\nAgenda: ${m.agenda || 'N/A'}`;
                } else {
                    textResponse = `Error fetching Zoom meeting details (via NLU): ${response.error || `Meeting with ID ${meeting_id} not found or an unknown error occurred.`}`;
                }
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "GetZoomMeetingDetails":`, error.message);
            textResponse = `Sorry, an unexpected error occurred while fetching details for Zoom meeting ${nluResponse.entities.meeting_id} (NLU path).`;
        }
        break;

      case "ListGoogleMeetEvents":
        try {
            const limit = nluResponse.entities?.limit && typeof nluResponse.entities.limit === 'number' ? nluResponse.entities.limit : 5;
            const response: ListGoogleMeetEventsResponse = await listUpcomingGoogleMeetEvents(userId, limit);
            if (response.ok && response.events && response.events.length > 0) {
                let output = "Your Upcoming Google Meet Events (via NLU):\n";
                for (const event of response.events) {
                    const meetLink = event.conferenceData?.entryPoints?.find(ep => ep.entryPointType === 'video' && ep.uri?.startsWith('https://meet.google.com/'))?.uri;
                    output += `- ${event.summary} (Starts: ${new Date(event.startTime).toLocaleString()})${meetLink ? ` - Link: ${meetLink}` : ' (No direct Meet link found, check calendar event details)'}\n`;
                }
                textResponse = output;
            } else if (response.ok) {
                textResponse = "No upcoming Google Meet events found (via NLU).";
            } else {
                textResponse = `Error fetching Google Meet events (via NLU): ${response.error || 'Unknown error'}`;
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "ListGoogleMeetEvents":`, error.message);
            textResponse = "Sorry, an unexpected error occurred while fetching your Google Meet events (NLU path).";
        }
        break;

      case "GetGoogleMeetEventDetails":
        try {
            const { event_id } = nluResponse.entities;
            if (!event_id || typeof event_id !== 'string') {
                textResponse = "Google Calendar Event ID is required to get details via NLU.";
            } else {
                const response: GetGoogleMeetEventDetailsResponse = await getGoogleMeetEventDetails(userId, event_id);
                if (response.ok && response.event) {
                    const ev = response.event;
                    let output = `Event (via NLU): ${ev.summary}\nStart: ${new Date(ev.startTime).toLocaleString()}\nEnd: ${new Date(ev.endTime).toLocaleString()}`;
                    const meetLink = ev.conferenceData?.entryPoints?.find(ep => ep.entryPointType === 'video' && ep.uri?.startsWith('https://meet.google.com/'))?.uri;
                    if (meetLink) output += `\nMeet Link: ${meetLink}`;
                    else if (ev.conferenceData?.conferenceSolution?.name) output += `\nConference: ${ev.conferenceData.conferenceSolution.name} (Details might be in description or calendar entry)`;
                    else output += "\n(No Google Meet link or explicit conference data found for this event)";
                    if (ev.htmlLink) output += `\nCalendar Link: ${ev.htmlLink}`;
                    if (ev.description) output += `\nDescription: ${ev.description}`;
                    textResponse = output;
                } else {
                    textResponse = `Error fetching Google Meet event details (via NLU): ${response.error || `Event with ID ${event_id} not found or an unknown error occurred.`}`;
                }
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "GetGoogleMeetEventDetails":`, error.message);
            textResponse = `Sorry, an unexpected error occurred while fetching details for event ${nluResponse.entities.event_id} (NLU path).`;
        }
        break;

      case "ListMicrosoftTeamsMeetings":
        try {
            const userPrincipalNameOrId = "me";
            const limit = nluResponse.entities?.limit && typeof nluResponse.entities.limit === 'number' ? nluResponse.entities.limit : 10;
            const next_link = nluResponse.entities?.next_link && typeof nluResponse.entities.next_link === 'string' ? nluResponse.entities.next_link : undefined;
            const options = { limit, nextLink: next_link, filterForTeams: true };
            const response: ListMSTeamsMeetingsResponse = await listMicrosoftTeamsMeetings(userPrincipalNameOrId, options);
            if (response.ok && response.events && response.events.length > 0) {
                let output = "Your Microsoft Teams Meetings (via NLU):\n";
                for (const event of response.events) {
                    output += `- ${event.subject} (ID: ${event.id}) - Start: ${event.start?.dateTime ? new Date(event.start.dateTime).toLocaleString() : 'N/A'} - Join: ${event.onlineMeeting?.joinUrl || 'N/A'}\n`;
                }
                if (response.nextLink) {
                    output += `More meetings available. Next page link (for API use): ${response.nextLink}\nTo get next page, you could say: list teams meetings with limit ${limit} and next_link ${response.nextLink}\n`;
                }
                textResponse = output;
            } else if (response.ok) {
                textResponse = "No Microsoft Teams meetings found matching your criteria (via NLU).";
            } else {
                textResponse = `Error fetching Microsoft Teams meetings (via NLU): ${response.error || 'Unknown error'}`;
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "ListMicrosoftTeamsMeetings":`, error.message);
            textResponse = "Sorry, an unexpected error occurred while fetching your Microsoft Teams meetings (NLU path).";
        }
        break;

      case "GetMicrosoftTeamsMeetingDetails":
        try {
            const userPrincipalNameOrId = "me";
            const { event_id } = nluResponse.entities;
            if (!event_id || typeof event_id !== 'string') {
                textResponse = "Microsoft Graph Event ID is required to get Teams meeting details via NLU.";
            } else {
                const response: GetMSTeamsMeetingDetailsResponse = await getMicrosoftTeamsMeetingDetails(userPrincipalNameOrId, event_id);
                if (response.ok && response.event) {
                    const ev = response.event;
                    let output = `Teams Meeting (via NLU): ${ev.subject}\nID: ${ev.id}\nStart: ${ev.start?.dateTime ? new Date(ev.start.dateTime).toLocaleString() : 'N/A'}\nEnd: ${ev.end?.dateTime ? new Date(ev.end.dateTime).toLocaleString() : 'N/A'}`;
                    if (ev.onlineMeeting?.joinUrl) output += `\nJoin URL: ${ev.onlineMeeting.joinUrl}`;
                    if (ev.bodyPreview) output += `\nPreview: ${ev.bodyPreview}`;
                    if (ev.webLink) output += `\nOutlook Link: ${ev.webLink}`;
                    textResponse = output;
                } else {
                    textResponse = `Error fetching Teams meeting details (via NLU): ${response.error || `Meeting with ID ${event_id} not found or an unknown error occurred.`}`;
                }
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "GetMicrosoftTeamsMeetingDetails":`, error.message);
            textResponse = `Sorry, an unexpected error occurred while fetching details for Teams meeting ${nluResponse.entities.event_id} (NLU path).`;
        }
        break;

      case "ListStripePayments":
        try {
            const { limit, starting_after, customer } = nluResponse.entities;
            const options: { limit?: number; starting_after?: string; customer?: string } = {};
            if (limit && typeof limit === 'number') options.limit = limit; else options.limit = 10;
            if (starting_after && typeof starting_after === 'string') options.starting_after = starting_after;
            if (customer && typeof customer === 'string') options.customer = customer;
            const response: ListStripePaymentsResponse = await listStripePayments(options);
            if (response.ok && response.payments && response.payments.length > 0) {
                let output = "Stripe Payments (via NLU):\n";
                for (const payment of response.payments) {
                    output += `- ID: ${payment.id}, Amount: ${(payment.amount / 100).toFixed(2)} ${payment.currency.toUpperCase()}, Status: ${payment.status}, Created: ${new Date(payment.created * 1000).toLocaleDateString()}${payment.latest_charge?.receipt_url ? `, Receipt: ${payment.latest_charge.receipt_url}` : ''}\n`;
                }
                if (response.has_more && response.payments.length > 0) {
                    output += `More payments available. For next page, use option: starting_after=${response.payments[response.payments.length - 1].id}\n`;
                }
                textResponse = output;
            } else if (response.ok) {
                textResponse = "No Stripe payments found matching your criteria (via NLU).";
            } else {
                textResponse = `Error fetching Stripe payments (via NLU): ${response.error || 'Unknown error'}`;
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "ListStripePayments":`, error.message);
            textResponse = "Sorry, an unexpected error occurred while fetching Stripe payments (NLU path).";
        }
        break;

      case "GetStripePaymentDetails":
        try {
            const { payment_intent_id } = nluResponse.entities;
            if (!payment_intent_id || typeof payment_intent_id !== 'string') {
                textResponse = "Stripe PaymentIntent ID is required to get details via NLU.";
            } else {
                const response: GetStripePaymentDetailsResponse = await getStripePaymentDetails(payment_intent_id);
                if (response.ok && response.payment) {
                    const p = response.payment;
                    let output = `Stripe Payment Details (ID: ${p.id}, via NLU):\nAmount: ${(p.amount / 100).toFixed(2)} ${p.currency.toUpperCase()}\nStatus: ${p.status}\nCreated: ${new Date(p.created * 1000).toLocaleString()}\nDescription: ${p.description || 'N/A'}`;
                    if (p.customer) output += `\nCustomer ID: ${p.customer}`;
                    if (p.latest_charge?.receipt_url) output += `\nReceipt URL: ${p.latest_charge.receipt_url}`;
                    textResponse = output;
                } else {
                    textResponse = `Error fetching Stripe payment details (via NLU): ${response.error || `PaymentIntent with ID ${payment_intent_id} not found or an unknown error occurred.`}`;
                }
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "GetStripePaymentDetails":`, error.message);
            textResponse = `Sorry, an unexpected error occurred while fetching Stripe payment details for ${nluResponse.entities.payment_intent_id} (NLU path).`;
        }
        break;

      case "GetQuickBooksAuthUrl":
        try {
            const authUri = getQuickBooksAuthUri();
            if (authUri) {
                textResponse = `To authorize QuickBooks Online (via NLU), please visit this URL in your browser: ${authUri}\nAfter authorization, the agent will need the resulting tokens and realmId to be stored in its configured token file path (${ATOM_QB_TOKEN_FILE_PATH}). This step typically requires manual intervention or a separate callback handler not part of this command.`;
            } else {
                textResponse = "Could not generate QuickBooks authorization URL (via NLU). Please check server configuration.";
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "GetQuickBooksAuthUrl":`, error.message);
            textResponse = "Sorry, an error occurred while generating the QuickBooks authorization URL (NLU path).";
        }
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
        try {
            const { email, first_name, last_name, contact_name, company_name } = nluResponse.entities;
            if (!email || typeof email !== 'string') {
                textResponse = "Email is required (and must be a string) to create a HubSpot contact via NLU.";
            } else {
                let finalFirstName = first_name;
                let finalLastName = last_name;
                if (!finalFirstName && !finalLastName && contact_name && typeof contact_name === 'string') {
                    const nameParts = contact_name.split(' ');
                    finalFirstName = nameParts[0];
                    if (nameParts.length > 1) finalLastName = nameParts.slice(1).join(' ');
                }
                const contactDetails: HubSpotContactProperties = {
                    email,
                    firstname: typeof finalFirstName === 'string' ? finalFirstName : undefined,
                    lastname: typeof finalLastName === 'string' ? finalLastName : undefined,
                    company: typeof company_name === 'string' ? company_name : undefined,
                };
                const hubspotResponse: CreateHubSpotContactResponse = await createHubSpotContact(userId, contactDetails);
                if (hubspotResponse.success && hubspotResponse.contactId && hubspotResponse.hubSpotContact) {
                    const contact = hubspotResponse.hubSpotContact;
                    const name = `${contact.properties.firstname || ''} ${contact.properties.lastname || ''}`.trim() || 'N/A';
                    textResponse = `HubSpot contact created via NLU! ID: ${hubspotResponse.contactId}. Name: ${name}. Email: ${contact.properties.email}.`;
                } else {
                    textResponse = `Failed to create HubSpot contact via NLU: ${hubspotResponse.message || 'Unknown HubSpot error.'}`;
                }
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "CreateHubSpotContact":`, error.message);
            textResponse = "Sorry, there was an issue creating the HubSpot contact based on your request.";
        }
        break;

      case "SendSlackMessage":
        try {
            const { slack_channel, message_text } = nluResponse.entities;
            if (!slack_channel || typeof slack_channel !== 'string') {
                textResponse = "Slack channel/user ID is required to send a message via NLU.";
            } else if (!message_text || typeof message_text !== 'string') {
                textResponse = "Message text is required to send a Slack message via NLU.";
            } else {
                const slackResponse = await sendSlackMessage(userId, slack_channel, message_text);
                if (slackResponse.ok) {
                    textResponse = `Message sent to Slack channel/user ${slack_channel}.`;
                } else {
                    textResponse = `Failed to send Slack message to ${slack_channel} via NLU. Error: ${slackResponse.error}`;
                }
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "SendSlackMessage":`, error.message);
            textResponse = "Sorry, there was an issue sending your Slack message.";
        }
        break;

      case "ListQuickBooksInvoices":
        try {
            const { customer_id, status, limit: nluLimit, offset: nluOffset } = nluResponse.entities;
            const options: { limit?: number; offset?: number; customerId?: string; status?: string } = {};
            if (nluLimit) {
                 if (typeof nluLimit === 'number') options.limit = nluLimit;
                 else if (typeof nluLimit === 'string') { const parsed = parseInt(nluLimit, 10); if (!isNaN(parsed)) options.limit = parsed; }
            }
            if (nluOffset) {
                 if (typeof nluOffset === 'number') options.offset = nluOffset;
                 else if (typeof nluOffset === 'string') { const parsed = parseInt(nluOffset, 10); if (!isNaN(parsed)) options.offset = parsed; }
            }
            if (customer_id && typeof customer_id === 'string') options.customerId = customer_id;
            if (status && typeof status === 'string') console.log(`[Handler][${interfaceType}] NLU: ListQuickBooksInvoices received status filter: ${status}. Currently illustrative, skill may not filter by it.`);
            const response: ListQuickBooksInvoicesResponse = await listQuickBooksInvoices(options);
             if (response.ok && response.invoices && response.invoices.length > 0) {
                let output = "QuickBooks Invoices (via NLU):\n";
                for (const inv of response.invoices) {
                    output += `- ID: ${inv.Id}, Num: ${inv.DocNumber || 'N/A'}, Cust: ${inv.CustomerRef?.name || inv.CustomerRef?.value || 'N/A'}, Total: ${inv.TotalAmt !== undefined ? inv.TotalAmt.toFixed(2) : 'N/A'} ${inv.CurrencyRef?.value || ''}\n`;
                }
                if (response.queryResponse) output += `Showing results. Max per page: ${response.queryResponse.maxResults || options.limit}\n`;
                textResponse = output;
            } else if (response.ok) {
                textResponse = "No QuickBooks invoices found via NLU matching your criteria.";
            } else {
                textResponse = `Error fetching QuickBooks invoices via NLU: ${response.error || 'Unknown error'}. Ensure QuickBooks is connected and authorized.`;
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "ListQuickBooksInvoices":`, error.message);
            textResponse = "Sorry, an error occurred while fetching QuickBooks invoices via NLU.";
        }
        break;

      case "GetQuickBooksInvoiceDetails":
        try {
            const { invoice_id } = nluResponse.entities;
            if (!invoice_id || typeof invoice_id !== 'string') {
                textResponse = "Invoice ID is required to get QuickBooks invoice details via NLU.";
            } else {
                const response: GetQuickBooksInvoiceDetailsResponse = await getQuickBooksInvoiceDetails(invoice_id);
                if (response.ok && response.invoice) {
                    const inv = response.invoice;
                    textResponse = `QuickBooks Invoice (ID: ${inv.Id}):\nDoc #: ${inv.DocNumber || 'N/A'}\nCustomer: ${inv.CustomerRef?.name || inv.CustomerRef?.value || 'N/A'}\nTotal: ${inv.TotalAmt !== undefined ? inv.TotalAmt.toFixed(2) : 'N/A'} ${inv.CurrencyRef?.value || ''}\nBalance: ${inv.Balance !== undefined ? inv.Balance.toFixed(2) : 'N/A'}`;
                } else {
                    textResponse = `Error fetching QuickBooks invoice details via NLU: ${response.error || 'Invoice not found or error occurred.'}`;
                }
            }
        } catch (error: any) {
            console.error(`[Handler][${interfaceType}] Error in NLU Intent "GetQuickBooksInvoiceDetails":`, error.message);
            textResponse = "Sorry, an error occurred while fetching QuickBooks invoice details via NLU.";
        }
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
              textResponse = await handleSemanticSearchMeetingNotesSkill(skillArgs); // No ApiHelper needed now
          }

          console.log(`[Handler][${interfaceType}] SemanticSearchMeetingNotes response: ${textResponse.substring(0, 200)}...`);
        } catch (error: any) {
          console.error(`[Handler][${interfaceType}] Error in NLU Intent "SemanticSearchMeetingNotes":`, error.message, error.stack);
          textResponse = "Sorry, an error occurred while searching your meeting notes.";
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

  return { text: textResponse, nluResponse };
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
  payload: { text: string }
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
  const { text: coreResponseText, nluResponse } = await _internalHandleMessage(interfaceType, text, userId);

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
        return { text: coreResponseText, audioUrl: ttsResult.audio_url };
      } else {
        console.error(`[Handler][${interfaceType}] TTS response OK, but no audio_url:`, ttsResult);
        conversationManager.setAgentResponding(interfaceType, false); // Agent finished processing (with error)
        return { text: coreResponseText, error: "TTS synthesis succeeded but no audio URL was returned." };
      }
    } else {
      const errorBody = await ttsResponse.text();
      console.error(`[Handler][${interfaceType}] TTS request failed:`, ttsResponse.status, errorBody);
      conversationManager.setAgentResponding(interfaceType, false); // Agent finished processing (with error)
      return { text: coreResponseText, error: `Failed to synthesize audio. Status: ${ttsResponse.status}` };
    }
  } catch (error: any) {
    console.error(`[Handler][${interfaceType}] Error calling TTS service:`, error.message, error.stack);
    conversationManager.setAgentResponding(interfaceType, false); // Agent finished processing (with error)
    return { text: coreResponseText, error: "Error occurred during audio synthesis." };
  }
}


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

  const { text: coreResponseText, nluResponse } = await _internalHandleMessage(interfaceType, message, userId);

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
    } catch (error) {
      console.error(`[Handler][${interfaceType}] Error initiating STM to LTM processing:`, error);
    }
  }

  // For 'text' interface, we do NOT call TTS.
  // conversationManager.setAgentResponding(interfaceType, false); // Agent has finished.

  // Deactivate after single text interaction, unless a longer session is desired.
  // For now, let's assume single interaction for Hasura.
  conversationManager.deactivateConversation(interfaceType, "completed_text_interaction");


  return { text: coreResponseText }; // No audioUrl or error from TTS for text interface.
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
