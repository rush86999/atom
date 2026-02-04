import axios, { AxiosError } from 'axios';
import {
  SkillResponse,
  SalesforceContact,
  SalesforceAccount,
  SalesforceOpportunity,
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

export async function listSalesforceContacts(
  userId: string
): Promise<SkillResponse<{ contacts: SalesforceContact[] }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/salesforce/contacts?user_id=${userId}`;

  try {
    const response = await axios.get(endpoint);
    return handlePythonApiResponse(response, 'listSalesforceContacts');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'listSalesforceContacts');
  }
}

export async function listSalesforceAccounts(
  userId: string
): Promise<SkillResponse<{ accounts: SalesforceAccount[] }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/salesforce/accounts?user_id=${userId}`;

  try {
    const response = await axios.get(endpoint);
    return handlePythonApiResponse(response, 'listSalesforceAccounts');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'listSalesforceAccounts');
  }
}

export async function listSalesforceOpportunities(
  userId: string
): Promise<SkillResponse<{ opportunities: SalesforceOpportunity[] }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/salesforce/opportunities?user_id=${userId}`;

  try {
    const response = await axios.get(endpoint);
    return handlePythonApiResponse(response, 'listSalesforceOpportunities');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'listSalesforceOpportunities');
  }
}

export async function createSalesforceContact(
  userId: string,
  lastName: string,
  firstName?: string,
  email?: string
): Promise<SkillResponse<SalesforceContact>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/salesforce/contacts`;

  try {
    const response = await axios.post(endpoint, {
      user_id: userId,
      LastName: lastName,
      FirstName: firstName,
      Email: email,
    });
    return handlePythonApiResponse(response, 'createSalesforceContact');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'createSalesforceContact');
  }
}

export async function createSalesforceAccount(
  userId: string,
  name: string
): Promise<SkillResponse<SalesforceAccount>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/salesforce/accounts`;

  try {
    const response = await axios.post(endpoint, {
      user_id: userId,
      Name: name,
    });
    return handlePythonApiResponse(response, 'createSalesforceAccount');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'createSalesforceAccount');
  }
}

export async function createSalesforceOpportunity(
  userId: string,
  name: string,
  stageName: string,
  closeDate: string,
  amount?: number
): Promise<SkillResponse<SalesforceOpportunity>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/salesforce/opportunities`;

  try {
    const response = await axios.post(endpoint, {
      user_id: userId,
      Name: name,
      StageName: stageName,
      CloseDate: closeDate,
      Amount: amount,
    });
    return handlePythonApiResponse(response, 'createSalesforceOpportunity');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'createSalesforceOpportunity');
  }
}

export async function updateSalesforceOpportunity(
  userId: string,
  opportunityId: string,
  fields: Partial<SalesforceOpportunity>
): Promise<SkillResponse<SalesforceOpportunity>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/salesforce/opportunities/${opportunityId}`;

  try {
    const response = await axios.put(endpoint, {
      user_id: userId,
      ...fields,
    });
    return handlePythonApiResponse(response, 'updateSalesforceOpportunity');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'updateSalesforceOpportunity');
  }
}

export async function getSalesforceOpportunity(
  userId: string,
  opportunityId: string
): Promise<SkillResponse<SalesforceOpportunity>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/salesforce/opportunities/${opportunityId}?user_id=${userId}`;

  try {
    const response = await axios.get(endpoint);
    return handlePythonApiResponse(response, 'getSalesforceOpportunity');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'getSalesforceOpportunity');
  }
}
