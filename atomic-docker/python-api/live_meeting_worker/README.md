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

*   **`OPENAI_API_KEY`**: Your API key for OpenAI services, used for Speech-to-Text (Whisper API). The application will not be able to perform transcriptions if this is not set.

**Optional/Future Environment Variables:**

*   `NOTION_API_KEY` (Example, for future Notion integration for saving notes)
*   Other API keys as new integrations are added.

Create a `.env` file in this directory for local development (ensure `.env` is in `.gitignore`):
```dotenv
OPENAI_API_KEY="sk-your_openai_api_key_here"
# NOTION_API_KEY="secret_your_notion_api_key_here"
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
A `Dockerfile` will be provided to containerize this application for deployment as part of the `atomic-docker` setup. The `docker-compose.yml` file in the `atomic-docker` root will manage running this worker alongside other services.
The frontend's `NEXT_PUBLIC_LIVE_MEETING_WORKER_URL` should be configured to point to the address of this service within the Docker network (e.g., `http://live-meeting-worker:8001`).
```
