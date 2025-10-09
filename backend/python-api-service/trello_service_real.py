# Real Trello service implementation using py-trello
# This provides real implementations for Trello API functionality using frontend API keys

from typing import Dict, Any, Optional, List
from mcp_base import MCPBase
import os
import logging
from trello import TrelloClient

logger = logging.getLogger(__name__)


class RealTrelloService(MCPBase):
    def __init__(self, api_key: str, api_token: str):
        """Initialize real Trello client with API key and token from frontend"""
        self.client = TrelloClient(api_key=api_key, token=api_token)
        self.is_mock = False

    def list_files(
        self,
        board_id: str,
        query: Optional[str] = None,
        page_size: int = 100,
        page_token: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Get cards from a Trello board with optional search filtering"""
        try:
            # Get the board
            board = self.client.get_board(board_id)

            # Get all cards from the board
            cards = board.all_cards()

            # Filter cards based on query if provided
            if query:
                filtered_cards = [
                    card
                    for card in cards
                    if query.lower() in card.name.lower()
                    or (card.desc and query.lower() in card.desc.lower())
                ]
            else:
                filtered_cards = cards

            # Convert cards to dictionary format
            files = []
            for card in filtered_cards:
                files.append(
                    {
                        "id": card.id,
                        "name": card.name,
                        "description": card.desc,
                        "url": card.url,
                        "due_date": card.due_date.isoformat()
                        if card.due_date
                        else None,
                        "labels": [label.name for label in card.labels],
                        "list_name": card.list_name,
                        "closed": card.closed,
                        "date_last_activity": card.date_last_activity.isoformat()
                        if card.date_last_activity
                        else None,
                    }
                )

            # Simple pagination (Trello API has its own pagination, but we'll handle it simply)
            start_idx = int(page_token) if page_token else 0
            end_idx = start_idx + page_size
            paginated_files = files[start_idx:end_idx]

            next_page_token = str(end_idx) if end_idx < len(files) else None

            return {
                "status": "success",
                "data": {
                    "files": paginated_files,
                    "nextPageToken": next_page_token,
                    "total_count": len(files),
                },
            }
        except Exception as e:
            logger.error(f"Error listing Trello cards: {e}")
            return {"status": "error", "message": str(e)}

    def get_file_metadata(self, file_id: str, **kwargs) -> Dict[str, Any]:
        """Get detailed information about a specific Trello card"""
        try:
            card = self.client.get_card(file_id)

            return {
                "status": "success",
                "data": {
                    "id": card.id,
                    "name": card.name,
                    "description": card.desc,
                    "url": card.url,
                    "due_date": card.due_date.isoformat() if card.due_date else None,
                    "labels": [label.name for label in card.labels],
                    "list_name": card.list_name,
                    "closed": card.closed,
                    "date_last_activity": card.date_last_activity.isoformat()
                    if card.date_last_activity
                    else None,
                    "checklists": [
                        {
                            "name": checklist.name,
                            "items": [
                                {"name": item.name, "completed": item.checked}
                                for item in checklist.items
                            ],
                        }
                        for checklist in card.checklists
                    ],
                    "attachments": [
                        {
                            "name": attachment.name,
                            "url": attachment.url,
                            "date": attachment.date.isoformat()
                            if attachment.date
                            else None,
                        }
                        for attachment in card.attachments
                    ],
                },
            }
        except Exception as e:
            logger.error(f"Error getting Trello card metadata: {e}")
            return {"status": "error", "message": str(e)}

    def download_file(self, file_id: str, **kwargs) -> Dict[str, Any]:
        """Download functionality for Trello attachments (not directly for cards)"""
        try:
            card = self.client.get_card(file_id)

            # Check if card has attachments that could be downloaded
            if card.attachments:
                # For now, return attachment information rather than actual file content
                attachments_info = []
                for attachment in card.attachments:
                    attachments_info.append(
                        {
                            "id": attachment.id,
                            "name": attachment.name,
                            "url": attachment.url,
                            "bytes": attachment.bytes
                            if hasattr(attachment, "bytes")
                            else None,
                            "mime_type": attachment.mime_type
                            if hasattr(attachment, "mime_type")
                            else None,
                            "is_upload": attachment.is_upload,
                        }
                    )

                return {
                    "status": "success",
                    "data": {"card_name": card.name, "attachments": attachments_info},
                }
            else:
                return {
                    "status": "error",
                    "message": "No downloadable attachments found for this card",
                }
        except Exception as e:
            logger.error(f"Error downloading Trello file: {e}")
            return {"status": "error", "message": str(e)}

    def get_service_status(self) -> Dict[str, Any]:
        """Get service status information"""
        try:
            # Test connectivity by getting user info
            me = self.client.get_member("me")
            return {
                "status": "connected",
                "message": "Trello service connected successfully",
                "available": True,
                "mock_data": False,
                "user": me.full_name if hasattr(me, "full_name") else me.username,
            }
        except Exception as e:
            return {
                "status": "disconnected",
                "message": f"Trello service connection failed: {str(e)}",
                "available": False,
                "mock_data": False,
            }


# Function to get real Trello client
def get_real_trello_client(api_key: str, api_token: str) -> RealTrelloService:
    """Get real Trello service client with provided API key and token"""
    return RealTrelloService(api_key, api_token)
