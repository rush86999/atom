import os
import requests
from datetime import datetime

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

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        board_data = response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error fetching data from Trello: {e}")

    overdue_cards = 0
    for card in board_data["cards"]:
        if card["due"] and datetime.fromisoformat(card["due"][:-1]) < datetime.now():
            overdue_cards += 1

    list_movement_times = []
    for card in board_data["cards"]:
        actions_url = f"https://api.trello.com/1/cards/{card['id']}/actions"
        actions_params = {
            "key": api_key,
            "token": token,
            "filter": "updateCard:list"
        }
        actions_response = requests.get(actions_url, params=actions_params)
        actions_response.raise_for_status()
        actions = actions_response.json()

        if len(actions) > 1:
            for i in range(len(actions) - 1):
                time1 = datetime.fromisoformat(actions[i]["date"][:-1])
                time2 = datetime.fromisoformat(actions[i+1]["date"][:-1])
                list_movement_times.append((time1 - time2).total_seconds())

    comment_counts = []
    for card in board_data["cards"]:
        actions_url = f"https://api.trello.com/1/cards/{card['id']}/actions"
        actions_params = {
            "key": api_key,
            "token": token,
            "filter": "commentCard"
        }
        actions_response = requests.get(actions_url, params=actions_params)
        actions_response.raise_for_status()
        actions = actions_response.json()
        comment_counts.append(len(actions))

    return {
        "overdue_cards": overdue_cards,
        "average_list_movement_time": sum(list_movement_times) / len(list_movement_times) if list_movement_times else 0,
        "average_comment_count": sum(comment_counts) / len(comment_counts) if comment_counts else 0
    }
