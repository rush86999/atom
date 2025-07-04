# Live Meeting Attendance: Setup and Usage Guide

## Overview

The Live Meeting Attendance feature allows Atom to capture audio from online meetings (e.g., Zoom, Google Meet, Microsoft Teams) or general desktop audio. This audio can then be processed for (eventual) real-time transcription and note generation in Notion. This document guides you through setting up and using this feature with the new Python-based worker.

## Prerequisites

1.  **Atom Services:** The following Atom services must be running and correctly configured as part of the `atomic-docker` setup:
    *   **Frontend Application (`app` service):** The Next.js application where users interact with Atom settings.
    *   **Live Meeting Worker (`live-meeting-worker` service):** The Python (FastAPI) backend service responsible for audio device listing, task management, audio capture, and Speech-to-Text (STT) processing. This service is defined in `atomic-docker/project/docker-compose.yaml`.
    *   Ensure that `NEXT_PUBLIC_LIVE_MEETING_WORKER_URL` for the `app` service points to the `live-meeting-worker` (e.g., `http://live-meeting-worker:8001`).

2.  **Environment Variables for `live-meeting-worker`:**
    *   **`OPENAI_API_KEY`**: This environment variable **must** be set for the `live-meeting-worker` service. It is required for transcribing captured audio using the OpenAI Whisper API. If not set, STT will be skipped. This should be defined in your `.env` file at the root of `atomic-docker/project/` and passed to the container via `docker-compose.yaml`.
    *   **`NOTION_API_KEY`**: This environment variable **must** be set for the `live-meeting-worker` service if you want transcripts to be saved to Notion. This should be your Notion integration token.
    *   **`NOTION_PARENT_PAGE_ID` (Optional)**: The ID of an existing Notion page under which new meeting note pages (containing transcripts) will be created. If not provided, pages will be created in the default location accessible by the Notion integration (often as private pages). Providing a parent page ID helps organize notes.

3.  **External Services (for future enhancements):**
    *   Other LLM API keys if different models are used for summarization beyond the transcript.

## Audio Setup (Crucial)

Correct audio configuration on the user's machine (or the machine where the browser accessing Atom runs) is essential for the system to capture the desired meeting audio rather than just microphone input. The Python worker itself, running in Docker, will list audio devices *available to its container environment*. For capturing desktop/meeting audio, the user needs to route that audio to an input that the *browser* can access, which then would be streamed to an appropriate backend if direct browser capture was implemented, OR the Python worker needs access to a virtual audio device on the host that captures system sounds if it were to run locally with such permissions.

**Current Implementation & Worker Behavior:** The `live-meeting-worker` (running in Docker) now uses `sounddevice` to:
1.  List available audio input devices it can detect within its container environment.
2.  Attempt real audio capture from the selected device, saving it as a WAV file in the container's temporary directory (e.g., `/tmp/{task_id}_audio.wav`).

The `Dockerfile` for the worker includes `libportaudio2`, which is necessary for `sounddevice` to function. However, by default, Docker containers are isolated from the host's audio hardware.

**Accessing Host Audio Devices in Docker:**
*   **Linux Hosts:** To allow the `live-meeting-worker` container to access your host machine's audio devices (including virtual loopback devices you've configured for capturing meeting audio), you may need to modify your `docker-compose.yaml` (or a `docker-compose.override.yaml`) for the `live-meeting-worker` service by adding:
    ```yaml
    devices:
      - "/dev/snd:/dev/snd"
    ```
    This maps the host's sound devices into the container. You might also need to ensure the user inside the container has appropriate permissions, or run the container with additional privileges if issues persist.
*   **macOS and Windows Hosts (Docker Desktop):** Direct hardware mapping is more complex. Audio capture from host devices into a Docker container might require advanced configurations (e.g., setting up PulseAudio to be accessible over the network or via a shared socket). For these platforms, if capturing specific host audio is critical, initial testing of `sounddevice` capture logic might be easier by running the Python worker script directly on the host OS (outside Docker) during development.
*   **Default Behavior (No Host Device Mapping):** Without explicit host device mapping, the worker will only be able to list and attempt to capture from any audio devices that are available within the Docker container's isolated environment (e.g., dummy devices, or virtual devices if ALSA/PulseAudio creates them within the container itself). The "mock_input_device" will be returned if `sounddevice` cannot find any real devices. Real audio capture will likely fail or capture silence/internal container audio unless host devices are properly exposed.

