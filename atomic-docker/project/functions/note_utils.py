import os
import requests # For GPT API calls
import json # For parsing GPT response
import threading # For live audio processing
from unittest.mock import MagicMock # For streaming placeholder
from notion_client import Client
from deepgram import DeepgramClient, PrerecordedOptions, FileSource # Added Deepgram imports

# --- Notion Configuration ---
NOTION_API_TOKEN = os.environ.get("NOTION_API_TOKEN")
NOTION_NOTES_DATABASE_ID = os.environ.get("NOTION_NOTES_DATABASE_ID")

# Initialize Notion Client
notion = None
if NOTION_API_TOKEN and NOTION_NOTES_DATABASE_ID:
    try:
        notion = Client(auth=NOTION_API_TOKEN)
        # You could try a small test call here like notion.databases.retrieve(NOTION_NOTES_DATABASE_ID)
        # to ensure the token and DB ID are valid, but be mindful of rate limits and error handling.
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

# TODO: Configure Deepgram client for streaming if different from PrerecordedOptions.

# --- Agent Imports (Optional) ---
try:
    # Assuming 'agents' is a sub-package of 'functions' or accessible in PYTHONPATH
    from .agents.zoom_agent import ZoomAgent
except ImportError:
    # This allows note_utils to be imported elsewhere without the agents package necessarily being present
    # or if there's a circular dependency during certain test setups.
    # For testing ZoomAgent integration specifically, ensure agents.zoom_agent is in the path.
    ZoomAgent = None
    print("Warning: ZoomAgent could not be imported from note_utils. Live Zoom processing might not work if called.")


# --- OpenAI GPT Configuration ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_API_ENDPOINT = os.environ.get("OPENAI_API_ENDPOINT", "https://api.openai.com/v1/chat/completions") # Default endpoint
GPT_MODEL_NAME = os.environ.get("GPT_MODEL_NAME", "gpt-3.5-turbo") # Default model

if not OPENAI_API_KEY:
    print("Warning: OPENAI_API_KEY not set. GPT functions may not work.")


def create_notion_note(title: str, content: str, source: str, linked_task_id: str = None, linked_event_id: str = None, transcription: str = None, audio_file_link: str = None, summary: str = None, key_points: str = None) -> str:
    """
    Creates a new note in the Notion database.
    Returns: The ID of the newly created Notion page, or None if error.
    """
    if not notion:
        print("Error: Notion client not initialized. Cannot create note.")
        return None
    if not NOTION_NOTES_DATABASE_ID: # Should have been caught by client init, but good practice
        print("Error: NOTION_NOTES_DATABASE_ID not configured. Cannot create note.")
        return None

    properties = {
        "Title": {"title": [{"text": {"content": title}}]},
        # Assuming 'Content' is a text property in Notion for the main text body for simplicity of property update.
        # Page content (blocks) will store the longer content.
        "ContentText": {"rich_text": [{"text": {"content": content[:2000]}}]}, # Notion text properties have 2000 char limit
        "Source": {"rich_text": [{"text": {"content": source}}]},
    }
    if linked_task_id:
        properties["Linked Task ID"] = {"rich_text": [{"text": {"content": linked_task_id}}]}
    if linked_event_id:
        properties["Linked Event ID"] = {"rich_text": [{"text": {"content": linked_event_id}}]}
    if transcription:
        # Assuming 'TranscriptionText' for property, page block for full transcription
        properties["TranscriptionText"] = {"rich_text": [{"text": {"content": transcription[:2000]}}]}
    if audio_file_link:
        properties["Audio File Link"] = {"url": audio_file_link}
    if summary:
        properties["Summary"] = {"rich_text": [{"text": {"content": summary[:2000]}}]} # Truncate for property
    if key_points:
        properties["Key Points"] = {"rich_text": [{"text": {"content": key_points[:2000]}}]} # Truncate for property

    page_content_blocks = []
    if content: # Main content block
        page_content_blocks.append({
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": content}}]}
        })

    if summary:
        page_content_blocks.append({
            "object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Summary"}}]}
        })
        for i in range(0, len(summary), 2000): # Split if long
            page_content_blocks.append({
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": summary[i:i+2000]}}]}
            })

    if key_points:
        page_content_blocks.append({
            "object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Key Points"}}]}
        })
        for i in range(0, len(key_points), 2000): # Split if long
            page_content_blocks.append({
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": key_points[i:i+2000]}}]}
            })

    if transcription: # Transcription block (after summary and key points)
        page_content_blocks.append({
            "object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Transcription"}}]}
        })
        # Split transcription into multiple blocks if it's very long (Notion block limit is 2000 chars for rich text)
        for i in range(0, len(transcription), 2000):
            page_content_blocks.append({
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": transcription[i:i+2000]}}]}
            })

    try:
        response = notion.pages.create(
            parent={"database_id": NOTION_NOTES_DATABASE_ID},
            properties=properties,
            children=page_content_blocks if page_content_blocks else None
        )
        return response["id"]
    except Exception as e:
        print(f"Error creating Notion page: {e}")
        return None


