import asyncio
import logging
import uuid
import wave # For saving WAV files
import tempfile # For temporary file storage
import os # For path manipulation
from contextlib import asynccontextmanager
from enum import Enum
from typing import Dict, List, Optional, Any
import datetime
import numpy as np # For handling audio data
from openai import OpenAI # Import OpenAI library
from notion_client import AsyncClient as NotionAsyncClient, APIResponseError # Import Notion Async Client and error type

import sounddevice as sd
from fastapi import FastAPI, HTTPException, Path, Body
from pydantic import BaseModel, Field

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Audio Configuration ---
# Standard audio parameters - consider making these configurable if needed
SAMPLE_RATE = 16000  # Hz (16kHz is common for STT)
CHANNELS = 1         # Mono
DTYPE = 'int16'      # Data type for audio samples
BLOCK_DURATION_MS = 500 # Duration of each audio block processed by the callback, in milliseconds
TEMP_AUDIO_DIR = tempfile.gettempdir() # Or a dedicated temp dir within the app

# --- OpenAI Client Initialization ---
# The API key will be read from the OPENAI_API_KEY environment variable by default by the library
# You can also pass it explicitly: client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
# For robustness, ensure OPENAI_API_KEY is set in the environment where the worker runs.
openai_client: Optional[OpenAI] = None
try:
    if os.getenv("OPENAI_API_KEY"):
        openai_client = OpenAI()
        logger.info("OpenAI client initialized successfully.")
    else:
        logger.warning("OPENAI_API_KEY environment variable not found. STT functionality will be disabled.")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)
    openai_client = None # Ensure it's None if initialization fails

# --- Notion Client Initialization ---
notion_api_key = os.getenv("NOTION_API_KEY")
# Using a parent page ID for simplicity. If a database is preferred, NOTION_DATABASE_ID would be used.
notion_parent_page_id = os.getenv("NOTION_PARENT_PAGE_ID")
notion_client: Optional[NotionAsyncClient] = None

if notion_api_key:
    try:
        notion_client = NotionAsyncClient(auth=notion_api_key)
        logger.info("Notion client initialized successfully.")
        if not notion_parent_page_id:
            logger.warning("NOTION_PARENT_PAGE_ID environment variable not found. Notes will be created in the root of the workspace or a default private page, which might not be ideal.")
    except Exception as e:
        logger.error(f"Failed to initialize Notion client: {e}", exc_info=True)
        notion_client = None
else:
    logger.warning("NOTION_API_KEY environment variable not found. Notion integration will be disabled.")


# --- Models ---
class AudioDevice(BaseModel):
    id: Any # Can be int or string depending on host API
    name: str

class AudioDeviceList(BaseModel):
    devices: List[AudioDevice]

class TaskStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    PROCESSING_COMPLETION = "processing_completion"
    COMPLETED = "completed"
    ERROR = "error"

class StartMeetingRequest(BaseModel):
    platform: str = Field(..., example="zoom")
    meeting_id: str = Field(..., example="https://example.zoom.us/j/1234567890")
    audio_device_id: Any = Field(..., example="default") # Can be int or string
    notion_page_title: str = Field(..., example="Meeting Notes - Project Alpha Q3 Review")
    user_id: str = Field(..., example="user_abc_123")

class StartMeetingResponse(BaseModel):
    task_id: str
    status: TaskStatus
    message: Optional[str] = None

class MeetingTask(BaseModel):
    task_id: str
    user_id: str
    platform: str
    meeting_id: str
    audio_device_id: Any
    notion_page_title: str
    status: TaskStatus = TaskStatus.PENDING
    message: Optional[str] = None
    start_time: Optional[datetime.datetime] = None
    end_time: Optional[datetime.datetime] = None
    duration_seconds: Optional[int] = None
    transcript_preview: Optional[str] = None
    notes_preview: Optional[str] = None
    final_transcript_location: Optional[str] = None
    final_notes_location: Optional[str] = None # Could store path to generated notes file eventually

    # Internal attributes for managing the audio stream etc.
    _audio_stream_object: Optional[sd.InputStream] = None # Holds the sounddevice InputStream
    _audio_stream_task: Optional[asyncio.Task] = None # The asyncio task running the capture loop
    _audio_file_path: Optional[str] = None # Path to the temporary WAV file
    _audio_file_writer: Optional[wave.Wave_write] = None # Wave file writer object
    _stop_event: Optional[asyncio.Event] = None # Event to signal the audio callback to stop

    class Config:
        arbitrary_types_allowed = True # To allow complex types like asyncio.Event, sd.InputStream

# In-memory store for active tasks.
# For production, consider Redis or another persistent/distributed cache.
active_tasks: Dict[str, MeetingTask] = {}

# --- Helper Functions ---

async def _get_audio_devices() -> List[AudioDevice]:
    """Synchronously gets audio devices and wraps in a list."""
    try:
        devices = sd.query_devices()
        logger.info(f"Raw devices found: {devices}")
        input_devices = []
        for i, device in enumerate(devices):
            # Heuristic: check for input channels or common input device names
            # This might need refinement based on how sounddevice reports on different OS
            # On some systems, default might be the only reliable one without deeper inspection
            is_input = False
            try:
                # Try to query if it's an input device by checking its max_input_channels
                if device.get('max_input_channels', 0) > 0:
                    is_input = True
                # Fallback for devices that don't report max_input_channels well but are common inputs
                elif any(keyword in device.get('name', '').lower() for keyword in ['mic', 'input', 'default']):
                     # Check if it's not an output device
                    if device.get('max_output_channels', 0) == 0:
                        is_input = True


            except Exception as e:
                logger.warning(f"Could not determine if device {device.get('name')} is input: {e}")


            if is_input:
                # Use the device index as ID if 'id' field is not directly available or suitable
                # Name is usually descriptive enough.
                # sd.query_devices() returns a list of dicts or a single dict if device is specified.
                # The 'index' or simply its position can serve as an ID.
                # For device selection in sd.InputStream, we might need index or name.
                # Let's use index for robustness if names aren't unique.
                device_id = device.get('index', i) # Prefer 'index' if present
                input_devices.append(AudioDevice(id=device_id, name=device['name']))

        if not input_devices and devices: # If no inputs specifically identified, but devices exist
            logger.warning("Could not specifically identify input devices. Falling back to listing all devices.")
            return [AudioDevice(id=i, name=d['name']) for i, d in enumerate(devices)]

        # Ensure 'default' is an option if available and makes sense
        # sd.default.device can give default input/output. sd.default.device[0] is input.
        try:
            default_input_idx = sd.default.device[0]
            if default_input_idx != -1 and not any(d.id == default_input_idx for d in input_devices):
                 default_device_info = sd.query_devices(default_input_idx)
                 input_devices.append(AudioDevice(id=default_input_idx, name=f"{default_device_info['name']} (Default Input)"))
            elif default_input_idx == -1 and not any('default' in d.name.lower() for d in input_devices):
                # If no system default, but we want a "default" option for simplicity for the user
                # This is tricky, as "default" for sounddevice means system default.
                # Perhaps the first enumerated input device can be a pragmatic "default" if no other default is found.
                pass


        except Exception as e:
            logger.warning(f"Could not query default input device: {e}")


        logger.info(f"Filtered input devices: {input_devices}")
        return input_devices
    except Exception as e:
        logger.error(f"Error querying audio devices: {e}", exc_info=True)
        # Fallback: Provide a mock device if listing fails, so frontend doesn't break.
        # This is crucial for environments where sounddevice might not have access (e.g. some CI/serverless without audio).
        return [AudioDevice(id="mock_input_device", name="Mock Input Device (Error listing real devices)")]


async def transcribe_audio_with_openai(audio_file_path: str, task_id: str) -> Optional[str]:
    """
    Transcribes the given audio file using OpenAI Whisper API.
    Returns the transcribed text or None if an error occurs or STT is disabled.
    """
    if not openai_client:
        logger.warning(f"Task {task_id}: OpenAI client not available. Skipping STT.")
        return None
    if not os.path.exists(audio_file_path):
        logger.error(f"Task {task_id}: Audio file not found at {audio_file_path} for STT.")
        return None

    logger.info(f"Task {task_id}: Starting STT processing for {audio_file_path} using OpenAI Whisper.")
    try:
        with open(audio_file_path, "rb") as audio_file_object:
            # The OpenAI client's methods are synchronous, so run in a thread pool
            # to avoid blocking FastAPI's event loop.
            transcript_response = await asyncio.to_thread(
                openai_client.audio.transcriptions.create,
                model="whisper-1",
                file=audio_file_object
            )
        # Assuming the response object has a 'text' attribute for the transcript
        transcript = transcript_response.text
        logger.info(f"Task {task_id}: STT successful. Transcript length: {len(transcript)} chars.")
        return transcript
    except Exception as e: # Catch any OpenAI API errors or other issues
        logger.error(f"Task {task_id}: OpenAI Whisper STT failed for {audio_file_path}: {e}", exc_info=True)
        return None

async def create_notion_page_with_transcript(
    task_id: str,
    page_title: str,
    transcript: str,
    # user_id: str # user_id currently not used for Notion client, assuming one API key for now
) -> Optional[str]:
    """
    Creates a new page in Notion with the given title and transcript content.
    Uses `notion_parent_page_id` from environment if set, otherwise creates in workspace root.
    Returns the URL of the created page or None if an error occurs or Notion is disabled.
    """
    if not notion_client:
        logger.warning(f"Task {task_id}: Notion client not available. Skipping Notion page creation.")
        return None

    logger.info(f"Task {task_id}: Creating Notion page titled '{page_title}'.")

    # Notion API has a limit of 2000 characters per text block and 100 blocks per append request.
    # We'll split the transcript into paragraphs and create multiple blocks if needed.
    # A simple approach: split by newline, then ensure each paragraph block is under 2000 chars.
    # More sophisticated splitting might be needed for very long continuous text without newlines.

    content_blocks = []
    # Split transcript into paragraphs by double newlines, then by single if no double.
    paragraphs = transcript.split('\n\n')
    if len(paragraphs) == 1 and '\n' in transcript: # If no double newlines, try single
        paragraphs = transcript.split('\n')

    for para in paragraphs:
        para = para.strip()
        if not para: # Skip empty paragraphs
            continue

        # Ensure each paragraph chunk is under 2000 chars
        # This is a simplification; Notion's "rich_text" object has the limit.
        # For very long paragraphs, this might need to be chunked further.
        for i in range(0, len(para), 1999): # Notion's limit is 2000 for rich_text content
            chunk = para[i:i+1999]
            content_blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": chunk}}]
                    },
                }
            )
            if len(content_blocks) >= 99: # API limit for children is 100 blocks
                logger.warning(f"Task {task_id}: Reached near Notion block limit (99). Transcript might be truncated.")
                break
        if len(content_blocks) >= 99:
            break

    if not content_blocks: # If transcript was empty or only whitespace
        content_blocks.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": { "rich_text": [{"type": "text", "text": {"content": "(Transcript was empty)"}}]}
            }
        )

    page_properties = {
        "title": [{"type": "text", "text": {"content": page_title}}]
    }

    create_payload = {
        "parent": {},
        "properties": page_properties,
        "children": content_blocks
    }

    if notion_parent_page_id:
        create_payload["parent"] = {"page_id": notion_parent_page_id}
    else:
        # If no parent_page_id, Notion API requires the parent to be a workspace.
        # The notion-client library might handle this by default if parent is an empty dict,
        # or one might need to specify "type": "workspace" and "workspace": True,
        # but this usually means the page is created in the integration's private pages.
        # For broader visibility, a parent_page_id is usually better.
        # The SDK examples show `parent={"page_id": PARENT_PAGE_ID}` or `parent={"database_id": DATABASE_ID}`.
        # Let's rely on the NOTION_PARENT_PAGE_ID being set for now. If not, this might fail or create a private page.
        logger.warning(f"Task {task_id}: NOTION_PARENT_PAGE_ID not set. Attempting to create page in default location (may be private).")
        # For creating in workspace root (typically private pages of the integration):
        # The SDK handles parent: {} as creating a page that the integration owns.
        # To make it accessible, it should be shared manually or created under a shared page.

    try:
        created_page = await notion_client.pages.create(**create_payload)
        page_url = created_page.get("url")
        logger.info(f"Task {task_id}: Notion page created successfully: {page_url}")
        return page_url
    except APIResponseError as e:
        logger.error(f"Task {task_id}: Notion API error while creating page: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Task {task_id}: Unexpected error while creating Notion page: {e}", exc_info=True)
        return None


