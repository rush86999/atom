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

### 2.4. Shared LanceDB Service (`_utils/lancedb_service.ts`)

To support the migration of multiple services and ensure consistent interaction with LanceDB, a shared utility service was created at `atomic-docker/project/functions/_utils/lancedb_service.ts`.

*   **Purpose:** Provides centralized LanceDB connection management, schema definitions, and generic CRUD (Create, Read, Update, Delete) operations.
*   **Connection Management:** Implements a singleton pattern for LanceDB connections using `vectordb.connect()`. The LanceDB data path defaults to `/data/lancedb`.
*   **Schema Definitions:**
    *   `EventSchema`: For general event data, including `id`, `userId`, `vector`, `start_date`, `end_date`, `raw_event_text`, `title`, `calendarId`, `last_modified`. Used for general event search.
    *   `TrainingEventSchema`: For "training" data used by services like `features-apply`, `_chat`, and `schedule-event`. Includes `id` (source event ID), `userId`, `vector`, `source_event_text`, `created_at`.
*   **Table Management:**
    *   Manages two primary tables: `events_data` (for `EventSchema`) and `training_data` (for `TrainingEventSchema`).
    *   Includes a `getOrCreateTable` function that can initialize these tables if they don't exist, using sample data to help LanceDB infer schemas and set up vector indexing.
*   **CRUD Operations:**
    *   Provides generic functions like `upsertItems`, `deleteItemsByIds`, `searchTableByVector`, and `getItemById`.
    *   Offers specific wrapper functions for easier interaction with the `events_data` and `training_data` tables (e.g., `upsertEvents`, `searchEvents`, `upsertTrainingEvents`, `searchTrainingEvents`).

### 2.5. Migration of `features-apply` Service

The `features-apply` service, which uses a vector-based training mechanism to learn from past events and apply their properties to new ones, was migrated from OpenSearch to LanceDB.

*   **Core Logic Location:** `_applyFeaturesWorker_/index.ts` with helpers in `_libs/api-helper.ts`.
*   **LanceDB Integration:**
    *   `_libs/api-helper.ts` was refactored to remove all OpenSearch client logic and direct OpenSearch calls.
    *   It now imports and uses functions from the shared `_utils/lancedb_service.ts`:
        *   `searchTrainingEvents` (replaces `searchTrainEventIndexInOpenSearch`) for finding similar training event vectors in the `training_data` table.
        *   `getEventById` (from `lancedb_service`, used by a new `getEventVectorById` helper) to fetch event vectors from the `events_data` table (assuming vectors of processed events are stored there).
        *   `deleteTrainingEventsByIds` (replaces `deleteDocInTrainEventIndexInOpenSearch`) for removing entries from `training_data`.
        *   A new `addTrainingData` helper was added, utilizing `upsertTrainingEvents` to save new entries to the `training_data` table when the system learns from a new event.
    *   The worker (`_applyFeaturesWorker_/index.ts`) was updated to call these new/modified helper functions and to correctly handle the direct `TrainingEventSchema | null` or `EventSchema | null` return types instead of OpenSearch response objects.
*   **Cleanup:** The local `_libs/types/OpenSearchResponseType.ts` file was removed.

### 2.6. Migration of `_chat` Service

The `_chat` service utilized OpenSearch for two main functionalities: general event vector search (for user queries like "find my meeting about X") and a training data mechanism similar to `features-apply`. Both have been migrated to LanceDB.

*   **Core Logic Location:** Primarily in `_libs/api-helper.ts` for OpenSearch interactions, with various skill handlers (e.g., `_libs/skills/askCalendar/findEvent/api-helper.ts`) consuming these helpers.
*   **LanceDB Integration (`_chat/_libs/api-helper.ts`):**
    *   All OpenSearch client logic and direct OpenSearch functions were removed.
    *   The file now imports and uses functions from `_utils/lancedb_service.ts`.
    *   **General Event Search:**
        *   Functions like `allEventOpenSearch`, `allEventWithDatesOpenSearch`, etc., were replaced with new functions (e.g., `searchSingleEventByVectorLanceDb`, `searchMultipleEventsByVectorWithDatesLanceDb`) that call `searchEvents` on the `events_data` table.
        *   Vector storage for general events (`putDataInAllEventIndexInOpenSearch`) now uses `upsertEvents` into the `events_data` table.
        *   Fetching a specific event's vector (`getVectorInAllEventIndexInOpenSearch`) now uses `getEventById` (from `lancedb_service`) and retrieves the vector from the `events_data` table.
    *   **Training Data Mechanism:**
        *   Functions managing the `openTrainEventIndex` (e.g., `searchTrainEventIndexInOpenSearch`, `putDataInTrainEventIndexInOpenSearch`) were replaced with equivalents using `searchTrainingEvents`, `upsertTrainingEvents`, and `deleteTrainingEventsByIds` on the `training_data` table.
*   **Skill Handler Updates:**
    *   Skill handlers, such as those in `_libs/skills/askCalendar/findEvent/`, `findEvents/`, and `nextEvent/`, were updated to call the new LanceDB-backed functions in `_chat/_libs/api-helper.ts`.
    *   Their logic was adapted to handle the direct `LanceDbEventSchema[]` or `LanceDbEventSchema | null` return types.
*   **Cleanup:** The local `_libs/types/OpenSearchResponseType.ts` file was removed.

### 2.7. Migration of `schedule-event` Service

The `schedule-event` service employs a training data mechanism, similar to `features-apply`, to apply learned event properties. This has been migrated to LanceDB.

*   **Core Logic Location:** Worker files `_scheduleEventShortWorker_/index.ts` and `_scheduleEventWorker_/index.ts`, with helpers in `_libs/api-helper.ts`.
*   **LanceDB Integration:**
    *   `_libs/api-helper.ts` was refactored:
        *   OpenSearch client and direct calls were removed.
        *   It now uses functions from `_utils/lancedb_service.ts`:
            *   `searchTrainingEvents` (replaces `searchTrainEventIndexInOpenSearch` and an older `searchData3`).
            *   `getEventById` (used by a new `getEventVectorById` helper).
            *   `deleteTrainingEventsByIds` (replaces `deleteDocInSearch3`).
            *   A new `addTrainingData` helper (using `upsertTrainingEvents`) was added.
    *   Both worker files (`_scheduleEventShortWorker_/index.ts` and `_scheduleEventWorker_/index.ts`) were updated to:
        *   Import and use the new LanceDB-based helpers from their `api-helper.ts`.
        *   Adapt to the `TrainingEventSchema | null` return type from searches.
        *   Call `addTrainingData` to save new training entries.
*   **Cleanup:** The local `_libs/types/OpenSearchResponseType.ts` file was removed.

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
*   **Centralized DB Logic:** The `_utils/lancedb_service.ts` provides a single source of truth for LanceDB interactions, reducing code duplication and improving maintainability.

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
