import axios, { AxiosError } from "axios";

// Type definitions
interface SkillResponse<T> {
  ok: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
}

interface PythonApiResponse<T> {
  ok: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
}

// Configuration
const PYTHON_API_SERVICE_BASE_URL =
  process.env.PYTHON_API_SERVICE_BASE_URL || "http://localhost:5058";

// Simple logger
const logger = {
  warn: (message: string, error?: any) => console.warn(message, error),
  error: (message: string, error?: any) => console.error(message, error),
};

// Helper to handle Python API responses
function handlePythonApiResponse<T>(
  response: PythonApiResponse<T>,
  operationName: string,
): SkillResponse<T> {
  if (response.ok && response.data !== undefined) {
    return { ok: true, data: response.data };
  }
  logger.warn(
    `[${operationName}] Failed API call. API ok: ${response.ok}`,
    response.error,
  );
  return {
    ok: false,
    error: {
      code: response.error?.code || "PYTHON_API_ERROR",
      message: response.error?.message || `Failed to ${operationName}.`,
      details: response.error?.details,
    },
  };
}

// Helper to handle network/axios errors
function handleAxiosError(
  error: AxiosError,
  operationName: string,
): SkillResponse<null> {
  if (error.response) {
    logger.error(
      `[${operationName}] Error: ${error.response.status}`,
      error.response.data,
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
      error.request,
    );
    return {
      ok: false,
      error: {
        code: "NETWORK_ERROR",
        message: `No response received for ${operationName}.`,
      },
    };
  }
  logger.error(`[${operationName}] Error: ${error.message}`);
  return {
    ok: false,
    error: {
      code: "REQUEST_SETUP_ERROR",
      message: `Error setting up request for ${operationName}: ${error.message}`,
    },
  };
}

export async function searchAsana(
  userId: string,
  projectId: string,
  query: string,
): Promise<SkillResponse<any>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: "CONFIG_ERROR",
        message: "Python API service URL is not configured.",
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/asana/search`;

  try {
    const response = await axios.post<PythonApiResponse<any>>(endpoint, {
      user_id: userId,
      project_id: projectId,
      query: query,
    });
    return handlePythonApiResponse(response.data, "searchAsana");
  } catch (error) {
    return handleAxiosError(error as AxiosError, "searchAsana");
  }
}

export async function listAsanaTasks(
  userId: string,
  projectId: string,
): Promise<SkillResponse<any>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: "CONFIG_ERROR",
        message: "Python API service URL is not configured.",
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/asana/list-tasks`;

  try {
    const response = await axios.post<PythonApiResponse<any>>(endpoint, {
      user_id: userId,
      project_id: projectId,
    });
    return handlePythonApiResponse(response.data, "listAsanaTasks");
  } catch (error) {
    return handleAxiosError(error as AxiosError, "listAsanaTasks");
  }
}

export async function getAsanaProjects(
  userId: string,
  workspaceId?: string,
  limit: number = 100,
  offset?: string,
): Promise<SkillResponse<any>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: "CONFIG_ERROR",
        message: "Python API service URL is not configured.",
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/asana/projects`;

  try {
    const response = await axios.post<PythonApiResponse<any>>(endpoint, {
      user_id: userId,
      workspace_id: workspaceId,
      limit: limit,
      offset: offset,
    });
    return handlePythonApiResponse(response.data, "getAsanaProjects");
  } catch (error) {
    return handleAxiosError(error as AxiosError, "getAsanaProjects");
  }
}

export async function getAsanaSections(
  userId: string,
  projectId: string,
  limit: number = 100,
  offset?: string,
): Promise<SkillResponse<any>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: "CONFIG_ERROR",
        message: "Python API service URL is not configured.",
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/asana/sections`;

  try {
    const response = await axios.post<PythonApiResponse<any>>(endpoint, {
      user_id: userId,
      project_id: projectId,
      limit: limit,
      offset: offset,
    });
    return handlePythonApiResponse(response.data, "getAsanaSections");
  } catch (error) {
    return handleAxiosError(error as AxiosError, "getAsanaSections");
  }
}

export async function getAsanaTeams(
  userId: string,
  workspaceId: string,
  limit: number = 100,
  offset?: string,
): Promise<SkillResponse<any>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: "CONFIG_ERROR",
        message: "Python API service URL is not configured.",
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/asana/teams`;

  try {
    const response = await axios.post<PythonApiResponse<any>>(endpoint, {
      user_id: userId,
      workspace_id: workspaceId,
      limit: limit,
      offset: offset,
    });
    return handlePythonApiResponse(response.data, "getAsanaTeams");
  } catch (error) {
    return handleAxiosError(error as AxiosError, "getAsanaTeams");
  }
}

export async function getAsanaUsers(
  userId: string,
  workspaceId: string,
  limit: number = 100,
  offset?: string,
): Promise<SkillResponse<any>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: "CONFIG_ERROR",
        message: "Python API service URL is not configured.",
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/asana/users`;

  try {
    const response = await axios.post<PythonApiResponse<any>>(endpoint, {
      user_id: userId,
      workspace_id: workspaceId,
      limit: limit,
      offset: offset,
    });
    return handlePythonApiResponse(response.data, "getAsanaUsers");
  } catch (error) {
    return handleAxiosError(error as AxiosError, "getAsanaUsers");
  }
}

export async function getAsanaUserProfile(
  userId: string,
  targetUserId: string = "me",
): Promise<SkillResponse<any>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: "CONFIG_ERROR",
        message: "Python API service URL is not configured.",
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/asana/user-profile`;

  try {
    const response = await axios.post<PythonApiResponse<any>>(endpoint, {
      user_id: userId,
      target_user_id: targetUserId,
    });
    return handlePythonApiResponse(response.data, "getAsanaUserProfile");
  } catch (error) {
    return handleAxiosError(error as AxiosError, "getAsanaUserProfile");
  }
}

export async function createAsanaTask(
  userId: string,
  projectId: string,
  name: string,
  notes: string = "",
  dueOn?: string,
  assignee?: string,
): Promise<SkillResponse<any>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: "CONFIG_ERROR",
        message: "Python API service URL is not configured.",
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/asana/create-task`;

  try {
    const response = await axios.post<PythonApiResponse<any>>(endpoint, {
      user_id: userId,
      project_id: projectId,
      name: name,
      notes: notes,
      due_on: dueOn,
      assignee: assignee,
    });
    return handlePythonApiResponse(response.data, "createAsanaTask");
  } catch (error) {
    return handleAxiosError(error as AxiosError, "createAsanaTask");
  }
}

export async function updateAsanaTask(
  userId: string,
  taskId: string,
  name?: string,
  notes?: string,
  dueOn?: string,
  completed?: boolean,
): Promise<SkillResponse<any>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: "CONFIG_ERROR",
        message: "Python API service URL is not configured.",
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/asana/update-task`;

  try {
    const response = await axios.post<PythonApiResponse<any>>(endpoint, {
      user_id: userId,
      task_id: taskId,
      name: name,
      notes: notes,
      due_on: dueOn,
      completed: completed,
    });
    return handlePythonApiResponse(response.data, "updateAsanaTask");
  } catch (error) {
    return handleAxiosError(error as AxiosError, "updateAsanaTask");
  }
}
