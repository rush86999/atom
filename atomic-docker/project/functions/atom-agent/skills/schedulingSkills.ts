import { agenda, ScheduledAgentTaskData } from '../../../agendaService'; // Adjusted path

// New ScheduleTaskParams interface for Agenda-based scheduling
export interface ScheduleTaskParams {
  taskDescription?: string; // Description of the task for logging/confirmation
  when: string | Date;       // Date string (ISO), human-readable ("tomorrow at 10am"), Date object, or cron string for recurring
  originalUserIntent: string; // The actual agent intent to be executed (e.g., "SEND_EMAIL", "CREATE_CALENDAR_EVENT")
  entities: Record<string, any>; // Entities required for the originalUserIntent
  userId: string;
  conversationId?: string;   // Optional: for context
  // For recurring tasks (using agenda.every)
  isRecurring?: boolean;         // Flag to indicate if the task is recurring
  repeatInterval?: string;     // e.g., "1 day", "2 hours", cron string. Used if isRecurring is true.
  repeatTimezone?: string;     // Optional: Timezone for recurring tasks, e.g., "America/New_York"
}

/**
 * Schedules a task (agent action) to be executed at a specified time or interval using Agenda.
 *
 * @param params - The parameters for scheduling the task.
 * @returns A promise that resolves to a string message indicating success or failure.
 */
export async function scheduleTask(params: ScheduleTaskParams): Promise<string> {
  const {
    when,
    originalUserIntent,
    entities,
    userId,
    conversationId,
    taskDescription, // Used for confirmation messages
    isRecurring,
    repeatInterval,
    repeatTimezone,
  } = params;

  // Validate essential parameters for scheduling
  if (!when) {
    return "Scheduling time ('when') must be provided.";
  }
  if (!originalUserIntent) {
    return "The original user intent to be scheduled must be provided.";
  }
  if (!userId) {
    return "User ID must be provided for scheduling.";
  }

  const jobData: ScheduledAgentTaskData = {
    originalUserIntent,
    entities: entities || {}, // Ensure entities is at least an empty object
    userId,
    conversationId,
  };

  try {
    let jobDetailsMessage: string;

    if (isRecurring && repeatInterval) {
      const options: { timezone?: string; startDate?: Date } = {};
      if (repeatTimezone) {
        options.timezone = repeatTimezone;
      }
      if (when instanceof Date || (typeof when === 'string' && !when.includes('*') && !when.toLowerCase().startsWith('every'))) {
      }

      await agenda.every(repeatInterval, 'EXECUTE_AGENT_ACTION', jobData, options);
      jobDetailsMessage = `Recurring task "${taskDescription || originalUserIntent}" scheduled to run based on interval: ${repeatInterval}.`;
      console.log(`Recurring task for intent '${originalUserIntent}' for user '${userId}' scheduled. Interval: ${repeatInterval}. Data:`, JSON.stringify(jobData));

    } else {
      if (typeof when !== 'string' && !(when instanceof Date)) {
        return "Invalid 'when' parameter for a one-time task. Must be a date string or Date object.";
      }
      await agenda.schedule(when, 'EXECUTE_AGENT_ACTION', jobData);
      jobDetailsMessage = `Task "${taskDescription || originalUserIntent}" has been scheduled for ${typeof when === 'string' ? when : when.toISOString()}.`;
      console.log(`One-time task for intent '${originalUserIntent}' for user '${userId}' scheduled for '${when}'. Data:`, JSON.stringify(jobData));
    }

    return jobDetailsMessage;

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error(`Error scheduling task for intent '${originalUserIntent}' for user '${userId}':`, errorMessage, error);
    return `Failed to schedule task: ${errorMessage}`;
  }
}

export interface CancelTaskParams {
  jobId?: string;
  jobName?: string;
  userId?: string;
  originalUserIntent?: string;
}

export async function cancelTask(params: CancelTaskParams): Promise<string> {
    try {
        const query: any = {};
        if (params.jobName) {
            query.name = params.jobName;
        }
        if (params.userId) {
            query['data.userId'] = params.userId;
        }
        if (params.originalUserIntent) {
            query['data.originalUserIntent'] = params.originalUserIntent;
        }

        if (Object.keys(query).length === 0 && !params.jobId) {
            return "No criteria provided to cancel tasks. Please specify jobName, userId, or originalUserIntent.";
        }

        const numRemoved = await agenda.cancel(query);

        if (numRemoved > 0) {
            return `Successfully cancelled ${numRemoved} task(s) matching criteria.`;
        } else {
            return "No tasks found matching the criteria to cancel.";
        }
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        console.error('Error cancelling task(s):', errorMessage, error);
        return `Failed to cancel task(s): ${errorMessage}`;
    }
}


