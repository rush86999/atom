import { SkillResponse } from '../../atomic-docker/project/functions/atom-agent/types';
export declare function searchTrello(userId: string, boardId: string, query: string): Promise<SkillResponse<any>>;
export declare function listTrelloCards(userId: string, boardId: string): Promise<SkillResponse<any>>;
