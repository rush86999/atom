import os
import requests
import json
import tempfile # For downloading audio from URL
from notion_client import Client, APIResponseError
from deepgram import DeepgramClient, PrerecordedOptions, FileSource # For Deepgram
import openai # For OpenAI

# --- Global Clients (to be initialized by functions or handlers) ---
notion: Client | None = None
deepgram_client_global: DeepgramClient | None = None # Renamed to avoid conflict if re-initialized

# --- Global Configuration Variables (can be overridden by parameters) ---
# These act as defaults if not provided to functions or if init functions are not called by a handler
NOTION_API_TOKEN_GLOBAL = os.environ.get("NOTION_API_TOKEN")
NOTION_NOTES_DATABASE_ID_GLOBAL = os.environ.get("NOTION_NOTES_DATABASE_ID") # Default DB

DEEPGRAM_API_KEY_GLOBAL = os.environ.get("DEEPGRAM_API_KEY")
OPENAI_API_KEY_GLOBAL = os.environ.get("OPENAI_API_KEY")
GPT_MODEL_NAME_GLOBAL = os.environ.get("GPT_MODEL_NAME", "gpt-3.5-turbo-1106") # gpt-4-turbo-preview for larger context
OPENAI_API_ENDPOINT_GLOBAL = os.environ.get("OPENAI_API_ENDPOINT", "https://api.openai.com/v1/chat/completions")


def init_notion(api_token: str, database_id: str = None) -> dict:
    """Initializes or reinitializes the global Notion client and optionally the default database ID."""
    global notion, NOTION_API_TOKEN_GLOBAL, NOTION_NOTES_DATABASE_ID_GLOBAL
    if not api_token:
        return {"status": "error", "message": "Notion API token is required for initialization.", "code": "CONFIG_ERROR"}

    NOTION_API_TOKEN_GLOBAL = api_token
    if database_id:
        NOTION_NOTES_DATABASE_ID_GLOBAL = database_id

    try:
        notion = Client(auth=NOTION_API_TOKEN_GLOBAL)
        # Verify client works by trying a simple read (optional, but good for immediate feedback)
        # notion.users.me() # Example check
        return {"status": "success", "message": "Notion client initialized successfully."}
    except Exception as e:
        notion = None # Ensure client is None if init fails
        return {"status": "error", "message": f"Failed to initialize Notion client: {str(e)}", "code": "NOTION_CLIENT_INIT_ERROR"}

def init_deepgram(api_key: str) -> dict:
    """Initializes or reinitializes the global Deepgram client."""
    global deepgram_client_global, DEEPGRAM_API_KEY_GLOBAL
    if not api_key:
        return {"status": "error", "message": "Deepgram API key is required for initialization.", "code": "CONFIG_ERROR"}
    DEEPGRAM_API_KEY_GLOBAL = api_key
    try:
        deepgram_client_global = DeepgramClient(DEEPGRAM_API_KEY_GLOBAL)
        return {"status": "success", "message": "Deepgram client initialized successfully."}
    except Exception as e:
        deepgram_client_global = None
        return {"status": "error", "message": f"Failed to initialize Deepgram client: {str(e)}", "code": "DEEPGRAM_CLIENT_INIT_ERROR"}

# --- Notion Functions ---

