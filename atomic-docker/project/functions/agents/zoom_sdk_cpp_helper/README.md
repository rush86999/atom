# Zoom SDK C++ Helper for Raw Audio Recording

This C++ application uses the Zoom Linux SDK to join a Zoom meeting and stream raw audio data (PCM) to standard output (`stdout`). It is intended to be called by a parent Python process (e.g., `NewZoomSdkAgent` in Atom) which will provide the necessary meeting parameters and consume the audio stream.

## Features

*   Joins a specified Zoom meeting.
*   Authenticates using an SDK JWT (JSON Web Token).
*   Captures raw audio data from the meeting.
*   Outputs raw PCM audio data to `stdout`.
*   Logs status messages and errors to `stderr`.

## Command-Line Arguments

*   `--meeting_id <ID>`: (Required) The Zoom Meeting ID.
*   `--token <SDK_JWT>`: (Required) The SDK JWT for authentication with the Zoom SDK.
*   `--password <PASSWORD>`: (Optional) The password for the Zoom meeting, if required.
*   `--sample_rate <RATE>`: (Optional) The desired sample rate for the audio output (e.g., 16000, 32000, 48000). Defaults to 16000 Hz.
*   `--channels <CHANNELS>`: (Optional) The desired number of audio channels (e.g., 1 for mono, 2 for stereo). Defaults to 1 (mono). Note: The actual output might depend on what the Zoom SDK provides.

## Dependencies

*   Zoom Linux SDK (headers and libraries).
*   A C++17 compliant compiler (e.g., g++).
*   CMake (version 3.10 or higher).
*   Standard Linux development libraries (e.g., `pthread`, `glib-2.0`).

## Building

1.  **Ensure Zoom SDK is available:**
    *   Download the Zoom Linux SDK (e.g., from the Zoom Marketplace).
    *   Extract the SDK. You'll need the header files (usually in an `h` or `include` directory) and the library files (e.g., `libmeetingsdk.so`, `libzoom_rawdata.so`, etc., usually in a `lib` directory).
    *   Place them in a known location or update `CMakeLists.txt` to point to their paths. For Docker builds, these will be copied into the build environment.

2.  **Configure and Build with CMake:**
    ```bash
    cd path/to/zoom_sdk_cpp_helper
    mkdir build
    cd build
    # Example: cmake -DZOOM_SDK_PATH=/path/to/your/zoom_sdk_linux_x86_64_VERSION ..
    # If ZOOM_SDK_PATH is not set, it will assume SDK files are in standard system paths
    # or a path known to the Docker build environment.
    cmake ..
    make
    ```
    The compiled executable `zoom_sdk_helper` will be in the `build` directory.

## Running

The application is typically run by the parent Python script. To run it manually for testing:

```bash
./build/zoom_sdk_helper --meeting_id 1234567890 --token "YOUR_SDK_JWT_HERE" --password "OPTIONAL_PASSWORD" > audio_output.pcm
```

*   Replace placeholders with actual values.
*   `audio_output.pcm` will contain the raw PCM audio data.
*   Check `stderr` for logs and error messages.

## Audio Output Format

The default audio output format to `stdout` is:
*   **Sample Rate:** 16000 Hz (configurable via `--sample_rate`)
*   **Channels:** 1 (mono) (configurable via `--channels`)
*   **Bit Depth:** 16-bit signed little-endian PCM.

This format is suitable for most speech-to-text engines.
