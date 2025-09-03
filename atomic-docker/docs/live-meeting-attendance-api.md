# Live Meeting Attendance Worker API

This document outlines the API endpoints for the Live Meeting Attendance Worker, which is responsible for capturing audio from meetings, transcribing it, and generating notes.

The base URL for this worker will be determined by the `NEXT_PUBLIC_LIVE_MEETING_WORKER_URL` environment variable in the Next.js frontend.

## Endpoints

### 1. List Audio Devices

*   **Endpoint:** `GET /list_audio_devices`
*   **Description:** Retrieves a list of available audio input devices that can be used for capturing meeting audio.
*   **Request Body:** None
*   **Response Body:**
    ```json
    {
      "devices": [
        {
          "id": "string", // Unique identifier for the device
          "name": "string" // Human-readable name of the device
        }
        // ... more devices
      ]
    }
    ```
*   **Example Success (200 OK):**
    ```json
    {
      "devices": [
        {
          "id": "default",
          "name": "Default Input Device"
        },
        {
          "id": "hw:0,0",
          "name": "MacBook Pro Microphone"
        }
      ]
    }
    ```
*   **Example Error (500 Internal Server Error):**
    ```json
    {
      "error": "Failed to retrieve audio devices",
      "details": "Specific error message here"
    }
    ```

### 2. Start Meeting Attendance

*   **Endpoint:** `POST /start_meeting_attendance`
*   **Description:** Initiates the process of attending a meeting, including audio capture, transcription, and note-taking.
*   **Request Body:**
    ```json
    {
      "platform": "string", // e.g., "zoom", "msteams", "gmeet", "other"
      "meeting_id": "string", // Identifier for the meeting (e.g., URL, meeting code)
      "audio_device_id": "string", // ID of the audio device to use (from /list_audio_devices)
      "notion_page_title": "string", // Desired title for the Notion page where notes will be stored
      "user_id": "string" // The user ID initiating the request
    }
    ```
    *Note: `api_key` for platform-specific integrations (e.g., auto-join) is deferred for future implementation.*
*   **Response Body:**
    ```json
    {
      "task_id": "string", // Unique identifier for this attendance task
      "status": "pending" | "active" | "error", // Initial status
      "message": "string" // Optional message (e.g., confirmation or error details)
    }
    ```
*   **Example Success (202 Accepted):**
    ```json
    {
      "task_id": "b7a2f8c1-e5d6-4a3b-9c8d-7e6f5a4b3c2d",
      "status": "pending",
      "message": "Meeting attendance task accepted and is being initialized."
    }
    ```
*   **Example Error (400 Bad Request):**
    ```json
    {
      "error": "Invalid request payload",
      "details": "Field 'audio_device_id' is required."
    }
    ```
*   **Example Error (500 Internal Server Error):**
    ```json
    {
      "task_id": "b7a2f8c1-e5d6-4a3b-9c8d-7e6f5a4b3c2d", // May or may not be present if task creation failed early
      "status": "error",
      "message": "Failed to initialize audio capture."
    }
    ```

### 3. Get Meeting Attendance Status

*   **Endpoint:** `GET /meeting_attendance_status/{task_id}`
*   **Description:** Polls for the current status and progress of an active meeting attendance task.
*   **Path Parameters:**
    *   `task_id`: The ID of the task (obtained from `/start_meeting_attendance`).
*   **Request Body:** None
*   **Response Body:**
    ```json
    {
      "task_id": "string",
      "status": "pending" | "active" | "processing_completion" | "completed" | "error",
      "message": "string", // Optional message (e.g., current activity, error details)
      "duration_seconds": "integer", // Duration the meeting has been active in seconds
      "transcript_preview": "string", // Optional: A short snippet of the latest transcript
      "notes_preview": "string" // Optional: A short snippet of the latest notes/summary
    }
    ```
*   **Example Success (200 OK - Active):**
    ```json
    {
      "task_id": "b7a2f8c1-e5d6-4a3b-9c8d-7e6f5a4b3c2d",
      "status": "active",
      "message": "Transcription and note-taking in progress.",
      "duration_seconds": 600,
      "transcript_preview": "...and that's when we decided to pivot the strategy...",
      "notes_preview": "- Key decision: Pivot strategy\n- Next steps: Update roadmap"
    }
    ```
