import os
import requests
import json
import tempfile # For downloading audio from URL
from notion_client import Client, APIResponseError
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions, # For configuring client per-stream
    PrerecordedOptions,
    FileSource,
    LiveTranscriptionEvents,
    LiveOptions
)
import openai # For OpenAI
import asyncio # For live streaming
from typing import Optional, List # Ensure List is imported if not already
from datetime import datetime # For handling meeting_date
import logging
from ._utils.lancedb_service import add_transcript_embedding

# --- Global Clients (to be initialized by functions or handlers) ---
notion: Client | None = None
# deepgram_client_global is removed as live streaming needs per-instance client or careful management
# For pre-recorded, we'll also instantiate client per call for simplicity or use a passed-in one.

# --- Global Configuration Variables (can be overridden by parameters) ---
NOTION_API_TOKEN_GLOBAL = os.environ.get("NOTION_API_TOKEN")
NOTION_NOTES_DATABASE_ID_GLOBAL = os.environ.get("NOTION_NOTES_DATABASE_ID")

DEEPGRAM_API_KEY_GLOBAL = os.environ.get("DEEPGRAM_API_KEY")
OPENAI_API_KEY_GLOBAL = os.environ.get("OPENAI_API_KEY")
GPT_MODEL_NAME_GLOBAL = os.environ.get("GPT_MODEL_NAME", "gpt-3.5-turbo-1106")
OPENAI_API_ENDPOINT_GLOBAL = os.environ.get("OPENAI_API_ENDPOINT", "https://api.openai.com/v1/chat/completions")


def init_notion(api_token: str, database_id: str = None) -> dict:
    global notion, NOTION_API_TOKEN_GLOBAL, NOTION_NOTES_DATABASE_ID_GLOBAL
    if not api_token: return {"status": "error", "message": "Notion API token required.", "code": "CONFIG_ERROR"}
    NOTION_API_TOKEN_GLOBAL = api_token
    if database_id: NOTION_NOTES_DATABASE_ID_GLOBAL = database_id
    try:
        notion = Client(auth=NOTION_API_TOKEN_GLOBAL)
        return {"status": "success", "message": "Notion client initialized."}
    except Exception as e:
        notion = None
        return {"status": "error", "message": f"Failed to initialize Notion client: {str(e)}", "code": "NOTION_CLIENT_INIT_ERROR"}

# init_deepgram is removed as we'll pass key to functions needing Deepgram client

# --- Notion Functions (create_notion_note, get_notion_note, update_notion_note, search_notion_notes) ---
# ... (These functions remain as they were in the last successful 'overwrite_file_with_block' for note_utils.py - Subtask 25)
# ... For brevity, their full code is not repeated here, but they are assumed to be present and correct.
def create_notion_note(
    title: str, content: str, notion_db_id: str = None, source: str = None,
    linked_task_id: str = None, linked_event_id: str = None, transcription: str = None,
    audio_file_link: str = None, summary: str = None, key_points: str = None,
    decisions: list = None, action_items: list = None
) -> dict:
    if not notion: return {"status": "error", "message": "Notion client not initialized.", "code": "NOTION_CLIENT_ERROR"}
    db_id_to_use = notion_db_id or NOTION_NOTES_DATABASE_ID_GLOBAL
    if not db_id_to_use: return {"status": "error", "message": "Notion database ID not configured.", "code": "NOTION_CONFIG_ERROR"}
    if not title: return {"status": "error", "message": "Title is required.", "code": "VALIDATION_ERROR"}

    properties = {"Title": {"title": [{"text": {"content": title}}]}}

    if content and len(content.strip()) > 0 : properties["ContentText"] = {"rich_text": [{"text": {"content": content[:1999]}}]}
    if source: properties["Source"] = {"rich_text": [{"text": {"content": source}}]}
    if linked_task_id: properties["Linked Task ID"] = {"rich_text": [{"text": {"content": linked_task_id}}]}
    if linked_event_id: properties["Linked Event ID"] = {"rich_text": [{"text": {"content": linked_event_id}}]}
    if transcription and len(transcription.strip()) > 0: properties["TranscriptionText"] = {"rich_text": [{"text": {"content": transcription[:1999]}}]}
    if audio_file_link: properties["Audio File Link"] = {"url": audio_file_link}
    if summary and len(summary.strip()) > 0 : properties["Summary"] = {"rich_text": [{"text": {"content": summary[:1999]}}]}
    if key_points and len(key_points.strip()) > 0: properties["Key Points"] = {"rich_text": [{"text": {"content": key_points[:1999]}}]}

    formatted_decisions = ""
    if decisions and isinstance(decisions, list) and len(decisions) > 0:
        formatted_decisions = "\n".join([f"- {str(item)}" for item in decisions])

    formatted_action_items = ""
    if action_items and isinstance(action_items, list) and len(action_items) > 0:
        formatted_action_items = "\n".join([f"- {str(item)}" for item in action_items])

    if formatted_decisions:
        properties["Decisions Logged"] = {"rich_text": [{"text": {"content": formatted_decisions[:1999]}}]}

    if formatted_action_items:
        properties["Action Items Logged"] = {"rich_text": [{"text": {"content": formatted_action_items[:1999]}}]}
    page_content_blocks = []
    if content:
        for i in range(0, len(content), 2000): page_content_blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": content[i:i+2000]}}]}})
    try:
        response = notion.pages.create(parent={"database_id": db_id_to_use}, properties=properties, children=page_content_blocks if page_content_blocks else None)
        return {"status": "success", "data": {"page_id": response["id"], "url": response.get("url")}}
    except APIResponseError as e: return {"status": "error", "message": f"Notion API error: {e.body.get('message', str(e))}", "code": f"NOTION_API_{e.code.upper()}", "details": e.body}
    except Exception as e: return {"status": "error", "message": f"Error creating Notion page: {str(e)}", "code": "NOTION_CREATE_ERROR"}

