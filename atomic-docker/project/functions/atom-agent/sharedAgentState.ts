// atomic-docker/project/functions/atom-agent/sharedAgentState.ts

// Import dbService functions
import {
  addPendingJob,
  getPendingJob,
  deletePendingJob,
  // updatePendingJobStatus, // Optional: if we want to expose status updates via sharedAgentState
} from '../_utils/dbService'; // Adjust path as needed if _utils is elsewhere

// For storing information about pending scheduling requests
// This interface defines the structure of the data passed around in the application logic.
// The dbService will handle mapping this to/from the database schema.
export interface PendingRequestInfo {
  fileKey: string;
  userId: string; // Agent's internal userId who made the original request
  hostId: string; // hostId sent to the scheduler
  singletonId: string; // singletonId sent to the scheduler
  originalQuery?: string; // Optional: the user's original natural language query
  submittedAt: Date;
  // status?: string; // Status is managed in the DB layer, not typically part of this app-level info object
  // when initially storing. It's more of a DB column.
}

// Using console for logging within this file if no central logger is passed around.
const logger = {
  info: console.log,
  error: console.error,
  warn: console.warn,
};

// The in-memory map is now removed. Logic is delegated to dbService.

export async function storePendingRequest(
  jobInfo: PendingRequestInfo
): Promise<void> {
  logger.info(
    `[sharedAgentState.storePendingRequest] Storing job with fileKey: ${jobInfo.fileKey}`
  );
  try {
    // The addPendingJob function in dbService expects a PendingRequestInfo object
    // that aligns with the DB schema (e.g., submittedAt should be Date or ISO string).
    // The status is handled by dbService internally (defaults to 'PENDING').
    await addPendingJob(jobInfo);
    logger.info(
      `[sharedAgentState.storePendingRequest] Successfully stored job with fileKey: ${jobInfo.fileKey}`
    );
  } catch (error) {
    logger.error(
      `[sharedAgentState.storePendingRequest] Error storing job with fileKey ${jobInfo.fileKey}:`,
      error
    );
    // Re-throw or handle as appropriate for the application's error handling strategy
    throw error;
  }
}

export async function retrievePendingRequest(
  fileKey: string
): Promise<PendingRequestInfo | null> {
  logger.info(
    `[sharedAgentState.retrievePendingRequest] Retrieving job with fileKey: ${fileKey}`
  );
  try {
    // getPendingJob from dbService returns PendingRequestInfo | null
    // and specifically fetches jobs with status = 'PENDING'.
    const jobInfo = await getPendingJob(fileKey);
    if (jobInfo) {
      logger.info(
        `[sharedAgentState.retrievePendingRequest] Successfully retrieved job with fileKey: ${fileKey}`
      );
    } else {
      logger.info(
        `[sharedAgentState.retrievePendingRequest] No 'PENDING' job found with fileKey: ${fileKey}`
      );
    }
    return jobInfo;
  } catch (error) {
    logger.error(
      `[sharedAgentState.retrievePendingRequest] Error retrieving job with fileKey ${fileKey}:`,
      error
    );
    throw error;
  }
}

export async function removePendingRequest(fileKey: string): Promise<void> {
  logger.info(
    `[sharedAgentState.removePendingRequest] Removing job with fileKey: ${fileKey}`
  );
  try {
    await deletePendingJob(fileKey);
    // deletePendingJob in dbService already logs success/failure to delete.
    // No specific success confirmation needed here unless different logic is required.
  } catch (error) {
    logger.error(
      `[sharedAgentState.removePendingRequest] Error removing job with fileKey ${fileKey}:`,
      error
    );
    throw error;
  }
}

// Optional: Expose status update if needed by application logic directly through sharedAgentState
// import { updatePendingJobStatus as dbUpdateStatus } from '../_utils/dbService'; // Alias if needed
// export async function updateStatusForPendingRequest(fileKey: string, status: string): Promise<void> {
//   logger.info(`[sharedAgentState.updateStatusForPendingRequest] Updating status to '${status}' for fileKey: ${fileKey}`);
//   try {
//     await dbUpdateStatus(fileKey, status);
//   } catch (error) {
//     logger.error(`[sharedAgentState.updateStatusForPendingRequest] Error updating status for fileKey ${fileKey}:`, error);
//     throw error;
//   }
// }

// (Could add other shared state management functions here in the future if needed)
