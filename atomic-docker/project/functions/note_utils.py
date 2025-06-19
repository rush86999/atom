import os
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


def create_notion_note(title: str, content: str, source: str, linked_task_id: str = None, linked_event_id: str = None, transcription: str = None, audio_file_link: str = None) -> str:
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

    page_content_blocks = []
    if content: # Main content block
        page_content_blocks.append({
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": content}}]}
        })
    if transcription: # Transcription block
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


def update_notion_note(page_id: str, title: str = None, content: str = None, linked_task_id: str = None, linked_event_id: str = None) -> bool:
    """
    Updates an existing Notion note. Title, content, linked_task_id, or linked_event_id.
    Content update replaces all page content blocks with the new content.
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

    try:
        if properties_to_update:
            notion.pages.update(page_id=page_id, properties=properties_to_update)

        if content is not None: # If content is being explicitly updated, replace page blocks
            # Delete existing blocks
            current_blocks = notion.blocks.children.list(block_id=page_id).get("results", [])
            # Filter out transcription blocks to preserve them, unless new content is empty (then delete all)
            transcription_heading_id = None
            transcription_blocks_ids_to_keep = []

            if content: # Only preserve transcription if new content is not empty
                for block in current_blocks:
                    if block.get("type") == "heading_2" and block.get("heading_2", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "") == "Transcription":
                        transcription_heading_id = block["id"]
                        transcription_blocks_ids_to_keep.append(block["id"]) # Keep heading
                        # Assume subsequent blocks are transcription until next heading or end
                        start_index = current_blocks.index(block) + 1
                        for i in range(start_index, len(current_blocks)):
                            if current_blocks[i].get("type") == "heading_2": # Stop if another heading
                                break
                            transcription_blocks_ids_to_keep.append(current_blocks[i]["id"])
                        break

            for block in current_blocks:
                if block["id"] not in transcription_blocks_ids_to_keep:
                    notion.blocks.delete(block_id=block['id'])

            # Add new content blocks (inserted before transcription if it exists)
            new_content_blocks = []
            for i in range(0, len(content), 2000):
                new_content_blocks.append({
                    "object": "block", "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": content[i:i+2000]}}]}
                })

            if new_content_blocks:
                if transcription_heading_id: # Insert before transcription heading
                    # This logic for 'after' might need refinement based on block ordering behavior
                    # For simplicity, appending after all current content blocks might be safer if preserving transcription isn't critical for content update
                    # Or, if transcription is always last, just append new content blocks before it.
                    # The Notion API for block ordering can be tricky.
                    # A simpler approach: delete all non-transcription blocks, then append new content, then re-append transcription if it was preserved.
                    # For now, this simplified 'after' might not place it correctly if other blocks exist before transcription.
                    # Safest if new content replaces ALL old content, and transcription is re-added if necessary.
                    # The current code deletes non-transcription, then adds new content. Where it adds depends on Notion's append behavior.
                    # It will likely append at the end of any remaining (transcription) blocks.
                    # To ensure it's *before* transcription, one might need to fetch all blocks,
                    # build the new list of blocks in desired order, delete all, and re-add all.
                    # This is complex. The current approach is a simplification.
                    notion.blocks.children.append(block_id=page_id, children=new_content_blocks) # Appends to the end
                else: # Append to end if no transcription or if it was deleted
                    notion.blocks.children.append(block_id=page_id, children=new_content_blocks)
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
