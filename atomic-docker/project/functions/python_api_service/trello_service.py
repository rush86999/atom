import os
import logging
from typing import Optional, Tuple, List, Dict, Any
import httpx

logger = logging.getLogger(__name__)

TRELLO_API_BASE_URL = "https://api.trello.com/1"

async def get_trello_credentials(user_id: str, db_conn_pool) -> Tuple[Optional[str], Optional[str]]:
    # This is a placeholder. In a real application, you would fetch the user's Trello API key and token
    # from a secure database. For now, we'll use environment variables.
    # You'll need to create a table to store these credentials, similar to the Dropbox and Google Drive implementations.
    api_key = os.environ.get("TRELLO_API_KEY")
    token = os.environ.get("TRELLO_OAUTH_TOKEN")
    return api_key, token

async def list_boards(api_key: str, token: str) -> Optional[List[Dict[str, Any]]]:
    async with httpx.AsyncClient() as client:
        url = f"{TRELLO_API_BASE_URL}/members/me/boards"
        params = {"key": api_key, "token": token, "fields": "id,name,url"}
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

async def list_lists(api_key: str, token: str, board_id: str) -> Optional[List[Dict[str, Any]]]:
    async with httpx.AsyncClient() as client:
        url = f"{TRELLO_API_BASE_URL}/boards/{board_id}/lists"
        params = {"key": api_key, "token": token, "fields": "id,name"}
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

async def list_cards(api_key: str, token: str, list_id: str) -> Optional[List[Dict[str, Any]]]:
    async with httpx.AsyncClient() as client:
        url = f"{TRELLO_API_BASE_URL}/lists/{list_id}/cards"
        params = {"key": api_key, "token": token, "fields": "id,name,desc,url"}
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

async def create_card(api_key: str, token: str, list_id: str, name: str, desc: Optional[str] = None) -> Optional[Dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        url = f"{TRELLO_API_BASE_URL}/cards"
        params = {"key": api_key, "token": token, "idList": list_id, "name": name}
        if desc:
            params["desc"] = desc
        response = await client.post(url, params=params)
        response.raise_for_status()
        return response.json()

async def move_card(api_key: str, token: str, card_id: str, new_list_id: str) -> Optional[Dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        url = f"{TRELLO_API_BASE_URL}/cards/{card_id}"
        params = {"key": api_key, "token": token, "idList": new_list_id}
        response = await client.put(url, params=params)
        response.raise_for_status()
        return response.json()
