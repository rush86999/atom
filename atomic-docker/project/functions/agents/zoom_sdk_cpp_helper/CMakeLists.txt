cmake_minimum_required(VERSION 3.10)
project(ZoomSdkHelper LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# Option to specify the path to the Zoom SDK (useful for local builds)
# For Docker, this path might be fixed (e.g., /usr/local/zoom_sdk)
option(ZOOM_SDK_PATH "Path to the Zoom Linux SDK root directory" "")

# --- Find or set Zoom SDK paths ---
if(ZOOM_SDK_PATH)
    set(ZOOM_SDK_INCLUDE_DIR ${ZOOM_SDK_PATH}/h)
    set(ZOOM_SDK_LIB_DIR ${ZOOM_SDK_PATH}/lib/linux_x86_64) # Common structure for Zoom SDK
    message(STATUS "Using ZOOM_SDK_PATH: ${ZOOM_SDK_PATH}")
    message(STATUS "Zoom SDK Include Dir: ${ZOOM_SDK_INCLUDE_DIR}")
    message(STATUS "Zoom SDK Lib Dir: ${ZOOM_SDK_LIB_DIR}")
else()
    # Assume SDK headers and libs are in standard system paths or will be provided by the build environment
    # e.g., /usr/local/include/zoom_sdk and /usr/local/lib/zoom_sdk for Docker.
    # These paths are placeholders and might need adjustment in the Dockerfile.
    set(ZOOM_SDK_INCLUDE_DIR "/usr/local/include/zoom_sdk_raw_data") # Placeholder
    set(ZOOM_SDK_LIB_DIR "/usr/local/lib/zoom_sdk") # Placeholder
    message(STATUS "ZOOM_SDK_PATH not specified. Using default SDK paths (for Docker build):")
    message(STATUS "  Include: ${ZOOM_SDK_INCLUDE_DIR}")
    message(STATUS "  Lib: ${ZOOM_SDK_LIB_DIR}")
endif()

include_directories(
    src
    ${ZOOM_SDK_INCLUDE_DIR}
    # Add other necessary include directories from the Zoom SDK if they exist, e.g.
    # ${ZOOM_SDK_PATH}/meeting_sdk/include (if Meeting SDK has separate includes)
)

# --- Find System Libraries (Example: GLib-2.0) ---
# The Zoom Raw Recording sample often uses GLib for main loop, etc.
find_package(PkgConfig REQUIRED)
pkg_check_modules(GLIB REQUIRED glib-2.0)
include_directories(${GLIB_INCLUDE_DIRS})
link_directories(${GLIB_LIBRARY_DIRS}) # Not always needed if libs are in standard paths

# Add source files
add_executable(zoom_sdk_helper
    src/main.cpp
    src/zoom_sdk_helper.cpp
)

# --- Link Libraries ---
# Placeholder names for Zoom SDK libraries. These names might vary based on the SDK version.
# Common libraries from Zoom SDK:
# - libmeetingsdk.so (Core Meeting SDK)
# - libzoom_rawdata.so (For raw data access)
# - libjson.so (Often bundled for JSON parsing)
# - libcrypto.so, libssl.so (Bundled SSL/Crypto)
# The exact linking method (direct path or find_library) depends on how SDK is structured.

# Example of linking directly if libraries are in ZOOM_SDK_LIB_DIR
# Ensure these .so files exist or adjust names.
# Using absolute paths for libraries:
set(ZOOM_MEETING_SDK_LIB ${ZOOM_SDK_LIB_DIR}/libmeetingsdk.so)
set(ZOOM_RAWDATA_LIB ${ZOOM_SDK_LIB_DIR}/libzoom_rawdata.so)
# Add other SDK libs as needed, e.g., libjson, crypto, ssl if they are separate
# and not automatically linked by libmeetingsdk or libzoom_rawdata.

target_link_libraries(zoom_sdk_helper
    PRIVATE
    # Zoom SDK Libraries (Using placeholders, actual names/paths might differ)
    # It's common to link the specific .so files.
    # If Zoom provides a CMake find script, that would be preferable.
    ${ZOOM_MEETING_SDK_LIB}
    ${ZOOM_RAWDATA_LIB}
    # Other system libraries
    pthread
    ${GLIB_LIBRARIES} # From pkg_check_modules
    dl # For dynamic loading if SDK uses it
    rt
)

# Set RPATH to find Zoom SDK libraries at runtime if they are not in standard system paths
# This is important if ZOOM_SDK_LIB_DIR is a custom path.
if(ZOOM_SDK_PATH)
    set(CMAKE_INSTALL_RPATH "${ZOOM_SDK_LIB_DIR}")
    set(CMAKE_BUILD_WITH_INSTALL_RPATH TRUE)
    target_link_options(zoom_sdk_helper PRIVATE "-Wl,-rpath,${ZOOM_SDK_LIB_DIR}")
endif()

install(TARGETS zoom_sdk_helper DESTINATION bin)

# Simple CTest setup (optional, but good practice)
enable_testing()
add_test(NAME ZoomSdkHelperRuns
    COMMAND zoom_sdk_helper --meeting_id test --token test # Basic invocation test
)
# This test will fail if the program exits with non-zero, e.g. due to missing args.
# More sophisticated tests would require mocking or a running Zoom instance.

message(STATUS "ZoomSdkHelper project configured. Executable will be: ${CMAKE_BINARY_DIR}/zoom_sdk_helper")
