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
    SearchResponse,
    EventRecord,
    CategoryType,
    AIProcessedEvent,
    AIQueryEnhancementResult
} from '../_libs/types';

// This is a simplified Express-like handler structure.
// In a real Express app, you would use `(req: Request, res: Response) => { ... }`
// and app.post('/search', eventSearchHandler);

interface MockExpressRequest {
  body: SearchRequest;
  query: Partial<SearchRequest>; // For GET requests if params are in query
}

interface MockExpressResponse {
  status: (code: number) => MockExpressResponse;
  json: (body: SearchResponse | { error: string }) => void;
  send: (body: string) => void;
}

export async function eventSearchHandler(
  req: MockExpressRequest, // Using mock Express request type
  res: MockExpressResponse  // Using mock Express response type
): Promise<void> {
  try {
    const {
      userId,
      searchText,
      startDate: requestStartDate, // Renaming to avoid conflict
      endDate: requestEndDate,   // Renaming to avoid conflict
      limit = DEFAULT_SEARCH_LIMIT,
    } = req.body;

    // --- Basic Input Validation ---
    if (!userId) {
      res.status(400).json({ error: 'Missing required parameter: userId' });
      return;
    }
    if (!searchText) {
      res.status(400).json({ error: 'Missing required parameter: searchText' });
      return;
    }
    if (typeof searchText !== 'string' || searchText.trim().length === 0) {
      res.status(400).json({ error: 'Parameter searchText must be a non-empty string.' });
      return;
    }
    if (limit && (typeof limit !== 'number' || limit <= 0)) {
      res.status(400).json({ error: 'Parameter limit must be a positive number.' });
      return;
    }
    // Add date format validation if necessary for requestStartDate, requestEndDate

    // --- Fetch API Keys and User Categories ---
    const openAIApiKey = OPENAI_API_KEY; // From constants
    const hasuraAdminSecret = HASURA_ADMIN_SECRET; // From constants

    if (!openAIApiKey || openAIApiKey === 'your-default-openai-api-key') {
        console.error('OpenAI API Key is not configured.');
        res.status(500).json({ error: 'Service configuration error: OpenAI API Key missing.' });
        return;
    }
    if (!hasuraAdminSecret || hasuraAdminSecret === 'your-hasura-admin-secret') {
        console.error('Hasura Admin Secret is not configured.');
        res.status(500).json({ error: 'Service configuration error: Hasura Admin Secret missing.' });
        return;
    }

    let userCategories: CategoryType[] = [];
    try {
      userCategories = await getUserCategories(userId, hasuraAdminSecret);
    } catch (error) {
      console.warn(`Failed to fetch user categories for userId ${userId}: ${error.message}. Proceeding without them.`);
      // Non-critical, AI prompts can handle empty category lists.
    }

    // --- (Placeholder for User Message History) ---
    // const userMessageHistory = await fetchUserMessageHistory(userId); // Example
    const userMessageHistory = undefined; // For now

    // --- Pre-Query AI Processing (Step 1) ---
    let queryEnhancementResult: AIQueryEnhancementResult;
    try {
      queryEnhancementResult = await callAIQueryEnhancer(searchText, userCategories, openAIApiKey, userMessageHistory);
    } catch (error) {
      console.error('Error calling AIQueryEnhancer:', error);
      res.status(500).json({ error: 'Failed to enhance search query with AI.' });
      return;
    }

    // --- LanceDB Search (Step 2 - Adjusted) ---
    let searchVector;
    try {
        searchVector = await convertTextToVector(queryEnhancementResult.refinedQueryText);
    } catch (error) {
        console.error('Error converting refined text to vector:', error);
        res.status(500).json({ error: 'Failed to process search query for vectorization.' });
        return;
    }

    // Determine startDate and endDate for the search
    const determinedStartDate = requestStartDate || queryEnhancementResult.identifiedDateRange?.start;
    const determinedEndDate = requestEndDate || queryEnhancementResult.identifiedDateRange?.end;

    let lanceDBEvents: EventRecord[];
    try {
      lanceDBEvents = await searchEventsInLanceDB(
        userId,
        searchVector,
        determinedStartDate,
        determinedEndDate,
        limit
      );
    } catch (error) {
      console.error('Error searching events in LanceDB:', error);
      res.status(500).json({ error: 'Failed to retrieve events from database.' });
      return;
    }

    // --- Post-Query AI Processing (Step 3) ---
    if (lanceDBEvents.length === 0) {
      // @ts-ignore SearchResponse expects EventRecord[], AIProcessedEvent[] is more specific
      res.status(200).json({ success: true, data: [] });
      return;
    }

    let processedEvents: AIProcessedEvent[];
    try {
      // Using original searchText for context to the AI event processor, along with refined query.
      processedEvents = await callAIEventProcessor(
        lanceDBEvents,
        searchText, // Original user query
        userCategories,
        openAIApiKey,
        userMessageHistory
      );
    } catch (error) {
      console.error('Error processing LanceDB results with AI:', error);
      res.status(500).json({ error: 'Failed to process search results with AI.' });
      return;
    }

    // --- Return Results (Step 4) ---
    // @ts-ignore SearchResponse expects EventRecord[], AIProcessedEvent[] is more specific
    res.status(200).json({ success: true, data: processedEvents });

  } catch (error) {
    console.error('Critical error in eventSearchHandler:', error);
    // Catch-all for unexpected errors
    if (!res.headersSent) { // Check if response has already been sent
        res.status(500).json({ error: 'An unexpected critical error occurred.' });
    }
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