The Atom UI will display the audio devices that the *worker reports from its environment*. The success of actual audio capture depends on whether the selected device is accessible and operational within that worker environment.

### 1. Listing Available Audio Devices (via Worker)

The `live-meeting-worker` (Python FastAPI service) provides an HTTP endpoint to list audio input devices it can detect within its containerized environment. The Atom frontend UI uses this list.

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
    **Alternatively, if the `live-meeting-worker` is intended to capture directly (requires host audio access for Docker as described above):** The `audio_device_id` selected in the UI would correspond to a device the *worker* can access (e.g., a host device mapped into the container).

**Current Worker Functionality:** The Python worker's `/start_meeting_attendance` endpoint takes an `audio_device_id` and now attempts **real audio capture** using `sounddevice`, saving the output to a temporary WAV file inside its container (e.g., `/tmp/{task_id}_audio.wav`). The success of this capture depends on `sounddevice`'s ability to access the specified audio device within the worker's environment.

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
          "message": "Audio capture active.",
          "start_time": "2023-11-15T10:00:00Z",
          "duration_seconds": 120,
          "transcript_preview": "Captured 120s of audio...",
          "notes_preview": null,
          "final_transcript_location": null,
          "final_notes_location": null
        }
        ```
    *   **Example Success Response (Task Completed with Transcription):**
        ```json
        {
          "task_id": "b7a2f8c1-e5d6-4a3b-9c8d-7e6f5a4b3c2d",
          "user_id": "supertokens_user_id_here",
          "platform": "other",
          "meeting_id": "Test STT Meeting",
          "audio_device_id": "default",
          "notion_page_title": "Notes for STT Test",
          "status": "completed",
          "message": "Transcription successful. Notes saved to Notion: https://www.notion.so/username/PageTitle-hash. Task completed.",
          "start_time": "2023-11-15T10:00:00Z",
          "end_time": "2023-11-15T10:02:00Z",
          "duration_seconds": 120,
          "transcript_preview": "This is the transcribed text from the Whisper API...",
          "notes_preview": null,
          "final_transcript_location": "/tmp/b7a2f8c1-e5d6-4a3b-9c8d-7e6f5a4b3c2d_audio.wav", // Path where audio *was*
          "final_notes_location": "https://www.notion.so/username/PageTitle-hash" // URL of the created Notion page
        }
        ```


*   **Stop Meeting Attendance:**
    *   `POST {NEXT_PUBLIC_LIVE_MEETING_WORKER_URL}/stop_meeting_attendance/{task_id}`
    *   **Example Success Response (after STT and Notion save):**
        ```json
        {
          "task_id": "b7a2f8c1-e5d6-4a3b-9c8d-7e6f5a4b3c2d",
          // ... (other fields updated to reflect completion)
          "status": "completed",
          "message": "Audio capture stopped. Preparing for STT. Transcription successful. Notes saved to Notion: https://www.notion.so/username/PageTitle-hash. Task completed.",
          "transcript_preview": "This is the transcribed text...",
          "final_transcript_location": "/tmp/b7a2f8c1-e5d6-4a3b-9c8d-7e6f5a4b3c2d_audio.wav", // Path where audio *was* before deletion
          "final_notes_location": "https://www.notion.so/username/PageTitle-hash"
        }
        ```

## Troubleshooting

*   **Worker Not Reachable:**
    *   Ensure the `live-meeting-worker` container is running: `docker ps | grep live-meeting-worker`.
    *   Check its logs: `docker logs live-meeting-worker`.
    *   Verify `NEXT_PUBLIC_LIVE_MEETING_WORKER_URL` in the `app` service's environment (inside `docker-compose.yaml`) correctly points to `http://live-meeting-worker:8001`.
