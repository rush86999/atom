import axios, { AxiosError } from 'axios';
import {
  SkillResponse,
  PythonApiResponse,
} from '../../atomic-docker/project/functions/atom-agent/types'; // Adjust path
import { PYTHON_API_SERVICE_BASE_URL } from '../../atomic-docker/project/functions/atom-agent/_libs/constants';
import { logger } from '../../atomic-docker/project/functions/_utils/logger';
import { decrypt } from 'atomic-docker/project/functions/_libs/crypto';
import { executeGraphQLQuery } from 'atomic-docker/project/functions/atom-agent/_libs/graphqlClient';

// Helper to handle Python API responses, can be centralized later
function handlePythonApiResponse<T>(
  response: PythonApiResponse<T>,
  operationName: string
): SkillResponse<T> {
  if (response.ok && response.data !== undefined) {
    return { ok: true, data: response.data };
  }
  logger.warn(
    `[${operationName}] Failed API call. API ok: ${response.ok}`,
    response.error
  );
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
function handleAxiosError(
  error: AxiosError,
  operationName: string
): SkillResponse<null> {
  if (error.response) {
    logger.error(
      `[${operationName}] Error: ${error.response.status}`,
      error.response.data
    );
    const errData = error.response.data as any;
    return {
      ok: false,
      error: {
        code: `HTTP_${error.response.status}`,
        message: errData?.error?.message || `Failed to ${operationName}.`,
      },
    };
  } else if (error.request) {
    logger.error(
      `[${operationName}] Error: No response received`,
      error.request
    );
    return {
      ok: false,
      error: {
        code: 'NETWORK_ERROR',
        message: `No response received for ${operationName}.`,
      },
    };
  }
  logger.error(`[${operationName}] Error: ${error.message}`);
  return {
    ok: false,
    error: {
      code: 'REQUEST_SETUP_ERROR',
      message: `Error setting up request for ${operationName}: ${error.message}`,
    },
  };
}

export async function getJiraAccessToken(userId: string): Promise<string | null> {
    const query = `
        query GetUserToken($userId: String!, $service: String!) {
            user_tokens(where: {user_id: {_eq: $userId}, service: {_eq: $service}}) {
                encrypted_access_token
            }
        }
    `;
    const variables = {
        userId,
        service: 'jira',
    };
    const response = await executeGraphQLQuery<{
        user_tokens: { encrypted_access_token: string }[];
    }>(query, variables, 'GetUserToken', userId);
    if (response.user_tokens && response.user_tokens.length > 0) {
        return decrypt(response.user_tokens[0].encrypted_access_token);
    }
    return null;
}

export async function searchJira(
  userId: string,
  projectId: string,
  query: string
): Promise<SkillResponse<any>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/jira/search`;

  try {
    const response = await axios.post<PythonApiResponse<any>>(endpoint, {
      user_id: userId,
      project_id: projectId,
      query: query,
    });
    return handlePythonApiResponse(response.data, 'searchJira');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'searchJira');
  }
}

export async function listJiraIssues(
  userId: string,
  projectId: string
): Promise<SkillResponse<any>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/jira/list-issues`;

  try {
    const response = await axios.post<PythonApiResponse<any>>(endpoint, {
      user_id: userId,
      project_id: projectId,
    });
    return handlePythonApiResponse(response.data, 'listJiraIssues');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'listJiraIssues');
  }
}

export async function listJiraProjects(userId: string): Promise<SkillResponse<any>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/jira/list-projects`;

  try {
    const response = await axios.post<PythonApiResponse<any>>(endpoint, {
      user_id: userId,
    });
    return handlePythonApiResponse(response.data, 'listJiraProjects');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'listJiraProjects');
  }
}

export async function createJiraIssue(
  userId: string,
  projectId: string,
  summary: string,
  description: string
): Promise<SkillResponse<any>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/jira/create-issue`;

  try {
    const response = await axios.post<PythonApiResponse<any>>(endpoint, {
      user_id: userId,
      project_id: projectId,
      summary: summary,
      description: description,
    });
    return handlePythonApiResponse(response.data, 'createJiraIssue');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'createJiraIssue');
  }
}
