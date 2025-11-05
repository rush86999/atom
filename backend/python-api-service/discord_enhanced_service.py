"""
Enhanced Discord Service Implementation
Complete Discord integration with comprehensive server management and bot capabilities
"""

import os
import logging
import asyncio
import httpx
import json
import base64
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Union

# Import encryption utilities
try:
    from atom_encryption import decrypt_data, encrypt_data
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False

# Import database operations
try:
    from db_oauth_discord_complete import get_user_discord_tokens, get_discord_user
    DISCORD_DB_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Discord database operations not available: {e}")
    DISCORD_DB_AVAILABLE = False

# Discord API configuration
DISCORD_API_BASE_URL = "https://discord.com/api/v10"
DEFAULT_TIMEOUT = 30

# Configure logging
logger = logging.getLogger(__name__)

# Data model classes
class DiscordGuild:
    """Discord server/guild data model"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.name = data.get("name")
        self.icon_hash = data.get("icon")
        self.splash_hash = data.get("splash")
        self.discovery_splash_hash = data.get("discovery_splash")
        self.owner_id = data.get("owner_id")
        self.owner = data.get("owner")
        self.permissions = data.get("permissions")
        self.region = data.get("region")
        self.afk_channel_id = data.get("afk_channel_id")
        self.afk_timeout = data.get("afk_timeout")
        self.widget_enabled = data.get("widget_enabled")
        self.widget_channel_id = data.get("widget_channel_id")
        self.verification_level = data.get("verification_level")
        self.default_message_notifications = data.get("default_message_notifications")
        self.explicit_content_filter = data.get("explicit_content_filter")
        self.mfa_level = data.get("mfa_level")
        self.application_id = data.get("application_id")
        self.system_channel_id = data.get("system_channel_id")
        self.system_channel_flags = data.get("system_channel_flags")
        self.rules_channel_id = data.get("rules_channel_id")
        self.joined_at = data.get("joined_at")
        self.large = data.get("large")
        self.unavailable = data.get("unavailable")
        self.member_count = data.get("member_count")
        self.presence_count = data.get("presence_count")
        self.max_members = data.get("max_members")
        self.max_presences = data.get("max_presences")
        self.description = data.get("description", "")
        self.banner_hash = data.get("banner")
        self.premium_tier = data.get("premium_tier")
        self.premium_subscription_count = data.get("premium_subscription_count")
        self.vanity_url_code = data.get("vanity_url_code")
        self.preferred_locale = data.get("preferred_locale")
        self.public_updates_channel_id = data.get("public_updates_channel_id")
        self.approximate_member_count = data.get("approximate_member_count")
        self.approximate_presence_count = data.get("approximate_presence_count")
        self.features = data.get("features", [])
        self.channels = []
        self.roles = []
        self.emojis = []
        self.members = []
    
    def get_icon_url(self, size: int = 128) -> str:
        if not self.icon_hash:
            return ""
        return f"https://cdn.discordapp.com/icons/{self.id}/{self.icon_hash}.png?size={size}"
    
    def get_banner_url(self, size: int = 640) -> str:
        if not self.banner_hash:
            return ""
        return f"https://cdn.discordapp.com/banners/{self.id}/{self.banner_hash}.png?size={size}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'iconHash': self.icon_hash,
            'iconUrl': self.get_icon_url(),
            'splashHash': self.splash_hash,
            'ownerId': self.owner_id,
            'owner': self.owner,
            'permissions': self.permissions,
            'region': self.region,
            'joinedAt': self.joined_at,
            'large': self.large,
            'memberCount': self.member_count,
            'approximateMemberCount': self.approximate_member_count,
            'description': self.description,
            'bannerHash': self.banner_hash,
            'bannerUrl': self.get_banner_url(),
            'premiumTier': self.premium_tier,
            'premiumSubscriptionCount': self.premium_subscription_count,
            'vanityUrlCode': self.vanity_url_code,
            'preferredLocale': self.preferred_locale,
            'features': self.features,
            'channels': self.channels,
            'roles': self.roles,
            'emojis': self.emojis
        }

class DiscordChannel:
    """Discord channel data model"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.type = data.get("type")
        self.guild_id = data.get("guild_id")
        self.position = data.get("position", 0)
        self.permission_overwrites = data.get("permission_overwrites", [])
        self.name = data.get("name")
        self.topic = data.get("topic")
        self.nsfw = data.get("nsfw", False)
        self.last_message_id = data.get("last_message_id")
        self.bitrate = data.get("bitrate")
        self.user_limit = data.get("user_limit")
        self.rate_limit_per_user = data.get("rate_limit_per_user", 0)
        self.recipients = data.get("recipients", [])
        self.icon_hash = data.get("icon")
        self.owner_id = data.get("owner_id")
        self.application_id = data.get("application_id")
        self.parent_id = data.get("parent_id")
        self.last_pin_timestamp = data.get("last_pin_timestamp")
        self.rtc_region = data.get("rtc_region")
        self.video_quality_mode = data.get("video_quality_mode")
        self.message_count = data.get("message_count", 0)
        self.member_count = data.get("member_count", 0)
        self.default_auto_archive_duration = data.get("default_auto_archive_duration")
        self.permissions = data.get("permissions")
        self.flags = data.get("flags", 0)
    
    def get_type_name(self) -> str:
        type_names = {
            0: "Text",
            1: "DM",
            2: "Voice",
            3: "Group DM",
            4: "Category",
            5: "News",
            10: "News Thread",
            11: "Public Thread",
            12: "Private Thread",
            13: "Stage Voice"
        }
        return type_names.get(self.type, "Unknown")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'type': self.type,
            'typeName': self.get_type_name(),
            'guildId': self.guild_id,
            'position': self.position,
            'name': self.name,
            'topic': self.topic,
            'nsfw': self.nsfw,
            'lastMessageId': self.last_message_id,
            'bitrate': self.bitrate,
            'userLimit': self.user_limit,
            'rateLimitPerUser': self.rate_limit_per_user,
            'messageCount': self.message_count,
            'memberCount': self.member_count,
            'parentId': self.parent_id,
            'permissions': self.permissions,
            'ownerId': self.owner_id
        }