*   **No Audio Devices Listed / Incorrect Devices / Capture Fails:**
    *   This often indicates an issue with `sounddevice` inside the `live-meeting-worker` container, or the container's lack of access to suitable audio devices.
    *   Check worker logs for `PortAudioError` or messages like "Ensure device ... is valid and available."
    *   As detailed in the "Audio Setup" section, for the Dockerized worker to access host audio devices (especially on Linux), you might need to add `devices: ["/dev/snd:/dev/snd"]` to its service definition in `docker-compose.yaml`.
    *   If the worker falls back to the "mock_input_device", real audio capture will not occur.
*   **STT Issues:**
    *   If transcription fails or is skipped, the `message` field in the task status will indicate this. `transcript_preview` will not contain the transcript.
    *   Ensure `OPENAI_API_KEY` is correctly set for the `live-meeting-worker` service in your Docker environment. Check worker logs for "OpenAI client not available" or "OpenAI Whisper STT failed".
*   **Notion Integration Issues:**
    *   If saving to Notion fails, the `message` field will indicate this (e.g., "Failed to save notes to Notion."). `final_notes_location` will likely be null.
    *   Ensure `NOTION_API_KEY` is correctly set and has permissions to create pages (and under `NOTION_PARENT_PAGE_ID` if specified).
    *   Check worker logs for "Notion client not available", "Notion API error", or issues with `NOTION_PARENT_PAGE_ID`.
*   **Audio File Issues & Cleanup:**
    *   The worker saves captured audio to a temporary WAV file (e.g., `/tmp/TASK_ID_audio.wav`) inside its container.
    *   `final_transcript_location` in the task status will show this path (even after the file is deleted, serving as a record of the source audio).
    *   The worker attempts to delete this temporary WAV file after STT and Notion processing. Check worker logs for messages about file deletion.
*   **Task Errors:** Check the `message` field in the task status response for error details from the worker. Examine `live-meeting-worker` logs for more detailed Python tracebacks.

## Architecture Overview

1.  **Frontend (Atom UI):**
    *   User configures and initiates meeting attendance via settings.
    *   Makes API calls to the `live-meeting-worker` service.
2.  **Live Meeting Worker (`live-meeting-worker` - Python/FastAPI service):**
    *   Runs in a Docker container.
    *   Manages the lifecycle of attendance tasks (start, stop, status).
    *   Lists available audio devices within its container environment using `sounddevice`.
    *   Performs real audio capture using `sounddevice` and saves it to a temporary WAV file.
    *   Transcribes the captured WAV file using OpenAI Whisper API (requires `OPENAI_API_KEY`).
    *   Creates an initial Notion page with the specified title and the full transcript (requires `NOTION_API_KEY` and optionally `NOTION_PARENT_PAGE_ID`). The URL of this page is stored in `final_notes_location`.
    *   **Generates a summary, key decisions, and action items** from the transcript using an LLM (OpenAI by default).
    *   **Appends these generated sections (Summary, Key Decisions, Action Items)** to the previously created Notion page.
    *   The `notes_preview` field in the task status may contain a snippet of the generated summary.
    *   Deletes the temporary WAV file after all processing.
3.  **Docker & Docker Compose:**
    *   Manages the running of all services, including the new `live-meeting-worker`.
    *   Handles inter-service communication via defined networks and service names.

**Note on Previous Zoom SDK Agent:**
This document previously detailed a C++ based Zoom SDK agent. The current implementation uses a more generic Python-based worker. While the Python worker *could* eventually incorporate platform-specific SDKs, its current form relies on general audio capture via `sounddevice` (when not using placeholder logic). Therefore, much of the detailed Zoom C++ SDK setup, `NewZoomSdkAgent`, and related environment variables like `USE_NEW_ZOOM_SDK_AGENT` are not directly applicable to the current Python worker's core logic but are retained for historical context or potential future re-integration.

This guide should help you set up and use the live meeting attendance feature with the new Python worker. For further assistance, consult the system logs or the API documentation.