def create_notion_note(
    title: str, content: str,
    notion_db_id: str = None,
    source: str = None, linked_task_id: str = None, linked_event_id: str = None,
    transcription: str = None, audio_file_link: str = None, summary: str = None, key_points: str = None
) -> dict:
    if not notion: return {"status": "error", "message": "Notion client not initialized.", "code": "NOTION_CLIENT_ERROR"}

    db_id_to_use = notion_db_id or NOTION_NOTES_DATABASE_ID_GLOBAL
    if not db_id_to_use:
        return {"status": "error", "message": "Notion database ID not configured or provided.", "code": "NOTION_CONFIG_ERROR"}
    if not title:
        return {"status": "error", "message": "Title is required to create a Notion note.", "code": "VALIDATION_ERROR"}

    properties = {"Title": {"title": [{"text": {"content": title}}]}}
    # Only add properties if they have a value to avoid Notion API errors for empty rich_text etc.
    if content and len(content.strip()) > 0 : properties["ContentText"] = {"rich_text": [{"text": {"content": content[:1999]}}]} # Notion limit 2000 chars for property
    if source: properties["Source"] = {"rich_text": [{"text": {"content": source}}]}
    if linked_task_id: properties["Linked Task ID"] = {"rich_text": [{"text": {"content": linked_task_id}}]}
    if linked_event_id: properties["Linked Event ID"] = {"rich_text": [{"text": {"content": linked_event_id}}]}
    if transcription and len(transcription.strip()) > 0: properties["TranscriptionText"] = {"rich_text": [{"text": {"content": transcription[:1999]}}]}
    if audio_file_link: properties["Audio File Link"] = {"url": audio_file_link}
    if summary and len(summary.strip()) > 0 : properties["Summary"] = {"rich_text": [{"text": {"content": summary[:1999]}}]}
    if key_points and len(key_points.strip()) > 0: properties["Key Points"] = {"rich_text": [{"text": {"content": key_points[:1999]}}]}

    page_content_blocks = []
    if content: # Main content goes into page blocks for longer text
        for i in range(0, len(content), 2000): page_content_blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": content[i:i+2000]}}]}})
    # Append other long fields as blocks if they weren't truncated into properties or if they exceed property limits
    # This example focuses on content, but similar logic could apply to summary, key_points, transcription for full versions.

    try:
        response = notion.pages.create(parent={"database_id": db_id_to_use}, properties=properties, children=page_content_blocks if page_content_blocks else None)
        return {"status": "success", "data": {"page_id": response["id"], "url": response.get("url")}}
    except APIResponseError as e:
        return {"status": "error", "message": f"Notion API error: {e.body.get('message', str(e))}", "code": f"NOTION_API_{e.code.upper()}", "details": e.body}
    except Exception as e:
        return {"status": "error", "message": f"Error creating Notion page: {str(e)}", "code": "NOTION_CREATE_ERROR"}

def get_notion_note(page_id: str) -> dict:
    if not notion: return {"status": "error", "message": "Notion client not initialized.", "code": "NOTION_CLIENT_ERROR"}
    try:
        page_data = notion.pages.retrieve(page_id=page_id)
        # Extract properties and content in a structured way
        properties = page_data.get("properties", {})
        data = {"id": page_data["id"], "url": page_data.get("url"), "created_time": page_data.get("created_time"), "last_edited_time": page_data.get("last_edited_time")}
        for key, prop_data in properties.items():
            if prop_data["type"] == "title": data[key] = "".join(t["plain_text"] for t in prop_data["title"])
            elif prop_data["type"] == "rich_text": data[key] = "".join(t["plain_text"] for t in prop_data["rich_text"])
            elif prop_data["type"] == "url": data[key] = prop_data["url"]
            # Add other property types as needed

        # Fetch content blocks (simplified example, might need pagination for long content)
        blocks_response = notion.blocks.children.list(block_id=page_id)
        content_blocks = []
        for block in blocks_response.get("results", []):
            if block["type"] == "paragraph": content_blocks.append("".join(rt["plain_text"] for rt in block["paragraph"]["rich_text"]))
        data["full_content_blocks"] = content_blocks
        # For simplicity, using "ContentText" property if it exists for main content, else first paragraph
        data["content"] = data.get("ContentText", content_blocks[0] if content_blocks else "")


        return {"status": "success", "data": data}
    except APIResponseError as e:
        return {"status": "error", "message": f"Notion API error retrieving page: {e.body.get('message', str(e))}", "code": f"NOTION_API_{e.code.upper()}", "details": e.body}
    except Exception as e:
        return {"status": "error", "message": f"Error retrieving Notion page: {str(e)}", "code": "NOTION_GET_ERROR"}

def update_notion_note(page_id: str, content: str = None, title: str = None, **kwargs) -> dict:
    if not notion: return {"status": "error", "message": "Notion client not initialized.", "code": "NOTION_CLIENT_ERROR"}

    properties_to_update = {}
    if title: properties_to_update["Title"] = {"title": [{"text": {"content": title}}]}
    if content: properties_to_update["ContentText"] = {"rich_text": [{"text": {"content": content[:1999]}}]} # Assuming ContentText property exists

    for key, value in kwargs.items(): # Update other properties passed
        # Simple mapping, may need to be more sophisticated based on property type
        if key in ["Source", "Linked Task ID", "Linked Event ID", "TranscriptionText", "Summary", "Key Points"]:
            properties_to_update[key] = {"rich_text": [{"text": {"content": str(value)[:1999]}}]}
        elif key == "Audio File Link" and value:
            properties_to_update[key] = {"url": str(value)}

    children_to_update = []
    if content: # Overwrite main page content blocks if new content is provided
        children_to_update.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": content}}]}})
        # Note: This replaces existing page blocks. For appending, one would need to fetch existing blocks first.

    try:
        args = {"page_id": page_id}
        if properties_to_update: args["properties"] = properties_to_update
        # Updating children (page content blocks) is more complex.
        # The API doesn't allow directly updating properties and children in one call for pages.
        # Typically, you update properties, then manage blocks (add/delete).
        # For simplicity, if content is provided, we'll update the ContentText property.
        # If full block replacement is needed, that's a more involved operation.
        if properties_to_update:
            response = notion.pages.update(**args)
        # If only content blocks need update (and no properties), that's a block operation.
        # This example primarily focuses on property updates.
        return {"status": "success", "data": {"page_id": page_id, "updated_properties": list(properties_to_update.keys())}}
    except APIResponseError as e:
        return {"status": "error", "message": f"Notion API error updating page: {e.body.get('message', str(e))}", "code": f"NOTION_API_{e.code.upper()}", "details": e.body}
    except Exception as e:
        return {"status": "error", "message": f"Error updating Notion page: {str(e)}", "code": "NOTION_UPDATE_ERROR"}


def search_notion_notes(query: str, notion_db_id: str = None, source: str = None) -> dict:
    if not notion: return {"status": "error", "message": "Notion client not initialized.", "code": "NOTION_CLIENT_ERROR"}

    db_id_to_use = notion_db_id or NOTION_NOTES_DATABASE_ID_GLOBAL
    if not db_id_to_use:
        return {"status": "error", "message": "Notion database ID not configured or provided.", "code": "NOTION_CONFIG_ERROR"}

    filter_conditions = []
    if query: # Full text search in Notion
        filter_conditions.append({"property": "Title", "title": {"contains": query}})
        # Or use notion.search(query=query) for workspace-wide search, then filter by parent DB.
        # For database query, filtering is more structured.
        # This example assumes simple title search; Notion's query capabilities are more complex.
        # A compound filter might be needed for searching multiple properties.
    if source:
        filter_conditions.append({"property": "Source", "rich_text": {"contains": source}})

    filter_payload = None
    if len(filter_conditions) == 1: filter_payload = filter_conditions[0]
    elif len(filter_conditions) > 1: filter_payload = {"and": filter_conditions}

    try:
        response = notion.databases.query(database_id=db_id_to_use, filter=filter_payload if filter_payload else None)
        results = []
        for page in response.get("results", []):
            properties = page.get("properties", {})
            page_info = {"id": page["id"], "url": page.get("url")}
            for key, prop_data in properties.items(): # Simplified property extraction
                if prop_data["type"] == "title": page_info[key] = "".join(t["plain_text"] for t in prop_data["title"])
                elif prop_data["type"] == "rich_text": page_info[key] = "".join(t["plain_text"] for t in prop_data["rich_text"])
            # For search, content is usually not returned, only properties.
            # To get content, one would iterate and call get_notion_note or block fetch for each.
            # For now, we'll use ContentText if available as a property.
            page_info["content"] = page_info.get("ContentText", "")
            # Add other relevant properties like 'linked_task_id', 'linked_event_id' if they exist
            page_info["linked_task_id"] = page_info.get("Linked Task ID", None)
            page_info["linked_event_id"] = page_info.get("Linked Event ID", None)


            results.append(page_info)
        return {"status": "success", "data": results}
    except APIResponseError as e:
        return {"status": "error", "message": f"Notion API error searching notes: {e.body.get('message', str(e))}", "code": f"NOTION_API_{e.code.upper()}", "details": e.body}
    except Exception as e:
        return {"status": "error", "message": f"Error searching Notion notes: {str(e)}", "code": "NOTION_SEARCH_ERROR"}

