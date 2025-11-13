"""
Trello Service for ATOM Platform
Provides comprehensive Trello integration functionality
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
import requests
from urllib.parse import urljoin, urlencode

logger = logging.getLogger(__name__)

class TrelloService:
    """Trello API integration service"""
    
    def __init__(self, api_key: Optional[str] = None, access_token: Optional[str] = None):
        self.api_key = api_key or os.getenv('TRELLO_API_KEY')
        self.access_token = access_token or os.getenv('TRELLO_ACCESS_TOKEN')
        self.base_url = "https://api.trello.com/1"
        
        if not all([self.api_key, self.access_token]):
            raise ValueError("Trello api_key and access_token are required")
        
        # Setup authentication parameters
        self.auth_params = {
            'key': self.api_key,
            'token': self.access_token
        }
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ATOM-Platform/1.0',
            'Accept': 'application/json'
        })
    
    def test_connection(self) -> Dict[str, Any]:
        """Test Trello API connection"""
        try:
            params = self.auth_params.copy()
            response = self.session.get(f"{self.base_url}/members/me", params=params)
            if response.status_code == 200:
                user_data = response.json()
                return {
                    "status": "success",
                    "message": "Trello connection successful",
                    "user": user_data.get('username', ''),
                    "full_name": user_data.get('fullName', ''),
                    "authenticated": True
                }
            else:
                return {
                    "status": "error", 
                    "message": f"Authentication failed: {response.status_code}",
                    "authenticated": False
                }
        except Exception as e:
            logger.error(f"Trello connection test failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "authenticated": False
            }
    
    def get_boards(self, filter: str = "open") -> List[Dict[str, Any]]:
        """Get boards for authenticated user"""
        try:
            params = self.auth_params.copy()
            params['filter'] = filter
            
            response = self.session.get(f"{self.base_url}/members/me/boards", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get boards: {e}")
            return []
    
    def get_board(self, board_id: str) -> Optional[Dict[str, Any]]:
        """Get specific board details"""
        try:
            params = self.auth_params.copy()
            response = self.session.get(f"{self.base_url}/boards/{board_id}", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get board {board_id}: {e}")
            return None
    
    def create_board(self, name: str, description: str = "", 
                   default_lists: bool = True) -> Optional[Dict[str, Any]]:
        """Create a new board"""
        try:
            params = self.auth_params.copy()
            params['name'] = name
            params['desc'] = description
            params['defaultLists'] = str(default_lists).lower()
            
            response = self.session.post(f"{self.base_url}/boards/", data=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to create board: {e}")
            return None
    
    def get_lists(self, board_id: str, filter: str = "open") -> List[Dict[str, Any]]:
        """Get lists on a board"""
        try:
            params = self.auth_params.copy()
            params['filter'] = filter
            
            response = self.session.get(f"{self.base_url}/boards/{board_id}/lists", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get lists for board {board_id}: {e}")
            return []
    
    def create_list(self, board_id: str, name: str, pos: str = "bottom") -> Optional[Dict[str, Any]]:
        """Create a new list on a board"""
        try:
            params = self.auth_params.copy()
            params['name'] = name
            params['pos'] = pos
            
            response = self.session.post(f"{self.base_url}/boards/{board_id}/lists", data=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to create list: {e}")
            return None
    
    def get_cards(self, list_id: str = None, board_id: str = None,
                  filter: str = "open") -> List[Dict[str, Any]]:
        """Get cards from list or board"""
        try:
            params = self.auth_params.copy()
            params['filter'] = filter
            
            if list_id:
                response = self.session.get(f"{self.base_url}/lists/{list_id}/cards", params=params)
            elif board_id:
                response = self.session.get(f"{self.base_url}/boards/{board_id}/cards", params=params)
            else:
                response = self.session.get(f"{self.base_url}/members/me/cards", params=params)
            
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get cards: {e}")
            return []
    
    def get_card(self, card_id: str) -> Optional[Dict[str, Any]]:
        """Get specific card details"""
        try:
            params = self.auth_params.copy()
            response = self.session.get(f"{self.base_url}/cards/{card_id}", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get card {card_id}: {e}")
            return None
    
    def create_card(self, name: str, list_id: str, description: str = "",
                   pos: str = "bottom", due: str = None, 
                   labels: List[str] = None, members: List[str] = None) -> Optional[Dict[str, Any]]:
        """Create a new card"""
        try:
            params = self.auth_params.copy()
            params['name'] = name
            params['idList'] = list_id
            params['desc'] = description
            params['pos'] = pos
            
            if due:
                params['due'] = due
            
            if labels:
                params['idLabels'] = ','.join(labels)
            
            if members:
                params['idMembers'] = ','.join(members)
            
            response = self.session.post(f"{self.base_url}/cards", data=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to create card: {e}")
            return None
    
    def update_card(self, card_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a card"""
        try:
            params = self.auth_params.copy()
            params.update(update_data)
            
            response = self.session.put(f"{self.base_url}/cards/{card_id}", data=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to update card {card_id}: {e}")
            return None
    
    def archive_card(self, card_id: str) -> bool:
        """Archive a card"""
        try:
            params = self.auth_params.copy()
            params['closed'] = 'true'
            
            response = self.session.put(f"{self.base_url}/cards/{card_id}", data=params)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to archive card {card_id}: {e}")
            return False
    
    def delete_card(self, card_id: str) -> bool:
        """Delete a card permanently"""
        try:
            params = self.auth_params.copy()
            response = self.session.delete(f"{self.base_url}/cards/{card_id}", params=params)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to delete card {card_id}: {e}")
            return False
    
    def add_comment(self, card_id: str, text: str) -> Optional[Dict[str, Any]]:
        """Add comment to card"""
        try:
            params = self.auth_params.copy()
            params['text'] = text
            
            response = self.session.post(
                f"{self.base_url}/cards/{card_id}/actions/comments",
                data=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to add comment to card {card_id}: {e}")
            return None
    
    def get_comments(self, card_id: str) -> List[Dict[str, Any]]:
        """Get comments for a card"""
        try:
            params = self.auth_params.copy()
            params['filter'] = 'commentCard'
            
            response = self.session.get(
                f"{self.base_url}/cards/{card_id}/actions",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get comments for card {card_id}: {e}")
            return []
    
    def get_checklists(self, card_id: str) -> List[Dict[str, Any]]:
        """Get checklists for a card"""
        try:
            params = self.auth_params.copy()
            response = self.session.get(
                f"{self.base_url}/cards/{card_id}/checklists",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get checklists for card {card_id}: {e}")
            return []
    
    def create_checklist(self, card_id: str, name: str) -> Optional[Dict[str, Any]]:
        """Create checklist on card"""
        try:
            params = self.auth_params.copy()
            params['name'] = name
            
            response = self.session.post(
                f"{self.base_url}/cards/{card_id}/checklists",
                data=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to create checklist for card {card_id}: {e}")
            return None
    
    def add_checklist_item(self, checklist_id: str, name: str, 
                         checked: bool = False) -> Optional[Dict[str, Any]]:
        """Add item to checklist"""
        try:
            params = self.auth_params.copy()
            params['name'] = name
            params['checked'] = str(checked).lower()
            
            response = self.session.post(
                f"{self.base_url}/checklists/{checklist_id}/checkItems",
                data=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to add checklist item: {e}")
            return None
    
    def move_card(self, card_id: str, list_id: str, pos: str = "bottom") -> Optional[Dict[str, Any]]:
        """Move card to different list"""
        return self.update_card(card_id, {'idList': list_id, 'pos': pos})
    
    def get_members(self, board_id: str) -> List[Dict[str, Any]]:
        """Get members of a board"""
        try:
            params = self.auth_params.copy()
            response = self.session.get(
                f"{self.base_url}/boards/{board_id}/members",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get members for board {board_id}: {e}")
            return []
    
    def add_member_to_card(self, card_id: str, member_id: str) -> Optional[Dict[str, Any]]:
        """Add member to card"""
        try:
            params = self.auth_params.copy()
            params['value'] = member_id
            
            response = self.session.post(
                f"{self.base_url}/cards/{card_id}/members",
                data=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to add member to card {card_id}: {e}")
            return None
    
    def remove_member_from_card(self, card_id: str, member_id: str) -> bool:
        """Remove member from card"""
        try:
            params = self.auth_params.copy()
            response = self.session.delete(
                f"{self.base_url}/cards/{card_id}/members/{member_id}",
                params=params
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to remove member from card {card_id}: {e}")
            return False
    
    def get_labels(self, board_id: str) -> List[Dict[str, Any]]:
        """Get labels for a board"""
        try:
            params = self.auth_params.copy()
            response = self.session.get(
                f"{self.base_url}/boards/{board_id}/labels",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get labels for board {board_id}: {e}")
            return []
    
    def create_label(self, board_id: str, name: str, color: str = None) -> Optional[Dict[str, Any]]:
        """Create a new label on board"""
        try:
            params = self.auth_params.copy()
            params['name'] = name
            
            if color:
                params['color'] = color
            
            response = self.session.post(
                f"{self.base_url}/boards/{board_id}/labels",
                data=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to create label: {e}")
            return None
    
    def add_label_to_card(self, card_id: str, label_id: str) -> Optional[Dict[str, Any]]:
        """Add label to card"""
        try:
            params = self.auth_params.copy()
            params['value'] = label_id
            
            response = self.session.post(
                f"{self.base_url}/cards/{card_id}/labels",
                data=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to add label to card {card_id}: {e}")
            return None
    
    def remove_label_from_card(self, card_id: str, label_id: str) -> bool:
        """Remove label from card"""
        try:
            params = self.auth_params.copy()
            response = self.session.delete(
                f"{self.base_url}/cards/{card_id}/labels/{label_id}",
                params=params
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to remove label from card {card_id}: {e}")
            return False

# Singleton instance for global access
trello_service = TrelloService()

def get_trello_service() -> TrelloService:
    """Get Trello service instance"""
    return trello_service