# Live Meeting Attendance: Setup and Usage Guide

## Overview

The Live Meeting Attendance feature allows Atom to capture audio from online meetings (e.g., Zoom, Google Meet, Microsoft Teams) or general desktop audio. This audio can then be processed for (eventual) real-time transcription and note generation in Notion. This document guides you through setting up and using this feature with the new Python-based worker.

## Prerequisites

1.  **Atom Services:** The following Atom services must be running and correctly configured as part of the `atomic-docker` setup:
    *   **Frontend Application (`app` service):** The Next.js application where users interact with Atom settings.
    *   **Live Meeting Worker (`live-meeting-worker` service):** The new Python (FastAPI) backend service responsible for handling audio device listing, task management, and (placeholder) audio processing. This service is defined in `atomic-docker/project/docker-compose.yaml`.
    *   Ensure that the `NEXT_PUBLIC_LIVE_MEETING_WORKER_URL` environment variable for the `app` service in `docker-compose.yaml` is correctly set to point to the `live-meeting-worker` service (e.g., `http://live-meeting-worker:8001`).

2.  **External Services (for future full functionality):**
    *   While the current Python worker has placeholder logic, future enhancements for actual transcription and Notion integration would require:
        *   **Notion API Key:** For saving notes.
        *   **Transcription Service API Key (e.g., Deepgram, OpenAI Whisper):** For STT.
        *   **LLM API Key (e.g., OpenAI):** For summarization/note generation.
    *   These keys would typically be configured server-side for the `live-meeting-worker` or an intermediary service, not directly by the user in the current UI.

## Audio Setup (Crucial)

Correct audio configuration on the user's machine (or the machine where the browser accessing Atom runs) is essential for the system to capture the desired meeting audio rather than just microphone input. The Python worker itself, running in Docker, will list audio devices *available to its container environment*. For capturing desktop/meeting audio, the user needs to route that audio to an input that the *browser* can access, which then would be streamed to an appropriate backend if direct browser capture was implemented, OR the Python worker needs access to a virtual audio device on the host that captures system sounds if it were to run locally with such permissions.

**Current Implementation:** The `live-meeting-worker` (running in Docker) uses `sounddevice` to list audio devices. Inside a standard Docker container, `sounddevice` might only see limited virtual devices or none at all, unless the container is given special privileges or mappings to host audio devices (e.g., `/dev/snd`). The current `Dockerfile` for the worker includes `libportaudio2`, which is a step towards enabling `sounddevice`. The UI will display what the *worker* detects.

### 1. Listing Available Audio Devices (via Worker)

The `live-meeting-worker` provides an HTTP endpoint to list audio input devices it can detect within its environment. The Atom frontend UI uses this list.

*   **Worker Endpoint:** `GET /list_audio_devices`
    *   Accessed by the frontend at `NEXT_PUBLIC_LIVE_MEETING_WORKER_URL/list_audio_devices`.
    *   If running `atomic-docker` locally, this translates to `http://localhost:8001/list_audio_devices` (assuming default port mapping for the worker).

*   **Example Output (JSON from Worker):**
    ```json
    {
      "devices": [
        {
          "id": "default", // Or an index like 0, 1, etc.
          "name": "Default Input Device"
        },
        {
          "id": "pulse", // Example if PulseAudio is available in container
          "name": "PulseAudio Sound Server"
        }
        // ... other devices the worker can see
      ]
    }
    ```
    The actual list will depend heavily on the Docker container's audio configuration and permissions.

*   **Interpreting the Output:**
    *   `id`: A unique identifier (string or number) for the device, used in the `start_meeting_attendance` payload.
    *   `name`: A human-readable name for the device.

### 2. Capturing Meeting/Desktop Audio (User's Responsibility)

To capture audio *from* a meeting or general desktop sounds, the user typically needs to:
1.  Install a virtual audio cable/loopback program on their local machine (e.g., VB-CABLE for Windows, BlackHole for macOS, PulseAudio loopback for Linux).
2.  Configure their system or specific meeting application to output its sound to this virtual audio device.
3.  Set this virtual audio device as the **input device** for the Atom application if it were to capture audio directly via the browser and send it.
    **Alternatively, if the `live-meeting-worker` is intended to capture directly (requires host audio access for Docker):** The `audio_device_id` selected in the UI would correspond to a device the *worker* can access. This implies the worker's Docker container needs access to the host's audio system, including the virtual loopback device. This is an advanced Docker configuration (e.g., mounting `/dev/snd`, specific PulseAudio configurations).

**Current Worker Functionality:** The Python worker's `/start_meeting_attendance` endpoint takes an `audio_device_id`. Its placeholder logic currently simulates capture. For real capture using `sounddevice` from within Docker, the Docker container needs appropriate access to audio hardware/virtual devices.

## Interacting with Live Meeting Attendance via UI

The Atom frontend (in Agent Settings) provides a UI to manage live meeting attendance:

1.  **Select Audio Device:** Choose from the list populated by the `live-meeting-worker`.
2.  **Enter Meeting Details:**
    *   **Platform:** (e.g., "zoom", "googlemeet", "msteams", "other")
    *   **Meeting ID or Description:** A URL or any identifier for the meeting.
    *   **Notion Page Title:** The desired title for the Notion page where notes will eventually be saved.
