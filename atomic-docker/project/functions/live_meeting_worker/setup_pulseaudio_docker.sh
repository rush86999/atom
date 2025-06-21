#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

echo "Starting PulseAudio setup..."

# Start PulseAudio daemon
# --system is generally not recommended for user sessions, but might be used in some Docker scenarios.
# Running as a system-wide instance or a user instance depends on the final user setup in Docker.
# For simplicity, starting as a user daemon (root in many default Docker containers, unless USER is specified).
# --exit-idle-time=-1: Keeps PulseAudio running indefinitely.
# --daemonize=true is implied by -D.
pulseaudio -D --verbose --exit-idle-time=-1 --log-target=stderr

# Wait a bit for PulseAudio to initialize
sleep 2

# Check if PulseAudio is running
if ! pactl info > /dev/null 2>&1; then
    echo "Error: PulseAudio daemon failed to start."
    # pulseaudio --kill # Attempt to kill if it's in a bad state
    # sleep 1
    # pulseaudio -D --verbose --exit-idle-time=-1 --log-target=stderr # Try again once
    # sleep 2
    # if ! pactl info > /dev/null 2>&1; then
    #    echo "Error: PulseAudio still not running after retry. Exiting."
    #    exit 1
    # fi
    # For now, let's assume if it fails the first time, we log and continue,
    # as deeper retry logic might depend on the specific environment.
    # The application using PulseAudio will likely fail later if it's not truly up.
fi
echo "PulseAudio server started (or attempted)."

# Create a virtual sink (output device / virtual speakers) for Zoom to use if needed.
# This helps in headless environments where no physical audio hardware is present.
# The SDK might require an output device to function correctly even if we only care about raw input.
# pactl load-module module-null-sink sink_name=zoom_virtual_speaker sink_properties=device.description="ZoomVirtualSpeaker"
# echo "Loaded null sink module as zoom_virtual_speaker."

# Create a virtual source (input device / virtual microphone) if needed.
# Sometimes useful for testing or if the SDK needs a default source.
# However, for raw data recording, we are usually interested in the *output* of the meeting.
# pactl load-module module-virtual-source source_name=zoom_virtual_mic source_properties=device.description="ZoomVirtualMic"
# echo "Loaded virtual source module as zoom_virtual_mic."

# Set default sink and source (optional, depends on SDK behavior)
# If the SDK defaults to system default, these can ensure it uses our virtual devices.
# pactl set-default-sink zoom_virtual_speaker
# pactl set-default-source zoom_virtual_mic
# echo "Set default sink and source."

# Configure Zoom SDK to use PulseAudio (or system default which should now be PulseAudio)
# This configuration tells the Zoom client (and thus SDK) to use the system's audio driver,
# which we've set up to be PulseAudio.
# The path depends on the USER running the Zoom SDK process.
# If running as root (common in Docker if USER is not set), it's /root/.config/....
# If running as a non-root user 'appuser', it would be /home/appuser/.config/...
ZOOM_CONFIG_DIR="/root/.config/zoomus.conf" # Default to root, adjust if USER is different
if [ -n "$HOME" ] && [ "$HOME" != "/" ]; then # Check if HOME is set and not root's /
    ZOOM_CONFIG_DIR="$HOME/.config/zoomus.conf"
fi
mkdir -p "$(dirname "${ZOOM_CONFIG_DIR}")"
cat <<EOF > "${ZOOM_CONFIG_DIR}"
[General]
system.audio.type=default
enableMonsterAudio=false
enableRawData=true
EOF
echo "Zoom SDK audio configuration written to ${ZOOM_CONFIG_DIR}"
chown -R "$(stat -c '%u:%g' "$(dirname "${ZOOM_CONFIG_DIR}")")" "$(dirname "${ZOOM_CONFIG_DIR}")" # Ensure correct ownership

echo "PulseAudio setup script finished."

# Execute the main command passed to this script
# This allows the script to be used as an ENTRYPOINT wrapper.
exec "$@"
