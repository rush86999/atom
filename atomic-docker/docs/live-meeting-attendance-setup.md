# Live Meeting Attendance: Setup and Usage Guide

## Overview

The Live Meeting Attendance feature allows Atom to join online meetings (Zoom, Google Meet, Microsoft Teams), transcribe the audio in real-time, and save the transcript as a note in Notion. This document guides you through setting up and using this feature.

## Prerequisites

Before using this feature, ensure the following are in place:

1.  **API Keys:**
    *   **Notion:** A Notion API key with permissions to create and update pages in your target database.
    *   **Deepgram:** A Deepgram API key for real-time transcription services.
    *   **OpenAI:** An OpenAI API key (used for potential post-processing or summarization, depending on configuration).
    These keys are typically provided in the `apiKeys` section of the request to the `attend_live_meeting` endpoint.

2.  **Atom Services:** The following Atom services must be running and correctly configured:
    *   **API Handler:** The main API endpoint that receives the request (e.g., `POST /api/gql/AttendLiveMeetingAction` or a direct Flask endpoint).
    *   **Kafka:** Apache Kafka service used for queuing meeting attendance tasks. The default topic is `atom_live_meeting_tasks`.
    *   **Live Meeting Worker (`live_meeting_worker`):** This worker consumes tasks from Kafka, controls the meeting agents (Zoom, Google Meet, etc.), and processes the audio.

## Audio Setup (Crucial)

Correct audio configuration is essential for the system to capture the meeting's audio (what you hear from participants) rather than just your microphone input.

### 1. Listing Available Audio Devices

The `live_meeting_worker` provides an HTTP endpoint to list all audio input devices it can detect. This is useful for identifying the correct `audio_device_specifier` to use.

*   **Endpoint:** `GET http://<worker_host>:8081/list_audio_devices`
    *   `<worker_host>`: The hostname or IP address of the machine running the `live_meeting_worker`.
    *   If the worker is running inside a Docker container, ensure port `8081` (or the configured port) is mapped/exposed to the host or network where you are making this request. For example, if running Docker locally, you might use `http://localhost:8081/list_audio_devices`.

*   **Example Output (JSON):**
    ```json
    [
      {
        "index": 0,
        "name": "MacBook Pro Microphone",
        "hostapi_name": "Core Audio",
        "max_input_channels": 1
      },
      {
        "index": 1,
        "name": "BlackHole 2ch",
        "hostapi_name": "Core Audio",
        "max_input_channels": 2
      },
      {
        "index": 3,
        "name": "pulse",
        "hostapi_name": "ALSA",
        "max_input_channels": 32
      },
      {
        "index": 7,
        "name": "monitor of Null Output",
        "hostapi_name": "ALSA",
        "max_input_channels": 2
      }
    ]
    ```

*   **Interpreting the Output:**
    *   `index`: A number you can use as the `audio_device_specifier`.
    *   `name`: A human-readable name for the device. You can often use a unique part of this name (case-insensitive substring match) as the `audio_device_specifier`.
    *   `hostapi_name`: The audio Host API (e.g., Core Audio for macOS, ALSA for Linux, MME/WASAPI/DirectSound for Windows).
    *   `max_input_channels`: The number of input channels the device supports. **Crucially, this must be greater than 0 for the device to be usable as an input source.**

### 2. Capturing Meeting Audio (Not Just Your Microphone)

By default, systems are configured to capture microphone input. To capture the audio *from* the meeting (i.e., what other participants are saying), you need to route your system's or the specific meeting application's audio output to a virtual input device. Atom will then listen to this virtual input.

**Conceptual Steps:**

*   **Windows:**
    1.  **Enable "Stereo Mix":** Some sound cards offer a "Stereo Mix" (or "What U Hear") input device. If available, enable it in your sound settings and set it as the default recording device *temporarily* to test, or select it via its name/index.
    2.  **Virtual Audio Cable:** Install a virtual audio cable program (e.g., VB-CABLE, VoiceMeeter).
        *   Configure your system or meeting application to output its sound to the *input* end of the virtual cable.
        *   The *output* end of this virtual cable then becomes an input device that Atom can use. Select this device by its name or index as the `audio_device_specifier`.

