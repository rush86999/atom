# Imports assume PYTHONPATH="/app" is set in Docker environment,
# and the 'project' directory is directly under /app.
from project.functions import note_utils

# Example Params:
# handle_create_text_note_params = {'title': 'My Note', 'content': 'This is a test note.', 'source': 'manual'}
# handle_create_audio_note_params = {'audio_file_path': '/path/to/audio.mp3', 'title': 'Audio Note', 'source': 'audio', 'content': 'Optional initial content for audio note'}
# handle_get_note_params = {'page_id': 'some-notion-page-id'}
# handle_update_note_params = {'page_id': 'some-notion-page-id', 'title': 'Updated Title', 'content': 'Updated content.'}
# handle_delete_note_params = {'page_id': 'some-notion-page-id'}
# handle_search_notes_params = {'query': 'meeting notes', 'source': 'manual'}
# handle_link_note_params = {'page_id': 'some-notion-page-id', 'linked_task_id': 'task-123', 'linked_event_id': None} # Can explicitly unset a link

def handle_create_text_note(params: dict) -> dict:
    """
    Handles the creation of a text-based note.
    Expected params: title, content, source, [linked_task_id], [linked_event_id]
    """
    try:
        page_id = note_utils.create_notion_note(
            title=params.get("title", "Untitled Note"),
            content=params.get("content", ""),
            source=params.get("source", "manual"), # Default source to manual
            linked_task_id=params.get("linked_task_id"),
            linked_event_id=params.get("linked_event_id")
        )
        if page_id:
            return {"status": "success", "page_id": page_id, "message": "Text note created successfully."}
        else:
            return {"status": "error", "message": "Failed to create text note in Notion."}
    except Exception as e:
        return {"status": "error", "message": f"Error in handle_create_text_note: {str(e)}"}


def handle_create_audio_note(params: dict) -> dict:
    """
    Handles the creation of a note from an audio file using Deepgram for transcription.
    Expected params: audio_file_path, title, source, [content (initial)], [linked_task_id], [linked_event_id]
    """
    try:
        audio_file_path = params["audio_file_path"]
        transcription_result = note_utils.transcribe_audio_deepgram(audio_file_path)

        if transcription_result.startswith("Error:"):
             return {"status": "error", "message": f"Transcription failed: {transcription_result}"}

        initial_content = params.get("content", "") # Optional initial content from user

        page_id = note_utils.create_notion_note(
            title=params.get("title", "Audio Note"),
            content=initial_content, # User's initial content, if any
            source=params.get("source", "audio"), # Default source to audio
            transcription=transcription_result,
            # audio_file_link will be None for now as per requirements
            linked_task_id=params.get("linked_task_id"),
            linked_event_id=params.get("linked_event_id")
        )
        if page_id:
            return {"status": "success", "page_id": page_id, "transcription": transcription_result, "message": "Audio note created successfully with transcription."}
        else:
            return {"status": "error", "message": "Failed to create audio note in Notion after transcription."}
    except KeyError as e:
        return {"status": "error", "message": f"Missing required parameter for audio note: {e}"}
    except Exception as e:
        return {"status": "error", "message": f"Error in handle_create_audio_note: {str(e)}"}


def handle_get_note(params: dict) -> dict:
    """
    Handles retrieving a specific note.
    Expected params: page_id
    """
    try:
        page_id = params["page_id"]
        note_details = note_utils.get_notion_note(page_id=page_id)
        if note_details:
            return {"status": "success", "note": note_details}
        elif note_details is None and note_utils.notion is None: # Check if client failed init
             return {"status": "error", "message": "Notion client not initialized. Cannot get note."}
        else: # Note genuinely not found or other retrieval error
            return {"status": "error", "message": f"Note with page_id '{page_id}' not found or error retrieving."}
    except KeyError as e:
        return {"status": "error", "message": f"Missing parameter: {e}"}
    except Exception as e:
        return {"status": "error", "message": f"Error in handle_get_note: {str(e)}"}


def handle_update_note(params: dict) -> dict:
    """
    Handles updating an existing note.
    Expected params: page_id, [title], [content], [linked_task_id], [linked_event_id]
    """
    try:
        page_id = params["page_id"]
        success = note_utils.update_notion_note(
            page_id=page_id,
            title=params.get("title"), # Pass None if not provided, note_utils handles it
            content=params.get("content"), # Pass None if not provided
            linked_task_id=params.get("linked_task_id"), # Pass None if not provided explicitly
            linked_event_id=params.get("linked_event_id") # Pass None if not provided explicitly
        )
        if success:
            return {"status": "success", "message": "Note updated successfully."}
        else:
            return {"status": "error", "message": "Failed to update note (see server logs for details)."}
    except KeyError as e:
        return {"status": "error", "message": f"Missing page_id parameter: {e}"}
    except Exception as e:
        return {"status": "error", "message": f"Error in handle_update_note: {str(e)}"}


def handle_delete_note(params: dict) -> dict:
    """
    Handles deleting a note.
    Expected params: page_id
    """
    try:
        page_id = params["page_id"]
        success = note_utils.delete_notion_note(page_id=page_id)
        if success:
            return {"status": "success", "message": "Note deleted (archived) successfully."}
        else:
            return {"status": "error", "message": "Failed to delete note."}
    except KeyError as e:
        return {"status": "error", "message": f"Missing parameter: {e}"}
    except Exception as e:
        return {"status": "error", "message": f"Error in handle_delete_note: {str(e)}"}


def handle_search_notes(params: dict) -> dict:
    """
    Handles searching for notes.
    Expected params: [query], [date_range (tuple: start, end)], [source], [linked_task_id], [linked_event_id]
    """
    try:
        notes = note_utils.search_notion_notes(
            query=params.get("query", ""), # Default to empty query if not provided
            date_range=params.get("date_range"),
            source=params.get("source"),
            linked_task_id=params.get("linked_task_id"),
            linked_event_id=params.get("linked_event_id")
        )
        return {"status": "success", "notes": notes, "count": len(notes)}
    except Exception as e:
        return {"status": "error", "message": f"Error in handle_search_notes: {str(e)}"}


def handle_link_note(params: dict) -> dict:
    """
    Handles linking a note to a task or event by updating its properties.
    This is essentially a specialized call to update_notion_note.
    Expected params: page_id, [linked_task_id], [linked_event_id]
    To unset a link, pass an empty string for that link ID, e.g. linked_task_id=""
    """
    try:
        page_id = params["page_id"]
        if "linked_task_id" not in params and "linked_event_id" not in params:
            return {"status": "info", "message": "No link information (linked_task_id or linked_event_id) provided to update."}

        success = note_utils.update_notion_note(
            page_id=page_id,
            linked_task_id=params.get("linked_task_id"),
            linked_event_id=params.get("linked_event_id")
        )

        if success:
            return {"status": "success", "message": "Note links updated successfully."}
        else:
            return {"status": "error", "message": "Failed to update note links (see server logs for details)."}

    except KeyError as e:
        return {"status": "error", "message": f"Missing page_id parameter for linking: {e}"}
    except Exception as e:
        return {"status": "error", "message": f"Error in handle_link_note: {str(e)}"}
