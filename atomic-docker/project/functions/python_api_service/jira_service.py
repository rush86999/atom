import os
import logging
from typing import Optional, Dict, Any
from jira import JIRA

logger = logging.getLogger(__name__)

async def get_jira_client(user_id: str, db_conn_pool) -> Optional[JIRA]:
    # This is a placeholder. In a real application, you would fetch the user's Jira credentials
    # from a secure database. For now, we'll use environment variables.
    # You'll need to create a table to store these credentials, similar to the Dropbox and Google Drive implementations.
    server = os.environ.get("JIRA_SERVER")
    email = os.environ.get("JIRA_EMAIL")
    token = os.environ.get("JIRA_TOKEN")

    if not all([server, email, token]):
        logger.error("Jira credentials are not configured in environment variables.")
        return None

    try:
        client = JIRA(server=server, basic_auth=(email, token))
        return client
    except Exception as e:
        logger.error(f"Failed to create Jira client: {e}", exc_info=True)
        return None

async def create_issue(client: JIRA, issue_data: Dict[str, Any]) -> Dict[str, Any]:
    issue = client.create_issue(fields=issue_data)
    return issue.raw

async def get_issue(client: JIRA, issue_id: str) -> Dict[str, Any]:
    issue = client.issue(issue_id)
    return issue.raw