def get_notion_note(page_id: str) -> dict:
    """
    Retrieves details of a specific Notion note.
    Returns: A dictionary containing note details, or None if error.
    """
    if not notion:
        print("Error: Notion client not initialized.")
        return None
    try:
        response = notion.pages.retrieve(page_id=page_id)
        properties = response.get("properties", {})

        title = properties.get("Title", {}).get("title", [{}])[0].get("text", {}).get("content", "")

        # Fetch all blocks for content
        content_blocks_response = notion.blocks.children.list(block_id=page_id)
        page_content_list = []
        transcription_content_list = []
        is_transcription_section = False

        for block in content_blocks_response.get("results", []):
            if block.get("type") == "heading_2" and block.get("heading_2", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "") == "Transcription":
                is_transcription_section = True
                continue # Don't add the heading itself to content lists

            if block.get("type") == "paragraph":
                text_content = "".join(rt.get("text", {}).get("content", "") for rt in block.get("paragraph", {}).get("rich_text", []))
                if is_transcription_section:
                    transcription_content_list.append(text_content)
                else:
                    page_content_list.append(text_content)

        full_content = "\n".join(page_content_list)
        full_transcription = "\n".join(transcription_content_list) if transcription_content_list else properties.get("TranscriptionText", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "")


        return {
            "id": response.get("id"),
            "title": title,
            "content": full_content, # Derived from blocks
            "source": properties.get("Source", {}).get("rich_text", [{}])[0].get("text", {}).get("content", ""),
            "linked_task_id": properties.get("Linked Task ID", {}).get("rich_text", [{}])[0].get("text", {}).get("content", ""),
            "linked_event_id": properties.get("Linked Event ID", {}).get("rich_text", [{}])[0].get("text", {}).get("content", ""),
            "transcription": full_transcription, # Derived from blocks or property
            "audio_file_link": properties.get("Audio File Link", {}).get("url", ""),
            "created_time": response.get("created_time"),
            "last_edited_time": response.get("last_edited_time"),
            "archived": response.get("archived", False)
        }
    except Exception as e:
        print(f"Error getting Notion note {page_id}: {e}")
        return None


def update_notion_note(page_id: str, title: str = None, content: str = None, linked_task_id: str = None, linked_event_id: str = None, summary: str = None, key_points: str = None, transcription: str = None) -> bool:
    """
    Updates an existing Notion note. Title, content, linked_task_id, linked_event_id, summary, key_points, or transcription.
    Content update replaces all page content blocks with the new content. Summary, Key Points, and Transcription are handled.
    Returns: True if successful, False otherwise.
    """
    if not notion:
        print("Error: Notion client not initialized.")
        return False

    properties_to_update = {}
    if title:
        properties_to_update["Title"] = {"title": [{"text": {"content": title}}]}
    if content: # Update the ContentText property for quick preview
        properties_to_update["ContentText"] = {"rich_text": [{"text": {"content": content[:2000]}}]}
    if linked_task_id is not None: # Allow unsetting
        properties_to_update["Linked Task ID"] = {"rich_text": [{"text": {"content": linked_task_id or ""}}]}
    if linked_event_id is not None: # Allow unsetting
        properties_to_update["Linked Event ID"] = {"rich_text": [{"text": {"content": linked_event_id or ""}}]}
    if summary:
        properties_to_update["Summary"] = {"rich_text": [{"text": {"content": summary[:2000]}}]}
    if key_points:
        properties_to_update["Key Points"] = {"rich_text": [{"text": {"content": key_points[:2000]}}]}
    if transcription:
        properties_to_update["TranscriptionText"] = {"rich_text": [{"text": {"content": transcription[:2000]}}]} # Update property

    try:
        if properties_to_update:
            notion.pages.update(page_id=page_id, properties=properties_to_update)

        # Handle content update (replaces existing non-transcription blocks)
        if content is not None:
            current_blocks = notion.blocks.children.list(block_id=page_id).get("results", [])
            transcription_heading_id = None
            transcription_blocks_ids_to_keep = []

            # Identify transcription blocks to preserve them
            if content: # Only preserve transcription if new content is not empty
                for idx, block in enumerate(current_blocks):
                    if block.get("type") == "heading_2" and \
                       block.get("heading_2", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "") == "Transcription":
                        transcription_heading_id = block["id"]
                        transcription_blocks_ids_to_keep.append(block["id"])
                        # Assume subsequent blocks are part of transcription until another H2 or end
                        for i in range(idx + 1, len(current_blocks)):
                            if current_blocks[i].get("type") == "heading_2":
                                break
                            transcription_blocks_ids_to_keep.append(current_blocks[i]["id"])
                        break

            # Delete non-transcription blocks
            for block in current_blocks:
                if block["id"] not in transcription_blocks_ids_to_keep:
                    try:
                        notion.blocks.delete(block_id=block['id'])
                    except Exception as e:
                        print(f"Warning: Could not delete block {block['id']}: {e}")


            # Add new content blocks
            if content: # Ensure content is not empty string before adding
                new_content_blocks = []
                for i in range(0, len(content), 2000):
                    new_content_blocks.append({
                        "object": "block", "type": "paragraph",
                        "paragraph": {"rich_text": [{"type": "text", "text": {"content": content[i:i+2000]}}]}
                    })
                if new_content_blocks:
                    # Appending content blocks. These will be added after any preserved transcription blocks if any.
                    # This might not be the ideal order if transcription is meant to be last.
                    # For now, we append. A more sophisticated update would re-order.
                    notion.blocks.children.append(block_id=page_id, children=new_content_blocks)

        # Add Summary and Key Points blocks (appended)
        # For simplicity, these are always appended. No deletion of old summary/key points blocks.
        new_blocks_for_summary_kp = []
        if summary:
            new_blocks_for_summary_kp.append({
                "object": "block", "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Summary"}}]}
            })
            for i in range(0, len(summary), 2000):
                new_blocks_for_summary_kp.append({
                    "object": "block", "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": summary[i:i+2000]}}]}
                })

        if key_points:
            new_blocks_for_summary_kp.append({
                "object": "block", "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Key Points"}}]}
            })
            for i in range(0, len(key_points), 2000):
                new_blocks_for_summary_kp.append({
                    "object": "block", "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": key_points[i:i+2000]}}]}
                })

        if new_blocks_for_summary_kp:
            notion.blocks.children.append(block_id=page_id, children=new_blocks_for_summary_kp)

        return True
    except Exception as e:
        print(f"Error updating Notion note {page_id}: {e}")
        return False


def delete_notion_note(page_id: str) -> bool:
    """
    Deletes (archives) a Notion note.
    Returns: True if successful, False otherwise.
    """
    if not notion:
        print("Error: Notion client not initialized.")
        return False
    try:
        notion.pages.update(page_id=page_id, archived=True)
        return True
    except Exception as e:
        print(f"Error deleting Notion note {page_id}: {e}")
        return False


def search_notion_notes(query: str, date_range: tuple = None, source: str = None, linked_task_id: str = None, linked_event_id: str = None) -> list:
    """
    Searches for Notion notes.
    Returns: A list of note detail dictionaries, or an empty list if error/no results.
    """
    if not notion:
        print("Error: Notion client not initialized.")
        return []

    filter_conditions = []
    if query: # Searches title and ContentText properties
        filter_conditions.append({
            "or": [
                {"property": "Title", "title": {"contains": query}},
                {"property": "ContentText", "rich_text": {"contains": query}},
                {"property": "TranscriptionText", "rich_text": {"contains": query}} # Also search in transcription preview
            ]
        })
    if date_range and len(date_range) == 2:
        start_date, end_date = date_range
        if start_date:
            filter_conditions.append({"timestamp": "created_time", "date": {"on_or_after": start_date}})
        if end_date:
            filter_conditions.append({"timestamp": "created_time", "date": {"on_or_before": end_date}})
    if source:
        filter_conditions.append({"property": "Source", "rich_text": {"contains": source}})
    if linked_task_id:
        filter_conditions.append({"property": "Linked Task ID", "rich_text": {"equals": linked_task_id}})
    if linked_event_id:
        filter_conditions.append({"property": "Linked Event ID", "rich_text": {"equals": linked_event_id}})

    filter_payload = {}
    if len(filter_conditions) == 1:
        filter_payload = filter_conditions[0]
    elif len(filter_conditions) > 1:
        filter_payload = {"and": filter_conditions}

    try:
        response = notion.databases.query(
            database_id=NOTION_NOTES_DATABASE_ID,
            filter=filter_payload if filter_payload else None
        )
        results = []
        for page in response.get("results", []):
            note_details = get_notion_note(page["id"])
            if note_details:
                results.append(note_details)
        return results
    except Exception as e:
        print(f"Error searching Notion notes: {e}")
        return []


# --- Audio File/Recording Processing for Notion ---
def process_audio_for_note(
    audio_source: str, # Can be a file path or a URL
    source_type: str,  # "file" or "recording_url"
    notion_note_title: str,
    # Optional: if an existing Notion note_id is provided, update it.
    # This makes the function more versatile if the target note is already known.
    existing_notion_note_id: str = None,
    notion_content: str = "Meeting Notes (Audio Recording)", # Default content for the note body
    notion_source_text: str = "Audio Recording", # Text for the 'Source' property in Notion
    linked_task_id: str = None,
    linked_event_id: str = None
) -> str:
    """
    Processes a downloaded audio recording (file path or URL), transcribes it,
    summarizes it, and creates or updates a Notion note.
    Returns: The Notion page ID if successful, or an error message string otherwise.
    """

    transcript = None
    actual_audio_file_link_for_notion = None # This will be the original audio_source if it's a URL

    if source_type == "file":
        if not os.path.exists(audio_source):
            print(f"Error: Audio file not found at local path: {audio_source}")
            return f"Error: Audio file not found at {audio_source}"
        print(f"Processing local audio file: {audio_source}")
        transcript = transcribe_audio_deepgram(audio_source)
        # actual_audio_file_link_for_notion could be a file:// URL or None if only local
        # For simplicity, we won't set it for local files unless a public URL is generated.

    elif source_type == "recording_url":
        print(f"Processing audio from recording URL: {audio_source}")
        actual_audio_file_link_for_notion = audio_source # Store the original URL for Notion link
        downloaded_file_path = None
        try:
            # TODO: Implement download_audio_from_url(audio_source)
            # This function would download the file and return its local path.
            # For now, we'll simulate this by assuming the URL might also be a local path for testing,
            # or it's a path that transcribe_audio_deepgram can somehow handle (less likely for remote URLs).
            print(f"Simulating download for URL: {audio_source} (treating as local path for now)")
            downloaded_file_path = audio_source # Placeholder: Assume audio_source can be a local path for now.
                                                # A real implementation would download to a temp path.

            if not os.path.exists(downloaded_file_path):
                # This check is only effective if audio_source was indeed a local path.
                # If it was a URL, this check would likely fail unless the URL is also a valid local file name.
                print(f"Error: Audio file not found at {downloaded_file_path} (after 'download' simulation).")
                return f"Error: Audio file not found at {downloaded_file_path} after download attempt."

            transcript = transcribe_audio_deepgram(downloaded_file_path)

        finally:
            # Clean up the downloaded file if it was actually downloaded to a temporary location
            # and if downloaded_file_path is different from audio_source (i.e., it was a temp file).
            # if downloaded_file_path and downloaded_file_path != audio_source and os.path.exists(downloaded_file_path):
            #     try:
            #         os.remove(downloaded_file_path)
            #         print(f"Cleaned up temporary downloaded file: {downloaded_file_path}")
            #     except Exception as e:
            #         print(f"Error cleaning up temporary file {downloaded_file_path}: {e}")
            pass # Placeholder for cleanup logic

    else:
        print(f"Error: Unsupported source_type: {source_type}. Must be 'file' or 'recording_url'.")
        return f"Error: Unsupported source_type: {source_type}"

    if transcript is None or "Error:" in transcript or not transcript.strip():
        error_message = transcript if transcript else "Transcription failed or resulted in empty text."
        print(error_message)
        return f"Transcription failed: {error_message}"

    print("Transcription successful. Generating summary and key points...")
    summary, key_points = summarize_transcript_gpt(transcript)

    if summary is None and key_points is None:
        print("Warning: Summarization failed for the audio transcript.")
        # Proceed to create/update note without summary/key points, or handle as error

    if existing_notion_note_id:
        print(f"Updating existing Notion note: {existing_notion_note_id}")
        success = update_notion_note(
            page_id=existing_notion_note_id,
            title=notion_note_title, # Optionally update title
            content=notion_content,   # Optionally update main content body
            # source=notion_source_text, # Notion 'Source' property is not typically updated this way, but could be added
            linked_task_id=linked_task_id,
            linked_event_id=linked_event_id,
            transcription=transcript,
            summary=summary,
            key_points=key_points
            # audio_file_link is not directly part of update_notion_note's params.
            # If it needs update, it should be added to update_notion_note or handled separately.
        )
        # Also update the Audio File Link property if it changed or is new
        if success and actual_audio_file_link_for_notion:
            try:
                notion.pages.update(page_id=existing_notion_note_id, properties={"Audio File Link": {"url": actual_audio_file_link_for_notion}})
                print(f"Updated Audio File Link property for note {existing_notion_note_id}")
            except Exception as e:
                print(f"Warning: Failed to update Audio File Link property for note {existing_notion_note_id}: {e}")

        return existing_notion_note_id if success else f"Error: Failed to update Notion note {existing_notion_note_id}"

    else:
        print("Creating new Notion note for audio recording.")
        new_note_id = create_notion_note(
            title=notion_note_title,
            content=notion_content,
            source=notion_source_text,
            linked_task_id=linked_task_id,
            linked_event_id=linked_event_id,
            transcription=transcript,
            summary=summary,
            key_points=key_points,
            audio_file_link=actual_audio_file_link_for_notion
        )
        if new_note_id:
            print(f"New Notion page created from audio recording: {new_note_id}")
            return new_note_id
        else:
            print("Failed to create Notion page from audio recording.")
            return "Error: Failed to create Notion page from audio recording."

