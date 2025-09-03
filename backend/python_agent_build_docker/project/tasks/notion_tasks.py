from celery import shared_task
import logging
from typing import Dict, Any, List, Optional
import os
import requests
from notion_client import Client as NotionClient

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def sync_notion_database(self, database_id: str, filter_config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Sync data from a Notion database for workflow automation
    """
    try:
        logger.info(f"Syncing Notion database: {database_id} for workflow")

        notion_token = os.getenv("NOTION_API_TOKEN")
        if not notion_token:
            raise ValueError("NOTION_API_TOKEN not configured")

        client = NotionClient(auth=notion_token)

        # Query the database
        query_params = {}
        if filter_config:
            query_params["filter"] = filter_config

        response = client.databases.query(database_id=database_id, **query_params)

        # Process and return results
        pages = []
        for page in response.get("results", []):
            pages.append({
                "id": page.get("id"),
                "title": page.get("properties", {}).get("Name", {}).get("title", [{}])[0].get("text", {}).get("content", "Untitled"),
                "last_edited": page.get("last_edited_time"),
                "url": page.get("url"),
                "properties": page.get("properties", {})
            })

        return pages

    except Exception as e:
        logger.error(f"Error syncing Notion database {database_id}: {e}")
        raise self.retry(exc=e, countdown=60)

@shared_task(bind=True, max_retries=3)
def create_notion_task(self, database_id: str, task_name: str, description: Optional[str] = None,
                      due_date: Optional[str] = None, priority: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a new task in Notion for workflow automation
    """
    try:
        logger.info(f"Creating Notion task in database: {database_id}")

        notion_token = os.getenv("NOTION_API_TOKEN")
        if not notion_token:
            raise ValueError("NOTION_API_TOKEN not configured")

        client = NotionClient(auth=notion_token)

        # Prepare properties
        properties = {
            "Name": {
                "title": [
                    {
                        "text": {
                            "content": task_name
                        }
                    }
                ]
            }
        }

        if description:
            properties["Description"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": description
                        }
                    }
                ]
            }

        if due_date:
            properties["Due Date"] = {
                "date": {
                    "start": due_date
                }
            }

        if priority:
            properties["Priority"] = {
                "select": {
                    "name": priority
                }
            }

        # Create the page
        response = client.pages.create(
            parent={"database_id": database_id},
            properties=properties
        )

        return {
            "id": response.get("id"),
            "url": response.get("url"),
            "created_time": response.get("created_time"),
            "task_name": task_name
        }

    except Exception as e:
        logger.error(f"Error creating Notion task in {database_id}: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def update_notion_page(self, page_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update an existing Notion page for workflow automation
    """
    try:
        logger.info(f"Updating Notion page: {page_id}")

        notion_token = os.getenv("NOTION_API_TOKEN")
        if not notion_token:
            raise ValueError("NOTION_API_TOKEN not configured")

        client = NotionClient(auth=notion_token)

        response = client.pages.update(page_id=page_id, properties=properties)

        return {
            "id": response.get("id"),
            "updated": True,
            "last_edited": response.get("last_edited_time")
        }

    except Exception as e:
        logger.error(f"Error updating Notion page {page_id}: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def archive_notion_page(self, page_id: str) -> bool:
    """
    Archive (soft delete) a Notion page for workflow automation
    """
    try:
        logger.info(f"Archiving Notion page: {page_id}")

        notion_token = os.getenv("NOTION_API_TOKEN")
        if not notion_token:
            raise ValueError("NOTION_API_TOKEN not configured")

        client = NotionClient(auth=notion_token)

        response = client.pages.update(
            page_id=page_id,
            archived=True
        )

        return response.get("archived", False)

    except Exception as e:
        logger.error(f"Error archiving Notion page {page_id}: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def create_notion_database_page(self, database_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new page in a Notion database with custom properties
    Used by workflow automation system
    """
    try:
        logger.info(f"Creating Notion database page with custom properties")

        notion_token = os.getenv("NOTION_API_TOKEN")
        if not notion_token:
            raise ValueError("NOTION_API_TOKEN not configured")

        client = NotionClient(auth=notion_token)

        response = client.pages.create(
            parent={"database_id": database_id},
            properties=properties
        )

        return {
            "id": response.get("id"),
            "url": response.get("url"),
            "created_time": response.get("created_time"),
            "properties": response.get("properties", {})
        }

    except Exception as e:
        logger.error(f"Error creating Notion database page: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def query_notion_database(self, database_id: str, filter_config: Optional[Dict[str, Any]] = None,
                         sorts: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """
    Query a Notion database with filters and sorting
    Used by workflow automation system
    """
    try:
        logger.info(f"Querying Notion database: {database_id}")

        notion_token = os.getenv("NOTION_API_TOKEN")
        if not notion_token:
            raise ValueError("NOTION_API_TOKEN not configured")

        client = NotionClient(auth=notion_token)

        query_params = {}
        if filter_config:
            query_params["filter"] = filter_config
        if sorts:
            query_params["sorts"] = sorts

        response = client.databases.query(database_id=database_id, **query_params)

        return response.get("results", [])

    except Exception as e:
        logger.error(f"Error querying Notion database {database_id}: {e}")
        raise self.retry(exc=e, countdown=30)
