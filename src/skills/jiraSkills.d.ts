import { SkillResponse } from '../../atomic-docker/project/functions/atom-agent/types';
export declare function searchJira(userId: string, projectId: string, query: string): Promise<SkillResponse<any>>;
export declare function listJiraIssues(userId: string, projectId: string): Promise<SkillResponse<any>>;
