"""
Trello Project Management API Routes
Complete Trello project management automation endpoints
"""

import os
import logging
import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Union
from flask import Blueprint, request, jsonify, Response
from werkzeug.exceptions import BadRequest, NotFound, InternalServerError
from functools import wraps

# Import Trello services
try:
    from trello_enhanced_service import trello_enhanced_service
    TRELLO_SERVICE_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Trello service not available: {e}")
    TRELLO_SERVICE_AVAILABLE = False

try:
    from trello_lancedb_ingestion_service import trello_lancedb_service
    TRELLO_LANCEDB_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Trello LanceDB service not available: {e}")
    TRELLO_LANCEDB_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
trello_project_workflow_bp = Blueprint('trello_project_workflow', __name__)

# Error handling decorator
def handle_trello_project_workflow_errors(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except BadRequest as e:
            logger.error(f"Bad request in {f.__name__}: {e}")
            return jsonify({
                'ok': False,
                'error': str(e),
                'error_type': 'bad_request'
            }), 400
        except NotFound as e:
            logger.error(f"Resource not found in {f.__name__}: {e}")
            return jsonify({
                'ok': False,
                'error': str(e),
                'error_type': 'not_found'
            }), 404
        except InternalServerError as e:
            logger.error(f"Internal server error in {f.__name__}: {e}")
            return jsonify({
                'ok': False,
                'error': str(e),
                'error_type': 'internal_server_error'
            }), 500
        except Exception as e:
            logger.error(f"Unexpected error in {f.__name__}: {e}")
            return jsonify({
                'ok': False,
                'error': str(e),
                'error_type': 'unexpected_error'
            }), 500
    return decorated_function

# User authentication decorator
def require_user_auth(f):
    @wraps(f)
    @handle_trello_project_workflow_errors
    def decorated_function(*args, **kwargs):
        data = request.get_json() if request.method == 'POST' else request.args
        user_id = data.get('user_id')
        if not user_id:
            raise BadRequest('user_id is required')
        
        # Add user_id to kwargs
        kwargs['user_id'] = user_id
        
        return f(*args, **kwargs)
    return decorated_function

# Trello API key validation decorator
def require_trello_auth(f):
    @wraps(f)
    @handle_trello_project_workflow_errors
    def decorated_function(*args, **kwargs):
        data = request.get_json() if request.method == 'POST' else request.args
        api_key = data.get('api_key') or os.getenv('TRELLO_API_KEY')
        oauth_token = data.get('oauth_token') or os.getenv('TRELLO_OAUTH_TOKEN')
        
        if not api_key or not oauth_token:
            raise BadRequest('Trello API key and OAuth token are required')
        
        # Add auth to kwargs
        kwargs['api_key'] = api_key
        kwargs['oauth_token'] = oauth_token
        
        return f(*args, **kwargs)
    return decorated_function

# Health Check
@trello_project_workflow_bp.route("/api/trello/project-workflow/health", methods=["GET"])
@handle_trello_project_workflow_errors
def health_check():
    """Trello project workflow health check"""
    return jsonify({
        "ok": True,
        "service": "trello_project_workflow",
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "trello_service": TRELLO_SERVICE_AVAILABLE,
            "lancedb_service": TRELLO_LANCEDB_AVAILABLE
        }
    })

