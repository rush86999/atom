// Assuming a logger is available or can be imported/passed
// For now, using console for simplicity within this file.
const logger = {
    info: console.log,
    warn: console.warn,
    error: console.error,
};
import { sendSlackMessage } from '../skills/slackSkills';
// --- Shared State Import ---
import { retrievePendingRequest, removePendingRequest, } from '../sharedAgentState';
// Real user notification logic using Slack DMs
async function sendUserNotification(userId, message) {
    // userId here is assumed to be the Slack User ID for Direct Messaging.
    // The first argument to sendSlackMessage is a contextual 'calling' userId for logging within slackSkills.
    const agentProcessId = 'atomic-agent-scheduler-callback';
    logger.info(`[sendUserNotification] Attempting to send Slack DM to userId: ${userId}`);
    // Message content is already logged by the caller (handleSchedulerCallback) before this function.
    // logger.info(`[sendUserNotification] Message: "${message}"`);
    try {
        // Using userId as the channel for a DM, and a generic process ID for the first arg.
        const slackResponse = await sendSlackMessage(agentProcessId, userId, message);
        if (slackResponse.ok) {
            logger.info(`[sendUserNotification] Successfully sent Slack DM to userId: ${userId}. Message ID: ${slackResponse.ts}`);
            return true;
        }
        else {
            logger.error(`[sendUserNotification] Failed to send Slack DM to userId: ${userId}. Error: ${slackResponse.error}`);
            return false;
        }
    }
    catch (error) {
        logger.error(`[sendUserNotification] Exception while sending Slack DM to userId: ${userId}. Error: ${error.message}`, error.stack);
        return false;
    }
}
// --- Main Callback Handler Function ---
// Access environment variable for the expected token
const EXPECTED_CALLBACK_TOKEN = process.env.CALLBACK_SECRET_TOKEN;
export async function handleSchedulerCallback(req, res) {
    logger.info('[schedulerCallbackHandler.handleSchedulerCallback] Received a callback request.');
    // --- NEW TOKEN VALIDATION LOGIC ---
    if (!EXPECTED_CALLBACK_TOKEN) {
        logger.error('[schedulerCallbackHandler.handleSchedulerCallback] CRITICAL: CALLBACK_SECRET_TOKEN is not configured in the environment. Cannot securely process callbacks.');
        res
            .status(500)
            .send({
            error: 'Internal Server Error: Callback security not configured.',
        });
        return;
    }
    const receivedToken = req.headers['x-callback-token'];
    if (!receivedToken) {
        logger.warn('[schedulerCallbackHandler.handleSchedulerCallback] Unauthorized: Missing X-Callback-Token in request headers.');
        res.status(401).send({ error: 'Unauthorized: Missing callback token.' });
        return;
    }
    if (receivedToken !== EXPECTED_CALLBACK_TOKEN) {
        logger.warn('[schedulerCallbackHandler.handleSchedulerCallback] Forbidden: Invalid X-Callback-Token received.');
        // Potentially log the received token for debugging if in a dev environment, but be cautious in prod.
        // logger.info(`Received token: ${receivedToken}`);
        res.status(403).send({ error: 'Forbidden: Invalid callback token.' });
        return;
    }
    logger.info('[schedulerCallbackHandler.handleSchedulerCallback] Callback token validated successfully.');
    // --- END OF NEW TOKEN VALIDATION LOGIC ---
    // Existing logic starts here:
    if (!req.body) {
        logger.warn('[schedulerCallbackHandler.handleSchedulerCallback] Callback request body is empty after token validation.');
        res.status(400).send({ error: 'Bad Request: Empty payload.' });
        return;
    }
    const solution = req.body;
    logger.info('[schedulerCallbackHandler.handleSchedulerCallback] Processing solution for fileKey:', solution.fileKey, 'hostId:', solution.hostId);
    if (!solution.fileKey || !solution.hostId || !solution.eventPartList) {
        logger.warn('[schedulerCallbackHandler.handleSchedulerCallback] Invalid payload: Missing fileKey, hostId, or eventPartList.', solution);
        res
            .status(400)
            .send({
            error: 'Bad Request: Missing fileKey, hostId, or eventPartList.',
        });
        return;
    }
    const requestContext = await retrievePendingRequest(solution.fileKey);
    if (!requestContext) {
        logger.warn(`[schedulerCallbackHandler.handleSchedulerCallback] No pending request found for fileKey: ${solution.fileKey}. It might have been already processed, timed out, or is invalid.`);
        res
            .status(200)
            .send({
            message: 'Callback received, but no matching pending request found or already processed.',
        });
        return;
    }
    const { userId, singletonId, originalQuery, submittedAt } = requestContext;
    logger.info(`[schedulerCallbackHandler.handleSchedulerCallback] Found context for fileKey ${solution.fileKey}: userId=${userId}, singletonId=${singletonId}, submittedAt=${submittedAt.toISOString()}`);
    if (originalQuery) {
        logger.info(`[schedulerCallbackHandler.handleSchedulerCallback] Original query: "${originalQuery}"`);
    }
    // --- NEW LOGIC STARTS HERE ---
    try {
        const scheduledItems = [];
        const unscheduledItems = [];
        for (const part of solution.eventPartList) {
            const eventSummary = part.event?.summary ||
                part.event?.title ||
                part.event?.id ||
                part.id ||
                'Unnamed Event Part';
            if (part.timeslot) {
                let scheduledTimeInfo = 'at an unspecified time';
                if (part.timeslot.startTime && part.timeslot.endTime) {
                    const dateHint = part.timeslot.monthDay
                        ? `on ${part.timeslot.monthDay}`
                        : ''; // Assuming monthDay is like MM-DD
                    // To get a full date for the timeslot, we might need to infer the year or the scheduler needs to provide it.
                    // For now, relying on dayOfWeek and monthDay if available.
                    let dayInfo = part.timeslot.dayOfWeek || '';
                    if (dateHint) {
                        dayInfo = dayInfo ? `${dateHint} (${dayInfo})` : dateHint;
                    }
                    scheduledTimeInfo = `from ${part.timeslot.startTime} to ${part.timeslot.endTime}${dayInfo ? ' ' + dayInfo : ''}`;
                }
                scheduledItems.push(`- '${eventSummary}' scheduled ${scheduledTimeInfo.trim()}`);
            }
            else {
                unscheduledItems.push(`- '${eventSummary}' could not be scheduled.`);
            }
        }
        let notificationMessage = `Update for your scheduling request${originalQuery ? ` ("${originalQuery}")` : ''}:\n`;
        if (scheduledItems.length > 0) {
            notificationMessage += `\nSuccessfully scheduled items:\n${scheduledItems.join('\n')}\n`;
        }
        if (unscheduledItems.length > 0) {
            notificationMessage += `\nItems that could not be scheduled:\n${unscheduledItems.join('\n')}\n`;
        }
        if (scheduledItems.length === 0 &&
            unscheduledItems.length === 0 &&
            solution.eventPartList.length > 0) {
            notificationMessage +=
                'The scheduling process completed, but detailed outcomes for some items were not clear.\n';
        }
        else if (solution.eventPartList.length === 0) {
            notificationMessage +=
                'The scheduling process completed, but no events were processed.\n';
        }
        if (solution.score) {
            notificationMessage += `\nOverall schedule score: ${solution.score}`;
        }
        const notificationSent = await sendUserNotification(userId, notificationMessage.trim());
        if (notificationSent) {
            logger.info(`[schedulerCallbackHandler.handleSchedulerCallback] User notification successful for userId: ${userId}, fileKey: ${solution.fileKey}`);
        }
        else {
            logger.warn(`[schedulerCallbackHandler.handleSchedulerCallback] User notification FAILED for userId: ${userId}, fileKey: ${solution.fileKey}. The scheduling solution was processed, but the user was not notified via Slack.`);
            // TODO: Consider adding this failed notification to a retry queue or alternative notification mechanism in a more robust system.
        }
        // Clean up the pending request from the store after processing, regardless of notification success for this iteration.
        await removePendingRequest(solution.fileKey);
        logger.info(`[schedulerCallbackHandler.handleSchedulerCallback] Processed and cleaned up pending request for fileKey: ${solution.fileKey}`);
        // The message to the scheduler can remain positive if solution processing was okay.
        res
            .status(200)
            .send({
            message: 'Callback processed successfully. User notification attempted.',
        });
    }
    catch (processingError) {
        logger.error(`[schedulerCallbackHandler.handleSchedulerCallback] Error processing solution for fileKey ${solution.fileKey}:`, processingError.message, processingError.stack);
        // Do not delete from pendingSchedulingRequests here in case of processing error, to allow for retries or investigation.
        res
            .status(500)
            .send({
            error: 'Callback received, but an internal error occurred during solution processing.',
        });
    }
    // --- NEW LOGIC ENDS HERE ---
}
// Example of how this might be mounted in an Express-like app (conceptual):
// import express from 'express';
// const app = express();
// app.use(express.json()); // Middleware to parse JSON bodies
// app.post('/api/scheduler-callback', handleSchedulerCallback);
// const PORT = process.env.PORT || 3000; // Agent's port
// app.listen(PORT, () => logger.info(`Agent listening on port ${PORT}`));
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic2NoZWR1bGVyQ2FsbGJhY2tIYW5kbGVyLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsic2NoZWR1bGVyQ2FsbGJhY2tIYW5kbGVyLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLDJEQUEyRDtBQUMzRCwwREFBMEQ7QUFDMUQsTUFBTSxNQUFNLEdBQUc7SUFDYixJQUFJLEVBQUUsT0FBTyxDQUFDLEdBQUc7SUFDakIsSUFBSSxFQUFFLE9BQU8sQ0FBQyxJQUFJO0lBQ2xCLEtBQUssRUFBRSxPQUFPLENBQUMsS0FBSztDQUNyQixDQUFDO0FBRUYsT0FBTyxFQUFFLGdCQUFnQixFQUFFLE1BQU0sdUJBQXVCLENBQUM7QUErQnpELDhCQUE4QjtBQUM5QixPQUFPLEVBQ0wsc0JBQXNCLEVBQ3RCLG9CQUFvQixHQUVyQixNQUFNLHFCQUFxQixDQUFDO0FBa0M3QiwrQ0FBK0M7QUFDL0MsS0FBSyxVQUFVLG9CQUFvQixDQUNqQyxNQUFjLEVBQ2QsT0FBZTtJQUVmLHVFQUF1RTtJQUN2RSwwR0FBMEc7SUFDMUcsTUFBTSxjQUFjLEdBQUcsaUNBQWlDLENBQUM7SUFDekQsTUFBTSxDQUFDLElBQUksQ0FDVCxpRUFBaUUsTUFBTSxFQUFFLENBQzFFLENBQUM7SUFDRixrR0FBa0c7SUFDbEcsK0RBQStEO0lBRS9ELElBQUksQ0FBQztRQUNILG9GQUFvRjtRQUNwRixNQUFNLGFBQWEsR0FBRyxNQUFNLGdCQUFnQixDQUMxQyxjQUFjLEVBQ2QsTUFBTSxFQUNOLE9BQU8sQ0FDUixDQUFDO1FBRUYsSUFBSSxhQUFhLENBQUMsRUFBRSxFQUFFLENBQUM7WUFDckIsTUFBTSxDQUFDLElBQUksQ0FDVCxnRUFBZ0UsTUFBTSxpQkFBaUIsYUFBYSxDQUFDLEVBQUUsRUFBRSxDQUMxRyxDQUFDO1lBQ0YsT0FBTyxJQUFJLENBQUM7UUFDZCxDQUFDO2FBQU0sQ0FBQztZQUNOLE1BQU0sQ0FBQyxLQUFLLENBQ1YsNkRBQTZELE1BQU0sWUFBWSxhQUFhLENBQUMsS0FB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O1FBQ3BGLEdBQUc7YUFDQSxNQUFNLENBQUMsR0FBRyxDQUFDO2FBQ1gsSUFBSSxDQUFDO1lBQ0osT0FBTyxFQUNMLCtEQUErRDtTQUNsRSxDQUFDLENBQUM7SUFDUCxDQUFDO0lBQUMsT0FBTyxlQUFvQixFQUFFLENBQUM7UUFDOUIsTUFBTSxDQUFDLEtBQUssQ0FDViw0RkFBNEYsUUFBUSxDQUFDLE9BQU8sR0FBRyxFQUMvRyxlQUFlLENBQUMsT0FBTyxFQUN2QixlQUFlLENBQUMsS0FBSyxDQUN0QixDQUFDO1FBQ0Ysd0hBQXdIO1FBQ3hILEdBQUc7YUFDQSxNQUFNLENBQUMsR0FBRyxDQUFDO2FBQ1gsSUFBSSxDQUFDO1lBQ0osS0FBSyxFQUNILCtFQUErRTtTQUNsRixDQUFDLENBQUM7SUFDUCxDQUFDO0lBQ0QsOEJBQThCO0FBQ2hDLENBQUM7QUFFRCw0RUFBNEU7QUFDNUUsaUNBQWlDO0FBQ2pDLHlCQUF5QjtBQUN6Qiw4REFBOEQ7QUFDOUQsZ0VBQWdFO0FBQ2hFLHlEQUF5RDtBQUN6RCwwRUFBMEUiLCJzb3VyY2VzQ29udGVudCI6WyIvLyBBc3N1bWluZyBhIGxvZ2dlciBpcyBhdmFpbGFibGUgb3IgY2FuIGJlIGltcG9ydGVkL3Bhc3NlZFxuLy8gRm9yIG5vdywgdXNpbmcgY29uc29sZSBmb3Igc2ltcGxpY2l0eSB3aXRoaW4gdGhpcyBmaWxlLlxuY29uc3QgbG9nZ2VyID0ge1xuICBpbmZvOiBjb25zb2xlLmxvZyxcbiAgd2FybjogY29uc29sZS53YXJuLFxuICBlcnJvcjogY29uc29sZS5lcnJvcixcbn07XG5cbmltcG9ydCB7IHNlbmRTbGFja01lc3NhZ2UgfSBmcm9tICcuLi9za2lsbHMvc2xhY2tTa2lsbHMnO1xuaW1wb3J0IHsgY3JlYXRlQ2FsZW5kYXJFdmVudCB9IGZyb20gJy4uL3NraWxscy9jYWxlbmRhclNraWxscyc7XG5pbXBvcnQgeyBzZW5kRW1haWwgYXMgc2VuZEVtYWlsU2tpbGwgfSBmcm9tICcuLi9za2lsbHMvZW1haWxTa2lsbHMnOyAvLyBSZW5hbWVkIHRvIGF2b2lkIGNvbmZsaWN0XG5pbXBvcnQgeyBDYWxlbmRhckV2ZW50LCBFbWFpbERldGFpbHMsIFJlc29sdmVkQXR0ZW5kZWUgfSBmcm9tICcuLi90eXBlcyc7IC8vIEltcG9ydCBuZWNlc3NhcnkgdHlwZXNcblxuLy8gLS0tIFR5cGUgRGVmaW5pdGlvbnMgZm9yIFNjaGVkdWxlciBDYWxsYmFjayBQYXlsb2FkIChUaW1lVGFibGVTb2x1dGlvbkR0bykgLS0tXG4vLyBCYXNlZCBvbiBBUElfR1VJREUubWQuIFRoZXNlIG1pZ2h0IGJlIG1vdmVkIHRvIGEgc2hhcmVkIHR5cGVzIGZpbGUgbGF0ZXIuXG5cbmludGVyZmFjZSBUaW1lc2xvdER0byB7XG4gIGhvc3RJZD86IHN0cmluZztcbiAgZGF5T2ZXZWVrPzogc3RyaW5nO1xuICBzdGFydFRpbWU/OiBzdHJpbmc7XG4gIGVuZFRpbWU/OiBzdHJpbmc7XG4gIG1vbnRoRGF5Pzogc3RyaW5nO1xufVxuXG5pbnRlcmZhY2UgVXNlckR0byB7XG4gIGlkPzogc3RyaW5nO1xuICBob3N0SWQ/OiBzdHJpbmc7XG59XG5cbmludGVyZmFjZSBFdmVudER0byB7XG4gIGlkPzogc3RyaW5nO1xuICB1c2VySWQ/OiBzdHJpbmc7XG4gIGhvc3RJZD86IHN0cmluZztcbiAgc3VtbWFyeT86IHN0cmluZztcbiAgdGl0bGU/OiBzdHJpbmc7XG4gIGRlc2NyaXB0aW9uPzogc3RyaW5nO1xuICBwcmVmZXJyZWRUaW1lUmFuZ2VzPzogYW55W10gfCBudWxsO1xufVxuXG4vLyAtLS0gU2hhcmVkIFN0YXRlIEltcG9ydCAtLS1cbmltcG9ydCB7XG4gIHJldHJpZXZlUGVuZGluZ1JlcXVlc3QsXG4gIHJlbW92ZVBlbmRpbmdSZXF1ZXN0LFxuICBQZW5kaW5nUmVxdWVzdEluZm8sXG59IGZyb20gJy4uL3NoYXJlZEFnZW50U3RhdGUnO1xuXG5leHBvcnQgaW50ZXJmYWNlIEV2ZW50UGFydER0byB7XG4gIGlkPzogc3RyaW5nO1xuICBncm91cElkPzogc3RyaW5nO1xuICBldmVudElkPzogc3RyaW5nO1xuICBldmVudD86IEV2ZW50RHRvO1xuICB1c2VyPzogVXNlckR0bztcbiAgdGltZXNsb3Q/OiBUaW1lc2xvdER0byB8IG51bGw7XG4gIHNjaGVkdWxlZD86IGJvb2xlYW47XG59XG5cbmV4cG9ydCBpbnRlcmZhY2UgVGltZVRhYmxlU29sdXRpb25EdG8ge1xuICB0aW1lc2xvdExpc3Q/OiBUaW1lc2xvdER0b1tdO1xuICB1c2VyTGlzdD86IFVzZXJEdG9bXTtcbiAgZXZlbnRQYXJ0TGlzdDogRXZlbnRQYXJ0RHRvW107XG4gIHNjb3JlOiBzdHJpbmcgfCBudWxsO1xuICBmaWxlS2V5OiBzdHJpbmcgfCBudWxsO1xuICBob3N0SWQ6IHN0cmluZyB8IG51bGw7XG59XG5cbi8vIC0tLSBQbGFjZWhvbGRlciBmb3IgUmVxdWVzdC9SZXNwb25zZSB0eXBlcyBpZiB1c2luZyBhIHNwZWNpZmljIGZyYW1ld29yayBsaWtlIEV4cHJlc3MgLS0tXG5pbnRlcmZhY2UgUmVxdWVzdCB7XG4gIGJvZHk6IGFueTtcbiAgaGVhZGVyczogUmVjb3JkPHN0cmluZywgc3RyaW5nIHwgc3RyaW5nW10gfCB1bmRlZmluZWQ+O1xufVxuXG5pbnRlcmZhY2UgUmVzcG9uc2Uge1xuICBzdGF0dXM6IChjb2RlOiBudW1iZXIpID0+IFJlc3BvbnNlO1xuICBzZW5kOiAoYm9keT86IGFueSkgPT4gUmVzcG9uc2U7XG4gIGpzb246IChib2R5PzogYW55KSA9PiBSZXNwb25zZTtcbiAgZW5kOiAoKSA9PiB2b2lkO1xufVxuXG4vLyBSZWFsIHVzZXIgbm90aWZpY2F0aW9uIGxvZ2ljIHVzaW5nIFNsYWNrIERNc1xuYXN5bmMgZnVuY3Rpb24gc2VuZFVzZXJOb3RpZmljYXRpb24oXG4gIHVzZXJJZDogc3RyaW5nLFxuICBtZXNzYWdlOiBzdHJpbmdcbik6IFByb21pc2U8Ym9vbGVhbj4ge1xuICAvLyB1c2VySWQgaGVyZSBpcyBhc3N1bWVkIHRvIGJlIHRoZSBTbGFjayBVc2VyIElEIGZvciBEaXJlY3QgTWVzc2FnaW5nLlxuICAvLyBUaGUgZmlyc3QgYXJndW1lbnQgdG8gc2VuZFNsYWNrTWVzc2FnZSBpcyBhIGNvbnRleHR1YWwgJ2NhbGxpbmcnIHVzZXJJZCBmb3IgbG9nZ2luZyB3aXRoaW4gc2xhY2tTa2lsbHMuXG4gIGNvbnN0IGFnZW50UHJvY2Vzc0lkID0gJ2F0b21pYy1hZ2VudC1zY2hlZHVsZXItY2FsbGJhY2snO1xuICBsb2dnZXIuaW5mbyhcbiAgICBgW3NlbmRVc2VyTm90aWZpY2F0aW9uXSBBdHRlbXB0aW5nIHRvIHNlbmQgU2xhY2sgRE0gdG8gdXNlcklkOiAke3VzZXJJZH1gXG4gICk7XG4gIC8vIE1lc3NhZ2UgY29udGVudCBpcyBhbHJlYWR5IGxvZ2dlZCBieSB0aGUgY2FsbGVyIChoYW5kbGVTY2hlZHVsZXJDYWxsYmFjaykgYmVmb3JlIHRoaXMgZnVuY3Rpb24uXG4gIC8vIGxvZ2dlci5pbmZvKGBbc2VuZFVzZXJOb3RpZmljYXRpb25dIE1lc3NhZ2U6IFwiJHttZXNzYWdlfVwiYCk7XG5cbiAgdHJ5IHtcbiAgICAvLyBVc2luZyB1c2VySWQgYXMgdGhlIGNoYW5uZWwgZm9yIGEgRE0sIGFuZCBhIGdlbmVyaWMgcHJvY2VzcyBJRCBmb3IgdGhlIGZpcnN0IGFyZy5cbiAgICBjb25zdCBzbGFja1Jlc3BvbnNlID0gYXdhaXQgc2VuZFNsYWNrTWVzc2FnZShcbiAgICAgIGFnZW50UHJvY2Vzc0lkLFxuICAgICAgdXNlcklkLFxuICAgICAgbWVzc2FnZVxuICAgICk7XG5cbiAgICBpZiAoc2xhY2tSZXNwb25zZS5vaykge1xuICAgICAgbG9nZ2VyLmluZm8oXG4gICAgICAgIGBbc2VuZFVzZXJOb3RpZmljYXRpb25dIFN1Y2Nlc3NmdWxseSBzZW50IFNsYWNrIERNIHRvIHVzZXJJZDogJHt1c2VySWR9LiBNZXNzYWdlIElEOiAke3NsYWNrUmVzcG9uc2UudHN9YFxuICAgICAgKTtcbiAgICAgIHJldHVybiB0cnVlO1xuICAgIH0gZWxzZSB7XG4gICAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAgIGBbc2VuZFVzZXJOb3RpZmljYXRpb25dIEZhaWxlZCB0byBzZW5kIFNsYWNrIERNIHRvIHVzZXJJZDogJHt1c2VySWR9LiBFcnJvcjogJHtzbGFja1Jlc3BvbnNlLmVycm9yfWBcbiAgICAgICk7XG4gICAgICByZXR1cm4gZmFsc2U7XG4gICAgfVxuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFtzZW5kVXNlck5vdGlmaWNhdGlvbl0gRXhjZXB0aW9uIHdoaWxlIHNlbmRpbmcgU2xhY2sgRE0gdG8gdXNlcklkOiAke3VzZXJJZH0uIEVycm9yOiAke2Vycm9yLm1lc3NhZ2V9YCxcbiAgICAgIGVycm9yLnN0YWNrXG4gICAgKTtcbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cbn1cblxuLy8gLS0tIE1haW4gQ2FsbGJhY2sgSGFuZGxlciBGdW5jdGlvbiAtLS1cblxuLy8gQWNjZXNzIGVudmlyb25tZW50IHZhcmlhYmxlIGZvciB0aGUgZXhwZWN0ZWQgdG9rZW5cbmNvbnN0IEVYUEVDVEVEX0NBTExCQUNLX1RPS0VOID0gcHJvY2Vzcy5lbnYuQ0FMTEJBQ0tfU0VDUkVUX1RPS0VOO1xuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlU2NoZWR1bGVyQ2FsbGJhY2soXG4gIHJlcTogUmVxdWVzdCxcbiAgcmVzOiBSZXNwb25zZVxuKTogUHJvbWlzZTx2b2lkPiB7XG4gIGxvZ2dlci5pbmZvKFxuICAgICdbc2NoZWR1bGVyQ2FsbGJhY2tIYW5kbGVyLmhhbmRsZVNjaGVkdWxlckNhbGxiYWNrXSBSZWNlaXZlZCBhIGNhbGxiYWNrIHJlcXVlc3QuJ1xuICApO1xuXG4gIC8vIC0tLSBORVcgVE9LRU4gVkFMSURBVElPTiBMT0dJQyAtLS1cbiAgaWYgKCFFWFBFQ1RFRF9DQUxMQkFDS19UT0tFTikge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICdbc2NoZWR1bGVyQ2FsbGJhY2tIYW5kbGVyLmhhbmRsZVNjaGVkdWxlckNhbGxiYWNrXSBDUklUSUNBTDogQ0FMTEJBQ0tfU0VDUkVUX1RPS0VOIGlzIG5vdCBjb25maWd1cmVkIGluIHRoZSBlbnZpcm9ubWVudC4gQ2Fubm90IHNlY3VyZWx5IHByb2Nlc3MgY2FsbGJhY2tzLidcbiAgICApO1xuICAgIHJlc1xuICAgICAgLnN0YXR1cyg1MDApXG4gICAgICAuc2VuZCh7XG4gICAgICAgIGVycm9yOiAnSW50ZXJuYWwgU2VydmVyIEVycm9yOiBDYWxsYmFjayBzZWN1cml0eSBub3QgY29uZmlndXJlZC4nLFxuICAgICAgfSk7XG4gICAgcmV0dXJuO1xuICB9XG5cbiAgY29uc3QgcmVjZWl2ZWRUb2tlbiA9IHJlcS5oZWFkZXJzWyd4LWNhbGxiYWNrLXRva2VuJ10gYXMgc3RyaW5nIHwgdW5kZWZpbmVkO1xuXG4gIGlmICghcmVjZWl2ZWRUb2tlbikge1xuICAgIGxvZ2dlci53YXJuKFxuICAgICAgJ1tzY2hlZHVsZXJDYWxsYmFja0hhbmRsZXIuaGFuZGxlU2NoZWR1bGVyQ2FsbGJhY2tdIFVuYXV0aG9yaXplZDogTWlzc2luZyBYLUNhbGxiYWNrLVRva2VuIGluIHJlcXVlc3QgaGVhZGVycy4nXG4gICAgKTtcbiAgICByZXMuc3RhdHVzKDQwMSkuc2VuZCh7IGVycm9yOiAnVW5hdXRob3JpemVkOiBNaXNzaW5nIGNhbGxiYWNrIHRva2VuLicgfSk7XG4gICAgcmV0dXJuO1xuICB9XG5cbiAgaWYgKHJlY2VpdmVkVG9rZW4gIT09IEVYUEVDVEVEX0NBTExCQUNLX1RPS0VOKSB7XG4gICAgbG9nZ2VyLndhcm4oXG4gICAgICAnW3NjaGVkdWxlckNhbGxiYWNrSGFuZGxlci5oYW5kbGVTY2hlZHVsZXJDYWxsYmFja10gRm9yYmlkZGVuOiBJbnZhbGlkIFgtQ2FsbGJhY2stVG9rZW4gcmVjZWl2ZWQuJ1xuICAgICk7XG4gICAgLy8gUG90ZW50aWFsbHkgbG9nIHRoZSByZWNlaXZlZCB0b2tlbiBmb3IgZGVidWdnaW5nIGlmIGluIGEgZGV2IGVudmlyb25tZW50LCBidXQgYmUgY2F1dGlvdXMgaW4gcHJvZC5cbiAgICAvLyBsb2dnZXIuaW5mbyhgUmVjZWl2ZWQgdG9rZW46ICR7cmVjZWl2ZWRUb2tlbn1gKTtcbiAgICByZXMuc3RhdHVzKDQwMykuc2VuZCh7IGVycm9yOiAnRm9yYmlkZGVuOiBJbnZhbGlkIGNhbGxiYWNrIHRva2VuLicgfSk7XG4gICAgcmV0dXJuO1xuICB9XG4gIGxvZ2dlci5pbmZvKFxuICAgICdbc2NoZWR1bGVyQ2FsbGJhY2tIYW5kbGVyLmhhbmRsZVNjaGVkdWxlckNhbGxiYWNrXSBDYWxsYmFjayB0b2tlbiB2YWxpZGF0ZWQgc3VjY2Vzc2Z1bGx5LidcbiAgKTtcbiAgLy8gLS0tIEVORCBPRiBORVcgVE9LRU4gVkFMSURBVElPTiBMT0dJQyAtLS1cblxuICAvLyBFeGlzdGluZyBsb2dpYyBzdGFydHMgaGVyZTpcbiAgaWYgKCFyZXEuYm9keSkge1xuICAgIGxvZ2dlci53YXJuKFxuICAgICAgJ1tzY2hlZHVsZXJDYWxsYmFja0hhbmRsZXIuaGFuZGxlU2NoZWR1bGVyQ2FsbGJhY2tdIENhbGxiYWNrIHJlcXVlc3QgYm9keSBpcyBlbXB0eSBhZnRlciB0b2tlbiB2YWxpZGF0aW9uLidcbiAgICApO1xuICAgIHJlcy5zdGF0dXMoNDAwKS5zZW5kKHsgZXJyb3I6ICdCYWQgUmVxdWVzdDogRW1wdHkgcGF5bG9hZC4nIH0pO1xuICAgIHJldHVybjtcbiAgfVxuXG4gIGNvbnN0IHNvbHV0aW9uID0gcmVxLmJvZHkgYXMgVGltZVRhYmxlU29sdXRpb25EdG87XG4gIGxvZ2dlci5pbmZvKFxuICAgICdbc2NoZWR1bGVyQ2FsbGJhY2tIYW5kbGVyLmhhbmRsZVNjaGVkdWxlckNhbGxiYWNrXSBQcm9jZXNzaW5nIHNvbHV0aW9uIGZvciBmaWxlS2V5OicsXG4gICAgc29sdXRpb24uZmlsZUtleSxcbiAgICAnaG9zdElkOicsXG4gICAgc29sdXRpb24uaG9zdElkXG4gICk7XG5cbiAgaWYgKCFzb2x1dGlvbi5maWxlS2V5IHx8ICFzb2x1dGlvbi5ob3N0SWQgfHwgIXNvbHV0aW9uLmV2ZW50UGFydExpc3QpIHtcbiAgICBsb2dnZXIud2FybihcbiAgICAgICdbc2NoZWR1bGVyQ2FsbGJhY2tIYW5kbGVyLmhhbmRsZVNjaGVkdWxlckNhbGxiYWNrXSBJbnZhbGlkIHBheWxvYWQ6IE1pc3NpbmcgZmlsZUtleSwgaG9zdElkLCBvciBldmVudFBhcnRMaXN0LicsXG4gICAgICBzb2x1dGlvblxuICAgICk7XG4gICAgcmVzXG4gICAgICAuc3RhdHVzKDQwMClcbiAgICAgIC5zZW5kKHtcbiAgICAgICAgZXJyb3I6ICdCYWQgUmVxdWVzdDogTWlzc2luZyBmaWxlS2V5LCBob3N0SWQsIG9yIGV2ZW50UGFydExpc3QuJyxcbiAgICAgIH0pO1xuICAgIHJldHVybjtcbiAgfVxuXG4gIGNvbnN0IHJlcXVlc3RDb250ZXh0ID0gYXdhaXQgcmV0cmlldmVQZW5kaW5nUmVxdWVzdChzb2x1dGlvbi5maWxlS2V5KTtcblxuICBpZiAoIXJlcXVlc3RDb250ZXh0KSB7XG4gICAgbG9nZ2VyLndhcm4oXG4gICAgICBgW3NjaGVkdWxlckNhbGxiYWNrSGFuZGxlci5oYW5kbGVTY2hlZHVsZXJDYWxsYmFja10gTm8gcGVuZGluZyByZXF1ZXN0IGZvdW5kIGZvciBmaWxlS2V5OiAke3NvbHV0aW9uLmZpbGVLZXl9LiBJdCBtaWdodCBoYXZlIGJlZW4gYWxyZWFkeSBwcm9jZXNzZWQsIHRpbWVkIG91dCwgb3IgaXMgaW52YWxpZC5gXG4gICAgKTtcbiAgICByZXNcbiAgICAgIC5zdGF0dXMoMjAwKVxuICAgICAgLnNlbmQoe1xuICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgICdDYWxsYmFjayByZWNlaXZlZCwgYnV0IG5vIG1hdGNoaW5nIHBlbmRpbmcgcmVxdWVzdCBmb3VuZCBvciBhbHJlYWR5IHByb2Nlc3NlZC4nLFxuICAgICAgfSk7XG4gICAgcmV0dXJuO1xuICB9XG5cbiAgY29uc3QgeyB1c2VySWQsIHNpbmdsZXRvbklkLCBvcmlnaW5hbFF1ZXJ5LCBzdWJtaXR0ZWRBdCB9ID0gcmVxdWVzdENvbnRleHQ7XG4gIGxvZ2dlci5pbmZvKFxuICAgIGBbc2NoZWR1bGVyQ2FsbGJhY2tIYW5kbGVyLmhhbmRsZVNjaGVkdWxlckNhbGxiYWNrXSBGb3VuZCBjb250ZXh0IGZvciBmaWxlS2V5ICR7c29sdXRpb24uZmlsZUtleX06IHVzZXJJZD0ke3VzZXJJZH0sIHNpbmdsZXRvbklkPSR7c2luZ2xldG9uSWR9LCBzdWJtaXR0ZWRBdD0ke3N1Ym1pdHRlZEF0LnRvSVNPU3RyaW5nKCl9YFxuICApO1xuICBpZiAob3JpZ2luYWxRdWVyeSkge1xuICAgIGxvZ2dlci5pbmZvKFxuICAgICAgYFtzY2hlZHVsZXJDYWxsYmFja0hhbmRsZXIuaGFuZGxlU2NoZWR1bGVyQ2FsbGJhY2tdIE9yaWdpbmFsIHF1ZXJ5OiBcIiR7b3JpZ2luYWxRdWVyeX1cImBcbiAgICApO1xuICB9XG5cbiAgLy8gLS0tIE5FVyBMT0dJQyBTVEFSVFMgSEVSRSAtLS1cbiAgdHJ5IHtcbiAgICBjb25zdCBzY2hlZHVsZWRJdGVtczogc3RyaW5nW10gPSBbXTtcbiAgICBjb25zdCB1bnNjaGVkdWxlZEl0ZW1zOiBzdHJpbmdbXSA9IFtdO1xuXG4gICAgZm9yIChjb25zdCBwYXJ0IG9mIHNvbHV0aW9uLmV2ZW50UGFydExpc3QpIHtcbiAgICAgIGNvbnN0IGV2ZW50U3VtbWFyeSA9XG4gICAgICAgIHBhcnQuZXZlbnQ/LnN1bW1hcnkgfHxcbiAgICAgICAgcGFydC5ldmVudD8udGl0bGUgfHxcbiAgICAgICAgcGFydC5ldmVudD8uaWQgfHxcbiAgICAgICAgcGFydC5pZCB8fFxuICAgICAgICAnVW5uYW1lZCBFdmVudCBQYXJ0JztcblxuICAgICAgaWYgKHBhcnQudGltZXNsb3QpIHtcbiAgICAgICAgbGV0IHNjaGVkdWxlZFRpbWVJbmZvID0gJ2F0IGFuIHVuc3BlY2lmaWVkIHRpbWUnO1xuICAgICAgICBpZiAocGFydC50aW1lc2xvdC5zdGFydFRpbWUgJiYgcGFydC50aW1lc2xvdC5lbmRUaW1lKSB7XG4gICAgICAgICAgY29uc3QgZGF0ZUhpbnQgPSBwYXJ0LnRpbWVzbG90Lm1vbnRoRGF5XG4gICAgICAgICAgICA/IGBvbiAke3BhcnQudGltZXNsb3QubW9udGhEYXl9YFxuICAgICAgICAgICAgOiAnJzsgLy8gQXNzdW1pbmcgbW9udGhEYXkgaXMgbGlrZSBNTS1ERFxuICAgICAgICAgIC8vIFRvIGdldCBhIGZ1bGwgZGF0ZSBmb3IgdGhlIHRpbWVzbG90LCB3ZSBtaWdodCBuZWVkIHRvIGluZmVyIHRoZSB5ZWFyIG9yIHRoZSBzY2hlZHVsZXIgbmVlZHMgdG8gcHJvdmlkZSBpdC5cbiAgICAgICAgICAvLyBGb3Igbm93LCByZWx5aW5nIG9uIGRheU9mV2VlayBhbmQgbW9udGhEYXkgaWYgYXZhaWxhYmxlLlxuICAgICAgICAgIGxldCBkYXlJbmZvID0gcGFydC50aW1lc2xvdC5kYXlPZldlZWsgfHwgJyc7XG4gICAgICAgICAgaWYgKGRhdGVIaW50KSB7XG4gICAgICAgICAgICBkYXlJbmZvID0gZGF5SW5mbyA/IGAke2RhdGVIaW50fSAoJHtkYXlJbmZvfSlgIDogZGF0ZUhpbnQ7XG4gICAgICAgICAgfVxuICAgICAgICAgIHNjaGVkdWxlZFRpbWVJbmZvID0gYGZyb20gJHtwYXJ0LnRpbWVzbG90LnN0YXJ0VGltZX0gdG8gJHtwYXJ0LnRpbWVzbG90LmVuZFRpbWV9JHtkYXlJbmZvID8gJyAnICsgZGF5SW5mbyA6ICcnfWA7XG4gICAgICAgIH1cbiAgICAgICAgc2NoZWR1bGVkSXRlbXMucHVzaChcbiAgICAgICAgICBgLSAnJHtldmVudFN1bW1hcnl9JyBzY2hlZHVsZWQgJHtzY2hlZHVsZWRUaW1lSW5mby50cmltKCl9YFxuICAgICAgICApO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgdW5zY2hlZHVsZWRJdGVtcy5wdXNoKGAtICcke2V2ZW50U3VtbWFyeX0nIGNvdWxkIG5vdCBiZSBzY2hlZHVsZWQuYCk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgbGV0IG5vdGlmaWNhdGlvbk1lc3NhZ2UgPSBgVXBkYXRlIGZvciB5b3VyIHNjaGVkdWxpbmcgcmVxdWVzdCR7b3JpZ2luYWxRdWVyeSA/IGAgKFwiJHtvcmlnaW5hbFF1ZXJ5fVwiKWAgOiAnJ306XFxuYDtcbiAgICBpZiAoc2NoZWR1bGVkSXRlbXMubGVuZ3RoID4gMCkge1xuICAgICAgbm90aWZpY2F0aW9uTWVzc2FnZSArPSBgXFxuU3VjY2Vzc2Z1bGx5IHNjaGVkdWxlZCBpdGVtczpcXG4ke3NjaGVkdWxlZEl0ZW1zLmpvaW4oJ1xcbicpfVxcbmA7XG4gICAgfVxuICAgIGlmICh1bnNjaGVkdWxlZEl0ZW1zLmxlbmd0aCA+IDApIHtcbiAgICAgIG5vdGlmaWNhdGlvbk1lc3NhZ2UgKz0gYFxcbkl0ZW1zIHRoYXQgY291bGQgbm90IGJlIHNjaGVkdWxlZDpcXG4ke3Vuc2NoZWR1bGVkSXRlbXMuam9pbignXFxuJyl9XFxuYDtcbiAgICB9XG4gICAgaWYgKFxuICAgICAgc2NoZWR1bGVkSXRlbXMubGVuZ3RoID09PSAwICYmXG4gICAgICB1bnNjaGVkdWxlZEl0ZW1zLmxlbmd0aCA9PT0gMCAmJlxuICAgICAgc29sdXRpb24uZXZlbnRQYXJ0TGlzdC5sZW5ndGggPiAwXG4gICAgKSB7XG4gICAgICBub3RpZmljYXRpb25NZXNzYWdlICs9XG4gICAgICAgICdUaGUgc2NoZWR1bGluZyBwcm9jZXNzIGNvbXBsZXRlZCwgYnV0IGRldGFpbGVkIG91dGNvbWVzIGZvciBzb21lIGl0ZW1zIHdlcmUgbm90IGNsZWFyLlxcbic7XG4gICAgfSBlbHNlIGlmIChzb2x1dGlvbi5ldmVudFBhcnRMaXN0Lmxlbmd0aCA9PT0gMCkge1xuICAgICAgbm90aWZpY2F0aW9uTWVzc2FnZSArPVxuICAgICAgICAnVGhlIHNjaGVkdWxpbmcgcHJvY2VzcyBjb21wbGV0ZWQsIGJ1dCBubyBldmVudHMgd2VyZSBwcm9jZXNzZWQuXFxuJztcbiAgICB9XG5cbiAgICBpZiAoc29sdXRpb24uc2NvcmUpIHtcbiAgICAgIG5vdGlmaWNhdGlvbk1lc3NhZ2UgKz0gYFxcbk92ZXJhbGwgc2NoZWR1bGUgc2NvcmU6ICR7c29sdXRpb24uc2NvcmV9YDtcbiAgICB9XG5cbiAgICBjb25zdCBub3RpZmljYXRpb25TZW50ID0gYXdhaXQgc2VuZFVzZXJOb3RpZmljYXRpb24oXG4gICAgICB1c2VySWQsXG4gICAgICBub3RpZmljYXRpb25NZXNzYWdlLnRyaW0oKVxuICAgICk7XG5cbiAgICBpZiAobm90aWZpY2F0aW9uU2VudCkge1xuICAgICAgbG9nZ2VyLmluZm8oXG4gICAgICAgIGBbc2NoZWR1bGVyQ2FsbGJhY2tIYW5kbGVyLmhhbmRsZVNjaGVkdWxlckNhbGxiYWNrXSBVc2VyIG5vdGlmaWNhdGlvbiBzdWNjZXNzZnVsIGZvciB1c2VySWQ6ICR7dXNlcklkfSwgZmlsZUtleTogJHtzb2x1dGlvbi5maWxlS2V5fWBcbiAgICAgICk7XG4gICAgfSBlbHNlIHtcbiAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICBgW3NjaGVkdWxlckNhbGxiYWNrSGFuZGxlci5oYW5kbGVTY2hlZHVsZXJDYWxsYmFja10gVXNlciBub3RpZmljYXRpb24gRkFJTEVEIGZvciB1c2VySWQ6ICR7dXNlcklkfSwgZmlsZUtleTogJHtzb2x1dGlvbi5maWxlS2V5fS4gVGhlIHNjaGVkdWxpbmcgc29sdXRpb24gd2FzIHByb2Nlc3NlZCwgYnV0IHRoZSB1c2VyIHdhcyBub3Qgbm90aWZpZWQgdmlhIFNsYWNrLmBcbiAgICAgICk7XG4gICAgICAvLyBUT0RPOiBDb25zaWRlciBhZGRpbmcgdGhpcyBmYWlsZWQgbm90aWZpY2F0aW9uIHRvIGEgcmV0cnkgcXVldWUgb3IgYWx0ZXJuYXRpdmUgbm90aWZpY2F0aW9uIG1lY2hhbmlzbSBpbiBhIG1vcmUgcm9idXN0IHN5c3RlbS5cbiAgICB9XG5cbiAgICAvLyBDbGVhbiB1cCB0aGUgcGVuZGluZyByZXF1ZXN0IGZyb20gdGhlIHN0b3JlIGFmdGVyIHByb2Nlc3NpbmcsIHJlZ2FyZGxlc3Mgb2Ygbm90aWZpY2F0aW9uIHN1Y2Nlc3MgZm9yIHRoaXMgaXRlcmF0aW9uLlxuICAgIGF3YWl0IHJlbW92ZVBlbmRpbmdSZXF1ZXN0KHNvbHV0aW9uLmZpbGVLZXkpO1xuICAgIGxvZ2dlci5pbmZvKFxuICAgICAgYFtzY2hlZHVsZXJDYWxsYmFja0hhbmRsZXIuaGFuZGxlU2NoZWR1bGVyQ2FsbGJhY2tdIFByb2Nlc3NlZCBhbmQgY2xlYW5lZCB1cCBwZW5kaW5nIHJlcXVlc3QgZm9yIGZpbGVLZXk6ICR7c29sdXRpb24uZmlsZUtleX1gXG4gICAgKTtcblxuICAgIC8vIFRoZSBtZXNzYWdlIHRvIHRoZSBzY2hlZHVsZXIgY2FuIHJlbWFpbiBwb3NpdGl2ZSBpZiBzb2x1dGlvbiBwcm9jZXNzaW5nIHdhcyBva2F5LlxuICAgIHJlc1xuICAgICAgLnN0YXR1cygyMDApXG4gICAgICAuc2VuZCh7XG4gICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgJ0NhbGxiYWNrIHByb2Nlc3NlZCBzdWNjZXNzZnVsbHkuIFVzZXIgbm90aWZpY2F0aW9uIGF0dGVtcHRlZC4nLFxuICAgICAgfSk7XG4gIH0gY2F0Y2ggKHByb2Nlc3NpbmdFcnJvcjogYW55KSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFtzY2hlZHVsZXJDYWxsYmFja0hhbmRsZXIuaGFuZGxlU2NoZWR1bGVyQ2FsbGJhY2tdIEVycm9yIHByb2Nlc3Npbmcgc29sdXRpb24gZm9yIGZpbGVLZXkgJHtzb2x1dGlvbi5maWxlS2V5fTpgLFxuICAgICAgcHJvY2Vzc2luZ0Vycm9yLm1lc3NhZ2UsXG4gICAgICBwcm9jZXNzaW5nRXJyb3Iuc3RhY2tcbiAgICApO1xuICAgIC8vIERvIG5vdCBkZWxldGUgZnJvbSBwZW5kaW5nU2NoZWR1bGluZ1JlcXVlc3RzIGhlcmUgaW4gY2FzZSBvZiBwcm9jZXNzaW5nIGVycm9yLCB0byBhbGxvdyBmb3IgcmV0cmllcyBvciBpbnZlc3RpZ2F0aW9uLlxuICAgIHJlc1xuICAgICAgLnN0YXR1cyg1MDApXG4gICAgICAuc2VuZCh7XG4gICAgICAgIGVycm9yOlxuICAgICAgICAgICdDYWxsYmFjayByZWNlaXZlZCwgYnV0IGFuIGludGVybmFsIGVycm9yIG9jY3VycmVkIGR1cmluZyBzb2x1dGlvbiBwcm9jZXNzaW5nLicsXG4gICAgICB9KTtcbiAgfVxuICAvLyAtLS0gTkVXIExPR0lDIEVORFMgSEVSRSAtLS1cbn1cblxuLy8gRXhhbXBsZSBvZiBob3cgdGhpcyBtaWdodCBiZSBtb3VudGVkIGluIGFuIEV4cHJlc3MtbGlrZSBhcHAgKGNvbmNlcHR1YWwpOlxuLy8gaW1wb3J0IGV4cHJlc3MgZnJvbSAnZXhwcmVzcyc7XG4vLyBjb25zdCBhcHAgPSBleHByZXNzKCk7XG4vLyBhcHAudXNlKGV4cHJlc3MuanNvbigpKTsgLy8gTWlkZGxld2FyZSB0byBwYXJzZSBKU09OIGJvZGllc1xuLy8gYXBwLnBvc3QoJy9hcGkvc2NoZWR1bGVyLWNhbGxiYWNrJywgaGFuZGxlU2NoZWR1bGVyQ2FsbGJhY2spO1xuLy8gY29uc3QgUE9SVCA9IHByb2Nlc3MuZW52LlBPUlQgfHwgMzAwMDsgLy8gQWdlbnQncyBwb3J0XG4vLyBhcHAubGlzdGVuKFBPUlQsICgpID0+IGxvZ2dlci5pbmZvKGBBZ2VudCBsaXN0ZW5pbmcgb24gcG9ydCAke1BPUlR9YCkpO1xuIl19