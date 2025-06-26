// Assuming a logger is available or can be imported/passed
// For now, using console for simplicity within this file.
const logger = {
  info: console.log,
  warn: console.warn,
  error: console.error,
};

import { sendSlackMessage } from '../skills/slackSkills';
import { createCalendarEvent } from '../skills/calendarSkills';
import { sendEmail as sendEmailSkill } from '../skills/emailSkills'; // Renamed to avoid conflict
import { CalendarEvent, EmailDetails, ResolvedAttendee } from '../types'; // Import necessary types

// --- Type Definitions for Scheduler Callback Payload (TimeTableSolutionDto) ---
// Based on API_GUIDE.md. These might be moved to a shared types file later.

interface TimeslotDto {
  hostId?: string;
  dayOfWeek?: string;
  startTime?: string;
  endTime?: string;
  monthDay?: string;
}

interface UserDto {
  id?: string;
  hostId?: string;
}

interface EventDto {
  id?: string;
  userId?: string;
  hostId?: string;
  summary?: string;
  title?: string;
  description?: string;
  preferredTimeRanges?: any[] | null;
}

// --- Shared State Import ---
import { retrievePendingRequest, removePendingRequest, PendingRequestInfo } from '../sharedAgentState';

export interface EventPartDto {
  id?: string;
  groupId?: string;
  eventId?: string;
  event?: EventDto;
  user?: UserDto;
  timeslot?: TimeslotDto | null;
  scheduled?: boolean;
}

export interface TimeTableSolutionDto {
  timeslotList?: TimeslotDto[];
  userList?: UserDto[];
  eventPartList: EventPartDto[];
  score: string | null;
  fileKey: string | null;
  hostId: string | null;
}

// --- Placeholder for Request/Response types if using a specific framework like Express ---
interface Request {
  body: any;
  headers: Record<string, string | string[] | undefined>;
}

interface Response {
  status: (code: number) => Response;
  send: (body?: any) => Response;
  json: (body?: any) => Response;
  end: () => void;
}

// Real user notification logic using Slack DMs
async function sendUserNotification(userId: string, message: string): Promise<boolean> {
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
    } else {
      logger.error(`[sendUserNotification] Failed to send Slack DM to userId: ${userId}. Error: ${slackResponse.error}`);
      return false;
    }
  } catch (error: any) {
    logger.error(`[sendUserNotification] Exception while sending Slack DM to userId: ${userId}. Error: ${error.message}`, error.stack);
    return false;
  }
}


// --- Main Callback Handler Function ---

// Access environment variable for the expected token
const EXPECTED_CALLBACK_TOKEN = process.env.CALLBACK_SECRET_TOKEN;

