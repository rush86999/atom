import { SkillResponse } from '../../atomic-docker/project/functions/atom-agent/types';
export declare function createGreenhouseCandidateFromLinkedInProfile(userId: string, linkedInProfileUrl: string): Promise<SkillResponse<any>>;
export declare function getGreenhouseCandidateSummary(userId: string, candidateId: string): Promise<SkillResponse<any>>;
export declare function createTrelloCardFromGreenhouseCandidate(userId: string, candidateId: string, trelloListId: string): Promise<SkillResponse<any>>;
