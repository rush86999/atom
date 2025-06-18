# LanceDB Migration & Event Search Overhaul Summary

## 1. Introduction

This document summarizes the migration from OpenSearch to LanceDB for vector storage and the corresponding overhaul of the event search/matching functionality. The primary goals were to simplify the vector database infrastructure, leverage LanceDB's capabilities, and pave the way for more advanced AI-driven event processing.

## 2. Key Changes

### 2.1. Data Ingestion and Vector Storage (`google-calendar-sync`)

*   **OpenSearch Removal:** The `_event2VectorsWorker_` within the `google-calendar-sync` function no longer interacts with OpenSearch.
*   **LanceDB Integration:**
    *   A new `lancedb_helper.ts` was introduced in `google-calendar-sync/_libs/`.
    *   This helper manages connections to a LanceDB database (path defaults to `/data/lancedb`).
    *   It defines a schema for an "events" table:
        *   `id`: STRING (Primary key: `eventId#calendarId`)
        *   `userId`: STRING
        *   `vector`: VECTOR (dimension 1536 for OpenAI `text-embedding-3-small`)
        *   `start_date`: STRING (ISO 8601)
        *   `end_date`: STRING (ISO 8601)
        *   `raw_event_text`: STRING (Summary + Description)
    *   The worker now:
        *   Generates vector embeddings for events using OpenAI's `text-embedding-3-small` model via `convertEventTitleToOpenAIVector`.
        *   Upserts event data (including the vector, user ID, start/end dates, and raw text) into the LanceDB "events" table using a `bulkUpsertToLanceDBEvents` function (which performs a delete-then-add for existing IDs).
        *   Deletes event data from the LanceDB "events" table using `bulkDeleteFromLanceDBEvents` when events are removed from the primary database.
*   **Dependencies:** Conceptually, `vectordb` (LanceDB client) is now a dependency for `google-calendar-sync`.
*   **Testing:** Unit tests (`index.test.ts`) were added for `event2VectorBody` to verify interactions with mocked LanceDB helper functions.

### 2.2. New `lance-event-matcher` Service

*   **Purpose:** A new dedicated service for event matching and retrieval, designed for AI agent integration.
*   **Directory:** `atomic-docker/project/functions/lance-event-matcher/`
*   **Core Components:**
    *   `_libs/constants.ts`: Defines paths, table names, OpenAI model details.
    *   `_libs/types.ts`: Defines `EventRecord`, `SearchRequest`, `SearchResponse` interfaces.
    *   `_libs/lancedb_connect.ts`: Provides `getEventTable()` for connecting to the "events" table in LanceDB.
    *   `_libs/api_helper.ts`:
        *   `getUserCategories(userId, hasuraAdminSecret)`: Fetches user-defined event categories from Hasura.
        *   `convertTextToVector(text: string)`: Converts search text to an embedding.
        *   `searchEventsInLanceDB(userId, searchVector, startDate?, endDate?, limit?)`: Queries the LanceDB "events" table.
    *   `_libs/ai_helper.ts`:
        *   `callAIQueryEnhancer(userQuery, userCategories, openAIApiKey, userMessageHistory?)`: The first AI stage. Takes the user's raw query, categories, and optional message history to produce a refined query text, suggest relevant category IDs, and identify date intentions.
        *   `callAIEventProcessor(events, userQuery, userCategories, openAIApiKey, userMessageHistory?)`: The second AI stage. Takes events retrieved from LanceDB, the original user query, user categories, and optional message history to filter events, assign a final category, and add a relevance score.
    *   `service/handler.ts` (`eventSearchHandler`):
        *   Orchestrates the multi-step process:
            1.  Fetches API keys (OpenAI, Hasura).
            2.  Calls `getUserCategories`.
            3.  Calls `callAIQueryEnhancer` to process the initial `searchText`.
            4.  Uses the `refinedQueryText` from the enhancer to call `convertTextToVector`.
            5.  Determines search dates, prioritizing client-provided dates over AI-identified dates.
            6.  Calls `searchEventsInLanceDB`.
            7.  If events are found, calls `callAIEventProcessor` to further refine and categorize them.
            8.  Returns the AI-processed events.
        *   Includes robust error handling for each step.
*   **Configuration:** The service endpoint is intended to be configurable (e.g., `NEXT_PUBLIC_LANCE_EVENT_MATCHER_URL`).
*   **Testing:** Unit tests (`handler.test.ts`) were updated to mock the new AI helper functions and `getUserCategories`. Tests cover the full workflow, date prioritization, error handling for AI and API calls, and API key configuration issues.

