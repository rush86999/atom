import {
  createDailyFeaturesApplyEventTrigger,
  upsertAutopilotOne,
  deleteScheduledEventForAutopilot,
  deleteAutopilotGivenId,
  listAutopilotsGivenUserId,
  getAutopilotGivenId,
} from '../../autopilot/_libs/api-helper';
import { AutopilotType, ScheduleAssistWithMeetingQueueBodyType, AutopilotApiResponse } from '../../autopilot/_libs/types';
import dayjs from 'dayjs';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';

dayjs.extend(timezone);
dayjs.extend(utc);

// Placeholder for a more sophisticated query parsing mechanism
interface AutopilotQuery {
  autopilotId?: string;
  eventId?: string;
  // Add other relevant fields from AutopilotType or ScheduleAssistWithMeetingQueueBodyType as needed
  scheduleAt?: string;
  timezone?: string;
  payload?: ScheduleAssistWithMeetingQueueBodyType;
}

// Helper to parse the query string (very basic for now)
function parseQuery(query: string): AutopilotQuery {
  try {
    // Assuming query is a JSON string for now for enable/disable specifics
    return JSON.parse(query);
  } catch (e) {
    // If not JSON, it might be a simple ID for get/delete, or just a descriptor
    console.warn(`Query string is not a valid JSON: ${query}. Treating as simple string or relying on defaults.`);
    // For getAutopilotStatus, query might be autopilotId. For disable, it might be eventId.
    // This simplistic parsing needs to be made robust.
    if (query.length > 0 && !query.includes("{")) { // Simple heuristic for ID-like string
        return { autopilotId: query, eventId: query }; // Assume it could be either
    }
    return {};
  }
}


export async function enableAutopilot(userId: string, query: string): Promise<AutopilotApiResponse<AutopilotType | null>> {
  console.log(`Attempting to enable Autopilot for user ${userId} with query: ${query}`);
  const parsedQuery = parseQuery(query);

  // For enabling, we need to construct AutopilotType and ScheduleAssistWithMeetingQueueBodyType
  // This is a simplified example. A real implementation would need more robust construction of these objects.
  // The `query` should ideally provide all necessary details for `autopilotData` and `bodyData`.

  const bodyData: ScheduleAssistWithMeetingQueueBodyType = parsedQuery.payload || {
    userId,
    windowStartDate: dayjs().add(1, 'day').toISOString(), // Example: schedule for tomorrow
    windowEndDate: dayjs().add(8, 'days').toISOString(),   // Example: 7-day window
    timezone: parsedQuery.timezone || dayjs.tz.guess(),
    // other necessary fields for ScheduleAssistWithMeetingQueueBodyType
  };

  const autopilotData: AutopilotType = {
    id: '', // This will be set by the event_id from createDailyFeaturesApplyEventTrigger
    userId,
    scheduleAt: parsedQuery.scheduleAt || dayjs(bodyData.windowStartDate).utc().format(),
    timezone: bodyData.timezone,
    payload: bodyData, // Embed the body data
    createdDate: dayjs().toISOString(),
    updatedAt: dayjs().toISOString(),
  };

  try {
    // 1. Create the scheduled event in Hasura
    const eventTriggerResponse = await createDailyFeaturesApplyEventTrigger(autopilotData, bodyData);
    if (!eventTriggerResponse.ok || !eventTriggerResponse.data) {
      console.error('Failed to create scheduled event trigger:', eventTriggerResponse.error);
      return { ok: false, error: eventTriggerResponse.error || { code: 'CREATE_EVENT_ERROR', message: 'Failed to create scheduled event.' } };
    }

    autopilotData.id = eventTriggerResponse.data; // The event_id becomes the autopilot record's ID

    // 2. Upsert the Autopilot record with the event_id as its ID
    const upsertResponse = await upsertAutopilotOne(autopilotData);
    if (!upsertResponse.ok) {
      console.error('Failed to upsert autopilot configuration:', upsertResponse.error);
      // Attempt to clean up the created scheduled event if upsert fails
      await deleteScheduledEventForAutopilot(autopilotData.id);
      console.warn(`Cleaned up scheduled event ${autopilotData.id} after failed upsert.`);
      return { ok: false, error: upsertResponse.error || { code: 'UPSERT_AUTOPILOT_ERROR', message: 'Failed to save autopilot configuration.'} };
    }

    console.log(`Autopilot enabled successfully for user ${userId}. Autopilot ID (Event ID): ${autopilotData.id}`);
    return { ok: true, data: upsertResponse.data };

  } catch (error: any) {
    console.error('Error enabling Autopilot:', error);
    return { ok: false, error: { code: 'ENABLE_AUTOPILOT_EXCEPTION', message: error.message || 'An unexpected error occurred.' } };
  }
}

