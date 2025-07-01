import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from enum import Enum
from typing import Dict, List, Optional, Any
import datetime

import sounddevice as sd
from fastapi import FastAPI, HTTPException, Path, Body, BackgroundTasks
from pydantic import BaseModel, Field

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
    final_notes_location: Optional[str] = None
    # Internal attributes for managing the audio stream etc.
    _audio_stream_task: Optional[asyncio.Task] = None
    _raw_audio_chunks: List[bytes] = [] # Placeholder for audio data

    class Config:
        arbitrary_types_allowed = True # To allow asyncio.Task

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


async def audio_capture_placeholder(task: MeetingTask):
    """Placeholder for actual audio capture and processing."""
    logger.info(f"Task {task.task_id}: Starting audio capture (placeholder) for device {task.audio_device_id}")
    task.status = TaskStatus.ACTIVE
    task.message = "Audio capture started (placeholder)."
    task.start_time = datetime.datetime.now(datetime.timezone.utc)

    # Simulate audio streaming and processing
    try:
        # This is where real audio capture using sounddevice.InputStream would happen
        # For now, just simulate activity
        for i in range(120): # Simulate 2 minutes of activity (60 * 2 seconds)
            if task.task_id not in active_tasks or active_tasks[task.task_id].status != TaskStatus.ACTIVE:
                logger.info(f"Task {task.task_id}: Audio capture loop interrupted (task stopped or status changed).")
                break

            await asyncio.sleep(1) # Simulate 1 second of audio processing

            # Simulate transcript/notes update
            task.transcript_preview = f"Transcript snippet {i+1} for task {task.task_id}..."
            task.notes_preview = f"- Note point {i+1}\n- Another detail for task {task.task_id}"
            task.duration_seconds = (datetime.datetime.now(datetime.timezone.utc) - task.start_time).total_seconds()

            # Storing mock audio data
            task._raw_audio_chunks.append(b'\x00' * 1024) # Simulate 1KB of audio data per second

            if i % 10 == 0: # Log progress periodically
                 logger.info(f"Task {task.task_id}: Still active, duration {task.duration_seconds:.0f}s")


    except asyncio.CancelledError:
        logger.info(f"Task {task.task_id}: Audio capture task cancelled.")
        task.message = "Audio capture was cancelled."
        task.status = TaskStatus.PROCESSING_COMPLETION # Or directly to COMPLETED if no post-processing
    except Exception as e:
        logger.error(f"Task {task.task_id}: Error during audio capture placeholder: {e}", exc_info=True)
        task.status = TaskStatus.ERROR
        task.message = f"Error during audio capture: {str(e)}"
    finally:
        logger.info(f"Task {task.task_id}: Placeholder audio capture finished.")
        task.end_time = datetime.datetime.now(datetime.timezone.utc)
        if task.start_time:
            task.duration_seconds = (task.end_time - task.start_time).total_seconds()

        if task.status == TaskStatus.ACTIVE: # If it finished naturally (not stopped or errored mid-way)
            task.status = TaskStatus.PROCESSING_COMPLETION

        # Simulate final processing
        await asyncio.sleep(2) # Simulate time taken to "save" files

        task.final_transcript_location = f"/path/to/mock_transcript_{task.task_id}.txt"
        task.final_notes_location = f"/path/to/mock_notes_{task.task_id}.txt"
        task.status = TaskStatus.COMPLETED
        task.message = "Meeting attendance completed. Mock transcript and notes generated."
        logger.info(f"Task {task.task_id}: Processing complete. Status: {task.status}")


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

    # Start the audio capture placeholder in the background
    # The audio_capture_placeholder will update task.status and other fields
    audio_task = asyncio.create_task(audio_capture_placeholder(task))
    task._audio_stream_task = audio_task
    # If you need background_tasks for something FastAPI manages:
    # background_tasks.add_task(audio_capture_placeholder, task)
    # But for asyncio tasks, creating them directly is fine.

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

    if task._audio_stream_task and not task._audio_stream_task.done():
        logger.info(f"Task {task_id}: Cancelling audio stream task.")
        task.status = TaskStatus.PROCESSING_COMPLETION # Indicate it's being stopped
        task.message = "Stop request received. Finalizing task..."
        task._audio_stream_task.cancel()
        try:
            await task._audio_stream_task # Allow cancellation to propagate and cleanup in the task
        except asyncio.CancelledError:
            logger.info(f"Task {task_id}: Audio stream task cancelled successfully.")
            # The audio_capture_placeholder's finally block should set COMPLETED status
        except Exception as e: # Should not happen if cancellation is handled well
            logger.error(f"Task {task_id}: Error during supervised cancellation: {e}", exc_info=True)
            task.status = TaskStatus.ERROR
            task.message = f"Error while trying to stop the task: {str(e)}"
    else:
        # If no stream task (e.g., it finished very quickly or failed to start properly)
        logger.info(f"Task {task_id}: No active audio stream task to cancel, or already done. Marking as completed.")
        task.status = TaskStatus.COMPLETED
        task.message = "Task stopped (or was already terminal)."
        if not task.end_time: task.end_time = datetime.datetime.now(datetime.timezone.utc)
        if task.start_time and not task.duration_seconds:
             task.duration_seconds = (task.end_time - task.start_time).total_seconds()


    logger.info(f"Task {task_id} stop processed. Final status: {task.status}")
    return task


if __name__ == "__main__":
    import uvicorn
    # This is for direct execution. `uvicorn main:app --reload` is preferred for dev.
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")

```
