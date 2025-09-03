import logging
from . import salesforce_service
from . import jira_service # We need to create this
from . import trello_service

logger = logging.getLogger(__name__)

async def create_jira_issue_from_salesforce_case(user_id: str, salesforce_case_id: str, db_conn_pool):
    """
    Creates a Jira issue from a Salesforce case.
    """
    sf_client = await salesforce_service.get_salesforce_client(user_id, db_conn_pool)
    if not sf_client:
        raise Exception("Could not get authenticated Salesforce client.")

    salesforce_case = await salesforce_service.get_case(sf_client, salesforce_case_id)

    jira_client = await jira_service.get_jira_client(user_id, db_conn_pool)
    if not jira_client:
        raise Exception("Could not get authenticated Jira client.")

    issue_data = {
        "project": {"key": os.environ.get("JIRA_PROJECT_KEY")}, # You'll need to get this from the user
        "summary": salesforce_case['Subject'],
        "description": salesforce_case['Description'],
        "issuetype": {"name": "Task"} # This should be configurable
    }

    issue = await jira_service.create_issue(jira_client, issue_data)
    return issue

async def get_jira_issue_summary(user_id: str, issue_id: str, db_conn_pool):
    """
    Gets a summary of a Jira issue.
    """
    jira_client = await jira_service.get_jira_client(user_id, db_conn_pool)
    if not jira_client:
        raise Exception("Could not get authenticated Jira client.")

    issue = await jira_service.get_issue(jira_client, issue_id)
    return issue

async def create_trello_card_from_jira_issue(user_id: str, issue_id: str, trello_list_id: str, db_conn_pool):
    """
    Creates a Trello card for a new Jira issue.
    """
    jira_client = await jira_service.get_jira_client(user_id, db_conn_pool)
    if not jira_client:
        raise Exception("Could not get authenticated Jira client.")

    issue = await jira_service.get_issue(jira_client, issue_id)

    trello_api_key, trello_token = await trello_service.get_trello_credentials(user_id, db_conn_pool)
    if not trello_api_key or not trello_token:
        raise Exception("Could not get Trello credentials.")

    card_name = f"New Issue: {issue.fields.summary}"
    card_desc = f"**Issue ID:** {issue.key}\n**Link:** {issue.permalink()}"

    card = await trello_service.create_card(trello_api_key, trello_token, trello_list_id, card_name, card_desc)
    return card