class DiscordMessage:
    """Discord message data model"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.channel_id = data.get("channel_id")
        self.guild_id = data.get("guild_id")
        self.author = data.get("author")
        self.member = data.get("member")
        self.content = data.get("content", "")
        self.timestamp = data.get("timestamp")
        self.edited_timestamp = data.get("edited_timestamp")
        self.tts = data.get("tts", False)
        self.mention_everyone = data.get("mention_everyone", False)
        self.mentions = data.get("mentions", [])
        self.mention_roles = data.get("mention_roles", [])
        self.mention_channels = data.get("mention_channels", [])
        self.attachments = data.get("attachments", [])
        self.embeds = data.get("embeds", [])
        self.reactions = data.get("reactions", [])
        self.nonce = data.get("nonce")
        self.pinned = data.get("pinned", False)
        self.webhook_id = data.get("webhook_id")
        self.type = data.get("type")
        self.activity = data.get("activity")
        self.application = data.get("application")
        self.application_id = data.get("application_id")
        self.message_reference = data.get("message_reference")
        self.flags = data.get("flags", 0)
        self.stickers = data.get("stickers", [])
        self.referenced_message = data.get("referenced_message")
        self.components = data.get("components", [])
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'channelId': self.channel_id,
            'guildId': self.guild_id,
            'author': self.author,
            'content': self.content,
            'timestamp': self.timestamp,
            'editedTimestamp': self.edited_timestamp,
            'tts': self.tts,
            'mentionEveryone': self.mention_everyone,
            'mentions': self.mentions,
            'mentionRoles': self.mention_roles,
            'attachments': self.attachments,
            'embeds': self.embeds,
            'reactions': self.reactions,
            'pinned': self.pinned,
            'type': self.type,
            'flags': self.flags
        }

class DiscordUser:
    """Discord user data model"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.username = data.get("username")
        self.discriminator = data.get("discriminator")
        self.global_name = data.get("global_name")
        self.display_name = data.get("display_name")
        self.avatar_hash = data.get("avatar")
        self.bot = data.get("bot", False)
        self.system = data.get("system", False)
        self.mfa_enabled = data.get("mfa_enabled")
        self.banner_hash = data.get("banner")
        self.accent_color = data.get("accent_color")
        self.locale = data.get("locale")
        self.email = data.get("email", "")
        self.verified = data.get("verified", False)
        self.flags = data.get("flags")
        self.premium_type = data.get("premium_type")
        self.public_flags = data.get("public_flags")
        self.avatar_url_decoration = data.get("avatar_url_decoration")
    
    def get_avatar_url(self, size: int = 128) -> str:
        if not self.avatar_hash:
            # Default avatar URL based on discriminator
            return f"https://cdn.discordapp.com/embed/avatars/{self.id}/{int(self.discriminator or '0')}.png?size={size}"
        return f"https://cdn.discordapp.com/avatars/{self.id}/{self.avatar_hash}.png?size={size}"
    
    def get_banner_url(self, size: int = 640) -> str:
        if not self.banner_hash:
            return ""
        return f"https://cdn.discordapp.com/banners/{self.id}/{self.banner_hash}.png?size={size}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'username': self.username,
            'discriminator': self.discriminator,
            'globalName': self.global_name,
            'displayName': self.display_name or self.global_name or self.username,
            'avatarHash': self.avatar_hash,
            'avatarUrl': self.get_avatar_url(),
            'bannerHash': self.banner_hash,
            'bannerUrl': self.get_banner_url(),
            'bot': self.bot,
            'system': self.system,
            'mfaEnabled': self.mfa_enabled,
            'accentColor': self.accent_color,
            'locale': self.locale,
            'email': self.email,
            'verified': self.verified,
            'flags': self.flags,
            'premiumType': self.premium_type,
            'publicFlags': self.public_flags
        }

