import axios, { AxiosError } from 'axios';
import {
  SkillResponse,
  XeroInvoice,
  XeroBill,
  XeroContact
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

export async function listXeroInvoices(
  userId: string
): Promise<SkillResponse<{ invoices: XeroInvoice[] }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python API service URL is not configured.' } };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/xero/invoices?user_id=${userId}`;

  try {
    const response = await axios.get(endpoint);
    return handlePythonApiResponse(response, 'listXeroInvoices');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'listXeroInvoices');
  }
}

export async function listXeroBills(
  userId: string
): Promise<SkillResponse<{ bills: XeroBill[] }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python API service URL is not configured.' } };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/xero/bills?user_id=${userId}`;

  try {
    const response = await axios.get(endpoint);
    return handlePythonApiResponse(response, 'listXeroBills');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'listXeroBills');
  }
}

export async function listXeroContacts(
  userId: string
): Promise<SkillResponse<{ contacts: XeroContact[] }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python API service URL is not configured.' } };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/xero/contacts?user_id=${userId}`;

  try {
    const response = await axios.get(endpoint);
    return handlePythonApiResponse(response, 'listXeroContacts');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'listXeroContacts');
  }
}

export async function createXeroInvoice(
  userId: string,
  contactId: string,
  lineItems: any[], // Simplified for example
  type: 'ACCREC' | 'ACCPAY' = 'ACCREC'
): Promise<SkillResponse<XeroInvoice>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python API service URL is not configured.' } };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/xero/invoices`;

  try {
    const response = await axios.post(endpoint, {
      user_id: userId,
      Contact: { ContactID: contactId },
      LineItems: lineItems,
      Type: type,
      Status: 'DRAFT'
    });
    return handlePythonApiResponse(response, 'createXeroInvoice');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'createXeroInvoice');
  }
}

export async function createXeroBill(
    userId: string,
    contactId: string,
    lineItems: any[], // Simplified for example
    type: 'ACCREC' | 'ACCPAY' = 'ACCPAY'
  ): Promise<SkillResponse<XeroBill>> {
    if (!PYTHON_API_SERVICE_BASE_URL) {
      return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python API service URL is not configured.' } };
    }
    const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/xero/bills`;

    try {
      const response = await axios.post(endpoint, {
        user_id: userId,
        Contact: { ContactID: contactId },
        LineItems: lineItems,
        Type: type,
        Status: 'DRAFT'
      });
      return handlePythonApiResponse(response, 'createXeroBill');
    } catch (error) {
      return handleAxiosError(error as AxiosError, 'createXeroBill');
    }
  }

export async function createXeroContact(
  userId: string,
  name: string,
  email?: string
): Promise<SkillResponse<XeroContact>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python API service URL is not configured.' } };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/xero/contacts`;

  try {
    const response = await axios.post(endpoint, {
      user_id: userId,
      Name: name,
      EmailAddress: email,
    });
    return handlePythonApiResponse(response, 'createXeroContact');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'createXeroContact');
  }
}

export async function updateXeroContact(
  userId: string,
  contactId: string,
  fields: Partial<XeroContact>
): Promise<SkillResponse<XeroContact>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python API service URL is not configured.' } };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/xero/contacts/${contactId}`;

  try {
    const response = await axios.put(endpoint, {
      user_id: userId,
      ...fields,
    });
    return handlePythonApiResponse(response, 'updateXeroContact');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'updateXeroContact');
  }
}

export async function getXeroContact(
  userId: string,
  contactId: string
): Promise<SkillResponse<XeroContact>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python API service URL is not configured.' } };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/xero/contacts/${contactId}?user_id=${userId}`;

  try {
    const response = await axios.get(endpoint);
    return handlePythonApiResponse(response, 'getXeroContact');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'getXeroContact');
  }
}
