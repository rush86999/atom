import os
import json
import logging
from typing import List, Dict, Any
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
import httpx
import msal
from Crypto.Cipher import AES

# Configure logging
logger = logging.getLogger(__name__)

# --- Decryption Logic (Python equivalent of _utils/crypto.ts) ---
# NOTE: MSTEAMS_TOKEN_ENCRYPTION_KEY should be a 64-character hex string (32 bytes)
ENCRYPTION_KEY = os.getenv("MSTEAMS_TOKEN_ENCRYPTION_KEY")

def decrypt(encrypted_text: str, key: str) -> str:
    """
    Decrypts text encrypted by the corresponding TypeScript encrypt function.
    """
    if not key:
        raise ValueError("Encryption key is not set.")

    key_bytes = bytes.fromhex(key)
    parts = encrypted_text.split(':')
    iv = bytes.fromhex(parts[0])
    auth_tag = bytes.fromhex(parts[1])
    encrypted_data = bytes.fromhex(parts[2])

    cipher = AES.new(key_bytes, AES.MODE_GCM, iv)
    decrypted_data = cipher.decrypt_and_verify(encrypted_data, auth_tag)
    return decrypted_data.decode('utf-8')

# --- MSAL and Token Management ---
MSGRAPH_AUTHORITY = os.getenv("MSGRAPH_DELEGATED_AUTHORITY")
MSGRAPH_CLIENT_ID = os.getenv("MSGRAPH_DELEGATED_CLIENT_ID")
MSGRAPH_CLIENT_SECRET = os.getenv("MSGRAPH_DELEGATED_CLIENT_SECRET")
MSGRAPH_SCOPES = os.getenv("MSGRAPH_DELEGATED_SCOPES", "").split(" ")

async def get_msteams_oauth_token(user_id: str, db_conn_pool: Any) -> Dict[str, Any]:
    """
    Retrieves and refreshes the MS Teams OAuth token for a given user from the database.
    """
    conn = None
    try:
        conn = db_conn_pool.getconn()
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT encrypted_refresh_token, account_json FROM public.user_msteams_oauth_tokens WHERE user_id = %s",
                (user_id,)
            )
            record = cur.fetchone()
            if not record:
                logger.warning(f"No MS Teams token found for user {user_id}.")
                return {}

            refresh_token = decrypt(record["encrypted_refresh_token"], ENCRYPTION_KEY)
            account_info = json.loads(record["account_json"])

            app = msal.ConfidentialClientApplication(
                MSGRAPH_CLIENT_ID,
                authority=MSGRAPH_AUTHORITY,
                client_credential=MSGRAPH_CLIENT_SECRET,
            )

            result = app.acquire_token_by_refresh_token(
                refresh_token=refresh_token,
                scopes=MSGRAPH_SCOPES
            )

            if "access_token" in result:
                # TODO: Store the new access and refresh tokens in the database.
                return {"token": result["access_token"]}
            else:
                logger.error(f"Failed to refresh MS Teams token for user {user_id}: {result.get('error_description')}")
                return {}
    except Exception as e:
        logger.error(f"Error getting MS Teams token for user {user_id}: {e}", exc_info=True)
        return {}
    finally:
        if conn:
            db_conn_pool.putconn(conn)

# --- Data Extraction Logic ---
GRAPH_API_BASE_URL = "https://graph.microsoft.com/v1.0"

async def extract_data_from_msteams(user_id: str, db_conn_pool: Any) -> List[Dict[str, Any]]:
    """
    Extracts messages from Microsoft Teams channels for a given user.
    """
    logger.info(f"Starting MS Teams data extraction for user {user_id}.")

    token_data = await get_msteams_oauth_token(user_id, db_conn_pool)
    if not token_data or "token" not in token_data:
        logger.warning(f"No valid MS Teams credentials found for user {user_id}. Skipping extraction.")
        return []

    access_token = token_data["token"]
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
