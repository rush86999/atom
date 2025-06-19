import axios, { AxiosError } from 'axios';
import {
  SkillResponse,
  SkillError,
  PythonApiResponse,
  InitiateResearchData,
  ProcessResearchQueueData,
  CreateNoteData,
  NotionSearchResultData,
} from '../types';
import {
  PYTHON_RESEARCH_API_URL,
  PYTHON_NOTE_API_URL,
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
): Promise<SkillResponse<NotionSearchResultData[]>> {
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
    return handlePythonApiResponse(response.data, 'SearchNotionNotes');
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
