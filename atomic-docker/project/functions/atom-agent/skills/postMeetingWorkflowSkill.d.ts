import { ProcessMeetingOutcomesNluEntities, ProcessMeetingOutcomesSkillResponse } from '../types';
/**
 * Orchestrates the processing of meeting outcomes based on NLU entities.
 * This includes fetching meeting content, extracting insights, and performing requested actions.
 *
 * @param userId The ID of the user requesting the actions.
 * @param nluEntities The parsed NLU entities from the ProcessMeetingOutcomes intent.
 * @returns A promise that resolves to ProcessMeetingOutcomesSkillResponse containing results of actions.
 */
export declare function executePostMeetingActions(userId: string, nluEntities: ProcessMeetingOutcomesNluEntities): Promise<ProcessMeetingOutcomesSkillResponse>;
