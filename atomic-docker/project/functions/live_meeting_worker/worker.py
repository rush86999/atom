import json
import os
import sys
import logging
import asyncio
import uuid # Though taskId comes from message, good to have if worker needs to generate IDs

# Adjust sys.path to allow imports from parent 'functions' directory
FUNCTIONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if FUNCTIONS_DIR not in sys.path:
    sys.path.append(FUNCTIONS_DIR)
AGENTS_DIR = os.path.join(FUNCTIONS_DIR, 'agents') # If agents are in functions/agents
if AGENTS_DIR not in sys.path:
     sys.path.append(AGENTS_DIR)

# LanceDB service import
try:
    from _utils.lancedb_service import create_meeting_transcripts_table_if_not_exists
except ImportError as e:
    print(f"Warning: Failed to import lancedb_service: {e}", file=sys.stderr)
    create_meeting_transcripts_table_if_not_exists = None # Placeholder

# Kafka Consumer (using kafka-python)
try:
    from kafka import KafkaConsumer
    from kafka.errors import KafkaError
    KAFKA_AVAILABLE = True
except ImportError:
    KafkaConsumer = None
    KafkaError = Exception # Placeholder
    KAFKA_AVAILABLE = False
    print("WARNING: kafka-python library not found. Kafka worker cannot start.", file=sys.stderr)

# Agent Imports
ZoomAgent = None
GoogleMeetAgent = None
MSTeamsAgent = None
try:
    from agents.zoom_agent import ZoomAgent as ImportedZoomAgent
    ZoomAgent = ImportedZoomAgent
except ImportError as e:
    print(f"Warning: ZoomAgent failed to import in worker: {e}", file=sys.stderr)
try:
    from agents.google_meet_agent import GoogleMeetAgent as ImportedGoogleMeetAgent
    GoogleMeetAgent = ImportedGoogleMeetAgent
except ImportError as e:
    print(f"Warning: GoogleMeetAgent failed to import in worker: {e}", file=sys.stderr)
try:
    from agents.ms_teams_agent import MSTeamsAgent as ImportedMSTeamsAgent
    MSTeamsAgent = ImportedMSTeamsAgent
except ImportError as e:
    print(f"Warning: MSTeamsAgent failed to import in worker: {e}", file=sys.stderr)

# note_utils import
note_utils_module = None
try:
    import note_utils as nu_module
    note_utils_module = nu_module
    if not hasattr(note_utils_module, 'process_live_audio_for_notion') or \
       not hasattr(note_utils_module, 'init_notion'):
        print("Error: Required functions (process_live_audio_for_notion, init_notion) not found in note_utils.", file=sys.stderr)
        note_utils_module = None
except ImportError as e:
    print(f"Critical Import Error for note_utils in live_meeting_worker: {e}", file=sys.stderr)

# Constants
try:
    from _utils import constants as app_constants
except ImportError:
    class MockAppConstants: # Fallback if constants can't be imported (e.g. path issue in test)
        KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        KAFKA_LIVE_MEETING_TOPIC = os.environ.get("KAFKA_LIVE_MEETING_TOPIC", "atom_live_meeting_tasks")
    app_constants = MockAppConstants()
    print("Warning: Could not import shared constants for Kafka worker. Using fallback values.", file=sys.stderr)


