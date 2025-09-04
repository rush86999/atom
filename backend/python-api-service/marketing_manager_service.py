import logging
import salesforce_service
import mailchimp_service # We need to create this
import trello_service

logger = logging.getLogger(__name__)

import os
from typing import Optional

async def create_mailchimp_campaign_from_salesforce_campaign(user_id: str, salesforce_campaign_id: str, list_id: str, from_name: str, reply_to: str, template_id: Optional[int], db_conn_pool):
    """
    Creates a Mailchimp campaign from a Salesforce campaign.
    """
    sf_client = await salesforce_service.get_salesforce_client(user_id, db_conn_pool)
    if not sf_client:
        raise Exception("Could not get authenticated Salesforce client.")

    salesforce_campaign = await salesforce_service.get_campaign(sf_client, salesforce_campaign_id)

    mailchimp_client = await mailchimp_service.get_mailchimp_client(user_id, db_conn_pool)
    if not mailchimp_client:
        raise Exception("Could not get authenticated Mailchimp client.")

    campaign = await mailchimp_service.create_campaign(
        mailchimp_client,
        list_id,
        salesforce_campaign['Name'],
        from_name,
        reply_to,
        template_id
    )
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
