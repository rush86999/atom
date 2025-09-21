# Mock Trello service implementation for development
# This provides mock implementations for Trello API functionality

from typing import Dict, Any, Optional, List
from mcp_base import MCPBase

class MockTrello:
    """Mock Trello client for development"""

    def __init__(self, api_key: str = None, api_secret: str = None, token: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.token = token

    def get_board(self, board_id: str) -> 'MockBoard':
        """Mock method to get a board"""
        return MockBoard(board_id)

    def get_card(self, card_id: str) -> 'MockCard':
        """Mock method to get a card"""
        return MockCard(card_id)

class MockBoard:
    """Mock Trello Board"""

    def __init__(self, board_id: str):
        self.id = board_id
        self.name = f"Mock Board {board_id}"

    def all_cards(self) -> List['MockCard']:
        """Mock method to get all cards"""
        return [
            MockCard("card_1", "Task 1", "todo"),
            MockCard("card_2", "Task 2", "inprogress"),
            MockCard("card_3", "Task 3", "done")
        ]

class MockCard:
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

class TrelloService(MCPBase):
    def __init__(self, client: MockTrello):
        self.client = client

    def list_files(
        self,
        board_id: str,
        query: Optional[str] = None,
        page_size: int = 100,
        page_token: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        try:
            board = self.client.get_board(board_id)
            if query:
                # Filter cards based on query
                cards = [card for card in board.all_cards() if query.lower() in card.name.lower()]
            else:
                cards = board.all_cards()

            # Convert to dict format
            files = [card.to_dict() for card in cards]

            return {
                "status": "success",
                "data": {
                    "files": files,
                    "nextPageToken": None
                }
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_file_metadata(
        self,
        file_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        try:
            card = self.client.get_card(file_id)
            return {
                "status": "success",
                "data": card.to_dict()
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def download_file(
        self,
        file_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        return {
            "status": "error",
            "message": "Download not directly supported for Trello cards."
        }

# Mock function to get Trello client (for compatibility with existing code)
def get_trello_client(api_key: str, api_secret: str, token: str) -> MockTrello:
    """Mock function to get Trello client"""
    return MockTrello(api_key, api_secret, token)
