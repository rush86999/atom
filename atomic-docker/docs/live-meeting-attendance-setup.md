# Live Meeting Attendance: Setup and Usage Guide

## Overview

The Live Meeting Attendance feature allows Atom to join online meetings (Zoom, Google Meet, Microsoft Teams), transcribe the audio in real-time, and save the transcript as a note in Notion. This document guides you through setting up and using this feature.

## Prerequisites

Before using this feature, ensure the following are in place:

1.  **API Keys:**
    *   **Notion:** A Notion API key with permissions to create and update pages in your target database.
    *   **Deepgram:** A Deepgram API key for real-time transcription services.
    *   **OpenAI:** An OpenAI API key (used for potential post-processing or summarization, depending on configuration).
    *   **For Zoom (using the new SDK-based agent):**
        *   `ZOOM_SDK_KEY` and `ZOOM_SDK_SECRET`: Obtained by creating an SDK App on the Zoom Marketplace. Refer to the [Zoom SDK App Setup Guide](./zoom-sdk-app-setup.md) for detailed instructions on obtaining these. These credentials must be configured as environment variables for the service running the `attend_live_meeting` API handler. The handler will then include them in the message sent to the worker.

    All API keys (Notion, Deepgram, OpenAI, and conditionally Zoom SDK Key/Secret) are typically provided in the `handler_input` (or `handler_input.apiKeys`) section of the JSON request to the `attend_live_meeting` endpoint.

2.  **Atom Services:** The following Atom services must be running and correctly configured:
    *   **API Handler (`attend_live_meeting/handler.py`):** The main API endpoint that receives the request to join a meeting. This service now requires `ZOOM_SDK_KEY` and `ZOOM_SDK_SECRET` in its environment if the new Zoom SDK agent is to be used.
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
        *   Then, configure your meeting application to output to `my_meeting_app_sink` (or its monitor source) and set `audio_device_specifier` for **non-SDK agents** to `VirtualMeetingInput` (or the monitor source of your actual output sink, e.g., "Monitor of Built-in Audio Analog Stereo").
    2.  **Graphical Tools:** Tools like Helvum or Catia (for PipeWire) or `pavucontrol` (PulseAudio Volume Control) can help you graphically route audio streams for **non-SDK agents**.
    3.  **Agent Auto-Detection (Old Zoom Agent on Linux):** The older, sounddevice-based Zoom agent for Linux attempts to automatically find Zoom's audio output monitor source using `pactl` if no `audio_device_specifier` is provided. This is experimental and requires `pactl`. If it fails, it falls back to the default input. **This auto-detection does not apply to the new `NewZoomSdkAgent`.**

**For non-SDK agents (Google Meet, MS Teams, old Zoom agent), the `audio_device_specifier` you provide to Atom should be the name or index of this virtual input device that carries the meeting's audio.**

**For the `NewZoomSdkAgent` (for Zoom):**
*   Audio capture is managed *within* the Docker container using PulseAudio, as configured by `setup_pulseaudio_docker.sh` and `zoomus.conf` (which tells the SDK to use the default PulseAudio setup).
*   The `audio_device_specifier` parameter in the API call to `attend_live_meeting` is **effectively ignored** by the `NewZoomSdkAgent`. The SDK interacts with the PulseAudio environment inside the Docker container directly. You can still provide the parameter, but it will not influence device selection for this agent.
*   The primary audio source for the SDK agent is determined by how PulseAudio is configured within the Docker container (typically to capture all system sounds or a specific virtual output).

### 3. Passing `audio_device_specifier` (for non-SDK agents)

