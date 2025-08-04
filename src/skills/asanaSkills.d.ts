import { SkillResponse } from '../../atomic-docker/project/functions/atom-agent/types';
export declare function searchAsana(userId: string, projectId: string, query: string): Promise<SkillResponse<any>>;
export declare function listAsanaTasks(userId: string, projectId: string): Promise<SkillResponse<any>>;
