import os
from git import Repo

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

    commit_count = repo.head.commit.count()

    return {
        "commit_count": commit_count
    }
