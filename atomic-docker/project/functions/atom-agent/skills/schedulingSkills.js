import { agenda } from '@/agendaService'; // Adjusted path
/**
 * Schedules a task (agent action) to be executed at a specified time or interval using Agenda.
 *
 * @param params - The parameters for scheduling the task.
 * @returns A promise that resolves to a string message indicating success or failure.
 */
export async function scheduleTask(params) {
    const { when, originalUserIntent, entities, userId, conversationId, taskDescription, // Used for confirmation messages
    isRecurring, repeatInterval, repeatTimezone, } = params;
    // Validate essential parameters for scheduling
    if (!when) {
        return "Scheduling time ('when') must be provided.";
    }
    if (!originalUserIntent) {
        return 'The original user intent to be scheduled must be provided.';
    }
    if (!userId) {
        return 'User ID must be provided for scheduling.';
    }
    const jobData = {
        originalUserIntent,
        entities: entities || {}, // Ensure entities is at least an empty object
        userId,
        conversationId,
    };
    try {
        let jobDetailsMessage;
        if (isRecurring && repeatInterval) {
            const options = {};
            if (repeatTimezone) {
                options.timezone = repeatTimezone;
            }
            if (when instanceof Date ||
                (typeof when === 'string' &&
                    !when.includes('*') &&
                    !when.toLowerCase().startsWith('every'))) {
            }
            await agenda.every(repeatInterval, 'EXECUTE_AGENT_ACTION', jobData, options);
            jobDetailsMessage = `Recurring task "${taskDescription || originalUserIntent}" scheduled to run based on interval: ${repeatInterval}.`;
            console.log(`Recurring task for intent '${originalUserIntent}' for user '${userId}' scheduled. Interval: ${repeatInterval}. Data:`, JSON.stringify(jobData));
        }
        else {
            if (typeof when !== 'string' && !(when instanceof Date)) {
                return "Invalid 'when' parameter for a one-time task. Must be a date string or Date object.";
            }
            await agenda.schedule(when, 'EXECUTE_AGENT_ACTION', jobData);
            jobDetailsMessage = `Task "${taskDescription || originalUserIntent}" has been scheduled for ${typeof when === 'string' ? when : when.toISOString()}.`;
            console.log(`One-time task for intent '${originalUserIntent}' for user '${userId}' scheduled for '${when}'. Data:`, JSON.stringify(jobData));
        }
        return jobDetailsMessage;
    }
    catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        console.error(`Error scheduling task for intent '${originalUserIntent}' for user '${userId}':`, errorMessage, error);
        return `Failed to schedule task: ${errorMessage}`;
    }
}
export async function cancelTask(params) {
    try {
        const query = {};
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
            return 'No criteria provided to cancel tasks. Please specify jobName, userId, or originalUserIntent.';
        }
        const numRemoved = await agenda.cancel(query);
        if (numRemoved > 0) {
            return `Successfully cancelled ${numRemoved} task(s) matching criteria.`;
        }
        else {
            return 'No tasks found matching the criteria to cancel.';
        }
    }
    catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        console.error('Error cancelling task(s):', errorMessage, error);
        return `Failed to cancel task(s): ${errorMessage}`;
    }
}
import { executeGraphQLQuery } from '../_libs/graphqlClient';
import { listUpcomingEvents } from './calendarSkills';
import { HASURA_GRAPHQL_URL, HASURA_ADMIN_SECRET } from '../_libs/constants';
async function _fetchUserWorkTimes(userId) {
    console.log(`[_fetchUserWorkTimes] Fetching work times for user ${userId}`);
    if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
        console.error('[_fetchUserWorkTimes] GraphQL client not configured.');
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
        const response = await executeGraphQLQuery(query, variables, operationName, userId);
        if (response && response.user_work_preferences) {
            return response.user_work_preferences.map((pref) => ({
                dayOfWeek: pref.day_of_week.toUpperCase(),
                startTime: pref.start_time,
                endTime: pref.end_time,
            }));
        }
        return [];
    }
    catch (error) {
        console.error(`[_fetchUserWorkTimes] Error fetching work times for user ${userId}:`, error);
        return [];
    }
}
export async function getUsersAvailability(userIds, windowStart, windowEnd) {
    console.log(`[schedulingSkills] Getting availability for users: ${userIds.join(', ')} within window: ${windowStart} to ${windowEnd}`);
    const allUsersAvailability = [];
    const errors = [];
    for (const userId of userIds) {
        try {
            const workTimes = await _fetchUserWorkTimes(userId);
            const eventsResponse = await listUpcomingEvents(userId, 250);
            let relevantEvents = [];
            if (eventsResponse.ok && eventsResponse.data) {
                const windowStartTime = new Date(windowStart).getTime();
                const windowEndTime = new Date(windowEnd).getTime();
                relevantEvents = eventsResponse.data.filter((event) => {
                    try {
                        const eventStart = new Date(event.startTime).getTime();
                        const eventEnd = new Date(event.endTime).getTime();
                        return eventStart < windowEndTime && eventEnd > windowStartTime;
                    }
                    catch (dateParseError) {
                        console.warn(`[getUsersAvailability] Could not parse event dates for event ID ${event.id}, user ${userId}:`, dateParseError);
                        return false;
                    }
                });
            }
            else {
                console.warn(`[getUsersAvailability] Could not fetch calendar events for user ${userId}: ${eventsResponse.error?.message}`);
                errors.push({
                    code: 'CALENDAR_FETCH_FAILED',
                    message: `Failed to fetch calendar events for user ${userId}.`,
                    details: eventsResponse.error,
                });
            }
            allUsersAvailability.push({
                userId,
                workTimes,
                calendarEvents: relevantEvents,
            });
        }
        catch (error) {
            console.error(`[getUsersAvailability] Critical error getting availability for user ${userId}: ${error.message}`);
            errors.push({
                code: 'AVAILABILITY_FETCH_ERROR',
                message: `Failed to get availability for user ${userId}.`,
                details: error.message,
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
export async function handleScheduleSkillActivation(userId, entities) {
    const { skill_to_schedule, activation_time, skill_entities } = entities;
    if (!skill_to_schedule || !activation_time) {
        return 'I need to know which skill to schedule and when to schedule it.';
    }
    const params = {
        when: activation_time,
        originalUserIntent: skill_to_schedule,
        entities: skill_entities,
        userId: userId,
    };
    return scheduleTask(params);
}
export async function createSchedulingRule(userId, ruleDetails) {
    console.log('createSchedulingRule called with:', userId, ruleDetails);
    // Placeholder
    return { success: false, message: 'createSchedulingRule not implemented.' };
}
export async function blockCalendarTime(userId, blockDetails) {
    console.log('blockCalendarTime called with:', userId, blockDetails);
    // Placeholder
    return { success: false, message: 'blockCalendarTime not implemented.' };
}
export async function initiateTeamMeetingScheduling(userId, meetingDetails) {
    console.log('initiateTeamMeetingScheduling called with:', userId, meetingDetails);
    // This is where the call to OptaPlanner or similar scheduling AI would be made.
    // Placeholder
    return {
        success: false,
        message: 'initiateTeamMeetingScheduling not implemented yet. This would call OptaPlanner.',
    };
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic2NoZWR1bGluZ1NraWxscy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInNjaGVkdWxpbmdTa2lsbHMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUFFLE1BQU0sRUFBMEIsTUFBTSxpQkFBaUIsQ0FBQyxDQUFDLGdCQUFnQjtBQWdCbEY7Ozs7O0dBS0c7QUFDSCxNQUFNLENBQUMsS0FBSyxVQUFVLFlBQVksQ0FDaEMsTUFBMEI7SUFFMUIsTUFBTSxFQUNKLElBQUksRUFDSixrQkFBa0IsRUFDbEIsUUFBUSxFQUNSLE1BQU0sRUFDTixjQUFjLEVBQ2QsZUFBZSxFQUFFLGlDQUFpQztJQUNsRCxXQUFXLEVBQ1gsY0FBYyxFQUNkLGNBQWMsR0FDZixHQUFHLE1BQU0sQ0FBQztJQUVYLCtDQUErQztJQUMvQyxJQUFJLENBQUMsSUFBSSxFQUFFLENBQUM7UUFDVixPQUFPLDRDQUE0QyxDQUFDO0lBQ3RELENBQUM7SUFDRCxJQUFJLENBQUMsa0JBQWtCLEVBQUUsQ0FBQztRQUN4QixPQUFPLDREQUE0RCxDQUFDO0lBQ3RFLENBQUM7SUFDRCxJQUFJLENBQUMsTUFBTSxFQUFFLENBQUM7UUFDWixPQUFPLDBDQUEwQyxDQUFDO0lBQ3BELENBQUM7SUFFRCxNQUFNLE9BQU8sR0FBMkI7UUFDdEMsa0JBQWtCO1FBQ2xCLFFBQVEsRUFBRSxRQUFRLElBQUksRUFBRSxFQUFFLDhDQUE4QztRQUN4RSxNQUFNO1FBQ04sY0FBYztLQUNmLENBQUM7SUFFRixJQUFJLENBQUM7UUFDSCxJQUFJLGlCQUF5QixDQUFDO1FBRTlCLElBQUksV0FBVyxJQUFJLGNBQWMsRUFBRSxDQUFDO1lBQ2xDLE1BQU0sT0FBTyxHQUE0QyxFQUFFLENBQUM7WUFDNUQsSUFBSSxjQUFjLEVBQUUsQ0FBQztnQkFDbkIsT0FBTyxDQUFDLFFBQVEsR0FBRyxjQUFjLENBQUM7WUFDcEMsQ0FBQztZQUNELElBQ0UsSUFBSSxZQUFZLElBQUk7Z0JBQ3BCLENBQUMsT0FBTyxJQUFJLEtBQUssUUFBUTtvQkFDdkIsQ0FBQyxJQUFJLENBQUMsUUFBUSxDQUFDLEdBQUcsQ0FBQztvQkFDbkIsQ0FBQyxJQUFJLENBQUMsV0FBVyxFQUFFLENBQUMsVUFBVSxDQUFDLE9BQU8sQ0FBQyxDQUFDLEVBQzFDLENBQUM7WUFDSCxDQUFDO1lBRUQsTUFBTSxNQUFNLENBQUMsS0FBSyxDQUNoQixjQUFjLEVBQ2Qsc0JBQXNCLEVBQ3RCLE9BQU8sRUFDUCxPQUFPLENBQ1IsQ0FBQztZQUNGLGlCQUFpQixHQUFHLG1CQUFtQixlQUFlLElBQUksa0JBQWtCLHlDQUF5QyxjQUFjLEdBQUcsQ0FBQztZQUN2SSxPQUFPLENBQUMsR0FBRyxDQUNULDhCQUE4QixrQkFBa0IsZUFBZSxNQUFNLDBCQUEwQixjQUFjLFNBQVMsRUFDdEgsSUFBSSxDQUFDLFNBQVMsQ0FBQyxPQUFPLENBQUMsQ0FDeEIsQ0FBQztRQUNKLENBQUM7YUFBTSxDQUFDO1lBQ04sSUFBSSxPQUFPLElBQUksS0FBSyxRQUFRLElBQUksQ0FBQyxDQUFDLElBQUksWUFBWSxJQUFJLENBQUMsRUFBRSxDQUFDO2dCQUN4RCxPQUFPLHFGQUFxRixDQUFDO1lBQy9GLENBQUM7WUFDRCxNQUFNLE1BQU0sQ0FBQyxRQUFRLENBQUMsSUFBSSxFQUFFLHNCQUFzQixFQUFFLE9BQU8sQ0FBQyxDQUFDO1lBQzdELGlCQUFpQixHQUFHLFNBQVMsZUFBZSxJQUFJLGtCQUFrQiw0QkFBNEIsT0FBTyxJQUFJLEtBQUssUUFBUSxDQUFDLENBQUMsQ0FBQyxJQUFJLENBQUMsQ0FBQyxDQUFDLElBQUksQ0FBQyxXQUFXLEVBQUUsR0FBRyxDQUFDO1lBQ3RKLE9BQU8sQ0FBQyxHQUFHLENBQ1QsNkJBQTZCLGtCQUFrQixlQUFlLE1BQU0sb0JBQW9CLElBQUksVUFBVSxFQUN0RyxJQUFJLENBQUMsU0FBUyxDQUFDLE9BQU8sQ0FBQyxDQUN4QixDQUFDO1FBQ0osQ0FBQztRQUVELE9BQU8saUJBQWlCLENBQUM7SUFDM0IsQ0FBQztJQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7UUFDZixNQUFNLFlBQVksR0FBRyxLQUFLLFlBQVksS0FBSyxDQUFDLENBQUMsQ0FBQyxLQUFLLENBQUMsT0FBTyxDQUFDLENBQUMsQ0FBQyxNQUFNLENBQUMsS0FBSyxDQUFDLENBQUM7UUFDNUUsT0FBTyxDQUFDLEtBQUssQ0FDWCxxQ0FBcUMsa0JBQWtCLGVBQWUsTUFBTSxJQUFJLEVBQ2hGLFlBQVksRUFDWixLQUFLLENBQ04sQ0FBQztRQUNGLE9BQU8sNEJBQTRCLFlBQVksRUFBRSxDQUFDO0lBQ3BELENBQUM7QUFDSCxDQUFDO0FBU0QsTUFBTSxDQUFDLEtBQUssVUFBVSxVQUFVLENBQUMsTUFBd0I7SUFDdkQsSUFBSSxDQUFDO1FBQ0gsTUFBTSxLQUFLLEdBQVEsRUFBRSxDQUFDO1FBQ3RCLElBQUksTUFBTSxDQUFDLE9BQU8sRUFBRSxDQUFDO1lBQ25CLEtBQUssQ0FBQyxJQUFJLEdBQUcsTUFBTSxDQUFDLE9BQU8sQ0FBQztRQUM5QixDQUFDO1FBQ0QsSUFBSSxNQUFNLENBQUMsTUFBTSxFQUFFLENBQUM7WUFDbEIsS0FBSyxDQUFDLGFBQWEsQ0FBQyxHQUFHLE1BQU0sQ0FBQyxNQUFNLENBQUM7UUFDdkMsQ0FBQztRQUNELElBQUksTUFBTSxDQUFDLGtCQUFrQixFQUFFLENBQUM7WUFDOUIsS0FBSyxDQUFDLHlCQUF5QixDQUFDLEdBQUcsTUFBTSxDQUFDLGtCQUFrQixDQUFDO1FBQy9ELENBQUM7UUFFRCxJQUFJLE1BQU0sQ0FBQyxJQUFJLENBQUMsS0FBSyxDQUFDLENBQUMsTUFBTSxLQUFLLENBQUMsSUFBSSxDQUFDLE1BQU0sQ0FBQyxLQUFLLEVBQUUsQ0FBQztZQUNyRCxPQUFPLDhGQUE4RixDQUFDO1FBQ3hHLENBQUM7UUFFRCxNQUFNLFVBQVUsR0FBRyxNQUFNLE1BQU0sQ0FBQyxNQUFNLENBQUMsS0FBSyxDQUFDLENBQUM7UUFFOUMsSUFBSSxVQUFVLEdBQUcsQ0FBQyxFQUFFLENBQUM7WUFDbkIsT0FBTywwQkFBMEIsVUFBVSw2QkFBNkIsQ0FBQztRQUMzRSxDQUFDO2FBQU0sQ0FBQztZQUNOLE9BQU8saURBQWlELENBQUM7UUFDM0QsQ0FBQztJQUNILENBQUM7SUFBQyxPQUFPLEtBQUssRUFBRSxDQUFDO1FBQ2YsTUFBTSxZQUFZLEdBQUcsS0FBSyxZQUFZLEtBQUssQ0FBQyxDQUFDLENBQUMsS0FBSyxDQUFDLE9BQU8sQ0FBQyxDQUFDLENBQUMsTUFBTSxDQUFDLEtBQUssQ0FBQyxDQUFDO1FBQzVFLE9BQU8sQ0FBQyxLQUFLLENBQUMsMkJBQTJCLEVBQUUsWUFBWSxFQUFFLEtBQUssQ0FBQyxDQUFDO1FBQ2hFLE9BQU8sNkJBQTZCLFlBQVksRUFBRSxDQUFDO0lBQ3JELENBQUM7QUFDSCxDQUFDO0FBZ0JELE9BQU8sRUFBRSxtQkFBbUIsRUFBRSxNQUFNLHdCQUF3QixDQUFDO0FBRzdELE9BQU8sRUFBRSxrQkFBa0IsRUFBRSxNQUFNLGtCQUFrQixDQUFDO0FBQ3RELE9BQU8sRUFBRSxrQkFBa0IsRUFBRSxtQkFBbUIsRUFBRSxNQUFNLG9CQUFvQixDQUFDO0FBRTdFLEtBQUssVUFBVSxtQkFBbUIsQ0FBQyxNQUFjO0lBQy9DLE9BQU8sQ0FBQyxHQUFHLENBQUMsc0RBQXNELE1BQU0sRUFBRSxDQUFDLENBQUM7SUFDNUUsSUFBSSxDQUFDLGtCQUFrQixJQUFJLENBQUMsbUJBQW1CLEVBQUUsQ0FBQztRQUNoRCxPQUFPLENBQUMsS0FBSyxDQUFDLHNEQUFzRCxDQUFDLENBQUM7UUFDdEUsT0FBTyxFQUFFLENBQUM7SUFDWixDQUFDO0lBRUQsTUFBTSxLQUFLLEdBQUc7Ozs7Ozs7O0tBUVgsQ0FBQztJQUNKLE1BQU0sU0FBUyxHQUFHLEVBQUUsTUFBTSxFQUFFLENBQUM7SUFDN0IsTUFBTSxhQUFhLEdBQUcsd0JBQXdCLENBQUM7SUFFL0MsSUFBSSxDQUFDO1FBQ0gsTUFBTSxRQUFRLEdBQUcsTUFBTSxtQkFBbUIsQ0FNdkMsS0FBSyxFQUFFLFNBQVMsRUFBRSxhQUFhLEVBQUUsTUFBTSxDQUFDLENBQUM7UUFFNUMsSUFBSSxRQUFRLElBQUksUUFBUSxDQUFDLHFCQUFxQixFQUFFLENBQUM7WUFDL0MsT0FBTyxRQUFRLENBQUMscUJBQXFCLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxFQUFFLEVBQUUsQ0FBQyxDQUFDO2dCQUNuRCxTQUFTLEVBQUUsSUFBSSxDQUFDLFdBQVcsQ0FBQyxXQUFXLEVBQStCO2dCQUN0RSxTQUFTLEVBQUUsSUFBSSxDQUFDLFVBQVU7Z0JBQzFCLE9BQU8sRUFBRSxJQUFJLENBQUMsUUFBUTthQUN2QixDQUFDLENBQUMsQ0FBQztRQUNOLENBQUM7UUFDRCxPQUFPLEVBQUUsQ0FBQztJQUNaLENBQUM7SUFBQyxPQUFPLEtBQVUsRUFBRSxDQUFDO1FBQ3BCLE9BQU8sQ0FBQyxLQUFLLENBQ1gsNERBQTRELE1BQU0sR0FBRyxFQUNyRSxLQUFLLENBQ04sQ0FBQztRQUNGLE9BQU8sRUFBRSxDQUFDO0lBQ1osQ0FBQztBQUNILENBQUM7QUFFRCxNQUFNLENBQUMsS0FBSyxVQUFVLG9CQUFvQixDQUN4QyxPQUFpQixFQUNqQixXQUFtQixFQUNuQixTQUFpQjtJQUVqQixPQUFPLENBQUMsR0FBRyxDQUNULHNEQUFzRCxPQUFPLENBQUMsSUFBSSxDQUFDLElBQUksQ0FBQyxtQkFBbUIsV0FBVyxPQUFPLFNBQVMsRUFBRSxDQUN6SCxDQUFDO0lBQ0YsTUFBTSxvQkFBb0IsR0FBdUIsRUFBRSxDQUFDO0lBQ3BELE1BQU0sTUFBTSxHQUFpQixFQUFFLENBQUM7SUFFaEMsS0FBSyxNQUFNLE1BQU0sSUFBSSxPQUFPLEVBQUUsQ0FBQztRQUM3QixJQUFJLENBQUM7WUFDSCxNQUFNLFNBQVMsR0FBRyxNQUFNLG1CQUFtQixDQUFDLE1BQU0sQ0FBQyxDQUFDO1lBQ3BELE1BQU0sY0FBYyxHQUFHLE1BQU0sa0JBQWtCLENBQUMsTUFBTSxFQUFFLEdBQUcsQ0FBQyxDQUFDO1lBQzdELElBQUksY0FBYyxHQUFvQixFQUFFLENBQUM7WUFFekMsSUFBSSxjQUFjLENBQUMsRUFBRSxJQUFJLGNBQWMsQ0FBQyxJQUFJLEVBQUUsQ0FBQztnQkFDN0MsTUFBTSxlQUFlLEdBQUcsSUFBSSxJQUFJLENBQUMsV0FBVyxDQUFDLENBQUMsT0FBTyxFQUFFLENBQUM7Z0JBQ3hELE1BQU0sYUFBYSxHQUFHLElBQUksSUFBSSxDQUFDLFNBQVMsQ0FBQyxDQUFDLE9BQU8sRUFBRSxDQUFDO2dCQUNwRCxjQUFjLEdBQUcsY0FBYyxDQUFDLElBQUksQ0FBQyxNQUFNLENBQUMsQ0FBQyxLQUFLLEVBQUUsRUFBRTtvQkFDcEQsSUFBSSxDQUFDO3dCQUNILE1BQU0sVUFBVSxHQUFHLElBQUksSUFBSSxDQUFDLEtBQUssQ0FBQyxTQUFTLENBQUMsQ0FBQyxPQUFPLEVBQUUsQ0FBQzt3QkFDdkQsTUFBTSxRQUFRLEdBQUcsSUFBSSxJQUFJLENBQUMsS0FBSyxDQUFDLE9BQU8sQ0FBQyxDQUFDLE9BQU8sRUFBRSxDQUFDO3dCQUNuRCxPQUFPLFVBQVUsR0FBRyxhQUFhLElBQUksUUFBUSxHQUFHLGVBQWUsQ0FBQztvQkFDbEUsQ0FBQztvQkFBQyxPQUFPLGNBQWMsRUFBRSxDQUFDO3dCQUN4QixPQUFPLENBQUMsSUFBSSxDQUNWLG1FQUFtRSxLQUFLLENBQUMsRUFBRSxVQUFVLE1BQU0sR0FBRyxFQUM5RixjQUFjLENBQ2YsQ0FBQzt3QkFDRixPQUFPLEtBQUssQ0FBQztvQkFDZixDQUFDO2dCQUNILENBQUMsQ0FBQyxDQUFDO1lBQ0wsQ0FBQztpQkFBTSxDQUFDO2dCQUNOLE9BQU8sQ0FBQyxJQUFJLENBQ1YsbUVBQW1FLE1BQU0sS0FBSyxjQUFjLENBQUMsS0FBSyxFQUFFLE9BQU8sRUFBRSxDQUM5RyxDQUFDO2dCQUNGLE1BQU0sQ0FBQyxJQUFJLENBQUM7b0JBQ1YsSUFBSSxFQUFFLHVCQUF1QjtvQkFDN0IsT0FBTyxFQUFFLDRDQUE0QyxNQUFNLEdBQUc7b0JBQzlELE9BQU8sRUFBRSxjQUFjLENBQUMsS0FBSztpQkFDOUIsQ0FBQyxDQUFDO1lBQ0wsQ0FBQztZQUVELG9CQUFvQixDQUFDLElBQUksQ0FBQztnQkFDeEIsTUFBTTtnQkFDTixTQUFTO2dCQUNULGNBQWMsRUFBRSxjQUFjO2FBQy9CLENBQUMsQ0FBQztRQUNMLENBQUM7UUFBQyxPQUFPLEtBQVUsRUFBRSxDQUFDO1lBQ3BCLE9BQU8sQ0FBQyxLQUFLLENBQ1gsdUVBQXVFLE1BQU0sS0FBSyxLQUFLLENBQUMsT0FBTyxFQUFFLENBQ2xHLENBQUM7WUFDRixNQUFNLENBQUMsSUFBSSxDQUFDO2dCQUNWLElBQUksRUFBRSwwQkFBMEI7Z0JBQ2hDLE9BQU8sRUFBRSx1Q0FBdUMsTUFBTSxHQUFHO2dCQUN6RCxPQUFPLEVBQUUsS0FBSyxDQUFDLE9BQU87YUFDdkIsQ0FBQyxDQUFDO1FBQ0wsQ0FBQztJQUNILENBQUM7SUFFRCxJQUFJLE1BQU0sQ0FBQyxNQUFNLEdBQUcsQ0FBQyxJQUFJLG9CQUFvQixDQUFDLE1BQU0sS0FBSyxDQUFDLEVBQUUsQ0FBQztRQUMzRCxPQUFPLEVBQUUsRUFBRSxFQUFFLEtBQUssRUFBRSxLQUFLLEVBQUUsTUFBTSxDQUFDLENBQUMsQ0FBQyxFQUFFLENBQUM7SUFDekMsQ0FBQztJQUVELE9BQU8sRUFBRSxFQUFFLEVBQUUsSUFBSSxFQUFFLElBQUksRUFBRSxvQkFBb0IsRUFBRSxDQUFDO0FBQ2xELENBQUM7QUFFRCxnRkFBZ0Y7QUFDaEYsMkZBQTJGO0FBQzNGLE1BQU0sQ0FBQyxLQUFLLFVBQVUsNkJBQTZCLENBQ2pELE1BQWMsRUFDZCxRQUFhO0lBRWIsTUFBTSxFQUFFLGlCQUFpQixFQUFFLGVBQWUsRUFBRSxjQUFjLEVBQUUsR0FBRyxRQUFRLENBQUM7SUFFeEUsSUFBSSxDQUFDLGlCQUFpQixJQUFJLENBQUMsZUFBZSxFQUFFLENBQUM7UUFDM0MsT0FBTyxpRUFBaUUsQ0FBQztJQUMzRSxDQUFDO0lBRUQsTUFBTSxNQUFNLEdBQXVCO1FBQ2pDLElBQUksRUFBRSxlQUFlO1FBQ3JCLGtCQUFrQixFQUFFLGlCQUFpQjtRQUNyQyxRQUFRLEVBQUUsY0FBYztRQUN4QixNQUFNLEVBQUUsTUFBTTtLQUNmLENBQUM7SUFFRixPQUFPLFlBQVksQ0FBQyxNQUFNLENBQUMsQ0FBQztBQUM5QixDQUFDO0FBRUQsTUFBTSxDQUFDLEtBQUssVUFBVSxvQkFBb0IsQ0FDeEMsTUFBYyxFQUNkLFdBQWdEO0lBRWhELE9BQU8sQ0FBQyxHQUFHLENBQUMsbUNBQW1DLEVBQUUsTUFBTSxFQUFFLFdBQVcsQ0FBQyxDQUFDO0lBQ3RFLGNBQWM7SUFDZCxPQUFPLEVBQUUsT0FBTyxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsdUNBQXVDLEVBQUUsQ0FBQztBQUM5RSxDQUFDO0FBRUQsTUFBTSxDQUFDLEtBQUssVUFBVSxpQkFBaUIsQ0FDckMsTUFBYyxFQUNkLFlBQXNDO0lBRXRDLE9BQU8sQ0FBQyxHQUFHLENBQUMsZ0NBQWdDLEVBQUUsTUFBTSxFQUFFLFlBQVksQ0FBQyxDQUFDO0lBQ3BFLGNBQWM7SUFDZCxPQUFPLEVBQUUsT0FBTyxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsb0NBQW9DLEVBQUUsQ0FBQztBQUMzRSxDQUFDO0FBRUQsTUFBTSxDQUFDLEtBQUssVUFBVSw2QkFBNkIsQ0FDakQsTUFBYyxFQUNkLGNBQThDO0lBRTlDLE9BQU8sQ0FBQyxHQUFHLENBQ1QsNENBQTRDLEVBQzVDLE1BQU0sRUFDTixjQUFjLENBQ2YsQ0FBQztJQUNGLGdGQUFnRjtJQUNoRixjQUFjO0lBQ2QsT0FBTztRQUNMLE9BQU8sRUFBRSxLQUFLO1FBQ2QsT0FBTyxFQUNMLGlGQUFpRjtLQUNwRixDQUFDO0FBQ0osQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGFnZW5kYSwgU2NoZWR1bGVkQWdlbnRUYXNrRGF0YSB9IGZyb20gJ0AvYWdlbmRhU2VydmljZSc7IC8vIEFkanVzdGVkIHBhdGhcblxuLy8gTmV3IFNjaGVkdWxlVGFza1BhcmFtcyBpbnRlcmZhY2UgZm9yIEFnZW5kYS1iYXNlZCBzY2hlZHVsaW5nXG5leHBvcnQgaW50ZXJmYWNlIFNjaGVkdWxlVGFza1BhcmFtcyB7XG4gIHRhc2tEZXNjcmlwdGlvbj86IHN0cmluZzsgLy8gRGVzY3JpcHRpb24gb2YgdGhlIHRhc2sgZm9yIGxvZ2dpbmcvY29uZmlybWF0aW9uXG4gIHdoZW46IHN0cmluZyB8IERhdGU7IC8vIERhdGUgc3RyaW5nIChJU08pLCBodW1hbi1yZWFkYWJsZSAoXCJ0b21vcnJvdyBhdCAxMGFtXCIpLCBEYXRlIG9iamVjdCwgb3IgY3JvbiBzdHJpbmcgZm9yIHJlY3VycmluZ1xuICBvcmlnaW5hbFVzZXJJbnRlbnQ6IHN0cmluZzsgLy8gVGhlIGFjdHVhbCBhZ2VudCBpbnRlbnQgdG8gYmUgZXhlY3V0ZWQgKGUuZy4sIFwiU0VORF9FTUFJTFwiLCBcIkNSRUFURV9DQUxFTkRBUl9FVkVOVFwiKVxuICBlbnRpdGllczogUmVjb3JkPHN0cmluZywgYW55PjsgLy8gRW50aXRpZXMgcmVxdWlyZWQgZm9yIHRoZSBvcmlnaW5hbFVzZXJJbnRlbnRcbiAgdXNlcklkOiBzdHJpbmc7XG4gIGNvbnZlcnNhdGlvbklkPzogc3RyaW5nOyAvLyBPcHRpb25hbDogZm9yIGNvbnRleHRcbiAgLy8gRm9yIHJlY3VycmluZyB0YXNrcyAodXNpbmcgYWdlbmRhLmV2ZXJ5KVxuICBpc1JlY3VycmluZz86IGJvb2xlYW47IC8vIEZsYWcgdG8gaW5kaWNhdGUgaWYgdGhlIHRhc2sgaXMgcmVjdXJyaW5nXG4gIHJlcGVhdEludGVydmFsPzogc3RyaW5nOyAvLyBlLmcuLCBcIjEgZGF5XCIsIFwiMiBob3Vyc1wiLCBjcm9uIHN0cmluZy4gVXNlZCBpZiBpc1JlY3VycmluZyBpcyB0cnVlLlxuICByZXBlYXRUaW1lem9uZT86IHN0cmluZzsgLy8gT3B0aW9uYWw6IFRpbWV6b25lIGZvciByZWN1cnJpbmcgdGFza3MsIGUuZy4sIFwiQW1lcmljYS9OZXdfWW9ya1wiXG59XG5cbi8qKlxuICogU2NoZWR1bGVzIGEgdGFzayAoYWdlbnQgYWN0aW9uKSB0byBiZSBleGVjdXRlZCBhdCBhIHNwZWNpZmllZCB0aW1lIG9yIGludGVydmFsIHVzaW5nIEFnZW5kYS5cbiAqXG4gKiBAcGFyYW0gcGFyYW1zIC0gVGhlIHBhcmFtZXRlcnMgZm9yIHNjaGVkdWxpbmcgdGhlIHRhc2suXG4gKiBAcmV0dXJucyBBIHByb21pc2UgdGhhdCByZXNvbHZlcyB0byBhIHN0cmluZyBtZXNzYWdlIGluZGljYXRpbmcgc3VjY2VzcyBvciBmYWlsdXJlLlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gc2NoZWR1bGVUYXNrKFxuICBwYXJhbXM6IFNjaGVkdWxlVGFza1BhcmFtc1xuKTogUHJvbWlzZTxzdHJpbmc+IHtcbiAgY29uc3Qge1xuICAgIHdoZW4sXG4gICAgb3JpZ2luYWxVc2VySW50ZW50LFxuICAgIGVudGl0aWVzLFxuICAgIHVzZXJJZCxcbiAgICBjb252ZXJzYXRpb25JZCxcbiAgICB0YXNrRGVzY3JpcHRpb24sIC8vIFVzZWQgZm9yIGNvbmZpcm1hdGlvbiBtZXNzYWdlc1xuICAgIGlzUmVjdXJyaW5nLFxuICAgIHJlcGVhdEludGVydmFsLFxuICAgIHJlcGVhdFRpbWV6b25lLFxuICB9ID0gcGFyYW1zO1xuXG4gIC8vIFZhbGlkYXRlIGVzc2VudGlhbCBwYXJhbWV0ZXJzIGZvciBzY2hlZHVsaW5nXG4gIGlmICghd2hlbikge1xuICAgIHJldHVybiBcIlNjaGVkdWxpbmcgdGltZSAoJ3doZW4nKSBtdXN0IGJlIHByb3ZpZGVkLlwiO1xuICB9XG4gIGlmICghb3JpZ2luYWxVc2VySW50ZW50KSB7XG4gICAgcmV0dXJuICdUaGUgb3JpZ2luYWwgdXNlciBpbnRlbnQgdG8gYmUgc2NoZWR1bGVkIG11c3QgYmUgcHJvdmlkZWQuJztcbiAgfVxuICBpZiAoIXVzZXJJZCkge1xuICAgIHJldHVybiAnVXNlciBJRCBtdXN0IGJlIHByb3ZpZGVkIGZvciBzY2hlZHVsaW5nLic7XG4gIH1cblxuICBjb25zdCBqb2JEYXRhOiBTY2hlZHVsZWRBZ2VudFRhc2tEYXRhID0ge1xuICAgIG9yaWdpbmFsVXNlckludGVudCxcbiAgICBlbnRpdGllczogZW50aXRpZXMgfHwge30sIC8vIEVuc3VyZSBlbnRpdGllcyBpcyBhdCBsZWFzdCBhbiBlbXB0eSBvYmplY3RcbiAgICB1c2VySWQsXG4gICAgY29udmVyc2F0aW9uSWQsXG4gIH07XG5cbiAgdHJ5IHtcbiAgICBsZXQgam9iRGV0YWlsc01lc3NhZ2U6IHN0cmluZztcblxuICAgIGlmIChpc1JlY3VycmluZyAmJiByZXBlYXRJbnRlcnZhbCkge1xuICAgICAgY29uc3Qgb3B0aW9uczogeyB0aW1lem9uZT86IHN0cmluZzsgc3RhcnREYXRlPzogRGF0ZSB9ID0ge307XG4gICAgICBpZiAocmVwZWF0VGltZXpvbmUpIHtcbiAgICAgICAgb3B0aW9ucy50aW1lem9uZSA9IHJlcGVhdFRpbWV6b25lO1xuICAgICAgfVxuICAgICAgaWYgKFxuICAgICAgICB3aGVuIGluc3RhbmNlb2YgRGF0ZSB8fFxuICAgICAgICAodHlwZW9mIHdoZW4gPT09ICdzdHJpbmcnICYmXG4gICAgICAgICAgIXdoZW4uaW5jbHVkZXMoJyonKSAmJlxuICAgICAgICAgICF3aGVuLnRvTG93ZXJDYXNlKCkuc3RhcnRzV2l0aCgnZXZlcnknKSlcbiAgICAgICkge1xuICAgICAgfVxuXG4gICAgICBhd2FpdCBhZ2VuZGEuZXZlcnkoXG4gICAgICAgIHJlcGVhdEludGVydmFsLFxuICAgICAgICAnRVhFQ1VURV9BR0VOVF9BQ1RJT04nLFxuICAgICAgICBqb2JEYXRhLFxuICAgICAgICBvcHRpb25zXG4gICAgICApO1xuICAgICAgam9iRGV0YWlsc01lc3NhZ2UgPSBgUmVjdXJyaW5nIHRhc2sgXCIke3Rhc2tEZXNjcmlwdGlvbiB8fCBvcmlnaW5hbFVzZXJJbnRlbnR9XCIgc2NoZWR1bGVkIHRvIHJ1biBiYXNlZCBvbiBpbnRlcnZhbDogJHtyZXBlYXRJbnRlcnZhbH0uYDtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBgUmVjdXJyaW5nIHRhc2sgZm9yIGludGVudCAnJHtvcmlnaW5hbFVzZXJJbnRlbnR9JyBmb3IgdXNlciAnJHt1c2VySWR9JyBzY2hlZHVsZWQuIEludGVydmFsOiAke3JlcGVhdEludGVydmFsfS4gRGF0YTpgLFxuICAgICAgICBKU09OLnN0cmluZ2lmeShqb2JEYXRhKVxuICAgICAgKTtcbiAgICB9IGVsc2Uge1xuICAgICAgaWYgKHR5cGVvZiB3aGVuICE9PSAnc3RyaW5nJyAmJiAhKHdoZW4gaW5zdGFuY2VvZiBEYXRlKSkge1xuICAgICAgICByZXR1cm4gXCJJbnZhbGlkICd3aGVuJyBwYXJhbWV0ZXIgZm9yIGEgb25lLXRpbWUgdGFzay4gTXVzdCBiZSBhIGRhdGUgc3RyaW5nIG9yIERhdGUgb2JqZWN0LlwiO1xuICAgICAgfVxuICAgICAgYXdhaXQgYWdlbmRhLnNjaGVkdWxlKHdoZW4sICdFWEVDVVRFX0FHRU5UX0FDVElPTicsIGpvYkRhdGEpO1xuICAgICAgam9iRGV0YWlsc01lc3NhZ2UgPSBgVGFzayBcIiR7dGFza0Rlc2NyaXB0aW9uIHx8IG9yaWdpbmFsVXNlckludGVudH1cIiBoYXMgYmVlbiBzY2hlZHVsZWQgZm9yICR7dHlwZW9mIHdoZW4gPT09ICdzdHJpbmcnID8gd2hlbiA6IHdoZW4udG9JU09TdHJpbmcoKX0uYDtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBgT25lLXRpbWUgdGFzayBmb3IgaW50ZW50ICcke29yaWdpbmFsVXNlckludGVudH0nIGZvciB1c2VyICcke3VzZXJJZH0nIHNjaGVkdWxlZCBmb3IgJyR7d2hlbn0nLiBEYXRhOmAsXG4gICAgICAgIEpTT04uc3RyaW5naWZ5KGpvYkRhdGEpXG4gICAgICApO1xuICAgIH1cblxuICAgIHJldHVybiBqb2JEZXRhaWxzTWVzc2FnZTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICBjb25zdCBlcnJvck1lc3NhZ2UgPSBlcnJvciBpbnN0YW5jZW9mIEVycm9yID8gZXJyb3IubWVzc2FnZSA6IFN0cmluZyhlcnJvcik7XG4gICAgY29uc29sZS5lcnJvcihcbiAgICAgIGBFcnJvciBzY2hlZHVsaW5nIHRhc2sgZm9yIGludGVudCAnJHtvcmlnaW5hbFVzZXJJbnRlbnR9JyBmb3IgdXNlciAnJHt1c2VySWR9JzpgLFxuICAgICAgZXJyb3JNZXNzYWdlLFxuICAgICAgZXJyb3JcbiAgICApO1xuICAgIHJldHVybiBgRmFpbGVkIHRvIHNjaGVkdWxlIHRhc2s6ICR7ZXJyb3JNZXNzYWdlfWA7XG4gIH1cbn1cblxuZXhwb3J0IGludGVyZmFjZSBDYW5jZWxUYXNrUGFyYW1zIHtcbiAgam9iSWQ/OiBzdHJpbmc7XG4gIGpvYk5hbWU/OiBzdHJpbmc7XG4gIHVzZXJJZD86IHN0cmluZztcbiAgb3JpZ2luYWxVc2VySW50ZW50Pzogc3RyaW5nO1xufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gY2FuY2VsVGFzayhwYXJhbXM6IENhbmNlbFRhc2tQYXJhbXMpOiBQcm9taXNlPHN0cmluZz4ge1xuICB0cnkge1xuICAgIGNvbnN0IHF1ZXJ5OiBhbnkgPSB7fTtcbiAgICBpZiAocGFyYW1zLmpvYk5hbWUpIHtcbiAgICAgIHF1ZXJ5Lm5hbWUgPSBwYXJhbXMuam9iTmFtZTtcbiAgICB9XG4gICAgaWYgKHBhcmFtcy51c2VySWQpIHtcbiAgICAgIHF1ZXJ5WydkYXRhLnVzZXJJZCddID0gcGFyYW1zLnVzZXJJZDtcbiAgICB9XG4gICAgaWYgKHBhcmFtcy5vcmlnaW5hbFVzZXJJbnRlbnQpIHtcbiAgICAgIHF1ZXJ5WydkYXRhLm9yaWdpbmFsVXNlckludGVudCddID0gcGFyYW1zLm9yaWdpbmFsVXNlckludGVudDtcbiAgICB9XG5cbiAgICBpZiAoT2JqZWN0LmtleXMocXVlcnkpLmxlbmd0aCA9PT0gMCAmJiAhcGFyYW1zLmpvYklkKSB7XG4gICAgICByZXR1cm4gJ05vIGNyaXRlcmlhIHByb3ZpZGVkIHRvIGNhbmNlbCB0YXNrcy4gUGxlYXNlIHNwZWNpZnkgam9iTmFtZSwgdXNlcklkLCBvciBvcmlnaW5hbFVzZXJJbnRlbnQuJztcbiAgICB9XG5cbiAgICBjb25zdCBudW1SZW1vdmVkID0gYXdhaXQgYWdlbmRhLmNhbmNlbChxdWVyeSk7XG5cbiAgICBpZiAobnVtUmVtb3ZlZCA+IDApIHtcbiAgICAgIHJldHVybiBgU3VjY2Vzc2Z1bGx5IGNhbmNlbGxlZCAke251bVJlbW92ZWR9IHRhc2socykgbWF0Y2hpbmcgY3JpdGVyaWEuYDtcbiAgICB9IGVsc2Uge1xuICAgICAgcmV0dXJuICdObyB0YXNrcyBmb3VuZCBtYXRjaGluZyB0aGUgY3JpdGVyaWEgdG8gY2FuY2VsLic7XG4gICAgfVxuICB9IGNhdGNoIChlcnJvcikge1xuICAgIGNvbnN0IGVycm9yTWVzc2FnZSA9IGVycm9yIGluc3RhbmNlb2YgRXJyb3IgPyBlcnJvci5tZXNzYWdlIDogU3RyaW5nKGVycm9yKTtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBjYW5jZWxsaW5nIHRhc2socyk6JywgZXJyb3JNZXNzYWdlLCBlcnJvcik7XG4gICAgcmV0dXJuIGBGYWlsZWQgdG8gY2FuY2VsIHRhc2socyk6ICR7ZXJyb3JNZXNzYWdlfWA7XG4gIH1cbn1cblxuLy8gLS0tIFVzZXIgQXZhaWxhYmlsaXR5IEZ1bmN0aW9ucyAtLS1cbmltcG9ydCB7XG4gIFVzZXJBdmFpbGFiaWxpdHksXG4gIFVzZXJXb3JrVGltZSxcbiAgQ2FsZW5kYXJFdmVudCxcbiAgU2tpbGxSZXNwb25zZSxcbiAgU2tpbGxFcnJvcixcbiAgLy8gVHlwZXMgZm9yIE5MVSBlbnRpdGllcyBpZiBuZWVkZWQgZm9yIHNjaGVkdWxpbmcgZnVuY3Rpb25zXG4gIE5MVUNyZWF0ZVRpbWVQcmVmZXJlbmNlUnVsZUVudGl0aWVzLFxuICBOTFVCbG9ja1RpbWVTbG90RW50aXRpZXMsXG4gIE5MVVNjaGVkdWxlVGVhbU1lZXRpbmdFbnRpdGllcyxcbiAgU2NoZWR1bGluZ1Jlc3BvbnNlLFxuICBTa2lsbFJlc3BvbnNlLCAvLyBBZGRlZCBmb3IgaW52b2tlT3B0YVBsYW5uZXJTY2hlZHVsaW5nXG59IGZyb20gJy4uL3R5cGVzJztcbmltcG9ydCB7IGV4ZWN1dGVHcmFwaFFMUXVlcnkgfSBmcm9tICcuLi9fbGlicy9ncmFwaHFsQ2xpZW50JztcbmltcG9ydCB7IEFUT01fT1BUQVBMQU5ORVJfQVBJX0JBU0VfVVJMIH0gZnJvbSAnLi4vX2xpYnMvY29uc3RhbnRzJzsgLy8gRm9yIE9wdGFQbGFubmVyIFVSTFxuaW1wb3J0IGF4aW9zIGZyb20gJ2F4aW9zJzsgLy8gRm9yIG1ha2luZyBIVFRQIHJlcXVlc3RzIHRvIE9wdGFQbGFubmVyXG5pbXBvcnQgeyBsaXN0VXBjb21pbmdFdmVudHMgfSBmcm9tICcuL2NhbGVuZGFyU2tpbGxzJztcbmltcG9ydCB7IEhBU1VSQV9HUkFQSFFMX1VSTCwgSEFTVVJBX0FETUlOX1NFQ1JFVCB9IGZyb20gJy4uL19saWJzL2NvbnN0YW50cyc7XG5cbmFzeW5jIGZ1bmN0aW9uIF9mZXRjaFVzZXJXb3JrVGltZXModXNlcklkOiBzdHJpbmcpOiBQcm9taXNlPFVzZXJXb3JrVGltZVtdPiB7XG4gIGNvbnNvbGUubG9nKGBbX2ZldGNoVXNlcldvcmtUaW1lc10gRmV0Y2hpbmcgd29yayB0aW1lcyBmb3IgdXNlciAke3VzZXJJZH1gKTtcbiAgaWYgKCFIQVNVUkFfR1JBUEhRTF9VUkwgfHwgIUhBU1VSQV9BRE1JTl9TRUNSRVQpIHtcbiAgICBjb25zb2xlLmVycm9yKCdbX2ZldGNoVXNlcldvcmtUaW1lc10gR3JhcGhRTCBjbGllbnQgbm90IGNvbmZpZ3VyZWQuJyk7XG4gICAgcmV0dXJuIFtdO1xuICB9XG5cbiAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgIHF1ZXJ5IEdldFVzZXJXb3JrUHJlZmVyZW5jZXMoJHVzZXJJZDogU3RyaW5nISkge1xuICAgICAgICAgICAgdXNlcl93b3JrX3ByZWZlcmVuY2VzKHdoZXJlOiB7dXNlcl9pZDoge19lcTogJHVzZXJJZH19KSB7XG4gICAgICAgICAgICAgICAgZGF5X29mX3dlZWtcbiAgICAgICAgICAgICAgICBzdGFydF90aW1lXG4gICAgICAgICAgICAgICAgZW5kX3RpbWVcbiAgICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgIGA7XG4gIGNvbnN0IHZhcmlhYmxlcyA9IHsgdXNlcklkIH07XG4gIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnR2V0VXNlcldvcmtQcmVmZXJlbmNlcyc7XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGV4ZWN1dGVHcmFwaFFMUXVlcnk8e1xuICAgICAgdXNlcl93b3JrX3ByZWZlcmVuY2VzOiBBcnJheTx7XG4gICAgICAgIGRheV9vZl93ZWVrOiBzdHJpbmc7XG4gICAgICAgIHN0YXJ0X3RpbWU6IHN0cmluZztcbiAgICAgICAgZW5kX3RpbWU6IHN0cmluZztcbiAgICAgIH0+O1xuICAgIH0+KHF1ZXJ5LCB2YXJpYWJsZXMsIG9wZXJhdGlvbk5hbWUsIHVzZXJJZCk7XG5cbiAgICBpZiAocmVzcG9uc2UgJiYgcmVzcG9uc2UudXNlcl93b3JrX3ByZWZlcmVuY2VzKSB7XG4gICAgICByZXR1cm4gcmVzcG9uc2UudXNlcl93b3JrX3ByZWZlcmVuY2VzLm1hcCgocHJlZikgPT4gKHtcbiAgICAgICAgZGF5T2ZXZWVrOiBwcmVmLmRheV9vZl93ZWVrLnRvVXBwZXJDYXNlKCkgYXMgVXNlcldvcmtUaW1lWydkYXlPZldlZWsnXSxcbiAgICAgICAgc3RhcnRUaW1lOiBwcmVmLnN0YXJ0X3RpbWUsXG4gICAgICAgIGVuZFRpbWU6IHByZWYuZW5kX3RpbWUsXG4gICAgICB9KSk7XG4gICAgfVxuICAgIHJldHVybiBbXTtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICBgW19mZXRjaFVzZXJXb3JrVGltZXNdIEVycm9yIGZldGNoaW5nIHdvcmsgdGltZXMgZm9yIHVzZXIgJHt1c2VySWR9OmAsXG4gICAgICBlcnJvclxuICAgICk7XG4gICAgcmV0dXJuIFtdO1xuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRVc2Vyc0F2YWlsYWJpbGl0eShcbiAgdXNlcklkczogc3RyaW5nW10sXG4gIHdpbmRvd1N0YXJ0OiBzdHJpbmcsXG4gIHdpbmRvd0VuZDogc3RyaW5nXG4pOiBQcm9taXNlPFNraWxsUmVzcG9uc2U8VXNlckF2YWlsYWJpbGl0eVtdPj4ge1xuICBjb25zb2xlLmxvZyhcbiAgICBgW3NjaGVkdWxpbmdTa2lsbHNdIEdldHRpbmcgYXZhaWxhYmlsaXR5IGZvciB1c2VyczogJHt1c2VySWRzLmpvaW4oJywgJyl9IHdpdGhpbiB3aW5kb3c6ICR7d2luZG93U3RhcnR9IHRvICR7d2luZG93RW5kfWBcbiAgKTtcbiAgY29uc3QgYWxsVXNlcnNBdmFpbGFiaWxpdHk6IFVzZXJBdmFpbGFiaWxpdHlbXSA9IFtdO1xuICBjb25zdCBlcnJvcnM6IFNraWxsRXJyb3JbXSA9IFtdO1xuXG4gIGZvciAoY29uc3QgdXNlcklkIG9mIHVzZXJJZHMpIHtcbiAgICB0cnkge1xuICAgICAgY29uc3Qgd29ya1RpbWVzID0gYXdhaXQgX2ZldGNoVXNlcldvcmtUaW1lcyh1c2VySWQpO1xuICAgICAgY29uc3QgZXZlbnRzUmVzcG9uc2UgPSBhd2FpdCBsaXN0VXBjb21pbmdFdmVudHModXNlcklkLCAyNTApO1xuICAgICAgbGV0IHJlbGV2YW50RXZlbnRzOiBDYWxlbmRhckV2ZW50W10gPSBbXTtcblxuICAgICAgaWYgKGV2ZW50c1Jlc3BvbnNlLm9rICYmIGV2ZW50c1Jlc3BvbnNlLmRhdGEpIHtcbiAgICAgICAgY29uc3Qgd2luZG93U3RhcnRUaW1lID0gbmV3IERhdGUod2luZG93U3RhcnQpLmdldFRpbWUoKTtcbiAgICAgICAgY29uc3Qgd2luZG93RW5kVGltZSA9IG5ldyBEYXRlKHdpbmRvd0VuZCkuZ2V0VGltZSgpO1xuICAgICAgICByZWxldmFudEV2ZW50cyA9IGV2ZW50c1Jlc3BvbnNlLmRhdGEuZmlsdGVyKChldmVudCkgPT4ge1xuICAgICAgICAgIHRyeSB7XG4gICAgICAgICAgICBjb25zdCBldmVudFN0YXJ0ID0gbmV3IERhdGUoZXZlbnQuc3RhcnRUaW1lKS5nZXRUaW1lKCk7XG4gICAgICAgICAgICBjb25zdCBldmVudEVuZCA9IG5ldyBEYXRlKGV2ZW50LmVuZFRpbWUpLmdldFRpbWUoKTtcbiAgICAgICAgICAgIHJldHVybiBldmVudFN0YXJ0IDwgd2luZG93RW5kVGltZSAmJiBldmVudEVuZCA+IHdpbmRvd1N0YXJ0VGltZTtcbiAgICAgICAgICB9IGNhdGNoIChkYXRlUGFyc2VFcnJvcikge1xuICAgICAgICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAgICAgICBgW2dldFVzZXJzQXZhaWxhYmlsaXR5XSBDb3VsZCBub3QgcGFyc2UgZXZlbnQgZGF0ZXMgZm9yIGV2ZW50IElEICR7ZXZlbnQuaWR9LCB1c2VyICR7dXNlcklkfTpgLFxuICAgICAgICAgICAgICBkYXRlUGFyc2VFcnJvclxuICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIHJldHVybiBmYWxzZTtcbiAgICAgICAgICB9XG4gICAgICAgIH0pO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAgIGBbZ2V0VXNlcnNBdmFpbGFiaWxpdHldIENvdWxkIG5vdCBmZXRjaCBjYWxlbmRhciBldmVudHMgZm9yIHVzZXIgJHt1c2VySWR9OiAke2V2ZW50c1Jlc3BvbnNlLmVycm9yPy5tZXNzYWdlfWBcbiAgICAgICAgKTtcbiAgICAgICAgZXJyb3JzLnB1c2goe1xuICAgICAgICAgIGNvZGU6ICdDQUxFTkRBUl9GRVRDSF9GQUlMRUQnLFxuICAgICAgICAgIG1lc3NhZ2U6IGBGYWlsZWQgdG8gZmV0Y2ggY2FsZW5kYXIgZXZlbnRzIGZvciB1c2VyICR7dXNlcklkfS5gLFxuICAgICAgICAgIGRldGFpbHM6IGV2ZW50c1Jlc3BvbnNlLmVycm9yLFxuICAgICAgICB9KTtcbiAgICAgIH1cblxuICAgICAgYWxsVXNlcnNBdmFpbGFiaWxpdHkucHVzaCh7XG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgd29ya1RpbWVzLFxuICAgICAgICBjYWxlbmRhckV2ZW50czogcmVsZXZhbnRFdmVudHMsXG4gICAgICB9KTtcbiAgICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICBgW2dldFVzZXJzQXZhaWxhYmlsaXR5XSBDcml0aWNhbCBlcnJvciBnZXR0aW5nIGF2YWlsYWJpbGl0eSBmb3IgdXNlciAke3VzZXJJZH06ICR7ZXJyb3IubWVzc2FnZX1gXG4gICAgICApO1xuICAgICAgZXJyb3JzLnB1c2goe1xuICAgICAgICBjb2RlOiAnQVZBSUxBQklMSVRZX0ZFVENIX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogYEZhaWxlZCB0byBnZXQgYXZhaWxhYmlsaXR5IGZvciB1c2VyICR7dXNlcklkfS5gLFxuICAgICAgICBkZXRhaWxzOiBlcnJvci5tZXNzYWdlLFxuICAgICAgfSk7XG4gICAgfVxuICB9XG5cbiAgaWYgKGVycm9ycy5sZW5ndGggPiAwICYmIGFsbFVzZXJzQXZhaWxhYmlsaXR5Lmxlbmd0aCA9PT0gMCkge1xuICAgIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IGVycm9yc1swXSB9O1xuICB9XG5cbiAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IGFsbFVzZXJzQXZhaWxhYmlsaXR5IH07XG59XG5cbi8vIFRPRE86IEltcGxlbWVudCB0aGVzZSBmdW5jdGlvbnMgYmFzZWQgb24gTkxVIGludGVudHMgaWYgdGhleSBhcmUgc3RpbGwgbmVlZGVkXG4vLyBGb3Igbm93LCB0aGV5IGFyZSBwbGFjZWhvbGRlcnMgYXMgdGhlIHByaW1hcnkgZm9jdXMgaXMgb24gdGhlIG5ldyBlbWFpbCBzY2hlZHVsaW5nIGZsb3cuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlU2NoZWR1bGVTa2lsbEFjdGl2YXRpb24oXG4gIHVzZXJJZDogc3RyaW5nLFxuICBlbnRpdGllczogYW55XG4pOiBQcm9taXNlPHN0cmluZz4ge1xuICBjb25zdCB7IHNraWxsX3RvX3NjaGVkdWxlLCBhY3RpdmF0aW9uX3RpbWUsIHNraWxsX2VudGl0aWVzIH0gPSBlbnRpdGllcztcblxuICBpZiAoIXNraWxsX3RvX3NjaGVkdWxlIHx8ICFhY3RpdmF0aW9uX3RpbWUpIHtcbiAgICByZXR1cm4gJ0kgbmVlZCB0byBrbm93IHdoaWNoIHNraWxsIHRvIHNjaGVkdWxlIGFuZCB3aGVuIHRvIHNjaGVkdWxlIGl0Lic7XG4gIH1cblxuICBjb25zdCBwYXJhbXM6IFNjaGVkdWxlVGFza1BhcmFtcyA9IHtcbiAgICB3aGVuOiBhY3RpdmF0aW9uX3RpbWUsXG4gICAgb3JpZ2luYWxVc2VySW50ZW50OiBza2lsbF90b19zY2hlZHVsZSxcbiAgICBlbnRpdGllczogc2tpbGxfZW50aXRpZXMsXG4gICAgdXNlcklkOiB1c2VySWQsXG4gIH07XG5cbiAgcmV0dXJuIHNjaGVkdWxlVGFzayhwYXJhbXMpO1xufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gY3JlYXRlU2NoZWR1bGluZ1J1bGUoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBydWxlRGV0YWlsczogTkxVQ3JlYXRlVGltZVByZWZlcmVuY2VSdWxlRW50aXRpZXNcbik6IFByb21pc2U8U2NoZWR1bGluZ1Jlc3BvbnNlPiB7XG4gIGNvbnNvbGUubG9nKCdjcmVhdGVTY2hlZHVsaW5nUnVsZSBjYWxsZWQgd2l0aDonLCB1c2VySWQsIHJ1bGVEZXRhaWxzKTtcbiAgLy8gUGxhY2Vob2xkZXJcbiAgcmV0dXJuIHsgc3VjY2VzczogZmFsc2UsIG1lc3NhZ2U6ICdjcmVhdGVTY2hlZHVsaW5nUnVsZSBub3QgaW1wbGVtZW50ZWQuJyB9O1xufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gYmxvY2tDYWxlbmRhclRpbWUoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBibG9ja0RldGFpbHM6IE5MVUJsb2NrVGltZVNsb3RFbnRpdGllc1xuKTogUHJvbWlzZTxTY2hlZHVsaW5nUmVzcG9uc2U+IHtcbiAgY29uc29sZS5sb2coJ2Jsb2NrQ2FsZW5kYXJUaW1lIGNhbGxlZCB3aXRoOicsIHVzZXJJZCwgYmxvY2tEZXRhaWxzKTtcbiAgLy8gUGxhY2Vob2xkZXJcbiAgcmV0dXJuIHsgc3VjY2VzczogZmFsc2UsIG1lc3NhZ2U6ICdibG9ja0NhbGVuZGFyVGltZSBub3QgaW1wbGVtZW50ZWQuJyB9O1xufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gaW5pdGlhdGVUZWFtTWVldGluZ1NjaGVkdWxpbmcoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBtZWV0aW5nRGV0YWlsczogTkxVU2NoZWR1bGVUZWFtTWVldGluZ0VudGl0aWVzXG4pOiBQcm9taXNlPFNjaGVkdWxpbmdSZXNwb25zZT4ge1xuICBjb25zb2xlLmxvZyhcbiAgICAnaW5pdGlhdGVUZWFtTWVldGluZ1NjaGVkdWxpbmcgY2FsbGVkIHdpdGg6JyxcbiAgICB1c2VySWQsXG4gICAgbWVldGluZ0RldGFpbHNcbiAgKTtcbiAgLy8gVGhpcyBpcyB3aGVyZSB0aGUgY2FsbCB0byBPcHRhUGxhbm5lciBvciBzaW1pbGFyIHNjaGVkdWxpbmcgQUkgd291bGQgYmUgbWFkZS5cbiAgLy8gUGxhY2Vob2xkZXJcbiAgcmV0dXJuIHtcbiAgICBzdWNjZXNzOiBmYWxzZSxcbiAgICBtZXNzYWdlOlxuICAgICAgJ2luaXRpYXRlVGVhbU1lZXRpbmdTY2hlZHVsaW5nIG5vdCBpbXBsZW1lbnRlZCB5ZXQuIFRoaXMgd291bGQgY2FsbCBPcHRhUGxhbm5lci4nLFxuICB9O1xufVxuIl19