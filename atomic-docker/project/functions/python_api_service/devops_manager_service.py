import logging
from . import jira_service
from . import github_service # We need to create this
from . import trello_service

logger = logging.getLogger(__name__)

async def create_github_issue_from_jira_issue(user_id: str, jira_issue_id: str, db_conn_pool):
    """
    Creates a GitHub issue from a Jira issue.
    """
    jira_client = await jira_service.get_jira_client(user_id, db_conn_pool)
    if not jira_client:
        raise Exception("Could not get authenticated Jira client.")

    jira_issue = await jira_service.get_issue(jira_client, jira_issue_id)

    github_client = await github_service.get_github_client(user_id, db_conn_pool)
    if not github_client:
        raise Exception("Could not get authenticated GitHub client.")

    repo = github_client.get_repo(os.environ.get("GITHUB_REPO")) # You'll need to get this from the user

    issue_data = {
        "title": jira_issue.fields.summary,
        "body": jira_issue.fields.description
    }

    issue = await github_service.create_issue(repo, issue_data)
    return issue

async def get_github_pull_request_status(user_id: str, pull_request_url: str, db_conn_pool):
    """
    Gets the status of a GitHub pull request.
    """
    github_client = await github_service.get_github_client(user_id, db_conn_pool)
    if not github_client:
        raise Exception("Could not get authenticated GitHub client.")

    repo_name = pull_request_url.split('/')[-3]
    pr_number = int(pull_request_url.split('/')[-1])

    repo = github_client.get_repo(repo_name)
    pr = await github_service.get_pull_request(repo, pr_number)
    return pr.state

async def create_trello_card_from_github_issue(user_id: str, issue_url: str, trello_list_id: str, db_conn_pool):
    """
    Creates a Trello card for a new GitHub issue.
    """
    github_client = await github_service.get_github_client(user_id, db_conn_pool)
    if not github_client:
        raise Exception("Could not get authenticated GitHub client.")

    repo_name = issue_url.split('/')[-3]
    issue_number = int(issue_url.split('/')[-1])

    repo = github_client.get_repo(repo_name)
    issue = await github_service.get_issue(repo, issue_number)

    trello_api_key, trello_token = await trello_service.get_trello_credentials(user_id, db_conn_pool)
    if not trello_api_key or not trello_token:
        raise Exception("Could not get Trello credentials.")

    card_name = f"New Issue: {issue.title}"
    card_desc = f"**Issue URL:** {issue.html_url}"

    card = await trello_service.create_card(trello_api_key, trello_token, trello_list_id, card_name, card_desc)
    return card