### 2.3. Decommissioning of `events-search` Service

*   **OpenSearch Logic Removed:**
    *   All OpenSearch-specific functions (client setup, index management, CRUD, search) were deleted from `events-search/_libs/api-helper.ts`. OpenAI utility functions were retained.
    *   OpenSearch-related constants and type imports were removed from this helper file.
*   **API Endpoints Updated:**
    *   Both `events-search/eventsSearch/events-search-admin.ts` and `events-search/eventsSearch/events-search-auth.ts` were gutted.
    *   The main `opensearch` handler function in both files now returns an **HTTP 410 (Gone)** status with a JSON message:
        `{ message: 'This OpenSearch event search service is deprecated and no longer operational. Please use the new LanceDB-based event matching service.' }`
    *   Unused imports (like `dayjs`) were removed from these handler files.

## 3. Client-Side Updates (`app_build_docker`)

*   **Constants Update:**
    *   Added `lanceEventMatcherUrl` to `app_build_docker/lib/constants.ts` for the new service.
*   **Event Deletion Flow (`UserViewCalendarWeb.tsx`):**
    *   In the `deleteEvent` function, the `axios.post` calls to `methodToSearchIndexAuthUrl` (which previously interacted with the `events-search` OpenSearch service for index deletion) were **removed**.
    *   This change reflects that vector index cleanup is now implicitly handled by the `_event2VectorsWorker_` when it processes event deletion messages from Kafka. The frontend no longer needs to trigger index deletions directly.
*   **"Search & Apply Features" (Unaffected for now):** The existing `featuresApplyToEventsAuthUrl` call in `UserViewCalendarWeb.tsx` was **not modified** in this phase. It may still point to older infrastructure or require separate refactoring to use the new `lance-event-matcher`.

## 4. Impact & Benefits

*   **Simplified Vector DB:** LanceDB offers a more lightweight, embedded solution compared to managing a separate OpenSearch cluster.
*   **Modernized Search:** The new `lance-event-matcher` provides a clean, focused service for vector search.
*   **Clear Deprecation:** The old `events-search` service is clearly marked as deprecated, preventing further use.
*   **Foundation for AI:** The `lance-event-matcher` is designed with future AI agent integration in mind, allowing for more intelligent event processing beyond simple similarity search.

## 5. AI Integration Details in `lance-event-matcher`

The `lance-event-matcher` service now implements a two-stage AI processing workflow:

*   **Stage 1: Pre-Query AI Enhancement (`callAIQueryEnhancer`)**
    *   **Input:** Takes the user's original search query, a list of the user's predefined event categories (fetched from Hasura via `getUserCategories`), the OpenAI API key, and an optional user message history (currently deferred for history fetching/passing).
    *   **Processing:** An LLM analyzes these inputs to:
        *   Refine the original query into a concise search phrase optimized for semantic vector search.
        *   Suggest potentially relevant category IDs from the user's list.
        *   Identify any specific dates or date ranges implied in the query or history (e.g., "next Tuesday", "events in July").
    *   **Output:** An `AIQueryEnhancementResult` object containing `refinedQueryText`, `suggestedCategoryIds` (optional), and `identifiedDateRange` (optional).

*   **Stage 2: Post-Query AI Results Processing (`callAIEventProcessor`)**
    *   **Input:** Takes the list of `EventRecord` objects retrieved from LanceDB (based on the `refinedQueryText`), the original user query, the user's categories, the OpenAI API key, and optional user message history.
    *   **Processing:** An LLM processes these inputs to:
        *   Filter the retrieved events for relevance against the user's original intent and the refined query context.
        *   Assign a single, most relevant category ID (from the user's list) to each pertinent event.
        *   Provide a `relevanceScore` (0.0 to 1.0) for each event.
    *   **Output:** An array of `AIProcessedEvent` objects, each containing `eventId`, `assignedCategoryId`, and `relevanceScore`. Events deemed irrelevant by the AI are excluded.

**User Message History:**
While both AI processing stages are designed to accept `userMessageHistory` for richer contextual understanding, the actual fetching and passing of this history from the client/frontend to the `lance-event-matcher` service is currently deferred. This means the AI functions will operate based on the immediate query and user categories. Future enhancements can focus on integrating this history.

This two-stage AI approach allows for more sophisticated query understanding and results processing, aiming to deliver more relevant and accurately categorized events to the user.
