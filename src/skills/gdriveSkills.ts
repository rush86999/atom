import axios, { AxiosError } from 'axios';
import {
  SkillResponse,
} from '../../atomic-docker/project/functions/atom-agent/types';
import { PYTHON_API_SERVICE_BASE_URL } from '../../atomic-docker/project/functions/atom-agent/_libs/constants';
import { logger } from '../../atomic-docker/project/functions/_utils/logger';

const GDRIVE_API_TIMEOUT = 20000; // Default for most GDrive ops
const GDRIVE_STATUS_TIMEOUT = 5000; // Shorter for status checks
const GDRIVE_DISCONNECT_TIMEOUT = 10000;

// Interface for GDrive Connection Status
export interface GDriveConnectionStatusInfo {
  isConnected: boolean;
  email?: string;
  reason?: string;
}

// Updated Interface for Google Drive file metadata
export interface GoogleDriveFile {
  id: string;
  name: string;
  mimeType: string;
  modifiedTime?: string; // ISO 8601 string from Drive API
  webViewLink?: string;
  parents?: string[];
  capabilities?: {
    canDownload?: boolean;
    canExport?: boolean;
  };
  exportLinks?: Record<string, string>; // e.g., { "application/pdf": "...", "text/html": "..." }
  shortcutDetails?: {
    targetId: string;
    targetMimeType?: string;
  };
  // Fields added by our gdrive_service when a shortcut is resolved:
  is_shortcut_to?: {
    shortcutId: string;
    shortcutName?: string;
    shortcutWebViewLink?: string;
  };
  original_shortcut_id_if_applicable?: string;
}

// Helper to construct SkillResponse from axios errors
function handleAxiosError(error: AxiosError, operationName: string): SkillResponse<null> {
  if (error.response) {
    logger.error(`[gdriveSkills:${operationName}] Error: ${error.response.status}`, error.response.data);
    const errData = error.response.data as any;
    return {
      ok: false,
      error: {
        code: errData?.error?.code || `HTTP_${error.response.status}`,
        message: errData?.error?.message || `Failed to ${operationName}. Status: ${error.response.status}`,
        details: errData?.error?.details || errData,
      },
    };
  } else if (error.request) {
    logger.error(`[gdriveSkills:${operationName}] Error: No response received for ${operationName}`, error.request);
    return { ok: false, error: { code: 'NETWORK_ERROR', message: `No response received for ${operationName}.` } };
  } else {
    logger.error(`[gdriveSkills:${operationName}] Error setting up request: ${error.message}`);
    return { ok: false, error: { code: 'REQUEST_SETUP_ERROR', message: `Error setting up request for ${operationName}: ${error.message}` } };
  }
}

export async function listGoogleDriveFiles(
  userId: string,
  folderId?: string,
  query?: string,
  pageSize: number = 50,
  pageToken?: string
): Promise<SkillResponse<{ files: GoogleDriveFile[]; nextPageToken?: string }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'PYTHON_API_SERVICE_BASE_URL not configured.' }};
  }
  if (!userId) {
    return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'userId is required to list Google Drive files.' }};
  }

  // No longer directly fetching access_token here; backend will handle it.
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/gdrive/list-files`;
  const payload = {
    user_id: userId, // Send user_id instead of access_token
    folder_id: folderId,
    query: query,
    page_size: pageSize,
    page_token: pageToken
  };
  logger.info(`[listGoogleDriveFiles] Listing GDrive files for user ${userId}. Folder: ${folderId || 'root/all'}, Query: ${query || 'none'}`);

  try {
    // Python endpoint now returns SkillResponse-like structure directly
    const response = await axios.post<SkillResponse<{ files: GoogleDriveFile[]; nextPageToken?: string }>>(endpoint, payload, { timeout: GDRIVE_API_TIMEOUT });

    if (response.data && response.data.ok && response.data.data) {
      logger.info(`[listGoogleDriveFiles] Successfully listed ${response.data.data.files?.length || 0} GDrive files for user ${userId}.`);
      return { ok: true, data: response.data.data };
    } else if (response.data && !response.data.ok && response.data.error) {
      logger.warn(`[listGoogleDriveFiles] Failed for user ${userId}. API Error:`, response.data.error);
      return { ok: false, error: response.data.error };
    } else {
      // Fallback for unexpected response structure
      logger.warn(`[listGoogleDriveFiles] Failed for user ${userId}. Unexpected response structure.`, response.data);
      return { ok: false, error: { code: 'UNEXPECTED_RESPONSE', message: 'Unexpected response from GDrive list files API.' }};
    }
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'listGoogleDriveFiles');
  }
}

export async function getGoogleDriveFileMetadata(
  userId: string,
  fileId: string,
  fields?: string // Optional fields string for the API
): Promise<SkillResponse<GoogleDriveFile>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'PYTHON_API_SERVICE_BASE_URL not configured.' }};
  }
  if (!userId) return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'userId is required.' }};
  if (!fileId) return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'fileId is required.' }};

  // No longer directly fetching access_token here.
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/gdrive/get-file-metadata`;
  const payload: { user_id: string; file_id: string; fields?: string } = { // user_id instead of access_token
    user_id: userId,
    file_id: fileId
  };
  if (fields) payload.fields = fields;

  logger.info(`[getGoogleDriveFileMetadata] Fetching metadata for GDrive file ID ${fileId} for user ${userId}`);
  try {
    const response = await axios.post<SkillResponse<GoogleDriveFile>>(endpoint, payload, { timeout: GDRIVE_API_TIMEOUT });
    if (response.data && response.data.ok && response.data.data) {
      logger.info(`[getGoogleDriveFileMetadata] Successfully fetched metadata for GDrive file ID ${fileId}`);
      return { ok: true, data: response.data.data };
    } else if (response.data && !response.data.ok && response.data.error) {
      logger.warn(`[getGoogleDriveFileMetadata] Failed for file ID ${fileId}. API Error:`, response.data.error);
      return { ok: false, error: response.data.error };
    } else {
      logger.warn(`[getGoogleDriveFileMetadata] Failed for file ID ${fileId}. Unexpected response.`, response.data);
      return { ok: false, error: { code: 'UNEXPECTED_RESPONSE', message: 'Unexpected response from GDrive get metadata API.' }};
    }
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'getGoogleDriveFileMetadata');
  }
}

