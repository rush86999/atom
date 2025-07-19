import logging
from . import salesforce_service
from . import mailchimp_service # We need to create this
from . import trello_service

logger = logging.getLogger(__name__)

async def create_mailchimp_campaign_from_salesforce_campaign(user_id: str, salesforce_campaign_id: str, db_conn_pool):
    """
    Creates a Mailchimp campaign from a Salesforce campaign.
    """
    sf_client = await salesforce_service.get_salesforce_client(user_id, db_conn_pool)
    if not sf_client:
        raise Exception("Could not get authenticated Salesforce client.")

    salesforce_campaign = await salesforce_service.get_campaign(sf_client, salesforce_campaign_id) # We need to add this to salesforce_service.py

    mailchimp_client = await mailchimp_service.get_mailchimp_client(user_id, db_conn_pool)
    if not mailchimp_client:
        raise Exception("Could not get authenticated Mailchimp client.")

    # This is a simplified implementation. In a real application, you would need to map the
    # Salesforce campaign members to a Mailchimp list. For now, we'll just create an empty campaign.
    campaign_data = {
        "type": "regular",
        "recipients": {"list_id": os.environ.get("MAILCHIMP_LIST_ID")}, # You'll need to get this from the user
        "settings": {
            "subject_line": salesforce_campaign['Name'],
            "from_name": "Atom Agent", # This should be configurable
            "reply_to": "test@test.com" # This should be configurable
        }
    }

    campaign = await mailchimp_service.create_campaign(mailchimp_client, campaign_data)
    return campaign

async def get_mailchimp_campaign_summary(user_id: str, campaign_id: str, db_conn_pool):
    """
    Gets a summary of a Mailchimp campaign.
    """
    mailchimp_client = await mailchimp_service.get_mailchimp_client(user_id, db_conn_pool)
    if not mailchimp_client:
        raise Exception("Could not get authenticated Mailchimp client.")

    report = await mailchimp_service.get_campaign_report(mailchimp_client, campaign_id)
    return report

async def create_trello_card_from_mailchimp_campaign(user_id: str, campaign_id: str, trello_list_id: str, db_conn_pool):
    """
    Creates a Trello card for a new Mailchimp campaign.
    """
    mailchimp_client = await mailchimp_service.get_mailchimp_client(user_id, db_conn_pool)
    if not mailchimp_client:
        raise Exception("Could not get authenticated Mailchimp client.")

    campaign = await mailchimp_service.get_campaign(mailchimp_client, campaign_id)

    trello_api_key, trello_token = await trello_service.get_trello_credentials(user_id, db_conn_pool)
    if not trello_api_key or not trello_token:
        raise Exception("Could not get Trello credentials.")

    card_name = f"New Campaign: {campaign['settings']['subject_line']}"
    card_desc = f"**Campaign Name:** {campaign['settings']['title']}\n**Link:** {campaign['long_archive_url']}"

    card = await trello_service.create_card(trello_api_key, trello_token, trello_list_id, card_name, card_desc)
    return card
