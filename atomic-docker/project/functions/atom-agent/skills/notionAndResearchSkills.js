import axios from 'axios';
import { logger } from '../../_utils/logger'; // Added logger
import { decrypt } from '../../_libs/crypto';
import { executeGraphQLQuery } from '../_libs/graphqlClient';
async function getNotionApiKey(userId) {
    const query = `
        query GetUserCredential($userId: String!, $serviceName: String!) {
            user_credentials(where: {user_id: {_eq: $userId}, service_name: {_eq: $serviceName}}) {
                encrypted_secret
            }
        }
    `;
    const variables = {
        userId,
        serviceName: 'notion',
    };
    const response = await executeGraphQLQuery(query, variables, 'GetUserCredential', userId);
    if (response.user_credentials && response.user_credentials.length > 0) {
        return decrypt(response.user_credentials[0].encrypted_secret);
    }
    return null;
}
// --- Helper for handling Python API responses ---
function handlePythonApiResponse(pythonResponse, serviceName = 'Python API') {
    if (pythonResponse.ok && pythonResponse.data !== undefined) {
        return { ok: true, data: pythonResponse.data };
    }
    else if (pythonResponse.error) {
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
export async function initiateResearch(userId, topic) {
    const notionApiKey = await getNotionApiKey(userId);
    if (!PYTHON_RESEARCH_API_URL)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python Research API URL is not configured.' } };
    if (!notionApiKey)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion API token is not configured.' } };
    if (!OPENAI_API_KEY)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'OpenAI API key is not configured.' } };
    if (!NOTION_RESEARCH_PROJECTS_DB_ID)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion Research Projects DB ID is not configured.' } };
    if (!NOTION_RESEARCH_TASKS_DB_ID)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion Research Tasks DB ID is not configured.' } };
    try {
        const payload = {
            topic: topic,
            user_id: userId, // Pass userId to Python service
            research_db_id: NOTION_RESEARCH_PROJECTS_DB_ID,
            task_db_id: NOTION_RESEARCH_TASKS_DB_ID,
            notion_api_token: notionApiKey,
            openai_api_key: OPENAI_API_KEY,
        };
        const response = await axios.post(`${PYTHON_RESEARCH_API_URL}/initiate-research`, payload);
        return handlePythonApiResponse(response.data, 'ResearchInitiation');
    }
    catch (error) {
        const axiosError = error;
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
// --- Hybrid Search Orchestration ---
import { hybridSearch } from '../../../src/skills/lanceDbStorageSkills'; // Adjust path as needed
import { parseSearchQueryWithLLM } from '../../../src/nlu_agents/nluSearchFilterSkill'; // Adjust path
/**
 * Orchestrates a search by first parsing the raw query with an NLU LLM,
 * then executing a hybrid search with the parsed term and filters.
 * @param userId The ID of the user performing the search.
 * @param rawQuery The user's natural language search query.
 * @param options Optional limits for the search.
 * @returns A promise that resolves to a SkillResponse containing hybrid search results.
 */
export async function performHybridSearchWithNLU(userId, rawQuery, options // Callers shouldn't provide filters directly
) {
    logger.info(`[performHybridSearchWithNLU] Received raw query: "${rawQuery}"`);
    // 1. Parse the raw query to get search term and filters
    const parsedQuery = await parseSearchQueryWithLLM(rawQuery);
    logger.info(`[performHybridSearchWithNLU] NLU parsed result - Term: "${parsedQuery.search_term}", Filters:`, parsedQuery.filters);
    // 2. Execute the hybrid search with the parsed components
    const searchOptions = {
        ...options, // Pass through any limits from the caller
        filters: parsedQuery.filters, // Use the filters determined by the NLU
    };
    const searchResult = await hybridSearch(userId, parsedQuery.search_term, searchOptions);
    return searchResult;
}
// --- Notion Task Management Skills ---
export async function createNotionTask(userId, params, integrations) {
    const notionApiKey = await getNotionApiKey(userId);
    if (!PYTHON_NOTE_API_URL)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python Note API URL is not configured.' } };
    if (!notionApiKey)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion API token is not configured.' } };
    if (!params.notionTasksDbId && !ATOM_NOTION_TASKS_DATABASE_ID) {
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion Tasks Database ID is not configured.' } };
    }
    try {
        const payload = {
            ...params, // description, dueDate, status, priority, listName, notes
            user_id: userId,
            notion_api_token: notionApiKey,
            notion_db_id: params.notionTasksDbId || ATOM_NOTION_TASKS_DATABASE_ID
        };
        const response = await axios.post(`${PYTHON_NOTE_API_URL}/create-notion-task`, payload);
        return handlePythonApiResponse(response.data, 'CreateNotionTask');
    }
    catch (error) {
        const axiosError = error;
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
export async function queryNotionTasks(userId, params) {
    const notionApiKey = await getNotionApiKey(userId);
    if (!PYTHON_NOTE_API_URL)
        return { success: false, tasks: [], error: 'Python Note API URL is not configured.', message: 'Configuration error.' };
    if (!notionApiKey)
        return { success: false, tasks: [], error: 'Notion API token is not configured.', message: 'Configuration error.' };
    if (!params.notionTasksDbId && !ATOM_NOTION_TASKS_DATABASE_ID) {
        return { success: false, tasks: [], error: 'Notion Tasks Database ID is not configured.', message: 'Configuration error.' };
    }
    try {
        const payload = {
            ...params,
            user_id: userId, // Include userId for consistency, Python backend may or may not use it for filtering
            notion_api_token: notionApiKey,
            notion_db_id: params.notionTasksDbId || ATOM_NOTION_TASKS_DATABASE_ID
        };
        const response = await axios.post(`${PYTHON_NOTE_API_URL}/query-notion-tasks`, payload);
        if (response.data.ok && response.data.data) {
            return { success: true, tasks: response.data.data, message: response.data.message || 'Tasks queried successfully.' };
        }
        else if (response.data.error) {
            return { success: false, tasks: [], error: response.data.error.message, message: response.data.error.details };
        }
        return { success: false, tasks: [], error: 'Unexpected response from queryNotionTasks backend.', message: 'Backend communication error.' };
    }
    catch (error) {
        const axiosError = error;
        console.error(`Failed to query Notion tasks: ${axiosError.message}`, axiosError.response?.data || axiosError.message);
        return {
            success: false,
            tasks: [],
            error: `Failed to query Notion tasks: ${axiosError.message}`,
        };
    }
}
export async function updateNotionTask(userId, params) {
    const notionApiKey = await getNotionApiKey(userId);
    if (!PYTHON_NOTE_API_URL)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python Note API URL is not configured.' } };
    if (!notionApiKey)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion API token is not configured.' } };
    if (!params.taskId)
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Task ID (taskId) is required for update.' } };
    try {
        const payload = {
            ...params,
            user_id: userId,
            notion_api_token: notionApiKey
        };
        const response = await axios.post(`${PYTHON_NOTE_API_URL}/update-notion-task`, payload);
        return handlePythonApiResponse(response.data, 'UpdateNotionTask');
    }
    catch (error) {
        const axiosError = error;
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
export async function searchSimilarNotionNotes(userId, queryText, limit) {
    if (!PYTHON_NOTE_API_URL) {
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python Note API URL is not configured.' } };
    }
    if (!OPENAI_API_KEY) { // OpenAI API key is needed by the Python endpoint for embedding the query
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'OpenAI API key is not configured for similarity search.' } };
    }
    if (!userId) { // user_id is crucial for filtering results in LanceDB
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'User ID is required for searching similar notes.' } };
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
        const response = await axios.post(`${PYTHON_NOTE_API_URL}/search-similar-notes`, payload);
        return handlePythonApiResponse(response.data, 'SearchSimilarNotionNotes');
    }
    catch (error) {
        const axiosError = error;
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
export async function processResearchQueue(userId // Contextual, Python service doesn't strictly need it if keys are global there
) {
    const notionApiKey = await getNotionApiKey(userId);
    if (!PYTHON_RESEARCH_API_URL)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python Research API URL is not configured.' } };
    if (!notionApiKey)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion API token is not configured.' } };
    if (!OPENAI_API_KEY)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'OpenAI API key is not configured.' } };
    if (!ATOM_SERPAPI_API_KEY)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'SerpApi API key is not configured.' } };
    if (!NOTION_RESEARCH_PROJECTS_DB_ID)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion Research Projects DB ID is not configured.' } };
    if (!NOTION_RESEARCH_TASKS_DB_ID)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion Research Tasks DB ID is not configured.' } };
    try {
        const payload = {
            user_id: userId, // Pass userId for context if Python service uses it
            research_db_id: NOTION_RESEARCH_PROJECTS_DB_ID,
            task_db_id: NOTION_RESEARCH_TASKS_DB_ID,
            notion_api_token: notionApiKey,
            openai_api_key: OPENAI_API_KEY,
            search_api_key: ATOM_SERPAPI_API_KEY,
        };
        const response = await axios.post(`${PYTHON_RESEARCH_API_URL}/process-research-queue`, payload);
        return handlePythonApiResponse(response.data, 'ResearchQueueProcessing');
    }
    catch (error) {
        const axiosError = error;
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
function mapNotionSearchResultToPageSummary(searchResult) {
    // Assuming Python backend might pass through more fields than defined in NotionSearchResultData
    const unknownProps = searchResult;
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
export async function getNotionPageSummaryById(userId, pageId) {
    const notionApiKey = await getNotionApiKey(userId);
    logger.info(`[getNotionPageSummaryById] Called for userId: ${userId}, pageId: ${pageId}`);
    if (!PYTHON_NOTE_API_URL)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python Note API URL is not configured.' } };
    if (!notionApiKey)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion API token is not configured.' } };
    if (!pageId)
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Page ID is required.' } };
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
export async function createNotionNote(userId, // For potential logging or if Python service uses it
title, content, notionDbId // Optional: if not provided, Python uses its default
) {
    const notionApiKey = await getNotionApiKey(userId);
    if (!PYTHON_NOTE_API_URL)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python Note API URL is not configured.' } };
    if (!notionApiKey)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion API token is not configured.' } };
    try {
        const payload = {
            title,
            content,
            user_id: userId,
            notion_api_token: notionApiKey,
        };
        if (notionDbId)
            payload.notion_db_id = notionDbId;
        else if (NOTION_NOTES_DATABASE_ID)
            payload.notion_db_id = NOTION_NOTES_DATABASE_ID; // Use default if available
        const response = await axios.post(`${PYTHON_NOTE_API_URL}/create-note`, payload);
        return handlePythonApiResponse(response.data, 'CreateNotionNote');
    }
    catch (error) {
        const axiosError = error;
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
export async function createAudioNoteFromUrl(userId, audioUrl, title, notionDbId, notionSource, linkedEventId) {
    const notionApiKey = await getNotionApiKey(userId);
    if (!PYTHON_NOTE_API_URL)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python Note API URL is not configured.' } };
    if (!notionApiKey)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion API token is not configured.' } };
    if (!DEEPGRAM_API_KEY)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Deepgram API key is not configured.' } };
    if (!OPENAI_API_KEY)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'OpenAI API key is not configured.' } };
    try {
        const payload = {
            audio_url: audioUrl,
            title,
            user_id: userId,
            notion_api_token: notionApiKey,
            deepgram_api_key: DEEPGRAM_API_KEY,
            openai_api_key: OPENAI_API_KEY,
        };
        if (notionDbId)
            payload.notion_db_id = notionDbId;
        else if (NOTION_NOTES_DATABASE_ID)
            payload.notion_db_id = NOTION_NOTES_DATABASE_ID;
        if (notionSource)
            payload.notion_source = notionSource;
        if (linkedEventId)
            payload.linked_event_id = linkedEventId;
        const response = await axios.post(`${PYTHON_NOTE_API_URL}/create-audio-note-url`, payload);
        return handlePythonApiResponse(response.data, 'CreateAudioNote');
    }
    catch (error) {
        const axiosError = error;
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
export async function searchNotionNotes(userId, // For context/logging
queryText, notionDbId, source // Optional filter by 'Source' property
) {
    const notionApiKey = await getNotionApiKey(userId);
    if (!PYTHON_NOTE_API_URL)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Python Note API URL is not configured.' } };
    if (!notionApiKey)
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion API token is not configured.' } };
    try {
        const payload = {
            query_text: queryText,
            user_id: userId,
            notion_api_token: notionApiKey,
        };
        if (notionDbId)
            payload.notion_db_id = notionDbId;
        else if (NOTION_NOTES_DATABASE_ID)
            payload.notion_db_id = NOTION_NOTES_DATABASE_ID;
        if (source)
            payload.source = source;
        const response = await axios.post(`${PYTHON_NOTE_API_URL}/search-notes`, payload);
        // Use handlePythonApiResponse and then map the results
        const pythonResponse = handlePythonApiResponse(response.data, 'SearchNotionNotes');
        if (pythonResponse.ok && pythonResponse.data) {
            return {
                ok: true,
                data: pythonResponse.data.map(mapNotionSearchResultToPageSummary)
            };
        }
        return {
            ok: false,
            error: pythonResponse.error
        };
    }
    catch (error) {
        const axiosError = error;
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
[end, of, atomic - docker / project / functions / atom - agent / skills / notionAndResearchSkills.ts];
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibm90aW9uQW5kUmVzZWFyY2hTa2lsbHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJub3Rpb25BbmRSZXNlYXJjaFNraWxscy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxPQUFPLEtBQXFCLE1BQU0sT0FBTyxDQUFDO0FBb0IxQyxPQUFPLEVBQUUsTUFBTSxFQUFFLE1BQU0scUJBQXFCLENBQUMsQ0FBQyxlQUFlO0FBQzdELE9BQU8sRUFBRSxPQUFPLEVBQUUsTUFBTSxvQkFBb0IsQ0FBQztBQUM3QyxPQUFPLEVBQUUsbUJBQW1CLEVBQUUsTUFBTSx3QkFBd0IsQ0FBQztBQUU3RCxLQUFLLFVBQVUsZUFBZSxDQUFDLE1BQWM7SUFDekMsTUFBTSxLQUFLLEdBQUc7Ozs7OztLQU1iLENBQUM7SUFDRixNQUFNLFNBQVMsR0FBRztRQUNkLE1BQU07UUFDTixXQUFXLEVBQUUsUUFBUTtLQUN4QixDQUFDO0lBQ0YsTUFBTSxRQUFRLEdBQUcsTUFBTSxtQkFBbUIsQ0FBdUQsS0FBSyxFQUFFLFNBQVMsRUFBRSxtQkFBbUIsRUFBRSxNQUFNLENBQUMsQ0FBQztJQUNoSixJQUFJLFFBQVEsQ0FBQyxnQkFBZ0IsSUFBSSxRQUFRLENBQUMsZ0JBQWdCLENBQUMsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDO1FBQ3BFLE9BQU8sT0FBTyxDQUFDLFFBQVEsQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDLENBQUMsQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDO0lBQ2xFLENBQUM7SUFDRCxPQUFPLElBQUksQ0FBQztBQUNoQixDQUFDO0FBRUQsbURBQW1EO0FBQ25ELFNBQVMsdUJBQXVCLENBQzlCLGNBQW9DLEVBQ3BDLGNBQXNCLFlBQVk7SUFFbEMsSUFBSSxjQUFjLENBQUMsRUFBRSxJQUFJLGNBQWMsQ0FBQyxJQUFJLEtBQUssU0FBUyxFQUFFLENBQUM7UUFDM0QsT0FBTyxFQUFFLEVBQUUsRUFBRSxJQUFJLEVBQUUsSUFBSSxFQUFFLGNBQWMsQ0FBQyxJQUFJLEVB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SUFBSSxVQUFVLENBQUMsT0FBTzthQUN6RDtTQUNGLENBQUM7SUFDSixDQUFDO0FBQ0gsQ0FBQztBQUVELENBQUMsR0FBRyxFQUFDLEVBQUUsRUFBQyxNQUFNLEdBQUMsTUFBTSxHQUFDLE9BQU8sR0FBQyxTQUFTLEdBQUMsSUFBSSxHQUFDLEtBQUssR0FBQyxNQUFNLEdBQUMsdUJBQXVCLENBQUMsRUFBRSxDQUFDLENBQUEiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgYXhpb3MsIHsgQXhpb3NFcnJvciB9IGZyb20gJ2F4aW9zJztcbmltcG9ydCB7XG4gIFNraWxsUmVzcG9uc2UsXG4gIFNraWxsRXJyb3IsXG4gIFB5dGhvbkFwaVJlc3BvbnNlLFxuICBJbml0aWF0ZVJlc2VhcmNoRGF0YSxcbiAgUHJvY2Vzc1Jlc2VhcmNoUXVldWVEYXRhLFxuICBDcmVhdGVOb3RlRGF0YSxcbiAgTm90aW9uU2VhcmNoUmVzdWx0RGF0YSxcbiAgTm90aW9uU2ltaWxhck5vdGVSZXN1bHQsIC8vIEFkZGVkIHRoaXMgbWlzc2luZyB0eXBlXG4gIC8vIE5ldyBUYXNrIE1hbmFnZW1lbnQgVHlwZXNcbiAgQ3JlYXRlTm90aW9uVGFza1BhcmFtcyxcbiAgUXVlcnlOb3Rpb25UYXNrc1BhcmFtcyxcbiAgVGFza1F1ZXJ5UmVzcG9uc2UsIC8vIFVzZWQgZGlyZWN0bHkgYnkgcXVlcnlOb3Rpb25UYXNrc1xuICBVcGRhdGVOb3Rpb25UYXNrUGFyYW1zLFxuICBDcmVhdGVUYXNrRGF0YSwgICAgLy8gRm9yIFNraWxsUmVzcG9uc2U8Q3JlYXRlVGFza0RhdGE+XG4gIFVwZGF0ZVRhc2tEYXRhLCAgICAvLyBGb3IgU2tpbGxSZXNwb25zZTxVcGRhdGVUYXNrRGF0YT5cbiAgTm90aW9uVGFzaywgICAgICAgIC8vIEZvciBUYXNrUXVlcnlSZXNwb25zZS50YXNrcyBhbmQgUHl0aG9uQXBpUmVzcG9uc2U8Tm90aW9uVGFza1tdPlxuICBOb3Rpb25QYWdlU3VtbWFyeSwgLy8gQWRkZWQgZm9yIGdldE5vdGlvblBhZ2VTdW1tYXJ5QnlJZFxufSBmcm9tICcuLi90eXBlcyc7XG5pbXBvcnQgeyBsb2dnZXIgfSBmcm9tICcuLi8uLi9fdXRpbHMvbG9nZ2VyJzsgLy8gQWRkZWQgbG9nZ2VyXG5pbXBvcnQgeyBkZWNyeXB0IH0gZnJvbSAnLi4vLi4vX2xpYnMvY3J5cHRvJztcbmltcG9ydCB7IGV4ZWN1dGVHcmFwaFFMUXVlcnkgfSBmcm9tICcuLi9fbGlicy9ncmFwaHFsQ2xpZW50JztcblxuYXN5bmMgZnVuY3Rpb24gZ2V0Tm90aW9uQXBpS2V5KHVzZXJJZDogc3RyaW5nKTogUHJvbWlzZTxzdHJpbmcgfCBudWxsPiB7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgIHF1ZXJ5IEdldFVzZXJDcmVkZW50aWFsKCR1c2VySWQ6IFN0cmluZyEsICRzZXJ2aWNlTmFtZTogU3RyaW5nISkge1xuICAgICAgICAgICAgdXNlcl9jcmVkZW50aWFscyh3aGVyZToge3VzZXJfaWQ6IHtfZXE6ICR1c2VySWR9LCBzZXJ2aWNlX25hbWU6IHtfZXE6ICRzZXJ2aWNlTmFtZX19KSB7XG4gICAgICAgICAgICAgICAgZW5jcnlwdGVkX3NlY3JldFxuICAgICAgICAgICAgfVxuICAgICAgICB9XG4gICAgYDtcbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgc2VydmljZU5hbWU6ICdub3Rpb24nLFxuICAgIH07XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBleGVjdXRlR3JhcGhRTFF1ZXJ5PHsgdXNlcl9jcmVkZW50aWFsczogeyBlbmNyeXB0ZWRfc2VjcmV0OiBzdHJpbmcgfVtdIH0+KHF1ZXJ5LCB2YXJpYWJsZXMsICdHZXRVc2VyQ3JlZGVudGlhbCcsIHVzZXJJZCk7XG4gICAgaWYgKHJlc3BvbnNlLnVzZXJfY3JlZGVudGlhbHMgJiYgcmVzcG9uc2UudXNlcl9jcmVkZW50aWFscy5sZW5ndGggPiAwKSB7XG4gICAgICAgIHJldHVybiBkZWNyeXB0KHJlc3BvbnNlLnVzZXJfY3JlZGVudGlhbHNbMF0uZW5jcnlwdGVkX3NlY3JldCk7XG4gICAgfVxuICAgIHJldHVybiBudWxsO1xufVxuXG4vLyAtLS0gSGVscGVyIGZvciBoYW5kbGluZyBQeXRob24gQVBJIHJlc3BvbnNlcyAtLS1cbmZ1bmN0aW9uIGhhbmRsZVB5dGhvbkFwaVJlc3BvbnNlPFQ+KFxuICBweXRob25SZXNwb25zZTogUHl0aG9uQXBpUmVzcG9uc2U8VD4sXG4gIHNlcnZpY2VOYW1lOiBzdHJpbmcgPSAnUHl0aG9uIEFQSSdcbik6IFNraWxsUmVzcG9uc2U8VD4ge1xuICBpZiAocHl0aG9uUmVzcG9uc2Uub2sgJiYgcHl0aG9uUmVzcG9uc2UuZGF0YSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IHB5dGhvblJlc3BvbnNlLmRhdGEgfTtcbiAgfSBlbHNlIGlmIChweXRob25SZXNwb25zZS5lcnJvcikge1xuICAgIGNvbnNvbGUuZXJyb3IoYCR7c2VydmljZU5hbWV9IGVycm9yOmAsIHB5dGhvblJlc3BvbnNlLmVycm9yKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogcHl0aG9uUmVzcG9uc2UuZXJyb3IuY29kZSB8fCAnUFlUSE9OX1NFUlZJQ0VfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiBweXRob25SZXNwb25zZS5lcnJvci5tZXNzYWdlIHx8IGBVbmtub3duIGVycm9yIGZyb20gJHtzZXJ2aWNlTmFtZX0uYCxcbiAgICAgICAgZGV0YWlsczogcHl0aG9uUmVzcG9uc2UuZXJyb3IuZGV0YWlscyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICByZXR1cm4ge1xuICAgIG9rOiBmYWxzZSxcbiAgICBlcnJvcjoge1xuICAgICAgY29kZTogJ1BZVEhPTl9VTkVYUEVDVEVEX1JFU1BPTlNFJyxcbiAgICAgIG1lc3NhZ2U6IGBVbmV4cGVjdGVkIHJlc3BvbnNlIHN0cnVjdHVyZSBmcm9tICR7c2VydmljZU5hbWV9LmAsXG4gICAgICBkZXRhaWxzOiBweXRob25SZXNwb25zZSxcbiAgICB9LFxuICB9O1xufVxuXG5cbi8vIC0tLSBSZXNlYXJjaCBTa2lsbHMgLS0tXG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBpbml0aWF0ZVJlc2VhcmNoKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdG9waWM6IHN0cmluZ1xuKTogUHJvbWlzZTxTa2lsbFJlc3BvbnNlPEluaXRpYXRlUmVzZWFyY2hEYXRhPj4ge1xuICBjb25zdCBub3Rpb25BcGlLZXkgPSBhd2FpdCBnZXROb3Rpb25BcGlLZXkodXNlcklkKTtcbiAgaWYgKCFQWVRIT05fUkVTRUFSQ0hfQVBJX1VSTCkgcmV0dXJuIHsgb2s6IGZhbHNlLCBlcnJvcjogeyBjb2RlOiAnQ09ORklHX0VSUk9SJywgbWVzc2FnZTogJ1B5dGhvbiBSZXNlYXJjaCBBUEkgVVJMIGlzIG5vdCBjb25maWd1cmVkLicgfSB9O1xuICBpZiAoIW5vdGlvbkFwaUtleSkgcmV0dXJuIHsgb2s6IGZhbHNlLCBlcnJvcjogeyBjb2RlOiAnQ09ORklHX0VSUk9SJywgbWVzc2FnZTogJ05vdGlvbiBBUEkgdG9rZW4gaXMgbm90IGNvbmZpZ3VyZWQuJyB9IH07XG4gIGlmICghT1BFTkFJX0FQSV9LRVkpIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHsgY29kZTogJ0NPTkZJR19FUlJPUicsIG1lc3NhZ2U6ICdPcGVuQUkgQVBJIGtleSBpcyBub3QgY29uZmlndXJlZC4nIH0gfTtcbiAgaWYgKCFOT1RJT05fUkVTRUFSQ0hfUFJPSkVDVFNfREJfSUQpIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHsgY29kZTogJ0NPTkZJR19FUlJPUicsIG1lc3NhZ2U6ICdOb3Rpb24gUmVzZWFyY2ggUHJvamVjdHMgREIgSUQgaXMgbm90IGNvbmZpZ3VyZWQuJyB9IH07XG4gIGlmICghTk9USU9OX1JFU0VBUkNIX1RBU0tTX0RCX0lEKSByZXR1cm4geyBvazogZmFsc2UsIGVycm9yOiB7IGNvZGU6ICdDT05GSUdfRVJST1InLCBtZXNzYWdlOiAnTm90aW9uIFJlc2VhcmNoIFRhc2tzIERCIElEIGlzIG5vdCBjb25maWd1cmVkLicgfSB9O1xuXG4gIHRyeSB7XG4gICAgY29uc3QgcGF5bG9hZCA9IHtcbiAgICAgIHRvcGljOiB0b3BpYyxcbiAgICAgIHVzZXJfaWQ6IHVzZXJJZCwgLy8gUGFzcyB1c2VySWQgdG8gUHl0aG9uIHNlcnZpY2VcbiAgICAgIHJlc2VhcmNoX2RiX2lkOiBOT1RJT05fUkVTRUFSQ0hfUFJPSkVDVFNfREJfSUQsXG4gICAgICB0YXNrX2RiX2lkOiBOT1RJT05fUkVTRUFSQ0hfVEFTS1NfREJfSUQsXG4gICAgICBub3Rpb25fYXBpX3Rva2VuOiBub3Rpb25BcGlLZXksXG4gICAgICBvcGVuYWlfYXBpX2tleTogT1BFTkFJX0FQSV9LRVksXG4gICAgfTtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGF4aW9zLnBvc3Q8UHl0aG9uQXBpUmVzcG9uc2U8SW5pdGlhdGVSZXNlYXJjaERhdGE+PihcbiAgICAgIGAke1BZVEhPTl9SRVNFQVJDSF9BUElfVVJMfS9pbml0aWF0ZS1yZXNlYXJjaGAsXG4gICAgICBwYXlsb2FkXG4gICAgKTtcbiAgICByZXR1cm4gaGFuZGxlUHl0aG9uQXBpUmVzcG9uc2UocmVzcG9uc2UuZGF0YSwgJ1Jlc2VhcmNoSW5pdGlhdGlvbicpO1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgY29uc3QgYXhpb3NFcnJvciA9IGVycm9yIGFzIEF4aW9zRXJyb3I7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6IGF4aW9zRXJyb3IuaXNBeGlvc0Vycm9yID8gYEhUVFBfJHtheGlvc0Vycm9yLnJlc3BvbnNlPy5zdGF0dXMgfHwgJ05FVFdPUktfRVJST1InfWAgOiAnU0tJTExfSU5URVJOQUxfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiBgRmFpbGVkIHRvIGluaXRpYXRlIHJlc2VhcmNoOiAke2F4aW9zRXJyb3IubWVzc2FnZX1gLFxuICAgICAgICBkZXRhaWxzOiBheGlvc0Vycm9yLnJlc3BvbnNlPy5kYXRhIHx8IGF4aW9zRXJyb3IubWVzc2FnZSxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufVxuXG5cbi8vIC0tLSBIeWJyaWQgU2VhcmNoIE9yY2hlc3RyYXRpb24gLS0tXG5pbXBvcnQgeyBoeWJyaWRTZWFyY2gsIEh5YnJpZFNlYXJjaE9wdGlvbnMgfSBmcm9tICcuLi8uLi8uLi9zcmMvc2tpbGxzL2xhbmNlRGJTdG9yYWdlU2tpbGxzJzsgLy8gQWRqdXN0IHBhdGggYXMgbmVlZGVkXG5pbXBvcnQgeyBwYXJzZVNlYXJjaFF1ZXJ5V2l0aExMTSB9IGZyb20gJy4uLy4uLy4uL3NyYy9ubHVfYWdlbnRzL25sdVNlYXJjaEZpbHRlclNraWxsJzsgLy8gQWRqdXN0IHBhdGhcbmltcG9ydCB7IEh5YnJpZFNlYXJjaFJlc3VsdEl0ZW0gfSBmcm9tICcuLi90eXBlcyc7XG5cbi8qKlxuICogT3JjaGVzdHJhdGVzIGEgc2VhcmNoIGJ5IGZpcnN0IHBhcnNpbmcgdGhlIHJhdyBxdWVyeSB3aXRoIGFuIE5MVSBMTE0sXG4gKiB0aGVuIGV4ZWN1dGluZyBhIGh5YnJpZCBzZWFyY2ggd2l0aCB0aGUgcGFyc2VkIHRlcm0gYW5kIGZpbHRlcnMuXG4gKiBAcGFyYW0gdXNlcklkIFRoZSBJRCBvZiB0aGUgdXNlciBwZXJmb3JtaW5nIHRoZSBzZWFyY2guXG4gKiBAcGFyYW0gcmF3UXVlcnkgVGhlIHVzZXIncyBuYXR1cmFsIGxhbmd1YWdlIHNlYXJjaCBxdWVyeS5cbiAqIEBwYXJhbSBvcHRpb25zIE9wdGlvbmFsIGxpbWl0cyBmb3IgdGhlIHNlYXJjaC5cbiAqIEByZXR1cm5zIEEgcHJvbWlzZSB0aGF0IHJlc29sdmVzIHRvIGEgU2tpbGxSZXNwb25zZSBjb250YWluaW5nIGh5YnJpZCBzZWFyY2ggcmVzdWx0cy5cbiAqL1xuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHBlcmZvcm1IeWJyaWRTZWFyY2hXaXRoTkxVKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgcmF3UXVlcnk6IHN0cmluZyxcbiAgb3B0aW9ucz86IE9taXQ8SHlicmlkU2VhcmNoT3B0aW9ucywgJ2ZpbHRlcnMnPiAvLyBDYWxsZXJzIHNob3VsZG4ndCBwcm92aWRlIGZpbHRlcnMgZGlyZWN0bHlcbik6IFByb21pc2U8U2tpbGxSZXNwb25zZTxIeWJyaWRTZWFyY2hSZXN1bHRJdGVtW10+PiB7XG4gIGxvZ2dlci5pbmZvKGBbcGVyZm9ybUh5YnJpZFNlYXJjaFdpdGhOTFVdIFJlY2VpdmVkIHJhdyBxdWVyeTogXCIke3Jhd1F1ZXJ5fVwiYCk7XG5cbiAgLy8gMS4gUGFyc2UgdGhlIHJhdyBxdWVyeSB0byBnZXQgc2VhcmNoIHRlcm0gYW5kIGZpbHRlcnNcbiAgY29uc3QgcGFyc2VkUXVlcnkgPSBhd2FpdCBwYXJzZVNlYXJjaFF1ZXJ5V2l0aExMTShyYXdRdWVyeSk7XG4gIGxvZ2dlci5pbmZvKGBbcGVyZm9ybUh5YnJpZFNlYXJjaFdpdGhOTFVdIE5MVSBwYXJzZWQgcmVzdWx0IC0gVGVybTogXCIke3BhcnNlZFF1ZXJ5LnNlYXJjaF90ZXJtfVwiLCBGaWx0ZXJzOmAsIHBhcnNlZFF1ZXJ5LmZpbHRlcnMpO1xuXG4gIC8vIDIuIEV4ZWN1dGUgdGhlIGh5YnJpZCBzZWFyY2ggd2l0aCB0aGUgcGFyc2VkIGNvbXBvbmVudHNcbiAgY29uc3Qgc2VhcmNoT3B0aW9uczogSHlicmlkU2VhcmNoT3B0aW9ucyA9IHtcbiAgICAuLi5vcHRpb25zLCAvLyBQYXNzIHRocm91Z2ggYW55IGxpbWl0cyBmcm9tIHRoZSBjYWxsZXJcbiAgICBmaWx0ZXJzOiBwYXJzZWRRdWVyeS5maWx0ZXJzLCAvLyBVc2UgdGhlIGZpbHRlcnMgZGV0ZXJtaW5lZCBieSB0aGUgTkxVXG4gIH07XG5cbiAgY29uc3Qgc2VhcmNoUmVzdWx0ID0gYXdhaXQgaHlicmlkU2VhcmNoKFxuICAgIHVzZXJJZCxcbiAgICBwYXJzZWRRdWVyeS5zZWFyY2hfdGVybSxcbiAgICBzZWFyY2hPcHRpb25zXG4gICk7XG5cbiAgcmV0dXJuIHNlYXJjaFJlc3VsdDtcbn1cblxuLy8gLS0tIE5vdGlvbiBUYXNrIE1hbmFnZW1lbnQgU2tpbGxzIC0tLVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gY3JlYXRlTm90aW9uVGFzayhcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHBhcmFtczogQ3JlYXRlTm90aW9uVGFza1BhcmFtcyxcbiAgaW50ZWdyYXRpb25zOiBhbnlcbik6IFByb21pc2U8U2tpbGxSZXNwb25zZTxDcmVhdGVUYXNrRGF0YT4+IHtcbiAgY29uc3Qgbm90aW9uQXBpS2V5ID0gYXdhaXQgZ2V0Tm90aW9uQXBpS2V5KHVzZXJJZCk7XG4gIGlmICghUFlUSE9OX05PVEVfQVBJX1VSTCkgcmV0dXJuIHsgb2s6IGZhbHNlLCBlcnJvcjogeyBjb2RlOiAnQ09ORklHX0VSUk9SJywgbWVzc2FnZTogJ1B5dGhvbiBOb3RlIEFQSSBVUkwgaXMgbm90IGNvbmZpZ3VyZWQuJyB9IH07XG4gIGlmICghbm90aW9uQXBpS2V5KSByZXR1cm4geyBvazogZmFsc2UsIGVycm9yOiB7IGNvZGU6ICdDT05GSUdfRVJST1InLCBtZXNzYWdlOiAnTm90aW9uIEFQSSB0b2tlbiBpcyBub3QgY29uZmlndXJlZC4nIH0gfTtcbiAgaWYgKCFwYXJhbXMubm90aW9uVGFza3NEYklkICYmICFBVE9NX05PVElPTl9UQVNLU19EQVRBQkFTRV9JRCkge1xuICAgICAgcmV0dXJuIHsgb2s6IGZhbHNlLCBlcnJvcjogeyBjb2RlOiAnQ09ORklHX0VSUk9SJywgbWVzc2FnZTogJ05vdGlvbiBUYXNrcyBEYXRhYmFzZSBJRCBpcyBub3QgY29uZmlndXJlZC4nfX07XG4gIH1cblxuICB0cnkge1xuICAgIGNvbnN0IHBheWxvYWQgPSB7XG4gICAgICAuLi5wYXJhbXMsIC8vIGRlc2NyaXB0aW9uLCBkdWVEYXRlLCBzdGF0dXMsIHByaW9yaXR5LCBsaXN0TmFtZSwgbm90ZXNcbiAgICAgIHVzZXJfaWQ6IHVzZXJJZCxcbiAgICAgIG5vdGlvbl9hcGlfdG9rZW46IG5vdGlvbkFwaUtleSxcbiAgICAgIG5vdGlvbl9kYl9pZDogcGFyYW1zLm5vdGlvblRhc2tzRGJJZCB8fCBBVE9NX05PVElPTl9UQVNLU19EQVRBQkFTRV9JRFxuICAgIH07XG5cbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGF4aW9zLnBvc3Q8UHl0aG9uQXBpUmVzcG9uc2U8Q3JlYXRlVGFza0RhdGE+PihcbiAgICAgIGAke1BZVEhPTl9OT1RFX0FQSV9VUkx9L2NyZWF0ZS1ub3Rpb24tdGFza2AsXG4gICAgICBwYXlsb2FkXG4gICAgKTtcbiAgICByZXR1cm4gaGFuZGxlUHl0aG9uQXBpUmVzcG9uc2UocmVzcG9uc2UuZGF0YSwgJ0NyZWF0ZU5vdGlvblRhc2snKTtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGNvbnN0IGF4aW9zRXJyb3IgPSBlcnJvciBhcyBBeGlvc0Vycm9yO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiBheGlvc0Vycm9yLmlzQXhpb3NFcnJvciA/IGBIVFRQXyR7YXhpb3NFcnJvci5yZXNwb25zZT8uc3RhdHVzIHx8ICdORVRXT1JLX0VSUk9SJ31gIDogJ1NLSUxMX0lOVEVSTkFMX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogYEZhaWxlZCB0byBjcmVhdGUgTm90aW9uIHRhc2s6ICR7YXhpb3NFcnJvci5tZXNzYWdlfWAsXG4gICAgICAgIGRldGFpbHM6IGF4aW9zRXJyb3IucmVzcG9uc2U/LmRhdGEgfHwgYXhpb3NFcnJvci5tZXNzYWdlLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBxdWVyeU5vdGlvblRhc2tzKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgcGFyYW1zOiBRdWVyeU5vdGlvblRhc2tzUGFyYW1zXG4pOiBQcm9taXNlPFRhc2tRdWVyeVJlc3BvbnNlPiB7IC8vIERpcmVjdCB1c2Ugb2YgVGFza1F1ZXJ5UmVzcG9uc2VcbiAgY29uc3Qgbm90aW9uQXBpS2V5ID0gYXdhaXQgZ2V0Tm90aW9uQXBpS2V5KHVzZXJJZCk7XG4gIGlmICghUFlUSE9OX05PVEVfQVBJX1VSTCkgcmV0dXJuIHsgc3VjY2VzczogZmFsc2UsIHRhc2tzOiBbXSwgZXJyb3I6ICdQeXRob24gTm90ZSBBUEkgVVJMIGlzIG5vdCBjb25maWd1cmVkLicsIG1lc3NhZ2U6ICdDb25maWd1cmF0aW9uIGVycm9yLicgfTtcbiAgaWYgKCFub3Rpb25BcGlLZXkpIHJldHVybiB7IHN1Y2Nlc3M6IGZhbHNlLCB0YXNrczogW10sIGVycm9yOiAnTm90aW9uIEFQSSB0b2tlbiBpcyBub3QgY29uZmlndXJlZC4nLCBtZXNzYWdlOiAnQ29uZmlndXJhdGlvbiBlcnJvci4nIH07XG4gIGlmICghcGFyYW1zLm5vdGlvblRhc2tzRGJJZCAmJiAhQVRPTV9OT1RJT05fVEFTS1NfREFUQUJBU0VfSUQpIHtcbiAgICAgIHJldHVybiB7IHN1Y2Nlc3M6IGZhbHNlLCB0YXNrczogW10sIGVycm9yOiAnTm90aW9uIFRhc2tzIERhdGFiYXNlIElEIGlzIG5vdCBjb25maWd1cmVkLicsIG1lc3NhZ2U6ICdDb25maWd1cmF0aW9uIGVycm9yLid9O1xuICB9XG5cbiAgdHJ5IHtcbiAgICBjb25zdCBwYXlsb2FkID0ge1xuICAgICAgLi4ucGFyYW1zLFxuICAgICAgdXNlcl9pZDogdXNlcklkLCAvLyBJbmNsdWRlIHVzZXJJZCBmb3IgY29uc2lzdGVuY3ksIFB5dGhvbiBiYWNrZW5kIG1heSBvciBtYXkgbm90IHVzZSBpdCBmb3IgZmlsdGVyaW5nXG4gICAgICBub3Rpb25fYXBpX3Rva2VuOiBub3Rpb25BcGlLZXksXG4gICAgICBub3Rpb25fZGJfaWQ6IHBhcmFtcy5ub3Rpb25UYXNrc0RiSWQgfHwgQVRPTV9OT1RJT05fVEFTS1NfREFUQUJBU0VfSURcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcy5wb3N0PFB5dGhvbkFwaVJlc3BvbnNlPE5vdGlvblRhc2tbXT4+KFxuICAgICAgYCR7UFlUSE9OX05PVEVfQVBJX1VSTH0vcXVlcnktbm90aW9uLXRhc2tzYCxcbiAgICAgIHBheWxvYWRcbiAgICApO1xuXG4gICAgaWYgKHJlc3BvbnNlLmRhdGEub2sgJiYgcmVzcG9uc2UuZGF0YS5kYXRhKSB7XG4gICAgICAgIHJldHVybiB7IHN1Y2Nlc3M6IHRydWUsIHRhc2tzOiByZXNwb25zZS5kYXRhLmRhdGEsIG1lc3NhZ2U6IHJlc3BvbnNlLmRhdGEubWVzc2FnZSB8fCAnVGFza3MgcXVlcmllZCBzdWNjZXNzZnVsbHkuJyB9O1xuICAgIH0gZWxzZSBpZiAocmVzcG9uc2UuZGF0YS5lcnJvcikge1xuICAgICAgICByZXR1cm4geyBzdWNjZXNzOiBmYWxzZSwgdGFza3M6IFtdLCBlcnJvcjogcmVzcG9uc2UuZGF0YS5lcnJvci5tZXNzYWdlLCBtZXNzYWdlOiByZXNwb25zZS5kYXRhLmVycm9yLmRldGFpbHMgYXMgc3RyaW5nfHVuZGVmaW5lZCB9O1xuICAgIH1cbiAgICByZXR1cm4geyBzdWNjZXNzOiBmYWxzZSwgdGFza3M6IFtdLCBlcnJvcjogJ1VuZXhwZWN0ZWQgcmVzcG9uc2UgZnJvbSBxdWVyeU5vdGlvblRhc2tzIGJhY2tlbmQuJywgbWVzc2FnZTogJ0JhY2tlbmQgY29tbXVuaWNhdGlvbiBlcnJvci4nfTtcblxuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgY29uc3QgYXhpb3NFcnJvciA9IGVycm9yIGFzIEF4aW9zRXJyb3I7XG4gICAgY29uc29sZS5lcnJvcihgRmFpbGVkIHRvIHF1ZXJ5IE5vdGlvbiB0YXNrczogJHtheGlvc0Vycm9yLm1lc3NhZ2V9YCwgYXhpb3NFcnJvci5yZXNwb25zZT8uZGF0YSB8fCBheGlvc0Vycm9yLm1lc3NhZ2UpO1xuICAgIHJldHVybiB7XG4gICAgICBzdWNjZXNzOiBmYWxzZSxcbiAgICAgIHRhc2tzOiBbXSxcbiAgICAgIGVycm9yOiBgRmFpbGVkIHRvIHF1ZXJ5IE5vdGlvbiB0YXNrczogJHtheGlvc0Vycm9yLm1lc3NhZ2V9YCxcbiAgICB9O1xuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiB1cGRhdGVOb3Rpb25UYXNrKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgcGFyYW1zOiBVcGRhdGVOb3Rpb25UYXNrUGFyYW1zXG4pOiBQcm9taXNlPFNraWxsUmVzcG9uc2U8VXBkYXRlVGFza0RhdGE+PiB7XG4gIGNvbnN0IG5vdGlvbkFwaUtleSA9IGF3YWl0IGdldE5vdGlvbkFwaUtleSh1c2VySWQpO1xuICBpZiAoIVBZVEhPTl9OT1RFX0FQSV9VUkwpIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHsgY29kZTogJ0NPTkZJR19FUlJPUicsIG1lc3NhZ2U6ICdQeXRob24gTm90ZSBBUEkgVVJMIGlzIG5vdCBjb25maWd1cmVkLicgfSB9O1xuICBpZiAoIW5vdGlvbkFwaUtleSkgcmV0dXJuIHsgb2s6IGZhbHNlLCBlcnJvcjogeyBjb2RlOiAnQ09ORklHX0VSUk9SJywgbWVzc2FnZTogJ05vdGlvbiBBUEkgdG9rZW4gaXMgbm90IGNvbmZpZ3VyZWQuJyB9IH07XG4gIGlmICghcGFyYW1zLnRhc2tJZCkgcmV0dXJuIHsgb2s6IGZhbHNlLCBlcnJvcjogeyBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsIG1lc3NhZ2U6ICdUYXNrIElEICh0YXNrSWQpIGlzIHJlcXVpcmVkIGZvciB1cGRhdGUuJyB9fTtcblxuICB0cnkge1xuICAgIGNvbnN0IHBheWxvYWQgPSB7XG4gICAgICAuLi5wYXJhbXMsXG4gICAgICB1c2VyX2lkOiB1c2VySWQsXG4gICAgICBub3Rpb25fYXBpX3Rva2VuOiBub3Rpb25BcGlLZXlcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcy5wb3N0PFB5dGhvbkFwaVJlc3BvbnNlPFVwZGF0ZVRhc2tEYXRhPj4oXG4gICAgICBgJHtQWVRIT05fTk9URV9BUElfVVJMfS91cGRhdGUtbm90aW9uLXRhc2tgLFxuICAgICAgcGF5bG9hZFxuICAgICk7XG4gICAgcmV0dXJuIGhhbmRsZVB5dGhvbkFwaVJlc3BvbnNlKHJlc3BvbnNlLmRhdGEsICdVcGRhdGVOb3Rpb25UYXNrJyk7XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBjb25zdCBheGlvc0Vycm9yID0gZXJyb3IgYXMgQXhpb3NFcnJvcjtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogYXhpb3NFcnJvci5pc0F4aW9zRXJyb3IgPyBgSFRUUF8ke2F4aW9zRXJyb3IucmVzcG9uc2U/LnN0YXR1cyB8fCAnTkVUV09SS19FUlJPUid9YCA6ICdTS0lMTF9JTlRFUk5BTF9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IGBGYWlsZWQgdG8gdXBkYXRlIE5vdGlvbiB0YXNrOiAke2F4aW9zRXJyb3IubWVzc2FnZX1gLFxuICAgICAgICBkZXRhaWxzOiBheGlvc0Vycm9yLnJlc3BvbnNlPy5kYXRhIHx8IGF4aW9zRXJyb3IubWVzc2FnZSxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufVxuXG4vKipcbiAqIFNlYXJjaGVzIGZvciBOb3Rpb24gbm90ZXMgc2ltaWxhciB0byBhIGdpdmVuIHF1ZXJ5IHRleHQgdXNpbmcgdmVjdG9yIHNpbWlsYXJpdHkuXG4gKlxuICogQHBhcmFtIHVzZXJJZCBUaGUgSUQgb2YgdGhlIHVzZXIgcGVyZm9ybWluZyB0aGUgc2VhcmNoICh0byBzY29wZSByZXN1bHRzKS5cbiAqIEBwYXJhbSBxdWVyeVRleHQgVGhlIG5hdHVyYWwgbGFuZ3VhZ2UgdGV4dCB0byBzZWFyY2ggZm9yLlxuICogQHBhcmFtIGxpbWl0IE9wdGlvbmFsLiBUaGUgbWF4aW11bSBudW1iZXIgb2Ygc2ltaWxhciBub3RlcyB0byByZXR1cm4uXG4gKiBAcmV0dXJucyBBIHByb21pc2UgdGhhdCByZXNvbHZlcyB0byBhIFNraWxsUmVzcG9uc2UgY29udGFpbmluZyBhbiBhcnJheSBvZiBzaW1pbGFyIE5vdGlvbiBub3Rlcy5cbiAqL1xuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHNlYXJjaFNpbWlsYXJOb3Rpb25Ob3RlcyhcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHF1ZXJ5VGV4dDogc3RyaW5nLFxuICBsaW1pdD86IG51bWJlclxuKTogUHJvbWlzZTxTa2lsbFJlc3BvbnNlPE5vdGlvblNpbWlsYXJOb3RlUmVzdWx0W10+PiB7XG4gIGlmICghUFlUSE9OX05PVEVfQVBJX1VSTCkge1xuICAgIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHsgY29kZTogJ0NPTkZJR19FUlJPUicsIG1lc3NhZ2U6ICdQeXRob24gTm90ZSBBUEkgVVJMIGlzIG5vdCBjb25maWd1cmVkLicgfSB9O1xuICB9XG4gIGlmICghT1BFTkFJX0FQSV9LRVkpIHsgLy8gT3BlbkFJIEFQSSBrZXkgaXMgbmVlZGVkIGJ5IHRoZSBQeXRob24gZW5kcG9pbnQgZm9yIGVtYmVkZGluZyB0aGUgcXVlcnlcbiAgICByZXR1cm4geyBvazogZmFsc2UsIGVycm9yOiB7IGNvZGU6ICdDT05GSUdfRVJST1InLCBtZXNzYWdlOiAnT3BlbkFJIEFQSSBrZXkgaXMgbm90IGNvbmZpZ3VyZWQgZm9yIHNpbWlsYXJpdHkgc2VhcmNoLicgfSB9O1xuICB9XG4gIGlmICghdXNlcklkKSB7IC8vIHVzZXJfaWQgaXMgY3J1Y2lhbCBmb3IgZmlsdGVyaW5nIHJlc3VsdHMgaW4gTGFuY2VEQlxuICAgICAgcmV0dXJuIHsgb2s6IGZhbHNlLCBlcnJvcjogeyBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsIG1lc3NhZ2U6ICdVc2VyIElEIGlzIHJlcXVpcmVkIGZvciBzZWFyY2hpbmcgc2ltaWxhciBub3Rlcy4nfX07XG4gIH1cbiAgIGlmICghcXVlcnlUZXh0IHx8IHF1ZXJ5VGV4dC50cmltKCkgPT09IFwiXCIpIHtcbiAgICByZXR1cm4geyBvazogZmFsc2UsIGVycm9yOiB7IGNvZGU6ICdWQUxJREFUSU9OX0VSUk9SJywgbWVzc2FnZTogJ1F1ZXJ5IHRleHQgY2Fubm90IGJlIGVtcHR5IGZvciBzaW1pbGFyaXR5IHNlYXJjaC4nIH0gfTtcbiAgfVxuXG4gIHRyeSB7XG4gICAgY29uc3QgcGF5bG9hZCA9IHtcbiAgICAgIHF1ZXJ5X3RleHQ6IHF1ZXJ5VGV4dCxcbiAgICAgIHVzZXJfaWQ6IHVzZXJJZCxcbiAgICAgIG9wZW5haV9hcGlfa2V5OiBPUEVOQUlfQVBJX0tFWSwgLy8gUHl0aG9uIHNlcnZpY2Ugd2lsbCB1c2UgdGhpcyB0byBlbWJlZCB0aGUgcXVlcnlfdGV4dFxuICAgICAgbGltaXQ6IGxpbWl0IHx8IDUsIC8vIERlZmF1bHQgdG8gNSBpZiBub3QgcHJvdmlkZWRcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcy5wb3N0PFB5dGhvbkFwaVJlc3BvbnNlPE5vdGlvblNpbWlsYXJOb3RlUmVzdWx0W10+PihcbiAgICAgIGAke1BZVEhPTl9OT1RFX0FQSV9VUkx9L3NlYXJjaC1zaW1pbGFyLW5vdGVzYCxcbiAgICAgIHBheWxvYWRcbiAgICApO1xuICAgIHJldHVybiBoYW5kbGVQeXRob25BcGlSZXNwb25zZShyZXNwb25zZS5kYXRhLCAnU2VhcmNoU2ltaWxhck5vdGlvbk5vdGVzJyk7XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBjb25zdCBheGlvc0Vycm9yID0gZXJyb3IgYXMgQXhpb3NFcnJvcjtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogYXhpb3NFcnJvci5pc0F4aW9zRXJyb3IgPyBgSFRUUF8ke2F4aW9zRXJyb3IucmVzcG9uc2U/LnN0YXR1cyB8fCAnTkVUV09SS19FUlJPUid9YCA6ICdTS0lMTF9JTlRFUk5BTF9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IGBGYWlsZWQgdG8gc2VhcmNoIGZvciBzaW1pbGFyIE5vdGlvbiBub3RlczogJHtheGlvc0Vycm9yLm1lc3NhZ2V9YCxcbiAgICAgICAgZGV0YWlsczogYXhpb3NFcnJvci5yZXNwb25zZT8uZGF0YSB8fCBheGlvc0Vycm9yLm1lc3NhZ2UsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHByb2Nlc3NSZXNlYXJjaFF1ZXVlKFxuICB1c2VySWQ6IHN0cmluZyAvLyBDb250ZXh0dWFsLCBQeXRob24gc2VydmljZSBkb2Vzbid0IHN0cmljdGx5IG5lZWQgaXQgaWYga2V5cyBhcmUgZ2xvYmFsIHRoZXJlXG4pOiBQcm9taXNlPFNraWxsUmVzcG9uc2U8UHJvY2Vzc1Jlc2VhcmNoUXVldWVEYXRhPj4ge1xuICBjb25zdCBub3Rpb25BcGlLZXkgPSBhd2FpdCBnZXROb3Rpb25BcGlLZXkodXNlcklkKTtcbiAgaWYgKCFQWVRIT05fUkVTRUFSQ0hfQVBJX1VSTCkgcmV0dXJuIHsgb2s6IGZhbHNlLCBlcnJvcjogeyBjb2RlOiAnQ09ORklHX0VSUk9SJywgbWVzc2FnZTogJ1B5dGhvbiBSZXNlYXJjaCBBUEkgVVJMIGlzIG5vdCBjb25maWd1cmVkLicgfSB9O1xuICBpZiAoIW5vdGlvbkFwaUtleSkgcmV0dXJuIHsgb2s6IGZhbHNlLCBlcnJvcjogeyBjb2RlOiAnQ09ORklHX0VSUk9SJywgbWVzc2FnZTogJ05vdGlvbiBBUEkgdG9rZW4gaXMgbm90IGNvbmZpZ3VyZWQuJyB9IH07XG4gIGlmICghT1BFTkFJX0FQSV9LRVkpIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHsgY29kZTogJ0NPTkZJR19FUlJPUicsIG1lc3NhZ2U6ICdPcGVuQUkgQVBJIGtleSBpcyBub3QgY29uZmlndXJlZC4nIH0gfTtcbiAgaWYgKCFBVE9NX1NFUlBBUElfQVBJX0tFWSkgcmV0dXJuIHsgb2s6IGZhbHNlLCBlcnJvcjogeyBjb2RlOiAnQ09ORklHX0VSUk9SJywgbWVzc2FnZTogJ1NlcnBBcGkgQVBJIGtleSBpcyBub3QgY29uZmlndXJlZC4nIH0gfTtcbiAgaWYgKCFOT1RJT05fUkVTRUFSQ0hfUFJPSkVDVFNfREJfSUQpIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHsgY29kZTogJ0NPTkZJR19FUlJPUicsIG1lc3NhZ2U6ICdOb3Rpb24gUmVzZWFyY2ggUHJvamVjdHMgREIgSUQgaXMgbm90IGNvbmZpZ3VyZWQuJyB9IH07XG4gIGlmICghTk9USU9OX1JFU0VBUkNIX1RBU0tTX0RCX0lEKSByZXR1cm4geyBvazogZmFsc2UsIGVycm9yOiB7IGNvZGU6ICdDT05GSUdfRVJST1InLCBtZXNzYWdlOiAnTm90aW9uIFJlc2VhcmNoIFRhc2tzIERCIElEIGlzIG5vdCBjb25maWd1cmVkLicgfSB9O1xuXG4gIHRyeSB7XG4gICAgY29uc3QgcGF5bG9hZCA9IHtcbiAgICAgIHVzZXJfaWQ6IHVzZXJJZCwgLy8gUGFzcyB1c2VySWQgZm9yIGNvbnRleHQgaWYgUHl0aG9uIHNlcnZpY2UgdXNlcyBpdFxuICAgICAgcmVzZWFyY2hfZGJfaWQ6IE5PVElPTl9SRVNFQVJDSF9QUk9KRUNUU19EQl9JRCxcbiAgICAgIHRhc2tfZGJfaWQ6IE5PVElPTl9SRVNFQVJDSF9UQVNLU19EQl9JRCxcbiAgICAgIG5vdGlvbl9hcGlfdG9rZW46IG5vdGlvbkFwaUtleSxcbiAgICAgIG9wZW5haV9hcGlfa2V5OiBPUEVOQUlfQVBJX0tFWSxcbiAgICAgIHNlYXJjaF9hcGlfa2V5OiBBVE9NX1NFUlBBUElfQVBJX0tFWSxcbiAgICB9O1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MucG9zdDxQeXRob25BcGlSZXNwb25zZTxQcm9jZXNzUmVzZWFyY2hRdWV1ZURhdGE+PihcbiAgICAgIGAke1BZVEhPTl9SRVNFQVJDSF9BUElfVVJMfS9wcm9jZXNzLXJlc2VhcmNoLXF1ZXVlYCxcbiAgICAgIHBheWxvYWRcbiAgICApO1xuICAgIHJldHVybiBoYW5kbGVQeXRob25BcGlSZXNwb25zZShyZXNwb25zZS5kYXRhLCAnUmVzZWFyY2hRdWV1ZVByb2Nlc3NpbmcnKTtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGNvbnN0IGF4aW9zRXJyb3IgPSBlcnJvciBhcyBBeGlvc0Vycm9yO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiBheGlvc0Vycm9yLmlzQXhpb3NFcnJvciA/IGBIVFRQXyR7YXhpb3NFcnJvci5yZXNwb25zZT8uc3RhdHVzIHx8ICdORVRXT1JLX0VSUk9SJ31gIDogJ1NLSUxMX0lOVEVSTkFMX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogYEZhaWxlZCB0byBwcm9jZXNzIHJlc2VhcmNoIHF1ZXVlOiAke2F4aW9zRXJyb3IubWVzc2FnZX1gLFxuICAgICAgICBkZXRhaWxzOiBheGlvc0Vycm9yLnJlc3BvbnNlPy5kYXRhIHx8IGF4aW9zRXJyb3IubWVzc2FnZSxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufVxuXG4vLyBIZWxwZXIgdG8gbWFwIE5vdGlvblNlYXJjaFJlc3VsdERhdGEgdG8gTm90aW9uUGFnZVN1bW1hcnlcbmZ1bmN0aW9uIG1hcE5vdGlvblNlYXJjaFJlc3VsdFRvUGFnZVN1bW1hcnkoc2VhcmNoUmVzdWx0OiBOb3Rpb25TZWFyY2hSZXN1bHREYXRhKTogTm90aW9uUGFnZVN1bW1hcnkge1xuICAvLyBBc3N1bWluZyBQeXRob24gYmFja2VuZCBtaWdodCBwYXNzIHRocm91Z2ggbW9yZSBmaWVsZHMgdGhhbiBkZWZpbmVkIGluIE5vdGlvblNlYXJjaFJlc3VsdERhdGFcbiAgY29uc3QgdW5rbm93blByb3BzID0gc2VhcmNoUmVzdWx0IGFzIGFueTtcbiAgcmV0dXJuIHtcbiAgICBpZDogc2VhcmNoUmVzdWx0LmlkLFxuICAgIHRpdGxlOiBzZWFyY2hSZXN1bHQudGl0bGUsXG4gICAgdXJsOiBzZWFyY2hSZXN1bHQudXJsLFxuICAgIHByZXZpZXdfdGV4dDogc2VhcmNoUmVzdWx0LmNvbnRlbnQsIC8vIE1hcCAnY29udGVudCcgdG8gJ3ByZXZpZXdfdGV4dCdcbiAgICAvLyBUaW1lc3RhbXBzIGFuZCBpY29uIHdvdWxkIGlkZWFsbHkgY29tZSBmcm9tIHRoZSBiYWNrZW5kIGlmIGF2YWlsYWJsZVxuICAgIGxhc3RfZWRpdGVkX3RpbWU6IHVua25vd25Qcm9wcy5sYXN0X2VkaXRlZF90aW1lIHx8IHVua25vd25Qcm9wcy5wcm9wZXJ0aWVzPy5sYXN0X2VkaXRlZF90aW1lPy5sYXN0X2VkaXRlZF90aW1lIHx8IHVuZGVmaW5lZCxcbiAgICBjcmVhdGVkX3RpbWU6IHVua25vd25Qcm9wcy5jcmVhdGVkX3RpbWUgfHwgdW5rbm93blByb3BzLnByb3BlcnRpZXM/LmNyZWF0ZWRfdGltZT8uY3JlYXRlZF90aW1lIHx8IHVuZGVmaW5lZCxcbiAgICBpY29uOiB1bmtub3duUHJvcHMuaWNvbiB8fCB1bmRlZmluZWQsIC8vIEFzc3VtaW5nIGljb24gc3RydWN0dXJlIG1hdGNoZXMgTm90aW9uUGFnZVN1bW1hcnkncyBpY29uIHR5cGVcbiAgfTtcbn1cblxuLyoqXG4gKiBQbGFjZWhvbGRlciBmb3IgZmV0Y2hpbmcgZGV0YWlsZWQgc3VtbWFyeSBvZiBhIHNwZWNpZmljIE5vdGlvbiBwYWdlIGJ5IGl0cyBJRC5cbiAqIFRoaXMgd291bGQgY2FsbCBhIFB5dGhvbiBiYWNrZW5kIGVuZHBvaW50IChlLmcuLCAvZ2V0LW5vdGlvbi1wYWdlLXN1bW1hcnkpLlxuICogVGhlIFB5dGhvbiBiYWNrZW5kIHdvdWxkIHVzZSBOb3Rpb24gQVBJIHRvIGdldCBwYWdlIGRldGFpbHMgYW5kIGZvcm1hdCB0aGVtLlxuICogQHBhcmFtIHVzZXJJZCBUaGUgSUQgb2YgdGhlIHVzZXIuXG4gKiBAcGFyYW0gcGFnZUlkIFRoZSBJRCBvZiB0aGUgTm90aW9uIHBhZ2UuXG4gKiBAcmV0dXJucyBBIHByb21pc2UgdGhhdCByZXNvbHZlcyB0byBhIFNraWxsUmVzcG9uc2UgY29udGFpbmluZyB0aGUgTm90aW9uUGFnZVN1bW1hcnkuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXROb3Rpb25QYWdlU3VtbWFyeUJ5SWQoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBwYWdlSWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxTa2lsbFJlc3BvbnNlPE5vdGlvblBhZ2VTdW1tYXJ5Pj4geyAvLyBBc3N1bWluZyBOb3Rpb25QYWdlU3VtbWFyeSBpcyBkZWZpbmVkIGluIHR5cGVzXG4gIGNvbnN0IG5vdGlvbkFwaUtleSA9IGF3YWl0IGdldE5vdGlvbkFwaUtleSh1c2VySWQpO1xuICBsb2dnZXIuaW5mbyhgW2dldE5vdGlvblBhZ2VTdW1tYXJ5QnlJZF0gQ2FsbGVkIGZvciB1c2VySWQ6ICR7dXNlcklkfSwgcGFnZUlkOiAke3BhZ2VJZH1gKTtcbiAgaWYgKCFQWVRIT05fTk9URV9BUElfVVJMKSByZXR1cm4geyBvazogZmFsc2UsIGVycm9yOiB7IGNvZGU6ICdDT05GSUdfRVJST1InLCBtZXNzYWdlOiAnUHl0aG9uIE5vdGUgQVBJIFVSTCBpcyBub3QgY29uZmlndXJlZC4nIH0gfTtcbiAgaWYgKCFub3Rpb25BcGlLZXkpIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHsgY29kZTogJ0NPTkZJR19FUlJPUicsIG1lc3NhZ2U6ICdOb3Rpb24gQVBJIHRva2VuIGlzIG5vdCBjb25maWd1cmVkLicgfSB9O1xuICBpZiAoIXBhZ2VJZCkgcmV0dXJuIHsgb2s6IGZhbHNlLCBlcnJvcjogeyBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsIG1lc3NhZ2U6ICdQYWdlIElEIGlzIHJlcXVpcmVkLid9fTtcblxuICAvLyBUaGlzIGlzIGEgcGxhY2Vob2xkZXIuIEluIGEgcmVhbCBpbXBsZW1lbnRhdGlvbjpcbiAgLy8gMS4gRGVmaW5lIGEgUHl0aG9uIGVuZHBvaW50IChlLmcuLCBHRVQgL2dldC1ub3Rpb24tcGFnZS1zdW1tYXJ5LzpwYWdlX2lkKVxuICAvLyAyLiBQeXRob24gZW5kcG9pbnQgdXNlcyBOb3Rpb24gQVBJIHRvIGZldGNoIHBhZ2UgcHJvcGVydGllcyBhbmQgY29udGVudCBibG9jayBzdW1tYXJpZXMuXG4gIC8vIDMuIFB5dGhvbiBlbmRwb2ludCBmb3JtYXRzIHRoaXMgaW50byBhIHN0cnVjdHVyZSBtYXRjaGluZyBOb3Rpb25QYWdlU3VtbWFyeS5cbiAgLy8gNC4gQ2FsbCB0aGF0IGVuZHBvaW50IGhlcmUgdXNpbmcgYXhpb3MuXG5cbiAgbG9nZ2VyLndhcm4oYFtnZXROb3Rpb25QYWdlU3VtbWFyeUJ5SWRdIFRoaXMgZnVuY3Rpb24gaXMgYSBwbGFjZWhvbGRlciBhbmQgZG9lcyBub3QgY2FsbCBhIHJlYWwgYmFja2VuZCB5ZXQuYCk7XG4gIC8vIE1vY2sgcmVzcG9uc2UgZm9yIG5vdzpcbiAgLy8gcmV0dXJuIFByb21pc2UucmVzb2x2ZSh7XG4gIC8vICAgb2s6IGZhbHNlLFxuICAvLyAgIGVycm9yOiB7IGNvZGU6ICdOT1RfSU1QTEVNRU5URUQnLCBtZXNzYWdlOiAnZ2V0Tm90aW9uUGFnZVN1bW1hcnlCeUlkIGlzIG5vdCBpbXBsZW1lbnRlZCB5ZXQuJ31cbiAgLy8gfSk7XG5cbiAgLy8gRm9yIHRlc3Rpbmcgc21hcnRNZWV0aW5nUHJlcFNraWxsLCBsZXQncyByZXR1cm4gYSBtb2NrIHN1Y2Nlc3MgaWYgYSBrbm93biBJRCBpcyBwYXNzZWQuXG4gIGlmIChwYWdlSWQgPT09IFwibW9jay1wYWdlLWlkLWZyb20tZGVzY3JpcHRpb25cIikge1xuICAgIHJldHVybiBQcm9taXNlLnJlc29sdmUoe1xuICAgICAgb2s6IHRydWUsXG4gICAgICBkYXRhOiB7XG4gICAgICAgIGlkOiBwYWdlSWQsXG4gICAgICAgIHRpdGxlOiBcIk1vY2tlZCBQYWdlIGZyb20gRGVzY3JpcHRpb25cIixcbiAgICAgICAgdXJsOiBgaHR0cHM6Ly93d3cubm90aW9uLnNvLyR7cGFnZUlkfWAsXG4gICAgICAgIHByZXZpZXdfdGV4dDogXCJUaGlzIGlzIGEgbW9jayBzdW1tYXJ5IGZvciBhIHBhZ2UgZXhwbGljaXRseSBsaW5rZWQgaW4gYSBtZWV0aW5nIGRlc2NyaXB0aW9uLi4uXCIsXG4gICAgICAgIGxhc3RfZWRpdGVkX3RpbWU6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgY3JlYXRlZF90aW1lOiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgIC8vIGljb246IHsgdHlwZTogXCJlbW9qaVwiLCBlbW9qaTogXCLwn5OEXCIgfVxuICAgICAgfVxuICAgIH0pO1xuICB9XG5cbiAgcmV0dXJuIFByb21pc2UucmVzb2x2ZSh7XG4gICAgb2s6IGZhbHNlLFxuICAgIGVycm9yOiB7IGNvZGU6ICdOT1RfRk9VTkRfT1JfTk9UX0lNUExFTUVOVEVEJywgbWVzc2FnZTogYFBhZ2UgJHtwYWdlSWR9IG5vdCBmb3VuZCAob3IgZmVhdHVyZSBub3QgZnVsbHkgaW1wbGVtZW50ZWQpLmAgfVxuICB9KTtcbn1cblxuXG4vLyAtLS0gTm90ZS1UYWtpbmcgU2tpbGxzIC0tLVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gY3JlYXRlTm90aW9uTm90ZShcbiAgdXNlcklkOiBzdHJpbmcsIC8vIEZvciBwb3RlbnRpYWwgbG9nZ2luZyBvciBpZiBQeXRob24gc2VydmljZSB1c2VzIGl0XG4gIHRpdGxlOiBzdHJpbmcsXG4gIGNvbnRlbnQ6IHN0cmluZyxcbiAgbm90aW9uRGJJZD86IHN0cmluZyAvLyBPcHRpb25hbDogaWYgbm90IHByb3ZpZGVkLCBQeXRob24gdXNlcyBpdHMgZGVmYXVsdFxuKTogUHJvbWlzZTxTa2lsbFJlc3BvbnNlPENyZWF0ZU5vdGVEYXRhPj4ge1xuICBjb25zdCBub3Rpb25BcGlLZXkgPSBhd2FpdCBnZXROb3Rpb25BcGlLZXkodXNlcklkKTtcbiAgaWYgKCFQWVRIT05fTk9URV9BUElfVVJMKSByZXR1cm4geyBvazogZmFsc2UsIGVycm9yOiB7IGNvZGU6ICdDT05GSUdfRVJST1InLCBtZXNzYWdlOiAnUHl0aG9uIE5vdGUgQVBJIFVSTCBpcyBub3QgY29uZmlndXJlZC4nIH0gfTtcbiAgaWYgKCFub3Rpb25BcGlLZXkpIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHsgY29kZTogJ0NPTkZJR19FUlJPUicsIG1lc3NhZ2U6ICdOb3Rpb24gQVBJIHRva2VuIGlzIG5vdCBjb25maWd1cmVkLicgfSB9O1xuXG4gIHRyeSB7XG4gICAgY29uc3QgcGF5bG9hZDogYW55ID0ge1xuICAgICAgdGl0bGUsXG4gICAgICBjb250ZW50LFxuICAgICAgdXNlcl9pZDogdXNlcklkLFxuICAgICAgbm90aW9uX2FwaV90b2tlbjogbm90aW9uQXBpS2V5LFxuICAgIH07XG4gICAgaWYgKG5vdGlvbkRiSWQpIHBheWxvYWQubm90aW9uX2RiX2lkID0gbm90aW9uRGJJZDtcbiAgICBlbHNlIGlmIChOT1RJT05fTk9URVNfREFUQUJBU0VfSUQpIHBheWxvYWQubm90aW9uX2RiX2lkID0gTk9USU9OX05PVEVTX0RBVEFCQVNFX0lEOyAvLyBVc2UgZGVmYXVsdCBpZiBhdmFpbGFibGVcblxuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MucG9zdDxQeXRob25BcGlSZXNwb25zZTxDcmVhdGVOb3RlRGF0YT4+KFxuICAgICAgYCR7UFlUSE9OX05PVEVfQVBJX1VSTH0vY3JlYXRlLW5vdGVgLFxuICAgICAgcGF5bG9hZFxuICAgICk7XG4gICAgcmV0dXJuIGhhbmRsZVB5dGhvbkFwaVJlc3BvbnNlKHJlc3BvbnNlLmRhdGEsICdDcmVhdGVOb3Rpb25Ob3RlJyk7XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBjb25zdCBheGlvc0Vycm9yID0gZXJyb3IgYXMgQXhpb3NFcnJvcjtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogYXhpb3NFcnJvci5pc0F4aW9zRXJyb3IgPyBgSFRUUF8ke2F4aW9zRXJyb3IucmVzcG9uc2U/LnN0YXR1cyB8fCAnTkVUV09SS19FUlJPUid9YCA6ICdTS0lMTF9JTlRFUk5BTF9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IGBGYWlsZWQgdG8gY3JlYXRlIE5vdGlvbiBub3RlOiAke2F4aW9zRXJyb3IubWVzc2FnZX1gLFxuICAgICAgICBkZXRhaWxzOiBheGlvc0Vycm9yLnJlc3BvbnNlPy5kYXRhIHx8IGF4aW9zRXJyb3IubWVzc2FnZSxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gY3JlYXRlQXVkaW9Ob3RlRnJvbVVybChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGF1ZGlvVXJsOiBzdHJpbmcsXG4gIHRpdGxlOiBzdHJpbmcsXG4gIG5vdGlvbkRiSWQ/OiBzdHJpbmcsXG4gIG5vdGlvblNvdXJjZT86IHN0cmluZyxcbiAgbGlua2VkRXZlbnRJZD86IHN0cmluZ1xuKTogUHJvbWlzZTxTa2lsbFJlc3BvbnNlPENyZWF0ZU5vdGVEYXRhPj4ge1xuICBjb25zdCBub3Rpb25BcGlLZXkgPSBhd2FpdCBnZXROb3Rpb25BcGlLZXkodXNlcklkKTtcbiAgaWYgKCFQWVRIT05fTk9URV9BUElfVVJMKSByZXR1cm4geyBvazogZmFsc2UsIGVycm9yOiB7IGNvZGU6ICdDT05GSUdfRVJST1InLCBtZXNzYWdlOiAnUHl0aG9uIE5vdGUgQVBJIFVSTCBpcyBub3QgY29uZmlndXJlZC4nIH0gfTtcbiAgaWYgKCFub3Rpb25BcGlLZXkpIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHsgY29kZTogJ0NPTkZJR19FUlJPUicsIG1lc3NhZ2U6ICdOb3Rpb24gQVBJIHRva2VuIGlzIG5vdCBjb25maWd1cmVkLicgfSB9O1xuICBpZiAoIURFRVBHUkFNX0FQSV9LRVkpIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHsgY29kZTogJ0NPTkZJR19FUlJPUicsIG1lc3NhZ2U6ICdEZWVwZ3JhbSBBUEkga2V5IGlzIG5vdCBjb25maWd1cmVkLicgfSB9O1xuICBpZiAoIU9QRU5BSV9BUElfS0VZKSByZXR1cm4geyBvazogZmFsc2UsIGVycm9yOiB7IGNvZGU6ICdDT05GSUdfRVJST1InLCBtZXNzYWdlOiAnT3BlbkFJIEFQSSBrZXkgaXMgbm90IGNvbmZpZ3VyZWQuJyB9IH07XG5cbiAgdHJ5IHtcbiAgICBjb25zdCBwYXlsb2FkOiBhbnkgPSB7XG4gICAgICBhdWRpb191cmw6IGF1ZGlvVXJsLFxuICAgICAgdGl0bGUsXG4gICAgICB1c2VyX2lkOiB1c2VySWQsXG4gICAgICBub3Rpb25fYXBpX3Rva2VuOiBub3Rpb25BcGlLZXksXG4gICAgICBkZWVwZ3JhbV9hcGlfa2V5OiBERUVQR1JBTV9BUElfS0VZLFxuICAgICAgb3BlbmFpX2FwaV9rZXk6IE9QRU5BSV9BUElfS0VZLFxuICAgIH07XG4gICAgaWYgKG5vdGlvbkRiSWQpIHBheWxvYWQubm90aW9uX2RiX2lkID0gbm90aW9uRGJJZDtcbiAgICBlbHNlIGlmIChOT1RJT05fTk9URVNfREFUQUJBU0VfSUQpIHBheWxvYWQubm90aW9uX2RiX2lkID0gTk9USU9OX05PVEVTX0RBVEFCQVNFX0lEO1xuICAgIGlmIChub3Rpb25Tb3VyY2UpIHBheWxvYWQubm90aW9uX3NvdXJjZSA9IG5vdGlvblNvdXJjZTtcbiAgICBpZiAobGlua2VkRXZlbnRJZCkgcGF5bG9hZC5saW5rZWRfZXZlbnRfaWQgPSBsaW5rZWRFdmVudElkO1xuXG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcy5wb3N0PFB5dGhvbkFwaVJlc3BvbnNlPENyZWF0ZU5vdGVEYXRhPj4oXG4gICAgICBgJHtQWVRIT05fTk9URV9BUElfVVJMfS9jcmVhdGUtYXVkaW8tbm90ZS11cmxgLFxuICAgICAgcGF5bG9hZFxuICAgICk7XG4gICAgcmV0dXJuIGhhbmRsZVB5dGhvbkFwaVJlc3BvbnNlKHJlc3BvbnNlLmRhdGEsICdDcmVhdGVBdWRpb05vdGUnKTtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGNvbnN0IGF4aW9zRXJyb3IgPSBlcnJvciBhcyBBeGlvc0Vycm9yO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiBheGlvc0Vycm9yLmlzQXhpb3NFcnJvciA/IGBIVFRQXyR7YXhpb3NFcnJvci5yZXNwb25zZT8uc3RhdHVzIHx8ICdORVRXT1JLX0VSUk9SJ31gIDogJ1NLSUxMX0lOVEVSTkFMX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogYEZhaWxlZCB0byBjcmVhdGUgYXVkaW8gbm90ZSBmcm9tIFVSTDogJHtheGlvc0Vycm9yLm1lc3NhZ2V9YCxcbiAgICAgICAgZGV0YWlsczogYXhpb3NFcnJvci5yZXNwb25zZT8uZGF0YSB8fCBheGlvc0Vycm9yLm1lc3NhZ2UsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHNlYXJjaE5vdGlvbk5vdGVzKFxuICB1c2VySWQ6IHN0cmluZywgLy8gRm9yIGNvbnRleHQvbG9nZ2luZ1xuICBxdWVyeVRleHQ6IHN0cmluZyxcbiAgbm90aW9uRGJJZD86IHN0cmluZyxcbiAgc291cmNlPzogc3RyaW5nIC8vIE9wdGlvbmFsIGZpbHRlciBieSAnU291cmNlJyBwcm9wZXJ0eVxuKTogUHJvbWlzZTxTa2lsbFJlc3BvbnNlPE5vdGlvblBhZ2VTdW1tYXJ5W10+PiB7IC8vIENoYW5nZWQgcmV0dXJuIHR5cGVcbiAgY29uc3Qgbm90aW9uQXBpS2V5ID0gYXdhaXQgZ2V0Tm90aW9uQXBpS2V5KHVzZXJJZCk7XG4gIGlmICghUFlUSE9OX05PVEVfQVBJX1VSTCkgcmV0dXJuIHsgb2s6IGZhbHNlLCBlcnJvcjogeyBjb2RlOiAnQ09ORklHX0VSUk9SJywgbWVzc2FnZTogJ1B5dGhvbiBOb3RlIEFQSSBVUkwgaXMgbm90IGNvbmZpZ3VyZWQuJyB9IH07XG4gIGlmICghbm90aW9uQXBpS2V5KSByZXR1cm4geyBvazogZmFsc2UsIGVycm9yOiB7IGNvZGU6ICdDT05GSUdfRVJST1InLCBtZXNzYWdlOiAnTm90aW9uIEFQSSB0b2tlbiBpcyBub3QgY29uZmlndXJlZC4nIH0gfTtcblxuICB0cnkge1xuICAgIGNvbnN0IHBheWxvYWQ6IGFueSA9IHtcbiAgICAgIHF1ZXJ5X3RleHQ6IHF1ZXJ5VGV4dCxcbiAgICAgIHVzZXJfaWQ6IHVzZXJJZCxcbiAgICAgIG5vdGlvbl9hcGlfdG9rZW46IG5vdGlvbkFwaUtleSxcbiAgICB9O1xuICAgIGlmIChub3Rpb25EYklkKSBwYXlsb2FkLm5vdGlvbl9kYl9pZCA9IG5vdGlvbkRiSWQ7XG4gICAgZWxzZSBpZiAoTk9USU9OX05PVEVTX0RBVEFCQVNFX0lEKSBwYXlsb2FkLm5vdGlvbl9kYl9pZCA9IE5PVElPTl9OT1RFU19EQVRBQkFTRV9JRDtcbiAgICBpZiAoc291cmNlKSBwYXlsb2FkLnNvdXJjZSA9IHNvdXJjZTtcblxuXG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcy5wb3N0PFB5dGhvbkFwaVJlc3BvbnNlPE5vdGlvblNlYXJjaFJlc3VsdERhdGFbXT4+KFxuICAgICAgYCR7UFlUSE9OX05PVEVfQVBJX1VSTH0vc2VhcmNoLW5vdGVzYCxcbiAgICAgIHBheWxvYWRcbiAgICApO1xuXG4gICAgLy8gVXNlIGhhbmRsZVB5dGhvbkFwaVJlc3BvbnNlIGFuZCB0aGVuIG1hcCB0aGUgcmVzdWx0c1xuICAgIGNvbnN0IHB5dGhvblJlc3BvbnNlID0gaGFuZGxlUHl0aG9uQXBpUmVzcG9uc2U8Tm90aW9uU2VhcmNoUmVzdWx0RGF0YVtdPihyZXNwb25zZS5kYXRhLCAnU2VhcmNoTm90aW9uTm90ZXMnKTtcbiAgICBpZiAocHl0aG9uUmVzcG9uc2Uub2sgJiYgcHl0aG9uUmVzcG9uc2UuZGF0YSkge1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgb2s6IHRydWUsXG4gICAgICAgIGRhdGE6IHB5dGhvblJlc3BvbnNlLmRhdGEubWFwKG1hcE5vdGlvblNlYXJjaFJlc3VsdFRvUGFnZVN1bW1hcnkpXG4gICAgICB9O1xuICAgIH1cbiAgICByZXR1cm4geyAvLyBFcnJvciBjYXNlIGZyb20gaGFuZGxlUHl0aG9uQXBpUmVzcG9uc2VcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiBweXRob25SZXNwb25zZS5lcnJvclxuICAgIH07XG5cbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGNvbnN0IGF4aW9zRXJyb3IgPSBlcnJvciBhcyBBeGlvc0Vycm9yO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiBheGlvc0Vycm9yLmlzQXhpb3NFcnJvciA/IGBIVFRQXyR7YXhpb3NFcnJvci5yZXNwb25zZT8uc3RhdHVzIHx8ICdORVRXT1JLX0VSUk9SJ31gIDogJ1NLSUxMX0lOVEVSTkFMX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogYEZhaWxlZCB0byBzZWFyY2ggTm90aW9uIG5vdGVzOiAke2F4aW9zRXJyb3IubWVzc2FnZX1gLFxuICAgICAgICBkZXRhaWxzOiBheGlvc0Vycm9yLnJlc3BvbnNlPy5kYXRhIHx8IGF4aW9zRXJyb3IubWVzc2FnZSxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufVxuXG5bZW5kIG9mIGF0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvYXRvbS1hZ2VudC9za2lsbHMvbm90aW9uQW5kUmVzZWFyY2hTa2lsbHMudHNdXG4iXX0=