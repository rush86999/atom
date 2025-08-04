import { SkillResponse } from '../../atomic-docker/project/functions/atom-agent/types';
export declare function searchBox(userId: string, query: string): Promise<SkillResponse<any>>;
export declare function listBoxFiles(userId: string, folderId?: string): Promise<SkillResponse<any>>;
