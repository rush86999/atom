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

    return {"status": "success", "data": {"notion_page_id": create_note_resp["data"]["page_id"], "url": create_note_resp["data"]["url"], "summary": summary, "key_points": key_points, "full_transcript_preview": final_transcript[:200]}}


# --- Other pre-existing functions (transcribe_audio_deepgram - for pre-recorded, summarize_transcript_gpt, process_audio_url_for_notion, get_text_embedding_openai) ---
# ... (These functions remain as they were in the last successful 'overwrite_file_with_block' for note_utils.py - Subtask 25 & 27)
# ... For brevity, their full code is not repeated here, but they are assumed to be present and correct.
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
    except Exception as e: return {"status": "error", "message": f"Unexpected error generating OpenAI embedding: {e}", "code": "OPENAI_EMBEDDING_ERROR", "details": str(e)}

[end of atomic-docker/project/functions/note_utils.py]
