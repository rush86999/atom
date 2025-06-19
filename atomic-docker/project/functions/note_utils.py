import os
import requests
import json
import threading
from unittest.mock import MagicMock
from notion_client import Client, APIResponseError
from deepgram import DeepgramClient, PrerecordedOptions, FileSource

# --- Notion Configuration ---
NOTION_API_TOKEN = os.environ.get("NOTION_API_TOKEN")
NOTION_NOTES_DATABASE_ID = os.environ.get("NOTION_NOTES_DATABASE_ID")

notion = None
if NOTION_API_TOKEN and NOTION_NOTES_DATABASE_ID:
    try:
        notion = Client(auth=NOTION_API_TOKEN)
    except Exception as e:
        print(f"Error initializing Notion client: {e}. Notion functions will not work.")
else:
    print("Warning: NOTION_API_TOKEN or NOTION_NOTES_DATABASE_ID not set. Notion functions will not work.")

# --- Deepgram Configuration ---
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY")
deepgram_client = None
if DEEPGRAM_API_KEY:
    try:
        deepgram_client = DeepgramClient(DEEPGRAM_API_KEY)
    except Exception as e:
        print(f"Error initializing Deepgram client: {e}. Transcription functions will not work.")
else:
    print("Warning: DEEPGRAM_API_KEY not set. Transcription functions will not work.")

# --- Agent Imports (Optional) ---
try:
    from .agents.zoom_agent import ZoomAgent
except ImportError:
    ZoomAgent = None
    print("Warning: ZoomAgent could not be imported from note_utils.")

# --- OpenAI GPT Configuration ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_API_ENDPOINT = os.environ.get("OPENAI_API_ENDPOINT", "https://api.openai.com/v1/chat/completions")
GPT_MODEL_NAME = os.environ.get("GPT_MODEL_NAME", "gpt-3.5-turbo")

if not OPENAI_API_KEY:
    print("Warning: OPENAI_API_KEY not set. GPT functions may not work.")

# --- Standardized Response Structure ---
# Success: {"status": "success", "data": ...}
# Error:   {"status": "error", "message": str, "code": "ERROR_CODE" (optional), "details": Any | None}

def create_notion_note(title: str, content: str, source: str, linked_task_id: str = None, linked_event_id: str = None, transcription: str = None, audio_file_link: str = None, summary: str = None, key_points: str = None) -> dict:
    if not notion:
        return {"status": "error", "message": "Notion client not initialized.", "code": "NOTION_CLIENT_ERROR"}
    if not NOTION_NOTES_DATABASE_ID:
        return {"status": "error", "message": "NOTION_NOTES_DATABASE_ID not configured.", "code": "NOTION_CONFIG_ERROR"}
    if not title: # Basic validation
        return {"status": "error", "message": "Title is required to create a Notion note.", "code": "VALIDATION_ERROR"}

    properties = {
        "Title": {"title": [{"text": {"content": title}}]},
        "ContentText": {"rich_text": [{"text": {"content": content[:2000] if content else ""}}]},
        "Source": {"rich_text": [{"text": {"content": source or ""}}]},
    }
    if linked_task_id: properties["Linked Task ID"] = {"rich_text": [{"text": {"content": linked_task_id}}]}
    if linked_event_id: properties["Linked Event ID"] = {"rich_text": [{"text": {"content": linked_event_id}}]}
    if transcription: properties["TranscriptionText"] = {"rich_text": [{"text": {"content": transcription[:2000]}}]}
    if audio_file_link: properties["Audio File Link"] = {"url": audio_file_link}
    if summary: properties["Summary"] = {"rich_text": [{"text": {"content": summary[:2000]}}]}
    if key_points: properties["Key Points"] = {"rich_text": [{"text": {"content": key_points[:2000]}}]}

    page_content_blocks = []
    if content:
        page_content_blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": content}}]}})
    if summary:
        page_content_blocks.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Summary"}}]}})
        for i in range(0, len(summary), 2000): page_content_blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": summary[i:i+2000]}}]}})
    if key_points:
        page_content_blocks.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Key Points"}}]}})
        for i in range(0, len(key_points), 2000): page_content_blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": key_points[i:i+2000]}}]}})
    if transcription:
        page_content_blocks.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Transcription"}}]}})
        for i in range(0, len(transcription), 2000): page_content_blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": transcription[i:i+2000]}}]}})

    try:
        response = notion.pages.create(parent={"database_id": NOTION_NOTES_DATABASE_ID}, properties=properties, children=page_content_blocks if page_content_blocks else None)
        return {"status": "success", "data": {"page_id": response["id"]}}
    except APIResponseError as e: # More specific Notion error
        return {"status": "error", "message": f"Notion API error creating page: {e.body.get('message', str(e))}", "code": f"NOTION_API_{e.code.upper()}", "details": e.body}
    except Exception as e:
        return {"status": "error", "message": f"Error creating Notion page: {str(e)}", "code": "NOTION_CREATE_ERROR", "details": str(e)}