# --- Audio Processing & Summarization ---

def transcribe_audio_deepgram(audio_file_path: str, deepgram_api_key_param: str = None) -> dict:
    dg_key_to_use = deepgram_api_key_param or DEEPGRAM_API_KEY_GLOBAL
    current_dg_client = deepgram_client_global # Use the globally initialized one if available

    if not dg_key_to_use: return {"status": "error", "message": "Deepgram API key not configured or provided.", "code": "DEEPGRAM_CONFIG_ERROR"}
    if not current_dg_client and dg_key_to_use: # Attempt re-init if key provided but client not set
        init_resp = init_deepgram(dg_key_to_use)
        if init_resp["status"] == "error": return init_resp
        current_dg_client = deepgram_client_global # Use the newly initialized client
    if not current_dg_client: return {"status": "error", "message": "Deepgram client not initialized.", "code": "DEEPGRAM_CLIENT_ERROR"}

    if not audio_file_path or not os.path.exists(audio_file_path):
        return {"status": "error", "message": f"Audio file not found: {audio_file_path}", "code": "FILE_NOT_FOUND"}

    try:
        with open(audio_file_path, "rb") as audio: buffer_data = audio.read()
        payload: FileSource = {"buffer": buffer_data}
        options = PrerecordedOptions(model="nova-2", smart_format=True, utterances=False, punctuate=True)
        response = current_dg_client.listen.prerecorded.v("1").transcribe_file(payload, options)
        transcript = response.results.channels[0].alternatives[0].transcript if response.results and response.results.channels else ""
        return {"status": "success", "data": {"transcript": transcript}}
    except Exception as e:
        return {"status": "error", "message": f"Deepgram API error: {str(e)}", "code": "DEEPGRAM_API_ERROR"}

