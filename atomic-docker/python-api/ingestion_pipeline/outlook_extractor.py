import os
import logging
from typing import List, Dict, Any
import httpx
from .msteams_extractor import get_msteams_oauth_token

# Configure logging
logger = logging.getLogger(__name__)

# --- Data Extraction Logic ---
GRAPH_API_BASE_URL = "https://graph.microsoft.com/v1.0"

async def extract_data_from_outlook(user_id: str, db_conn_pool: Any) -> List[Dict[str, Any]]:
    """
    Extracts emails from a user's Outlook account using the Microsoft Graph API.
    """
    logger.info(f"Starting Outlook data extraction for user {user_id}.")

    # Reuse the same token retrieval and refresh logic as MS Teams
    token_data = await get_msteams_oauth_token(user_id, db_conn_pool)
    if not token_data or "token" not in token_data:
        logger.warning(f"No valid MS Graph credentials found for user {user_id}. Skipping Outlook extraction.")
        return []

    access_token = token_data["token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    all_emails = []

    async with httpx.AsyncClient() as client:
        try:
            messages_url = f"{GRAPH_API_BASE_URL}/me/messages?$select=id,subject,body,webLink,createdDateTime,lastModifiedDateTime"
            while messages_url:
                response = await client.get(messages_url, headers=headers)
                response.raise_for_status()
                email_data = response.json()

                for email in email_data.get("value", []):
                    if email.get("body", {}).get("content"):
                        formatted_email = {
                            "document_id": f"outlook:{email['id']}",
                            "document_title": email.get("subject", "No Subject"),
                            "full_text": email["body"]["content"],
                            "source": "outlook",
                            "user_id": user_id,
                            "url": email.get("webLink"),
                            "created_at": email.get("createdDateTime"),
                            "last_edited_at": email.get("lastModifiedDateTime"),
                        }
                        all_emails.append(formatted_email)

                messages_url = email_data.get("@odata.nextLink")

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during Outlook extraction for user {user_id}: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during Outlook extraction for user {user_id}: {e}", exc_info=True)

    logger.info(f"Successfully extracted {len(all_emails)} emails from Outlook for user {user_id}.")
    return all_emails
