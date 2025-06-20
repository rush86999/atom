import asyncio
import subprocess
import platform
import os
import re
import sys # For stderr
from typing import Optional, AsyncIterator, Dict, Any

# Attempt to import sounddevice, but make it optional
try:
    import sounddevice as sd
    import numpy as np
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    print("Warning: sounddevice library not found. Real audio capture will not be available for ZoomAgent.", file=sys.stderr)
    # Dummy sd object for type hinting and basic class structure
    class DummySoundDevice:
        def __init__(self): pass
        def RawInputStream(self, *args, **kwargs): raise NotImplementedError("sounddevice not available")
        def query_devices(self, *args, **kwargs) -> list: return []
        def get_hostapi_info(self, *args, **kwargs) -> Dict[str, Any]: return {} # Return dict for type hints
        class PortAudioError(Exception): pass
        class CallbackFlags(int): pass # Dummy for type hint
    sd = DummySoundDevice()


class ZoomAgent:
    """
    ZoomAgent aims to interact with Zoom meetings. Its primary functionalities include:
    1. Launching/Joining Zoom meetings using system-level URL handlers.
    2. Capturing audio from a specified or default system audio input device.

    IMPORTANT AUDIO CAPTURE NOTE:
    By default, this agent will capture audio from the system's default microphone.
    To capture the actual meeting audio (i.e., what you hear from other participants),
    you MUST configure your system's audio routing. This typically involves:
    - Windows: Enabling "Stereo Mix" as an input device and setting it as default, or using a virtual audio cable.
    - macOS/Linux: Using software like BlackHole, LoopBeAudio, VB-Cable, or PulseAudio loopback module
      to route application output (Zoom's audio) to a virtual input device, then configuring this
      agent to use that virtual input device via the `ZOOM_AGENT_AUDIO_DEVICE_NAME_OR_ID` environment variable.
    Without proper audio routing, this agent will only capture microphone input, not the meeting's output audio.
    """
    def __init__(self, user_id: str, target_device_specifier_override: Optional[str] = None):
        self.user_id: str = user_id
        self.current_meeting_id: Optional[str] = None

        self.audio_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
        self.is_capturing: bool = False
        self.audio_stream: Optional[sd.RawInputStream] = None

        self.sample_rate: int = 16000
        self.channels: int = 1
        self.dtype: str = 'int16'

        self.target_device_specifier: Optional[str] = target_device_specifier_override or os.environ.get('ZOOM_AGENT_AUDIO_DEVICE_NAME_OR_ID')
        print(f"ZoomAgent initialized for user_id: {self.user_id}. Sounddevice available: {SOUNDDEVICE_AVAILABLE}. Target device spec: '{self.target_device_specifier}' (Override was: '{target_device_specifier_override}')")

    def _parse_meeting_id(self, meeting_url_or_id: str) -> Optional[str]:
        """Extracts meeting ID from a URL or returns the ID directly."""
        if "zoom.us/j/" in meeting_url_or_id:
            match = re.search(r'zoom.us/j/(\d+)', meeting_url_or_id)
            return match.group(1) if match else None
        elif meeting_url_or_id.replace(" ", "").isdigit() and len(meeting_url_or_id.replace(" ", "")) > 8:
            return meeting_url_or_id.replace(" ", "")
        print(f"ZoomAgent: Could not parse meeting ID from: {meeting_url_or_id}")
        return None

    def join_meeting(self, meeting_url_or_id: str, meeting_password: Optional[str] = None) -> bool:
        """
        Attempts to join a Zoom meeting by launching the Zoom client via URL.
        This is a synchronous operation as it just launches a process.
        """
        parsed_meeting_id = self._parse_meeting_id(meeting_url_or_id)
        if not parsed_meeting_id:
            print(f"ZoomAgent: Invalid meeting ID or URL format provided: {meeting_url_or_id}", file=sys.stderr)
            return False

        print(f"ZoomAgent ({self.user_id}): Attempting to join Zoom meeting: {parsed_meeting_id}")
        zoom_url = f"zoommtg://zoom.us/join?confno={parsed_meeting_id}"
        if meeting_password:
            zoom_url += f"&pwd={meeting_password}"

        try:
            system = platform.system()
            if system == "Windows": os.startfile(zoom_url)
            elif system == "Darwin": subprocess.Popen(['open', zoom_url])
            else: subprocess.Popen(['xdg-open', zoom_url])

            self.current_meeting_id = parsed_meeting_id
            print(f"ZoomAgent ({self.user_id}): Launched Zoom client for meeting: {self.current_meeting_id}. Manual interaction may be required in Zoom client.")
            return True
        except Exception as e:
            print(f"ZoomAgent ({self.user_id}): Failed to launch Zoom client for meeting {parsed_meeting_id}. Error: {e}", file=sys.stderr)
            self.current_meeting_id = None
            return False

    def _sd_callback(self, indata: np.ndarray, frames: int, time_info: Any, status: sd.CallbackFlags):
        """Sounddevice callback. Puts audio data into the asyncio queue."""
        if status: print(f"Sounddevice callback status: {status}", file=sys.stderr)
        if self.is_capturing:
            try: self.audio_queue.put_nowait(bytes(indata))
            except asyncio.QueueFull: print("ZoomAgent: Audio queue full, dropping audio frame.", file=sys.stderr)

    async def start_audio_capture(self, meeting_id_to_confirm: str) -> AsyncIterator[bytes]:
        """
        Starts capturing audio and yields audio chunks as an async generator.

        Audio Device Selection:
        - If `ZOOM_AGENT_AUDIO_DEVICE_NAME_OR_ID` env var is set (or override provided to __init__),
          it attempts to use that device. The value can be a device name (substring match) or an integer index.
        - If not set, it uses the system's default input device.
        - **CRITICAL:** For capturing Zoom meeting audio (not just microphone), system audio
          routing (e.g., Stereo Mix, VB-Cable, BlackHole) must be configured to route
          Zoom's output to the input device selected by this agent.

        Raises:
            ValueError: If the specified or default audio device is not found or unsuitable.
            RuntimeError: If the audio stream fails to open.
        """
        if not SOUNDDEVICE_AVAILABLE:
            print("ZoomAgent: Sounddevice not available. Cannot start real audio capture.", file=sys.stderr)
            if False: yield b'' # Ensure it's an async generator type even if it does nothing
            return

        if self.current_meeting_id != meeting_id_to_confirm:
            msg = f"ZoomAgent: Meeting ID mismatch. Current: '{self.current_meeting_id}', requested: '{meeting_id_to_confirm}'."
            print(msg, file=sys.stderr); raise ValueError(msg)

        if self.is_capturing or self.audio_stream:
            msg = f"ZoomAgent: Audio capture already active for meeting {self.current_meeting_id}."
            print(msg, file=sys.stderr); raise RuntimeError(msg)

        chosen_device_info = None
        try:
            devices = sd.query_devices()
            host_api_names = [api['name'] for api in sd.query_hostapis()]

            if self.target_device_specifier:
                print(f"ZoomAgent: Attempting to use specified audio device: '{self.target_device_specifier}'")
                try:
                    dev_idx = int(self.target_device_specifier)
                    if 0 <= dev_idx < len(devices): chosen_device_info = devices[dev_idx]
                except ValueError:
                    for dev in devices:
                        if self.target_device_specifier.lower() in dev.get('name', '').lower() and dev.get('max_input_channels', 0) > 0:
                            chosen_device_info = dev; break
                if not chosen_device_info or chosen_device_info.get('max_input_channels', 0) == 0:
                    msg = f"Specified audio device '{self.target_device_specifier}' not found or not an input device."
                    print(f"ZoomAgent: {msg} Available devices: {devices}", file=sys.stderr); raise ValueError(msg)
            else:
                print("ZoomAgent: ZOOM_AGENT_AUDIO_DEVICE_NAME_OR_ID not set.", file=sys.stdout)
                print("*************************************************************************************", file=sys.stdout)
                print("WARNING: Using system default input device. This will capture microphone audio.", file=sys.stdout)
                print("For Zoom meeting audio, ensure system audio (Zoom's output) is routed to this", file=sys.stdout)
                print("default input (e.g., via Stereo Mix, Loopback software). See agent documentation.", file=sys.stdout)
                print("*************************************************************************************", file=sys.stdout)
                default_input_idx = sd.default.device[0]
                if default_input_idx == -1 or default_input_idx >= len(devices) or devices[default_input_idx].get('max_input_channels', 0) == 0:
                    msg = "No suitable default audio input device found."
                    print(f"ZoomAgent: {msg} Default input index: {default_input_idx}. Available: {devices}", file=sys.stderr); raise ValueError(msg)
                chosen_device_info = devices[default_input_idx]

            if not chosen_device_info: raise ValueError("Could not determine a suitable audio input device.")

            device_id_for_stream = chosen_device_info['index']
            device_name_for_log = chosen_device_info.get('name', f"Index {device_id_for_stream}")
            host_api_idx = chosen_device_info.get('hostapi', -1)
            host_api_name = host_api_names[host_api_idx] if 0 <= host_api_idx < len(host_api_names) else "UnknownAPI"
            print(f"ZoomAgent: Selected audio device: '{device_name_for_log}' (Index: {device_id_for_stream}, HostAPI: {host_api_name}, MaxInputChannels: {chosen_device_info.get('max_input_channels')})")

        except Exception as e:
            msg = f"ZoomAgent: Error selecting audio device: {e}"
            print(msg, file=sys.stderr); raise ValueError(msg)


        self.is_capturing = True
        while not self.audio_queue.empty(): self.audio_queue.get_nowait(); self.audio_queue.task_done()

        print(f"ZoomAgent ({self.user_id}): Starting audio capture stream for meeting {self.current_meeting_id} on device '{device_name_for_log}'...")
        try:
            self.audio_stream = sd.RawInputStream(
                samplerate=self.sample_rate, channels=self.channels, dtype=self.dtype,
                device=device_id_for_stream, callback=self._sd_callback,
                blocksize=int(self.sample_rate * 0.1)
            )
            self.audio_stream.start()
            print(f"ZoomAgent: Audio stream active. Device: '{device_name_for_log}', Samplerate: {self.audio_stream.samplerate} Hz, Channels: {self.audio_stream.channels}")

            while self.is_capturing or not self.audio_queue.empty():
                try:
                    chunk = await asyncio.wait_for(self.audio_queue.get(), timeout=0.2)
                    if chunk is None: self.audio_queue.task_done(); break
                    yield chunk
                    self.audio_queue.task_done()
                except asyncio.TimeoutError:
                    if not self.is_capturing and self.audio_queue.empty(): break
                    continue

        except sd.PortAudioError as e:
            msg = f"ZoomAgent: PortAudioError opening audio stream on device '{device_name_for_log}': {e}"
            print(msg, file=sys.stderr)
            self.is_capturing = False; self.audio_stream = None
            raise RuntimeError(msg)
        except Exception as e:
            msg = f"ZoomAgent: Error during audio capture stream for {self.current_meeting_id} on device '{device_name_for_log}': {e}"
            print(msg, file=sys.stderr)
            self.is_capturing = False; self.audio_stream = None
            raise RuntimeError(msg)
        finally:
            print(f"ZoomAgent: Cleaning up audio stream for {self.current_meeting_id} (Device: '{device_name_for_log}')...")
            if self.audio_stream:
                if self.audio_stream.active: self.audio_stream.stop(); self.audio_stream.close()
                print("ZoomAgent: Sounddevice stream stopped and closed.")
            self.audio_stream = None; self.is_capturing = False
            if self.audio_queue.empty(): self.audio_queue.put_nowait(None)

    async def stop_audio_capture(self) -> None:
        if not self.is_capturing and not self.audio_stream:
            print(f"ZoomAgent ({self.user_id}): Audio capture not active.")
            return
        print(f"ZoomAgent ({self.user_id}): Stopping audio capture for {self.current_meeting_id}...")
        self.is_capturing = False
        if self.audio_stream:
            if self.audio_stream.active: self.audio_stream.stop(); self.audio_stream.close()
            self.audio_stream = None
            print("ZoomAgent: Sounddevice stream explicitly stopped/closed via stop_audio_capture.")
        try: self.audio_queue.put_nowait(None)
        except asyncio.QueueFull: print("ZoomAgent: Audio queue full sending stop sentinel.", file=sys.stderr)
        print(f"ZoomAgent ({self.user_id}): Audio capture stopped signal sent.")

    async def leave_meeting(self) -> None:
        print(f"ZoomAgent ({self.user_id}): Leaving meeting {self.current_meeting_id}...")
        if self.is_capturing or self.audio_stream:
            print(f"ZoomAgent ({self.user_id}): Audio capture active, stopping it first.")
            await self.stop_audio_capture()
        # Platform-specific commands to close Zoom (use with caution):
        # Windows: subprocess.run(['taskkill', '/F', '/IM', 'Zoom.exe'], check=False)
        # macOS: subprocess.run(['pkill', '-f', 'Zoom.us'], check=False)
        # Linux: subprocess.run(['pkill', '-f', 'zoom'], check=False)
        print(f"ZoomAgent ({self.user_id}): Left meeting {self.current_meeting_id}. (Note: Zoom application itself may still be open).")
        self.current_meeting_id = None

[end of atomic-docker/project/functions/agents/zoom_agent.py]
