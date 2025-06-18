// Assuming a logger is available or can be imported/passed
// For now, using console for simplicity within this file.
const logger = {
  info: console.log,
  warn: console.warn,
  error: console.error,
};

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
import { pendingSchedulingRequests, PendingRequestInfo } from '../sharedAgentState';

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

// --- Placeholder User Notification Function ---
async function sendUserNotification(userId: string, message: string): Promise<void> {
  logger.info(`[sendUserNotification] Attempting to notify userId: ${userId}`);
  logger.info(`[sendUserNotification] Message: "${message}"`);
  // In a real implementation, this would call Slack, email, or other notification services.
  // For example: await sendSlackMessage(userId, userId, message); // Assuming sendSlackMessage is available
  // For now, we just log it.
  // Simulate a slight delay as if a real notification was sent.
  await new Promise(resolve => setTimeout(resolve, 100));
  logger.info(`[sendUserNotification] Notification for userId ${userId} (simulated) complete.`);
}


// --- Main Callback Handler Function ---
export async function handleSchedulerCallback(req: Request, res: Response): Promise<void> {
  logger.info('[schedulerCallbackHandler.handleSchedulerCallback] Received a callback request.');

  if (!req.body) {
    logger.warn('[schedulerCallbackHandler.handleSchedulerCallback] Callback request body is empty.');
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

  const requestContext = pendingSchedulingRequests.get(solution.fileKey);

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

    await sendUserNotification(userId, notificationMessage.trim());

    pendingSchedulingRequests.delete(solution.fileKey);
    logger.info(`[schedulerCallbackHandler.handleSchedulerCallback] Processed and cleaned up pending request for fileKey: ${solution.fileKey}`);

    res.status(200).send({ message: 'Callback processed successfully. User has been notified.' });

  } catch (processingError: any) {
    logger.error(`[schedulerCallbackHandler.handleSchedulerCallback] Error processing solution for fileKey ${solution.fileKey}:`, processingError.message, processingError.stack);
    // Do not delete from pendingSchedulingRequests here, as it might be a temporary processing error.
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