# Board Management
@trello_project_workflow_bp.route("/api/trello/project-workflow/boards/list", methods=["POST"])
@handle_trello_project_workflow_errors
@require_user_auth
@require_trello_auth
def list_boards(user_id: str, api_key: str, oauth_token: str):
    """List Trello boards"""
    try:
        data = request.get_json()
        filter_param = data.get('filter', 'all')
        
        if not TRELLO_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Trello service not available"
            }), 503
        
        # Initialize service with provided credentials
        service = __import__('trello_enhanced_service', fromlist=['TrelloEnhancedService']).TrelloEnhancedService(api_key, oauth_token)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        boards = loop.run_until_complete(
            service.get_boards(user_id, filter_param)
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "boards": [board.to_dict() for board in boards],
            "total_boards": len(boards),
            "filters": {
                "filter": filter_param
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing Trello boards: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@trello_project_workflow_bp.route("/api/trello/project-workflow/boards/get", methods=["POST"])
@handle_trello_project_workflow_errors
@require_user_auth
@require_trello_auth
def get_board(user_id: str, api_key: str, oauth_token: str):
    """Get Trello board details"""
    try:
        data = request.get_json()
        board_id = data.get('board_id')
        include_lists = data.get('include_lists', True)
        include_cards = data.get('include_cards', True)
        include_members = data.get('include_members', True)
        
        if not board_id:
            raise BadRequest('board_id is required')
        
        if not TRELLO_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Trello service not available"
            }), 503
        
        # Initialize service
        service = __import__('trello_enhanced_service', fromlist=['TrelloEnhancedService']).TrelloEnhancedService(api_key, oauth_token)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        board = loop.run_until_complete(
            service.get_board(board_id, include_lists, include_cards, include_members)
        )
        loop.close()
        
        if board:
            return jsonify({
                "ok": True,
                "board": board.to_dict()
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Board not found",
                "error_type": "not_found"
            }), 404
        
    except Exception as e:
        logger.error(f"Error getting Trello board: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Card Management
@trello_project_workflow_bp.route("/api/trello/project-workflow/cards/list", methods=["POST"])
@handle_trello_project_workflow_errors
@require_user_auth
@require_trello_auth
def list_cards(user_id: str, api_key: str, oauth_token: str):
    """List Trello cards"""
    try:
        data = request.get_json()
        board_id = data.get('board_id')
        list_id = data.get('list_id')
        filter_param = data.get('filter', 'all')
        
        if not board_id and not list_id:
            raise BadRequest('board_id or list_id is required')
        
        if not TRELLO_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Trello service not available"
            }), 503
        
        # Initialize service
        service = __import__('trello_enhanced_service', fromlist=['TrelloEnhancedService']).TrelloEnhancedService(api_key, oauth_token)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        cards = loop.run_until_complete(
            service.get_cards(board_id, list_id, filter_param)
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "cards": [card.to_dict() for card in cards],
            "total_cards": len(cards),
            "filters": {
                "board_id": board_id,
                "list_id": list_id,
                "filter": filter_param
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing Trello cards: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@trello_project_workflow_bp.route("/api/trello/project-workflow/cards/get", methods=["POST"])
@handle_trello_project_workflow_errors
@require_user_auth
@require_trello_auth
def get_card(user_id: str, api_key: str, oauth_token: str):
    """Get Trello card details"""
    try:
        data = request.get_json()
        card_id = data.get('card_id')
        include_attachments = data.get('include_attachments', True)
        include_checklists = data.get('include_checklists', True)
        include_members = data.get('include_members', True)
        
        if not card_id:
            raise BadRequest('card_id is required')
        
        if not TRELLO_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Trello service not available"
            }), 503
        
        # Initialize service
        service = __import__('trello_enhanced_service', fromlist=['TrelloEnhancedService']).TrelloEnhancedService(api_key, oauth_token)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        card = loop.run_until_complete(
            service.get_card(card_id, include_attachments, include_checklists, include_members)
        )
        loop.close()
        
        if card:
            return jsonify({
                "ok": True,
                "card": card.to_dict()
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Card not found",
                "error_type": "not_found"
            }), 404
        
    except Exception as e:
        logger.error(f"Error getting Trello card: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@trello_project_workflow_bp.route("/api/trello/project-workflow/cards/create", methods=["POST"])
@handle_trello_project_workflow_errors
@require_user_auth
@require_trello_auth
def create_card(user_id: str, api_key: str, oauth_token: str):
    """Create Trello card"""
    try:
        data = request.get_json()
        name = data.get('name')
        id_list = data.get('id_list')
        desc = data.get('description', '')
        due = data.get('due', '')
        id_members = data.get('id_members', [])
        id_labels = data.get('id_labels', [])
        pos = data.get('pos', 'bottom')
        address = data.get('address', '')
        url_source = data.get('url_source', '')
        file_source = data.get('file_source', '')
        id_card_source = data.get('id_card_source', '')
        
        if not name or not id_list:
            raise BadRequest('name and id_list are required')
        
        if not TRELLO_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Trello service not available"
            }), 503
        
        # Initialize service
        service = __import__('trello_enhanced_service', fromlist=['TrelloEnhancedService']).TrelloEnhancedService(api_key, oauth_token)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        card = loop.run_until_complete(
            service.create_card(
                name=name,
                id_list=id_list,
                desc=desc,
                due=due,
                id_members=id_members,
                id_labels=id_labels,
                pos=pos,
                address=address,
                url_source=url_source,
                file_source=file_source,
                id_card_source=id_card_source
            )
        )
        loop.close()
        
        if card:
            return jsonify({
                "ok": True,
                "card": card.to_dict(),
                "message": "Card created successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to create card",
                "error_type": "create_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error creating Trello card: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@trello_project_workflow_bp.route("/api/trello/project-workflow/cards/update", methods=["POST"])
@handle_trello_project_workflow_errors
@require_user_auth
@require_trello_auth
def update_card(user_id: str, api_key: str, oauth_token: str):
    """Update Trello card"""
    try:
        data = request.get_json()
        card_id = data.get('card_id')
        name = data.get('name')
        desc = data.get('description')
        due = data.get('due')
        closed = data.get('closed')
        pos = data.get('pos')
        due_complete = data.get('due_complete')
        id_members = data.get('id_members')
        id_labels = data.get('id_labels')
        
        if not card_id:
            raise BadRequest('card_id is required')
        
        if not TRELLO_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Trello service not available"
            }), 503
        
        # Initialize service
        service = __import__('trello_enhanced_service', fromlist=['TrelloEnhancedService']).TrelloEnhancedService(api_key, oauth_token)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        card = loop.run_until_complete(
            service.update_card(
                card_id=card_id,
                name=name,
                desc=desc,
                due=due,
                closed=closed,
                pos=pos,
                due_complete=due_complete,
                id_members=id_members,
                id_labels=id_labels
            )
        )
        loop.close()
        
        if card:
            return jsonify({
                "ok": True,
                "card": card.to_dict(),
                "message": "Card updated successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to update card",
                "error_type": "update_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error updating Trello card: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@trello_project_workflow_bp.route("/api/trello/project-workflow/cards/delete", methods=["POST"])
@handle_trello_project_workflow_errors
@require_user_auth
@require_trello_auth
def delete_card(user_id: str, api_key: str, oauth_token: str):
    """Delete Trello card"""
    try:
        data = request.get_json()
        card_id = data.get('card_id')
        
        if not card_id:
            raise BadRequest('card_id is required')
        
        if not TRELLO_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Trello service not available"
            }), 503
        
        # Initialize service
        service = __import__('trello_enhanced_service', fromlist=['TrelloEnhancedService']).TrelloEnhancedService(api_key, oauth_token)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(
            service.delete_card(card_id)
        )
        loop.close()
        
        if success:
            return jsonify({
                "ok": True,
                "message": "Card deleted successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to delete card",
                "error_type": "delete_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error deleting Trello card: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# List Management
@trello_project_workflow_bp.route("/api/trello/project-workflow/lists/get", methods=["POST"])
@handle_trello_project_workflow_errors
@require_user_auth
@require_trello_auth
def get_lists(user_id: str, api_key: str, oauth_token: str):
    """Get Trello lists from board"""
    try:
        data = request.get_json()
        board_id = data.get('board_id')
        include_cards = data.get('include_cards', False)
        
        if not board_id:
            raise BadRequest('board_id is required')
        
        if not TRELLO_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Trello service not available"
            }), 503
        
        # Initialize service
        service = __import__('trello_enhanced_service', fromlist=['TrelloEnhancedService']).TrelloEnhancedService(api_key, oauth_token)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        lists = loop.run_until_complete(
            service.get_lists(board_id, include_cards)
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "lists": [trello_list.to_dict() for trello_list in lists],
            "total_lists": len(lists),
            "filters": {
                "board_id": board_id,
                "include_cards": include_cards
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting Trello lists: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Member Management
@trello_project_workflow_bp.route("/api/trello/project-workflow/members/list", methods=["POST"])
@handle_trello_project_workflow_errors
@require_user_auth
@require_trello_auth
def list_members(user_id: str, api_key: str, oauth_token: str):
    """List Trello members"""
    try:
        data = request.get_json()
        board_id = data.get('board_id')
        include_boards = data.get('include_boards', False)
        
        if not TRELLO_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Trello service not available"
            }), 503
        
        # Initialize service
        service = __import__('trello_enhanced_service', fromlist=['TrelloEnhancedService']).TrelloEnhancedService(api_key, oauth_token)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        members = loop.run_until_complete(
            service.get_members(board_id, include_boards)
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "members": [member.to_dict() for member in members],
            "total_members": len(members),
            "filters": {
                "board_id": board_id,
                "include_boards": include_boards
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing Trello members: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Checklist Management
@trello_project_workflow_bp.route("/api/trello/project-workflow/checklists/create", methods=["POST"])
@handle_trello_project_workflow_errors
@require_user_auth
@require_trello_auth
def create_checklist(user_id: str, api_key: str, oauth_token: str):
    """Create Trello checklist"""
    try:
        data = request.get_json()
        name = data.get('name')
        id_card = data.get('id_card')
        check_items = data.get('check_items', [])
        
        if not name or not id_card:
            raise BadRequest('name and id_card are required')
        
        if not TRELLO_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Trello service not available"
            }), 503
        
        # Initialize service
        service = __import__('trello_enhanced_service', fromlist=['TrelloEnhancedService']).TrelloEnhancedService(api_key, oauth_token)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        checklist = loop.run_until_complete(
            service.create_checklist(
                name=name,
                id_card=id_card,
                check_items=check_items
            )
        )
        loop.close()
        
        if checklist:
            return jsonify({
                "ok": True,
                "checklist": checklist.to_dict(),
                "message": "Checklist created successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to create checklist",
                "error_type": "create_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error creating Trello checklist: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Label Management
@trello_project_workflow_bp.route("/api/trello/project-workflow/labels/create", methods=["POST"])
@handle_trello_project_workflow_errors
@require_user_auth
@require_trello_auth
def create_label(user_id: str, api_key: str, oauth_token: str):
    """Create Trello label"""
    try:
        data = request.get_json()
        name = data.get('name')
        color = data.get('color')
        id_board = data.get('id_board')
        
        if not name or not color or not id_board:
            raise BadRequest('name, color, and id_board are required')
        
        if not TRELLO_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Trello service not available"
            }), 503
        
        # Initialize service
        service = __import__('trello_enhanced_service', fromlist=['TrelloEnhancedService']).TrelloEnhancedService(api_key, oauth_token)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        label = loop.run_until_complete(
            service.create_label(
                name=name,
                color=color,
                id_board=id_board
            )
        )
        loop.close()
        
        if label:
            return jsonify({
                "ok": True,
                "label": label.to_dict(),
                "message": "Label created successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to create label",
                "error_type": "create_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error creating Trello label: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Search Operations
@trello_project_workflow_bp.route("/api/trello/project-workflow/search/cards", methods=["POST"])
@handle_trello_project_workflow_errors
@require_user_auth
@require_trello_auth
def search_cards(user_id: str, api_key: str, oauth_token: str):
    """Search Trello cards"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        id_boards = data.get('id_boards', [])
        id_cards = data.get('id_cards', [])
        id_labels = data.get('id_labels', [])
        id_members = data.get('id_members', [])
        limit = data.get('limit', 50)
        
        if not TRELLO_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Trello service not available"
            }), 503
        
        # Initialize service
        service = __import__('trello_enhanced_service', fromlist=['TrelloEnhancedService']).TrelloEnhancedService(api_key, oauth_token)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        cards = loop.run_until_complete(
            service.search_cards(
                query=query,
                id_boards=id_boards,
                id_cards=id_cards,
                id_labels=id_labels,
                id_members=id_members,
                limit=limit
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "cards": [card.to_dict() for card in cards],
            "count": len(cards),
            "search_filters": {
                "query": query,
                "id_boards": id_boards,
                "id_cards": id_cards,
                "id_labels": id_labels,
                "id_members": id_members,
                "limit": limit
            }
        })
        
    except Exception as e:
        logger.error(f"Error searching Trello cards: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@trello_project_workflow_bp.route("/api/trello/project-workflow/search/activities", methods=["POST"])
@handle_trello_project_workflow_errors
@require_user_auth
@require_trello_auth
def get_board_activities(user_id: str, api_key: str, oauth_token: str):
    """Get Trello board activities"""
    try:
        data = request.get_json()
        board_id = data.get('board_id')
        limit = data.get('limit', 50)
        before = data.get('before', '')
        since = data.get('since', '')
        
        if not board_id:
            raise BadRequest('board_id is required')
        
        if not TRELLO_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Trello service not available"
            }), 503
        
        # Initialize service
        service = __import__('trello_enhanced_service', fromlist=['TrelloEnhancedService']).TrelloEnhancedService(api_key, oauth_token)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        activities = loop.run_until_complete(
            service.get_board_activities(
                board_id=board_id,
                limit=limit,
                before=before,
                since=since
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "activities": [activity.to_dict() for activity in activities],
            "count": len(activities),
            "filters": {
                "board_id": board_id,
                "limit": limit,
                "before": before,
                "since": since
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting Trello board activities: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Memory Management
@trello_project_workflow_bp.route("/api/trello/project-workflow/memory/settings", methods=["POST"])
@handle_trello_project_workflow_errors
@require_user_auth
def get_memory_settings(user_id: str):
    """Get Trello memory settings for user"""
    try:
        if not TRELLO_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Trello LanceDB service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        settings = loop.run_until_complete(
            trello_lancedb_service.get_user_settings(user_id)
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "settings": {
                "user_id": settings.user_id,
                "ingestion_enabled": settings.ingestion_enabled,
                "sync_frequency": settings.sync_frequency,
                "data_retention_days": settings.data_retention_days,
                "include_boards": settings.include_boards or [],
                "exclude_boards": settings.exclude_boards or [],
                "include_archived_boards": settings.include_archived_boards,
                "include_cards": settings.include_cards,
                "include_lists": settings.include_lists,
                "include_members": settings.include_members,
                "include_checklists": settings.include_checklists,
                "include_labels": settings.include_labels,
                "include_attachments": settings.include_attachments,
                "include_activities": settings.include_activities,
                "max_cards_per_sync": settings.max_cards_per_sync,
                "max_activities_per_sync": settings.max_activities_per_sync,
                "sync_archived_cards": settings.sync_archived_cards,
                "sync_card_attachments": settings.sync_card_attachments,
                "index_card_content": settings.index_card_content,
                "search_enabled": settings.search_enabled,
                "semantic_search_enabled": settings.semantic_search_enabled,
                "metadata_extraction_enabled": settings.metadata_extraction_enabled,
                "board_tracking_enabled": settings.board_tracking_enabled,
                "member_analysis_enabled": settings.member_analysis_enabled,
                "last_sync_timestamp": settings.last_sync_timestamp,
                "next_sync_timestamp": settings.next_sync_timestamp,
                "sync_in_progress": settings.sync_in_progress,
                "error_message": settings.error_message,
                "created_at": settings.created_at,
                "updated_at": settings.updated_at
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting Trello memory settings: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@trello_project_workflow_bp.route("/api/trello/project-workflow/memory/settings", methods=["PUT"])
@handle_trello_project_workflow_errors
@require_user_auth
def save_memory_settings(user_id: str):
    """Save Trello memory settings for user"""
    try:
        data = request.get_json()
        
        if not TRELLO_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Trello LanceDB service not available"
            }), 503
        
        # Validate settings
        valid_frequencies = ["real-time", "hourly", "daily", "weekly", "manual"]
        sync_frequency = data.get('sync_frequency', 'hourly')
        if sync_frequency not in valid_frequencies:
            return jsonify({
                "ok": False,
                "error": f"Invalid sync frequency. Must be one of: {valid_frequencies}",
                "error_type": "validation_error"
            }), 400
        
        # Create settings object
        settings_class = __import__('trello_lancedb_ingestion_service', fromlist=['TrelloMemorySettings']).TrelloMemorySettings
        settings = settings_class(
            user_id=user_id,
            ingestion_enabled=data.get('ingestion_enabled', True),
            sync_frequency=sync_frequency,
            data_retention_days=data.get('data_retention_days', 365),
            include_boards=data.get('include_boards', []),
            exclude_boards=data.get('exclude_boards', []),
            include_archived_boards=data.get('include_archived_boards', False),
            include_cards=data.get('include_cards', True),
            include_lists=data.get('include_lists', True),
            include_members=data.get('include_members', True),
            include_checklists=data.get('include_checklists', True),
            include_labels=data.get('include_labels', True),
            include_attachments=data.get('include_attachments', True),
            include_activities=data.get('include_activities', True),
            max_cards_per_sync=data.get('max_cards_per_sync', 1000),
            max_activities_per_sync=data.get('max_activities_per_sync', 500),
            sync_archived_cards=data.get('sync_archived_cards', False),
            sync_card_attachments=data.get('sync_card_attachments', True),
            index_card_content=data.get('index_card_content', True),
            search_enabled=data.get('search_enabled', True),
            semantic_search_enabled=data.get('semantic_search_enabled', True),
            metadata_extraction_enabled=data.get('metadata_extraction_enabled', True),
            board_tracking_enabled=data.get('board_tracking_enabled', True),
            member_analysis_enabled=data.get('member_analysis_enabled', True)
        )
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(
            trello_lancedb_service.save_user_settings(settings)
        )
        loop.close()
        
        if success:
            return jsonify({
                "ok": True,
                "message": "Trello memory settings saved successfully",
                "settings": {
                    "user_id": settings.user_id,
                    "ingestion_enabled": settings.ingestion_enabled,
                    "sync_frequency": settings.sync_frequency,
                    "updated_at": settings.updated_at
                }
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to save Trello memory settings",
                "error_type": "save_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error saving Trello memory settings: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@trello_project_workflow_bp.route("/api/trello/project-workflow/memory/ingest", methods=["POST"])
@handle_trello_project_workflow_errors
@require_user_auth
def start_ingestion(user_id: str):
    """Start Trello data ingestion"""
    try:
        data = request.get_json()
        api_key = data.get('api_key') or os.getenv('TRELLO_API_KEY')
        oauth_token = data.get('oauth_token') or os.getenv('TRELLO_OAUTH_TOKEN')
        board_ids = data.get('board_ids', [])
        force_sync = data.get('force_sync', False)
        
        if not TRELLO_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Trello LanceDB service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            trello_lancedb_service.ingest_trello_data(
                user_id=user_id,
                api_key=api_key,
                oauth_token=oauth_token,
                force_sync=force_sync,
                board_ids=board_ids
            )
        )
        loop.close()
        
        if result.get('success'):
            return jsonify({
                "ok": True,
                "ingestion_result": {
                    "boards_ingested": result.get('boards_ingested', 0),
                    "cards_ingested": result.get('cards_ingested', 0),
                    "lists_ingested": result.get('lists_ingested', 0),
                    "members_ingested": result.get('members_ingested', 0),
                    "activities_ingested": result.get('activities_ingested', 0),
                    "checklists_ingested": result.get('checklists_ingested', 0),
                    "attachments_ingested": result.get('attachments_ingested', 0),
                    "total_size_mb": result.get('total_size_mb', 0),
                    "batch_id": result.get('batch_id'),
                    "next_sync": result.get('next_sync'),
                    "sync_frequency": result.get('sync_frequency')
                },
                "message": "Trello data ingestion completed successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": result.get('error', 'Unknown ingestion error'),
                "error_type": result.get('error_type', 'ingestion_error')
            }), 500
        
    except Exception as e:
        logger.error(f"Error starting Trello ingestion: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@trello_project_workflow_bp.route("/api/trello/project-workflow/memory/status", methods=["POST"])
@handle_trello_project_workflow_errors
@require_user_auth
def get_memory_status(user_id: str):
    """Get Trello memory synchronization status"""
    try:
        if not TRELLO_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Trello LanceDB service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        status = loop.run_until_complete(
            trello_lancedb_service.get_sync_status(user_id)
        )
        loop.close()
        
        if status.get('error'):
            return jsonify({
                "ok": False,
                "error": status.get('error'),
                "error_type": status.get('error_type', 'status_error')
            }), 500
        
        return jsonify({
            "ok": True,
            "memory_status": status
        })
        
    except Exception as e:
        logger.error(f"Error getting Trello memory status: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@trello_project_workflow_bp.route("/api/trello/project-workflow/memory/search/boards", methods=["POST"])
@handle_trello_project_workflow_errors
@require_user_auth
def search_memory_boards(user_id: str):
    """Search Trello boards in memory"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        closed = data.get('closed', None)
        limit = data.get('limit', 50)
        
        if not TRELLO_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Trello LanceDB service not available"
            }), 503
        
        # Validate limit
        limit = min(limit, 200)  # Max 200 results
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        boards = loop.run_until_complete(
            trello_lancedb_service.search_trello_boards(
                user_id=user_id,
                query=query,
                closed=closed,
                limit=limit
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "boards": boards,
            "count": len(boards),
            "search_filters": {
                "query": query,
                "closed": closed,
                "limit": limit
            }
        })
        
    except Exception as e:
        logger.error(f"Error searching Trello memory boards: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@trello_project_workflow_bp.route("/api/trello/project-workflow/memory/search/cards", methods=["POST"])
@handle_trello_project_workflow_errors
@require_user_auth
def search_memory_cards(user_id: str):
    """Search Trello cards in memory"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        board_id = data.get('board_id', None)
        list_id = data.get('list_id', None)
        member_id = data.get('member_id', None)
        label_name = data.get('label_name', None)
        closed = data.get('closed', None)
        limit = data.get('limit', 50)
        
        if not TRELLO_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Trello LanceDB service not available"
            }), 503
        
        # Validate limit
        limit = min(limit, 200)  # Max 200 results
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        cards = loop.run_until_complete(
            trello_lancedb_service.search_trello_cards(
                user_id=user_id,
                query=query,
                board_id=board_id,
                list_id=list_id,
                member_id=member_id,
                label_name=label_name,
                closed=closed,
                limit=limit
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "cards": cards,
            "count": len(cards),
            "search_filters": {
                "query": query,
                "board_id": board_id,
                "list_id": list_id,
                "member_id": member_id,
                "label_name": label_name,
                "closed": closed,
                "limit": limit
            }
        })
        
    except Exception as e:
        logger.error(f"Error searching Trello memory cards: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@trello_project_workflow_bp.route("/api/trello/project-workflow/memory/search/members", methods=["POST"])
@handle_trello_project_workflow_errors
@require_user_auth
def search_memory_members(user_id: str):
    """Search Trello members in memory"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        limit = data.get('limit', 50)
        
        if not TRELLO_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Trello LanceDB service not available"
            }), 503
        
        # Validate limit
        limit = min(limit, 200)  # Max 200 results
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        members = loop.run_until_complete(
            trello_lancedb_service.search_trello_members(
                user_id=user_id,
                query=query,
                limit=limit
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "members": members,
            "count": len(members),
            "search_filters": {
                "query": query,
                "limit": limit
            }
        })
        
    except Exception as e:
        logger.error(f"Error searching Trello memory members: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@trello_project_workflow_bp.route("/api/trello/project-workflow/memory/ingestion-stats", methods=["POST"])
@handle_trello_project_workflow_errors
@require_user_auth
def get_ingestion_stats(user_id: str):
    """Get Trello ingestion statistics"""
    try:
        if not TRELLO_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Trello LanceDB service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        stats = loop.run_until_complete(
            trello_lancedb_service.get_ingestion_stats(user_id)
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "ingestion_stats": {
                "user_id": stats.user_id,
                "total_boards_ingested": stats.total_boards_ingested,
                "total_cards_ingested": stats.total_cards_ingested,
                "total_lists_ingested": stats.total_lists_ingested,
                "total_members_ingested": stats.total_members_ingested,
                "total_activities_ingested": stats.total_activities_ingested,
                "total_checklists_ingested": stats.total_checklists_ingested,
                "total_attachments_ingested": stats.total_attachments_ingested,
                "last_ingestion_timestamp": stats.last_ingestion_timestamp,
                "total_size_mb": stats.total_size_mb,
                "failed_ingestions": stats.failed_ingestions,
                "last_error_message": stats.last_error_message,
                "avg_cards_per_board": stats.avg_cards_per_board,
                "avg_processing_time_ms": stats.avg_processing_time_ms,
                "created_at": stats.created_at,
                "updated_at": stats.updated_at
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting Trello ingestion stats: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@trello_project_workflow_bp.route("/api/trello/project-workflow/memory/delete", methods=["POST"])
@handle_trello_project_workflow_errors
@require_user_auth
def delete_user_data(user_id: str):
    """Delete all Trello data for user"""
    try:
        data = request.get_json()
        confirm = data.get('confirm', False)
        
        if not TRELLO_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Trello LanceDB service not available"
            }), 503
        
        if not confirm:
            return jsonify({
                "ok": False,
                "error": "Confirmation required to delete Trello data",
                "error_type": "confirmation_required"
            }), 400
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(
            trello_lancedb_service.delete_user_data(user_id)
        )
        loop.close()
        
        if success:
            return jsonify({
                "ok": True,
                "message": "All Trello data deleted successfully",
                "deleted_at": datetime.utcnow().isoformat()
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to delete Trello data",
                "error_type": "delete_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error deleting Trello user data: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Utility Endpoints
@trello_project_workflow_bp.route("/api/trello/project-workflow/service-info", methods=["GET"])
@handle_trello_project_workflow_errors
def get_service_info():
    """Get service information"""
    try:
        if TRELLO_SERVICE_AVAILABLE:
            service_info = trello_enhanced_service.get_service_info()
        else:
            service_info = {
                "name": "Enhanced Trello Service",
                "version": "1.0.0",
                "error": "Trello service not available"
            }
        
        return jsonify({
            "ok": True,
            "service_info": service_info,
            "lancedb_available": TRELLO_LANCEDB_AVAILABLE,
            "trello_service_available": TRELLO_SERVICE_AVAILABLE
        })
        
    except Exception as e:
        logger.error(f"Error getting Trello service info: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Export components
__all__ = [
    'trello_project_workflow_bp'
]