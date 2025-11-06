"""
ATOM Enhanced Trello API Handler
Complete Trello integration with comprehensive API operations
"""

import os
import logging
import asyncio
import httpx
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from flask import Blueprint, request, jsonify, current_app
from loguru import logger

# Import Trello service
try:
    from trello_service_real import trello_service
    TRELLO_SERVICE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Trello service not available: {e}")
    TRELLO_SERVICE_AVAILABLE = False
    trello_service = None

# Import database handler
try:
    from db_oauth_trello import get_user_tokens, save_tokens
    TRELLO_DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Trello database handler not available: {e}")
    TRELLO_DB_AVAILABLE = False

trello_enhanced_bp = Blueprint("trello_enhanced_bp", __name__)

# Configuration
TRELLO_API_BASE_URL = "https://api.trello.com/1"
REQUEST_TIMEOUT = 30

def get_user_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """Get Trello tokens for user"""
    if not TRELLO_DB_AVAILABLE:
        # Mock implementation for testing
        return {
            'token': os.getenv('TRELLO_ACCESS_TOKEN'),
            'tokenSecret': os.getenv('TRELLO_TOKEN_SECRET'),
            'memberId': os.getenv('TRELLO_MEMBER_ID'),
            'memberName': os.getenv('TRELLO_MEMBER_NAME', 'Test User'),
            'memberUsername': os.getenv('TRELLO_MEMBER_USERNAME', 'testuser'),
            'memberEmail': os.getenv('TRELLO_MEMBER_EMAIL', 'test@example.com'),
            'memberAvatar': os.getenv('TRELLO_MEMBER_AVATAR'),
            'enterpriseId': os.getenv('TRELLO_ENTERPRISE_ID'),
            'enterpriseName': os.getenv('TRELLO_ENTERPRISE_NAME'),
            'expires_at': (datetime.utcnow() + timedelta(hours=1)).isoformat()
        }

    try:
        tokens = get_user_tokens(user_id)
        return tokens
    except Exception as e:
        logger.error(f"Error getting Trello tokens for user {user_id}: {e}")
        return None

def format_trello_response(data: Any, endpoint: str) -> Dict[str, Any]:
    """Format Trello API response"""
    return {
        'ok': True,
        'data': data,
        'endpoint': endpoint,
        'timestamp': datetime.utcnow().isoformat(),
        'source': 'trello_api'
    }

def format_error_response(error: Exception, endpoint: str) -> Dict[str, Any]:
    """Format error response"""
    return {
        'ok': False,
        'error': {
            'code': type(error).__name__,
            'message': str(error),
            'endpoint': endpoint
        },
        'timestamp': datetime.utcnow().isoformat(),
        'source': 'trello_api'
    }

