import axios, { AxiosError } from 'axios';
import {
  SkillResponse,
} from '../../atomic-docker/project/functions/atom-agent/types';
import { PYTHON_API_SERVICE_BASE_URL } from '../../atomic-docker/project/functions/atom-agent/_libs/constants';
import { logger } from '../../atomic-docker/project/functions/_utils/logger';
import { AuthService } from '../services/authService';

const GDRIVE_API_TIMEOUT = 20000;

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

  const accessToken = await AuthService.getGoogleDriveAccessToken(userId);
  if (!accessToken) {
    return { ok: false, error: { code: 'AUTH_TOKEN_MISSING', message: 'Failed to retrieve Google Drive access token. Please ensure your Google Drive account is connected and authorized.' }};
  }

  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/gdrive/list-files`;
  const payload = { access_token: accessToken, folder_id: folderId, query: query, page_size: pageSize, page_token: pageToken };
  logger.info(`[listGoogleDriveFiles] Listing GDrive files for user ${userId}. Folder: ${folderId || 'root/all'}, Query: ${query || 'none'}`);

  try {
    const response = await axios.post(endpoint, payload, { timeout: GDRIVE_API_TIMEOUT });
    if (response.data && response.data.status === "success" && response.data.data) {
      logger.info(`[listGoogleDriveFiles] Successfully listed ${response.data.data.files?.length || 0} GDrive files for user ${userId}.`);
      return { ok: true, data: response.data.data };
    } else {
      logger.warn(`[listGoogleDriveFiles] Failed for user ${userId}. API status: ${response.data?.status}`, response.data);
      return { ok: false, error: { code: response.data?.code || 'GDRIVE_LIST_FAILED', message: response.data?.message || 'Failed to list GDrive files via Python API.' , details: response.data?.details }};
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

  const accessToken = await AuthService.getGoogleDriveAccessToken(userId);
  if (!accessToken) {
    return { ok: false, error: { code: 'AUTH_TOKEN_MISSING', message: 'Failed to retrieve Google Drive access token. Please connect your Google Drive account.' }};
  }

  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/gdrive/get-file-metadata`;
  const payload: { access_token: string; file_id: string; fields?: string } = {
    access_token: accessToken,
    file_id: fileId
  };
  if (fields) payload.fields = fields;

  logger.info(`[getGoogleDriveFileMetadata] Fetching metadata for GDrive file ID ${fileId} for user ${userId}`);
  try {
    const response = await axios.post(endpoint, payload, { timeout: GDRIVE_API_TIMEOUT });
    if (response.data && response.data.ok && response.data.data) {
      logger.info(`[getGoogleDriveFileMetadata] Successfully fetched metadata for GDrive file ID ${fileId}`);
      return { ok: true, data: response.data.data as GoogleDriveFile };
    } else {
      logger.warn(`[getGoogleDriveFileMetadata] Failed for file ID ${fileId}. API ok: ${response.data?.ok}`, response.data?.error);
      return { ok: false, error: response.data?.error || { code: 'GDRIVE_METADATA_FETCH_FAILED', message: 'Failed to fetch GDrive file metadata.' }};
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

  const accessToken = await AuthService.getGoogleDriveAccessToken(userId);
  if (!accessToken) {
    return { ok: false, error: { code: 'AUTH_TOKEN_MISSING', message: 'Failed to retrieve Google Drive access token for ingestion. Please ensure your Google Drive account is connected and authorized.' }};
  }

  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/ingest-gdrive-document`;
  const payload = {
    user_id: userId, access_token: accessToken, gdrive_file_id: gdriveFileId,
    original_file_metadata: originalFileMetadata,
  };

  logger.info(`[triggerGoogleDriveFileIngestion] Triggering ingestion for GDrive file ID ${gdriveFileId} for user ${userId}`);
  try {
    const response = await axios.post(endpoint, payload, { timeout: GDRIVE_API_TIMEOUT * 2 });
    if (response.data && response.data.ok && response.data.data) {
      logger.info(`[triggerGoogleDriveFileIngestion] Successfully triggered ingestion for GDrive file ${gdriveFileId}. Doc ID: ${response.data.data.doc_id}`);
      return { ok: true, data: response.data.data };
    } else {
      logger.warn(`[triggerGoogleDriveFileIngestion] Failed. Python API ok: ${response.data?.ok}`, response.data?.error);
      return { ok: false, error: response.data?.error || { code: 'GDRIVE_INGEST_TRIGGER_FAILED', message: 'Failed to trigger GDrive file ingestion via Python API.' }};
    }
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'triggerGoogleDriveFileIngestion');
  }
}
```
