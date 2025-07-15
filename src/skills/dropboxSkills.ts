import axios, { AxiosError } from 'axios';
import {
  SkillResponse,
  DropboxConnectionStatusInfo,
  DropboxFile,
  PythonApiResponse
} from '../../atomic-docker/project/functions/atom-agent/types'; // Adjust path
import { PYTHON_API_SERVICE_BASE_URL } from '../../atomic-docker/project/functions/atom-agent/_libs/constants';
import { logger } from '../../atomic-docker/project/functions/_utils/logger';

// Helper to handle Python API responses, can be centralized later
function handlePythonApiResponse<T>(
  response: PythonApiResponse<T>,
  operationName: string
): SkillResponse<T> {
  if (response.ok && response.data !== undefined) {
    return { ok: true, data: response.data };
  }
  logger.warn(`[${operationName}] Failed API call. API ok: ${response.ok}`, response.error);
  return {
    ok: false,
    error: {
      code: response.error?.code || 'PYTHON_API_ERROR',
      message: response.error?.message || `Failed to ${operationName}.`,
      details: response.error?.details,
    },
  };
}

// Helper to handle network/axios errors
function handleAxiosError(error: AxiosError, operationName: string): SkillResponse<null> {
    if (error.response) {
      logger.error(`[${operationName}] Error: ${error.response.status}`, error.response.data);
      const errData = error.response.data as any;
      return { ok: false, error: { code: `HTTP_${error.response.status}`, message: errData?.error?.message || `Failed to ${operationName}.` } };
    } else if (error.request) {
      logger.error(`[${operationName}] Error: No response received`, error.request);
      return { ok: false, error: { code: 'NETWORK_ERROR', message: `No response received for ${operationName}.` } };
    }
    logger.error(`[${operationName}] Error: ${error.message}`);
    return { ok: false, error: { code: 'REQUEST_SETUP_ERROR', message: `Error setting up request for ${operationName}: ${error.message}` } };
}


export async function getDropboxConnectionStatus(
  userId: string
): Promise<SkillResponse<DropboxConnectionStatusInfo>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python API service URL is not configured.' } };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/dropbox/status?user_id=${userId}`;

  try {
    const response = await axios.get<PythonApiResponse<DropboxConnectionStatusInfo>>(endpoint);
    return handlePythonApiResponse(response.data, 'getDropboxConnectionStatus');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'getDropboxConnectionStatus');
  }
}

export async function disconnectDropbox(
  userId: string
): Promise<SkillResponse<{ message: string }>> {
    if (!PYTHON_API_SERVICE_BASE_URL) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python API service URL is not configured.' } };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/dropbox/disconnect`;

  try {
    const response = await axios.post<PythonApiResponse<{ message: string }>>(endpoint, { user_id: userId });
    return handlePythonApiResponse(response.data, 'disconnectDropbox');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'disconnectDropbox');
  }
}

export async function listDropboxFiles(
  userId: string,
  path: string = ''
): Promise<SkillResponse<{ entries: DropboxFile[] }>> {
    if (!PYTHON_API_SERVICE_BASE_URL) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python API service URL is not configured.' } };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/dropbox/list-files`;

  try {
    const response = await axios.post<PythonApiResponse<{ entries: DropboxFile[] }>>(endpoint, {
      user_id: userId,
      path: path,
    });
    return handlePythonApiResponse(response.data, 'listDropboxFiles');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'listDropboxFiles');
  }
}

export async function triggerDropboxFileIngestion(
  userId: string,
  filePath: string, // Corresponds to 'path_lower' from a DropboxFile item
): Promise<SkillResponse<{ doc_id: string; num_chunks_stored: number } | null>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python API service URL is not configured.' } };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/dropbox/ingest-file`;

  try {
    const response = await axios.post<PythonApiResponse<{ doc_id: string; num_chunks_stored: number }>>(endpoint, {
      user_id: userId,
      file_path: filePath,
    });
    return handlePythonApiResponse(response.data, 'triggerDropboxFileIngestion');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'triggerDropboxFileIngestion');
  }
}
