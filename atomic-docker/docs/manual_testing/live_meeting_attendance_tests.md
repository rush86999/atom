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
    *   **Verification:** If possible (e.g., `docker exec -it live-meeting-worker bash` then `ls /tmp`), check that the `{task_id}_audio.wav` file is created in the worker's `/tmp` directory.

### Test Case 4: Monitor Task Status (Polling & Audio File Growth)

1.  **Action:** While a task is active (from Test Case 3), observe the UI, Network tab, and worker.
2.  **Expected Result (Frontend):**
    *   `GET` requests to `/meeting_attendance_status/{task_id}` continue.
    *   The "Task Status" section in the UI updates with:
        *   Status "active".
        *   Message like "Audio capture active."
        *   Increasing "Duration".
        *   "Transcript Preview" updating with "Captured Xs of audio...".
3.  **Expected Result (Worker Logs):**
    *   Log entries for requests to `/meeting_attendance_status/{task_id}`.
    *   No continuous per-second logs from the audio loop itself, but the `audio_callback` might log warnings if `status_flags` are present.
4.  **Expected Result (Worker File System - Manual Check):**
    *   If you have access to the worker container (`docker exec`), periodically check the size of `/tmp/{task_id}_audio.wav`. It should be increasing over time, indicating audio data is being written. `ls -lh /tmp/{task_id}_audio.wav`.

### Test Case 5: Stop Meeting Attendance (Verify File Finalization)

1.  **Action:** While a task is active, click the "Stop Attending Meeting" button.
2.  **Expected Result (Frontend):**
    *   The "Stop Attending Meeting" button might show a loading state.
    *   A `POST` request to `http://localhost:8001/stop_meeting_attendance/{task_id}`.
    *   The request should complete with 200 OK.
    *   The UI should update to show status `COMPLETED` and a message like "Audio capture stopped. Task completed. Audio saved to /tmp/{task_id}_audio.wav."
    *   "Final Transcript Location" should display the path to the WAV file (e.g., `/tmp/{task_id}_audio.wav`).
    *   Polling should stop.
    *   The "Stop Attending Meeting" button should hide or become disabled.
    *   The "Start Attending Meeting" button should become enabled again.
3.  **Expected Result (Worker Logs):**
    *   Log entry for request to `/stop_meeting_attendance/{task_id}`.
    *   Log entry "Task X: Signaling audio capture to stop."
    *   Log entry "Task X: Audio capture loop finished."
    *   Log entry "Task X: Cleaning up audio capture resources."
    *   Log entry "Task X: WAV file closed: /tmp/X_audio.wav".
    *   Log entry "Task X: Processing complete. Final status: completed".
    *   Task status in `active_tasks` should be `COMPLETED`.
4.  **Expected Result (Worker File System - Manual Check):**
    *   The file `/tmp/{task_id}_audio.wav` should exist and be a valid WAV file (can be copied out using `docker cp live-meeting-worker:/tmp/{task_id}_audio.wav .` and played if audio was captured).

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

This initial set of tests covers the main interactions and error conditions for real audio capture. More specific tests can be added as STT and other processing features are integrated.
```
