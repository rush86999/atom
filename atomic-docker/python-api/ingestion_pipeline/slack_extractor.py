import os
import logging
from typing import List, Dict, Any
import psycopg2
import psycopg2.extras
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError
from datetime import datetime, timezone

# Configure logging
logger = logging.getLogger(__name__)

# In a production system, a secure way to handle secrets (like a decryption utility
# using AWS KMS or HashiCorp Vault) would be used here. For this implementation,
# we assume the token is not stored encrypted in the database.
async def get_slack_oauth_token(user_id: str, db_conn_pool: Any) -> Dict[str, Any]:
    """
    Retrieves the Slack OAuth token for a given user from the database.
    NOTE: This simplified version does not handle token decryption.
    """
    conn = None
    try:
        conn = db_conn_pool.getconn()
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT encrypted_access_token, team_id FROM public.user_slack_oauth_tokens WHERE user_id = %s",
                (user_id,)
            )
            record = cur.fetchone()
            if record:
                # We are assuming the token is stored as a plain string for now.
                # In a real implementation, this would be a call to a decryption service.
                access_token = record["encrypted_access_token"]
                if isinstance(access_token, bytes):
                    # If it were encrypted, it would be bytes. We'd decrypt it.
                    # For now, we'll just decode it assuming it's plain text stored as bytes.
                    access_token = access_token.decode('utf-8')

                logger.info(f"Successfully retrieved Slack token for user {user_id}.")
                return {"token": access_token, "team_id": record["team_id"]}
            else:
                logger.warning(f"No Slack token found for user {user_id}.")
                return {}
    except psycopg2.Error as e:
        logger.error(f"Database error while fetching Slack token for user {user_id}: {e}")
        return {}
    finally:
        if conn:
            db_conn_pool.putconn(conn)


async def extract_data_from_slack(user_id: str, db_conn_pool: Any) -> List[Dict[str, Any]]:
    """
    Extracts messages from public Slack channels for a given user.
    """
    logger.info(f"Starting Slack data extraction for user {user_id}.")

    token_data = await get_slack_oauth_token(user_id, db_conn_pool)
    if not token_data or "token" not in token_data:
        logger.warning(f"No Slack credentials found for user {user_id}. Skipping extraction.")
        return []

    access_token = token_data["token"]
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
