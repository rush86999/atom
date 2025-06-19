import {
    convertTextToVector,
    searchEventsInLanceDB,
    getUserCategories
} from '../_libs/api_helper';
import {
    callAIQueryEnhancer,
    callAIEventProcessor // Assuming this is the correct name from previous subtask (instead of callAIResultsProcessor)
} from '../_libs/ai_helper';
import {
    DEFAULT_SEARCH_LIMIT,
    OPENAI_API_KEY,
    HASURA_ADMIN_SECRET
} from '../_libs/constants';
import {
    SearchRequest,
    // SearchResponse, // Superseded by LanceEventMatcherResponse
    EventRecord,
    CategoryType,
    AIProcessedEvent,
    AIQueryEnhancementResult,
    LanceEventMatcherResponse, // New standardized response type
    SkillError // Standardized error type
} from '../_libs/types';

// This is a simplified Express-like handler structure.
// In a real Express app, this function would be wrapped by an Express route handler
// which would then call res.status().json() or res.send().
// For this refactor, the handler itself will return the standardized response object.

// interface MockExpressRequest { // Kept for context, but not used by the refactored function directly
//   body: SearchRequest;
//   query: Partial<SearchRequest>;
// }

// interface MockExpressResponse { // Kept for context
//   status: (code: number) => MockExpressResponse;
//   json: (body: LanceEventMatcherResponse<AIProcessedEvent[]> | { error: SkillError }) => void;
//   send: (body: string) => void;
// }

export async function eventSearchHandler(
  // Instead of req, res, it now takes the SearchRequest directly for easier testing and portability
  searchRequestBody: SearchRequest
): Promise<LanceEventMatcherResponse<AIProcessedEvent[]>> {
  try {
    const {
      userId,
      searchText,
      startDate: requestStartDate,
      endDate: requestEndDate,
      limit = DEFAULT_SEARCH_LIMIT,
    } = searchRequestBody;

    // --- Basic Input Validation ---
    if (!userId) {
      return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Missing required parameter: userId' } };
    }
    if (!searchText) {
      return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Missing required parameter: searchText' } };
    }
    if (typeof searchText !== 'string' || searchText.trim().length === 0) {
      return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Parameter searchText must be a non-empty string.' } };
    }
    if (limit && (typeof limit !== 'number' || limit <= 0)) {
      return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Parameter limit must be a positive number.' } };
    }
    // TODO: Add date format validation if necessary for requestStartDate, requestEndDate

    // --- Fetch API Keys and User Categories ---
    const openAIApiKey = OPENAI_API_KEY;
    const hasuraAdminSecret = HASURA_ADMIN_SECRET;

    if (!openAIApiKey || openAIApiKey === 'your-default-openai-api-key' || !openAIApiKey.startsWith('sk-')) {
        console.error('OpenAI API Key is not configured or is invalid.');
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Service configuration error: OpenAI API Key missing or invalid.' } };
    }
    if (!hasuraAdminSecret || hasuraAdminSecret === 'your-hasura-admin-secret') {
        console.error('Hasura Admin Secret is not configured.');
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Service configuration error: Hasura Admin Secret missing.' } };
    }

    let userCategories: CategoryType[] = [];
    try {
      userCategories = await getUserCategories(userId, hasuraAdminSecret);
    } catch (error: any) {
      console.warn(`Failed to fetch user categories for userId ${userId}: ${error.message}. Proceeding without them.`);
      // Non-critical for the main flow, AI prompts can handle empty category lists.
    }

    const userMessageHistory = undefined; // Placeholder

    // --- Pre-Query AI Processing (Step 1) ---
    let queryEnhancementResult: AIQueryEnhancementResult;
    try {
      queryEnhancementResult = await callAIQueryEnhancer(searchText, userCategories, openAIApiKey, userMessageHistory);
    } catch (error: any) {
      console.error('Error calling AIQueryEnhancer:', error);
      return { ok: false, error: { code: 'AI_QUERY_ENHANCER_ERROR', message: 'Failed to enhance search query with AI.', details: error.message } };
    }

    // --- Vectorization (Step 2a) ---
    let searchVector;
    try {
        searchVector = await convertTextToVector(queryEnhancementResult.refinedQueryText);
        if (!searchVector || searchVector.length === 0) {
            throw new Error("Vectorization resulted in an empty vector.");
        }
    } catch (error: any) {
        console.error('Error converting refined text to vector:', error);
        return { ok: false, error: { code: 'VECTORIZATION_ERROR', message: 'Failed to process search query for vectorization.', details: error.message } };
    }

    // --- LanceDB Search (Step 2b) ---
    const determinedStartDate = requestStartDate || queryEnhancementResult.identifiedDateRange?.start;
    const determinedEndDate = requestEndDate || queryEnhancementResult.identifiedDateRange?.end;

    let lanceDBEvents: EventRecord[];
    try {
      lanceDBEvents = await searchEventsInLanceDB(
        userId, searchVector, determinedStartDate, determinedEndDate, limit
      );
    } catch (error: any) {
      console.error('Error searching events in LanceDB:', error);
      // This could be a connection error or a search execution error.
      return { ok: false, error: { code: 'LANCEDB_SEARCH_ERROR', message: 'Failed to retrieve events from LanceDB.', details: error.message } };
    }

    // --- Post-Query AI Processing (Step 3) ---
    if (lanceDBEvents.length === 0) {
      return { ok: true, data: [] }; // No events found is a successful empty search
    }

    let processedEvents: AIProcessedEvent[];
    try {
      processedEvents = await callAIEventProcessor(
        lanceDBEvents, searchText, userCategories, openAIApiKey, userMessageHistory
      );
    } catch (error: any) {
      console.error('Error processing LanceDB results with AI:', error);
      return { ok: false, error: { code: 'AI_EVENT_PROCESSOR_ERROR', message: 'Failed to process search results with AI.', details: error.message } };
    }

    // --- Return Results (Step 4) ---
    return { ok: true, data: processedEvents };

  } catch (error: any) { // Catch-all for unexpected errors in the handler itself
    console.error('Critical unexpected error in eventSearchHandler:', error);
    return { ok: false, error: { code: 'INTERNAL_SERVER_ERROR', message: 'An unexpected critical error occurred.', details: error.message } };
  }
}

// Example of how this might be used in a simple server setup (conceptual)
/*
import express from 'express';
const app = express();
app.use(express.json());

app.post('/search-events', (req, res) => {
    eventSearchHandler(
        req as unknown as MockExpressRequest, // Cast for compatibility
        res as unknown as MockExpressResponse // Cast for compatibility
    );
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Lance Event Matcher service running on port ${PORT}`);
});
*/
