import { createDailyFeaturesApplyEventTrigger, upsertAutopilotOne, deleteScheduledEventForAutopilot, deleteAutopilotGivenId, listAutopilotsGivenUserId, getAutopilotGivenId, } from '../../autopilot/_libs/api-helper';
import dayjs from 'dayjs';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
dayjs.extend(timezone);
dayjs.extend(utc);
// Helper to parse the query string (very basic for now)
function parseQuery(query) {
    try {
        // Assuming query is a JSON string for now for enable/disable specifics
        return JSON.parse(query);
    }
    catch (e) {
        // If not JSON, it might be a simple ID for get/delete, or just a descriptor
        console.warn(`Query string is not a valid JSON: ${query}. Treating as simple string or relying on defaults.`);
        // For getAutopilotStatus, query might be autopilotId. For disable, it might be eventId.
        // This simplistic parsing needs to be made robust.
        if (query.length > 0 && !query.includes('{')) {
            // Simple heuristic for ID-like string
            return { autopilotId: query, eventId: query }; // Assume it could be either
        }
        return {};
    }
}
export async function enableAutopilot(userId, query) {
    console.log(`Attempting to enable Autopilot for user ${userId} with query: ${query}`);
    const parsedQuery = parseQuery(query);
    // For enabling, we need to construct AutopilotType and ScheduleAssistWithMeetingQueueBodyType
    // This is a simplified example. A real implementation would need more robust construction of these objects.
    // The `query` should ideally provide all necessary details for `autopilotData` and `bodyData`.
    const bodyData = parsedQuery.payload || {
        userId,
        windowStartDate: dayjs().add(1, 'day').toISOString(), // Example: schedule for tomorrow
        windowEndDate: dayjs().add(8, 'days').toISOString(), // Example: 7-day window
        timezone: parsedQuery.timezone || dayjs.tz.guess(),
        // other necessary fields for ScheduleAssistWithMeetingQueueBodyType
    };
    const autopilotData = {
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
            return {
                ok: false,
                error: eventTriggerResponse.error || {
                    code: 'CREATE_EVENT_ERROR',
                    message: 'Failed to create scheduled event.',
                },
            };
        }
        autopilotData.id = eventTriggerResponse.data; // The event_id becomes the autopilot record's ID
        // 2. Upsert the Autopilot record with the event_id as its ID
        const upsertResponse = await upsertAutopilotOne(autopilotData);
        if (!upsertResponse.ok) {
            console.error('Failed to upsert autopilot configuration:', upsertResponse.error);
            // Attempt to clean up the created scheduled event if upsert fails
            await deleteScheduledEventForAutopilot(autopilotData.id);
            console.warn(`Cleaned up scheduled event ${autopilotData.id} after failed upsert.`);
            return {
                ok: false,
                error: upsertResponse.error || {
                    code: 'UPSERT_AUTOPILOT_ERROR',
                    message: 'Failed to save autopilot configuration.',
                },
            };
        }
        console.log(`Autopilot enabled successfully for user ${userId}. Autopilot ID (Event ID): ${autopilotData.id}`);
        return { ok: true, data: upsertResponse.data };
    }
    catch (error) {
        console.error('Error enabling Autopilot:', error);
        return {
            ok: false,
            error: {
                code: 'ENABLE_AUTOPILOT_EXCEPTION',
                message: error.message || 'An unexpected error occurred.',
            },
        };
    }
}
export async function disableAutopilot(userId, query) {
    console.log(`Attempting to disable Autopilot for user ${userId} with query: ${query}`);
    const parsedQuery = parseQuery(query);
    const eventId = parsedQuery.eventId || parsedQuery.autopilotId; // Query should provide the eventId (which is also the autopilotId)
    if (!eventId) {
        console.error('Error disabling Autopilot: eventId (autopilotId) not provided in query.');
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'eventId (autopilotId) is required in query to disable Autopilot.',
            },
        };
    }
    try {
        // 1. Delete the scheduled event from Hasura
        const deleteEventResponse = await deleteScheduledEventForAutopilot(eventId);
        if (!deleteEventResponse.ok) {
            console.warn(`Failed to delete scheduled event ${eventId}. It might have already been processed or deleted. Proceeding to delete DB record.`, deleteEventResponse.error);
            // Don't necessarily return an error here, as the main goal is to stop future autopilot actions.
            // The DB record deletion is also important.
        }
        else {
            console.log(`Successfully deleted scheduled event ${eventId}.`);
        }
        // 2. Delete the Autopilot record from the database
        // Assuming eventId is the same as autopilotId used in the database
        const deleteAutopilotRecordResponse = await deleteAutopilotGivenId(eventId);
        if (!deleteAutopilotRecordResponse.ok) {
            console.error(`Failed to delete Autopilot database record ${eventId}:`, deleteAutopilotRecordResponse.error);
            // This is a more significant issue if the event was deleted but the record persists.
            return {
                ok: false,
                error: deleteAutopilotRecordResponse.error || {
                    code: 'DELETE_DB_RECORD_ERROR',
                    message: `Failed to delete Autopilot record ${eventId}, but scheduled event might be deleted.`,
                },
            };
        }
        console.log(`Autopilot (ID: ${eventId}) disabled successfully for user ${userId}.`);
        return { ok: true, data: { success: true } };
    }
    catch (error) {
        console.error(`Error disabling Autopilot (ID: ${eventId}):`, error);
        return {
            ok: false,
            error: {
                code: 'DISABLE_AUTOPILOT_EXCEPTION',
                message: error.message || 'An unexpected error occurred during disable.',
            },
        };
    }
}
export async function getAutopilotStatus(userId, query) {
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
        }
        else {
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
    }
    catch (error) {
        console.error('Error getting Autopilot status:', error);
        return {
            ok: false,
            error: {
                code: 'GET_AUTOPILOT_STATUS_EXCEPTION',
                message: error.message || 'An unexpected error occurred.',
            },
        };
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXV0b3BpbG90U2tpbGxzLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiYXV0b3BpbG90U2tpbGxzLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLE9BQU8sRUFDTCxvQ0FBb0MsRUFDcEMsa0JBQWtCLEVBQ2xCLGdDQUFnQyxFQUNoQyxzQkFBc0IsRUFDdEIseUJBQXlCLEVBQ3pCLG1CQUFtQixHQUNwQixNQUFNLGtDQUFrQyxDQUFDO0FBTTFDLE9BQU8sS0FBSyxNQUFNLE9BQU8sQ0FBQztBQUMxQixPQUFPLFFBQVEsTUFBTSx1QkFBdUIsQ0FBQztBQUM3QyxPQUFPLEdBQUcsTUFBTSxrQkFBa0IsQ0FBQztBQUVuQyxLQUFLLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxDQUFDO0FBQ3ZCLEtBQUssQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUM7QUFZbEIsd0RBQXdEO0FBQ3hELFNBQVMsVUFBVSxDQUFDLEtBQWE7SUFDL0IsSUFBSSxDQUFDO1FBQ0gsdUVBQXVFO1FBQ3ZFLE9BQU8sSUFBSSxDQUFDLEtBQUssQ0FBQyxLQUFLLENBQUMsQ0FBQztJQUMzQixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLDRFQUE0RTtRQUM1RSxPQUFPLENBQUMsSUFBSSxDQUNWLHFDQUFxQyxLQUFLLHFEQUFxRCxDQUNoRyxDQUFDO1FBQ0Ysd0ZBQXdGO1FBQ3hGLG1EQUFtRDtRQUNuRCxJQUFJLEtBQUssQ0FBQyxNQUFNLEdBQUcsQ0FBQyxJQUFJLENBQUMsS0FBSyxDQUFDLFFBQVEsQ0FBQyxHQUFHLENBQUMsRUFBRSxDQUFDO1lBQzdDLHNDQUFzQztZQUN0QyxPQUFPLEVBQUUsV0FBVyxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsS0FBSyxFQUFFLENBQUMsQ0FBQyw0QkFBNEI7UUFDN0UsQ0FBQztRQUNELE9BQU8sRUFBRSxDQUFDO0lBQ1osQ0FBQztBQUNILENBQUM7QUFFRCxNQUFNLENBQUMsS0FBSyxVQUFVLGVBQWUsQ0FD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QztRQUNwQixPQUFPLENBQUMsS0FBSyxDQUFDLGlDQUFpQyxFQUFFLEtBQUssQ0FBQyxDQUFDO1FBQ3hELE9BQU87WUFDTCxFQUFFLEVBQUUsS0FBSztZQUNULEtBQUssRUFBRTtnQkFDTCxJQUFJLEVBQUUsZ0NBQWdDO2dCQUN0QyxPQUFPLEVBQUUsS0FBSyxDQUFDLE9BQU8sSUFBSSwrQkFBK0I7YUFDMUQ7U0FDRixDQUFDO0lBQ0osQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQge1xuICBjcmVhdGVEYWlseUZlYXR1cmVzQXBwbHlFdmVudFRyaWdnZXIsXG4gIHVwc2VydEF1dG9waWxvdE9uZSxcbiAgZGVsZXRlU2NoZWR1bGVkRXZlbnRGb3JBdXRvcGlsb3QsXG4gIGRlbGV0ZUF1dG9waWxvdEdpdmVuSWQsXG4gIGxpc3RBdXRvcGlsb3RzR2l2ZW5Vc2VySWQsXG4gIGdldEF1dG9waWxvdEdpdmVuSWQsXG59IGZyb20gJy4uLy4uL2F1dG9waWxvdC9fbGlicy9hcGktaGVscGVyJztcbmltcG9ydCB7XG4gIEF1dG9waWxvdFR5cGUsXG4gIFNjaGVkdWxlQXNzaXN0V2l0aE1lZXRpbmdRdWV1ZUJvZHlUeXBlLFxuICBBdXRvcGlsb3RBcGlSZXNwb25zZSxcbn0gZnJvbSAnLi4vLi4vYXV0b3BpbG90L19saWJzL3R5cGVzJztcbmltcG9ydCBkYXlqcyBmcm9tICdkYXlqcyc7XG5pbXBvcnQgdGltZXpvbmUgZnJvbSAnZGF5anMvcGx1Z2luL3RpbWV6b25lJztcbmltcG9ydCB1dGMgZnJvbSAnZGF5anMvcGx1Z2luL3V0Yyc7XG5cbmRheWpzLmV4dGVuZCh0aW1lem9uZSk7XG5kYXlqcy5leHRlbmQodXRjKTtcblxuLy8gUGxhY2Vob2xkZXIgZm9yIGEgbW9yZSBzb3BoaXN0aWNhdGVkIHF1ZXJ5IHBhcnNpbmcgbWVjaGFuaXNtXG5pbnRlcmZhY2UgQXV0b3BpbG90UXVlcnkge1xuICBhdXRvcGlsb3RJZD86IHN0cmluZztcbiAgZXZlbnRJZD86IHN0cmluZztcbiAgLy8gQWRkIG90aGVyIHJlbGV2YW50IGZpZWxkcyBmcm9tIEF1dG9waWxvdFR5cGUgb3IgU2NoZWR1bGVBc3Npc3RXaXRoTWVldGluZ1F1ZXVlQm9keVR5cGUgYXMgbmVlZGVkXG4gIHNjaGVkdWxlQXQ/OiBzdHJpbmc7XG4gIHRpbWV6b25lPzogc3RyaW5nO1xuICBwYXlsb2FkPzogU2NoZWR1bGVBc3Npc3RXaXRoTWVldGluZ1F1ZXVlQm9keVR5cGU7XG59XG5cbi8vIEhlbHBlciB0byBwYXJzZSB0aGUgcXVlcnkgc3RyaW5nICh2ZXJ5IGJhc2ljIGZvciBub3cpXG5mdW5jdGlvbiBwYXJzZVF1ZXJ5KHF1ZXJ5OiBzdHJpbmcpOiBBdXRvcGlsb3RRdWVyeSB7XG4gIHRyeSB7XG4gICAgLy8gQXNzdW1pbmcgcXVlcnkgaXMgYSBKU09OIHN0cmluZyBmb3Igbm93IGZvciBlbmFibGUvZGlzYWJsZSBzcGVjaWZpY3NcbiAgICByZXR1cm4gSlNPTi5wYXJzZShxdWVyeSk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICAvLyBJZiBub3QgSlNPTiwgaXQgbWlnaHQgYmUgYSBzaW1wbGUgSUQgZm9yIGdldC9kZWxldGUsIG9yIGp1c3QgYSBkZXNjcmlwdG9yXG4gICAgY29uc29sZS53YXJuKFxuICAgICAgYFF1ZXJ5IHN0cmluZyBpcyBub3QgYSB2YWxpZCBKU09OOiAke3F1ZXJ5fS4gVHJlYXRpbmcgYXMgc2ltcGxlIHN0cmluZyBvciByZWx5aW5nIG9uIGRlZmF1bHRzLmBcbiAgICApO1xuICAgIC8vIEZvciBnZXRBdXRvcGlsb3RTdGF0dXMsIHF1ZXJ5IG1pZ2h0IGJlIGF1dG9waWxvdElkLiBGb3IgZGlzYWJsZSwgaXQgbWlnaHQgYmUgZXZlbnRJZC5cbiAgICAvLyBUaGlzIHNpbXBsaXN0aWMgcGFyc2luZyBuZWVkcyB0byBiZSBtYWRlIHJvYnVzdC5cbiAgICBpZiAocXVlcnkubGVuZ3RoID4gMCAmJiAhcXVlcnkuaW5jbHVkZXMoJ3snKSkge1xuICAgICAgLy8gU2ltcGxlIGhldXJpc3RpYyBmb3IgSUQtbGlrZSBzdHJpbmdcbiAgICAgIHJldHVybiB7IGF1dG9waWxvdElkOiBxdWVyeSwgZXZlbnRJZDogcXVlcnkgfTsgLy8gQXNzdW1lIGl0IGNvdWxkIGJlIGVpdGhlclxuICAgIH1cbiAgICByZXR1cm4ge307XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGVuYWJsZUF1dG9waWxvdChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHF1ZXJ5OiBzdHJpbmdcbik6IFByb21pc2U8QXV0b3BpbG90QXBpUmVzcG9uc2U8QXV0b3BpbG90VHlwZSB8IG51bGw+PiB7XG4gIGNvbnNvbGUubG9nKFxuICAgIGBBdHRlbXB0aW5nIHRvIGVuYWJsZSBBdXRvcGlsb3QgZm9yIHVzZXIgJHt1c2VySWR9IHdpdGggcXVlcnk6ICR7cXVlcnl9YFxuICApO1xuICBjb25zdCBwYXJzZWRRdWVyeSA9IHBhcnNlUXVlcnkocXVlcnkpO1xuXG4gIC8vIEZvciBlbmFibGluZywgd2UgbmVlZCB0byBjb25zdHJ1Y3QgQXV0b3BpbG90VHlwZSBhbmQgU2NoZWR1bGVBc3Npc3RXaXRoTWVldGluZ1F1ZXVlQm9keVR5cGVcbiAgLy8gVGhpcyBpcyBhIHNpbXBsaWZpZWQgZXhhbXBsZS4gQSByZWFsIGltcGxlbWVudGF0aW9uIHdvdWxkIG5lZWQgbW9yZSByb2J1c3QgY29uc3RydWN0aW9uIG9mIHRoZXNlIG9iamVjdHMuXG4gIC8vIFRoZSBgcXVlcnlgIHNob3VsZCBpZGVhbGx5IHByb3ZpZGUgYWxsIG5lY2Vzc2FyeSBkZXRhaWxzIGZvciBgYXV0b3BpbG90RGF0YWAgYW5kIGBib2R5RGF0YWAuXG5cbiAgY29uc3QgYm9keURhdGE6IFNjaGVkdWxlQXNzaXN0V2l0aE1lZXRpbmdRdWV1ZUJvZHlUeXBlID1cbiAgICBwYXJzZWRRdWVyeS5wYXlsb2FkIHx8IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIHdpbmRvd1N0YXJ0RGF0ZTogZGF5anMoKS5hZGQoMSwgJ2RheScpLnRvSVNPU3RyaW5nKCksIC8vIEV4YW1wbGU6IHNjaGVkdWxlIGZvciB0b21vcnJvd1xuICAgICAgd2luZG93RW5kRGF0ZTogZGF5anMoKS5hZGQoOCwgJ2RheXMnKS50b0lTT1N0cmluZygpLCAvLyBFeGFtcGxlOiA3LWRheSB3aW5kb3dcbiAgICAgIHRpbWV6b25lOiBwYXJzZWRRdWVyeS50aW1lem9uZSB8fCBkYXlqcy50ei5ndWVzcygpLFxuICAgICAgLy8gb3RoZXIgbmVjZXNzYXJ5IGZpZWxkcyBmb3IgU2NoZWR1bGVBc3Npc3RXaXRoTWVldGluZ1F1ZXVlQm9keVR5cGVcbiAgICB9O1xuXG4gIGNvbnN0IGF1dG9waWxvdERhdGE6IEF1dG9waWxvdFR5cGUgPSB7XG4gICAgaWQ6ICcnLCAvLyBUaGlzIHdpbGwgYmUgc2V0IGJ5IHRoZSBldmVudF9pZCBmcm9tIGNyZWF0ZURhaWx5RmVhdHVyZXNBcHBseUV2ZW50VHJpZ2dlclxuICAgIHVzZXJJZCxcbiAgICBzY2hlZHVsZUF0OlxuICAgICAgcGFyc2VkUXVlcnkuc2NoZWR1bGVBdCB8fCBkYXlqcyhib2R5RGF0YS53aW5kb3dTdGFydERhdGUpLnV0YygpLmZvcm1hdCgpLFxuICAgIHRpbWV6b25lOiBib2R5RGF0YS50aW1lem9uZSxcbiAgICBwYXlsb2FkOiBib2R5RGF0YSwgLy8gRW1iZWQgdGhlIGJvZHkgZGF0YVxuICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgdXBkYXRlZEF0OiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gIH07XG5cbiAgdHJ5IHtcbiAgICAvLyAxLiBDcmVhdGUgdGhlIHNjaGVkdWxlZCBldmVudCBpbiBIYXN1cmFcbiAgICBjb25zdCBldmVudFRyaWdnZXJSZXNwb25zZSA9IGF3YWl0IGNyZWF0ZURhaWx5RmVhdHVyZXNBcHBseUV2ZW50VHJpZ2dlcihcbiAgICAgIGF1dG9waWxvdERhdGEsXG4gICAgICBib2R5RGF0YVxuICAgICk7XG4gICAgaWYgKCFldmVudFRyaWdnZXJSZXNwb25zZS5vayB8fCAhZXZlbnRUcmlnZ2VyUmVzcG9uc2UuZGF0YSkge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgJ0ZhaWxlZCB0byBjcmVhdGUgc2NoZWR1bGVkIGV2ZW50IHRyaWdnZXI6JyxcbiAgICAgICAgZXZlbnRUcmlnZ2VyUmVzcG9uc2UuZXJyb3JcbiAgICAgICk7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiBldmVudFRyaWdnZXJSZXNwb25zZS5lcnJvciB8fCB7XG4gICAgICAgICAgY29kZTogJ0NSRUFURV9FVkVOVF9FUlJPUicsXG4gICAgICAgICAgbWVzc2FnZTogJ0ZhaWxlZCB0byBjcmVhdGUgc2NoZWR1bGVkIGV2ZW50LicsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH1cblxuICAgIGF1dG9waWxvdERhdGEuaWQgPSBldmVudFRyaWdnZXJSZXNwb25zZS5kYXRhOyAvLyBUaGUgZXZlbnRfaWQgYmVjb21lcyB0aGUgYXV0b3BpbG90IHJlY29yZCdzIElEXG5cbiAgICAvLyAyLiBVcHNlcnQgdGhlIEF1dG9waWxvdCByZWNvcmQgd2l0aCB0aGUgZXZlbnRfaWQgYXMgaXRzIElEXG4gICAgY29uc3QgdXBzZXJ0UmVzcG9uc2UgPSBhd2FpdCB1cHNlcnRBdXRvcGlsb3RPbmUoYXV0b3BpbG90RGF0YSk7XG4gICAgaWYgKCF1cHNlcnRSZXNwb25zZS5vaykge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgJ0ZhaWxlZCB0byB1cHNlcnQgYXV0b3BpbG90IGNvbmZpZ3VyYXRpb246JyxcbiAgICAgICAgdXBzZXJ0UmVzcG9uc2UuZXJyb3JcbiAgICAgICk7XG4gICAgICAvLyBBdHRlbXB0IHRvIGNsZWFuIHVwIHRoZSBjcmVhdGVkIHNjaGVkdWxlZCBldmVudCBpZiB1cHNlcnQgZmFpbHNcbiAgICAgIGF3YWl0IGRlbGV0ZVNjaGVkdWxlZEV2ZW50Rm9yQXV0b3BpbG90KGF1dG9waWxvdERhdGEuaWQpO1xuICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICBgQ2xlYW5lZCB1cCBzY2hlZHVsZWQgZXZlbnQgJHthdXRvcGlsb3REYXRhLmlkfSBhZnRlciBmYWlsZWQgdXBzZXJ0LmBcbiAgICAgICk7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiB1cHNlcnRSZXNwb25zZS5lcnJvciB8fCB7XG4gICAgICAgICAgY29kZTogJ1VQU0VSVF9BVVRPUElMT1RfRVJST1InLFxuICAgICAgICAgIG1lc3NhZ2U6ICdGYWlsZWQgdG8gc2F2ZSBhdXRvcGlsb3QgY29uZmlndXJhdGlvbi4nLFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGBBdXRvcGlsb3QgZW5hYmxlZCBzdWNjZXNzZnVsbHkgZm9yIHVzZXIgJHt1c2VySWR9LiBBdXRvcGlsb3QgSUQgKEV2ZW50IElEKTogJHthdXRvcGlsb3REYXRhLmlkfWBcbiAgICApO1xuICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiB1cHNlcnRSZXNwb25zZS5kYXRhIH07XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBlbmFibGluZyBBdXRvcGlsb3Q6JywgZXJyb3IpO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnRU5BQkxFX0FVVE9QSUxPVF9FWENFUFRJT04nLFxuICAgICAgICBtZXNzYWdlOiBlcnJvci5tZXNzYWdlIHx8ICdBbiB1bmV4cGVjdGVkIGVycm9yIG9jY3VycmVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGRpc2FibGVBdXRvcGlsb3QoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBxdWVyeTogc3RyaW5nXG4pOiBQcm9taXNlPEF1dG9waWxvdEFwaVJlc3BvbnNlPHsgc3VjY2VzczogYm9vbGVhbiB9Pj4ge1xuICBjb25zb2xlLmxvZyhcbiAgICBgQXR0ZW1wdGluZyB0byBkaXNhYmxlIEF1dG9waWxvdCBmb3IgdXNlciAke3VzZXJJZH0gd2l0aCBxdWVyeTogJHtxdWVyeX1gXG4gICk7XG4gIGNvbnN0IHBhcnNlZFF1ZXJ5ID0gcGFyc2VRdWVyeShxdWVyeSk7XG4gIGNvbnN0IGV2ZW50SWQgPSBwYXJzZWRRdWVyeS5ldmVudElkIHx8IHBhcnNlZFF1ZXJ5LmF1dG9waWxvdElkOyAvLyBRdWVyeSBzaG91bGQgcHJvdmlkZSB0aGUgZXZlbnRJZCAod2hpY2ggaXMgYWxzbyB0aGUgYXV0b3BpbG90SWQpXG5cbiAgaWYgKCFldmVudElkKSB7XG4gICAgY29uc29sZS5lcnJvcihcbiAgICAgICdFcnJvciBkaXNhYmxpbmcgQXV0b3BpbG90OiBldmVudElkIChhdXRvcGlsb3RJZCkgbm90IHByb3ZpZGVkIGluIHF1ZXJ5LidcbiAgICApO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgJ2V2ZW50SWQgKGF1dG9waWxvdElkKSBpcyByZXF1aXJlZCBpbiBxdWVyeSB0byBkaXNhYmxlIEF1dG9waWxvdC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgdHJ5IHtcbiAgICAvLyAxLiBEZWxldGUgdGhlIHNjaGVkdWxlZCBldmVudCBmcm9tIEhhc3VyYVxuICAgIGNvbnN0IGRlbGV0ZUV2ZW50UmVzcG9uc2UgPSBhd2FpdCBkZWxldGVTY2hlZHVsZWRFdmVudEZvckF1dG9waWxvdChldmVudElkKTtcbiAgICBpZiAoIWRlbGV0ZUV2ZW50UmVzcG9uc2Uub2spIHtcbiAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgYEZhaWxlZCB0byBkZWxldGUgc2NoZWR1bGVkIGV2ZW50ICR7ZXZlbnRJZH0uIEl0IG1pZ2h0IGhhdmUgYWxyZWFkeSBiZWVuIHByb2Nlc3NlZCBvciBkZWxldGVkLiBQcm9jZWVkaW5nIHRvIGRlbGV0ZSBEQiByZWNvcmQuYCxcbiAgICAgICAgZGVsZXRlRXZlbnRSZXNwb25zZS5lcnJvclxuICAgICAgKTtcbiAgICAgIC8vIERvbid0IG5lY2Vzc2FyaWx5IHJldHVybiBhbiBlcnJvciBoZXJlLCBhcyB0aGUgbWFpbiBnb2FsIGlzIHRvIHN0b3AgZnV0dXJlIGF1dG9waWxvdCBhY3Rpb25zLlxuICAgICAgLy8gVGhlIERCIHJlY29yZCBkZWxldGlvbiBpcyBhbHNvIGltcG9ydGFudC5cbiAgICB9IGVsc2Uge1xuICAgICAgY29uc29sZS5sb2coYFN1Y2Nlc3NmdWxseSBkZWxldGVkIHNjaGVkdWxlZCBldmVudCAke2V2ZW50SWR9LmApO1xuICAgIH1cblxuICAgIC8vIDIuIERlbGV0ZSB0aGUgQXV0b3BpbG90IHJlY29yZCBmcm9tIHRoZSBkYXRhYmFzZVxuICAgIC8vIEFzc3VtaW5nIGV2ZW50SWQgaXMgdGhlIHNhbWUgYXMgYXV0b3BpbG90SWQgdXNlZCBpbiB0aGUgZGF0YWJhc2VcbiAgICBjb25zdCBkZWxldGVBdXRvcGlsb3RSZWNvcmRSZXNwb25zZSA9IGF3YWl0IGRlbGV0ZUF1dG9waWxvdEdpdmVuSWQoZXZlbnRJZCk7XG4gICAgaWYgKCFkZWxldGVBdXRvcGlsb3RSZWNvcmRSZXNwb25zZS5vaykge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgYEZhaWxlZCB0byBkZWxldGUgQXV0b3BpbG90IGRhdGFiYXNlIHJlY29yZCAke2V2ZW50SWR9OmAsXG4gICAgICAgIGRlbGV0ZUF1dG9waWxvdFJlY29yZFJlc3BvbnNlLmVycm9yXG4gICAgICApO1xuICAgICAgLy8gVGhpcyBpcyBhIG1vcmUgc2lnbmlmaWNhbnQgaXNzdWUgaWYgdGhlIGV2ZW50IHdhcyBkZWxldGVkIGJ1dCB0aGUgcmVjb3JkIHBlcnNpc3RzLlxuICAgICAgcmV0dXJuIHtcbiAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICBlcnJvcjogZGVsZXRlQXV0b3BpbG90UmVjb3JkUmVzcG9uc2UuZXJyb3IgfHwge1xuICAgICAgICAgIGNvZGU6ICdERUxFVEVfREJfUkVDT1JEX0VSUk9SJyxcbiAgICAgICAgICBtZXNzYWdlOiBgRmFpbGVkIHRvIGRlbGV0ZSBBdXRvcGlsb3QgcmVjb3JkICR7ZXZlbnRJZH0sIGJ1dCBzY2hlZHVsZWQgZXZlbnQgbWlnaHQgYmUgZGVsZXRlZC5gLFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGBBdXRvcGlsb3QgKElEOiAke2V2ZW50SWR9KSBkaXNhYmxlZCBzdWNjZXNzZnVsbHkgZm9yIHVzZXIgJHt1c2VySWR9LmBcbiAgICApO1xuICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiB7IHN1Y2Nlc3M6IHRydWUgfSB9O1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcihgRXJyb3IgZGlzYWJsaW5nIEF1dG9waWxvdCAoSUQ6ICR7ZXZlbnRJZH0pOmAsIGVycm9yKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0RJU0FCTEVfQVVUT1BJTE9UX0VYQ0VQVElPTicsXG4gICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgZXJyb3IubWVzc2FnZSB8fCAnQW4gdW5leHBlY3RlZCBlcnJvciBvY2N1cnJlZCBkdXJpbmcgZGlzYWJsZS4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRBdXRvcGlsb3RTdGF0dXMoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBxdWVyeTogc3RyaW5nXG4pOiBQcm9taXNlPEF1dG9waWxvdEFwaVJlc3BvbnNlPEF1dG9waWxvdFR5cGUgfCBBdXRvcGlsb3RUeXBlW10gfCBudWxsPj4ge1xuICBjb25zb2xlLmxvZyhcbiAgICBgR2V0dGluZyBBdXRvcGlsb3Qgc3RhdHVzIGZvciB1c2VyICR7dXNlcklkfSB3aXRoIHF1ZXJ5OiAke3F1ZXJ5fWBcbiAgKTtcbiAgY29uc3QgcGFyc2VkUXVlcnkgPSBwYXJzZVF1ZXJ5KHF1ZXJ5KTtcbiAgY29uc3QgYXV0b3BpbG90SWQgPSBwYXJzZWRRdWVyeS5hdXRvcGlsb3RJZDsgLy8gUXVlcnkgbWlnaHQgcHJvdmlkZSBhIHNwZWNpZmljIGF1dG9waWxvdElkXG5cbiAgdHJ5IHtcbiAgICBpZiAoYXV0b3BpbG90SWQpIHtcbiAgICAgIC8vIElmIGEgc3BlY2lmaWMgYXV0b3BpbG90SWQgaXMgcHJvdmlkZWQsIGZldGNoIHRoYXQgb25lXG4gICAgICBjb25zb2xlLmxvZyhgRmV0Y2hpbmcgc3RhdHVzIGZvciBzcGVjaWZpYyBBdXRvcGlsb3QgSUQ6ICR7YXV0b3BpbG90SWR9YCk7XG4gICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGdldEF1dG9waWxvdEdpdmVuSWQoYXV0b3BpbG90SWQpO1xuICAgICAgaWYgKCFyZXNwb25zZS5vaykge1xuICAgICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICAgIGBFcnJvciBmZXRjaGluZyBzdGF0dXMgZm9yIEF1dG9waWxvdCBJRCAke2F1dG9waWxvdElkfTpgLFxuICAgICAgICAgIHJlc3BvbnNlLmVycm9yXG4gICAgICAgICk7XG4gICAgICB9XG4gICAgICByZXR1cm4gcmVzcG9uc2U7XG4gICAgfSBlbHNlIHtcbiAgICAgIC8vIE90aGVyd2lzZSwgbGlzdCBhbGwgYXV0b3BpbG90cyBmb3IgdGhlIHVzZXJcbiAgICAgIC8vIE5vdGU6IGxpc3RBdXRvcGlsb3RzR2l2ZW5Vc2VySWQgY3VycmVudGx5IHJldHVybnMgQXV0b3BpbG90VHlwZSB8IG51bGwgKHRoZSBmaXJzdCBvbmUpXG4gICAgICAvLyBJZiBtdWx0aXBsZSBhcmUgZXhwZWN0ZWQsIGFwaS1oZWxwZXIudHMgd291bGQgbmVlZCBhZGp1c3RtZW50IG9yIHdlIGxpc3QgYWxsIGFuZCByZXR1cm4gYXMgYXJyYXlcbiAgICAgIGNvbnNvbGUubG9nKGBGZXRjaGluZyBhbGwgQXV0b3BpbG90IHN0YXR1c2VzIGZvciB1c2VyIElEOiAke3VzZXJJZH1gKTtcbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgbGlzdEF1dG9waWxvdHNHaXZlblVzZXJJZCh1c2VySWQpOyAvLyBUaGlzIGdldHMgb25lIHJlY29yZFxuICAgICAgLy8gVG8gbGlzdCBBTEwsIHdlIHdvdWxkIG5lZWQgYSBkaWZmZXJlbnQgaGVscGVyIG9yIG1vZGlmeSBsaXN0QXV0b3BpbG90c0dpdmVuVXNlcklkXG4gICAgICAvLyBGb3Igbm93LCBzdGlja2luZyB0byB0aGUgY3VycmVudCBoZWxwZXIncyBiZWhhdmlvci5cbiAgICAgIC8vIElmIHlvdSBuZWVkIGFsbCwgdGhlIGhlbHBlciBgbGlzdEF1dG9waWxvdHNHaXZlblVzZXJJZGAgc2hvdWxkIGJlIG1vZGlmaWVkIHRvIHJldHVybiBgQXV0b3BpbG90VHlwZVtdIHwgbnVsbGBcbiAgICAgIC8vIGFuZCB0aGUgR3JhcGhRTCBxdWVyeSBpbnNpZGUgaXQgc2hvdWxkIG5vdCBwaWNrIFswXS5cbiAgICAgIGlmICghcmVzcG9uc2Uub2spIHtcbiAgICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgICBgRXJyb3IgZmV0Y2hpbmcgQXV0b3BpbG90IHN0YXR1c2VzIGZvciB1c2VyICR7dXNlcklkfTpgLFxuICAgICAgICAgIHJlc3BvbnNlLmVycm9yXG4gICAgICAgICk7XG4gICAgICB9XG4gICAgICByZXR1cm4gcmVzcG9uc2U7XG4gICAgfVxuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcignRXJyb3IgZ2V0dGluZyBBdXRvcGlsb3Qgc3RhdHVzOicsIGVycm9yKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0dFVF9BVVRPUElMT1RfU1RBVFVTX0VYQ0VQVElPTicsXG4gICAgICAgIG1lc3NhZ2U6IGVycm9yLm1lc3NhZ2UgfHwgJ0FuIHVuZXhwZWN0ZWQgZXJyb3Igb2NjdXJyZWQuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufVxuIl19