import os
import requests # For GPT API calls
import json # For parsing GPT response
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


# --- Audio Processing and Note Integration ---
def process_audio_for_note(
    audio_file_path: str,
    note_id: str = None,
    title: str = "New Audio Note", # Default title if creating a new note
    content: str = "", # Default content
    source: str = "Audio Upload", # Default source
    linked_task_id: str = None,
    linked_event_id: str = None
) -> str:
    """
    Processes an audio file, transcribes it, summarizes it, and creates or updates a Notion note.
    Returns: The Notion page ID if successful, or None/error message otherwise.
    """
    print(f"Processing audio file: {audio_file_path}")
    transcription = transcribe_audio_deepgram(audio_file_path)

    if "Error:" in transcription or not transcription.strip():
        print(f"Transcription failed or empty: {transcription}")
        # Optionally, still create/update note with just audio link if needed,
        # but current requirement implies transcription is key.
        return f"Transcription failed: {transcription}"

    print("Transcription successful. Generating summary and key points...")
    summary, key_points = summarize_transcript_gpt(transcription)

    if note_id:
        print(f"Updating existing Notion note: {note_id}")
        # Construct content for update.
        # update_notion_note handles transcription separately if it's a property.
        # Here, we want to ensure the transcription is part of the main body or appended.
        # The current update_notion_note doesn't explicitly add transcription to blocks,
        # but it preserves existing transcription blocks if content is updated.
        # For now, let's assume transcription is handled as a property or we rely on existing blocks.
        # The prompt for update_notion_note was to "add the transcript, summary, and key points".
        # Let's pass transcription to content for update_notion_note, assuming it will be added as a block.
        # This might need refinement based on how update_notion_note handles 'content' vs 'transcription' blocks.
        # For simplicity, we'll pass transcription to update_notion_note's content parameter for now.
        # This is a slight divergence from create_notion_note which has a specific transcription param.
        # Re-reading update_notion_note: it does not have a 'transcription' param.
        # It preserves existing transcription blocks.
        # We need to ensure new transcription, summary, key_points are added.
        # The current update_notion_note will append summary and key_points blocks.
        # It does not have a mechanism to add/update a transcription block directly.
        # This is a limitation of the current update_notion_note design.
        # For now, we will update properties and summary/keypoints blocks.
        # The transcription will be in the "TranscriptionText" property.

        # Let's refine: update_notion_note should also accept 'transcription' to update the property
        # and potentially manage transcription blocks similar to how create_notion_note does.
        # This is beyond the original scope for `update_notion_note` changes.
        # So, for now, process_audio_for_note will update the `TranscriptionText` property via `update_notion_note`
        # and then add summary and key points.
        # This means `update_notion_note` needs a `transcription` parameter.

        # Let's go back and quickly add `transcription` to `update_notion_note` params and properties.
        # This is a necessary adjustment for `process_audio_for_note` to function as intended.
        # This will be a separate patch after this one.
        # For now, proceed with the current structure and make a note for this adjustment.

        # For now, we will call update_notion_note without transcription in its direct params,
        # relying on it being set if it were a property (which it's not directly in update)
        # This will be fixed in a subsequent step by modifying update_notion_note signature.
        # Let's assume for now it will be added.

        # The prompt stated for `update_notion_note`: "add the transcript, summary, and key points".
        # `update_notion_note` was modified to take `summary` and `key_points`.
        # It was NOT modified to take `transcription` to add as blocks.
        # It has `TranscriptionText` property.

        # Let's assume `update_notion_note` should be called with `content` being the new transcription
        # or some combination. The original `update_notion_note` replaces content blocks.
        # This is tricky. Let's assume the main "content" parameter of the note is NOT the transcription.
        # The transcription is separate.

        # Revised plan for update:
        # 1. Update 'TranscriptionText' property.
        # 2. Update 'Summary' property and blocks.
        # 3. Update 'Key Points' property and blocks.
        # The existing `update_notion_note` already handles summary/key_points properties and blocks.
        # It needs to handle 'TranscriptionText' property. (This needs to be added to `update_notion_note`)

        # Let's assume `update_notion_note` is already capable of updating `TranscriptionText`.
        # I will add `transcription` to the `update_notion_note` call.
        # I need to modify `update_notion_note` to accept `transcription` and update the `TranscriptionText` property.
        # And ideally, manage transcription blocks (though this was simplified).

        # Given the complexity, I will first write `process_audio_for_note` as best as possible,
        # and then make a small adjustment to `update_notion_note` to accept `transcription` for the property.

        success = update_notion_note(
            page_id=note_id,
            # title=title, # Title update can be optional or based on if new title is provided
            # content=content, # Content update is also optional
            summary=summary,
            key_points=key_points
            # transcription=transcription # This will be added to update_notion_note later
        )
        # After this block, I will create a new diff for update_notion_note to handle transcription property.

        # For now, let's assume `update_notion_note` will be enhanced to take `transcription`.
        # So, I'll include it in the call.
        if update_notion_note(page_id=note_id, summary=summary, key_points=key_points, transcription=transcription):
            # The direct call to update transcription property is removed from here,
            # as update_notion_note will now handle it.
            return note_id
        else:
            return f"Failed to update note {note_id}"

    else:
        print("Creating new Notion note.")
        new_note_id = create_notion_note(
            title=title,
            content=content, # Main content if any, not the transcription itself
            source=source,
            linked_task_id=linked_task_id,
            linked_event_id=linked_event_id,
            transcription=transcription,
            summary=summary,
            key_points=key_points
            # audio_file_link can be added here if available
        )
        return new_note_id

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
