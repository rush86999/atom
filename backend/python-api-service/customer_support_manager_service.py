import logging
from . import salesforce_service
from . import zendesk_service # We need to create this
from . import trello_service

logger = logging.getLogger(__name__)

async def create_zendesk_ticket_from_salesforce_case(user_id: str, salesforce_case_id: str, db_conn_pool):
    """
    Creates a Zendesk ticket from a Salesforce case.
    """
    sf_client = await salesforce_service.get_salesforce_client(user_id, db_conn_pool)
    if not sf_client:
        raise Exception("Could not get authenticated Salesforce client.")

    salesforce_case = await salesforce_service.get_case(sf_client, salesforce_case_id) # We need to add this to salesforce_service.py

    zendesk_client = await zendesk_service.get_zendesk_client(user_id, db_conn_pool)
    if not zendesk_client:
        raise Exception("Could not get authenticated Zendesk client.")

    # This is a simplified implementation. In a real application, you would need to map the
    # Salesforce contact to a Zendesk user. For now, we'll just create a new user.
    zendesk_user = await zendesk_service.create_user(zendesk_client, salesforce_case['Contact']['Name'], salesforce_case['Contact']['Email'])

    ticket_data = {
        "ticket": {
            "subject": salesforce_case['Subject'],
            "comment": { "body": salesforce_case['Description'] },
            "requester_id": zendesk_user.id
        }
    }

    ticket = await zendesk_service.create_ticket(zendesk_client, ticket_data)
    return ticket

async def get_zendesk_ticket_summary(user_id: str, ticket_id: str, db_conn_pool):
    """
    Gets a summary of a Zendesk ticket.
    """
    zendesk_client = await zendesk_service.get_zendesk_client(user_id, db_conn_pool)
    if not zendesk_client:
        raise Exception("Could not get authenticated Zendesk client.")

    ticket = await zendesk_service.get_ticket(zendesk_client, ticket_id)
    return ticket

async def create_trello_card_from_zendesk_ticket(user_id: str, ticket_id: str, trello_list_id: str, db_conn_pool):
    """
    Creates a Trello card for a new Zendesk ticket.
    """
    zendesk_client = await zendesk_service.get_zendesk_client(user_id, db_conn_pool)
    if not zendesk_client:
        raise Exception("Could not get authenticated Zendesk client.")

    ticket = await zendesk_service.get_ticket(zendesk_client, ticket_id)

    trello_api_key, trello_token = await trello_service.get_trello_credentials(user_id, db_conn_pool)
    if not trello_api_key or not trello_token:
        raise Exception("Could not get Trello credentials.")

    card_name = f"New Ticket: {ticket.subject}"
    card_desc = f"**Ticket ID:** {ticket.id}\n**Link:** {ticket.url}"

    card = await trello_service.create_card(trello_api_key, trello_token, trello_list_id, card_name, card_desc)
    return card
