import logging
from . import twitter_service
from . import trello_service
from . import salesforce_service
from . import agenda_service # We'll need a way to schedule tasks

logger = logging.getLogger(__name__)

async def schedule_tweet(user_id: str, status: str, send_at: str, db_conn_pool):
    """
    Schedules a tweet to be posted at a later time.
    """
    # This is a simplified implementation. In a real application, you would use a proper
    # task scheduler like Celery or APScheduler to handle the scheduling.
    # For now, we'll just log the request.
    logger.info(f"Scheduling tweet for user {user_id} at {send_at}: {status}")

    # In a real implementation, you would do something like this:
    # agenda_service.schedule(send_at, 'post_tweet', {'user_id': user_id, 'status': status})

    return {"message": "Tweet scheduled successfully."}

async def monitor_twitter_mentions(user_id: str, trello_list_id: str, db_conn_pool):
    """
    Monitors Twitter mentions and adds them to a Trello board.
    """
    api = await twitter_service.get_twitter_api(user_id, db_conn_pool)
    if not api:
        raise Exception("Could not get authenticated Twitter client.")

    mentions = await twitter_service.get_mentions(api) # We need to add this to twitter_service.py

    trello_api_key, trello_token = await trello_service.get_trello_credentials(user_id, db_conn_pool)
    if not trello_api_key or not trello_token:
        raise Exception("Could not get Trello credentials.")

    for mention in mentions:
        card_name = f"New mention from @{mention.user.screen_name}"
        card_desc = f"{mention.text}\n\nhttps://twitter.com/{mention.user.screen_name}/status/{mention.id_str}"
        await trello_service.create_card(trello_api_key, trello_token, trello_list_id, card_name, card_desc)

    return {"message": "Mentions monitored successfully."}

async def create_salesforce_lead_from_tweet(user_id: str, tweet_id: str, db_conn_pool):
    """
    Creates a Salesforce lead from a Twitter user.
    """
    twitter_api = await twitter_service.get_twitter_api(user_id, db_conn_pool)
    if not twitter_api:
        raise Exception("Could not get authenticated Twitter client.")

    tweet = await twitter_service.get_tweet(twitter_api, tweet_id)
    twitter_user = tweet.user

    sf_client = await salesforce_service.get_salesforce_client(user_id, db_conn_pool)
    if not sf_client:
        raise Exception("Could not get authenticated Salesforce client.")

    lead_data = {
        'LastName': twitter_user.name,
        'Company': 'Twitter', # Or some other default
        'TwitterScreenName__c': twitter_user.screen_name # Requires a custom field in Salesforce
    }

    lead = await salesforce_service.create_lead(sf_client, lead_data) # We need to add this to salesforce_service.py

    return {"message": "Salesforce lead created successfully.", "lead_id": lead['id']}
