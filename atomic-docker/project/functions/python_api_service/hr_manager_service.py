import logging
from . import greenhouse_service
from . import bamboohr_service # We need to create this
from . import trello_service

logger = logging.getLogger(__name__)

async def create_bamboohr_employee_from_greenhouse_candidate(user_id: str, greenhouse_candidate_id: str, db_conn_pool):
    """
    Creates a BambooHR employee from a Greenhouse candidate.
    """
    greenhouse_client = await greenhouse_service.get_greenhouse_client(user_id, db_conn_pool)
    if not greenhouse_client:
        raise Exception("Could not get authenticated Greenhouse client.")

    candidate = await greenhouse_service.get_candidate(greenhouse_client, greenhouse_candidate_id)

    bamboohr_client = await bamboohr_service.get_bamboohr_client(user_id, db_conn_pool)
    if not bamboohr_client:
        raise Exception("Could not get authenticated BambooHR client.")

    employee_data = {
        "firstName": candidate['first_name'],
        "lastName": candidate['last_name'],
        "homeEmail": candidate['email_addresses'][0]['value']
    }

    employee = await bamboohr_service.create_employee(bamboohr_client, employee_data)
    return employee

async def get_bamboohr_employee_summary(user_id: str, employee_id: str, db_conn_pool):
    """
    Gets a summary of a BambooHR employee.
    """
    bamboohr_client = await bamboohr_service.get_bamboohr_client(user_id, db_conn_pool)
    if not bamboohr_client:
        raise Exception("Could not get authenticated BambooHR client.")

    employee = await bamboohr_service.get_employee(bamboohr_client, employee_id)
    return employee

async def create_trello_card_from_bamboohr_employee(user_id: str, employee_id: str, trello_list_id: str, db_conn_pool):
    """
    Creates a Trello card for a new BambooHR employee.
    """
    bamboohr_client = await bamboohr_service.get_bamboohr_client(user_id, db_conn_pool)
    if not bamboohr_client:
        raise Exception("Could not get authenticated BambooHR client.")

    employee = await bamboohr_service.get_employee(bamboohr_client, employee_id)

    trello_api_key, trello_token = await trello_service.get_trello_credentials(user_id, db_conn_pool)
    if not trello_api_key or not trello_token:
        raise Exception("Could not get Trello credentials.")

    card_name = f"New Employee: {employee['firstName']} {employee['lastName']}"
    card_desc = f"**Employee ID:** {employee['id']}"

    card = await trello_service.create_card(trello_api_key, trello_token, trello_list_id, card_name, card_desc)
    return card