export async function disableAutopilot(userId: string, query: string): Promise<AutopilotApiResponse<{ success: boolean }>> {
  console.log(`Attempting to disable Autopilot for user ${userId} with query: ${query}`);
  const parsedQuery = parseQuery(query);
  const eventId = parsedQuery.eventId || parsedQuery.autopilotId; // Query should provide the eventId (which is also the autopilotId)

  if (!eventId) {
    console.error('Error disabling Autopilot: eventId (autopilotId) not provided in query.');
    return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'eventId (autopilotId) is required in query to disable Autopilot.' } };
  }

  try {
    // 1. Delete the scheduled event from Hasura
    const deleteEventResponse = await deleteScheduledEventForAutopilot(eventId);
    if (!deleteEventResponse.ok) {
      console.warn(`Failed to delete scheduled event ${eventId}. It might have already been processed or deleted. Proceeding to delete DB record.`, deleteEventResponse.error);
      // Don't necessarily return an error here, as the main goal is to stop future autopilot actions.
      // The DB record deletion is also important.
    } else {
      console.log(`Successfully deleted scheduled event ${eventId}.`);
    }

    // 2. Delete the Autopilot record from the database
    // Assuming eventId is the same as autopilotId used in the database
    const deleteAutopilotRecordResponse = await deleteAutopilotGivenId(eventId);
    if (!deleteAutopilotRecordResponse.ok) {
      console.error(`Failed to delete Autopilot database record ${eventId}:`, deleteAutopilotRecordResponse.error);
      // This is a more significant issue if the event was deleted but the record persists.
      return { ok: false, error: deleteAutopilotRecordResponse.error || { code: 'DELETE_DB_RECORD_ERROR', message: `Failed to delete Autopilot record ${eventId}, but scheduled event might be deleted.` } };
    }

    console.log(`Autopilot (ID: ${eventId}) disabled successfully for user ${userId}.`);
    return { ok: true, data: { success: true } };

  } catch (error: any) {
    console.error(`Error disabling Autopilot (ID: ${eventId}):`, error);
    return { ok: false, error: { code: 'DISABLE_AUTOPILOT_EXCEPTION', message: error.message || 'An unexpected error occurred during disable.' } };
  }
}

export async function getAutopilotStatus(userId: string, query: string): Promise<AutopilotApiResponse<AutopilotType | AutopilotType[] | null>> {
  console.log(`Getting Autopilot status for user ${userId} with query: ${query}`);
  const parsedQuery = parseQuery(query);
  const autopilotId = parsedQuery.autopilotId; // Query might provide a specific autopilotId

  try {
    if (autopilotId) {
      // If a specific autopilotId is provided, fetch that one
      console.log(`Fetching status for specific Autopilot ID: ${autopilotId}`);
      const response = await getAutopilotGivenId(autopilotId);
      if (!response.ok) {
        console.error(`Error fetching status for Autopilot ID ${autopilotId}:`, response.error);
      }
      return response;
    } else {
      // Otherwise, list all autopilots for the user
      // Note: listAutopilotsGivenUserId currently returns AutopilotType | null (the first one)
      // If multiple are expected, api-helper.ts would need adjustment or we list all and return as array
      console.log(`Fetching all Autopilot statuses for user ID: ${userId}`);
      const response = await listAutopilotsGivenUserId(userId); // This gets one record
      // To list ALL, we would need a different helper or modify listAutopilotsGivenUserId
      // For now, sticking to the current helper's behavior.
      // If you need all, the helper `listAutopilotsGivenUserId` should be modified to return `AutopilotType[] | null`
      // and the GraphQL query inside it should not pick [0].
      if (!response.ok) {
        console.error(`Error fetching Autopilot statuses for user ${userId}:`, response.error);
      }
      return response;
    }
  } catch (error: any) {
    console.error('Error getting Autopilot status:', error);
    return { ok: false, error: { code: 'GET_AUTOPILOT_STATUS_EXCEPTION', message: error.message || 'An unexpected error occurred.' } };
  }
}