# Logging Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def process_live_meeting_message(message_payload: dict):
    """
    Processes a single live meeting task message from Kafka.
    """
    task_id = message_payload.get('taskId', str(uuid.uuid4()))
    logger.info(f"Task {task_id}: Received live meeting processing request.")

    # --- Extract data from payload ---
    user_id = message_payload.get('userId')
    platform = message_payload.get('platform', '').lower()
    meeting_identifier = message_payload.get('meetingIdentifier')
    notion_note_title = message_payload.get('notionNoteTitle')

    notion_source = message_payload.get('notionSource', 'Live Meeting Transcription via Kafka Worker')
    linked_event_id = message_payload.get('linkedEventId')
    notion_db_id = message_payload.get('notionDbId') # Optional DB ID for the note

    api_keys = message_payload.get('apiKeys', {})
    notion_api_token = api_keys.get('notion')
    deepgram_api_key = api_keys.get('deepgram')
    openai_api_key = api_keys.get('openai')

    audio_settings = message_payload.get('audioSettings', {})
    audio_device_specifier = audio_settings.get('audioDeviceSpecifier')

    # --- Validate essential parameters ---
    required_for_processing = {
        "userId": user_id, "platform": platform, "meetingIdentifier": meeting_identifier,
        "notionNoteTitle": notion_note_title, "notionApiKey": notion_api_token,
        "deepgramApiKey": deepgram_api_key, "openaiApiKey": openai_api_key
    }
    missing_processing_params = [k for k,v in required_for_processing.items() if not v]
    if missing_processing_params:
        logger.error(f"Task {task_id}: Missing critical parameters for processing: {', '.join(missing_processing_params)}. Payload: {message_payload}")
        return # Cannot proceed

    if not note_utils_module:
        logger.error(f"Task {task_id}: note_utils module not available. Skipping processing.")
        return

    # --- Initialize Notion Client (per task for now, could be optimized) ---
    init_notion_resp = note_utils_module.init_notion(notion_api_token, database_id=notion_db_id)
    if init_notion_resp["status"] != "success":
        logger.error(f"Task {task_id}: Failed to initialize Notion client. Error: {init_notion_resp.get('message')}. Details: {init_notion_resp.get('details')}")
        return

    # --- Agent Instantiation & Configuration ---
    agent = None
    platform_interface = None
    try:
        if platform == "zoom":
            if not ZoomAgent: raise RuntimeError("ZoomAgent not imported/available.")
            agent = ZoomAgent(user_id=user_id, target_device_specifier_override=audio_device_specifier)
        elif platform in ["googlemeet", "google_meet"]:
            if not GoogleMeetAgent: raise RuntimeError("GoogleMeetAgent not imported/available.")
            agent = GoogleMeetAgent(user_id=user_id, target_device_specifier_override=audio_device_specifier)
        elif platform in ["msteams", "microsoft_teams", "teams"]:
            if not MSTeamsAgent: raise RuntimeError("MSTeamsAgent not imported/available.")
            agent = MSTeamsAgent(user_id=user_id, target_device_specifier_override=audio_device_specifier)
        else:
            logger.error(f"Task {task_id}: Platform '{platform}' is not supported. Supported: zoom, googlemeet, msteams.")
            return
        platform_interface = agent

        logger.info(f"Task {task_id}: Instantiated {type(agent).__name__} for user {user_id} on platform {platform}.")

        # --- Meeting Lifecycle ---
        logger.info(f"Task {task_id}: Attempting to join meeting {meeting_identifier}...")
        join_success = platform_interface.join_meeting(meeting_identifier)

        if not join_success:
            logger.error(f"Task {task_id}: Agent failed to launch/join meeting: {meeting_identifier} on platform {platform}.")
            return # Cannot proceed if join fails

        logger.info(f"Task {task_id}: Successfully joined {meeting_identifier}. Starting live processing.")

        process_live_audio_func = getattr(note_utils_module, 'process_live_audio_for_notion')
        current_meeting_id = platform_interface.get_current_meeting_id() or meeting_identifier

        processing_result = await process_live_audio_func(
            platform_module=platform_interface,
            meeting_id=current_meeting_id,
            notion_note_title=notion_note_title,
            deepgram_api_key=deepgram_api_key,
            openai_api_key=openai_api_key,
            notion_db_id=notion_db_id,
            notion_source=notion_source,
            linked_event_id=linked_event_id
        )

        if processing_result and processing_result.get("status") == "success":
            logger.info(f"Task {task_id}: Successfully processed and created Notion note: {processing_result.get('data')}")

            # --- Embed and Store Transcript in LanceDB ---
            notion_page_id = processing_result["data"].get("notion_page_id")
            full_transcript_text = processing_result["data"].get("full_transcript")

            lancedb_uri_call = os.environ.get("LANCEDB_URI")

            if notion_page_id and full_transcript_text and lancedb_uri_call:
                logger.info(f"Task {task_id}: Attempting to embed transcript for Notion page {notion_page_id}")
                try:
                    # Meeting date: Pass None, so embed_and_store_transcript_in_lancedb uses current time.
                    # Sourcing a more accurate meeting_date from linked_event_id is a future enhancement.
                    meeting_date_iso_param = None

                    embed_and_store_func = getattr(note_utils_module, 'embed_and_store_transcript_in_lancedb', None)
                    if embed_and_store_func:
                        # Note: embed_and_store_transcript_in_lancedb is synchronous in note_utils.py
                        # If it were async, this would need `await` and the calling function `process_live_meeting_message`
                        # would need to be consistently async (it already is).
                        # For now, assuming it's synchronous as per current definition.
                        # If it becomes async: embed_result = await embed_and_store_func(...)
                        embed_result = embed_and_store_func(
                            notion_page_id=notion_page_id,
                            transcript_text=full_transcript_text,
                            meeting_title=notion_note_title, # from original payload
                            meeting_date_iso=meeting_date_iso_param,
                            user_id=user_id, # from original payload
                            openai_api_key_param=openai_api_key, # from original payload
                            lancedb_uri_param=lancedb_uri_call
                        )
                        if embed_result.get("status") == "success":
                            logger.info(f"Task {task_id}: Successfully embedded transcript for Notion page {notion_page_id}")
                        else:
                            logger.error(f"Task {task_id}: Failed to embed transcript for {notion_page_id}. Error: {embed_result.get('message')}")
                    else:
                        logger.error(f"Task {task_id}: 'embed_and_store_transcript_in_lancedb' not found in note_utils.")
                except Exception as e:
                    logger.error(f"Task {task_id}: Exception during transcript embedding for {notion_page_id}: {e}", exc_info=True)
            elif not lancedb_uri_call:
                logger.info(f"Task {task_id}: Skipping LanceDB embedding for {notion_page_id} as LANCEDB_URI is not set (checked at call time).")
            elif not notion_page_id or not full_transcript_text:
                logger.warning(f"Task {task_id}: Skipping LanceDB embedding for {notion_page_id if notion_page_id else 'Unknown Page'} due to missing notion_page_id or full_transcript.")

        else:
            err_msg = processing_result.get("message", "Processing failed") if processing_result else "Processing function returned None."
            err_code = processing_result.get("code", "PROCESSING_FAILED") if processing_result else "PROCESSING_RETURNED_NONE"
            err_details = processing_result.get("details") if processing_result else None
            logger.error(f"Task {task_id}: Live audio processing failed for {current_meeting_id}. Code: {err_code}, Msg: {err_msg}, Details: {err_details}")

    except Exception as e:
        logger.error(f"Task {task_id}: Unexpected error during processing: {str(e)}", exc_info=True)
    finally:
        if agent and hasattr(agent, 'current_meeting_id') and agent.current_meeting_id:
            meeting_id_for_leave = agent.get_current_meeting_id()
            logger.info(f"Task {task_id}: Ensuring agent leaves meeting {meeting_id_for_leave}.")
            if hasattr(agent, 'leave_meeting') and asyncio.iscoroutinefunction(agent.leave_meeting):
                await agent.leave_meeting()
            elif hasattr(agent, 'leave_meeting'): # Should be async
                agent.leave_meeting()
        logger.info(f"Task {task_id}: Processing finished.")