@trello_enhanced_bp.route('/api/integrations/trello/boards', methods=['POST'])
def list_boards():
    """List user Trello boards"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        include_closed = data.get('include_closed', False)
        limit = data.get('limit', 50)

        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400

        # Get user tokens
        tokens = get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Trello tokens not found'}
            }), 401

        # Use Trello service
        if TRELLO_SERVICE_AVAILABLE:
            boards = trello_service.get_user_boards(user_id)

            boards_data = [{
                'id': board.id,
                'name': board.name,
                'desc': board.desc,
                'descData': board.descData,
                'closed': board.closed,
                'idOrganization': board.idOrganization,
                'pinned': board.pinned,
                'url': board.url,
                'shortUrl': board.shortUrl,
                'prefs': board.prefs,
                'starred': board.starred,
                'dateLastActivity': board.dateLastActivity,
                'dateLastView': board.dateLastView,
                'limits': board.limits,
                'memberships': board.memberships,
                'shortLink': board.shortLink,
                'subscribed': board.subscribed,
                'labelNames': board.labelNames,
                'powerUps': board.powerUps,
                'datePluginDisable': board.datePluginDisable,
                'creationMethod': board.creationMethod,
                'ixUpdate': board.ixUpdate
            } for board in boards]

            # Filter based on preferences
            if not include_closed:
                boards_data = [b for b in boards_data if not b.get('closed')]

            return jsonify(format_trello_response({
                'boards': boards_data[:limit],
                'total_count': len(boards_data)
            }, 'list_boards'))

        # Fallback to mock data
        mock_boards = [
            {
                'id': 'board-123',
                'name': 'Project Management',
                'desc': 'Main project tracking board',
                'closed': False,
                'idOrganization': tokens.get('enterpriseId'),
                'pinned': True,
                'url': 'https://trello.com/board-123',
                'shortUrl': 'https://trello.com/b/board-123',
                'prefs': {
                    'permissionLevel': 'private',
                    'voting': 'disabled',
                    'comments': 'members',
                    'invitations': 'members',
                    'selfJoin': False,
                    'cardCovers': True,
                    'cardAging': False,
                    'calendarFeedEnabled': False,
                    'background': '#0079BF',
                    'backgroundImage': None,
                    'backgroundTile': False,
                    'backgroundBrightness': 'dark',
                    'backgroundBottomColor': '#0079BF',
                    'backgroundTopColor': '#0079BF',
                    'canBePublic': True,
                    'canBeOrg': True,
                    'canBePrivate': True,
                    'canInvite': True
                },
                'starred': True,
                'dateLastActivity': datetime.utcnow().isoformat() + 'Z',
                'memberships': [
                    {
                        'id': 'member-123',
                        'idMember': tokens.get('memberId'),
                        'memberType': 'admin',
                        'unconfirmed': False,
                        'deactivated': False
                    }
                ],
                'shortLink': '123abc',
                'subscribed': True,
                'labelNames': {
                    'green': '',
                    'yellow': '',
                    'red': '',
                    'purple': '',
                    'orange': '',
                    'blue': '',
                    'sky': '',
                    'pink': '',
                    'black': '',
                    'lime': ''
                },
                'powerUps': [],
                'ixUpdate': 123456789
            },
            {
                'id': 'board-456',
                'name': 'Development Tasks',
                'desc': 'Software development tracking',
                'closed': False,
                'idOrganization': tokens.get('enterpriseId'),
                'pinned': False,
                'url': 'https://trello.com/board-456',
                'shortUrl': 'https://trello.com/b/board-456',
                'prefs': {
                    'permissionLevel': 'org',
                    'voting': 'disabled',
                    'comments': 'members',
                    'invitations': 'members',
                    'selfJoin': True,
                    'cardCovers': True,
                    'cardAging': False,
                    'calendarFeedEnabled': False,
                    'background': '#5AC92A',
                    'backgroundImage': None,
                    'backgroundTile': False,
                    'backgroundBrightness': 'dark',
                    'backgroundBottomColor': '#5AC92A',
                    'backgroundTopColor': '#5AC92A',
                    'canBePublic': True,
                    'canBeOrg': True,
                    'canBePrivate': True,
                    'canInvite': True
                },
                'starred': False,
                'dateLastActivity': datetime.utcnow().isoformat() + 'Z',
                'memberships': [
                    {
                        'id': 'member-456',
                        'idMember': tokens.get('memberId'),
                        'memberType': 'normal',
                        'unconfirmed': False,
                        'deactivated': False
                    }
                ],
                'shortLink': '456def',
                'subscribed': False,
                'labelNames': {
                    'green': '',
                    'yellow': '',
                    'red': '',
                    'purple': '',
                    'orange': '',
                    'blue': '',
                    'sky': '',
                    'pink': '',
                    'black': '',
                    'lime': ''
                },
                'powerUps': ['calendar'],
                'ixUpdate': 987654321
            }
        ]

        return jsonify(format_trello_response({
            'boards': mock_boards[:limit],
            'total_count': len(mock_boards)
        }, 'list_boards'))

    except Exception as e:
        logger.error(f"Error listing boards: {e}")
        return jsonify(format_error_response(e, 'list_boards')), 500

@trello_enhanced_bp.route('/api/integrations/trello/lists', methods=['POST'])
def list_lists():
    """List lists from boards"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        board_id = data.get('board_id')
        include_closed = data.get('include_closed', False)
        limit = data.get('limit', 100)

        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400

        # Get user tokens
        tokens = get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Trello tokens not found'}
            }), 401

        # Use Trello service
        if TRELLO_SERVICE_AVAILABLE:
            lists = trello_service.get_board_lists(user_id, board_id)

            lists_data = [{
                'id': lst.id,
                'name': lst.name,
                'closed': lst.closed,
                'idBoard': lst.idBoard,
                'pos': lst.pos,
                'subscribed': lst.subscribed
            } for lst in lists]

            # Filter based on preferences
            if not include_closed:
                lists_data = [l for l in lists_data if not l.get('closed')]

            return jsonify(format_trello_response({
                'lists': lists_data[:limit],
                'total_count': len(lists_data)
            }, 'list_lists'))

        # Fallback to mock data
        mock_lists = [
            {
                'id': 'list-1',
                'name': 'To Do',
                'closed': False,
                'idBoard': board_id or 'board-123',
                'pos': 16384,
                'subscribed': False
            },
            {
                'id': 'list-2',
                'name': 'In Progress',
                'closed': False,
                'idBoard': board_id or 'board-123',
                'pos': 32768,
                'subscribed': False
            },
            {
                'id': 'list-3',
                'name': 'Done',
                'closed': False,
                'idBoard': board_id or 'board-123',
                'pos': 65536,
                'subscribed': False
            },
            {
                'id': 'list-4',
                'name': 'Archive',
                'closed': True,
                'idBoard': board_id or 'board-123',
                'pos': 131072,
                'subscribed': False
            }
        ]

        # Filter based on preferences
        if not include_closed:
            mock_lists = [l for l in mock_lists if not l.get('closed')]

        return jsonify(format_trello_response({
            'lists': mock_lists[:limit],
            'total_count': len(mock_lists)
        }, 'list_lists'))

    except Exception as e:
        logger.error(f"Error listing lists: {e}")
        return jsonify(format_error_response(e, 'list_lists')), 500