// --- User Availability Functions ---
import {
    UserAvailability,
    UserWorkTime,
    CalendarEvent,
    SkillResponse,
    SkillError,
    // Types for NLU entities if needed for scheduling functions
    NLUCreateTimePreferenceRuleEntities,
    NLUBlockTimeSlotEntities,
    NLUScheduleTeamMeetingEntities,
    SchedulingResponse,
    SkillResponse // Added for invokeOptaPlannerScheduling
} from '../types';
import { executeGraphQLQuery } from '../_libs/graphqlClient';
import { ATOM_OPTAPLANNER_API_BASE_URL } from '../_libs/constants'; // For OptaPlanner URL
import axios from 'axios'; // For making HTTP requests to OptaPlanner
import { listUpcomingEvents } from './calendarSkills';
import { HASURA_GRAPHQL_URL, HASURA_ADMIN_SECRET } from '../_libs/constants';


async function _fetchUserWorkTimes(userId: string): Promise<UserWorkTime[]> {
    console.log(`[_fetchUserWorkTimes] Fetching work times for user ${userId}`);
    if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
        console.error("[_fetchUserWorkTimes] GraphQL client not configured.");
        return [];
    }

    const query = `
        query GetUserWorkPreferences($userId: String!) {
            user_work_preferences(where: {user_id: {_eq: $userId}}) {
                day_of_week
                start_time
                end_time
            }
        }
    `;
    const variables = { userId };
    const operationName = 'GetUserWorkPreferences';

    try {
        const response = await executeGraphQLQuery<{ user_work_preferences: Array<{ day_of_week: string; start_time: string; end_time: string }> }>(
            query,
            variables,
            operationName,
            userId
        );

        if (response && response.user_work_preferences) {
            return response.user_work_preferences.map(pref => ({
                dayOfWeek: pref.day_of_week.toUpperCase() as UserWorkTime['dayOfWeek'],
                startTime: pref.start_time,
                endTime: pref.end_time,
            }));
        }
        return [];
    } catch (error: any) {
        console.error(`[_fetchUserWorkTimes] Error fetching work times for user ${userId}:`, error);
        return [];
    }
}

export async function getUsersAvailability(
    userIds: string[],
    windowStart: string,
    windowEnd: string
): Promise<SkillResponse<UserAvailability[]>> {
    console.log(`[schedulingSkills] Getting availability for users: ${userIds.join(', ')} within window: ${windowStart} to ${windowEnd}`);
    const allUsersAvailability: UserAvailability[] = [];
    const errors: SkillError[] = [];

    for (const userId of userIds) {
        try {
            const workTimes = await _fetchUserWorkTimes(userId);
            const eventsResponse = await listUpcomingEvents(userId, 250);
            let relevantEvents: CalendarEvent[] = [];

            if (eventsResponse.ok && eventsResponse.data) {
                const windowStartTime = new Date(windowStart).getTime();
                const windowEndTime = new Date(windowEnd).getTime();
                relevantEvents = eventsResponse.data.filter(event => {
                    try {
                        const eventStart = new Date(event.startTime).getTime();
                        const eventEnd = new Date(event.endTime).getTime();
                        return eventStart < windowEndTime && eventEnd > windowStartTime;
                    } catch (dateParseError) {
                        console.warn(`[getUsersAvailability] Could not parse event dates for event ID ${event.id}, user ${userId}:`, dateParseError);
                        return false;
                    }
                });
            } else {
                console.warn(`[getUsersAvailability] Could not fetch calendar events for user ${userId}: ${eventsResponse.error?.message}`);
                errors.push({
                    code: "CALENDAR_FETCH_FAILED",
                    message: `Failed to fetch calendar events for user ${userId}.`,
                    details: eventsResponse.error
                });
            }

            allUsersAvailability.push({
                userId,
                workTimes,
                calendarEvents: relevantEvents,
            });

        } catch (error: any) {
            console.error(`[getUsersAvailability] Critical error getting availability for user ${userId}: ${error.message}`);
            errors.push({
                code: "AVAILABILITY_FETCH_ERROR",
                message: `Failed to get availability for user ${userId}.`,
                details: error.message
            });
        }
    }

    if (errors.length > 0 && allUsersAvailability.length === 0) {
        return { ok: false, error: errors[0] };
    }

    return { ok: true, data: allUsersAvailability };
}

// TODO: Implement these functions based on NLU intents if they are still needed
// For now, they are placeholders as the primary focus is on the new email scheduling flow.
export async function createSchedulingRule(userId: string, ruleDetails: NLUCreateTimePreferenceRuleEntities): Promise<SchedulingResponse> {
    console.log("createSchedulingRule called with:", userId, ruleDetails);
    // Placeholder
    return { success: false, message: "createSchedulingRule not implemented." };
}

export async function blockCalendarTime(userId: string, blockDetails: NLUBlockTimeSlotEntities): Promise<SchedulingResponse> {
    console.log("blockCalendarTime called with:", userId, blockDetails);
    // Placeholder
    return { success: false, message: "blockCalendarTime not implemented." };
}

export async function initiateTeamMeetingScheduling(userId: string, meetingDetails: NLUScheduleTeamMeetingEntities): Promise<SchedulingResponse> {
    console.log("initiateTeamMeetingScheduling called with:", userId, meetingDetails);
    // This is where the call to OptaPlanner or similar scheduling AI would be made.
    // Placeholder
    return { success: false, message: "initiateTeamMeetingScheduling not implemented yet. This would call OptaPlanner." };
}