export async function triggerGoogleDriveFileIngestion(
  userId: string,
  gdriveFileId: string,
  originalFileMetadata: {
    name: string;
    mimeType: string;
    webViewLink?: string;
  }
): Promise<SkillResponse<{ doc_id: string; num_chunks_stored: number } | null >> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
     return { ok: false, error: { code: 'CONFIG_ERROR', message: 'PYTHON_API_SERVICE_BASE_URL not configured.' }};
  }
  if (!userId) return { ok: false, error: {code: 'VALIDATION_ERROR', message: 'userId is required.'}};
  if (!gdriveFileId) return { ok: false, error: {code: 'VALIDATION_ERROR', message: 'gdriveFileId is required.'}};
  if (!originalFileMetadata || !originalFileMetadata.name || !originalFileMetadata.mimeType) {
    return { ok: false, error: {code: 'VALIDATION_ERROR', message: 'originalFileMetadata (with name and mimeType) is required.'}};
  }

  // No longer directly fetching access_token here.
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/ingest-gdrive-document`;
  const payload = { // user_id instead of access_token
    user_id: userId,
    gdrive_file_id: gdriveFileId,
    original_file_metadata: originalFileMetadata,
  };

  logger.info(`[triggerGoogleDriveFileIngestion] Triggering ingestion for GDrive file ID ${gdriveFileId} for user ${userId}`);
  try {
    const response = await axios.post<SkillResponse<{ doc_id: string; num_chunks_stored: number } | null >>(endpoint, payload, { timeout: GDRIVE_API_TIMEOUT * 2 });
    if (response.data && response.data.ok && response.data.data) {
      logger.info(`[triggerGoogleDriveFileIngestion] Successfully triggered ingestion for GDrive file ${gdriveFileId}. Doc ID: ${response.data.data.doc_id}`);
      return { ok: true, data: response.data.data };
    } else if (response.data && !response.data.ok && response.data.error) {
      logger.warn(`[triggerGoogleDriveFileIngestion] Failed. API Error:`, response.data.error);
      return { ok: false, error: response.data.error };
    } else {
      logger.warn(`[triggerGoogleDriveFileIngestion] Failed. Unexpected response.`, response.data);
      return { ok: false, error: { code: 'UNEXPECTED_RESPONSE', message: 'Unexpected response from GDrive trigger ingestion API.' }};
    }
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'triggerGoogleDriveFileIngestion');
  }
}

// --- New functions for GDrive Connection Management ---

export async function getGDriveConnectionStatus(userId: string): Promise<SkillResponse<GDriveConnectionStatusInfo>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'PYTHON_API_SERVICE_BASE_URL not configured.' }};
  }
  if (!userId) return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'userId is required.' }};

  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/gdrive/connection-status?user_id=${userId}`;
  logger.info(`[getGDriveConnectionStatus] Checking GDrive connection status for user ${userId}`);

  try {
    const response = await axios.get<SkillResponse<GDriveConnectionStatusInfo>>(endpoint, { timeout: GDRIVE_STATUS_TIMEOUT });
    if (response.data && response.data.ok && typeof response.data.data?.isConnected === 'boolean') {
      logger.info(`[getGDriveConnectionStatus] Status for user ${userId}: Connected - ${response.data.data.isConnected}, Email - ${response.data.data.email}`);
      return { ok: true, data: response.data.data };
    } else if (response.data && !response.data.ok && response.data.error) {
      logger.warn(`[getGDriveConnectionStatus] Failed. API Error:`, response.data.error);
      return { ok: false, error: response.data.error };
    } else {
      logger.warn(`[getGDriveConnectionStatus] Failed. Unexpected response.`, response.data);
      return { ok: false, error: { code: 'UNEXPECTED_RESPONSE', message: 'Unexpected response from GDrive connection status API.' }};
    }
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'getGDriveConnectionStatus');
  }
}

export async function disconnectGDrive(userId: string): Promise<SkillResponse<{ message: string }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'PYTHON_API_SERVICE_BASE_URL not configured.' }};
  }
  if (!userId) return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'userId is required.' }};

  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/auth/gdrive/disconnect`;
  const payload = { user_id: userId };
  logger.info(`[disconnectGDrive] Disconnecting GDrive for user ${userId}`);

  try {
    const response = await axios.post<SkillResponse<{ message: string }>>(endpoint, payload, { timeout: GDRIVE_DISCONNECT_TIMEOUT });
    if (response.data && response.data.ok) {
      logger.info(`[disconnectGDrive] Successfully disconnected GDrive for user ${userId}. Message: ${response.data.message}`);
      return { ok: true, data: { message: response.data.message || "Successfully disconnected." }, message: response.data.message };
    } else if (response.data && !response.data.ok && response.data.error) {
      logger.warn(`[disconnectGDrive] Failed. API Error:`, response.data.error);
      return { ok: false, error: response.data.error };
    } else {
      logger.warn(`[disconnectGDrive] Failed. Unexpected response.`, response.data);
      return { ok: false, error: { code: 'UNEXPECTED_RESPONSE', message: 'Unexpected response from GDrive disconnect API.' }};
    }
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'disconnectGDrive');
  }
}

```