class DiscordRole:
    """Discord role data model"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.name = data.get("name")
        self.color = data.get("color", 0)
        self.hoist = data.get("hoist", False)
        self.position = data.get("position", 0)
        self.managed = data.get("managed", False)
        self.mentionable = data.get("mentionable", False)
        self.icon_hash = data.get("icon")
        self.unicode_emoji = data.get("unicode_emoji")
        self.permissions = data.get("permissions", "0")
        self.flags = data.get("flags", 0)
    
    def get_color_hex(self) -> str:
        return f"#{self.color:06x}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'color': self.color,
            'colorHex': self.get_color_hex(),
            'hoist': self.hoist,
            'position': self.position,
            'managed': self.managed,
            'mentionable': self.mentionable,
            'iconHash': self.icon_hash,
            'unicodeEmoji': self.unicode_emoji,
            'permissions': self.permissions,
            'flags': self.flags
        }

class DiscordBot:
    """Discord bot data model"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.username = data.get("username")
        self.discriminator = data.get("discriminator")
        self.avatar_hash = data.get("avatar")
        self.code = data.get("code")
        self.redirect_uris = data.get("redirect_uris", [])
        self.applications = data.get("applications", [])
    
    def get_avatar_url(self, size: int = 128) -> str:
        if not self.avatar_hash:
            return f"https://cdn.discordapp.com/embed/avatars/{self.id}/{0}.png?size={size}"
        return f"https://cdn.discordapp.com/avatars/{self.id}/{self.avatar_hash}.png?size={size}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'username': self.username,
            'discriminator': self.discriminator,
            'avatarHash': self.avatar_hash,
            'avatarUrl': self.get_avatar_url(),
            'code': self.code,
            'redirectUris': self.redirect_uris,
            'applications': self.applications
        }