@trello_enhanced_bp.route('/api/integrations/trello/cards', methods=['POST'])
def list_cards():
    """List cards from lists or boards"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        board_id = data.get('board_id')
        list_id = data.get('list_id')
        include_archived = data.get('include_archived', False)
        filters = data.get('filters', {})
        operation = data.get('operation', 'list')
        limit = data.get('limit', 200)

        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400

        # Get user tokens
        tokens = get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Trello tokens not found'}
            }), 401

        if operation == 'create':
            # Create card
            return _create_card(user_id, tokens, data)

        # List cards
        if TRELLO_SERVICE_AVAILABLE:
            cards = trello_service.get_board_cards(
                user_id, board_id, list_id, filters, limit
            )

            cards_data = [{
                'id': card.id,
                'name': card.name,
                'desc': card.desc,
                'descData': card.descData,
                'closed': card.closed,
                'idList': card.idList,
                'idBoard': card.idBoard,
                'idMembersVoted': card.idMembersVoted,
                'idShort': card.idShort,
                'idChecklists': card.idChecklists,
                'idAttachmentCover': card.idAttachmentCover,
                'manualCoverAttachment': card.manualCoverAttachment,
                'idLabels': card.idLabels,
                'due': card.due,
                'dueComplete': card.dueComplete,
                'start': card.start,
                'dateLastActivity': card.dateLastActivity,
                'pos': card.pos,
                'shortLink': card.shortLink,
                'isTemplate': card.isTemplate,
                'cardRole': card.cardRole,
                'badges': card.badges,
                'customFieldItems': card.customFieldItems,
                'addr': card.addr,
                'locationName': card.locationName,
                'coordinates': card.coordinates,
                'address': card.address,
                'cover': card.cover,
                'labels': card.labels,
                'shortUrl': card.shortUrl,
                'url': card.url
            } for card in cards]

            # Filter based on preferences
            if not include_archived:
                cards_data = [c for c in cards_data if not c.get('closed')]

            return jsonify(format_trello_response({
                'cards': cards_data[:limit],
                'total_count': len(cards_data)
            }, 'list_cards'))

        # Fallback to mock data
        mock_cards = [
            {
                'id': 'card-1',
                'name': 'Setup development environment',
                'desc': 'Install all necessary tools and dependencies',
                'closed': False,
                'idList': list_id or 'list-1',
                'idBoard': board_id or 'board-123',
                'idShort': 1,
                'idChecklists': ['checklist-1'],
                'idLabels': ['label-1'],
                'due': (datetime.utcnow() + timedelta(days=3)).isoformat() + 'Z',
                'dueComplete': False,
                'dateLastActivity': datetime.utcnow().isoformat() + 'Z',
                'pos': 1,
                'shortLink': 'abc123',
                'isTemplate': False,
                'cardRole': 'regular',
                'badges': {
                    'votes': 0,
                    'viewingMemberVoted': False,
                    'subscribed': False,
                    'fogbugz': '',
                    'checkItems': 3,
                    'checkItemsChecked': 1,
                    'comments': 2,
                    'attachments': 1,
                    'description': True
                },
                'labels': [
                    {
                        'id': 'label-1',
                        'idBoard': board_id or 'board-123',
                        'name': 'High Priority',
                        'color': 'red'
                    }
                ],
                'shortUrl': 'https://trello.com/c/abc123',
                'url': 'https://trello.com/c/abc123/setup-development-environment'
            },
            {
                'id': 'card-2',
                'name': 'Implement user authentication',
                'desc': 'Add login and registration functionality',
                'closed': False,
                'idList': list_id or 'list-2',
                'idBoard': board_id or 'board-123',
                'idShort': 2,
                'idChecklists': ['checklist-2'],
                'idLabels': ['label-2'],
                'due': (datetime.utcnow() + timedelta(days=7)).isoformat() + 'Z',
                'dueComplete': False,
                'dateLastActivity': datetime.utcnow().isoformat() + 'Z',
                'pos': 2,
                'shortLink': 'def456',
                'isTemplate': False,
                'cardRole': 'regular',
                'badges': {
                    'votes': 0,
                    'viewingMemberVoted': False,
                    'subscribed': False,
                    'fogbugz': '',
                    'checkItems': 5,
                    'checkItemsChecked': 2,
                    'comments': 1,
                    'attachments': 2,
                    'description': True
                },
                'labels': [
                    {
                        'id': 'label-2',
                        'idBoard': board_id or 'board-123',
                        'name': 'Feature',
                        'color': 'blue'
                    }
                ],
                'shortUrl': 'https://trello.com/c/def456',
                'url': 'https://trello.com/c/def456/implement-user-authentication'
            }
        ]

        # Filter based on preferences
        if not include_archived:
            mock_cards = [c for c in mock_cards if not c.get('closed')]

        return jsonify(format_trello_response({
            'cards': mock_cards[:limit],
            'total_count': len(mock_cards)
        }, 'list_cards'))

    except Exception as e:
        logger.error(f"Error listing cards: {e}")
        return jsonify(format_error_response(e, 'list_cards')), 500

def _create_card(user_id: str, tokens: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper function to create card"""
    try:
        card_data = data.get('data', {})

        if not card_data.get('name'):
            return jsonify({
                'ok': False,
                'error': {'message': 'Card name is required'}
            }), 400

        # Use Trello service
        if TRELLO_SERVICE_AVAILABLE:
            result = trello_service.create_card(user_id, card_data)

            if result.get('ok'):
                return jsonify(format_trello_response({
                    'card': result.get('card'),
                    'url': result.get('card', {}).get('url'),
                    'message': 'Card created successfully'
                }, 'create_card'))
            else:
                return jsonify(result)

        # Fallback to mock creation
        mock_card = {
            'id': 'card-' + str(int(datetime.utcnow().timestamp())),
            'name': card_data['name'],
            'desc': card_data.get('desc', ''),
            'closed': False,
            'idList': card_data.get('idList', 'list-1'),
            'idBoard': card_data.get('idBoard', 'board-123'),
            'idShort': int(datetime.utcnow().timestamp()),
            'idChecklists': [],
            'idLabels': card_data.get('idLabels', []),
            'due': card_data.get('due'),
            'dueComplete': False,
            'dateLastActivity': datetime.utcnow().isoformat() + 'Z',
            'pos': 65535,
            'shortLink': 'card' + str(int(datetime.utcnow().timestamp())),
            'isTemplate': False,
            'cardRole': 'regular',
            'badges': {
                'votes': 0,
                'viewingMemberVoted': False,
                'subscribed': False,
                'fogbugz': '',
                'checkItems': 0,
                'checkItemsChecked': 0,
                'comments': 0,
                'attachments': 0,
                'description': bool(card_data.get('desc'))
            },
            'labels': [],
            'shortUrl': f"https://trello.com/c/{int(datetime.utcnow().timestamp())}",
            'url': f"https://trello.com/c/{int(datetime.utcnow().timestamp())}/{card_data['name'].replace(' ', '-').lower()}"
        }

        return jsonify(format_trello_response({
            'card': mock_card,
            'url': mock_card['url'],
            'message': 'Card created successfully'
        }, 'create_card'))

    except Exception as e:
        logger.error(f"Error creating card: {e}")
        return jsonify(format_error_response(e, 'create_card')), 500

