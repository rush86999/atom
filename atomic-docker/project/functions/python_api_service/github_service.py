import os
import logging
from typing import Optional, Dict, Any
from github import Github, GithubException

logger = logging.getLogger(__name__)

async def get_github_client(user_id: str, db_conn_pool) -> Optional[Github]:
    # This is a placeholder. In a real application, you would fetch the user's GitHub credentials
    # from a secure database. For now, we'll use environment variables.
    # You'll need to create a table to store these credentials, similar to the Dropbox and Google Drive implementations.
    access_token = os.environ.get("GITHUB_ACCESS_TOKEN")

    if not access_token:
        logger.error("GitHub access token is not configured in environment variables.")
        return None

    try:
        client = Github(access_token)
        return client
    except Exception as e:
        logger.error(f"Failed to create GitHub client: {e}", exc_info=True)
        return None

async def create_issue(repo, issue_data: Dict[str, Any]):
    try:
        issue = repo.create_issue(**issue_data)
        return issue
    except GithubException as e:
        logger.error(f"Error creating GitHub issue: {e}", exc_info=True)
        raise

async def get_pull_request(repo, pr_number: int):
    try:
        pr = repo.get_pull(pr_number)
        return pr
    except GithubException as e:
        logger.error(f"Error getting GitHub pull request: {e}", exc_info=True)
        raise

async def get_issue(repo, issue_number: int):
    try:
        issue = repo.get_issue(issue_number)
        return issue
    except GithubException as e:
        logger.error(f"Error getting GitHub issue: {e}", exc_info=True)
        raise