*   **macOS:**
    1.  **Virtual Audio Device Software:** Install software like BlackHole (free) or LoopBack (paid) or GroundControl CAST (free).
        *   Set your system's audio output (or the specific meeting application's output if possible) to this virtual device.
        *   This virtual device will then appear as an input source. Use its name (e.g., "BlackHole 2ch") or index as the `audio_device_specifier`.

*   **Linux (PulseAudio/PipeWire):**
    1.  **PulseAudio Loopback Module:**
        *   You can create a loopback module to route an application's output sink to a new virtual source.
        *   Example: `pactl load-module module-loopback sink_name=my_meeting_app_sink source_name=my_virtual_input source_properties=device.description="VirtualMeetingInput"`
        *   Then, configure your meeting application to output to `my_meeting_app_sink` (or its monitor source) and set `audio_device_specifier` to `VirtualMeetingInput` (or the monitor source of your actual output sink, e.g., "Monitor of Built-in Audio Analog Stereo").
    2.  **Graphical Tools:** Tools like Helvum or Catia (for PipeWire) or `pavucontrol` (PulseAudio Volume Control) can help you graphically route audio streams. Create a virtual source or route the meeting application's monitor stream.
    3.  **Agent Auto-Detection (Zoom on Linux):** For Zoom meetings on Linux, the agent will attempt to automatically find Zoom's audio output monitor source using `pactl` if no `audio_device_specifier` is provided. This is experimental and requires `pactl` to be installed and accessible. If it fails, it will fall back to the default input (likely your microphone).

**The `audio_device_specifier` you provide to Atom should be the name or index of this virtual input device that carries the meeting's audio.**

### 3. Passing `audio_device_specifier`

The selected device identifier (name or index from the `/list_audio_devices` endpoint, corresponding to your configured virtual input) must be included in the JSON payload when you call the `attend_live_meeting` API.

## Initiating Live Meeting Attendance

To start the live meeting attendance process, you typically send a POST request to an Atom API endpoint. This might be a GraphQL mutation (e.g., `AttendLiveMeetingAction`) or a direct REST endpoint.

*   **Example API Endpoint (Conceptual - refer to your specific Atom deployment):**
    `POST /api/gql/AttendLiveMeetingAction`
    or
    `POST /api/direct/attend_live_meeting`

*   **Example JSON Payload:**
    ```json
    {
      "platform": "zoom", // "zoom", "googlemeet", or "msteams"
      "meeting_identifier": "1234567890", // Meeting ID or full URL
      "notion_note_title": "My Important Meeting Notes",
      "handler_input": { // This structure might vary based on your API
        "api_keys": {
          "notion": "secret_YOUR_NOTION_KEY",
          "deepgram": "YOUR_DEEPGRAM_KEY",
          "openai": "sk-YOUR_OPENAI_KEY"
        },
        "audio_settings": {
          "audio_device_specifier": "BlackHole 2ch" // Or an index, e.g., 1
        },
        "user_id": "user_example_123", // The user associated with this task
        // Optional:
        // "notion_db_id": "your_notion_database_id_if_not_default",
        // "linked_event_id": "optional_calendar_event_id_for_linking"
      }
    }
    ```
    **Note:** The exact structure of `handler_input` might differ. Pay close attention to where `api_keys`, `audio_settings`, and `user_id` are expected. The `taskId` for status checking is usually returned in the response to this initial request.

## Checking Task Status

Once a meeting attendance task is initiated, you can check its status using a GET request to the following API endpoint:

*   **Endpoint:** `GET /api/meeting_attendance_status/[taskId]`
    *   Replace `[taskId]` with the actual task ID received from the initiation request.
