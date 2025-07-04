# Manual Testing Plan: Live Meeting Attendance

This document outlines the manual testing steps for the Live Meeting Attendance feature, focusing on the interaction between the frontend UI and the Python-based `live-meeting-worker`.

## Prerequisites

1.  **Environment Running:** The entire `atomic-docker` environment should be up and running (`docker-compose up --build`).
    *   This includes the `app` (frontend), `live-meeting-worker` (Python FastAPI), and all other supporting services.
2.  **User Login:** You must be logged into the Atom application.
3.  **Atom Agent Settings Page:** Navigate to the Atom Agent Settings page in the UI where the "Live Meeting Attendance" section is available.
    *   Typically `Settings -> Atom Agent Configuration` (or similar path).
4.  **Browser Developer Tools:** Have your browser's developer tools open (Network tab and Console tab) to monitor API requests and frontend logs.
5.  **Worker Logs:** Be prepared to check the logs of the `live-meeting-worker` container: `docker logs live-meeting-worker -f`.

## Test Cases

### Test Case 1: Verify UI and Initial State

1.  **Action:** Navigate to the Live Meeting Attendance settings section.
2.  **Expected Result:**
    *   The section title "Live Meeting Attendance" is displayed.
    *   Input fields for "Platform", "Meeting ID or Description", and "Notion Page Title" are visible and enabled.
    *   The "Refresh Audio Devices" button is visible and enabled.
    *   The "Select Audio Device" dropdown might be empty or show a loading state initially.
    *   The "Start Attending Meeting" button is visible. Its initial state might be disabled if no audio devices are selected yet.
    *   No task status information is displayed initially.
    *   No errors are shown.

### Test Case 2: List Audio Devices

1.  **Action:** Click the "Refresh Audio Devices" button.
2.  **Expected Result (Frontend):**
    *   The "Refresh Audio Devices" button might show a loading state (e.g., "Refreshing Devices...").
    *   The browser's Network tab should show a `GET` request to `http://localhost:8001/list_audio_devices` (or the configured worker URL).
    *   The request should complete with a 200 OK status.
    *   The response payload should be a JSON object like `{"devices": [{"id": "...", "name": "..."}, ...]}`.
    *   The "Select Audio Device" dropdown should be populated with the names and IDs of the devices returned by the worker.
    *   If devices are found, the first device in the list should be selected by default.
    *   If no devices are found by the worker, an appropriate message like "No audio input devices found..." should be displayed.
    *   Any errors during the fetch should be displayed in the UI (e.g., "Could not connect...").
3.  **Expected Result (Worker Logs):**
    *   Logs should show a request received for `/list_audio_devices`.
    *   Logs should indicate `sounddevice` querying devices (e.g., "Raw devices found:", "Filtered input devices:").
    *   If `sounddevice` fails (e.g., no audio hardware in Docker without specific setup), it should log the error and return the mock device: `[AudioDevice(id='mock_input_device', name='Mock Input Device (Error listing real devices)')]`. The UI should reflect this.

### Test Case 3: Start Meeting Attendance (Happy Path)

1.  **Action:**
    *   Ensure at least one audio device is listed and selected (e.g., "default" or the mock device).
    *   Select a "Platform" (e.g., "other").
    *   Enter a "Meeting ID or Description" (e.g., "Test Meeting 1").
    *   Enter a "Notion Page Title" (e.g., "Notes for Test Meeting 1").
    *   Click the "Start Attending Meeting" button.
