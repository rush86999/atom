import os
import requests
from datetime import datetime
from typing import List, Dict, Any

class TrelloManager:
    def __init__(self, api_key: str, token: str):
        self.api_key = api_key
        self.token = token
        self.base_url = "https://api.trello.com/1"

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Helper function to make requests to the Trello API."""
        url = f"{self.base_url}/{endpoint}"
        kwargs["params"] = kwargs.get("params", {})
        kwargs["params"]["key"] = self.api_key
        kwargs["params"]["token"] = self.token
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            # Log the error appropriately
            print(f"Error making request to Trello API: {e}")
            raise

    def get_board_data(self, board_id: str) -> Dict[str, Any]:
        """Fetches all cards and lists for a given board."""
        return self._make_request("GET", f"boards/{board_id}", params={"cards": "all", "lists": "all"})

    def get_card_actions(self, card_id: str, action_filter: str) -> List[Dict[str, Any]]:
        """Fetches actions for a given card."""
        return self._make_request("GET", f"cards/{card_id}/actions", params={"filter": action_filter})

def get_trello_data(board_id: str) -> Dict[str, Any]:
    """
    Fetches and processes data from a Trello board to assess project health.

    Args:
        board_id: The ID of the Trello board.

    Returns:
        A dictionary containing Trello data points for project health.
    """
    api_key = os.environ.get("TRELLO_API_KEY")
    token = os.environ.get("TRELLO_TOKEN")

    if not api_key or not token:
        raise ValueError("TRELLO_API_KEY and TRELLO_TOKEN environment variables must be set.")

    trello_manager = TrelloManager(api_key, token)

    try:
        board_data = trello_manager.get_board_data(board_id)
        cards = board_data.get("cards", [])

        overdue_cards = sum(1 for card in cards if card.get("due") and datetime.fromisoformat(card["due"][:-1]) < datetime.now())

        list_movement_times = []
        comment_counts = []

        for card in cards:
            card_id = card["id"]

            # Calculate list movement times
            list_updates = trello_manager.get_card_actions(card_id, "updateCard:list")
            if len(list_updates) > 1:
                # Sort actions by date descending to calculate time between movements
                list_updates.sort(key=lambda x: x["date"], reverse=True)
                for i in range(len(list_updates) - 1):
                    time1 = datetime.fromisoformat(list_updates[i]["date"][:-1])
                    time2 = datetime.fromisoformat(list_updates[i+1]["date"][:-1])
                    list_movement_times.append(abs((time1 - time2).total_seconds()))

            # Calculate comment counts
            comments = trello_manager.get_card_actions(card_id, "commentCard")
            comment_counts.append(len(comments))

        return {
            "overdue_cards": overdue_cards,
            "average_list_movement_time": sum(list_movement_times) / len(list_movement_times) if list_movement_times else 0,
            "average_comment_count": sum(comment_counts) / len(comment_counts) if comment_counts else 0,
        }
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch data from Trello for board {board_id}: {e}")
        # Return a default/error structure or re-raise a more specific exception
        return {
            "overdue_cards": -1,
            "average_list_movement_time": -1,
            "average_comment_count": -1,
            "error": str(e),
        }
    except Exception as e:
        print(f"An unexpected error occurred while processing Trello data: {e}")
        raise
