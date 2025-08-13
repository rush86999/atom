# Atom Ingestion Pipeline Guide

## Purpose

This guide describes the Ingestion Pipeline responsible for processing documents, messages, and other textual data from various cloud sources (like Notion, Google Drive, Slack, etc.). It generates text embeddings from this data and stores them in a LanceDB vector database. This enables powerful semantic search capabilities across all connected sources via the Atom agent.

## How It Works

The pipeline operates in several stages:

1.  **Data Extraction:**
    *   The pipeline connects to various data sources configured for the user.
    *   This can include Notion databases, Google Drive files, Slack channels, and more.
    *   For each source, it extracts the primary textual content and relevant metadata (title, URL, creation/edit times, source-specific ID).

2.  **Text Processing & Embedding:**
    *   The extracted text from each Notion page is split into smaller, manageable chunks.
    *   For each text chunk, a vector embedding is generated using an OpenAI embedding model (e.g., `text-embedding-ada-002`).

3.  **LanceDB Storage:**
    *   The text chunks, their corresponding embeddings, and the extracted Notion metadata are stored in a LanceDB table.
    *   This data is associated with an `ATOM_USER_ID_FOR_INGESTION` to ensure data isolation if Atom is used in a multi-user context in the future.
    *   The pipeline supports an "incremental" mode to only process new or updated Notion pages, and a "full" mode to re-process all pages. Idempotency is handled by deleting and re-inserting data for a given Notion page if it's updated.

## Configuration

The Ingestion Pipeline is configured via environment variables. These should typically be set in a `.env` file at the root of your `atomic-docker/project/` directory when using Docker Compose, or directly in the environment where the pipeline service/script runs.

Refer to `atomic-docker/python-api/ingestion_pipeline/.env.example` for a template.

**Required Environment Variables:**

*   `NOTION_API_KEY`: Your Notion integration token (API key) with read access to the target database.
*   `NOTION_TRANSCRIPTS_DATABASE_ID`: The ID of the Notion database containing the pages (transcripts/notes) to be ingested.
*   `OPENAI_API_KEY`: Your API key for OpenAI, used for generating text embeddings.
*   `LANCEDB_URI`: The URI for your LanceDB database.
    *   For local Docker deployment, this will be a path *inside* the container (e.g., `/lancedb_data/atom_core_db`). A volume must be mounted to this path for persistence.
    *   It can also be a URI for a cloud-based LanceDB instance (e.g., LanceDB Cloud).
*   `ATOM_USER_ID_FOR_INGESTION`: An identifier for the Atom user whose data is being ingested. This is used to tag the data in LanceDB. For single-user setups, this can be a default value.

**Optional Environment Variables:**

*   `LANCEDB_TABLE_NAME`: Custom name for the LanceDB table where embeddings are stored.
    *   *Default:* `meeting_transcripts_embeddings`
*   `PROCESSING_MODE`: Determines how pages are selected for processing.
    *   `incremental` (default): Only processes pages that are new or have been updated in Notion since their last ingestion into LanceDB.
    *   `full`: Re-processes all pages from the specified Notion database.
*   `LOG_LEVEL`: Sets the logging level for the pipeline scripts (e.g., `DEBUG`, `INFO`, `WARNING`, `ERROR`).
    *   *Default:* `INFO`

## Deployment & Running

The Ingestion Pipeline is designed to run as a Docker service named `ingestion-pipeline-service`, defined in `atomic-docker/project/docker-compose.yaml`.

*   **Building & Running with Docker Compose:**
    ```bash
    cd atomic-docker/project
    docker-compose up --build ingestion-pipeline-service
    # (or `docker-compose up --build -d` to run all services)
    ```

*   **LanceDB Data Persistence & Sharing:**
    *   The `LANCEDB_URI` points to a path within the container (e.g., `/lancedb_data/atom_core_db`).
    *   The `docker-compose.yaml` file mounts a host directory (specified by the `${LANCEDB_HOST_PATH}` variable in your root `.env` file, e.g., `LANCEDB_HOST_PATH=./lance_db_data_shared`) to `/lancedb_data` inside the `ingestion-pipeline-service` container.
    *   **Crucially**, any other service that needs to *query* this LanceDB (e.g., `python-agent` or `functions` service responsible for semantic search) **must also mount this same `${LANCEDB_HOST_PATH}` to its own internal path**, and its `LANCEDB_URI` environment variable must point to that internal path. This ensures both services access the same physical database.