def get_notion_note(page_id: str) -> dict:
    if not notion: return {"status": "error", "message": "Notion client not initialized.", "code": "NOTION_CLIENT_ERROR"}
    try:
        page_data = notion.pages.retrieve(page_id=page_id); properties = page_data.get("properties", {})
        data = {"id": page_data["id"], "url": page_data.get("url"), "created_time": page_data.get("created_time"), "last_edited_time": page_data.get("last_edited_time")}
        for key, prop_data in properties.items():
            if prop_data["type"] == "title": data[key] = "".join(t["plain_text"] for t in prop_data["title"])
            elif prop_data["type"] == "rich_text": data[key] = "".join(t["plain_text"] for t in prop_data["rich_text"])
            elif prop_data["type"] == "url": data[key] = prop_data["url"]
        blocks_response = notion.blocks.children.list(block_id=page_id); content_blocks = []
        for block in blocks_response.get("results", []):
            if block["type"] == "paragraph": content_blocks.append("".join(rt["plain_text"] for rt in block["paragraph"]["rich_text"]))
        data["full_content_blocks"] = content_blocks; data["content"] = data.get("ContentText", content_blocks[0] if content_blocks else "")
        return {"status": "success", "data": data}
    except APIResponseError as e: return {"status": "error", "message": f"Notion API error retrieving page: {e.body.get('message', str(e))}", "code": f"NOTION_API_{e.code.upper()}", "details": e.body}
    except Exception as e: return {"status": "error", "message": f"Error retrieving Notion page: {str(e)}", "code": "NOTION_GET_ERROR"}

def update_notion_note(page_id: str, content: str = None, title: str = None, **kwargs) -> dict:
    if not notion: return {"status": "error", "message": "Notion client not initialized.", "code": "NOTION_CLIENT_ERROR"}
    properties_to_update = {}
    if title: properties_to_update["Title"] = {"title": [{"text": {"content": title}}]}
    if content: properties_to_update["ContentText"] = {"rich_text": [{"text": {"content": content[:1999]}}]}
    for key, value in kwargs.items():
        if key in ["Source", "Linked Task ID", "Linked Event ID", "TranscriptionText", "Summary", "Key Points"]: properties_to_update[key] = {"rich_text": [{"text": {"content": str(value)[:1999]}}]}
        elif key == "Audio File Link" and value: properties_to_update[key] = {"url": str(value)}
    try:
        args = {"page_id": page_id};
        if properties_to_update: args["properties"] = properties_to_update
        if properties_to_update: response = notion.pages.update(**args)
        return {"status": "success", "data": {"page_id": page_id, "updated_properties": list(properties_to_update.keys())}}
    except APIResponseError as e: return {"status": "error", "message": f"Notion API error updating page: {e.body.get('message', str(e))}", "code": f"NOTION_API_{e.code.upper()}", "details": e.body}
    except Exception as e: return {"status": "error", "message": f"Error updating Notion page: {str(e)}", "code": "NOTION_UPDATE_ERROR"}

def search_notion_notes(query: str, notion_db_id: str = None, source: str = None) -> dict:
    if not notion: return {"status": "error", "message": "Notion client not initialized.", "code": "NOTION_CLIENT_ERROR"}
    db_id_to_use = notion_db_id or NOTION_NOTES_DATABASE_ID_GLOBAL
    if not db_id_to_use: return {"status": "error", "message": "Notion database ID not configured.", "code": "NOTION_CONFIG_ERROR"}
    filter_conditions = []
    if query: filter_conditions.append({"property": "Title", "title": {"contains": query}})
    if source: filter_conditions.append({"property": "Source", "rich_text": {"contains": source}})
    filter_payload = None
    if len(filter_conditions) == 1: filter_payload = filter_conditions[0]
    elif len(filter_conditions) > 1: filter_payload = {"and": filter_conditions}
    try:
        response = notion.databases.query(database_id=db_id_to_use, filter=filter_payload if filter_payload else None); results = []
        for page in response.get("results", []):
            properties = page.get("properties", {}); page_info = {"id": page["id"], "url": page.get("url")}
            for key, prop_data in properties.items():
                if prop_data["type"] == "title": page_info[key] = "".join(t["plain_text"] for t in prop_data["title"])
                elif prop_data["type"] == "rich_text": page_info[key] = "".join(t["plain_text"] for t in prop_data["rich_text"])
            page_info["content"] = page_info.get("ContentText", ""); page_info["linked_task_id"] = page_info.get("Linked Task ID", None); page_info["linked_event_id"] = page_info.get("Linked Event ID", None)
            results.append(page_info)
        return {"status": "success", "data": results}
    except APIResponseError as e: return {"status": "error", "message": f"Notion API error searching: {e.body.get('message', str(e))}", "code": f"NOTION_API_{e.code.upper()}", "details": e.body}
    except Exception as e: return {"status": "error", "message": f"Error searching Notion notes: {str(e)}", "code": "NOTION_SEARCH_ERROR"}

# --- Audio Processing & Summarization ---

