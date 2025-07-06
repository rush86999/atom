import axios, { AxiosError } from 'axios';
import {
  SkillResponse,
  SkillError,
  PythonApiResponse,
  InitiateResearchData,
  ProcessResearchQueueData,
  CreateNoteData,
  NotionSearchResultData,
  NotionSimilarNoteResult, // Added this missing type
  // New Task Management Types
  CreateNotionTaskParams,
  QueryNotionTasksParams,
  TaskQueryResponse, // Used directly by queryNotionTasks
  UpdateNotionTaskParams,
  CreateTaskData,    // For SkillResponse<CreateTaskData>
  UpdateTaskData,    // For SkillResponse<UpdateTaskData>
  NotionTask,        // For TaskQueryResponse.tasks and PythonApiResponse<NotionTask[]>
  NotionPageSummary, // Added for getNotionPageSummaryById
} from '../types';
import { logger } from '../../_utils/logger'; // Added logger
import {
  PYTHON_RESEARCH_API_URL,
  PYTHON_NOTE_API_URL,
  ATOM_NOTION_TASKS_DATABASE_ID, // Added for default tasks DB
  NOTION_API_TOKEN,
  NOTION_NOTES_DATABASE_ID, // Default general notes DB
  NOTION_RESEARCH_PROJECTS_DB_ID,
  NOTION_RESEARCH_TASKS_DB_ID,
  ATOM_SERPAPI_API_KEY, // Search API Key for research tasks
  OPENAI_API_KEY,       // OpenAI API Key for research tasks (decomposition, synthesis)
  DEEPGRAM_API_KEY,     // Deepgram API Key for audio notes
} from '../_libs/constants';

// --- Helper for handling Python API responses ---
function handlePythonApiResponse<T>(
  pythonResponse: PythonApiResponse<T>,
  serviceName: string = 'Python API'
): SkillResponse<T> {
  if (pythonResponse.ok && pythonResponse.data !== undefined) {
    return { ok: true, data: pythonResponse.data };
  } else if (pythonResponse.error) {
    console.error(`${serviceName} error:`, pythonResponse.error);
    return {
      ok: false,
      error: {
        code: pythonResponse.error.code || 'PYTHON_SERVICE_ERROR',
        message: pythonResponse.error.message || `Unknown error from ${serviceName}.`,
        details: pythonResponse.error.details,
      },
    };
  }
  return {
    ok: false,
    error: {
      code: 'PYTHON_UNEXPECTED_RESPONSE',
      message: `Unexpected response structure from ${serviceName}.`,
      details: pythonResponse,
    },
  };
}


// --- Research Skills ---

export async function initiateResearch(
  userId: string, // Though not directly used by Python's initiate_research_project, useful for context/future
  topic: string
): Promise<SkillResponse<InitiateResearchData>> {
  if (!PYTHON_RESEARCH_API_URL) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python Research API URL is not configured.' } };
  if (!NOTION_API_TOKEN) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion API token is not configured.' } };
  if (!OPENAI_API_KEY) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'OpenAI API key is not configured.' } };
  if (!NOTION_RESEARCH_PROJECTS_DB_ID) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion Research Projects DB ID is not configured.' } };
  if (!NOTION_RESEARCH_TASKS_DB_ID) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion Research Tasks DB ID is not configured.' } };

  try {
    const payload = {
      topic: topic,
      user_id: userId, // Pass userId to Python service
      research_db_id: NOTION_RESEARCH_PROJECTS_DB_ID,
      task_db_id: NOTION_RESEARCH_TASKS_DB_ID,
      notion_api_token: NOTION_API_TOKEN,
      openai_api_key: OPENAI_API_KEY,
    };
    const response = await axios.post<PythonApiResponse<InitiateResearchData>>(
      `${PYTHON_RESEARCH_API_URL}/initiate-research`,
      payload
    );
    return handlePythonApiResponse(response.data, 'ResearchInitiation');
  } catch (error: any) {
    const axiosError = error as AxiosError;
    return {
      ok: false,
      error: {
        code: axiosError.isAxiosError ? `HTTP_${axiosError.response?.status || 'NETWORK_ERROR'}` : 'SKILL_INTERNAL_ERROR',
        message: `Failed to initiate research: ${axiosError.message}`,
        details: axiosError.response?.data || axiosError.message,
      },
    };
  }
}

