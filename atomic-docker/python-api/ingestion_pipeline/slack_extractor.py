import os
import logging
from typing import List, Dict, Any
import httpx
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError
from datetime import datetime, timezone

# Configure logging
logger = logging.getLogger(__name__)

# The URL for the new, centralized token service
TOKEN_SERVICE_URL = os.getenv("TOKEN_SERVICE_URL", "http://token-service:8080")

async def get_slack_token_from_service(user_id: str) -> str | None:
    """
    Retrieves the Slack access token for a user by calling the token service.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{TOKEN_SERVICE_URL}/get-token/{user_id}/slack")
            response.raise_for_status()
            return response.json().get("access_token")
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to get Slack token for user {user_id} from token service: {e.response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Error calling token service for Slack token: {e}", exc_info=True)
        return None


async def extract_data_from_slack(user_id: str, db_conn_pool: Any) -> List[Dict[str, Any]]:
    """
    Extracts messages from public Slack channels for a given user.
    """
    logger.info(f"Starting Slack data extraction for user {user_id}.")

    access_token = await get_slack_token_from_service(user_id)
    if not access_token:
        logger.warning(f"No Slack credentials found for user {user_id}. Skipping extraction.")
        return []

    client = AsyncWebClient(token=access_token)
    all_messages = []

    try:
        # 1. Fetch list of public channels
        conv_response = await client.conversations_list(types="public_channel", limit=200)
        channels = conv_response.get("channels", [])
        logger.info(f"Found {len(channels)} public channels for user {user_id}.")

        for channel in channels:
            channel_id = channel["id"]
            channel_name = channel.get("name", "unknown-channel")
            logger.info(f"Fetching messages from channel: #{channel_name} ({channel_id})")

            # 2. For each channel, fetch message history
            history_response = await client.conversations_history(channel=channel_id, limit=100) # Using a limit, pagination would be needed for full history
            messages = history_response.get("messages", [])

            for msg in messages:
                # We only want to ingest actual user messages, not system events like joins/leaves.
                if msg.get("type") == "message" and msg.get("subtype") is None and "text" in msg:
                    msg_ts = msg["ts"]
                    created_dt = datetime.fromtimestamp(float(msg_ts), tz=timezone.utc)

                    # Check for an edited timestamp, otherwise use the creation timestamp
                    edited_ts = msg.get("edited", {}).get("ts")
                    last_edited_dt = datetime.fromtimestamp(float(edited_ts), tz=timezone.utc) if edited_ts else created_dt

                    # 3. Get a permalink for the message to provide a direct URL
                    try:
                        permalink_response = await client.chat_getPermalink(channel=channel_id, message_ts=msg_ts)
                        permalink = permalink_response.get("permalink", "")
                    except SlackApiError as permalink_error:
                        logger.warning(f"Could not get permalink for message {msg_ts} in channel {channel_id}: {permalink_error}")
                        permalink = ""

                    # 4. Format the message into the standard dictionary structure for the pipeline
                    formatted_message = {
                        "document_id": f"slack:{channel_id}:{msg_ts}",
                        "document_title": f"Message in #{channel_name}",
                        "full_text": msg.get("text", ""),
                        "source": "slack",
                        "user_id": user_id,
                        "url": permalink,
                        "created_at": created_dt.isoformat(),
                        "last_edited_at": last_edited_dt.isoformat(),
                    }
                    all_messages.append(formatted_message)

    except SlackApiError as e:
        logger.error(f"A Slack API error occurred during extraction for user {user_id}: {e.response['error']}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during Slack extraction for user {user_id}: {e}", exc_info=True)

    logger.info(f"Successfully extracted {len(all_messages)} messages from Slack for user {user_id}.")
    return all_messages
