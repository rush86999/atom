import { GetDailyPriorityBriefingNluEntities } from '../types';
/**
 * Handles the "GetDailyPriorityBriefing" intent.
 * Calls the daily briefing skill and formats the results into a structured
 * message object for the frontend to render with a custom component.
 *
 * @param userId The ID of the user.
 * @param entities The NLU entities extracted for the GetDailyPriorityBriefing intent.
 * @returns A promise that resolves to a message object for the client, or a simple string on error.
 */
export declare function handleGetDailyBriefingRequest(userId: string, entities: GetDailyPriorityBriefingNluEntities): Promise<any>;