*   **Authentication:** This endpoint is authenticated. You must be logged in to access it, and you can only view the status of tasks associated with your user ID.

*   **Example JSON Response:**
    ```json
    {
      "task_id": "c6b3e1f0-a21a-4e7a-95db-310998f8b3e8",
      "user_id": "user_example_123",
      "platform": "zoom",
      "meeting_identifier": "1234567890",
      "status_timestamp": "2023-10-27T10:30:00.123Z",
      "current_status_message": "Capturing Audio & Transcribing",
      "final_notion_page_url": null,
      "error_details": null,
      "created_at": "2023-10-27T10:25:00.456Z"
    }
    ```
    Or in case of failure:
    ```json
    {
      "task_id": "d7c4f2g1-b32b-5f8b-96ec-421aa9f9c4f9",
      "user_id": "user_example_456",
      "platform": "googlemeet",
      "meeting_identifier": "abc-defg-hij",
      "status_timestamp": "2023-10-27T11:05:10.789Z",
      "current_status_message": "Failed: Audio Device Error",
      "final_notion_page_url": null,
      "error_details": "Audio device error for GoogleMeetAgent: Specified audio device 'NonExistentDevice' not found as a valid input device.",
      "created_at": "2023-10-27T11:00:00.123Z"
    }
    ```

*   **Response Fields:**
    *   `task_id`: The unique ID of the task.
    *   `user_id`: The user who initiated the task.
    *   `platform`: Meeting platform (e.g., "zoom").
    *   `meeting_identifier`: ID or URL of the meeting.
    *   `status_timestamp`: When the `current_status_message` was last updated.
    *   `current_status_message`: Human-readable status (e.g., "Pending", "Joining Meeting", "Transcribing", "Failed: Audio device not found").
    *   `final_notion_page_url`: URL of the Notion page if successfully created (null otherwise).
    *   `error_details`: Detailed error message if the task failed (null otherwise).
    *   `created_at`: When the task was first registered.

## Troubleshooting

*   **Incorrect API Keys:** Ensure all API keys (Notion, Deepgram, OpenAI) are correct and have the necessary permissions.
*   **Audio Device Misconfiguration:** This is the most common issue.
    *   Use the `/list_audio_devices` endpoint on the worker to verify the device name/index.
    *   Double-check your system's audio routing to ensure meeting audio (not microphone) is sent to the device specified.
    *   Check `live_meeting_worker` logs for errors related to `SoundDeviceNotAvailableError` or `AudioDeviceSelectionError`. The logs often provide a list of available devices when selection fails.
*   **Services Not Running:** Verify that the API handler, Kafka, and `live_meeting_worker` are all running.
*   **Kafka Issues:** Check Kafka logs if tasks are not being picked up by the worker.
*   **Firewall/Network Issues:** Ensure the worker can reach the meeting platforms and the necessary API services (Notion, Deepgram, OpenAI). If the worker is containerized, check port mappings for the `/list_audio_devices` endpoint.
*   **Log Locations:**
    *   **Live Meeting Worker:** Contains detailed logs about agent instantiation, audio device selection, meeting joining, and transcription processes. This is the primary place to look for audio-related issues.
    *   **API Handler:** Logs for the initial request to start meeting attendance.
    *   **PostgreSQL:** Database logs for `meeting_attendance_status` table operations (less common for users to check).

## Administrative/Developer Notes

*   **Database Table:** Task statuses are stored in the `meeting_attendance_status` table in the PostgreSQL database.
*   **Kafka Topic:** The default Kafka topic for these tasks is `atom_live_meeting_tasks`.
*   **Agent Custom Exceptions:** The agents (`ZoomAgent`, `GoogleMeetAgent`, `MSTeamsAgent`) now raise specific exceptions like `SoundDeviceNotAvailableError` and `AudioDeviceSelectionError`, which are caught and logged by the `live_meeting_worker` and reflected in the task status.

This guide should help you set up and use the live meeting attendance feature effectively. For further assistance, consult the system logs or contact your system administrator.
