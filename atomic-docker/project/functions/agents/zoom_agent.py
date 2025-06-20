import asyncio
import subprocess
import platform
import os
import re
from typing import Optional, AsyncIterator

# Attempt to import sounddevice, but make it optional for environments where it can't be installed
# or for testing the non-audio parts of the agent.
try:
    import sounddevice as sd
    import numpy as np # Often a dependency/used with sounddevice
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    print("Warning: sounddevice library not found. Real audio capture will not be available.")
    # Define a dummy sd object if not available, so parts of the class can be defined.
    class DummySoundDevice:
        def __init__(self): pass
        def RawInputStream(self, *args, **kwargs): raise NotImplementedError("sounddevice not available")
        def query_devices(self, *args, **kwargs): return [] if args else {} # Match behavior
    sd = DummySoundDevice()


class ZoomAgent:
    """
    A conceptual agent for interacting with Zoom meetings, including joining,
    and capturing audio via the system's default microphone.
    This agent is designed to be used with asyncio.
    """
    def __init__(self, user_id: str):
        self.user_id: str = user_id
        self.current_meeting_id: Optional[str] = None

        self.audio_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
        self.is_capturing: bool = False
        self.audio_stream: Optional[sd.RawInputStream] = None # For sounddevice stream

        self.sample_rate: int = 16000 # Hz, common for voice
        self.channels: int = 1 # Mono
        self.dtype: str = 'int16' # Data type for audio samples

        print(f"ZoomAgent initialized for user_id: {self.user_id}. Sounddevice available: {SOUNDDEVICE_AVAILABLE}")

    def _parse_meeting_id(self, meeting_url_or_id: str) -> Optional[str]:
        """Extracts meeting ID from a URL or returns the ID directly."""
        if "zoom.us/j/" in meeting_url_or_id:
            match = re.search(r'zoom.us/j/(\d+)', meeting_url_or_id)
            return match.group(1) if match else None
        elif meeting_url_or_id.isdigit() and len(meeting_url_or_id) > 8: # Basic check for a raw ID
            return meeting_url_or_id
        return None

    def join_meeting(self, meeting_url_or_id: str, meeting_password: Optional[str] = None) -> bool:
        """
        Attempts to join a Zoom meeting by launching the Zoom client via URL.
        """
        parsed_meeting_id = self._parse_meeting_id(meeting_url_or_id)
        if not parsed_meeting_id:
            print(f"ZoomAgent: Invalid meeting ID or URL format: {meeting_url_or_id}")
            return False

        print(f"ZoomAgent ({self.user_id}): Attempting to join Zoom meeting: {parsed_meeting_id}")

        # Construct Zoom meeting URL
        zoom_url = f"zoommtg://zoom.us/join?confno={parsed_meeting_id}"
        if meeting_password:
            zoom_url += f"&pwd={meeting_password}"

        try:
            system = platform.system()
            if system == "Windows":
                os.startfile(zoom_url)
            elif system == "Darwin": # macOS
                subprocess.Popen(['open', zoom_url])
            else: # Linux and other Unix-like
                subprocess.Popen(['xdg-open', zoom_url])

            self.current_meeting_id = parsed_meeting_id
            print(f"ZoomAgent ({self.user_id}): Successfully launched Zoom client for meeting: {self.current_meeting_id}")
            return True
        except Exception as e:
            print(f"ZoomAgent ({self.user_id}): Failed to launch Zoom client for meeting {parsed_meeting_id}. Error: {e}")
            self.current_meeting_id = None
            return False

    def _sd_callback(self, indata: np.ndarray, frames: int, time_info, status: sd.CallbackFlags):
        """Sounddevice callback to queue audio data."""
        if status:
            print(f"Sounddevice callback status: {status}", file=sys.stderr)
        if self.is_capturing:
            try:
                self.audio_queue.put_nowait(bytes(indata))
            except asyncio.QueueFull:
                print("ZoomAgent: Audio queue full, dropping frame.", file=sys.stderr)
        # If not capturing, data is ignored.

    async def start_audio_capture(self, meeting_id_to_confirm: str) -> AsyncIterator[bytes]:
        """
        Starts capturing audio from the system's default input device (or configured device)
        and yields audio chunks. This is an async generator.
        """
        if not SOUNDDEVICE_AVAILABLE:
            print("ZoomAgent: Sounddevice not available, cannot start real audio capture.")
            # Yield one empty chunk then stop, to satisfy async generator contract if called
            if False: yield b'' # Make it a generator
            return

        if self.current_meeting_id != meeting_id_to_confirm:
            msg = f"ZoomAgent: Meeting ID mismatch. Currently in '{self.current_meeting_id}', requested capture for '{meeting_id_to_confirm}'."
            print(msg)
            raise ValueError(msg)

        if self.is_capturing or self.audio_stream:
            print(f"ZoomAgent: Audio capture already in progress for meeting {self.current_meeting_id}.")
            # This should ideally not happen if logic is correct.
            # If it does, one might choose to stop the old one or raise an error.
            # For now, let's assume the caller manages this state correctly.
            # If we want to allow "re-starting" on an existing stream, that's more complex.
            # For this version, we'll just yield from the existing queue if is_capturing is true.
            # However, the problem is a new call to start_audio_capture implies a new consumer.
            # The current model of one queue per agent instance is simpler.
            # If this function is called again while already capturing, it's likely a logical error.
            # We will let it proceed to create a new stream if self.audio_stream is None,
            # but if self.is_capturing is True and stream exists, it's problematic.
            # Safest is to raise error or return if already capturing.
            raise RuntimeError("Audio capture is already active.")


        device_name_or_idx = os.environ.get("ZOOM_AGENT_AUDIO_DEVICE")
        selected_device = None
        if device_name_or_idx:
            try: # Try as int (index) first
                selected_device = int(device_name_or_idx)
            except ValueError: # Then as string (name)
                selected_device = device_name_or_idx
            print(f"ZoomAgent: Using configured audio device: {device_name_or_idx}")
        else:
            print("ZoomAgent: ZOOM_AGENT_AUDIO_DEVICE not set, using default input device.")
            # Default device is used if `device=None` in RawInputStream

        self.is_capturing = True
        # Clear queue in case it has old data (e.g. sentinel from previous stop)
        while not self.audio_queue.empty():
            self.audio_queue.get_nowait()
            self.audio_queue.task_done() # Should be empty, but good practice

        print(f"ZoomAgent ({self.user_id}): Starting audio capture for meeting {self.current_meeting_id}...")
        try:
            self.audio_stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                device=selected_device,
                callback=self._sd_callback,
                blocksize=int(self.sample_rate * 0.1) # 100ms chunks
            )
            self.audio_stream.start()
            print(f"ZoomAgent: Audio stream started. Device: {self.audio_stream.device}, Samplerate: {self.audio_stream.samplerate}")

            while self.is_capturing or not self.audio_queue.empty():
                try:
                    chunk = await asyncio.wait_for(self.audio_queue.get(), timeout=0.1) # Timeout to allow checking is_capturing
                    if chunk is None:  # Sentinel value indicates stop
                        print("ZoomAgent: Sentinel received from audio queue. Ending capture stream.")
                        self.audio_queue.task_done()
                        break
                    yield chunk
                    self.audio_queue.task_done()
                except asyncio.TimeoutError:
                    if not self.is_capturing and self.audio_queue.empty():
                        break # Exit if capture stopped and queue is drained
                    continue # Continue waiting if capturing or queue might still get data

        except Exception as e:
            print(f"ZoomAgent: Error during audio capture stream for {self.current_meeting_id}. Error: {e}")
            self.is_capturing = False # Ensure flag is reset on error
            # We might want to put a final None or re-raise to signal error to consumer
            raise # Re-raise the exception so the caller is aware
        finally:
            print(f"ZoomAgent: Cleaning up audio stream for {self.current_meeting_id}...")
            if self.audio_stream:
                if self.audio_stream.active:
                    self.audio_stream.stop()
                self.audio_stream.close()
                print("ZoomAgent: Sounddevice stream stopped and closed.")
            self.audio_stream = None
            self.is_capturing = False # Redundant but safe
            # Ensure any remaining consumer waiting on queue.get() is unblocked if loop exited early
            if self.audio_queue.empty(): # Check to avoid error if already put by stop_audio_capture
                 self.audio_queue.put_nowait(None)


    async def stop_audio_capture(self) -> None:
        """Stops the active audio capture stream."""
        if not self.is_capturing and not self.audio_stream:
            print(f"ZoomAgent ({self.user_id}): Audio capture is not currently active.")
            return

        print(f"ZoomAgent ({self.user_id}): Stopping audio capture for meeting {self.current_meeting_id}...")
        self.is_capturing = False # Signal callback and generator to stop

        if self.audio_stream:
            if self.audio_stream.active:
                self.audio_stream.stop()
                self.audio_stream.close() # Ensure resources are released
                print("ZoomAgent: Sounddevice stream explicitly stopped and closed.")
            self.audio_stream = None

        try:
            # Put sentinel value to unblock the generator if it's waiting on queue.get()
            self.audio_queue.put_nowait(None)
        except asyncio.QueueFull:
            print("ZoomAgent: Audio queue full while trying to send stop sentinel. Consumer might be stuck.")
            # This case is less likely if the generator is actively consuming.
            # If queue is full, we might need to clear it or handle differently.

        # Optional: Wait for the queue to be fully processed if using task_done/join
        # However, the generator itself handles task_done. If it's already exited or will exit due to sentinel,
        # join() might not be necessary or could hang if task_done() wasn't called for the sentinel.
        # For simplicity, we rely on the sentinel to terminate the generator loop.
        # If strict "all items processed" guarantee is needed before this function returns,
        # one might `await self.audio_queue.join()` but ensure sentinel is handled with task_done.
        print(f"ZoomAgent ({self.user_id}): Audio capture stopped.")

    async def leave_meeting(self) -> None:
        """Stops audio capture and leaves the current Zoom meeting."""
        print(f"ZoomAgent ({self.user_id}): Attempting to leave meeting {self.current_meeting_id}.")
        if self.is_capturing or self.audio_stream:
            print(f"ZoomAgent ({self.user_id}): Audio capture is active, stopping it first.")
            await self.stop_audio_capture()

        # Placeholder for actual "leave meeting" SDK call or UI automation
        # For now, we just log and reset state.
        # Future, more aggressive options for closing Zoom:
        # - Windows: subprocess.run(['taskkill', '/F', '/IM', 'Zoom.exe'], check=False)
        # - macOS: subprocess.run(['pkill', '-f', 'Zoom.us'], check=False)
        # - Linux: subprocess.run(['pkill', '-f', 'zoom'], check=False)
        # These are system-wide and might close all Zoom instances, use with caution.
        print(f"ZoomAgent ({self.user_id}): Successfully left/disconnected from meeting {self.current_meeting_id}.")
        self.current_meeting_id = None
        print(f"ZoomAgent ({self.user_id}): Ready for new meeting or shutdown.")

# Removed old __main__ block as it's incompatible with async structure
# and testing async audio capture requires a proper asyncio event loop runner.
# Example (conceptual, needs to be run in an async context):
# async def main_test():
#     agent = ZoomAgent("test_user_async")
#     if agent.join_meeting("123456789"): # Replace with a real or test meeting ID if launching
#         try:
#             async for audio_chunk in agent.start_audio_capture("123456789"):
#                 print(f"Received audio chunk of length: {len(audio_chunk)}")
#                 # In a real scenario, send this to Deepgram stream
#                 # For testing, maybe stop after a few chunks
#                 # if some_condition: await agent.stop_audio_capture()
#         except ValueError as e:
#             print(f"Capture error: {e}")
#         finally:
#             await agent.leave_meeting()
#
# if __name__ == "__main__":
#    # This would require `asyncio.run(main_test())`
#    # and a way to trigger stop or manage the duration of capture for a test.
#    pass

[end of atomic-docker/project/functions/agents/zoom_agent.py]
