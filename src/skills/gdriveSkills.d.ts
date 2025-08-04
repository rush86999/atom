import { SkillResponse } from '../../atomic-docker/project/functions/atom-agent/types';
export interface GDriveConnectionStatusInfo {
    isConnected: boolean;
    email?: string;
    reason?: string;
}
export interface GoogleDriveFile {
    id: string;
    name: string;
    mimeType: string;
    modifiedTime?: string;
    webViewLink?: string;
    parents?: string[];
    capabilities?: {
        canDownload?: boolean;
        canExport?: boolean;
    };
    exportLinks?: Record<string, string>;
    shortcutDetails?: {
        targetId: string;
        targetMimeType?: string;
    };
    is_shortcut_to?: {
        shortcutId: string;
        shortcutName?: string;
        shortcutWebViewLink?: string;
    };
    original_shortcut_id_if_applicable?: string;
}
export declare function listGoogleDriveFiles(userId: string, folderId?: string, query?: string, pageSize?: number, pageToken?: string): Promise<SkillResponse<{
    files: GoogleDriveFile[];
    nextPageToken?: string;
}>>;
export declare function getGoogleDriveFileMetadata(userId: string, fileId: string, fields?: string): Promise<SkillResponse<GoogleDriveFile>>;
export declare function triggerGoogleDriveFileIngestion(userId: string, gdriveFileId: string, originalFileMetadata: {
    name: string;
    mimeType: string;
    webViewLink?: string;
}): Promise<SkillResponse<{
    doc_id: string;
    num_chunks_stored: number;
} | null>>;
export declare function getGDriveConnectionStatus(userId: string): Promise<SkillResponse<GDriveConnectionStatusInfo>>;
export declare function disconnectGDrive(userId: string): Promise<SkillResponse<{
    message: string;
}>>;
