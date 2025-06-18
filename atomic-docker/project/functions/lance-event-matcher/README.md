# `lance-event-matcher` Service

## Purpose
This service provides event matching and retrieval capabilities using LanceDB for vector storage and search, and is intended to integrate with an AI agent for enhanced decision-making regarding event types. It replaces the previous OpenSearch-based `events-search` service.

## Endpoint
The service is typically accessed via an API endpoint, configured through an environment variable (e.g., `NEXT_PUBLIC_LANCE_EVENT_MATCHER_URL`) or defaulting to a path like `/api/lance-event-matcher`.

## Key Features
*   **Text-to-Vector Conversion:** Converts input search text into vector embeddings using OpenAI models.
*   **LanceDB Vector Search:** Performs similarity searches on event vectors stored in LanceDB.
*   **Date Filtering:** Supports filtering search results by `start_date` and `end_date`.
*   **User-Specific Search:** Filters search results by `userId`.
*   **AI Agent Integration (Pending):** Designed to incorporate an AI agent to process search results and assist with applying event types. This part is currently a placeholder in the code.
