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
from openai import OpenAI, APIError, RateLimitError, AuthenticationError, APIConnectionError # Import OpenAI library and specific errors
from notion_client import AsyncClient as NotionAsyncClient, APIResponseError, APIErrorCode # Import Notion Async Client and error types
import aiosqlite # For async SQLite operations
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type # For retry mechanisms

import sounddevice as sd
from fastapi import FastAPI, HTTPException, Path, Body, BackgroundTasks, WebSocket
from pydantic import BaseModel, Field

# --- Add TranscriptionSkill import ---
from src.skills.transcription import TranscriptionSkill

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

# --- Database Configuration ---
DATABASE_URL = "/app/data/live_meeting_tasks.db" # Path within the container
# Ensure the /app/data directory is created if it doesn't exist, will be handled in init_db

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

# --- Database Helper Functions ---

# Fields to select for reconstructing MeetingTask from DB row
MEETING_TASK_DB_FIELDS = [
    "task_id", "user_id", "platform", "meeting_id", "audio_device_id",
    "notion_page_title", "status", "message", "start_time", "end_time",
    "duration_seconds", "transcript_preview", "notes_preview",
    "final_transcript_location", "final_notes_location", "audio_file_path"
]

def _db_row_to_task_model(row: aiosqlite.Row) -> Optional[MeetingTask]:
    if not row:
        return None
    # Convert row to dict
    task_data = dict(row)
    # Convert datetime strings back to datetime objects if they exist
    if task_data.get("start_time"):
        task_data["start_time"] = datetime.datetime.fromisoformat(task_data["start_time"])
    if task_data.get("end_time"):
        task_data["end_time"] = datetime.datetime.fromisoformat(task_data["end_time"])
    # audio_device_id might be int or str, handle conversion if necessary (though TEXT in DB is fine)
    # For now, assume it's stored as TEXT and can be used directly or converted by Pydantic if needed.
    return MeetingTask(**task_data)

async def add_task_to_db(task: MeetingTask):
    async with get_db_connection() as db:
        # Convert MeetingTask Pydantic model to a dict for DB insertion
        # Exclude fields starting with '_' as they are internal runtime attributes
        task_dict = task.model_dump(exclude_none=True, exclude={"_audio_stream_object", "_audio_stream_task", "_audio_file_writer", "_stop_event"})

        # Convert datetime objects to ISO format strings for DB storage
        if task_dict.get("start_time"):
            task_dict["start_time"] = task_dict["start_time"].isoformat()
        if task_dict.get("end_time"):
            task_dict["end_time"] = task_dict["end_time"].isoformat()

        # Ensure all fields from MEETING_TASK_DB_FIELDS are present, defaulting to None if missing
        # This is important if task_dict from model_dump(exclude_none=True) omits some fields.
        # However, the table schema allows NULLs for most, so direct insertion is fine.
        # For insert, we need to ensure the order of values matches columns or use named placeholders.

        columns = ', '.join(task_dict.keys())
        placeholders = ', '.join('?' for _ in task_dict)
        sql = f"INSERT INTO meeting_tasks ({columns}) VALUES ({placeholders})"

        try:
            await db.execute(sql, list(task_dict.values()))
            await db.commit()
            logger.info(f"Task {task.task_id} added to database.")
        except Exception as e:
            logger.error(f"Task {task.task_id}: Failed to add to database: {e}", exc_info=True)
            # Depending on policy, might re-raise or handle
            raise