2.  **Expected Result (Frontend):**
    *   The "Start Attending Meeting" button might show a loading state (e.g., "Starting..."). UI elements (inputs, device selection) should become disabled.
    *   A `POST` request to `http://localhost:8001/start_meeting_attendance` should be visible in the Network tab.
    *   The request payload should be JSON matching the input values, e.g.:
        ```json
        {
          "platform": "other",
          "meeting_id": "Test Meeting 1",
          "audio_device_id": "default", // or the selected device ID
          "notion_page_title": "Notes for Test Meeting 1",
          "user_id": "<your_supertokens_user_id>"
        }
        ```
    *   The request should complete with a 202 Accepted (or 200 OK if status is immediately active).
    *   The response payload should contain `task_id`, `status` (e.g., "pending" or "active"), and `message`.
    *   The "Task Status" section should appear in the UI, displaying the `task_id` and initial status/message.
    *   Polling should begin: `GET` requests to `/meeting_attendance_status/{task_id}` should appear every ~5 seconds.
    *   The "Stop Attending Meeting" button should become visible and enabled.
    *   The "Start Attending Meeting" button should become disabled.
3.  **Expected Result (Worker Logs):**
    *   Log entry for request to `/start_meeting_attendance` with the payload.
    *   Log entry indicating task creation.
    *   Log messages related to `sounddevice.InputStream` opening, such as:
        *   "Task X: Starting audio capture for device 'Y'. Saving to /tmp/X_audio.wav"
        *   "Task X: Audio stream opened. Sample rate: Z, Channels: C, Device: D"
    *   Task status should change to `ACTIVE`.
    *   The `transcript_preview` in the UI should update to "Captured Xs of audio...".
    *   **Verification:** Check worker logs for messages like "Starting audio capture for device..." and "Audio stream opened...". If possible (`docker exec -it live-meeting-worker bash`), verify `/tmp/{task_id}_audio.wav` is created.

### Test Case 4: Monitor Task Status (Polling & Audio File Growth)

1.  **Action:** While a task is active (from Test Case 3), observe the UI, Network tab, and worker.
2.  **Expected Result (Frontend):**
    *   `GET` requests to `/meeting_attendance_status/{task_id}` continue.
    *   UI updates:
        *   Status: "active".
        *   Message: "Audio capture active."
        *   Duration: Increasing.
        *   Transcript Preview: "Captured Xs of audio...".
3.  **Expected Result (Worker Logs):**
    *   Periodic logs for status requests.
    *   (If audio is very short and stop is quick) Logs related to STT processing might appear if capture finishes before extensive polling.
4.  **Expected Result (Worker File System - Manual Check):**
    *   Using `docker exec live-meeting-worker ls -lh /tmp/{task_id}_audio.wav`, verify the WAV file size increases.

### Test Case 5: Stop Meeting Attendance (Verify STT and File Cleanup)

1.  **Action:** While a task is active, click the "Stop Attending Meeting" button.
2.  **Expected Result (Frontend):**
    *   The "Stop Attending Meeting" button might show a loading state.
    *   A `POST` request to `http://localhost:8001/stop_meeting_attendance/{task_id}`.
    *   The request should complete with 200 OK.
    *   UI updates:
        *   Status: `COMPLETED`.
        *   Message: Should indicate success for STT, Notion page creation, and appending LLM-generated content (e.g., "...Summary added to Notion. Decisions added to Notion. Action items added to Notion. Task completed.").
        *   Transcript Preview: Shows full transcribed text.
        *   Notes Preview: Shows a snippet of the LLM-generated summary.
        *   Final Notes Location: Shows the URL of the Notion page.
    *   Polling should stop.
    *   "Stop Attending Meeting" button hides/disables.
    *   "Start Attending Meeting" button enables.
3.  **Expected Result (Worker Logs):**
    *   Logs for STT success.
    *   Logs for initial Notion page creation.
    *   Logs for LLM calls (summary, decisions, action items).
    *   Logs for appending each section to the Notion page.
    *   Log for temporary file deletion.
    *   Log "Processing complete. Final status: completed".
4.  **Expected Result (Worker File System - Manual Check):**
    *   Temporary WAV file `/tmp/{task_id}_audio.wav` should be deleted.
5.  **Expected Result (Notion):**
    *   Navigate to the URL from `final_notes_location`.
    *   Verify the Notion page exists with the correct title.
    *   Verify the page content includes:
        *   The full transcript.
        *   A "Summary" section with LLM-generated summary.
        *   A "Key Decisions" section with LLM-generated decisions (bulleted).
        *   An "Action Items" section with LLM-generated action items (bulleted, with assignees if found).