# Renamed from audio_capture_placeholder
async def audio_capture_loop(task: MeetingTask):
    """Handles actual audio capture using sounddevice and saves to a WAV file."""
    task._stop_event = asyncio.Event()

    # Define the callback function for the audio stream
    def audio_callback(indata: np.ndarray, frames: int, time_info, status_flags: sd.CallbackFlags):
        if status_flags:
            logger.warning(f"Task {task.task_id}: Audio callback status flags: {status_flags}")
            # Potentially update task.message or handle specific errors like input overflow
            if status_flags.input_overflow:
                task.message = "Warning: Audio input overflow detected."
            # Add more specific error handling based on flags if needed

        if task._stop_event and task._stop_event.is_set():
            logger.info(f"Task {task.task_id}: Stop event received in audio callback. Raising StopException.")
            raise sd.CallbackStop # Signal sounddevice to stop the stream

        try:
            if task._audio_file_writer:
                task._audio_file_writer.writeframes(indata.tobytes())
            # Update previews less frequently to avoid too much logging / state update churn
            if task.duration_seconds and int(task.duration_seconds) % 5 == 0 :
                 task.transcript_preview = f"Captured {int(task.duration_seconds)}s of audio..."
        except Exception as e:
            logger.error(f"Task {task.task_id}: Error in audio_callback: {e}", exc_info=True)
            # Potentially set task to error state here if callback errors are critical
            task.status = TaskStatus.ERROR
            task.message = f"Error during audio data handling: {str(e)}"
            if task._stop_event: task._stop_event.set() # Signal stop on critical error
            raise sd.CallbackStop


    try:
        task.start_time = datetime.datetime.now(datetime.timezone.utc)

        # Ensure TEMP_AUDIO_DIR exists
        os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)
        task._audio_file_path = os.path.join(TEMP_AUDIO_DIR, f"{task.task_id}_audio.wav")

        # Setup WAV file writer
        task._audio_file_writer = wave.open(task._audio_file_path, 'wb')
        task._audio_file_writer.setnchannels(CHANNELS)
        task._audio_file_writer.setsampwidth(np.dtype(DTYPE).itemsize) # itemsize gives bytes per sample
        task._audio_file_writer.setframerate(SAMPLE_RATE)

        logger.info(f"Task {task.task_id}: Starting audio capture for device '{task.audio_device_id}'. Saving to {task._audio_file_path}")
        task.status = TaskStatus.ACTIVE
        task.message = "Audio capture initiated."

        # Attempt to parse audio_device_id if it's a string that looks like an int
        device_id_to_use = task.audio_device_id
        if isinstance(task.audio_device_id, str):
            try:
                device_id_to_use = int(task.audio_device_id)
            except ValueError:
                # If it's not 'default' or an int-like string, sounddevice might handle it as a name substring.
                # Or, you might want to explicitly query devices again to find by name if needed.
                logger.info(f"Task {task.task_id}: audio_device_id '{task.audio_device_id}' is a string, using as is.")

        blocksize_frames = int(SAMPLE_RATE * BLOCK_DURATION_MS / 1000)

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            device=device_id_to_use,
            channels=CHANNELS,
            dtype=DTYPE,
            callback=audio_callback,
            blocksize=blocksize_frames # Number of frames per callback
        ) as stream:
            task._audio_stream_object = stream
            logger.info(f"Task {task.task_id}: Audio stream opened. Sample rate: {stream.samplerate}, Channels: {stream.channels}, Device: {stream.device}")
            task.message = "Audio capture active."

            # Keep the stream alive until stop_event is set
            while not task._stop_event.is_set():
                # Update duration
                if task.start_time: # Should always be set here
                    task.duration_seconds = (datetime.datetime.now(datetime.timezone.utc) - task.start_time).total_seconds()

                # Check if task was externally marked as error or completed to break loop
                if task.status != TaskStatus.ACTIVE:
                    logger.info(f"Task {task.task_id}: Status changed to {task.status}, stopping capture loop.")
                    task._stop_event.set() # Ensure callback knows to stop
                    break

                await asyncio.sleep(0.1) # Sleep briefly to yield control and check stop_event

            logger.info(f"Task {task.task_id}: Audio capture loop finished.")

    except sd.PortAudioError as pae:
        logger.error(f"Task {task.task_id}: PortAudioError during audio capture setup: {pae}", exc_info=True)
        task.status = TaskStatus.ERROR
        task.message = f"Audio device error: {str(pae)}. Ensure device '{task.audio_device_id}' is valid and available."
    except FileNotFoundError as fnfe: # If temp directory is an issue, though makedirs should handle it
        logger.error(f"Task {task.task_id}: File error during WAV setup: {fnfe}", exc_info=True)
        task.status = TaskStatus.ERROR
        task.message = f"File system error: {str(fnfe)}."
    except Exception as e:
        logger.error(f"Task {task.task_id}: Unexpected error during audio capture: {e}", exc_info=True)
        task.status = TaskStatus.ERROR
        task.message = f"Unexpected error during audio capture: {str(e)}"
    finally:
        logger.info(f"Task {task.task_id}: Cleaning up audio capture resources.")
        if task._audio_stream_object and not task._audio_stream_object.closed:
            # This might already be closed if sd.CallbackStop was raised or context exited
            try:
                task._audio_stream_object.stop() # Ensure stream is stopped
                task._audio_stream_object.close()
                logger.info(f"Task {task.task_id}: Audio stream explicitly stopped and closed.")
            except Exception as e_close:
                logger.error(f"Task {task.task_id}: Error closing audio stream: {e_close}", exc_info=True)

        if task._audio_file_writer:
            try:
                task._audio_file_writer.close()
                logger.info(f"Task {task.task_id}: WAV file closed: {task._audio_file_path}")
                if task.status not in [TaskStatus.ERROR] and os.path.exists(task._audio_file_path or ""):
                     task.final_transcript_location = task._audio_file_path # Using this field for audio file path for now
                     task.message = task.message + f" Audio saved to {task._audio_file_path}."
                elif task._audio_file_path and os.path.exists(task._audio_file_path): # If error, but file exists, maybe keep it
                    logger.warning(f"Task {task.task_id}: Task errored but audio file exists at {task._audio_file_path}")
                    task.final_transcript_location = task._audio_file_path # Still note its location
            except Exception as e_close_wav:
                logger.error(f"Task {task.task_id}: Error closing WAV file: {e_close_wav}", exc_info=True)
                if task.status != TaskStatus.ERROR: # Avoid overwriting a more specific error
                    task.status = TaskStatus.ERROR
                    task.message = "Error finalizing audio file."


        task.end_time = datetime.datetime.now(datetime.timezone.utc)
        if task.start_time: # Should always be set
            task.duration_seconds = (task.end_time - task.start_time).total_seconds()

        if task.status == TaskStatus.ACTIVE: # If loop finished due to _stop_event but not an error
            task.status = TaskStatus.PROCESSING_COMPLETION
            task.message = "Audio capture stopped. Preparing for STT."

        # Attempt STT if audio capture was successful (or processing_completion) and file exists
        if task.status in [TaskStatus.PROCESSING_COMPLETION, TaskStatus.ACTIVE] and \
           task._audio_file_path and os.path.exists(task._audio_file_path):

            logger.info(f"Task {task.task_id}: Proceeding to STT for {task._audio_file_path}.")
            task.message = "Audio captured. Starting transcription..."
            transcript = await transcribe_audio_with_openai(task._audio_file_path, task.task_id)
            if transcript:
                task.transcript_preview = transcript # Store full transcript here for now
                task.message = "Transcription successful."
                # task.final_notes_location could store path to a text file with transcript if saved separately
                logger.info(f"Task {task.task_id}: Transcription successful.")
            else:
                task.message = "Transcription failed or was skipped. Audio file available."
                # task.status could be set to a specific STT_FAILED status if needed
                logger.warning(f"Task {task.task_id}: Transcription failed or skipped for {task._audio_file_path}.")

            # Attempt to create Notion page if STT was successful
            if transcript:
                logger.info(f"Task {task.task_id}: Attempting to create Notion page with title '{task.notion_page_title}'.")
                page_url = await create_notion_page_with_transcript(
                    task_id=task.task_id,
                    page_title=task.notion_page_title,
                    transcript=transcript
                    # user_id=task.user_id # Pass if needed by Notion function
                )
                if page_url:
                    task.final_notes_location = page_url
                    task.message += f" Notes saved to Notion: {page_url}."
                    logger.info(f"Task {task.task_id}: Successfully saved transcript to Notion: {page_url}")
                else:
                    task.message += " Failed to save notes to Notion."
                    logger.error(f"Task {task.task_id}: Failed to save transcript to Notion.")

            # Transition to COMPLETED after STT and Notion attempts
            task.status = TaskStatus.COMPLETED
            task.message += " Task completed."

        elif task.status == TaskStatus.ERROR:
            logger.error(f"Task {task.task_id}: Task ended with error before STT/Notion. Status: {task.status}, Message: {task.message}")
            # No STT attempt if already in error
        else: # PENDING or other unexpected states
            logger.warning(f"Task {task.task_id}: Task in unexpected state {task.status} at STT phase. Marking completed without STT.")
            task.status = TaskStatus.COMPLETED
            task.message = (task.message or "") + " Task finalized without STT due to prior state."

        logger.info(f"Task {task.task_id}: Final processing complete. Final status: {task.status}")

        # Clean up internal attributes not meant for external model
        task._audio_stream_object = None
        task._audio_file_writer = None
        task._stop_event = None

        # Attempt to delete the temporary audio file after processing is complete
        if task._audio_file_path and os.path.exists(task._audio_file_path):
            try:
                os.remove(task._audio_file_path)
                logger.info(f"Task {task.task_id}: Temporary audio file {task._audio_file_path} deleted successfully.")
                # If we successfully delete it, we might want to clear task.final_transcript_location
                # if it solely pointed to the audio file and the transcript is now in task.transcript_preview.
                # However, for now, keeping it as a record of where the audio *was* is fine.
                # If STT was successful, the transcript is in task.transcript_preview.
            except OSError as e:
                logger.error(f"Task {task.task_id}: Error deleting temporary audio file {task._audio_file_path}: {e}", exc_info=True)

        # task._audio_file_path can be cleared now, as the file is deleted or attempt was made.
        # This also prevents re-deletion attempts if this finally block were ever re-entered (though it shouldn't).
        task._audio_file_path = None


