import axios, { AxiosError } from 'axios';
import {
  SkillResponse,
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

export async function searchTrello(
    userId: string,
    boardId: string,
    query: string
    ): Promise<SkillResponse<any>> {
    if (!PYTHON_API_SERVICE_BASE_URL) {
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python API service URL is not configured.' } };
    }
    const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/trello/search`;

    try {
        const response = await axios.post<PythonApiResponse<any>>(endpoint, {
        user_id: userId,
        board_id: boardId,
        query: query,
        });
        return handlePythonApiResponse(response.data, 'searchTrello');
    } catch (error) {
        return handleAxiosError(error as AxiosError, 'searchTrello');
    }
}

export async function listTrelloCards(
    userId: string,
    boardId: string
    ): Promise<SkillResponse<any>> {
    if (!PYTHON_API_SERVICE_BASE_URL) {
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python API service URL is not configured.' } };
    }
    const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/trello/list-cards`;

    try {
        const response = await axios.post<PythonApiResponse<any>>(endpoint, {
        user_id: userId,
        board_id: boardId,
        });
        return handlePythonApiResponse(response.data, 'listTrelloCards');
    } catch (error) {
        return handleAxiosError(error as AxiosError, 'listTrelloCards');
    }
}