async def transcribe_audio_deepgram_stream(
    audio_chunk_iterator, # Must be an async iterator
    deepgram_api_key_param: str = None,
    options: dict = None
) -> dict:
    """Transcribes live audio stream using Deepgram SDK."""
    dg_key_to_use = deepgram_api_key_param or DEEPGRAM_API_KEY_GLOBAL
    if not dg_key_to_use:
        return {"status": "error", "message": "Deepgram API key not configured or provided.", "code": "DEEPGRAM_CONFIG_ERROR"}

    dg_config = DeepgramClientOptions(verbose=0) # Or some logging level from environment
    deepgram = DeepgramClient(dg_key_to_use, dg_config)

    # Default options if none provided
    if options is None:
        options = LiveOptions(
            model="nova-2", language="en-US", punctuate=True, smart_format=True,
            interim_results=False, endpointing="200", # Endpointing helps determine end of speech
            utterance_end_ms="1000"
        )

    dg_connection = deepgram.listen.live.v("1")

    full_transcript_parts = []
    stream_error = None
    connection_opened = asyncio.Event()
    connection_closed = asyncio.Event()
    # transcript_received_event = asyncio.Event() # Could be used for more granular control or timeouts

    def on_open(self, open, **kwargs):
        print("Deepgram connection opened.")
        connection_opened.set()

    def on_message(self, result, **kwargs):
        sentence = result.channel.alternatives[0].transcript
        if len(sentence) == 0: return
        if result.is_final and result.speech_final: # Only final, complete utterances
            full_transcript_parts.append(sentence)
            print(f"DS: Appended final transcript part: {sentence}")
            # transcript_received_event.set()
            # transcript_received_event.clear() # Reset for next potential segment

    def on_metadata(self, metadata, **kwargs): pass # print(f"Deepgram Metadata: {metadata}")
    def on_speech_started(self, speech_started, **kwargs): pass # print("Deepgram Speech Started")
    def on_utterance_end(self, utterance_end, **kwargs): pass # print("Deepgram Utterance Ended")

    def on_error(self, error, **kwargs):
        nonlocal stream_error
        err_msg = f"Deepgram stream error: {error}"
        print(err_msg)
        stream_error = {"message": err_msg, "details": kwargs}
        connection_opened.set() # Unblock start if stuck
        connection_closed.set() # Unblock finish

    def on_close(self, close, **kwargs):
        print("Deepgram connection closed.")
        connection_closed.set()

    dg_connection.on(LiveTranscriptionEvents.Open, on_open)
    dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
    dg_connection.on(LiveTranscriptionEvents.Metadata, on_metadata)
    dg_connection.on(LiveTranscriptionEvents.SpeechStarted, on_speech_started)
    dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, on_utterance_end)
    dg_connection.on(LiveTranscriptionEvents.Error, on_error)
    dg_connection.on(LiveTranscriptionEvents.Close, on_close)

    try:
        if not await dg_connection.start(options): # Returns bool success
            return {"status": "error", "message": "Failed to start Deepgram connection.", "code": "DEEPGRAM_CONNECTION_START_FAILED"}

        await connection_opened.wait() # Wait for on_open
        if stream_error: # Check if error occurred during open
             return {"status": "error", "message": stream_error["message"], "code": "DEEPGRAM_STREAM_ERROR_ON_OPEN", "details": stream_error["details"]}


        # Sender coroutine
        async def sender(dg_conn, audio_iterator):
            try:
                async for chunk in audio_iterator:
                    if chunk: dg_conn.send(chunk)
            except Exception as e:
                nonlocal stream_error
                err_msg = f"Error reading/sending audio chunk: {str(e)}"
                print(err_msg)
                stream_error = {"message": err_msg, "details": str(e)}
            finally:
                print("Audio iterator exhausted, finishing Deepgram connection.")
                await dg_conn.finish() # Signal end of audio stream

        sender_task = asyncio.create_task(sender(dg_connection, audio_chunk_iterator))

        # Wait for sender to complete and connection to close, with timeout
        try:
            await asyncio.wait_for(connection_closed.wait(), timeout=3600.0) # e.g., 1 hour timeout
        except asyncio.TimeoutError:
            nonlocal stream_error
            stream_error = {"message": "Deepgram stream processing timed out.", "details": "Timeout after 1 hour"}
            print(stream_error["message"])
            await dg_connection.finish() # Attempt to close if timed out

        await sender_task # Ensure sender task is complete / exceptions propagated

        if stream_error:
            return {"status": "error", "message": stream_error["message"], "code": "DEEPGRAM_STREAM_ERROR", "details": stream_error.get("details")}

        final_transcript = " ".join(full_transcript_parts).strip()
        return {"status": "success", "data": {"full_transcript": final_transcript}}

    except Exception as e:
        print(f"Outer exception in transcribe_audio_deepgram_stream: {e}")
        return {"status": "error", "message": f"Deepgram stream general error: {str(e)}", "code": "DEEPGRAM_STREAM_GENERAL_ERROR", "details": str(e)}
    finally:
        if dg_connection and dg_connection.is_connected(): # Ensure it's connected before trying to finish
             print("Ensuring Deepgram connection is finished in finally block.")
             await dg_connection.finish()


async def process_live_audio_for_notion(
    platform_module, # Conceptual: needs to provide async iterator `start_audio_capture(meeting_id)`
    meeting_id: str,
    notion_note_title: str,
    deepgram_api_key: str, # Must be passed by handler
    openai_api_key: str,   # Must be passed by handler
    notion_db_id: str = None,
    notion_source: str = "Live Meeting Transcription",
    linked_task_id: str = None,
    linked_event_id: str = None
) -> dict:
    if not notion: return {"status": "error", "message": "Notion client not initialized.", "code": "NOTION_CLIENT_ERROR"}
    if not deepgram_api_key: return {"status": "error", "message": "Deepgram API Key not provided.", "code": "DEEPGRAM_CONFIG_ERROR"}
    if not openai_api_key: return {"status": "error", "message": "OpenAI API Key not provided.", "code": "OPENAI_CONFIG_ERROR"}

    if not hasattr(platform_module, 'start_audio_capture') or not hasattr(platform_module, 'stop_audio_capture'):
        return {"status": "error", "message": "Platform module lacks required audio capture methods.", "code": "PLATFORM_MODULE_INVALID"}

    audio_chunk_iterator = None
    try:
        # This part is conceptual - platform_module must provide an ASYNC iterator
        audio_chunk_iterator = platform_module.start_audio_capture(meeting_id)
        if audio_chunk_iterator is None: # Or if it's not an async iterator
            return {"status": "error", "message": f"Failed to start audio capture for meeting {meeting_id}.", "code": "AUDIO_CAPTURE_FAILED"}

        print(f"Starting live transcription for meeting {meeting_id}...")
        transcription_options = LiveOptions(model="nova-2", language="en-US", punctuate=True, smart_format=True, interim_results=False, endpointing="300", utterance_end_ms="1000")

        transcript_resp = await transcribe_audio_deepgram_stream(
            audio_chunk_iterator,
            deepgram_api_key_param=deepgram_api_key,
            options=transcription_options
        )

    except Exception as e: # Catch errors from start_audio_capture or if it's not async
        return {"status": "error", "message": f"Audio capture setup error: {str(e)}", "code": "AUDIO_CAPTURE_SETUP_ERROR"}
    finally:
        if hasattr(platform_module, 'stop_audio_capture'):
            try: platform_module.stop_audio_capture() # This should ideally be async too if start is
            except Exception as e: print(f"Error stopping audio capture: {str(e)}")

    if transcript_resp["status"] == "error":
        return {"status": "error", "message": "Live transcription failed.", "code": "TRANSCRIPTION_ERROR", "details": transcript_resp.get("message")}

    final_transcript = transcript_resp.get("data", {}).get("full_transcript", "").strip()
    if not final_transcript:
        # If DG returned success but empty transcript, it means no speech or very short audio.
        # Log this, but maybe still create a note.
        print(f"Warning: Live transcript for {meeting_id} was empty.")
        # For now, let's consider it an error if no transcript is produced from a live session.
        return {"status": "error", "message": "No transcript generated from live audio.", "code": "TRANSCRIPTION_EMPTY"}

    summarize_resp = summarize_transcript_gpt(final_transcript, openai_api_key_param=openai_api_key)
    summary, key_points = None, None
    decisions_list = []
    action_items_list = []
    if summarize_resp["status"] == "success":
        summary = summarize_resp["data"].get("summary")
        key_points = summarize_resp["data"].get("key_points") # Backward compatible key_points string
        decisions_list = summarize_resp["data"].get("decisions", [])
        action_items_list = summarize_resp["data"].get("action_items", [])
    else:
        print(f"Warning: Summarization failed for live transcript of {meeting_id}: {summarize_resp['message']}")
        # Proceed to save note even if summarization fails, decisions/action_items will be empty

    create_note_resp = create_notion_note(
        title=notion_note_title,
        content=f"Live meeting notes for: {notion_note_title}", # Main content can be brief
        notion_db_id=notion_db_id,
        source=notion_source,
        linked_task_id=linked_task_id, linked_event_id=linked_event_id,
        transcription=final_transcript, summary=summary, key_points=key_points,
        decisions=decisions_list, action_items=action_items_list
    )

    if create_note_resp["status"] == "error":
        return {"status": "error", "message": "Failed to create Notion note for live transcript.", "code": "NOTION_SAVE_ERROR", "details": create_note_resp.get("message")}

    return {"status": "success", "data": {
        "notion_page_id": create_note_resp["data"]["page_id"],
        "url": create_note_resp["data"]["url"],
        "summary": summary,
        "key_points": key_points,
        "full_transcript": final_transcript, # Added full transcript
        "full_transcript_preview": final_transcript[:200]
    }}