// --- Notion Task Management Skills ---

export async function createNotionTask(
  userId: string, // For logging and consistency
  params: CreateNotionTaskParams
): Promise<SkillResponse<CreateTaskData>> {
  if (!PYTHON_NOTE_API_URL) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python Note API URL is not configured.' } };
  if (!NOTION_API_TOKEN) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion API token is not configured.' } };
  if (!params.notionTasksDbId && !ATOM_NOTION_TASKS_DATABASE_ID) {
      return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion Tasks Database ID is not configured.'}};
  }

  try {
    const payload = {
      ...params, // description, dueDate, status, priority, listName, notes
      user_id: userId,
      notion_api_token: NOTION_API_TOKEN,
      notion_db_id: params.notionTasksDbId || ATOM_NOTION_TASKS_DATABASE_ID
    };

    const response = await axios.post<PythonApiResponse<CreateTaskData>>(
      `${PYTHON_NOTE_API_URL}/create-notion-task`,
      payload
    );
    return handlePythonApiResponse(response.data, 'CreateNotionTask');
  } catch (error: any) {
    const axiosError = error as AxiosError;
    return {
      ok: false,
      error: {
        code: axiosError.isAxiosError ? `HTTP_${axiosError.response?.status || 'NETWORK_ERROR'}` : 'SKILL_INTERNAL_ERROR',
        message: `Failed to create Notion task: ${axiosError.message}`,
        details: axiosError.response?.data || axiosError.message,
      },
    };
  }
}

export async function queryNotionTasks(
  userId: string,
  params: QueryNotionTasksParams
): Promise<TaskQueryResponse> { // Direct use of TaskQueryResponse
  if (!PYTHON_NOTE_API_URL) return { success: false, tasks: [], error: 'Python Note API URL is not configured.', message: 'Configuration error.' };
  if (!NOTION_API_TOKEN) return { success: false, tasks: [], error: 'Notion API token is not configured.', message: 'Configuration error.' };
  if (!params.notionTasksDbId && !ATOM_NOTION_TASKS_DATABASE_ID) {
      return { success: false, tasks: [], error: 'Notion Tasks Database ID is not configured.', message: 'Configuration error.'};
  }

  try {
    const payload = {
      ...params,
      user_id: userId, // Include userId for consistency, Python backend may or may not use it for filtering
      notion_api_token: NOTION_API_TOKEN,
      notion_db_id: params.notionTasksDbId || ATOM_NOTION_TASKS_DATABASE_ID
    };

    const response = await axios.post<PythonApiResponse<NotionTask[]>>(
      `${PYTHON_NOTE_API_URL}/query-notion-tasks`,
      payload
    );

    if (response.data.ok && response.data.data) {
        return { success: true, tasks: response.data.data, message: response.data.message || 'Tasks queried successfully.' };
    } else if (response.data.error) {
        return { success: false, tasks: [], error: response.data.error.message, message: response.data.error.details as string|undefined };
    }
    return { success: false, tasks: [], error: 'Unexpected response from queryNotionTasks backend.', message: 'Backend communication error.'};

  } catch (error: any) {
    const axiosError = error as AxiosError;
    console.error(`Failed to query Notion tasks: ${axiosError.message}`, axiosError.response?.data || axiosError.message);
    return {
      success: false,
      tasks: [],
      error: `Failed to query Notion tasks: ${axiosError.message}`,
    };
  }
}

export async function updateNotionTask(
  userId: string,
  params: UpdateNotionTaskParams
): Promise<SkillResponse<UpdateTaskData>> {
  if (!PYTHON_NOTE_API_URL) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python Note API URL is not configured.' } };
  if (!NOTION_API_TOKEN) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion API token is not configured.' } };
  if (!params.taskId) return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Task ID (taskId) is required for update.' }};

  try {
    const payload = {
      ...params,
      user_id: userId,
      notion_api_token: NOTION_API_TOKEN
    };

    const response = await axios.post<PythonApiResponse<UpdateTaskData>>(
      `${PYTHON_NOTE_API_URL}/update-notion-task`,
      payload
    );
    return handlePythonApiResponse(response.data, 'UpdateNotionTask');
  } catch (error: any) {
    const axiosError = error as AxiosError;
    return {
      ok: false,
      error: {
        code: axiosError.isAxiosError ? `HTTP_${axiosError.response?.status || 'NETWORK_ERROR'}` : 'SKILL_INTERNAL_ERROR',
        message: `Failed to update Notion task: ${axiosError.message}`,
        details: axiosError.response?.data || axiosError.message,
      },
    };
  }
}

