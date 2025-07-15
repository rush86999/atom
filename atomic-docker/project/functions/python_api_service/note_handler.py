import os
import logging
from notion_client import Client

logger = logging.getLogger(__name__)

notion = Client(auth=os.environ.get("NOTION_API_KEY"))
NOTION_NOTES_DATABASE_ID = os.environ.get("NOTION_NOTES_DATABASE_ID")

def search_notes(query: str) -> str:
    """
    Searches notes in a Notion database for the given query.
    """
    if not NOTION_NOTES_DATABASE_ID:
        return "NOTION_NOTES_DATABASE_ID environment variable not set."

    try:
        results = notion.databases.query(
            database_id=NOTION_NOTES_DATABASE_ID,
            filter={
                "property": "title",
                "rich_text": {
                    "contains": query,
                },
            },
        )

        if not results["results"]:
            return "No relevant notes found."

        notes = ""
        for result in results["results"]:
            title = result["properties"]["title"]["title"][0]["text"]["content"]
            url = result["url"]
            notes += f"- [{title}]({url})\n"

        return notes
    except Exception as e:
        logger.error(f"Error searching notes: {e}")
        return "Error searching notes."
