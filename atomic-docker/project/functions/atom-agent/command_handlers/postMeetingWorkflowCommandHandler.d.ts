import { ProcessMeetingOutcomesNluEntities } from '../types';
/**
 * Handles the "ProcessMeetingOutcomes" intent.
 * Calls the post-meeting workflow skill and formats the results for the user.
 *
 * @param userId The ID of the user.
 * @param entities The NLU entities extracted for the ProcessMeetingOutcomes intent.
 * @returns A promise that resolves to a user-facing string response.
 */
export declare function handleProcessMeetingOutcomesRequest(userId: string, entities: ProcessMeetingOutcomesNluEntities): Promise<string>;
