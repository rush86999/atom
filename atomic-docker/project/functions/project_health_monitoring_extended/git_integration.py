import os
from git import Repo
from datetime import datetime, timedelta

def get_git_data(repo_path):
    """
    Fetches data from a Git repository.

    Args:
        repo_path: The path to the Git repository.

    Returns:
        A dictionary containing the Git data.
    """
    if not os.path.isdir(repo_path):
        raise Exception(f"Repository path does not exist: {repo_path}")

    repo = Repo(repo_path)

    commits_per_day = {}
    for commit in repo.iter_commits('master', since='30.days.ago'):
        commit_date = commit.authored_datetime.date()
        if commit_date in commits_per_day:
            commits_per_day[commit_date] += 1
        else:
            commits_per_day[commit_date] = 1

    # Placeholder for pull request comments and lines of code changes
    pull_request_comments = 0
    lines_of_code_changed = 0

    return {
        "commits_per_day": commits_per_day,
        "pull_request_comments": pull_request_comments,
        "lines_of_code_changed": lines_of_code_changed
    }
