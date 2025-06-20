import lancedb
from lancedb.pydantic import LanceModel, vector
from lancedb.embeddings import get_registry
from typing import List, Optional
from datetime import datetime
import hashlib
import os

# --- LanceDB Schema Definition ---
class LanceDBNoteSchema(LanceModel):
    note_id: str  # Primary Notion page ID
    user_id: Optional[str] = None # Allow user_id to be optional if not always available
    text_content_hash: str  # SHA256 hash of the text content used for vectorization
    # Vector dimension for OpenAI text-embedding-3-small is 1536
    # For text-embedding-ada-002 it's also 1536. text-embedding-3-large is 3072.
    # Let's assume text-embedding-3-small or ada-002.
    vector: List[float] = vector(1536)
    created_at: datetime
    updated_at: datetime

    # LanceDB requires a unique ID for merging/deleting.
    # We can use note_id as a primary reference, but LanceDB itself doesn't enforce uniqueness
    # on this field in the way a traditional SQL PK does. Upsert logic handles this.

def upsert_note_vector(
    db_path: str,
    note_id: str,
    text_content: str,
    vector_embedding: List[float],
    user_id: Optional[str] = None,
    table_name: str = "notes"
) -> dict:
    """
    Upserts a note's vector into LanceDB.
    If a note with the same ID and text content hash exists, it's skipped.
    If a note with the same ID but different content exists, old versions are deleted.
    """
    if not db_path:
        return {"status": "error", "message": "LanceDB path (LANCEDB_URI) is not configured.", "code": "LANCEDB_CONFIG_ERROR"}
    if not note_id or not text_content or not vector_embedding:
        return {"status": "error", "message": "Missing required parameters: note_id, text_content, or vector.", "code": "VALIDATION_ERROR"}

    try:
        db = lancedb.connect(db_path)
        # Ensure parent directory exists for local LanceDB
        if "://" not in db_path: # Simple check for local path vs remote URI
            db_dir = os.path.dirname(db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                print(f"Created LanceDB directory: {db_dir}")


        # Open or create table
        try:
            table = db.open_table(table_name)
        except FileNotFoundError: # Table does not exist
            print(f"LanceDB table '{table_name}' not found at {db_path}. Creating new table.")
            # Schema is passed to create_table, not open_table directly in this way.
            # We should try to open, if it fails, create with schema.
            table = db.create_table(table_name, schema=LanceDBNoteSchema, mode="overwrite") # or mode="create"
            print(f"Table '{table_name}' created successfully.")
        except Exception as e: # Other errors opening table
            print(f"Error opening LanceDB table '{table_name}': {e}")
            # If opening fails and it's not FileNotFoundError, it might be a schema mismatch or corruption.
            # For simplicity, try to recreate if schema mismatch is suspected (though LanceDB aims to handle schema evolution)
            # This is a basic recovery, more sophisticated handling might be needed.
            try:
                print(f"Attempting to recreate table '{table_name}' due to open error.")
                table = db.create_table(table_name, schema=LanceDBNoteSchema, mode="overwrite")
                print(f"Table '{table_name}' recreated successfully.")
            except Exception as create_e:
                 return {"status": "error", "message": f"Failed to open or create LanceDB table '{table_name}': {create_e}", "code": "LANCEDB_TABLE_ERROR"}


        current_time = datetime.now()
        new_content_hash = hashlib.sha256(text_content.encode('utf-8')).hexdigest()

        # Check for existing identical record (same note_id and hash)
        # Querying by note_id and then checking hash in results for more precise control.
        # LanceDB's SQL `where` clause might be more efficient if direct hash comparison is supported well.
        # For now, filter by note_id, then check hash.
        # existing_records_df = table.search().where(f"note_id = '{note_id}'").to_df()
        # Simpler: select all columns, then filter
        # Note: LanceDB python API for filtering is evolving.
        # Using a simpler select and manual check for now.
        # A more direct SQL-like where clause: table.delete(f"note_id = '{note_id}' AND text_content_hash != '{new_content_hash}'")

        existing_records = []
        try:
            # Check if table is empty or note_id exists
            if table.count_rows() > 0:
                 # This select might be inefficient for large tables if not indexed on note_id.
                 # LanceDB automatically creates secondary index for scalar fields.
                selected_records = table.to_lance().to_table().to_pydict()
                for i in range(len(selected_records["note_id"])):
                    if selected_records["note_id"][i] == note_id:
                        existing_records.append({
                            "note_id": selected_records["note_id"][i],
                            "text_content_hash": selected_records["text_content_hash"][i]
                            # other fields not needed for this check
                        })
        except Exception as e:
            # This can happen if the table is empty or schema issues not caught by open/create
            print(f"Could not query table '{table_name}' for existing records (may be empty or first insert): {e}")


        found_identical = False
        ids_to_delete = []

        for record in existing_records:
            if record["text_content_hash"] == new_content_hash:
                print(f"Note {note_id} with identical content hash {new_content_hash} already exists. Skipping upsert.")
                found_identical = True
                # Optionally, update `updated_at` for the existing identical record if desired.
                # This would require a specific update mechanism if LanceDB supports partial updates by ID.
                # For now, we just skip.
                break
            else:
                # Same note_id, different hash - mark for deletion
                # LanceDB delete works on a SQL-like predicate.
                # We'll collect note_ids and delete them.
                # However, since we are adding a new version, we can just delete all old versions for this note_id.
                pass # Deletion handled below more broadly

        if found_identical:
            return {"status": "success", "message": "Note vector already up-to-date.", "operation": "skipped"}

        # Delete ALL old versions of this note_id if we are adding a new one
        if not found_identical and any(rec['note_id'] == note_id for rec in existing_records):
            print(f"Deleting old versions of note {note_id} from LanceDB table '{table_name}'.")
            try:
                table.delete(f"note_id = '{note_id}'")
            except Exception as e: # Catch specific LanceDB delete errors if possible
                return {"status": "error", "message": f"Failed to delete old versions of note {note_id}: {str(e)}", "code": "LANCEDB_DELETE_ERROR"}

        # Add new record
        new_data = [{
            "note_id": note_id,
            "user_id": user_id,
            "text_content_hash": new_content_hash,
            "vector": vector_embedding,
            "created_at": current_time, # Or fetch existing created_at if this is an update of content
            "updated_at": current_time
        }]
        table.add(new_data)
        print(f"Successfully upserted vector for note {note_id} into LanceDB table '{table_name}'.")
        return {"status": "success", "message": "Note vector upserted successfully.", "operation": "added/updated"}

    except Exception as e:
        print(f"An error occurred in upsert_note_vector: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"LanceDB operation failed: {str(e)}", "code": "LANCEDB_OPERATION_ERROR"}


# --- Note Search Result Type ---
from typing import TypedDict

class NoteSearchResult(TypedDict):
    id: str  # Can be notion_page_id (for transcripts) or note_id (for general notes)
    title: Optional[str] # e.g., meeting_title
    date: Optional[str]  # e.g., meeting_date or updated_at (as ISO string)
    score: float # Similarity score (distance)
    user_id: Optional[str]


# --- LanceDB Schema for Meeting Transcripts ---
class MeetingTranscriptSchema(LanceModel):
    notion_page_id: str
    user_id: Optional[str] = None
    meeting_title: str
    meeting_date: datetime
    transcript_chunk: str # The actual text content of the chunk
    vector: List[float] = vector(1536) # Vector embedding of the transcript_chunk
    created_at: datetime

def create_meeting_transcripts_table_if_not_exists(
    db_path: str,
    table_name: str = "meeting_transcripts"
) -> None:
    """
    Creates the meeting_transcripts LanceDB table if it doesn't already exist.
    """
    if not db_path:
        print("Error: LanceDB path (LANCEDB_URI) is not configured. Cannot create meeting_transcripts table.")
        # Or raise an error: raise ValueError("LanceDB path is required.")
        return

    try:
        db = lancedb.connect(db_path)
        # Ensure parent directory exists for local LanceDB
        if "://" not in db_path: # Simple check for local path vs remote URI
            db_dir = os.path.dirname(db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                print(f"Created LanceDB directory for transcripts: {db_dir}")

        table_names = db.table_names()
        if table_name in table_names:
            print(f"LanceDB table '{table_name}' already exists at {db_path}.")
            # Optionally, open and verify schema, but for now, just check existence.
            # table = db.open_table(table_name)
            # print(f"Table '{table_name}' schema: {table.schema}")
        else:
            print(f"LanceDB table '{table_name}' not found at {db_path}. Creating new table.")
            db.create_table(table_name, schema=MeetingTranscriptSchema, mode="create")
            print(f"Table '{table_name}' with MeetingTranscriptSchema created successfully.")

    except FileNotFoundError: # Should be caught by table_names check, but as a fallback for create_table itself
        print(f"Error: Path for LanceDB not found at {db_path} during table creation for '{table_name}'.")
        # Potentially re-raise or handle as a critical error
        # raise
    except Exception as e:
        print(f"An error occurred while creating/checking LanceDB table '{table_name}': {e}")
        import traceback
        traceback.print_exc()
        # Potentially re-raise
        # raise


def add_transcript_embedding(
    db_path: str,
    notion_page_id: str,
    meeting_title: str,
    meeting_date: datetime, # Expect datetime object
    transcript_chunk: str,
    vector_embedding: List[float],
    user_id: Optional[str] = None,
    table_name: str = "meeting_transcripts"
) -> dict:
    """
    Adds a new meeting transcript chunk embedding to the specified LanceDB table.
    Note: This function performs a simple add. It does not check for duplicates
    or perform upsert operations based on notion_page_id or chunk content.
    """
    if not db_path:
        return {"status": "error", "message": "LanceDB path (LANCEDB_URI) is not configured.", "code": "LANCEDB_CONFIG_ERROR"}
    if not all([notion_page_id, meeting_title, meeting_date, transcript_chunk, vector_embedding]):
        return {"status": "error", "message": "Missing one or more required parameters for transcript embedding.", "code": "VALIDATION_ERROR"}

    try:
        db = lancedb.connect(db_path)
        try:
            table = db.open_table(table_name)
        except FileNotFoundError:
            print(f"Error: LanceDB table '{table_name}' not found at {db_path}. Please ensure it's created first.")
            return {"status": "error", "message": f"Table '{table_name}' does not exist. Cannot add embedding.", "code": "LANCEDB_TABLE_NOT_FOUND"}
        except Exception as e:
            print(f"Error opening LanceDB table '{table_name}': {e}")
            return {"status": "error", "message": f"Failed to open LanceDB table '{table_name}': {str(e)}", "code": "LANCEDB_TABLE_ERROR"}

        current_time = datetime.now()
        new_data = [{
            "notion_page_id": notion_page_id,
            "user_id": user_id,
            "meeting_title": meeting_title,
            "meeting_date": meeting_date, # Store datetime object directly
            "transcript_chunk": transcript_chunk,
            "vector": vector_embedding,
            "created_at": current_time
        }]

        table.add(new_data)
        print(f"Successfully added transcript embedding for Notion page ID '{notion_page_id}' to table '{table_name}'.")
        return {"status": "success", "message": "Transcript embedding added successfully."}

    except Exception as e:
        print(f"An error occurred in add_transcript_embedding: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"LanceDB operation failed to add transcript embedding: {str(e)}", "code": "LANCEDB_OPERATION_ERROR"}


# --- LanceDB Schema for Training Events ---
class LanceDBTrainingEventSchema(LanceModel):
    id: str  # Primary key, Google Calendar event ID (googleEventId)
    userId: str # Changed from user_id, made non-optional to align with TS features-apply
    vector: List[float] = vector(1536) # Assuming same embedding model as notes
    source_event_text: Optional[str] = None # Store the text that was vectorized
    created_at: datetime
    # updated_at is not strictly needed if we delete and re-add on conflict

def upsert_training_event_vector(
    db_path: str,
    event_id: str,
    vector_embedding: List[float],
    userId: str, # Changed from user_id, made non-optional
    event_text: Optional[str] = None,
    table_name: str = "training_data" # Aligned with lancedb_service.ts
) -> dict:
    """
    Upserts a training event's vector into LanceDB.
    Deletes any existing record with the same event_id before adding the new one.
    """
    if not db_path:
        return {"status": "error", "message": "LanceDB path (LANCEDB_URI) is not configured.", "code": "LANCEDB_CONFIG_ERROR"}
    if not event_id or not vector_embedding or not userId: # Added userId check
        return {"status": "error", "message": "Missing required parameters: event_id, userId, or vector.", "code": "VALIDATION_ERROR"}

    try:
        db = lancedb.connect(db_path)
        if "://" not in db_path:
            db_dir = os.path.dirname(db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)

        try:
            table = db.open_table(table_name)
        except FileNotFoundError:
            table = db.create_table(table_name, schema=LanceDBTrainingEventSchema, mode="overwrite")
            print(f"LanceDB table '{table_name}' created.")
        except Exception as e: # Attempt to recreate if schema mismatch or other open errors
            print(f"Error opening training_events table '{table_name}', attempting to recreate: {e}")
            try:
                table = db.create_table(table_name, schema=LanceDBTrainingEventSchema, mode="overwrite")
            except Exception as create_e:
                return {"status": "error", "message": f"Failed to create/recreate LanceDB table '{table_name}': {create_e}", "code": "LANCEDB_TABLE_ERROR"}

        # Upsert logic: delete existing by event_id, then add new.
        try:
            # Check if table has any data before trying to delete, to avoid error on empty table query
            # However, delete with a non-matching predicate on an empty table is usually fine.
            # More robust: check if any record with this id exists.
            # For simplicity, we just attempt delete. If it fails for a reason other than "not found", it's an issue.
            # If the table is very large, querying first might be better.
            table.delete(f"id = '{event_id}'")
            print(f"Deleted existing records for event_id '{event_id}' in table '{table_name}'.")
        except Exception as e:
            # LanceDB might raise an error if the `where` condition matches no rows,
            # or if the table is empty and delete is called. We can often ignore this.
            # Or, it might be a more serious issue. For now, log and continue.
            print(f"Note/Warning: Could not delete event_id '{event_id}' (may not exist, or other issue): {str(e)}")


        current_time = datetime.now()
        new_data = [{
            "id": event_id,
            "userId": userId, # Changed from user_id
            "vector": vector_embedding,
            "source_event_text": event_text,
            "created_at": current_time
        }]
        table.add(new_data)
        print(f"Successfully inserted vector for training event {event_id} into LanceDB table '{table_name}'.")
        return {"status": "success", "message": "Training event vector inserted successfully.", "operation": "inserted"}

    except Exception as e:
        print(f"An error occurred in upsert_training_event_vector: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"LanceDB operation failed for training event: {str(e)}", "code": "LANCEDB_OPERATION_ERROR"}


def search_similar_notes(
    db_path: str,
    query_vector: List[float],
    user_id: Optional[str] = None, # Optional: search across all users if None
    table_name: str = "notes",
    limit: int = 5
) -> dict:
    """
    Searches for notes with vectors similar to the query_vector, optionally filtered by user_id.
    """
    if not db_path:
        return {"status": "error", "message": "LanceDB path (LANCEDB_URI) is not configured.", "code": "LANCEDB_CONFIG_ERROR"}
    if not query_vector:
        return {"status": "error", "message": "Query vector is required for similarity search.", "code": "VALIDATION_ERROR"}

    try:
        db = lancedb.connect(db_path)
        try:
            table = db.open_table(table_name)
        except FileNotFoundError:
            return {"status": "success", "data": [], "message": f"Table '{table_name}' not found. No search performed."} # Not an error if table just doesn't exist yet
        except Exception as e:
            return {"status": "error", "message": f"Failed to open LanceDB table '{table_name}': {str(e)}", "code": "LANCEDB_TABLE_ERROR"}

        search_query = table.search(query_vector).limit(limit)

        # Apply user_id filter if provided
        # Note: LanceDB's where clause syntax can be specific.
        # Ensuring user_id is properly quoted if it's a string.
        if user_id:
            search_query = search_query.where(f"user_id = '{user_id}'")

        # Select specific columns to return. Add others if stored and needed.
        # 'vector' and 'text_content_hash' are usually not needed in search results.
        select_fields = ["user_id"] # Always include user_id and the implicit _distance (score)
        if table_name == "meeting_transcripts":
            select_fields.extend(["notion_page_id", "meeting_title", "meeting_date"])
        elif table_name == "notes": # Default or explicit "notes" table
            select_fields.extend(["note_id", "updated_at"])
        else:
            # For unknown table types, we might select common fields or minimal fields
            # For now, let's assume specific handling or it defaults to just user_id + score
            # Or, if a schema is strictly enforced elsewhere, this 'else' might not be needed.
            # To be safe, if table_name is not recognized, select only user_id
            # and expect other fields to be handled via .get() in formatting.
            # However, the query will fail if fields don't exist.
            # A better minimal set might be just user_id, or an error if table_name is unknown.
            # For this iteration, we'll rely on the caller to use known table_names.
            # If select_fields remains just ["user_id"], it's not very useful.
            # Defaulting to "notes" schema fields if table_name is not "meeting_transcripts"
            select_fields.extend(["note_id", "updated_at"])


        search_query = search_query.select(select_fields)
        results_raw = search_query.to_list()

        formatted_results: List[NoteSearchResult] = []
        for record in results_raw:
            item_id = ""
            item_title = None
            item_date_obj = None

            if table_name == "meeting_transcripts":
                item_id = record.get("notion_page_id", "")
                item_title = record.get("meeting_title")
                item_date_obj = record.get("meeting_date")
            elif table_name == "notes":
                item_id = record.get("note_id", "")
                # "notes" table doesn't have a "title" field in its schema (LanceDBNoteSchema)
                # It has text_content_hash, created_at, updated_at.
                # We could potentially add a way to get a snippet or title if it were stored.
                # For now, title will be None for "notes".
                item_date_obj = record.get("updated_at")

            item_date_iso = None
            if isinstance(item_date_obj, datetime):
                item_date_iso = item_date_obj.isoformat()
            elif item_date_obj is not None: # If it's already a string (e.g. from older data or different source)
                item_date_iso = str(item_date_obj)

            formatted_results.append({
                "id": item_id,
                "title": item_title,
                "date": item_date_iso,
                "score": record["_distance"], # LanceDB uses _distance for similarity score
                "user_id": record.get("user_id")
            })

        return {"status": "success", "data": formatted_results}

    except Exception as e:
        print(f"An error occurred in search_similar_notes: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"LanceDB search operation failed: {str(e)}", "code": "LANCEDB_SEARCH_ERROR"}

[end of atomic-docker/project/functions/_utils/lancedb_service.py]