def summarize_transcript_gpt(transcript: str, openai_api_key_param: str = None, gpt_model_param: str = None) -> dict:
    oai_key_to_use = openai_api_key_param or OPENAI_API_KEY_GLOBAL
    model_to_use = gpt_model_param or GPT_MODEL_NAME_GLOBAL

    if not oai_key_to_use or not oai_key_to_use.startswith('sk-'):
        return {"status": "error", "message": "OpenAI API key not set or invalid.", "code": "OPENAI_CONFIG_ERROR"}
    if not transcript or not transcript.strip():
        return {"status": "success", "data": {"summary": "Transcript was empty.", "key_points": ""}} # Not an error, but empty summary

    system_prompt = "You are an expert summarizer. Given the meeting transcript, provide a concise summary and a list of key bullet points. Respond ONLY with a valid JSON object with two keys: \"summary\" (string) and \"key_points\" (list of strings). For example: {\"summary\": \"The meeting was about X...\", \"key_points\": [\"Point 1 about Y\", \"Point 2 about Z\"]}"
    user_prompt = f"Here is the meeting transcript:\n\n{transcript}\n\nPlease provide the summary and key points in the specified JSON format."
    headers = {"Authorization": f"Bearer {oai_key_to_use}", "Content-Type": "application/json"}
    payload = {"model": model_to_use, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "response_format": {"type": "json_object"}, "temperature": 0.3}

    try:
        response = requests.post(OPENAI_API_ENDPOINT_GLOBAL, headers=headers, json=payload, timeout=120) # Increased timeout
        response.raise_for_status()
        gpt_response_json = response.json()
        message_content_str = gpt_response_json.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not message_content_str:
            return {"status": "error", "message": "OpenAI response content is empty.", "code": "OPENAI_EMPTY_RESPONSE", "details": gpt_response_json}

        parsed_content = json.loads(message_content_str)
        summary = parsed_content.get("summary")
        key_points_list = parsed_content.get("key_points")
        if not isinstance(summary, str) or not isinstance(key_points_list, list):
            raise ValueError("Parsed content from GPT does not have correct 'summary' or 'key_points' structure.")
        key_points_str = "\n".join([f"- {item}" for item in key_points_list if isinstance(item, str)])
        return {"status": "success", "data": {"summary": summary, "key_points": key_points_str}}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"OpenAI API request error: {e}", "code": "OPENAI_API_REQUEST_ERROR"}
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        return {"status": "error", "message": f"Error processing OpenAI response: {e}", "code": "OPENAI_RESPONSE_ERROR", "details": message_content_str if 'message_content_str' in locals() else str(gpt_response_json if 'gpt_response_json' in locals() else "")}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error during GPT summarization: {e}", "code": "INTERNAL_ERROR"}

def process_audio_url_for_notion(
    audio_url: str, title: str,
    notion_db_id: str = None, notion_source_text: str = "Audio URL Note",
    linked_task_id: str = None, linked_event_id: str = None,
    deepgram_api_key: str = None, openai_api_key: str = None
) -> dict:
    if not notion: return {"status": "error", "message": "Notion client not initialized.", "code": "NOTION_CLIENT_ERROR"}
    # API keys for Deepgram/OpenAI will be checked by their respective functions if not passed here

    # 1. Download audio from URL
    temp_audio_file = None
    try:
        with requests.get(audio_url, stream=True, timeout=30) as r:
            r.raise_for_status()
            # Create a temporary file to store the audio
            temp_audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".tmpaudio") # Ensure suffix if needed by Deepgram
            for chunk in r.iter_content(chunk_size=8192):
                temp_audio_file.write(chunk)
            temp_audio_file_path = temp_audio_file.name
            temp_audio_file.close() # Close it so Deepgram can open
    except requests.exceptions.RequestException as e:
        if temp_audio_file: os.unlink(temp_audio_file.name) # Clean up if download failed
        return {"status": "error", "message": f"Failed to download audio from URL: {audio_url}. Error: {e}", "code": "AUDIO_DOWNLOAD_ERROR"}
    except Exception as e: # Other errors during download/temp file creation
        if temp_audio_file and os.path.exists(temp_audio_file.name): os.unlink(temp_audio_file.name)
        return {"status": "error", "message": f"Error preparing audio file from URL: {str(e)}", "code": "FILE_PREPARATION_ERROR"}

    # 2. Transcribe
    transcript_resp = transcribe_audio_deepgram(temp_audio_file_path, deepgram_api_key_param=deepgram_api_key)
    os.unlink(temp_audio_file_path) # Clean up temp file after transcription

    if transcript_resp["status"] == "error":
        return {"status": "error", "message": "Transcription failed for downloaded audio.", "code": "TRANSCRIPTION_ERROR", "details": transcript_resp.get("message")}
    transcript = transcript_resp.get("data", {}).get("transcript", "")

    # 3. Summarize
    summary, key_points = None, None
    if transcript.strip(): # Only summarize if transcript is not empty
        summarize_resp = summarize_transcript_gpt(transcript, openai_api_key_param=openai_api_key)
        if summarize_resp["status"] == "success":
            summary = summarize_resp["data"]["summary"]
            key_points = summarize_resp["data"]["key_points"]
        else:
            print(f"Warning: Summarization failed for transcript from {audio_url}: {summarize_resp['message']}")
    else: # Transcript was empty
        summary = "No speech detected or transcript was empty."
        key_points = ""

    # 4. Create Notion Note
    create_note_resp = create_notion_note(
        title=title, content=f"Note created from audio URL: {audio_url}",
        notion_db_id=notion_db_id, source=notion_source_text,
        linked_task_id=linked_task_id, linked_event_id=linked_event_id,
        transcription=transcript, summary=summary, key_points=key_points,
        audio_file_link=audio_url # Link to the original audio URL
    )

    if create_note_resp["status"] == "success":
        return {"status": "success", "data": {"notion_page_id": create_note_resp["data"]["page_id"], "url": create_note_resp["data"]["url"], "summary": summary, "key_points": key_points}}
    else:
        return {"status": "error", "message": "Failed to create Notion note from audio URL.", "code": "NOTION_CREATE_ERROR", "details": create_note_resp.get("message")}