# --- Deepgram Transcription Function ---
def transcribe_audio_deepgram(audio_file_path: str) -> str:
    """
    Transcribes an audio file using Deepgram.
    Returns: The transcription text, or an error message string.
    """
    if not deepgram_client:
        return "Error: Deepgram client not initialized."
    if not DEEPGRAM_API_KEY:
        return "Error: DEEPGRAM_API_KEY not configured."
    if not os.path.exists(audio_file_path):
        return f"Error: Audio file not found at {audio_file_path}"

    try:
        with open(audio_file_path, "rb") as audio:
            buffer_data = audio.read()

        payload: FileSource = {"buffer": buffer_data}

        options = PrerecordedOptions(
            model="nova-2",
            smart_format=True,
            utterances=False,
            punctuate=True,
        )
        response = deepgram_client.listen.prerecorded.v("1").transcribe_file(payload, options)

        transcript = ""
        if response.results and response.results.channels and len(response.results.channels) > 0:
            alternatives = response.results.channels[0].alternatives
            if alternatives and len(alternatives) > 0:
                transcript = alternatives[0].transcript

        return transcript if transcript else "Transcription result was empty or not found in response."

    except Exception as e:
        error_message = f"Error transcribing audio with Deepgram: {str(e)}"
        print(error_message)
        return error_message


