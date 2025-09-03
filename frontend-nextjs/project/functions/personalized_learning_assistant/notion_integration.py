import os
from notion_client import Client
from rake_nltk import Rake

def analyze_notes(database_id):
    """
    Analyzes the user's notes to identify areas of interest and knowledge gaps.

    Args:
        database_id: The ID of the Notion database containing the user's notes.

    Returns:
        A dictionary containing the analysis results.
    """
    notion_token = os.environ.get("NOTION_TOKEN")

    if not notion_token:
        raise Exception("NOTION_TOKEN environment variable is not set.")

    notion = Client(auth=notion_token)
    rake = Rake()

    results = notion.databases.query(database_id=database_id)
    pages = results["results"]

    text = ""
    for page in pages:
        for block in notion.blocks.children.list(block_id=page["id"])["results"]:
            if block["type"] == "paragraph":
                for rich_text in block["paragraph"]["rich_text"]:
                    text += rich_text["plain_text"]

    rake.extract_keywords_from_text(text)
    keywords = rake.get_ranked_phrases()

    return {
        "areas_of_interest": keywords,
        "knowledge_gaps": [],
    }
