# Mock implementations for lancedb when not available
try:
    import lancedb
    from lancedb.pydantic import LanceModel, vector
    from datetime import datetime, timezone
except ImportError:
    # Create a mock exception class that inherits from Exception
    class LanceDBClientError(Exception):
        pass

    class MockLanceDB:
        class _Exceptions:
            LanceDBClientError = LanceDBClientError
        exceptions = _Exceptions()

        def connect(self, uri):
            return MockDatabase(uri)

    class MockDatabase:
        def __init__(self, uri):
            self.uri = uri
            self.tables = {}

        def open_table(self, name):
            if name not in self.tables:
                self.tables[name] = MockTable(name)
            return self.tables[name]

        def table_names(self):
            return list(self.tables.keys())

    class MockTable:
        def __init__(self, name):
            self.name = name
            self.data = []

        def search(self, query_vector, query_type="vector"):
            # Return mock results
            return MockSearchBuilder(self, query_vector)

        def to_pandas(self):
            import pandas as pd
            return pd.DataFrame(self.data)

    class MockSearchBuilder:
        def __init__(self, table, query_vector):
            self.table = table
            self.query_vector = query_vector
            self.limit_value = 10
            self.where_clause = None
            self.select_cols = None

        def limit(self, n):
            self.limit_value = n
            return self

        def where(self, clause):
            self.where_clause = clause
            return self

        def select(self, columns):
            self.select_cols = columns
            return self

        def to_pandas(self):
            import pandas as pd
            from datetime import datetime, timezone
            # Return mock search results
            mock_results = []
            for i in range(min(self.limit_value, 3)):
                mock_results.append({
                    'notion_page_id': f'mock-page-{i}',
                    'notion_page_title': f'Mock Meeting {i}',
                    'notion_page_url': f'https://notion.so/mock-{i}',
                    'chunk_text': f'This is mock transcript content for result {i}',
                    '_distance': 0.1 * (i + 1),
                    'last_edited_at_notion': datetime.now(timezone.utc).isoformat(),
                    'user_id': 'mock-user'
                })
            return pd.DataFrame(mock_results)

    class LanceModel:
        pass

    def vector(*args, **kwargs):
        return list

    lancedb = MockLanceDB()

from typing import List, Optional, TypedDict
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# Define the structure of the search results we expect to return
class SemanticSearchResult(TypedDict):
    notion_page_id: str
    notion_page_title: str
    notion_page_url: str
    text_chunk_preview: str # A snippet of the relevant text chunk
    score: float # Similarity score
    last_edited_at_notion: Optional[str] # ISO format string
    user_id: Optional[str]