# --- FastAPI Application ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Live Meeting Worker starting up...")
    # You could pre-load models or connect to databases here if needed
    yield
    # Shutdown logic
    logger.info("Live Meeting Worker shutting down...")
    # Clean up any ongoing tasks (optional, depending on desired behavior)
    for task_id, task in list(active_tasks.items()):
        if task._audio_stream_task and not task._audio_stream_task.done():
            logger.info(f"Cancelling ongoing audio task {task_id} during shutdown.")
            task._audio_stream_task.cancel()
            try:
                await task._audio_stream_task
            except asyncio.CancelledError:
                logger.info(f"Audio task {task_id} cancelled successfully.")
            except Exception as e:
                logger.error(f"Error cancelling task {task_id} during shutdown: {e}")
        task.status = TaskStatus.COMPLETED # Or ERROR, depending on how you want to mark interrupted tasks
        task.message = "Service shut down, task interrupted."


app = FastAPI(
    title="Live Meeting Attendance Worker",
    description="API for managing live meeting audio capture, transcription, and note-taking.",
    version="0.1.0",
    lifespan=lifespan
)

# --- API Endpoints ---

@app.get("/list_audio_devices", response_model=AudioDeviceList)
async def list_audio_devices():
    """
    Retrieves a list of available audio input devices.
    """
    logger.info("Request received for /list_audio_devices")
    try:
        # Running sounddevice in a thread pool executor as it can be blocking
        devices = await asyncio.to_thread(_get_audio_devices)
        return AudioDeviceList(devices=devices)
    except Exception as e:
        logger.error(f"Failed to list audio devices: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve audio devices: {str(e)}")

