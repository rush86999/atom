import os
import logging
import dropbox
from flask import Blueprint

logger = logging.getLogger(__name__)

dropbox_bp = Blueprint('dropbox_bp', __name__)

def search_dropbox(query: str) -> str:
    """
    Searches Dropbox for the given query.
    """
    try:
        dbx = dropbox.Dropbox(os.environ.get("DROPBOX_ACCESS_TOKEN"))
        results = dbx.files_search_v2(query).matches
        if not results:
            return "No relevant documents found in Dropbox."

        docs = ""
        for match in results:
            metadata = match.metadata.get_metadata()
            docs += f"- [{metadata.name}]({metadata.path_display})\n"

        return docs
    except Exception as e:
        logger.error(f"Error searching Dropbox: {e}")
        return "Error searching Dropbox."
