import os
import base64
import logging
from typing import List, Dict, Any
import httpx
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timezone

# Configure logging
logger = logging.getLogger(__name__)

# The URL for the new, centralized token service
TOKEN_SERVICE_URL = os.getenv("TOKEN_SERVICE_URL", "http://token-service:8080")

async def get_gmail_token_from_service(user_id: str) -> str | None:
    """
    Retrieves the Gmail access token for a user by calling the token service.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{TOKEN_SERVICE_URL}/get-token/{user_id}/gmail")
            response.raise_for_status()
            return response.json().get("access_token")
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to get Gmail token for user {user_id} from token service: {e.response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Error calling token service for Gmail token: {e}", exc_info=True)
        return None

def get_email_body(parts):
    if not parts:
        return ""
    for part in parts:
        if part['mimeType'] == 'text/plain':
            return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
        elif part.get('parts'):
            return get_email_body(part['parts'])
    return ""

async def extract_data_from_gmail(user_id: str, db_conn_pool: Any) -> List[Dict[str, Any]]:
    logger.info(f"Starting Gmail data extraction for user {user_id}.")

    access_token = await get_gmail_token_from_service(user_id)
    if not access_token:
        logger.warning(f"No valid Gmail credentials found for user {user_id}. Skipping extraction.")
        return []

    creds = Credentials(token=access_token)
    all_emails = []
    try:
        service = build('gmail', 'v1', credentials=creds)

        request = service.users().messages().list(userId='me', maxResults=100)
        while request is not None:
            response = request.execute()
            messages = response.get('messages', [])

            for message_info in messages:
                msg_id = message_info['id']
                message = service.users().messages().get(userId='me', id=msg_id).execute()

                headers = {h['name']: h['value'] for h in message['payload']['headers']}
                subject = headers.get('Subject', 'No Subject')
                body = get_email_body(message['payload'].get('parts'))

                if body:
                    formatted_email = {
                        "document_id": f"gmail:{msg_id}",
                        "document_title": subject,
                        "full_text": body,
                        "source": "gmail",
                        "user_id": user_id,
                        "url": f"https://mail.google.com/mail/u/0/#inbox/{message['threadId']}",
                        "created_at": datetime.fromtimestamp(int(message['internalDate']) / 1000, tz=timezone.utc).isoformat(),
                        "last_edited_at": datetime.fromtimestamp(int(message['internalDate']) / 1000, tz=timezone.utc).isoformat(),
                    }
                    all_emails.append(formatted_email)

            request = service.users().messages().list_next(previous_request=request, previous_response=response)

    except Exception as e:
        logger.error(f"An unexpected error occurred during Gmail extraction for user {user_id}: {e}", exc_info=True)

    logger.info(f"Successfully extracted {len(all_emails)} emails from Gmail for user {user_id}.")
    return all_emails
