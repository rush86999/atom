// atomic-docker/project/functions/atom-agent/sharedAgentState.ts

// For storing information about pending scheduling requests
export interface PendingRequestInfo {
  userId: string; // Agent's internal userId who made the original request
  hostId: string; // hostId sent to the scheduler
  fileKey: string; // fileKey sent to the scheduler, used for callback correlation
  singletonId: string; // singletonId sent to the scheduler
  originalQuery?: string; // Optional: the user's original natural language query
  submittedAt: Date;
  // Potentially add callbackUrl here if it can vary per request, though currently it's fixed
}

// In-memory store for pending requests. Maps fileKey to PendingRequestInfo.
// TODO: Replace with a persistent store (e.g., Redis, Database) for production.
export const pendingSchedulingRequests = new Map<string, PendingRequestInfo>();

// (Could add other shared state here in the future if needed)