3.  **Start Meeting:** Click "Start Attending Meeting".
4.  **Monitor Status:** View the task ID, current status, message, duration, and any previews.
5.  **Stop Meeting:** Click "Stop Attending Meeting" for an active task.

## API Interaction (Frontend to Worker)

The frontend interacts with the `live-meeting-worker` API. Refer to `atomic-docker/docs/live-meeting-attendance-api.md` for full API details.

*   **Start Meeting Attendance:**
    *   `POST {NEXT_PUBLIC_LIVE_MEETING_WORKER_URL}/start_meeting_attendance`
    *   **Example Request Payload:**
        ```json
        {
          "platform": "googlemeet",
          "meeting_id": "https://meet.google.com/abc-xyz",
          "audio_device_id": "default", // ID from /list_audio_devices
          "notion_page_title": "My Q3 Planning Session Notes",
          "user_id": "supertokens_user_id_here"
        }
        ```
    *   **Example Success Response:**
        ```json
        {
          "task_id": "b7a2f8c1-e5d6-4a3b-9c8d-7e6f5a4b3c2d",
          "status": "pending", // Or "active" if started quickly
          "message": "Meeting attendance task accepted and is being initialized."
        }
        ```

*   **Get Meeting Attendance Status:**
    *   `GET {NEXT_PUBLIC_LIVE_MEETING_WORKER_URL}/meeting_attendance_status/{task_id}`
    *   **Example Success Response (Active Task):**
        ```json
        {
          "task_id": "b7a2f8c1-e5d6-4a3b-9c8d-7e6f5a4b3c2d",
          "user_id": "supertokens_user_id_here",
          "platform": "googlemeet",
          "meeting_id": "https://meet.google.com/abc-xyz",
          "audio_device_id": "default",
          "notion_page_title": "My Q3 Planning Session Notes",
          "status": "active",
          "message": "Audio capture started (placeholder).",
          "start_time": "2023-11-15T10:00:00Z",
          "duration_seconds": 120,
          "transcript_preview": "Transcript snippet 120...",
          "notes_preview": "- Note point 120...",
          "final_transcript_location": null,
          "final_notes_location": null
        }
        ```

*   **Stop Meeting Attendance:**
    *   `POST {NEXT_PUBLIC_LIVE_MEETING_WORKER_URL}/stop_meeting_attendance/{task_id}`
    *   **Example Success Response:**
        ```json
        {
          "task_id": "b7a2f8c1-e5d6-4a3b-9c8d-7e6f5a4b3c2d",
          // ... (other fields updated to reflect completion)
          "status": "completed",
          "message": "Meeting attendance completed. Mock transcript and notes generated.",
          "final_transcript_location": "/path/to/mock_transcript_task_id.txt",
          "final_notes_location": "/path/to/mock_notes_task_id.txt"
        }
        ```

## Troubleshooting

*   **Worker Not Reachable:**
    *   Ensure the `live-meeting-worker` container is running: `docker ps | grep live-meeting-worker`.
    *   Check its logs: `docker logs live-meeting-worker`.
    *   Verify `NEXT_PUBLIC_LIVE_MEETING_WORKER_URL` in the `app` service's environment (inside `docker-compose.yaml`) correctly points to `http://live-meeting-worker:8001`.
*   **No Audio Devices Listed / Incorrect Devices:**
    *   This indicates an issue with `sounddevice` inside the `live-meeting-worker` container or the container's access to host audio.
    *   The `Dockerfile` for `live-meeting-worker` installs `libportaudio2`. For more comprehensive audio device access from within Docker (especially for capturing host system audio), advanced Docker configurations like mounting `/dev/snd` (Linux) or specific PulseAudio setups might be required. This is beyond the default setup.
    *   The current placeholder worker simulates audio, so device selection is for future real capture.
*   **Task Errors:** Check the `message` field in the task status response for error details from the worker. Examine `live-meeting-worker` logs for more detailed Python tracebacks.

## Architecture Overview

1.  **Frontend (Atom UI):**
    *   User configures and initiates meeting attendance via settings.
    *   Makes API calls to the `live-meeting-worker` service.
2.  **Live Meeting Worker (`live-meeting-worker` - Python/FastAPI service):**
    *   Runs in a Docker container.
    *   Manages the lifecycle of attendance tasks (start, stop, status).
    *   Lists available audio devices within its container environment using `sounddevice`.
    *   Currently simulates audio capture and processing.
    *   (Future) Will integrate real STT, note generation, and Notion API calls.
3.  **Docker & Docker Compose:**
    *   Manages the running of all services, including the new `live-meeting-worker`.
    *   Handles inter-service communication via defined networks and service names.

**Note on Previous Zoom SDK Agent:**
This document previously detailed a C++ based Zoom SDK agent. The current implementation uses a more generic Python-based worker. While the Python worker *could* eventually incorporate platform-specific SDKs, its current form relies on general audio capture via `sounddevice` (when not using placeholder logic). Therefore, much of the detailed Zoom C++ SDK setup, `NewZoomSdkAgent`, and related environment variables like `USE_NEW_ZOOM_SDK_AGENT` are not directly applicable to the current Python worker's core logic but are retained for historical context or potential future re-integration.

This guide should help you set up and use the live meeting attendance feature with the new Python worker. For further assistance, consult the system logs or the API documentation.
