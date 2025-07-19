import logging
from typing import Optional
from . import linkedin_service
from . import greenhouse_service # We need to create this
from . import trello_service

logger = logging.getLogger(__name__)

async def create_greenhouse_candidate_from_linkedin_profile(user_id: str, linkedin_profile_url: Optional[str] = None, search_query: Optional[str] = None, db_conn_pool):
    """
    Creates a Greenhouse candidate from a LinkedIn profile.
    """
    linkedin_api = await linkedin_service.get_linkedin_api(user_id, db_conn_pool)
    if not linkedin_api:
        raise Exception("Could not get authenticated LinkedIn client.")

    if not linkedin_profile_url and search_query:
        profiles = await linkedin_service.search_linkedin_profiles(linkedin_api, search_query)
        if not profiles:
            raise Exception("No LinkedIn profiles found for the given search query.")
        linkedin_profile_url = profiles[0]['public_profile_url']

    # This is a simplified implementation. In a real application, you would use a web scraper
    # to get the candidate's information from their LinkedIn profile.
    # For now, we'll just use the profile URL as the candidate's name.
    candidate_name = linkedin_profile_url.split('/')[-1]

    greenhouse_client = await greenhouse_service.get_greenhouse_client(user_id, db_conn_pool)
    if not greenhouse_client:
        raise Exception("Could not get authenticated Greenhouse client.")

    candidate_data = {
        "first_name": candidate_name,
        "last_name": "",
        "external_id": linkedin_profile_url
    }

    candidate = await greenhouse_service.create_candidate(greenhouse_client, candidate_data)
    return candidate

async def get_greenhouse_candidate_summary(user_id: str, candidate_id: str, db_conn_pool):
    """
    Gets a summary of a Greenhouse candidate.
    """
    greenhouse_client = await greenhouse_service.get_greenhouse_client(user_id, db_conn_pool)
    if not greenhouse_client:
        raise Exception("Could not get authenticated Greenhouse client.")

    candidate = await greenhouse_service.get_candidate(greenhouse_client, candidate_id)
    return candidate

async def create_trello_card_from_greenhouse_candidate(user_id: str, candidate_id: str, trello_list_id: str, db_conn_pool):
    """
    Creates a Trello card for a new Greenhouse candidate.
    """
    greenhouse_client = await greenhouse_service.get_greenhouse_client(user_id, db_conn_pool)
    if not greenhouse_client:
        raise Exception("Could not get authenticated Greenhouse client.")

    candidate = await greenhouse_service.get_candidate(greenhouse_client, candidate_id)

    trello_api_key, trello_token = await trello_service.get_trello_credentials(user_id, db_conn_pool)
    if not trello_api_key or not trello_token:
        raise Exception("Could not get Trello credentials.")

    card_name = f"New Candidate: {candidate['first_name']} {candidate['last_name']}"
    card_desc = f"**Candidate ID:** {candidate['id']}\n**Link:** {candidate['site_admin_url']}"

    card = await trello_service.create_card(trello_api_key, trello_token, trello_list_id, card_name, card_desc)
    return card