class DiscordService:
    """Enhanced Discord service class"""
    
    def __init__(self):
        self._mock_mode = True
        self.api_base_url = DISCORD_API_BASE_URL
        self.timeout = DEFAULT_TIMEOUT
        self._mock_db = {
            'guilds': [],
            'channels': [],
            'messages': [],
            'users': [],
            'roles': [],
            'bots': []
        }
        self._init_mock_data()
    
    def _init_mock_data(self):
        """Initialize mock data for testing"""
        # Mock user (authenticated user)
        self._mock_db['users'].append(DiscordUser({
            'id': 'user-123456789',
            'username': 'atom_bot_user',
            'discriminator': '1234',
            'global_name': 'ATOM Bot User',
            'display_name': 'ATOM Bot',
            'avatar': 'mock_avatar_hash',
            'bot': False,
            'verified': True,
            'email': 'atomuser@example.com',
            'locale': 'en-US'
        }))
        
        # Mock guilds (servers)
        self._mock_db['guilds'].extend([
            DiscordGuild({
                'id': 'guild-987654321',
                'name': 'ATOM Development',
                'icon': 'mock_guild_icon_1',
                'banner': 'mock_guild_banner_1',
                'owner_id': 'user-123456789',
                'permissions': '2147483647',
                'description': 'Main ATOM development server',
                'region': 'us-east',
                'joined_at': datetime.utcnow().isoformat() + 'Z',
                'large': True,
                'member_count': 150,
                'approximate_member_count': 150,
                'premium_tier': 2,
                'features': ['COMMUNITY', 'NEWS', 'WELCOME_SCREEN_ENABLED'],
                'preferred_locale': 'en-US'
            }),
            DiscordGuild({
                'id': 'guild-987654322',
                'name': 'AI Chatbots',
                'icon': 'mock_guild_icon_2',
                'owner_id': 'other-user-id',
                'permissions': '68608',
                'description': 'Server for AI chatbot discussions',
                'region': 'us-west',
                'joined_at': datetime.utcnow().isoformat() + 'Z',
                'large': True,
                'member_count': 5000,
                'approximate_member_count': 5000,
                'premium_tier': 3,
                'features': ['COMMUNITY', 'NEWS', 'WELCOME_SCREEN_ENABLED', 'MEMBER_VERIFICATION_GATE_ENABLED'],
                'preferred_locale': 'en-US'
            })
        ])
        
        # Mock channels
        self._mock_db['channels'].extend([
            DiscordChannel({
                'id': 'channel-111111111',
                'type': 0,  # Text
                'guild_id': 'guild-987654321',
                'name': 'general',
                'topic': 'General discussion and announcements',
                'position': 0,
                'permission_overwrites': [],
                'nsfw': False,
                'rate_limit_per_user': 0,
                'parent_id': None
            }),
            DiscordChannel({
                'id': 'channel-111111112',
                'type': 0,  # Text
                'guild_id': 'guild-987654321',
                'name': 'development',
                'topic': 'Development discussions and code sharing',
                'position': 1,
                'permission_overwrites': [],
                'nsfw': False,
                'rate_limit_per_user': 0,
                'parent_id': None
            }),
            DiscordChannel({
                'id': 'channel-111111113',
                'type': 2,  # Voice
                'guild_id': 'guild-987654321',
                'name': 'Voice General',
                'position': 2,
                'permission_overwrites': [],
                'bitrate': 64000,
                'user_limit': 99
            }),
            DiscordChannel({
                'id': 'channel-111111114',
                'type': 0,  # Text
                'guild_id': 'guild-987654322',
                'name': 'ai-chat',
                'topic': 'General AI chat discussions',
                'position': 0,
                'permission_overwrites': [],
                'nsfw': False,
                'rate_limit_per_user': 0,
                'parent_id': None
            })
        ])
        
        # Mock roles
        self._mock_db['roles'].extend([
            DiscordRole({
                'id': 'role-111111111',
                'name': 'Admin',
                'color': 16711680,  # Red
                'hoist': True,
                'position': 10,
                'permissions': '8',
                'mentionable': True
            }),
            DiscordRole({
                'id': 'role-111111112',
                'name': 'Developer',
                'color': 65280,  # Green
                'hoist': False,
                'position': 5,
                'permissions': '2147483647',
                'mentionable': True
            }),
            DiscordRole({
                'id': 'role-111111113',
                'name': 'Member',
                'color': 8421504,  # Gray
                'hoist': False,
                'position': 0,
                'permissions': '68608',
                'mentionable': False
            })
        ])
        
        # Mock messages
        now = datetime.utcnow()
        for i in range(10):
            message_data = {
                'id': f'msg-{1000000 + i}',
                'channel_id': 'channel-111111111',
                'guild_id': 'guild-987654321',
                'author': {
                    'id': f'user-{2000000 + i}',
                    'username': f'User{i + 1}',
                    'discriminator': f'{i:04d}',
                    'display_name': f'Test User {i + 1}',
                    'avatar': f'avatar_hash_{i}'
                },
                'content': f'This is test message {i + 1} in the general channel. Some example content for testing purposes.',
                'timestamp': (now - timedelta(hours=i)).isoformat() + 'Z',
                'edited_timestamp': None,
                'tts': False,
                'mention_everyone': False,
                'mentions': [],
                'mention_roles': [],
                'attachments': [],
                'embeds': [],
                'reactions': [],
                'pinned': i == 0,
                'type': 0,
                'flags': 0
            }
            
            self._mock_db['messages'].append(DiscordMessage(message_data))
    
    def set_mock_mode(self, enabled: bool):
        """Set mock mode for testing"""
        self._mock_mode = enabled
        if enabled:
            self._init_mock_data()
    
    async def _get_user_access_token(self, user_id: str) -> Optional[str]:
        """Get access token for user"""
        if self._mock_mode:
            return os.getenv('DISCORD_ACCESS_TOKEN', 'mock_discord_token')
        
        # In real implementation, this would fetch from database
        if DISCORD_DB_AVAILABLE:
            tokens = await get_user_discord_tokens(None, user_id)
            if tokens:
                access_token = tokens.get('access_token', '')
                if ENCRYPTION_AVAILABLE and isinstance(access_token, bytes):
                    access_token = decrypt_data(access_token, os.getenv('ATOM_OAUTH_ENCRYPTION_KEY'))
                return access_token
        return None
    
    async def _get_bot_token(self) -> Optional[str]:
        """Get bot token"""
        if self._mock_mode:
            return os.getenv('DISCORD_BOT_TOKEN', 'mock_bot_token')
        
        # In real implementation, this would fetch from environment/config
        return os.getenv('DISCORD_BOT_TOKEN')
    
    async def _make_api_request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None,
                             data: Optional[Dict[str, Any]] = None, files: Optional[Dict[str, Any]] = None,
                             access_token: Optional[str] = None, bot_token: Optional[str] = None) -> Dict[str, Any]:
        """Make API request to Discord"""
        if self._mock_mode:
            return await self._make_mock_request(method, endpoint, params, data, files)
        
        try:
            # Determine which token to use
            token = bot_token or access_token
            if not token:
                raise ValueError("No access token or bot token provided")
            
            headers = {
                'Authorization': f'Bot {token}' if bot_token else f'Bearer {token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.api_base_url}/{endpoint.lstrip('/')}"
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if method.upper() == 'GET':
                    response = await client.get(url, headers=headers, params=params)
                elif method.upper() == 'POST':
                    if files:
                        # For file uploads, don't set content-type manually
                        headers.pop('Content-Type', None)
                        response = await client.post(url, headers=headers, data=data, files=files)
                    else:
                        response = await client.post(url, headers=headers, json=data)
                elif method.upper() == 'PUT':
                    response = await client.put(url, headers=headers, json=data)
                elif method.upper() == 'DELETE':
                    response = await client.delete(url, headers=headers, params=params)
                elif method.upper() == 'PATCH':
                    response = await client.patch(url, headers=headers, json=data)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                # Discord returns 204 for some successful operations
                if response.status_code == 204:
                    return {'success': True}
                
                response.raise_for_status()
                
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {'success': True, 'response': response.text}
                
        except httpx.HTTPError as e:
            logger.error(f"Discord API request error: {e}")
            return {'error': str(e)}
        except Exception as e:
            logger.error(f"Unexpected Discord API request error: {e}")
            return {'error': str(e)}
    
    async def _make_mock_request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None,
                               data: Optional[Dict[str, Any]] = None, files: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make mock API request"""
        # Simulate network delay
        await asyncio.sleep(0.1)
        
        endpoint = endpoint.lower()
        
        # Mock user operations
        if 'users/@me' in endpoint and 'GET' in method.upper():
            user = self._mock_db['users'][0] if self._mock_db['users'] else None
            return user.to_dict() if user else {'error': 'User not found'}
        
        elif 'users/@me/guilds' in endpoint and 'GET' in method.upper():
            return [guild.to_dict() for guild in self._mock_db['guilds']]
        
        # Mock guild operations
        elif 'guilds/' in endpoint and 'GET' in method.upper():
            # Get specific guild
            guild_id = endpoint.split('/')[-1].split('?')[0]
            guild = next((g for g in self._mock_db['guilds'] if g.id == guild_id), None)
            
            if guild:
                guild_data = guild.to_dict()
                # Add channels and roles
                guild_data['channels'] = [ch.to_dict() for ch in self._mock_db['channels'] if ch.guild_id == guild_id]
                guild_data['roles'] = [role.to_dict() for role in self._mock_db['roles']]
                return guild_data
            return {'error': 'Guild not found'}
        
        # Mock channel operations
        elif 'channels/' in endpoint:
            if 'GET' in method.upper():
                # Get channel
                channel_id = endpoint.split('/')[-1].split('?')[0]
                channel = next((ch for ch in self._mock_db['channels'] if ch.id == channel_id), None)
                return channel.to_dict() if channel else {'error': 'Channel not found'}
            
            elif 'POST' in method.upper():
                # Create channel
                if not data:
                    return {'error': 'Channel data is required'}
                
                channel_data = {
                    'id': f'channel-{hash(data.get("name", ""))}',
                    'type': data.get('type', 0),
                    'guild_id': data.get('guild_id'),
                    'name': data.get('name'),
                    'topic': data.get('topic', ''),
                    'position': data.get('position', 0)
                }
                
                new_channel = DiscordChannel(channel_data)
                self._mock_db['channels'].append(new_channel)
                
                return {
                    'id': new_channel.id,
                    'name': new_channel.name,
                    'type': new_channel.type,
                    'topic': new_channel.topic
                }
        
        elif 'channels/' in endpoint and 'messages' in endpoint:
            if 'GET' in method.upper():
                # Get channel messages
                channel_id = endpoint.split('/')[2]
                limit = params.get('limit', 50) if params else 50
                
                messages = [msg.to_dict() for msg in self._mock_db['messages']
                           if msg.channel_id == channel_id]
                
                # Apply limit
                messages = messages[:limit]
                
                return messages
            elif 'POST' in method.upper():
                # Send message
                if not data or not data.get('content'):
                    return {'error': 'Message content is required'}
                
                message_data = {
                    'id': f'msg-{hash(data.get("content", ""))}',
                    'channel_id': data.get('channel_id'),
                    'guild_id': data.get('guild_id'),
                    'author': self._mock_db['users'][0].to_dict(),
                    'content': data.get('content'),
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'edited_timestamp': None,
                    'tts': data.get('tts', False),
                    'mention_everyone': data.get('mention_everyone', False),
                    'mentions': data.get('mentions', []),
                    'mention_roles': data.get('mention_roles', []),
                    'attachments': data.get('attachments', []),
                    'embeds': data.get('embeds', []),
                    'reactions': [],
                    'pinned': False,
                    'type': 0,
                    'flags': 0
                }
                
                new_message = DiscordMessage(message_data)
                self._mock_db['messages'].append(new_message)
                
                return new_message.to_dict()
        
        # Mock bot operations
        elif 'applications/@me' in endpoint and 'GET' in method.upper():
            bot_data = {
                'id': os.getenv('DISCORD_BOT_ID', 'mock_bot_id'),
                'name': os.getenv('DISCORD_BOT_NAME', 'ATOM Bot'),
                'description': 'Advanced ATOM integration bot',
                'icon': 'mock_bot_icon',
                'owner': {'id': 'user-123456789'},
                'team': None,
                'redirect_uris': [os.getenv('DISCORD_REDIRECT_URI', 'http://localhost:3000/discord/callback')],
                'rpc_origins': [],
                'bot_public': True,
                'bot_require_code_grant': False,
                'bot': {
                    'id': os.getenv('DISCORD_BOT_ID', 'mock_bot_id'),
                    'username': os.getenv('DISCORD_BOT_NAME', 'ATOM Bot'),
                    'discriminator': '0001',
                    'avatar': 'mock_bot_avatar',
                    'token': bot_token or 'mock_bot_token',
                    'permissions': '8',  # Administrator
                    'public_flags': 0
                }
            }
            return bot_data
        
        # Default mock response
        return {
            'mock_response': True,
            'endpoint': endpoint,
            'method': method,
            'params': params,
            'data': data
        }
    
    # User operations
    async def get_current_user(self, user_id: str) -> Optional[DiscordUser]:
        """Get current authenticated user"""
        try:
            access_token = await self._get_user_access_token(user_id)
            
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return None
            
            response = await self._make_api_request('GET', 'users/@me', access_token=access_token)
            
            if response and not response.get('error'):
                return DiscordUser(response)
            else:
                logger.error(f"Error getting Discord user: {response.get('error')}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error getting Discord user: {e}")
            return None
    
    # Guild operations
    async def get_user_guilds(self, user_id: str, limit: int = 100, before: Optional[str] = None,
                            after: Optional[str] = None) -> List[DiscordGuild]:
        """Get guilds (servers) for user"""
        try:
            access_token = await self._get_user_access_token(user_id)
            
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return []
            
            params = {
                'limit': min(limit, 200)
            }
            
            if before:
                params['before'] = before
            if after:
                params['after'] = after
            
            response = await self._make_api_request('GET', 'users/@me/guilds', 
                                                params=params, access_token=access_token)
            
            if response and isinstance(response, list):
                return [DiscordGuild(guild) for guild in response]
            else:
                logger.error(f"Error getting Discord guilds: {response.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"Unexpected error getting Discord guilds: {e}")
            return []
    
    async def get_guild_info(self, user_id: str, guild_id: str) -> Optional[DiscordGuild]:
        """Get detailed information about a guild"""
        try:
            access_token = await self._get_user_access_token(user_id)
            
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return None
            
            response = await self._make_api_request('GET', f'guilds/{guild_id}', 
                                                access_token=access_token)
            
            if response and not response.get('error'):
                return DiscordGuild(response)
            else:
                logger.error(f"Error getting Discord guild: {response.get('error')}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error getting Discord guild: {e}")
            return None
    
    # Channel operations
    async def get_guild_channels(self, user_id: str, guild_id: str) -> List[DiscordChannel]:
        """Get channels for a guild"""
        try:
            access_token = await self._get_user_access_token(user_id)
            
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return []
            
            response = await self._make_api_request('GET', f'guilds/{guild_id}/channels', 
                                                access_token=access_token)
            
            if response and isinstance(response, list):
                return [DiscordChannel(channel) for channel in response]
            else:
                logger.error(f"Error getting Discord channels: {response.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"Unexpected error getting Discord channels: {e}")
            return []
    
    async def create_channel(self, user_id: str, guild_id: str, name: str, 
                          channel_type: int = 0, topic: str = "", position: int = 0,
                          permission_overwrites: List[Dict] = None) -> Optional[DiscordChannel]:
        """Create a new channel in a guild"""
        try:
            access_token = await self._get_user_access_token(user_id)
            
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return None
            
            data = {
                'name': name,
                'type': channel_type,
                'topic': topic,
                'position': position,
                'permission_overwrites': permission_overwrites or []
            }
            
            response = await self._make_api_request('POST', f'guilds/{guild_id}/channels', 
                                                data=data, access_token=access_token)
            
            if response and not response.get('error'):
                return DiscordChannel(response)
            else:
                logger.error(f"Error creating Discord channel: {response.get('error')}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error creating Discord channel: {e}")
            return None
    
    # Message operations
    async def get_channel_messages(self, user_id: str, channel_id: str, limit: int = 50,
                               before: Optional[str] = None, after: Optional[str] = None) -> List[DiscordMessage]:
        """Get messages from a channel"""
        try:
            access_token = await self._get_user_access_token(user_id)
            
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return []
            
            params = {
                'limit': min(limit, 100)
            }
            
            if before:
                params['before'] = before
            if after:
                params['after'] = after
            
            response = await self._make_api_request('GET', f'channels/{channel_id}/messages', 
                                                params=params, access_token=access_token)
            
            if response and isinstance(response, list):
                return [DiscordMessage(message) for message in response]
            else:
                logger.error(f"Error getting Discord messages: {response.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"Unexpected error getting Discord messages: {e}")
            return []
    
    async def send_message(self, user_id: str, channel_id: str, content: str,
                        embeds: List[Dict] = None, tts: bool = False, 
                        allowed_mentions: Dict = None, message_reference: Dict = None) -> Optional[DiscordMessage]:
        """Send a message to a channel"""
        try:
            access_token = await self._get_user_access_token(user_id)
            
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return None
            
            data = {
                'content': content,
                'tts': tts,
                'embeds': embeds or [],
                'allowed_mentions': allowed_mentions or {},
                'message_reference': message_reference or {}
            }
            
            response = await self._make_api_request('POST', f'channels/{channel_id}/messages', 
                                                data=data, access_token=access_token)
            
            if response and not response.get('error'):
                return DiscordMessage(response)
            else:
                logger.error(f"Error sending Discord message: {response.get('error')}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error sending Discord message: {e}")
            return None
    
    # Bot operations
    async def get_bot_info(self, bot_token: Optional[str] = None) -> Optional[DiscordBot]:
        """Get bot application information"""
        try:
            token = bot_token or await self._get_bot_token()
            
            if not token:
                logger.error("No bot token found")
                return None
            
            response = await self._make_api_request('GET', 'applications/@me', bot_token=token)
            
            if response and not response.get('error'):
                return DiscordBot(response)
            else:
                logger.error(f"Error getting Discord bot info: {response.get('error')}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error getting Discord bot info: {e}")
            return None
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get service information"""
        return {
            'name': 'Enhanced Discord Service',
            'version': '2.0.0',
            'mock_mode': self._mock_mode,
            'api_base_url': self.api_base_url,
            'timeout': self.timeout,
            'capabilities': [
                'Get current user',
                'List user guilds',
                'Get guild information',
                'List guild channels',
                'Create channels',
                'Get channel messages',
                'Send messages',
                'Bot management',
                'User management'
            ]
        }

# Create singleton instance
discord_enhanced_service = DiscordService()