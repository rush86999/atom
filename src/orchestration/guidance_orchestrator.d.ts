import { EnrichedIntent } from '../nlu_agents/nlu_types';
import { LearningAndGuidanceResult } from '../skills/learningAndGuidanceSkill';
export interface OrchestratorResponse {
    messageToUser: string;
    guidanceResult?: LearningAndGuidanceResult;
    enrichedIntent?: EnrichedIntent;
}
/**
 * Processes a user query for learning and guidance,
 * first using NLULeadAgent, then potentially LearningAndGuidanceSkill.
 */
export declare function processGuidanceRequest(originalQuery: string, userId: string, applicationContext?: string): Promise<OrchestratorResponse>;