For Google Meet, MS Teams, or if using the older sounddevice-based Zoom agent, the selected device identifier (name or index from the `/list_audio_devices` endpoint, corresponding to your configured virtual input) must be included in the JSON payload when you call the `attend_live_meeting` API. For the `NewZoomSdkAgent`, this parameter is ignored.

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
      "handler_input": {
        // apiKeys are now directly under handler_input as per recent changes
        // This needs to be consistent with how attend_live_meeting/handler.py expects them.
        // Assuming handler_input itself is the apiKeys dictionary for simplicity here,
        // or it's a sub-object like handler_input.api_keys.
        // The example below assumes handler_input contains api_keys directly or nested.
        // For clarity, let's assume they are passed directly in handler_input for this example,
        // or adjust if your handler.py expects them under handler_input.api_keys.
        // **Crucially, for NewZoomSdkAgent, include zoom_sdk_key and zoom_sdk_secret here.**
        "notion_api_token": "secret_YOUR_NOTION_KEY",
        "deepgram_api_key": "YOUR_DEEPGRAM_KEY",
        "openai_api_key": "sk-YOUR_OPENAI_KEY",
        "zoom_sdk_key": "YOUR_ZOOM_SDK_KEY_IF_PLATFORM_IS_ZOOM_AND_USING_SDK_AGENT", // Required for NewZoomSdkAgent
        "zoom_sdk_secret": "YOUR_ZOOM_SDK_SECRET_IF_PLATFORM_IS_ZOOM_AND_USING_SDK_AGENT", // Required for NewZoomSdkAgent

        "audio_settings": { // This part remains for non-SDK agents, or if passing other audio-related settings
          "audio_device_specifier": "BlackHole 2ch" // Ignored by NewZoomSdkAgent, used by others
        },
        "user_id": "user_example_123", // The user associated with this task
        // Optional:
        // "notion_db_id": "your_notion_database_id_if_not_default",
        // "linked_event_id": "optional_calendar_event_id_for_linking"
      }
    }
    ```
    **Note:** The exact structure for providing API keys (directly in `handler_input` vs. `handler_input.apiKeys`) needs to match what `attend_live_meeting/handler.py` expects. The subtask for `handler.py` modification added `zoom_sdk_key` and `zoom_sdk_secret` to `kafka_message_payload['apiKeys']` by extracting them from `handler_input.get('zoom_sdk_key')`. So, the client calling the handler should place them within `handler_input`. The example above is updated to reflect this.
    The `taskId` for status checking is usually returned in the response to this initial request.

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

*   **Incorrect API Keys:** Ensure all API keys (Notion, Deepgram, OpenAI, and Zoom SDK Key/Secret if applicable) are correct, have necessary permissions, and are provided correctly in the `handler_input` of the request to `attend_live_meeting/handler.py`.
*   **Audio Device Misconfiguration (for non-SDK agents like Google Meet, MS Teams, or `OldZoomAgent`):**
    *   Use the `/list_audio_devices` endpoint on the worker to verify the device name/index.
    *   Double-check your system's audio routing to ensure meeting audio (not microphone) is sent to the device specified.
    *   Check `live_meeting_worker` logs for errors related to `SoundDeviceNotAvailableError` or `AudioDeviceSelectionError`.
*   **Services Not Running:** Verify that the API handler (`attend_live_meeting/handler.py`), Kafka, and `live_meeting_worker` are all running.
*   **Kafka Issues:** Check Kafka logs if tasks are not being picked up by the worker.
*   **Firewall/Network Issues:** Ensure the worker can reach the meeting platforms and the necessary API services. If the worker is containerized, check port mappings for the `/list_audio_devices` endpoint (port 8081).
*   **Zoom SDK Specific (`NewZoomSdkAgent`):**
    *   **Credential Errors:** Ensure `ZOOM_SDK_KEY` and `ZOOM_SDK_SECRET` are correctly provided in the `handler_input` of the API request to `attend_live_meeting/handler.py`. Verify that the `attend_live_meeting` handler service has these set in its environment and is passing them through.
    *   **Docker Build Issues:** Confirm that the `live_meeting_worker` Docker image (e.g., from `Dockerfile.zoom_sdk_worker`) was built successfully with the **actual Zoom Linux SDK libraries and the compiled C++ helper (`zoom_sdk_helper`)**. Check Docker build logs for warnings about missing files during the `COPY` steps for these components.
    *   **C++ Helper Logs:** Examine the `live_meeting_worker` logs for entries prefixed with `[CPP_HELPER_LOG]`. These are `stderr` outputs from the `zoom_sdk_helper` C++ application and can provide clues about SDK initialization, authentication failures, or meeting join issues. **Note:** The current C++ helper source code is a simulation. It will log its simulated actions, but full SDK interaction logs will only appear once it's fully implemented with the Zoom SDK.
    *   **PulseAudio Issues:** Problems with PulseAudio setup inside the Docker container (configured by `setup_pulseaudio_docker.sh`) can prevent the C++ helper from starting or capturing audio.
    *   **SDK Version Compatibility:** Ensure the downloaded Zoom Linux SDK version is compatible with the C++ helper code (once fully implemented).
*   **Log Locations:**
    *   **Live Meeting Worker (`live_meeting_worker.py`):** Contains detailed logs about agent instantiation, audio device selection (for non-SDK agents), meeting joining, transcription processes, and logs from `NewZoomSdkAgent` including C++ helper's stderr. This is the primary place to look for most issues.
    *   **API Handler (`attend_live_meeting/handler.py`):** Logs for the initial request processing and Kafka publishing status.
    *   **PostgreSQL:** Database logs for `meeting_attendance_status` table operations (less common for users to check).

## Architecture Details (Especially for Zoom with `NewZoomSdkAgent`)

The live meeting attendance feature, particularly for Zoom when using the `NewZoomSdkAgent`, involves several components:

1.  **API Handler (`attend_live_meeting/handler.py`):**
    *   Receives the initial HTTP request to join a meeting.
    *   Crucially, it extracts `ZOOM_SDK_KEY` and `ZOOM_SDK_SECRET` from the `handler_input` part of the API request. These credentials **must be provided by the client** making the call to this handler. The handler itself does not source them from its own environment variables directly for the worker payload, but relies on the client passing them in `handler_input`.
    *   Publishes a task message to a Kafka topic (`atom_live_meeting_tasks`), including all necessary API keys (Notion, Deepgram, OpenAI, and the provided Zoom SDK Key/Secret).

2.  **Kafka:**
    *   A message broker that queues the meeting attendance tasks.

3.  **Live Meeting Worker (`live_meeting_worker.py`):**
    *   Consumes tasks from Kafka.
    *   Updates task status in the PostgreSQL `meeting_attendance_status` table.
    *   **For Zoom (using `NewZoomSdkAgent`, if `USE_NEW_ZOOM_SDK_AGENT="true"`):**
        *   Instantiates `NewZoomSdkAgent.py` using the `zoom_sdk_key` and `zoom_sdk_secret` received in the Kafka message (which originated from the `handler_input` of the API call).
        *   The Python `NewZoomSdkAgent` generates a Zoom SDK JWT.
        *   It then launches a C++ helper application (`zoom_sdk_helper`) as a subprocess within its Docker container.
    *   **For other platforms (or `OldZoomAgent` for Zoom if `USE_NEW_ZOOM_SDK_AGENT="false"`):**
        *   Instantiates the respective Python-based agent (e.g., `GoogleMeetAgent`, `OldZoomAgent`). This will use the `audio_device_specifier`.

4.  **C++ Zoom SDK Helper (`zoom_sdk_helper` - for `NewZoomSdkAgent` only):**
    *   **Functionality:** A command-line application written in C++. It is launched by `NewZoomSdkAgent.py`. Its role is to initialize and authenticate with the Zoom Linux SDK using the JWT provided by `NewZoomSdkAgent.py`, join the specified Zoom meeting, access raw audio data from the meeting via SDK callbacks, and stream this raw PCM audio data to its standard output (`stdout`). It also logs operational messages and errors to its standard error (`stderr`).
    *   **Current Status:** The C++ source code for this helper (`atomic-docker/project/functions/agents/zoom_sdk_cpp_helper/`) is currently a **simulation**. It correctly handles command-line arguments, logs to `stderr`, and streams silent PCM data to `stdout`, but it does not yet contain the actual Zoom SDK integration logic. Full implementation with the Zoom Linux SDK is required for it to capture real meeting audio.
    *   **Environment:** Runs within the `live_meeting_worker` Docker container, utilizing the PulseAudio environment set up by `setup_pulseaudio_docker.sh`.

5.  **`NewZoomSdkAgent.py` (Python - for `NewZoomSdkAgent` only):**
    *   **Role:** Manages the lifecycle of the `zoom_sdk_helper` C++ subprocess (launching, monitoring, terminating).
    *   **Data Handling:** Reads the raw PCM audio data from the C++ helper's `stdout` and provides this audio stream (as an asynchronous iterator) to the `note_utils.py` module for transcription.
    *   **Logging:** Captures and logs the `stderr` output from the C++ helper, prefixing it with `[CPP_HELPER_LOG]`.
    *   **Audio Input:** The `audio_device_specifier` parameter (if provided in the API call) is **ignored** by `NewZoomSdkAgent`, as audio capture is handled internally by the C++ helper interacting with the Zoom SDK and the Docker container's PulseAudio environment.

**Environment Variable for Zoom Agent Selection:**
The `live_meeting_worker` service uses an environment variable `USE_NEW_ZOOM_SDK_AGENT` (boolean string, e.g., `"true"` or `"false"`, defaults to `"false"` if not set) to determine which Zoom agent to use:
*   If `USE_NEW_ZOOM_SDK_AGENT="true"`, the `NewZoomSdkAgent` (with the C++ helper) is used for Zoom tasks. This requires `ZOOM_SDK_KEY` and `ZOOM_SDK_SECRET` to be passed in the `handler_input` of the API call to `attend_live_meeting/handler.py`.
*   If `USE_NEW_ZOOM_SDK_AGENT="false"` (or the variable is not set), the `OldZoomAgent` (sounddevice-based) is used for Zoom tasks. This uses the `audio_device_specifier`.

## Administrative/Developer Notes

*   **Database Table:** Task statuses are stored in the `meeting_attendance_status` table in the PostgreSQL database. This table is crucial for tracking the progress and outcome of each attendance task.
*   **Kafka Topic:** The default Kafka topic for these tasks is `atom_live_meeting_tasks`.
*   **Agent Custom Exceptions:**
    *   Non-SDK agents (`OldZoomAgent`, `GoogleMeetAgent`, `MSTeamsAgent`) raise `SoundDeviceNotAvailableError` and `AudioDeviceSelectionError`.
    *   `NewZoomSdkAgent` raises `ZoomSdkAuthError`, `ZoomSdkAgentError`, and `ZoomSdkMeetingError`.
    These exceptions are caught by the `live_meeting_worker` and their details are recorded in the `meeting_attendance_status` table.
*   **Docker Setup for `NewZoomSdkAgent` (CRITICAL):**
    *   The `Dockerfile.zoom_sdk_worker` (or the primary worker Dockerfile if merged) is specifically designed to support the `NewZoomSdkAgent`. It includes:
        *   Installation of numerous system libraries required by the Zoom Linux SDK.
        *   Setup of PulseAudio for headless audio operation within the container via `setup_pulseaudio_docker.sh`.
        *   **Placeholders for Zoom SDK and C++ Helper:** The Dockerfile contains comments and placeholder `COPY` commands for:
            1.  The Zoom Linux SDK libraries (e.g., `.so` files).
            2.  The Zoom Linux SDK header files (e.g., `.h` files).
            3.  The pre-compiled `zoom_sdk_helper` C++ binary.
        *   **ACTION REQUIRED:** Administrators/developers **must manually download the Zoom Linux SDK** (specifically, the version for raw data access/recording if available) and place its components into the Docker build context before building the `live_meeting_worker` image.
            *   SDK library files (e.g., `libmeetingsdk.so`, `libzoom_rawdata.so`) should be placed in a directory named `zoom_sdk_libs_context/` within the build context of `live_meeting_worker`.
            *   SDK header files should be placed in `zoom_sdk_headers_context/`.
            *   The compiled `zoom_sdk_helper` binary (from `atomic-docker/project/functions/agents/zoom_sdk_cpp_helper/build/zoom_sdk_helper` after compiling it) should be placed in `cpp_helper_bin_context/`.
        *   Refer to the comments within `Dockerfile.zoom_sdk_worker` for precise instructions. **Without these manual steps, the `NewZoomSdkAgent` will not function correctly as the C++ helper will be missing or the SDK libraries will not be found.**
    *   **Compiling `zoom_sdk_helper`:** The C++ helper application (`atomic-docker/project/functions/agents/zoom_sdk_cpp_helper/`) needs to be compiled (e.g., using CMake as per its `README.md`). The resulting binary is what needs to be copied into the Docker build context. As noted, the current C++ source is a simulation; it needs to be fully implemented with the Zoom SDK for real audio capture.

This guide should help you set up and use the live meeting attendance feature effectively. For further assistance, consult the system logs or contact your system administrator.
