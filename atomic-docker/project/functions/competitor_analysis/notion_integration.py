import os
from notion_client import Client

def create_notion_page(title, content):
    """
    Creates a new page in Notion.

    Args:
        title: The title of the page.
        content: The content of the page.
    """
    notion_token = os.environ.get("NOTION_TOKEN")
    database_id = os.environ.get("NOTION_DATABASE_ID")

    if not notion_token or not database_id:
        raise Exception("NOTION_TOKEN and NOTION_DATABASE_ID environment variables are not set.")

    notion = Client(auth=notion_token)

    notion.pages.create(
        parent={"database_id": database_id},
        properties={
            "title": [
                {
                    "text": {
                        "content": title
                    }
                }
            ]
        },
        children=[
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": content
                            }
                        }
                    ]
                }
            }
        ]
    )
