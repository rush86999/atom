"""
Trello Enhanced Service Implementation
Complete Trello project management with API integration
"""

import os
import logging
import json
import asyncio
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
import httpx

# Configure logging
logger = logging.getLogger(__name__)

# Trello API configuration
TRELLO_API_BASE_URL = "https://api.trello.com/1"
TRELLO_WEBHOOK_URL = "https://api.trello.com/1/webhooks"

@dataclass
class TrelloBoard:
    """Trello board representation"""
    id: str
    name: str
    description: str
    closed: bool
    organization_id: str
    pinned: bool
    url: str
    short_url: str
    short_link: str
    date_last_activity: str
    date_last_view: str
    date_plugin_disable: str
    creation_date: str
    memberships: List[Dict[str, Any]]
    invited: List[Dict[str, Any]]
    power_ups: List[str]
    background_color: str
    background_image: str
    background_image_scaled: List[Dict[str, Any]]
    background_tile: bool
    background_brightness: str
    background_bottom_color: str
    background_top_color: str
    card_cover_images: bool
    card Aging: str
    calendar_feed_enabled: bool
    comment_permissions: str
    hidden_cards: str
    hide_votes: str
    invitations_enabled: bool
    invitees: List[Dict[str, Any]]
    level: str
    limit_attachments: str
    limited_attachments: str
    list_limit: int
    max_attachment_size: int
    max_card_size: int
    max_description_length: int
    max_name_length: int
    max_title_length: int
    member_level: str
    members_everywhere: bool
    members_omitted: List[str]
    minutes_between_summaries: int
    need_a_board_or_card_to_email_to: str
    need_an_email_to_see_comments: str
    need_to_see_about_edits: str
    need_to_see_about_moves: str
    need_to_see_about_voting: str
    oauth_token_id: str
    preflight_board: str
    preflight_card: str
    preflight_card_position: str
    preflight_list: str
    preflight_self_join: str
    preflight_share_board: str
    preflight_share_card: str
    preflight_share_list: str
    preflight_tag_card: str
    preflight_tag_list: str
    preflight_tag_member: str
    preflight_unassign: str
    preflight_upload: str
    preflight_upload_cover: str
    preflight_unmember: str
    show_board_invite_ui: str
    show_card_cover_images: str
    show_members_only_on_cards: str
    show_sidebar: str
    show_sidebar_activity: str
    show_sidebar_board_actions: str
    show_sidebar_card_actions: str
    show_sidebar_members: str
    start_at: str
    starred: bool
    subscribed: bool
    template_gallery: List[Dict[str, Any]]
    use_limited_attachments: str
    voting_permitted: bool
    preferences: Dict[str, Any]
    label_names: Dict[str, str]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class TrelloCard:
    """Trello card representation"""
    id: str
    id_board: str
    id_list: str
    id_short: int
    id_checklists: List[str]
    id_attachment_cover: str
    id_labels: List[str]
    id_members: List[str]
    id_members_voted: List[str]
    manual_cover_attachment: bool
    name: str
    desc: str
    due: str
    due_complete: bool
    start: str
    pos: float
    address: str
    id_card_sources: List[str]
    id_attachment_sheets: List[str]
    coordinates: str
    creation_method: str
    creation_date: str
    data: Dict[str, Any]
    date_last_activity: str
    desc_data: Dict[str, Any]
    email: str
    id_board_source: str
    id_chapter_source: str
    id_card_plugin_source: List[str]
    id_attachment_background: str
    id_custom_fields: List[str]
    id_attachment_preview: str
    url: str
    short_url: str
    short_link: str
    subscribed: bool
    badges: Dict[str, Any]
    custom_field_items: List[Dict[str, Any]]
    cover: Dict[str, Any]
    attachments: List[Dict[str, Any]]
    check_item_states: List[Dict[str, Any]]
    checklists: List[Dict[str, Any]]
    labels: List[Dict[str, Any]]
    id_plugin_data: List[Dict[str, Any]]
    plugin_data: List[Dict[str, Any]]
    member_ids: List[str]
    members: List[Dict[str, Any]]
    plugin_data_screens: List[Dict[str, Any]]
    plugin_data_with_screen: List[Dict[str, Any]]
    source: Dict[str, Any]
    source_id: str
    source_id_board: str
    source_id_list: str
    source_id_chapter: str
    source_member: str
    source_siblings: List[Dict[str, Any]]
    source_parent: Dict[str, Any]
    source_list: Dict[str, Any]
    source_board: Dict[str, Any]
    source_channel: str
    source_channel_id: str
    source_teams: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class TrelloList:
    """Trello list representation"""
    id: str
    name: str
    closed: bool
    id_board: str
    pos: float
    subscribed: bool
    soft_limit: int
    id_card_source: str
    url: str
    short_url: str
    short_link: str
    board_id: str
    board_name: str
    board_url: str
    board_short_url: str
    board_short_link: str
    cards: List[TrelloCard]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = asdict(self)
        # Convert cards to dicts
        result['cards'] = [card.to_dict() for card in self.cards]
        return result

@dataclass
class TrelloMember:
    """Trello member representation"""
    id: str
    activity_blocked: bool
    avatar_hash: str
    avatar_url: str
    avatar_source: str
    confirmed: bool
    email: str
    full_name: str
    id_enterprise: str
    id_enterprise_admin: List[str]
    id_member_referrer: str
    id_premium_account: str
    id_scim_tier: str
    initials: str
    login_allowed: bool
    member_type: str
    one_time_messages_dismissed: List[str]
    phone_numbers: List[Dict[str, Any]]
    preferences: Dict[str, Any]
    premium_features: List[str]
    products: List[str]
    status: str
    url: str
    username: str
    boards: List[TrelloBoard]
    organizations: List[Dict[str, Any]]
    invited: List[Dict[str, Any]]
    bio: str
    bio_data: Dict[str, Any]
    aa_email: str
    non_public: Dict[str, Any]
    non_public_available: Dict[str, Any]
    trophy_text: str
    available_organizations: List[Dict[str, Any]]
    gravatar_hash: str
    uploaded_avatar_hash: str
    uploaded_avatar_url: str
    uploadedAvatarUrl: str
    uploaded_avatar_url250: str
    uploaded_avatar_url170: str
    uploaded_avatar_url30: str
    login_allowed_week: str
    login_allowed_hours: List[str]
    login_blocked_expiration: str
    login_blocked_for_header: bool
    md_mid: str
    md_active_board: str
    md_profile_image_url: str
    md_profile_background_color: str
    md_profile_background_url: str
    md_template_url: str
    md_template_name: str
    md_profile_initials: str
    md_profile_link_color: str
    md_profile_link_color_preset: str
    md_profile_link_color_locked: bool
    md_profile_link_color_preset_locked: bool
    md_profile_link_color_name: str
    md_profile_link_color_name_locked: str
    md_profile_link_color_value: str
    md_profile_link_color_value_locked: str
    md_profile_link_color_css: str
    md_profile_link_color_css_locked: str
    md_profile_link_color_hex: str
    md_profile_link_color_hex_locked: str
    md_profile_link_color_rgb: str
    md_profile_link_color_rgb_locked: str
    md_profile_link_color_rgba: str
    md_profile_link_color_rgba_locked: str
    md_profile_link_color_hsl: str
    md_profile_link_color_hsl_locked: str
    md_profile_link_color_hsla: str
    md_profile_link_color_hsla_locked: str
    md_profile_link_color_hsv: str
    md_profile_link_color_hsv_locked: str
    md_profile_link_color_hsva: str
    md_profile_link_color_hsva_locked: str
    md_profile_link_color_hwb: str
    md_profile_link_color_hwb_locked: str
    md_profile_link_color_hwba: str
    md_profile_link_color_hwba_locked: str
    md_profile_link_color_cmyk: str
    md_profile_link_color_cmyk_locked: str
    md_profile_link_color_cmyka: str
    md_profile_link_color_cmyka_locked: str
    md_profile_link_color_ncol: str
    md_profile_link_color_ncol_locked: str
    md_profile_link_color_ncola: str
    md_profile_link_color_ncola_locked: str
    md_profile_link_color_xyz: str
    md_profile_link_color_xyz_locked: str
    md_profile_link_color_xyza: str
    md_profile_link_color_xyza_locked: str
    md_profile_link_color_lab: str
    md_profile_link_color_lab_locked: str
    md_profile_link_color_laba: str
    md_profile_link_color_laba_locked: str
    md_profile_link_color_lch: str
    md_profile_link_color_lch_locked: str
    md_profile_link_color_lcha: str
    md_profile_link_color_lcha_locked: str
    md_profile_link_color_luv: str
    md_profile_link_color_luv_locked: str
    md_profile_link_color_luva: str
    md_profile_link_color_luva_locked: str
    md_profile_link_color_hsluv: str
    md_profile_link_color_hsluv_locked: str
    md_profile_link_color_hsluva: str
    md_profile_link_color_hsluva_locked: bool
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = asdict(self)
        # Convert boards to dicts
        result['boards'] = [board.to_dict() for board in self.boards]
        return result

