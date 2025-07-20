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

    commits_today = 0
    today = datetime.now().date()
    for commit in repo.iter_commits('master', since='30.days.ago'):
        if commit.authored_datetime.date() == today:
            commits_today += 1

    # Placeholder for lines of code changes
    lines_of_code_changed = 0

    return {
        "commits_today": commits_today,
        "lines_of_code_changed": lines_of_code_changed
    }
