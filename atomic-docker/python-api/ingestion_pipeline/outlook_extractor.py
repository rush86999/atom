import os
import logging
from typing import List, Dict, Any
import httpx

# Configure logging
logger = logging.getLogger(__name__)

# The URL for the new, centralized token service
TOKEN_SERVICE_URL = os.getenv("TOKEN_SERVICE_URL", "http://token-service:8080")

async def get_outlook_token_from_service(user_id: str) -> str | None:
    """
    Retrieves the MS Graph access token for a user by calling the token service.
    """
    try:
        async with httpx.AsyncClient() as client:
            # The service name 'msteams' is used here because both Teams and Outlook use the same MS Graph token.
            response = await client.get(f"{TOKEN_SERVICE_URL}/get-token/{user_id}/msteams")
            response.raise_for_status()
            return response.json().get("access_token")
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to get Outlook token for user {user_id} from token service: {e.response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Error calling token service for Outlook token: {e}", exc_info=True)
        return None


# --- Data Extraction Logic ---
GRAPH_API_BASE_URL = "https://graph.microsoft.com/v1.0"

async def extract_data_from_outlook(user_id: str, db_conn_pool: Any) -> List[Dict[str, Any]]:
    """
    Extracts emails from a user's Outlook account using the Microsoft Graph API.
    """
    logger.info(f"Starting Outlook data extraction for user {user_id}.")

    access_token = await get_outlook_token_from_service(user_id)
    if not access_token:
        logger.warning(f"No valid MS Graph credentials found for user {user_id}. Skipping Outlook extraction.")
        return []

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