# Placeholder for transcribe_audio_deepgram_stream and process_live_audio_for_notion
# These are more complex and involve live streaming, which is a different pattern than the Flask handlers for discrete files/URLs.
# For the purpose of this Flask API service, process_audio_url_for_notion is the key one for pre-recorded audio.
# process_live_audio_for_notion would typically be triggered differently (e.g., from a websocket handler or a specific agent).

# --- Text Embedding Function ---
def get_text_embedding_openai(text_to_embed: str, openai_api_key_param: str = None, embedding_model: str = "text-embedding-3-small") -> dict:
    """
    Generates a vector embedding for the given text using OpenAI.

    Args:
        text_to_embed: The text to embed.
        openai_api_key_param: Optional OpenAI API key. If not provided, uses global OPENAI_API_KEY_GLOBAL.
        embedding_model: The OpenAI embedding model to use.

    Returns:
        A dictionary with 'status' ('success' or 'error') and 'data' (the embedding vector) or 'message'/'details'.
    """
    oai_key_to_use = openai_api_key_param or OPENAI_API_KEY_GLOBAL
    if not oai_key_to_use or not oai_key_to_use.startswith('sk-'):
        return {"status": "error", "message": "OpenAI API key not set or invalid for embedding.", "code": "OPENAI_CONFIG_ERROR"}
    if not text_to_embed or not text_to_embed.strip():
        return {"status": "error", "message": "Text to embed cannot be empty.", "code": "VALIDATION_ERROR"}

    try:
        # Ensure the client is initialized with the correct key.
        # If a global client exists, it might be using a different key.
        # For simplicity in this function, create a new client instance if a specific key is passed,
        # or rely on a global client if no key is passed (assuming global client is already configured).
        # A more robust solution might involve an OpenAI client manager or passing client instances.
        client = openai.OpenAI(api_key=oai_key_to_use)

        response = client.embeddings.create(
            model=embedding_model,
            input=text_to_embed.strip() # Ensure no leading/trailing whitespace affects embedding
        )

        embedding_vector = response.data[0].embedding
        return {"status": "success", "data": embedding_vector}

    except openai.APIConnectionError as e: # Handle connection errors
        return {"status": "error", "message": f"OpenAI API connection error: {e}", "code": "OPENAI_CONNECTION_ERROR", "details": str(e)}
    except openai.RateLimitError as e: # Handle rate limit errors
        return {"status": "error", "message": f"OpenAI API rate limit exceeded: {e}", "code": "OPENAI_RATE_LIMIT_ERROR", "details": str(e)}
    except openai.APIStatusError as e: # Handle API errors with status codes
        return {"status": "error", "message": f"OpenAI API status error (HTTP {e.status_code}): {e.response.text}", "code": f"OPENAI_API_STATUS_{e.status_code}", "details": e.response.text if e.response else str(e)}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error generating OpenAI embedding: {e}", "code": "OPENAI_EMBEDDING_ERROR", "details": str(e)}

[end of atomic-docker/project/functions/note_utils.py]
