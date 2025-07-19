import axios, { AxiosError } from 'axios';
import {
  SkillResponse,
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

export async function createJiraIssueFromSalesforceCase(
  userId: string,
  salesforceCaseId: string
): Promise<SkillResponse<any>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python API service URL is not configured.' } };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/it/create-jira-issue-from-salesforce-case`;

  try {
    const response = await axios.post(endpoint, {
      user_id: userId,
      salesforce_case_id: salesforceCaseId,
    });
    return handlePythonApiResponse(response, 'createJiraIssueFromSalesforceCase');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'createJiraIssueFromSalesforceCase');
  }
}

export async function getJiraIssueSummary(
    userId: string,
    issueId: string
): Promise<SkillResponse<any>> {
    if (!PYTHON_API_SERVICE_BASE_URL) {
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python API service URL is not configured.' } };
    }
    const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/it/jira-issue-summary/${issueId}?user_id=${userId}`;

    try {
        const response = await axios.get(endpoint);
        return handlePythonApiResponse(response, 'getJiraIssueSummary');
    } catch (error) {
        return handleAxiosError(error as AxiosError, 'getJiraIssueSummary');
    }
}

export async function createTrelloCardFromJiraIssue(
    userId: string,
    issueId: string,
    trelloListId: string
): Promise<SkillResponse<any>> {
    if (!PYTHON_API_SERVICE_BASE_URL) {
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python API service URL is not configured.' } };
    }
    const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/it/create-trello-card-from-jira-issue`;

    try {
        const response = await axios.post(endpoint, {
            user_id: userId,
            issue_id: issueId,
            trello_list_id: trelloListId,
        });
        return handlePythonApiResponse(response, 'createTrelloCardFromJiraIssue');
    } catch (error) {
        return handleAxiosError(error as AxiosError, 'createTrelloCardFromJiraIssue');
    }
}
