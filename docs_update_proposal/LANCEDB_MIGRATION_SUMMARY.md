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
        *   `convertTextToVector(text: string)`: Converts search text to an embedding.
        *   `searchEventsInLanceDB(userId, searchVector, startDate?, endDate?, limit?)`: Queries the LanceDB "events" table using vector similarity search (`table.search(vector)`), and filters by `userId` and optionally by `start_date`/`end_date` using SQL `WHERE` clauses.
    *   `service/handler.ts`:
        *   Provides an Express.js-style handler (`eventSearchHandler`).
        *   Takes `userId`, `searchText`, optional `startDate`, `endDate`, `limit`.
        *   Calls `convertTextToVector` and `searchEventsInLanceDB`.
        *   **Crucially, includes a placeholder comment for future AI agent integration** to process LanceDB results and apply event types. Currently, it returns the raw (or slightly formatted) results from LanceDB.
*   **Configuration:** The service endpoint is intended to be configurable (e.g., `NEXT_PUBLIC_LANCE_EVENT_MATCHER_URL`).
*   **Testing:** Unit tests (`handler.test.ts`) were added for `eventSearchHandler`, mocking LanceDB interactions and OpenAI vector conversion, and testing various search scenarios, input validations, and error handling. A test also verifies the presence of the AI integration placeholder comment.

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

## 5. Future AI Integration Notes (for `lance-event-matcher`)

The `lance-event-matcher/service/handler.ts` currently has placeholder comments:
```typescript
// TODO: Process LanceDB results with AI agent to find and apply event types.
// This will involve calling the AI agent's API with the event data
// (e.g., eventsFromDB.map(event => event.raw_event_text))
// and using its response to enrich or modify the event information.
// For example, an AI agent might return an `eventType` for each event.
```
This signifies the next step where an AI agent will consume the events retrieved by `searchEventsInLanceDB` to perform tasks like:
*   Classifying events by type (e.g., "meeting", "focus time", "personal appointment").
*   Extracting key entities or topics.
*   Suggesting actions or providing insights based on event content.

The results from this AI processing will then be used to enrich the event data returned to the client.
