import os
from notion_client import Client

def get_notion_data(database_id):
    """
    Fetches data from a Notion database.

    Args:
        database_id: The ID of the Notion database.

    Returns:
        A dictionary containing the Notion data.
    """
    notion_token = os.environ.get("NOTION_TOKEN")

    if not notion_token:
        raise Exception("NOTION_TOKEN environment variable is not set.")

    notion = Client(auth=notion_token)

    # This is a placeholder for the actual Notion API integration.
    # results = notion.databases.query(database_id=database_id).get("results")
    # return {"pages": results}

    return {
        "pages": [
            {
                "properties": {
                    "Name": {
                        "title": [
                            {
                                "text": {
                                    "content": "My notes on Python"
                                }
                            }
                        ]
                    },
                    "Tags": {
                        "multi_select": [
                            {"name": "python"},
                            {"name": "programming"},
                        ]
                    }
                }
            },
            {
                "properties": {
                    "Name": {
                        "title": [
                            {
                                "text": {
                                    "content": "My notes on productivity"
                                }
                            }
                        ]
                    },
                    "Tags": {
                        "multi_select": [
                            {"name": "productivity"},
                            {"name": "self-help"},
                        ]
                    }
                }
            }
        ]
    }
