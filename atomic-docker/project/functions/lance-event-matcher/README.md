# `lance-event-matcher` Service

## Purpose
This service provides event matching and retrieval capabilities using LanceDB for vector storage and search, and is intended to integrate with an AI agent for enhanced decision-making regarding event types. It replaces the previous OpenSearch-based `events-search` service.

## Endpoint
The service is typically accessed via an API endpoint, configured through an environment variable (e.g., `NEXT_PUBLIC_LANCE_EVENT_MATCHER_URL`) or defaulting to a path like `/api/lance-event-matcher`.

## Workflow Overview
The service employs a multi-step process to handle user search requests:
1.  **(Optional) User Category Fetching:** Retrieves event categories defined by the user from a data store (e.g., Hasura).
2.  **Pre-Query AI Enhancement:** The user's raw search query, along with their categories and (optionally) recent message history, is processed by an AI model (`callAIQueryEnhancer`). This step refines the query for better semantic search, suggests relevant category IDs, and attempts to identify date intentions.
3.  **Vector Search:** The refined query text is converted into a vector embedding. This vector is used to search for matching events in LanceDB. Date filters from the original request or identified by the AI are applied.
4.  **Post-Query AI Results Processing:** The events retrieved from LanceDB are then processed by another AI model (`callAIEventProcessor`). This stage uses the original query, refined query, user categories, and (optionally) message history to filter the results further, assign a final category to each relevant event, and provide a relevance score.
5.  **Response:** The AI-processed and scored events are returned to the client.

## Key Features
*   **Two-Stage AI Processing:**
    *   **Pre-Query AI Enhancement (`callAIQueryEnhancer`):**
        *   Refines the user's natural language query into an optimized search phrase for vector search.
        *   Suggests potentially relevant event category IDs based on the query and user's defined categories.
        *   Identifies date ranges or specific dates implied in the user's query (e.g., "next week", "events in July").
        *   Optionally considers user message history for richer contextual understanding.
    *   **Post-Query AI Results Processing (`callAIEventProcessor`):**
        *   Filters events retrieved from LanceDB based on their relevance to the user's original query and the refined query.
        *   Assigns the single most relevant category (from the user's list) to each event.
        *   Provides a relevance score (0.0 to 1.0) for each event.
        *   Optionally considers user message history for more accurate event processing.
*   **Text-to-Vector Conversion:** Converts the AI-refined search text into vector embeddings using OpenAI models for semantic search.
*   **LanceDB Vector Search:** Performs similarity searches on event vectors stored in LanceDB, combined with structured filtering.
*   **Flexible Date Filtering:** Supports filtering search results by `start_date` and `end_date`, accommodating dates provided in the original request or identified by the AI.
*   **User-Specific Search:** Ensures that search results are scoped to the `userId`.
