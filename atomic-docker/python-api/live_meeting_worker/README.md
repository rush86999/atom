# Live Meeting Attendance Worker

This Python FastAPI application serves as the backend worker for the Live Meeting Attendance feature of the Atom project. It handles requests to list audio devices, start, monitor, and stop meeting attendance tasks, which involve audio capture, (eventual) transcription, and note-generation.

## Setup and Running

### Prerequisites
*   Python 3.8+
*   Pip

### Installation

1.  **Navigate to the worker directory:**
    ```bash
    cd atomic-docker/python-api/live_meeting_worker
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### Running Locally

Use Uvicorn to run the FastAPI application:
```bash
uvicorn main:app --reload --port 8001
# Change the port if needed, ensure it matches NEXT_PUBLIC_LIVE_MEETING_WORKER_URL in the frontend .env
```
The `--reload` flag enables auto-reloading on code changes, useful for development.

### Environment Variables
The application relies on environment variables for certain integrations. Ensure these are set in your environment or managed via a `.env` file when running locally (requires `python-dotenv` to be added to `requirements.txt` and loaded in `main.py`). When deployed via Docker Compose, these are passed through the `docker-compose.yaml` file.

**Required Environment Variables:**

*   **`OPENAI_API_KEY`**: Your API key for OpenAI services, used for Speech-to-Text (Whisper API). STT functionality will be disabled if this is not set.
*   **`NOTION_API_KEY`**: Your Notion integration token (API key). Notion integration for saving transcripts will be disabled if this is not set.

**Optional Environment Variables:**

*   **`NOTION_PARENT_PAGE_ID`**: The ID of a Notion page under which new notes (transcripts) will be created. If not provided, notes will be created at the root of the workspace accessible by the API key, which might be the user's private pages. It's recommended to set this to a specific "Meetings" or "Transcripts" page ID for better organization.
*   Other API keys as new integrations are added.

Create a `.env` file in this directory for local development (ensure `.env` is in `.gitignore`):
```dotenv
OPENAI_API_KEY="sk-your_openai_api_key_here"
NOTION_API_KEY="secret_your_notion_api_key_here"
# NOTION_PARENT_PAGE_ID="your_notion_parent_page_id_here" # Optional
```

## API Documentation
The API endpoints are defined in `main.py` and follow the OpenAPI specification. When the application is running, interactive API documentation (Swagger UI) is typically available at `/docs` (e.g., `http://localhost:8001/docs`).

Refer to `atomic-docker/docs/live-meeting-attendance-api.md` for a detailed description of the API contract.

## Project Structure
```
live_meeting_worker/
├── main.py             # FastAPI application, endpoint definitions
├── requirements.txt    # Python dependencies
├── README.md           # This file
├── .env.example        # Example environment variables (optional)
└── utils/              # Optional: Utility functions (e.g., audio handling, STT wrappers)
    └── audio_utils.py
└── services/           # Optional: For external service integrations (Notion, LLMs)
    └── notion_service.py
    └── stt_service.py
```

## Key Functionality (To Be Implemented/Enhanced)
*   **Audio Device Listing:** Dynamically lists available audio input devices.
*   **Task Management:** Manages the lifecycle of meeting attendance tasks.
*   **Audio Capture:** Captures audio from the selected device. (Platform-dependent, may require specific libraries or OS permissions).
*   **Speech-to-Text (STT):** Transcribes captured audio in real-time or batches. (Requires integration with an STT engine like Whisper).
*   **Note Generation/Summarization:** Processes the transcript to create summaries or structured notes. (Requires integration with an LLM).
*   **Notion Integration:** Saves transcripts and notes to a specified Notion page.

## Dockerization
A `Dockerfile` is provided to containerize this application. When deployed via `docker-compose.yaml` (located in `atomic-docker/project/`), this worker service (`live-meeting-worker`) should have a volume mounted for data persistence if using SQLite.

**Data Persistence (SQLite):**
The worker uses an SQLite database (`live_meeting_tasks.db` by default, stored in `/app/data/` within the container) to persist task information. For the data to survive container restarts, a volume should be mounted in `docker-compose.yaml`:
```yaml
services:
  live-meeting-worker:
    # ... other configurations ...
    volumes:
      - ../python-api/live_meeting_worker:/app # For code
      - ./worker_data:/app/data          # For persistent SQLite DB
                                         # (creates 'worker_data' dir in atomic-docker/project/)
```

The frontend's `NEXT_PUBLIC_LIVE_MEETING_WORKER_URL` should be configured to point to the address of this service within the Docker network (e.g., `http://live-meeting-worker:8001`).
```