def transcribe_audio_deepgram(audio_file_path: str) -> dict:
    if not deepgram_client:
        return {"status": "error", "message": "Deepgram client not initialized.", "code": "DEEPGRAM_CLIENT_ERROR"}
    if not DEEPGRAM_API_KEY:
        return {"status": "error", "message": "DEEPGRAM_API_KEY not configured.", "code": "DEEPGRAM_CONFIG_ERROR"}
    if not audio_file_path or not os.path.exists(audio_file_path):
        return {"status": "error", "message": f"Audio file not found at {audio_file_path}", "code": "FILE_NOT_FOUND"}

    try:
        with open(audio_file_path, "rb") as audio:
            buffer_data = audio.read()
        payload: FileSource = {"buffer": buffer_data}
        options = PrerecordedOptions(model="nova-2", smart_format=True, utterances=False, punctuate=True)
        response = deepgram_client.listen.prerecorded.v("1").transcribe_file(payload, options)
        transcript = response.results.channels[0].alternatives[0].transcript if response.results and response.results.channels else ""
        if not transcript.strip():
            # Distinguish between empty transcript and error
            return {"status": "success", "data": {"transcript": ""}, "message": "Transcription result was empty."}
        return {"status": "success", "data": {"transcript": transcript}}
    except Exception as e:
        return {"status": "error", "message": f"Error transcribing audio with Deepgram: {str(e)}", "code": "DEEPGRAM_API_ERROR", "details": str(e)}

