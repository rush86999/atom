import asyncio
import subprocess # For type hints, but will use asyncio.create_subprocess_exec
import os
import logging
import time # For JWT iat/exp
from datetime import datetime, timedelta, timezone
from typing import Optional, AsyncIterator, List, Dict, Any
import jwt # PyJWT library

# Define custom exceptions similar to other agents for consistency
class ZoomSdkAgentError(Exception):
    """Base class for NewZoomSdkAgent related errors."""
    pass

class ZoomSdkAuthError(ZoomSdkAgentError):
    """Raised for authentication errors with Zoom SDK."""
    pass

class ZoomSdkMeetingError(ZoomSdkAgentError):
    """Raised for errors related to joining or managing Zoom meetings via SDK."""
    pass

class NewZoomSdkAgent:
    """
    NewZoomSdkAgent interacts with Zoom meetings using a C++ helper application
    that leverages the Zoom Linux SDK for raw audio/video data access.
    This agent is responsible for:
    1. Generating SDK JWT for authentication.
    2. Launching and managing the C++ helper subprocess.
    3. Streaming raw audio data received from the C++ helper.
    """

    # Path to the C++ helper executable within the Docker container
    CPP_HELPER_PATH = "/app/zoom_sdk_cpp_helper_bin/zoom_sdk_helper"
    # Audio chunk size (e.g., 100ms of 16kHz, 16-bit mono audio = 1600 samples * 2 bytes/sample = 3200 bytes)
    # This should align with what the C++ helper outputs per "chunk" or read buffer size.
    AUDIO_CHUNK_SIZE = 3200

    def __init__(self, user_id: str,
                 zoom_sdk_key: Optional[str] = None,
                 zoom_sdk_secret: Optional[str] = None,
                 logger_instance: Optional[logging.Logger] = None):

        self.user_id: str = user_id
        self.zoom_sdk_key: Optional[str] = zoom_sdk_key or os.environ.get('ZOOM_SDK_KEY')
        self.zoom_sdk_secret: Optional[str] = zoom_sdk_secret or os.environ.get('ZOOM_SDK_SECRET')

        if not self.zoom_sdk_key or not self.zoom_sdk_secret:
            raise ValueError("Zoom SDK Key and Secret are required and were not provided or found in environment variables.")

        self.current_meeting_id: Optional[str] = None
        self.cpp_helper_process: Optional[asyncio.subprocess.Process] = None
        self.audio_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue() # Not directly used if stdout is read directly

        if logger_instance:
            self.logger = logger_instance
        else:
            self.logger = logging.getLogger(f"NewZoomSdkAgent-{self.user_id}")
            if not self.logger.handlers: # Avoid adding multiple handlers if logger already configured
                logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        self.logger.info(f"NewZoomSdkAgent initialized for user {self.user_id}. Expecting C++ helper at: {os.path.abspath(self.CPP_HELPER_PATH)}")
        if not os.path.exists(self.CPP_HELPER_PATH):
            self.logger.warning(f"C++ helper executable NOT FOUND at expected path: {os.path.abspath(self.CPP_HELPER_PATH)}")
        else:
            self.logger.info(f"C++ helper executable found at: {os.path.abspath(self.CPP_HELPER_PATH)}")
        self._stderr_reader_task: Optional[asyncio.Task] = None


    def _generate_sdk_jwt(self) -> str:
        """
        Generates a JWT for Zoom SDK authentication.
        Refer to Zoom SDK documentation for the most up-to-date payload structure.
        Commonly uses SDK Key as appKey, and SDK Secret for signing.
        """
        # Standard JWT: uses `exp` for expiration.
        # Zoom SDK JWT historically used `tokenExp` as well, which might be the same as `exp`.
        # Check Zoom SDK docs for current requirements. Assuming `exp` is primary.
        iat = int(time.time())
        # Expiration time for the token (e.g., 4 hours, Zoom SDK tokens are often short-lived for security)
        # Max recommended by Zoom is often 48 hours, but shorter is better if regenerated per session.
        # For a meeting agent, a few hours should be plenty.
        exp_seconds = 1 * 60 * 60 # 1 hour for testing, adjust as needed
        exp = iat + exp_seconds

        # `tokenExp` is often required by Zoom and should be the same as `exp`
        payload = {
            'appKey': self.zoom_sdk_key,
            'iat': iat,
            'exp': exp,
            'tokenExp': exp # Important: Zoom often requires tokenExp to match exp
        }

        self.logger.debug(f"Generating Zoom SDK JWT with payload: {payload}")
        try:
            token = jwt.encode(payload, self.zoom_sdk_secret, algorithm='HS256')
            return token
        except Exception as e:
            self.logger.error(f"Error generating Zoom SDK JWT: {e}", exc_info=True)
            raise ZoomSdkAuthError(f"Failed to generate SDK JWT: {e}")


    async def join_meeting(self, meeting_id: str,
                           meeting_password: Optional[str] = None,
                           sample_rate: int = 16000,
                           channels: int = 1) -> bool:
        if self.cpp_helper_process and self.cpp_helper_process.returncode is None:
            self.logger.warning(f"Attempted to join meeting {meeting_id} while another helper process is active for meeting {self.current_meeting_id}.")
            # Optionally, could terminate existing process or return error. For now, log and disallow.
            # await self.leave_meeting() # Example: leave previous before joining new
            raise ZoomSdkMeetingError(f"Already in meeting {self.current_meeting_id}. Leave first.")

        self.logger.info(f"Attempting to join meeting: {meeting_id}")
        try:
            sdk_jwt = self._generate_sdk_jwt()
        except ZoomSdkAuthError:
            return False # Error already logged by _generate_sdk_jwt

        cmd_args: List[str] = [
            self.CPP_HELPER_PATH,
            "--meeting_id", meeting_id,
            "--token", sdk_jwt,
            "--sample_rate", str(sample_rate),
            "--channels", str(channels)
        ]
        if meeting_password:
            cmd_args.extend(["--password", meeting_password])

        self.logger.info(f"Launching C++ helper: {' '.join(cmd_args)}")
        try:
            self.cpp_helper_process = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            self.current_meeting_id = meeting_id
            self.logger.info(f"C++ helper process launched for meeting {meeting_id}. PID: {self.cpp_helper_process.pid}")

            # Start the stderr reader task
            if self._stderr_reader_task is None or self._stderr_reader_task.done():
                self._stderr_reader_task = asyncio.create_task(self._read_stderr(), name=f"stderr_reader_{meeting_id}")

            # TODO: Add a mechanism to confirm successful meeting join from C++ helper's initial stderr output.
            # This might involve reading a few lines from stderr here or having _read_stderr set a flag.
            # For now, successful launch is considered a preliminary success.
            await asyncio.sleep(1) # Give a moment for initial logs/errors from C++ helper
            if self.cpp_helper_process.returncode is not None:
                 self.logger.error(f"C++ helper exited prematurely with code {self.cpp_helper_process.returncode} during join for meeting {meeting_id}.")
                 # Ensure stderr is drained if process exited quickly
                 if self._stderr_reader_task and not self._stderr_reader_task.done():
                    await asyncio.wait_for(self._stderr_reader_task, timeout=5) # wait for existing task to finish
                 self.cpp_helper_process = None # Clear the process
                 self.current_meeting_id = None
                 return False

            return True
        except FileNotFoundError:
            self.logger.error(f"C++ helper executable not found at {self.CPP_HELPER_PATH}", exc_info=True)
            raise ZoomSdkAgentError(f"C++ helper not found at {self.CPP_HELPER_PATH}")
        except Exception as e:
            self.logger.error(f"Failed to launch C++ helper for meeting {meeting_id}: {e}", exc_info=True)
            self.cpp_helper_process = None # Ensure it's None on failure
            self.current_meeting_id = None
            return False

    async def _read_stderr(self):
        if not self.cpp_helper_process or not self.cpp_helper_process.stderr:
            self.logger.error("C++ helper stderr stream not available for reading.")
            return

        self.logger.info("Starting C++ helper stderr reader task.")
        try:
            while self.cpp_helper_process and self.cpp_helper_process.returncode is None:
                line_bytes = await self.cpp_helper_process.stderr.readline()
                if not line_bytes: # EOF
                    self.logger.info("C++ helper stderr EOF reached (process likely exited).")
                    break
                line = line_bytes.decode('utf-8', errors='replace').strip()
                self.logger.info(f"[CPP_HELPER_LOG] {line}")
        except asyncio.CancelledError:
            self.logger.info("Stderr reader task cancelled.")
        except Exception as e:
            self.logger.error(f"Error reading C++ helper stderr: {e}", exc_info=True)
        finally:
            self.logger.info("C++ helper stderr reader task finished.")


    async def start_audio_capture(self, meeting_id_to_confirm: str) -> AsyncIterator[bytes]:
        self.logger.info(f"start_audio_capture called for meeting: {meeting_id_to_confirm}")
        if not self.cpp_helper_process or self.cpp_helper_process.returncode is not None:
            msg = f"C++ helper process is not active or has already exited. Cannot start audio capture for {meeting_id_to_confirm}."
            self.logger.error(msg)
            raise ZoomSdkMeetingError(msg)

        if self.current_meeting_id != meeting_id_to_confirm:
            msg = f"Meeting ID mismatch. Current: '{self.current_meeting_id}', requested for capture: '{meeting_id_to_confirm}'."
            self.logger.error(msg)
            raise ZoomSdkMeetingError(msg)

        if not self.cpp_helper_process.stdout:
            msg = "C++ helper stdout stream not available. Cannot capture audio."
            self.logger.error(msg)
            raise ZoomSdkMeetingError(msg)

        # Ensure stderr reader is running
        if self._stderr_reader_task is None or self._stderr_reader_task.done():
            self.logger.warning("Stderr reader task was not running or had finished; restarting.")
            self._stderr_reader_task = asyncio.create_task(self._read_stderr(), name=f"stderr_reader_capture_{self.current_meeting_id}")

        self.logger.info(f"Starting audio capture from C++ helper for meeting {self.current_meeting_id}...")
        try:
            while True:
                if self.cpp_helper_process.returncode is not None:
                    self.logger.warning(f"C++ helper process exited with code {self.cpp_helper_process.returncode} during audio capture.")
                    break

                try:
                    chunk = await asyncio.wait_for(self.cpp_helper_process.stdout.read(self.AUDIO_CHUNK_SIZE), timeout=5.0)
                except asyncio.TimeoutError:
                    self.logger.debug(f"Timeout reading from C++ helper stdout for meeting {self.current_meeting_id}, process still alive.")
                    # Check if process is still running; if not, break
                    if self.cpp_helper_process.returncode is not None:
                        self.logger.warning(f"C++ helper process exited (code {self.cpp_helper_process.returncode}) during stdout read timeout check.")
                        break
                    continue # Continue to next read attempt

                if not chunk: # EOF
                    self.logger.info(f"C++ helper stdout EOF. Audio stream ended for meeting {self.current_meeting_id}.")
                    break
                # self.logger.debug(f"Yielding audio chunk of size {len(chunk)} bytes.")
                yield chunk
        except asyncio.CancelledError:
            self.logger.info(f"Audio capture task cancelled for meeting {self.current_meeting_id}.")
            # Propagate cancellation if necessary, or handle cleanup
            raise
        except Exception as e:
            self.logger.error(f"Error reading audio from C++ helper for meeting {self.current_meeting_id}: {e}", exc_info=True)
            # Consider how to signal this failure to the consumer
        finally:
            self.logger.info(f"Audio capture loop finished for meeting {self.current_meeting_id}.")
            # Ensure related tasks are handled, e.g., if stderr reader should stop.
            # Usually, if stdout ends, stderr might also end soon if the process is terminating.

    async def stop_audio_capture(self) -> None:
        """
        This agent primarily controls audio via leave_meeting which terminates the C++ helper.
        Directly stopping audio capture while keeping the C++ helper in the meeting is not
        currently implemented by this method.
        """
        self.logger.info(f"stop_audio_capture called for meeting {self.current_meeting_id}. This method is a placeholder; use leave_meeting to stop the C++ helper.")
        # If C++ helper had separate controls for audio stream start/stop, they would be invoked here.
        # For now, it's tied to the lifecycle of the helper process.

    async def leave_meeting(self) -> None:
        self.logger.info(f"Attempting to leave meeting {self.current_meeting_id} by terminating C++ helper.")
        if self.cpp_helper_process and self.cpp_helper_process.returncode is None:
            pid = self.cpp_helper_process.pid
            self.logger.info(f"Terminating C++ helper process PID {pid} for meeting {self.current_meeting_id}...")
            try:
                self.cpp_helper_process.terminate() # Send SIGTERM
                try:
                    await asyncio.wait_for(self.cpp_helper_process.wait(), timeout=5.0)
                    self.logger.info(f"C++ helper process PID {pid} terminated gracefully with code {self.cpp_helper_process.returncode}.")
                except asyncio.TimeoutError:
                    self.logger.warning(f"C++ helper process PID {pid} did not terminate gracefully after 5s. Sending SIGKILL.")
                    self.cpp_helper_process.kill()
                    await self.cpp_helper_process.wait() # Wait for SIGKILL to take effect
                    self.logger.info(f"C++ helper process PID {pid} killed. Return code: {self.cpp_helper_process.returncode}.")
            except ProcessLookupError:
                 self.logger.warning(f"C++ helper process PID {pid} not found. Already exited?")
            except Exception as e:
                self.logger.error(f"Error terminating C++ helper process PID {pid}: {e}", exc_info=True)
        else:
            self.logger.info(f"No active C++ helper process to terminate for meeting {self.current_meeting_id}.")

        if self._stderr_reader_task and not self._stderr_reader_task.done():
            self.logger.info("Cancelling stderr_reader_task.")
            self._stderr_reader_task.cancel()
            try:
                await self._stderr_reader_task
            except asyncio.CancelledError:
                self.logger.info("Stderr_reader_task successfully cancelled.")
            except Exception as e: # Catch other potential errors if task fails on cancel
                self.logger.error(f"Error during stderr_reader_task cancellation: {e}", exc_info=True)


        self.cpp_helper_process = None
        self.current_meeting_id = None
        self._stderr_reader_task = None # Clear the task
        self.logger.info("Zoom SDK Agent meeting cleanup complete.")

    def get_current_meeting_id(self) -> Optional[str]:
        return self.current_meeting_id

    def is_active(self) -> bool:
        """Checks if the C++ helper process is currently active."""
        return self.cpp_helper_process is not None and self.cpp_helper_process.returncode is None