# --- Other pre-existing functions (transcribe_audio_deepgram - for pre-recorded, summarize_transcript_gpt, process_audio_url_for_notion, get_text_embedding_openai) ---
# ... (These functions remain as they were in the last successful 'overwrite_file_with_block' for note_utils.py - Subtask 25 & 27)
# ... For brevity, their full code is not repeated here, but they are assumed to be present and correct.

# New function to fetch and structure Notion page details for NotionPageSummary
def get_notion_page_summary_details(page_id: str, client: Optional[Client] = None) -> dict:
    """
    Fetches and formats Notion page details into a structure compatible with
    the TypeScript NotionPageSummary interface.
    Accepts an optional Notion client instance.
    """
    notion_client_to_use = client or notion # Use passed client or global
    if not notion_client_to_use:
        return {"status": "error", "message": "Notion client not initialized.", "code": "NOTION_CLIENT_ERROR"}

    try:
        page_data = notion_client_to_use.pages.retrieve(page_id=page_id)

        # --- Title Extraction ---
        extracted_title = "Untitled Page" # Default
        properties = page_data.get('properties', {})

        # Common property names for titles in Notion databases
        # Order can be adjusted based on likelihood or specific conventions
        title_prop_names_to_check = ['title', 'Name', 'Page Title', 'Task']

        for prop_name in title_prop_names_to_check:
            title_property = properties.get(prop_name)
            if title_property and title_property.get('type') == 'title' and title_property.get('title'):
                extracted_title = "".join(t.get('plain_text', '') for t in title_property['title']).strip()
                if extracted_title: # Found a non-empty title
                    break

        page_url = page_data.get('url')
        last_edited_time = page_data.get('last_edited_time')
        created_time = page_data.get('created_time')

        # Icon handling: Notion API returns an object for icon or null
        # Example: { "type": "emoji", "emoji": "🎉" } or { "type": "external", "external": { "url": "..." } }
        page_icon_obj = page_data.get('icon')

        # --- Preview Text Generation ---
        preview_text = ""
        MAX_PREVIEW_LENGTH = 300  # Target max characters for the preview
        MAX_BLOCKS_FOR_PREVIEW = 10 # Fetch up to 10 blocks for generating preview

        # Fetch blocks for the page
        blocks_response = notion_client_to_use.blocks.children.list(block_id=page_id, page_size=MAX_BLOCKS_FOR_PREVIEW)

        for block in blocks_response.get('results', []):
            if len(preview_text) >= MAX_PREVIEW_LENGTH:
                break # Stop if preview is already long enough

            block_type = block.get('type')
            current_block_text = ""

            # Extract text from common block types that contain 'rich_text'
            if block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3',
                              'bulleted_list_item', 'numbered_list_item',
                              'to_do', 'quote', 'callout', 'toggle']:
                # The 'rich_text' array is directly under the block_type key (e.g., block['paragraph']['rich_text'])
                rich_text_array = block.get(block_type, {}).get('rich_text', [])
                for rt_item in rich_text_array:
                    if rt_item.get('type') == 'text':
                        current_block_text += rt_item.get('plain_text', '')

            if current_block_text:
                if preview_text: # Add a space if appending to existing preview content
                    preview_text += " "

                # Calculate remaining space for the preview text
                remaining_space = MAX_PREVIEW_LENGTH - len(preview_text)

                if len(current_block_text) > remaining_space:
                    preview_text += current_block_text[:remaining_space - 3] + "..." # Ensure space for ellipsis
                    break # Preview is full
                else:
                    preview_text += current_block_text

        preview_text = preview_text.strip()
        # Final check for truncation if exactly at max length without ellipsis
        if len(preview_text) == MAX_PREVIEW_LENGTH and not preview_text.endswith("..."):
            preview_text = preview_text[:MAX_PREVIEW_LENGTH - 3] + "..."

        # Construct the summary dictionary matching NotionPageSummary
        summary_data = {
            "id": page_id,
            "title": extracted_title if extracted_title else "Untitled Page", # Ensure title is never null
            "url": page_url,
            "last_edited_time": last_edited_time,
            "created_time": created_time,
            "preview_text": preview_text if preview_text else None, # Return None if preview is empty
            "icon": page_icon_obj # This directly matches the structure expected by TS if icon is {type: string, emoji?: string, ...}
        }
        return {"status": "success", "data": summary_data}

    except APIResponseError as e:
        # Log the error for server-side debugging
        # print(f"Notion API Error for page {page_id}: {e}", file=sys.stderr) # Or use proper logging
        error_code_str = e.code.value if hasattr(e.code, 'value') else str(e.code) # Handle if e.code is Enum or str
        return {
            "status": "error",
            "message": f"Notion API error: {e.body.get('message', str(e))}",
            "code": f"NOTION_API_{error_code_str.upper()}",
            "details": e.body
        }
    except Exception as e:
        # print(f"Unexpected error processing page {page_id}: {e}", file=sys.stderr) # Or use proper logging
        return {
            "status": "error",
            "message": f"An unexpected error occurred while fetching Notion page details: {str(e)}",
            "code": "PYTHON_INTERNAL_ERROR_PAGE_SUMMARY",
            "details": str(e)
        }