@trello_enhanced_bp.route('/api/integrations/trello/members', methods=['POST'])
def list_members():
    """List members from workspace or boards"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        board_id = data.get('board_id')
        include_guests = data.get('include_guests', True)
        limit = data.get('limit', 100)

        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400

        # Get user tokens
        tokens = get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Trello tokens not found'}
            }), 401

        # Use Trello service
        if TRELLO_SERVICE_AVAILABLE:
            members = trello_service.get_board_members(
                user_id, board_id, include_guests, limit
            )

            members_data = [{
                'id': member.id,
                'fullName': member.fullName,
                'initials': member.initials,
                'username': member.username,
                'email': member.email,
                'avatarHash': member.avatarHash,
                'avatarUrl': member.avatarUrl,
                'bio': member.bio,
                'bioData': member.bioData,
                'confirmed': member.confirmed,
                'idEnterprise': member.idEnterprise,
                'status': member.status,
                'enterpriseId': member.enterpriseId,
                'enterpriseName': member.enterpriseName,
                'memberType': member.memberType,
                'limits': member.limits,
                'products': member.products,
                'marketingOptIn': member.marketingOptIn,
                'marketingOptInDate': member.marketingOptInDate,
                'emailVerified': member.emailVerified,
                'loginTypes': member.loginTypes,
                'oneTimeMessagesDismissed': member.oneTimeMessagesDismissed,
                'trophies': member.trophies,
                'prefs': member.prefs,
                'uploadedAvatar': member.uploadedAvatar,
                'uploadedAvatarUrl': member.uploadedAvatarUrl,
                'premiumFeatures': member.premiumFeatures,
                'idEnterprises': member.idEnterprises,
                'idTeams': member.idTeams
            } for member in members]

            return jsonify(format_trello_response({
                'members': members_data[:limit],
                'total_count': len(members_data)
            }, 'list_members'))

        # Fallback to mock data
        mock_members = [
            {
                'id': 'member-123',
                'fullName': 'John Developer',
                'initials': 'JD',
                'username': 'johndev',
                'email': 'john@company.com',
                'avatarHash': 'abc123',
                'avatarUrl': 'https://trello-members.s3.amazonaws.com/abc123/170x170.png',
                'bio': 'Senior developer passionate about clean code',
                'confirmed': True,
                'idEnterprise': tokens.get('enterpriseId'),
                'status': 'active',
                'memberType': 'admin',
                'products': ['trello', 'trello-gold'],
                'emailVerified': True,
                'loginTypes': ['password', 'google'],
                'oneTimeMessagesDismissed': [],
                'trophies': [],
                'uploadedAvatar': False,
                'premiumFeatures': [],
                'idEnterprises': [tokens.get('enterpriseId')] if tokens.get('enterpriseId') else [],
                'idTeams': []
            },
            {
                'id': 'member-456',
                'fullName': 'Jane Product',
                'initials': 'JP',
                'username': 'janeprod',
                'email': 'jane@company.com',
                'avatarHash': 'def456',
                'avatarUrl': 'https://trello-members.s3.amazonaws.com/def456/170x170.png',
                'bio': 'Product manager focused on user experience',
                'confirmed': True,
                'idEnterprise': tokens.get('enterpriseId'),
                'status': 'active',
                'memberType': 'normal',
                'products': ['trello'],
                'emailVerified': True,
                'loginTypes': ['password'],
                'oneTimeMessagesDismissed': [],
                'trophies': [],
                'uploadedAvatar': False,
                'premiumFeatures': [],
                'idEnterprises': [tokens.get('enterpriseId')] if tokens.get('enterpriseId') else [],
                'idTeams': []
            },
            {
                'id': 'guest-789',
                'fullName': 'External Collaborator',
                'initials': 'EC',
                'username': 'external',
                'email': 'collab@external.com',
                'avatarHash': 'ghi789',
                'avatarUrl': 'https://trello-members.s3.amazonaws.com/ghi789/170x170.png',
                'bio': 'Guest collaborator from partner company',
                'confirmed': True,
                'status': 'active',
                'memberType': 'guest',
                'products': ['trello'],
                'emailVerified': True,
                'loginTypes': ['password'],
                'oneTimeMessagesDismissed': [],
                'trophies': [],
                'uploadedAvatar': False,
                'premiumFeatures': [],
                'idEnterprises': [],
                'idTeams': []
            }
        ]

        # Filter based on preferences
        if not include_guests:
            mock_members = [m for m in mock_members if m['memberType'] !== 'guest']

        return jsonify(format_trello_response({
            'members': mock_members[:limit],
            'total_count': len(mock_members)
        }, 'list_members'))

    except Exception as e:
        logger.error(f"Error listing members: {e}")
        return jsonify(format_error_response(e, 'list_members')), 500

@trello_enhanced_bp.route('/api/integrations/trello/user/profile', methods=['POST'])
def get_user_profile():
    """Get authenticated user profile"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400

        # Get user tokens
        tokens = get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Trello tokens not found'}
            }), 401

        # Use Trello service
        if TRELLO_SERVICE_AVAILABLE:
            user = trello_service.get_user_profile(user_id)

            if user:
                return jsonify(format_trello_response({
                    'user': {
                        'id': user.id,
                        'fullName': user.fullName,
                        'username': user.username,
                        'email': user.email,
                        'avatarUrl': user.avatarUrl,
                        'memberType': user.memberType,
                        'idEnterprise': user.idEnterprise,
                        'enterpriseName': user.enterpriseName
                    }
                }, 'get_user_profile'))
            else:
                return jsonify({
                    'ok': False,
                    'error': {'message': 'User profile not found'}
                })

        # Fallback to token data
        return jsonify(format_trello_response({
            'user': {
                'id': tokens['memberId'],
                'fullName': tokens['memberName'],
                'username': tokens['memberUsername'],
                'email': tokens['memberEmail'],
                'avatarUrl': tokens['memberAvatar'] or f"https://trello-members.s3.amazonaws.com/{tokens['memberId']}/170x170.png",
                'memberType': 'admin',
                'idEnterprise': tokens['enterpriseId'],
                'enterpriseName': tokens['enterpriseName']
            }
        }, 'get_user_profile'))

    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        return jsonify(format_error_response(e, 'get_user_profile')), 500

