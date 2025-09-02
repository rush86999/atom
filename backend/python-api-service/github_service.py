import os
import requests
from .db_utils import get_decrypted_credential

GITHUB_API_URL = "https://api.github.com"

def get_github_token(user_id):
    """
    Retrieves the GitHub token for a given user from the database.
    """
    return get_decrypted_credential(user_id, 'github')

def get_user_repositories(user_id):
    """
    Fetches the repositories for a given user from GitHub.
    """
    token = get_github_token(user_id)
    if not token:
        raise Exception("GitHub token not found for user.")

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    response = requests.get(f"{GITHUB_API_URL}/user/repos", headers=headers)
    response.raise_for_status()
    return response.json()

def create_repository(user_id, name, description):
    """
    Creates a new repository on GitHub for the given user.
    """
    token = get_github_token(user_id)
    if not token:
        raise Exception("GitHub token not found for user.")

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {
        "name": name,
        "description": description,
        "private": False
    }
    response = requests.post(f"{GITHUB_API_URL}/user/repos", headers=headers, json=data)
    response.raise_for_status()
    return response.json()