export async function handleSchedulerCallback(req: Request, res: Response): Promise<void> {
  logger.info('[schedulerCallbackHandler.handleSchedulerCallback] Received a callback request.');

  // --- NEW TOKEN VALIDATION LOGIC ---
  if (!EXPECTED_CALLBACK_TOKEN) {
    logger.error('[schedulerCallbackHandler.handleSchedulerCallback] CRITICAL: CALLBACK_SECRET_TOKEN is not configured in the environment. Cannot securely process callbacks.');
    res.status(500).send({ error: 'Internal Server Error: Callback security not configured.' });
    return;
  }

  const receivedToken = req.headers['x-callback-token'] as string | undefined;

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

  const solution = req.body as TimeTableSolutionDto;
  logger.info('[schedulerCallbackHandler.handleSchedulerCallback] Processing solution for fileKey:', solution.fileKey, 'hostId:', solution.hostId);

  if (!solution.fileKey || !solution.hostId || !solution.eventPartList) {
    logger.warn('[schedulerCallbackHandler.handleSchedulerCallback] Invalid payload: Missing fileKey, hostId, or eventPartList.', solution);
    res.status(400).send({ error: 'Bad Request: Missing fileKey, hostId, or eventPartList.' });
    return;
  }

  const requestContext = await retrievePendingRequest(solution.fileKey);

  if (!requestContext) {
    logger.warn(`[schedulerCallbackHandler.handleSchedulerCallback] No pending request found for fileKey: ${solution.fileKey}. It might have been already processed, timed out, or is invalid.`);
    res.status(200).send({ message: 'Callback received, but no matching pending request found or already processed.' });
    return;
  }

  const { userId, singletonId, originalQuery, submittedAt } = requestContext;
  logger.info(`[schedulerCallbackHandler.handleSchedulerCallback] Found context for fileKey ${solution.fileKey}: userId=${userId}, singletonId=${singletonId}, submittedAt=${submittedAt.toISOString()}`);
  if (originalQuery) {
    logger.info(`[schedulerCallbackHandler.handleSchedulerCallback] Original query: "${originalQuery}"`);
  }

  // --- NEW LOGIC STARTS HERE ---
  try {
    const scheduledItems: string[] = [];
    const unscheduledItems: string[] = [];

    for (const part of solution.eventPartList) {
      const eventSummary = part.event?.summary || part.event?.title || part.event?.id || part.id || 'Unnamed Event Part';

      if (part.timeslot) {
        let scheduledTimeInfo = "at an unspecified time";
        if (part.timeslot.startTime && part.timeslot.endTime) {
            const dateHint = part.timeslot.monthDay ? `on ${part.timeslot.monthDay}` : ''; // Assuming monthDay is like MM-DD
            // To get a full date for the timeslot, we might need to infer the year or the scheduler needs to provide it.
            // For now, relying on dayOfWeek and monthDay if available.
            let dayInfo = part.timeslot.dayOfWeek || '';
            if (dateHint) {
                dayInfo = dayInfo ? `${dateHint} (${dayInfo})` : dateHint;
            }
            scheduledTimeInfo = `from ${part.timeslot.startTime} to ${part.timeslot.endTime}${dayInfo ? ' ' + dayInfo : ''}`;
        }
        scheduledItems.push(`- '${eventSummary}' scheduled ${scheduledTimeInfo.trim()}`);
      } else {
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
    if (scheduledItems.length === 0 && unscheduledItems.length === 0 && solution.eventPartList.length > 0) {
      notificationMessage += "The scheduling process completed, but detailed outcomes for some items were not clear.\n";
    } else if (solution.eventPartList.length === 0) {
        notificationMessage += "The scheduling process completed, but no events were processed.\n";
    }

    if (solution.score) {
      notificationMessage += `\nOverall schedule score: ${solution.score}`;
    }

    const notificationSent = await sendUserNotification(userId, notificationMessage.trim());

    if (notificationSent) {
      logger.info(`[schedulerCallbackHandler.handleSchedulerCallback] User notification successful for userId: ${userId}, fileKey: ${solution.fileKey}`);
    } else {
      logger.warn(`[schedulerCallbackHandler.handleSchedulerCallback] User notification FAILED for userId: ${userId}, fileKey: ${solution.fileKey}. The scheduling solution was processed, but the user was not notified via Slack.`);
      // TODO: Consider adding this failed notification to a retry queue or alternative notification mechanism in a more robust system.
    }

    // Clean up the pending request from the store after processing, regardless of notification success for this iteration.
    await removePendingRequest(solution.fileKey);
    logger.info(`[schedulerCallbackHandler.handleSchedulerCallback] Processed and cleaned up pending request for fileKey: ${solution.fileKey}`);

    // The message to the scheduler can remain positive if solution processing was okay.
    res.status(200).send({ message: 'Callback processed successfully. User notification attempted.' });

  } catch (processingError: any) {
    logger.error(`[schedulerCallbackHandler.handleSchedulerCallback] Error processing solution for fileKey ${solution.fileKey}:`, processingError.message, processingError.stack);
    // Do not delete from pendingSchedulingRequests here in case of processing error, to allow for retries or investigation.
    res.status(500).send({ error: 'Callback received, but an internal error occurred during solution processing.' });
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