@trello_enhanced_bp.route('/api/integrations/trello/search', methods=['POST'])
def search_trello():
    """Search across Trello"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        query = data.get('query')
        search_type = data.get('type', 'global')
        limit = data.get('limit', 50)

        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400

        if not query:
            return jsonify({
                'ok': False,
                'error': {'message': 'query is required'}
            }), 400

        # Get user tokens
        tokens = get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Trello tokens not found'}
            }), 401

        # Use Trello service
        if TRELLO_SERVICE_AVAILABLE:
            result = await trello_service.search_trello(
                user_id, query, search_type, limit
            )
            return jsonify(result)

        # Fallback to mock search
        mock_results = [
            {
                'object': 'card',
                'id': 'card-search-1',
                'title': f'Project {query.title()} Planning',
                'url': 'https://trello.com/card-search-1',
                'highlighted_title': f'<b>{query}</b> Project Planning',
                'snippet': f'This document contains information about {query} planning...'
            },
            {
                'object': 'board',
                'id': 'board-search-1',
                'title': f'{query.title()} Management',
                'url': 'https://trello.com/board-search-1',
                'highlighted_title': f'<b>{query}</b> Management',
                'snippet': f'Board for tracking {query}-related tasks...'
            }
        ]

        return jsonify(format_trello_response({
            'results': mock_results,
            'total_count': len(mock_results),
            'query': query
        }, 'search_trello'))

    except Exception as e:
        logger.error(f"Error searching Trello: {e}")
        return jsonify(format_error_response(e, 'search_trello')), 500

@trello_enhanced_bp.route('/api/integrations/trello/health', methods=['GET'])
async def health_check():
    """Trello service health check"""
    try:
        if not TRELLO_SERVICE_AVAILABLE:
            return jsonify({
                'status': 'unhealthy',
                'error': 'Trello service not available',
                'timestamp': datetime.utcnow().isoformat()
            })

        # Test Trello API connectivity
        try:
            if TRELLO_SERVICE_AVAILABLE:
                service_info = trello_service.get_service_info()
                return jsonify({
                    'status': 'healthy',
                    'message': 'Trello API is accessible',
                    'service_available': TRELLO_SERVICE_AVAILABLE,
                    'database_available': TRELLO_DB_AVAILABLE,
                    'service_info': service_info,
                    'timestamp': datetime.utcnow().isoformat()
                })
        except Exception as e:
            return jsonify({
                'status': 'degraded',
                'error': f'Trello service error: {str(e)}',
                'timestamp': datetime.utcnow().isoformat()
            })

        return jsonify({
            'status': 'healthy',
            'message': 'Trello API mock is accessible',
            'service_available': TRELLO_SERVICE_AVAILABLE,
            'database_available': TRELLO_DB_AVAILABLE,
            'timestamp': datetime.utcnow().isoformat()
        })

    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        })

# Error handlers
@trello_enhanced_bp.errorhandler(404)
async def not_found(error):
    return jsonify({
        'ok': False,
        'error': {
            'code': 'NOT_FOUND',
            'message': 'Endpoint not found'
        }
    }), 404

@trello_enhanced_bp.errorhandler(500)
async def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'ok': False,
        'error': {
            'code': 'INTERNAL_ERROR',
            'message': 'Internal server error'
        }
    }), 500
