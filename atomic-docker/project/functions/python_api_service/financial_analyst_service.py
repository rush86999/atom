import logging
from . import xero_service
from . import quickbooks_service # We need to create this
from . import salesforce_service
from . import trello_service

logger = logging.getLogger(__name__)

async def get_financial_summary(user_id: str, db_conn_pool):
    """
    Gets a summary of financial data from Xero and QuickBooks.
    """
    xero_client = await xero_service.get_xero_client(user_id, db_conn_pool)
    if not xero_client:
        raise Exception("Could not get authenticated Xero client.")

    xero_invoices = await xero_service.list_invoices(xero_client)
    xero_bills = await xero_service.list_bills(xero_client)

    qb_client = await quickbooks_service.get_quickbooks_client(user_id, db_conn_pool)
    if not qb_client:
        raise Exception("Could not get authenticated QuickBooks client.")

    qb_invoices = await quickbooks_service.list_invoices(qb_client)
    qb_bills = await quickbooks_service.list_bills(qb_client)

    return {
        "xero": {
            "invoices": xero_invoices,
            "bills": xero_bills
        },
        "quickbooks": {
            "invoices": qb_invoices,
            "bills": qb_bills
        }
    }

async def create_salesforce_opportunity_from_xero_invoice(user_id: str, invoice_id: str, db_conn_pool):
    """
    Creates a Salesforce opportunity from a Xero invoice.
    """
    xero_client = await xero_service.get_xero_client(user_id, db_conn_pool)
    if not xero_client:
        raise Exception("Could not get authenticated Xero client.")

    invoice = await xero_service.get_invoice(xero_client, invoice_id) # We need to add this to xero_service.py

    sf_client = await salesforce_service.get_salesforce_client(user_id, db_conn_pool)
    if not sf_client:
        raise Exception("Could not get authenticated Salesforce client.")

    opportunity_data = {
        'Name': f"Invoice {invoice['InvoiceNumber']}",
        'StageName': 'Prospecting', # Or some other default
        'CloseDate': invoice['DueDateString'],
        'Amount': invoice['Total']
    }

    opportunity = await salesforce_service.create_opportunity(sf_client, **opportunity_data)
    return opportunity

async def create_trello_card_from_xero_invoice(user_id: str, invoice_id: str, trello_list_id: str, db_conn_pool):
    """
    Creates a Trello card for a new Xero invoice.
    """
    xero_client = await xero_service.get_xero_client(user_id, db_conn_pool)
    if not xero_client:
        raise Exception("Could not get authenticated Xero client.")

    invoice = await xero_service.get_invoice(xero_client, invoice_id)

    trello_api_key, trello_token = await trello_service.get_trello_credentials(user_id, db_conn_pool)
    if not trello_api_key or not trello_token:
        raise Exception("Could not get Trello credentials.")

    card_name = f"New Invoice: {invoice['InvoiceNumber']}"
    card_desc = f"**Contact:** {invoice['Contact']['Name']}\n**Amount:** ${invoice['Total']}\n**Due Date:** {invoice['DueDateString']}"

    card = await trello_service.create_card(trello_api_key, trello_token, trello_list_id, card_name, card_desc)
    return card
