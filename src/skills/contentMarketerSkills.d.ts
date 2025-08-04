import { SkillResponse } from '../../atomic-docker/project/functions/atom-agent/types';
export declare function createWordPressPostFromGoogleDriveDocument(userId: string, googleDriveDocumentId: string): Promise<SkillResponse<any>>;
export declare function getWordPressPostSummary(userId: string, postId: string): Promise<SkillResponse<any>>;
export declare function createTrelloCardFromWordPressPost(userId: string, postId: string, trelloListId: string): Promise<SkillResponse<any>>;