*   **Example Success (200 OK - Completed):**
    ```json
    {
      "task_id": "b7a2f8c1-e5d6-4a3b-9c8d-7e6f5a4b3c2d",
      "status": "completed",
      "message": "Meeting attendance completed. Transcript and notes saved.",
      "duration_seconds": 3600,
      "final_transcript_location": "string", // e.g., Notion page ID/URL, S3 URI (actual field TBD)
      "final_notes_location": "string"      // e.g., Notion page ID/URL, S3 URI (actual field TBD)
    }
    ```
*   **Example Error (404 Not Found):**
    ```json
    {
      "error": "Task not found",
      "details": "No active or completed task with ID 'xyz' exists."
    }
    ```

### 4. Stop Meeting Attendance

*   **Endpoint:** `POST /stop_meeting_attendance/{task_id}`
*   **Description:** Manually stops an ongoing meeting attendance task.
*   **Path Parameters:**
    *   `task_id`: The ID of the task to stop.
*   **Request Body:** None
*   **Response Body:**
    ```json
    {
      "task_id": "string",
      "status": "completed" | "error", // Should transition to 'completed' or 'error' if stop fails
      "message": "string", // e.g., "Meeting attendance stopped successfully." or error details
      "final_transcript_location": "string", // (If applicable)
      "final_notes_location": "string"       // (If applicable)
    }
    ```
*   **Example Success (200 OK):**
    ```json
    {
      "task_id": "b7a2f8c1-e5d6-4a3b-9c8d-7e6f5a4b3c2d",
      "status": "completed",
      "message": "Meeting attendance task stopped and final processing initiated.",
      "final_transcript_location": "Processing...", // Or actual location if immediately available
      "final_notes_location": "Processing..."
    }
    ```
*   **Example Error (404 Not Found):**
    ```json
    {
      "error": "Task not found",
      "details": "No active task with ID 'xyz' exists to stop."
    }
    ```
*   **Example Error (500 Internal Server Error):**
    ```json
    {
      "task_id": "b7a2f8c1-e5d6-4a3b-9c8d-7e6f5a4b3c2d",
      "status": "error",
      "message": "Failed to gracefully stop the task. Resources may still be active."
    }
    ```

## Authentication & Authorization

*   Initially, these worker endpoints are assumed to be called from the Next.js backend (BFF pattern) or directly from the frontend if deployed in a trusted environment.
*   The Next.js backend should authenticate the user before proxying requests to this worker.
*   The `user_id` field in `/start_meeting_attendance` is crucial for associating tasks with users, especially for multi-user deployments and for Notion integration (saving notes to the correct user's Notion workspace, permission checks, etc.).
*   Future enhancements might include API key authentication for direct worker access if needed.

## Data Storage (Conceptual)

*   **Transcripts & Notes:** The worker will eventually need to store the full transcripts and generated notes. The `final_transcript_location` and `final_notes_location` fields hint at this. Initially, this might be a local file system path within the container, or direct integration with Notion. For scalability, an object store (like S3) or a dedicated document database might be used.
*   **Task State:** The worker needs to maintain the state of active tasks. For a single-instance worker, this could be in-memory. For a scaled-out worker, a distributed cache/store like Redis would be necessary.

## Future Considerations

*   **Platform-Specific Auto-Join:** For platforms like Zoom, Teams, GMeet, implementing auto-join capabilities using their respective APIs (would require secure credential/token management).
*   **Real-time STT Integration:** Integrating with services like OpenAI Whisper (self-hosted or API), Google Cloud Speech-to-Text, AWS Transcribe, etc.
*   **Advanced Note-Taking/Summarization:** Using LLMs for more sophisticated summarization, action item extraction, and topic detection from the transcript.
*   **Direct Notion Integration:** Securely handling Notion API tokens (per user) to create and update pages directly.
*   **WebSockets for Real-time Updates:** Instead of polling `/meeting_attendance_status`, the frontend could connect via WebSockets for more immediate status updates, transcript previews, etc.
*   **Security:** Rate limiting, input validation, and ensuring that only authorized users can control tasks.
```
