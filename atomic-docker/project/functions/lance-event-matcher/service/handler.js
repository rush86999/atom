import { convertTextToVector, searchEventsInLanceDB, getUserCategories, } from '../_libs/api_helper';
import { callAIQueryEnhancer, callAIEventProcessor, // Assuming this is the correct name from previous subtask (instead of callAIResultsProcessor)
 } from '../_libs/ai_helper';
import { DEFAULT_SEARCH_LIMIT, OPENAI_API_KEY, HASURA_ADMIN_SECRET, } from '../_libs/constants';
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
searchRequestBody) {
    try {
        const { userId, searchText, startDate: requestStartDate, endDate: requestEndDate, limit = DEFAULT_SEARCH_LIMIT, } = searchRequestBody;
        // --- Basic Input Validation ---
        if (!userId) {
            return {
                ok: false,
                error: {
                    code: 'VALIDATION_ERROR',
                    message: 'Missing required parameter: userId',
                },
            };
        }
        if (!searchText) {
            return {
                ok: false,
                error: {
                    code: 'VALIDATION_ERROR',
                    message: 'Missing required parameter: searchText',
                },
            };
        }
        if (typeof searchText !== 'string' || searchText.trim().length === 0) {
            return {
                ok: false,
                error: {
                    code: 'VALIDATION_ERROR',
                    message: 'Parameter searchText must be a non-empty string.',
                },
            };
        }
        if (limit && (typeof limit !== 'number' || limit <= 0)) {
            return {
                ok: false,
                error: {
                    code: 'VALIDATION_ERROR',
                    message: 'Parameter limit must be a positive number.',
                },
            };
        }
        // TODO: Add date format validation if necessary for requestStartDate, requestEndDate
        // --- Fetch API Keys and User Categories ---
        const openAIApiKey = OPENAI_API_KEY;
        const hasuraAdminSecret = HASURA_ADMIN_SECRET;
        if (!openAIApiKey ||
            openAIApiKey === 'your-default-openai-api-key' ||
            !openAIApiKey.startsWith('sk-')) {
            console.error('OpenAI API Key is not configured or is invalid.');
            return {
                ok: false,
                error: {
                    code: 'CONFIG_ERROR',
                    message: 'Service configuration error: OpenAI API Key missing or invalid.',
                },
            };
        }
        if (!hasuraAdminSecret ||
            hasuraAdminSecret === 'your-hasura-admin-secret') {
            console.error('Hasura Admin Secret is not configured.');
            return {
                ok: false,
                error: {
                    code: 'CONFIG_ERROR',
                    message: 'Service configuration error: Hasura Admin Secret missing.',
                },
            };
        }
        let userCategories = [];
        try {
            userCategories = await getUserCategories(userId, hasuraAdminSecret);
        }
        catch (error) {
            console.warn(`Failed to fetch user categories for userId ${userId}: ${error.message}. Proceeding without them.`);
            // Non-critical for the main flow, AI prompts can handle empty category lists.
        }
        const userMessageHistory = undefined; // Placeholder
        // --- Pre-Query AI Processing (Step 1) ---
        let queryEnhancementResult;
        try {
            queryEnhancementResult = await callAIQueryEnhancer(searchText, userCategories, openAIApiKey, userMessageHistory);
        }
        catch (error) {
            console.error('Error calling AIQueryEnhancer:', error);
            return {
                ok: false,
                error: {
                    code: 'AI_QUERY_ENHANCER_ERROR',
                    message: 'Failed to enhance search query with AI.',
                    details: error.message,
                },
            };
        }
        // --- Vectorization (Step 2a) ---
        let searchVector;
        try {
            searchVector = await convertTextToVector(queryEnhancementResult.refinedQueryText);
            if (!searchVector || searchVector.length === 0) {
                throw new Error('Vectorization resulted in an empty vector.');
            }
        }
        catch (error) {
            console.error('Error converting refined text to vector:', error);
            return {
                ok: false,
                error: {
                    code: 'VECTORIZATION_ERROR',
                    message: 'Failed to process search query for vectorization.',
                    details: error.message,
                },
            };
        }
        // --- LanceDB Search (Step 2b) ---
        const determinedStartDate = requestStartDate || queryEnhancementResult.identifiedDateRange?.start;
        const determinedEndDate = requestEndDate || queryEnhancementResult.identifiedDateRange?.end;
        let lanceDBEvents;
        try {
            lanceDBEvents = await searchEventsInLanceDB(userId, searchVector, determinedStartDate, determinedEndDate, limit);
        }
        catch (error) {
            console.error('Error searching events in LanceDB:', error);
            // This could be a connection error or a search execution error.
            return {
                ok: false,
                error: {
                    code: 'LANCEDB_SEARCH_ERROR',
                    message: 'Failed to retrieve events from LanceDB.',
                    details: error.message,
                },
            };
        }
        // --- Post-Query AI Processing (Step 3) ---
        if (lanceDBEvents.length === 0) {
            return { ok: true, data: [] }; // No events found is a successful empty search
        }
        let processedEvents;
        try {
            processedEvents = await callAIEventProcessor(lanceDBEvents, searchText, userCategories, openAIApiKey, userMessageHistory);
        }
        catch (error) {
            console.error('Error processing LanceDB results with AI:', error);
            return {
                ok: false,
                error: {
                    code: 'AI_EVENT_PROCESSOR_ERROR',
                    message: 'Failed to process search results with AI.',
                    details: error.message,
                },
            };
        }
        // --- Return Results (Step 4) ---
        return { ok: true, data: processedEvents };
    }
    catch (error) {
        // Catch-all for unexpected errors in the handler itself
        console.error('Critical unexpected error in eventSearchHandler:', error);
        return {
            ok: false,
            error: {
                code: 'INTERNAL_SERVER_ERROR',
                message: 'An unexpected critical error occurred.',
                details: error.message,
            },
        };
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaGFuZGxlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImhhbmRsZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUNMLG1CQUFtQixFQUNuQixxQkFBcUIsRUFDckIsaUJBQWlCLEdBQ2xCLE1BQU0scUJBQXFCLENBQUM7QUFDN0IsT0FBTyxFQUNMLG1CQUFtQixFQUNuQixvQkFBb0IsRUFBRSw4RkFBOEY7RUFDckgsTUFBTSxvQkFBb0IsQ0FBQztBQUM1QixPQUFPLEVBQ0wsb0JBQW9CLEVBQ3BCLGNBQWMsRUFDZCxtQkFBbUIsR0FDcEIsTUFBTSxvQkFBb0IsQ0FBQztBQVk1Qix1REFBdUQ7QUFDdkQsb0ZBQW9GO0FBQ3BGLDJEQUEyRDtBQUMzRCxzRkFBc0Y7QUFFdEYsdUdBQXVHO0FBQ3ZHLHlCQUF5QjtBQUN6QixtQ0FBbUM7QUFDbkMsSUFBSTtBQUVKLHNEQUFzRDtBQUN0RCxtREFBbUQ7QUFDbkQsaUdBQWlHO0FBQ2pHLGtDQUFrQztBQUNsQyxJQUFJO0FBRUosTUFBTSxDQUFDLEtBQUssVUFBVSxrQkFBa0I7QUFDdEMsa0dBQWtHO0FBQ2xHLGlCQUFnQztJQUVoQyxJQUFJLENBQUM7UUFDSCxNQUFNLEVBQ0osTUFBTSxFQUNOLFVBQVUsRUFDVixTQUFTLEVBQUUsZ0JBQWdCLEVBQzNCLE9BQU8sRUFBRSxjQUFjLEVBQ3ZCLEtBQUssR0FBRyxvQkFBb0IsR0FDN0IsR0FBRyxpQkFBaUIsQ0FBQztRQUV0QixpQ0FBaUM7UUFDakMsSUFBSSxDQUFDLE1BQU0sRUFBRSxDQUFDO1lBQ1osT0FBTztnQkFDTCxFQUFFLEVBQUUsS0FBSztnQkFDVCxLQUFLLEVBQUU7b0JBQ0wsSUFBSSxFQUFFLGtCQUFrQjtvQkFDeEIsT0FBTyxFQUFFLG9DQUFvQztpQkFDOUM7YUFDRixDQUFDO1FBQ0osQ0FBQztRQUNELElBQUksQ0FBQyxVQUFVLEVBQUUsQ0FBQztZQUNoQixPQUFPO2dCQUNMLEVBQUUsRUFBRSxLQUFLO2dCQUNULEtB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Ozs7Ozs7RUFnQkUiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQge1xuICBjb252ZXJ0VGV4dFRvVmVjdG9yLFxuICBzZWFyY2hFdmVudHNJbkxhbmNlREIsXG4gIGdldFVzZXJDYXRlZ29yaWVzLFxufSBmcm9tICcuLi9fbGlicy9hcGlfaGVscGVyJztcbmltcG9ydCB7XG4gIGNhbGxBSVF1ZXJ5RW5oYW5jZXIsXG4gIGNhbGxBSUV2ZW50UHJvY2Vzc29yLCAvLyBBc3N1bWluZyB0aGlzIGlzIHRoZSBjb3JyZWN0IG5hbWUgZnJvbSBwcmV2aW91cyBzdWJ0YXNrIChpbnN0ZWFkIG9mIGNhbGxBSVJlc3VsdHNQcm9jZXNzb3IpXG59IGZyb20gJy4uL19saWJzL2FpX2hlbHBlcic7XG5pbXBvcnQge1xuICBERUZBVUxUX1NFQVJDSF9MSU1JVCxcbiAgT1BFTkFJX0FQSV9LRVksXG4gIEhBU1VSQV9BRE1JTl9TRUNSRVQsXG59IGZyb20gJy4uL19saWJzL2NvbnN0YW50cyc7XG5pbXBvcnQge1xuICBTZWFyY2hSZXF1ZXN0LFxuICAvLyBTZWFyY2hSZXNwb25zZSwgLy8gU3VwZXJzZWRlZCBieSBMYW5jZUV2ZW50TWF0Y2hlclJlc3BvbnNlXG4gIEV2ZW50UmVjb3JkLFxuICBDYXRlZ29yeVR5cGUsXG4gIEFJUHJvY2Vzc2VkRXZlbnQsXG4gIEFJUXVlcnlFbmhhbmNlbWVudFJlc3VsdCxcbiAgTGFuY2VFdmVudE1hdGNoZXJSZXNwb25zZSwgLy8gTmV3IHN0YW5kYXJkaXplZCByZXNwb25zZSB0eXBlXG4gIFNraWxsRXJyb3IsIC8vIFN0YW5kYXJkaXplZCBlcnJvciB0eXBlXG59IGZyb20gJy4uL19saWJzL3R5cGVzJztcblxuLy8gVGhpcyBpcyBhIHNpbXBsaWZpZWQgRXhwcmVzcy1saWtlIGhhbmRsZXIgc3RydWN0dXJlLlxuLy8gSW4gYSByZWFsIEV4cHJlc3MgYXBwLCB0aGlzIGZ1bmN0aW9uIHdvdWxkIGJlIHdyYXBwZWQgYnkgYW4gRXhwcmVzcyByb3V0ZSBoYW5kbGVyXG4vLyB3aGljaCB3b3VsZCB0aGVuIGNhbGwgcmVzLnN0YXR1cygpLmpzb24oKSBvciByZXMuc2VuZCgpLlxuLy8gRm9yIHRoaXMgcmVmYWN0b3IsIHRoZSBoYW5kbGVyIGl0c2VsZiB3aWxsIHJldHVybiB0aGUgc3RhbmRhcmRpemVkIHJlc3BvbnNlIG9iamVjdC5cblxuLy8gaW50ZXJmYWNlIE1vY2tFeHByZXNzUmVxdWVzdCB7IC8vIEtlcHQgZm9yIGNvbnRleHQsIGJ1dCBub3QgdXNlZCBieSB0aGUgcmVmYWN0b3JlZCBmdW5jdGlvbiBkaXJlY3RseVxuLy8gICBib2R5OiBTZWFyY2hSZXF1ZXN0O1xuLy8gICBxdWVyeTogUGFydGlhbDxTZWFyY2hSZXF1ZXN0Pjtcbi8vIH1cblxuLy8gaW50ZXJmYWNlIE1vY2tFeHByZXNzUmVzcG9uc2UgeyAvLyBLZXB0IGZvciBjb250ZXh0XG4vLyAgIHN0YXR1czogKGNvZGU6IG51bWJlcikgPT4gTW9ja0V4cHJlc3NSZXNwb25zZTtcbi8vICAganNvbjogKGJvZHk6IExhbmNlRXZlbnRNYXRjaGVyUmVzcG9uc2U8QUlQcm9jZXNzZWRFdmVudFtdPiB8IHsgZXJyb3I6IFNraWxsRXJyb3IgfSkgPT4gdm9pZDtcbi8vICAgc2VuZDogKGJvZHk6IHN0cmluZykgPT4gdm9pZDtcbi8vIH1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGV2ZW50U2VhcmNoSGFuZGxlcihcbiAgLy8gSW5zdGVhZCBvZiByZXEsIHJlcywgaXQgbm93IHRha2VzIHRoZSBTZWFyY2hSZXF1ZXN0IGRpcmVjdGx5IGZvciBlYXNpZXIgdGVzdGluZyBhbmQgcG9ydGFiaWxpdHlcbiAgc2VhcmNoUmVxdWVzdEJvZHk6IFNlYXJjaFJlcXVlc3Rcbik6IFByb21pc2U8TGFuY2VFdmVudE1hdGNoZXJSZXNwb25zZTxBSVByb2Nlc3NlZEV2ZW50W10+PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qge1xuICAgICAgdXNlcklkLFxuICAgICAgc2VhcmNoVGV4dCxcbiAgICAgIHN0YXJ0RGF0ZTogcmVxdWVzdFN0YXJ0RGF0ZSxcbiAgICAgIGVuZERhdGU6IHJlcXVlc3RFbmREYXRlLFxuICAgICAgbGltaXQgPSBERUZBVUxUX1NFQVJDSF9MSU1JVCxcbiAgICB9ID0gc2VhcmNoUmVxdWVzdEJvZHk7XG5cbiAgICAvLyAtLS0gQmFzaWMgSW5wdXQgVmFsaWRhdGlvbiAtLS1cbiAgICBpZiAoIXVzZXJJZCkge1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICBlcnJvcjoge1xuICAgICAgICAgIGNvZGU6ICdWQUxJREFUSU9OX0VSUk9SJyxcbiAgICAgICAgICBtZXNzYWdlOiAnTWlzc2luZyByZXF1aXJlZCBwYXJhbWV0ZXI6IHVzZXJJZCcsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH1cbiAgICBpZiAoIXNlYXJjaFRleHQpIHtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsXG4gICAgICAgICAgbWVzc2FnZTogJ01pc3NpbmcgcmVxdWlyZWQgcGFyYW1ldGVyOiBzZWFyY2hUZXh0JyxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgfVxuICAgIGlmICh0eXBlb2Ygc2VhcmNoVGV4dCAhPT0gJ3N0cmluZycgfHwgc2VhcmNoVGV4dC50cmltKCkubGVuZ3RoID09PSAwKSB7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLFxuICAgICAgICAgIG1lc3NhZ2U6ICdQYXJhbWV0ZXIgc2VhcmNoVGV4dCBtdXN0IGJlIGEgbm9uLWVtcHR5IHN0cmluZy4nLFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICB9XG4gICAgaWYgKGxpbWl0ICYmICh0eXBlb2YgbGltaXQgIT09ICdudW1iZXInIHx8IGxpbWl0IDw9IDApKSB7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLFxuICAgICAgICAgIG1lc3NhZ2U6ICdQYXJhbWV0ZXIgbGltaXQgbXVzdCBiZSBhIHBvc2l0aXZlIG51bWJlci4nLFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICB9XG4gICAgLy8gVE9ETzogQWRkIGRhdGUgZm9ybWF0IHZhbGlkYXRpb24gaWYgbmVjZXNzYXJ5IGZvciByZXF1ZXN0U3RhcnREYXRlLCByZXF1ZXN0RW5kRGF0ZVxuXG4gICAgLy8gLS0tIEZldGNoIEFQSSBLZXlzIGFuZCBVc2VyIENhdGVnb3JpZXMgLS0tXG4gICAgY29uc3Qgb3BlbkFJQXBpS2V5ID0gT1BFTkFJX0FQSV9LRVk7XG4gICAgY29uc3QgaGFzdXJhQWRtaW5TZWNyZXQgPSBIQVNVUkFfQURNSU5fU0VDUkVUO1xuXG4gICAgaWYgKFxuICAgICAgIW9wZW5BSUFwaUtleSB8fFxuICAgICAgb3BlbkFJQXBpS2V5ID09PSAneW91ci1kZWZhdWx0LW9wZW5haS1hcGkta2V5JyB8fFxuICAgICAgIW9wZW5BSUFwaUtleS5zdGFydHNXaXRoKCdzay0nKVxuICAgICkge1xuICAgICAgY29uc29sZS5lcnJvcignT3BlbkFJIEFQSSBLZXkgaXMgbm90IGNvbmZpZ3VyZWQgb3IgaXMgaW52YWxpZC4nKTtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICBjb2RlOiAnQ09ORklHX0VSUk9SJyxcbiAgICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgICAgJ1NlcnZpY2UgY29uZmlndXJhdGlvbiBlcnJvcjogT3BlbkFJIEFQSSBLZXkgbWlzc2luZyBvciBpbnZhbGlkLicsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH1cbiAgICBpZiAoXG4gICAgICAhaGFzdXJhQWRtaW5TZWNyZXQgfHxcbiAgICAgIGhhc3VyYUFkbWluU2VjcmV0ID09PSAneW91ci1oYXN1cmEtYWRtaW4tc2VjcmV0J1xuICAgICkge1xuICAgICAgY29uc29sZS5lcnJvcignSGFzdXJhIEFkbWluIFNlY3JldCBpcyBub3QgY29uZmlndXJlZC4nKTtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICBjb2RlOiAnQ09ORklHX0VSUk9SJyxcbiAgICAgICAgICBtZXNzYWdlOiAnU2VydmljZSBjb25maWd1cmF0aW9uIGVycm9yOiBIYXN1cmEgQWRtaW4gU2VjcmV0IG1pc3NpbmcuJyxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgbGV0IHVzZXJDYXRlZ29yaWVzOiBDYXRlZ29yeVR5cGVbXSA9IFtdO1xuICAgIHRyeSB7XG4gICAgICB1c2VyQ2F0ZWdvcmllcyA9IGF3YWl0IGdldFVzZXJDYXRlZ29yaWVzKHVzZXJJZCwgaGFzdXJhQWRtaW5TZWNyZXQpO1xuICAgIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgYEZhaWxlZCB0byBmZXRjaCB1c2VyIGNhdGVnb3JpZXMgZm9yIHVzZXJJZCAke3VzZXJJZH06ICR7ZXJyb3IubWVzc2FnZX0uIFByb2NlZWRpbmcgd2l0aG91dCB0aGVtLmBcbiAgICAgICk7XG4gICAgICAvLyBOb24tY3JpdGljYWwgZm9yIHRoZSBtYWluIGZsb3csIEFJIHByb21wdHMgY2FuIGhhbmRsZSBlbXB0eSBjYXRlZ29yeSBsaXN0cy5cbiAgICB9XG5cbiAgICBjb25zdCB1c2VyTWVzc2FnZUhpc3RvcnkgPSB1bmRlZmluZWQ7IC8vIFBsYWNlaG9sZGVyXG5cbiAgICAvLyAtLS0gUHJlLVF1ZXJ5IEFJIFByb2Nlc3NpbmcgKFN0ZXAgMSkgLS0tXG4gICAgbGV0IHF1ZXJ5RW5oYW5jZW1lbnRSZXN1bHQ6IEFJUXVlcnlFbmhhbmNlbWVudFJlc3VsdDtcbiAgICB0cnkge1xuICAgICAgcXVlcnlFbmhhbmNlbWVudFJlc3VsdCA9IGF3YWl0IGNhbGxBSVF1ZXJ5RW5oYW5jZXIoXG4gICAgICAgIHNlYXJjaFRleHQsXG4gICAgICAgIHVzZXJDYXRlZ29yaWVzLFxuICAgICAgICBvcGVuQUlBcGlLZXksXG4gICAgICAgIHVzZXJNZXNzYWdlSGlzdG9yeVxuICAgICAgKTtcbiAgICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgICBjb25zb2xlLmVycm9yKCdFcnJvciBjYWxsaW5nIEFJUXVlcnlFbmhhbmNlcjonLCBlcnJvcik7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgY29kZTogJ0FJX1FVRVJZX0VOSEFOQ0VSX0VSUk9SJyxcbiAgICAgICAgICBtZXNzYWdlOiAnRmFpbGVkIHRvIGVuaGFuY2Ugc2VhcmNoIHF1ZXJ5IHdpdGggQUkuJyxcbiAgICAgICAgICBkZXRhaWxzOiBlcnJvci5tZXNzYWdlLFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICB9XG5cbiAgICAvLyAtLS0gVmVjdG9yaXphdGlvbiAoU3RlcCAyYSkgLS0tXG4gICAgbGV0IHNlYXJjaFZlY3RvcjtcbiAgICB0cnkge1xuICAgICAgc2VhcmNoVmVjdG9yID0gYXdhaXQgY29udmVydFRleHRUb1ZlY3RvcihcbiAgICAgICAgcXVlcnlFbmhhbmNlbWVudFJlc3VsdC5yZWZpbmVkUXVlcnlUZXh0XG4gICAgICApO1xuICAgICAgaWYgKCFzZWFyY2hWZWN0b3IgfHwgc2VhcmNoVmVjdG9yLmxlbmd0aCA9PT0gMCkge1xuICAgICAgICB0aHJvdyBuZXcgRXJyb3IoJ1ZlY3Rvcml6YXRpb24gcmVzdWx0ZWQgaW4gYW4gZW1wdHkgdmVjdG9yLicpO1xuICAgICAgfVxuICAgIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICAgIGNvbnNvbGUuZXJyb3IoJ0Vycm9yIGNvbnZlcnRpbmcgcmVmaW5lZCB0ZXh0IHRvIHZlY3RvcjonLCBlcnJvcik7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgY29kZTogJ1ZFQ1RPUklaQVRJT05fRVJST1InLFxuICAgICAgICAgIG1lc3NhZ2U6ICdGYWlsZWQgdG8gcHJvY2VzcyBzZWFyY2ggcXVlcnkgZm9yIHZlY3Rvcml6YXRpb24uJyxcbiAgICAgICAgICBkZXRhaWxzOiBlcnJvci5tZXNzYWdlLFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICB9XG5cbiAgICAvLyAtLS0gTGFuY2VEQiBTZWFyY2ggKFN0ZXAgMmIpIC0tLVxuICAgIGNvbnN0IGRldGVybWluZWRTdGFydERhdGUgPVxuICAgICAgcmVxdWVzdFN0YXJ0RGF0ZSB8fCBxdWVyeUVuaGFuY2VtZW50UmVzdWx0LmlkZW50aWZpZWREYXRlUmFuZ2U/LnN0YXJ0O1xuICAgIGNvbnN0IGRldGVybWluZWRFbmREYXRlID1cbiAgICAgIHJlcXVlc3RFbmREYXRlIHx8IHF1ZXJ5RW5oYW5jZW1lbnRSZXN1bHQuaWRlbnRpZmllZERhdGVSYW5nZT8uZW5kO1xuXG4gICAgbGV0IGxhbmNlREJFdmVudHM6IEV2ZW50UmVjb3JkW107XG4gICAgdHJ5IHtcbiAgICAgIGxhbmNlREJFdmVudHMgPSBhd2FpdCBzZWFyY2hFdmVudHNJbkxhbmNlREIoXG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgc2VhcmNoVmVjdG9yLFxuICAgICAgICBkZXRlcm1pbmVkU3RhcnREYXRlLFxuICAgICAgICBkZXRlcm1pbmVkRW5kRGF0ZSxcbiAgICAgICAgbGltaXRcbiAgICAgICk7XG4gICAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgICAgY29uc29sZS5lcnJvcignRXJyb3Igc2VhcmNoaW5nIGV2ZW50cyBpbiBMYW5jZURCOicsIGVycm9yKTtcbiAgICAgIC8vIFRoaXMgY291bGQgYmUgYSBjb25uZWN0aW9uIGVycm9yIG9yIGEgc2VhcmNoIGV4ZWN1dGlvbiBlcnJvci5cbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICBjb2RlOiAnTEFOQ0VEQl9TRUFSQ0hfRVJST1InLFxuICAgICAgICAgIG1lc3NhZ2U6ICdGYWlsZWQgdG8gcmV0cmlldmUgZXZlbnRzIGZyb20gTGFuY2VEQi4nLFxuICAgICAgICAgIGRldGFpbHM6IGVycm9yLm1lc3NhZ2UsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH1cblxuICAgIC8vIC0tLSBQb3N0LVF1ZXJ5IEFJIFByb2Nlc3NpbmcgKFN0ZXAgMykgLS0tXG4gICAgaWYgKGxhbmNlREJFdmVudHMubGVuZ3RoID09PSAwKSB7XG4gICAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogW10gfTsgLy8gTm8gZXZlbnRzIGZvdW5kIGlzIGEgc3VjY2Vzc2Z1bCBlbXB0eSBzZWFyY2hcbiAgICB9XG5cbiAgICBsZXQgcHJvY2Vzc2VkRXZlbnRzOiBBSVByb2Nlc3NlZEV2ZW50W107XG4gICAgdHJ5IHtcbiAgICAgIHByb2Nlc3NlZEV2ZW50cyA9IGF3YWl0IGNhbGxBSUV2ZW50UHJvY2Vzc29yKFxuICAgICAgICBsYW5jZURCRXZlbnRzLFxuICAgICAgICBzZWFyY2hUZXh0LFxuICAgICAgICB1c2VyQ2F0ZWdvcmllcyxcbiAgICAgICAgb3BlbkFJQXBpS2V5LFxuICAgICAgICB1c2VyTWVzc2FnZUhpc3RvcnlcbiAgICAgICk7XG4gICAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgICAgY29uc29sZS5lcnJvcignRXJyb3IgcHJvY2Vzc2luZyBMYW5jZURCIHJlc3VsdHMgd2l0aCBBSTonLCBlcnJvcik7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgY29kZTogJ0FJX0VWRU5UX1BST0NFU1NPUl9FUlJPUicsXG4gICAgICAgICAgbWVzc2FnZTogJ0ZhaWxlZCB0byBwcm9jZXNzIHNlYXJjaCByZXN1bHRzIHdpdGggQUkuJyxcbiAgICAgICAgICBkZXRhaWxzOiBlcnJvci5tZXNzYWdlLFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICB9XG5cbiAgICAvLyAtLS0gUmV0dXJuIFJlc3VsdHMgKFN0ZXAgNCkgLS0tXG4gICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IHByb2Nlc3NlZEV2ZW50cyB9O1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgLy8gQ2F0Y2gtYWxsIGZvciB1bmV4cGVjdGVkIGVycm9ycyBpbiB0aGUgaGFuZGxlciBpdHNlbGZcbiAgICBjb25zb2xlLmVycm9yKCdDcml0aWNhbCB1bmV4cGVjdGVkIGVycm9yIGluIGV2ZW50U2VhcmNoSGFuZGxlcjonLCBlcnJvcik7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdJTlRFUk5BTF9TRVJWRVJfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnQW4gdW5leHBlY3RlZCBjcml0aWNhbCBlcnJvciBvY2N1cnJlZC4nLFxuICAgICAgICBkZXRhaWxzOiBlcnJvci5tZXNzYWdlLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59XG5cbi8vIEV4YW1wbGUgb2YgaG93IHRoaXMgbWlnaHQgYmUgdXNlZCBpbiBhIHNpbXBsZSBzZXJ2ZXIgc2V0dXAgKGNvbmNlcHR1YWwpXG4vKlxuaW1wb3J0IGV4cHJlc3MgZnJvbSAnZXhwcmVzcyc7XG5jb25zdCBhcHAgPSBleHByZXNzKCk7XG5hcHAudXNlKGV4cHJlc3MuanNvbigpKTtcblxuYXBwLnBvc3QoJy9zZWFyY2gtZXZlbnRzJywgKHJlcSwgcmVzKSA9PiB7XG4gICAgZXZlbnRTZWFyY2hIYW5kbGVyKFxuICAgICAgICByZXEgYXMgdW5rbm93biBhcyBNb2NrRXhwcmVzc1JlcXVlc3QsIC8vIENhc3QgZm9yIGNvbXBhdGliaWxpdHlcbiAgICAgICAgcmVzIGFzIHVua25vd24gYXMgTW9ja0V4cHJlc3NSZXNwb25zZSAvLyBDYXN0IGZvciBjb21wYXRpYmlsaXR5XG4gICAgKTtcbn0pO1xuXG5jb25zdCBQT1JUID0gcHJvY2Vzcy5lbnYuUE9SVCB8fCAzMDAwO1xuYXBwLmxpc3RlbihQT1JULCAoKSA9PiB7XG4gIGNvbnNvbGUubG9nKGBMYW5jZSBFdmVudCBNYXRjaGVyIHNlcnZpY2UgcnVubmluZyBvbiBwb3J0ICR7UE9SVH1gKTtcbn0pO1xuKi9cbiJdfQ==