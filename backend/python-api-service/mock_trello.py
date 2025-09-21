# Mock Trello module for development
# This provides mock implementations for Trello API functionality

from typing import Dict, Any, List, Optional

class Trello:
    """Mock Trello client for development"""

    def __init__(self, api_key: str = None, api_secret: str = None, token: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.token = token

    def get_board(self, board_id: str) -> 'Board':
        """Mock method to get a board"""
        return Board(board_id)

    def get_card(self, card_id: str) -> 'Card':
        """Mock method to get a card"""
        return Card(card_id)

class Board:
    """Mock Trello Board"""

    def __init__(self, board_id: str):
        self.id = board_id
        self.name = f"Mock Board {board_id}"

    def all_cards(self) -> List['Card']:
        """Mock method to get all cards"""
        return [
            Card("card_1", "Task 1", "todo"),
            Card("card_2", "Task 2", "inprogress"),
            Card("card_3", "Task 3", "done")
        ]

class Card:
    """Mock Trello Card"""

    def __init__(self, card_id: str, name: str = "Mock Card", status: str = "todo"):
        self.id = card_id
        self.name = name
        self.status = status
        self.desc = f"Description for {name}"
        self.url = f"https://trello.com/c/{card_id}"
        self.due = None
        self.labels = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert card to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "description": self.desc,
            "url": self.url,
            "due_date": self.due,
            "labels": self.labels
        }

# Mock functions for Trello service
def get_trello_client(api_key: str, api_secret: str, token: str) -> Trello:
    """Mock function to get Trello client"""
    return Trello(api_key, api_secret, token)

def list_boards(client: Trello) -> List[Dict[str, Any]]:
    """Mock function to list boards"""
    return [
        {"id": "board_1", "name": "Project Board", "url": "https://trello.com/b/board_1"},
        {"id": "board_2", "name": "Personal Tasks", "url": "https://trello.com/b/board_2"}
    ]

def list_cards(client: Trello, board_id: str) -> List[Dict[str, Any]]:
    """Mock function to list cards"""
    board = client.get_board(board_id)
    return [card.to_dict() for card in board.all_cards()]

def create_card(client: Trello, board_id: str, name: str, description: str = None) -> Dict[str, Any]:
    """Mock function to create card"""
    return {
        "id": f"new_card_{len(name)}",
        "name": name,
        "description": description or "",
        "status": "todo",
        "url": f"https://trello.com/c/new_card_{len(name)}"
    }
