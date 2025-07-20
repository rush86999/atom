import os
import requests

def get_trello_data(board_id):
    """
    Fetches data from a Trello board.

    Args:
        board_id: The ID of the Trello board.

    Returns:
        A dictionary containing the Trello data.
    """
    api_key = os.environ.get("TRELLO_API_KEY")
    token = os.environ.get("TRELLO_TOKEN")

    if not api_key or not token:
        raise Exception("TRELLO_API_KEY and TRELLO_TOKEN environment variables are not set.")

    url = f"https://api.trello.com/1/boards/{board_id}"
    params = {
        "key": api_key,
        "token": token,
        "cards": "all",
        "lists": "all",
        "fields": "name,desc"
    }

    response = requests.get(url, params=params)
    response.raise_for_status()

    return response.json()
