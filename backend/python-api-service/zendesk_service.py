import os
import logging
from typing import Optional, Dict, Any
from zenpy import Zenpy
from zenpy.lib.api_objects import Ticket, User

logger = logging.getLogger(__name__)

async def get_zendesk_client(user_id: str, db_conn_pool) -> Optional[Zenpy]:
    # This is a placeholder. In a real application, you would fetch the user's Zendesk credentials
    # from a secure database. For now, we'll use environment variables.
    # You'll need to create a table to store these credentials, similar to the Dropbox and Google Drive implementations.
    subdomain = os.environ.get("ZENDESK_SUBDOMAIN")
    email = os.environ.get("ZENDESK_EMAIL")
    token = os.environ.get("ZENDESK_TOKEN")

    if not all([subdomain, email, token]):
        logger.error("Zendesk credentials are not configured in environment variables.")
        return None

    creds = {
        'email': email,
        'token': token,
        'subdomain': subdomain
    }

    try:
        client = Zenpy(**creds)
        return client
    except Exception as e:
        logger.error(f"Failed to create Zendesk client: {e}", exc_info=True)
        return None

async def create_ticket(client: Zenpy, ticket_data: Dict[str, Any]) -> Ticket:
    ticket_audit = client.tickets.create(Ticket(**ticket_data))
    return ticket_audit.ticket

async def get_ticket(client: Zenpy, ticket_id: str) -> Ticket:
    ticket = client.tickets(id=ticket_id)
    return ticket

async def create_user(client: Zenpy, name: str, email: str) -> User:
    user = client.users.create(User(name=name, email=email))
    return user.user
