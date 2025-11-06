from fastapi import APIRouter, HTTPException, Depends, Query, Body
from typing import Dict, List, Any, Optional
import logging
import asyncio
from datetime import datetime
import os
import sys

# Add the parent directory to the path to import from python-api-service
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "python-api-service"))

from trello_enhanced_service import TrelloEnhancedService
# TrelloHandler is not available, using only TrelloEnhancedService

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/integrations/trello", tags=["trello"])

# Service instances
trello_service = TrelloEnhancedService()


@router.get("/health")
async def trello_health():
    """Health check for Trello integration"""
    try:
        # Check if required environment variables are set
        api_key = os.getenv("TRELLO_API_KEY")
        oauth_token = os.getenv("TRELLO_OAUTH_TOKEN")

        service_info = await trello_service.get_service_info()

        return {
            "status": "healthy",
            "service": "trello",
            "timestamp": datetime.now().isoformat(),
            "service_available": True,
            "database_available": True,
            "api_key_configured": bool(api_key),
            "oauth_token_configured": bool(oauth_token),
            "service_info": service_info,
            "message": "Trello integration is operational",
        }
    except Exception as e:
        logger.error(f"Trello health check failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "service": "trello",
                "error": str(e),
                "message": "Trello integration is experiencing issues",
            },
        )