def transcribe_audio_deepgram(audio_file_path: str, deepgram_api_key_param: str = None) -> dict:
    dg_key_to_use = deepgram_api_key_param or DEEPGRAM_API_KEY_GLOBAL
    if not dg_key_to_use: return {"status": "error", "message": "Deepgram API key not configured or provided.", "code": "DEEPGRAM_CONFIG_ERROR"}
    try: # For pre-recorded, can use a short-lived client instance
        deepgram = DeepgramClient(dg_key_to_use)
        if not audio_file_path or not os.path.exists(audio_file_path): return {"status": "error", "message": f"Audio file not found: {audio_file_path}", "code": "FILE_NOT_FOUND"}
        with open(audio_file_path, "rb") as audio: buffer_data = audio.read()
        payload: FileSource = {"buffer": buffer_data}
        options = PrerecordedOptions(model="nova-2", smart_format=True, utterances=False, punctuate=True)
        response = deepgram.listen.prerecorded.v("1").transcribe_file(payload, options)
        transcript = response.results.channels[0].alternatives[0].transcript if response.results and response.results.channels else ""
        return {"status": "success", "data": {"transcript": transcript}}
    except Exception as e: return {"status": "error", "message": f"Deepgram API error for pre-recorded: {str(e)}", "code": "DEEPGRAM_API_ERROR"}

def create_processed_audio_note_in_notion(
    title: str,
    transcript: str,
    summary_data: dict, # Expects {"summary": str, "decisions": list, "action_items": list}
    notion_db_id: Optional[str] = None,
    source: Optional[str] = "In-Person Agent Audio Note",
    linked_event_id: Optional[str] = None,
    notion_client_param: Optional[Client] = None
) -> dict:
    client = notion_client_param or notion # Use global or passed client
    if not client: return {"status": "error", "message": "Notion client not initialized.", "code": "NOTION_CLIENT_ERROR"}

    # Initialize logger for this function
    logger_func = logging.getLogger(__name__ + ".create_processed_audio_note_in_notion")


    db_id_to_use = notion_db_id or NOTION_NOTES_DATABASE_ID_GLOBAL
    if not db_id_to_use: return {"status": "error", "message": "Notion database ID not configured for notes.", "code": "NOTION_CONFIG_ERROR"}

    properties = {"Title": {"title": [{"text": {"content": title}}]}}
    if source:
        properties["Source"] = {"rich_text": [{"text": {"content": source}}]}
    if linked_event_id:
        properties["Linked Event ID"] = {"rich_text": [{"text": {"content": linked_event_id}}]}

    page_content_blocks = []

    # Summary
    summary = summary_data.get("summary")
    if summary and summary.strip():
        page_content_blocks.append({"type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Summary"}}]}})
        for para in summary.split('\n\n'): # Handle multi-paragraph summaries
            if para.strip():
                 page_content_blocks.append({"type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": para.strip()[:1999]}}]}})
        page_content_blocks.append({"type": "divider", "divider": {}})

    # Decisions
    decisions = summary_data.get("decisions", [])
    if decisions and isinstance(decisions, list) and any(str(d).strip() for d in decisions):
        page_content_blocks.append({"type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Key Decisions"}}]}})
        for decision_item in decisions:
            item_text = str(decision_item).strip()
            if item_text:
                page_content_blocks.append({"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": item_text[:1999]}}]}})
        page_content_blocks.append({"type": "divider", "divider": {}})

    # Action Items
    action_items = summary_data.get("action_items", [])
    if action_items and isinstance(action_items, list) and any(str(ai).strip() for ai in action_items):
        page_content_blocks.append({"type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Action Items"}}]}})
        for action_text in action_items:
            item_text = str(action_text).strip()
            if item_text:
                page_content_blocks.append({"type": "to_do", "to_do": {"rich_text": [{"type": "text", "text": {"content": item_text[:1999]}}], "checked": False }})
        page_content_blocks.append({"type": "divider", "divider": {}})

    # Full Transcript
    transcript_header_text = "Full Transcript"
    transcript_paragraph_blocks = []
    if transcript and transcript.strip():
        for para in transcript.split('\n\n'):
            para_content = para.strip()
            if para_content:
                for i in range(0, len(para_content), 1999): # Max length for paragraph content part
                    transcript_paragraph_blocks.append({"type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": para_content[i:i+1999]}}]}})
    else:
        transcript_paragraph_blocks.append({"type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": "(No transcript available or transcript was empty)"}}]}})

    if len(transcript_paragraph_blocks) > 7 or len(transcript) > 2500 : # Heuristic for toggle
        page_content_blocks.append({
            "type": "toggle",
            "toggle": {
                "rich_text": [{"type": "text", "text": {"content": f"View {transcript_header_text}"}}],
                "children": [ # Children of toggle
                    {"type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": transcript_header_text}}]}},
                    *transcript_paragraph_blocks[:98] # Max children in toggle append for create
                ]
            }
        })
    else:
        page_content_blocks.append({"type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": transcript_header_text}}]}})
        page_content_blocks.extend(transcript_paragraph_blocks)

    try:
        response = client.pages.create(
            parent={"database_id": db_id_to_use},
            properties=properties,
            children=page_content_blocks[:100] # Send the first batch of blocks (up to 100)
        )

        page_id = response["id"]
        page_url = response.get("url")

        # If there are more than 100 blocks, append the rest in batches
        if len(page_content_blocks) > 100:
            logger_func.info(f"Notion note '{title}' has {len(page_content_blocks)} blocks. Appending remaining blocks in batches...")
            for i in range(100, len(page_content_blocks), 100):
                batch_to_append = page_content_blocks[i:i+100]
                try:
                    client.blocks.children.append(
                        block_id=page_id,
                        children=batch_to_append
                    )
                    logger_func.info(f"Successfully appended batch of {len(batch_to_append)} blocks to Notion page '{title}' (ID: {page_id}).")
                except APIResponseError as e_append:
                    logger_func.error(f"Notion API error appending blocks to page {page_id} for '{title}': {e_append.body.get('message', str(e_append))}")
                    # Decide if this should be a fatal error for the whole function
                    # For now, we'll return success for the page creation but log the append error.
                    # The main page is created, but content might be incomplete.
                    # Or, return an error indicating partial success.
                    # Let's add a warning to the success message.
                    return {
                        "status": "warning",
                        "message": f"Page created, but failed to append all content blocks due to API error: {e_append.body.get('message', str(e_append))}",
                        "data": {"page_id": page_id, "url": page_url, "append_error": True},
                        "code": f"NOTION_API_APPEND_{e_append.code.upper()}",
                        "details": e_append.body
                    }
                except Exception as e_append_general:
                    logger_func.error(f"General error appending blocks to page {page_id} for '{title}': {str(e_append_general)}")
                    return {
                        "status": "warning",
                        "message": f"Page created, but failed to append all content blocks due to a general error: {str(e_append_general)}",
                        "data": {"page_id": page_id, "url": page_url, "append_error": True},
                        "code": "NOTION_APPEND_ERROR"
                    }
            logger_func.info(f"All blocks successfully appended for Notion page '{title}' (ID: {page_id}).")

        return {"status": "success", "data": {"page_id": page_id, "url": page_url}}
    except APIResponseError as e:
        logger_func.error(f"Notion API error creating page '{title}': {e.body.get('message', str(e))}")
        return {"status": "error", "message": f"Notion API error: {e.body.get('message', str(e))}", "code": f"NOTION_API_{e.code.upper()}", "details": e.body}
    except Exception as e:
        logger_func.error(f"Error creating Notion processed audio note '{title}': {str(e)}")
        return {"status": "error", "message": f"Error creating Notion processed audio note: {str(e)}", "code": "NOTION_CREATE_ERROR"}


