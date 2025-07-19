import axios, { AxiosError } from 'axios';
import {
  SkillResponse,
  TrelloBoard,
  TrelloList,
  TrelloCard
} from '../../atomic-docker/project/functions/atom-agent/types'; // Adjust path
import { PYTHON_API_SERVICE_BASE_URL } from '../../atomic-docker/project/functions/atom-agent/_libs/constants';
import { logger } from '../../atomic-docker/project/functions/_utils/logger';

// Helper to handle Python API responses, can be centralized later
function handlePythonApiResponse<T>(
  response: any, // Adjust type as per actual Python API response structure
  operationName: string
): SkillResponse<T> {
  if (response.data && response.data.ok && response.data.data) {
    return { ok: true, data: response.data.data };
  }
  logger.warn(`[${operationName}] Failed API call.`, response.data?.error);
  return {
    ok: false,
    error: {
      code: response.data?.error?.code || 'PYTHON_API_ERROR',
      message: response.data?.error?.message || `Failed to ${operationName}.`,
      details: response.data?.error?.details,
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

export async function listTrelloBoards(
  userId: string
): Promise<SkillResponse<{ boards: TrelloBoard[] }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python API service URL is not configured.' } };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/trello/boards?user_id=${userId}`;

  try {
    const response = await axios.get(endpoint);
    return handlePythonApiResponse(response, 'listTrelloBoards');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'listTrelloBoards');
  }
}

export async function listTrelloLists(
  userId: string,
  boardId: string
): Promise<SkillResponse<{ lists: TrelloList[] }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python API service URL is not configured.' } };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/trello/lists?user_id=${userId}&board_id=${boardId}`;

  try {
    const response = await axios.get(endpoint);
    return handlePythonApiResponse(response, 'listTrelloLists');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'listTrelloLists');
  }
}

export async function listTrelloCards(
  userId: string,
  listId: string
): Promise<SkillResponse<{ cards: TrelloCard[] }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python API service URL is not configured.' } };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/trello/cards?user_id=${userId}&list_id=${listId}`;

  try {
    const response = await axios.get(endpoint);
    return handlePythonApiResponse(response, 'listTrelloCards');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'listTrelloCards');
  }
}

export async function createTrelloCard(
  userId: string,
  listId: string,
  name: string,
  desc?: string
): Promise<SkillResponse<TrelloCard>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python API service URL is not configured.' } };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/trello/cards`;

  try {
    const response = await axios.post(endpoint, {
      user_id: userId,
      list_id: listId,
      name,
      desc,
    });
    return handlePythonApiResponse(response, 'createTrelloCard');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'createTrelloCard');
  }
}

export async function moveTrelloCard(
  userId: string,
  cardId: string,
  newListId: string
): Promise<SkillResponse<TrelloCard>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python API service URL is not configured.' } };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/trello/cards/${cardId}/move`;

  try {
    const response = await axios.put(endpoint, {
      user_id: userId,
      list_id: newListId,
    });
    return handlePythonApiResponse(response, 'moveTrelloCard');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'moveTrelloCard');
  }
}