@app.post("/start_meeting_attendance", response_model=StartMeetingResponse, status_code=202)
async def start_meeting_attendance(
    request: StartMeetingRequest,
    background_tasks: BackgroundTasks
):
    """
    Initiates the process of attending a meeting.
    """
    logger.info(f"Request received for /start_meeting_attendance: {request.model_dump_json()}")
    task_id = str(uuid.uuid4())

    # Validate audio_device_id (optional, could do a quick check if it's in the list)
    # For now, we assume the frontend sends a valid one from /list_audio_devices

    task = MeetingTask(
        task_id=task_id,
        user_id=request.user_id,
        platform=request.platform,
        meeting_id=request.meeting_id,
        audio_device_id=request.audio_device_id,
        notion_page_title=request.notion_page_title,
        status=TaskStatus.PENDING,
        message="Task accepted and initializing."
    )
    active_tasks[task_id] = task
    logger.info(f"Task {task_id} created for user {request.user_id}. Status: {task.status}")

    # Start the audio capture loop in the background using asyncio.create_task
    # This allows the endpoint to return immediately while capture happens.
    # The audio_capture_loop function will update the task object in active_tasks.
    capture_task = asyncio.create_task(audio_capture_loop(task))
    task._audio_stream_task = capture_task # Store the asyncio Task object itself

    return StartMeetingResponse(
        task_id=task_id,
        status=task.status, # Will be PENDING initially
        message=task.message
    )