def summarize_transcript_gpt(transcript: str, openai_api_key_param: str = None, gpt_model_param: str = None) -> dict:
    oai_key_to_use = openai_api_key_param or OPENAI_API_KEY_GLOBAL; model_to_use = gpt_model_param or GPT_MODEL_NAME_GLOBAL
    if not oai_key_to_use or not oai_key_to_use.startswith('sk-'): return {"status": "error", "message": "OpenAI API key not set or invalid.", "code": "OPENAI_CONFIG_ERROR"}
    if not transcript or not transcript.strip(): return {"status": "success", "data": {"summary": "Transcript was empty.", "decisions": [], "action_items": [], "key_points": ""}}
    system_prompt = (
        "You are an expert meeting summarizer. Given the meeting transcript, "
        "provide a concise summary, a list of decisions made, and a list of action items. "
        "Respond ONLY with a valid JSON object with three keys: "
        "\"summary\" (string), \"decisions\" (list of strings), and \"action_items\" (list of strings). "
        "Each action item should include potential assignees and deadlines if mentioned. "
        "Example: {\"summary\": \"The meeting was about X...\", \"decisions\": [\"Decision 1 about Y was made.\", \"It was agreed to proceed with Z.\"], \"action_items\": [\"Action: John to complete report by Friday.\", \"Action: Sarah to investigate new tool.\"]}"
    )
    user_prompt = f"Transcript:\n\n{transcript}\n\nPlease provide summary, decisions, and action items in the specified JSON format."
    headers = {"Authorization": f"Bearer {oai_key_to_use}", "Content-Type": "application/json"}
    payload = {"model": model_to_use, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "response_format": {"type": "json_object"}, "temperature": 0.3}
    try:
        response = requests.post(OPENAI_API_ENDPOINT_GLOBAL, headers=headers, json=payload, timeout=120)
        response.raise_for_status(); gpt_response_json = response.json()
        message_content_str = gpt_response_json.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not message_content_str: return {"status": "error", "message": "OpenAI response content empty.", "code": "OPENAI_EMPTY_RESPONSE", "details": gpt_response_json}

        parsed_content = json.loads(message_content_str)

        summary = parsed_content.get("summary", "")
        decisions = parsed_content.get("decisions", [])
        action_items = parsed_content.get("action_items", [])

        if not isinstance(summary, str): summary = "" # Ensure summary is a string
        if not isinstance(decisions, list): decisions = [] # Ensure decisions is a list
        if not isinstance(action_items, list): action_items = [] # Ensure action_items is a list

        # Ensure all items in decisions and action_items are strings
        decisions = [str(item) for item in decisions]
        action_items = [str(item) for item in action_items]

        key_points_str = "\n".join([f"- {item}" for item in action_items if isinstance(item, str)])

        return {
            "status": "success",
            "data": {
                "summary": summary,
                "decisions": decisions,
                "action_items": action_items,
                "key_points": key_points_str # For backward compatibility
            }
        }
    except requests.exceptions.RequestException as e: return {"status": "error", "message": f"OpenAI API request error: {e}", "code": "OPENAI_API_REQUEST_ERROR"}
    except (json.JSONDecodeError, KeyError, ValueError) as e: return {"status": "error", "message": f"Error processing OpenAI response: {e}", "code": "OPENAI_RESPONSE_ERROR", "details": message_content_str if 'message_content_str' in locals() else str(gpt_response_json if 'gpt_response_json' in locals() else "")}
    except Exception as e: return {"status": "error", "message": f"Unexpected error in GPT summarization: {e}", "code": "INTERNAL_ERROR"}

def process_audio_url_for_notion( audio_url: str, title: str, notion_db_id: str = None, notion_source_text: str = "Audio URL Note", linked_task_id: str = None, linked_event_id: str = None, deepgram_api_key: str = None, openai_api_key: str = None ) -> dict:
    if not notion: return {"status": "error", "message": "Notion client not initialized.", "code": "NOTION_CLIENT_ERROR"}
    temp_audio_file = None
    try:
        with requests.get(audio_url, stream=True, timeout=30) as r:
            r.raise_for_status(); temp_audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".tmpaudio")
            for chunk in r.iter_content(chunk_size=8192): temp_audio_file.write(chunk)
            temp_audio_file_path = temp_audio_file.name; temp_audio_file.close()
    except requests.exceptions.RequestException as e:
        if temp_audio_file: os.unlink(temp_audio_file.name)
        return {"status": "error", "message": f"Failed to download audio from URL: {audio_url}. Error: {e}", "code": "AUDIO_DOWNLOAD_ERROR"}
    except Exception as e:
        if temp_audio_file and os.path.exists(temp_audio_file.name): os.unlink(temp_audio_file.name)
        return {"status": "error", "message": f"Error preparing audio file from URL: {str(e)}", "code": "FILE_PREPARATION_ERROR"}
    transcript_resp = transcribe_audio_deepgram(temp_audio_file_path, deepgram_api_key_param=deepgram_api_key)
    os.unlink(temp_audio_file_path)
    if transcript_resp["status"] == "error": return {"status": "error", "message": "Transcription failed for downloaded audio.", "code": "TRANSCRIPTION_ERROR", "details": transcript_resp.get("message")}
    transcript = transcript_resp.get("data", {}).get("transcript", ""); summary, key_points = None, None
    if transcript.strip():
        summarize_resp = summarize_transcript_gpt(transcript, openai_api_key_param=openai_api_key)
        if summarize_resp["status"] == "success": summary = summarize_resp["data"]["summary"]; key_points = summarize_resp["data"]["key_points"]
        else: print(f"Warning: Summarization failed for {audio_url}: {summarize_resp['message']}")
    else: summary = "No speech detected or transcript was empty."; key_points = ""
    create_note_resp = create_notion_note(title=title, content=f"Note from audio URL: {audio_url}", notion_db_id=notion_db_id, source=notion_source_text, linked_task_id=linked_task_id, linked_event_id=linked_event_id, transcription=transcript, summary=summary, key_points=key_points, audio_file_link=audio_url)
    if create_note_resp["status"] == "success": return {"status": "success", "data": {"notion_page_id": create_note_resp["data"]["page_id"], "url": create_note_resp["data"]["url"], "summary": summary, "key_points": key_points, "transcript_preview": transcript[:200]}}
    else: return {"status": "error", "message": "Failed to create Notion note from audio URL.", "code": "NOTION_CREATE_ERROR", "details": create_note_resp.get("message")}