# --- Deepgram Streaming Transcription (Conceptual Placeholder) ---
def transcribe_audio_deepgram_stream(
    audio_chunk_iterator,
    on_transcript_segment_callback,
    on_stream_error_callback,
    on_stream_close_callback
):
    """
    Conceptual placeholder for transcribing an audio stream using Deepgram.
    This function simulates interaction with a streaming SDK.
    """
    if not deepgram_client:
        err_msg = "Error: Deepgram client not initialized for streaming."
        print(err_msg)
        if on_stream_error_callback:
            on_stream_error_callback({"error": err_msg, "type": "client_initialization"})
        if on_stream_close_callback: # Ensure close is called if stream effectively doesn't open
            on_stream_close_callback()
        return

    if not DEEPGRAM_API_KEY:
        err_msg = "Error: DEEPGRAM_API_KEY not configured for streaming."
        print(err_msg)
        if on_stream_error_callback:
            on_stream_error_callback({"error": err_msg, "type": "api_key_missing"})
        if on_stream_close_callback:
            on_stream_close_callback()
        return

    print("Attempting to start Deepgram streaming connection (simulated).")

    # Conceptual: dg_connection = deepgram_client.listen.live(...)
    # Simulate options that would be passed to such a method
    stream_options = {
        "model": "nova-2",
        "smart_format": True,
        "interim_results": True,
        "punctuate": True,
        "encoding": "linear16", # Example encoding
        "sample_rate": 16000    # Example sample rate
        # Potentially add language, keywords, tagging, etc.
    }
    print(f"Simulated Deepgram stream options: {stream_options}")

    # Simulate event handlers
    # In a real SDK, these would be like:
    # dg_connection.on('open', on_open_handler)
    # dg_connection.on('transcript', on_transcript_handler)
    # dg_connection.on('error', on_error_handler)
    # dg_connection.on('close', on_close_handler)

    # Simulate 'open' event
    print("Simulated Deepgram connection opened.")

    try:
        for i, chunk in enumerate(audio_chunk_iterator):
            if chunk:
                # Simulate sending chunk: dg_connection.send(chunk)
                # print(f"Simulated sending audio chunk {i+1} of size {len(chunk)}")

                # Simulate receiving a transcript segment (interim or final)
                # This part is highly dependent on the actual SDK's behavior and callback structure.
                # For this placeholder, we'll directly call the callback with dummy data.
                # A real implementation would receive this from the SDK's event loop.
                if (i + 1) % 5 == 0: # Simulate a transcript segment every 5 chunks
                    is_final_segment = (i + 1) % 10 == 0 # Simulate some segments being final
                    # Construct a MagicMock that mimics the expected Deepgram transcript object structure
                    # more closely for the attributes accessed by handle_transcript_segment.
                    mock_segment = MagicMock()

                    # Simulate path: transcript_data.channel.alternatives[0].transcript
                    mock_alternative = MagicMock()
                    mock_alternative.transcript = f"Segment { (i+1)//5 } transcript part {'final' if is_final_segment else 'interim'}..."

                    mock_channel = MagicMock()
                    mock_channel.alternatives = [mock_alternative]

                    mock_segment.channel = mock_channel
                    mock_segment.is_final = is_final_segment
                    # Add other attributes if process_live_audio_for_notion's callbacks use them
                    # e.g., speech_final, metadata often found in Deepgram responses.
                    mock_segment.speech_final = is_final_segment
                    mock_segment.metadata = MagicMock(request_id="simulated_req_id")

                    if on_transcript_segment_callback:
                        on_transcript_segment_callback(mock_segment)
            else:
                print("Simulated received empty or null chunk, stopping iteration.")
                break

        # Simulate end of stream signal: dg_connection.finish()
        print("Simulated sending finish signal to Deepgram stream.")

    except Exception as e:
        err_msg = f"Error during simulated audio chunk iteration or sending: {e}"
        print(err_msg)
        if on_stream_error_callback:
            on_stream_error_callback({"error": err_msg, "type": "chunk_processing"})
    finally:
        # Simulate 'close' event
        print("Simulated Deepgram connection closed.")
        if on_stream_close_callback:
            on_stream_close_callback()