def search_meeting_transcripts(
    db_path: str, # Comes from LANCEDB_URI
    query_vector: List[float],
    user_id: str, # Made non-optional for user-specific search
    table_name: str, # Should be the same as used by ingestion pipeline, e.g., "meeting_transcripts_embeddings"
    limit: int = 5,
    select_columns: Optional[List[str]] = None
) -> dict:
    """
    Searches for transcript chunks with vectors similar to the query_vector,
    filtered by user_id.
    Uses the schema fields defined in the ingestion pipeline's lancedb_handler.TranscriptChunk.
    """
    if not db_path:
        return {"status": "error", "message": "LanceDB path (LANCEDB_URI) is not configured.", "code": "LANCEDB_CONFIG_ERROR"}
    if not query_vector:
        return {"status": "error", "message": "Query vector is required for similarity search.", "code": "VALIDATION_ERROR"}
    if not user_id: # Should always be provided for this search
        return {"status": "error", "message": "user_id is required for searching meeting transcripts.", "code": "VALIDATION_ERROR_USERID"}
    if not table_name:
        return {"status": "error", "message": "LanceDB table_name is required.", "code": "LANCEDB_CONFIG_ERROR_TABLE"}

    try:
        db = lancedb.connect(db_path)
        try:
            table = db.open_table(table_name)
            logger.info(f"Successfully opened LanceDB table: {table_name} at {db_path}")
        except FileNotFoundError as e: # More specific LanceDB table not found
            logger.warning(f"LanceDB table '{table_name}' not found at {db_path}: {e}. No search performed.")
            return {"status": "success", "data": [], "message": f"Table '{table_name}' not found. No search performed."}
        except Exception as e: # Catch other potential errors during table open
            logger.error(f"Failed to open LanceDB table '{table_name}' at {db_path}: {e}", exc_info=True)
            return {"status": "error", "message": f"Failed to open LanceDB table '{table_name}': {str(e)}", "code": "LANCEDB_TABLE_ERROR"}

        search_query = table.search(query_vector).limit(limit)
        search_query = search_query.where(f"user_id = '{user_id}'") # Critical filter

        # Fields to retrieve based on TranscriptChunk schema from lancedb_handler.py
        # (embedding, text_chunk, chunk_id, notion_page_id, notion_page_title, notion_page_url, user_id,
        #  created_at_notion, last_edited_at_notion, ingested_at)
        default_select_columns = [
            "notion_page_id", "notion_page_title", "notion_page_url",
            "text_chunk", "last_edited_at_notion", "user_id"
            # also implicitly gets _distance (score)
        ]
        columns_to_select = select_columns if select_columns else default_select_columns
        search_query = search_query.select(columns_to_select)

        logger.info(f"Executing LanceDB search on table '{table_name}' for user_id '{user_id}' with limit {limit}.")
        results_raw = search_query.to_list() # Returns a list of dicts
        logger.info(f"LanceDB search returned {len(results_raw)} raw results.")

        formatted_results: List[SemanticSearchResult] = []
        for record in results_raw:
            last_edited_iso: Optional[str] = None
            last_edited_dt = record.get("last_edited_at_notion")
            if isinstance(last_edited_dt, datetime):
                last_edited_iso = last_edited_dt.isoformat()
            elif isinstance(last_edited_dt, (int, float)): # LanceDB might return timestamp as int/float (nanoseconds)
                try:
                    # Convert from nanoseconds to seconds for datetime.fromtimestamp
                    last_edited_dt = datetime.fromtimestamp(last_edited_dt / 1e9, tz=timezone.utc)
                    last_edited_iso = last_edited_dt.isoformat()
                except Exception as e_ts:
                    logger.warning(f"Could not parse timestamp {last_edited_dt} for page {record.get('notion_page_id')}: {e_ts}")
            elif isinstance(last_edited_dt, str): # If already string
                 last_edited_iso = last_edited_dt


            text_chunk_preview = record.get("text_chunk", "")
            if len(text_chunk_preview) > 250: # Create a snippet
                text_chunk_preview = text_chunk_preview[:247] + "..."

            formatted_results.append({
                "notion_page_id": record.get("notion_page_id", ""),
                "notion_page_title": record.get("notion_page_title", "Untitled"),
                "notion_page_url": record.get("notion_page_url", ""),
                "text_chunk_preview": text_chunk_preview,
                "score": record.get("_distance", 0.0), # LanceDB uses _distance
                "last_edited_at_notion": last_edited_iso,
                "user_id": record.get("user_id")
            })

        logger.info(f"Formatted {len(formatted_results)} search results.")
        return {"status": "success", "data": formatted_results}

    except Exception as e:
        logger.error(f"An error occurred in search_meeting_transcripts: {e}", exc_info=True)
        return {"status": "error", "message": f"LanceDB search operation failed: {str(e)}", "code": "LANCEDB_SEARCH_ERROR"}

# --- Remove old/unused functions and schemas ---
# The functions upsert_note_vector, create_meeting_transcripts_table_if_not_exists,
# add_transcript_embedding, upsert_training_event_vector, and their associated schemas
# (LanceDBNoteSchema, MeetingTranscriptSchema, LanceDBTrainingEventSchema)
# are superseded by the ingestion pipeline's lancedb_handler.py or are for different use cases.
# For the "Searchable Meeting Archive", we only need search_meeting_transcripts here.
# Keeping search_similar_notes for now if it's used by other parts of the python_api_service for "notes" table.
# But if the goal is only meeting transcripts, it can be removed or refactored.
# For this plan, we focus on making search_meeting_transcripts the primary search function.

# If 'search_similar_notes' is still needed for a generic "notes" table, it should be kept.
# If not, it can be removed. For now, I will assume it might be used elsewhere and keep it,
# but make search_meeting_transcripts the focus for our current feature.
# The `search_routes.py` should be updated to call `search_meeting_transcripts`.
