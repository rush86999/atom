import axios, { AxiosError } from 'axios';
import {
  SkillResponse,
  // Assuming PYTHON_API_SERVICE_BASE_URL will host these GDrive endpoints
} from '../../atomic-docker/project/functions/atom-agent/types';
import { PYTHON_API_SERVICE_BASE_URL } from '../../atomic-docker/project/functions/atom-agent/_libs/constants';
import { logger } from '../../atomic-docker/project/functions/_utils/logger';

const GDRIVE_API_TIMEOUT = 20000; // 20 seconds for listing/triggering, download itself is on backend

// Interface for Google Drive file metadata (subset of what Drive API returns)
export interface GoogleDriveFile {
  id: string;
  name: string;
  mimeType: string;
  modifiedTime?: string; // ISO 8601
  webViewLink?: string;  // Link to view in browser
  parents?: string[];    // List of parent folder IDs
  capabilities?: {
    canDownload?: boolean;
    canExport?: boolean; // For Google Workspace files
  };
  // Add other fields as needed, e.g., iconLink, size, owners
}

import { AuthService } from '../services/authService'; // Adjust path if necessary

// Helper to construct SkillResponse from axios errors (copied from lanceDbStorageSkills.ts for now)
// TODO: Move this to a shared utility file if more skills use it.
function handleAxiosError(error: AxiosError, operationName: string): SkillResponse<null> {
  if (error.response) {
    logger.error(`[${operationName}] Error: ${error.response.status}`, error.response.data);
    const errData = error.response.data as any; // Python returns {ok: false, error: {code, message}}
    return {
      ok: false,
      error: {
        code: errData?.error?.code || `HTTP_${error.response.status}`,
        message: errData?.error?.message || `Failed to ${operationName}. Status: ${error.response.status}`,
        details: errData?.error?.details || errData,
      },
    };
  } else if (error.request) {
    logger.error(`[${operationName}] Error: No response received for ${operationName}`, error.request);
    return {
      ok: false,
      error: { code: 'NETWORK_ERROR', message: `No response received for ${operationName}.` },
    };
  } else {
    logger.error(`[${operationName}] Error setting up request: ${error.message}`);
    return {
      ok: false,
      error: { code: 'REQUEST_SETUP_ERROR', message: `Error setting up request for ${operationName}: ${error.message}` },
    };
  }
}

export async function listGoogleDriveFiles(
  userId: string,
  folderId?: string,
  query?: string, // Search query string
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
    return {
      ok: false,
      error: {
        code: 'AUTH_TOKEN_MISSING',
        message: 'Failed to retrieve Google Drive access token. Please ensure your Google Drive account is connected and authorized.'
      }
    };
  }

  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/gdrive/list-files`;
  const payload = {
    access_token: accessToken,
    folder_id: folderId,
    query: query,
    page_size: pageSize,
    page_token: pageToken,
  };

  logger.info(`[listGoogleDriveFiles] Listing GDrive files. Folder: ${folderId || 'root/all'}, Query: ${query || 'none'}`);

  try {
    const response = await axios.post(endpoint, payload, { timeout: GDRIVE_API_TIMEOUT });
    // Python endpoint returns: {"status": "success/error", "data": {"files": [], "nextPageToken": ...}, "message": ..., "code": ...}
    // We need to map this to SkillResponse: {ok: boolean, data?: T, error?: SkillError}
    if (response.data && response.data.status === "success" && response.data.data) {
      logger.info(`[listGoogleDriveFiles] Successfully listed ${response.data.data.files?.length || 0} GDrive files.`);
      return { ok: true, data: response.data.data };
    } else {
      logger.warn(`[listGoogleDriveFiles] Failed to list GDrive files. API status: ${response.data?.status}`, response.data);
      return {
        ok: false,
        error: {
          code: response.data?.code || 'GDRIVE_LIST_FAILED',
          message: response.data?.message || 'Failed to list Google Drive files via Python API.' ,
          details: response.data?.details
        }
      };
    }
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'listGoogleDriveFiles');
  }
}

export async function triggerGoogleDriveFileIngestion(
  userId: string,
  // accessToken: string, // User's GDrive access token - REMOVED, will fetch via AuthService
  gdriveFileId: string,
  originalFileMetadata: { // Pass essential metadata for processing and context
    name: string;
    mimeType: string;
    webViewLink?: string; // Used as source_uri
  }
): Promise<SkillResponse<{ doc_id: string; num_chunks_stored: number } | null >> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
     return { ok: false, error: { code: 'CONFIG_ERROR', message: 'PYTHON_API_SERVICE_BASE_URL not configured.' }};
  }
  if (!userId) return { ok: false, error: {code: 'VALIDATION_ERROR', message: 'userId is required.'}};
  // No direct accessToken check, will be handled by AuthService call
  if (!gdriveFileId) return { ok: false, error: {code: 'VALIDATION_ERROR', message: 'gdriveFileId is required.'}};
  if (!originalFileMetadata || !originalFileMetadata.name || !originalFileMetadata.mimeType) {
    return { ok: false, error: {code: 'VALIDATION_ERROR', message: 'originalFileMetadata (with name and mimeType) is required.'}};
  }

  const accessToken = await AuthService.getGoogleDriveAccessToken(userId);
  if (!accessToken) {
    return {
      ok: false,
      error: {
        code: 'AUTH_TOKEN_MISSING',
        message: 'Failed to retrieve Google Drive access token for ingestion. Please ensure your Google Drive account is connected and authorized.'
      }
    };
  }

  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/ingest-gdrive-document`;
  const payload = {
    user_id: userId,
    access_token: accessToken,
    gdrive_file_id: gdriveFileId,
    original_file_metadata: originalFileMetadata,
    // openai_api_key: USER_SPECIFIC_KEY_IF_ANY // Optional: pass if embeddings should use a specific key
  };

  logger.info(`[triggerGoogleDriveFileIngestion] Triggering ingestion for GDrive file ID ${gdriveFileId} for user ${userId}`);

  try {
    // Python endpoint returns: {"ok": True/False, "data": ... or "error": ...}
    const response = await axios.post(endpoint, payload, { timeout: GDRIVE_API_TIMEOUT * 2 }); // Longer for download + initial processing call

    if (response.data && response.data.ok && response.data.data) {
      logger.info(`[triggerGoogleDriveFileIngestion] Successfully triggered ingestion for GDrive file ${gdriveFileId}. Doc ID: ${response.data.data.doc_id}`);
      return { ok: true, data: response.data.data };
    } else {
      logger.warn(`[triggerGoogleDriveFileIngestion] Failed. Python API ok: ${response.data?.ok}`, response.data?.error);
      return {
        ok: false,
        error: response.data?.error || {
          code: 'GDRIVE_INGEST_TRIGGER_FAILED',
          message: 'Failed to trigger GDrive file ingestion via Python API.'
        }
      };
    }
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'triggerGoogleDriveFileIngestion');
  }
}
```