async def consume_live_meeting_tasks():
    """
    Consumes tasks from the Kafka topic for live meeting processing.
    """
    if not KAFKA_AVAILABLE:
        logger.error("Kafka client library (kafka-python) not available. Worker cannot start.")
        return
    if not ZoomAgent and not GoogleMeetAgent and not MSTeamsAgent:
        logger.error("No meeting agent implementations (Zoom, GoogleMeet, MSTeams) are available. Worker cannot effectively process tasks.")
        return
    if not note_utils_module:
        logger.error("note_utils module is not available. Worker cannot process tasks.")
        return

    # --- Initialize LanceDB Table for Meeting Transcripts ---
    lancedb_uri_env = os.environ.get("LANCEDB_URI")
    if not lancedb_uri_env:
        logger.warning("LANCEDB_URI environment variable not set. LanceDB operations for meeting transcripts will be skipped.")
    elif not create_meeting_transcripts_table_if_not_exists:
        logger.warning("create_meeting_transcripts_table_if_not_exists function not available. LanceDB table initialization skipped.")
    else:
        try:
            # This function is synchronous
            create_meeting_transcripts_table_if_not_exists(db_path=lancedb_uri_env)
            logger.info(f"Ensured LanceDB table 'meeting_transcripts' exists at {lancedb_uri_env}")
        except Exception as e:
            logger.error(f"Failed to initialize LanceDB table 'meeting_transcripts': {e}", exc_info=True)
            # Worker will continue, but embedding will likely fail if table is needed.

    consumer = None
    try:
        consumer = KafkaConsumer(
            app_constants.KAFKA_LIVE_MEETING_TOPIC,
            bootstrap_servers=app_constants.KAFKA_BOOTSTRAP_SERVERS.split(','),
            group_id="live-meeting-worker-group-v1", # Consumer group ID
            auto_offset_reset='earliest', # Start reading at the earliest message if no offset stored
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            # key_deserializer=lambda x: x.decode('utf-8') if x else None, # If key is used
            # enable_auto_commit=True, # Default, commits offsets automatically in background
            # auto_commit_interval_ms=5000 # Default
            # For more control, set enable_auto_commit=False and commit manually:
            # consumer.commit()
        )
        logger.info(f"KafkaConsumer initialized for topic '{app_constants.KAFKA_LIVE_MEETING_TOPIC}' on servers '{app_constants.KAFKA_BOOTSTRAP_SERVERS}'. Waiting for messages...")

        async for message in consumer:
            task_id = message.value.get('taskId', 'UnknownTask')
            logger.info(f"Task {task_id}: Received message from Kafka: Topic '{message.topic}', Partition {message.partition}, Offset {message.offset}")
            try:
                await process_live_meeting_message(message.value)
                # If manual commit: consumer.commit() # or commit specific offsets
            except Exception as e:
                logger.error(f"Task {task_id}: Unhandled exception during process_live_meeting_message: {e}", exc_info=True)
                # Decide on error strategy: retry, dead-letter queue, or skip.
                # For now, it logs and continues to next message.

    except KafkaError as e:
        logger.error(f"Kafka Consumer error: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error in Kafka consumer loop: {e}", exc_info=True)
    finally:
        if consumer:
            logger.info("Closing Kafka consumer.")
            consumer.close()

if __name__ == '__main__':
    logger.info("Starting Live Meeting Worker...")
    # Ensure Python 3.7+ for asyncio.run
    if sys.version_info >= (3, 7):
        try:
            asyncio.run(consume_live_meeting_tasks())
        except KeyboardInterrupt:
            logger.info("Worker shutdown requested via KeyboardInterrupt.")
        except Exception as e: # Catch errors from consume_live_meeting_tasks if it raises before loop
            logger.error(f"Critical error preventing worker from running: {e}", exc_info=True)
    else:
        logger.error("Python 3.7 or higher is required to run this worker.")

[end of atomic-docker/project/functions/live_meeting_worker/worker.py]