@app.get("/meeting_attendance_status/{task_id}", response_model=MeetingTask)
async def get_meeting_attendance_status(
    task_id: str = Path(..., description="The ID of the task to query")
):
    """
    Polls for the current status and progress of an active meeting attendance task.
    """
    logger.debug(f"Request received for /meeting_attendance_status/{task_id}")
    task = active_tasks.get(task_id)
    if not task:
        logger.warning(f"Task not found: {task_id}")
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    # Update duration if task is active and has a start time
    if task.status == TaskStatus.ACTIVE and task.start_time:
        task.duration_seconds = (datetime.datetime.now(datetime.timezone.utc) - task.start_time).total_seconds()

    logger.debug(f"Returning status for task {task_id}: {task.status}, message: {task.message}")
    return task

@app.post("/stop_meeting_attendance/{task_id}", response_model=MeetingTask)
async def stop_meeting_attendance(
    task_id: str = Path(..., description="The ID of the task to stop")
):
    """
    Manually stops an ongoing meeting attendance task.
    """
    logger.info(f"Request received for /stop_meeting_attendance/{task_id}")
    task = active_tasks.get(task_id)
    if not task:
        logger.warning(f"Task not found for stopping: {task_id}")
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    if task.status not in [TaskStatus.ACTIVE, TaskStatus.PENDING]:
        logger.warning(f"Task {task_id} is not active or pending, cannot stop. Status: {task.status}")
        raise HTTPException(status_code=400, detail=f"Task is not currently active or pending. Status: {task.status}")

    if task._stop_event and not task._stop_event.is_set():
        logger.info(f"Task {task_id}: Signaling audio capture to stop.")
        task.status = TaskStatus.PROCESSING_COMPLETION
        task.message = "Stop request received. Finalizing task..."
        task._stop_event.set() # Signal the audio_capture_loop to stop

        # Wait for the audio capture task to finish its cleanup
        if task._audio_stream_task and not task._audio_stream_task.done():
            try:
                await asyncio.wait_for(task._audio_stream_task, timeout=10.0) # Wait for cleanup
                logger.info(f"Task {task_id}: Audio stream task completed after stop signal.")
            except asyncio.TimeoutError:
                logger.error(f"Task {task_id}: Timeout waiting for audio stream task to complete after stop signal. Forcing cancellation.")
                task._audio_stream_task.cancel() # Force cancel if cleanup hangs
                task.status = TaskStatus.ERROR
                task.message = "Error: Timeout during audio stop. Resources might not be fully released."
            except Exception as e:
                logger.error(f"Task {task_id}: Error waiting for audio stream task completion: {e}", exc_info=True)
                task.status = TaskStatus.ERROR
                task.message = f"Error during task stop: {str(e)}"
    elif task._audio_stream_task and task._audio_stream_task.done() and task.status != TaskStatus.COMPLETED and task.status != TaskStatus.ERROR:
        # If task was already done but not yet marked COMPLETED/ERROR (e.g. finished naturally just before stop call)
        logger.info(f"Task {task_id}: Audio stream task was already done. Ensuring final status.")
        # The audio_capture_loop's finally block should have set the status.
        # This is more of a safeguard or for tasks that might have errored out without explicit stop.
        if task.status not in [TaskStatus.COMPLETED, TaskStatus.ERROR]:
             task.status = TaskStatus.COMPLETED # Assume completed if not errored
             task.message = "Task finalized upon stop request."
    else:
        logger.info(f"Task {task_id}: No active audio capture to stop, or already stopped/terminal. Current status: {task.status}")
        if task.status not in [TaskStatus.COMPLETED, TaskStatus.ERROR]: # If it's PENDING and stop is called
            task.status = TaskStatus.COMPLETED
            task.message = "Task stopped before activation."
            if not task.end_time: task.end_time = datetime.datetime.now(datetime.timezone.utc)

    # Ensure duration is calculated if task is considered ended
    if task.status in [TaskStatus.COMPLETED, TaskStatus.ERROR] and task.start_time and not task.duration_seconds:
        if not task.end_time: task.end_time = datetime.datetime.now(datetime.timezone.utc)
        task.duration_seconds = (task.end_time - task.start_time).total_seconds()

    logger.info(f"Task {task.id} stop processed. Final status: {task.status}")
    return task


if __name__ == "__main__":
    import uvicorn
    # This is for direct execution. `uvicorn main:app --reload` is preferred for dev.
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")

```
