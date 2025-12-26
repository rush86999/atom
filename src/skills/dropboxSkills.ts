import axios from 'axios';
// Type definitions
export interface SkillResponse<T> {
  ok: boolean;
  data?: T;
  message?: string;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
}

export interface PythonApiResponse<T> {
  ok: boolean;
  data?: T;
  message?: string;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
}

export interface DropboxConnectionStatusInfo {
  isConnected: boolean;
  reason?: string;
}

export interface DropboxFile {
  ".tag": string;
  name: string;
  path_display: string;
  id: string;
}

// Configuration
const PYTHON_API_SERVICE_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Simple logger
const logger = {
  warn: (message: string, error?: any) => console.warn(message, error),
  error: (message: string, error?: any) => console.error(message, error),
  info: (message: string, data?: any) => console.log(message, data),
};

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
// Helper to handle network/axios errors
function handleAxiosError<T>(
  error: any,
  operationName: string
): SkillResponse<T> {
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
    } as SkillResponse<T>;
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
    } as SkillResponse<T>;
  }
  logger.error(`[${operationName}] Error: ${error.message}`);
  return {
    ok: false,
    error: {
      code: 'REQUEST_SETUP_ERROR',
      message: `Error setting up request for ${operationName}: ${error.message}`,
    },
  } as SkillResponse<T>;
}

export async function getDropboxConnectionStatus(
  userId: string
): Promise<SkillResponse<DropboxConnectionStatusInfo>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/dropbox/status?user_id=${userId}`;

  try {
    const response =
      await axios.get<PythonApiResponse<DropboxConnectionStatusInfo>>(endpoint);
    return handlePythonApiResponse(response.data, 'getDropboxConnectionStatus');
  } catch (error) {
    return handleAxiosError<DropboxConnectionStatusInfo>(error, 'getDropboxConnectionStatus');
  }
}

export async function disconnectDropbox(
  userId: string
): Promise<SkillResponse<{ message: string }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/dropbox/disconnect`;

  try {
    const response = await axios.post<PythonApiResponse<{ message: string }>>(
      endpoint,
      { user_id: userId }
    );
    return handlePythonApiResponse(response.data, 'disconnectDropbox');
  } catch (error) {
    return handleAxiosError<{ message: string }>(error, 'disconnectDropbox');
  }
}

export async function listDropboxFiles(
  userId: string,
  path: string = ''
): Promise<SkillResponse<{ entries: DropboxFile[] }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/dropbox/list-files`;

  try {
    const response = await axios.post<
      PythonApiResponse<{ entries: DropboxFile[] }>
    >(endpoint, {
      user_id: userId,
      path: path,
    });
    return handlePythonApiResponse(response.data, 'listDropboxFiles');
  } catch (error) {
    return handleAxiosError<{ entries: DropboxFile[] }>(error, 'listDropboxFiles');
  }
}
