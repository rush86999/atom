import { GetDailyPriorityBriefingNluEntities, GetDailyPriorityBriefingSkillResponse } from '../types';
/**
 * Generates a daily priority briefing for the user, consolidating information
 * from tasks, meetings, and potentially urgent messages.
 *
 * @param userId The ID of the user requesting the briefing.
 * @param nluEntities The parsed NLU entities from the GetDailyPriorityBriefing intent.
 * @returns A promise that resolves to GetDailyPriorityBriefingSkillResponse.
 */
export declare function generateDailyBriefing(userId: string, nluEntities: GetDailyPriorityBriefingNluEntities): Promise<GetDailyPriorityBriefingSkillResponse>;
