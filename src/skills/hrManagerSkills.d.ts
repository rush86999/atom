import { SkillResponse } from '../../atomic-docker/project/functions/atom-agent/types';
export declare function createBambooHREmployeeFromGreenhouseCandidate(userId: string, greenhouseCandidateId: string): Promise<SkillResponse<any>>;
export declare function getBambooHREmployeeSummary(userId: string, employeeId: string): Promise<SkillResponse<any>>;
export declare function createTrelloCardFromBambooHREmployee(userId: string, employeeId: string, trelloListId: string): Promise<SkillResponse<any>>;
