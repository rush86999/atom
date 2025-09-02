import logging
from . import salesforce_service
from . import docusign_service # We need to create this
from . import trello_service

logger = logging.getLogger(__name__)

async def create_docusign_envelope_from_salesforce_opportunity(user_id: str, salesforce_opportunity_id: str, db_conn_pool):
    """
    Creates a Docusign envelope from a Salesforce opportunity.
    """
    sf_client = await salesforce_service.get_salesforce_client(user_id, db_conn_pool)
    if not sf_client:
        raise Exception("Could not get authenticated Salesforce client.")

    opportunity = await salesforce_service.get_opportunity(sf_client, salesforce_opportunity_id)

    docusign_client = await docusign_service.get_docusign_client(user_id, db_conn_pool)
    if not docusign_client:
        raise Exception("Could not get authenticated Docusign client.")

    # This is a simplified implementation. In a real application, you would need to get the
    # document to be signed from a template or a file.
    # For now, we'll just create an empty envelope.
    envelope_definition = {
        "email_subject": f"Please sign this document for {opportunity['Name']}",
        "status": "sent",
        "recipients": {
            "signers": [
                {
                    "email": opportunity['Contact']['Email'],
                    "name": opportunity['Contact']['Name'],
                    "recipient_id": "1",
                    "routing_order": "1"
                }
            ]
        }
    }

    envelope = await docusign_service.create_envelope(docusign_client, envelope_definition)
    return envelope

async def get_docusign_envelope_status(user_id: str, envelope_id: str, db_conn_pool):
    """
    Gets the status of a Docusign envelope.
    """
    docusign_client = await docusign_service.get_docusign_client(user_id, db_conn_pool)
    if not docusign_client:
        raise Exception("Could not get authenticated Docusign client.")

    status = await docusign_service.get_envelope_status(docusign_client, envelope_id)
    return status

async def create_trello_card_from_docusign_envelope(user_id: str, envelope_id: str, trello_list_id: str, db_conn_pool):
    """
    Creates a Trello card for a new Docusign envelope.
    """
    docusign_client = await docusign_service.get_docusign_client(user_id, db_conn_pool)
    if not docusign_client:
        raise Exception("Could not get authenticated Docusign client.")

    envelope = await docusign_service.get_envelope(docusign_client, envelope_id)

    trello_api_key, trello_token = await trello_service.get_trello_credentials(user_id, db_conn_pool)
    if not trello_api_key or not trello_token:
        raise Exception("Could not get Trello credentials.")

    card_name = f"New Envelope: {envelope.email_subject}"
    card_desc = f"**Envelope ID:** {envelope.envelope_id}\n**Status:** {envelope.status}"

    card = await trello_service.create_card(trello_api_key, trello_token, trello_list_id, card_name, card_desc)
    return card
