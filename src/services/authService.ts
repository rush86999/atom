import axios, { AxiosError } from 'axios';
// Assuming types.ts path relative to src/services/
import { SkillResponse } from '../../atomic-docker/project/functions/atom-agent/types';
// Assuming constants.ts path relative to src/services/
import { PYTHON_API_SERVICE_BASE_URL } from '../../atomic-docker/project/functions/atom-agent/_libs/constants';
// Assuming logger.ts path relative to src/services/
import { logger } from '../../atomic-docker/project/functions/_utils/logger';

const AUTH_SERVICE_API_TIMEOUT = 10000; // 10 seconds timeout for auth related calls

// Local error handler, similar to helpers in other skill files
// TODO: Consolidate into a shared utility if this pattern is widespread
function handleAuthServiceAxiosError(error: AxiosError, operationName: string): { ok: false; error: SkillResponse<null>['error'] } {
  if (error.response) {
    logger.error(`[AuthService:${operationName}] HTTP Error: ${error.response.status}`, error.response.data);
    const errData = error.response.data as any; // Backend returns {ok: false, error: {code, message}}
    return {
      ok: false,
      error: {
        code: errData?.error?.code || `HTTP_${error.response.status}`,
        message: errData?.error?.message || `Failed to ${operationName}. Status: ${error.response.status}`,
        details: errData?.error?.details || errData,
      },
    };
  } else if (error.request) {
    logger.error(`[AuthService:${operationName}] Network Error: No response received for ${operationName}`, error.request);
    return {
      ok: false,
      error: { code: 'NETWORK_ERROR', message: `No response received for ${operationName}.` },
    };
  } else {
    logger.error(`[AuthService:${operationName}] Request Setup Error: ${error.message}`);
    return {
      ok: false,
      error: { code: 'REQUEST_SETUP_ERROR', message: `Error setting up request for ${operationName}: ${error.message}` },
    };
  }
}


/**
 * Retrieves a valid Google Drive access token for the given user.
 * Calls a secure backend endpoint that handles token storage and refresh logic.
 * @param userId The ID of the user for whom to retrieve the token.
 * @returns A promise that resolves to the access token string if successful, or null if not.
 */
async function getGoogleDriveAccessToken(userId: string): Promise<string | null> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    logger.error("[AuthService:getGoogleDriveAccessToken] PYTHON_API_SERVICE_BASE_URL is not configured.");
    return null;
  }
  if (!userId || userId.trim() === "") {
    logger.warn("[AuthService:getGoogleDriveAccessToken] userId is required and cannot be empty.");
    return null;
  }

  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/auth/gdrive/get-access-token`;

  try {
    logger.info(`[AuthService:getGoogleDriveAccessToken] Requesting GDrive access token for user ${userId}`);

    const response = await axios.get<{ ok: boolean; data?: { access_token: string }; error?: any }>(
      endpoint,
      {
        params: { user_id: userId }, // Python endpoint expects user_id as query param
        timeout: AUTH_SERVICE_API_TIMEOUT,
        // Headers for internal service authentication might be needed here if the Python endpoint is protected
        // e.g., headers: { 'X-Internal-Service-Key': 'INTERNAL_SECRET_KEY' }
      }
    );

    if (response.data && response.data.ok && response.data.data?.access_token) {
      logger.info(`[AuthService:getGoogleDriveAccessToken] Successfully retrieved GDrive access token for user ${userId}`);
      return response.data.data.access_token;
    } else {
      const errorMsg = response.data?.error?.message || 'Failed to retrieve GDrive access token from backend.';
      const errorCode = response.data?.error?.code || 'TOKEN_RETRIEVAL_FAILED';
      logger.warn(`[AuthService:getGoogleDriveAccessToken] Failed for user ${userId}. Code: ${errorCode}, Msg: ${errorMsg}`, response.data?.error?.details);
      return null;
    }
  } catch (error) {
    const axiosErr = error as AxiosError;
    const errResponse = handleAuthServiceAxiosError(axiosErr, 'getGoogleDriveAccessToken');
    logger.error(`[AuthService:getGoogleDriveAccessToken] Exception for user ${userId}: ${errResponse.error?.message}`, errResponse.error?.details);
    return null;
  }
}

/**
 * Constructs the URL to initiate the Google Drive OAuth flow.
 * This URL points to the backend endpoint that starts the OAuth dance with Google.
 * @param userId The Atom user ID to associate with the OAuth flow (will be passed in 'state').
 * @returns The URL string or null if configuration is missing.
 */
function getGoogleDriveAuthInitiateUrl(userId: string): string | null {
    if (!PYTHON_API_SERVICE_BASE_URL) {
        logger.error("[AuthService:getGoogleDriveAuthInitiateUrl] PYTHON_API_SERVICE_BASE_URL is not configured.");
        return null;
    }
    if (!userId || userId.trim() === "") {
        logger.warn("[AuthService:getGoogleDriveAuthInitiateUrl] userId is required and cannot be empty.");
        return null;
    }
    // This URL should point to the backend endpoint that starts the OAuth dance
    return `${PYTHON_API_SERVICE_BASE_URL}/api/auth/gdrive/initiate?user_id=${encodeURIComponent(userId)}`;
}


export const AuthService = {
  getGoogleDriveAccessToken,
  getGoogleDriveAuthInitiateUrl,
};