## Triggering the Pipeline

If the `ingestion-pipeline-service` is running (e.g., via `docker-compose up`):

*   **API Endpoint:** It exposes a FastAPI endpoint to trigger the pipeline.
    *   `POST /trigger-ingestion`
    *   Example using `curl` (if the service's port 8002 is mapped to host port 8002):
        ```bash
        curl -X POST http://localhost:8002/trigger-ingestion
        ```
    *   This will start the pipeline run in the background.
*   **Status Check:**
    *   `GET /ingestion-status`
    *   Example:
        ```bash
        curl http://localhost:8002/ingestion-status
        ```

*   **Direct Script Execution (for development/debugging):**
    *   You can also run the orchestrator script directly if you have the Python environment set up and environment variables configured:
        ```bash
        # Navigate to the ingestion_pipeline directory
        cd atomic-docker/python-api/ingestion_pipeline
        # Ensure your .env file is present here or variables are globally set
        python pipeline_orchestrator.py
        ```
    *   Or, from the project root, using the module path:
        ```bash
        # (Ensure PYTHONPATH includes the root or atomic-docker/python-api)
        python -m python-api.ingestion_pipeline.pipeline_orchestrator
        ```

## Other Integrations

The pipeline is designed to be extensible to multiple data sources. The general flow for each integration is the same: extract text and metadata, process it, and store it in LanceDB.

### Slack Integration

*   **Authentication**: The Slack integration uses OAuth 2.0. To enable it, a user's OAuth access token must be securely stored in the `public.user_slack_oauth_tokens` table in the database. The pipeline retrieves the token from this table for the specified `ATOM_USER_ID_FOR_INGESTION`.
*   **Data Scoped**: The integration fetches messages from all public channels in the user's connected Slack workspace.
*   **Configuration**: No specific environment variables are needed for the Slack token itself, as it's managed via the database.

### Microsoft Teams Integration

*   **Authentication**: The MS Teams integration uses the Microsoft Graph API and authenticates via OAuth 2.0. Credentials (including a refresh token) must be stored in the `public.user_msteams_oauth_tokens` table. The extractor handles the token refresh flow using the MSAL library.
*   **Data Scoped**: The integration fetches messages from all channels in all teams that the user is a member of.
*   **Configuration**: This integration requires several environment variables for the MSAL client to be configured, including the client ID, client secret, and authority URL. An encryption key is also required for securing the tokens in the database.

### Outlook Integration

*   **Authentication**: The Outlook integration uses the same Microsoft Graph API authentication flow as the MS Teams integration. It reuses the same tokens stored in the `public.user_msteams_oauth_tokens` table.
*   **Data Scoped**: The integration fetches all emails from the user's Outlook inbox.
*   **Configuration**: The `Mail.Read` scope must be included in the `MSGRAPH_DELEGATED_SCOPES` environment variable.

## Data Source Structure Assumptions

*   **Notion**: The pipeline expects pages within the `NOTION_TRANSCRIPTS_DATABASE_ID` to contain their primary textual content directly within their blocks (e.g., as paragraphs, headings). It attempts to find a page title using common property names like "Name", "Title", or "Task Description".
*   **Other Sources**: Each extractor has its own assumptions about the data structure. Refer to the specific `_extractor.py` file for details.

## LanceDB Schema Overview

The data is stored in LanceDB with a schema similar to the `TranscriptChunk` Pydantic model in `lancedb_handler.py`. Key fields include:
*   `embedding` (vector)
*   `text_chunk` (string)
*   `chunk_id` (string, unique ID for the chunk)
*   `notion_page_id` (string)
*   `notion_page_title` (string)
*   `notion_page_url` (string)
*   `user_id` (string, the Atom user ID)
*   `created_at_notion` (datetime)
*   `last_edited_at_notion` (datetime)
*   `ingested_at` (datetime, when the chunk was processed by this pipeline)