@dataclass
class TrelloChecklist:
    """Trello checklist representation"""
    id: str
    name: str
    id_board: str
    id_card: str
    pos: float
    check_items: List[Dict[str, Any]]
    id_checklists: List[str]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class TrelloLabel:
    """Trello label representation"""
    id: str
    id_board: str
    name: str
    color: str
    uses: int
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class TrelloActivity:
    """Trello activity representation"""
    id: str
    id_member_author: str
    data: Dict[str, Any]
    type: str
    date: str
    member_creator: Dict[str, Any]
    member: Dict[str, Any]
    board: Dict[str, Any]
    card: Dict[str, Any]
    list: Dict[str, Any]
    organization: Dict[str, Any]
    app: Dict[str, Any]
    display: Dict[str, Any]
    text: str
    translation_key: str
    member_type: str
    member_level: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

class TrelloEnhancedService:
    """Enhanced Trello service with complete project management automation"""
    
    def __init__(self, api_key: str = None, oauth_token: str = None):
        self.api_key = api_key or os.getenv('TRELLO_API_KEY')
        self.oauth_token = oauth_token or os.getenv('TRELLO_OAUTH_TOKEN')
        self.api_base_url = TRELLO_API_BASE_URL
        
        # Cache for storing data
        self.boards_cache = {}
        self.cards_cache = {}
        self.lists_cache = {}
        self.members_cache = {}
        
        # Common Trello colors
        self.label_colors = {
            'green': '#61BD4F',
            'yellow': '#F2D600',
            'orange': '#FFAB4A',
            'red': '#EB5A46',
            'purple': '#C379E0',
            'blue': '#0079BF',
            'sky': '#00C2E0',
            'lime': '#51E898',
            'pink': '#FF80CE',
            'black': '#4D4D4D',
            'null': '#B6BBBF'
        }
        
        # Common card types
        self.card_types = {
            'task': 'Task',
            'bug': 'Bug',
            'feature': 'Feature',
            'enhancement': 'Enhancement',
            'epic': 'Epic',
            'story': 'User Story',
            'subtask': 'Subtask',
            'issue': 'Issue',
            'risk': 'Risk',
            'milestone': 'Milestone'
        }
    
    def _get_auth_params(self) -> Dict[str, str]:
        """Get authentication parameters"""
        return {
            'key': self.api_key,
            'token': self.oauth_token
        }
    
    def _build_url(self, endpoint: str) -> str:
        """Build complete API URL"""
        return f"{self.api_base_url}/{endpoint}"
    
    async def _make_request(self, method: str, endpoint: str, 
                          params: Dict[str, Any] = None,
                          data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to Trello API"""
        try:
            # Add auth parameters
            auth_params = self._get_auth_params()
            
            # Merge with existing parameters
            if params:
                params.update(auth_params)
            else:
                params = auth_params
            
            # Build URL
            url = self._build_url(endpoint)
            
            async with httpx.AsyncClient(timeout=30) as client:
                if method.upper() == 'GET':
                    response = await client.get(url, params=params)
                elif method.upper() == 'POST':
                    response = await client.post(url, params=params, json=data)
                elif method.upper() == 'PUT':
                    response = await client.put(url, params=params, json=data)
                elif method.upper() == 'DELETE':
                    response = await client.delete(url, params=params)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                response.raise_for_status()
                
                return response.json()
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Trello API HTTP error: {e.response.status_code} - {e.response.text}")
            return {
                'error': f'HTTP {e.response.status_code}',
                'message': e.response.text,
                'type': 'http_error'
            }
        except Exception as e:
            logger.error(f"Trello API request error: {e}")
            return {
                'error': str(e),
                'type': 'request_error'
            }
    
    def _generate_cache_key(self, user_id: str, entity_id: str) -> str:
        """Generate cache key"""
        return f"{user_id}:{entity_id}"
    
    async def get_boards(self, user_id: str, filter: str = None) -> List[TrelloBoard]:
        """Get Trello boards for user"""
        try:
            # Check cache first
            cache_key = self._generate_cache_key(user_id, 'boards')
            if cache_key in self.boards_cache:
                return self.boards_cache[cache_key]
            
            # Build parameters
            params = {
                'filter': filter or 'all',
                'lists': 'all',
                'memberships': 'all',
                'memberships_member': 'true',
                'memberships_member_fields': 'all',
                'organization': 'true',
                'organization_fields': 'name,displayName',
                'fields': 'all'
            }
            
            # Make request
            result = await self._make_request('GET', f'members/{user_id}/boards', params)
            
            if result.get('error'):
                return []
            
            # Create board objects
            boards = []
            for board_data in result:
                board = TrelloBoard(
                    id=board_data.get('id', ''),
                    name=board_data.get('name', ''),
                    description=board_data.get('desc', ''),
                    closed=board_data.get('closed', False),
                    organization_id=board_data.get('idOrganization', ''),
                    pinned=board_data.get('pinned', False),
                    url=board_data.get('url', ''),
                    short_url=board_data.get('shortUrl', ''),
                    short_link=board_data.get('shortLink', ''),
                    date_last_activity=board_data.get('dateLastActivity', ''),
                    date_last_view=board_data.get('dateLastView', ''),
                    date_plugin_disable=board_data.get('datePluginDisable', ''),
                    creation_date=board_data.get('creation_date', ''),
                    memberships=board_data.get('memberships', []),
                    invited=board_data.get('invited', []),
                    power_ups=board_data.get('powerUps', []),
                    background_color=board_data.get('prefs', {}).get('background', ''),
                    background_image=board_data.get('prefs', {}).get('backgroundImage', ''),
                    background_image_scaled=board_data.get('prefs', {}).get('backgroundImageScaled', []),
                    background_tile=board_data.get('prefs', {}).get('backgroundTile', False),
                    background_brightness=board_data.get('prefs', {}).get('backgroundBrightness', 'light'),
                    background_bottom_color=board_data.get('prefs', {}).get('backgroundBottomColor', ''),
                    background_top_color=board_data.get('prefs', {}).get('backgroundTopColor', ''),
                    card_cover_images=board_data.get('prefs', {}).get('cardCovers', True),
                    card_Aging=board_data.get('prefs', {}).get('cardAging', 'regular'),
                    calendar_feed_enabled=board_data.get('prefs', {}).get('calendarFeedEnabled', False),
                    comment_permissions=board_data.get('prefs', {}).get('comments', 'members'),
                    hidden_cards=board_data.get('prefs', {}).get('hiddenCards', ''),
                    hide_votes=board_data.get('prefs', {}).get('hideVotes', False),
                    invitations_enabled=board_data.get('prefs', {}).get('invitations', 'members'),
                    invitees=board_data.get('prefs', {}).get('invitees', []),
                    level=board_data.get('level', ''),
                    limit_attachments=board_data.get('prefs', {}).get('limitAttachments', ''),
                    limited_attachments=board_data.get('prefs', {}).get('limitedAttachments', ''),
                    list_limit=board_data.get('prefs', {}).get('listLimit', 200),
                    max_attachment_size=board_data.get('prefs', {}).get('maxAttachmentSize', 10485760),
                    max_card_size=board_data.get('prefs', {}).get('maxCardSize', 16384),
                    max_description_length=board_data.get('prefs', {}).get('maxDescriptionLength', 16384),
                    max_name_length=board_data.get('prefs', {}).get('maxNameLength', 16384),
                    max_title_length=board_data.get('prefs', {}).get('maxTitleLength', 16384),
                    member_level=board_data.get('member_level', ''),
                    members_everywhere=board_data.get('prefs', {}).get('membersEverywhere', False),
                    members_omitted=board_data.get('prefs', {}).get('membersOmitted', []),
                    minutes_between_summaries=board_data.get('prefs', {}).get('minutesBetweenSummaries', 60),
                    need_a_board_or_card_to_email_to=board_data.get('prefs', {}).get('needABoardOrCardToEmailTo', ''),
                    need_an_email_to_see_comments=board_data.get('prefs', {}).get('needAnEmailToSeeComments', ''),
                    need_to_see_about_edits=board_data.get('prefs', {}).get('needToSeeAboutEdits', ''),
                    need_to_see_about_moves=board_data.get('prefs', {}).get('needToSeeAboutMoves', ''),
                    need_to_see_about_voting=board_data.get('prefs', {}).get('needToSeeAboutVoting', ''),
                    oauth_token_id=board_data.get('prefs', {}).get('oauthTokenId', ''),
                    preflight_board=board_data.get('prefs', {}).get('preflightBoard', ''),
                    preflight_card=board_data.get('prefs', {}).get('preflightCard', ''),
                    preflight_card_position=board_data.get('prefs', {}).get('preflightCardPosition', ''),
                    preflight_list=board_data.get('prefs', {}).get('preflightList', ''),
                    preflight_self_join=board_data.get('prefs', {}).get('preflightSelfJoin', ''),
                    preflight_share_board=board_data.get('prefs', {}).get('preflightShareBoard', ''),
                    preflight_share_card=board_data.get('prefs', {}).get('preflightShareCard', ''),
                    preflight_share_list=board_data.get('prefs', {}).get('preflightShareList', ''),
                    preflight_tag_card=board_data.get('prefs', {}).get('preflightTagCard', ''),
                    preflight_tag_list=board_data.get('prefs', {}).get('preflightTagList', ''),
                    preflight_tag_member=board_data.get('prefs', {}).get('preflightTagMember', ''),
                    preflight_unassign=board_data.get('prefs', {}).get('preflightUnassign', ''),
                    show_board_invite_ui=board_data.get('prefs', {}).get('showBoardInviteUi', ''),
                    show_card_cover_images=board_data.get('prefs', {}).get('showCardCoverImages', ''),
                    show_members_only_on_cards=board_data.get('prefs', {}).get('showMembersOnlyOnCards', False),
                    show_sidebar=board_data.get('prefs', {}).get('showSidebar', True),
                    show_sidebar_activity=board_data.get('prefs', {}).get('showSidebarActivity', True),
                    show_sidebar_board_actions=board_data.get('prefs', {}).get('showSidebarBoardActions', True),
                    show_sidebar_card_actions=board_data.get('prefs', {}).get('showSidebarCardActions', True),
                    show_sidebar_members=board_data.get('prefs', {}).get('showSidebarMembers', True),
                    start_at=board_data.get('prefs', {}).get('startAt', ''),
                    starred=board_data.get('starred', False),
                    subscribed=board_data.get('subscribed', False),
                    template_gallery=board_data.get('templateGallery', []),
                    use_limited_attachments=board_data.get('prefs', {}).get('useLimitedAttachments', ''),
                    voting_permitted=board_data.get('prefs', {}).get('votingPermission', 'members'),
                    preferences=board_data.get('prefs', {}),
                    label_names=board_data.get('labelNames', {}),
                    metadata={
                        'accessed_at': datetime.utcnow().isoformat(),
                        'source': 'trello_api'
                    }
                )
                boards.append(board)
            
            # Cache boards
            self.boards_cache[cache_key] = boards
            
            logger.info(f"Trello boards retrieved: {len(boards)}")
            return boards
            
        except Exception as e:
            logger.error(f"Error getting Trello boards: {e}")
            return []
    
    async def get_board(self, board_id: str, include_lists: bool = True, 
                      include_cards: bool = True, include_members: bool = True) -> Optional[TrelloBoard]:
        """Get Trello board by ID"""
        try:
            # Check cache first
            cache_key = self._generate_cache_key('board', board_id)
            if cache_key in self.boards_cache:
                return self.boards_cache[cache_key]
            
            # Build parameters
            params = {
                'fields': 'all',
                'lists': 'all' if include_lists else 'none',
                'cards': 'all' if include_cards else 'none',
                'members': 'all' if include_members else 'none',
                'memberships': 'all',
                'memberships_member': 'true',
                'memberships_member_fields': 'all',
                'organization': 'true',
                'organization_fields': 'name,displayName',
                'member_fields': 'all',
                'card_fields': 'all',
                'card_attachments': 'true',
                'card_attachment_fields': 'all',
                'card_checklists': 'all',
                'card_checklist_fields': 'all',
                'card_stickers': 'true',
                'card_sticker_fields': 'all',
                'labels': 'all',
                'label_fields': 'all',
                'list_fields': 'all',
                'pluginData': 'true',
                'pluginData_fields': 'all'
            }
            
            # Make request
            result = await self._make_request('GET', f'boards/{board_id}', params)
            
            if result.get('error'):
                return None
            
            # Create board object
            board = TrelloBoard(
                id=result.get('id', ''),
                name=result.get('name', ''),
                description=result.get('desc', ''),
                closed=result.get('closed', False),
                organization_id=result.get('idOrganization', ''),
                pinned=result.get('pinned', False),
                url=result.get('url', ''),
                short_url=result.get('shortUrl', ''),
                short_link=result.get('shortLink', ''),
                date_last_activity=result.get('dateLastActivity', ''),
                date_last_view=result.get('dateLastView', ''),
                date_plugin_disable=result.get('datePluginDisable', ''),
                creation_date=result.get('creation_date', ''),
                memberships=result.get('memberships', []),
                invited=result.get('invited', []),
                power_ups=result.get('powerUps', []),
                background_color=result.get('prefs', {}).get('background', ''),
                background_image=result.get('prefs', {}).get('backgroundImage', ''),
                background_image_scaled=result.get('prefs', {}).get('backgroundImageScaled', []),
                background_tile=result.get('prefs', {}).get('backgroundTile', False),
                background_brightness=result.get('prefs', {}).get('backgroundBrightness', 'light'),
                background_bottom_color=result.get('prefs', {}).get('backgroundBottomColor', ''),
                background_top_color=result.get('prefs', {}).get('backgroundTopColor', ''),
                card_cover_images=result.get('prefs', {}).get('cardCovers', True),
                card_Aging=result.get('prefs', {}).get('cardAging', 'regular'),
                calendar_feed_enabled=result.get('prefs', {}).get('calendarFeedEnabled', False),
                comment_permissions=result.get('prefs', {}).get('comments', 'members'),
                hidden_cards=result.get('prefs', {}).get('hiddenCards', ''),
                hide_votes=result.get('prefs', {}).get('hideVotes', False),
                invitations_enabled=result.get('prefs', {}).get('invitations', 'members'),
                invitees=result.get('prefs', {}).get('invitees', []),
                level=result.get('level', ''),
                limit_attachments=result.get('prefs', {}).get('limitAttachments', ''),
                limited_attachments=result.get('prefs', {}).get('limitedAttachments', ''),
                list_limit=result.get('prefs', {}).get('listLimit', 200),
                max_attachment_size=result.get('prefs', {}).get('maxAttachmentSize', 10485760),
                max_card_size=result.get('prefs', {}).get('maxCardSize', 16384),
                max_description_length=result.get('prefs', {}).get('maxDescriptionLength', 16384),
                max_name_length=result.get('prefs', {}).get('maxNameLength', 16384),
                max_title_length=result.get('prefs', {}).get('maxTitleLength', 16384),
                member_level=result.get('member_level', ''),
                members_everywhere=result.get('prefs', {}).get('membersEverywhere', False),
                members_omitted=result.get('prefs', {}).get('membersOmitted', []),
                minutes_between_summaries=result.get('prefs', {}).get('minutesBetweenSummaries', 60),
                need_a_board_or_card_to_email_to=result.get('prefs', {}).get('needABoardOrCardToEmailTo', ''),
                need_an_email_to_see_comments=result.get('prefs', {}).get('needAnEmailToSeeComments', ''),
                need_to_see_about_edits=result.get('prefs', {}).get('needToSeeAboutEdits', ''),
                need_to_see_about_moves=result.get('prefs', {}).get('needToSeeAboutMoves', ''),
                need_to_see_about_voting=result.get('prefs', {}).get('needToSeeAboutVoting', ''),
                oauth_token_id=result.get('prefs', {}).get('oauthTokenId', ''),
                preflight_board=result.get('prefs', {}).get('preflightBoard', ''),
                preflight_card=result.get('prefs', {}).get('preflightCard', ''),
                preflight_card_position=result.get('prefs', {}).get('preflightCardPosition', ''),
                preflight_list=result.get('prefs', {}).get('preflightList', ''),
                preflight_self_join=result.get('prefs', {}).get('preflightSelfJoin', ''),
                preflight_share_board=result.get('prefs', {}).get('preflightShareBoard', ''),
                preflight_share_card=result.get('prefs', {}).get('preflightShareCard', ''),
                preflight_share_list=result.get('prefs', {}).get('preflightShareList', ''),
                preflight_tag_card=result.get('prefs', {}).get('preflightTagCard', ''),
                preflight_tag_list=result.get('prefs', {}).get('preflightTagList', ''),
                preflight_tag_member=result.get('prefs', {}).get('preflightTagMember', ''),
                preflight_unassign=result.get('prefs', {}).get('preflightUnassign', ''),
                show_board_invite_ui=result.get('prefs', {}).get('showBoardInviteUi', ''),
                show_card_cover_images=result.get('prefs', {}).get('showCardCoverImages', ''),
                show_members_only_on_cards=result.get('prefs', {}).get('showMembersOnlyOnCards', False),
                show_sidebar=result.get('prefs', {}).get('showSidebar', True),
                show_sidebar_activity=result.get('prefs', {}).get('showSidebarActivity', True),
                show_sidebar_board_actions=result.get('prefs', {}).get('showSidebarBoardActions', True),
                show_sidebar_card_actions=result.get('prefs', {}).get('showSidebarCardActions', True),
                show_sidebar_members=result.get('prefs', {}).get('showSidebarMembers', True),
                start_at=result.get('prefs', {}).get('startAt', ''),
                starred=result.get('starred', False),
                subscribed=result.get('subscribed', False),
                template_gallery=result.get('templateGallery', []),
                use_limited_attachments=result.get('prefs', {}).get('useLimitedAttachments', ''),
                voting_permitted=result.get('prefs', {}).get('votingPermission', 'members'),
                preferences=result.get('prefs', {}),
                label_names=result.get('labelNames', {}),
                metadata={
                    'accessed_at': datetime.utcnow().isoformat(),
                    'source': 'trello_api'
                }
            )
            
            # Cache board
            self.boards_cache[cache_key] = board
            
            logger.info(f"Trello board retrieved: {board_id}")
            return board
            
        except Exception as e:
            logger.error(f"Error getting Trello board: {e}")
            return None
    
    async def get_cards(self, board_id: str, list_id: str = None, 
                      filter: str = None) -> List[TrelloCard]:
        """Get Trello cards from board or list"""
        try:
            # Check cache first
            cache_key = self._generate_cache_key('cards', f"{board_id}:{list_id or 'all'}")
            if cache_key in self.cards_cache:
                return self.cards_cache[cache_key]
            
            # Build endpoint
            if list_id:
                endpoint = f'lists/{list_id}/cards'
            else:
                endpoint = f'boards/{board_id}/cards'
            
            # Build parameters
            params = {
                'filter': filter or 'all',
                'fields': 'all',
                'attachments': 'true',
                'attachment_fields': 'all',
                'checklists': 'all',
                'checklist_fields': 'all',
                'stickers': 'true',
                'sticker_fields': 'all',
                'members': 'true',
                'member_fields': 'all',
                'membersVoted': 'true',
                'memberVoted_fields': 'all',
                'checkItemStates': 'true',
                'checkItemState_fields': 'all',
                'customFieldItems': 'true',
                'customFieldItem_fields': 'all',
                'labels': 'true',
                'label_fields': 'all',
                'pluginData': 'true',
                'pluginData_fields': 'all'
            }
            
            # Make request
            result = await self._make_request('GET', endpoint, params)
            
            if result.get('error'):
                return []
            
            # Create card objects
            cards = []
            for card_data in result:
                card = TrelloCard(
                    id=card_data.get('id', ''),
                    id_board=card_data.get('idBoard', ''),
                    id_list=card_data.get('idList', ''),
                    id_short=card_data.get('idShort', 0),
                    id_checklists=card_data.get('idChecklists', []),
                    id_attachment_cover=card_data.get('idAttachmentCover', ''),
                    id_labels=card_data.get('idLabels', []),
                    id_members=card_data.get('idMembers', []),
                    id_members_voted=card_data.get('idMembersVoted', []),
                    manual_cover_attachment=card_data.get('manualCoverAttachment', False),
                    name=card_data.get('name', ''),
                    desc=card_data.get('desc', ''),
                    due=card_data.get('due', ''),
                    due_complete=card_data.get('dueComplete', False),
                    start=card_data.get('start', ''),
                    pos=card_data.get('pos', 0),
                    address=card_data.get('address', ''),
                    id_card_sources=card_data.get('idCardSources', []),
                    id_attachment_sheets=card_data.get('idAttachmentSheets', []),
                    coordinates=card_data.get('coordinates', ''),
                    creation_method=card_data.get('creation_method', ''),
                    creation_date=card_data.get('creation_date', ''),
                    data=card_data.get('data', {}),
                    date_last_activity=card_data.get('dateLastActivity', ''),
                    desc_data=card_data.get('descData', {}),
                    email=card_data.get('email', ''),
                    id_board_source=card_data.get('idBoardSource', ''),
                    id_chapter_source=card_data.get('idChapterSource', ''),
                    id_card_plugin_source=card_data.get('idCardPluginSource', []),
                    id_attachment_background=card_data.get('idAttachmentBackground', ''),
                    id_custom_fields=card_data.get('idCustomFields', []),
                    id_attachment_preview=card_data.get('idAttachmentPreview', ''),
                    url=card_data.get('url', ''),
                    short_url=card_data.get('shortUrl', ''),
                    short_link=card_data.get('shortLink', ''),
                    subscribed=card_data.get('subscribed', False),
                    badges=card_data.get('badges', {}),
                    custom_field_items=card_data.get('customFieldItems', []),
                    cover=card_data.get('cover', {}),
                    attachments=card_data.get('attachments', []),
                    check_item_states=card_data.get('checkItemStates', []),
                    checklists=card_data.get('checklists', []),
                    labels=card_data.get('labels', []),
                    id_plugin_data=card_data.get('idPluginData', []),
                    plugin_data=card_data.get('pluginData', []),
                    member_ids=card_data.get('member_ids', []),
                    members=card_data.get('members', []),
                    plugin_data_screens=card_data.get('pluginDataScreens', []),
                    plugin_data_with_screen=card_data.get('pluginDataWithScreen', []),
                    source=card_data.get('source', {}),
                    source_id=card_data.get('source_id', ''),
                    source_id_board=card_data.get('source_id_board', ''),
                    source_id_list=card_data.get('source_id_list', ''),
                    source_id_chapter=card_data.get('source_id_chapter', ''),
                    source_member=card_data.get('source_member', ''),
                    source_siblings=card_data.get('source_siblings', []),
                    source_parent=card_data.get('source_parent', {}),
                    source_list=card_data.get('source_list', {}),
                    source_board=card_data.get('source_board', {}),
                    source_channel=card_data.get('source_channel', ''),
                    source_channel_id=card_data.get('source_channel_id', ''),
                    source_teams=card_data.get('source_teams', []),
                    metadata={
                        'accessed_at': datetime.utcnow().isoformat(),
                        'source': 'trello_api'
                    }
                )
                cards.append(card)
            
            # Cache cards
            self.cards_cache[cache_key] = cards
            
            logger.info(f"Trello cards retrieved: {len(cards)}")
            return cards
            
        except Exception as e:
            logger.error(f"Error getting Trello cards: {e}")
            return []
    
    async def get_card(self, card_id: str, include_attachments: bool = True,
                      include_checklists: bool = True, include_members: bool = True) -> Optional[TrelloCard]:
        """Get Trello card by ID"""
        try:
            # Check cache first
            cache_key = self._generate_cache_key('card', card_id)
            if cache_key in self.cards_cache:
                return self.cards_cache[cache_key]
            
            # Build parameters
            params = {
                'fields': 'all',
                'attachments': 'true' if include_attachments else 'false',
                'attachment_fields': 'all',
                'checklists': 'all' if include_checklists else 'none',
                'checklist_fields': 'all',
                'members': 'true' if include_members else 'false',
                'member_fields': 'all',
                'membersVoted': 'true',
                'memberVoted_fields': 'all',
                'checkItemStates': 'true',
                'checkItemState_fields': 'all',
                'customFieldItems': 'true',
                'customFieldItem_fields': 'all',
                'labels': 'true',
                'label_fields': 'all',
                'pluginData': 'true',
                'pluginData_fields': 'all'
            }
            
            # Make request
            result = await self._make_request('GET', f'cards/{card_id}', params)
            
            if result.get('error'):
                return None
            
            # Create card object
            card = TrelloCard(
                id=result.get('id', ''),
                id_board=result.get('idBoard', ''),
                id_list=result.get('idList', ''),
                id_short=result.get('idShort', 0),
                id_checklists=result.get('idChecklists', []),
                id_attachment_cover=result.get('idAttachmentCover', ''),
                id_labels=result.get('idLabels', []),
                id_members=result.get('idMembers', []),
                id_members_voted=result.get('idMembersVoted', []),
                manual_cover_attachment=result.get('manualCoverAttachment', False),
                name=result.get('name', ''),
                desc=result.get('desc', ''),
                due=result.get('due', ''),
                due_complete=result.get('dueComplete', False),
                start=result.get('start', ''),
                pos=result.get('pos', 0),
                address=result.get('address', ''),
                id_card_sources=result.get('idCardSources', []),
                id_attachment_sheets=result.get('idAttachmentSheets', []),
                coordinates=result.get('coordinates', ''),
                creation_method=result.get('creation_method', ''),
                creation_date=result.get('creation_date', ''),
                data=result.get('data', {}),
                date_last_activity=result.get('dateLastActivity', ''),
                desc_data=result.get('descData', {}),
                email=result.get('email', ''),
                id_board_source=result.get('idBoardSource', ''),
                id_chapter_source=result.get('idChapterSource', ''),
                id_card_plugin_source=result.get('idCardPluginSource', []),
                id_attachment_background=result.get('idAttachmentBackground', ''),
                id_custom_fields=result.get('idCustomFields', []),
                id_attachment_preview=result.get('idAttachmentPreview', ''),
                url=result.get('url', ''),
                short_url=result.get('shortUrl', ''),
                short_link=result.get('shortLink', ''),
                subscribed=result.get('subscribed', False),
                badges=result.get('badges', {}),
                custom_field_items=result.get('customFieldItems', []),
                cover=result.get('cover', {}),
                attachments=result.get('attachments', []),
                check_item_states=result.get('checkItemStates', []),
                checklists=result.get('checklists', []),
                labels=result.get('labels', []),
                id_plugin_data=result.get('idPluginData', []),
                plugin_data=result.get('pluginData', []),
                member_ids=result.get('member_ids', []),
                members=result.get('members', []),
                plugin_data_screens=result.get('pluginDataScreens', []),
                plugin_data_with_screen=result.get('pluginDataWithScreen', []),
                source=result.get('source', {}),
                source_id=result.get('source_id', ''),
                source_id_board=result.get('source_id_board', ''),
                source_id_list=result.get('source_id_list', ''),
                source_id_chapter=result.get('source_id_chapter', ''),
                source_member=result.get('source_member', ''),
                source_siblings=result.get('source_siblings', []),
                source_parent=result.get('source_parent', {}),
                source_list=result.get('source_list', {}),
                source_board=result.get('source_board', {}),
                source_channel=result.get('source_channel', ''),
                source_channel_id=result.get('source_channel_id', ''),
                source_teams=result.get('source_teams', []),
                metadata={
                    'accessed_at': datetime.utcnow().isoformat(),
                    'source': 'trello_api'
                }
            )
            
            # Cache card
            self.cards_cache[cache_key] = card
            
            logger.info(f"Trello card retrieved: {card_id}")
            return card
            
        except Exception as e:
            logger.error(f"Error getting Trello card: {e}")
            return None
    
    async def get_lists(self, board_id: str, include_cards: bool = False) -> List[TrelloList]:
        """Get Trello lists from board"""
        try:
            # Check cache first
            cache_key = self._generate_cache_key('lists', board_id)
            if cache_key in self.lists_cache:
                return self.lists_cache[cache_key]
            
            # Build parameters
            params = {
                'cards': 'all' if include_cards else 'none',
                'card_fields': 'all',
                'filter': 'all',
                'fields': 'all'
            }
            
            # Make request
            result = await self._make_request('GET', f'boards/{board_id}/lists', params)
            
            if result.get('error'):
                return []
            
            # Create list objects
            lists = []
            for list_data in result:
                # Get cards for this list if requested
                cards = []
                if include_cards:
                    cards = await self.get_cards(board_id, list_data.get('id', ''))
                
                trello_list = TrelloList(
                    id=list_data.get('id', ''),
                    name=list_data.get('name', ''),
                    closed=list_data.get('closed', False),
                    id_board=list_data.get('idBoard', ''),
                    pos=list_data.get('pos', 0),
                    subscribed=list_data.get('subscribed', False),
                    soft_limit=list_data.get('softLimit', 0),
                    id_card_source=list_data.get('idCardSource', ''),
                    url=list_data.get('url', ''),
                    short_url=list_data.get('shortUrl', ''),
                    short_link=list_data.get('shortLink', ''),
                    board_id=board_id,
                    board_name=list_data.get('board_name', ''),
                    board_url=list_data.get('board_url', ''),
                    board_short_url=list_data.get('board_short_url', ''),
                    board_short_link=list_data.get('board_short_link', ''),
                    cards=cards,
                    metadata={
                        'accessed_at': datetime.utcnow().isoformat(),
                        'source': 'trello_api'
                    }
                )
                lists.append(trello_list)
            
            # Cache lists
            self.lists_cache[cache_key] = lists
            
            logger.info(f"Trello lists retrieved: {len(lists)}")
            return lists
            
        except Exception as e:
            logger.error(f"Error getting Trello lists: {e}")
            return []
    
    async def get_members(self, board_id: str = None, include_boards: bool = False) -> List[TrelloMember]:
        """Get Trello members from board or all members"""
        try:
            # Check cache first
            cache_key = self._generate_cache_key('members', board_id or 'all')
            if cache_key in self.members_cache:
                return self.members_cache[cache_key]
            
            # Build endpoint
            if board_id:
                endpoint = f'boards/{board_id}/members'
            else:
                endpoint = f'members/me'
            
            # Build parameters
            params = {
                'filter': 'all',
                'fields': 'all',
                'boards': 'all' if include_boards else 'none',
                'board_fields': 'all',
                'organizations': 'all',
                'organization_fields': 'all',
                'invited': 'all',
                'invited_fields': 'all',
                'paid_account': 'true',
                'account_type': 'all'
            }
            
            # Make request
            if board_id:
                result = await self._make_request('GET', endpoint, params)
            else:
                # Get current user and then their boards
                user_result = await self._make_request('GET', endpoint, params)
                if user_result.get('error'):
                    return []
                result = [user_result]  # Wrap in list for consistent processing
            
            if result.get('error'):
                return []
            
            # Create member objects
            members = []
            for member_data in result:
                # Get boards for this member if requested
                boards = []
                if include_boards and member_data.get('id'):
                    boards = await self.get_boards(member_data.get('id', ''))
                
                member = TrelloMember(
                    id=member_data.get('id', ''),
                    activity_blocked=member_data.get('activityBlocked', False),
                    avatar_hash=member_data.get('avatarHash', ''),
                    avatar_url=member_data.get('avatarUrl', ''),
                    avatar_source=member_data.get('avatarSource', ''),
                    confirmed=member_data.get('confirmed', False),
                    email=member_data.get('email', ''),
                    full_name=member_data.get('fullName', ''),
                    id_enterprise=member_data.get('idEnterprise', ''),
                    id_enterprise_admin=member_data.get('idEnterpriseAdmin', []),
                    id_member_referrer=member_data.get('idMemberReferrer', ''),
                    id_premium_account=member_data.get('idPremiumAccount', ''),
                    id_scim_tier=member_data.get('idScimTier', ''),
                    initials=member_data.get('initials', ''),
                    login_allowed=member_data.get('loginAllowed', True),
                    member_type=member_data.get('memberType', ''),
                    one_time_messages_dismissed=member_data.get('oneTimeMessagesDismissed', []),
                    phone_numbers=member_data.get('phoneNumbers', []),
                    preferences=member_data.get('prefs', {}),
                    premium_features=member_data.get('premiumFeatures', []),
                    products=member_data.get('products', []),
                    status=member_data.get('status', ''),
                    url=member_data.get('url', ''),
                    username=member_data.get('username', ''),
                    boards=boards,
                    organizations=member_data.get('organizations', []),
                    invited=member_data.get('invited', []),
                    bio=member_data.get('bio', ''),
                    bio_data=member_data.get('bioData', {}),
                    aa_email=member_data.get('aaEmail', ''),
                    non_public=member_data.get('nonPublic', {}),
                    non_public_available=member_data.get('nonPublicAvailable', {}),
                    trophy_text=member_data.get('trophyText', ''),
                    available_organizations=member_data.get('availableOrganizations', []),
                    gravatar_hash=member_data.get('gravatarHash', ''),
                    uploaded_avatar_hash=member_data.get('uploadedAvatarHash', ''),
                    uploaded_avatar_url=member_data.get('uploadedAvatarUrl', ''),
                    uploadedAvatarUrl=member_data.get('uploadedAvatarUrl', ''),
                    uploaded_avatar_url250=member_data.get('uploadedAvatarUrl250', ''),
                    uploaded_avatar_url170=member_data.get('uploadedAvatarUrl170', ''),
                    uploaded_avatar_url30=member_data.get('uploadedAvatarUrl30', ''),
                    login_allowed_week=member_data.get('loginAllowedWeek', ''),
                    login_allowed_hours=member_data.get('loginAllowedHours', []),
                    login_blocked_expiration=member_data.get('loginBlockedExpiration', ''),
                    login_blocked_for_header=member_data.get('loginBlockedForHeader', False),
                    md_mid=member_data.get('mdMid', ''),
                    md_active_board=member_data.get('mdActiveBoard', ''),
                    md_profile_image_url=member_data.get('mdProfileImageUrl', ''),
                    md_profile_background_color=member_data.get('mdProfileBackgroundColor', ''),
                    md_profile_background_url=member_data.get('mdProfileBackgroundUrl', ''),
                    md_template_url=member_data.get('mdTemplateUrl', ''),
                    md_template_name=member_data.get('mdTemplateName', ''),
                    md_profile_initials=member_data.get('mdProfileInitials', ''),
                    md_profile_link_color=member_data.get('mdProfileLinkColor', ''),
                    md_profile_link_color_preset=member_data.get('mdProfileLinkColorPreset', ''),
                    md_profile_link_color_locked=member_data.get('mdProfileLinkColorLocked', False),
                    md_profile_link_color_preset_locked=member_data.get('mdProfileLinkColorPresetLocked', False),
                    md_profile_link_color_name=member_data.get('mdProfileLinkColorName', ''),
                    md_profile_link_color_name_locked=member_data.get('mdProfileLinkColorNameLocked', False),
                    md_profile_link_color_value=member_data.get('mdProfileLinkColorValue', ''),
                    md_profile_link_color_value_locked=member_data.get('mdProfileLinkColorValueLocked', False),
                    md_profile_link_color_css=member_data.get('mdProfileLinkColorCss', ''),
                    md_profile_link_color_css_locked=member_data.get('mdProfileLinkColorCssLocked', False),
                    md_profile_link_color_hex=member_data.get('mdProfileLinkColorHex', ''),
                    md_profile_link_color_hex_locked=member_data.get('mdProfileLinkColorHexLocked', False),
                    md_profile_link_color_rgb=member_data.get('mdProfileLinkColorRgb', ''),
                    md_profile_link_color_rgb_locked=member_data.get('mdProfileLinkColorRgbLocked', False),
                    md_profile_link_color_rgba=member_data.get('mdProfileLinkColorRgba', ''),
                    md_profile_link_color_rgba_locked=member_data.get('mdProfileLinkColorRgbaLocked', False),
                    md_profile_link_color_hsl=member_data.get('mdProfileLinkColorHsl', ''),
                    md_profile_link_color_hsl_locked=member_data.get('mdProfileLinkColorHslLocked', False),
                    md_profile_link_color_hsla=member_data.get('mdProfileLinkColorHsla', ''),
                    md_profile_link_color_hsla_locked=member_data.get('mdProfileLinkColorHslaLocked', False),
                    md_profile_link_color_hsv=member_data.get('mdProfileLinkColorHsv', ''),
                    md_profile_link_color_hsv_locked=member_data.get('mdProfileLinkColorHsvLocked', False),
                    md_profile_link_color_hsva=member_data.get('mdProfileLinkColorHsva', ''),
                    md_profile_link_color_hsva_locked=member_data.get('mdProfileLinkColorHsvaLocked', False),
                    md_profile_link_color_hwb=member_data.get('mdProfileLinkColorHwb', ''),
                    md_profile_link_color_hwb_locked=member_data.get('mdProfileLinkColorHwbLocked', False),
                    md_profile_link_color_hwba=member_data.get('mdProfileLinkColorHwba', ''),
                    md_profile_link_color_hwba_locked=member_data.get('mdProfileLinkColorHwbaLocked', False),
                    md_profile_link_color_cmyk=member_data.get('mdProfileLinkColorCmyk', ''),
                    md_profile_link_color_cmyk_locked=member_data.get('mdProfileLinkColorCmykLocked', False),
                    md_profile_link_color_cmyka=member_data.get('mdProfileLinkColorCmyka', ''),
                    md_profile_link_color_cmyka_locked=member_data.get('mdProfileLinkColorCmykaLocked', False),
                    md_profile_link_color_ncol=member_data.get('mdProfileLinkColorNcol', ''),
                    md_profile_link_color_ncol_locked=member_data.get('mdProfileLinkColorNcolLocked', False),
                    md_profile_link_color_ncola=member_data.get('mdProfileLinkColorNcola', ''),
                    md_profile_link_color_ncola_locked=member_data.get('mdProfileLinkColorNcolaLocked', False),
                    md_profile_link_color_xyz=member_data.get('mdProfileLinkColorXyz', ''),
                    md_profile_link_color_xyz_locked=member_data.get('mdProfileLinkColorXyzLocked', False),
                    md_profile_link_color_xyza=member_data.get('mdProfileLinkColorXyza', ''),
                    md_profile_link_color_xyza_locked=member_data.get('mdProfileLinkColorXyzaLocked', False),
                    md_profile_link_color_lab=member_data.get('mdProfileLinkColorLab', ''),
                    md_profile_link_color_lab_locked=member_data.get('mdProfileLinkColorLabLocked', False),
                    md_profile_link_color_laba=member_data.get('mdProfileLinkColorLaba', ''),
                    md_profile_link_color_laba_locked=member_data.get('mdProfileLinkColorLabaLocked', False),
                    md_profile_link_color_lch=member_data.get('mdProfileLinkColorLch', ''),
                    md_profile_link_color_lch_locked=member_data.get('mdProfileLinkColorLchLocked', False),
                    md_profile_link_color_lcha=member_data.get('mdProfileLinkColorLcha', ''),
                    md_profile_link_color_lcha_locked=member_data.get('mdProfileLinkColorLchaLocked', False),
                    md_profile_link_color_luv=member_data.get('mdProfileLinkColorLuv', ''),
                    md_profile_link_color_luv_locked=member_data.get('mdProfileLinkColorLuvLocked', False),
                    md_profile_link_color_luva=member_data.get('mdProfileLinkColorLuva', ''),
                    md_profile_link_color_luva_locked=member_data.get('mdProfileLinkColorLuvaLocked', False),
                    md_profile_link_color_hsluv=member_data.get('mdProfileLinkColorHsluv', ''),
                    md_profile_link_color_hsluv_locked=member_data.get('mdProfileLinkColorHsluvLocked', False),
                    md_profile_link_color_hsluva=member_data.get('mdProfileLinkColorHsluva', ''),
                    md_profile_link_color_hsluva_locked=member_data.get('mdProfileLinkColorHsluvaLocked', False),
                    metadata={
                        'accessed_at': datetime.utcnow().isoformat(),
                        'source': 'trello_api'
                    }
                )
                members.append(member)
            
            # Cache members
            self.members_cache[cache_key] = members
            
            logger.info(f"Trello members retrieved: {len(members)}")
            return members
            
        except Exception as e:
            logger.error(f"Error getting Trello members: {e}")
            return []
    
    async def create_card(self, name: str, id_list: str, desc: str = None,
                         due: str = None, id_members: List[str] = None,
                         id_labels: List[str] = None, pos: str = None,
                         address: str = None, url_source: str = None,
                         file_source: str = None, id_card_source: str = None) -> Optional[TrelloCard]:
        """Create Trello card"""
        try:
            # Build data
            data = {
                'name': name,
                'idList': id_list,
                'desc': desc or '',
                'due': due,
                'idMembers': id_members or [],
                'idLabels': id_labels or [],
                'pos': pos or 'bottom',
                'address': address,
                'urlSource': url_source,
                'fileSource': file_source,
                'idCardSource': id_card_source
            }
            
            # Make request
            result = await self._make_request('POST', 'cards', data=data)
            
            if result.get('error'):
                return None
            
            # Create card object
            card = TrelloCard(
                id=result.get('id', ''),
                id_board=result.get('idBoard', ''),
                id_list=result.get('idList', ''),
                id_short=result.get('idShort', 0),
                id_checklists=result.get('idChecklists', []),
                id_attachment_cover=result.get('idAttachmentCover', ''),
                id_labels=result.get('idLabels', []),
                id_members=result.get('idMembers', []),
                id_members_voted=result.get('idMembersVoted', []),
                manual_cover_attachment=result.get('manualCoverAttachment', False),
                name=result.get('name', ''),
                desc=result.get('desc', ''),
                due=result.get('due', ''),
                due_complete=result.get('dueComplete', False),
                start=result.get('start', ''),
                pos=result.get('pos', 0),
                address=result.get('address', ''),
                id_card_sources=result.get('idCardSources', []),
                id_attachment_sheets=result.get('idAttachmentSheets', []),
                coordinates=result.get('coordinates', ''),
                creation_method=result.get('creation_method', ''),
                creation_date=result.get('creation_date', ''),
                data=result.get('data', {}),
                date_last_activity=result.get('dateLastActivity', ''),
                desc_data=result.get('descData', {}),
                email=result.get('email', ''),
                id_board_source=result.get('idBoardSource', ''),
                id_chapter_source=result.get('idChapterSource', ''),
                id_card_plugin_source=result.get('idCardPluginSource', []),
                id_attachment_background=result.get('idAttachmentBackground', ''),
                id_custom_fields=result.get('idCustomFields', []),
                id_attachment_preview=result.get('idAttachmentPreview', ''),
                url=result.get('url', ''),
                short_url=result.get('shortUrl', ''),
                short_link=result.get('shortLink', ''),
                subscribed=result.get('subscribed', False),
                badges=result.get('badges', {}),
                custom_field_items=result.get('customFieldItems', []),
                cover=result.get('cover', {}),
                attachments=result.get('attachments', []),
                check_item_states=result.get('checkItemStates', []),
                checklists=result.get('checklists', []),
                labels=result.get('labels', []),
                id_plugin_data=result.get('idPluginData', []),
                plugin_data=result.get('pluginData', []),
                member_ids=result.get('member_ids', []),
                members=result.get('members', []),
                plugin_data_screens=result.get('pluginDataScreens', []),
                plugin_data_with_screen=result.get('pluginDataWithScreen', []),
                source=result.get('source', {}),
                source_id=result.get('source_id', ''),
                source_id_board=result.get('source_id_board', ''),
                source_id_list=result.get('source_id_list', ''),
                source_id_chapter=result.get('source_id_chapter', ''),
                source_member=result.get('source_member', ''),
                source_siblings=result.get('source_siblings', []),
                source_parent=result.get('source_parent', {}),
                source_list=result.get('source_list', {}),
                source_board=result.get('source_board', {}),
                source_channel=result.get('source_channel', ''),
                source_channel_id=result.get('source_channel_id', ''),
                source_teams=result.get('source_teams', []),
                metadata={
                    'created_at': datetime.utcnow().isoformat(),
                    'source': 'trello_api'
                }
            )
            
            # Clear cache
            self._clear_card_cache()
            
            logger.info(f"Trello card created: {card.id}")
            return card
            
        except Exception as e:
            logger.error(f"Error creating Trello card: {e}")
            return None
    
    async def update_card(self, card_id: str, name: str = None, desc: str = None,
                         due: str = None, closed: bool = None, pos: str = None,
                         due_complete: bool = None, id_members: List[str] = None,
                         id_labels: List[str] = None) -> Optional[TrelloCard]:
        """Update Trello card"""
        try:
            # Build data
            data = {}
            if name is not None:
                data['name'] = name
            if desc is not None:
                data['desc'] = desc
            if due is not None:
                data['due'] = due
            if closed is not None:
                data['closed'] = closed
            if pos is not None:
                data['pos'] = pos
            if due_complete is not None:
                data['dueComplete'] = due_complete
            if id_members is not None:
                data['idMembers'] = id_members
            if id_labels is not None:
                data['idLabels'] = id_labels
            
            # Make request
            result = await self._make_request('PUT', f'cards/{card_id}', data=data)
            
            if result.get('error'):
                return None
            
            # Create card object
            card = TrelloCard(
                id=result.get('id', ''),
                id_board=result.get('idBoard', ''),
                id_list=result.get('idList', ''),
                id_short=result.get('idShort', 0),
                id_checklists=result.get('idChecklists', []),
                id_attachment_cover=result.get('idAttachmentCover', ''),
                id_labels=result.get('idLabels', []),
                id_members=result.get('idMembers', []),
                id_members_voted=result.get('idMembersVoted', []),
                manual_cover_attachment=result.get('manualCoverAttachment', False),
                name=result.get('name', ''),
                desc=result.get('desc', ''),
                due=result.get('due', ''),
                due_complete=result.get('dueComplete', False),
                start=result.get('start', ''),
                pos=result.get('pos', 0),
                address=result.get('address', ''),
                id_card_sources=result.get('idCardSources', []),
                id_attachment_sheets=result.get('idAttachmentSheets', []),
                coordinates=result.get('coordinates', ''),
                creation_method=result.get('creation_method', ''),
                creation_date=result.get('creation_date', ''),
                data=result.get('data', {}),
                date_last_activity=result.get('dateLastActivity', ''),
                desc_data=result.get('descData', {}),
                email=result.get('email', ''),
                id_board_source=result.get('idBoardSource', ''),
                id_chapter_source=result.get('idChapterSource', ''),
                id_card_plugin_source=result.get('idCardPluginSource', []),
                id_attachment_background=result.get('idAttachmentBackground', ''),
                id_custom_fields=result.get('idCustomFields', []),
                id_attachment_preview=result.get('idAttachmentPreview', ''),
                url=result.get('url', ''),
                short_url=result.get('shortUrl', ''),
                short_link=result.get('shortLink', ''),
                subscribed=result.get('subscribed', False),
                badges=result.get('badges', {}),
                custom_field_items=result.get('customFieldItems', []),
                cover=result.get('cover', {}),
                attachments=result.get('attachments', []),
                check_item_states=result.get('checkItemStates', []),
                checklists=result.get('checklists', []),
                labels=result.get('labels', []),
                id_plugin_data=result.get('idPluginData', []),
                plugin_data=result.get('pluginData', []),
                member_ids=result.get('member_ids', []),
                members=result.get('members', []),
                plugin_data_screens=result.get('pluginDataScreens', []),
                plugin_data_with_screen=result.get('pluginDataWithScreen', []),
                source=result.get('source', {}),
                source_id=result.get('source_id', ''),
                source_id_board=result.get('source_id_board', ''),
                source_id_list=result.get('source_id_list', ''),
                source_id_chapter=result.get('source_id_chapter', ''),
                source_member=result.get('source_member', ''),
                source_siblings=result.get('source_siblings', []),
                source_parent=result.get('source_parent', {}),
                source_list=result.get('source_list', {}),
                source_board=result.get('source_board', ''),
                source_channel=result.get('source_channel', ''),
                source_channel_id=result.get('source_channel_id', ''),
                source_teams=result.get('source_teams', []),
                metadata={
                    'updated_at': datetime.utcnow().isoformat(),
                    'source': 'trello_api'
                }
            )
            
            # Clear cache
            self._clear_card_cache()
            
            logger.info(f"Trello card updated: {card_id}")
            return card
            
        except Exception as e:
            logger.error(f"Error updating Trello card: {e}")
            return None
    
    async def delete_card(self, card_id: str) -> bool:
        """Delete Trello card"""
        try:
            # Make request
            result = await self._make_request('DELETE', f'cards/{card_id}')
            
            # Check for error
            if result.get('error'):
                return False
            
            # Clear cache
            self._clear_card_cache()
            
            logger.info(f"Trello card deleted: {card_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting Trello card: {e}")
            return False
    
    async def create_checklist(self, name: str, id_card: str, 
                             check_items: List[str] = None) -> Optional[TrelloChecklist]:
        """Create Trello checklist"""
        try:
            # Build data
            data = {
                'name': name,
                'idCard': id_card,
                'checkItems': check_items or []
            }
            
            # Make request
            result = await self._make_request('POST', 'checklists', data=data)
            
            if result.get('error'):
                return None
            
            # Create checklist object
            checklist = TrelloChecklist(
                id=result.get('id', ''),
                name=result.get('name', ''),
                id_board=result.get('idBoard', ''),
                id_card=result.get('idCard', ''),
                pos=result.get('pos', 0),
                check_items=result.get('checkItems', []),
                id_checklists=result.get('idChecklists', []),
                metadata={
                    'created_at': datetime.utcnow().isoformat(),
                    'source': 'trello_api'
                }
            )
            
            logger.info(f"Trello checklist created: {checklist.id}")
            return checklist
            
        except Exception as e:
            logger.error(f"Error creating Trello checklist: {e}")
            return None
    
    async def create_label(self, name: str, color: str, id_board: str) -> Optional[TrelloLabel]:
        """Create Trello label"""
        try:
            # Build data
            data = {
                'name': name,
                'color': color,
                'idBoard': id_board
            }
            
            # Make request
            result = await self._make_request('POST', 'labels', data=data)
            
            if result.get('error'):
                return None
            
            # Create label object
            label = TrelloLabel(
                id=result.get('id', ''),
                id_board=result.get('idBoard', ''),
                name=result.get('name', ''),
                color=result.get('color', ''),
                uses=result.get('uses', 0),
                metadata={
                    'created_at': datetime.utcnow().isoformat(),
                    'source': 'trello_api'
                }
            )
            
            logger.info(f"Trello label created: {label.id}")
            return label
            
        except Exception as e:
            logger.error(f"Error creating Trello label: {e}")
            return None
    
    async def search_cards(self, query: str, id_boards: List[str] = None,
                         id_cards: List[str] = None, id_labels: List[str] = None,
                         id_members: List[str] = None, limit: int = 50) -> List[TrelloCard]:
        """Search Trello cards"""
        try:
            # Build parameters
            params = {
                'query': query,
                'idBoards': id_boards or [],
                'idCards': id_cards or [],
                'idLabels': id_labels or [],
                'idMembers': id_members or [],
                'limit': limit,
                'fields': 'all',
                'attachments': 'true',
                'attachment_fields': 'all',
                'checklists': 'all',
                'checklist_fields': 'all',
                'stickers': 'true',
                'sticker_fields': 'all',
                'members': 'true',
                'member_fields': 'all',
                'membersVoted': 'true',
                'memberVoted_fields': 'all',
                'checkItemStates': 'true',
                'checkItemState_fields': 'all',
                'customFieldItems': 'true',
                'customFieldItem_fields': 'all',
                'labels': 'true',
                'label_fields': 'all',
                'pluginData': 'true',
                'pluginData_fields': 'all'
            }
            
            # Make request
            result = await self._make_request('GET', 'search', params)
            
            if result.get('error'):
                return []
            
            # Create card objects
            cards = []
            for card_data in result.get('cards', []):
                card = TrelloCard(
                    id=card_data.get('id', ''),
                    id_board=card_data.get('idBoard', ''),
                    id_list=card_data.get('idList', ''),
                    id_short=card_data.get('idShort', 0),
                    id_checklists=card_data.get('idChecklists', []),
                    id_attachment_cover=card_data.get('idAttachmentCover', ''),
                    id_labels=card_data.get('idLabels', []),
                    id_members=card_data.get('idMembers', []),
                    id_members_voted=card_data.get('idMembersVoted', []),
                    manual_cover_attachment=card_data.get('manualCoverAttachment', False),
                    name=card_data.get('name', ''),
                    desc=card_data.get('desc', ''),
                    due=card_data.get('due', ''),
                    due_complete=card_data.get('dueComplete', False),
                    start=card_data.get('start', ''),
                    pos=card_data.get('pos', 0),
                    address=card_data.get('address', ''),
                    id_card_sources=card_data.get('idCardSources', []),
                    id_attachment_sheets=card_data.get('idAttachmentSheets', []),
                    coordinates=card_data.get('coordinates', ''),
                    creation_method=card_data.get('creation_method', ''),
                    creation_date=card_data.get('creation_date', ''),
                    data=card_data.get('data', {}),
                    date_last_activity=card_data.get('dateLastActivity', ''),
                    desc_data=card_data.get('descData', {}),
                    email=card_data.get('email', ''),
                    id_board_source=card_data.get('idBoardSource', ''),
                    id_chapter_source=card_data.get('idChapterSource', ''),
                    id_card_plugin_source=card_data.get('idCardPluginSource', []),
                    id_attachment_background=card_data.get('idAttachmentBackground', ''),
                    id_custom_fields=card_data.get('idCustomFields', []),
                    id_attachment_preview=card_data.get('idAttachmentPreview', ''),
                    url=card_data.get('url', ''),
                    short_url=card_data.get('shortUrl', ''),
                    short_link=card_data.get('shortLink', ''),
                    subscribed=card_data.get('subscribed', False),
                    badges=card_data.get('badges', {}),
                    custom_field_items=card_data.get('customFieldItems', []),
                    cover=card_data.get('cover', {}),
                    attachments=card_data.get('attachments', []),
                    check_item_states=card_data.get('checkItemStates', []),
                    checklists=card_data.get('checklists', []),
                    labels=card_data.get('labels', []),
                    id_plugin_data=card_data.get('idPluginData', []),
                    plugin_data=card_data.get('pluginData', []),
                    member_ids=card_data.get('member_ids', []),
                    members=card_data.get('members', []),
                    plugin_data_screens=card_data.get('pluginDataScreens', []),
                    plugin_data_with_screen=card_data.get('pluginDataWithScreen', []),
                    source=card_data.get('source', {}),
                    source_id=card_data.get('source_id', ''),
                    source_id_board=card_data.get('source_id_board', ''),
                    source_id_list=card_data.get('source_id_list', ''),
                    source_id_chapter=card_data.get('source_id_chapter', ''),
                    source_member=card_data.get('source_member', ''),
                    source_siblings=card_data.get('source_siblings', []),
                    source_parent=card_data.get('source_parent', {}),
                    source_list=card_data.get('source_list', {}),
                    source_board=card_data.get('source_board', ''),
                    source_channel=card_data.get('source_channel', ''),
                    source_channel_id=card_data.get('source_channel_id', ''),
                    source_teams=card_data.get('source_teams', []),
                    metadata={
                        'accessed_at': datetime.utcnow().isoformat(),
                        'source': 'trello_search'
                    }
                )
                cards.append(card)
            
            logger.info(f"Trello cards search completed: {len(cards)} results")
            return cards
            
        except Exception as e:
            logger.error(f"Error searching Trello cards: {e}")
            return []
    
    async def get_board_activities(self, board_id: str, limit: int = 50,
                                before: str = None, since: str = None) -> List[TrelloActivity]:
        """Get Trello board activities"""
        try:
            # Build parameters
            params = {
                'filter': 'all',
                'limit': limit,
                'before': before,
                'since': since,
                'display': 'true',
                'fields': 'all',
                'member_fields': 'all',
                'memberCreator_fields': 'all',
                'card_fields': 'all',
                'list_fields': 'all',
                'board_fields': 'all',
                'organization_fields': 'all',
                'cardPluginData_fields': 'all',
                'memberPluginData_fields': 'all',
                'organizationPluginData_fields': 'all',
                'boardPluginData_fields': 'all',
                'sticker_fields': 'all',
                'customFieldItem_fields': 'all',
                'member_customFieldItem_fields': 'all',
                'organization_customFieldItem_fields': 'all',
                'board_customFieldItem_fields': 'all'
            }
            
            # Make request
            result = await self._make_request('GET', f'boards/{board_id}/actions', params)
            
            if result.get('error'):
                return []
            
            # Create activity objects
            activities = []
            for activity_data in result:
                activity = TrelloActivity(
                    id=activity_data.get('id', ''),
                    id_member_author=activity_data.get('idMemberCreator', ''),
                    data=activity_data.get('data', {}),
                    type=activity_data.get('type', ''),
                    date=activity_data.get('date', ''),
                    member_creator=activity_data.get('memberCreator', {}),
                    member=activity_data.get('member', {}),
                    board=activity_data.get('board', {}),
                    card=activity_data.get('card', {}),
                    list=activity_data.get('list', {}),
                    organization=activity_data.get('organization', {}),
                    app=activity_data.get('app', {}),
                    display=activity_data.get('display', {}),
                    text=activity_data.get('text', ''),
                    translation_key=activity_data.get('translationKey', ''),
                    member_type=activity_data.get('member_type', ''),
                    member_level=activity_data.get('member_level', ''),
                    metadata={
                        'accessed_at': datetime.utcnow().isoformat(),
                        'source': 'trello_api'
                    }
                )
                activities.append(activity)
            
            logger.info(f"Trello board activities retrieved: {len(activities)}")
            return activities
            
        except Exception as e:
            logger.error(f"Error getting Trello board activities: {e}")
            return []
    
    def _clear_cache(self):
        """Clear all caches"""
        self.boards_cache.clear()
        self.cards_cache.clear()
        self.lists_cache.clear()
        self.members_cache.clear()
    
    def _clear_board_cache(self):
        """Clear board cache"""
        self.boards_cache.clear()
    
    def _clear_card_cache(self):
        """Clear card cache"""
        self.cards_cache.clear()
    
    def _clear_list_cache(self):
        """Clear list cache"""
        self.lists_cache.clear()
    
    def _clear_member_cache(self):
        """Clear member cache"""
        self.members_cache.clear()
    
    async def get_service_info(self) -> Dict[str, Any]:
        """Get service information"""
        return {
            "name": "Enhanced Trello Service",
            "version": "1.0.0",
            "description": "Complete Trello project management automation",
            "capabilities": [
                "board_management",
                "card_operations",
                "list_management",
                "member_management",
                "checklist_tracking",
                "label_management",
                "search_and_filtering",
                "activity_tracking",
                "webhook_support",
                "task_automation"
            ],
            "api_endpoints": [
                "/api/trello/enhanced/boards/list",
                "/api/trello/enhanced/boards/get",
                "/api/trello/enhanced/cards/list",
                "/api/trello/enhanced/cards/get",
                "/api/trello/enhanced/cards/create",
                "/api/trello/enhanced/cards/update",
                "/api/trello/enhanced/cards/delete",
                "/api/trello/enhanced/lists/get",
                "/api/trello/enhanced/members/list",
                "/api/trello/enhanced/checklists/create",
                "/api/trello/enhanced/labels/create",
                "/api/trello/enhanced/search/cards",
                "/api/trello/enhanced/activities/board",
                "/api/trello/enhanced/health"
            ],
            "label_colors": self.label_colors,
            "card_types": self.card_types,
            "initialized_at": datetime.utcnow().isoformat()
        }

# Create singleton instance
trello_enhanced_service = TrelloEnhancedService()