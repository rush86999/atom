import os
import logging
from typing import List, Dict, Optional, Any
from notion_client import AsyncClient, APIResponseError
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)
# Basic configuration if run standalone, though usually configured by the app using this module
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
# NOTION_TRANSCRIPTS_DATABASE_ID will be passed to functions, not a global here.

# Initialize Notion client (can be passed in or initialized globally)
_notion_client_instance: Optional[AsyncClient] = None

def get_notion_client() -> Optional[AsyncClient]:
    global _notion_client_instance
    if _notion_client_instance is None:
        if NOTION_API_KEY:
            _notion_client_instance = AsyncClient(auth=NOTION_API_KEY)
            logger.info("Notion client initialized by extractor module.")
        else:
            logger.warning("NOTION_API_KEY not set. Notion client cannot be initialized by extractor.")
    return _notion_client_instance

async def fetch_pages_from_database(
    database_id: str,
    notion_client: Optional[AsyncClient] = None,
    page_size: int = 100
) -> List[Dict[str, Any]]:
    """
    Fetches all page objects (summary) from a given Notion database.
    Returns a list of page objects from the Notion API.
    """
    client = notion_client or get_notion_client()
    if not client or not database_id:
        logger.error("Notion client or database_id not available/configured for fetching pages.")
        return []

    pages_data: List[Dict[str, Any]] = []
    start_cursor: Optional[str] = None
    logger.info(f"Fetching pages from Notion database_id: {database_id}")

    while True:
        try:
            query_params: Dict[str, Any] = {
                "database_id": database_id,
                "page_size": page_size
            }
            if start_cursor:
                query_params["start_cursor"] = start_cursor

            response = await client.databases.query(**query_params)
            results = response.get("results", [])
            pages_data.extend(results)
            logger.debug(f"Fetched {len(results)} pages. Total so far: {len(pages_data)}. Has more: {response.get('has_more')}")

            if not response.get("has_more"):
                break
            start_cursor = response.get("next_cursor")
            if not start_cursor: # Should not happen if has_more is true, but as a safeguard
                logger.warning("Notion indicated has_more but no next_cursor was provided. Stopping pagination.")
                break
        except APIResponseError as e:
            logger.error(f"Notion API error while fetching pages from database {database_id}: {e}", exc_info=True)
            break
        except Exception as e:
            logger.error(f"Unexpected error fetching pages from database {database_id}: {e}", exc_info=True)
            break
    logger.info(f"Finished fetching pages from Notion database_id: {database_id}. Total pages retrieved: {len(pages_data)}")
    return pages_data

async def extract_text_from_page_blocks(page_id: str, notion_client: Optional[AsyncClient] = None) -> str:
    """
    Fetches all blocks from a page and concatenates their plain text content.
    Handles simple text extraction from common block types.
    """
    client = notion_client or get_notion_client()
    if not client:
        logger.error(f"Notion client not available for extracting blocks from page {page_id}.")
        return ""

    all_text_parts: List[str] = []
    start_cursor: Optional[str] = None
    logger.debug(f"Extracting text from blocks for page_id: {page_id}")

    while True:
        try:
            response = await client.blocks.children.list(
                block_id=page_id,
                page_size=100, # Max 100
                start_cursor=start_cursor
            )
            blocks = response.get("results", [])
            for block in blocks:
                block_type = block.get("type")
                # Check if the block type key exists and it has 'rich_text'
                if block_type and block_type in block and "rich_text" in block[block_type]:
                    for rt_item in block[block_type]["rich_text"]:
                        if rt_item.get("type") == "text" and "content" in rt_item.get("text", {}):
                            all_text_parts.append(rt_item["text"]["content"])
                # TODO: Consider extracting text from other block types if necessary (e.g., callouts, quotes)
                # TODO: Handle child_database or child_page blocks (e.g., by recursion or skipping)

            if not response.get("has_more"):
                break
            start_cursor = response.get("next_cursor")
            if not start_cursor:
                logger.warning(f"Notion indicated has_more blocks for page {page_id} but no next_cursor. Stopping block fetch.")
                break
        except APIResponseError as e:
            logger.error(f"Notion API error fetching blocks for page {page_id}: {e}", exc_info=True)
            break
        except Exception as e:
            logger.error(f"Unexpected error fetching blocks for page {page_id}: {e}", exc_info=True)
            break

    return "\n".join(all_text_parts).strip()