@router.post("/boards")
async def get_boards(
    user_id: str = Body(..., description="User ID"),
    include_closed: bool = Body(False, description="Include closed boards"),
    limit: int = Body(50, description="Maximum number of boards to return"),
    fields: List[str] = Body(
        ["name", "id", "desc", "url", "closed", "starred"],
        description="Fields to include",
    ),
):
    """Get all boards for a user"""
    try:
        logger.info(f"Fetching boards for user {user_id}")

        boards = await trello_service.get_boards(
            user_id=user_id, include_closed=include_closed, limit=limit, fields=fields
        )

        return {
            "ok": True,
            "data": {
                "boards": boards,
                "total_count": len(boards),
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(f"Failed to fetch boards for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": f"Failed to fetch boards: {str(e)}",
                "user_id": user_id,
            },
        )


@router.post("/boards/{board_id}")
async def get_board(
    board_id: str,
    user_id: str = Body(..., description="User ID"),
    fields: List[str] = Body(
        ["name", "id", "desc", "url", "closed", "starred", "prefs"],
        description="Fields to include",
    ),
):
    """Get specific board details"""
    try:
        logger.info(f"Fetching board {board_id} for user {user_id}")

        board = await trello_service.get_board(
            board_id=board_id, user_id=user_id, fields=fields
        )

        return {
            "ok": True,
            "data": {
                "board": board,
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(f"Failed to fetch board {board_id} for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": f"Failed to fetch board: {str(e)}",
                "board_id": board_id,
                "user_id": user_id,
            },
        )


@router.post("/lists")
async def get_lists(
    user_id: str = Body(..., description="User ID"),
    board_id: str = Body(..., description="Board ID"),
    include_closed: bool = Body(False, description="Include closed lists"),
    limit: int = Body(100, description="Maximum number of lists to return"),
    fields: List[str] = Body(
        ["name", "id", "closed", "pos"], description="Fields to include"
    ),
):
    """Get lists for a specific board"""
    try:
        logger.info(f"Fetching lists for board {board_id} and user {user_id}")

        lists = await trello_service.get_lists(
            user_id=user_id,
            board_id=board_id,
            include_closed=include_closed,
            limit=limit,
            fields=fields,
        )

        return {
            "ok": True,
            "data": {
                "lists": lists,
                "total_count": len(lists),
                "board_id": board_id,
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(
            f"Failed to fetch lists for board {board_id} and user {user_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": f"Failed to fetch lists: {str(e)}",
                "board_id": board_id,
                "user_id": user_id,
            },
        )


@router.post("/cards")
async def get_cards(
    user_id: str = Body(..., description="User ID"),
    board_id: str = Body(None, description="Board ID"),
    list_id: str = Body(None, description="List ID"),
    include_archived: bool = Body(False, description="Include archived cards"),
    limit: int = Body(100, description="Maximum number of cards to return"),
    fields: List[str] = Body(
        ["name", "id", "desc", "due", "labels", "idList", "idBoard"],
        description="Fields to include",
    ),
):
    """Get cards from a board or list"""
    try:
        logger.info(
            f"Fetching cards for user {user_id}, board {board_id}, list {list_id}"
        )

        cards = await trello_service.get_cards(
            user_id=user_id,
            board_id=board_id,
            list_id=list_id,
            include_archived=include_archived,
            limit=limit,
            fields=fields,
        )

        return {
            "ok": True,
            "data": {
                "cards": cards,
                "total_count": len(cards),
                "board_id": board_id,
                "list_id": list_id,
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(f"Failed to fetch cards for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": f"Failed to fetch cards: {str(e)}",
                "user_id": user_id,
                "board_id": board_id,
                "list_id": list_id,
            },
        )


@router.post("/cards/{card_id}")
async def get_card(
    card_id: str,
    user_id: str = Body(..., description="User ID"),
    fields: List[str] = Body(
        ["name", "id", "desc", "due", "labels", "idList", "idBoard", "url"],
        description="Fields to include",
    ),
):
    """Get specific card details"""
    try:
        logger.info(f"Fetching card {card_id} for user {user_id}")

        card = await trello_service.get_card(
            card_id=card_id, user_id=user_id, fields=fields
        )

        return {
            "ok": True,
            "data": {
                "card": card,
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(f"Failed to fetch card {card_id} for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": f"Failed to fetch card: {str(e)}",
                "card_id": card_id,
                "user_id": user_id,
            },
        )


@router.post("/cards/create")
async def create_card(
    user_id: str = Body(..., description="User ID"),
    name: str = Body(..., description="Card name"),
    id_list: str = Body(..., description="List ID"),
    desc: str = Body("", description="Card description"),
    due: str = Body(None, description="Due date"),
    labels: List[str] = Body([], description="Label IDs"),
    card_type: str = Body("task", description="Card type (task, bug, feature, etc.)"),
):
    """Create a new card"""
    try:
        logger.info(f"Creating card '{name}' in list {id_list} for user {user_id}")

        # Map card type to appropriate labels/formatting
        card_data = {
            "name": name,
            "desc": desc,
            "idList": id_list,
            "due": due,
            "idLabels": labels,
        }

        # Add card type specific formatting
        if card_type in trello_service.card_types:
            formatted_name = f"[{trello_service.card_types[card_type].upper()}] {name}"
            card_data["name"] = formatted_name

        card = await trello_service.create_card(user_id=user_id, card_data=card_data)

        return {
            "ok": True,
            "data": {
                "card": card,
                "message": f"Card '{name}' created successfully",
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(f"Failed to create card for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": f"Failed to create card: {str(e)}",
                "user_id": user_id,
            },
        )


@router.put("/cards/{card_id}")
async def update_card(
    card_id: str,
    user_id: str = Body(..., description="User ID"),
    name: str = Body(None, description="Card name"),
    desc: str = Body(None, description="Card description"),
    due: str = Body(None, description="Due date"),
    id_list: str = Body(None, description="List ID"),
    labels: List[str] = Body(None, description="Label IDs"),
):
    """Update an existing card"""
    try:
        logger.info(f"Updating card {card_id} for user {user_id}")

        update_data = {}
        if name is not None:
            update_data["name"] = name
        if desc is not None:
            update_data["desc"] = desc
        if due is not None:
            update_data["due"] = due
        if id_list is not None:
            update_data["idList"] = id_list
        if labels is not None:
            update_data["idLabels"] = labels

        card = await trello_service.update_card(
            card_id=card_id, user_id=user_id, update_data=update_data
        )

        return {
            "ok": True,
            "data": {
                "card": card,
                "message": f"Card {card_id} updated successfully",
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(f"Failed to update card {card_id} for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": f"Failed to update card: {str(e)}",
                "card_id": card_id,
                "user_id": user_id,
            },
        )


@router.delete("/cards/{card_id}")
async def delete_card(card_id: str, user_id: str = Body(..., description="User ID")):
    """Delete a card"""
    try:
        logger.info(f"Deleting card {card_id} for user {user_id}")

        result = await trello_service.delete_card(card_id=card_id, user_id=user_id)

        return {
            "ok": True,
            "data": {
                "message": f"Card {card_id} deleted successfully",
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(f"Failed to delete card {card_id} for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": f"Failed to delete card: {str(e)}",
                "card_id": card_id,
                "user_id": user_id,
            },
        )


@router.post("/members")
async def get_members(
    user_id: str = Body(..., description="User ID"),
    board_id: str = Body(..., description="Board ID"),
    include_guests: bool = Body(False, description="Include guest members"),
    limit: int = Body(50, description="Maximum number of members to return"),
    fields: List[str] = Body(
        ["fullName", "username", "id", "avatarUrl", "memberType"],
        description="Fields to include",
    ),
):
    """Get members of a board"""
    try:
        logger.info(f"Fetching members for board {board_id} and user {user_id}")

        members = await trello_service.get_members(
            user_id=user_id,
            board_id=board_id,
            include_guests=include_guests,
            limit=limit,
            fields=fields,
        )

        return {
            "ok": True,
            "data": {
                "members": members,
                "total_count": len(members),
                "board_id": board_id,
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(
            f"Failed to fetch members for board {board_id} and user {user_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": f"Failed to fetch members: {str(e)}",
                "board_id": board_id,
                "user_id": user_id,
            },
        )


@router.post("/user/profile")
async def get_user_profile(user_id: str = Body(..., description="User ID")):
    """Get current user profile"""
    try:
        logger.info(f"Fetching user profile for {user_id}")

        # This would typically call the Trello API to get user profile
        # For now, return basic user info
        profile = {
            "user": {
                "id": user_id,
                "fullName": f"User {user_id}",
                "username": f"user_{user_id}",
                "email": f"user_{user_id}@example.com",
            },
            "enterprise": {
                "enterpriseName": "ATOM Platform",
                "enterpriseId": "atom-enterprise",
            },
        }

        return {"ok": True, "data": profile}
    except Exception as e:
        logger.error(f"Failed to fetch user profile for {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": f"Failed to fetch user profile: {str(e)}",
                "user_id": user_id,
            },
        )


@router.post("/search")
async def search_cards(
    user_id: str = Body(..., description="User ID"),
    query: str = Body(..., description="Search query"),
    type: str = Body("global", description="Search type (global, board, card)"),
    limit: int = Body(50, description="Maximum number of results"),
    board_id: str = Body(None, description="Board ID for board-specific search"),
):
    """Search for cards, boards, or members"""
    try:
        logger.info(f"Searching for '{query}' for user {user_id}")

        results = await trello_service.search_cards(
            user_id=user_id,
            query=query,
            search_type=type,
            limit=limit,
            board_id=board_id,
        )

        return {
            "ok": True,
            "data": {
                "results": results,
                "total_count": len(results),
                "query": query,
                "type": type,
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(f"Failed to search for '{query}' for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": f"Failed to search: {str(e)}",
                "query": query,
                "user_id": user_id,
            },
        )


@router.post("/activities")
async def get_board_activities(
    user_id: str = Body(..., description="User ID"),
    board_id: str = Body(..., description="Board ID"),
    limit: int = Body(50, description="Maximum number of activities"),
    since: str = Body(None, description="Filter activities since this date"),
):
    """Get recent activities for a board"""
    try:
        logger.info(f"Fetching activities for board {board_id} and user {user_id}")

        activities = await trello_service.get_board_activities(
            user_id=user_id, board_id=board_id, limit=limit, since=since
        )

        return {
            "ok": True,
            "data": {
                "activities": activities,
                "total_count": len(activities),
                "board_id": board_id,
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(
            f"Failed to fetch activities for board {board_id} and user {user_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": f"Failed to fetch activities: {str(e)}",
                "board_id": board_id,
                "user_id": user_id,
            },
        )


@router.get("/info")
async def get_service_info():
    """Get Trello service information"""
    try:
        service_info = await trello_service.get_service_info()

        return {
            "ok": True,
            "data": {
                "service": "trello",
                "version": "1.0.0",
                "info": service_info,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(f"Failed to get service info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"ok": False, "error": f"Failed to get service info: {str(e)}"},
        )
