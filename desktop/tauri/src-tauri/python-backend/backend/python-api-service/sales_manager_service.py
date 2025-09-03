import logging
from . import salesforce_service
from . import xero_service
from . import trello_service

logger = logging.getLogger(__name__)

async def create_xero_invoice_from_salesforce_opportunity(user_id: str, opportunity_id: str, db_conn_pool):
    """
    Creates a Xero invoice from a Salesforce opportunity.
    """
    sf_client = await salesforce_service.get_salesforce_client(user_id, db_conn_pool)
    if not sf_client:
        raise Exception("Could not get authenticated Salesforce client.")

    opportunity = await salesforce_service.get_opportunity(sf_client, opportunity_id)

    xero_client = await xero_service.get_xero_client(user_id, db_conn_pool)
    if not xero_client:
        raise Exception("Could not get authenticated Xero client.")

    # This is a simplified implementation. In a real application, you would need to map the
    # Salesforce account to a Xero contact. For now, we'll assume the contact already exists
    # in Xero with the same name as the Salesforce account.
    contacts = await xero_service.list_contacts(xero_client)
    xero_contact = next((c for c in contacts if c['Name'] == opportunity['Account']['Name']), None)

    if not xero_contact:
        raise Exception(f"Could not find a Xero contact with the name {opportunity['Account']['Name']}.")

    invoice_data = {
        "Type": "ACCREC",
        "Contact": {"ContactID": xero_contact['ContactID']},
        "LineItems": [
            {
                "Description": opportunity['Name'],
                "Quantity": 1,
                "UnitAmount": opportunity['Amount'],
                "AccountCode": "200" # This should be configured based on the user's Xero setup
            }
        ],
        "Status": "DRAFT"
    }

    invoice = await xero_service.create_invoice(xero_client, invoice_data)
    return invoice

async def create_trello_card_from_salesforce_opportunity(user_id: str, opportunity_id: str, trello_list_id: str, db_conn_pool):
    """
    Creates a Trello card for a new Salesforce opportunity.
    """
    sf_client = await salesforce_service.get_salesforce_client(user_id, db_conn_pool)
    if not sf_client:
        raise Exception("Could not get authenticated Salesforce client.")

    opportunity = await salesforce_service.get_opportunity(sf_client, opportunity_id)

    trello_api_key, trello_token = await trello_service.get_trello_credentials(user_id, db_conn_pool)
    if not trello_api_key or not trello_token:
        raise Exception("Could not get Trello credentials.")

    card_name = f"New Opportunity: {opportunity['Name']}"
    card_desc = f"**Account:** {opportunity['Account']['Name']}\n**Amount:** ${opportunity['Amount']}\n**Close Date:** {opportunity['CloseDate']}"

    card = await trello_service.create_card(trello_api_key, trello_token, trello_list_id, card_name, card_desc)
    return card

async def create_salesforce_contact_from_xero_contact(user_id: str, xero_contact_id: str, db_conn_pool):
    """
    Creates a Salesforce contact from a Xero contact.
    """
    xero_client = await xero_service.get_xero_client(user_id, db_conn_pool)
    if not xero_client:
        raise Exception("Could not get authenticated Xero client.")

    xero_contact = await xero_service.get_contact(xero_client, xero_contact_id)

    sf_client = await salesforce_service.get_salesforce_client(user_id, db_conn_pool)
    if not sf_client:
        raise Exception("Could not get authenticated Salesforce client.")

    contact_data = {
        'LastName': xero_contact['Name'],
        'Email': xero_contact.get('EmailAddress')
    }

    contact = await salesforce_service.create_contact(sf_client, **contact_data)
    return contact

async def get_open_opportunities_for_account(user_id: str, account_id: str, db_conn_pool):
    """
    Gets a list of all open opportunities for a specific account.
    """
    sf_client = await salesforce_service.get_salesforce_client(user_id, db_conn_pool)
    if not sf_client:
        raise Exception("Could not get authenticated Salesforce client.")

    query = f"SELECT Id, Name, StageName, Amount, CloseDate FROM Opportunity WHERE AccountId = '{account_id}' AND IsClosed = false"
    result = sf_client.query_all(query)
    return result['records']