/**
 * Searches for Notion notes similar to a given query text using vector similarity.
 *
 * @param userId The ID of the user performing the search (to scope results).
 * @param queryText The natural language text to search for.
 * @param limit Optional. The maximum number of similar notes to return.
 * @returns A promise that resolves to a SkillResponse containing an array of similar Notion notes.
 */
export async function searchSimilarNotionNotes(
  userId: string,
  queryText: string,
  limit?: number
): Promise<SkillResponse<NotionSimilarNoteResult[]>> {
  if (!PYTHON_NOTE_API_URL) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python Note API URL is not configured.' } };
  }
  if (!OPENAI_API_KEY) { // OpenAI API key is needed by the Python endpoint for embedding the query
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'OpenAI API key is not configured for similarity search.' } };
  }
  if (!userId) { // user_id is crucial for filtering results in LanceDB
      return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'User ID is required for searching similar notes.'}};
  }
   if (!queryText || queryText.trim() === "") {
    return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Query text cannot be empty for similarity search.' } };
  }

  try {
    const payload = {
      query_text: queryText,
      user_id: userId,
      openai_api_key: OPENAI_API_KEY, // Python service will use this to embed the query_text
      limit: limit || 5, // Default to 5 if not provided
    };

    const response = await axios.post<PythonApiResponse<NotionSimilarNoteResult[]>>(
      `${PYTHON_NOTE_API_URL}/search-similar-notes`,
      payload
    );
    return handlePythonApiResponse(response.data, 'SearchSimilarNotionNotes');
  } catch (error: any) {
    const axiosError = error as AxiosError;
    return {
      ok: false,
      error: {
        code: axiosError.isAxiosError ? `HTTP_${axiosError.response?.status || 'NETWORK_ERROR'}` : 'SKILL_INTERNAL_ERROR',
        message: `Failed to search for similar Notion notes: ${axiosError.message}`,
        details: axiosError.response?.data || axiosError.message,
      },
    };
  }
}

export async function processResearchQueue(
  userId: string // Contextual, Python service doesn't strictly need it if keys are global there
): Promise<SkillResponse<ProcessResearchQueueData>> {
  if (!PYTHON_RESEARCH_API_URL) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python Research API URL is not configured.' } };
  if (!NOTION_API_TOKEN) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion API token is not configured.' } };
  if (!OPENAI_API_KEY) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'OpenAI API key is not configured.' } };
  if (!ATOM_SERPAPI_API_KEY) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'SerpApi API key is not configured.' } };
  if (!NOTION_RESEARCH_PROJECTS_DB_ID) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion Research Projects DB ID is not configured.' } };
  if (!NOTION_RESEARCH_TASKS_DB_ID) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion Research Tasks DB ID is not configured.' } };

  try {
    const payload = {
      user_id: userId, // Pass userId for context if Python service uses it
      research_db_id: NOTION_RESEARCH_PROJECTS_DB_ID,
      task_db_id: NOTION_RESEARCH_TASKS_DB_ID,
      notion_api_token: NOTION_API_TOKEN,
      openai_api_key: OPENAI_API_KEY,
      search_api_key: ATOM_SERPAPI_API_KEY,
    };
    const response = await axios.post<PythonApiResponse<ProcessResearchQueueData>>(
      `${PYTHON_RESEARCH_API_URL}/process-research-queue`,
      payload
    );
    return handlePythonApiResponse(response.data, 'ResearchQueueProcessing');
  } catch (error: any) {
    const axiosError = error as AxiosError;
    return {
      ok: false,
      error: {
        code: axiosError.isAxiosError ? `HTTP_${axiosError.response?.status || 'NETWORK_ERROR'}` : 'SKILL_INTERNAL_ERROR',
        message: `Failed to process research queue: ${axiosError.message}`,
        details: axiosError.response?.data || axiosError.message,
      },
    };
  }
}