# --- Live Audio Processing for Notion ---
def process_live_audio_for_notion(
    platform_module,  # e.g., zoom_agent, teams_agent module
    meeting_id: str,
    notion_note_title: str,
    notion_source: str,
    linked_task_id: str = None,
    linked_event_id: str = None
):
    """
    Processes a live audio stream from a platform module, transcribes it,
    summarizes, and creates a Notion note.
    """
    full_transcript_parts = []
    accumulated_errors = []
    stream_closed_event = threading.Event()

    def handle_transcript_segment(transcript_data):
        try:
            # Accessing attributes via getattr for MagicMock compatibility in placeholder
            transcript_text = getattr(getattr(getattr(transcript_data, 'channel', {}), 'alternatives', [{}])[0], 'transcript', '')
            is_final = getattr(transcript_data, 'is_final', False) # Deepgram specific might be speech_final

            if transcript_text:
                full_transcript_parts.append(transcript_text)
                if is_final: # Or use speech_final depending on Deepgram SDK version for live
                    print(f"Live Interim Transcript (final segment): ... {transcript_text[-100:] if len(transcript_text) > 100 else transcript_text}")
        except Exception as e:
            print(f"Error processing transcript segment: {e} - Data: {transcript_data}")


    def handle_stream_error(error_data):
        err_str = f"Deepgram stream error: {error_data}"
        print(err_str)
        accumulated_errors.append(err_str)

    def handle_stream_close():
        print("Deepgram stream closed.")
        stream_closed_event.set()

    if not hasattr(platform_module, 'start_audio_capture') or not hasattr(platform_module, 'stop_audio_capture'):
        print(f"Error: Provided platform_module does not have required audio capture methods.")
        return None

    audio_chunk_iterator = None
    stream_thread = None

    try:
        print(f"Attempting to start audio capture for meeting: {meeting_id} via {platform_module}")
        audio_chunk_iterator = platform_module.start_audio_capture(meeting_id)

        if audio_chunk_iterator is None:
            print(f"Error: Failed to start audio capture from platform_module for meeting {meeting_id}.")
            return "Error: Audio capture could not be initiated."

        print("Starting Deepgram transcription stream in a new thread.")
        stream_thread = threading.Thread(
            target=transcribe_audio_deepgram_stream,
            args=(audio_chunk_iterator, handle_transcript_segment, handle_stream_error, handle_stream_close)
        )
        stream_thread.daemon = True # Allow main thread to exit even if this one is running
        stream_thread.start()

        print("Waiting for Deepgram stream to close (max 1 hour)...")
        # Wait for the stream to close, or a timeout
        stream_closed = stream_closed_event.wait(timeout=3600) # 1 hour timeout

        if not stream_closed:
            print("Warning: Stream did not close within the timeout period.")
            # Potentially force stop the platform audio capture here if needed
            # and trigger on_stream_close_callback if the stream is still technically open

    except Exception as e:
        print(f"Exception during live audio processing setup or waiting: {e}")
        accumulated_errors.append(str(e))
    finally:
        print("Ensuring platform audio capture is stopped.")
        if hasattr(platform_module, 'stop_audio_capture'):
            try:
                platform_module.stop_audio_capture()
                print("Platform audio capture stopped.")
            except Exception as e:
                print(f"Error stopping platform audio capture: {e}")
                accumulated_errors.append(f"Error stopping platform audio capture: {str(e)}")

        if stream_thread and stream_thread.is_alive():
            print("Waiting for transcription stream thread to join...")
            stream_thread.join(timeout=10) # Wait for the thread to finish
            if stream_thread.is_alive():
                print("Warning: Transcription stream thread did not join in time.")

    if accumulated_errors:
        # Depending on severity, decide if to proceed or return an error
        error_summary = "; ".join(accumulated_errors)
        print(f"Errors accumulated during streaming: {error_summary}")
        # For now, we'll try to process any transcript we got, but log errors.
        # If no transcript, then it's a definite failure.

    final_transcript = "".join(full_transcript_parts).strip()

    if not final_transcript:
        if not accumulated_errors: # No transcript and no specific errors means it just didn't get anything
             print("No transcript was generated from the live audio stream.")
             return "Error: No transcript generated from live audio."
        else: # Errors occurred, and no transcript
            return f"Error: Streaming failed with errors and no transcript: {error_summary}"


    print(f"Final live transcript (first 200 chars): {final_transcript[:200]}")
    print("Summarizing final live transcript...")
    summary, key_points = summarize_transcript_gpt(final_transcript)

    if summary is None and key_points is None:
        print("Warning: Summarization failed for the live transcript.")
        # Proceed to create note without summary/key points, or handle as error

    print("Creating Notion note for live transcript...")
    notion_page_id = create_notion_note(
        title=notion_note_title,
        content="Meeting Notes (Live Transcription)", # Default content preface
        source=notion_source,
        linked_task_id=linked_task_id,
        linked_event_id=linked_event_id,
        transcription=final_transcript,
        summary=summary,
        key_points=key_points
    )

    if notion_page_id:
        print(f"Notion page created for live transcript: {notion_page_id}")
    else:
        print("Failed to create Notion page for live transcript.")
        return "Error: Failed to create Notion page for live transcript."

    return notion_page_id


