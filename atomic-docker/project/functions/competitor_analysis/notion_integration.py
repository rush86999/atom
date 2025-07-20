import os
from notion_client import Client

def create_notion_page(title, briefing):
    """
    Creates a new page in Notion with the competitor briefing.

    Args:
        title: The title of the page.
        briefing: The competitor briefing.
    """
    notion_token = os.environ.get("NOTION_TOKEN")
    database_id = os.environ.get("NOTION_DATABASE_ID")

    if not notion_token or not database_id:
        raise Exception("NOTION_TOKEN and NOTION_DATABASE_ID environment variables are not set.")

    notion = Client(auth=notion_token)

    children = []
    for line in briefing.split("\n"):
        if line.startswith("# "):
            children.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": [{"type": "text", "text": {"content": line[2:]}}]
                }
            })
        elif line.startswith("## "):
            children.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": line[3:]}}]
                }
            })
        elif line.startswith("### "):
            children.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": line[4:]}}]
                }
            })
        elif line.startswith("- "):
            children.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": line[2:]}}]
                }
            })
        elif line.startswith("**"):
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": line.replace("*", "")},
                        "annotations": {"bold": True}
                    }]
                }
            })
        elif line.strip():
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": line}}]
                }
            })

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
        children=children
    )
