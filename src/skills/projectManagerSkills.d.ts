import { SkillResponse, GoogleDriveFile, TrelloBoard } from '../../atomic-docker/project/functions/atom-agent/types';
export declare function createGoogleDriveFolderFromTrelloBoard(userId: string, boardId: string): Promise<SkillResponse<GoogleDriveFile>>;
export declare function uploadTrelloAttachmentsToGoogleDrive(userId: string, cardId: string, folderId: string): Promise<SkillResponse<any>>;
export declare function createTrelloBoardFromGoogleDriveFolder(userId: string, folderId: string): Promise<SkillResponse<TrelloBoard>>;
export declare function createTrelloCardForNewFileInGoogleDrive(userId: string, folderId: string, trelloListId: string): Promise<SkillResponse<any>>;