# --- Post-Meeting Transcript Processing for Notion ---
def process_post_meeting_transcript_for_notion(
    transcript_text: str,
    notion_note_title: str,
    notion_source: str,
    linked_task_id: str = None,
    linked_event_id: str = None,
    audio_file_link: str = None # Link to original audio if available
):
    """
    Processes a provided transcript text, summarizes it, and creates a Notion note.
    """
    if not transcript_text or not transcript_text.strip():
        print("Error: Provided transcript_text is empty or whitespace.")
        return None # Or raise an error, or return an error message string

    print(f"Processing post-meeting transcript (length: {len(transcript_text)} chars).")
    print("Summarizing transcript...")
    summary, key_points = summarize_transcript_gpt(transcript_text)

    if summary is None and key_points is None:
        print("Warning: Summarization failed for the provided transcript.")
        # Decide if to proceed without summary/key_points or return an error
        # For now, proceeding.

    print("Creating Notion note for post-meeting transcript...")
    notion_page_id = create_notion_note(
        title=notion_note_title,
        content="Meeting Notes (Post-Transcript)", # Default content preface
        source=notion_source,
        linked_task_id=linked_task_id,
        linked_event_id=linked_event_id,
        transcription=transcript_text,
        summary=summary,
        key_points=key_points,
        audio_file_link=audio_file_link
    )

    if notion_page_id:
        print(f"Notion page created for post-meeting transcript: {notion_page_id}")
    else:
        print("Failed to create Notion page for post-meeting transcript.")
        # Consider returning a more specific error message if create_notion_note indicates failure type
        return "Error: Failed to create Notion page for post-meeting transcript."

    return notion_page_id

# --- GPT-based Summarization ---

# --- GPT-based Summarization ---
def summarize_transcript_gpt(transcript: str) -> tuple[str | None, str | None]:
    """
    Summarizes a transcript and extracts key points using a GPT model.
    Takes a transcript string and returns a tuple of (summary, key_points).
    Returns (None, None) if an error occurs.
    """
    if not OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY not set. Cannot summarize transcript.")
        return None, None
    if not transcript or not transcript.strip():
        print("Error: Transcript is empty. Cannot summarize.")
        return None, None

    system_prompt = """You are an expert meeting assistant. Your task is to process a meeting transcript and provide a concise summary and a list of key discussion points or action items.
Respond with a JSON object containing two keys: "summary" and "key_points".
The "summary" should be a brief overview of the meeting's main topics and outcomes.
The "key_points" should be a list of strings, each representing a distinct important point, decision, or action item.
For example:
{
  "summary": "The team discussed the Q3 project roadmap, focusing on resource allocation and timeline adjustments. Key decisions were made regarding the marketing strategy.",
  "key_points": [
    "Finalize Q3 resource allocation by end of week.",
    "Adjust project timeline for feature X to accommodate new feedback.",
    "Marketing team to present revised strategy next Monday."
  ]
}"""

    user_prompt = f"Here is the meeting transcript:\n\n{transcript}\n\nPlease provide the summary and key points in the specified JSON format."

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": GPT_MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"}, # Request JSON response
        "temperature": 0.5, # Adjust for desired creativity/factuality
    }

    try:
        print(f"Sending request to GPT model: {GPT_MODEL_NAME} at {OPENAI_API_ENDPOINT}")
        response = requests.post(OPENAI_API_ENDPOINT, headers=headers, json=payload, timeout=60) # Added timeout
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)

        gpt_response_json = response.json()

        if not gpt_response_json.get("choices") or not gpt_response_json["choices"][0].get("message") or not gpt_response_json["choices"][0]["message"].get("content"):
            print(f"Error: Unexpected response structure from GPT API: {gpt_response_json}")
            return None, None

        message_content_str = gpt_response_json["choices"][0]["message"]["content"]

        # The content itself is expected to be a JSON string
        parsed_content = json.loads(message_content_str)

        summary = parsed_content.get("summary")
        key_points_list = parsed_content.get("key_points")

        if not isinstance(summary, str) or not isinstance(key_points_list, list):
            print(f"Error: Parsed content from GPT does not have correct 'summary' (string) or 'key_points' (list) structure: {parsed_content}")
            return None, None

        # Convert key_points list to a single string, e.g., bulleted list
        key_points_str = "\n".join([f"- {item}" for item in key_points_list if isinstance(item, str)])

        print("Successfully received and parsed summary and key points from GPT.")
        return summary, key_points_str

    except requests.exceptions.RequestException as e:
        print(f"Error calling OpenAI API: {e}")
        return None, None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response from GPT or its content: {e}")
        print(f"Raw response content from GPT: {message_content_str if 'message_content_str' in locals() else 'N/A'}")
        return None, None
    except KeyError as e:
        print(f"Error accessing expected keys in GPT response: {e}")
        print(f"GPT Response JSON: {gpt_response_json if 'gpt_response_json' in locals() else 'N/A'}")
        return None, None
    except Exception as e:
        print(f"An unexpected error occurred during GPT summarization: {e}")
        return None, None