# Example Usage (for testing purposes, if run directly)
async def main_test():
    # IMPORTANT: Set ZOOM_SDK_KEY and ZOOM_SDK_SECRET in your environment for this test
    if not os.environ.get('ZOOM_SDK_KEY') or not os.environ.get('ZOOM_SDK_SECRET'):
        print("Error: ZOOM_SDK_KEY and ZOOM_SDK_SECRET environment variables must be set for this test.")
        return

    print("Starting NewZoomSdkAgent test...")
    agent = NewZoomSdkAgent(user_id="test_user_sdk")

    meeting_id_to_join = input("Enter Meeting ID to join: ")
    meeting_password_to_join = input("Enter Meeting Password (or press Enter if none): ") or None

    if await agent.join_meeting(meeting_id_to_join, meeting_password_to_join):
        print(f"Successfully launched C++ helper for meeting {meeting_id_to_join}.")

        audio_file_path = f"meeting_{meeting_id_to_join}_audio.pcm"
        print(f"Capturing audio... Press Ctrl+C to stop. Audio will be saved to {audio_file_path}")

        try:
            with open(audio_file_path, "wb") as f:
                async for audio_chunk in agent.start_audio_capture(meeting_id_to_join):
                    f.write(audio_chunk)
                    print(f"Received audio chunk of size {len(audio_chunk)}, writing to file...")
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received. Stopping capture and leaving meeting.")
        except ZoomSdkMeetingError as e:
            print(f"Meeting Error during capture: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during capture: {e}")
        finally:
            print("Leaving meeting...")
            await agent.leave_meeting()
            print("Test finished.")
    else:
        print(f"Failed to join meeting {meeting_id_to_join}.")

if __name__ == '__main__':
    # This main_test() is for standalone testing of the agent.
    # It requires the C++ helper to be compiled and at CPP_HELPER_PATH.
    # You also need valid SDK credentials in env vars.

    # To run, ensure you have PyJWT: pip install pyjwt
    # And from the project root: python -m functions.agents.NewZoomSdkAgent
    # (adjust path if necessary)

    # Setup basic logging for the test
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    try:
        asyncio.run(main_test())
    except KeyboardInterrupt:
        print("Test run cancelled by user.")
    except Exception as e:
        print(f"Unhandled error in test run: {e}")
        import traceback
        traceback.print_exc()