### Test Case 6: Start Meeting - Missing Required Fields

1.  **Action:**
    *   Do not select an audio device (if multiple are available and none pre-selected).
    *   Leave "Meeting ID" or "Notion Page Title" blank.
    *   Click "Start Attending Meeting".
2.  **Expected Result (Frontend):**
    *   A client-side validation error message should appear (e.g., "Please select an audio device.", "Meeting ID/URL and Notion Page Title are required.").
    *   No API call should be made to the worker.

### Test Case 7: Worker Not Running - List Audio Devices

1.  **Action:**
    *   Stop the `live-meeting-worker` container: `docker stop live-meeting-worker`.
    *   In the UI, click "Refresh Audio Devices".
2.  **Expected Result (Frontend):**
    *   The Network tab should show the request to `/list_audio_devices` failing (e.g., connection refused).
    *   The UI should display an error message like "Could not connect to the live meeting worker..." or "Failed to fetch audio devices...".
    *   The audio device list should be empty or show the error.

### Test Case 8: Worker Not Running - Start Meeting

1.  **Action:**
    *   Ensure `live-meeting-worker` is stopped.
    *   Fill in all required fields in the UI.
    *   Click "Start Attending Meeting".
2.  **Expected Result (Frontend):**
    *   The Network tab should show the request to `/start_meeting_attendance` failing.
    *   The UI should display an error message indicating the failure to initiate the task.
    *   No task status should be displayed.

### Test Case 9: Invalid Task ID for Status/Stop

