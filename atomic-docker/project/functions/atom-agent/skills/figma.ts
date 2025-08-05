import axios from 'axios';
import {
  SkillResponse,
  FigmaFile,
  FigmaNode,
  FigmaComments,
  FigmaProject,
  PythonApiResponse,
} from '../types';
import { PYTHON_API_SERVICE_BASE_URL } from '../_libs/constants';
import { logger } from '../_utils/logger';

// Helper to handle Python API responses
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

// Figma API helpers
export async function handleListFigmaFiles(
  userId: string,
  params?: { project_id?: string }
): Promise<SkillResponse<{ files: FigmaFile[] }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }

  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/figma/files`;
  const queryParams = new URLSearchParams({ user_id: userId });

  if (params?.project_id) {
    queryParams.append('project_id', params.project_id);
  }

  try {
    const response =
      await axios.get<PythonApiResponse<{ files: FigmaFile[] }>>(
        `${endpoint}?${queryParams}`
      );
    return handlePythonApiResponse(response.data, 'handleListFigmaFiles');
  } catch (error: any) {
    logger.error('Figma files fetch failed:', error);
    return {
      ok: false,
      error: {
        code: 'FIGMA_API_ERROR',
        message: `Failed to fetch Figma files: ${error.message}`,
      },
    };
  }
}

export async function handleGetFigmaFile(
  userId: string,
  fileId: string
): Promise<SkillResponse<FigmaFile>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }

  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/figma/files/${fileId}?user_id=${userId}`;

  try {
    const response = await axios.get<PythonApiResponse<FigmaFile>>(endpoint);
    return handlePythonApiResponse(response.data, 'handleGetFigmaFile');
  } catch (error: any) {
    logger.error('Figma file fetch failed:', error);
    return {
      ok: false,
      error: {
        code: 'FIGMA_API_ERROR',
        message: `Failed to fetch Figma file: ${error.message}`,
      },
    };
  }
}

export async function handleListFigmaProjects(
  userId: string
): Promise<SkillResponse<{ projects: FigmaProject[] }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }

  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/figma/projects?user_id=${userId}`;

  try {
    const response =
      await axios.get<PythonApiResponse<{ projects: FigmaProject[] }>>(endpoint);
    return handlePythonApiResponse(response.data, 'handleListFigmaProjects');
  } catch (error: any) {
    logger.error('Figma projects fetch failed:', error);
    return {
      ok: false,
      error: {
        code: 'FIGMA_API_ERROR',
        message: `Failed to fetch Figma projects: ${error.message}`,
      },
    };
  }
}

export async function handleGetFigmaComments(
  userId: string,
  fileId: string
): Promise<SkillResponse<FigmaComments>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }

  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/figma/files/${fileId}/comments?user_id=${userId}`;

  try {
    const response = await axios.get<PythonApiResponse<FigmaComments>>(endpoint);
    return handlePythonApiResponse(response.data, 'handleGetFigmaComments');
  } catch (error: any) {
    logger.error('Figma comments fetch failed:', error);
    return {
      ok: false,
      error: {
        code: 'FIGMA_API_ERROR',
        message: `Failed to fetch Figma comments: ${error.message}`,
      },
    };
  }
}

export async function handleCreateFigmaComment(
  userId: string,
  fileId: string,
  comment: string
): Promise<SkillResponse<{ comment_id: string }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }

  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/figma/files/${fileId}/comments`;

  try {
    const response = await axios.post<PythonApiResponse<{ comment_id: string }>>(
      endpoint,
      { user_id: userId, comment: comment }
    );
    return handlePythonApiResponse(response.data, 'handleCreateFigmaComment');
  } catch (error: any) {
    logger.error('Figma comment creation failed:', error);
    return {
      ok: false,
      error: {
        code: 'FIGMA_API_ERROR',
        message: `Failed to create Figma comment: ${error.message}`,
      },
    };
  }
}

export async function handleExportFigmaFile(
  userId: string,
  fileId: string,
  format: 'png' | 'svg' | 'pdf',
  scale?: number
): Promise<SkillResponse<{ download_url: string }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }

  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/figma/files/${fileId}/export`;
  const params = new URLSearchParams({
    user_id: userId,
    format,
    scale: scale?.toString() || '1'
  });

  try {
    const response = await axios.post<PythonApiResponse<{ download_url: string }>>(
      `${endpoint}?${params}`
    );
    return handlePythonApiResponse(response.data, 'handleExportFigmaFile');
  } catch (error: any) {
    logger.error('Figma export failed:', error);
    return {
      ok: false,
      error: {
        code: 'FIGMA_API_ERROR',
        message: `Failed to export Figma file: ${error.message}`,
      },
    };
  }
}
