import os
from git import Repo, GitCommandError
from datetime import datetime, timedelta
from typing import Dict, Any, List
import requests

class GitManager:
    """A manager for interacting with a Git repository."""

    def __init__(self, repo_path: str, github_token: str = None):
        if not os.path.isdir(repo_path):
            raise FileNotFoundError(f"Repository path does not exist: {repo_path}")
        self.repo_path = repo_path
        self.repo = Repo(repo_path)
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN")

    def get_commits_per_day(self, days_ago: int = 30) -> Dict[str, int]:
        """Calculates the number of commits per day for the last X days."""
        commits_per_day = {}
        since_date = datetime.now() - timedelta(days=days_ago)
        try:
            for commit in self.repo.iter_commits('master', since=since_date.isoformat()):
                commit_date = commit.authored_datetime.date().isoformat()
                commits_per_day[commit_date] = commits_per_day.get(commit_date, 0) + 1
        except GitCommandError as e:
            print(f"Error iterating commits: {e}")
        return commits_per_day

    def get_lines_of_code_changed(self, days_ago: int = 30) -> int:
        """Calculates the total lines of code changed in the last X days."""
        total_lines_changed = 0
        since_date = datetime.now() - timedelta(days=days_ago)
        try:
            for commit in self.repo.iter_commits('master', since=since_date.isoformat()):
                stats = commit.stats.total
                total_lines_changed += stats.get('lines', 0)
        except GitCommandError as e:
            print(f"Error calculating lines of code changed: {e}")
        return total_lines_changed

    def get_pull_request_comments(self, repo_name: str, days_ago: int = 30) -> int:
        """
        Fetches the number of comments on pull requests from the GitHub API.
        Note: This requires the repository to be on GitHub.
        """
        if not self.github_token:
            print("GITHUB_TOKEN is not set. Cannot fetch pull request comments.")
            return 0

        comments_count = 0
        since_date = (datetime.now() - timedelta(days=days_ago)).isoformat()
        url = f"https://api.github.com/repos/{repo_name}/pulls/comments"
        headers = {"Authorization": f"token {self.github_token}"}
        params = {"since": since_date, "per_page": 100}

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            comments = response.json()
            comments_count = len(comments)
            # Add logic for pagination if necessary
        except requests.exceptions.RequestException as e:
            print(f"Error fetching pull request comments from GitHub: {e}")
        return comments_count

def get_git_data(repo_path: str, repo_name: str = None) -> Dict[str, Any]:
    """
    Fetches and processes data from a Git repository to assess project health.

    Args:
        repo_path: The local path to the Git repository.
        repo_name: The name of the repository on GitHub (e.g., 'owner/repo').
                   Required for fetching pull request data.

    Returns:
        A dictionary containing Git data points for project health.
    """
    try:
        git_manager = GitManager(repo_path)

        commits_per_day = git_manager.get_commits_per_day()
        lines_of_code_changed = git_manager.get_lines_of_code_changed()

        pull_request_comments = 0
        if repo_name:
            pull_request_comments = git_manager.get_pull_request_comments(repo_name)

        return {
            "commits_per_day": commits_per_day,
            "pull_request_comments": pull_request_comments,
            "lines_of_code_changed": lines_of_code_changed,
        }
    except FileNotFoundError as e:
        print(f"Git repository not found at path: {repo_path}. Error: {e}")
        return {"error": str(e)}
    except Exception as e:
        print(f"An unexpected error occurred while processing Git data: {e}")
        return {"error": str(e)}