1.  **Action (Manual API call if UI doesn't allow this directly, or if a task was cleared):**
    *   Attempt to get status for a non-existent task ID: `GET http://localhost:8001/meeting_attendance_status/invalid-task-id`
    *   Attempt to stop a non-existent task ID: `POST http://localhost:8001/stop_meeting_attendance/invalid-task-id`
2.  **Expected Result (API Response):**
    *   The worker should return a 404 Not Found error with a JSON detail message (e.g., `{"detail":"Task not found: invalid-task-id"}`).
3.  **Expected Result (Frontend, if interaction leads to this):**
    *   If the UI attempts this after a task is cleared (e.g. worker restarted), it should handle the 404 gracefully, perhaps by clearing the current task display and showing an error.

### Test Case 10: Task Lifecycle (Natural Completion - if applicable)

*Note: The current `audio_capture_loop` runs indefinitely until explicitly stopped or an error occurs. This test case would apply if a maximum duration were implemented in the worker.*

1.  **Action:** Start a meeting attendance task. Let it run until any implemented maximum duration or until it stops naturally (if applicable).
2.  **Expected Result (Frontend & Worker):**
    *   The task progresses through `ACTIVE` state.
    *   If a max duration is hit, the worker should automatically stop capture, finalize the WAV file, and transition status to `COMPLETED`.
    *   The UI reflects these changes, polling stops, and the final WAV file path is shown.

### Test Case 11: Audio Device Access Error (Difficult to force, but conceptual)

1.  **Action (Conceptual - if a device is listed but becomes unavailable or has permission issues *after* selection but *before* stream start):**
    *   Select a problematic audio device (if one can be identified or simulated).
    *   Click "Start Attending Meeting".
2.  **Expected Result (Worker Logs):**
    *   A `sd.PortAudioError` should be logged (e.g., "Invalid device ID", "Device unavailable").
    *   The task status should become `ERROR`.
    *   The task message should indicate an "Audio device error".
3.  **Expected Result (Frontend):**
    *   The UI should display the error status and message from the worker.
    *   Polling might stop or continue, showing the error state.
    *   The "Start Attending Meeting" button should become enabled again.

### Test Case 12: STT Failure (e.g., No API Key)

1.  **Action:**
    *   Ensure the `live-meeting-worker` is started **without** the `OPENAI_API_KEY` environment variable (e.g., comment it out in `docker-compose.yaml` and restart the service: `docker-compose up -d --force-recreate live-meeting-worker`).
    *   Perform Test Case 3 (Start Meeting).
    *   Let the capture run for a short duration (e.g., 10-15 seconds).
    *   Perform Test Case 5 (Stop Meeting).
2.  **Expected Result (Worker Logs):**
    *   Worker logs should show "OPENAI_API_KEY environment variable not found. STT functionality will be disabled." upon startup (or "OpenAI client not available. Skipping STT." during processing).
    *   Audio capture logs should appear normal.
    *   When STT is attempted, logs should indicate it was skipped or failed due to no client/key.
    *   Logs for temporary file deletion should still appear.
3.  **Expected Result (Frontend):**
    *   Task status message upon completion should indicate STT failure/skip (e.g., "Transcription failed or was skipped. Audio file available. Task completed.").
    *   `transcript_preview` should be empty or show the "Captured Xs of audio..." message, but not a transcript.
    *   `final_transcript_location` should still show the path where the WAV file *was*.
    *   `final_notes_location` should be null.
    *   Task should still transition to `COMPLETED`.
4.  **Action (Post-test):** Remember to restore the `OPENAI_API_KEY` in `docker-compose.yaml` and restart the worker if you modified it.

### Test Case 13: Notion Failure (e.g., Invalid API Key or Parent Page ID)

1.  **Action:**
    *   Ensure `OPENAI_API_KEY` is correctly set.
    *   Set an invalid `NOTION_API_KEY` or an invalid/inaccessible `NOTION_PARENT_PAGE_ID` for the `live-meeting-worker` (e.g., via `docker-compose.yaml` and restart).
    *   Perform Test Case 3 (Start Meeting).
    *   Let capture run for 10-15 seconds.
    *   Perform Test Case 5 (Stop Meeting).
2.  **Expected Result (Worker Logs):**
    *   STT processing logs should appear normal and successful.
    *   Logs should indicate an attempt to create a Notion page.
    *   Logs should show a "Notion API error" or "Failed to initialize Notion client" (if key is totally missing/malformed at startup) or "Notion client not available".
    *   Logs for temporary file deletion should still appear.
3.  **Expected Result (Frontend):**
    *   Task status message upon completion should indicate STT success but Notion failure (e.g., "Transcription successful. Failed to save notes to Notion. Task completed.").
    *   `transcript_preview` should contain the transcript.
    *   `final_notes_location` should be null.
    *   Task should still transition to `COMPLETED`.
4.  **Action (Post-test):** Restore correct Notion env vars and restart worker.

### Test Case 14: LLM Content Generation Failure/Empty Response

1.  **Action:**
    *   (Difficult to force directly without altering LLM responses or prompts significantly)
    *   Conceptually, if the LLM calls for summary, decisions, or action items were to fail (e.g., API error, or model returns empty/unusable content like "I cannot summarize this."), this test would verify graceful handling.
    *   Alternatively, test with a very short, nonsensical transcript that might lead to empty LLM outputs for summary/decisions/actions.
2.  **Expected Result (Worker Logs):**
    *   Logs indicating successful STT and initial Notion page creation.
    *   Logs for LLM calls, potentially followed by warnings like "LLM generated an empty or trivial summary" or "LLM reported no specific decisions."
    *   Logs for Notion append attempts (which might append nothing or just headings if content is empty).
3.  **Expected Result (Frontend):**
    *   Task completes. Message might indicate partial success (e.g., "Transcript saved to Notion. Summary generation skipped.").
    *   `notes_preview` might be empty or show the transcript snippet.
4.  **Expected Result (Notion):**
    *   The main transcript should be on the Notion page.
    *   Sections for Summary, Decisions, Action Items might have headings but be empty, or show fallback text like "(No summary generated)" if we implement that.

This set of tests covers audio capture, STT, Notion integration, and basic LLM-generated content.
```
