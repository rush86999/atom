import { SkillResponse, DropboxConnectionStatusInfo, DropboxFile } from '../../atomic-docker/project/functions/atom-agent/types';
export declare function getDropboxConnectionStatus(userId: string): Promise<SkillResponse<DropboxConnectionStatusInfo>>;
export declare function disconnectDropbox(userId: string): Promise<SkillResponse<{
    message: string;
}>>;
export declare function listDropboxFiles(userId: string, path?: string): Promise<SkillResponse<{
    entries: DropboxFile[];
}>>;