async def get_task_from_db(task_id: str) -> Optional[MeetingTask]:
    async with get_db_connection() as db:
        fields_str = ", ".join(MEETING_TASK_DB_FIELDS)
        async with db.execute(f"SELECT {fields_str} FROM meeting_tasks WHERE task_id = ?", (task_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return _db_row_to_task_model(row)
            return None

async def update_task_in_db(task: MeetingTask):
    async with get_db_connection() as db:
        task_dict = task.model_dump(exclude_none=False, exclude={"_audio_stream_object", "_audio_stream_task", "_audio_file_writer", "_stop_event"})

        if task_dict.get("start_time"):
            task_dict["start_time"] = task_dict["start_time"].isoformat() if isinstance(task_dict["start_time"], datetime.datetime) else task_dict["start_time"]
        if task_dict.get("end_time"):
            task_dict["end_time"] = task_dict["end_time"].isoformat() if isinstance(task_dict["end_time"], datetime.datetime) else task_dict["end_time"]

        # Ensure status is the string value of the enum
        task_dict["status"] = task.status.value if isinstance(task.status, Enum) else task.status

        # Prepare for UPDATE: remove task_id from fields to update, use it in WHERE
        update_fields = {k: v for k, v in task_dict.items() if k != "task_id"}
        set_clause = ', '.join(f"{key} = ?" for key in update_fields)
        values = list(update_fields.values())
        values.append(task.task_id) # For the WHERE clause

        sql = f"UPDATE meeting_tasks SET {set_clause} WHERE task_id = ?"

        try:
            await db.execute(sql, values)
            await db.commit()
            logger.debug(f"Task {task.task_id} updated in database. Status: {task.status}, Message: {task.message}")
        except Exception as e:
            logger.error(f"Task {task.task_id}: Failed to update in database: {e}", exc_info=True)
            # Depending on policy, might re-raise or handle
            raise

async def get_db_connection():
    # Ensure the data directory exists
    db_dir = os.path.dirname(DATABASE_URL)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        logger.info(f"Created database directory: {db_dir}")

    db = await aiosqlite.connect(DATABASE_URL)
    # Use Row factory to access columns by name
    db.row_factory = aiosqlite.Row
    return db

async def init_db():
    async with get_db_connection() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS meeting_tasks (
                task_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                platform TEXT,
                meeting_id TEXT,
                audio_device_id TEXT,
                notion_page_title TEXT,
                status TEXT NOT NULL,
                message TEXT,
                start_time TEXT,
                end_time TEXT,
                duration_seconds INTEGER,
                transcript_preview TEXT,
                notes_preview TEXT,
                final_transcript_location TEXT,
                final_notes_location TEXT,
                audio_file_path TEXT
            )
        """)
        await db.commit()
        logger.info("Database initialized and meeting_tasks table ensured.")

async def handle_interrupted_tasks():
    """Marks tasks that were active during a restart as ERRORED."""
    logger.info("Checking for tasks interrupted by restart...")
    async with get_db_connection() as db:
        # Find tasks that were in a non-terminal state
        async with db.execute(
            "SELECT task_id FROM meeting_tasks WHERE status = ? OR status = ?",
            (TaskStatus.ACTIVE.value, TaskStatus.PROCESSING_COMPLETION.value)
        ) as cursor:
            interrupted_tasks = await cursor.fetchall()

            if interrupted_tasks:
                for row in interrupted_tasks:
                    task_id = row["task_id"]
                    logger.warning(f"Task {task_id} was interrupted by worker restart. Marking as ERROR.")
                    await db.execute(
                        "UPDATE meeting_tasks SET status = ?, message = ? WHERE task_id = ?",
                        (TaskStatus.ERROR.value, "Task interrupted due to worker restart.", task_id)
                    )
                await db.commit()
                logger.info(f"Marked {len(interrupted_tasks)} tasks as ERRORED due to restart.")
            else:
                logger.info("No interrupted tasks found.")

# In-memory store for active asyncio.Task objects (not for persistent task data)
# These are the actual running audio capture loops.
running_async_tasks: Dict[str, asyncio.Task] = {}
# In-memory store for stop events, associated with task_id. These are used to signal
# the corresponding asyncio.Task in running_async_tasks to stop.
task_stop_events: Dict[str, asyncio.Event] = {}
# The active_tasks dictionary is now removed as task state is managed in the database.
import re

# --- Helper Functions ---

def parse_action_item_line(line: str) -> tuple[str, Optional[str]]:
    """
    Parses a line of text to extract action item description and assignee.
    Expected format examples:
                     "- Action description (Assigned to: Assignee)"
                     "- Action description (Assigned to: N/A)"
                     "- Action description"
    Returns: (description, assignee_or_none)
    """
    line = line.strip("- ").strip() # Remove leading bullet and spaces

    match = re.search(r'\s*\(Assigned to:\s*(.*?)\)$', line, re.IGNORECASE)

    assignee: Optional[str] = None
    description: str = line

    if match:
        assignee_text = match.group(1).strip()
        if assignee_text.lower() not in ["n/a", "na", ""]:
            assignee = assignee_text
        description = line[:match.start()].strip() # Get the part before the assignee match

    return description, assignee

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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((APIError, RateLimitError, APIConnectionError))
    )
    async def _transcribe_with_retry():
        try:
            with open(audio_file_path, "rb") as audio_file_object:
                transcript_response = await asyncio.to_thread(
                    openai_client.audio.transcriptions.create,
                    model="whisper-1",
                    file=audio_file_object
                )
            transcript = transcript_response.text
            logger.info(f"Task {task_id}: STT successful. Transcript length: {len(transcript)} chars.")
            return transcript
        except AuthenticationError as e:
            logger.error(f"Task {task_id}: OpenAI AuthenticationError during STT: {e}. Will not retry.", exc_info=True)
            # Non-retryable, re-raise to be caught by the outer handler or let it propagate if not caught.
            # For this function, we want to return None and log.
            raise # Will be caught by the outer try-except
        except APIError as e: # Includes RateLimitError, APIConnectionError, etc. that are retryable by tenacity
            logger.warning(f"Task {task_id}: OpenAI APIError during STT (will retry if applicable): {e}", exc_info=True)
            raise # Re-raise to trigger tenacity retry
        except Exception as e: # Catch other unexpected errors during the attempt
            logger.error(f"Task {task_id}: Unexpected error during STT attempt: {e}", exc_info=True)
            raise # Re-raise to be caught by the outer try-except

    try:
        return await _transcribe_with_retry()
    except AuthenticationError: # Already logged, just ensure None is returned
        return None
    except Exception as e: # This catches errors after retries are exhausted or non-retryable ones not AuthenticationError
        logger.error(f"Task {task_id}: OpenAI Whisper STT failed for {audio_file_path} after retries or due to non-retryable error: {e}", exc_info=True)
        return None

async def create_notion_page_with_title(
    task_id: str,
    page_title: str
) -> Optional[tuple[str, str]]: # Returns (page_url, page_id) or None
    """
    Creates a new page in Notion with only the given title.
    Uses `notion_parent_page_id` from environment if set, otherwise creates in workspace root.
    Returns a tuple (URL, page_ID) of the created page or None if an error occurs or Notion is disabled.
    """
    if not notion_client:
        logger.warning(f"Task {task_id}: Notion client not available. Skipping Notion page creation.")
        return None

    logger.info(f"Task {task_id}: Preparing to create Notion page with title '{page_title}'.")

    page_properties = {"title": [{"type": "text", "text": {"content": page_title}}]}
    # Create page with no children initially, content will be appended later.
    create_payload = {"parent": {}, "properties": page_properties, "children": []}

    if notion_parent_page_id:
        create_payload["parent"] = {"page_id": notion_parent_page_id}
    else:
        logger.warning(f"Task {task_id}: NOTION_PARENT_PAGE_ID not set. Attempting to create page in default location.")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception) # Generic exception for network, will refine with specific Notion errors if possible
    )
    async def _create_page_with_retry():
        try:
            logger.info(f"Task {task_id}: Attempting to create Notion page (attempt {getattr(_create_page_with_retry, 'retry', {}).get('statistics', {}).get('attempt_number', 1)}).")
            created_page = await notion_client.pages.create(**create_payload)
            page_url = created_page.get("url")
            logger.info(f"Task {task_id}: Notion page created successfully: {page_url}")
            return page_url
        except APIResponseError as e:
            # Check if the error is retryable
            retryable_notion_errors = [
                APIErrorCode.RateLimited,
                APIErrorCode.InternalServerError,
                APIErrorCode.ServiceUnavailable, # Typically a 503
                # ConflictError might be retryable if it's due to eventual consistency, but often indicates a logic issue.
                # For now, not retrying on ConflictError unless specific use case arises.
            ]
            if e.code in retryable_notion_errors:
                logger.warning(f"Task {task_id}: Notion APIResponseError (retryable - {e.code.value}) while creating page: {e}. Will retry.", exc_info=True)
                raise # Re-raise to trigger tenacity retry
            else:
                logger.error(f"Task {task_id}: Notion APIResponseError (non-retryable - {e.code.value}) while creating page: {e}", exc_info=True)
                raise # Re-raise to be caught by outer try-except as non-retryable
        except Exception as e: # Other exceptions like network issues
            logger.warning(f"Task {task_id}: Unexpected error during Notion page creation (will retry): {e}", exc_info=True)
            raise # Re-raise to trigger tenacity retry

    try:
        return await _create_page_with_retry()
    except APIResponseError as e: # Non-retryable APIResponseError after check inside retry func
        # Error already logged with specifics
        return None
    except Exception as e: # Catches errors after retries are exhausted or other non-APIResponseErrors
        logger.error(f"Task {task_id}: Failed to create Notion page after retries or due to non-retryable error: {e}", exc_info=True)
        return None


async def append_to_notion_page(page_id: str, task_id: str, content_blocks: List[Dict]) -> bool:
    """
    Appends a list of content blocks to an existing Notion page.
    Returns True on success, False on failure or if Notion is disabled.
    """
    if not notion_client:
        logger.warning(f"Task {task_id}: Notion client not available. Skipping append to page {page_id}.")
        return False
    if not content_blocks:
        logger.info(f"Task {task_id}: No content blocks to append to page {page_id}.")
        return True

    logger.info(f"Task {task_id}: Appending {len(content_blocks)} blocks to Notion page {page_id}.")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception) # Generic for now, refined inside
    )
    async def _append_blocks_with_retry(block_batch: List[Dict]):
        try:
            attempt_num = getattr(_append_blocks_with_retry, 'retry', {}).get('statistics', {}).get('attempt_number', 1)
            logger.info(f"Task {task_id}: Attempting to append {len(block_batch)} blocks to Notion page {page_id} (attempt {attempt_num}).")
            await notion_client.blocks.children.append(block_id=page_id, children=block_batch)
        except APIResponseError as e:
            retryable_notion_errors = [
                APIErrorCode.RateLimited, APIErrorCode.InternalServerError, APIErrorCode.ServiceUnavailable
            ]
            if e.code in retryable_notion_errors:
                logger.warning(f"Task {task_id}: Notion APIResponseError (retryable - {e.code.value}) while appending to page {page_id}: {e}. Will retry batch.", exc_info=True)
                raise
            else:
                logger.error(f"Task {task_id}: Notion APIResponseError (non-retryable - {e.code.value}) while appending to page {page_id}: {e}", exc_info=True)
                raise # Non-retryable, caught by outer try-except
        except Exception as e:
            logger.warning(f"Task {task_id}: Unexpected error during Notion page append (will retry batch): {e}", exc_info=True)
            raise

    try:
        for i in range(0, len(content_blocks), 100):
            batch = content_blocks[i:i+100]
            await _append_blocks_with_retry(batch) # Apply retry to each batch
            if len(content_blocks) > 100:
                logger.info(f"Task {task_id}: Appended batch starting at index {i} to Notion page {page_id}.")
                await asyncio.sleep(0.5) # Small delay if multiple batches

        logger.info(f"Task {task_id}: Successfully appended all blocks to Notion page {page_id}.")
        return True
    except APIResponseError as e: # Non-retryable APIResponseError
        # Error already logged from within retry logic
        return False
    except Exception as e: # Catches errors after retries on a batch are exhausted
        logger.error(f"Task {task_id}: Failed to append blocks to Notion page {page_id} after retries: {e}", exc_info=True)
        return False

async def _call_openai_chat_completion(task_id: str, system_message: str, user_message: str, model: str = "gpt-3.5-turbo") -> Optional[str]:
    """Helper function to call OpenAI Chat Completion API."""
    if not openai_client:
        logger.warning(f"Task {task_id}: OpenAI client not available. Skipping LLM call.")
        return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((APIError, RateLimitError, APIConnectionError))
    )
    async def _chat_completion_with_retry():
        try:
            logger.info(f"Task {task_id}: Calling OpenAI Chat Completion API with model {model} (attempt {getattr(_chat_completion_with_retry, 'retry', {}).get('statistics', {}).get('attempt_number', 1)}).")
            response = await asyncio.to_thread(
                openai_client.chat.completions.create,
                model=model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3, # Lower temperature for more factual/deterministic output
            )
            content = response.choices[0].message.content
            logger.info(f"Task {task_id}: LLM call successful. Response length: {len(content or '')} chars.")
            return content.strip() if content else None
        except AuthenticationError as e:
            logger.error(f"Task {task_id}: OpenAI AuthenticationError during chat completion: {e}. Will not retry.", exc_info=True)
            raise
        except APIError as e: # Retryable errors
            logger.warning(f"Task {task_id}: OpenAI APIError during chat completion (will retry if applicable): {e}", exc_info=True)
            raise
        except Exception as e: # Other unexpected errors
            logger.error(f"Task {task_id}: Unexpected error during chat completion attempt: {e}", exc_info=True)
            raise

    try:
        return await _chat_completion_with_retry()
    except AuthenticationError: # Already logged
        return None
    except Exception as e: # Catches errors after retries or non-retryable ones
        logger.error(f"Task {task_id}: OpenAI Chat Completion API call failed for model {model} after retries or due to non-retryable error: {e}", exc_info=True)
        return None

async def get_llm_summary(transcript: str, task_id: str) -> Optional[str]:
    """Generates a summary of the transcript using an LLM."""
    logger.info(f"Task {task_id}: Requesting LLM summary for transcript (length: {len(transcript)}).")
    system_message = "You are a helpful AI assistant tasked with summarizing meeting transcripts. Provide a concise summary that captures the main topics discussed, key insights, and overall outcome of the meeting."
    user_message = f"Please provide a concise summary of the following meeting transcript:\n\n<transcript>\n{transcript}\n</transcript>\n\nSummary:"

    summary = await _call_openai_chat_completion(task_id, system_message, user_message)
    if not summary or summary.lower().strip() == "no summary available." or len(summary.strip()) < 10 : # Basic check for empty/useless summary
        logger.warning(f"Task {task_id}: LLM generated an empty or trivial summary.")
        return None
    return summary

async def get_llm_decisions(transcript: str, task_id: str) -> Optional[str]:
    """Extracts key decisions from the transcript using an LLM."""
    logger.info(f"Task {task_id}: Requesting LLM to extract key decisions (transcript length: {len(transcript)}).")
    system_message = "You are an AI assistant specializing in extracting key decisions from meeting transcripts. List the decisions made during the meeting. Each decision should be on a new line and start with '- '. If no clear decisions are found, state 'No specific decisions were identified.'"
    user_message = f"Extract the key decisions made from the following meeting transcript. Ensure each decision is on a new line and starts with '- '.\n\n<transcript>\n{transcript}\n</transcript>\n\nKey Decisions:"
    # Removed the trailing '-' from the prompt as we expect the LLM to generate it.

    decisions_text = await _call_openai_chat_completion(task_id, system_message, user_message)
    if not decisions_text or "no specific decisions were identified" in decisions_text.lower() or len(decisions_text.strip()) < 5:
        logger.info(f"Task {task_id}: LLM reported no specific decisions or an empty list.")
        return None
    # Prepend the leading dash if the model didn't include it and it's a list
    if not decisions_text.strip().startswith("-"):
        return f"- {decisions_text.strip()}"
    return decisions_text.strip()


async def get_llm_action_items(transcript: str, task_id: str) -> Optional[str]:
    """Extracts action items from the transcript using an LLM."""
    logger.info(f"Task {task_id}: Requesting LLM to extract action items (transcript length: {len(transcript)}).")
    system_message = "You are an AI assistant skilled at identifying action items from meeting transcripts. List all action items discussed. Each action item should be on a new line and start with '- '. For each action item, if an assignee or owner is mentioned, please include that using the format '(Assigned to: [Name/N/A])'. If no action items are found, state 'No specific action items were identified.'"
    user_message = f"Identify all action items from the following meeting transcript. Ensure each action item is on a new line and starts with '- '. If possible, for each action item, specify the person assigned or responsible using the format '(Assigned to: [Name/N/A])'.\n\nExample:\n- Review the budget proposal (Assigned to: John Doe)\n- Follow up with client (Assigned to: N/A)\n\n<transcript>\n{transcript}\n</transcript>\n\nAction Items:"
    # Removed the trailing '-' from the prompt.

    action_items_text = await _call_openai_chat_completion(task_id, system_message, user_message)
    if not action_items_text or "no specific action items were identified" in action_items_text.lower() or len(action_items_text.strip()) < 5:
        logger.info(f"Task {task_id}: LLM reported no specific action items or an empty list.")
        return None
    if not action_items_text.strip().startswith("-"):
        return f"- {action_items_text.strip()}"
    return action_items_text.strip()


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
                task.transcript_preview = transcript
                task.message = "Transcription successful."
                logger.info(f"Task {task.task_id}: Transcription successful.")

                page_creation_result = await create_notion_page_with_title(
                    task_id=task.task_id,
                    page_title=task.notion_page_title
                )

                if page_creation_result:
                    page_url, page_id = page_creation_result
                    task.message = f"Notion page created: {page_url}." # Base message
                    logger.info(f"Task {task.task_id}: Successfully created Notion page shell: {page_url}")

                    insights_blocks = []
                    insights_blocks.append({"type": "heading_1", "heading_1": {"rich_text": [{"type": "text", "text": {"content": "Meeting Insights"}}]}})
                    insights_blocks.append({"type": "divider", "divider": {}})

                    # Summary
                    summary = await get_llm_summary(transcript, task.task_id)
                    insights_blocks.append({"type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Summary"}}]}})
                    if summary:
                        task.notes_preview = summary[:200] + "..." if len(summary) > 200 else summary
                        insights_blocks.append({"type": "callout", "callout": {"rich_text": [{"type": "text", "text": {"content": summary}}], "icon": {"emoji": "📝"}}})
                        task.message += " Summary generated."
                    else:
                        insights_blocks.append({"type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": "No summary could be generated."}}]}})
                        task.message += " Summary generation failed or was empty."
                    insights_blocks.append({"type": "divider", "divider": {}})

                    # Key Decisions
                    decisions = await get_llm_decisions(transcript, task.task_id)
                    insights_blocks.append({"type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Key Decisions"}}]}})
                    if decisions:
                        for item_text in decisions.split('\n'):
                            item_text = item_text.strip("- ").strip()
                            if item_text:
                                insights_blocks.append({"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": item_text}}]}})
                        task.message += " Decisions extracted."
                    else:
                        insights_blocks.append({"type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": "No specific decisions were identified."}}]}})
                        task.message += " Decision extraction failed or was empty."
                    insights_blocks.append({"type": "divider", "divider": {}})

                    # Action Items
                    action_items_text = await get_llm_action_items(transcript, task.task_id)
                    insights_blocks.append({"type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Action Items"}}]}})
                    if action_items_text:
                        action_item_count = 0
                        for line in action_items_text.split('\n'):
                            description, assignee = parse_action_item_line(line)
                            if description: # Only add if there's a description
                                display_text = description
                                if assignee:
                                    display_text += f" (Assigned to: {assignee})"

                                insights_blocks.append({
                                    "type": "to_do",
                                    "to_do": {
                                        "rich_text": [{"type": "text", "text": {"content": display_text}}],
                                        "checked": False
                                    }
                                })
                                action_item_count += 1
                        if action_item_count > 0:
                            task.message += f" {action_item_count} action item(s) extracted."
                        else:
                            # This case handles if LLM returns text for action items, but parsing yields nothing (e.g. "No action items found" as a single line)
                            task.message += " No valid action items found after parsing LLM output."
                            insights_blocks.append({"type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": "No specific action items were identified after parsing."}}]}})
                    else:
                        insights_blocks.append({"type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": "No specific action items were identified."}}]}})
                        task.message += " Action item extraction LLM call failed or was empty."

                    # Append all "Meeting Insights" blocks
                    if not await append_to_notion_page(page_id, task.task_id, insights_blocks):
                        task.message += " [Warning] Failed to append Meeting Insights to Notion."
                        logger.warning(f"Task {task.task_id}: Failed to append Meeting Insights to Notion page {page_id}")

                    # Full Transcript Section
                    transcript_section_blocks = []
                    transcript_header_text = "Full Transcript"

                    actual_transcript_paragraph_blocks = []
                    if not transcript.strip():
                         actual_transcript_paragraph_blocks.append({"type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": "(Transcript was empty)"}}]}})
                    else:
                        transcript_paragraphs = transcript.split('\n\n')
                        if len(transcript_paragraphs) == 1 and '\n' in transcript: # Handle single block of text with newlines
                            transcript_paragraphs = transcript.split('\n')
                        for para in transcript_paragraphs:
                            para_text = para.strip()
                            if not para_text: continue
                            # Max 2000 chars per paragraph block handled by Notion client, but Notion API has 100 blocks per append
                            # Keep individual paragraphs relatively short if possible for LLM output structure.
                            # Here, we just pass the paragraph as is, assuming it's reasonably sized.
                            # For very long paragraphs, chunking (as done in the original create_notion_page_with_transcript) might be needed
                            # if we weren't using the SDK's auto-chunking for paragraph content (which it does).
                            # The main concern is total number of blocks.
                            actual_transcript_paragraph_blocks.append({"type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": para_text}}]}})

                    # Decide whether to use a toggle for the transcript
                    if len(actual_transcript_paragraph_blocks) > 7 or len(transcript) > 2500: # Heuristic for using toggle
                        # Max 100 children for a toggle block when creating/appending
                        toggle_children = [{"type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": transcript_header_text}}]}}]
                        toggle_children.extend(actual_transcript_paragraph_blocks[:98]) # Leave room for header + ensure under 100
                        transcript_section_blocks.append({
                            "type": "toggle",
                            "toggle": {
                                "rich_text": [{"type": "text", "text": {"content": "View Full Transcript"}}], # Toggle Title
                                "children": toggle_children
                            }
                        })
                        if len(actual_transcript_paragraph_blocks) > 98:
                             task.message += " [Info] Transcript was long and might be truncated in toggle view."
                    else:
                        transcript_section_blocks.append({"type": "heading_1", "heading_1": {"rich_text": [{"type": "text", "text": {"content": transcript_header_text}}]}})
                        transcript_section_blocks.extend(actual_transcript_paragraph_blocks)

                    if not await append_to_notion_page(page_id, task.task_id, transcript_section_blocks):
                        task.message += " [Warning] Failed to append Full Transcript to Notion."
                        logger.warning(f"Task {task.task_id}: Failed to append Full Transcript to Notion page {page_id}")

                    task.final_notes_location = page_url
                    task.status = TaskStatus.COMPLETED
                    task.message += " Task processing completed." # Final message part

                else: # Initial Notion page (title only) creation failed
                    task.status = TaskStatus.ERROR
                    task.message = "Transcription successful, but failed to create Notion page shell. LLM analysis not performed or stored."
                    logger.error(f"Task {task.task_id}: Failed to create initial Notion page (title only). Transcript available in preview.")
            else: # Transcription failed
                task.status = TaskStatus.ERROR
                task.message = "Transcription failed after retries. No Notion page created or LLM analysis performed."
                logger.error(f"Task {task.task_id}: Transcription failed for {task._audio_file_path}. Further processing halted.")

        elif task.status == TaskStatus.ERROR: # Error occurred before STT/Notion/LLM part
            logger.error(f"Task {task.task_id}: Task ended with error before STT/Notion/LLM processing. Status: {task.status}, Message: {task.message}")
        else: # Should not happen if status was ACTIVE or PROCESSING_COMPLETION before this block
            logger.warning(f"Task {task.task_id}: Task in unexpected state {task.status} at STT/Notion/LLM phase. Marking as error.")
            task.status = TaskStatus.ERROR
            task.message = (task.message or "") + " Task finalized with error due to unexpected state before STT."

        logger.info(f"Task {task.task_id}: Final processing complete. Final status for DB: {task.status}")

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

        # Persist all final changes to the task to the database
        try:
            await update_task_in_db(task)
            logger.info(f"Task {task.task_id}: Final state saved to DB in audio_capture_loop. Status: {task.status}")
        except Exception as e_db_update:
            logger.error(f"Task {task.task_id}: Critical error: Failed to save final task state to DB in audio_capture_loop: {e_db_update}", exc_info=True)
            # This is a significant issue, as the DB might not reflect the task's true end state.
            # Depending on policy, could try a retry mechanism or ensure this is heavily monitored.


# --- FastAPI Application ---

@app.websocket("/ws/transcribe")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    transcription_skill = TranscriptionSkill(os.getenv("DEEPGRAM_API_KEY"))
    transcription_skill.start(lambda transcript: websocket.send_text(transcript))

    try:
        while True:
            data = await websocket.receive_bytes()
            transcription_skill.send(data)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        transcription_skill.stop()
        await websocket.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Live Meeting Worker starting up...")
    await init_db()
    await handle_interrupted_tasks()
    # You could pre-load other models or connect to other databases here if needed
    yield
    # Shutdown logic
    logger.info("Live Meeting Worker shutting down...")
    # Clean up any ongoing asyncio tasks (which are in-memory)
    for task_id, async_task_obj in list(running_async_tasks.items()):
        if async_task_obj and not async_task_obj.done():
            logger.info(f"Cancelling ongoing asyncio task {task_id} during shutdown.")
            async_task_obj.cancel()
            try:
                await async_task_obj # Give it a chance to clean up
            except asyncio.CancelledError:
                logger.info(f"Asyncio task {task_id} cancelled successfully during shutdown.")
            except Exception as e:
                logger.error(f"Error during cancellation of asyncio task {task_id} on shutdown: {e}")
        # The database record for this task should have already been updated by handle_interrupted_tasks
        # or by the task itself if it completed/errored before shutdown.
        # If we want to be absolutely sure, we could re-query and update DB status here too,
        # but handle_interrupted_tasks on next startup is the primary mechanism for DB state correction.

    logger.info("Live Meeting Worker shutdown complete.")


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

    try:
        await add_task_to_db(task)
        logger.info(f"Task {task_id} created and saved to DB for user {request.user_id}. Status: {task.status}")
    except Exception as e:
        logger.error(f"Task {task_id}: Failed to save initial task to database: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to initialize task in database.")

    # Start the audio capture loop in the background using asyncio.create_task.
    # The audio_capture_loop function will update the task object (fetched from DB or passed)
    # and persist these updates to the database.
    # We pass a *copy* of the task object or relevant details if audio_capture_loop fetches its own state.
    # For now, passing the task object; audio_capture_loop will use it and update DB.
    # The asyncio task itself is stored in running_async_tasks to manage its lifecycle (e.g., for stopping).

    # Create the asyncio.Event for this task
    stop_event = asyncio.Event()
    task_stop_events[task_id] = stop_event
    # The MeetingTask model itself doesn't store the event or the asyncio.Task object,
    # as these are runtime constructs not suitable for DB persistence.
    # We will pass the stop_event to the audio_capture_loop.

    # The `task` object here is Pydantic model. We need to ensure audio_capture_loop uses this instance
    # or fetches a fresh one from DB.
    # For simplicity, audio_capture_loop can receive this `task` instance and be responsible for all DB updates.
    # Crucially, `task._stop_event` needs to be set on this instance if `audio_capture_loop` uses it directly.

    # Re-fetch task from DB to ensure we pass the persisted version if add_task_to_db modified it (e.g. defaults)
    # However, our current add_task_to_db doesn't modify the passed task object in place in a way that's critical here.
    # The main thing is that `audio_capture_loop` must use `update_task_in_db`.

    # Assign the stop event to the task object (will not be persisted)
    task._stop_event = stop_event

    capture_task_async = asyncio.create_task(audio_capture_loop(task))
    running_async_tasks[task_id] = capture_task_async
    # task._audio_stream_task = capture_task_async # This was for the model field, now managed by running_async_tasks

    return StartMeetingResponse(
        task_id=task_id,
        status=task.status, # Will be PENDING initially from the model
        message=task.message
    )

@app.get("/meeting_attendance_status/{task_id}", response_model=MeetingTask)
async def get_meeting_attendance_status(
    task_id: str = Path(..., description="The ID of the task to query")
):
    """
    Polls for the current status and progress of an active meeting attendance task.
    Fetches status directly from the database.
    """
    logger.debug(f"Request received for /meeting_attendance_status/{task_id}")
    task = await get_task_from_db(task_id)

    if not task:
        logger.warning(f"Task not found in DB: {task_id}")
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    # If the task is marked as ACTIVE in the DB, and we have a running asyncio task for it,
    # we can dynamically update its duration based on the actual start time.
    # The DB record's duration_seconds is only updated when the task stops or errors.
    if task.status == TaskStatus.ACTIVE and task.start_time and task_id in running_async_tasks:
        # Ensure the running_async_tasks dict is for the current, live asyncio tasks
        # and not just leftover from a previous run if not cleaned properly (though lifespan should handle it).
        current_duration = (datetime.datetime.now(datetime.timezone.utc) - task.start_time).total_seconds()
        task.duration_seconds = current_duration # Update for the response, not persisted here

    logger.debug(f"Returning status for task {task_id} from DB: {task.status}, message: {task.message}")
    return task

@app.post("/stop_meeting_attendance/{task_id}", response_model=MeetingTask)
async def stop_meeting_attendance(
    task_id: str = Path(..., description="The ID of the task to stop")
):
    """
    Manually stops an ongoing meeting attendance task.
    Updates status in the database.
    """
    logger.info(f"Request received for /stop_meeting_attendance/{task_id}")
    task = await get_task_from_db(task_id)

    if not task:
        logger.warning(f"Task not found in DB for stopping: {task_id}")
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    if task.status not in [TaskStatus.ACTIVE, TaskStatus.PENDING]:
        logger.warning(f"Task {task_id} is not active or pending (status: {task.status}), cannot stop. Returning current state.")
        # Return the current state from DB, as it's already in a terminal or non-stoppable state.
        return task

    # Retrieve the stop event and the asyncio task
    stop_event = task_stop_events.get(task_id)
    async_task_obj = running_async_tasks.get(task_id)

    original_status = task.status # Keep original status for logging/logic

    if stop_event and not stop_event.is_set():
        logger.info(f"Task {task_id}: Signaling audio capture to stop via event.")
        task.status = TaskStatus.PROCESSING_COMPLETION # Optimistic: will be completed by loop
        task.message = "Stop request received. Finalizing task..."
        stop_event.set() # Signal the audio_capture_loop to stop

        if async_task_obj and not async_task_obj.done():
            try:
                # Give the audio_capture_loop some time to finish gracefully
                await asyncio.wait_for(async_task_obj, timeout=15.0) # Increased timeout
                logger.info(f"Task {task_id}: Audio capture loop completed after stop signal.")
                # The audio_capture_loop should have updated the task's status in DB to COMPLETED or ERROR.
                # Re-fetch the task to get its final state.
                task = await get_task_from_db(task_id) or task # Fallback to current task if somehow not found
            except asyncio.TimeoutError:
                logger.error(f"Task {task_id}: Timeout waiting for audio capture loop to complete. Forcing cancellation.")
                async_task_obj.cancel()
                task.status = TaskStatus.ERROR
                task.message = "Error: Timeout during stop. Audio capture forcibly cancelled."
                if not task.end_time: task.end_time = datetime.datetime.now(datetime.timezone.utc)
            except Exception as e:
                logger.error(f"Task {task_id}: Error waiting for audio capture loop completion: {e}", exc_info=True)
                task.status = TaskStatus.ERROR
                task.message = f"Error during task stop: {str(e)}"
                if not task.end_time: task.end_time = datetime.datetime.now(datetime.timezone.utc)
        else: # No running async task, or it was already done
             logger.info(f"Task {task_id}: No active async task to wait for, or task was already done. Current DB status: {task.status}")
             if original_status == TaskStatus.PENDING: # If it was pending and never really started
                 task.status = TaskStatus.COMPLETED # Or perhaps a new "CANCELLED" status
                 task.message = "Task stopped before full activation."
                 if not task.end_time: task.end_time = datetime.datetime.now(datetime.timezone.utc)
             # If it was ACTIVE but async task is done, audio_capture_loop's finally should handle DB update.
             # Re-fetch to be sure.
             refetched_task = await get_task_from_db(task_id)
             if refetched_task: task = refetched_task

    elif not stop_event and original_status == TaskStatus.PENDING :
        # Task was PENDING, never fully started (no stop_event created, no async task)
        logger.info(f"Task {task_id}: Was PENDING and no stop event/async task found. Marking as completed/cancelled.")
        task.status = TaskStatus.COMPLETED # Or CANCELLED
        task.message = "Task stopped while pending and before async execution."
        if not task.end_time: task.end_time = datetime.datetime.now(datetime.timezone.utc)

    else: # No stop event, or already set, or no async task associated (should not happen if task is ACTIVE)
        logger.info(f"Task {task_id}: No active audio capture process to signal stop, or already stopping/stopped. Current DB status: {task.status}")
        # If it's already processing completion, completed, or error, that's fine.
        # If it was PENDING and somehow missed above, ensure it's finalized.
        if task.status == TaskStatus.PENDING:
            task.status = TaskStatus.COMPLETED
            task.message = "Task stopped before activation (final check)."
            if not task.end_time: task.end_time = datetime.datetime.now(datetime.timezone.utc)


    # Calculate duration if it hasn't been set by the loop's finalization
    if task.start_time and task.end_time and not task.duration_seconds:
        task.duration_seconds = (task.end_time - task.start_time).total_seconds()
    elif task.start_time and not task.end_time and task.status in [TaskStatus.COMPLETED, TaskStatus.ERROR]:
        # If loop somehow didn't set end_time but task is terminal
        task.end_time = datetime.datetime.now(datetime.timezone.utc)
        task.duration_seconds = (task.end_time - task.start_time).total_seconds()


    # Persist the final state determined by this stop endpoint logic
    try:
        await update_task_in_db(task)
        logger.info(f"Task {task_id} stop processed. Final status in DB: {task.status}")
    except Exception as e:
        logger.error(f"Task {task_id}: Failed to update task status in DB during stop: {e}", exc_info=True)
        # The task object returned might not reflect the DB state if this fails.

    # Clean up from runtime tracking dictionaries
    running_async_tasks.pop(task_id, None)
    task_stop_events.pop(task_id, None)

    return task


if __name__ == "__main__":
    import uvicorn
    # This is for direct execution. `uvicorn main:app --reload` is preferred for dev.
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")

```