def get_text_embedding_openai(text_to_embed: str, openai_api_key_param: str = None, embedding_model: str = "text-embedding-3-small") -> dict:
    oai_key_to_use = openai_api_key_param or OPENAI_API_KEY_GLOBAL
    if not oai_key_to_use or not oai_key_to_use.startswith('sk-'): return {"status": "error", "message": "OpenAI API key not set or invalid for embedding.", "code": "OPENAI_CONFIG_ERROR"}
    if not text_to_embed or not text_to_embed.strip(): return {"status": "error", "message": "Text to embed cannot be empty.", "code": "VALIDATION_ERROR"}
    try:
        client = openai.OpenAI(api_key=oai_key_to_use)
        response = client.embeddings.create(model=embedding_model, input=text_to_embed.strip())
        embedding_vector = response.data[0].embedding
        return {"status": "success", "data": embedding_vector}
    except openai.APIConnectionError as e: return {"status": "error", "message": f"OpenAI API connection error: {e}", "code": "OPENAI_CONNECTION_ERROR", "details": str(e)}
    except openai.RateLimitError as e: return {"status": "error", "message": f"OpenAI API rate limit exceeded: {e}", "code": "OPENAI_RATE_LIMIT_ERROR", "details": str(e)}
    except openai.APIStatusError as e: return {"status": "error", "message": f"OpenAI API status error (HTTP {e.status_code}): {e.response.text}", "code": f"OPENAI_API_STATUS_{e.status_code}", "details": e.response.text if e.response else str(e)}
    except openai.AuthenticationError as e: # Non-retryable
        return {"status": "error", "message": f"OpenAI API authentication error: {e}", "code": "OPENAI_AUTH_ERROR", "details": str(e)}
    except openai.APIConnectionError as e: # Retryable by caller if wrapped
        return {"status": "error", "message": f"OpenAI API connection error: {e}", "code": "OPENAI_CONNECTION_ERROR", "details": str(e)}
    except openai.RateLimitError as e: # Retryable by caller
        return {"status": "error", "message": f"OpenAI API rate limit exceeded: {e}", "code": "OPENAI_RATE_LIMIT_ERROR", "details": str(e)}
    except openai.APIStatusError as e: # Potentially retryable for 5xx by caller
        return {"status": "error", "message": f"OpenAI API status error (HTTP {e.status_code}): {e.response.text if e.response else str(e)}", "code": f"OPENAI_API_STATUS_{e.status_code}", "details": e.response.text if e.response else str(e)}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error generating OpenAI embedding: {e}", "code": "OPENAI_EMBEDDING_ERROR", "details": str(e)}

# It's better to wrap the call to this function with tenacity in the calling code (e.g., search_routes.py)
# or make this function itself async and use tenacity internally if it were managing its own async operations.
# For now, keeping it synchronous and letting the caller handle retries if needed for this specific function.
# However, for consistency with text_processor.py, let's add tenacity here.
# This function is synchronous, so tenacity will work directly.

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((openai.APIConnectionError, openai.RateLimitError, openai.APIStatusError)) # Retry on these
)
def get_text_embedding_openai_with_retry(text_to_embed: str, openai_api_key_param: str = None, embedding_model: str = "text-embedding-ada-002") -> dict:
    # Default model changed to ada-002
    oai_key_to_use = openai_api_key_param or OPENAI_API_KEY_GLOBAL
    if not oai_key_to_use or not oai_key_to_use.startswith('sk-'):
        # This is a config error, should not be retried.
        return {"status": "error", "message": "OpenAI API key not set or invalid for embedding.", "code": "OPENAI_CONFIG_ERROR"}
    if not text_to_embed or not text_to_embed.strip():
        # Validation error, should not be retried.
        return {"status": "error", "message": "Text to embed cannot be empty.", "code": "VALIDATION_ERROR"}

    try:
        logger = logging.getLogger(__name__) # Ensure logger is available
        attempt_num = getattr(get_text_embedding_openai_with_retry, 'retry', {}).get('statistics', {}).get('attempt_number', 1)
        logger.info(f"Attempt {attempt_num}: Generating OpenAI embedding with model {embedding_model} for text (first 50 chars): '{text_to_embed[:50]}...'")

        client = openai.OpenAI(api_key=oai_key_to_use) # Client re-created per attempt by tenacity if it fails
        response = client.embeddings.create(model=embedding_model, input=text_to_embed.strip())
        embedding_vector = response.data[0].embedding
        return {"status": "success", "data": embedding_vector}
    except openai.AuthenticationError as e:
        # This error should ideally be caught before retry, or tenacity's retry_if_exception_type should exclude it.
        # For now, if it gets here, it will be raised by tenacity and not retried if not in retry_if_exception_type.
        # To prevent retry on this, we can raise it directly to stop tenacity.
        logging.error(f"OpenAI API authentication error (non-retryable): {e}")
        raise # This will stop tenacity retries if AuthenticationError is not in retry_if_exception_type
    except (openai.APIConnectionError, openai.RateLimitError, openai.APIStatusError) as e:
        logging.warning(f"OpenAI API error during embedding (attempt {getattr(get_text_embedding_openai_with_retry, 'retry', {}).get('statistics', {}).get('attempt_number', 1)}): {e}. Tenacity will retry if applicable.")
        raise # Re-raise to let tenacity handle retry
    except Exception as e:
        logging.error(f"Unexpected error generating OpenAI embedding (attempt {getattr(get_text_embedding_openai_with_retry, 'retry', {}).get('statistics', {}).get('attempt_number', 1)}): {e}", exc_info=True)
        # If we want tenacity to retry this too, we'd need to add 'Exception' to retry_if_exception_type,
        # but that's usually too broad. It's better to catch specific retryable exceptions.
        # For now, other exceptions will be raised and not retried by this decorator.
        # We'll return it as an error from the main calling function.
        raise # Let it propagate to be caught by the final try-except in the calling logic if tenacity gives up.