// Helper to map NotionSearchResultData to NotionPageSummary
function mapNotionSearchResultToPageSummary(searchResult: NotionSearchResultData): NotionPageSummary {
  // Assuming Python backend might pass through more fields than defined in NotionSearchResultData
  const unknownProps = searchResult as any;
  return {
    id: searchResult.id,
    title: searchResult.title,
    url: searchResult.url,
    preview_text: searchResult.content, // Map 'content' to 'preview_text'
    // Timestamps and icon would ideally come from the backend if available
    last_edited_time: unknownProps.last_edited_time || unknownProps.properties?.last_edited_time?.last_edited_time || undefined,
    created_time: unknownProps.created_time || unknownProps.properties?.created_time?.created_time || undefined,
    icon: unknownProps.icon || undefined, // Assuming icon structure matches NotionPageSummary's icon type
  };
}

/**
 * Placeholder for fetching detailed summary of a specific Notion page by its ID.
 * This would call a Python backend endpoint (e.g., /get-notion-page-summary).
 * The Python backend would use Notion API to get page details and format them.
 * @param userId The ID of the user.
 * @param pageId The ID of the Notion page.
 * @returns A promise that resolves to a SkillResponse containing the NotionPageSummary.
 */
export async function getNotionPageSummaryById(
  userId: string,
  pageId: string
): Promise<SkillResponse<NotionPageSummary>> { // Assuming NotionPageSummary is defined in types
  logger.info(`[getNotionPageSummaryById] Called for userId: ${userId}, pageId: ${pageId}`);
  if (!PYTHON_NOTE_API_URL) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python Note API URL is not configured.' } };
  if (!NOTION_API_TOKEN) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion API token is not configured.' } };
  if (!pageId) return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Page ID is required.'}};

  // This is a placeholder. In a real implementation:
  // 1. Define a Python endpoint (e.g., GET /get-notion-page-summary/:page_id)
  // 2. Python endpoint uses Notion API to fetch page properties and content block summaries.
  // 3. Python endpoint formats this into a structure matching NotionPageSummary.
  // 4. Call that endpoint here using axios.

  logger.warn(`[getNotionPageSummaryById] This function is a placeholder and does not call a real backend yet.`);
  // Mock response for now:
  // return Promise.resolve({
  //   ok: false,
  //   error: { code: 'NOT_IMPLEMENTED', message: 'getNotionPageSummaryById is not implemented yet.'}
  // });

  // For testing smartMeetingPrepSkill, let's return a mock success if a known ID is passed.
  if (pageId === "mock-page-id-from-description") {
    return Promise.resolve({
      ok: true,
      data: {
        id: pageId,
        title: "Mocked Page from Description",
        url: `https://www.notion.so/${pageId}`,
        preview_text: "This is a mock summary for a page explicitly linked in a meeting description...",
        last_edited_time: new Date().toISOString(),
        created_time: new Date().toISOString(),
        // icon: { type: "emoji", emoji: "📄" }
      }
    });
  }

  return Promise.resolve({
    ok: false,
    error: { code: 'NOT_FOUND_OR_NOT_IMPLEMENTED', message: `Page ${pageId} not found (or feature not fully implemented).` }
  });
}


// --- Note-Taking Skills ---

export async function createNotionNote(
  userId: string, // For potential logging or if Python service uses it
  title: string,
  content: string,
  notionDbId?: string // Optional: if not provided, Python uses its default
): Promise<SkillResponse<CreateNoteData>> {
  if (!PYTHON_NOTE_API_URL) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python Note API URL is not configured.' } };
  if (!NOTION_API_TOKEN) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion API token is not configured.' } };

  try {
    const payload: any = {
      title,
      content,
      user_id: userId,
      notion_api_token: NOTION_API_TOKEN,
    };
    if (notionDbId) payload.notion_db_id = notionDbId;
    else if (NOTION_NOTES_DATABASE_ID) payload.notion_db_id = NOTION_NOTES_DATABASE_ID; // Use default if available

    const response = await axios.post<PythonApiResponse<CreateNoteData>>(
      `${PYTHON_NOTE_API_URL}/create-note`,
      payload
    );
    return handlePythonApiResponse(response.data, 'CreateNotionNote');
  } catch (error: any) {
    const axiosError = error as AxiosError;
    return {
      ok: false,
      error: {
        code: axiosError.isAxiosError ? `HTTP_${axiosError.response?.status || 'NETWORK_ERROR'}` : 'SKILL_INTERNAL_ERROR',
        message: `Failed to create Notion note: ${axiosError.message}`,
        details: axiosError.response?.data || axiosError.message,
      },
    };
  }
}

