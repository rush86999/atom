import os
import logging
from typing import List, Dict, Any
import httpx

# Configure logging
logger = logging.getLogger(__name__)

# The URL for the new, centralized token service
TOKEN_SERVICE_URL = os.getenv("TOKEN_SERVICE_URL", "http://token-service:8080")

async def get_msteams_token_from_service(user_id: str) -> str | None:
    """
    Retrieves the MS Graph access token for a user by calling the token service.
    """
    try:
        async with httpx.AsyncClient() as client:
            # The service name 'msteams' is used to get the correct token from the generic service
            response = await client.get(f"{TOKEN_SERVICE_URL}/get-token/{user_id}/msteams")
            response.raise_for_status()
            return response.json().get("access_token")
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to get MS Teams token for user {user_id} from token service: {e.response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Error calling token service for MS Teams token: {e}", exc_info=True)
        return None


# --- Data Extraction Logic ---
GRAPH_API_BASE_URL = "https://graph.microsoft.com/v1.0"

async def extract_data_from_msteams(user_id: str, db_conn_pool: Any) -> List[Dict[str, Any]]:
    """
    Extracts messages from Microsoft Teams channels for a given user.
    """
    logger.info(f"Starting MS Teams data extraction for user {user_id}.")

    access_token = await get_msteams_token_from_service(user_id)
    if not access_token:
        logger.warning(f"No valid MS Teams credentials found for user {user_id}. Skipping extraction.")
        return []

    headers = {"Authorization": f"Bearer {access_token}"}
    all_messages = []

    async with httpx.AsyncClient() as client:
        try:
            # 1. Get joined teams
            teams_url = f"{GRAPH_API_BASE_URL}/me/joinedTeams"
            while teams_url:
                response = await client.get(teams_url, headers=headers)
                response.raise_for_status()
                teams_data = response.json()

                for team in teams_data.get("value", []):
                    team_id = team["id"]

                    # 2. Get channels for each team
                    channels_url = f"{GRAPH_API_BASE_URL}/teams/{team_id}/channels"
                    while channels_url:
                        channel_response = await client.get(channels_url, headers=headers)
                        channel_response.raise_for_status()
                        channels_data = channel_response.json()

                        for channel in channels_data.get("value", []):
                            channel_id = channel["id"]
                            channel_name = channel.get("displayName", "unknown-channel")

                            # 3. Get messages for each channel
                            messages_url = f"{GRAPH_API_BASE_URL}/teams/{team_id}/channels/{channel_id}/messages"
                            while messages_url:
                                message_response = await client.get(messages_url, headers=headers)
                                message_response.raise_for_status()
                                messages_data = message_response.json()

                                for msg in messages_data.get("value", []):
                                    if msg.get("body", {}).get("content"):
                                        formatted_message = {
                                            "document_id": f"msteams:{channel_id}:{msg['id']}",
                                            "document_title": f"Message in #{channel_name}",
                                            "full_text": msg["body"]["content"],
                                            "source": "msteams",
                                            "user_id": user_id,
                                            "url": msg.get("webUrl"),
                                            "created_at": msg.get("createdDateTime"),
                                            "last_edited_at": msg.get("lastModifiedDateTime"),
                                        }
                                        all_messages.append(formatted_message)

                                messages_url = messages_data.get("@odata.nextLink")

                        channels_url = channels_data.get("@odata.nextLink")

                teams_url = teams_data.get("@odata.nextLink")

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during MS Teams extraction for user {user_id}: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during MS Teams extraction for user {user_id}: {e}", exc_info=True)

    logger.info(f"Successfully extracted {len(all_messages)} messages from MS Teams for user {user_id}.")
    return all_messages