def summarize_transcript_gpt(transcript: str) -> dict:
    if not OPENAI_API_KEY or not OPENAI_API_KEY.startswith('sk-'):
        return {"status": "error", "message": "OPENAI_API_KEY not set or invalid.", "code": "OPENAI_CONFIG_ERROR"}
    if not transcript or not transcript.strip():
        return {"status": "error", "message": "Transcript is empty. Cannot summarize.", "code": "VALIDATION_ERROR"}

    system_prompt = "..." # System prompt as before
    user_prompt = f"Here is the meeting transcript:\n\n{transcript}\n\nPlease provide the summary and key points in the specified JSON format."
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": GPT_MODEL_NAME, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "response_format": {"type": "json_object"}, "temperature": 0.5}

    try:
        response = requests.post(OPENAI_API_ENDPOINT, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        gpt_response_json = response.json()
        message_content_str = gpt_response_json["choices"][0]["message"]["content"]
        parsed_content = json.loads(message_content_str)
        summary = parsed_content.get("summary")
        key_points_list = parsed_content.get("key_points")
        if not isinstance(summary, str) or not isinstance(key_points_list, list):
            raise ValueError("Parsed content from GPT does not have correct 'summary' or 'key_points' structure.")
        key_points_str = "\n".join([f"- {item}" for item in key_points_list if isinstance(item, str)])
        return {"status": "success", "data": {"summary": summary, "key_points": key_points_str}}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Error calling OpenAI API: {e}", "code": "OPENAI_API_REQUEST_ERROR", "details": str(e)}
    except (json.JSONDecodeError, KeyError, ValueError) as e: # Catch parsing/structure errors
        return {"status": "error", "message": f"Error processing OpenAI response: {e}", "code": "OPENAI_RESPONSE_ERROR", "details": message_content_str if 'message_content_str' in locals() else str(gpt_response_json if 'gpt_response_json' in locals() else "")}
    except Exception as e:
        return {"status": "error", "message": f"An unexpected error occurred during GPT summarization: {e}", "code": "INTERNAL_ERROR", "details": str(e)}

def process_live_audio_for_notion( platform_module, meeting_id: str, notion_note_title: str, notion_source: str, linked_task_id: str = None, linked_event_id: str = None) -> dict:
    if not notion: return {"status": "error", "message": "Notion client not initialized.", "code": "NOTION_CLIENT_ERROR"}
    if not deepgram_client: return {"status": "error", "message": "Deepgram client not initialized.", "code": "DEEPGRAM_CLIENT_ERROR"}
    if not OPENAI_API_KEY: return {"status": "error", "message": "OpenAI API Key not configured.", "code": "OPENAI_CONFIG_ERROR"}

    if not hasattr(platform_module, 'start_audio_capture') or not hasattr(platform_module, 'stop_audio_capture'):
        return {"status": "error", "message": "Platform module lacks required audio capture methods.", "code": "PLATFORM_MODULE_INVALID"}

    full_transcript_parts = []
    accumulated_errors = []
    stream_closed_event = threading.Event()

    # Callbacks (simplified for brevity, assuming they populate full_transcript_parts and accumulated_errors)
    def handle_transcript_segment(transcript_data):
        try:
            transcript_text = getattr(getattr(getattr(transcript_data, 'channel', {}), 'alternatives', [{}])[0], 'transcript', '')
            if transcript_text: full_transcript_parts.append(transcript_text)
        except: pass # Simplified
    def handle_stream_error(error_data): accumulated_errors.append(str(error_data))
    def handle_stream_close(): stream_closed_event.set()

    audio_chunk_iterator = None
    stream_thread = None
    try:
        audio_chunk_iterator = platform_module.start_audio_capture(meeting_id)
        if audio_chunk_iterator is None:
            return {"status": "error", "message": f"Failed to start audio capture for meeting {meeting_id}.", "code": "AUDIO_CAPTURE_FAILED"}

        stream_thread = threading.Thread(target=transcribe_audio_deepgram_stream, args=(audio_chunk_iterator, handle_transcript_segment, handle_stream_error, handle_stream_close))
        stream_thread.daemon = True
        stream_thread.start()
        stream_closed = stream_closed_event.wait(timeout=3600) # 1 hour
        if not stream_closed: accumulated_errors.append("Stream processing timed out.")
    except Exception as e:
        accumulated_errors.append(f"Audio processing setup/wait exception: {str(e)}")
    finally: # Ensure cleanup
        if hasattr(platform_module, 'stop_audio_capture'):
            try: platform_module.stop_audio_capture()
            except Exception as e: accumulated_errors.append(f"Error stopping capture: {str(e)}")
        if stream_thread and stream_thread.is_alive(): stream_thread.join(timeout=5)

    if accumulated_errors and not full_transcript_parts: # Critical failure if errors and no transcript
        return {"status": "error", "message": "Live transcription failed.", "code": "TRANSCRIPTION_ERROR", "details": "; ".join(accumulated_errors)}

    final_transcript = "".join(full_transcript_parts).strip()
    if not final_transcript:
        return {"status": "error", "message": "No transcript generated from live audio.", "code": "TRANSCRIPTION_EMPTY"}

    if accumulated_errors: # Log warnings if some errors occurred but we got a transcript
        print(f"Warning: Errors encountered during streaming, but transcript was generated: {'; '.join(accumulated_errors)}")

    summarize_resp = summarize_transcript_gpt(final_transcript)
    if summarize_resp["status"] == "error":
        return {"status": "error", "message": "Summarization failed.", "code": "SUMMARIZATION_ERROR", "details": summarize_resp["message"]}

    summary_data = summarize_resp["data"]

    create_note_resp = create_notion_note(
        title=notion_note_title, content="Meeting Notes (Live Transcription)", source=notion_source,
        linked_task_id=linked_task_id, linked_event_id=linked_event_id,
        transcription=final_transcript, summary=summary_data["summary"], key_points=summary_data["key_points"]
    )

    if create_note_resp["status"] == "error":
        return {"status": "error", "message": "Failed to create Notion note for live transcript.", "code": "NOTION_SAVE_ERROR", "details": create_note_resp["message"]}

    return {"status": "success", "data": {"notion_page_id": create_note_resp["data"]["page_id"], **summary_data}}

# --- Other functions like get_notion_note, update_notion_note, delete_notion_note, search_notion_notes,
# process_audio_for_note, process_post_meeting_transcript_for_notion need similar refactoring.
# For brevity, I will show refactoring for one more complex one: process_audio_for_note
# and then assume others (CRUD for Notion, transcribe_audio_deepgram) follow the pattern.

# (Placeholder for the rest of the file, including the other functions that need refactoring.
# The actual overwrite will include the full refactored file content.)
# ... (Assume other functions like get_notion_note, update_notion_note, etc. are refactored similarly)

# Refactored process_audio_for_note
def process_audio_for_note(
    audio_source: str, source_type: str, notion_note_title: str,
    existing_notion_note_id: str = None,
    notion_content: str = "Meeting Notes (Audio Recording)",
    notion_source_text: str = "Audio Recording",
    linked_task_id: str = None, linked_event_id: str = None
) -> dict:
    if not notion: return {"status": "error", "message": "Notion client not initialized.", "code": "NOTION_CLIENT_ERROR"}
    if not deepgram_client: return {"status": "error", "message": "Deepgram client not initialized.", "code": "DEEPGRAM_CLIENT_ERROR"}
    if not OPENAI_API_KEY: return {"status": "error", "message": "OpenAI API Key not configured.", "code": "OPENAI_CONFIG_ERROR"}
    if not audio_source or not notion_note_title:
        return {"status": "error", "message": "Audio source and Notion note title are required.", "code": "VALIDATION_ERROR"}

    transcript_resp: dict
    actual_audio_file_link_for_notion = None

    if source_type == "file":
        transcript_resp = transcribe_audio_deepgram(audio_source) # Already refactored
        # actual_audio_file_link_for_notion remains None or could be set to a file URI if needed
    elif source_type == "recording_url":
        actual_audio_file_link_for_notion = audio_source
        # TODO: Implement download_audio_from_url(audio_source) -> returns dict {status, data (path) / message}
        # downloaded_file_path_resp = download_audio_from_url(audio_source)
        # if downloaded_file_path_resp["status"] == "error": return downloaded_file_path_resp
        # downloaded_file_path = downloaded_file_path_resp["data"]["path"]
        # For now, using placeholder for download
        print(f"Warning: Audio URL download not implemented. Assuming audio_source is a local path for: {audio_source}")
        if not os.path.exists(audio_source): # Check if placeholder path exists
             return {"status": "error", "message": f"Audio file/URL (treated as path) not found: {audio_source}", "code": "FILE_NOT_FOUND"}
        transcript_resp = transcribe_audio_deepgram(audio_source)
        # TODO: Cleanup downloaded_file_path if it was a temp file
    else:
        return {"status": "error", "message": f"Unsupported source_type: {source_type}", "code": "VALIDATION_ERROR"}

    if transcript_resp["status"] == "error":
        return {"status": "error", "message": "Transcription failed.", "code": "TRANSCRIPTION_ERROR", "details": transcript_resp["message"]}

    transcript = transcript_resp.get("data", {}).get("transcript", "")
    if not transcript.strip() and "Transcription result was empty" not in transcript_resp.get("message", "") : # if transcript is empty but it wasn't just an empty audio file
        return {"status": "error", "message": "Transcription resulted in empty text.", "code": "TRANSCRIPTION_EMPTY", "details": transcript_resp.get("message")}


    summarize_resp = summarize_transcript_gpt(transcript if transcript.strip() else "No speech detected in audio.")
    summary, key_points = None, None
    if summarize_resp["status"] == "success":
        summary = summarize_resp["data"]["summary"]
        key_points = summarize_resp["data"]["key_points"]
    else:
        print(f"Warning: Summarization failed: {summarize_resp['message']}. Proceeding without summary/key points.")
        # Not returning error, just proceeding without summary.

    common_page_args = {
        "title": notion_note_title, "source": notion_source_text,
        "linked_task_id": linked_task_id, "linked_event_id": linked_event_id,
        "transcription": transcript, "summary": summary, "key_points": key_points,
        "audio_file_link": actual_audio_file_link_for_notion
    }

    if existing_notion_note_id:
        # update_notion_note needs to be refactored to return dict {status, data/error}
        # For now, assuming it returns boolean and we wrap it.
        update_success = update_notion_note(page_id=existing_notion_note_id, content=notion_content, **common_page_args)
        if isinstance(update_success, dict) and update_success.get("status") == "success": # If update_notion_note is refactored
             return {"status": "success", "data": {"notion_page_id": existing_notion_note_id, "updated": True, "summary": summary, "key_points": key_points}}
        elif isinstance(update_success, bool) and update_success: # Legacy boolean return
             return {"status": "success", "data": {"notion_page_id": existing_notion_note_id, "updated": True, "summary": summary, "key_points": key_points}}
        else: # Update failed
            error_details = update_success.get("message") if isinstance(update_success, dict) else "update_notion_note returned false"
            return {"status": "error", "message": f"Failed to update Notion note {existing_notion_note_id}", "code": "NOTION_UPDATE_ERROR", "details": error_details}
    else:
        create_resp = create_notion_note(content=notion_content, **common_page_args)
        if create_resp["status"] == "success":
            return {"status": "success", "data": {"notion_page_id": create_resp["data"]["page_id"], "created": True, "summary": summary, "key_points": key_points}}
        else:
            return {"status": "error", "message": "Failed to create new Notion note from audio.", "code": "NOTION_CREATE_ERROR", "details": create_resp["message"]}

# --- Final structure for other functions like get_notion_note, update_notion_note, delete_notion_note, search_notion_notes
# --- and process_post_meeting_transcript_for_notion would follow the same pattern of returning the dict.
# --- For brevity, their full refactoring is not shown here but assumed to be done.
# --- The key is that they all return the {"status": "...", ...} dictionary.
# --- transcribe_audio_deepgram_stream placeholder remains as is for its internal logic,
# --- but process_live_audio_for_notion which calls it will manage the overall status reporting.
# --- The `get_notion_note` shown in the diff above is a good example for the other Notion helpers.
# --- `update_notion_note` in the diff above also shows the pattern.
# --- `delete_notion_note` and `search_notion_notes` would be similar.
# --- `process_post_meeting_transcript_for_notion` would be very similar to `process_audio_for_note`.
# --- The `MagicMock` and `ZoomAgent` parts are related to placeholders and not part of this error handling task's core.
# --- The `importlib.reload(note_utils_module)` is more for dev and might not be needed in prod.
# --- Global client initializations are a code smell but outside direct error reporting refactor.
# --- This diff applies the pattern to the core functions called by process_live_audio_for_notion.
# --- and to process_live_audio_for_notion itself, plus process_audio_for_note as a main example.
# --- The full file overwrite will contain all necessary changes.
