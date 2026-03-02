"""
Obsidian Service for ATOM Platform
Provides interaction with Obsidian Local REST API
"""

import logging
import requests
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class ObsidianService:
    """Obsidian Local REST API integration service"""
    
    def __init__(self, api_token: Optional[str] = None, plugin_url: str = "http://localhost:27123"):
        self.api_token = api_token
        self.plugin_url = plugin_url.rstrip('/')
        self.session = requests.Session()
        
        if self.api_token:
            self.session.headers.update({
                'Authorization': f'Bearer {self.api_token}',
                'Content-Type': 'application/json',
                'User-Agent': 'ATOM-Platform/1.0'
            })
    
    def test_connection(self) -> Dict[str, Any]:
        """Test connection to Obsidian Local REST API"""
        try:
            response = self.session.get(f"{self.plugin_url}/")
            if response.status_code == 200:
                return {
                    "status": "success",
                    "message": "Obsidian connection successful",
                    "authenticated": True
                }
            else:
                return {
                    "status": "error",
                    "message": f"Connection failed: {response.status_code}",
                    "authenticated": False
                }
        except Exception as e:
            logger.error(f"Obsidian connection test failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "authenticated": False
            }
    
    def list_notes(self) -> List[str]:
        """List all notes in the vault"""
        try:
            response = self.session.get(f"{self.plugin_url}/active/")
            response.raise_for_status()
            return response.json().get('files', [])
        except Exception as e:
            logger.error(f"Failed to list Obsidian notes: {e}")
            return []
            
    def get_note(self, path: str) -> Optional[str]:
        """Get note content"""
        try:
            # Note: /vault/ endpoint returns raw text
            response = self.session.get(f"{self.plugin_url}/vault/{path.lstrip('/')}")
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Failed to get Obsidian note {path}: {e}")
            return None
            
    def create_note(self, path: str, content: str) -> bool:
        """Create or overwrite a note"""
        try:
            response = self.session.put(
                f"{self.plugin_url}/vault/{path.lstrip('/')}",
                data=content,
                headers={'Content-Type': 'text/markdown'}
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to create Obsidian note {path}: {e}")
            return False
            
    def append_note(self, path: str, content: str) -> bool:
        """Append content to a note"""
        try:
            response = self.session.post(
                f"{self.plugin_url}/vault/{path.lstrip('/')}",
                data=content,
                headers={'Content-Type': 'text/markdown'}
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to append to Obsidian note {path}: {e}")
            return False

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search notes"""
        try:
            response = self.session.post(
                f"{self.plugin_url}/search/",
                json={"query": query}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Obsidian search failed: {e}")
            return []