# Original function kept for reference or if non-retry version is needed by other parts.
# The search_routes.py should be updated to call get_text_embedding_openai_with_retry.
# For now, I will modify the original function directly to include tenacity and model change.

def get_text_embedding_openai(text_to_embed: str, openai_api_key_param: str = None, embedding_model: str = "text-embedding-ada-002") -> dict:
    # Default model changed to ada-002
    oai_key_to_use = openai_api_key_param or OPENAI_API_KEY_GLOBAL
    if not oai_key_to_use or not oai_key_to_use.startswith('sk-'):
        return {"status": "error", "message": "OpenAI API key not set or invalid for embedding.", "code": "OPENAI_CONFIG_ERROR"}
    if not text_to_embed or not text_to_embed.strip():
        return {"status": "error", "message": "Text to embed cannot be empty.", "code": "VALIDATION_ERROR"}

    # This is the effective function that will be retried
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((openai.APIConnectionError, openai.RateLimitError, openai.APIStatusError))
        # Retry only on these specific, potentially transient OpenAI errors.
        # openai.APIStatusError can include 5xx, which are good candidates for retries.
        # 4xx errors (like BadRequestError for too long input) will not be retried by this.
    )
    def _get_embedding_core():
        logger_nu = logging.getLogger(__name__) # Local logger instance
        attempt_num = getattr(_get_embedding_core, 'retry', {}).get('statistics', {}).get('attempt_number', 1)
        logger_nu.info(f"OpenAI Embedding Attempt {attempt_num} with model {embedding_model} for text (first 50): '{text_to_embed[:50]}...'")

        client = openai.OpenAI(api_key=oai_key_to_use)
        response = client.embeddings.create(model=embedding_model, input=text_to_embed.strip())
        return response.data[0].embedding

    try:
        embedding_vector = _get_embedding_core()
        return {"status": "success", "data": embedding_vector}
    except openai.AuthenticationError as e: # Explicitly catch non-retryable critical errors
        logging.error(f"OpenAI API authentication error (non-retryable): {e}")
        return {"status": "error", "message": f"OpenAI API authentication error: {e}", "code": "OPENAI_AUTH_ERROR", "details": str(e)}
    except openai.BadRequestError as e: # Example of another non-retryable error (e.g. input too long)
        logging.error(f"OpenAI API BadRequestError (non-retryable): {e}")
        return {"status": "error", "message": f"OpenAI API bad request: {e}", "code": "OPENAI_BAD_REQUEST", "details": str(e)}
    except Exception as e: # Catches errors after tenacity retries are exhausted or other non-decorated errors
        # This will catch APIConnectionError, RateLimitError, APIStatusError if retries fail,
        # or any other unexpected error from _get_embedding_core.
        logging.error(f"Failed to generate OpenAI embedding after retries or due to other error: {e}", exc_info=True)
        # Provide a more generic error message to the caller for final failure
        error_code = "OPENAI_EMBEDDING_ERROR"
        if isinstance(e, openai.RateLimitError): error_code = "OPENAI_RATE_LIMIT_ERROR"
        elif isinstance(e, openai.APIConnectionError): error_code = "OPENAI_CONNECTION_ERROR"
        elif isinstance(e, openai.APIStatusError): error_code = f"OPENAI_API_STATUS_{e.status_code}"

        return {"status": "error", "message": f"Failed to generate OpenAI embedding: {type(e).__name__}", "code": error_code, "details": str(e)}

def embed_and_store_transcript_in_lancedb(
    notion_page_id: str,
    transcript_text: str,
    meeting_title: str,
    meeting_date_iso: Optional[str], # Expect ISO date string or None
    user_id: Optional[str] = None,
    openai_api_key_param: Optional[str] = None, # For OpenAI
    lancedb_uri_param: Optional[str] = None # For LanceDB
) -> dict:
    """
    Generates embedding for the transcript text and stores it in LanceDB
    along with metadata.
    """
    db_path = lancedb_uri_param or os.environ.get("LANCEDB_URI")
    if not db_path:
        return {"status": "error", "message": "LanceDB URI not configured.", "code": "LANCEDB_CONFIG_ERROR"}

    if not notion_page_id or not transcript_text or not meeting_title:
        return {"status": "error", "message": "Missing required fields: notion_page_id, transcript_text, or meeting_title.", "code": "VALIDATION_ERROR"}

    # Handle meeting_date
    parsed_meeting_date: datetime
    if meeting_date_iso:
        try:
            # Attempt to parse ISO format, handling potential 'Z' for UTC
            if meeting_date_iso.endswith("Z"):
                parsed_meeting_date = datetime.fromisoformat(meeting_date_iso[:-1] + "+00:00")
            else:
                parsed_meeting_date = datetime.fromisoformat(meeting_date_iso)
        except ValueError:
            print(f"Warning: Could not parse meeting_date_iso '{meeting_date_iso}'. Defaulting to now.")
            parsed_meeting_date = datetime.now()
    else:
        parsed_meeting_date = datetime.now()
        print("Warning: meeting_date_iso not provided. Defaulting to now.")

    # Generate Text Embedding
    embedding_response = get_text_embedding_openai(
        transcript_text,
        openai_api_key_param=openai_api_key_param
    )

    if embedding_response["status"] == "error":
        return embedding_response # Propagate error from embedding function

    vector_embedding = embedding_response["data"]

    # Store in LanceDB
    store_result = add_transcript_embedding(
        db_path=db_path,
        notion_page_id=notion_page_id,
        meeting_title=meeting_title,
        meeting_date=parsed_meeting_date, # Pass datetime object
        transcript_chunk=transcript_text, # Using full transcript as one chunk for now
        vector_embedding=vector_embedding,
        user_id=user_id
        # table_name defaults to "meeting_transcripts" in add_transcript_embedding
    )

    return store_result