async def get_page_metadata(page_id: str, notion_client: Optional[AsyncClient] = None) -> Optional[Dict[str, Any]]:
    """
    Fetches a specific page's metadata.
    Returns a dictionary with id, title, url, created_time, last_edited_time.
    Title extraction assumes the standard 'title' property name for a database page, or a 'Name' property.
    """
    client = notion_client or get_notion_client()
    if not client:
        logger.error(f"Notion client not available for fetching metadata for page {page_id}.")
        return None
    try:
        page_object = await client.pages.retrieve(page_id=page_id)

        page_title = "Untitled" # Default title
        properties = page_object.get("properties", {})

        # Try to get title from a 'title' type property (often named 'Name' or 'Title')
        # This logic attempts to find the common title property names.
        title_prop_names_to_check = ['Name', 'Task Description', 'title', 'Page Title']
        # 'Task Description' added based on FEATURES.MD for task DB

        found_title_prop = None
        for prop_name in title_prop_names_to_check:
            if prop_name in properties and properties[prop_name].get("type") == "title":
                found_title_prop = properties[prop_name]
                break

        if found_title_prop and found_title_prop.get("title"):
            title_array = found_title_prop.get("title", [])
            if title_array and isinstance(title_array, list) and len(title_array) > 0:
                 if "plain_text" in title_array[0]:
                    page_title = title_array[0]["plain_text"]

        return {
            "id": page_object.get("id"),
            "title": page_title,
            "url": page_object.get("url"),
            "created_time": page_object.get("created_time"),
            "last_edited_time": page_object.get("last_edited_time"),
            "archived": page_object.get("archived", False) # Good to know if page is archived
        }
    except APIResponseError as e:
        logger.error(f"Notion API error fetching page metadata for {page_id}: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching page metadata for {page_id}: {e}", exc_info=True)
        return None

async def extract_structured_data_from_db(
    database_id: str,
    atom_user_id: str, # The Atom user this extraction is for
    notion_client_override: Optional[AsyncClient] = None # Allow passing a pre-configured client
) -> List[Dict[str, Any]]:
    """
    High-level function to fetch pages from a Notion database, then extract text and metadata for each.
    Returns a list of dictionaries, each containing structured data for a page.
    """
    client = notion_client_override or get_notion_client()
    if not client:
        logger.error("Notion client not initialized/provided. Cannot extract data.")
        return []

    logger.info(f"Starting Notion data extraction for database_id: {database_id}, user_id: {atom_user_id}")

    page_summaries = await fetch_pages_from_database(database_id, notion_client=client)

    extracted_page_data_list: List[Dict[str, Any]] = []
    for page_summary in page_summaries:
        page_id = page_summary.get("id")
        if not page_id:
            logger.warning("Found page summary without an ID. Skipping.")
            continue

        page_metadata = await get_page_metadata(page_id, notion_client=client)
        if not page_metadata:
            logger.warning(f"Could not retrieve metadata for page {page_id}. Skipping.")
            continue

        if page_metadata.get("archived", False):
            logger.info(f"Page {page_id} ('{page_metadata['title']}') is archived. Skipping content extraction.")
            continue

        logger.info(f"Extracting content for page: {page_metadata['title']} ({page_id})")
        page_content_text = await extract_text_from_page_blocks(page_id, notion_client=client)

        # We include pages even if they have no text content, metadata might be useful.
        # The text chunking step later will handle empty text.
        extracted_page_data_list.append({
            "notion_page_id": page_id,
            "notion_page_title": page_metadata["title"],
            "notion_page_url": page_metadata["url"],
            "user_id": atom_user_id,
            "full_text": page_content_text,
            "created_at_notion": page_metadata["created_time"],
            "last_edited_at_notion": page_metadata["last_edited_time"]
        })

    logger.info(f"Extracted data for {len(extracted_page_data_list)} pages from Notion database {database_id}.")
    return extracted_page_data_list

if __name__ == '__main__':
    # Example Usage (requires environment variables to be set)
    # Ensure NOTION_API_KEY and NOTION_TRANSCRIPTS_DATABASE_ID are set in your environment

    async def main_test():
        db_id = os.getenv("NOTION_TRANSCRIPTS_DATABASE_ID")
        test_user_id = "test_atom_user_123" # Example user ID

        if not db_id:
            print("Please set NOTION_TRANSCRIPTS_DATABASE_ID environment variable for testing.")
            return
        if not NOTION_API_KEY:
            print("Please set NOTION_API_KEY environment variable for testing.")
            return

        print(f"Attempting to extract data from Notion DB: {db_id} for user {test_user_id}")
        pages_with_content = await extract_structured_data_from_db(db_id, test_user_id)

        if pages_with_content:
            print(f"\nSuccessfully extracted {len(pages_with_content)} pages.")
            for i, page_data in enumerate(pages_with_content):
                print(f"\n--- Page {i+1} ---")
                print(f"  ID: {page_data['notion_page_id']}")
                print(f"  Title: {page_data['notion_page_title']}")
                print(f"  URL: {page_data['notion_page_url']}")
                print(f"  User ID: {page_data['user_id']}")
                print(f"  Created: {page_data['created_at_notion']}")
                print(f"  Last Edited: {page_data['last_edited_at_notion']}")
                print(f"  Text Preview (first 200 chars): {page_data['full_text'][:200]}...")
        else:
            print("No pages extracted or an error occurred.")

    # asyncio.run(main_test()) # Comment out if not running directly
    pass
