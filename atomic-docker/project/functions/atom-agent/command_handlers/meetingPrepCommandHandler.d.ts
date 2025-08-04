import { MeetingPrepNluEntities } from '../types';
/**
 * Handles the "RequestMeetingPreparation" intent.
 * Calls the meeting preparation skill and formats the results for the user.
 *
 * @param userId The ID of the user.
 * @param entities The NLU entities extracted for the RequestMeetingPreparation intent.
 * @returns A promise that resolves to a user-facing string response.
 */
export declare function handleMeetingPreparationRequest(userId: string, entities: MeetingPrepNluEntities): Promise<string>;