export async function createAudioNoteFromUrl(
  userId: string,
  audioUrl: string,
  title: string,
  notionDbId?: string,
  notionSource?: string,
  linkedEventId?: string
): Promise<SkillResponse<CreateNoteData>> {
  if (!PYTHON_NOTE_API_URL) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python Note API URL is not configured.' } };
  if (!NOTION_API_TOKEN) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion API token is not configured.' } };
  if (!DEEPGRAM_API_KEY) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Deepgram API key is not configured.' } };
  if (!OPENAI_API_KEY) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'OpenAI API key is not configured.' } };

  try {
    const payload: any = {
      audio_url: audioUrl,
      title,
      user_id: userId,
      notion_api_token: NOTION_API_TOKEN,
      deepgram_api_key: DEEPGRAM_API_KEY,
      openai_api_key: OPENAI_API_KEY,
    };
    if (notionDbId) payload.notion_db_id = notionDbId;
    else if (NOTION_NOTES_DATABASE_ID) payload.notion_db_id = NOTION_NOTES_DATABASE_ID;
    if (notionSource) payload.notion_source = notionSource;
    if (linkedEventId) payload.linked_event_id = linkedEventId;

    const response = await axios.post<PythonApiResponse<CreateNoteData>>(
      `${PYTHON_NOTE_API_URL}/create-audio-note-url`,
      payload
    );
    return handlePythonApiResponse(response.data, 'CreateAudioNote');
  } catch (error: any) {
    const axiosError = error as AxiosError;
    return {
      ok: false,
      error: {
        code: axiosError.isAxiosError ? `HTTP_${axiosError.response?.status || 'NETWORK_ERROR'}` : 'SKILL_INTERNAL_ERROR',
        message: `Failed to create audio note from URL: ${axiosError.message}`,
        details: axiosError.response?.data || axiosError.message,
      },
    };
  }
}

export async function searchNotionNotes(
  userId: string, // For context/logging
  queryText: string,
  notionDbId?: string,
  source?: string // Optional filter by 'Source' property
): Promise<SkillResponse<NotionPageSummary[]>> { // Changed return type
  if (!PYTHON_NOTE_API_URL) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python Note API URL is not configured.' } };
  if (!NOTION_API_TOKEN) return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion API token is not configured.' } };

  try {
    const payload: any = {
      query_text: queryText,
      user_id: userId,
      notion_api_token: NOTION_API_TOKEN,
    };
    if (notionDbId) payload.notion_db_id = notionDbId;
    else if (NOTION_NOTES_DATABASE_ID) payload.notion_db_id = NOTION_NOTES_DATABASE_ID;
    if (source) payload.source = source;


    const response = await axios.post<PythonApiResponse<NotionSearchResultData[]>>(
      `${PYTHON_NOTE_API_URL}/search-notes`,
      payload
    );

    // Use handlePythonApiResponse and then map the results
    const pythonResponse = handlePythonApiResponse<NotionSearchResultData[]>(response.data, 'SearchNotionNotes');
    if (pythonResponse.ok && pythonResponse.data) {
      return {
        ok: true,
        data: pythonResponse.data.map(mapNotionSearchResultToPageSummary)
      };
    }
    return { // Error case from handlePythonApiResponse
      ok: false,
      error: pythonResponse.error
    };

  } catch (error: any) {
    const axiosError = error as AxiosError;
    return {
      ok: false,
      error: {
        code: axiosError.isAxiosError ? `HTTP_${axiosError.response?.status || 'NETWORK_ERROR'}` : 'SKILL_INTERNAL_ERROR',
        message: `Failed to search Notion notes: ${axiosError.message}`,
        details: axiosError.response?.data || axiosError.message,
      },
    };
  }
}

[end of atomic-docker/project/functions/atom-agent/skills/notionAndResearchSkills.ts]
